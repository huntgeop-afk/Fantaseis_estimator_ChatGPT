from dataclasses import dataclass
import math


@dataclass
class OffsetSummary:
    """Stores first-order offset statistics for a survey geometry."""

    minimum_offset: float
    maximum_offset: float
    average_offset: float
    receiver_count: int
    shot_count: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Offset Analysis",
            f"Receiver Count : {self.receiver_count}",
            f"Shot Count : {self.shot_count}",
            f"Minimum Offset : {self.minimum_offset:.0f} ft",
            f"Average Offset : {self.average_offset:.0f} ft",
            f"Maximum Offset : {self.maximum_offset:.0f} ft",
        ])


class OffsetAnalysis:
    """Analyzes offset behavior using engineering approximations only."""

    def __init__(self, survey, geometry):
        self.survey = survey
        self.geometry = geometry

    #################################################################

    def analyze(self):
        receiver_count = self.geometry.receiver_count
        shot_count = self.geometry.shot_count

        maximum_offset = self._maximum_offset_from_design()
        minimum_offset = 0.0
        average_offset = maximum_offset / 2.0

        return OffsetSummary(
            minimum_offset=minimum_offset,
            maximum_offset=maximum_offset,
            average_offset=average_offset,
            receiver_count=receiver_count,
            shot_count=shot_count,
        )

    #################################################################

    def _maximum_offset_from_design(self):
        target_depth = self.survey.target_depth
        maximum_incidence_angle_deg = self.survey.maximum_incidence_angle

        return target_depth * math.tan(math.radians(maximum_incidence_angle_deg))
