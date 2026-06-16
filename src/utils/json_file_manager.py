import dearpygui.dearpygui as dpg
import json

class JsonFileManager:
    def __init__(self):
        self.on_load_complete = None
        self._save_data = None
        self.uuid = dpg.generate_uuid()

    def create_dialogs(self):
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
        self._save_data = data_dict
        dpg.show_item(f"save_dialog_{self.uuid}")

    def load(self):
        dpg.show_item(f"load_dialog_{self.uuid}")

    def _save_callback(self, sender, app_data):
        path = app_data['file_path_name']
        with open(path, 'w') as f:
            json.dump(self._save_data, f, indent=4)

    def _load_callback(self, sender, app_data):
        path = app_data['file_path_name']
        with open(path, 'r') as f:
            data = json.load(f)
        if self.on_load_complete:
            self.on_load_complete(data)
