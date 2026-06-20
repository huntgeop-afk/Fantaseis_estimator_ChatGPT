import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.patches import Polygon
import numpy as np


class FoldHeatMap:
    """Plots true spatial fold from an already populated CMP grid."""

    def __init__(self, cmp_grid, gis):
        self.cmp_grid = cmp_grid
        self.gis = gis

    #################################################################

    def plot(self):
        bins = getattr(self.cmp_grid, "bins", [])

        if not bins:
            raise ValueError("CMP grid contains no bins.")

        x_values = np.array([bin_record.xy[0] for bin_record in bins])
        y_values = np.array([bin_record.xy[1] for bin_record in bins])
        fold_values = np.array([bin_record.trace_count for bin_record in bins])

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
