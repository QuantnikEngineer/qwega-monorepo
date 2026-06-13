"""
AWS CloudWatch monitoring adapter implementation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import (
    BaseMonitoringAdapter,
    AlertData,
    AlertSeverity,
    MetricSeries,
    MetricDataPoint,
    MetricType,
    HistoricalAlert
)


class CloudWatchAdapter(BaseMonitoringAdapter):
    """AWS CloudWatch monitoring adapter."""
    
    def __init__(self, api_key: str = None, app_key: str = None, **kwargs):
        super().__init__(api_key, app_key, **kwargs)
        self.region = kwargs.get("aws_region", "us-east-1")
        self._cw_client = None
        self._sns_client = None
    
    @property
    def adapter_name(self) -> str:
        return "cloudwatch"
    
    def _get_cloudwatch_client(self):
        """Get or create CloudWatch client."""
        if self._cw_client is None:
            import boto3
            self._cw_client = boto3.client("cloudwatch", region_name=self.region)
        return self._cw_client
    
    def parse_webhook(self, payload: Dict[str, Any]) -> AlertData:
        """Parse SNS/CloudWatch alarm webhook payload."""
        
        # CloudWatch sends via SNS, payload might be in "Message" as JSON string
        message = payload
        if "Message" in payload:
            import json
            try:
                message = json.loads(payload["Message"])
            except (json.JSONDecodeError, TypeError):
                message = payload
        
        # Map CloudWatch alarm states to severity
        state = message.get("NewStateValue", "ALARM")
        severity_map = {
            "ALARM": AlertSeverity.CRITICAL,
            "INSUFFICIENT_DATA": AlertSeverity.MEDIUM,
            "OK": AlertSeverity.INFO,
        }
        
        # Extract dimensions
        trigger = message.get("Trigger", {})
        dimensions = {d["name"]: d["value"] for d in trigger.get("Dimensions", [])}
        
        # Get metric value from state reason
        value = 0.0
        state_reason = message.get("NewStateReason", "")
        import re
        match = re.search(r"\[([\d.]+)\]", state_reason)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                pass
        
        return AlertData(
            alert_id=message.get("AlarmArn") or message.get("AlarmName", "unknown"),
            title=message.get("AlarmName", "CloudWatch Alarm"),
            message=message.get("AlarmDescription") or state_reason,
            severity=severity_map.get(state, AlertSeverity.MEDIUM),
            status="triggered" if state == "ALARM" else state.lower(),
            metric_name=trigger.get("MetricName", "unknown"),
            metric_value=value,
            threshold=trigger.get("Threshold"),
            hostname=dimensions.get("InstanceId") or dimensions.get("ClusterName"),
            pod_name=dimensions.get("PodName"),
            namespace=dimensions.get("Namespace") or trigger.get("Namespace"),
            deployment=dimensions.get("Deployment"),
            timestamp=datetime.fromisoformat(
                message.get("StateChangeTime", datetime.now().isoformat()).replace("Z", "+00:00")
            ),
            tags=dimensions,
            raw_payload=payload
        )
    
    async def fetch_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
        tags: Optional[Dict[str, str]] = None
    ) -> MetricSeries:
        """Fetch metrics from CloudWatch."""
        
        client = self._get_cloudwatch_client()
        
        # Parse metric_query format: "Namespace/MetricName"
        parts = metric_query.split("/")
        namespace = parts[0] if len(parts) > 1 else "AWS/EC2"
        metric_name = parts[-1]
        
        # Build dimensions from tags
        dimensions = []
        if tags:
            dimensions = [{"Name": k, "Value": v} for k, v in tags.items()]
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=["Average", "Maximum"]
            )
        )
        
        data_points = []
        for dp in sorted(response.get("Datapoints", []), key=lambda x: x["Timestamp"]):
            data_points.append(MetricDataPoint(
                timestamp=dp["Timestamp"],
                value=dp.get("Average", dp.get("Maximum", 0))
            ))
        
        return MetricSeries(
            metric_name=metric_query,
            metric_type=MetricType.CUSTOM,
            data_points=data_points,
            unit=response.get("Label", "")
        )
    
    async def fetch_cpu_metrics(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime,
        namespace: Optional[str] = None
    ) -> MetricSeries:
        """Fetch CPU metrics for a target."""
        
        if namespace:
            # EKS Container Insights
            query = "ContainerInsights/pod_cpu_utilization"
            tags = {"ClusterName": target, "Namespace": namespace}
        else:
            # EC2 instance
            query = "AWS/EC2/CPUUtilization"
            tags = {"InstanceId": target}
        
        series = await self.fetch_metrics(query, start_time, end_time, tags)
        series.metric_type = MetricType.CPU
        series.unit = "percent"
        return series
    
    async def fetch_memory_metrics(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime,
        namespace: Optional[str] = None
    ) -> MetricSeries:
        """Fetch memory metrics for a target."""
        
        if namespace:
            query = "ContainerInsights/pod_memory_utilization"
            tags = {"ClusterName": target, "Namespace": namespace}
        else:
            # Requires CloudWatch agent for memory metrics
            query = "CWAgent/mem_used_percent"
            tags = {"InstanceId": target}
        
        series = await self.fetch_metrics(query, start_time, end_time, tags)
        series.metric_type = MetricType.MEMORY
        series.unit = "percent"
        return series
    
    async def fetch_historical_alerts(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalAlert]:
        """Fetch alarm history from CloudWatch."""
        
        client = self._get_cloudwatch_client()
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.describe_alarm_history(
                AlarmTypes=["MetricAlarm"],
                HistoryItemType="StateUpdate",
                StartDate=start_time,
                EndDate=end_time,
                MaxRecords=100
            )
        )
        
        alerts = []
        for item in response.get("AlarmHistoryItems", []):
            import json
            try:
                data = json.loads(item.get("HistoryData", "{}"))
            except json.JSONDecodeError:
                data = {}
            
            new_state = data.get("newState", {}).get("stateValue", "UNKNOWN")
            severity_map = {
                "ALARM": AlertSeverity.CRITICAL,
                "INSUFFICIENT_DATA": AlertSeverity.MEDIUM,
                "OK": AlertSeverity.INFO,
            }
            
            alerts.append(HistoricalAlert(
                alert_id=item.get("AlarmName", ""),
                title=item.get("AlarmName", ""),
                timestamp=item.get("Timestamp", datetime.now()),
                severity=severity_map.get(new_state, AlertSeverity.MEDIUM),
                status=new_state.lower()
            ))
        
        return alerts
    
    async def health_check(self) -> bool:
        """Check CloudWatch accessibility."""
        try:
            client = self._get_cloudwatch_client()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.list_metrics(Limit=1)
            )
            return True
        except Exception:
            return False
