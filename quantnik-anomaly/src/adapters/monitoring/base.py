"""
Abstract base class for monitoring tool adapters.
Allows swapping between Datadog, Prometheus, CloudWatch, Splunk, Dynatrace.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class MetricType(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"
    NETWORK = "network"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MetricDataPoint(BaseModel):
    """Single metric data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = {}


class MetricSeries(BaseModel):
    """Time series of metric data."""
    metric_name: str
    metric_type: MetricType
    data_points: List[MetricDataPoint]
    unit: str = ""
    
    @property
    def avg(self) -> float:
        if not self.data_points:
            return 0.0
        return sum(p.value for p in self.data_points) / len(self.data_points)
    
    @property
    def max(self) -> float:
        if not self.data_points:
            return 0.0
        return max(p.value for p in self.data_points)
    
    @property
    def min(self) -> float:
        if not self.data_points:
            return 0.0
        return min(p.value for p in self.data_points)
    
    @property
    def latest(self) -> float:
        if not self.data_points:
            return 0.0
        return self.data_points[-1].value


class AlertData(BaseModel):
    """Standardized alert data from any monitoring tool."""
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    status: str  # triggered, recovered, etc.
    metric_name: str
    metric_value: float
    threshold: Optional[float] = None
    hostname: Optional[str] = None
    pod_name: Optional[str] = None
    namespace: Optional[str] = None
    deployment: Optional[str] = None
    timestamp: datetime
    tags: Dict[str, str] = {}
    raw_payload: Dict[str, Any] = {}


class HistoricalAlert(BaseModel):
    """Historical alert record."""
    alert_id: str
    title: str
    timestamp: datetime
    severity: AlertSeverity
    status: str


class BaseMonitoringAdapter(ABC):
    """Abstract base class for monitoring tool adapters."""
    
    def __init__(self, api_key: str, app_key: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.app_key = app_key
        self.config = kwargs
    
    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Return the adapter name."""
        pass
    
    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> AlertData:
        """
        Parse incoming webhook payload into standardized AlertData.
        
        Args:
            payload: Raw webhook payload from monitoring tool
            
        Returns:
            Standardized AlertData
        """
        pass
    
    @abstractmethod
    async def fetch_metrics(
        self,
        metric_query: str,
        start_time: datetime,
        end_time: datetime,
        tags: Optional[Dict[str, str]] = None
    ) -> MetricSeries:
        """
        Fetch metric data from monitoring tool.
        
        Args:
            metric_query: Metric query (format varies by tool)
            start_time: Start of time range
            end_time: End of time range
            tags: Optional filter tags
            
        Returns:
            MetricSeries with data points
        """
        pass
    
    @abstractmethod
    async def fetch_cpu_metrics(
        self,
        target: str,  # hostname, pod_name, or deployment
        start_time: datetime,
        end_time: datetime,
        namespace: Optional[str] = None
    ) -> MetricSeries:
        """Fetch CPU metrics for a target."""
        pass
    
    @abstractmethod
    async def fetch_memory_metrics(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime,
        namespace: Optional[str] = None
    ) -> MetricSeries:
        """Fetch memory metrics for a target."""
        pass
    
    @abstractmethod
    async def fetch_historical_alerts(
        self,
        target: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalAlert]:
        """Fetch historical alerts for a target."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the monitoring tool is accessible."""
        pass


def get_monitoring_adapter(
    adapter: str,
    api_key: str,
    app_key: Optional[str] = None,
    **kwargs
) -> BaseMonitoringAdapter:
    """
    Factory function to get the appropriate monitoring adapter.
    
    Args:
        adapter: Adapter name (datadog, prometheus, cloudwatch, splunk, dynatrace)
        api_key: API key for the monitoring tool
        app_key: Application key (if required)
        **kwargs: Additional adapter-specific configuration
        
    Returns:
        Configured monitoring adapter instance
    """
    adapters = {
        "datadog": "src.adapters.monitoring.datadog.DatadogAdapter",
        "prometheus": "src.adapters.monitoring.prometheus.PrometheusAdapter",
        "cloudwatch": "src.adapters.monitoring.cloudwatch.CloudWatchAdapter",
        "splunk": "src.adapters.monitoring.splunk.SplunkAdapter",
        "dynatrace": "src.adapters.monitoring.dynatrace.DynatraceAdapter",
    }
    
    if adapter not in adapters:
        raise ValueError(f"Unknown monitoring adapter: {adapter}. Available: {list(adapters.keys())}")
    
    module_path, class_name = adapters[adapter].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    adapter_class = getattr(module, class_name)
    
    return adapter_class(api_key=api_key, app_key=app_key, **kwargs)
