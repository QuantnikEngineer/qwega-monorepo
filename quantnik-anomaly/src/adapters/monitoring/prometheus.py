"""
Prometheus monitoring adapter implementation.
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


class PrometheusAdapter(BaseMonitoringAdapter):
    """Prometheus monitoring adapter."""
    
    def __init__(self, api_key: str = None, app_key: str = None, **kwargs):
        super().__init__(api_key, app_key, **kwargs)
        self.base_url = kwargs.get("prometheus_url", "http://prometheus:9090")
        self.alertmanager_url = kwargs.get("alertmanager_url", "http://alertmanager:9093")
    
    @property
    def adapter_name(self) -> str:
        return "prometheus"
    
    def parse_webhook(self, payload: Dict[str, Any]) -> AlertData:
        """Parse Alertmanager webhook payload."""
        
        # Alertmanager sends alerts in "alerts" array
        alerts = payload.get("alerts", [payload])
        alert = alerts[0] if alerts else payload
        
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        
        # Map severity
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "warning": AlertSeverity.MEDIUM,
            "info": AlertSeverity.INFO,
        }
        severity = severity_map.get(
            labels.get("severity", "warning").lower(),
            AlertSeverity.MEDIUM
        )
        
        # Extract metric value from annotation or label
        value = 0.0
        value_str = annotations.get("value") or labels.get("value", "0")
        try:
            value = float(value_str)
        except ValueError:
            pass
        
        return AlertData(
            alert_id=alert.get("fingerprint", labels.get("alertname", "unknown")),
            title=labels.get("alertname", "Prometheus Alert"),
            message=annotations.get("description") or annotations.get("summary", ""),
            severity=severity,
            status=alert.get("status", "firing"),
            metric_name=labels.get("__name__") or labels.get("alertname", "unknown"),
            metric_value=value,
            threshold=None,
            hostname=labels.get("instance") or labels.get("node"),
            pod_name=labels.get("pod"),
            namespace=labels.get("namespace"),
            deployment=labels.get("deployment"),
            timestamp=datetime.fromisoformat(
                alert.get("startsAt", datetime.now().isoformat()).replace("Z", "+00:00")
            ),
            tags=labels,
            raw_payload=payload
        )
    
    async def fetch_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
        tags: Optional[Dict[str, str]] = None
    ) -> MetricSeries:
        """Fetch metrics from Prometheus."""
        
        # Add label selectors if tags provided
        query = metric_query
        if tags:
            label_str = ",".join(f'{k}="{v}"' for k, v in tags.items())
            if "{" in query:
                query = query.replace("}", f",{label_str}}}")
            else:
                query = f"{query}{{{label_str}}}"
        
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start_time.timestamp(),
            "end": end_time.timestamp(),
            "step": "60"  # 1 minute resolution
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        data_points = []
        if data.get("status") == "success":
            results = data.get("data", {}).get("result", [])
            if results:
                for ts, value in results[0].get("values", []):
                    try:
                        data_points.append(MetricDataPoint(
                            timestamp=datetime.fromtimestamp(ts),
                            value=float(value),
                            tags=results[0].get("metric", {})
                        ))
                    except (ValueError, TypeError):
                        continue
        
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
        
        if namespace:
            # Kubernetes pod CPU
            query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{target}.*"}}[5m])) * 100'
        else:
            # Node CPU
            query = f'100 - (avg(rate(node_cpu_seconds_total{{mode="idle",instance=~"{target}.*"}}[5m])) * 100)'
        
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
            query = f'sum(container_memory_usage_bytes{{namespace="{namespace}",pod=~"{target}.*"}}) / sum(container_spec_memory_limit_bytes{{namespace="{namespace}",pod=~"{target}.*"}}) * 100'
        else:
            query = f'(1 - (node_memory_MemAvailable_bytes{{instance=~"{target}.*"}} / node_memory_MemTotal_bytes{{instance=~"{target}.*"}})) * 100'
        
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
        """Fetch historical alerts from Alertmanager."""
        
        url = f"{self.alertmanager_url}/api/v2/alerts"
        params = {
            "filter": f'instance=~"{target}.*"'
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception:
            return []
        
        alerts = []
        for alert in data:
            labels = alert.get("labels", {})
            severity_map = {
                "critical": AlertSeverity.CRITICAL,
                "high": AlertSeverity.HIGH,
                "warning": AlertSeverity.MEDIUM,
            }
            alerts.append(HistoricalAlert(
                alert_id=alert.get("fingerprint", ""),
                title=labels.get("alertname", ""),
                timestamp=datetime.fromisoformat(
                    alert.get("startsAt", datetime.now().isoformat()).replace("Z", "+00:00")
                ),
                severity=severity_map.get(labels.get("severity", "warning"), AlertSeverity.MEDIUM),
                status=alert.get("status", {}).get("state", "unknown")
            ))
        
        return alerts
    
    async def health_check(self) -> bool:
        """Check Prometheus accessibility."""
        try:
            url = f"{self.base_url}/-/healthy"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
