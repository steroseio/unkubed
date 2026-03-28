from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class ClusterConnectForm(FlaskForm):
    nickname = StringField("Nickname", validators=[DataRequired(), Length(max=120)])
    kubeconfig_path = StringField(
        "Kubeconfig Path",
        validators=[DataRequired(), Length(max=500)],
    )
    context_name = SelectField(
        "Context",
        validators=[Optional(), Length(max=200)],
        choices=[],
        validate_choice=False,
    )
    manual_context = StringField(
        "Manual context name",
        validators=[Optional(), Length(max=200)],
    )
    submit = SubmitField("Save connection")
