def test_app_factory_uses_testing_config(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_app_has_registered_blueprints(app):
    rules = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "auth.login" in rules
    assert "dashboard.overview" in rules
