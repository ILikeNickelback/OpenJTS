import json
import tkinter as tk
from tkinter import filedialog

import dearpygui.dearpygui as dpg
from core.window_base import WindowBase
from utils.json_file_manager import JsonFileManager


def _tk_save_file(
    title="Save as",
    filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
    defaultextension=".json",
) -> str:
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.asksaveasfilename(
        title=title, filetypes=filetypes, defaultextension=defaultextension, parent=root
    )
    root.destroy()
    return path or ""


class Sample_container_win(WindowBase):
    """
    Collected results manager panel.

    Each completed acquisition appends a named, checkable entry. Toggling
    a checkbox adds or removes that series in the lineplot via the
    ``plot_cmd`` bus event. Entries can be renamed inline and deleted via
    right-click context menu. Selected samples can be exported to JSON.
    """

    def __init__(
        self,
        label="Sample Container",
        pos=None,
        width=None,
        height=None,
        uuid=None,
        visible=True,
        state=None,
        bus=None,
        experiment_name=None,
    ):
        super().__init__(label=label, uuid=uuid, visible=visible)
        self.json = JsonFileManager()
        self.json.create_dialogs()

        self.state = state
        self.bus = bus
        self.experiment_name = experiment_name

        self.clear_samples_tag = f"clear_samples_{self.UUID}"
        self.select_all_samples_tag = f"select_all_samples_{self.UUID}"
        self.deselect_all_samples_tag = f"deselect_all_samples_{self.UUID}"
        self.samples_group_tag = f"samples_group_{self.UUID}"

        self.samples_dict = {}
        self.samples_count = 0
        self.bassline_points = 4

        if bus:
            bus.subscribe(
                "final_data",
                lambda final_results, time_values, sequence, **_: self.input_cb(
                    y=final_results, x=time_values, sequence=sequence
                ),
            )
            bus.subscribe(
                "bassline_points_changed",
                lambda nbr_of_points, **_: self.input_cb_processing(nbr_of_points),
            )

        with dpg.child_window(
            label=self.label,
            width=width,
            height=height,
            pos=pos,
            tag=self.winID,
            show=visible,
        ):
            dpg.add_button(
                label="Select all", width=-1, callback=self.select_all_samples_cb
            )
            dpg.add_button(
                label="Deselect all", width=-1, callback=self.deselect_all_samples_cb
            )
            dpg.add_button(
                label="Save selected samples",
                width=-1,
                callback=self.save_selected_samples,
            )
            dpg.add_group(tag=self.samples_group_tag)

    def save_selected_samples(self):
        selected_samples = {}
        for UUID, sample in self.samples_dict.items():
            if dpg.get_value(f"sample_checkbox_{self.UUID}_{UUID}"):
                selected_samples[sample["name"]] = {
                    "sequence": sample["sequence"],
                    "time": [float(t) for t in sample["x"]],
                    "values": [float(v) for v in sample["y"]],
                }

        if not selected_samples:
            return

        path = _tk_save_file(title="Save selected samples")
        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            json.dump(selected_samples, f, indent=4)

    def input_cb(self, *args, **kwargs):
        y = kwargs.get("y") or (args[0] if args and isinstance(args[0], list) else None)
        x = kwargs.get("x") or (
            args[1] if len(args) > 1 and isinstance(args[1], list) else None
        )
        sequence = kwargs.get("sequence")
        name = kwargs.get("name", None)
        UUID = kwargs.get("uuid", None)

        if UUID is None:
            self.samples_count += 1
            UUID = self.samples_count

        if name is None:
            sample_id = ""
            if self.state and self.experiment_name:
                exp = next(
                    (
                        e
                        for e in self.state.get_experiments()
                        if e["name"] == self.experiment_name
                    ),
                    {},
                )
                sample_id = exp.get("sample_id", "") or ""
            name = sample_id if sample_id else f"{UUID}"

        self.samples_dict[UUID] = {
            "y": y,
            "x": x,
            "sequence": sequence,
            "name": name,
            "uuid": UUID,
        }

        dpg.push_container_stack(self.samples_group_tag)
        with dpg.group(horizontal=True, tag=f"sample_group_{self.UUID}_{UUID}"):
            dpg.add_checkbox(
                tag=f"sample_checkbox_{self.UUID}_{UUID}",
                default_value=True,
                callback=self.sample_checkbox_cb,
                user_data=UUID,
            )
            with dpg.popup(dpg.last_item(), mousebutton=dpg.mvMouseButton_Right):
                dpg.add_menu_item(
                    label="Delete", user_data=UUID, callback=self.delete_sample_cb
                )

            dpg.add_input_text(
                tag=f"sample_name_{self.UUID}_{UUID}",
                default_value=f"{name}",
                callback=self.sample_name_cb,
                user_data=UUID,
            )
            with dpg.popup(dpg.last_item(), mousebutton=dpg.mvMouseButton_Right):
                dpg.add_menu_item(
                    label="Delete", user_data=UUID, callback=self.delete_sample_cb
                )
        dpg.pop_container_stack()

        self.sample_checkbox_cb(f"sample_checkbox_{UUID}", True, UUID)

    def sample_checkbox_cb(self, sender, app_data, user_data):
        UUID = user_data
        if app_data:
            y = self.samples_dict[UUID]["y"]
            x = self.samples_dict[UUID]["x"]
            name = self.samples_dict[UUID]["name"]

            cmd = {
                "action": "add serie",
                "data": {"y": y, "x": x, "name": name, "uuid": f"{self.UUID}_{UUID}"},
            }
            self.trigger_cb(cmd=cmd)
        else:
            cmd = {"action": "remove serie", "data": {"uuid": f"{self.UUID}_{UUID}"}}
            self.trigger_cb(cmd=cmd)

    def sample_name_cb(self, sender, app_data, user_data):
        UUID = user_data
        new_name = app_data.strip()

        if new_name:
            self.samples_dict[UUID]["name"] = new_name
            cmd = {
                "action": "update serie name",
                "data": {"name": new_name, "uuid": f"{self.UUID}_{UUID}"},
            }
            self.trigger_cb(cmd=cmd)
            if self.bus:
                self.bus.publish("serie_renamed", series_id=UUID - 1, name=new_name)

    def delete_sample_cb(self, sender, app_data, user_data):
        UUID = user_data
        if UUID in self.samples_dict:
            del self.samples_dict[UUID]
            dpg.delete_item(f"sample_group_{self.UUID}_{UUID}")
            cmd = {"action": "remove serie", "data": {"uuid": f"{self.UUID}_{UUID}"}}
            self.trigger_cb(cmd=cmd)

    def select_all_samples_cb(self, sender, app_data):
        for UUID in self.samples_dict:
            dpg.set_value(f"sample_checkbox_{self.UUID}_{UUID}", True)
            self.sample_checkbox_cb(None, True, UUID)

    def deselect_all_samples_cb(self, sender, app_data):
        for UUID in self.samples_dict:
            dpg.set_value(f"sample_checkbox_{self.UUID}_{UUID}", False)
            self.sample_checkbox_cb(None, False, UUID)

    def clear_samples_cb(self, sender, app_data):
        for UUID in list(self.samples_dict.keys()):
            dpg.delete_item(f"sample_group_{self.UUID}_{UUID}")
            del self.samples_dict[UUID]
            self.sample_checkbox_cb(None, False, UUID)

    def get_samples(self) -> list:
        """Return all samples as a serialisable list (used by autosave)."""
        return [
            {
                "final_results": sample["y"],
                "time_values": sample["x"],
                "sequence": sample["sequence"],
                "label": sample["name"],
            }
            for sample in self.samples_dict.values()
        ]

    def load_results(self, results: list):
        """Recreate sample entries from a saved results list (workspace restore)."""
        for r in results:
            self.input_cb(
                y=r.get("final_results"),
                x=r.get("time_values"),
                sequence=r.get("sequence"),
                name=r.get("label"),
            )

    def trigger_cb(self, **kwargs):
        if self.bus:
            self.bus.publish("plot_cmd", **kwargs)


EXPORTED_CLASS = Sample_container_win
EXPORTED_NAME = "Sample Container"
