from .cmp_validation import CMPValidationRunner
from .fold_validation import FoldValidationRunner


class EngineeringValidationRunner:
    """Top-level validation package entrypoint for Features 051-061."""

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary, debug_mode=False):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self.geometry = geometry
        self.acquisition = acquisition
        self.gis = gis
        self.true_fold_summary = true_fold_summary
        self.debug_mode = bool(debug_mode)

    def run(self):
        print("========================================")
        print("ENGINEERING VALIDATION")
        print("========================================")
        print("Validation Features")
        print("051, 052, 053, 054, 055, 056, 057, 058, 059, 060, 061")

        fold_result = FoldValidationRunner(
            cmp_grid=self.cmp_grid,
            survey=self.survey,
            geometry=self.geometry,
            acquisition=self.acquisition,
            gis=self.gis,
            true_fold_summary=self.true_fold_summary,
            debug_mode=self.debug_mode,
        ).run()

        cmp_result = CMPValidationRunner(
            cmp_grid=self.cmp_grid,
            survey=self.survey,
            geometry=self.geometry,
            acquisition=self.acquisition,
            gis=self.gis,
            true_fold_summary=self.true_fold_summary,
        ).run()

        validation_pass = bool(fold_result.get("overall_pass", False)) and bool(cmp_result.get("overall_pass", True))

        print("ENGINEERING VALIDATION")
        print("PASS" if validation_pass else "FAIL")
        print("========================================")

        return {
            "overall_pass": validation_pass,
            "fold": fold_result,
            "cmp": cmp_result,
        }
