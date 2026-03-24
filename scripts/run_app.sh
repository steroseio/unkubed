#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP=${FLASK_APP:-unkubed:create_app}
export FLASK_ENV=${FLASK_ENV:-development}
export APP_ENV=${APP_ENV:-development}
export PORT=${PORT:-5173}

python -m flask run --debug --port "${PORT}"
