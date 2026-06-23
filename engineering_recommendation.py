import csv
import math
import os
from pathlib import Path

from business_model import BusinessModel
from gis import GISProject


class EngineeringRecommendationEngine:
    """Builds an engineering manager-style recommendation report from existing optimizer outputs."""

    def __init__(self, project_folder, business_model=None, preset_info=None):
        self.project_folder = Path(project_folder)
        self.results_csv = self.project_folder / "optimization_results.csv"
        self.top20_csv = self.project_folder / "top_20_designs.csv"
        self.decision_summary_txt = self.project_folder / "optimizer_decision_summary.txt"
        self.diagnostics_txt = self.project_folder / "optimization_diagnostics.txt"
        self.failure_summary_csv = self.project_folder / "optimization_failure_summary.csv"
        self.optimization_json = self.project_folder / "optimization.json"
        self.output_txt = self.project_folder / "engineering_recommendation.txt"
        self.business_model = business_model if business_model is not None else BusinessModel(project_folder)
        self.preset_info = dict(preset_info) if isinstance(preset_info, dict) else None

    #################################################################

    def run(self):
        rows = self._read_csv(self.results_csv)
        top20 = self._read_csv(self.top20_csv)
        config = self._read_json(self.optimization_json)
        diagnostics_text = self._read_text(self.diagnostics_txt)
        decision_text = self._read_text(self.decision_summary_txt)
        failure_counts = self._read_failure_summary(self.failure_summary_csv)

        gis = GISProject(self.project_folder)
        gis.load_boundary()

        selected, next_best = self._select_designs(rows, top20)
        if selected is None:
            raise RuntimeError("No optimization candidate rows found for engineering recommendation.")

        selected_shipping = self.business_model.node_shipping_options(int(selected["required_node_count"]), gis)

        next_shipping = None
        if next_best is not None:
            next_shipping = self.business_model.node_shipping_options(int(next_best["required_node_count"]), gis)

        objective_rows, pass_count = self._client_objectives(selected, config)
        business_rows = self._business_objectives(selected, selected_shipping, gis)
        why_bullets = self._why_selected(rows, selected, next_best, selected_shipping, next_shipping, objective_rows)
        comparison_rows = self._compare_next_best(selected, next_best, selected_shipping, next_shipping)

        confidence_level, confidence_reason_lines = self._confidence(
            rows,
            selected,
            next_best,
            objective_rows,
            diagnostics_text,
            failure_counts,
        )

        text = self._build_report_text(
            selected=selected,
            objective_rows=objective_rows,
            business_rows=business_rows,
            why_bullets=why_bullets,
            comparison_rows=comparison_rows,
            confidence_level=confidence_level,
            confidence_reason_lines=confidence_reason_lines,
            decision_text=decision_text,
            diagnostics_text=diagnostics_text,
            examined_count=len(rows),
            valid_count=sum(1 for row in rows if row.get("is_valid", False)),
            pass_count=pass_count,
        )

        self._write_text(self.output_txt, text)
        print(text, end="")

        return {
            "selected_design": selected,
            "confidence": confidence_level,
        }

    #################################################################

    def _read_csv(self, path):
        if not path.exists():
            return []

        with open(path, "r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = []
            for raw in reader:
                row = dict(raw)
                for key in [
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
                    "node_rental_days",
                    "total_internal_cost",
                    "estimated_client_bid_price",
                    "estimated_profit",
                    "avaz_range",
                    "optimization_score",
                ]:
                    value = row.get(key, "")
                    row[key] = float(value) if value not in {"", None} else 0.0

                row["active_receiver_lines"] = int(round(row["active_receiver_lines"]))
                row["required_node_count"] = int(round(row["required_node_count"]))
                row["is_valid"] = str(row.get("is_valid", "")).strip().lower() == "true"
                rows.append(row)

        return rows

    #################################################################

    def _read_json(self, path):
        import json

        if not path.exists():
            return {}

        with open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)

    #################################################################

    def _read_text(self, path):
        if not path.exists():
            return ""

        with open(path, "r", encoding="utf-8") as stream:
            return stream.read()

    #################################################################

    def _read_failure_summary(self, path):
        rows = self._read_csv(path)
        if not rows:
            return {}

        out = {}
        for row in rows:
            constraint = str(row.get("Constraint", "")).strip()
            try:
                out[constraint] = int(float(row.get("FailureCount", 0)))
            except Exception:
                out[constraint] = 0

        return out

    #################################################################

    def _write_text(self, path, content):
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    #################################################################

    def _valid_ranking_key(self, row):
        simplicity = (
            row["receiver_line_spacing"]
            + row["receiver_interval"]
            + row["source_line_spacing"]
            + row["shot_interval"]
            + row["active_receiver_lines"]
        )

        return (
            -row["estimated_profit"],
            row["acquisition_days"],
            row["required_node_count"],
            simplicity,
            -row["optimization_score"],
            row["receiver_interval"],
            row["receiver_line_spacing"],
            row["shot_interval"],
            row["source_line_spacing"],
            row["active_receiver_lines"],
        )

    #################################################################

    def _fallback_ranking_key(self, row):
        return (
            -row["coverage_percent"],
            -row["maximum_incidence_angle"],
            -row["interior_fold"],
            -row["estimated_profit"],
            row["acquisition_days"],
            row["required_node_count"],
        )

    #################################################################

    def _select_designs(self, rows, top20):
        valid_rows = [row for row in rows if row.get("is_valid", False)]

        if top20:
            selected = dict(top20[0])
            next_best = dict(top20[1]) if len(top20) > 1 else None
            return selected, next_best

        if valid_rows:
            ranked = sorted(valid_rows, key=self._valid_ranking_key)
            selected = dict(ranked[0])
            next_best = dict(ranked[1]) if len(ranked) > 1 else None
            return selected, next_best

        if not rows:
            return None, None

        ranked = sorted(rows, key=self._fallback_ranking_key)
        selected = dict(ranked[0])
        return selected, None

    #################################################################

    def _client_objectives(self, selected, config):
        targets = config.get("targets", {}) if isinstance(config, dict) else {}
        limits = config.get("limits", {}) if isinstance(config, dict) else {}

        objectives = [
            (
                "Minimum Interior Fold",
                selected["interior_fold"],
                float(targets.get("interior_fold_min", 0.0)),
                ">=",
            ),
            (
                "Minimum AVA Angle",
                selected["maximum_incidence_angle"],
                float(targets.get("maximum_incidence_angle_min", 0.0)),
                ">=",
            ),
            (
                "Minimum AVAz Coverage",
                selected["orientation_coverage"],
                float(targets.get("orientation_coverage_min_deg", 0.0)),
                ">=",
            ),
            (
                "Minimum Survey Coverage",
                selected["coverage_percent"],
                float(targets.get("coverage_min_percent", 0.0)),
                ">=",
            ),
            (
                "Maximum Acquisition Days",
                selected["acquisition_days"],
                float(limits.get("acquisition_days_max", float("inf"))),
                "<=",
            ),
            (
                "Maximum Node Count",
                float(selected["required_node_count"]),
                float(limits.get("node_count_max", float("inf"))),
                "<=",
            ),
        ]

        rows = []
        pass_count = 0
        for name, actual, required, rule in objectives:
            if rule == ">=":
                passed = actual >= required
                margin = (actual - required)
            else:
                passed = actual <= required
                margin = (required - actual)

            if passed:
                pass_count += 1

            rows.append(
                {
                    "name": name,
                    "actual": actual,
                    "required": required,
                    "rule": rule,
                    "status": "PASS" if passed else "FAIL",
                    "margin": margin,
                }
            )

        return rows, pass_count

    #################################################################

    def _business_objectives(self, selected, shipping, gis):
        internal_cost = selected["total_internal_cost"]
        client_price = selected["estimated_client_bid_price"]
        expected_profit = selected["estimated_profit"]
        margin_pct = (expected_profit / client_price * 100.0) if client_price else 0.0

        acquisition_days = selected["acquisition_days"]
        profit_per_day = expected_profit / acquisition_days if acquisition_days > 0 else 0.0

        area_sq_miles = self._survey_area_sq_miles(gis)
        profit_per_sq_mile = expected_profit / area_sq_miles if area_sq_miles > 0 else 0.0

        return [
            ("Expected Internal Cost", f"${internal_cost:,.2f}"),
            ("Expected Client Price", f"${client_price:,.2f}"),
            ("Expected Profit", f"${expected_profit:,.2f}"),
            ("Profit Margin", f"{margin_pct:.2f}%"),
            ("Profit per Day", f"${profit_per_day:,.2f}"),
            ("Profit per Square Mile", f"${profit_per_sq_mile:,.2f}"),
            ("Expected Acquisition Days", f"{acquisition_days:.2f}"),
            ("Live Nodes Leased", f"{selected['required_node_count']:,}"),
            ("Shipping Method", shipping["selected_shipping_method_label"]),
        ]

    #################################################################

    def _survey_area_sq_miles(self, gis):
        try:
            area_sq_ft = float(gis.boundary.geometry.area.sum())
            return area_sq_ft / 27878400.0
        except Exception:
            return 0.0

    #################################################################

    def _why_selected(self, rows, selected, next_best, shipping, next_shipping, objective_rows):
        bullets = []

        total_objectives = len(objective_rows)
        pass_count = sum(1 for row in objective_rows if row["status"] == "PASS")
        if pass_count == total_objectives:
            bullets.append("Meets every required client objective.")
        else:
            bullets.append(f"Meets {pass_count} of {total_objectives} required client objectives.")

        peers = [row for row in rows if row.get("is_valid", False)] or rows

        max_profit = max((row["estimated_profit"] for row in peers), default=selected["estimated_profit"])
        min_cost = min((row["total_internal_cost"] for row in peers), default=selected["total_internal_cost"])
        min_nodes = min((row["required_node_count"] for row in peers), default=selected["required_node_count"])
        min_days = min((row["acquisition_days"] for row in peers), default=selected["acquisition_days"])

        if math.isclose(selected["estimated_profit"], max_profit, rel_tol=1e-9, abs_tol=1e-6):
            bullets.append("Highest expected profit among peer designs.")

        if math.isclose(selected["total_internal_cost"], min_cost, rel_tol=1e-9, abs_tol=1e-6):
            bullets.append("Lowest acquisition cost among peer designs.")

        if selected["required_node_count"] <= min_nodes:
            bullets.append("Uses the lowest live node count among peer designs.")

        if selected["acquisition_days"] <= min_days:
            bullets.append("Has the shortest acquisition schedule among peer designs.")

        if next_best is not None:
            if selected["required_node_count"] < next_best["required_node_count"]:
                bullets.append("Uses fewer live nodes than the next-best valid design.")

            if shipping["selected_shipping_cost"] < next_shipping["selected_shipping_cost"]:
                bullets.append("Lower transportation cost than the next-best valid design.")

            if selected["node_rental_cost"] < next_best["node_rental_cost"]:
                bullets.append("Lower node rental cost than the next-best valid design.")

            if selected["acquisition_days"] < next_best["acquisition_days"]:
                bullets.append("Shorter acquisition schedule than the next-best valid design.")

        objective_lookup = {row["name"]: row for row in objective_rows}
        if objective_lookup["Minimum AVA Angle"]["status"] == "PASS":
            bullets.append("Maintains required AVA angle objective.")
        if objective_lookup["Minimum Interior Fold"]["status"] == "PASS":
            bullets.append("Maintains required interior fold objective.")
        if objective_lookup["Minimum Survey Coverage"]["status"] == "PASS":
            bullets.append("Maintains required survey coverage objective.")

        return bullets

    #################################################################

    def _compare_next_best(self, selected, next_best, shipping, next_shipping):
        if next_best is None:
            return []

        return [
            ("Profit", self._format_signed_currency(selected["estimated_profit"] - next_best["estimated_profit"])),
            ("Acquisition Days", self._format_signed_number(selected["acquisition_days"] - next_best["acquisition_days"], 2)),
            ("Node Count", self._format_signed_int(selected["required_node_count"] - next_best["required_node_count"])),
            (
                "Transportation Cost",
                self._format_signed_currency(shipping["selected_shipping_cost"] - next_shipping["selected_shipping_cost"]),
            ),
            ("Interior Fold", self._format_signed_number(selected["interior_fold"] - next_best["interior_fold"], 2)),
            (
                "Maximum Incidence Angle",
                self._format_signed_number(selected["maximum_incidence_angle"] - next_best["maximum_incidence_angle"], 2) + "°",
            ),
            ("Coverage", self._format_signed_number(selected["coverage_percent"] - next_best["coverage_percent"], 2) + "%"),
        ]

    #################################################################

    def _format_signed_currency(self, value):
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.2f}"

    #################################################################

    def _format_signed_number(self, value, decimals):
        sign = "+" if value >= 0 else "-"
        return f"{sign}{abs(value):.{decimals}f}"

    #################################################################

    def _format_signed_int(self, value):
        sign = "+" if value >= 0 else "-"
        return f"{sign}{abs(int(round(value))):,}"

    #################################################################

    def _confidence(self, rows, selected, next_best, objective_rows, diagnostics_text, failure_counts):
        valid_rows = [row for row in rows if row.get("is_valid", False)]
        valid_count = len(valid_rows)

        stable_ratio = self._sensitivity_stability_ratio(diagnostics_text)
        all_pass = all(row["status"] == "PASS" for row in objective_rows)
        robustness = self._objective_robustness(objective_rows)

        profit_margin_pct = 0.0
        node_delta = 0
        day_delta = 0.0
        if next_best is not None and abs(next_best["estimated_profit"]) > 1.0e-9:
            profit_margin_pct = (
                (selected["estimated_profit"] - next_best["estimated_profit"])
                / abs(next_best["estimated_profit"])
                * 100.0
            )
            node_delta = selected["required_node_count"] - next_best["required_node_count"]
            day_delta = selected["acquisition_days"] - next_best["acquisition_days"]

        score = 0
        if valid_count >= 20:
            score += 2
        elif valid_count >= 5:
            score += 1
        elif valid_count == 0:
            score -= 2

        if next_best is not None:
            if profit_margin_pct >= 10.0:
                score += 2
            elif profit_margin_pct >= 3.0:
                score += 1
            elif profit_margin_pct < 0.0:
                score -= 1

            if node_delta <= -1000:
                score += 1
            if day_delta <= -1.0:
                score += 1

        if stable_ratio >= 0.70:
            score += 1
        elif stable_ratio < 0.40:
            score -= 1

        if all_pass and robustness >= 0.0:
            score += 1
        elif not all_pass:
            score -= 1

        major_failures = sum(
            failure_counts.get(key, 0)
            for key in ["AVA Angle", "Interior Fold", "Coverage", "Node Count", "Acquisition Days"]
        )
        if major_failures > max(1, len(rows)):
            score -= 1

        if score >= 4:
            level = "HIGH"
        elif score >= 2:
            level = "MODERATE"
        else:
            level = "LOW"

        reasons = [f"{valid_count} valid designs evaluated."]

        if next_best is not None:
            reasons.append(f"Winning design profit margin versus next best: {profit_margin_pct:.2f}%.")
            reasons.append(
                f"Node delta versus next best: {self._format_signed_int(node_delta)}; acquisition-day delta: {self._format_signed_number(day_delta, 2)}."
            )
        else:
            reasons.append("No second valid design available for comparative margin testing.")

        reasons.append(f"Sensitivity stability ratio: {stable_ratio * 100.0:.1f}% neutral responses.")

        pass_count = sum(1 for row in objective_rows if row["status"] == "PASS")
        reasons.append(f"Client objectives passed: {pass_count}/{len(objective_rows)}.")

        if diagnostics_text:
            limiting = self._most_limiting_constraint(diagnostics_text)
            if limiting:
                reasons.append(f"Most limiting constraint from diagnostics: {limiting}.")

        return level, reasons

    #################################################################

    def _sensitivity_stability_ratio(self, diagnostics_text):
        if not diagnostics_text:
            return 0.0

        total = 0
        neutral = 0
        for line in diagnostics_text.splitlines():
            line = line.strip()
            if "Increase ->" in line or "Decrease ->" in line:
                total += 1
                if line.endswith("Neutral"):
                    neutral += 1

        if total == 0:
            return 0.0

        return neutral / total

    #################################################################

    def _objective_robustness(self, objective_rows):
        margins = []
        for row in objective_rows:
            required = row["required"]
            if required in {0.0, float("inf")}:
                continue
            if row["rule"] == ">=":
                margins.append((row["actual"] - required) / abs(required) * 100.0)
            else:
                margins.append((required - row["actual"]) / abs(required) * 100.0)

        if not margins:
            return 0.0

        return sum(margins) / len(margins)

    #################################################################

    def _most_limiting_constraint(self, diagnostics_text):
        lines = [line.strip() for line in diagnostics_text.splitlines()]
        for index, line in enumerate(lines):
            if line == "Most Limiting Constraint":
                for follow in lines[index + 1:]:
                    if follow:
                        return follow
        return ""

    #################################################################

    def _build_report_text(
        self,
        selected,
        objective_rows,
        business_rows,
        why_bullets,
        comparison_rows,
        confidence_level,
        confidence_reason_lines,
        decision_text,
        diagnostics_text,
        examined_count,
        valid_count,
        pass_count,
    ):
        lines = []

        lines.extend([
            "==================================================",
            "ENGINEERING RECOMMENDATION",
            "==================================================",
            "",
        ])

        lines.extend([
            "Client Objectives",
            "",
        ])
        for row in objective_rows:
            lines.append(
                f"{row['name']}: {row['status']} (Actual {row['actual']:.2f} {row['rule']} Required {row['required']:.2f})"
            )

        lines.extend([
            "",
            "Business Objectives",
            "",
        ])
        for label, value in business_rows:
            lines.append(f"{label}: {value}")

        lines.extend([
            "",
            "Recommended Design",
            "",
            f"Receiver Line Spacing: {selected['receiver_line_spacing']:.2f}",
            f"Receiver Interval: {selected['receiver_interval']:.2f}",
            f"Source Line Spacing: {selected['source_line_spacing']:.2f}",
            f"Shot Interval: {selected['shot_interval']:.2f}",
            f"Active Receiver Lines: {selected['active_receiver_lines']}",
            f"Estimated Cost: ${selected['total_internal_cost']:,.2f}",
            f"Expected Profit: ${selected['estimated_profit']:,.2f}",
            f"Expected Acquisition Days: {selected['acquisition_days']:.2f}",
            f"Live Nodes Leased: {selected['required_node_count']:,}",
            "",
            "WHY THIS DESIGN WAS SELECTED",
            "",
        ])

        for bullet in why_bullets:
            lines.append(f"- {bullet}")

        lines.extend([
            "",
            "COMPARED WITH NEXT BEST DESIGN",
            "",
        ])

        if comparison_rows:
            for label, value in comparison_rows:
                lines.append(f"{label}: {value}")
        else:
            lines.append("No second valid design available for comparison.")

        lines.extend([
            "",
            "RECOMMENDATION CONFIDENCE",
            "",
            confidence_level,
            "",
            "Reason",
            "",
        ])

        for reason in confidence_reason_lines:
            lines.append(reason)

        lines.extend([
            "",
            "Validation Context",
            f"Candidate Designs Examined: {examined_count}",
            f"Valid Candidate Designs: {valid_count}",
            f"Client Objectives Passed: {pass_count}/{len(objective_rows)}",
            f"Decision Summary Available: {'YES' if bool(decision_text.strip()) else 'NO'}",
            f"Diagnostics Available: {'YES' if bool(diagnostics_text.strip()) else 'NO'}",
            "",
        ])

        preset_lines = self._preset_section_lines(examined_count)
        if preset_lines:
            lines.extend(preset_lines)

        return "\n".join(lines).rstrip() + "\n"

    #################################################################

    def _preset_section_lines(self, examined_count):
        if not self.preset_info:
            return []

        priorities = self.preset_info.get("objective_priorities", [])
        priorities_text = ", ".join(str(item) for item in priorities) if priorities else "N/A"

        return [
            "OPTIMIZATION PRESET",
            "",
            f"Preset Name: {self.preset_info.get('display_name', 'Unknown')}",
            f"Primary Objective: {self.preset_info.get('primary_objective', 'N/A')}",
            f"Search Space Size: {examined_count}",
            f"Objective Priorities: {priorities_text}",
            "",
        ]
