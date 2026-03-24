#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP=${FLASK_APP:-unkubed:create_app}
export APP_ENV=${APP_ENV:-development}

python -m flask db upgrade
