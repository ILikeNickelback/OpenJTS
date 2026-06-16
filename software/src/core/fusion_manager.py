import dearpygui.dearpygui as dpg
from core.module_registry import get_registered_modules
from loguru import logger


class FusionManager:
    def __init__(self, label="Fusion Manager"):
        self.label = label
        self.win_id = f"fusion_manager_{label}"
        self.table_id = f"{self.win_id}_table"
        self.tag_to_module = {}

        with dpg.window(label=self.label, width=600, height=400, tag=self.win_id, pos=(50, 50)):
            dpg.add_button(label="Refresh", callback=self.refresh, width=-1)
            with dpg.table(tag=self.table_id, header_row=True,
                           resizable=True, policy=dpg.mvTable_SizingStretchProp,
                           borders_innerH=True, borders_outerH=True):
                dpg.add_table_column(label="Window")
                dpg.add_table_column(label="Merged Into")
                dpg.add_table_column(label="Restore")

        self.refresh()

    def refresh(self):
        for child in dpg.get_item_children(self.table_id, 1):
            dpg.delete_item(child)

        self.tag_to_module.clear()

        for module in get_registered_modules():
            short_id = module.UUID[:8]
            btn_tag = f"btn_{short_id}"
            self.tag_to_module[btn_tag] = module

            with dpg.table_row(parent=self.table_id):

                # ------- Column 1 : Window (drag + drop + hover)
                btn_lbl = f"{module.label}##{short_id}"
                dpg.add_button(label=btn_lbl,
                               tag=btn_tag,
                               drop_callback=self._on_drop,
                               payload_type="windows_fusion",
                               user_data=module,
                               callback=self._on_hover)

                dpg.add_drag_payload(
                    parent=btn_tag,
                    payload_type="windows_fusion",
                    drag_data=module.UUID
                )

                # ------- Column 2 : Merged Into
                tgt_label = module.merged_into.label if module.merged_into else ""
                dpg.add_text(tgt_label)

                # ------- Column 3 : Restore
                if module.merged_into:
                    dpg.add_button(label="Restore", width=100,
                                   user_data=module,
                                   callback=lambda s, a, u: self._restore(u))
                else:
                    dpg.add_spacer(width=70)

    def _on_drop(self, sender, payload, user_data):
        target_module = self.tag_to_module.get(sender)
        source_uuid = payload

        if not target_module:
            logger.warning(f"No target module found for sender: {sender}")
            return

        source_module = next(
            (m for m in get_registered_modules() if m.UUID == source_uuid), None)

        if not source_module:
            logger.warning(f"No source module found with UUID: {source_uuid}")
            return

        if source_module == target_module:
            logger.warning("Cannot merge module into itself.")
            return

        source_module.merge_into(target_module)
        logger.success(
            f"{source_module.label} merged into {target_module.label}")
        self.refresh()

    def _restore(self, module):
        module.restore_contents()
        logger.info(f"{module.label} restored")
        self.refresh()

    def _on_hover(self, sender, app_data, user_data):
        if dpg.is_item_hovered(sender):
            win_id = user_data.winID
            if dpg.does_item_exist(win_id):
                dpg.show_item(win_id)
                dpg.focus_item(win_id)
