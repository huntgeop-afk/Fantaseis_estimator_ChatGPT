from dataclasses import dataclass
import math
import matplotlib.pyplot as plt


@dataclass
class OffsetSummary:
    """Stores offset and incidence-angle validation statistics from accepted traces."""

    minimum_offset: float
    p10_offset: float
    p25_offset: float
    median_offset: float
    average_offset: float
    p75_offset: float
    p90_offset: float
    maximum_offset: float
    maximum_incidence_angle: float
    median_incidence_angle: float
    p90_incidence_angle: float
    p95_incidence_angle: float
    trace_count: int
    histogram_bins: list[tuple[int, int, int]]
    traces_lt_1000: int
    traces_1000_2000: int
    traces_2000_4000: int
    traces_4000_6000: int
    traces_6000_8000: int
    traces_gt_8000: int

    #################################################################

    def summary(self):
        histogram_lines = [
            f"{lower}-{upper} ft : {count}"
            for lower, upper, count in self.histogram_bins
        ]

        return "\n".join([
            "==================================================",
            "OFFSET VALIDATION",
            "==================================================",
            f"Minimum Offset : {self.minimum_offset:.0f} ft",
            f"10%            : {self.p10_offset:.0f} ft",
            f"25%            : {self.p25_offset:.0f} ft",
            f"Median         : {self.median_offset:.0f} ft",
            f"Average        : {self.average_offset:.0f} ft",
            f"75%            : {self.p75_offset:.0f} ft",
            f"90%            : {self.p90_offset:.0f} ft",
            f"Maximum Offset : {self.maximum_offset:.0f} ft",
            "-----------------------------------------",
            f"Maximum Incidence Angle : {self.maximum_incidence_angle:.1f} deg",
            f"Median Incidence Angle  : {self.median_incidence_angle:.1f} deg",
            f"90%                     : {self.p90_incidence_angle:.1f} deg",
            f"95%                     : {self.p95_incidence_angle:.1f} deg",
            "-----------------------------------------",
            "Histogram",
            *histogram_lines,
            "==================================================",
        ])


