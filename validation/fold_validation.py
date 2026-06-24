from fold_audit_validation import FoldAuditValidation


class FoldValidationRunner:
    """Runs fold forensic validations without altering engineering calculations."""

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary, debug_mode=False):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self.geometry = geometry
        self.acquisition = acquisition
        self.gis = gis
        self.true_fold_summary = true_fold_summary
        self.debug_mode = bool(debug_mode)

    def run(self):
        audit = FoldAuditValidation(
            cmp_grid=self.cmp_grid,
            survey=self.survey,
            geometry=self.geometry,
            acquisition=self.acquisition,
            gis=self.gis,
            true_fold_summary=self.true_fold_summary,
            debug_mode=self.debug_mode,
        )
        return audit.run_all()
