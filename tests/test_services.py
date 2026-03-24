from types import SimpleNamespace

from unkubed.services.kube import KubectlService


def test_kubectl_service_builds_expected_command(app):
    dummy_cluster = SimpleNamespace(
        id=1, kubeconfig_path="/tmp/config", context_name="minikube"
    )
    service = KubectlService(dummy_cluster)
    assert service.base_command == [
        "kubectl",
        "--kubeconfig",
        "/tmp/config",
        "--context",
        "minikube",
    ]
