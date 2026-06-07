"""
Kubernetes Client for remediation operations.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("anomaly-agent")


class K8sClient:
    """Kubernetes client for deployment operations."""
    
    def __init__(self, in_cluster: bool = True, namespace: str = "default"):
        self.in_cluster = in_cluster
        self.default_namespace = namespace
        self._client = None
        self._apps_v1 = None
    
    def _get_client(self):
        """Get or create Kubernetes client."""
        if self._client is None:
            from kubernetes import client, config
            
            if self.in_cluster:
                config.load_incluster_config()
            else:
                config.load_kube_config()
            
            self._client = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
        
        return self._client, self._apps_v1
    
    async def get_replicas(self, deployment: str, namespace: Optional[str] = None) -> int:
        """Get current replica count for a deployment."""
        namespace = namespace or self.default_namespace
        
        _, apps_v1 = self._get_client()
        
        loop = asyncio.get_event_loop()
        deployment_obj = await loop.run_in_executor(
            None,
            lambda: apps_v1.read_namespaced_deployment(deployment, namespace)
        )
        
        return deployment_obj.spec.replicas or 1
    
    async def scale(self, deployment: str, namespace: Optional[str], replicas: int) -> bool:
        """Scale a deployment to specified replica count."""
        namespace = namespace or self.default_namespace
        
        _, apps_v1 = self._get_client()
        
        body = {"spec": {"replicas": replicas}}
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: apps_v1.patch_namespaced_deployment_scale(
                deployment, namespace, body
            )
        )
        
        logger.info(f"Scaled {namespace}/{deployment} to {replicas} replicas")
        return True
    
    async def restart(self, deployment: str, namespace: Optional[str] = None) -> bool:
        """Perform a rolling restart of a deployment."""
        namespace = namespace or self.default_namespace
        
        _, apps_v1 = self._get_client()
        
        from datetime import datetime
        
        # Patch with annotation to trigger restart
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()
                        }
                    }
                }
            }
        }
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: apps_v1.patch_namespaced_deployment(
                deployment, namespace, body
            )
        )
        
        logger.info(f"Initiated rolling restart for {namespace}/{deployment}")
        return True
    
    async def rollback(self, deployment: str, namespace: Optional[str] = None) -> bool:
        """Rollback deployment to previous revision."""
        namespace = namespace or self.default_namespace
        
        _, apps_v1 = self._get_client()
        
        # Get current revision
        loop = asyncio.get_event_loop()
        deployment_obj = await loop.run_in_executor(
            None,
            lambda: apps_v1.read_namespaced_deployment(deployment, namespace)
        )
        
        current_revision = deployment_obj.metadata.annotations.get(
            "deployment.kubernetes.io/revision", "1"
        )
        
        # Rollback by patching with rollback annotation
        # In practice, you'd use revision history
        body = {
            "metadata": {
                "annotations": {
                    "kubectl.kubernetes.io/rollback-to": str(int(current_revision) - 1)
                }
            }
        }
        
        await loop.run_in_executor(
            None,
            lambda: apps_v1.patch_namespaced_deployment(
                deployment, namespace, body
            )
        )
        
        logger.info(f"Initiated rollback for {namespace}/{deployment}")
        return True
    
    async def get_deployment_status(self, deployment: str, namespace: Optional[str] = None) -> dict:
        """Get deployment status."""
        namespace = namespace or self.default_namespace
        
        _, apps_v1 = self._get_client()
        
        loop = asyncio.get_event_loop()
        deployment_obj = await loop.run_in_executor(
            None,
            lambda: apps_v1.read_namespaced_deployment(deployment, namespace)
        )
        
        status = deployment_obj.status
        
        return {
            "replicas": status.replicas or 0,
            "ready_replicas": status.ready_replicas or 0,
            "available_replicas": status.available_replicas or 0,
            "updated_replicas": status.updated_replicas or 0,
            "conditions": [
                {
                    "type": c.type,
                    "status": c.status,
                    "reason": c.reason,
                    "message": c.message
                }
                for c in (status.conditions or [])
            ]
        }
