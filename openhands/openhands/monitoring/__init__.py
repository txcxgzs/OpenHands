"""
监控和诊断系统 - Prometheus/OTEL 支持
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    name: str
    description: str
    type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0
    timestamp: datetime = field(default_factory=datetime.now)


class PrometheusMetrics:
    """
    Prometheus 指标收集器
    """

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._labels: Dict[str, Dict[str, str]] = {}

    def counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """递增计数器"""
        key = self._make_key(name, labels)
        self._counters[key] += value
        if labels:
            self._labels[key] = labels

    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """设置仪表值"""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        if labels:
            self._labels[key] = labels

    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录直方图值"""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)
        if labels:
            self._labels[key] = labels

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """生成指标键"""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _format_labels(self, key: str) -> str:
        """格式化标签"""
        labels = self._labels.get(key, {})
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k, v in sorted(labels.items())) + "}"

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式"""
        lines = []

        # Counters
        for key, value in self._counters.items():
            labels = self._format_labels(key)
            metric_name = key.split("{")[0] if "{" in key else key
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"# HELP {metric_name}")
            lines.append(f"{metric_name}{labels} {value}")

        # Gauges
        for key, value in self._gauges.items():
            labels = self._format_labels(key)
            metric_name = key.split("{")[0] if "{" in key else key
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"# HELP {metric_name}")
            lines.append(f"{metric_name}{labels} {value}")

        # Histograms
        for key, values in self._histograms.items():
            labels = self._format_labels(key)
            metric_name = key.split("{")[0] if "{" in key else key
            lines.append(f"# TYPE {metric_name} histogram")

            # 计算分位数
            sorted_values = sorted(values)
            n = len(sorted_values)

            for quantile in [0.5, 0.9, 0.95, 0.99]:
                idx = int(n * quantile)
                q_labels = f'{labels},quantile="{quantile}"' if labels else f'quantile="{quantile}"'
                lines.append(f'{metric_name}_quantile{{{q_labels}}} {sorted_values[min(idx, n-1)]}')

            lines.append(f'{metric_name}_count{labels} {n}')
            lines.append(f'{metric_name}_sum{labels} {sum(values)}')

        return "\n".join(lines)

    def get_all_metrics(self) -> Dict[str, float]:
        """获取所有指标"""
        result = {}
        result.update(self._counters)
        result.update(self._gauges)
        for key, values in self._histograms.items():
            result[f"{key}_count"] = len(values)
            result[f"{key}_sum"] = sum(values)
        return result


class OpenTelemetryExporter:
    """
    OpenTelemetry 跟踪导出器
    """

    def __init__(self):
        self._traces: List[Dict[str, Any]] = []
        self._current_span: Optional[Dict[str, Any]] = None

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> str:
        """开始跟踪跨度"""
        span_id = f"span_{len(self._traces)}_{int(time.time() * 1000)}"

        span = {
            "name": name,
            "span_id": span_id,
            "trace_id": f"trace_{int(time.time() * 1000)}",
            "start_time": datetime.now().isoformat(),
            "attributes": attributes or {},
            "events": [],
            "status": "OK",
        }

        self._current_span = span
        logger.debug(f"Started span: {name}")

        return span_id

    def end_span(self, span_id: str, status: str = "OK") -> None:
        """结束跟踪跨度"""
        for span in self._traces:
            if span["span_id"] == span_id:
                span["end_time"] = datetime.now().isoformat()
                span["status"] = status
                break

        if self._current_span and self._current_span["span_id"] == span_id:
            self._current_span = None

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """添加事件"""
        if self._current_span:
            self._current_span["events"].append({
                "name": name,
                "timestamp": datetime.now().isoformat(),
                "attributes": attributes or {},
            })

    def record_exception(self, exception: Exception) -> None:
        """记录异常"""
        if self._current_span:
            self._current_span["events"].append({
                "name": "exception",
                "timestamp": datetime.now().isoformat(),
                "attributes": {
                    "exception.type": type(exception).__name__,
                    "exception.message": str(exception),
                },
            })
            self._current_span["status"] = "ERROR"

    def get_traces(self) -> List[Dict[str, Any]]:
        """获取所有跟踪"""
        return self._traces.copy()

    def export_json(self) -> str:
        """导出为 JSON"""
        import json
        return json.dumps({
            "traces": self._traces,
            "export_time": datetime.now().isoformat(),
        }, indent=2)


class MonitoringManager:
    """
    监控管理器 - 整合 Prometheus 和 OTEL
    """

    def __init__(self):
        self._prometheus = PrometheusMetrics()
        self._otel = OpenTelemetryExporter()
        self._health_checks: Dict[str, Callable] = {}
        self._start_time = time.time()

    @property
    def prometheus(self) -> PrometheusMetrics:
        return self._prometheus

    @property
    def otel(self) -> OpenTelemetryExporter:
        return self._otel

    def register_health_check(self, name: str, check: Callable) -> None:
        """注册健康检查"""
        self._health_checks[name] = check

    async def health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        results = {
            "status": "healthy",
            "uptime": time.time() - self._start_time,
            "checks": {},
        }

        for name, check in self._health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    result = await check()
                else:
                    result = check()

                results["checks"][name] = {
                    "status": "pass" if result else "fail",
                }
            except Exception as e:
                results["checks"][name] = {
                    "status": "error",
                    "error": str(e),
                }
                results["status"] = "unhealthy"

        return results

    def get_metrics(self) -> Dict[str, float]:
        """获取所有指标"""
        return self._prometheus.get_all_metrics()

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式"""
        return self._prometheus.export_prometheus()

    def export_otel_json(self) -> str:
        """导出 OTEL JSON 格式"""
        return self._otel.export_json()


class MetricsMiddleware:
    """指标中间件"""

    def __init__(self, monitoring: MonitoringManager):
        self._monitoring = monitoring

    async def track_request(
        self,
        method: str,
        endpoint: str,
        duration: float,
        status_code: int,
    ) -> None:
        """跟踪请求"""
        labels = {
            "method": method,
            "endpoint": endpoint,
            "status": str(status_code),
        }

        self._monitoring.prometheus.counter(
            "http_requests_total",
            1,
            labels
        )
        self._monitoring.prometheus.histogram(
            "http_request_duration_seconds",
            duration,
            labels
        )

    async def track_agent_iteration(
        self,
        agent_id: str,
        duration: float,
        tools_used: int,
    ) -> None:
        """跟踪 Agent 迭代"""
        labels = {"agent_id": agent_id}

        self._monitoring.prometheus.counter(
            "agent_iterations_total",
            1,
            labels
        )
        self._monitoring.prometheus.histogram(
            "agent_iteration_duration_seconds",
            duration,
            labels
        )
        self._monitoring.prometheus.gauge(
            "agent_tools_used",
            tools_used,
            labels
        )

    async def track_tool_execution(
        self,
        tool_name: str,
        duration: float,
        success: bool,
    ) -> None:
        """跟踪工具执行"""
        labels = {
            "tool": tool_name,
            "status": "success" if success else "error",
        }

        self._monitoring.prometheus.counter(
            "tool_executions_total",
            1,
            labels
        )
        self._monitoring.prometheus.histogram(
            "tool_execution_duration_seconds",
            duration,
            labels
        )
