from dataclasses import dataclass


@dataclass
class AzimuthDistributionSummary:
    """Stores survey-wide azimuth distribution statistics from populated CMP traces."""

    minimum_azimuth: float
    maximum_azimuth: float
    average_azimuth: float
    trace_count: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Azimuth Distribution",
            f"Minimum Azimuth : {self.minimum_azimuth:.1f}°",
            f"Average Azimuth : {self.average_azimuth:.1f}°",
            f"Maximum Azimuth : {self.maximum_azimuth:.1f}°",
            f"Trace Count : {self.trace_count}",
        ])


class AzimuthDistributionAnalysis:
    """Computes survey-wide trace azimuth distribution metrics without mutating CMP data."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def analyze(self):
        azimuths = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                azimuths.append(trace.azimuth_deg)

        if not azimuths:
            return AzimuthDistributionSummary(
                minimum_azimuth=0.0,
                maximum_azimuth=0.0,
                average_azimuth=0.0,
                trace_count=0,
            )

        azimuths.sort()

        minimum_azimuth = azimuths[0]
        maximum_azimuth = azimuths[-1]
        average_azimuth = sum(azimuths) / len(azimuths)

        return AzimuthDistributionSummary(
            minimum_azimuth=minimum_azimuth,
            maximum_azimuth=maximum_azimuth,
            average_azimuth=average_azimuth,
            trace_count=len(azimuths),
        )
