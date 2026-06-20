from dataclasses import dataclass
import math


@dataclass
class IlluminationSummary:
    """Stores first-order illumination metrics computed from populated CMP bins."""

    live_bins: int
    dead_bins: int
    coverage_percent: float
    average_fold: float
    illumination_score: float

    #################################################################

    def summary(self):
        return "\n".join([
            "Illumination Analysis",
            f"Live CMP Bins : {self.live_bins}",
            f"Dead CMP Bins : {self.dead_bins}",
            f"Coverage : {self.coverage_percent:.1f} %",
            f"Average Fold : {self.average_fold:.1f}",
            f"Illumination Score : {self.illumination_score:.1f}",
        ])


class IlluminationAnalysis:
    """Estimates survey illumination quality using CMP live/dead coverage and fold."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def analyze(self):
        bins = getattr(self.cmp_grid, "bins", [])

        if not bins:
            return IlluminationSummary(
                live_bins=0,
                dead_bins=0,
                coverage_percent=0.0,
                average_fold=0.0,
                illumination_score=0.0,
            )

        fold_values = [bin_record.trace_count for bin_record in bins]

        total_bins = len(fold_values)
        live_bins = sum(1 for fold in fold_values if fold > 0)
        dead_bins = total_bins - live_bins

        average_fold = math.fsum(fold_values) / total_bins
        coverage_percent = 100.0 * live_bins / total_bins

        illumination_score = coverage_percent * average_fold / 100.0

        return IlluminationSummary(
            live_bins=live_bins,
            dead_bins=dead_bins,
            coverage_percent=coverage_percent,
            average_fold=average_fold,
            illumination_score=illumination_score,
        )
