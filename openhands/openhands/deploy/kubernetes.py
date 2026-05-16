"""
Kubernetes 支持
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class KubernetesConfig:
    namespace: str = "openhands"
    replicas: int = 3
    image: str = "openhands/openhands:latest"
    service_type: str = "ClusterIP"
    redis_enabled: bool = True
    prometheus_enabled: bool = True


class KubernetesManifestGenerator:
    """
    Kubernetes Manifest 生成器
    """

    def __init__(self, config: Optional[KubernetesConfig] = None):
        self.config = config or KubernetesConfig()

    def generate_deployment(self) -> Dict[str, Any]:
        """生成 Deployment 配置"""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "openhands",
                "namespace": self.config.namespace,
                "labels": {
                    "app": "openhands",
                    "version": "v1",
                },
            },
            "spec": {
                "replicas": self.config.replicas,
                "selector": {
                    "matchLabels": {
                        "app": "openhands",
                    },
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "openhands",
                            "version": "v1",
                        },
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "openhands",
                                "image": self.config.image,
                                "ports": [
                                    {"containerPort": 8000},
                                    {"containerPort": 9090},
                                ],
                                "env": [
                                    {"name": "ANTHROPIC_API_KEY", "valueFrom": {"secretKeyRef": {"name": "openhands-secrets", "key": "anthropic-api-key"}}},
                                    {"name": "LOG_LEVEL", "value": "info"},
                                ],
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "256Mi"},
                                    "limits": {"cpu": "2000m", "memory": "4Gi"},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": 8000},
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/ready", "port": 8000},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            },
                        ],
                    },
                },
            },
        }

    def generate_service(self) -> Dict[str, Any]:
        """生成 Service 配置"""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "openhands-service",
                "namespace": self.config.namespace,
            },
            "spec": {
                "type": self.config.service_type,
                "selector": {
                    "app": "openhands",
                },
                "ports": [
                    {"name": "http", "port": 80, "targetPort": 8000},
                    {"name": "metrics", "port": 9090, "targetPort": 9090},
                ],
            },
        }

    def generate_horizontal_pod_autoscaler(self) -> Dict[str, Any]:
        """生成 HPA 配置"""
        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": "openhands-hpa",
                "namespace": self.config.namespace,
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "openhands",
                },
                "minReplicas": 1,
                "maxReplicas": 10,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": 70,
                            },
                        },
                    },
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "memory",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": 80,
                            },
                        },
                    },
                ],
            },
        }

    def generate_ingress(self, host: str = "openhands.example.com") -> Dict[str, Any]:
        """生成 Ingress 配置"""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": "openhands-ingress",
                "namespace": self.config.namespace,
                "annotations": {
                    "cert-manager.io/cluster-issuer": "letsencrypt-prod",
                    "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                },
            },
            "spec": {
                "ingressClassName": "nginx",
                "tls": [
                    {
                        "hosts": [host],
                        "secretName": "openhands-tls",
                    },
                ],
                "rules": [
                    {
                        "host": host,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": "openhands-service",
                                            "port": {"number": 80},
                                        },
                                    },
                                },
                            ],
                        },
                    },
                ],
            },
        }

    def generate_config_map(self) -> Dict[str, Any]:
        """生成 ConfigMap"""
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "openhands-config",
                "namespace": self.config.namespace,
            },
            "data": {
                "config.yaml": """
model:
  provider: anthropic
  temperature: 0.7

tools:
  default_profile: full

logging:
  level: info
  format: json
""".strip(),
            },
        }

    def generate_secret(self) -> Dict[str, Any]:
        """生成 Secret"""
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": "openhands-secrets",
                "namespace": self.config.namespace,
            },
            "type": "Opaque",
            "stringData": {
                "anthropic-api-key": "REPLACE_WITH_YOUR_KEY",
                "openai-api-key": "REPLACE_WITH_YOUR_KEY",
            },
        }

    def generate_all(self) -> Dict[str, Any]:
        """生成所有 K8s 资源"""
        return {
            "namespace": {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": self.config.namespace,
                },
            },
            "deployment": self.generate_deployment(),
            "service": self.generate_service(),
            "hpa": self.generate_horizontal_pod_autoscaler(),
            "ingress": self.generate_ingress(),
            "configmap": self.generate_config_map(),
            "secret": self.generate_secret(),
        }

    def export_yaml(self, output_dir: str = "./k8s") -> None:
        """导出 YAML 文件"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        resources = self.generate_all()

        for name, resource in resources.items():
            filepath = os.path.join(output_dir, f"{name}.yaml")
            with open(filepath, "w") as f:
                yaml.dump(resource, f, default_flow_style=False)

        logger.info(f"Kubernetes manifests exported to {output_dir}")
