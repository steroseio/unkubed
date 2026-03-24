from unkubed.models import User


def test_register_and_login_flow(client, app):
    register_resp = client.post(
        "/auth/register",
        data={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    assert register_resp.status_code == 200
    with app.app_context():
        assert User.query.count() == 1

    login_resp = client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "password123"},
        follow_redirects=True,
    )
    assert login_resp.status_code == 200
    assert b"Signed in successfully" in login_resp.data
