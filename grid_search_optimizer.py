from dataclasses import dataclass
import copy
import itertools


@dataclass
class SearchResult:
    """Stores summary information for a completed grid-search optimization run."""

    best_result: object
    candidate_count: int
    accepted_count: int
    rejected_count: int

    #################################################################

    def summary(self):
        if self.best_result is None:
            best_cost_text = "None"
        else:
            best_cost = getattr(self.best_result, "estimated_cost", None)
            if best_cost is None:
                best_cost_text = "None"
            else:
                best_cost_text = f"${best_cost:.0f}"

        return "\n".join([
            "Grid Search Results",
            f"Candidates Evaluated : {self.candidate_count}",
            f"Accepted : {self.accepted_count}",
            f"Rejected : {self.rejected_count}",
            f"Best Cost : {best_cost_text}",
        ])


class GridSearchOptimizer:
    """Evaluates candidate survey designs on a parameter grid and retains the lowest-cost valid result."""

    def __init__(self, survey, optimizer, constraint_engine):
        self.survey = survey
        self.optimizer = optimizer
        self.constraint_engine = constraint_engine

    #################################################################

    def search(self, parameter_ranges):
        parameter_names = list(parameter_ranges.keys())
        parameter_values = [parameter_ranges[name] for name in parameter_names]

        best_result = None
        candidate_count = 0
        accepted_count = 0
        rejected_count = 0

        for candidate_values in itertools.product(*parameter_values):
            candidate_count += 1

            survey_candidate = copy.deepcopy(self.survey)

            for name, value in zip(parameter_names, candidate_values):
                setattr(survey_candidate, name, value)

            self.optimizer.survey = survey_candidate
            result = self.optimizer.evaluate_current_design()

            if self.constraint_engine.evaluate(result):
                accepted_count += 1

                if best_result is None:
                    best_result = result
                else:
                    current_cost = getattr(result, "estimated_cost", float("inf"))
                    best_cost = getattr(best_result, "estimated_cost", float("inf"))

                    if current_cost < best_cost:
                        best_result = result
            else:
                rejected_count += 1

        return SearchResult(
            best_result=best_result,
            candidate_count=candidate_count,
            accepted_count=accepted_count,
            rejected_count=rejected_count,
        )
