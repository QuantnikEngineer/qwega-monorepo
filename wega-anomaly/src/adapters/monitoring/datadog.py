"""
Datadog monitoring adapter implementation.
"""

import httpx
from datetime import datetime
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


class DatadogAdapter(BaseMonitoringAdapter):
    """Datadog monitoring adapter."""
    
    API_BASE = "https://api.datadoghq.com/api/v1"
    
    @property
    def adapter_name(self) -> str:
        return "datadog"
    
    def parse_webhook(self, payload: Dict[str, Any]) -> AlertData:
        """Parse Datadog webhook payload."""
        
        # Extract severity from alert type or priority
        severity_map = {
            "error": AlertSeverity.CRITICAL,
            "warning": AlertSeverity.HIGH,
            "info": AlertSeverity.LOW,
        }
        alert_type = payload.get("alert_type", "info")
        severity = severity_map.get(alert_type, AlertSeverity.MEDIUM)
        
        # Parse metric value
        value = payload.get("alert_value") or payload.get("value", 0)
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = 0.0
        
        # Normalize 0-1 to percentage if needed
        if 0 <= value <= 1:
            value = value * 100
        
        return AlertData(
            alert_id=str(payload.get("alert_id") or payload.get("id") or payload.get("monitor_id", "unknown")),
            title=payload.get("title") or payload.get("event_title") or payload.get("message", "Datadog Alert"),
            message=payload.get("text_only_msg") or payload.get("body", ""),
            severity=severity,
            status=payload.get("alert_transition") or payload.get("alert_status") or payload.get("status", "triggered"),
            metric_name=payload.get("alert_metric") or payload.get("metric") or payload.get("alert_query", "unknown"),
            metric_value=value,
            threshold=payload.get("threshold"),
            hostname=payload.get("hostname") or payload.get("host"),
            pod_name=payload.get("pod_name") or payload.get("pod"),
            namespace=payload.get("kube_namespace"),
            deployment=payload.get("kube_deployment"),
            timestamp=datetime.now(),
            tags=self._parse_tags(payload.get("tags", "")),
            raw_payload=payload
        )
    
    def _parse_tags(self, tags: Any) -> Dict[str, str]:
        """Parse Datadog tags into dict."""
        result = {}
        if isinstance(tags, str):
            for tag in tags.split(","):
                if ":" in tag:
                    k, v = tag.split(":", 1)
                    result[k.strip()] = v.strip()
        elif isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and ":" in tag:
                    k, v = tag.split(":", 1)
                    result[k.strip()] = v.strip()
        return result
    
    async def fetch_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
        tags: Optional[Dict[str, str]] = None
    ) -> MetricSeries:
        """Fetch metrics from Datadog."""
        
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        # Build query with tags if provided
        query = metric_query
        if tags:
            tag_str = ",".join(f"{k}:{v}" for k, v in tags.items())
            if "{" in query:
                query = query.replace("}", f",{tag_str}}}")
            else:
                query = f"{query}{{{tag_str}}}"
        
        url = f"{self.API_BASE}/query"
        params = {
            "from": start_ts,
            "to": end_ts,
            "query": query
        }
        
        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key or ""
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        data_points = []
        if "series" in data and data["series"]:
            series = data["series"][0]
            for point in series.get("pointlist", []):
                if len(point) >= 2 and point[1] is not None:
                    data_points.append(MetricDataPoint(
                        timestamp=datetime.fromtimestamp(point[0] / 1000),
                        value=point[1]
                    ))
        
        return MetricSeries(
            metric_name=metric_query,
            metric_type=MetricType.CUSTOM,
            data_points=data_points
        )
    
    async def fetch_cpu_metrics(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime,
        namespace: Optional[str] = None
    ) -> MetricSeries:
        """Fetch CPU metrics for a target."""
        
        # For Kubernetes pods
        if namespace:
            query = f"max:kubernetes.cpu.usage.total{{kube_namespace:{namespace},kube_deployment:{target}}}"
        else:
            query = f"avg:system.cpu.user{{host:{target}}}"
        
        series = await self.fetch_metrics(query, start_time, end_time)
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
            query = f"max:kubernetes.memory.usage{{kube_namespace:{namespace},kube_deployment:{target}}}"
        else:
            query = f"avg:system.mem.pct_usable{{host:{target}}}"
        
        series = await self.fetch_metrics(query, start_time, end_time)
        series.metric_type = MetricType.MEMORY
        series.unit = "percent"
        return series
    
    async def fetch_historical_alerts(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalAlert]:
        """Fetch historical alerts from Datadog."""
        
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        url = f"{self.API_BASE}/events"
        params = {
            "start": start_ts,
            "end": end_ts,
            "tags": f"host:{target}",
            "sources": "alert"
        }
        
        headers = {
            "DD-API-KEY": self.api_key,
            "DD-APPLICATION-KEY": self.app_key or ""
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        alerts = []
        for event in data.get("events", []):
            severity_map = {
                "error": AlertSeverity.CRITICAL,
                "warning": AlertSeverity.HIGH,
                "info": AlertSeverity.LOW,
            }
            alerts.append(HistoricalAlert(
                alert_id=str(event.get("id", "")),
                title=event.get("title", ""),
                timestamp=datetime.fromtimestamp(event.get("date_happened", 0)),
                severity=severity_map.get(event.get("alert_type", "info"), AlertSeverity.MEDIUM),
                status=event.get("alert_status", "unknown")
            ))
        
        return alerts
    
    async def health_check(self) -> bool:
        """Check Datadog API accessibility."""
        try:
            url = f"{self.API_BASE}/validate"
            headers = {
                "DD-API-KEY": self.api_key,
                "DD-APPLICATION-KEY": self.app_key or ""
            }
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception:
            return False
