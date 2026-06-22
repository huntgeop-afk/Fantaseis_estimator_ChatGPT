from dataclasses import dataclass
import math


@dataclass
class TrueFoldSummary:
    """Stores true spatial fold statistics derived from populated CMP bins."""

    design_fold: float
    minimum_fold: int
    maximum_fold: int
    average_fold: float
    total_bins: int
    live_bins: int
    dead_bins: int

    #################################################################

    def summary(self):
        coverage_percent = (
            (self.live_bins / self.total_bins) * 100.0
            if self.total_bins > 0
            else 0.0
        )

        return "\n".join([
            "==================================================",
            "TRUE FOLD SUMMARY",
            "==================================================",
            f"Design Fold (temporary) : {self.design_fold:.1f}",
            f"Minimum True Fold       : {self.minimum_fold:.1f}",
            f"Average True Fold       : {self.average_fold:.1f}",
            f"Maximum True Fold       : {self.maximum_fold:.1f}",
            f"Live CMP Bins           : {self.live_bins}",
            f"Dead CMP Bins           : {self.dead_bins}",
            f"Coverage                : {coverage_percent:.1f} %",
            "==================================================",
        ])


class TrueFoldAnalysis:
    """Analyzes live and dead CMP bins to compute true spatial fold statistics."""

    def __init__(self, cmp_grid):
        self.cmp_grid = cmp_grid

    #################################################################

    def analyze(self):
        bins = getattr(self.cmp_grid, "bins", [])

        if not bins:
            self._print_fold_distribution([])
            return TrueFoldSummary(
                design_fold=0.0,
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
            live_folds = []
            minimum_fold = 0
            maximum_fold = 0
            average_fold = 0.0
        else:
            live_folds = [fold for fold in folds if fold > 0]
            minimum_fold = min(live_folds)
            maximum_fold = max(live_folds)
            average_fold = sum(live_folds) / live_bins

        self._print_fold_distribution(live_folds)

        # Design fold is reported as measured live-bin average fold in this validated workflow.
        design_fold = average_fold

        return TrueFoldSummary(
            design_fold=design_fold,
            minimum_fold=minimum_fold,
            maximum_fold=maximum_fold,
            average_fold=average_fold,
            total_bins=total_bins,
            live_bins=live_bins,
            dead_bins=dead_bins,
        )

    #################################################################

    def _percentile(self, sorted_values, fraction):
        if not sorted_values:
            return 0.0

        if fraction <= 0.0:
            return float(sorted_values[0])

        if fraction >= 1.0:
            return float(sorted_values[-1])

        position = (len(sorted_values) - 1) * fraction
        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        if lower_index == upper_index:
            return float(sorted_values[lower_index])

        weight = position - lower_index
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]

        return lower_value + (upper_value - lower_value) * weight

    #################################################################

    def _print_fold_distribution(self, live_folds):
        values = sorted(live_folds)

        minimum_fold = self._percentile(values, 0.00)
        p05 = self._percentile(values, 0.05)
        p10 = self._percentile(values, 0.10)
        p25 = self._percentile(values, 0.25)
        median = self._percentile(values, 0.50)
        average = (sum(values) / len(values)) if values else 0.0
        p75 = self._percentile(values, 0.75)
        p90 = self._percentile(values, 0.90)
        p95 = self._percentile(values, 0.95)
        maximum_fold = self._percentile(values, 1.00)

        fold_eq_1 = sum(1 for fold in values if fold == 1)
        fold_2_5 = sum(1 for fold in values if 2 <= fold <= 5)
        fold_6_10 = sum(1 for fold in values if 6 <= fold <= 10)
        fold_11_20 = sum(1 for fold in values if 11 <= fold <= 20)
        fold_gt_20 = sum(1 for fold in values if fold > 20)

        print("==================================================")
        print("FOLD DISTRIBUTION")
        print("==================================================")
        print(f"Minimum Fold : {minimum_fold:.1f}")
        print(f"5%           : {p05:.1f}")
        print(f"10%          : {p10:.1f}")
        print(f"25%          : {p25:.1f}")
        print(f"Median       : {median:.1f}")
        print(f"Average      : {average:.1f}")
        print(f"75%          : {p75:.1f}")
        print(f"90%          : {p90:.1f}")
        print(f"95%          : {p95:.1f}")
        print(f"Maximum      : {maximum_fold:.1f}")
        print("-----------------------------------------")
        print(f"Fold=1       : {fold_eq_1}")
        print(f"Fold 2-5     : {fold_2_5}")
        print(f"Fold 6-10    : {fold_6_10}")
        print(f"Fold 11-20   : {fold_11_20}")
        print(f"Fold>20      : {fold_gt_20}")
        print("==================================================")
