from dataclasses import dataclass
import copy


@dataclass
class OptimizationResult:
    """Stores one candidate survey design evaluation for optimization workflows."""

    receiver_line_spacing: float
    receiver_interval: float
    source_line_spacing: float
    shot_interval: float
    active_receiver_lines: int
    estimated_cost: float
    estimated_days: float
    minimum_fold: float
    average_fold: float
    maximum_fold: float
    coverage_percent: float
    meets_constraints: bool

    #################################################################

    def summary(self):
        return "\n".join([
            "Survey Optimization Result",
            f"Receiver Line Spacing : {self.receiver_line_spacing:.1f} ft",
            f"Receiver Interval : {self.receiver_interval:.1f} ft",
            f"Source Line Spacing : {self.source_line_spacing:.1f} ft",
            f"Shot Interval : {self.shot_interval:.1f} ft",
            f"Active Receiver Lines : {self.active_receiver_lines}",
            f"Estimated Cost : ${self.estimated_cost:.2f}",
            f"Estimated Days : {self.estimated_days:.1f}",
            f"Minimum Fold : {self.minimum_fold:.1f}",
            f"Average Fold : {self.average_fold:.1f}",
            f"Maximum Fold : {self.maximum_fold:.1f}",
            f"Coverage : {self.coverage_percent:.1f} %",
            f"Meets Constraints : {self.meets_constraints}",
        ])


class SurveyOptimizer:
    """Framework for evaluating survey designs before full optimization algorithms are added."""

    def __init__(self, survey, geometry, production, cost_model):
        self.survey = survey
        self.geometry = geometry
        self.production = production
        self.cost_model = cost_model

    #################################################################

    def evaluate_current_design(self):
        survey_snapshot = copy.deepcopy(self.survey)

        estimated_cost = self._estimate_cost()
        estimated_days = self._estimate_days()

        minimum_fold = self._value_from(self.geometry, ["minimum_fold"], 0.0)
        average_fold = self._value_from(self.geometry, ["average_fold", "nominal_fold", "fold"], 0.0)
        maximum_fold = self._value_from(self.geometry, ["maximum_fold"], 0.0)
        coverage_percent = self._value_from(self.geometry, ["coverage_percent"], 0.0)

        return OptimizationResult(
            receiver_line_spacing=survey_snapshot.receiver_line_spacing,
            receiver_interval=survey_snapshot.receiver_interval,
            source_line_spacing=survey_snapshot.source_line_spacing,
            shot_interval=survey_snapshot.shot_interval,
            active_receiver_lines=survey_snapshot.active_receiver_lines,
            estimated_cost=estimated_cost,
            estimated_days=estimated_days,
            minimum_fold=minimum_fold,
            average_fold=average_fold,
            maximum_fold=maximum_fold,
            coverage_percent=coverage_percent,
            meets_constraints=self._meets_constraints(),
        )

    #################################################################

    def _estimate_cost(self):
        return self._value_from(self.cost_model, ["total_project_cost", "total_cost", "cost"], 0.0)

    #################################################################

    def _estimate_days(self):
        return self._value_from(self.production, ["critical_path_days", "estimated_days", "days"], 0.0)

    #################################################################

    def _meets_constraints(self):
        return True

    #################################################################

    def _value_from(self, obj, names, default):
        for name in names:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if callable(value):
                    value = value()
                return value

        return default
