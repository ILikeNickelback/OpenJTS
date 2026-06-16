# core/module_registry.py
import importlib.util
import os
import json
import dearpygui.dearpygui as dpg
from loguru import logger

MODULES_REGISTRY: list = []


def register_module(module):
    if module not in MODULES_REGISTRY:
        MODULES_REGISTRY.append(module)


def unregister_module(module):
    if module in MODULES_REGISTRY:
        MODULES_REGISTRY.remove(module)


def get_registered_modules():
    return MODULES_REGISTRY


def clear_registry():
    MODULES_REGISTRY.clear()


def get_available_modules(base_path: str = "modules") -> dict:
    module_registry: dict = {}

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(
                    full_path, base_path).replace("\\", "/")
                module_name = rel_path[:-3].replace("/", ".")

                spec = importlib.util.spec_from_file_location(
                    module_name, full_path)
                mod = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(mod)  # type: ignore
                except Exception as e:
                    logger.error(f"Failed to load module {module_name}: {e}")
                    continue

                if hasattr(mod, "EXPORTED_CLASS"):
                    module_registry[module_name] = mod.EXPORTED_CLASS

    return module_registry


def export_workspace(instances=None, filepath: str = "layout.json"):
    """
    Export windows *and* connections to a JSON file.
    """
    if instances is None:
        instances = get_registered_modules()

    data = {
        "windows": [win.serialize() for win in instances],
        "connections": [
            {
                "from": win.UUID,
                "output": output_key,
                "to": tgt.UUID,
            }
            for win in instances
            for output_key, targets in getattr(win, "connections", {}).items()
            for tgt in targets
        ],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    logger.success(f"Workspace exported to {filepath}")


def oldload_workspace(filepath: str = "layout.json", module_registry=None):
    """
    Load a workspace JSON and recreate windows and links.
    """

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if module_registry is None:
        module_registry = get_available_modules()

    clear_registry()
    instances: dict[str, object] = {}

    # ---------- recreate windows -------------------------------------------
    for wdata in data["windows"]:
        module_path = wdata["module"]
        cls = module_registry.get(module_path)
        if not cls:
            logger.warning(f"Unknown module: {module_path}")
            continue

        size = wdata.get("size", [-1, -1])
        visible = wdata.get("visible", True)

        win = cls(
            uuid=wdata["uuid"],
            pos=tuple(wdata["pos"]),
            win_width=size[0],
            win_height=size[1],
            visible=visible,
            **wdata["params"],
        )
        register_module(win)
        instances[wdata["uuid"]] = win

        # instantly update DPG item if already created
        if dpg.does_item_exist(win.winID):
            dpg.set_item_pos(win.winID, win.pos)
            dpg.set_item_width(win.winID, win.win_width)
            dpg.set_item_height(win.winID, win.win_height)
            dpg.configure_item(win.winID, show=visible)

    # ---------- recreate links ---------------------------------------------
    for conn in data["connections"]:
        src = instances.get(conn["from"])
        tgt = instances.get(conn["to"])
        output_key = conn.get("output")

        # support legacy format with list of targets
        if isinstance(conn.get("to"), list):
            for tgt_uuid in conn["to"]:
                tgt_obj = instances.get(tgt_uuid)
                if src and tgt_obj:
                    # default to first output
                    src.connect_to(tgt_obj, output=0)
            continue

        if src and tgt and output_key is not None:
            src.connect_to(tgt, output=output_key)

    logger.success(f"Workspace loaded from {filepath}")

    return list(instances.values())


def load_workspace(filepath: str = "layout.json", module_registry=None):
    """
    Load a workspace JSON and recreate windows, links, and merges.
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if module_registry is None:
        module_registry = get_available_modules()

    clear_registry()
    instances: dict[str, object] = {}
    merge_requests: list[tuple[str, str]] = []

    # ---------- recreate windows -------------------------------------------
    for wdata in data["windows"]:
        module_path = wdata["module"]
        cls = module_registry.get(module_path)
        if not cls:
            logger.warning(f"Unknown module: {module_path}")
            continue

        size = wdata.get("size", [-1, -1])
        visible = wdata.get("visible", True)

        # Préparation des paramètres
        params = dict(wdata.get("params", {}))
        merge_target_uuid = params.pop("merged_into", None)

        # Création de l'instance sans merged_into
        try:
            win = cls(
                uuid=wdata["uuid"],
                pos=tuple(wdata["pos"]),
                win_width=size[0],
                win_height=size[1],
                visible=visible,
                **params,
            )
        except Exception as e:
            logger.error(
                f"Failed to instantiate {cls} with UUID {wdata['uuid']}: {e}")
            continue

        register_module(win)
        instances[wdata["uuid"]] = win

        # Retenir la fusion à faire plus tard
        if merge_target_uuid:
            merge_requests.append((wdata["uuid"], merge_target_uuid))

        # Mise à jour DPG immédiate
        if dpg.does_item_exist(win.winID):
            dpg.set_item_pos(win.winID, win.pos)
            dpg.set_item_width(win.winID, win.win_width)
            dpg.set_item_height(win.winID, win.win_height)
            dpg.configure_item(win.winID, show=visible)

    # ---------- reapply merges ---------------------------------------------
    for src_uuid, tgt_uuid in merge_requests:
        src = instances.get(src_uuid)
        tgt = instances.get(tgt_uuid)
        if src and tgt:
            src.merge_into(tgt)

    # ---------- recreate connections ---------------------------------------
    for conn in data["connections"]:
        src = instances.get(conn["from"])
        tgt = instances.get(conn["to"])
        output_key = conn.get("output")

        # support legacy format with list of targets
        if isinstance(conn.get("to"), list):
            for tgt_uuid in conn["to"]:
                tgt_obj = instances.get(tgt_uuid)
                if src and tgt_obj:
                    src.connect_to(tgt_obj, output=0)
            continue

        if src and tgt and output_key is not None:
            src.connect_to(tgt, output=output_key)

    logger.success(f"Workspace loaded from {filepath}")
    return list(instances.values())


def create_module_instance(cls):
    instance = cls()
    register_module(instance)
    return instance
