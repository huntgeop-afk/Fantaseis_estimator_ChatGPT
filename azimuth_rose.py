import math
import matplotlib.pyplot as plt
import numpy as np


class AzimuthRose:
    """Plots a polar rose diagram of trace azimuths from a populated CMP grid."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def plot(self):
        azimuths_deg = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                azimuths_deg.append(trace.azimuth_deg)

        if not azimuths_deg:
            raise ValueError("CMP grid contains no trace azimuths.")

        azimuths_rad = np.deg2rad(np.array(azimuths_deg))

        counts, edges = np.histogram(
            azimuths_rad,
            bins=36,
            range=(0.0, 2.0 * math.pi),
        )

        theta = edges[:-1]
        width = 2 * math.pi / 36

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})

        cmap = plt.get_cmap()
        if counts.max() > 0:
            bar_colors = cmap(counts / counts.max())
        else:
            bar_colors = cmap(np.zeros_like(counts, dtype=float))

        ax.bar(theta, counts, width=width, align="edge", color=bar_colors)

        ax.set_title("Trace Azimuth Rose Diagram")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.grid(True)

        plt.tight_layout()
        plt.show()
