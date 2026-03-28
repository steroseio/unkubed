from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class TemplateForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    namespace = StringField(
        "Namespace",
        validators=[DataRequired(), Length(max=120)],
        default="default",
    )
    image = StringField("Container Image", validators=[Optional(), Length(max=200)])
    replicas = IntegerField("Replicas", validators=[Optional(), NumberRange(min=1)], default=1)
    container_port = IntegerField(
        "Container Port", validators=[Optional(), NumberRange(min=1, max=65535)], default=80
    )
    service_type = SelectField(
        "Service Type",
        choices=[("ClusterIP", "ClusterIP"), ("NodePort", "NodePort"), ("LoadBalancer", "LoadBalancer")],
    )
    service_port = IntegerField(
        "Service Port", validators=[Optional(), NumberRange(min=1, max=65535)], default=80
    )
    target_port = IntegerField(
        "Target Port", validators=[Optional(), NumberRange(min=1, max=65535)], default=80
    )
    config_data = TextAreaField(
        "ConfigMap data (key=value per line)",
        validators=[Optional()],
    )
    save_template = BooleanField("Save this template")
    submit = SubmitField("Generate YAML")
