from dataclasses import dataclass
import math


@dataclass
class AzimuthSummary:
    """Stores survey-wide azimuth statistics computed from populated CMP traces."""

    minimum_azimuth: float
    maximum_azimuth: float
    average_azimuth: float
    trace_count: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Azimuth Analysis",
            f"Minimum Azimuth : {self.minimum_azimuth:.1f}\N{DEGREE SIGN}",
            f"Average Azimuth : {self.average_azimuth:.1f}\N{DEGREE SIGN}",
            f"Maximum Azimuth : {self.maximum_azimuth:.1f}\N{DEGREE SIGN}",
            f"Trace Count : {self.trace_count}",
        ])


class AzimuthAnalysis:
    """Analyzes azimuth distribution from CMP bin traces without modifying grid content."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def analyze(self):
        azimuth_values = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                azimuth_values.append(trace.azimuth_deg)

        if not azimuth_values:
            return AzimuthSummary(
                minimum_azimuth=0.0,
                maximum_azimuth=0.0,
                average_azimuth=0.0,
                trace_count=0,
            )

        minimum_azimuth = min(azimuth_values)
        maximum_azimuth = max(azimuth_values)
        average_azimuth = math.fsum(azimuth_values) / len(azimuth_values)

        return AzimuthSummary(
            minimum_azimuth=minimum_azimuth,
            maximum_azimuth=maximum_azimuth,
            average_azimuth=average_azimuth,
            trace_count=len(azimuth_values),
        )
