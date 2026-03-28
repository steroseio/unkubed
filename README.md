# Unkubed

Unkubed is a Flask-based learning companion that demystifies Kubernetes by lining up the UI, the generated YAML, and the underlying `kubectl` commands. The MVP focuses on safe, read-heavy workflows so learners can explore Minikube or any kubeconfig-backed cluster with confidence.

## Features

- Flask application factory with SQLAlchemy, Alembic migrations, Flask-Login auth, and Dockerized Postgres
- Cluster connection flow that accepts a kubeconfig path + context and records every `kubectl` command executed through the UI
- Resource browsers for namespaces, pods (with troubleshooting summaries + logs), deployments, and services
- YAML template generator for Deployments, Services, and ConfigMaps with the matching `kubectl apply` command
- Command history ledger stored in Postgres
- Modern UI with a hero landing page plus dark/light themes that auto-toggle based on the user’s local sunset time

## Prerequisites

- Python 3.12+
- Docker Desktop (for local Postgres)
- `kubectl` configured for your cluster (Minikube recommended for MVP)

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

1. Verify Docker is available: `scripts/check_docker.sh`
2. Start Postgres: `scripts/start_db.sh`
3. Run migrations: `scripts/run_migrations.sh`
4. Launch Flask: `scripts/run_app.sh`

The app defaults to `http://127.0.0.1:5173`.

## Running tests

```bash
pytest
```

## Run everything with Docker

If you prefer to containerize both the Flask app and Postgres:

1. Duplicate the sample env file: `cp .env.example .env` and set `SECRET_KEY` plus any overrides.
2. Ensure your host `~/.kube` **and** `~/.minikube` directories exist (Minikube certificates live there). They are bind-mounted read-only into the container both at `/home/appuser` **and** the original host absolute path so kubeconfigs referencing `/Users/...` keep working.
3. Confirm `.env` has `HOST_HOME_PATH` set to your host home (defaults to `$HOME`) so Unkubed can translate any host-only paths a kubeconfig might contain. Set `MINIKUBE_BRIDGE_IP` if your Minikube VM advertises a different IP than the default `192.168.49.2`.
4. Build and start the stack: `docker compose up --build`

The compose file:

- Builds an application image from the included `Dockerfile` (Python 3.12 + kubectl + Gunicorn).
- Runs database migrations automatically (see `scripts/docker-entrypoint.sh`) before starting Gunicorn at port `5173`.
- Mounts `${HOME}/.kube` and `${HOME}/.minikube` into `/home/appuser` **and** into the original `${HOME}` path so kubeconfig references and certificates resolve naturally. At boot the entrypoint copies `${HOME}/.kube/config` to `${HOME}/.kube/config-docker`, rewriting the API server endpoint to `https://$MINIKUBE_BRIDGE_IP:8443` so the container can reach Minikube without manual edits.
- Keeps Postgres in a persistent Docker volume (`postgres-data`).

Access the site at `http://localhost:5173` once the `web` container reports healthy. You can still use `docker compose exec web flask ...` to run management commands inside the container.

## Kubernetes integration notes

- Unkubed intentionally surfaces the verbatim `kubectl` command used for each view/action.
- Only an allowlisted set of read operations (`get`, `logs`, and relevant `events`) are executed.
- Cluster connections are stored per-user; activating one automatically deactivates the previous.
- Commands and troubleshooting summaries are recorded in Postgres for review under `/commands/history`.

## Dark/light theme toggle

The UI ships with a manual theme switch plus a sunset-aware auto toggle. When the page loads it asks the browser for geolocation, fetches the local sunset time from [sunrise-sunset.org](https://sunrise-sunset.org/), and flips to the dark palette at sunset unless the user has manually chosen a theme. The result is an opinionated but calm teaching interface suitable for evening study sessions.
