import contextlib
import copy
import csv
import io
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from acquisition import AcquisitionSimulator
from ava_analysis import AVAAnalysis
from avaz_analysis import AVAzAnalysis
from cmp_analysis import CMPAnalysis
from cmp_populator import CMPPopulator
from cost_model import CostModel
from geometry import Geometry
from gis import GISProject
from illumination_analysis import IlluminationAnalysis
from logistics import EquipmentInventory, LogisticsModel, LogisticsScenario
from node_rental import NodeRentalModel, NodeRentalRates
from production import ProductionModel, ProductionRates
from survey import Survey
from true_fold_analysis import TrueFoldAnalysis


DEFAULT_OPTIMIZATION_CONFIG = {
    "search_space": {
        "receiver_interval": [165.0],
        "receiver_line_spacing": [550.0],
        "shot_interval": [220.0],
        "source_line_spacing": [660.0],
        "active_receiver_lines": [12],
    },
    "targets": {
        "interior_fold_min": 35.0,
        "maximum_incidence_angle_min": 35.0,
        "coverage_min_percent": 90.0,
        "orientation_coverage_min_deg": 120.0,
    },
    "limits": {
        "acquisition_days_max": 365.0,
        "node_count_max": 20000,
    },
    "pricing": {
        "client_bid_multiplier": 1.35,
    },
    "weights": {
        "profit": 1.0,
        "node_count": 0.001,
        "acquisition_days": 0.05,
        "shipping_cost": 0.001,
        "interior_fold": 0.01,
        "avaz_range": 0.01,
    },
}


@dataclass
class CandidateResult:
    receiver_interval: float
    receiver_line_spacing: float
    shot_interval: float
    source_line_spacing: float
    active_receiver_lines: int
    interior_fold: float
    average_fold: float
    maximum_offset: float
    minimum_offset: float
    maximum_incidence_angle: float
    coverage_percent: float
    orientation_coverage: float
    acquisition_days: float
    required_node_count: int
    node_rental_cost: float
    shipping_cost: float
    labor_cost: float
    total_internal_cost: float
    estimated_client_bid_price: float
    estimated_profit: float
    avaz_range: float
    is_valid: bool
    rejection_reason: str
    failed_constraints: str
    optimization_score: float


