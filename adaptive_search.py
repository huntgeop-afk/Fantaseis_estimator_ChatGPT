import csv
import json
import math
from collections import defaultdict
from pathlib import Path


class AdaptiveSearch:
    """Deterministically reorders exhaustive candidates using diagnostics and running influence stats."""

    VARIABLE_KEYS = [
        "receiver_interval",
        "receiver_line_spacing",
        "shot_interval",
        "source_line_spacing",
        "active_receiver_lines",
    ]

    METRIC_KEYS = [
        "interior_fold",
        "maximum_offset",
        "maximum_incidence_angle",
        "coverage_percent",
        "required_node_count",
        "acquisition_days",
    ]

    DRIVER_TO_TARGET_METRIC = {
        "Interior Fold": "interior_fold",
        "Node Count": "required_node_count",
        "Acquisition Days": "acquisition_days",
        "AVA Angle": "maximum_incidence_angle",
        "Coverage": "coverage_percent",
        "Maximum Offset": "maximum_offset",
        "Minimum Offset": "maximum_offset",
        "Orientation Coverage": "coverage_percent",
        "Client-defined constraints": "interior_fold",
        "None": "interior_fold",
    }

    DRIVER_PRIORITY_WEIGHTS = {
        "Interior Fold": {
            "active_receiver_lines": 6.0,
            "receiver_line_spacing": 5.0,
            "source_line_spacing": 4.0,
            "receiver_interval": 1.0,
            "shot_interval": 1.0,
        },
        "Node Count": {
            "receiver_interval": 6.0,
            "receiver_line_spacing": 5.0,
            "active_receiver_lines": 2.0,
            "shot_interval": 1.0,
            "source_line_spacing": 1.0,
        },
        "Acquisition Days": {
            "shot_interval": 6.0,
            "receiver_interval": 5.0,
            "receiver_line_spacing": 2.0,
            "source_line_spacing": 1.0,
            "active_receiver_lines": 1.0,
        },
        "AVA Angle": {
            "shot_interval": 6.0,
            "receiver_interval": 5.0,
            "receiver_line_spacing": 4.0,
            "source_line_spacing": 1.0,
            "active_receiver_lines": 1.0,
        },
        "Coverage": {
            "active_receiver_lines": 5.0,
            "receiver_line_spacing": 4.0,
            "shot_interval": 3.0,
            "source_line_spacing": 2.0,
            "receiver_interval": 2.0,
        },
        "Maximum Offset": {
            "receiver_line_spacing": 4.0,
            "source_line_spacing": 4.0,
            "active_receiver_lines": 3.0,
            "receiver_interval": 2.0,
            "shot_interval": 2.0,
        },
        "Minimum Offset": {
            "receiver_line_spacing": 4.0,
            "source_line_spacing": 4.0,
            "active_receiver_lines": 3.0,
            "receiver_interval": 2.0,
            "shot_interval": 2.0,
        },
        "Orientation Coverage": {
            "source_line_spacing": 4.0,
            "shot_interval": 3.0,
            "receiver_line_spacing": 3.0,
            "receiver_interval": 2.0,
            "active_receiver_lines": 2.0,
        },
        "Client-defined constraints": {
            "receiver_interval": 1.0,
            "receiver_line_spacing": 1.0,
            "shot_interval": 1.0,
            "source_line_spacing": 1.0,
            "active_receiver_lines": 1.0,
        },
        "None": {
            "receiver_interval": 1.0,
            "receiver_line_spacing": 1.0,
            "shot_interval": 1.0,
            "source_line_spacing": 1.0,
            "active_receiver_lines": 1.0,
        },
    }

    def __init__(self, project_folder, base_survey):
        self.project_folder = Path(project_folder)
        self.base_survey = base_survey
        self.optimization_path = self.project_folder / "optimization.json"
        self.failure_summary_path = self.project_folder / "optimization_failure_summary.csv"
        self.diagnostics_path = self.project_folder / "optimization_diagnostics.txt"

        self.search_space = self._load_search_space()
        self.primary_failure_driver = self._load_primary_failure_driver()

        self.variable_ranges = self._variable_ranges()
        self.rule_weights = self.DRIVER_PRIORITY_WEIGHTS.get(
            self.primary_failure_driver,
            self.DRIVER_PRIORITY_WEIGHTS["None"],
        )

        self.metric_target = self.DRIVER_TO_TARGET_METRIC.get(self.primary_failure_driver, "interior_fold")

        self._stats = {
            variable: {
                metric: {
                    "n": 0,
                    "sum_x": 0.0,
                    "sum_x2": 0.0,
                    "sum_y": 0.0,
                    "sum_y2": 0.0,
                    "sum_xy": 0.0,
                }
                for metric in self.METRIC_KEYS
            }
            for variable in self.VARIABLE_KEYS
        }

    #################################################################

    def print_header(self, candidate_count):
        print("==================================================")
        print("ADAPTIVE SEARCH")
        print("==================================================")
        print(f"Total Candidates         : {candidate_count}")
        print("Priority Model Built")
        print(f"Primary Failure Driver   : {self.primary_failure_driver}")
        print("Search Order Optimized")

    #################################################################

    def prioritize_candidates(self, candidates, evaluate_callback):
        queue = list(range(len(candidates)))
        evaluation_order = []
        evaluated_results = []
        average_priority_accumulator = 0.0
        evaluated_count = 0
        metrics_by_index = {}

        while queue:
            scored = self._score_remaining_queue(candidates, queue)
            queue = [index for index, _ in scored]

            selected_index, selected_priority = scored[0]
            queue.pop(0)

            result = evaluate_callback(candidates[selected_index])
            metrics_by_index[selected_index] = self._extract_metrics(result)

            self._update_running_statistics(candidates[selected_index], result)

            evaluation_order.append(selected_index)
            evaluated_results.append(result)
            average_priority_accumulator += selected_priority
            evaluated_count += 1

        average_priority = average_priority_accumulator / evaluated_count if evaluated_count else 0.0
        print(f"Average Candidate Priority: {average_priority:.4f}")
        print("==================================================")

        deterministic_ok = self._verify_deterministic_order(candidates, evaluation_order, metrics_by_index)
        self._print_validation(len(candidates), len(evaluation_order), deterministic_ok)

        return evaluation_order, evaluated_results

    #################################################################

    def _score_remaining_queue(self, candidates, queue):
        scored = []
        influence_weights = self._metric_influence_weights(self.metric_target)

        for index in queue:
            candidate = candidates[index]
            score = 0.0

            for variable in self.VARIABLE_KEYS:
                delta = self._normalized_delta(candidate, variable)
                rule_weight = float(self.rule_weights.get(variable, 1.0))
                influence = float(influence_weights.get(variable, 0.0))

                score += delta * (rule_weight * 100.0 + influence)

            scored.append((index, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

    #################################################################

    def _update_running_statistics(self, candidate, result):
        metrics = self._extract_metrics(result)

        for variable in self.VARIABLE_KEYS:
            x_value = float(getattr(candidate, variable))

            for metric in self.METRIC_KEYS:
                y_value = float(metrics[metric])
                bucket = self._stats[variable][metric]

                bucket["n"] += 1
                bucket["sum_x"] += x_value
                bucket["sum_x2"] += x_value * x_value
                bucket["sum_y"] += y_value
                bucket["sum_y2"] += y_value * y_value
                bucket["sum_xy"] += x_value * y_value

    #################################################################

    def _metric_influence_weights(self, metric_key):
        weights = {}

        for variable in self.VARIABLE_KEYS:
            bucket = self._stats[variable][metric_key]
            n_value = bucket["n"]
            if n_value < 2:
                weights[variable] = 0.0
                continue

            denominator_x = n_value * bucket["sum_x2"] - bucket["sum_x"] * bucket["sum_x"]
            denominator_y = n_value * bucket["sum_y2"] - bucket["sum_y"] * bucket["sum_y"]
            if denominator_x <= 0.0 or denominator_y <= 0.0:
                weights[variable] = 0.0
                continue

            numerator = n_value * bucket["sum_xy"] - bucket["sum_x"] * bucket["sum_y"]
            correlation = abs(numerator / (denominator_x * denominator_y) ** 0.5)
            weights[variable] = correlation * 100.0

        return weights

    #################################################################

    def _extract_metrics(self, result):
        return {
            "interior_fold": float(result.interior_fold),
            "maximum_offset": float(result.maximum_offset),
            "maximum_incidence_angle": float(result.maximum_incidence_angle),
            "coverage_percent": float(result.coverage_percent),
            "required_node_count": float(result.required_node_count),
            "acquisition_days": float(result.acquisition_days),
        }

    #################################################################

    def _normalized_delta(self, candidate, variable):
        candidate_value = float(getattr(candidate, variable))
        base_value = float(getattr(self.base_survey, variable))
        value_range = self.variable_ranges.get(variable, 1.0)

        if value_range <= 0.0:
            return 0.0

        return abs(candidate_value - base_value) / value_range

    #################################################################

    def _variable_ranges(self):
        ranges = {}
        for key in self.VARIABLE_KEYS:
            values = self._values_for_key(key)
            if not values:
                ranges[key] = 1.0
                continue

            value_range = max(values) - min(values)
            ranges[key] = value_range if value_range > 0.0 else 1.0

        return ranges

    #################################################################

    def _values_for_key(self, key):
        spec = self.search_space.get(key)

        if spec is None:
            return [float(getattr(self.base_survey, key))]

        if isinstance(spec, list):
            return [float(value) for value in spec]

        if isinstance(spec, (int, float)):
            return [float(spec)]

        if isinstance(spec, dict):
            mode = str(spec.get("mode", "fixed")).strip().lower()

            if mode == "fixed":
                value = spec.get("value", getattr(self.base_survey, key))
                return [float(value)]

            minimum = float(spec.get("minimum", getattr(self.base_survey, key)))
            maximum = float(spec.get("maximum", getattr(self.base_survey, key)))
            increment = float(spec.get("increment", 1.0))

            if increment <= 0.0 or maximum < minimum:
                return [float(getattr(self.base_survey, key))]

            values = []
            current = minimum
            while current <= maximum + 1.0e-9:
                values.append(float(round(current, 10)))
                current += increment

            if values and maximum - values[-1] > 1.0e-8:
                values.append(float(maximum))

            if not values:
                values = [float(getattr(self.base_survey, key))]

            return values

        return [float(getattr(self.base_survey, key))]

    #################################################################

    def _load_search_space(self):
        if not self.optimization_path.exists():
            return {}

        with open(self.optimization_path, "r", encoding="utf-8") as stream:
            config = json.load(stream)

        if "search_space" in config:
            return dict(config.get("search_space", {}))

        return {
            key: config[key]
            for key in self.VARIABLE_KEYS
            if key in config
        }

    #################################################################

    def _load_primary_failure_driver(self):
        counts = self._read_failure_summary_counts()
        if counts:
            filtered = [
                (name, count)
                for name, count in counts.items()
                if name not in {"Multiple Constraints", "Client-defined constraints"}
            ]
            filtered = [item for item in filtered if item[1] > 0]
            if filtered:
                filtered.sort(key=lambda item: item[1], reverse=True)
                return filtered[0][0]

        parsed = self._parse_driver_from_diagnostics_txt()
        if parsed:
            return parsed

        return "None"

    #################################################################

    def _read_failure_summary_counts(self):
        if not self.failure_summary_path.exists():
            return {}

        counts = {}
        with open(self.failure_summary_path, "r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                name = str(row.get("Constraint", "")).strip()
                count_text = str(row.get("FailureCount", "0")).strip()
                if not name:
                    continue
                try:
                    counts[name] = int(float(count_text))
                except ValueError:
                    counts[name] = 0

        return counts

    #################################################################

    def _parse_driver_from_diagnostics_txt(self):
        if not self.diagnostics_path.exists():
            return ""

        text = self.diagnostics_path.read_text(encoding="utf-8", errors="ignore")
        marker = "Most Limiting Constraint"
        index = text.find(marker)
        if index < 0:
            return ""

        tail = text[index + len(marker):].splitlines()
        for line in tail:
            value = line.strip()
            if not value:
                continue
            if value.startswith("=") or value.startswith("-"):
                continue
            return value

        return ""

    #################################################################

    def _verify_deterministic_order(self, candidates, evaluation_order, metrics_by_index):
        replay = list(range(len(candidates)))
        replay_stats = self._empty_stats()
        replay_order = []

        while replay:
            influence_weights = self._metric_influence_weights_with_stats(self.metric_target, replay_stats)

            scored = []
            for index in replay:
                candidate = candidates[index]
                score = 0.0
                for variable in self.VARIABLE_KEYS:
                    delta = self._normalized_delta(candidate, variable)
                    rule_weight = float(self.rule_weights.get(variable, 1.0))
                    influence = float(influence_weights.get(variable, 0.0))
                    score += delta * (rule_weight * 100.0 + influence)
                scored.append((index, score))

            scored.sort(key=lambda item: item[1], reverse=True)
            selected_index, _ = scored[0]
            replay.remove(selected_index)
            replay_order.append(selected_index)

            metrics = metrics_by_index.get(selected_index)
            if metrics is None:
                return False

            self._update_stats_for_replay(replay_stats, candidates[selected_index], metrics)

        return replay_order == evaluation_order

    #################################################################

    def _empty_stats(self):
        return {
            variable: {
                metric: {
                    "n": 0,
                    "sum_x": 0.0,
                    "sum_x2": 0.0,
                    "sum_y": 0.0,
                    "sum_y2": 0.0,
                    "sum_xy": 0.0,
                }
                for metric in self.METRIC_KEYS
            }
            for variable in self.VARIABLE_KEYS
        }

    #################################################################

    def _metric_influence_weights_with_stats(self, metric_key, stats):
        weights = {}

        for variable in self.VARIABLE_KEYS:
            bucket = stats[variable][metric_key]
            n_value = bucket["n"]
            if n_value < 2:
                weights[variable] = 0.0
                continue

            denominator_x = n_value * bucket["sum_x2"] - bucket["sum_x"] * bucket["sum_x"]
            denominator_y = n_value * bucket["sum_y2"] - bucket["sum_y"] * bucket["sum_y"]
            if denominator_x <= 0.0 or denominator_y <= 0.0:
                weights[variable] = 0.0
                continue

            numerator = n_value * bucket["sum_xy"] - bucket["sum_x"] * bucket["sum_y"]
            correlation = abs(numerator / (denominator_x * denominator_y) ** 0.5)
            weights[variable] = correlation * 100.0

        return weights

    #################################################################

    def _update_stats_for_replay(self, stats, candidate, metrics):
        for variable in self.VARIABLE_KEYS:
            x_value = float(getattr(candidate, variable))
            for metric in self.METRIC_KEYS:
                y_value = float(metrics[metric])
                bucket = stats[variable][metric]
                bucket["n"] += 1
                bucket["sum_x"] += x_value
                bucket["sum_x2"] += x_value * x_value
                bucket["sum_y"] += y_value
                bucket["sum_y2"] += y_value * y_value
                bucket["sum_xy"] += x_value * y_value

    #################################################################

    def _print_validation(self, before_count, after_count, deterministic_ok):
        difference = before_count - after_count
        all_evaluated_ok = before_count == after_count and after_count >= 0

        print("==================================================")
        print("ADAPTIVE SEARCH VALIDATION")
        print("==================================================")
        print(f"Candidate Count Before Sorting : {before_count}")
        print(f"Candidate Count After Sorting  : {after_count}")
        print(f"Difference                     : {difference}")
        print("PASS if identical" if difference == 0 else "PASS if identical FAIL")
        print("PASS if every candidate evaluated" if all_evaluated_ok else "PASS if every candidate evaluated FAIL")
        print("PASS if deterministic ordering verified" if deterministic_ok else "PASS if deterministic ordering verified FAIL")
        print("==================================================")
