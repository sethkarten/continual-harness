import json
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

from _lib.map_skill_benchmark import (
    BenchmarkSimulator,
    CoordinateView,
    _distance_over_reference_steps,
    _progress_ratio,
    reconstruct_skill_versions,
)
from _lib.run_discovery import RunRecord, load_manifest


def test_h_auto_discovery_includes_full_28_run_paper_data_corpus():
    manifest_only = [
        run
        for run in load_manifest()
        if run.scaffold_family == "H_auto"
        and run.group in {"continual_harness_p1", "bootstrap_frozen", "bootstrap_continued"}
    ]
    discovered = [
        run
        for run in load_manifest(include_inferred_paper_data=True)
        if run.scaffold_family == "H_auto"
        and run.group in {"continual_harness_p1", "bootstrap_frozen", "bootstrap_continued"}
    ]

    assert len(manifest_only) == 16
    assert len(discovered) == 28
    assert sum(1 for run in discovered if run.model == "gemini-3-flash-preview") == 9
    assert sum(1 for run in discovered if run.model == "gemini-3.1-flash-lite-preview") == 9
    assert sum(1 for run in discovered if run.model == "gemini-3.1-pro") == 10


def test_reconstruct_skill_versions_replays_code_history(tmp_path):
    skills = {
        "next_id": 2,
        "entries": {
            "move_to_coords": {
                "id": "move_to_coords",
                "name": "Move to Coordinates",
                "path": "navigation/basic",
                "code": "result = 'final'",
                "created_at": "2026-04-10T00:00:00",
                "updated_at": "2026-04-10T03:00:00",
                "mutation_history": [
                    {
                        "timestamp": "2026-04-10T01:00:00",
                        "fields": {
                            "code": {
                                "old": "result = 'initial'",
                                "new": "result = 'middle'",
                            }
                        },
                    },
                    {
                        "timestamp": "2026-04-10T02:00:00",
                        "fields": {
                            "code": {
                                "old": "result = 'middle'",
                                "new": "result = 'final'",
                            }
                        },
                    },
                ],
            }
        },
    }
    (tmp_path / "skills.json").write_text(json.dumps(skills), encoding="utf-8")

    run = RunRecord(
        run_id="test_run",
        model="gemini-3-flash-preview",
        capacity_tier="flash",
        scaffold="continualharness",
        scaffold_family="H_auto",
        trial=1,
        group="continual_harness_p1",
        path=tmp_path,
        is_symlink=False,
        live=False,
        includes_phase2=False,
        censor_at_last_milestone=True,
        notes="",
    )

    versions = reconstruct_skill_versions(run)

    assert [version.version_id for version in versions] == [
        "move_to_coords__v000",
        "move_to_coords__v001",
        "move_to_coords__v002",
    ]
    assert [version.code for version in versions] == [
        "result = 'initial'",
        "result = 'middle'",
        "result = 'final'",
    ]


def test_coordinate_view_supports_dict_and_sequence_access():
    coord = CoordinateView(4, 9)

    assert coord["x"] == 4
    assert coord["y"] == 9
    assert coord[0] == 4
    assert coord[1] == 9
    assert tuple(coord) == (4, 9)
    assert coord == {"x": 4, "y": 9}
    assert coord == (4, 9)


def test_negative_normalized_progress_ratio_means_farther_from_target():
    ratio, metric = _progress_ratio(10, 13, 13)

    assert metric == "shortest_path"
    assert ratio == pytest.approx(-0.3)


def test_distance_over_reference_steps_uses_expert_path_denominator():
    assert _distance_over_reference_steps(5, 20) == pytest.approx(0.25)
    assert _distance_over_reference_steps(0, 0) == 0.0
    assert _distance_over_reference_steps(None, 20) is None


def test_simulator_does_not_overlay_static_objects_as_blockers():
    payload = {
        "location": "TEST MAP",
        "grid": ["...", "...", "..."],
        "dimensions": {"width": 3, "height": 3},
        "objects": [
            {
                "x": 1,
                "y": 1,
                "movement_type": "MOVEMENT_TYPE_FACE_UP",
            }
        ],
        "runtime_objects": [],
        "warps": [],
        "raw_tiles": [[(0, 0, 0, 0)] * 3 for _ in range(3)],
    }
    simulator = BenchmarkSimulator(payload, (0, 0), memory_entries={}, button_budget=10)

    map_data = simulator.get_map_data()

    assert map_data["grid"][1][1] == "."
