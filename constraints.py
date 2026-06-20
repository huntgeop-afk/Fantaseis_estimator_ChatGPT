from dataclasses import dataclass


@dataclass
class SurveyConstraints:
    """Stores user-defined engineering and geophysical limits for survey designs."""

    minimum_fold: float = 0.0
    minimum_coverage_percent: float = 0.0
    minimum_ava_angle: float = 0.0
    minimum_avaz_range: float = 0.0
    maximum_cost: float = float("inf")
    maximum_days: float = float("inf")
    maximum_nodes: int = 2147483647

    #################################################################

    def summary(self):
        return "\n".join([
            "Survey Constraints",
            f"Minimum Fold : {self.minimum_fold:.1f}",
            f"Minimum Coverage : {self.minimum_coverage_percent:.1f} %",
            f"Minimum AVA Angle : {self.minimum_ava_angle:.1f}\N{DEGREE SIGN}",
            f"Minimum AVAz Range : {self.minimum_avaz_range:.1f}\N{DEGREE SIGN}",
            f"Maximum Cost : ${self.maximum_cost:.0f}",
            f"Maximum Days : {self.maximum_days:.1f}",
            f"Maximum Nodes : {self.maximum_nodes}",
        ])


class ConstraintEngine:
    """Evaluates optimization results against the supplied survey constraints."""

    def __init__(self, constraints):
        self.constraints = constraints

    #################################################################

    def evaluate(self, result):
        if not self._check(getattr(result, "average_fold", 0.0), self.constraints.minimum_fold, ">="):
            return False

        if not self._check(getattr(result, "coverage_percent", 0.0), self.constraints.minimum_coverage_percent, ">="):
            return False

        if not self._check(getattr(result, "estimated_cost", 0.0), self.constraints.maximum_cost, "<="):
            return False

        if not self._check(getattr(result, "estimated_days", 0.0), self.constraints.maximum_days, "<="):
            return False

        if hasattr(result, "maximum_incidence_angle"):
            if not self._check(result.maximum_incidence_angle, self.constraints.minimum_ava_angle, ">="):
                return False

        if hasattr(result, "azimuth_range"):
            if not self._check(result.azimuth_range, self.constraints.minimum_avaz_range, ">="):
                return False

        if hasattr(result, "required_nodes"):
            if not self._check(result.required_nodes, self.constraints.maximum_nodes, "<="):
                return False

        return True

    #################################################################

    def _check(self, value, limit, comparison):
        if comparison == ">=":
            return value >= limit

        if comparison == "<=":
            return value <= limit

        raise ValueError(f"Unsupported comparison operator: {comparison}")
