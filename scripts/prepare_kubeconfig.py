#!/usr/bin/env python3
"""Create a kubeconfig copy that rewrites the advertised server address."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a kubeconfig copy with a different API server endpoint.",
    )
    parser.add_argument("--source", required=True, help="Path to the source kubeconfig.")
    parser.add_argument(
        "--destination", required=True, help="Where to write the rewritten kubeconfig."
    )
    parser.add_argument(
        "--cluster-name",
        default="minikube",
        help="Cluster entry to rewrite (default: %(default)s).",
    )
    parser.add_argument(
        "--server",
        required=True,
        help="The https://host:port URL to set for the target cluster.",
    )
    return parser


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a valid kubeconfig document.")
    return data


def write_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)
    os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = Path(args.source).expanduser()
    destination = Path(args.destination).expanduser()

    if not source.exists():
        print(f"[prepare_kubeconfig] Source kubeconfig not found at {source}", file=sys.stderr)
        return 0

    try:
        config = load_config(source)
    except ValueError as exc:
        print(f"[prepare_kubeconfig] {exc}", file=sys.stderr)
        return 0

    clusters = config.get("clusters") or []
    target_cluster = None
    for entry in clusters:
        if entry.get("name") == args.cluster_name:
            target_cluster = entry
            break

    if not target_cluster:
        print(
            f"[prepare_kubeconfig] Cluster '{args.cluster_name}' not found. "
            "Copying source without modification.",
            file=sys.stderr,
        )
        shutil.copyfile(source, destination)
        os.chmod(destination, 0o600)
        return 0

    target_cluster.setdefault("cluster", {})
    target_cluster["cluster"]["server"] = args.server

    write_config(destination, config)
    print(
        f"[prepare_kubeconfig] Wrote {destination} with server {args.server}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
