from pathlib import Path

from automated_software_developer.agent.agile.metrics import MetricsStore


def test_metrics_record_and_persist(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    store = MetricsStore(path=metrics_path)
    store.load()
    store.record_sprint(velocity=5, cycle_time=1.5, lead_time=2.0)
    store.record_quality_events(defect_rate=0.1, failed_deployments=1, incident_count=2)
    store.save()
    reloaded = MetricsStore(path=metrics_path)
    reloaded.load()
    snapshot = reloaded.snapshot()
    assert snapshot.velocity_history[0] == 5
    assert snapshot.failed_deployments == 1
    assert snapshot.incident_count == 2
