from dataclasses import dataclass
import math


@dataclass
class AVAzSummary:
    """Stores survey-wide azimuth spread metrics used for AVAz suitability screening."""

    minimum_azimuth: float
    maximum_azimuth: float
    azimuth_range: float
    trace_count: int
    recommended_for_avaz: bool

    #################################################################

    def summary(self):
        return "\n".join([
            "AVAz Suitability Analysis",
            f"Minimum Azimuth : {self.minimum_azimuth:.1f}\N{DEGREE SIGN}",
            f"Maximum Azimuth : {self.maximum_azimuth:.1f}\N{DEGREE SIGN}",
            f"Azimuth Range : {self.azimuth_range:.1f}\N{DEGREE SIGN}",
            f"Trace Count : {self.trace_count}",
            f"Recommended for AVAz : {self.recommended_for_avaz}",
        ])


class AVAzAnalysis:
    """Evaluates AVAz suitability from populated CMP trace azimuth diversity."""

    def __init__(self, cmp_grid, minimum_required_range_deg=120.0):
        self.cmp_grid = cmp_grid
        self.minimum_required_range_deg = minimum_required_range_deg

    #################################################################

    def analyze(self):
        azimuth_values = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                azimuth_values.append(trace.azimuth_deg)

        if not azimuth_values:
            return AVAzSummary(
                minimum_azimuth=0.0,
                maximum_azimuth=0.0,
                azimuth_range=0.0,
                trace_count=0,
                recommended_for_avaz=False,
            )

        minimum_azimuth = min(azimuth_values)
        maximum_azimuth = max(azimuth_values)
        azimuth_range = maximum_azimuth - minimum_azimuth

        recommended_for_avaz = azimuth_range >= self.minimum_required_range_deg

        return AVAzSummary(
            minimum_azimuth=minimum_azimuth,
            maximum_azimuth=maximum_azimuth,
            azimuth_range=azimuth_range,
            trace_count=len(azimuth_values),
            recommended_for_avaz=recommended_for_avaz,
        )
