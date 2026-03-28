from types import SimpleNamespace

from unkubed.extensions import db
from unkubed.models import Cluster, User
from unkubed.services.kube import KubectlService


def _login(client, app):
    with app.app_context():
        user = User(email="templates@example.com", full_name="Template User")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={"email": "templates@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_deployment_template_generates_with_defaults(client, app):
    _login(client, app)

    response = client.post(
        "/templates/new/deployment",
        data={
            "name": "nginx-test-deploy",
            "namespace": "default",
            "image": "",
            "replicas": "",
            "container_port": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Generated deployment YAML" in response.data
    assert b"name: nginx-test-deploy" in response.data
    assert b"image: nginx:latest" in response.data
    assert b"Run it" in response.data


def test_deployment_template_apply_uses_active_cluster(client, app, monkeypatch):
    _login(client, app)

    with app.app_context():
        user = User.query.filter_by(email="templates@example.com").first()
        cluster = Cluster(
            user_id=user.id,
            nickname="minikube",
            kubeconfig_path="/tmp/config-docker",
            context_name="minikube",
            is_active=True,
        )
        db.session.add(cluster)
        db.session.commit()

    captured = {}

    def fake_apply_manifest(self, manifest, user_id, resource_type, resource_name):
        captured["manifest"] = manifest
        captured["user_id"] = user_id
        captured["resource_type"] = resource_type
        captured["resource_name"] = resource_name
        return SimpleNamespace(
            success=True,
            command="kubectl apply -f deployment-nginx-test-deploy.yaml",
            stdout="deployment.apps/nginx-test-deploy created",
            stderr="",
        )

    monkeypatch.setattr(KubectlService, "apply_manifest", fake_apply_manifest)

    response = client.post(
        "/templates/new/deployment",
        data={
            "name": "nginx-test-deploy",
            "namespace": "default",
            "image": "nginx:latest",
            "replicas": "3",
            "container_port": "80",
            "action": "apply",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert captured["resource_type"] == "deployment"
    assert captured["resource_name"] == "nginx-test-deploy"
    assert "replicas: 3" in captured["manifest"]
    assert b"Apply result" in response.data
    assert b"deployment.apps/nginx-test-deploy created" in response.data
