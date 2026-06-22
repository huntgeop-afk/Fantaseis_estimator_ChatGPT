from dataclasses import dataclass
import math

import matplotlib.pyplot as plt


@dataclass
class CenterCMPSummary:
    cmp_x: float
    cmp_y: float
    fold: int
    minimum_offset: float
    maximum_offset: float
    average_offset: float
    median_offset: float
    minimum_orientation: float
    maximum_orientation: float
    orientation_coverage: float


class CenterCMPValidation:
    """Validation-only diagnostics for the CMP nearest survey geometric center."""

    def __init__(self, cmp_grid, gis):
        self.cmp_grid = cmp_grid
        self.gis = gis
        self._center_bin = None
        self._offsets = []
        self._orientations = []

    #################################################################

    def analyze(self):
        """Compute center-CMP fold, offset, and orientation statistics from accepted traces."""
        center_x, center_y = self._survey_center()
        center_bin = self._nearest_cmp_bin(center_x, center_y)

        traces = list(getattr(center_bin, "traces", []))

        offsets = [trace.offset for trace in traces]
        orientations = [(trace.azimuth_deg % 180.0) for trace in traces]

        offsets.sort()
        orientations.sort()

        fold = len(traces)

        if offsets:
            minimum_offset = offsets[0]
            maximum_offset = offsets[-1]
            average_offset = math.fsum(offsets) / len(offsets)
            median_offset = self._percentile(offsets, 0.50)
        else:
            minimum_offset = 0.0
            maximum_offset = 0.0
            average_offset = 0.0
            median_offset = 0.0

        if orientations:
            minimum_orientation = orientations[0]
            maximum_orientation = orientations[-1]
            orientation_coverage = maximum_orientation - minimum_orientation
        else:
            minimum_orientation = 0.0
            maximum_orientation = 0.0
            orientation_coverage = 0.0

        self._center_bin = center_bin
        self._offsets = offsets
        self._orientations = orientations

        return CenterCMPSummary(
            cmp_x=center_bin.xy[0],
            cmp_y=center_bin.xy[1],
            fold=fold,
            minimum_offset=minimum_offset,
            maximum_offset=maximum_offset,
            average_offset=average_offset,
            median_offset=median_offset,
            minimum_orientation=minimum_orientation,
            maximum_orientation=maximum_orientation,
            orientation_coverage=orientation_coverage,
        )

    #################################################################

    def print_center_cmp_validation(self):
        """Print center-CMP engineering validation summary to console."""
        summary = self.analyze()

        print("==================================================")
        print("CENTER CMP VALIDATION")
        print("==================================================")
        print()
        print(f"CMP X Coordinate      : {summary.cmp_x:.2f}")
        print(f"CMP Y Coordinate      : {summary.cmp_y:.2f}")
        print()
        print(f"Fold                  : {summary.fold}")
        print()
        print(f"Minimum Offset        : {summary.minimum_offset:.0f} ft")
        print(f"Maximum Offset        : {summary.maximum_offset:.0f} ft")
        print(f"Average Offset        : {summary.average_offset:.0f} ft")
        print(f"Median Offset         : {summary.median_offset:.0f} ft")
        print()
        print(f"Minimum Orientation   : {summary.minimum_orientation:.1f}°")
        print(f"Maximum Orientation   : {summary.maximum_orientation:.1f}°")
        print()
        print(f"Orientation Coverage  : {summary.orientation_coverage:.1f}°")
        print()
        print("==================================================")

    #################################################################

    def plot_center_cmp_offsets(self, save_path=None):
        """Create and optionally save offset histogram for traces in the center CMP."""
        if self._center_bin is None:
            self.analyze()

        fig, ax = plt.subplots(figsize=(10, 6))

        try:
            ax.hist(
                self._offsets,
                bins=20,
                color="royalblue",
                edgecolor="black",
                linewidth=0.5,
            )
            ax.set_xlabel("Offset (ft)")
            ax.set_ylabel("Trace Count")
            ax.set_title("Center CMP Offset Distribution")
            ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.6)

            if save_path is not None:
                fig.savefig(save_path, dpi=300, bbox_inches="tight")
            else:
                plt.show()

        finally:
            plt.close(fig)

    #################################################################

    def plot_center_cmp_orientations(self, save_path=None):
        """Create and optionally save orientation histogram for traces in the center CMP."""
        if self._center_bin is None:
            self.analyze()

        fig, ax = plt.subplots(figsize=(10, 6))

        try:
            ax.hist(
                self._orientations,
                bins=18,
                range=(0.0, 180.0),
                color="darkorange",
                edgecolor="black",
                linewidth=0.5,
            )
            ax.set_xlabel("Orientation (degrees)")
            ax.set_ylabel("Trace Count")
            ax.set_title("Center CMP Orientation Distribution")
            ax.set_xlim(0.0, 180.0)
            ax.set_xticks(range(0, 181, 30))
            ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.6)

            if save_path is not None:
                fig.savefig(save_path, dpi=300, bbox_inches="tight")
            else:
                plt.show()

        finally:
            plt.close(fig)

    #################################################################

    def _survey_center(self):
        xmin, ymin, xmax, ymax = self.gis.bounds
        return (xmin + xmax) / 2.0, (ymin + ymax) / 2.0

    #################################################################

    def _nearest_cmp_bin(self, x, y):
        if not getattr(self.cmp_grid, "bins", []):
            raise ValueError("CMP grid contains no bins.")

        return min(
            self.cmp_grid.bins,
            key=lambda record: (record.xy[0] - x) ** 2 + (record.xy[1] - y) ** 2,
        )

    #################################################################

    def _percentile(self, sorted_values, fraction):
        if not sorted_values:
            return 0.0

        if fraction <= 0.0:
            return sorted_values[0]

        if fraction >= 1.0:
            return sorted_values[-1]

        position = (len(sorted_values) - 1) * fraction
        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        if lower_index == upper_index:
            return sorted_values[lower_index]

        weight = position - lower_index
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]

        return lower_value + (upper_value - lower_value) * weight
