# Unkubed

Unkubed is a Flask-based web application for learning Kubernetes by lining up the UI, the generated YAML, the exact `kubectl` command, and the resulting cluster state. The MVP focuses on read-heavy workflows so users can explore Minikube or any kubeconfig-backed cluster with less guesswork.

## Video Demo URL

https://www.youtube.com/watch?v=LvSYcFLOZEU

## Features

- Flask application factory with SQLAlchemy, Alembic migrations, Flask-Login auth, and Dockerized Postgres
- Cluster connection flow that accepts a kubeconfig path + context and records every `kubectl` command executed through the UI
- Resource browsers for namespaces, pods (with troubleshooting summaries + logs), deployments, and services
- YAML template generator for Deployments, Services, and ConfigMaps with the matching `kubectl apply` command
- Command history ledger stored in Postgres
- Clean UI with dashboard, resource, troubleshooting, and template pages

A typical request flow in Unkubed is:

1. the user performs an action in the UI
2. the app builds the matching allowlisted `kubectl` command
3. the command is executed against the active cluster context
4. the response is rendered in the UI and recorded in command history

This keeps the application focused on teaching Kubernetes rather than hiding it.

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

## Project structure

The backend is intentionally simple and easy to trace:

- `unkubed/__init__.py` boots the Flask app, loads configuration, initializes extensions, and registers blueprints.
- `unkubed/dashboard/routes.py` contains most of the application logic, including authentication, cluster connection, dashboard views, resource browsing, troubleshooting, command history, and template generation.
- `unkubed/models.py` contains the SQLAlchemy models for users, clusters, command history, saved templates, and troubleshooting reports.
- `unkubed/templates/` contains the Jinja templates for the UI.
- `unkubed/static/` contains the shared CSS, JavaScript, and image assets.

## File guide

- `unkubed/__init__.py`: Boots the Flask app, loads configuration, initializes extensions, registers blueprints, and wires the login manager and shell context.
- `unkubed/dashboard/routes.py`: Holds most of the application logic, including the landing pages, auth flow, cluster connection, dashboard views, resource browsing, command history, troubleshooting logic, template generation, and the allowlisted `kubectl` execution helpers.
- `unkubed/models.py`: Defines the SQLAlchemy models for users, saved cluster connections, command history, saved templates, and troubleshooting reports.
- `wsgi.py`: Exposes the Flask application object for production-style servers such as Gunicorn.
- `compose.yml`: Defines the local Docker Compose stack for the web app and Postgres, including mounts, environment variables, and the startup command.
- `Dockerfile`: Builds the application image with Python, the app dependencies, and the runtime setup used by the `web` service.
- `.env.example`: Provides the sample environment variables needed for local development and Docker-based setup.
- `pyproject.toml`: Defines the project metadata and Python dependencies needed to install and run Unkubed.
- `alembic.ini`: Configures Alembic so database migrations can run against the app’s SQLAlchemy models.
- `migrations/env.py`: Connects Alembic to the Flask app and database metadata so migration scripts can be generated and applied.
- `migrations/script.py.mako`: Provides the template Alembic uses when creating new migration files.
- `scripts/check_docker.sh`: Verifies that Docker is installed and available before trying to start the local stack.
- `scripts/start_db.sh`: Starts the local Postgres service using Docker Compose.
- `scripts/run_migrations.sh`: Runs the database migrations so the schema is up to date before the app starts.
- `scripts/run_app.sh`: Launches the Flask development server for local non-Docker development.
- `scripts/docker-entrypoint.sh`: Prepares the container runtime, runs migrations, and starts the web server when the Docker app container boots.
- `scripts/prepare_kubeconfig.py`: Creates the Docker-friendly kubeconfig copy used inside the container so the app can talk to Minikube without manual edits.
- `tests/conftest.py`: Provides the shared pytest fixtures for creating the Flask app, test client, and temporary test database.
- `tests/test_app_factory.py`: Checks that the Flask app boots with the testing configuration and registers the expected routes.
- `tests/test_auth.py`: Covers the basic user registration and login flow.
- `tests/test_services.py`: Verifies the helper that builds the base `kubectl` command from the active cluster configuration.
- `tests/test_templates.py`: Tests YAML template generation and the flow that applies a generated manifest against the active cluster.
- `tests/test_troubleshooting.py`: Exercises the rule-based pod troubleshooting summary logic for common failure cases.
- `unkubed/templates/base.html`: Defines the shared page layout, navigation, footer, and flash messages used across the site.
- `unkubed/templates/main/index.html`: Renders the landing page introduction and preview screenshots.
- `unkubed/templates/main/features.html`: Presents the feature overview page for the main parts of the app.
- `unkubed/templates/auth/login.html`: Renders the sign-in form for returning users.
- `unkubed/templates/auth/register.html`: Renders the account creation form for new users.
- `unkubed/templates/clusters/connect.html`: Renders the cluster connection form plus the saved cluster list with activate and delete actions.
- `unkubed/templates/dashboard/index.html`: Renders the main dashboard with cluster summary metrics and recent command history.
- `unkubed/templates/commands/history.html`: Renders the full command history view with expandable command output and status information.
- `unkubed/templates/resources/pods.html`: Renders the pod list view with status, restart counts, and links to pod inspection pages.
- `unkubed/templates/resources/pod_detail.html`: Renders the pod inspection page with metadata, events, logs, troubleshooting output, and supporting `kubectl` commands.
- `unkubed/templates/resources/namespaces.html`: Renders the namespace list view and the command used to retrieve it.
- `unkubed/templates/resources/deployments.html`: Renders the deployment list view with rollout and readiness information.
- `unkubed/templates/resources/services.html`: Renders the service list view with type, cluster IP, and exposed port information.
- `unkubed/templates/templates/list.html`: Renders the saved template library and links to create new deployment, service, and ConfigMap templates.
- `unkubed/templates/templates/new.html`: Renders the template builder form, generated YAML preview, and apply result output for new manifests.
- `unkubed/static/css/main.css`: Contains the shared visual design system, layout rules, resource table styling, terminal-style panels, and theme-aware colors.

