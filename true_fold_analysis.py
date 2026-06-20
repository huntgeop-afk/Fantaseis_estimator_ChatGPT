from dataclasses import dataclass


@dataclass
class TrueFoldSummary:
    """Stores true spatial fold statistics derived from populated CMP bins."""

    minimum_fold: int
    maximum_fold: int
    average_fold: float
    total_bins: int
    live_bins: int
    dead_bins: int

    #################################################################

    def summary(self):
        return "\n".join([
            "True Spatial Fold",
            f"Minimum Fold : {self.minimum_fold}",
            f"Average Fold : {self.average_fold:.1f}",
            f"Maximum Fold : {self.maximum_fold}",
            f"Live CMP Bins : {self.live_bins}",
            f"Dead CMP Bins : {self.dead_bins}",
            f"Total CMP Bins : {self.total_bins}",
        ])


class TrueFoldAnalysis:
    """Analyzes live and dead CMP bins to compute true spatial fold statistics."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def analyze(self):
        bins = getattr(self.cmp_grid, "bins", [])

        if not bins:
            return TrueFoldSummary(
                minimum_fold=0,
                maximum_fold=0,
                average_fold=0.0,
                total_bins=0,
                live_bins=0,
                dead_bins=0,
            )

        folds = [bin_record.trace_count for bin_record in bins]
        total_bins = len(folds)
        live_bins = sum(1 for fold in folds if fold > 0)
        dead_bins = sum(1 for fold in folds if fold == 0)

        if live_bins == 0:
            minimum_fold = 0
            maximum_fold = 0
            average_fold = 0.0
        else:
            live_folds = [fold for fold in folds if fold > 0]
            minimum_fold = min(live_folds)
            maximum_fold = max(live_folds)
            average_fold = sum(folds) / total_bins

        return TrueFoldSummary(
            minimum_fold=minimum_fold,
            maximum_fold=maximum_fold,
            average_fold=average_fold,
            total_bins=total_bins,
            live_bins=live_bins,
            dead_bins=dead_bins,
        )
