import copy
import json
from pathlib import Path


DEFAULT_CONFIG = {
    "search_space": {
        "receiver_interval": {
            "mode": "optimize",
            "value": 165.0,
            "minimum": 110.0,
            "maximum": 220.0,
            "increment": 55.0,
        },
        "receiver_line_spacing": {
            "mode": "optimize",
            "value": 550.0,
            "minimum": 220.0,
            "maximum": 660.0,
            "increment": 55.0,
        },
        "shot_interval": {
            "mode": "optimize",
            "value": 220.0,
            "minimum": 110.0,
            "maximum": 330.0,
            "increment": 55.0,
        },
        "source_line_spacing": {
            "mode": "optimize",
            "value": 660.0,
            "minimum": 440.0,
            "maximum": 880.0,
            "increment": 55.0,
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


class OptimizationPresetManager:
    """Creates in-memory optimization configurations for predefined engineering presets."""

    PRESET_DEFINITIONS = {
        "smoke": {
            "display_name": "Smoke Test",
            "primary_objective": "Balanced Engineering",
            "philosophy": "Validation-Only Deterministic Run",
            "reason": "Exercises the full optimization workflow with a deliberately tiny, fixed search space for software validation.",
            "objective_priorities": [
                "Profit",
                "Acquisition Days",
                "Node Count",
                "Shipping Cost",
            ],
            "expected_candidates": 16,
            "purpose": "Optimizer Validation",
        },
        "conservative": {
            "display_name": "Conservative",
            "primary_objective": "Lower-Risk Engineering Compliance",
            "philosophy": "Conservative Engineering",
            "reason": "Prioritizes low-risk, tight-variation designs that satisfy constraints with minimal schedule and logistics volatility.",
            "objective_priorities": [
                "Engineering Compliance",
                "Acquisition Days",
                "Node Count",
                "Shipping Cost",
            ],
        },
        "balanced": {
            "display_name": "Balanced",
            "primary_objective": "Balanced Engineering",
            "philosophy": "Balanced Engineering",
            "reason": "Balances profitability, logistics, and seismic quality while satisfying all client constraints.",
            "objective_priorities": [
                "Profit",
                "Acquisition Days",
                "Node Count",
                "Shipping Cost",
            ],
        },
        "profit": {
            "display_name": "Maximum Profit",
            "primary_objective": "Maximum Expected Profit",
            "philosophy": "Profit-First within Constraints",
            "reason": "Prioritizes profit maximization while retaining all engineering guardrails as mandatory constraints.",
            "objective_priorities": [
                "Profit",
                "Acquisition Cost",
                "Acquisition Days",
                "Node Count",
            ],
        },
        "nodes": {
            "display_name": "Minimum Nodes",
            "primary_objective": "Minimum Live Node Inventory",
            "philosophy": "Logistics-Light Node Strategy",
            "reason": "Prioritizes smaller live-node footprints to reduce deployment burden, shipping exposure, and node rental pressure.",
            "objective_priorities": [
                "Node Count",
                "Shipping Cost",
                "Node Rental Cost",
                "Profit",
            ],
        },
        "fast": {
            "display_name": "Fast Acquisition",
            "primary_objective": "Fewest Acquisition Days",
            "philosophy": "Schedule-First Engineering",
            "reason": "Prioritizes schedule compression while preserving client engineering requirements.",
            "objective_priorities": [
                "Acquisition Days",
                "Profit",
                "Node Count",
                "Shipping Cost",
            ],
        },
        "quality": {
            "display_name": "Premium Data Quality",
            "primary_objective": "Maximum Data Quality",
            "philosophy": "Quality-First Seismic Imaging",
            "reason": "Prioritizes fold, AVA margin, AVAz coverage, and illumination robustness while still tracking business outcomes.",
            "objective_priorities": [
                "Interior Fold",
                "AVA Margin",
                "AVAz Coverage",
                "Survey Coverage",
                "Profit",
            ],
        },
        "custom": {
            "display_name": "Custom",
            "primary_objective": "User-Defined optimization.json",
            "philosophy": "Custom Configuration",
            "reason": "Uses optimization.json exactly as provided by the user.",
            "objective_priorities": [
                "As defined in optimization.json",
            ],
        },
    }

    ALIASES = {
        "smoke": "smoke",
        "smoke-test": "smoke",
        "conservative": "conservative",
        "balanced": "balanced",
        "profit": "profit",
        "maximum-profit": "profit",
        "max-profit": "profit",
        "nodes": "nodes",
        "minimum-nodes": "nodes",
        "fast": "fast",
        "fast-acquisition": "fast",
        "quality": "quality",
        "premium-data-quality": "quality",
        "custom": "custom",
    }

    def __init__(self, project_folder):
        self.project_folder = Path(project_folder)
        self.optimization_path = self.project_folder / "optimization.json"

    #################################################################

    @classmethod
    def normalize_preset_name(cls, preset_name):
        if preset_name is None:
            return "balanced"

        key = str(preset_name).strip().lower()
        normalized = cls.ALIASES.get(key)
        if normalized is None:
            valid = ", ".join(sorted(set(cls.ALIASES.keys())))
            raise ValueError(f"Unknown preset '{preset_name}'. Valid values: {valid}")

        return normalized

    #################################################################

    def build_config(self, preset_name):
        preset = self.normalize_preset_name(preset_name)
        preset_info = copy.deepcopy(self.PRESET_DEFINITIONS[preset])
        preset_info["preset_key"] = preset

        if preset == "custom":
            return None, preset_info

        base = self._load_base_config()
        config = copy.deepcopy(base)

        search = config["search_space"]

        if preset == "smoke":
            search["receiver_interval"] = self._spec_opt(165.0, 165.0, 220.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(550.0, 550.0, 660.0, 110.0)
            search["shot_interval"] = self._spec_opt(220.0, 220.0, 330.0, 110.0)
            search["source_line_spacing"] = self._spec_fixed(660.0)
            search["active_receiver_lines"] = self._spec_opt(10, 10, 12, 2)
            config["targets"] = copy.deepcopy(DEFAULT_CONFIG["targets"])
            config["limits"] = copy.deepcopy(DEFAULT_CONFIG["limits"])

        elif preset == "conservative":
            search["receiver_interval"] = self._spec_opt(165.0, 165.0, 220.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(550.0, 495.0, 605.0, 55.0)
            search["shot_interval"] = self._spec_opt(220.0, 220.0, 275.0, 55.0)
            search["source_line_spacing"] = self._spec_opt(660.0, 605.0, 715.0, 55.0)
            search["active_receiver_lines"] = self._spec_opt(12, 10, 14, 2)
            config["limits"]["acquisition_days_max"] = min(float(config["limits"].get("acquisition_days_max", 21.0)), 18.0)
            config["limits"]["node_count_max"] = min(float(config["limits"].get("node_count_max", 2000.0)), 1800.0)

        elif preset == "balanced":
            search["receiver_interval"] = self._spec_opt(165.0, 110.0, 220.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(550.0, 330.0, 660.0, 55.0)
            search["shot_interval"] = self._spec_opt(220.0, 110.0, 330.0, 55.0)
            search["source_line_spacing"] = self._spec_opt(660.0, 440.0, 880.0, 55.0)
            search["active_receiver_lines"] = self._spec_opt(12, 8, 20, 2)

        elif preset == "profit":
            search["receiver_interval"] = self._spec_opt(220.0, 165.0, 330.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(660.0, 440.0, 880.0, 55.0)
            search["shot_interval"] = self._spec_opt(275.0, 165.0, 385.0, 55.0)
            search["source_line_spacing"] = self._spec_opt(770.0, 550.0, 990.0, 55.0)
            search["active_receiver_lines"] = self._spec_opt(10, 8, 16, 2)

        elif preset == "nodes":
            search["receiver_interval"] = self._spec_opt(220.0, 165.0, 330.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(660.0, 550.0, 935.0, 55.0)
            search["shot_interval"] = self._spec_opt(275.0, 220.0, 385.0, 55.0)
            search["source_line_spacing"] = self._spec_opt(825.0, 660.0, 1045.0, 55.0)
            search["active_receiver_lines"] = self._spec_opt(8, 8, 14, 2)
            config["limits"]["node_count_max"] = min(float(config["limits"].get("node_count_max", 2000.0)), 1700.0)

        elif preset == "fast":
            search["receiver_interval"] = self._spec_opt(220.0, 165.0, 330.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(660.0, 550.0, 935.0, 55.0)
            search["shot_interval"] = self._spec_opt(275.0, 220.0, 385.0, 55.0)
            search["source_line_spacing"] = self._spec_opt(825.0, 660.0, 1100.0, 55.0)
            search["active_receiver_lines"] = self._spec_opt(10, 8, 14, 2)
            config["limits"]["acquisition_days_max"] = min(float(config["limits"].get("acquisition_days_max", 21.0)), 16.0)

        elif preset == "quality":
            search["receiver_interval"] = self._spec_opt(110.0, 110.0, 220.0, 55.0)
            search["receiver_line_spacing"] = self._spec_opt(440.0, 220.0, 550.0, 55.0)
            search["shot_interval"] = self._spec_opt(110.0, 110.0, 220.0, 55.0)
            search["source_line_spacing"] = self._spec_opt(440.0, 440.0, 715.0, 55.0)
            search["active_receiver_lines"] = self._spec_opt(16, 12, 20, 2)
            config["targets"]["interior_fold_min"] = max(float(config["targets"].get("interior_fold_min", 35.0)), 40.0)
            config["targets"]["maximum_incidence_angle_min"] = max(float(config["targets"].get("maximum_incidence_angle_min", 35.0)), 35.0)
            config["targets"]["orientation_coverage_min_deg"] = max(float(config["targets"].get("orientation_coverage_min_deg", 120.0)), 130.0)
            config["targets"]["coverage_min_percent"] = max(float(config["targets"].get("coverage_min_percent", 90.0)), 92.0)

        return config, preset_info

    #################################################################

    def _load_base_config(self):
        if not self.optimization_path.exists():
            return copy.deepcopy(DEFAULT_CONFIG)

        with open(self.optimization_path, "r", encoding="utf-8") as stream:
            raw = json.load(stream)

        config = {
            "search_space": copy.deepcopy(raw.get("search_space", DEFAULT_CONFIG["search_space"])),
            "targets": copy.deepcopy(raw.get("targets", DEFAULT_CONFIG["targets"])),
            "limits": copy.deepcopy(raw.get("limits", DEFAULT_CONFIG["limits"])),
        }

        return config

    #################################################################

    def _spec_opt(self, value, minimum, maximum, increment):
        return {
            "mode": "optimize",
            "value": value,
            "minimum": minimum,
            "maximum": maximum,
            "increment": increment,
        }

    #################################################################

    def _spec_fixed(self, value):
        return {
            "mode": "fixed",
            "value": value,
            "minimum": value,
            "maximum": value,
            "increment": 1 if isinstance(value, int) else 1.0,
        }
