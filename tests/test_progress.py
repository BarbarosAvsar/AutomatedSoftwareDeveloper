from pathlib import Path

from automated_software_developer.agent.progress import ProgressTracker


def test_progress_snapshot_and_eta(tmp_path: Path) -> None:
    tracker = ProgressTracker(project_id="alpha", base_dir=tmp_path)
    tracker.start_phase("Requirements")
    tracker.complete_step("Requirements", "draft")
    tracker.record_story_points(completed=2, total=10)

    snapshot = tracker.snapshot()
    assert snapshot.phase == "Requirements"
    assert snapshot.percent_complete > 0
    assert snapshot.eta_range is not None


def test_progress_is_monotonic(tmp_path: Path) -> None:
    tracker = ProgressTracker(project_id="beta", base_dir=tmp_path)
    tracker.complete_step("Requirements", "draft")
    first = tracker.snapshot().percent_complete
    tracker.complete_step("Requirements", "refine")
    second = tracker.snapshot().percent_complete
    assert second >= first


def test_progress_save_and_resume(tmp_path: Path) -> None:
    tracker = ProgressTracker(project_id="gamma", base_dir=tmp_path)
    tracker.complete_step("Requirements", "draft")
    saved = tracker.save()

    reloaded = ProgressTracker(project_id="gamma", base_dir=tmp_path).load_latest()
    assert reloaded is not None
    assert reloaded.phase == saved.phase
