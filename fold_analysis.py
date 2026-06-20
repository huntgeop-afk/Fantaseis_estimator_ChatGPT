from dataclasses import dataclass


@dataclass
class FoldSummary:
    """Stores fold analysis metrics for survey aperture and trace density assessment."""

    nominal_fold: float
    minimum_fold: float
    maximum_fold: float
    average_fold: float
    receiver_count: int
    shot_count: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Fold Analysis",
            f"Receiver Count : {self.receiver_count}",
            f"Shot Count : {self.shot_count}",
            f"Nominal Fold : {self.nominal_fold}",
            f"Minimum Fold : {self.minimum_fold}",
            f"Average Fold : {self.average_fold}",
            f"Maximum Fold : {self.maximum_fold}",
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

        return FoldSummary(
            nominal_fold=nominal_fold,
            minimum_fold=nominal_fold,
            maximum_fold=nominal_fold,
            average_fold=nominal_fold,
            receiver_count=receiver_count,
            shot_count=shot_count,
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
