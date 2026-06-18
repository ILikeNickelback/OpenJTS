"""Unit tests for core.workspace_manager (save_to / load)."""

import json

import pytest

from core import workspace_manager

pytestmark = pytest.mark.unit


class FakeTab:
    """Stand-in for an ExperimentTab exposing only collect_save_data()."""

    def __init__(self, data):
        self._data = data

    def collect_save_data(self):
        return self._data


def test_save_to_writes_index_and_per_experiment_files(tmp_path):
    tabs = {
        "exp1": FakeTab(
            {
                "name": "exp1",
                "acquisition_type": "Sequence",
                "experiment_type": "Fluo",
                "results": [1, 2, 3],
            }
        ),
        "exp2": FakeTab(
            {
                "name": "exp2",
                "acquisition_type": "Frequency",
                "experiment_type": "Spectro",
            }
        ),
    }

    workspace_manager.save_to(tmp_path, tabs)

    index = json.loads((tmp_path / "workspace.json").read_text())
    assert index["version"] == workspace_manager.VERSION
    assert index["experiments"] == [
        {"name": "exp1", "acq_type": "Sequence", "exp_type": "Fluo"},
        {"name": "exp2", "acq_type": "Frequency", "exp_type": "Spectro"},
    ]
    assert json.loads((tmp_path / "exp1.json").read_text())["results"] == [1, 2, 3]


def test_save_to_creates_missing_directory(tmp_path):
    workspace_dir = tmp_path / "nested" / "workspace"
    workspace_manager.save_to(workspace_dir, {})
    assert (workspace_dir / "workspace.json").exists()


def test_load_round_trips_saved_workspace(tmp_path):
    tabs = {
        "exp1": FakeTab(
            {
                "name": "exp1",
                "acquisition_type": "Sequence",
                "experiment_type": "Fluo",
                "results": [1, 2, 3],
            }
        )
    }
    workspace_manager.save_to(tmp_path, tabs)

    loaded = workspace_manager.load(tmp_path / "workspace.json")

    assert loaded["global_settings"] == {}
    assert len(loaded["experiments"]) == 1
    assert loaded["experiments"][0]["results"] == [1, 2, 3]


def test_load_falls_back_to_default_when_experiment_file_missing(tmp_path):
    workspace_json = {
        "version": 1,
        "experiments": [{"name": "ghost", "acq_type": "Sequence", "exp_type": "Fluo"}],
        "global_settings": {},
    }
    (tmp_path / "workspace.json").write_text(json.dumps(workspace_json))

    loaded = workspace_manager.load(tmp_path / "workspace.json")

    exp = loaded["experiments"][0]
    assert exp["name"] == "ghost"
    assert exp["acquisition_type"] == "Sequence"
    assert exp["experiment_type"] == "Fluo"
    assert exp["metadata"] == {}
    assert exp["sequences"] == []
    assert exp["results"] == []
