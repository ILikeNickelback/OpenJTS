import dearpygui.dearpygui as dpg
from core.module_registry import get_available_modules, create_module_instance
from collections import defaultdict
from loguru import logger


class NodeEditor:
    """
    NodeEditor handles module instantiation and linking within a DearPyGui node editor context.
    Supports module creation, deletion, validation of type compatibility, and connection tracking.
    """

    def __init__(self, label="Node editor"):

        self.UUID = str(dpg.generate_uuid())
        self.winID = f"{label}_{self.UUID}"
        self.node_map = {}  # node_id -> module instance
        self.link_map = {}  # link_id -> (output_node, input_node)
        self.mouse_pos = [0, 0]  # Position of last right click
        self.popup_tag = "node_popup_menu"
        self.editor_tag = "node_editor"
        self.anchor_node_tag = "anchor_node"

        with dpg.window(label=label, width=800, height=600, tag=self.winID):

            with dpg.node_editor(callback=self.link_callback, delink_callback=self.delink_callback, tag=self.editor_tag):
                with dpg.node(label="", draggable=False, tag=self.anchor_node_tag):
                    with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output):
                        dpg.add_text("")

            # Right-click handler
            with dpg.handler_registry():
                dpg.add_mouse_click_handler(
                    button=dpg.mvMouseButton_Right,
                    callback=self.right_click_callback
                )
                dpg.add_mouse_click_handler(
                    button=dpg.mvMouseButton_Left,
                    callback=self.left_click_callback
                )

            with dpg.window(tag=self.popup_tag, show=False, no_title_bar=True, no_resize=True, no_move=True):
                grouped_modules = defaultdict(list)
                for name, cls in get_available_modules().items():
                    folder, module = name.split(".", 1)
                    grouped_modules[folder].append((module, cls))

                for folder, entries in grouped_modules.items():
                    with dpg.menu(label=folder):
                        for module_name, cls in entries:
                            dpg.add_menu_item(
                                label=module_name, callback=self.add_node, user_data=cls)

        logger.info("Node editor initialized")

    def get_mouse_pos(self):
        """
        Return (relative_to_editor, absolute) mouse coordinates,
        using an invisible anchor node to deduce internal panning.
        """
        abs_pos = dpg.get_mouse_pos(local=False)

        # where the anchor node appears on screen
        ref_screen_pos = dpg.get_item_rect_min(self.anchor_node_tag)
        # where the anchor node is supposed to be (0,0)
        ref_editor_pos = dpg.get_item_pos(self.anchor_node_tag)

        # Correction based on how much the anchor moved due to panning
        pan_offset = [
            ref_editor_pos[0] - ref_screen_pos[0],
            ref_editor_pos[1] - ref_screen_pos[1]
        ]

        # Relative position = absolute position + panning
        rel_pos = [
            abs_pos[0] + pan_offset[0],
            abs_pos[1] + pan_offset[1]
        ]

        return rel_pos, abs_pos

    def right_click_callback(self, sender, app_data):
        if dpg.is_item_hovered(self.editor_tag):
            self.mouse_pos, absolute_mouse_pos = self.get_mouse_pos()
            dpg.focus_item(self.popup_tag)
            dpg.configure_item(
                self.popup_tag,
                pos=absolute_mouse_pos,
                show=True)

    def left_click_callback(self, sender, app_data):
        if dpg.is_item_visible(self.popup_tag):
            if dpg.is_item_hovered(self.popup_tag):
                return
            for child in dpg.get_item_children(self.popup_tag, 1):
                if dpg.is_item_hovered(child):
                    return
            dpg.configure_item(self.popup_tag, show=False)

    def delete_node(self, sender, app_data, node_id):
        if node_id in self.node_map:
            dpg.delete_item(node_id)
            self.node_map[node_id].close()
            del self.node_map[node_id]
            # Remove associated links
            to_remove = [lid for lid, (src, tgt) in self.link_map.items(
            ) if src == node_id or tgt == node_id]
            for lid in to_remove:
                src_id, tgt_id = self.link_map[lid]
                src = self.node_map.get(src_id)
                tgt = self.node_map.get(tgt_id)
                if src and tgt and tgt in src.outputs:
                    src.outputs.remove(tgt)
                dpg.delete_item(lid)
                del self.link_map[lid]

    def add_node(self, sender, app_data, module_class):
        label = module_class.__name__

        with dpg.node(label=label, parent=self.editor_tag, pos=self.mouse_pos) as node_id:
            with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Input):
                dpg.add_text("In")

            instance = create_module_instance(module_class)
            self.node_map[node_id] = instance

            for output in instance.outputs.keys():
                with dpg.node_attribute(attribute_type=dpg.mvNode_Attr_Output, tag=f"{node_id}_{output}"):
                    dpg.add_text(output)

                # with dpg.tooltip(parent=f"{node_id}_{output}"):
                #     dpg.add_text(f"{instance.outputs[output].description}")

        # Add right-click popup to node for deletion
        with dpg.popup(node_id, mousebutton=dpg.mvMouseButton_Right):
            dpg.add_button(label="Delete Node",
                           callback=self.delete_node, user_data=node_id)

        # Hide popup after adding
        dpg.configure_item(self.popup_tag, show=False)

    def _get_output_IDs(self, node_id):
        """Return a list of attribute IDs that are mvNode_Attr_Output under the given node."""
        children = dpg.get_item_children(node_id, 1)
        output_ids = []
        for attr_id in children:
            if dpg.get_item_type(attr_id) == "mvAppItemType::mvNodeAttribute" and dpg.get_item_configuration(attr_id).get("attribute_type") == dpg.mvNode_Attr_Output:
                output_ids.append(attr_id)

        return output_ids

    def link_callback(self, sender, app_data):
        link_id = dpg.generate_uuid()
        from_attr, to_attr = app_data

        from_node = dpg.get_item_parent(from_attr)
        to_node = dpg.get_item_parent(to_attr)

        src = self.node_map.get(from_node)
        tgt = self.node_map.get(to_node)

        # node_output_ids = dpg.get_item_children(from_node, 1)[1:]
        node_output_ids = self._get_output_IDs(from_node)

        output_index = node_output_ids.index(from_attr)

        if src and tgt:
            src_key = list(src.outputs.keys())[output_index]
            src_type = src.outputs[src_key]
            tgt_types = getattr(tgt, "accepted_input_types", [])

            if tgt_types and src_type not in tgt_types:
                logger.warning(f"Incompatible types: {src_type} → {tgt_types}")
                return

            if tgt not in src.connections[src_key]:
                src.connections[src_key].append(tgt)
                dpg.add_node_link(from_attr, to_attr,
                                  parent=self.editor_tag, tag=link_id)
                self.link_map[link_id] = (from_attr, to_attr)

    def delink_callback(self, sender, app_data):
        link_id = app_data
        if link_id not in self.link_map:
            dpg.delete_item(link_id)       # sécurité
            return

        from_attr, to_attr = self.link_map.pop(link_id)
        from_node = dpg.get_item_parent(from_attr)
        to_node = dpg.get_item_parent(to_attr)

        src = self.node_map.get(from_node)
        tgt = self.node_map.get(to_node)

        if src and tgt:
            # node_output_ids = dpg.get_item_children(from_node, 1)[1:]
            node_output_ids = self._get_output_IDs(from_node)
            output_index = node_output_ids.index(from_attr)
            src_key = list(src.outputs.keys())[output_index]

            if tgt in src.connections[src_key]:
                src.connections[src_key].remove(tgt)

        dpg.delete_item(link_id)
