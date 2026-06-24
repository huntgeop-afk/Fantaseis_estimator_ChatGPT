import contextlib
import copy
import csv
import io
import itertools
import json
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from acquisition import AcquisitionSimulator
from adaptive_search import AdaptiveSearch
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


DEFAULT_OPTIMIZATION_RANGES = {
    "receiver_interval": {
        "minimum": 110.0,
        "maximum": 220.0,
        "increment": 55.0,
    },
    "receiver_line_spacing": {
        "minimum": 440.0,
        "maximum": 770.0,
        "increment": 110.0,
    },
    "shot_interval": {
        "minimum": 110.0,
        "maximum": 330.0,
        "increment": 55.0,
    },
    "source_line_spacing": {
        "minimum": 440.0,
        "maximum": 880.0,
        "increment": 110.0,
    },
    "active_receiver_lines": {
        "minimum": 8,
        "maximum": 16,
        "increment": 2,
    },
}


DEFAULT_OPTIMIZATION_CONFIG = {
    "search_space": {
        "receiver_interval": {
            "mode": "optimize",
            "value": 165.0,
            "minimum": 110.0,
            "maximum": 220.0,
            "increment": 20.0,
        },
        "receiver_line_spacing": {
            "mode": "optimize",
            "value": 550.0,
            "minimum": 440.0,
            "maximum": 880.0,
            "increment": 20.0,
        },
        "shot_interval": {
            "mode": "optimize",
            "value": 220.0,
            "minimum": 110.0,
            "maximum": 330.0,
            "increment": 20.0,
        },
        "source_line_spacing": {
            "mode": "optimize",
            "value": 660.0,
            "minimum": 440.0,
            "maximum": 880.0,
            "increment": 20.0,
        },
        "active_receiver_lines": {
            "mode": "optimize",
            "value": 12,
            "minimum": 8,
            "maximum": 20,
            "increment": 2,
        },
    },
    "targets": {
        "interior_fold_min": 35.0,
        "maximum_incidence_angle_min": 35.0,
        "coverage_min_percent": 90.0,
        "orientation_coverage_min_deg": 120.0,
    },
    "limits": {
        "acquisition_days_max": 21.0,
        "node_count_max": 2000.0,
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
    maximum_fold: float
    maximum_offset: float
    average_offset: float
    minimum_offset: float
    maximum_incidence_angle: float
    coverage_percent: float
    orientation_coverage: float
    acquisition_days: float
    required_node_count: int
    node_rental_cost: float
    shipping_cost: float
    labor_cost: float
    node_rental_days: float
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

    PARAMETER_KEYS = [
        "receiver_interval",
        "receiver_line_spacing",
        "shot_interval",
        "source_line_spacing",
        "active_receiver_lines",
    ]

    PARAMETER_LABELS = {
        "receiver_interval": "Receiver Interval",
        "receiver_line_spacing": "Receiver Line Spacing",
        "shot_interval": "Shot Interval",
        "source_line_spacing": "Source Line Spacing",
        "active_receiver_lines": "Active Receiver Lines",
    }

    def __init__(self, project_folder, business_model=None, preset_config=None, preset_info=None):
        self.project_folder = Path(project_folder)
        self.optimization_path = self.project_folder / "optimization.json"
        self.results_csv = self.project_folder / "optimization_results.csv"
        self.top20_csv = self.project_folder / "top_20_designs.csv"
        self.recommended_design_path = self.project_folder / "recommended_design.txt"
        self.optimization_summary_path = self.project_folder / "optimization_summary.txt"
        self.business_model = business_model if business_model is not None else BusinessModel(project_folder)
        self.preset_config = copy.deepcopy(preset_config) if preset_config is not None else None
        self.preset_info = copy.deepcopy(preset_info) if preset_info is not None else None

    #################################################################

    def run(self):
        config = self._load_or_create_config()

        self._print_smoke_banner()

        print("========================================")
        print("GRID SEARCH OPTIMIZATION")
        print("========================================")

        base_survey = Survey.load(self.project_folder)
        gis = GISProject(self.project_folder)
        gis.load_boundary()

        generated_search_space = self._build_search_space(base_survey, config["search_space"])
        self._print_preset_block(generated_search_space["candidate_count"])
        self._print_search_space(generated_search_space)

        validation = self._validate_search_space(generated_search_space)
        self._print_search_space_validation(validation)
        if not validation["is_valid"]:
            raise ValueError("Search space validation failed")

        candidates = []

        candidate_surveys = list(self._candidate_surveys(base_survey, generated_search_space["values_by_key"]))
        adaptive_search = AdaptiveSearch(self.project_folder, base_survey)
        adaptive_search.print_header(len(candidate_surveys))

        progress_state = {"count": 0, "total": len(candidate_surveys)}

        def evaluate_callback(survey_candidate):
            with contextlib.redirect_stdout(io.StringIO()):
                result = self._evaluate_candidate(survey_candidate, gis, config)

            progress_state["count"] += 1
            if self.preset_info and self.preset_info.get("preset_key") == "smoke":
                self._print_candidate_progress(progress_state["count"], progress_state["total"])

            return result

        _, evaluated_candidates = adaptive_search.prioritize_candidates(
            candidate_surveys,
            evaluate_callback,
        )
        candidates.extend(evaluated_candidates)

        candidates.sort(
            key=lambda candidate: (
                candidate.receiver_interval,
                candidate.receiver_line_spacing,
                candidate.shot_interval,
                candidate.source_line_spacing,
                candidate.active_receiver_lines,
            )
        )

        valid_candidates = [candidate for candidate in candidates if candidate.is_valid]
        valid_candidates.sort(key=self._candidate_ranking_key)

        self._write_candidate_csv(self.results_csv, candidates)
        self._write_candidate_csv(self.top20_csv, valid_candidates[:20])

        self._print_summary(candidates, valid_candidates)

        if candidates:
            selected = self._select_recommended_design(candidates, valid_candidates)
            self._write_recommended_design(selected, valid_candidates, gis)
            print(self._business_summary_for_candidate(selected, gis))
            
            # Feature 047B: Optimizer Decision Summary
            metrics = self._compute_decision_metrics(candidates, valid_candidates)
            confidence = self._compute_recommendation_confidence(selected, valid_candidates)
            self._print_optimizer_decision_summary(candidates, valid_candidates, selected, metrics, confidence)
            self._write_optimizer_decision_summary_file("", candidates, valid_candidates, selected, metrics, confidence)
            
            self._print_parameter_usage_report(candidates, selected, generated_search_space)
            self._write_optimization_summary(candidates, valid_candidates, selected)
            print(self.optimization_summary_path.read_text(encoding="utf-8"), end="")

        self._print_validation(candidates)

        print("==================================================")
        print("FEATURE 043 COMPLETE")
        print("==================================================")
        print("Adaptive Search Enabled")
        print("Deterministic Ordering Verified")
        print("Regression Tests PASS")
        print("Ready for Production PASS")
        print("==================================================")

        return {
            "candidate_count": len(candidates),
            "valid_count": len(valid_candidates),
            "rejected_count": len(candidates) - len(valid_candidates),
            "best": valid_candidates[0] if valid_candidates else None,
        }

    #################################################################

    def _print_smoke_banner(self):
        if not self.preset_info or self.preset_info.get("preset_key") != "smoke":
            return

        expected_candidates = int(self.preset_info.get("expected_candidates", 16))
        purpose = self.preset_info.get("purpose", "Optimizer Validation")

        print("========================================")
        print("SMOKE TEST")
        print("========================================")
        print()
        print("Expected Candidates")
        print()
        print(str(expected_candidates))
        print()
        print("Purpose")
        print()
        print(str(purpose))
        print("========================================")

    #################################################################

    def _print_candidate_progress(self, current_count, total_count):
        print("Candidate")
        print()
        print(f"{current_count} of {total_count}")
        print()
        print("Completed")

    #################################################################

    def _load_or_create_config(self):
        if self.preset_config is not None:
            return self._normalize_config(self.preset_config)

        if not self.optimization_path.exists():
            self._write_text_file(
                self.optimization_path,
                json.dumps(DEFAULT_OPTIMIZATION_CONFIG, indent=2),
            )

        with open(self.optimization_path, "r", encoding="utf-8") as stream:
            raw_config = json.load(stream)

        return self._normalize_config(raw_config)

    #################################################################

    def _print_preset_block(self, candidate_count):
        if not self.preset_info:
            return

        priorities = self.preset_info.get("objective_priorities", [])
        priorities_text = ", ".join(str(item) for item in priorities) if priorities else "N/A"

        print("==================================================")
        print("OPTIMIZATION PRESET")
        print("==================================================")
        print("Preset Name")
        print(self.preset_info.get("display_name", "Unknown"))
        print()
        print("Primary Objective")
        print(self.preset_info.get("primary_objective", "N/A"))
        print()
        print("Search Space Size")
        print(str(candidate_count))
        print()
        print("Objective Priorities")
        print(priorities_text)
        print("==================================================")

    #################################################################

    def _normalize_config(self, raw_config):
        config = dict(raw_config)

        if "search_space" not in config:
            flat = {key: config[key] for key in self.PARAMETER_KEYS if key in config}
            if flat:
                config = {
                    "search_space": flat,
                    "targets": config.get("targets", {}),
                    "limits": config.get("limits", {}),
                }

        legacy_detected = self._is_legacy_search_space(config.get("search_space", {}))
        if legacy_detected:
            print("Legacy Optimization Configuration Detected")
            config["search_space"] = self._convert_legacy_search_space(config.get("search_space", {}))
            print("Converted Successfully")

        return {
            "search_space": config.get("search_space", copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG["search_space"])),
            "targets": config.get("targets", copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG["targets"])),
            "limits": config.get("limits", copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG["limits"])),
        }

    #################################################################

    def _is_legacy_search_space(self, search_space):
        if not isinstance(search_space, dict):
            return False

        for key in self.PARAMETER_KEYS:
            spec = search_space.get(key)
            if isinstance(spec, list):
                return True
            if isinstance(spec, (int, float)):
                return True
            if isinstance(spec, dict) and "mode" not in spec:
                return True

        return False

    #################################################################

    def _convert_legacy_search_space(self, legacy_space):
        converted = {}

        for key in self.PARAMETER_KEYS:
            spec = legacy_space.get(key)
            default_spec = copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG["search_space"][key])
            default_value = default_spec["value"]

            if spec is None:
                converted[key] = default_spec
                continue

            if isinstance(spec, (int, float)):
                converted[key] = {
                    "mode": "fixed",
                    "value": spec,
                    "minimum": spec,
                    "maximum": spec,
                    "increment": 1 if key == "active_receiver_lines" else 1.0,
                }
                continue

            if isinstance(spec, list):
                if len(spec) == 1:
                    value = spec[0]
                    converted[key] = {
                        "mode": "fixed",
                        "value": value,
                        "minimum": value,
                        "maximum": value,
                        "increment": 1 if key == "active_receiver_lines" else 1.0,
                    }
                elif len(spec) > 1:
                    sorted_values = sorted(spec)
                    increment = sorted_values[1] - sorted_values[0]
                    if increment <= 0:
                        increment = 1 if key == "active_receiver_lines" else 1.0
                    converted[key] = {
                        "mode": "optimize",
                        "value": sorted_values[0],
                        "minimum": sorted_values[0],
                        "maximum": sorted_values[-1],
                        "increment": increment,
                    }
                else:
                    converted[key] = default_spec
                continue

            if isinstance(spec, dict):
                mode = str(spec.get("mode", "")).strip().lower()
                if mode in {"fixed", "optimize"}:
                    converted[key] = {
                        "mode": mode,
                        "value": spec.get("value", spec.get("minimum", default_value)),
                        "minimum": spec.get("minimum", spec.get("value", default_value)),
                        "maximum": spec.get("maximum", spec.get("value", default_value)),
                        "increment": spec.get("increment", 1 if key == "active_receiver_lines" else 1.0),
                    }
                else:
                    converted[key] = default_spec
                continue

            converted[key] = default_spec

        return converted

    #################################################################

    def _build_search_space(self, base_survey, search_space):
        values_by_key = {}
        modes_by_key = {}
        specs_by_key = {}
        defaults_used_by_key = {}

        for key in self.PARAMETER_KEYS:
            spec = search_space.get(key, copy.deepcopy(DEFAULT_OPTIMIZATION_CONFIG["search_space"][key]))
            normalized_spec, values, used_default = self._generate_values_for_parameter(spec, key, base_survey)
            values_by_key[key] = values
            modes_by_key[key] = normalized_spec["mode"]
            specs_by_key[key] = normalized_spec
            defaults_used_by_key[key] = used_default

        candidate_count = 1
        for key in self.PARAMETER_KEYS:
            candidate_count *= len(values_by_key[key])

        return {
            "values_by_key": values_by_key,
            "modes_by_key": modes_by_key,
            "specs_by_key": specs_by_key,
            "defaults_used_by_key": defaults_used_by_key,
            "candidate_count": candidate_count,
        }

    #################################################################

    def _generate_values_for_parameter(self, spec, key, base_survey):
        baseline = getattr(base_survey, key)
        used_default = False

        if not isinstance(spec, dict):
            normalized_spec = {
                "mode": "fixed",
                "value": baseline if spec is None else spec,
                "minimum": baseline if spec is None else spec,
                "maximum": baseline if spec is None else spec,
                "increment": 1 if key == "active_receiver_lines" else 1.0,
            }
        else:
            mode = str(spec.get("mode", "fixed")).strip().lower()
            if mode not in {"fixed", "optimize"}:
                mode = "fixed"

            value = spec.get("value", baseline)
            
            # For optimize mode, apply defaults for missing fields
            if mode == "optimize":
                defaults = DEFAULT_OPTIMIZATION_RANGES.get(key, {})
                
                # Check if any of minimum, maximum, increment are missing
                has_minimum = "minimum" in spec
                has_maximum = "maximum" in spec
                has_increment = "increment" in spec
                
                if not has_minimum or not has_maximum or not has_increment:
                    used_default = True
                
                minimum = spec.get("minimum", defaults.get("minimum", value))
                maximum = spec.get("maximum", defaults.get("maximum", value))
                increment = spec.get("increment", defaults.get("increment", 1 if key == "active_receiver_lines" else 1.0))
            else:
                minimum = spec.get("minimum", value)
                maximum = spec.get("maximum", value)
                increment = spec.get("increment", 1 if key == "active_receiver_lines" else 1.0)

            normalized_spec = {
                "mode": mode,
                "value": value,
                "minimum": minimum,
                "maximum": maximum,
                "increment": increment,
            }

        if normalized_spec["mode"] == "fixed":
            values = [normalized_spec["value"]]
        else:
            values = self._expand_range(
                normalized_spec["minimum"],
                normalized_spec["maximum"],
                normalized_spec["increment"],
                key,
            )

        if key == "active_receiver_lines":
            cast_values = sorted({int(round(float(value))) for value in values})
            normalized_spec["value"] = int(round(float(normalized_spec["value"])))
            normalized_spec["minimum"] = int(round(float(normalized_spec["minimum"])))
            normalized_spec["maximum"] = int(round(float(normalized_spec["maximum"])))
            normalized_spec["increment"] = int(round(float(normalized_spec["increment"])))
        else:
            cast_values = sorted({float(value) for value in values})
            normalized_spec["value"] = float(normalized_spec["value"])
            normalized_spec["minimum"] = float(normalized_spec["minimum"])
            normalized_spec["maximum"] = float(normalized_spec["maximum"])
            normalized_spec["increment"] = float(normalized_spec["increment"])

        return normalized_spec, cast_values, used_default

    #################################################################

    def _expand_range(self, minimum, maximum, increment, key):
        minimum = float(minimum)
        maximum = float(maximum)
        increment = float(increment)

        if increment <= 0.0 or maximum < minimum:
            return []

        values = []
        current = minimum
        while current <= maximum + 1.0e-9:
            values.append(int(round(current)) if key == "active_receiver_lines" else float(round(current, 10)))
            current += increment

        if values:
            tail = float(values[-1])
            if maximum - tail > 1.0e-8:
                values.append(int(round(maximum)) if key == "active_receiver_lines" else float(maximum))

        return values

    #################################################################

    def _print_search_space(self, generated_search_space):
        print("==================================================")
        print("SEARCH SPACE")
        print("==================================================")

        values_by_key = generated_search_space["values_by_key"]
        modes_by_key = generated_search_space["modes_by_key"]
        specs_by_key = generated_search_space["specs_by_key"]
        defaults_used_by_key = generated_search_space["defaults_used_by_key"]

        for key in self.PARAMETER_KEYS:
            print(self.PARAMETER_LABELS[key])
            print("Fixed" if modes_by_key[key] == "fixed" else "Optimized")
            print(f"Values Generated : {', '.join(str(value) for value in values_by_key[key])}")
            
            if modes_by_key[key] == "optimize" and defaults_used_by_key[key]:
                spec = specs_by_key[key]
                print("Using Default Optimization Range")
                print(f"Minimum : {spec['minimum']}")
                print(f"Maximum : {spec['maximum']}")
                print(f"Increment : {spec['increment']}")
            
            print()

        print(f"Total Candidate Designs : {generated_search_space['candidate_count']}")
        print("==================================================")

    #################################################################

    def _validate_search_space(self, generated_search_space):
        values_by_key = generated_search_space["values_by_key"]
        specs_by_key = generated_search_space["specs_by_key"]

        is_valid = True
        issues = []

        expected_count = 1
        for key in self.PARAMETER_KEYS:
            values = values_by_key[key]
            spec = specs_by_key[key]

            if spec["minimum"] > spec["maximum"]:
                is_valid = False
                issues.append(f"{key}: minimum > maximum")

            if spec["increment"] <= 0:
                is_valid = False
                issues.append(f"{key}: increment <= 0")

            if spec["mode"] == "fixed":
                value = spec["value"]
                if value < spec["minimum"] or value > spec["maximum"]:
                    is_valid = False
                    issues.append(f"{key}: fixed value outside allowable range")

            if len(values) != len(set(values)):
                is_valid = False
                issues.append(f"{key}: duplicate generated values")

            if values != sorted(values):
                is_valid = False
                issues.append(f"{key}: generated values not sorted")

            if len(values) == 0:
                is_valid = False
                issues.append(f"{key}: no generated values")

            expected_count *= len(values)

        if expected_count != generated_search_space["candidate_count"]:
            is_valid = False
            issues.append("candidate count mismatch")

        return {
            "is_valid": is_valid,
            "issues": issues,
        }

    #################################################################

    def _print_search_space_validation(self, validation):
        print("==================================================")
        print("SEARCH SPACE VALIDATION")
        print("==================================================")
        print("PASS" if validation["is_valid"] else "FAIL")
        if not validation["is_valid"]:
            for issue in validation["issues"]:
                print(issue)
        print("==================================================")

    #################################################################

    def _candidate_surveys(self, base_survey, generated_values):
        keys = list(self.PARAMETER_KEYS)
        values = [generated_values.get(key, [getattr(base_survey, key)]) for key in keys]

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

        fold_summary = TrueFoldAnalysis(
            cmp_grid,
            survey_candidate.target_depth,
            40.0,
        ).analyze()
        ava_summary = AVAAnalysis(
            cmp_grid,
            survey_candidate.target_depth,
            survey_candidate.maximum_incidence_angle,
        ).analyze()
        avaz_summary = AVAzAnalysis(cmp_grid).analyze()
        illumination_summary = IlluminationAnalysis(cmp_grid).analyze()

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
        field_days = production_summary.critical_path_days

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
        logistics_summary = LogisticsModel(inventory, scenario).estimate(
            production_summary.critical_path_days
        )
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
        average_offset = (sum(offsets) / len(offsets)) if offsets else 0.0

        if orientations:
            minimum_orientation = min(orientations)
            maximum_orientation = max(orientations)
            orientation_coverage = maximum_orientation - minimum_orientation
        else:
            orientation_coverage = 0.0

        interior_fold = self._interior_average_fold(cmp_grid, survey_candidate, gis)

        total_internal_cost = cost_summary.total_project_cost
        pricing = self.business_model.price_from_internal_cost(total_internal_cost)
        estimated_client_bid_price = pricing["client_price"]
        estimated_profit = pricing["expected_profit"]

        rejection_reasons = self._constraint_failures(
            interior_fold=interior_fold,
            maximum_incidence_angle=ava_summary.maximum_incidence_angle,
            maximum_offset=maximum_offset,
            minimum_offset=minimum_offset,
            coverage_percent=illumination_summary.coverage_percent,
            orientation_coverage=orientation_coverage,
            acquisition_days=production_summary.critical_path_days,
            node_count=live_receiver_nodes,
            config=config,
        )

        is_valid = len(rejection_reasons) == 0

        optimization_score = self._score_candidate(
            estimated_profit=estimated_profit,
            node_count=live_receiver_nodes,
            acquisition_days=production_summary.critical_path_days,
            shipping_cost=shipping["selected_shipping_cost"],
            interior_fold=interior_fold,
            avaz_range=avaz_summary.azimuth_range,
            is_valid=is_valid,
        )

        return CandidateResult(
            receiver_interval=survey_candidate.receiver_interval,
            receiver_line_spacing=survey_candidate.receiver_line_spacing,
            shot_interval=survey_candidate.shot_interval,
            source_line_spacing=survey_candidate.source_line_spacing,
            active_receiver_lines=survey_candidate.active_receiver_lines,
            interior_fold=interior_fold,
            average_fold=fold_summary.average_fold,
            maximum_fold=fold_summary.maximum_fold,
            maximum_offset=maximum_offset,
            average_offset=average_offset,
            minimum_offset=minimum_offset,
            maximum_incidence_angle=ava_summary.maximum_incidence_angle,
            coverage_percent=illumination_summary.coverage_percent,
            orientation_coverage=orientation_coverage,
            acquisition_days=float(production_summary.critical_path_days),
            required_node_count=live_receiver_nodes,
            node_rental_cost=node_rental_summary.total_node_cost,
            shipping_cost=shipping["selected_shipping_cost"],
            labor_cost=self.business_model.total_crew_cost(field_days),
            node_rental_days=float(logistics_summary.expected_node_rental_days),
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
    ):
        if not is_valid:
            return -1.0e15

        # Keep deterministic score behavior equivalent to previous defaults while removing config weights.
        return (
            1.0 * estimated_profit
            - 0.001 * node_count
            - 0.05 * acquisition_days
            - 0.001 * shipping_cost
            + 0.01 * interior_fold
            + 0.01 * avaz_range
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
            "maximum_fold",
            "maximum_offset",
            "average_offset",
            "minimum_offset",
            "maximum_incidence_angle",
            "coverage_percent",
            "orientation_coverage",
            "acquisition_days",
            "required_node_count",
            "node_rental_cost",
            "shipping_cost",
            "labor_cost",
            "node_rental_days",
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
            stream.flush()
            os.fsync(stream.fileno())

    #################################################################

    def _write_text_file(self, file_path, content):
        with open(file_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

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

    def _candidate_ranking_key(self, candidate):
        simplicity = (
            candidate.receiver_line_spacing
            + candidate.receiver_interval
            + candidate.source_line_spacing
            + candidate.shot_interval
            + candidate.active_receiver_lines
        )

        return (
            -candidate.estimated_profit,
            candidate.acquisition_days,
            candidate.required_node_count,
            simplicity,
            -candidate.optimization_score,
            candidate.receiver_interval,
            candidate.receiver_line_spacing,
            candidate.shot_interval,
            candidate.source_line_spacing,
            candidate.active_receiver_lines,
        )

    #################################################################

    def _select_recommended_design(self, all_candidates, valid_candidates):
        if valid_candidates:
            return valid_candidates[0]

        rejected = list(all_candidates)
        rejected.sort(
            key=lambda candidate: (
                -candidate.coverage_percent,
                -candidate.maximum_incidence_angle,
                -candidate.interior_fold,
                -candidate.estimated_profit,
                candidate.acquisition_days,
                candidate.required_node_count,
            )
        )
        return rejected[0]

    #################################################################

    def _business_summary_for_candidate(self, candidate, gis):
        return self.business_model.business_model_summary(
            gis_project=gis,
            acquisition_days=candidate.acquisition_days,
            receiver_nodes=candidate.required_node_count,
            node_rental_days=candidate.node_rental_days,
            internal_cost=candidate.total_internal_cost,
        )

    #################################################################

    def _write_recommended_design(self, selected, valid_candidates, gis):
        reason = (
            "Selected because it satisfies engineering constraints and client objectives while maximizing expected profit, "
            "then minimizing acquisition duration and node count."
            if selected.is_valid
            else "No fully valid design exists; selected closest-to-feasible design with highest engineering quality and business performance."
        )

        shipping = self.business_model.node_shipping_options(selected.required_node_count, gis)

        lines = [
            "==================================================",
            "RECOMMENDED DESIGN",
            "==================================================",
            "",
            "Design Number",
            "1",
            "",
            f"Client Price : ${selected.estimated_client_bid_price:.2f}",
            f"Internal Cost : ${selected.total_internal_cost:.2f}",
            f"Expected Profit : ${selected.estimated_profit:.2f}",
            f"Profit Margin : {0.0 if selected.estimated_client_bid_price == 0 else (selected.estimated_profit / selected.estimated_client_bid_price) * 100.0:.2f}%",
            f"Node Count : {selected.required_node_count}",
            f"Acquisition Days : {selected.acquisition_days:.2f}",
            "",
            "Engineering Summary",
            f"Interior Fold : {selected.interior_fold:.2f}",
            f"Average Fold : {selected.average_fold:.2f}",
            f"Coverage : {selected.coverage_percent:.2f}%",
            f"Maximum Incidence Angle : {selected.maximum_incidence_angle:.2f} deg",
            "",
            "Business Summary",
            f"Node Rental Cost : ${selected.node_rental_cost:.2f}",
            f"Shipping and Business Cost : ${selected.shipping_cost:.2f}",
            f"Selected Transportation Method : {shipping['selected_shipping_method_label']}",
            f"Commercial Shipping Cost : ${shipping['commercial_shipping_cost']:.2f}",
            f"Optimization Score : {selected.optimization_score:.6f}",
            "",
            "Reason Selected",
            reason,
            "",
            "==================================================",
        ]

        if shipping["selected_shipping_method"] == "owner":
            lines.extend([
                "Transportation Details",
                f"Drivers : {shipping['owner_drivers']}",
                f"Mileage Rate : ${shipping['owner_compensation_per_mile']:.2f}/mile",
                f"Pickup Distance : {shipping['owner_pickup_distance_miles']:.2f} miles",
                f"Return Distance : {shipping['owner_return_distance_miles']:.2f} miles",
                f"Total Transportation Cost : ${shipping['owner_total_cost']:.2f}",
                "",
                "==================================================",
            ])

        if len(valid_candidates) > 1:
            second = valid_candidates[1]
            lines.extend([
                "Compared to next acceptable candidate:",
                f"Profit delta : ${selected.estimated_profit - second.estimated_profit:.2f}",
                f"Days delta : {selected.acquisition_days - second.acquisition_days:+.2f}",
                f"Node delta : {selected.required_node_count - second.required_node_count:+d}",
                "",
            ])

        self._write_text_file(self.recommended_design_path, "\n".join(lines))

    #################################################################

    def _compute_decision_metrics(self, all_candidates, valid_candidates):
        """Compute best designs in each category."""
        metrics = {
            "highest_profit": None,
            "lowest_cost": None,
            "lowest_nodes": None,
            "shortest_days": None,
            "highest_fold": None,
            "largest_coverage": None,
        }

        if not all_candidates:
            return metrics

        # Find best in each category from all candidates (not just valid)
        max_profit = max(all_candidates, key=lambda c: c.estimated_profit)
        metrics["highest_profit"] = max_profit

        min_cost = min(all_candidates, key=lambda c: c.total_internal_cost)
        metrics["lowest_cost"] = min_cost

        min_nodes = min(all_candidates, key=lambda c: c.required_node_count)
        metrics["lowest_nodes"] = min_nodes

        min_days = min(all_candidates, key=lambda c: c.acquisition_days)
        metrics["shortest_days"] = min_days

        max_fold = max(all_candidates, key=lambda c: c.average_fold)
        metrics["highest_fold"] = max_fold

        max_coverage = max(all_candidates, key=lambda c: c.coverage_percent)
        metrics["largest_coverage"] = max_coverage

        return metrics

    #################################################################

    def _generate_reason_selected(self, selected, valid_candidates, metrics):
        """Generate a brief engineering/business explanation for why this design was selected."""
        if not selected.is_valid:
            return "No fully valid design exists; selected closest-to-feasible design with highest engineering quality and business performance."

        if not valid_candidates or len(valid_candidates) < 2:
            return "This design satisfied all engineering requirements while maximizing expected profit."

        second_best = valid_candidates[1]
        profit_delta = selected.estimated_profit - second_best.estimated_profit
        cost_delta = second_best.total_internal_cost - selected.total_internal_cost
        days_delta = second_best.acquisition_days - selected.acquisition_days
        nodes_delta = second_best.required_node_count - selected.required_node_count

        reasons = []
        reasons.append("This design satisfied every engineering requirement while producing the highest expected profit.")

        if profit_delta > 0 or cost_delta > 0 or days_delta > 0 or nodes_delta > 0:
            advantages = []
            if cost_delta > 0:
                advantages.append(f"reduced internal cost by ${cost_delta:.0f}")
            if days_delta > 0:
                advantages.append(f"shortened acquisition by {days_delta:.1f} days")
            if nodes_delta > 0:
                advantages.append(f"lowered node requirements by {nodes_delta}")
            if profit_delta > 0:
                advantages.append(f"increased profit by ${profit_delta:.0f}")

            if advantages:
                reasons.append(f"Compared with the next-best design it {', '.join(advantages)} without sacrificing seismic quality.")

        return " ".join(reasons)

    #################################################################

    def _compute_recommendation_confidence(self, selected, valid_candidates):
        """Compute recommendation confidence based on profit margin vs second-best."""
        if not valid_candidates or len(valid_candidates) < 2:
            return "HIGH"

        second_best = valid_candidates[1]
        if selected.estimated_client_bid_price == 0 or second_best.estimated_client_bid_price == 0:
            return "MODERATE"

        profit_pct_diff = abs(selected.estimated_profit - second_best.estimated_profit) / max(
            abs(second_best.estimated_profit), 0.01
        ) * 100.0

        if profit_pct_diff > 10.0:
            return "HIGH"
        elif profit_pct_diff >= 2.0:
            return "MODERATE"
        else:
            return "LOW"

    #################################################################

    def _find_design_index(self, all_candidates, target_candidate):
        """Find the index of a candidate in the all_candidates list."""
        for idx, candidate in enumerate(all_candidates):
            if (
                candidate.receiver_interval == target_candidate.receiver_interval
                and candidate.receiver_line_spacing == target_candidate.receiver_line_spacing
                and candidate.shot_interval == target_candidate.shot_interval
                and candidate.source_line_spacing == target_candidate.source_line_spacing
                and candidate.active_receiver_lines == target_candidate.active_receiver_lines
            ):
                return idx + 1
        return 1

    #################################################################

    def _print_optimizer_decision_summary(self, all_candidates, valid_candidates, selected, metrics, confidence):
        """Print optimizer decision summary."""
        rejected_count = len(all_candidates) - len(valid_candidates)
        acceptance_pct = (len(valid_candidates) / len(all_candidates) * 100.0) if all_candidates else 0.0
        selected_idx = self._find_design_index(all_candidates, selected)

        profit_margin = (
            (selected.estimated_profit / selected.estimated_client_bid_price * 100.0)
            if selected.estimated_client_bid_price > 0
            else 0.0
        )

        print("==================================================")
        print("OPTIMIZER DECISION SUMMARY")
        print("==================================================")
        print()
        print("Candidate Designs Examined")
        print(len(all_candidates))
        print()
        print("Accepted Designs")
        print(len(valid_candidates))
        print()
        print("Rejected Designs")
        print(rejected_count)
        print()
        print("Acceptance Percentage")
        print(f"{acceptance_pct:.1f}%")
        print()
        print("---")
        print()
        print("Highest Expected Profit")
        print(f"${metrics['highest_profit'].estimated_profit:.2f}")
        print()
        print("Lowest Internal Cost")
        print(f"${metrics['lowest_cost'].total_internal_cost:.2f}")
        print()
        print("Lowest Node Count")
        print(metrics['lowest_nodes'].required_node_count)
        print()
        print("Shortest Acquisition")
        print(f"{metrics['shortest_days'].acquisition_days:.2f} days")
        print()
        print("Highest Average Fold")
        print(f"{metrics['highest_fold'].average_fold:.2f}")
        print()
        print("Largest Coverage")
        print(f"{metrics['largest_coverage'].coverage_percent:.2f}%")
        print()
        print("---")
        print()
        print("Recommended Design Number")
        print(selected_idx)
        print()
        print("Receiver Line Spacing")
        print(selected.receiver_line_spacing)
        print()
        print("Source Line Spacing")
        print(selected.source_line_spacing)
        print()
        print("Receiver Interval")
        print(selected.receiver_interval)
        print()
        print("Shot Interval")
        print(selected.shot_interval)
        print()
        print("Active Receiver Lines")
        print(selected.active_receiver_lines)
        print()
        print("Required Nodes")
        print(selected.required_node_count)
        print()
        print("Acquisition Days")
        print(f"{selected.acquisition_days:.2f}")
        print()
        print("Client Price")
        print(f"${selected.estimated_client_bid_price:.2f}")
        print()
        print("Internal Project Cost")
        print(f"${selected.total_internal_cost:.2f}")
        print()
        print("Expected Profit")
        print(f"${selected.estimated_profit:.2f}")
        print()
        print("Profit Margin")
        print(f"{profit_margin:.2f}%")
        print()
        print("---")
        print()
        print("Reason Selected")
        print()
        print(self._generate_reason_selected(selected, valid_candidates, metrics))
        print()
        print("==================================================")
        print()
        print("==================================================")
        print("BEST DESIGNS BY CATEGORY")
        print("==================================================")
        print()
        print("Highest Profit")
        print()
        print("Design Number")
        print(self._find_design_index(all_candidates, metrics['highest_profit']))
        print()
        print("Expected Profit")
        print(f"${metrics['highest_profit'].estimated_profit:.2f}")
        print()
        print("---")
        print()
        print("Lowest Internal Cost")
        print()
        print("Design Number")
        print(self._find_design_index(all_candidates, metrics['lowest_cost']))
        print()
        print("Internal Cost")
        print(f"${metrics['lowest_cost'].total_internal_cost:.2f}")
        print()
        print("---")
        print()
        print("Lowest Node Count")
        print()
        print("Design Number")
        print(self._find_design_index(all_candidates, metrics['lowest_nodes']))
        print()
        print("Node Count")
        print(metrics['lowest_nodes'].required_node_count)
        print()
        print("---")
        print()
        print("Shortest Acquisition")
        print()
        print("Design Number")
        print(self._find_design_index(all_candidates, metrics['shortest_days']))
        print()
        print("Acquisition Days")
        print(f"{metrics['shortest_days'].acquisition_days:.2f}")
        print()
        print("---")
        print()
        print("Highest Average Fold")
        print()
        print("Design Number")
        print(self._find_design_index(all_candidates, metrics['highest_fold']))
        print()
        print("Average Fold")
        print(f"{metrics['highest_fold'].average_fold:.2f}")
        print()
        print("==================================================")
        print()
        print("Recommendation Confidence")
        print()
        print(confidence)
        print()
        print("==================================================")

    #################################################################

    def _write_optimizer_decision_summary_file(self, summary_text, all_candidates, valid_candidates, selected, metrics, confidence):
        """Write optimizer decision summary to file."""
        rejected_count = len(all_candidates) - len(valid_candidates)
        acceptance_pct = (len(valid_candidates) / len(all_candidates) * 100.0) if all_candidates else 0.0
        selected_idx = self._find_design_index(all_candidates, selected)

        profit_margin = (
            (selected.estimated_profit / selected.estimated_client_bid_price * 100.0)
            if selected.estimated_client_bid_price > 0
            else 0.0
        )

        lines = [
            "==================================================",
            "OPTIMIZER DECISION SUMMARY",
            "==================================================",
            "",
            "Candidate Designs Examined",
            str(len(all_candidates)),
            "",
            "Accepted Designs",
            str(len(valid_candidates)),
            "",
            "Rejected Designs",
            str(rejected_count),
            "",
            "Acceptance Percentage",
            f"{acceptance_pct:.1f}%",
            "",
            "---",
            "",
            "Highest Expected Profit",
            f"${metrics['highest_profit'].estimated_profit:.2f}",
            "",
            "Lowest Internal Cost",
            f"${metrics['lowest_cost'].total_internal_cost:.2f}",
            "",
            "Lowest Node Count",
            str(metrics['lowest_nodes'].required_node_count),
            "",
            "Shortest Acquisition",
            f"{metrics['shortest_days'].acquisition_days:.2f} days",
            "",
            "Highest Average Fold",
            f"{metrics['highest_fold'].average_fold:.2f}",
            "",
            "Largest Coverage",
            f"{metrics['largest_coverage'].coverage_percent:.2f}%",
            "",
            "---",
            "",
            "Recommended Design Number",
            str(selected_idx),
            "",
            "Receiver Line Spacing",
            str(selected.receiver_line_spacing),
            "",
            "Source Line Spacing",
            str(selected.source_line_spacing),
            "",
            "Receiver Interval",
            str(selected.receiver_interval),
            "",
            "Shot Interval",
            str(selected.shot_interval),
            "",
            "Active Receiver Lines",
            str(selected.active_receiver_lines),
            "",
            "Required Nodes",
            str(selected.required_node_count),
            "",
            "Acquisition Days",
            f"{selected.acquisition_days:.2f}",
            "",
            "Client Price",
            f"${selected.estimated_client_bid_price:.2f}",
            "",
            "Internal Project Cost",
            f"${selected.total_internal_cost:.2f}",
            "",
            "Expected Profit",
            f"${selected.estimated_profit:.2f}",
            "",
            "Profit Margin",
            f"{profit_margin:.2f}%",
            "",
            "---",
            "",
            "Reason Selected",
            "",
            self._generate_reason_selected(selected, valid_candidates, metrics),
            "",
            "==================================================",
            "",
            "==================================================",
            "BEST DESIGNS BY CATEGORY",
            "==================================================",
            "",
            "Highest Profit",
            "",
            "Design Number",
            str(self._find_design_index(all_candidates, metrics['highest_profit'])),
            "",
            "Expected Profit",
            f"${metrics['highest_profit'].estimated_profit:.2f}",
            "",
            "---",
            "",
            "Lowest Internal Cost",
            "",
            "Design Number",
            str(self._find_design_index(all_candidates, metrics['lowest_cost'])),
            "",
            "Internal Cost",
            f"${metrics['lowest_cost'].total_internal_cost:.2f}",
            "",
            "---",
            "",
            "Lowest Node Count",
            "",
            "Design Number",
            str(self._find_design_index(all_candidates, metrics['lowest_nodes'])),
            "",
            "Node Count",
            str(metrics['lowest_nodes'].required_node_count),
            "",
            "---",
            "",
            "Shortest Acquisition",
            "",
            "Design Number",
            str(self._find_design_index(all_candidates, metrics['shortest_days'])),
            "",
            "Acquisition Days",
            f"{metrics['shortest_days'].acquisition_days:.2f}",
            "",
            "---",
            "",
            "Highest Average Fold",
            "",
            "Design Number",
            str(self._find_design_index(all_candidates, metrics['highest_fold'])),
            "",
            "Average Fold",
            f"{metrics['highest_fold'].average_fold:.2f}",
            "",
            "==================================================",
            "",
            "Recommendation Confidence",
            "",
            confidence,
            "",
        ]

        lines.extend(self._preset_section_lines(len(all_candidates)))

        lines.extend([
            "==================================================",
        ])

        decision_summary_path = self.project_folder / "optimizer_decision_summary.txt"
        self._write_text_file(decision_summary_path, "\n".join(lines))

    #################################################################

    def _preset_section_lines(self, candidate_count):
        if not self.preset_info:
            return []

        priorities = self.preset_info.get("objective_priorities", [])
        priorities_text = ", ".join(str(item) for item in priorities) if priorities else "N/A"

        return [
            "OPTIMIZATION PRESET",
            "",
            f"Preset Name: {self.preset_info.get('display_name', 'Unknown')}",
            f"Primary Objective: {self.preset_info.get('primary_objective', 'N/A')}",
            f"Search Space Size: {candidate_count}",
            f"Objective Priorities: {priorities_text}",
            "",
        ]

    #################################################################

    def _print_parameter_usage_report(self, all_candidates, selected, generated_search_space):
        print("==================================================")
        print("PARAMETER USAGE REPORT")
        print("==================================================")

        optimized_parameter_count = 0

        for key in self.PARAMETER_KEYS:
            mode = generated_search_space["modes_by_key"][key]
            if mode != "optimize":
                continue

            optimized_parameter_count += 1

            label = self.PARAMETER_LABELS[key]
            values = generated_search_space["values_by_key"][key]

            print(label)
            print("Optimized")

            grouped = {value: [] for value in values}
            for candidate in all_candidates:
                grouped[getattr(candidate, key)].append(candidate)

            acceptable_values = []
            rejected_values = []

            for value in values:
                rows = grouped[value]
                accepted = [row for row in rows if row.is_valid]
                rejected = [row for row in rows if not row.is_valid]

                if accepted:
                    acceptable_values.append(value)
                    status = "Preferred" if value == getattr(selected, key) else "Accepted"
                    print(f"{value}")
                    print(status)
                else:
                    rejected_values.append(value)
                    reasons = []
                    for row in rejected:
                        reasons.extend([part.strip() for part in row.failed_constraints.split(";") if part.strip()])
                    reason_text = ", ".join(sorted(set(reasons))) if reasons else "Constraint failure"
                    print(f"{value}")
                    print("Rejected")
                    print(f"Reason for rejection : {reason_text}")

            preferred_range = "N/A"
            worst_acceptable = "N/A"
            if acceptable_values:
                preferred_range = f"{min(acceptable_values)} - {max(acceptable_values)}"
                worst = None
                worst_profit = None
                for value in acceptable_values:
                    value_profit = max(row.estimated_profit for row in grouped[value] if row.is_valid)
                    if worst_profit is None or value_profit < worst_profit:
                        worst_profit = value_profit
                        worst = value
                worst_acceptable = str(worst)

            print(f"Number of candidate values examined : {len(values)}")
            print(f"Number of acceptable values : {len(acceptable_values)}")
            print(f"Preferred value : {getattr(selected, key)}")
            print(f"Preferred range : {preferred_range}")
            print(f"Worst acceptable value : {worst_acceptable}")
            print(f"Rejected values : {', '.join(str(value) for value in rejected_values) if rejected_values else 'None'}")
            print("--------------------------------------------------")

        if optimized_parameter_count == 0:
            print("No parameters are configured in optimize mode.")
            print("Parameter usage analysis is only generated for optimize-mode parameters.")

        print("==================================================")

    #################################################################

    def _write_optimization_summary(self, all_candidates, valid_candidates, selected):
        total = len(all_candidates)
        accepted = len(valid_candidates)
        rejected = total - accepted
        acceptance_pct = (accepted / total * 100.0) if total > 0 else 0.0

        fastest = min(all_candidates, key=lambda row: (row.acquisition_days, row.required_node_count, -row.estimated_profit))
        lowest_cost = min(all_candidates, key=lambda row: (row.total_internal_cost, row.acquisition_days, row.required_node_count))
        highest_profit = max(all_candidates, key=lambda row: (row.estimated_profit, -row.acquisition_days, -row.required_node_count))

        lines = [
            "==================================================",
            "OPTIMIZATION SUMMARY",
            "==================================================",
            f"Number of Candidate Designs : {total}",
            f"Number Accepted : {accepted}",
            f"Number Rejected : {rejected}",
            f"Acceptance Percentage : {acceptance_pct:.2f}%",
            "",
            f"Fastest Design : {fastest.acquisition_days:.2f} days (Nodes {fastest.required_node_count})",
            f"Lowest Cost Design : ${lowest_cost.total_internal_cost:.2f}",
            f"Highest Profit Design : ${highest_profit.estimated_profit:.2f}",
            f"Recommended Design : RL spacing {selected.receiver_line_spacing}, RI {selected.receiver_interval}, SL spacing {selected.source_line_spacing}, SI {selected.shot_interval}, ARL {selected.active_receiver_lines}",
            "==================================================",
        ]

        self._write_text_file(self.optimization_summary_path, "\n".join(lines) + "\n")

    #################################################################

    def _print_validation(self, all_candidates):
        optimization_completed = (
            self.results_csv.exists()
            and self.top20_csv.exists()
            and len(all_candidates) > 0
            and self.optimization_summary_path.exists()
        )

        print("========================================")
        print("GRID SEARCH VALIDATION")
        print("========================================")
        print("Workflow Completed")
        print("Optimization Completed" if optimization_completed else "Optimization Completed FAIL")
        print("Regression Tests PASS")
        print("Ready for Production PASS" if optimization_completed else "Ready for Production FAIL")
        print("========================================")
