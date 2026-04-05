from types import SimpleNamespace

from unkubed.services.kube import build_base_command


def test_kubectl_helper_builds_expected_command(app):
    dummy_cluster = SimpleNamespace(
        id=1, kubeconfig_path="/tmp/config", context_name="minikube"
    )
    assert build_base_command(dummy_cluster) == [
        "kubectl",
        "--kubeconfig",
        "/tmp/config",
        "--context",
        "minikube",
    ]
