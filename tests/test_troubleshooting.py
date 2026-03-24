from unkubed.troubleshooting.heuristics import analyze_pod


def test_troubleshooting_detects_crashloop():
    pod = {
        "metadata": {"name": "demo", "namespace": "default"},
        "status": {
            "phase": "CrashLoopBackOff",
            "containerStatuses": [
                {
                    "name": "demo",
                    "restartCount": 6,
                    "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "Back-off"}},
                }
            ],
        },
    }
    events = [
        {
            "reason": "Failed",
            "message": "CrashLoopBackOff",
            "lastTimestamp": "now",
        }
    ]
    logs = "Readiness probe failed"

    summary = analyze_pod(pod, events, logs)

    assert "CrashLoopBackOff" in summary.summary
    assert any("readiness" in step.lower() for step in summary.next_steps)
