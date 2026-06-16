import dearpygui.dearpygui as dpg
from core.module_registry import register_module
from loguru import logger


class WindowBase:
    def __init__(self,
                 label="Window",
                 pos=(10, 10),
                 win_width=-1,
                 win_height=-1,
                 uuid=None,
                 outputs=None,
                 visible=True,
                 **kwargs):

        self.label = label
        self.pos = pos
        self.win_width = win_width
        self.win_height = win_height
        self.visible = visible
        self.outputs = outputs or {}
        self.UUID = uuid or str(dpg.generate_uuid())
        self.winID = f"{label}_{self.UUID}"
        self.accepted_input_types = []

        if not hasattr(self, "_persistent_fields"):
            self._persistent_fields = ["label"]

        for field in self._persistent_fields:
            if field in kwargs:
                setattr(self, field, kwargs[field])

        self.connections = {k: [] for k in self.outputs}

        self._original_children = []     # list of item ids
        self._moved_out = []
        self.merged_into = None

        register_module(self)

    def _backup_children(self):
        """Save the current list of children for potential restoration."""
        if dpg.does_item_exist(self.winID):
            self._original_children = dpg.get_item_children(
                self.winID, 1) or []

    def oldmerge_into(self, target_window):
        """Move all widgets into another WindowBase instance."""
        if not isinstance(target_window, WindowBase):
            raise TypeError("target_window must be a WindowBase")

        self._backup_children()

        for child in self._original_children:
            dpg.move_item(child, parent=target_window.winID)
            self._moved_out.append(child)

        dpg.hide_item(self.winID)
        self.merged_into = target_window

    def merge_into(self, target_window):
        """Move all widgets into another WindowBase instance.
        Si cette fenêtre est DÉJÀ fusionnée ailleurs, on la restaure d'abord,
        puis on la fusionne dans la nouvelle cible.
        """
        if not isinstance(target_window, WindowBase):
            raise TypeError("target_window must be a WindowBase")

        if self.merged_into is target_window:
            return

        if self.merged_into is not None:
            self.restore_contents()

        self._backup_children()

        for child in self._original_children:
            dpg.move_item(child, parent=target_window.winID)
            self._moved_out.append(child)

        dpg.hide_item(self.winID)
        self.merged_into = target_window

    def restore_contents(self):
        """Move back previously moved widgets to this window."""
        for child in self._moved_out:
            if dpg.does_item_exist(child):
                dpg.move_item(child, parent=self.winID)

        self._moved_out.clear()
        self.merged_into = None
        dpg.show_item(self.winID)

    def is_merged(self):
        """Check whether this window has been merged elsewhere."""
        return bool(self._moved_out)

    def absorb(self, source_window):
        """Merge another window's content into this one."""
        if not isinstance(source_window, WindowBase):
            raise TypeError("source_window must be a WindowBase")
        source_window.merge_into(self)

    def eject(self, absorbed_window):
        """Restore a previously absorbed window."""
        if not isinstance(absorbed_window, WindowBase):
            raise TypeError("eject() expects a WindowBase instance.")
        absorbed_window.restore_contents()

    def get_merge_target_label(self):
        """Returns the label of the window this one is merged into, or None."""
        return self.merged_into.label if self.merged_into else None

    def connect_to(self, target, output=None):
        """
        Connect this module to a target module on a specified output.
        'output' can be either the output key (str) or its index (int).
        """
        if not hasattr(target, "accepted_input_types"):
            logger.error(f"Target {target} has no accepted_input_types")
            return False

        # Résolution de la clé de sortie
        if isinstance(output, int):
            try:
                output_key = list(self.outputs.keys())[output]
            except IndexError:
                logger.error(f"Invalid output index: {output}")
                return False
        elif isinstance(output, str):
            if output not in self.outputs:
                logger.error(f"Output key '{output}' not found in outputs")
                return False
            output_key = output
        else:
            logger.error(
                f"Output must be a key (str) or index (int), got {type(output)}")
            return False

        # Vérification de compatibilité
        output_type = self.outputs[output_key]
        input_types = getattr(target, "accepted_input_types", [])

        if input_types and output_type not in input_types:
            logger.warning(
                f"Incompatible types: {output_type} → {input_types}")
            return False

        if target not in self.connections[output_key]:
            self.connections[output_key].append(target)

        return True

    def _is_output_compatible_with(self, target):
        output_types = getattr(self, "output_types", [])
        input_types = getattr(target, "accepted_input_types", [])
        return any(o in input_types for o in output_types)

    def disconnect_from(self, *windows):
        for win in windows:
            if win in self.outputs:
                self.outputs.remove(win)

    def oldserialize(self):
        # Si la fenêtre existe dans DPG, mettre à jour position et taille actuelles
        if dpg.does_item_exist(self.winID):
            self.pos = dpg.get_item_pos(self.winID)
            self.win_width, self.win_height = dpg.get_item_rect_size(
                self.winID)
            self.visible = dpg.is_item_visible(self.winID)

        params = {field: getattr(self, field)
                  for field in self._persistent_fields}
        return {
            "module": self.__class__.__module__.replace("modules.", ""),
            "class_name": self.__class__.__name__,
            "uuid": self.UUID,
            "pos": self.pos,
            "size": [self.win_width, self.win_height],
            "visible": self.visible,
            "params": params
        }

    def serialize(self):
        if dpg.does_item_exist(self.winID):
            self.pos = dpg.get_item_pos(self.winID)
            self.win_width, self.win_height = dpg.get_item_rect_size(
                self.winID)
            self.visible = dpg.is_item_visible(self.winID)

        params = {field: getattr(self, field)
                  for field in self._persistent_fields}

        if self.merged_into:
            params["merged_into"] = self.merged_into.UUID

        return {
            "module": self.__class__.__module__.replace("modules.", ""),
            "class_name": self.__class__.__name__,
            "uuid": self.UUID,
            "pos": self.pos,
            "size": [self.win_width, self.win_height],
            "visible": self.visible,
            "params": params,
        }

    def close(self):
        if dpg.does_item_exist(self.winID):
            dpg.delete_item(self.winID)
