from unkubed.extensions import db
from unkubed.models import User


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
    assert b"Generated YAML" in response.data
    assert b"name: nginx-test-deploy" in response.data
    assert b"image: nginx:latest" in response.data