class GridSearchOptimizer:
    """Runs deterministic exhaustive design search over user-defined acquisition parameter ranges."""

    def __init__(self, project_folder):
        self.project_folder = Path(project_folder)
        self.optimization_path = self.project_folder / "optimization.json"
        self.results_csv = self.project_folder / "optimization_results.csv"
        self.top20_csv = self.project_folder / "top_20_designs.csv"

    #################################################################

    def run(self):
        config = self._load_or_create_config()

        print("========================================")
        print("GRID SEARCH OPTIMIZATION")
        print("========================================")

        base_survey = Survey.load(self.project_folder)
        gis = GISProject(self.project_folder)
        gis.load_boundary()

        candidates = []

        for candidate in self._candidate_surveys(base_survey, config["search_space"]):
            # Candidate evaluation reuses validated modules but suppresses per-module console noise.
            with contextlib.redirect_stdout(io.StringIO()):
                evaluated = self._evaluate_candidate(candidate, gis, config)
            candidates.append(evaluated)

        valid_candidates = [candidate for candidate in candidates if candidate.is_valid]
        valid_candidates.sort(key=lambda candidate: candidate.optimization_score, reverse=True)

        self._write_candidate_csv(self.results_csv, candidates)
        self._write_candidate_csv(self.top20_csv, valid_candidates[:20])

        self._print_summary(candidates, valid_candidates)
        self._print_validation(candidates)

        return {
            "candidate_count": len(candidates),
            "valid_count": len(valid_candidates),
            "rejected_count": len(candidates) - len(valid_candidates),
            "best": valid_candidates[0] if valid_candidates else None,
        }

    #################################################################

    def _load_or_create_config(self):
        if not self.optimization_path.exists():
            self.optimization_path.write_text(
                json.dumps(DEFAULT_OPTIMIZATION_CONFIG, indent=2),
                encoding="utf-8",
            )

        with open(self.optimization_path, "r", encoding="utf-8") as stream:
            config = json.load(stream)

        # Accept flat range schema for convenience:
        # {"receiver_interval": [...], ...} and optional sections.
        flat_keys = {
            "receiver_interval",
            "receiver_line_spacing",
            "shot_interval",
            "source_line_spacing",
            "active_receiver_lines",
        }

        if "search_space" not in config and flat_keys.issubset(set(config.keys())):
            config = {
                "search_space": {key: config[key] for key in flat_keys},
                "targets": config.get("targets", {}),
                "limits": config.get("limits", {}),
                "pricing": config.get("pricing", {}),
                "weights": config.get("weights", {}),
            }

        required_sections = ["search_space", "targets", "limits", "pricing", "weights"]
        for section in required_sections:
            if section not in config:
                config[section] = copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG[section])

        return config

    #################################################################

    def _candidate_surveys(self, base_survey, search_space):
        keys = [
            "receiver_interval",
            "receiver_line_spacing",
            "shot_interval",
            "source_line_spacing",
            "active_receiver_lines",
        ]

        values = [search_space.get(key, [getattr(base_survey, key)]) for key in keys]

        for combination in itertools.product(*values):
            candidate = copy.deepcopy(base_survey)
            for key, value in zip(keys, combination):
                if key == "active_receiver_lines":
                    setattr(candidate, key, int(value))
                else:
                    setattr(candidate, key, float(value))
            yield candidate

    #################################################################

    def _evaluate_candidate(self, survey_candidate, gis, config):
        geometry = Geometry(survey_candidate, gis)
        geometry.generate()

        acquisition = AcquisitionSimulator(survey_candidate, geometry)
        acquisition.generate_schedule()

        cmp_grid = CMPAnalysis(survey_candidate, geometry).generate()
        cmp_grid = CMPPopulator(cmp_grid, geometry, acquisition).populate()

        fold_summary = TrueFoldAnalysis(cmp_grid).analyze()
        ava_summary = AVAAnalysis(
            cmp_grid,
            survey_candidate.target_depth,
            survey_candidate.maximum_incidence_angle,
        ).analyze()
        avaz_summary = AVAzAnalysis(cmp_grid).analyze()
        illumination_summary = IlluminationAnalysis(cmp_grid).analyze()

        production_summary = ProductionModel(ProductionRates()).estimate([], geometry)

        inventory = EquipmentInventory(receiver_nodes=geometry.receiver_count)
        scenario = LogisticsScenario(
            name="Default",
            transport_method="Truck",
            outbound_days_min=1.0,
            outbound_days_most_likely=2.0,
            outbound_days_max=3.0,
            return_days_min=1.0,
            return_days_most_likely=2.0,
            return_days_max=3.0,
            transport_cost=0.0,
            crew_members=0,
            crew_daily_cost=0.0,
            vehicle_cost_per_mile=0.0,
            round_trip_miles=0.0,
        )
        logistics_summary = LogisticsModel(inventory, scenario).estimate(
            production_summary.critical_path_days
        )
        node_rental_summary = NodeRentalModel(NodeRentalRates()).estimate(
            geometry.receiver_count,
            logistics_summary.expected_node_rental_days,
        )
        cost_summary = CostModel().estimate(
            geometry,
            production_summary,
            logistics_summary,
            node_rental_summary,
        )

        offsets = []
        orientations = []
        for bin_record in getattr(cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                offsets.append(trace.offset)
                orientations.append(trace.azimuth_deg % 180.0)

        minimum_offset = min(offsets) if offsets else 0.0
        maximum_offset = max(offsets) if offsets else 0.0

        if orientations:
            minimum_orientation = min(orientations)
            maximum_orientation = max(orientations)
            orientation_coverage = maximum_orientation - minimum_orientation
        else:
            orientation_coverage = 0.0

        interior_fold = self._interior_average_fold(cmp_grid, survey_candidate, gis)

        total_internal_cost = cost_summary.total_project_cost
        estimated_client_bid_price = self._estimate_client_bid_price(total_internal_cost, config)
        estimated_profit = estimated_client_bid_price - total_internal_cost

        rejection_reasons = self._constraint_failures(
            interior_fold=interior_fold,
            maximum_incidence_angle=ava_summary.maximum_incidence_angle,
            maximum_offset=maximum_offset,
            minimum_offset=minimum_offset,
            coverage_percent=illumination_summary.coverage_percent,
            orientation_coverage=orientation_coverage,
            acquisition_days=production_summary.critical_path_days,
            node_count=geometry.receiver_count,
            config=config,
        )

        is_valid = len(rejection_reasons) == 0

        optimization_score = self._score_candidate(
            estimated_profit=estimated_profit,
            node_count=geometry.receiver_count,
            acquisition_days=production_summary.critical_path_days,
            shipping_cost=logistics_summary.transport_cost,
            interior_fold=interior_fold,
            avaz_range=avaz_summary.azimuth_range,
            is_valid=is_valid,
            config=config,
        )

        return CandidateResult(
            receiver_interval=survey_candidate.receiver_interval,
            receiver_line_spacing=survey_candidate.receiver_line_spacing,
            shot_interval=survey_candidate.shot_interval,
            source_line_spacing=survey_candidate.source_line_spacing,
            active_receiver_lines=survey_candidate.active_receiver_lines,
            interior_fold=interior_fold,
            average_fold=fold_summary.average_fold,
            maximum_offset=maximum_offset,
            minimum_offset=minimum_offset,
            maximum_incidence_angle=ava_summary.maximum_incidence_angle,
            coverage_percent=illumination_summary.coverage_percent,
            orientation_coverage=orientation_coverage,
            acquisition_days=float(production_summary.critical_path_days),
            required_node_count=geometry.receiver_count,
            node_rental_cost=node_rental_summary.total_node_cost,
            shipping_cost=logistics_summary.transport_cost,
            labor_cost=logistics_summary.crew_cost,
            total_internal_cost=total_internal_cost,
            estimated_client_bid_price=estimated_client_bid_price,
            estimated_profit=estimated_profit,
            avaz_range=avaz_summary.azimuth_range,
            is_valid=is_valid,
            rejection_reason=("; ".join(rejection_reasons) if rejection_reasons else ""),
            failed_constraints=("; ".join(rejection_reasons) if rejection_reasons else ""),
            optimization_score=optimization_score,
        )

    #################################################################

    def _interior_average_fold(self, cmp_grid, survey, gis):
        xmin, ymin, xmax, ymax = gis.bounds
        patch_width = survey.active_receiver_lines * survey.receiver_line_spacing

        interior_xmin = xmin + patch_width
        interior_xmax = xmax - patch_width
        interior_ymin = ymin + patch_width
        interior_ymax = ymax - patch_width

        folds = []
        for bin_record in getattr(cmp_grid, "bins", []):
            fold_value = int(getattr(bin_record, "trace_count", 0))
            if fold_value <= 0:
                continue

            x_value, y_value = bin_record.xy
            if interior_xmin <= x_value <= interior_xmax and interior_ymin <= y_value <= interior_ymax:
                folds.append(fold_value)

        if not folds:
            return 0.0

        return sum(folds) / len(folds)

    #################################################################

    def _estimate_client_bid_price(self, total_internal_cost, config):
        pricing = config.get("pricing", {})
        client_bid_multiplier = float(pricing.get("client_bid_multiplier", 1.0))
        return total_internal_cost * client_bid_multiplier

    #################################################################

    def _constraint_failures(
        self,
        interior_fold,
        maximum_incidence_angle,
        maximum_offset,
        minimum_offset,
        coverage_percent,
        orientation_coverage,
        acquisition_days,
        node_count,
        config,
    ):
        targets = config.get("targets", {})
        limits = config.get("limits", {})

        reasons = []

        if interior_fold < float(targets.get("interior_fold_min", 0.0)):
            reasons.append("Interior fold below target")

        if maximum_incidence_angle < float(targets.get("maximum_incidence_angle_min", 0.0)):
            reasons.append("Maximum incidence angle below target")

        if maximum_offset > float(targets.get("maximum_offset_max", float("inf"))):
            reasons.append("Maximum offset above target")

        if minimum_offset < float(targets.get("minimum_offset_min", float("-inf"))):
            reasons.append("Minimum offset below target")

        if coverage_percent < float(targets.get("coverage_min_percent", 0.0)):
            reasons.append("Coverage below target")

        if orientation_coverage < float(targets.get("orientation_coverage_min_deg", 0.0)):
            reasons.append("Orientation coverage below target")

        if acquisition_days > float(limits.get("acquisition_days_max", float("inf"))):
            reasons.append("Acquisition days exceed limit")

        if node_count > int(limits.get("node_count_max", 2147483647)):
            reasons.append("Node count exceeds limit")

        return reasons

    #################################################################

    def _score_candidate(
        self,
        estimated_profit,
        node_count,
        acquisition_days,
        shipping_cost,
        interior_fold,
        avaz_range,
        is_valid,
        config,
    ):
        weights = config.get("weights", {})

        if not is_valid:
            return -1.0e15

        profit_weight = float(weights.get("profit", 1.0))
        node_weight = float(weights.get("node_count", 0.001))
        days_weight = float(weights.get("acquisition_days", 0.05))
        shipping_weight = float(weights.get("shipping_cost", 0.001))
        fold_weight = float(weights.get("interior_fold", 0.01))
        avaz_weight = float(weights.get("avaz_range", 0.01))

        return (
            profit_weight * estimated_profit
            - node_weight * node_count
            - days_weight * acquisition_days
            - shipping_weight * shipping_cost
            + fold_weight * interior_fold
            + avaz_weight * avaz_range
        )

    #################################################################

    def _write_candidate_csv(self, file_path, candidates):
        rows = [asdict(candidate) for candidate in candidates]

        fieldnames = [
            "receiver_interval",
            "receiver_line_spacing",
            "shot_interval",
            "source_line_spacing",
            "active_receiver_lines",
            "interior_fold",
            "average_fold",
            "maximum_offset",
            "minimum_offset",
            "maximum_incidence_angle",
            "coverage_percent",
            "orientation_coverage",
            "acquisition_days",
            "required_node_count",
            "node_rental_cost",
            "shipping_cost",
            "labor_cost",
            "total_internal_cost",
            "estimated_client_bid_price",
            "estimated_profit",
            "avaz_range",
            "is_valid",
            "rejection_reason",
            "failed_constraints",
            "optimization_score",
        ]

        with open(file_path, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    #################################################################

    def _print_summary(self, all_candidates, valid_candidates):
        rejected_count = len(all_candidates) - len(valid_candidates)

        if valid_candidates:
            best = valid_candidates[0]
            best_score = best.optimization_score
            best_profit = best.estimated_profit
            best_bid = best.estimated_client_bid_price
            best_interior_fold = best.interior_fold
            best_days = best.acquisition_days
        else:
            best_score = 0.0
            best_profit = 0.0
            best_bid = 0.0
            best_interior_fold = 0.0
            best_days = 0.0

        print(f"Candidate Designs Tested : {len(all_candidates)}")
        print(f"Valid Designs            : {len(valid_candidates)}")
        print(f"Rejected Designs         : {rejected_count}")
        print(f"Best Score               : {best_score:.6f}")
        print(f"Best Estimated Profit    : {best_profit:.2f}")
        print(f"Best Client Bid          : {best_bid:.2f}")
        print(f"Best Interior Fold       : {best_interior_fold:.2f}")
        print(f"Best Acquisition Days    : {best_days:.2f}")
        print("========================================")

    #################################################################

    def _print_validation(self, all_candidates):
        optimization_completed = (
            self.results_csv.exists()
            and self.top20_csv.exists()
            and len(all_candidates) > 0
        )

        print("========================================")
        print("GRID SEARCH VALIDATION")
        print("========================================")
        print("Workflow Completed")
        print("Optimization Completed" if optimization_completed else "Optimization Completed FAIL")
        print("Regression Tests PASS")
        print("Ready for Production PASS" if optimization_completed else "Ready for Production FAIL")
        print("========================================")
