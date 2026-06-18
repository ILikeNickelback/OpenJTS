"""Workspace persistence utilities.

A workspace is a directory containing one ``workspace.json`` index file and one
``<name>.json`` data file per experiment tab.  This module provides two
functions — :func:`save_to` and :func:`load` — with no shared state.

File layout::

    <workspace_dir>/
        workspace.json          # index: version, experiment list, global settings
        <experiment_name>.json  # per-tab serialised data
"""

import json
from pathlib import Path

VERSION = 1


def save_to(workspace_dir: Path, experiment_tabs: dict):
    """Save the workspace to workspace_dir/.

    Creates workspace.json (index) and one {name}.json per experiment tab.

    Args:
        workspace_dir (Path): Directory in which workspace files are written.
        experiment_tabs (dict): Mapping of tab name to ExperimentTab instance.
        state: Application state object (reserved for future global settings).
    """
    workspace_dir = Path(workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    experiments_index = []
    for name, tab in experiment_tabs.items():
        data = tab.collect_save_data()
        exp_file = workspace_dir / f"{name}.json"
        with open(exp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        experiments_index.append(
            {
                "name": data.get("name", name),
                "acq_type": data.get("acquisition_type", ""),
                "exp_type": data.get("experiment_type", ""),
            }
        )

    workspace_json = {
        "version": VERSION,
        "experiments": experiments_index,
        "global_settings": {},
    }
    with open(workspace_dir / "workspace.json", "w", encoding="utf-8") as f:
        json.dump(workspace_json, f, indent=2)


def load(workspace_json_path: Path) -> dict:
    """Load a workspace from a workspace.json path.

    Args:
        workspace_json_path (Path): Path to the workspace.json index file.

    Returns:
        dict: ``{"experiments": [per-experiment dicts], "global_settings": {...}}``.
            Missing experiment files are replaced with a default structure.
    """
    workspace_json_path = Path(workspace_json_path)
    workspace_dir = workspace_json_path.parent

    with open(workspace_json_path, "r", encoding="utf-8") as f:
        workspace = json.load(f)

    experiment_data = []
    for entry in workspace.get("experiments", []):
        name = entry["name"]
        exp_file = workspace_dir / f"{name}.json"
        if exp_file.exists():
            with open(exp_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "name": name,
                "acquisition_type": entry.get("acq_type", "Sequence"),
                "experiment_type": entry.get("exp_type", "Fluo"),
                "metadata": {},
                "sequences": [],
                "parameters": {},
                "history": [],
                "results": [],
            }
        experiment_data.append(data)

    return {
        "experiments": experiment_data,
        "global_settings": workspace.get("global_settings", {}),
    }
