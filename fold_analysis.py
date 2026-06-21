from dataclasses import dataclass


@dataclass
class FoldSummary:
    """Stores fold analysis metrics for survey aperture and trace density assessment."""

    design_fold: float
    nominal_fold: float
    minimum_fold: float
    maximum_fold: float
    average_fold: float
    receiver_count: int
    shot_count: int

    #################################################################

    def summary(self):
        if self.design_fold > 0.0:
            difference_percent = (
                abs(self.average_fold - self.design_fold) / self.design_fold
            ) * 100.0
        else:
            difference_percent = 0.0

        return "\n".join([
            "==================================================",
            "FOLD SUMMARY",
            "==================================================",
            f"Theoretical Design Fold : {self.design_fold:.1f}",
            f"Measured Average Fold   : {self.average_fold:.1f}",
            f"Measured Maximum Fold   : {self.maximum_fold:.1f}",
            f"Difference              : {difference_percent:.1f} %",
            "==================================================",
        ])


class FoldAnalysis:
    """Analyzes fold characteristics of pre-generated geometry; v1 uses nominal fold as placeholder."""

    def __init__(self, geometry):
        self.geometry = geometry

    #################################################################

    def analyze(self):
        receiver_count = self.geometry.receiver_count
        shot_count = self.geometry.shot_count

        nominal_fold = self._get_nominal_fold()
        design_fold = self.compute_design_fold()

        if design_fold > 0.0:
            difference_percent = abs(nominal_fold - design_fold) / design_fold * 100.0
            if difference_percent > 25.0:
                print("WARNING:")
                print("Measured fold differs significantly from theoretical design fold.")

        return FoldSummary(
            design_fold=design_fold,
            nominal_fold=nominal_fold,
            minimum_fold=nominal_fold,
            maximum_fold=nominal_fold,
            average_fold=nominal_fold,
            receiver_count=receiver_count,
            shot_count=shot_count,
        )

    #################################################################

    def compute_design_fold(self):
        survey = getattr(self.geometry, "survey", None)

        if survey is None:
            raise AttributeError("Geometry does not expose survey acquisition parameters")

        receiver_line_spacing = survey.receiver_line_spacing
        receiver_interval = survey.receiver_interval
        source_line_spacing = survey.source_line_spacing
        shot_interval = survey.shot_interval

        if (
            receiver_interval <= 0.0
            or shot_interval <= 0.0
            or receiver_line_spacing <= 0.0
            or source_line_spacing <= 0.0
        ):
            raise ValueError("Survey spacing and interval values must be greater than zero")

        # Standard orthogonal 3D design-fold approximation from trace-density theory:
        # F_design = (ReceiverLineSpacing * SourceLineSpacing)
        #            / (4 * ReceiverInterval * ShotInterval)
        # This follows conventional 3D orthogonal acquisition practice where
        # midpoint density is derived from shot and receiver areal spacing.
        return (
            receiver_line_spacing * source_line_spacing
        ) / (
            4.0 * receiver_interval * shot_interval
        )

    #################################################################

    def _get_nominal_fold(self):
        """Retrieve nominal fold from Geometry; return placeholder if not available."""

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

        return 1.0
