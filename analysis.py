from dataclasses import dataclass
import math


@dataclass
class AnalysisSummary:
    """Holds seismic geometry quality metrics derived from generated receiver and shot points."""

    receiver_count: int
    shot_count: int
    minimum_offset: float
    maximum_offset: float
    average_offset: float
    maximum_incidence_angle_deg: float
    maximum_target_depth: float
    nominal_fold: float
    receiver_line_spacing: float
    source_line_spacing: float
    receiver_interval: float
    shot_interval: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Seismic Geometry Analysis",
            f"Receivers : {self.receiver_count}",
            f"Shots : {self.shot_count}",
            f"Receiver Line Spacing : {self.receiver_line_spacing:.0f} ft",
            f"Source Line Spacing : {self.source_line_spacing:.0f} ft",
            f"Receiver Interval : {self.receiver_interval:.0f} ft",
            f"Shot Interval : {self.shot_interval:.0f} ft",
            f"Minimum Offset : {self.minimum_offset:.0f} ft",
            f"Maximum Offset : {self.maximum_offset:.0f} ft",
            f"Average Offset : {self.average_offset:.0f} ft",
            f"Maximum Incidence Angle : {self.maximum_incidence_angle_deg:.1f}\N{DEGREE SIGN}",
            f"Maximum Target Depth : {self.maximum_target_depth:.0f} ft",
            f"Nominal Fold : {self.nominal_fold}",
        ])


class GeometryAnalysis:
    """Analyzes pre-generated geometry metrics only; it does not generate or mutate geometry."""

    def __init__(self, survey, geometry):
        self.survey = survey
        self.geometry = geometry

    #################################################################

    def analyze(self):
        receiver_count = self.geometry.receiver_count
        shot_count = self.geometry.shot_count

        minimum_offset, maximum_offset, average_offset = self._offset_statistics()

        maximum_target_depth = self.survey.target_depth

        if maximum_target_depth <= 0:
            maximum_incidence_angle_deg = 0.0
        else:
            maximum_incidence_angle_deg = math.degrees(
                math.atan(maximum_offset / maximum_target_depth)
            )

        nominal_fold = self._nominal_fold_from_geometry()

        return AnalysisSummary(
            receiver_count=receiver_count,
            shot_count=shot_count,
            minimum_offset=minimum_offset,
            maximum_offset=maximum_offset,
            average_offset=average_offset,
            maximum_incidence_angle_deg=maximum_incidence_angle_deg,
            maximum_target_depth=maximum_target_depth,
            nominal_fold=nominal_fold,
            receiver_line_spacing=self.survey.receiver_line_spacing,
            source_line_spacing=self.survey.source_line_spacing,
            receiver_interval=self.survey.receiver_interval,
            shot_interval=self.survey.shot_interval,
        )

    #################################################################

    def _offset_statistics(self):
        receivers = self.geometry.receivers
        shots = self.geometry.shots

        if not receivers or not shots:
            return 0.0, 0.0, 0.0

        min_offset = float("inf")
        max_offset = 0.0
        offset_sum = 0.0
        pair_count = 0

        for receiver in receivers:
            for shot in shots:
                offset = math.hypot(receiver.x - shot.x, receiver.y - shot.y)

                if offset < min_offset:
                    min_offset = offset

                if offset > max_offset:
                    max_offset = offset

                offset_sum += offset
                pair_count += 1

        average_offset = offset_sum / pair_count

        return min_offset, max_offset, average_offset

    #################################################################

    def _nominal_fold_from_geometry(self):
        if hasattr(self.geometry, "nominal_fold"):
            fold_value = getattr(self.geometry, "nominal_fold")
            if callable(fold_value):
                return fold_value()
            return fold_value

        if hasattr(self.geometry, "fold"):
            fold_value = getattr(self.geometry, "fold")
            if callable(fold_value):
                return fold_value()
            return fold_value

        if hasattr(self.geometry, "calculate_nominal_fold"):
            return self.geometry.calculate_nominal_fold()

        if hasattr(self.geometry, "calculate_fold"):
            return self.geometry.calculate_fold()

        raise AttributeError(
            "Geometry does not expose a nominal fold calculation. "
            "Add a fold API to Geometry for GeometryAnalysis to consume."
        )
