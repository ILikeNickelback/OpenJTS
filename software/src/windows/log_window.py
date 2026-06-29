"""Tools-menu window that mirrors loguru output in real time.

A loguru sink pushes formatted lines into a thread-safe deque (loguru
sinks can fire from any worker thread). The main render loop drains
that deque into the DPG text widget once per frame, keeping all DPG
calls on the main thread.
"""

from collections import deque

import dearpygui.dearpygui as dpg
from loguru import logger

from core.window_base import WindowBase

MAX_LINES = 2000
LOG_FORMAT = "{time:HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"


class LogWindow(WindowBase):
    """Displays live loguru messages in a scrollable DPG window."""

    def __init__(
        self,
        label="Logs",
        pos=(50, 50),
        win_width=900,
        win_height=500,
        uuid=None,
        visible=False,
    ):
        super().__init__(
            label=label,
            pos=pos,
            win_width=win_width,
            win_height=win_height,
            uuid=uuid,
            visible=visible,
        )
        self._lines = deque(maxlen=MAX_LINES)
        self._pending = deque()
        self._buildui()
        logger.add(self._sink, format=LOG_FORMAT)

    def _sink(self, message):
        self._pending.append(message.rstrip("\n"))

    def _buildui(self):
        with dpg.window(
            label=self.label,
            pos=self.pos,
            width=self.win_width,
            height=self.win_height,
            tag=self.winID,
            show=self.visible,
        ):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Clear", callback=self.clear)
                dpg.add_checkbox(
                    label="Autoscroll",
                    default_value=True,
                    tag=f"log_autoscroll_{self.UUID}",
                )
            dpg.add_separator()
            with dpg.child_window(
                tag=f"log_body_{self.UUID}", autosize_x=True, autosize_y=True
            ):
                dpg.add_text("", tag=f"log_text_{self.UUID}")

    def show(self):
        dpg.show_item(self.winID)

    def clear(self):
        logger.debug("'Clear' button clicked")
        self._lines.clear()
        dpg.set_value(f"log_text_{self.UUID}", "")

    def poll(self):
        """Drain pending log lines into the widget. Call once per frame."""
        if not self._pending:
            return
        while self._pending:
            self._lines.append(self._pending.popleft())
        dpg.set_value(f"log_text_{self.UUID}", "\n".join(self._lines))
        if dpg.get_value(f"log_autoscroll_{self.UUID}"):
            dpg.set_y_scroll(
                f"log_body_{self.UUID}", dpg.get_y_scroll_max(f"log_body_{self.UUID}")
            )
