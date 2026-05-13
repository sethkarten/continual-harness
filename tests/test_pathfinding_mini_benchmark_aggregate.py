import math
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "thesis"
    / "sethpaper-continual-harness-data"
    / "scripts"
)
if not (SCRIPT_DIR / "_lib").exists():
    pytest.skip("ContinualHarness benchmark support package not available", allow_module_level=True)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _lib.run_discovery import RunRecord
from pathfinding_mini_benchmark_aggregate import (
    active_variant_rows_at_hour,
    aggregate_setting_rows,
    build_run_time_band_rows,
    compute_elapsed_timing,
    select_top_variant_ids,
    sort_variant_rows,
)


def _make_run() -> RunRecord:
    return RunRecord(
        run_id="flash_continual_harness_t1",
        model="gemini-3-flash-preview",
        capacity_tier="flash",
        scaffold="continualharness",
        scaffold_family="H_auto",
        trial=1,
        group="continual_harness_p1",
        path=Path("/tmp/nonexistent"),
        is_symlink=False,
        live=False,
        includes_phase2=False,
        censor_at_last_milestone=True,
        notes="",
    )


def test_compute_elapsed_timing_clamps_preexisting_versions_to_hour_zero():
    timing = compute_elapsed_timing(
        "2026-04-11T02:45:30",
        "2026-04-12T04:18:18",
    )

    assert timing.raw_hours < 0.0
    assert timing.clamped_hours == 0.0
    assert timing.available_at_run_start is True


def test_variant_ranking_uses_tie_breakers_within_run():
    variant_rows = [
        {
            "version_id": "v1",
            "mean_progress_ratio_clamped": 0.8,
            "exact_success_rate": 0.6,
            "mean_expert_normalized_distance": 0.5,
        },
        {
            "version_id": "v2",
            "mean_progress_ratio_clamped": 0.8,
            "exact_success_rate": 0.6,
            "mean_expert_normalized_distance": 0.2,
        },
        {
            "version_id": "v3",
            "mean_progress_ratio_clamped": 0.8,
            "exact_success_rate": 0.4,
            "mean_expert_normalized_distance": 0.1,
        },
    ]

    ranked = sort_variant_rows(variant_rows)

    assert [row["version_id"] for row in ranked] == ["v2", "v1", "v3"]
    assert select_top_variant_ids(variant_rows, 60) == ["v2", "v1"]


def test_build_run_time_band_rows_uses_only_variants_available_by_hour():
    run = _make_run()
    variant_rows = [
        {
            "version_id": "v_early",
            "elapsed_hours_from_run_start": 0.0,
            "mean_progress_ratio_clamped": 0.2,
            "exact_success_rate": 0.2,
            "mean_expert_normalized_distance": 0.8,
        },
        {
            "version_id": "v_late",
            "elapsed_hours_from_run_start": 5.0,
            "mean_progress_ratio_clamped": 0.8,
            "exact_success_rate": 0.8,
            "mean_expert_normalized_distance": 0.2,
        },
    ]
    result_rows_by_version = {
        "v_early": [
            {
                "case_id": "c1",
                "exact_success": False,
                "normalized_progress_ratio": 0.2,
                "normalized_progress_ratio_clamped": 0.2,
                "distance_to_target": 8,
                "manhattan_distance_to_target": 8,
                "distance_to_target_over_expert_reference_steps": 0.8,
                "manhattan_distance_to_target_over_expert_reference_steps": 0.8,
                "initial_distance": 10,
                "buttons_pressed": 5,
                "successful_moves": 2,
                "failure_tags": ["partial_progress"],
            }
        ],
        "v_late": [
            {
                "case_id": "c1",
                "exact_success": True,
                "normalized_progress_ratio": 0.8,
                "normalized_progress_ratio_clamped": 0.8,
                "distance_to_target": 2,
                "manhattan_distance_to_target": 2,
                "distance_to_target_over_expert_reference_steps": 0.2,
                "manhattan_distance_to_target_over_expert_reference_steps": 0.2,
                "initial_distance": 10,
                "buttons_pressed": 5,
                "successful_moves": 5,
                "failure_tags": ["exact_success"],
            }
        ],
    }

    time_rows = build_run_time_band_rows(
        run,
        variant_rows,
        result_rows_by_version,
        percentile_bands=(100,),
        max_hours=5,
        hour_bin_size=1,
    )

    hour_4 = next(row for row in time_rows if row["elapsed_hour_bin"] == 4)
    hour_5 = next(row for row in time_rows if row["elapsed_hour_bin"] == 5)

    assert hour_4["available_versions_count"] == 1
    assert hour_4["selected_versions_count"] == 1
    assert hour_4["mean_progress_ratio_clamped"] == pytest.approx(0.2)

    assert hour_5["available_versions_count"] == 2
    assert hour_5["selected_versions_count"] == 2
    assert hour_5["mean_progress_ratio_clamped"] == pytest.approx(0.5)


