# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install kubectl for cluster interactions
RUN curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x /usr/local/bin/kubectl

WORKDIR /app

COPY pyproject.toml README.md ./

RUN pip install --upgrade pip

COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY . .

RUN pip install --no-cache-dir .

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV FLASK_APP=unkubed:create_app \
    APP_ENV=production \
    PORT=5173 \
    KUBECONFIG=/home/appuser/.kube/config

EXPOSE 5173

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
