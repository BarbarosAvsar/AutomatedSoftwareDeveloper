"""Tests for pipeline truth map and schema validation."""

from __future__ import annotations

from automated_software_developer.agent.pipeline.schema import (
    PIPELINE_EVENT_SCHEMA,
    PIPELINE_STATUS_VALUES,
    pipeline_event_payload,
    pipeline_truth_map,
    validate_pipeline_event,
)


def test_pipeline_truth_map_contains_pipelines() -> None:
    pipelines = pipeline_truth_map()
    ids = {pipeline.pipeline_id for pipeline in pipelines}
    assert {"generator", "ui", "ci"}.issubset(ids)


def test_pipeline_event_schema_and_validation() -> None:
    payload = pipeline_event_payload(
        pipeline="generator",
        step="refine",
        status="in_progress",
        message="starting",
    )
    validate_pipeline_event(payload)
    assert PIPELINE_EVENT_SCHEMA["title"] == "PipelineEvent"
    assert "completed" in PIPELINE_STATUS_VALUES
