import math

import numpy as np
import matplotlib.pyplot as plt


class SurveyQC:
    """Engineering QC maps built from an already populated CMP grid."""

    def __init__(self, cmp_grid, survey):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self._x_centers = []
        self._y_centers = []
        self._bin_lookup = {}
        self._refresh_index()

    #################################################################

    def generate_fold_map(self, save_path=None):
        """Render and optionally save usable CMP fold after incidence-angle filtering."""
        data, extent = self._build_metric_matrix(self._fold_value)
        return self._render_map(
            data,
            extent,
            title="Usable CMP Fold Map",
            colorbar_label="Usable Fold",
            cmap_name="viridis",
            save_path=save_path,
        )

    #################################################################

    def generate_max_offset_map(self, save_path=None):
        """Render and optionally save per-CMP maximum offset map from accepted traces."""
        data, extent = self._build_metric_matrix(self._maximum_offset_value)
        return self._render_map(
            data,
            extent,
            title="Maximum Offset by CMP",
            colorbar_label="Maximum Offset (ft)",
            cmap_name="plasma",
            save_path=save_path,
        )

    #################################################################

    def generate_min_offset_map(self, save_path=None):
        """Render and optionally save per-CMP minimum offset map from accepted traces."""
        data, extent = self._build_metric_matrix(self._minimum_offset_value)
        return self._render_map(
            data,
            extent,
            title="Minimum Offset by CMP",
            colorbar_label="Minimum Offset (ft)",
            cmap_name="magma",
            save_path=save_path,
        )

    #################################################################

    def _refresh_index(self):
        bins = getattr(self.cmp_grid, "bins", [])
        self._bin_lookup = {bin_record.xy: bin_record for bin_record in bins}
        self._x_centers = sorted({bin_record.xy[0] for bin_record in bins})
        self._y_centers = sorted({bin_record.xy[1] for bin_record in bins})

    #################################################################

    def _build_metric_matrix(self, metric_fn):
        if not self._bin_lookup:
            self._refresh_index()

        if not self._x_centers or not self._y_centers:
            data = np.empty((0, 0), dtype=float)
            extent = (0.0, 0.0, 0.0, 0.0)
            return data, extent

        data = np.full((len(self._y_centers), len(self._x_centers)), np.nan, dtype=float)

        for bin_record in self.cmp_grid.bins:
            if getattr(bin_record, "trace_count", 0) <= 0:
                continue

            x_value, y_value = bin_record.xy
            x_index = self._x_centers.index(x_value)
            y_index = self._y_centers.index(y_value)
            data[y_index, x_index] = metric_fn(bin_record)

        x_step = getattr(self.cmp_grid, "bin_size_x", 1.0)
        y_step = getattr(self.cmp_grid, "bin_size_y", 1.0)

        extent = (
            self._x_centers[0] - (x_step / 2.0),
            self._x_centers[-1] + (x_step / 2.0),
            self._y_centers[0] - (y_step / 2.0),
            self._y_centers[-1] + (y_step / 2.0),
        )

        return data, extent

    #################################################################

    def _render_map(self, data, extent, title, colorbar_label, cmap_name, save_path=None):
        fig, ax = plt.subplots(figsize=(10, 10))

        cmap = plt.get_cmap(cmap_name)
        if hasattr(cmap, "copy"):
            cmap = cmap.copy()
        cmap.set_bad(color="white", alpha=0.0)

        try:
            masked = np.ma.masked_invalid(data)
            image = ax.imshow(
                masked,
                origin="lower",
                extent=extent,
                interpolation="nearest",
                cmap=cmap,
                aspect="equal",
            )
            ax.set_title(title)
            ax.set_xlabel("CMP X Coordinate")
            ax.set_ylabel("CMP Y Coordinate")
            colorbar = fig.colorbar(image, ax=ax)
            colorbar.set_label(colorbar_label)
            ax.set_aspect("equal", adjustable="box")
            plt.tight_layout()

            if save_path is not None:
                fig.savefig(save_path, dpi=300, bbox_inches="tight")

            return fig
        except Exception:
            plt.close(fig)
            raise

    #################################################################

    def _fold_value(self, bin_record):
        usable_count = 0
        for trace in getattr(bin_record, "traces", []):
            if self._incidence_angle(trace.offset) > float(self.survey.maximum_incidence_angle):
                continue
            usable_count += 1
        return usable_count

    #################################################################

    def _maximum_offset_value(self, bin_record):
        traces = getattr(bin_record, "traces", [])
        if not traces:
            return np.nan
        return max(trace.offset for trace in traces)

    #################################################################

    def _minimum_offset_value(self, bin_record):
        traces = getattr(bin_record, "traces", [])
        if not traces:
            return np.nan
        return min(trace.offset for trace in traces)

    #################################################################

    def _incidence_angle(self, offset):
        target_depth = float(getattr(self.survey, "target_depth", 0.0) or 0.0)
        if target_depth <= 0.0:
            return 0.0
        return math.degrees(math.atan(float(offset) / (2.0 * target_depth)))
