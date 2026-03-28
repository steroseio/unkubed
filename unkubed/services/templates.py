from __future__ import annotations

from typing import Any

import yaml


class TemplateBuilder:
    """Produces educational starter manifests."""

    @staticmethod
    def deployment(payload: dict[str, Any]) -> str:
        data = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": payload["name"],
                "namespace": payload.get("namespace", "default"),
                "labels": {"app": payload["name"]},
            },
            "spec": {
                "replicas": int(payload.get("replicas", 1)),
                "selector": {"matchLabels": {"app": payload["name"]}},
                "template": {
                    "metadata": {"labels": {"app": payload["name"]}},
                    "spec": {
                        "containers": [
                            {
                                "name": payload["name"],
                                "image": payload.get("image") or "nginx:latest",
                                "ports": [
                                    {
                                        "containerPort": int(
                                            payload.get("container_port", 80)
                                        )
                                    }
                                ],
                            }
                        ]
                    },
                },
            },
        }
        return _dump(data)

    @staticmethod
    def service(payload: dict[str, Any]) -> str:
        data = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": payload["name"],
                "namespace": payload.get("namespace", "default"),
            },
            "spec": {
                "type": payload.get("service_type") or "ClusterIP",
                "selector": {"app": payload.get("selector", payload["name"])},
                "ports": [
                    {
                        "port": int(payload.get("service_port", 80)),
                        "targetPort": int(payload.get("target_port", 80)),
                    }
                ],
            },
        }
        return _dump(data)

    @staticmethod
    def configmap(payload: dict[str, Any]) -> str:
        data = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": payload["name"],
                "namespace": payload.get("namespace", "default"),
            },
            "data": payload.get("data", {"example": "value"}),
        }
        return _dump(data)


def _dump(document: dict[str, Any]) -> str:
    return yaml.safe_dump(document, sort_keys=False)
