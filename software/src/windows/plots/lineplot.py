import dearpygui.dearpygui as dpg
import numpy as np
from core.window_base import WindowBase


class Lineplot_win(WindowBase):
    """
    Live and final results line plot panel.

    Handles three data flows: live streaming (one scalar per frame),
    intermediate per-run series during averaging, and final averaged
    results. Nearest-point annotation is shown on hover when the checkbox
    is enabled. Series are managed externally via the ``plot_cmd`` bus
    event (add, remove, rename). Final results are accumulated in
    _saved_results for workspace persistence.
    """

    LIVE_UUID = 999  # Constant to identify live data series

    def __init__(
        self,
        label="Lineplot",
        pos=None,
        width=None,
        height=None,
        uuid=None,
        visible=True,
        state=None,
        bus=None,
        experiment_name=None,
        experiment_type=None,
    ):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self.state = state
        self.bus = bus
        self.experiment_name = experiment_name
        self.experiment_type = experiment_type

        # Saved final results for workspace persistence
        self._saved_results = []

        # Live data buffers
        self.live_x, self.live_y = [], []
        self.live_series_tag = f"live_series_{self.LIVE_UUID}"
        self.selected_series = None

        # Tags of intermediate (per-run) series, cleared when average is published
        self._intermediate_tags = []

        # Tags for DPG items
        self.plot_tag = f"lineplot_plot_{self.UUID}"
        self.annot_check_tag = f"lineplot_annot_check_{self.UUID}"
        self.xaxis_tag = f"lineplot_x_axis_{self.UUID}"
        self.yaxis_tag = f"lineplot_y_axis_{self.UUID}"
        self.dragline_tag = f"lineplot_dragline_{self.UUID}"
        self.closest_point_annot_tag = f"closest_point_annot_{self.UUID}"

        self.pos = pos
        self.width = width
        self.height = height

        # Build UI
        self._build_ui()

        if bus:
            bus.subscribe(
                "live_data",
                lambda y, x, **_: self.plot_data(x=x, y=y, UUID=self.LIVE_UUID),
            )
            bus.subscribe("final_data", self._on_final_data)
            bus.subscribe("intermediate_data", self._on_intermediate_data)
            bus.subscribe("clear_live", lambda **_: self.clear_live_data())
            bus.subscribe(
                "clear_intermediates", lambda **_: self._clear_intermediate_series()
            )
            bus.subscribe(
                "plot_cmd", lambda cmd=None, **_: self._handle_cmd(cmd) if cmd else None
            )
            bus.subscribe("serie_renamed", self._on_serie_renamed)

    # --------------------------
    # UI BUILDING
    # --------------------------
    def _build_ui(self):
        self._container_tag = f"seq_container_{self.UUID}"
        with dpg.child_window(
            tag=self._container_tag,
            label="Lineplot",
            width=self.width,
            height=self.height,
            pos=self.pos,
            show=self.visible,
        ):
            dpg.add_checkbox(
                label="Annotation", tag=self.annot_check_tag, default_value=True
            )

            with dpg.plot(label="Line Series", height=-1, width=-1, tag=self.plot_tag):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (ms)", tag=self.xaxis_tag)
                dpg.add_plot_axis(
                    dpg.mvYAxis, label=self._y_axis_label(), tag=self.yaxis_tag
                )
                dpg.add_drag_line(
                    label="dline1",
                    tag=self.dragline_tag,
                    color=[255, 0, 0, 255],
                    callback=self.dragline_callback,
                )

            with dpg.handler_registry():
                dpg.add_mouse_move_handler(callback=self.plot_change_callback)

            dpg.configure_item(self.plot_tag, anti_aliased=True, crosshairs=True)

    # --------------------------
    # EXPERIMENT TYPE
    # --------------------------
    def _y_axis_label(self) -> str:
        return "dI/I" if self.experiment_type == "Spectro" else "I"

    def set_experiment_type(self, experiment_type: str) -> None:
        self.experiment_type = experiment_type
        if dpg.does_item_exist(self.yaxis_tag):
            dpg.configure_item(self.yaxis_tag, label=self._y_axis_label())

    # --------------------------
    # INTERNAL HELPERS
    # --------------------------
    def find_closest_point(self, mouse_x, mouse_y, x_data, y_data):
        x_scale = 1 / np.ptp(x_data + 1e-9)
        y_scale = 1 / np.ptp(y_data + 1e-9)
        distances = np.hypot((x_data - mouse_x) * x_scale, (y_data - mouse_y) * y_scale)
        return np.argmin(distances)

    def _get_active_series(self):
        """
        Return currently selected line series data or first series in plot.
        """
        if (
            self.selected_series
            and dpg.does_item_exist(self.selected_series)
            and dpg.get_item_type(self.selected_series) == "mvAppItemType::mvLineSeries"
        ):
            series_data = dpg.get_value(self.selected_series)
            # dpg.get_value returns (x, y, x2, y2, y3) for line series
            # We only need the first two elements
            if isinstance(series_data, (list, tuple)) and len(series_data) >= 2:
                return series_data[0], series_data[1]
            return [], []

        children = dpg.get_item_children(self.yaxis_tag, 1)
        if children:
            series_data = dpg.get_value(children[0])
            if isinstance(series_data, (list, tuple)) and len(series_data) >= 2:
                return series_data[0], series_data[1]
        return [], []

    # --------------------------
    # PLOTTING CALLBACKS
    # --------------------------
    def plot_change_callback(self, sender, app_data):
        if not dpg.is_item_hovered(self.plot_tag):
            return
        if not dpg.get_value(self.annot_check_tag):
            return

        if dpg.does_item_exist(self.closest_point_annot_tag):
            dpg.delete_item(self.closest_point_annot_tag)

        xplot, yplot = self._get_active_series()
        if not xplot or not yplot:
            return

        mouse_x, mouse_y = dpg.get_plot_mouse_pos()
        index = self.find_closest_point(
            mouse_x, mouse_y, np.array(xplot), np.array(yplot)
        )

        text = f"Index: {index}\nX: {xplot[index]}\nY: {yplot[index]}"
        dpg.add_plot_annotation(
            tag=self.closest_point_annot_tag,
            label=text,
            default_value=(xplot[index], yplot[index]),
            offset=(25, -25),
            color=[255, 255, 0, 255],
            parent=self.plot_tag,
        )

    def autofit_axis(self):
        dpg.fit_axis_data(self.xaxis_tag)
        dpg.fit_axis_data(self.yaxis_tag)

    def clear_live_data(self):
        """Clear live series and buffers"""
        if dpg.does_item_exist(self.live_series_tag):
            dpg.delete_item(self.live_series_tag)
        self.live_x, self.live_y = [], []

    # --------------------------
    # PLOTTING LOGIC
    # --------------------------
    def plot_data(self, x, y, name="Live", UUID=None):
        """
        Unified plotting method for both live and static data.
        Live series are identified by UUID=LIVE_UUID.
        """

        is_live = UUID == self.LIVE_UUID

        # Initialize or update live series
        if is_live:
            if not dpg.does_item_exist(self.live_series_tag):
                # FRESH START - clear old data
                self.live_x = [x]
                self.live_y = [y]
                dpg.add_line_series(
                    x=self.live_x,
                    y=self.live_y,
                    label="Live",
                    tag=self.live_series_tag,
                    parent=self.yaxis_tag,
                )
            else:
                if isinstance(x, list) or isinstance(y, list):
                    print("⚠ Live data must be scalar")
                    return
                self.live_x.append(x)
                self.live_y.append(y)
                dpg.configure_item(self.live_series_tag, x=self.live_x, y=self.live_y)

            # Autofit disabled for live data (perf: too expensive per-point)
            self.autofit_axis()
            return

        if x is None and y is not None:
            x = list(range(len(y)))

        series_id = f"prevplot_{UUID}"
        if not dpg.does_item_exist(series_id):
            # Create new series with COPIES of the data
            dpg.add_line_series(
                x=list(x), y=list(y), label=name, tag=series_id, parent=self.yaxis_tag
            )
        else:
            # Update existing series with COPIES of the data
            dpg.configure_item(series_id, x=list(x), y=list(y))

        self.selected_series = series_id
        self.autofit_axis()

    # --------------------------
    # BUS HANDLERS
    # --------------------------
    def _get_sample_id(self) -> str:
        if self.state and self.experiment_name:
            exp = next(
                (
                    e
                    for e in self.state.get_experiments()
                    if e["name"] == self.experiment_name
                ),
                {},
            )
            return exp.get("sample_id", "") or ""
        return ""

    def _on_final_data(
        self, final_results, time_values, series_id=0, n_avg=1, sequence=None, **_
    ):
        if time_values is None:
            time_values = list(range(len(final_results)))
        sample_id = self._get_sample_id()
        base = sample_id if sample_id else f"Result {series_id + 1}"
        label = f"{base} (avg×{n_avg})" if n_avg > 1 else base
        # Save for workspace persistence only — plotting is handled by sample_container
        self._saved_results.append(
            {
                "time_values": list(time_values),
                "final_results": list(final_results),
                "label": label,
                "series_id": series_id,
                "sequence": sequence,
            }
        )

    def get_results(self) -> list:
        """Return all accumulated final results for workspace saving."""
        return list(self._saved_results)

    def load_results(self, results: list):
        """Restore saved results into _saved_results.
        Actual plotting is driven by sample_container.load_results()."""
        self._saved_results = list(results)

    def _on_serie_renamed(self, series_id=0, name="", **_):
        """Keep _saved_results in sync when the user renames a sample."""
        if 0 <= series_id < len(self._saved_results):
            self._saved_results[series_id]["label"] = name

    def _on_intermediate_data(self, final_results, time_values, run=1, **_):
        if time_values is None:
            time_values = list(range(len(final_results)))
        tag_uuid = f"run_{run}_{self.UUID}"
        self._intermediate_tags.append(f"prevplot_{tag_uuid}")
        self.plot_data(x=time_values, y=final_results, name=f"Run {run}", UUID=tag_uuid)

    def _clear_intermediate_series(self):
        for tag in self._intermediate_tags:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        self._intermediate_tags.clear()

    # --------------------------
    # INPUT HANDLER
    # --------------------------
    def input_cb(self, *args, **kwargs):
        # Two lists → static/final plot
        if isinstance(args[0], list) and isinstance(args[1], list):
            self.plot_data(x=args[1], y=args[0], name="Final", UUID=12345)
            return

        # Single floats → live streaming
        try:
            x = float(args[1])
            y = float(args[0])
            self.plot_data(x=x, y=y, UUID=self.LIVE_UUID)
        except (ValueError, IndexError):
            print("⚠ Invalid input for live data")

    # --------------------------
    # COMMAND HANDLER
    # --------------------------
    def _handle_cmd(self, cmd):
        action = cmd.get("action")
        data = cmd.get("data", {})

        if action == "add serie":
            self.plot_data(
                x=data.get("x"),
                y=data.get("y"),
                name=data.get("name"),
                UUID=data.get("uuid"),
            )
        elif action == "remove serie":
            UUID = data.get("uuid")
            if UUID:
                dpg.delete_item(f"prevplot_{UUID}")
        elif action == "update serie name":
            UUID = data.get("uuid")
            name = data.get("name")
            if UUID and name:
                dpg.set_item_label(f"prevplot_{UUID}", name)
        elif action == "clear live":
            # New command to clear live data
            self.clear_live_data()

    # --------------------------
    # CALLBACK PLACEHOLDERS
    # --------------------------
    def dragline_callback(self, sender, app_data):
        pass

    def trigger_cb(self, *args, **kwargs):
        pass


# ===================== EXPORTS =====================
EXPORTED_CLASS = Lineplot_win
EXPORTED_NAME = "Lineplot"
