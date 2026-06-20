from dataclasses import dataclass
import math


@dataclass
class MarginSummary:
    """Stores survey margin analysis results for acquisition aperture planning."""

    target_depth: float
    maximum_incidence_angle_deg: float
    required_aperture: float
    recommended_margin: float
    receiver_line_spacing: float
    source_line_spacing: float
    receiver_interval: float
    shot_interval: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Survey Margin Analysis",
            f"Target Depth : {self.target_depth:.0f} ft",
            f"Maximum Incidence Angle : {self.maximum_incidence_angle_deg:.1f}°",
            f"Required Aperture : {self.required_aperture:.0f} ft",
            f"Recommended Margin : {self.recommended_margin:.0f} ft",
            f"Receiver Line Spacing : {self.receiver_line_spacing:.0f} ft",
            f"Source Line Spacing : {self.source_line_spacing:.0f} ft",
            f"Receiver Interval : {self.receiver_interval:.0f} ft",
            f"Shot Interval : {self.shot_interval:.0f} ft",
        ])


class MarginAnalysis:
    """Estimates survey extension margins needed to achieve acquisition aperture at target depth."""

    def __init__(self, survey):
        self.survey = survey

    #################################################################

    def analyze(self):
        target_depth = self.survey.target_depth
        maximum_incidence_angle_deg = self.survey.maximum_incidence_angle

        maximum_incidence_angle_rad = math.radians(maximum_incidence_angle_deg)

        required_aperture = target_depth * math.tan(maximum_incidence_angle_rad)

        recommended_margin = required_aperture

        return MarginSummary(
            target_depth=target_depth,
            maximum_incidence_angle_deg=maximum_incidence_angle_deg,
            required_aperture=required_aperture,
            recommended_margin=recommended_margin,
            receiver_line_spacing=self.survey.receiver_line_spacing,
            source_line_spacing=self.survey.source_line_spacing,
            receiver_interval=self.survey.receiver_interval,
            shot_interval=self.survey.shot_interval,
        )
