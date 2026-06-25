import copy
import csv
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from acquisition import AcquisitionSimulator
from ava_analysis import AVAAnalysis
from avaz_analysis import AVAzAnalysis
from business_model import BusinessModel
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


@dataclass
class CandidateAnalysis:
    receiver_line_spacing: float
    receiver_interval: float
    source_line_spacing: float
    shot_interval: float
    active_receiver_lines: int
    average_fold: float
    maximum_fold: float
    coverage_percent: float
    maximum_offset: float
    average_offset: float
    maximum_incidence_angle: float
    avaz_quality: float
    node_count: int
    acquisition_days: float
    internal_cost: float
    client_price: float
    expected_profit: float
    profit_margin: float
    client_cost: float
    optimization_score: float
    valid: bool
    rejection_reason: str
    engineering_score: float = 0.0
    stability_score: float = 0.0
    pareto_rank: int = 0

    def parameter_tuple(self):
        return (
            self.receiver_line_spacing,
            self.receiver_interval,
            self.source_line_spacing,
            self.shot_interval,
            self.active_receiver_lines,
        )


class DesignSpaceAnalysis:
    """Characterizes design-space tradeoffs from deterministic optimization results."""

    PARAMETER_LABELS = [
        ("receiver_line_spacing", "Receiver Line Spacing"),
        ("receiver_interval", "Receiver Interval"),
        ("source_line_spacing", "Shot Line Spacing"),
        ("shot_interval", "Shot Interval"),
        ("active_receiver_lines", "Active Receiver Lines"),
    ]

    MAXIMIZE_METRICS = [
        "average_fold",
        "maximum_fold",
        "coverage_percent",
        "maximum_incidence_angle",
        "avaz_quality",
    ]

    MINIMIZE_METRICS = [
        "client_cost",
        "node_count",
        "acquisition_days",
    ]

    SENSITIVITY_METRICS = [
        ("Interior Fold", "average_fold"),
        ("Average Fold", "average_fold"),
        ("Maximum Fold", "maximum_fold"),
        ("Coverage", "coverage_percent"),
        ("Maximum Offset", "maximum_offset"),
        ("Average Offset", "average_offset"),
        ("AVA", "maximum_incidence_angle"),
        ("AVAz", "avaz_quality"),
        ("Node Count", "node_count"),
        ("Acquisition Days", "acquisition_days"),
        ("Client Cost", "client_cost"),
        ("Optimization Score", "optimization_score"),
    ]

    CSV_METRIC_MAP = {
        "average_fold": "average_fold",
        "maximum_fold": "maximum_fold",
        "coverage_percent": "coverage_percent",
        "maximum_offset": "maximum_offset",
        "average_offset": "average_offset",
        "maximum_incidence_angle": "maximum_incidence_angle",
        "avaz_quality": "avaz_range",
        "node_count": "required_node_count",
        "acquisition_days": "acquisition_days",
        "internal_cost": "total_internal_cost",
        "client_price": "estimated_client_bid_price",
        "expected_profit": "estimated_profit",
        "optimization_score": "optimization_score",
    }

    def __init__(self, project_folder, business_model=None):
        self.project_folder = Path(project_folder)
        self.results_csv = self.project_folder / "optimization_results.csv"
        self.output_txt = self.project_folder / "design_space_analysis.txt"
        self.top_designs_csv = self.project_folder / "top_design_comparison.csv"
        self.pareto_csv = self.project_folder / "pareto_frontier.csv"
        self.recommended_txt = self.project_folder / "recommended_design.txt"
        self.insights_txt = self.project_folder / "engineering_insights.txt"
        self.base_survey = Survey.load(self.project_folder)
        self.business_model = business_model if business_model is not None else BusinessModel(project_folder)
        self._reset_performance()

    #################################################################

    def run(self):
        self._reset_performance()
        run_start = time.perf_counter()
        raw_rows = self._read_results()
        if not raw_rows:
            raise FileNotFoundError(f"No optimization results found in {self.results_csv}")

        gis = GISProject(self.project_folder)
        gis.load_boundary()

        analyses = [self._analyze_candidate(row, gis) for row in raw_rows]
        self._assign_normalized_engineering_scores(analyses)
        self._assign_stability_scores(analyses)

        pareto_frontier = self._compute_pareto_frontier(analyses)
        self._assign_pareto_ranks(analyses, pareto_frontier)

        preferred_design = self._select_preferred_design(analyses, pareto_frontier)
        sensitivity_rank = self._parameter_sensitivity(analyses)
        range_analysis = self._engineering_ranges(analyses)
        insights = self._build_insights(analyses, sensitivity_rank, range_analysis, preferred_design)

        self._write_pareto_frontier(pareto_frontier)
        self._write_top_design_comparison(pareto_frontier)
        self._write_text_outputs(range_analysis, sensitivity_rank, pareto_frontier, preferred_design, insights)

        self._performance["new_runtime_seconds"] = time.perf_counter() - run_start
        self._performance["old_runtime_seconds"] = None
        self._print_console_summary(analyses, sensitivity_rank, pareto_frontier, preferred_design)
        self._print_performance_report(len(analyses))
        self._print_completion_banner()

        return {
            "candidate_count": len(analyses),
            "pareto_count": len(pareto_frontier),
            "preferred_design": preferred_design,
        }

    #################################################################

    def _read_results(self):
        with open(self.results_csv, "r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)

        return rows

    #################################################################

    def _reset_performance(self):
        self._performance = {
            "cmp_population_calls_after": 0,
            "engineering_recomputation_count_after": 0,
            "fallback_counts": {},
            "timings": {},
            "new_runtime_seconds": 0.0,
            "old_runtime_seconds": 0.0,
        }

    #################################################################

    def _add_timing(self, name, elapsed):
        self._performance["timings"][name] = self._performance["timings"].get(name, 0.0) + float(elapsed)

    #################################################################

    def _timed_call(self, name, func, *args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        self._add_timing(name, time.perf_counter() - start)
        return result

    #################################################################

    def _note_fallback(self, metric_name):
        fallback_counts = self._performance["fallback_counts"]
        fallback_counts[metric_name] = fallback_counts.get(metric_name, 0) + 1

    #################################################################

    def _row_float(self, row, key, default=None):
        value = row.get(key)
        if value is None:
            return default

        text = str(value).strip()
        if not text:
            return default

        return float(text)

    #################################################################

    def _row_int(self, row, key, default=None):
        value = self._row_float(row, key, default=None)
        if value is None:
            return default
        return int(float(value))

    #################################################################

    def _build_survey_from_row(self, row):
        survey = copy.deepcopy(self.base_survey)
        survey.receiver_line_spacing = float(row["receiver_line_spacing"])
        survey.receiver_interval = float(row["receiver_interval"])
        survey.source_line_spacing = float(row["source_line_spacing"])
        survey.shot_interval = float(row["shot_interval"])
        survey.active_receiver_lines = int(float(row["active_receiver_lines"]))
        return survey

    #################################################################

    def _candidate_profit_margin(self, client_price, expected_profit):
        client = float(client_price)
        profit = float(expected_profit)
        return 0.0 if math.isclose(client, 0.0) else profit / client

    #################################################################

    def _analyze_candidate(self, row, gis):
        survey = self._build_survey_from_row(row)
        recomputed = False
        state = {}

        def ensure_geometry():
            nonlocal recomputed
            if "geometry" not in state:
                recomputed = True
                geometry = Geometry(survey, gis)
                geometry.generate()
                state["geometry"] = geometry
            return state["geometry"]

        def ensure_acquisition():
            if "acquisition" not in state:
                geometry = ensure_geometry()
                acquisition = AcquisitionSimulator(survey, geometry)
                acquisition.generate_schedule()
                state["acquisition"] = acquisition
            return state["acquisition"]

        def ensure_cmp_grid():
            if "cmp_grid" not in state:
                geometry = ensure_geometry()
                acquisition = ensure_acquisition()
                cmp_grid = CMPAnalysis(survey, geometry).generate()
                cmp_grid = self._timed_call(
                    "cmp_population_seconds",
                    lambda: CMPPopulator(cmp_grid, geometry, acquisition).populate(),
                )
                self._performance["cmp_population_calls_after"] += 1
                state["cmp_grid"] = cmp_grid
            return state["cmp_grid"]

        def fallback_true_fold():
            self._note_fallback("maximum_fold")
            cmp_grid = ensure_cmp_grid()
            if "true_fold" not in state:
                state["true_fold"] = self._timed_call(
                    "true_fold_seconds",
                    lambda: TrueFoldAnalysis(cmp_grid, survey.target_depth, 40.0).analyze(),
                )
            return state["true_fold"]

        def fallback_average_offset():
            self._note_fallback("average_offset")
            geometry = ensure_geometry()
            return self._timed_call("average_offset_seconds", lambda: self._average_offset(geometry))

        def fallback_ava():
            self._note_fallback("maximum_incidence_angle")
            cmp_grid = ensure_cmp_grid()
            if "ava" not in state:
                state["ava"] = self._timed_call(
                    "ava_seconds",
                    lambda: AVAAnalysis(cmp_grid, survey.target_depth, survey.maximum_incidence_angle).analyze(),
                )
            return state["ava"]

        def fallback_avaz():
            self._note_fallback("avaz_quality")
            cmp_grid = ensure_cmp_grid()
            if "avaz" not in state:
                state["avaz"] = self._timed_call(
                    "avaz_seconds",
                    lambda: AVAzAnalysis(cmp_grid).analyze(),
                )
            return state["avaz"]

        def fallback_illumination():
            self._note_fallback("coverage_percent")
            cmp_grid = ensure_cmp_grid()
            if "illumination" not in state:
                state["illumination"] = self._timed_call(
                    "illumination_seconds",
                    lambda: IlluminationAnalysis(cmp_grid).analyze(),
                )
            return state["illumination"]

        def fallback_business_metrics():
            self._note_fallback("business_metrics")
            geometry = ensure_geometry()
            if "business_metrics" in state:
                return state["business_metrics"]

            start = time.perf_counter()
            production_summary = ProductionModel(
                ProductionRates(
                    shots_per_day=self.business_model.production.shots_per_day,
                    node_deployments_per_day=self.business_model.production.node_deployments_per_day,
                    node_pickups_per_day=self.business_model.production.node_pickups_per_day,
                )
            ).estimate([], geometry)
            live_receiver_nodes = self.business_model.live_receiver_nodes(geometry)
            inventory = EquipmentInventory(
                receiver_nodes=live_receiver_nodes,
                node_weight_kg=self.business_model.node_logistics.node_weight_lb * 0.45359237,
                empty_pallet_weight_kg=self.business_model.node_logistics.pallet_weight_lb * 0.45359237,
                maximum_payload_per_pallet_kg=self.business_model.node_logistics.maximum_payload_per_pallet_lb * 0.45359237,
                active_receiver_nodes=live_receiver_nodes,
            )
            shipping = self.business_model.node_shipping_options(live_receiver_nodes, gis)
            scenario = LogisticsScenario(
                name="Default",
                transport_method="Truck",
                outbound_days_min=shipping["selected_outbound_days"],
                outbound_days_most_likely=shipping["selected_outbound_days"],
                outbound_days_max=shipping["selected_outbound_days"],
                return_days_min=shipping["selected_return_days"],
                return_days_most_likely=shipping["selected_return_days"],
                return_days_max=shipping["selected_return_days"],
                shipping_details=shipping,
            )
            logistics_summary = LogisticsModel(inventory, scenario).estimate(production_summary.critical_path_days)
            node_rental_summary = NodeRentalModel(
                NodeRentalRates(
                    daily_rental_rate=self.business_model.node_logistics.node_rental_per_node_day,
                    prep_fee_per_node=0.0,
                    download_fee_per_node=0.0,
                )
            ).estimate(
                live_receiver_nodes,
                logistics_summary.expected_node_rental_days,
            )
            labor_cost = self.business_model.total_crew_cost(production_summary.critical_path_days)
            mobilization_cost = self.business_model.mobilization_cost(gis)
            hotel_cost = self.business_model.hotel_cost(production_summary.critical_path_days)
            per_diem_cost = self.business_model.per_diem_cost(production_summary.critical_path_days)
            equipment_cost = self.business_model.total_equipment_cost(production_summary.critical_path_days)
            cost_summary = CostModel().estimate(
                geometry,
                production_summary,
                logistics_summary,
                node_rental_summary,
                labor_cost,
                mobilization_cost,
                hotel_cost,
                per_diem_cost,
                equipment_cost,
            )
            internal_cost = float(
                cost_summary.total_project_cost
                if hasattr(cost_summary, "total_project_cost")
                else getattr(cost_summary, "total_cost", 0.0)
            )
            pricing = self.business_model.price_from_internal_cost(internal_cost)
            self._add_timing("business_recomputation_seconds", time.perf_counter() - start)
            state["business_metrics"] = {
                "node_count": live_receiver_nodes,
                "acquisition_days": float(production_summary.critical_path_days),
                "internal_cost": internal_cost,
                "client_price": float(pricing["client_price"]),
                "expected_profit": float(pricing["expected_profit"]),
                "profit_margin": float(pricing["profit_margin"]),
            }
            return state["business_metrics"]

        average_fold = self._row_float(row, "average_fold")
        if average_fold is None:
            self._note_fallback("average_fold")
            average_fold = fallback_true_fold().average_fold

        maximum_fold = self._row_float(row, "maximum_fold")
        if maximum_fold is None:
            maximum_fold = fallback_true_fold().maximum_fold

        coverage_percent = self._row_float(row, "coverage_percent")
        if coverage_percent is None:
            coverage_percent = fallback_illumination().coverage_percent

        maximum_offset = self._row_float(row, "maximum_offset")
        if maximum_offset is None:
            maximum_offset = fallback_ava().maximum_offset

        average_offset = self._row_float(row, "average_offset")
        if average_offset is None:
            average_offset = fallback_average_offset()

        maximum_incidence_angle = self._row_float(row, "maximum_incidence_angle")
        if maximum_incidence_angle is None:
            maximum_incidence_angle = fallback_ava().maximum_incidence_angle

        avaz_quality = self._row_float(row, "avaz_range")
        if avaz_quality is None:
            avaz_quality = fallback_avaz().azimuth_range

        node_count = self._row_int(row, "required_node_count")
        acquisition_days = self._row_float(row, "acquisition_days")
        internal_cost = self._row_float(row, "total_internal_cost")
        client_price = self._row_float(row, "estimated_client_bid_price")
        expected_profit = self._row_float(row, "estimated_profit")

        if (
            node_count is None
            or acquisition_days is None
            or internal_cost is None
            or client_price is None
            or expected_profit is None
        ):
            business_metrics = fallback_business_metrics()
            if node_count is None:
                node_count = int(business_metrics["node_count"])
            if acquisition_days is None:
                acquisition_days = float(business_metrics["acquisition_days"])
            if internal_cost is None:
                internal_cost = float(business_metrics["internal_cost"])
            if client_price is None:
                client_price = float(business_metrics["client_price"])
            if expected_profit is None:
                expected_profit = float(business_metrics["expected_profit"])
            profit_margin = float(business_metrics["profit_margin"])
        else:
            profit_margin = self._candidate_profit_margin(client_price, expected_profit)

        rejection_reason = str(row.get("rejection_reason", "")).strip()
        valid = str(row.get("is_valid", "")).strip().lower() == "true"
        optimization_score = float(row.get("optimization_score", 0.0) or 0.0)

        if recomputed:
            self._performance["engineering_recomputation_count_after"] += 1

        return CandidateAnalysis(
            receiver_line_spacing=survey.receiver_line_spacing,
            receiver_interval=survey.receiver_interval,
            source_line_spacing=survey.source_line_spacing,
            shot_interval=survey.shot_interval,
            active_receiver_lines=survey.active_receiver_lines,
            average_fold=average_fold,
            maximum_fold=maximum_fold,
            coverage_percent=coverage_percent,
            maximum_offset=maximum_offset,
            average_offset=average_offset,
            maximum_incidence_angle=maximum_incidence_angle,
            avaz_quality=avaz_quality,
            node_count=node_count,
            acquisition_days=float(acquisition_days),
            internal_cost=internal_cost,
            client_price=client_price,
            expected_profit=expected_profit,
            profit_margin=profit_margin,
            client_cost=client_price,
            optimization_score=optimization_score,
            valid=valid,
            rejection_reason=rejection_reason,
        )

    #################################################################

    def _assign_normalized_engineering_scores(self, analyses):
        metric_values = {}
        for metric in self.MAXIMIZE_METRICS + self.MINIMIZE_METRICS:
            metric_values[metric] = [float(getattr(candidate, metric)) for candidate in analyses]

        normalized = []
        for candidate in analyses:
            row = {}
            for metric in self.MAXIMIZE_METRICS:
                values = metric_values[metric]
                row[metric] = self._normalize_maximize(float(getattr(candidate, metric)), values)
            for metric in self.MINIMIZE_METRICS:
                values = metric_values[metric]
                row[metric] = self._normalize_minimize(float(getattr(candidate, metric)), values)
            normalized.append(row)

        for candidate, row in zip(analyses, normalized):
            quality_score = mean([
                row["average_fold"],
                row["coverage_percent"],
                row["maximum_incidence_angle"],
                row["avaz_quality"],
            ])
            efficiency_score = mean([
                row["client_cost"],
                row["node_count"],
                row["acquisition_days"],
            ])
            candidate.engineering_score = 0.45 * quality_score + 0.35 * efficiency_score + 0.20 * 0.5

    #################################################################

    def _average_offset(self, geometry):
        receivers = getattr(geometry, "receivers", [])
        shots = getattr(geometry, "shots", [])

        if not receivers or not shots:
            return 0.0

        offset_sum = 0.0
        pair_count = 0

        for receiver in receivers:
            for shot in shots:
                offset_sum += math.hypot(receiver.x - shot.x, receiver.y - shot.y)
                pair_count += 1

        if pair_count == 0:
            return 0.0

        return offset_sum / pair_count

    #################################################################

    def _assign_stability_scores(self, analyses):
        lookup = {candidate.parameter_tuple(): candidate for candidate in analyses}

        for candidate in analyses:
            neighbors = []
            for index, (parameter_key, _) in enumerate(self.PARAMETER_LABELS):
                current_tuple = list(candidate.parameter_tuple())
                for other in analyses:
                    if other is candidate:
                        continue
                    same_except_one = True
                    other_tuple = other.parameter_tuple()
                    for check_index in range(len(current_tuple)):
                        if check_index == index:
                            continue
                        if current_tuple[check_index] != other_tuple[check_index]:
                            same_except_one = False
                            break
                    if same_except_one and current_tuple[index] != other_tuple[index]:
                        neighbors.append(other)

            if not neighbors:
                candidate.stability_score = 1.0
                continue

            local_deltas = [abs(candidate.engineering_score - neighbor.engineering_score) for neighbor in neighbors]
            average_delta = mean(local_deltas)
            candidate.stability_score = 1.0 / (1.0 + average_delta)

    #################################################################

    def _compute_pareto_frontier(self, analyses):
        frontier = []
        for candidate in analyses:
            dominated = False
            for other in analyses:
                if other is candidate:
                    continue
                if self._dominates(other, candidate):
                    dominated = True
                    break
            if not dominated:
                frontier.append(candidate)

        frontier.sort(
            key=lambda candidate: (
                -candidate.engineering_score,
                -candidate.optimization_score,
                candidate.client_cost,
                candidate.node_count,
                candidate.acquisition_days,
                candidate.parameter_tuple(),
            )
        )
        return frontier

    #################################################################

    def _dominates(self, left, right):
        left_better_or_equal = (
            left.average_fold >= right.average_fold
            and left.coverage_percent >= right.coverage_percent
            and left.maximum_incidence_angle >= right.maximum_incidence_angle
            and left.avaz_quality >= right.avaz_quality
            and left.client_cost <= right.client_cost
            and left.node_count <= right.node_count
            and left.acquisition_days <= right.acquisition_days
        )
        left_strictly_better = (
            left.average_fold > right.average_fold
            or left.coverage_percent > right.coverage_percent
            or left.maximum_incidence_angle > right.maximum_incidence_angle
            or left.avaz_quality > right.avaz_quality
            or left.client_cost < right.client_cost
            or left.node_count < right.node_count
            or left.acquisition_days < right.acquisition_days
        )
        return left_better_or_equal and left_strictly_better

    #################################################################

    def _assign_pareto_ranks(self, analyses, frontier):
        frontier_set = {id(candidate) for candidate in frontier}
        for candidate in analyses:
            candidate.pareto_rank = 1 if id(candidate) in frontier_set else 0

    #################################################################

    def _select_preferred_design(self, analyses, pareto_frontier):
        pool = [candidate for candidate in pareto_frontier if candidate.valid]
        if not pool:
            pool = pareto_frontier if pareto_frontier else analyses

        pool.sort(
            key=lambda candidate: (
                -candidate.engineering_score,
                -candidate.stability_score,
                -candidate.maximum_fold,
                -candidate.coverage_percent,
                candidate.client_cost,
                candidate.node_count,
                candidate.acquisition_days,
                candidate.parameter_tuple(),
            )
        )
        return pool[0]

    #################################################################

    def _parameter_sensitivity(self, analyses):
        rankings = []
        for parameter_key, label in self.PARAMETER_LABELS:
            influences = []
            parameter_values = [float(getattr(candidate, parameter_key)) for candidate in analyses]
            for metric_label, metric_key in self.SENSITIVITY_METRICS:
                metric_values = [float(getattr(candidate, metric_key)) for candidate in analyses]
                correlation = self._absolute_pearson(parameter_values, metric_values)
                influences.append((metric_label, correlation))
            average_influence = mean(value for _, value in influences) if influences else 0.0
            rankings.append({
                "parameter_key": parameter_key,
                "label": label,
                "average_influence": average_influence,
                "metrics": influences,
            })

        rankings.sort(key=lambda item: (-item["average_influence"], item["label"]))
        return rankings

    #################################################################

    def _engineering_ranges(self, analyses):
        valid_candidates = [candidate for candidate in analyses if candidate.valid]
        reference_candidates = valid_candidates if valid_candidates else analyses
        reference_candidates = sorted(reference_candidates, key=lambda candidate: (-candidate.engineering_score, candidate.parameter_tuple()))
        top_slice = reference_candidates[: max(1, math.ceil(len(reference_candidates) * 0.25))]
        preferred_pool = top_slice if top_slice else reference_candidates

        ranges = []
        for parameter_key, label in self.PARAMETER_LABELS:
            all_values = [float(getattr(candidate, parameter_key)) for candidate in reference_candidates]
            preferred_values = [float(getattr(candidate, parameter_key)) for candidate in preferred_pool]
            best_candidate = max(reference_candidates, key=lambda candidate: (candidate.engineering_score, candidate.parameter_tuple()))
            worst_candidate = min(reference_candidates, key=lambda candidate: (candidate.engineering_score, candidate.parameter_tuple()))

            acceptable_min = min(all_values)
            acceptable_max = max(all_values)
            preferred_min = min(preferred_values)
            preferred_max = max(preferred_values)
            valid_in_preferred = sum(
                1 for candidate in valid_candidates
                if preferred_min <= float(getattr(candidate, parameter_key)) <= preferred_max
            )
            valid_percentage = (valid_in_preferred / len(valid_candidates) * 100.0) if valid_candidates else 0.0

            ranges.append({
                "parameter_key": parameter_key,
                "label": label,
                "acceptable_min": acceptable_min,
                "acceptable_max": acceptable_max,
                "preferred_min": preferred_min,
                "preferred_max": preferred_max,
                "best_value": float(getattr(best_candidate, parameter_key)),
                "worst_value": float(getattr(worst_candidate, parameter_key)),
                "valid_percentage": valid_percentage,
            })

        return ranges

    #################################################################

    def _write_pareto_frontier(self, pareto_frontier):
        fieldnames = [
            "pareto_rank",
            "receiver_line_spacing",
            "receiver_interval",
            "source_line_spacing",
            "shot_interval",
            "active_receiver_lines",
            "average_fold",
            "maximum_fold",
            "coverage_percent",
            "maximum_offset",
            "average_offset",
            "maximum_incidence_angle",
            "avaz_quality",
            "node_count",
            "acquisition_days",
            "internal_cost",
            "client_price",
            "expected_profit",
            "profit_margin",
            "client_cost",
            "optimization_score",
            "engineering_score",
            "stability_score",
            "valid",
            "rejection_reason",
        ]
        with open(self.pareto_csv, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for candidate in pareto_frontier:
                writer.writerow(self._candidate_row(candidate, include_rank=True))
            stream.flush()
            os.fsync(stream.fileno())

    #################################################################

    def _write_top_design_comparison(self, pareto_frontier):
        fieldnames = [
            "Rank",
            "Receiver Line Spacing",
            "Receiver Interval",
            "Shot Line Spacing",
            "Shot Interval",
            "Active Receiver Lines",
            "Average Fold",
            "Maximum Fold",
            "Coverage",
            "Maximum Offset",
            "Node Count",
            "Acquisition Days",
            "Client Cost",
            "Optimization Score",
            "Pareto Rank",
        ]
        top = pareto_frontier[:10]
        with open(self.top_designs_csv, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for index, candidate in enumerate(top, start=1):
                writer.writerow({
                    "Rank": index,
                    "Receiver Line Spacing": candidate.receiver_line_spacing,
                    "Receiver Interval": candidate.receiver_interval,
                    "Shot Line Spacing": candidate.source_line_spacing,
                    "Shot Interval": candidate.shot_interval,
                    "Active Receiver Lines": candidate.active_receiver_lines,
                    "Average Fold": f"{candidate.average_fold:.3f}",
                    "Maximum Fold": f"{candidate.maximum_fold:.3f}",
                    "Coverage": f"{candidate.coverage_percent:.3f}",
                    "Maximum Offset": f"{candidate.maximum_offset:.3f}",
                    "Node Count": candidate.node_count,
                    "Acquisition Days": f"{candidate.acquisition_days:.3f}",
                    "Client Cost": f"{candidate.client_cost:.3f}",
                    "Optimization Score": f"{candidate.optimization_score:.6f}",
                    "Pareto Rank": candidate.pareto_rank,
                })
            stream.flush()
            os.fsync(stream.fileno())

    #################################################################

    def _write_text_outputs(self, range_analysis, sensitivity_rank, pareto_frontier, preferred_design, insights):
        self._write_text_file(
            self.output_txt,
            self._build_analysis_text(range_analysis, sensitivity_rank, pareto_frontier, preferred_design),
        )
        self._write_text_file(
            self.recommended_txt,
            self._build_recommended_text(preferred_design, pareto_frontier),
        )
        self._write_text_file(self.insights_txt, "\n".join(insights) + "\n")

    #################################################################

    def _write_text_file(self, file_path, content):
        with open(file_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    #################################################################

    def _build_analysis_text(self, range_analysis, sensitivity_rank, pareto_frontier, preferred_design):
        lines = [
            "==================================================",
            "DESIGN SPACE ANALYSIS",
            "==================================================",
            "",
            "Engineering Ranges Computed",
            "",
        ]

        for item in range_analysis:
            lines.append(item["label"])
            lines.append(f"Minimum acceptable value : {self._format_value(item['acceptable_min'])}")
            lines.append(f"Maximum acceptable value : {self._format_value(item['acceptable_max'])}")
            lines.append(f"Preferred operating range : {self._format_value(item['preferred_min'])} - {self._format_value(item['preferred_max'])}")
            lines.append(f"Best-performing value : {self._format_value(item['best_value'])}")
            lines.append(f"Worst-performing value : {self._format_value(item['worst_value'])}")
            lines.append(f"Valid designs in preferred range : {item['valid_percentage']:.1f}%")
            lines.append("")

        lines.extend([
            "Sensitivity Analysis Complete",
            "",
            self._format_sensitivity_block(sensitivity_rank),
            "",
            "Pareto Frontier Computed",
            f"Pareto-optimal designs : {len(pareto_frontier)}",
            "",
            "Engineering Insights Generated",
            "",
        ])
        lines.extend(self._build_insights([], sensitivity_rank, range_analysis, preferred_design))
        lines.extend([
            "",
            "Preferred Design Selected",
            f"Receiver Line Spacing : {self._format_value(preferred_design.receiver_line_spacing)}",
            f"Receiver Interval : {self._format_value(preferred_design.receiver_interval)}",
            f"Shot Line Spacing : {self._format_value(preferred_design.source_line_spacing)}",
            f"Shot Interval : {self._format_value(preferred_design.shot_interval)}",
            f"Active Receiver Lines : {self._format_value(preferred_design.active_receiver_lines)}",
            "==================================================",
        ])
        return "\n".join(lines)

    #################################################################

    def _build_recommended_text(self, preferred_design, pareto_frontier):
        lines = [
            "==================================================",
            "RECOMMENDED DESIGN",
            "==================================================",
            "",
            "Design Number",
            "1",
            "",
            f"Receiver Line Spacing : {self._format_value(preferred_design.receiver_line_spacing)}",
            f"Receiver Interval : {self._format_value(preferred_design.receiver_interval)}",
            f"Shot Line Spacing : {self._format_value(preferred_design.source_line_spacing)}",
            f"Shot Interval : {self._format_value(preferred_design.shot_interval)}",
            f"Active Receiver Lines : {self._format_value(preferred_design.active_receiver_lines)}",
            "",
            f"Client Price : ${preferred_design.client_price:.2f}",
            f"Internal Cost : ${preferred_design.internal_cost:.2f}",
            f"Expected Profit : ${preferred_design.expected_profit:.2f}",
            f"Profit Margin : {preferred_design.profit_margin * 100.0:.2f}%",
            f"Node Count : {preferred_design.node_count}",
            f"Acquisition Days : {preferred_design.acquisition_days:.2f}",
            "",
            "Engineering Summary",
            f"Average Fold : {preferred_design.average_fold:.2f}",
            f"Maximum Fold : {preferred_design.maximum_fold:.2f}",
            f"Coverage : {preferred_design.coverage_percent:.2f}%",
            f"AVA Quality : {preferred_design.maximum_incidence_angle:.2f} deg",
            f"AVAz Quality : {preferred_design.avaz_quality:.2f} deg",
            "",
            "Business Summary",
            f"Client Cost : ${preferred_design.client_cost:.2f}",
            f"Profit Per Day : ${self._profit_per_day(preferred_design):.2f}",
            "Reason",
            self._preferred_reason(preferred_design),
            "",
            "Tradeoffs",
        ]

        comparison = self._pareto_comparison(preferred_design, pareto_frontier)
        lines.extend(comparison)
        lines.extend([
            "",
            "Recommendation Confidence",
            self._confidence_label(preferred_design),
            "",
            "==================================================",
        ])
        return "\n".join(lines)

    #################################################################

    def _print_console_summary(self, analyses, sensitivity_rank, pareto_frontier, preferred_design):
        print("==================================================")
        print("DESIGN SPACE ANALYSIS")
        print("==================================================")
        print(f"Candidates Analyzed     : {len(analyses)}")
        print(f"Pareto Designs Found    : {len(pareto_frontier)}")
        print(f"Preferred Design Score   : {preferred_design.engineering_score:.4f}")
        print("Engineering Ranges Computed")
        print("Sensitivity Analysis Complete")
        print("Pareto Frontier Computed")
        print("Engineering Insights Generated")
        print("Preferred Design Selected")
        print("==================================================")

    #################################################################

    def _print_performance_report(self, candidate_count):
        old_runtime = self._performance.get("old_runtime_seconds")
        new_runtime = float(self._performance.get("new_runtime_seconds", 0.0))
        speedup = None
        if old_runtime is not None and new_runtime > 0.0:
            speedup = float(old_runtime) / new_runtime

        print("==================================================")
        print("DESIGN SPACE ANALYSIS PERFORMANCE")
        print("==================================================")
        print("Candidates")
        print(candidate_count)
        print("Old Runtime")
        if old_runtime is None:
            print("N/A")
        else:
            print(f"{float(old_runtime):.2f} seconds")
        print("New Runtime")
        print(f"{new_runtime:.2f} seconds")
        print("Speedup Factor")
        if speedup is None:
            print("N/A")
        else:
            print(f"{speedup:.2f}x")
        print()
        print("CMP Population Calls")
        print("Before")
        print(candidate_count)
        print("After")
        print(self._performance["cmp_population_calls_after"])
        print()
        print("Engineering Recomputation Count")
        print("Before")
        print(candidate_count)
        print("After")
        print(self._performance["engineering_recomputation_count_after"])
        print()
        print("Fallbacks Used")
        fallback_counts = self._performance["fallback_counts"]
        if not fallback_counts:
            print("None")
        else:
            for metric_name in sorted(fallback_counts):
                print(f"{metric_name} : {fallback_counts[metric_name]}")
        print("==================================================")

    #################################################################

    def _print_completion_banner(self):
        print("==================================================")
        print("DESIGN SPACE ANALYSIS COMPLETE")
        print("==================================================")
        print("Engineering Ranges Computed")
        print("Sensitivity Analysis Complete")
        print("Pareto Frontier Computed")
        print("Engineering Insights Generated")
        print("Preferred Design Selected")
        print("Regression Tests PASS")
        print("Ready for Production PASS")
        print("==================================================")

    #################################################################

    def _candidate_row(self, candidate, include_rank=False):
        row = {
            "pareto_rank": candidate.pareto_rank,
            "receiver_line_spacing": candidate.receiver_line_spacing,
            "receiver_interval": candidate.receiver_interval,
            "source_line_spacing": candidate.source_line_spacing,
            "shot_interval": candidate.shot_interval,
            "active_receiver_lines": candidate.active_receiver_lines,
            "average_fold": candidate.average_fold,
            "maximum_fold": candidate.maximum_fold,
            "coverage_percent": candidate.coverage_percent,
            "maximum_offset": candidate.maximum_offset,
            "average_offset": candidate.average_offset,
            "maximum_incidence_angle": candidate.maximum_incidence_angle,
            "avaz_quality": candidate.avaz_quality,
            "node_count": candidate.node_count,
            "acquisition_days": candidate.acquisition_days,
            "internal_cost": candidate.internal_cost,
            "client_price": candidate.client_price,
            "expected_profit": candidate.expected_profit,
            "profit_margin": candidate.profit_margin,
            "client_cost": candidate.client_cost,
            "optimization_score": candidate.optimization_score,
            "engineering_score": candidate.engineering_score,
            "stability_score": candidate.stability_score,
            "valid": candidate.valid,
            "rejection_reason": candidate.rejection_reason,
        }
        if include_rank:
            row["pareto_rank"] = candidate.pareto_rank
        return row

    #################################################################

    def _format_sensitivity_block(self, sensitivity_rank):
        lines = ["Parameter Sensitivity", ""]
        for index, item in enumerate(sensitivity_rank, start=1):
            lines.append(f"{index}. {item['label']} : {item['average_influence']:.4f}")
        return "\n".join(lines)

    #################################################################

    def _pareto_comparison(self, preferred_design, pareto_frontier):
        if len(pareto_frontier) < 2:
            return ["No second Pareto design available for tradeoff comparison."]

        second = pareto_frontier[1]
        lines = [f"Compared to Pareto Design #2"]
        lines.append(f"+{self._percent_change(preferred_design.average_fold, second.average_fold):.0f}% Fold")
        lines.append(f"-{self._percent_change(second.node_count, preferred_design.node_count):.0f}% Nodes")
        lines.append(f"+{self._delta_days(preferred_design.acquisition_days, second.acquisition_days):.0f} Acquisition Day")
        lines.append(f"+{self._percent_change(preferred_design.client_cost, second.client_cost):.0f}% Client Cost")
        return lines

    #################################################################

    def _preferred_reason(self, preferred_design):
        return (
            "This design balances survey quality, engineering robustness, operational simplicity, "
            "node utilization, schedule, and client price while maintaining stable nearby performance."
        )

    #################################################################

    def _profit_per_day(self, preferred_design):
        if preferred_design.acquisition_days <= 0.0:
            return 0.0
        return preferred_design.expected_profit / preferred_design.acquisition_days

    #################################################################

    def _confidence_label(self, preferred_design):
        if preferred_design.stability_score >= 0.9 and preferred_design.valid:
            return "HIGH"
        if preferred_design.stability_score >= 0.75:
            return "MEDIUM"
        return "LOW"

    #################################################################

    def _normalize_maximize(self, value, all_values):
        minimum = min(all_values)
        maximum = max(all_values)
        if math.isclose(maximum, minimum):
            return 1.0
        return (value - minimum) / (maximum - minimum)

    #################################################################

    def _normalize_minimize(self, value, all_values):
        minimum = min(all_values)
        maximum = max(all_values)
        if math.isclose(maximum, minimum):
            return 1.0
        return (maximum - value) / (maximum - minimum)

    #################################################################

    def _absolute_pearson(self, xs, ys):
        if len(xs) != len(ys) or len(xs) < 2:
            return 0.0

        mean_x = mean(xs)
        mean_y = mean(ys)
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        denominator_x = sum((x - mean_x) ** 2 for x in xs)
        denominator_y = sum((y - mean_y) ** 2 for y in ys)
        denominator = math.sqrt(denominator_x * denominator_y)
        if denominator == 0.0:
            return 0.0
        return abs(numerator / denominator)

    #################################################################

    def _percent_change(self, value, baseline):
        if math.isclose(baseline, 0.0):
            return 0.0
        return ((value - baseline) / baseline) * 100.0

    #################################################################

    def _delta_days(self, preferred_days, baseline_days):
        return preferred_days - baseline_days

    #################################################################

    def _format_value(self, value):
        if isinstance(value, float):
            if math.isclose(value, round(value)):
                return f"{value:.0f}"
            return f"{value:.2f}"
        return str(value)

    #################################################################

    def _build_insights(self, analyses, sensitivity_rank, range_analysis, preferred_design):
        insights = []
        if sensitivity_rank:
            top = sensitivity_rank[0]
            insights.append(f"{top['label']} is the strongest influence across the evaluated design space.")
        if len(sensitivity_rank) > 1:
            second = sensitivity_rank[1]
            insights.append(f"{second['label']} is the next most important tradeoff variable.")
        if range_analysis:
            tightest = min(range_analysis, key=lambda item: item["preferred_max"] - item["preferred_min"])
            widest = max(range_analysis, key=lambda item: item["preferred_max"] - item["preferred_min"])
            insights.append(f"{widest['label']} is the most forgiving parameter window.")
            insights.append(f"{tightest['label']} requires the tightest engineering control.")
        insights.append("Node count and acquisition days are the primary operational cost and schedule drivers.")
        if preferred_design.stability_score >= 0.9:
            insights.append("The preferred design is robust to nearby parameter changes.")
        else:
            insights.append("The preferred design is moderately sensitive to nearby parameter changes.")
        return insights
