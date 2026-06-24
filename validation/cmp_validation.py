from cmp_bin_authority_audit import CMPBinAuthorityAudit


class CMPValidationRunner:
    """Runs CMP assignment and authority validation suite."""

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self.geometry = geometry
        self.acquisition = acquisition
        self.gis = gis
        self.true_fold_summary = true_fold_summary

    def run(self):
        audit = CMPBinAuthorityAudit(
            cmp_grid=self.cmp_grid,
            survey=self.survey,
            geometry=self.geometry,
            acquisition=self.acquisition,
            gis=self.gis,
            true_fold_summary=self.true_fold_summary,
        )
        return audit.run()
