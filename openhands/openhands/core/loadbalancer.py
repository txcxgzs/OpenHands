"""
Model Failover 和 Load Balancing - 多提供商支持
"""

from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"
    WEIGHTED = "weighted"
    PRIORITY = "priority"


@dataclass
class ProviderConfig:
    name: str
    adapter_class: str
    priority: int = 1
    weight: float = 1.0
    max_rpm: Optional[int] = None
    max_tpm: Optional[int] = None
    enabled: bool = True
    timeout: int = 60
    retry_count: int = 3


@dataclass
class ProviderMetrics:
    name: str
    request_count: int = 0
    error_count: int = 0
    total_latency: float = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None

    @property
    def avg_latency(self) -> float:
        if self.request_count == 0:
            return 0
        return self.total_latency / self.request_count

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0
        return self.error_count / self.request_count


class ModelFailover:
    """
    模型故障转移管理器
    """

    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._metrics: Dict[str, ProviderMetrics] = {}
        self._provider_instances: Dict[str, Any] = {}

    def register_provider(self, config: ProviderConfig) -> None:
        """注册提供商"""
        self._providers[config.name] = config
        self._metrics[config.name] = ProviderMetrics(name=config.name)
        logger.info(f"Provider registered: {config.name}")

    def set_provider_instance(self, name: str, instance: Any) -> None:
        """设置提供商实例"""
        self._provider_instances[name] = instance

    def get_provider_instance(self, name: str) -> Optional[Any]:
        """获取提供商实例"""
        return self._provider_instances.get(name)

    def record_request(
        self,
        provider_name: str,
        success: bool,
        latency: float,
        error: Optional[str] = None,
    ) -> None:
        """记录请求结果"""
        if provider_name not in self._metrics:
            return

        metrics = self._metrics[provider_name]
        metrics.request_count += 1
        metrics.total_latency += latency
        metrics.last_used = datetime.now()

        if not success:
            metrics.error_count += 1
            metrics.last_error = error

    def get_available_providers(self) -> List[str]:
        """获取可用的提供商列表"""
        available = []

        for name, config in self._providers.items():
            if not config.enabled:
                continue

            metrics = self._metrics.get(name)
            if metrics and metrics.error_rate > 0.5:
                continue

            if config.max_rpm and metrics:
                rpm = metrics.request_count
                if rpm >= config.max_rpm:
                    continue

            available.append(name)

        return available if available else list(self._providers.keys())

    def get_best_provider(self) -> Optional[str]:
        """获取最佳提供商（基于指标）"""
        available = self.get_available_providers()
        if not available:
            return None

        best = None
        best_score = float("-inf")

        for name in available:
            metrics = self._metrics.get(name)
            config = self._providers[name]

            if not metrics:
                score = config.priority
            else:
                score = (
                    config.priority * 10
                    - metrics.error_rate * 100
                    - metrics.avg_latency / 10
                )

            if score > best_score:
                best_score = score
                best = name

        return best

    async def execute_with_failover(
        self,
        operation: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """执行操作并支持故障转移"""
        last_error = None

        for provider_name in self.get_available_providers():
            try:
                instance = self.get_provider_instance(provider_name)
                if not instance:
                    continue

                start_time = datetime.now()

                result = await operation(instance, *args, **kwargs)

                latency = (datetime.now() - start_time).total_seconds()
                self.record_request(provider_name, True, latency)

                return result

            except Exception as e:
                latency = (datetime.now() - start_time).total_seconds()
                self.record_request(provider_name, False, latency, str(e))
                last_error = e
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue

        raise last_error or Exception("All providers failed")

    def get_metrics(self) -> Dict[str, ProviderMetrics]:
        """获取所有指标"""
        return self._metrics.copy()

    def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        results = {}

        for name, config in self._providers.items():
            if not config.enabled:
                results[name] = False
                continue

            metrics = self._metrics.get(name)
            if metrics and metrics.error_rate > 0.5:
                results[name] = False
            else:
                results[name] = True

        return results


class LoadBalancer:
    """
    负载均衡器
    """

    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    ):
        self._strategy = strategy
        self._round_robin_index: Dict[str, int] = {}
        self._failover = ModelFailover()

    def add_provider(self, name: str, config: ProviderConfig) -> None:
        """添加提供商"""
        self._failover.register_provider(config)
        self._round_robin_index[name] = 0

    def set_provider_instance(self, name: str, instance: Any) -> None:
        """设置实例"""
        self._failover.set_provider_instance(name, instance)

    async def execute(
        self,
        operation: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """执行负载均衡操作"""
        provider_name = self._select_provider()
        instance = self._failover.get_provider_instance(provider_name)

        if not instance:
            return await self._failover.execute_with_failover(operation, *args, **kwargs)

        try:
            start_time = datetime.now()
            result = await operation(instance, *args, **kwargs)
            latency = (datetime.now() - start_time).total_seconds()
            self._failover.record_request(provider_name, True, latency)
            return result

        except Exception as e:
            latency = (datetime.now() - start_time).total_seconds()
            self._failover.record_request(provider_name, False, latency, str(e))

            return await self._failover.execute_with_failover(
                operation, *args, **kwargs
            )

    def _select_provider(self) -> Optional[str]:
        """选择提供商"""
        providers = self._failover.get_available_providers()
        if not providers:
            return None

        if self._strategy == LoadBalancingStrategy.ROUND_ROBIN:
            for name in providers:
                idx = self._round_robin_index.get(name, 0)
                self._round_robin_index[name] = (idx + 1) % 1000
                if idx == 0:
                    return name

        elif self._strategy == LoadBalancingStrategy.LEAST_LOADED:
            best = None
            best_load = float("inf")

            for name in providers:
                metrics = self._failover.get_metrics().get(name)
                if not metrics:
                    return name

                load = metrics.request_count
                if load < best_load:
                    best_load = load
                    best = name

            return best

        elif self._strategy == LoadBalancingStrategy.WEIGHTED:
            import random

            total_weight = sum(
                self._failover._providers[p].weight for p in providers
            )
            rand = random.uniform(0, total_weight)

            cum_weight = 0
            for name in providers:
                cum_weight += self._failover._providers[name].weight
                if rand <= cum_weight:
                    return name

        return providers[0]

    @property
    def failover(self) -> ModelFailover:
        return self._failover