def test_active_variant_rows_uses_latest_version_per_skill():
    variant_rows = [
        {
            "skill_id": "navigate",
            "version_id": "navigate_old_inherited",
            "version_index": 1,
            "elapsed_hours_from_run_start": 0.0,
            "mean_progress_ratio_clamped": 0.1,
            "exact_success_rate": 0.0,
            "mean_expert_normalized_distance": 0.9,
        },
        {
            "skill_id": "navigate",
            "version_id": "navigate_current_inherited",
            "version_index": 4,
            "elapsed_hours_from_run_start": 0.0,
            "mean_progress_ratio_clamped": 0.8,
            "exact_success_rate": 0.4,
            "mean_expert_normalized_distance": 0.2,
        },
        {
            "skill_id": "navigate",
            "version_id": "navigate_live_update",
            "version_index": 5,
            "elapsed_hours_from_run_start": 3.0,
            "mean_progress_ratio_clamped": 0.7,
            "exact_success_rate": 0.3,
            "mean_expert_normalized_distance": 0.3,
        },
    ]

    at_start = active_variant_rows_at_hour(variant_rows, 0)
    after_update = active_variant_rows_at_hour(variant_rows, 3)

    assert [row["version_id"] for row in at_start] == ["navigate_current_inherited"]
    assert [row["version_id"] for row in after_update] == ["navigate_live_update"]


def test_aggregate_setting_rows_averages_across_trials():
    rows = [
        {
            "run_id": "r1",
            "model": "gemini-3-flash-preview",
            "capacity_tier": "flash",
            "group": "continual_harness_p1",
            "trial": 1,
            "setting_key": "gemini-3-flash-preview::continual_harness_p1",
            "percentile_band": 30,
            "selected_versions_count": 3,
            "total_versions_count": 10,
            "benchmark_cases": 202,
            "evaluations": 606,
            "mean_progress_ratio": 0.4,
            "mean_progress_ratio_clamped": 0.5,
            "exact_success_rate": 0.3,
            "mean_distance_to_target": 4.0,
            "mean_manhattan_distance_to_target": 4.0,
            "mean_expert_normalized_distance": 0.4,
            "mean_manhattan_expert_normalized_distance": 0.4,
            "mean_initial_distance": 10.0,
            "mean_buttons_pressed": 5.0,
            "mean_successful_moves": 3.0,
        },
        {
            "run_id": "r2",
            "model": "gemini-3-flash-preview",
            "capacity_tier": "flash",
            "group": "continual_harness_p1",
            "trial": 2,
            "setting_key": "gemini-3-flash-preview::continual_harness_p1",
            "percentile_band": 30,
            "selected_versions_count": 4,
            "total_versions_count": 10,
            "benchmark_cases": 202,
            "evaluations": 808,
            "mean_progress_ratio": 0.6,
            "mean_progress_ratio_clamped": 0.7,
            "exact_success_rate": 0.5,
            "mean_distance_to_target": 2.0,
            "mean_manhattan_distance_to_target": 2.0,
            "mean_expert_normalized_distance": 0.2,
            "mean_manhattan_expert_normalized_distance": 0.2,
            "mean_initial_distance": 10.0,
            "mean_buttons_pressed": 6.0,
            "mean_successful_moves": 4.0,
        },
    ]

    aggregated = aggregate_setting_rows(
        rows,
        grouping_keys=("model", "group", "percentile_band"),
    )

    assert len(aggregated) == 1
    row = aggregated[0]
    assert row["run_count"] == 2
    assert row["mean_progress_ratio_clamped"] == pytest.approx(0.6)
    assert row["mean_progress_ratio_clamped_stderr"] > 0.0
    assert row["mean_selected_versions_count"] == pytest.approx(3.5)
    assert row["mean_evaluations"] == pytest.approx(707.0)
