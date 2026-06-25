import tkinter as tk
from tkinter import filedialog, simpledialog

import dearpygui.dearpygui as dpg
from core.tabbed_window_manager import TabbedWindowManager
import core.workspace_manager as workspace_manager
from windows.log_window import LogWindow
from pathlib import Path


def _tk_dir(title: str = "Select folder") -> str:
    """Open a native Windows folder-picker; return selected path or ''."""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askdirectory(title=title, parent=root)
    root.destroy()
    return path or ""


def _tk_file(title: str = "Open file", filetypes=()) -> str:
    """Open a native Windows file-picker; return selected path or ''."""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askopenfilename(title=title, filetypes=filetypes, parent=root)
    root.destroy()
    return path or ""


def _tk_ask(title: str, prompt: str) -> str:
    """Open a native Windows input dialog; return entered string or ''."""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    value = simpledialog.askstring(title, prompt, parent=root)
    root.destroy()
    return (value or "").strip()


class Main_win:
    """
    Primary application window.

    Layout::

        dpg.window  (primary window, fills viewport)
        └── menu_bar
        └── child_window  "main_body"   (fills remaining space below menu bar)
            └── TabbedWindowManager     (tab bar + tab content fills this child)
    """

    def __init__(self):
        self.winID = "main_win"

        # Set via setup() after layout.create_windows() runs
        self._get_tabs_fn = None
        self._restore_fn = None
        self._app_state = None
        self._bus = None

        self._workspace_dir: Path | None = None  # set after first Save As

        self.log_window = LogWindow()

        with dpg.window(tag=self.winID):
            # ── Menu bar ────────────────────────────────────────────────
            with dpg.menu_bar():
                with dpg.menu(label="File"):
                    dpg.add_menu_item(
                        label="Save",
                        tag="menu_save_workspace",
                        callback=self._save_workspace,
                        enabled=False,
                    )
                    dpg.add_menu_item(
                        label="Save As",
                        callback=self._save_workspace_as,
                    )
                    dpg.add_menu_item(
                        label="Open Workspace",
                        callback=self._open_load_dialog,
                    )
                with dpg.menu(label="Tools"):
                    dpg.add_menu_item(
                        label="Show Debug",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Debug),
                    )
                    dpg.add_menu_item(
                        label="Show Font Manager",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Font),
                    )
                    dpg.add_menu_item(
                        label="Show Item Registry",
                        callback=lambda: dpg.show_tool(dpg.mvTool_ItemRegistry),
                    )
                    dpg.add_menu_item(
                        label="Show Metrics",
                        callback=lambda: dpg.show_tool(dpg.mvTool_Metrics),
                    )
                    dpg.add_menu_item(
                        label="Toggle Fullscreen",
                        callback=lambda: dpg.toggle_viewport_fullscreen(),
                    )
                    dpg.add_menu_item(
                        label="Show About",
                        callback=lambda: dpg.show_tool(dpg.mvTool_About),
                    )
                    dpg.add_menu_item(
                        label="Show Logs",
                        callback=lambda: self.log_window.show(),
                    )

            with dpg.child_window(
                tag="main_body",
                autosize_x=True,
                autosize_y=True,
                border=False,
            ):
                self.control_tabs = TabbedWindowManager(
                    label="Control Panel",
                    parent="main_body",
                )

        # ── Theme ────────────────────────────────────────────────────────
        with dpg.theme() as mainwin_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (20, 20, 25, 255))
        dpg.bind_item_theme(self.winID, mainwin_theme)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def setup(self, state, bus, get_tabs_fn, restore_fn):
        """
        Call this after create_windows() to wire in the layout functions.

        Parameters
        ----------
        state        : AppState
        bus          : EventBus
        get_tabs_fn  : callable() -> dict   (layout.get_experiment_tabs)
        restore_fn   : callable(data, ...)  (layout.restore_workspace)
        """
        self._app_state = state
        self._bus = bus
        self._get_tabs_fn = get_tabs_fn
        self._restore_fn = restore_fn

    # ------------------------------------------------------------------
    # Save workspace  (native Windows dialogs)
    # ------------------------------------------------------------------
    def _save_workspace(self):
        """Save to the already-known workspace folder (no prompts)."""
        if self._workspace_dir is None:
            self._save_workspace_as()
            return
        try:
            tabs = self._get_tabs_fn() if self._get_tabs_fn else {}
            workspace_manager.save_to(
                workspace_dir=self._workspace_dir,
                experiment_tabs=tabs,
                state=self._app_state,
            )
        except Exception as e:
            print(f"Workspace save error: {e}")

    def _save_workspace_as(self):
        """Prompt for folder + name, then save."""
        folder = _tk_dir("Select save folder")
        if not folder:
            return

        name = _tk_ask("Workspace name", "Enter a name for this workspace:")
        if not name:
            return

        workspace_dir = Path(folder) / name
        try:
            tabs = self._get_tabs_fn() if self._get_tabs_fn else {}
            workspace_manager.save_to(
                workspace_dir=workspace_dir,
                experiment_tabs=tabs,
                state=self._app_state,
            )
            self._workspace_dir = workspace_dir
            dpg.configure_item("menu_save_workspace", enabled=True)
        except Exception as e:
            print(f"Workspace save error: {e}")

    # ------------------------------------------------------------------
    # Open workspace  (native Windows dialogs)
    # ------------------------------------------------------------------
    def _open_load_dialog(self):
        file_path = _tk_file(
            title="Open workspace.json",
            filetypes=[
                ("Workspace file", "workspace.json"),
                ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return

        path = Path(file_path)
        if path.is_dir():
            path = path / "workspace.json"
        if not path.exists():
            return

        try:
            workspace_data = workspace_manager.load(path)
        except Exception as e:
            print(f"Workspace load error: {e}")
            return

        self._workspace_dir = path.parent
        dpg.configure_item("menu_save_workspace", enabled=True)

        if self._restore_fn and self._app_state and self._bus:
            self._restore_fn(
                workspace_data,
                self._app_state,
                self._bus,
                self.control_tabs,
            )
