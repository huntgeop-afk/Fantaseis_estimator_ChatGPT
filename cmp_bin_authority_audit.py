from canonical_cmp_assignment_validation import CanonicalCMPAssignmentValidation


class CMPBinAuthorityAudit:
    """Compatibility wrapper to preserve pipeline import while executing Feature 058."""

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary):
        self.validator = CanonicalCMPAssignmentValidation(
            cmp_grid=cmp_grid,
            survey=survey,
            geometry=geometry,
            acquisition=acquisition,
            gis=gis,
            true_fold_summary=true_fold_summary,
        )

    #################################################################

    def run(self):
        return self.validator.run()
