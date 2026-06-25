import math

import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.patches import Polygon
import numpy as np


class FoldHeatMap:
    """Plots true spatial fold from an already populated CMP grid."""

    def __init__(self, cmp_grid, gis, survey):
        self.cmp_grid = cmp_grid
        self.gis = gis
        self.survey = survey

    #################################################################

    def plot(self):
        bins = getattr(self.cmp_grid, "bins", [])

        if not bins:
            raise ValueError("CMP grid contains no bins.")

        x_values = np.array([bin_record.xy[0] for bin_record in bins])
        y_values = np.array([bin_record.xy[1] for bin_record in bins])
        fold_values = np.array([self._usable_fold(bin_record) for bin_record in bins])

        fig, ax = plt.subplots(figsize=(10, 10))

        norm = colors.Normalize()

        scatter = ax.scatter(
            x_values,
            y_values,
            c=fold_values,
            cmap="viridis",
            norm=norm,
            marker="s",
            s=25,
            linewidth=0,
        )

        plt.colorbar(scatter, ax=ax, label="True Spatial Fold")

        boundary = getattr(self.gis, "boundary", None)
        if boundary is not None:
            boundary.plot(ax=ax, color="black", linewidth=2)

        ax.set_title("True Spatial Fold Heat Map")
        ax.set_xlabel("Easting")
        ax.set_ylabel("Northing")
        ax.set_aspect("equal")
        ax.grid(True, alpha=.3)

        plt.tight_layout()
        plt.show()

    #################################################################

    def _usable_fold(self, bin_record):
        return sum(
            1
            for trace in getattr(bin_record, "traces", [])
            if self._incidence_angle(trace.offset) <= float(self.survey.maximum_incidence_angle)
        )

    #################################################################

    def _incidence_angle(self, offset):
        target_depth = float(getattr(self.survey, "target_depth", 0.0) or 0.0)
        if target_depth <= 0.0:
            return 0.0
        return math.degrees(math.atan(float(offset) / (2.0 * target_depth)))