## Running tests

If you are running the app locally in a virtual environment:

```bash
pytest
```

If you are using Docker Compose for the app environment:

```bash
docker compose exec web pytest
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

For development, most code and template changes should appear after a refresh without rebuilding, because the project directory is mounted into the container.

## Kubernetes integration notes

- Unkubed intentionally surfaces the verbatim `kubectl` command used for each view/action.
- Only an allowlisted set of read operations (`get`, `logs`, and relevant `events`) are executed.
- Cluster connections are stored per-user; activating one automatically deactivates the previous.
- Commands and troubleshooting summaries are recorded in Postgres for review under `/commands/history`.

## Design choices

I began with the idea of multiple route.py files for each different service path, based on best practice design videos I had been watching before beginning the project. However, in the end, I flattened almost everything into `unkubed/dashboard/routes.py`. I felt that grouping the application logic like this meant it would be easier to understand for a new engineer looking to investigate the application.

I reviewed but did not use the Kubernetes Python client. The app is supposed to surface the real `kubectl` commands, however the client was threatening to obfuscate a lot of that useful information, and risking the purpose of the app, which is to educate the user on Kubernetes.

Architecturally I also thought in detail about what exactly should be stored in PostgreSQL. In the end I settled on App state but not Cluster state, to keep the database focused on:

- users
- saved clusters
- command history
- stored templates
- troubleshooting reports

This allowed the cluster itself (and the commands ran by the app) to be the source of truth, and keep the database relatively light.

## AI assistance

- I am not great at front end design! Accordingly I built functional Jinja templates and then provided detailed prompts to AI in Study mode, to outline the kind of layout and look I was aiming for. From there we pair programmed to produce the look of the web app.
- I also used AI to discover SQLAlchemy. I was searching for a tool that could build table definitions from Python classes and came across this. In addition to the core function I needed, it also handled connections to the database, translating model operations into valid SQL, and turning database rows back into Python objects with ease. I'm very happy to have this in my toolkit going forwards as it saved me a lot of time by avoiding writing SQL boilerplate.
