from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TroubleshootingSummary:
    summary: str
    evidence: list[str]
    next_steps: list[str]


def analyze_pod(pod: dict[str, Any], events: list[dict[str, Any]], logs: str) -> TroubleshootingSummary:
    evidence: list[str] = []
    next_steps: list[str] = []
    status = pod.get("status", {})
    phase = status.get("phase")
    container_statuses = status.get("containerStatuses", [])

    waiting_reasons = {
        "CrashLoopBackOff": "Pod is crashing on startup.",
        "ImagePullBackOff": "Image pull is failing.",
        "ErrImagePull": "Image could not be pulled.",
    }

    for container in container_statuses:
        state = container.get("state", {})
        waiting = state.get("waiting")
        if waiting:
            reason = waiting.get("reason")
            message = waiting.get("message")
            if reason in waiting_reasons:
                evidence.append(f"{container.get('name')} waiting: {reason} - {message}")
                if reason == "CrashLoopBackOff":
                    next_steps.append("Check container logs for startup failures and verify readiness probes.")
                if reason in {"ImagePullBackOff", "ErrImagePull"}:
                    next_steps.append("Verify image name/tag and registry credentials.")
        running = state.get("running")
        if running and container.get("restartCount", 0) > 5:
            evidence.append(
                f"{container.get('name')} restarted {container.get('restartCount')} times."
            )
            next_steps.append("Inspect liveness/readiness probes and container resource limits.")

    if phase == "Pending":
        evidence.append("Pod is pending scheduling.")
        next_steps.append("Check node resources or taints and ensure namespace quotas are sufficient.")

    for event in events[-5:]:
        reason = event.get("reason")
        message = event.get("message")
        if reason in ("FailedScheduling", "Failed"):
            evidence.append(f"Event {reason}: {message}")
            next_steps.append("Inspect kubectl describe pod for scheduling/resource errors.")
        if reason in ("Unhealthy", "FailedMount"):
            evidence.append(f"Event {reason}: {message}")
            next_steps.append("Check probe configuration or volume mounts.")

    if "Readiness probe failed" in logs:
        evidence.append("Logs mention readiness probe failures.")
        next_steps.append("Verify readiness probe endpoint or start-up time.")
    if "Liveness probe failed" in logs:
        evidence.append("Logs mention liveness probe failures.")
        next_steps.append("Confirm long-running work does not exceed liveness timeouts.")

    if not evidence:
        summary = f"Pod {pod.get('metadata', {}).get('name')} is {phase}."
        next_steps.append("Continue monitoring pod status and events.")
    else:
        summary = " ; ".join(evidence[:2])

    deduped_steps = list(dict.fromkeys(next_steps))

    return TroubleshootingSummary(summary=summary, evidence=evidence, next_steps=deduped_steps)