class OffsetAnalysis:
    """Analyzes accepted-trace offsets from a populated CMP grid."""

    def __init__(self, survey, geometry=None, cmp_grid=None):
        self.survey = survey
        self.geometry = geometry
        self.cmp_grid = cmp_grid if cmp_grid is not None else geometry

    #################################################################

    def analyze(self):
        offsets = self._accepted_offsets()

        if not offsets:
            summary = OffsetSummary(
                minimum_offset=0.0,
                p10_offset=0.0,
                p25_offset=0.0,
                median_offset=0.0,
                average_offset=0.0,
                p75_offset=0.0,
                p90_offset=0.0,
                maximum_offset=0.0,
                maximum_incidence_angle=0.0,
                median_incidence_angle=0.0,
                p90_incidence_angle=0.0,
                p95_incidence_angle=0.0,
                trace_count=0,
                histogram_bins=[],
                traces_lt_1000=0,
                traces_1000_2000=0,
                traces_2000_4000=0,
                traces_4000_6000=0,
                traces_6000_8000=0,
                traces_gt_8000=0,
            )
            print(summary.summary())
            return summary

        offsets.sort()

        minimum_offset = offsets[0]
        maximum_offset = offsets[-1]
        average_offset = math.fsum(offsets) / len(offsets)

        p10_offset = self._percentile(offsets, 0.10)
        p25_offset = self._percentile(offsets, 0.25)
        median_offset = self._percentile(offsets, 0.50)
        p75_offset = self._percentile(offsets, 0.75)
        p90_offset = self._percentile(offsets, 0.90)

        incidence_angles = self._incidence_angles(offsets)
        incidence_angles.sort()

        maximum_incidence_angle = incidence_angles[-1]
        median_incidence_angle = self._percentile(incidence_angles, 0.50)
        p90_incidence_angle = self._percentile(incidence_angles, 0.90)
        p95_incidence_angle = self._percentile(incidence_angles, 0.95)

        histogram_bins = self._histogram_500ft(offsets)

        traces_lt_1000 = sum(1 for value in offsets if value < 1000.0)
        traces_1000_2000 = sum(1 for value in offsets if 1000.0 <= value < 2000.0)
        traces_2000_4000 = sum(1 for value in offsets if 2000.0 <= value < 4000.0)
        traces_4000_6000 = sum(1 for value in offsets if 4000.0 <= value < 6000.0)
        traces_6000_8000 = sum(1 for value in offsets if 6000.0 <= value < 8000.0)
        traces_gt_8000 = sum(1 for value in offsets if value >= 8000.0)

        summary = OffsetSummary(
            minimum_offset=minimum_offset,
            p10_offset=p10_offset,
            p25_offset=p25_offset,
            median_offset=median_offset,
            average_offset=average_offset,
            p75_offset=p75_offset,
            p90_offset=p90_offset,
            maximum_offset=maximum_offset,
            maximum_incidence_angle=maximum_incidence_angle,
            median_incidence_angle=median_incidence_angle,
            p90_incidence_angle=p90_incidence_angle,
            p95_incidence_angle=p95_incidence_angle,
            trace_count=len(offsets),
            histogram_bins=histogram_bins,
            traces_lt_1000=traces_lt_1000,
            traces_1000_2000=traces_1000_2000,
            traces_2000_4000=traces_2000_4000,
            traces_4000_6000=traces_4000_6000,
            traces_6000_8000=traces_6000_8000,
            traces_gt_8000=traces_gt_8000,
        )

        print(summary.summary())
        return summary

    #################################################################

    def plot_offset_distribution(self, save_path=None):
        offsets = self._accepted_offsets()
        if offsets:
            offsets.sort()
        histogram_bins = self._histogram_500ft(offsets)

        fig, ax = plt.subplots(figsize=(10, 6))

        left_edges = [lower for lower, _, _ in histogram_bins]
        counts = [count for _, _, count in histogram_bins]

        if left_edges:
            ax.bar(
                left_edges,
                counts,
                width=500.0,
                align="edge",
                color="steelblue",
                edgecolor="black",
                linewidth=0.6,
                alpha=0.9,
            )

        ax.set_title("Offset Distribution")
        ax.set_xlabel("Offset (ft)")
        ax.set_ylabel("Trace Count")
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.7)

        if left_edges:
            ax.set_xlim(0.0, left_edges[-1] + 500.0)

        plt.tight_layout()

        if save_path is not None:
            plt.savefig(save_path, dpi=300)
            plt.close(fig)
        else:
            plt.show()

    #################################################################

    def create_offset_distribution_figure(self, save_path=None):
        self.plot_offset_distribution(save_path=save_path)

    #################################################################

    def print_offset_validation(self):
        """Print offset validation report using actual accepted trace offsets."""
        offsets = self._accepted_offsets()

        if not offsets:
            print("==================================================")
            print("OFFSET VALIDATION")
            print("==================================================")
            print("Accepted Traces           : 0")
            print("==================================================")
            return

        offsets.sort()

        minimum_offset = offsets[0]
        maximum_offset = offsets[-1]
        average_offset = math.fsum(offsets) / len(offsets)

        median_offset = self._percentile(offsets, 0.50)
        p05_offset = self._percentile(offsets, 0.05)
        p10_offset = self._percentile(offsets, 0.10)
        p25_offset = self._percentile(offsets, 0.25)
        p75_offset = self._percentile(offsets, 0.75)
        p90_offset = self._percentile(offsets, 0.90)
        p95_offset = self._percentile(offsets, 0.95)

        traces_lt_500 = sum(1 for v in offsets if v < 500.0)
        traces_500_1000 = sum(1 for v in offsets if 500.0 <= v < 1000.0)
        traces_1000_2000 = sum(1 for v in offsets if 1000.0 <= v < 2000.0)
        traces_2000_3000 = sum(1 for v in offsets if 2000.0 <= v < 3000.0)
        traces_3000_4000 = sum(1 for v in offsets if 3000.0 <= v < 4000.0)
        traces_4000_5000 = sum(1 for v in offsets if 4000.0 <= v < 5000.0)
        traces_5000_6000 = sum(1 for v in offsets if 5000.0 <= v < 6000.0)
        traces_6000_7000 = sum(1 for v in offsets if 6000.0 <= v < 7000.0)
        traces_gt_7000 = sum(1 for v in offsets if v >= 7000.0)

        print("==================================================")
        print("OFFSET VALIDATION")
        print("==================================================")
        print(f"Accepted Traces           : {len(offsets)}")
        print(f"Minimum Offset            : {minimum_offset:.0f} ft")
        print(f"Maximum Offset            : {maximum_offset:.0f} ft")
        print(f"Average Offset            : {average_offset:.0f} ft")
        print(f"Median Offset             : {median_offset:.0f} ft")
        print(f"5 Percentile              : {p05_offset:.0f} ft")
        print(f"10 Percentile             : {p10_offset:.0f} ft")
        print(f"25 Percentile             : {p25_offset:.0f} ft")
        print(f"75 Percentile             : {p75_offset:.0f} ft")
        print(f"90 Percentile             : {p90_offset:.0f} ft")
        print(f"95 Percentile             : {p95_offset:.0f} ft")
        print(f"Offset < 500 ft           : {traces_lt_500}")
        print(f"Offset 500-1000 ft        : {traces_500_1000}")
        print(f"Offset 1000-2000 ft       : {traces_1000_2000}")
        print(f"Offset 2000-3000 ft       : {traces_2000_3000}")
        print(f"Offset 3000-4000 ft       : {traces_3000_4000}")
        print(f"Offset 4000-5000 ft       : {traces_4000_5000}")
        print(f"Offset 5000-6000 ft       : {traces_5000_6000}")
        print(f"Offset 6000-7000 ft       : {traces_6000_7000}")
        print(f"Offset >7000 ft           : {traces_gt_7000}")
        print("==================================================")

    #################################################################

    def _accepted_offsets(self):
        offsets = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                offsets.append(trace.offset)

        return offsets

    #################################################################

    def _incidence_angles(self, offsets):
        target_depth = getattr(self.survey, "target_depth", 0.0)

        if target_depth <= 0.0:
            return [0.0 for _ in offsets]

        return [
            math.degrees(math.atan(offset / (2.0 * target_depth)))
            for offset in offsets
        ]

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

    #################################################################

    def _histogram_500ft(self, sorted_offsets):
        if not sorted_offsets:
            return []

        maximum_offset = sorted_offsets[-1]
        bin_count = int(math.floor(maximum_offset / 500.0)) + 1
        counts = [0] * bin_count

        for offset in sorted_offsets:
            index = int(math.floor(offset / 500.0))
            counts[index] += 1

        histogram = []
        for index, count in enumerate(counts):
            lower = index * 500
            upper = lower + 500
            histogram.append((lower, upper, count))

        return histogram
