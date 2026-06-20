from dataclasses import dataclass
import math


@dataclass
class OffsetDistributionSummary:
    """Stores survey-wide offset distribution statistics from populated CMP traces."""

    minimum_offset: float
    p10_offset: float
    median_offset: float
    average_offset: float
    p90_offset: float
    maximum_offset: float
    trace_count: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Offset Distribution",
            f"Minimum Offset : {self.minimum_offset:.0f} ft",
            f"10th Percentile : {self.p10_offset:.0f} ft",
            f"Median Offset : {self.median_offset:.0f} ft",
            f"Average Offset : {self.average_offset:.0f} ft",
            f"90th Percentile : {self.p90_offset:.0f} ft",
            f"Maximum Offset : {self.maximum_offset:.0f} ft",
            f"Trace Count : {self.trace_count}",
        ])


class OffsetDistributionAnalysis:
    """Computes survey-wide trace offset distribution metrics without mutating CMP data."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def analyze(self):
        offsets = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                offsets.append(trace.offset)

        if not offsets:
            return OffsetDistributionSummary(
                minimum_offset=0.0,
                p10_offset=0.0,
                median_offset=0.0,
                average_offset=0.0,
                p90_offset=0.0,
                maximum_offset=0.0,
                trace_count=0,
            )

        offsets.sort()

        minimum_offset = offsets[0]
        maximum_offset = offsets[-1]
        average_offset = math.fsum(offsets) / len(offsets)
        median_offset = self._percentile(offsets, 0.5)
        p10_offset = self._percentile(offsets, 0.1)
        p90_offset = self._percentile(offsets, 0.9)

        return OffsetDistributionSummary(
            minimum_offset=minimum_offset,
            p10_offset=p10_offset,
            median_offset=median_offset,
            average_offset=average_offset,
            p90_offset=p90_offset,
            maximum_offset=maximum_offset,
            trace_count=len(offsets),
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
