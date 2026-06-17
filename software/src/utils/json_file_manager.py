"""DearPyGui-based manager for saving and loading JSON files via file dialogs."""

import json
import dearpygui.dearpygui as dpg


class JsonFileManager:
    """Manages JSON file save and load operations via DearPyGui file dialogs.

    Attributes:
        on_load_complete (callable | None): Optional callback invoked with the loaded
            data dict after a successful file load.
        _save_data (dict | None): Data staged for saving, set by `save()`.
        uuid (int): Unique DearPyGui ID used to tag this instance's dialogs.
    """

    def __init__(self):
        self.on_load_complete = None
        self._save_data = None
        self.uuid = dpg.generate_uuid()

    def create_dialogs(self):
        """Register the save and load file dialogs with DearPyGui.

        Must be called inside an active DearPyGui context before calling
        `save()` or `load()`.
        """
        with dpg.file_dialog(directory_selector=False, show=False,
                             callback=self._save_callback,
                             tag=f"save_dialog_{self.uuid}",
                             width=700, height=400):
            dpg.add_file_extension(".json", color=(150, 255, 150, 255))
            dpg.add_file_extension(".*")

        with dpg.file_dialog(directory_selector=False, show=False,
                             callback=self._load_callback,
                             tag=f"load_dialog_{self.uuid}",
                             width=700, height=400):
            dpg.add_file_extension(".json", color=(150, 255, 150, 255))
            dpg.add_file_extension(".*")

    def save(self, data_dict):
        """Open the save dialog to write `data_dict` to a JSON file.

        Args:
            data_dict (dict): Data to serialize and save.
        """
        self._save_data = data_dict
        dpg.show_item(f"save_dialog_{self.uuid}")

    def load(self):
        """Open the load dialog to select and read a JSON file."""
        dpg.show_item(f"load_dialog_{self.uuid}")

    def _save_callback(self, app_data):
        """DearPyGui callback that writes the staged data to the selected path.

        Args:
            sender: DearPyGui item that triggered the callback (unused).
            app_data (dict): Dialog result containing 'file_path_name'.
        """
        path = app_data['file_path_name']
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._save_data, f, indent=4)

    def _load_callback(self, app_data):
        """DearPyGui callback that reads the selected JSON file and fires `on_load_complete`.

        Args:
            sender: DearPyGui item that triggered the callback (unused).
            app_data (dict): Dialog result containing 'file_path_name'.
        """
        path = app_data['file_path_name']
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if self.on_load_complete:
            self.on_load_complete(data)
