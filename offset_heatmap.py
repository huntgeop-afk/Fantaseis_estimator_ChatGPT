import matplotlib.pyplot as plt
import matplotlib.colors as colors
import numpy as np


class OffsetHeatMap:
    """Plots average trace offset per populated CMP bin without modifying grid content."""

    def __init__(self, cmp_grid, gis):
        self.cmp_grid = cmp_grid
        self.gis = gis

    #################################################################

    def plot(self):
        bins = getattr(self.cmp_grid, "bins", [])

        if not bins:
            raise ValueError("CMP grid contains no bins.")

        x_values = []
        y_values = []
        offset_values = []

        for bin_record in bins:
            x_values.append(bin_record.xy[0])
            y_values.append(bin_record.xy[1])

            traces = getattr(bin_record, "traces", [])

            if not traces:
                average_offset = 0.0
            else:
                average_offset = sum(trace.offset for trace in traces) / len(traces)

            offset_values.append(average_offset)

        x_values = np.array(x_values)
        y_values = np.array(y_values)
        offset_values = np.array(offset_values)

        fig, ax = plt.subplots(figsize=(10, 10))

        norm = colors.Normalize(
            vmin=offset_values.min(),
            vmax=offset_values.max(),
        )

        scatter = ax.scatter(
            x_values,
            y_values,
            marker="s",
            s=25,
            linewidth=0,
            c=offset_values,
            cmap="plasma",
            norm=norm,
        )

        plt.colorbar(scatter, ax=ax, label="Average Offset (ft)")

        self.gis.boundary.boundary.plot(
            ax=ax,
            color="black",
            linewidth=2,
        )

        ax.set_title("Average Offset Heat Map")
        ax.set_xlabel("Easting")
        ax.set_ylabel("Northing")
        ax.set_aspect("equal")
        ax.grid(True, alpha=.3)

        plt.tight_layout()
        plt.show()
