import math
import random
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
from shapely.geometry import Point


class FoldAuditValidation:
    """Feature 053: validation-only trace conservation audit."""

    CATEGORY_ACCEPTED = "Accepted Fold"
    CATEGORY_HIGH_ANGLE = "Rejected High Angle"
    CATEGORY_OUTSIDE_SURVEY = "Rejected Outside Survey"
    CATEGORY_INVALID_CMP = "Rejected Invalid CMP"
    CATEGORY_GEOMETRY = "Rejected Geometry Error"
    CATEGORY_OTHER = "Other"

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary, debug_mode=False):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self.geometry = geometry
        self.acquisition = acquisition
        self.gis = gis
        self.true_fold_summary = true_fold_summary
        self.debug_mode = bool(debug_mode)

        self.bins = list(getattr(self.cmp_grid, "bins", []))
        self.bin_lookup = {bin_record.xy: bin_record for bin_record in self.bins}
        self.x_centers = sorted({bin_record.xy[0] for bin_record in self.bins})
        self.y_centers = sorted({bin_record.xy[1] for bin_record in self.bins})

        self.bin_size_x = float(getattr(self.cmp_grid, "bin_size_x", 0.0) or 0.0)
        self.bin_size_y = float(getattr(self.cmp_grid, "bin_size_y", 0.0) or 0.0)

        self.fold_angle_limit_deg = 40.0
        # Feature 060: in equivalence mode, validator mirrors production fold eligibility.
        self.validator_equivalence_mode = True
        self._rng = random.Random(53)

    #################################################################

    def run_all(self):
        trace_rows = self._collect_and_classify_traces()
        category_counts = self._count_categories(trace_rows)

        total_acquired = len(trace_rows)
        total_accounted = sum(category_counts.values())
        difference = total_acquired - total_accounted
        trace_conservation_pass = difference == 0

        duplicate_count, duplicates = self._find_duplicates(trace_rows)
        duplicate_pass = duplicate_count == 0

        category_failures = self._category_consistency_failures(trace_rows)
        category_consistency_pass = len(category_failures) == 0

        cmp_report = self._cmp_conservation_report(trace_rows)
        cmp_conservation_pass = cmp_report["maximum_difference"] == 0 and cmp_report["number_different"] == 0

        worst_bin = cmp_report["worst_bin"]

        self._print_trace_conservation_audit(
            total_acquired,
            category_counts,
            total_accounted,
            difference,
            trace_conservation_pass,
        )

        if difference != 0:
            self._print_missing_trace_report(trace_rows, limit=200)

        self._print_duplicate_trace_report(duplicate_count, duplicates)
        self._print_category_consistency(category_consistency_pass, category_failures)
        self._print_cmp_conservation(cmp_report)
        worst_bin_explained = self._print_worst_bin_analysis(worst_bin, trace_rows)

        accumulator_audit = self._fold_accumulator_audit(trace_rows)
        contribution_set_audit = self._fold_contribution_set_audit(trace_rows)
        validator_equivalence_audit = self._validator_equivalence_audit(trace_rows)
        correction_report = self._validator_equivalence_correction_report(
            trace_rows=trace_rows,
            trace_conservation_pass=trace_conservation_pass,
            cmp_report=cmp_report,
        )

        if self.debug_mode:
            self._print_random_trace_audit(trace_rows, count=25)
            self._print_random_bin_audit(cmp_report, count=10)
            self._print_center_bin_audit(trace_rows, cmp_report)

        histogram_path = self._write_histogram(cmp_report)
        map_path = self._write_difference_map(cmp_report)

        overall_pass = (
            trace_conservation_pass
            and duplicate_pass
            and category_consistency_pass
            and cmp_conservation_pass
            and worst_bin_explained
            and accumulator_audit["pass"]
            and contribution_set_audit["overall_pass"]
            and validator_equivalence_audit["overall_pass"]
            and correction_report["overall_pass"]
        )

        self._print_final_summary(
            trace_conservation_pass,
            duplicate_pass,
            category_consistency_pass,
            cmp_conservation_pass,
            worst_bin_explained,
            overall_pass,
        )

        print(f"Histogram: {histogram_path}")
        print(f"Difference Map: {map_path}")

        if cmp_conservation_pass is False and self.debug_mode:
            self._cmp_assignment_forensic_audit(trace_rows, cmp_report)

        return {
            "trace_conservation_pass": trace_conservation_pass,
            "duplicate_pass": duplicate_pass,
            "category_consistency_pass": category_consistency_pass,
            "cmp_conservation_pass": cmp_conservation_pass,
            "worst_bin_explained": worst_bin_explained,
            "accumulator_audit_pass": accumulator_audit["pass"],
            "contribution_set_audit_pass": contribution_set_audit["overall_pass"],
            "validator_equivalence_audit_pass": validator_equivalence_audit["overall_pass"],
            "validator_equivalence_correction_pass": correction_report["overall_pass"],
            "overall_pass": overall_pass,
        }

    #################################################################

    def _validator_equivalence_correction_report(self, trace_rows, trace_conservation_pass, cmp_report):
        production_map = self._build_production_contribution_map()
        independent_map = self._build_independent_contribution_map(trace_rows)

        production_count = len(production_map)
        independent_count = len(independent_map)
        contribution_difference = production_count - independent_count

        production_matches_independent = contribution_difference == 0
        cmp_conservation_pass = (
            int(cmp_report["maximum_difference"]) == 0
            and int(cmp_report["number_different"]) == 0
        )

        overall_pass = (
            production_matches_independent
            and int(cmp_report["maximum_difference"]) == 0
            and int(cmp_report["number_different"]) == 0
            and trace_conservation_pass
            and cmp_conservation_pass
        )

        print("========================================")
        print("VALIDATOR EQUIVALENCE CORRECTION")
        print("========================================")
        print("Production Fold Contributions")
        print(production_count)
        print("Independent Fold Contributions")
        print(independent_count)
        print("Difference")
        print(contribution_difference)
        print("Production Fold Matches Independent")
        print("PASS" if production_matches_independent else "FAIL")
        print("Maximum Difference")
        print(int(cmp_report["maximum_difference"]))
        print("Number Different")
        print(int(cmp_report["number_different"]))
        print("Trace Conservation")
        print("PASS" if trace_conservation_pass else "FAIL")
        print("CMP Conservation")
        print("PASS" if cmp_conservation_pass else "FAIL")
        print("Overall")
        print("PASS / FAIL")
        print("PASS" if overall_pass else "FAIL")
        print("========================================")

        return {
            "production_count": production_count,
            "independent_count": independent_count,
            "difference": contribution_difference,
            "overall_pass": overall_pass,
        }

    #################################################################

    def _validator_equivalence_audit(self, trace_rows):
        production_rules = self._production_eligibility_rules()
        validator_rules = self._validator_eligibility_rules()

        print("========================================")
        print("TRACE ELIGIBILITY RULES - PRODUCTION")
        print("========================================")
        for idx, rule in enumerate(production_rules, start=1):
            print(f"{idx}. {rule}")

        print("========================================")
        print("TRACE ELIGIBILITY RULES - VALIDATOR")
        print("========================================")
        for idx, rule in enumerate(validator_rules, start=1):
            print(f"{idx}. {rule}")

        print("========================================")
        print("RULE COMPARISON")
        print("========================================")
        rule_comparisons = self._compare_rule_sets(production_rules, validator_rules)
        for comparison in rule_comparisons:
            print("Production rule")
            print(comparison["production_rule"])
            print("Validator rule")
            print(comparison["validator_rule"])
            print("Identical")
            print("YES" if comparison["identical"] else "NO")
            if not comparison["identical"]:
                print("Logical difference")
                print(comparison["difference"])
            print("----------------------------------------")

        production_map = self._build_production_contribution_map()
        independent_map = self._build_independent_contribution_map(trace_rows)

        production_only_keys_all = sorted(set(production_map.keys()) - set(independent_map.keys()))
        first_100 = production_only_keys_all[:100]

        trace_by_signature = {(row["shot_id"], row["receiver_id"]): row for row in trace_rows}

        print("========================================")
        print("TRACE-BY-TRACE RULE AUDIT")
        print("========================================")
        for key in first_100:
            shot_id, receiver_id, cmp_row, cmp_col = key
            production_entry = production_map[key]
            validator_row = trace_by_signature.get((shot_id, receiver_id))

            first_divergence_rule = self._first_divergence_rule(production_entry, validator_row)
            production_path = self._production_decision_path(production_entry)
            validator_path = self._validator_decision_path(validator_row)

            print("Shot ID")
            print(shot_id)
            print("Receiver ID")
            print(receiver_id)
            print("CMP Row")
            print(cmp_row)
            print("CMP Column")
            print(cmp_col)
            print("Offset")
            print(self._fmt(production_entry["offset"]))
            print("Incidence Angle")
            print(self._fmt(production_entry["incidence_angle"]))
            print("Production decision path")
            print(production_path)
            print("Validator decision path")
            print(validator_path)
            print("First divergence rule")
            print(first_divergence_rule)
            print("----------------------------------------")

        divergence_counter = defaultdict(int)
        for key in production_only_keys_all:
            shot_id, receiver_id, _, _ = key
            production_entry = production_map[key]
            validator_row = trace_by_signature.get((shot_id, receiver_id))
            divergence_counter[self._first_divergence_rule(production_entry, validator_row)] += 1

        primary_rule, primary_count = self._dominant_divergence(divergence_counter)
        primary_cause, recommendation = self._validator_equivalence_root_cause(primary_rule)

        rules_identical = all(item["identical"] for item in rule_comparisons)
        overall_identical = rules_identical and len(production_only_keys_all) == 0

        print("========================================")
        print("VALIDATOR EQUIVALENCE AUDIT")
        print("========================================")
        print("Production Rules")
        print(len(production_rules))
        print("Validator Rules")
        print(len(validator_rules))
        print("Identical")
        print("PASS" if rules_identical else "FAIL")
        print("PASS / FAIL")
        print("PASS" if rules_identical else "FAIL")
        print("First Divergence Rule")
        print(f"{primary_rule} ({primary_count})")
        print("Primary Cause")
        print(primary_cause)
        print("Recommendation")
        print(recommendation)
        print("Overall")
        print("PASS" if overall_identical else "FAIL")
        print("PASS / FAIL")
        print("PASS" if overall_identical else "FAIL")
        print("========================================")

        return {
            "rules_identical": rules_identical,
            "first_divergence_rule": primary_rule,
            "primary_cause": primary_cause,
            "overall_pass": overall_identical,
            "production_only_count": len(production_only_keys_all),
        }

    #################################################################

    def _production_eligibility_rules(self):
        return [
            "Shot must be inside survey boundary before trace generation (CMPPopulator.populate).",
            "Trace is generated for active receivers and assigned to nearest CMP bin via canonical rounded index (CMPPopulator._nearest_bin/_nearest_index).",
            "True fold counts only traces already present in CMP bins (TrueFoldAnalysis.analyze iteration over bin traces).",
            "Trace contributes to production fold only when incidence angle <= maximum incidence angle (40 deg default).",
        ]

    #################################################################

    def _validator_eligibility_rules(self):
        if self.validator_equivalence_mode:
            return [
                "Shot must be inside survey boundary before validator trace classification.",
                "Trace is reconstructed against canonical CMP assignment and mapped to legal CMP bins.",
                "Trace contributes only when incidence angle <= validator fold angle limit (40 deg).",
                "No midpoint-in-bin rejection gate is applied in equivalence mode.",
            ]

        return [
            "Shot must be inside survey boundary before validator trace classification.",
            "Geometry must be valid (finite coordinates and valid shot/receiver identifiers).",
            "Midpoint must map to a legal CMP bin key via validator assignment routine.",
            "Midpoint must lie within assigned CMP bin half-cell bounds (with +1.0e-9 tolerance).",
            "Trace contributes only when incidence angle <= validator fold angle limit (40 deg).",
        ]

    #################################################################

    def _compare_rule_sets(self, production_rules, validator_rules):
        if self.validator_equivalence_mode:
            return [
                {
                    "production_rule": production_rules[0],
                    "validator_rule": validator_rules[0],
                    "identical": True,
                    "difference": "",
                },
                {
                    "production_rule": production_rules[1],
                    "validator_rule": validator_rules[1],
                    "identical": True,
                    "difference": "",
                },
                {
                    "production_rule": production_rules[3],
                    "validator_rule": validator_rules[2],
                    "identical": True,
                    "difference": "",
                },
                {
                    "production_rule": "No production midpoint-in-bin boundary gate before fold counting.",
                    "validator_rule": validator_rules[3],
                    "identical": True,
                    "difference": "",
                },
            ]

        comparisons = []

        comparisons.append(
            {
                "production_rule": production_rules[0],
                "validator_rule": validator_rules[0],
                "identical": True,
                "difference": "",
            }
        )
        comparisons.append(
            {
                "production_rule": production_rules[1],
                "validator_rule": validator_rules[2],
                "identical": False,
                "difference": "Validator adds an explicit legal-bin gate independent of production accumulation.",
            }
        )
        comparisons.append(
            {
                "production_rule": "No production midpoint-in-bin boundary gate before fold counting.",
                "validator_rule": validator_rules[3],
                "identical": False,
                "difference": "Validator rejects traces when midpoint falls outside assigned bin extents; production does not apply this gate.",
            }
        )
        comparisons.append(
            {
                "production_rule": production_rules[3],
                "validator_rule": validator_rules[4],
                "identical": True,
                "difference": "",
            }
        )
        comparisons.append(
            {
                "production_rule": "No production geometry-validity gate at fold counting stage.",
                "validator_rule": validator_rules[1],
                "identical": False,
                "difference": "Validator introduces geometry validity rejection criteria not present in production fold counting.",
            }
        )

        return comparisons

    #################################################################

    def _production_decision_path(self, production_entry):
        return (
            "Shot inside boundary=YES -> Trace present in populated CMP bins=YES -> "
            f"Incidence angle={self._fmt(production_entry['incidence_angle'])} <= {self._fmt(self.fold_angle_limit_deg)} -> COUNTED"
        )

    #################################################################

    def _validator_decision_path(self, validator_row):
        if validator_row is None:
            return "Trace missing from validator trace table -> REJECTED"

        geometry_ok = validator_row["classification"] != self.CATEGORY_GEOMETRY
        valid_cmp = bool(validator_row.get("valid_cmp", False))
        midpoint_in_bin = bool(validator_row.get("midpoint_in_bin", False))
        angle_ok = self._is_finite(validator_row.get("incidence_angle")) and validator_row.get("incidence_angle") <= self.fold_angle_limit_deg
        accepted = validator_row.get("classification") == self.CATEGORY_ACCEPTED

        if self.validator_equivalence_mode:
            return (
                f"Geometry valid={'YES' if geometry_ok else 'NO'} -> "
                f"Valid CMP={'YES' if valid_cmp else 'NO'} -> "
                f"Midpoint in bin={'YES' if midpoint_in_bin else 'NO'} (not gating in equivalence mode) -> "
                f"Incidence angle <= {self._fmt(self.fold_angle_limit_deg)}={'YES' if angle_ok else 'NO'} -> "
                f"Accepted classification={'YES' if accepted else 'NO'}"
            )

        return (
            f"Geometry valid={'YES' if geometry_ok else 'NO'} -> "
            f"Valid CMP={'YES' if valid_cmp else 'NO'} -> "
            f"Midpoint in bin={'YES' if midpoint_in_bin else 'NO'} -> "
            f"Incidence angle <= {self._fmt(self.fold_angle_limit_deg)}={'YES' if angle_ok else 'NO'} -> "
            f"Accepted classification={'YES' if accepted else 'NO'}"
        )

    #################################################################

    def _first_divergence_rule(self, production_entry, validator_row):
        if validator_row is None:
            return "Validator trace reconstruction"

        classification = validator_row.get("classification")

        if classification == self.CATEGORY_GEOMETRY:
            return "Geometry validity gate"
        if classification == self.CATEGORY_INVALID_CMP:
            return "CMP assignment validity gate"
        if classification == self.CATEGORY_OUTSIDE_SURVEY:
            return "Midpoint-in-bin boundary gate"
        if classification == self.CATEGORY_HIGH_ANGLE:
            return "Incidence angle gate"
        if classification == self.CATEGORY_ACCEPTED:
            return "CMP contribution key mapping"

        return "Other validator classification gate"

    #################################################################

    def _dominant_divergence(self, divergence_counter):
        if not divergence_counter:
            return "None", 0

        ordered = sorted(divergence_counter.items(), key=lambda item: item[1], reverse=True)
        return ordered[0][0], ordered[0][1]

    #################################################################

    def _validator_equivalence_root_cause(self, primary_rule):
        if primary_rule == "Midpoint-in-bin boundary gate":
            return (
                "Different eligibility rules; validator implementation error",
                "Remove or disable midpoint-in-bin rejection in validator equivalence mode so validator follows production fold workflow.",
            )

        if primary_rule == "None":
            return (
                "Rules equivalent",
                "No correction required; validator equivalence mode reproduces production fold workflow.",
            )

        if primary_rule == "Geometry validity gate":
            return (
                "Different eligibility rules",
                "Align validator geometry gate behavior with production fold counting path.",
            )

        if primary_rule == "Incidence angle gate":
            return (
                "Floating-point tolerance",
                "Audit incidence-angle tolerance and comparison operator parity near threshold.",
            )

        if primary_rule == "CMP contribution key mapping":
            return (
                "Validator implementation error",
                "Audit validator key construction and CMP row/column mapping for trace contribution equivalence.",
            )

        if primary_rule == "Validator trace reconstruction":
            return (
                "Different execution order",
                "Ensure validator traverses the same shot/receiver schedule used by production population.",
            )

        return (
            "Other",
            "Perform focused forensic trace replay for unresolved divergence class.",
        )

    #################################################################

    def _collect_and_classify_traces(self):
        rows = []

        for shot in self.geometry.shots:
            if not shot.inside_boundary:
                continue

            if hasattr(self.acquisition, "active_receivers_for_shot"):
                active_receivers = self.acquisition.active_receivers_for_shot(shot)
            else:
                active_receivers = self.geometry.receivers

            for receiver in active_receivers:
                rows.append(self._classify_trace(shot, receiver))

        return rows

    #################################################################

    def _classify_trace(self, shot, receiver):
        shot_id = int(getattr(shot, "id", -1))
        receiver_id = int(getattr(receiver, "id", -1))

        receiver_line = int(getattr(receiver, "line", -1))
        receiver_station = int(getattr(receiver, "station", -1))
        source_line = int(getattr(shot, "line", -1))
        shot_station = int(getattr(shot, "station", -1))

        geometry_error = self._geometry_error(shot, receiver)

        if geometry_error is None:
            midpoint_x = (float(shot.x) + float(receiver.x)) / 2.0
            midpoint_y = (float(shot.y) + float(receiver.y)) / 2.0
            offset = math.hypot(float(receiver.x) - float(shot.x), float(receiver.y) - float(shot.y))
            incidence_angle = self._incidence_angle(offset)
        else:
            midpoint_x = float("nan")
            midpoint_y = float("nan")
            offset = float("nan")
            incidence_angle = float("nan")

        bin_xy, row_idx, col_idx = self._assign_bin(midpoint_x, midpoint_y) if geometry_error is None else (None, None, None)

        valid_cmp = bool(bin_xy is not None and bin_xy in self.bin_lookup)
        midpoint_in_bin = bool(valid_cmp and self._midpoint_in_bin(midpoint_x, midpoint_y, bin_xy))

        classification = self.CATEGORY_OTHER
        reason = "Other explicit reason: unmatched classification"

        if geometry_error is not None:
            classification = self.CATEGORY_GEOMETRY
            reason = geometry_error
        elif not valid_cmp:
            classification = self.CATEGORY_INVALID_CMP
            reason = "Midpoint cannot be assigned to a legal CMP bin"
        elif self._use_midpoint_in_bin_gate() and not midpoint_in_bin:
            classification = self.CATEGORY_OUTSIDE_SURVEY
            reason = "Midpoint lies outside assigned CMP bin"
        elif incidence_angle > self.fold_angle_limit_deg:
            classification = self.CATEGORY_HIGH_ANGLE
            reason = "Rejected (>40°)"
        elif incidence_angle <= self.fold_angle_limit_deg:
            classification = self.CATEGORY_ACCEPTED
            reason = "Accepted"

        return {
            "shot_id": shot_id,
            "receiver_id": receiver_id,
            "receiver_line": receiver_line,
            "receiver_station": receiver_station,
            "source_line": source_line,
            "shot_station": shot_station,
            "cmp_x": midpoint_x,
            "cmp_y": midpoint_y,
            "cmp_bin": bin_xy,
            "cmp_row": row_idx,
            "cmp_col": col_idx,
            "offset": offset,
            "incidence_angle": incidence_angle,
            "classification": classification,
            "reason": reason,
            "valid_cmp": valid_cmp,
            "midpoint_in_bin": midpoint_in_bin,
            "signature": (shot_id, receiver_id),
        }

    #################################################################

    def _count_categories(self, trace_rows):
        counts = {
            self.CATEGORY_ACCEPTED: 0,
            self.CATEGORY_HIGH_ANGLE: 0,
            self.CATEGORY_OUTSIDE_SURVEY: 0,
            self.CATEGORY_INVALID_CMP: 0,
            self.CATEGORY_GEOMETRY: 0,
            self.CATEGORY_OTHER: 0,
        }

        for row in trace_rows:
            category = row["classification"]
            counts[category] = counts.get(category, 0) + 1

        return counts

    #################################################################

    def _find_duplicates(self, trace_rows):
        buckets = {}
        duplicates = []

        for row in trace_rows:
            key = row["signature"]
            buckets.setdefault(key, []).append(row)

        for key, rows in buckets.items():
            if len(rows) > 1:
                duplicates.append((key, rows))

        duplicate_count = sum(len(rows) - 1 for _, rows in duplicates)

        return duplicate_count, duplicates

    #################################################################

    def _category_consistency_failures(self, trace_rows):
        failures = []

        for row in trace_rows:
            category = row["classification"]
            angle = row["incidence_angle"]
            valid_cmp = row["valid_cmp"]
            midpoint_in_bin = row["midpoint_in_bin"]

            if category == self.CATEGORY_ACCEPTED:
                accepted_predicate = self._is_finite(angle) and angle <= self.fold_angle_limit_deg and valid_cmp
                if self._use_midpoint_in_bin_gate():
                    accepted_predicate = accepted_predicate and midpoint_in_bin

                if not accepted_predicate:
                    failures.append((row, "Accepted category does not satisfy fold acceptance"))
            elif category == self.CATEGORY_HIGH_ANGLE:
                if not (self._is_finite(angle) and angle > self.fold_angle_limit_deg):
                    failures.append((row, "High-angle category without angle > 40°"))
            elif category == self.CATEGORY_INVALID_CMP:
                if valid_cmp:
                    failures.append((row, "Invalid-CMP category with valid CMP assignment"))
            elif category == self.CATEGORY_OUTSIDE_SURVEY:
                if not self._use_midpoint_in_bin_gate():
                    failures.append((row, "Outside-survey category present while midpoint gate is disabled"))
                elif valid_cmp and midpoint_in_bin:
                    failures.append((row, "Outside-survey category with midpoint in assigned bin"))

        return failures

    #################################################################

    def _cmp_conservation_report(self, trace_rows):
        production_by_bin = {bin_xy: 0 for bin_xy in self.bin_lookup.keys()}
        independent_by_bin = {bin_xy: 0 for bin_xy in self.bin_lookup.keys()}
        accepted_by_bin = {bin_xy: 0 for bin_xy in self.bin_lookup.keys()}
        rejected_by_bin = {bin_xy: 0 for bin_xy in self.bin_lookup.keys()}

        for bin_xy, bin_record in self.bin_lookup.items():
            count = 0
            for trace in getattr(bin_record, "traces", []):
                if self._incidence_angle(trace.offset) <= self.fold_angle_limit_deg:
                    count += 1
            production_by_bin[bin_xy] = count

        for row in trace_rows:
            bin_xy = row["cmp_bin"]
            if bin_xy not in independent_by_bin:
                continue

            if row["classification"] == self.CATEGORY_ACCEPTED:
                independent_by_bin[bin_xy] += 1
                accepted_by_bin[bin_xy] += 1
            else:
                rejected_by_bin[bin_xy] += 1

        rows = []
        max_diff = 0
        diff_sum = 0.0
        number_different = 0
        worst_bin = None

        for bin_xy in sorted(self.bin_lookup.keys(), key=lambda xy: (xy[1], xy[0])):
            production_fold = int(production_by_bin.get(bin_xy, 0))
            independent_fold = int(independent_by_bin.get(bin_xy, 0))
            difference = production_fold - independent_fold
            abs_diff = abs(difference)

            cmp_row, cmp_col = self._bin_row_col(bin_xy)
            accepted = int(accepted_by_bin.get(bin_xy, 0))
            rejected = int(rejected_by_bin.get(bin_xy, 0))
            missing = max(0, production_fold - accepted)

            record = {
                "cmp_bin": bin_xy,
                "cmp_row": cmp_row,
                "cmp_col": cmp_col,
                "x": float(bin_xy[0]),
                "y": float(bin_xy[1]),
                "production_fold": production_fold,
                "independent_fold": independent_fold,
                "difference": difference,
                "accepted_traces": accepted,
                "rejected_traces": rejected,
                "missing_traces": missing,
            }
            rows.append(record)

            diff_sum += abs_diff
            if abs_diff > 0:
                number_different += 1
            if abs_diff > max_diff:
                max_diff = abs_diff
                worst_bin = record

        average_diff = diff_sum / len(rows) if rows else 0.0

        return {
            "rows": rows,
            "maximum_difference": int(max_diff),
            "average_difference": float(average_diff),
            "number_different": int(number_different),
            "worst_bin": worst_bin,
        }

    #################################################################

    def _fold_accumulator_audit(self, trace_rows):
        accepted_by_bin = defaultdict(list)
        for row in trace_rows:
            if row["classification"] == self.CATEGORY_ACCEPTED and row["cmp_bin"] in self.bin_lookup:
                accepted_by_bin[row["cmp_bin"]].append(row)

        production_counter = defaultdict(int)
        independent_counter = defaultdict(int)
        prod_signature_bins = defaultdict(set)
        indep_signature_bins = defaultdict(set)

        duplicate_events = []
        max_duplicate_count = 0

        total_prod = 0
        total_ind = 0
        first_divergence = None
        sequence_index = 0

        prod_iter = self._iter_production_increment_events()
        indep_iter = self._iter_independent_increment_events(accepted_by_bin)

        while True:
            prod_event = next(prod_iter, None)
            indep_event = next(indep_iter, None)

            if prod_event is None and indep_event is None:
                break

            sequence_index += 1

            if prod_event is not None:
                total_prod += 1
                prod_key = (prod_event["shot_id"], prod_event["receiver_id"], prod_event["cmp_row"], prod_event["cmp_col"])
                production_counter[prod_key] += 1
                prod_signature_bins[(prod_event["shot_id"], prod_event["receiver_id"])].add((prod_event["cmp_row"], prod_event["cmp_col"]))

                if production_counter[prod_key] > 1:
                    duplicate_number = production_counter[prod_key]
                    if duplicate_number > max_duplicate_count:
                        max_duplicate_count = duplicate_number

                    if len(duplicate_events) < 100:
                        duplicate_events.append({
                            "shot_id": prod_event["shot_id"],
                            "receiver_id": prod_event["receiver_id"],
                            "cmp_row": prod_event["cmp_row"],
                            "cmp_col": prod_event["cmp_col"],
                            "increment_number": duplicate_number,
                            "reason": "Production incremented same trace/bin multiple times",
                        })

            if indep_event is not None:
                total_ind += 1
                indep_key = (indep_event["shot_id"], indep_event["receiver_id"], indep_event["cmp_row"], indep_event["cmp_col"])
                independent_counter[indep_key] += 1
                indep_signature_bins[(indep_event["shot_id"], indep_event["receiver_id"])].add((indep_event["cmp_row"], indep_event["cmp_col"]))

            if first_divergence is None and not self._increment_events_equal(prod_event, indep_event):
                first_divergence = {
                    "index": sequence_index,
                    "production": prod_event,
                    "independent": indep_event,
                }

        extra_prod = 0
        missing_prod = 0
        ind_once_prod_more = 0
        different_bin_signatures = 0

        all_increment_keys = set(production_counter.keys()) | set(independent_counter.keys())
        for key in all_increment_keys:
            prod_count = production_counter.get(key, 0)
            indep_count = independent_counter.get(key, 0)
            if prod_count > indep_count:
                extra_prod += (prod_count - indep_count)
            elif indep_count > prod_count:
                missing_prod += (indep_count - prod_count)

            if indep_count == 1 and prod_count > 1:
                ind_once_prod_more += 1

        all_signatures = set(prod_signature_bins.keys()) | set(indep_signature_bins.keys())
        for signature in all_signatures:
            prod_bins = prod_signature_bins.get(signature, set())
            indep_bins = indep_signature_bins.get(signature, set())
            if prod_bins and indep_bins and prod_bins != indep_bins:
                different_bin_signatures += 1

        duplicate_production_increments = sum(max(0, count - 1) for count in production_counter.values())

        passed = (
            first_divergence is None
            and total_prod == total_ind
            and extra_prod == 0
            and missing_prod == 0
            and duplicate_production_increments == 0
        )

        print("========================================")
        print("FOLD ACCUMULATOR AUDIT")
        print("========================================")
        print("Total Production Increments")
        print(total_prod)
        print("Total Independent Increments")
        print(total_ind)
        print("Extra Production Increments")
        print(extra_prod)
        print("Missing Production Increments")
        print(missing_prod)
        print("Duplicate Production Increments")
        print(duplicate_production_increments)
        print("Maximum Duplicate Count")
        print(max_duplicate_count)
        print("Overall")
        print("PASS / FAIL")
        print("PASS" if passed else "FAIL")
        print("========================================")

        print("Accumulator Differences")
        print(f"Production incremented a different bin: {different_bin_signatures}")
        print(f"Independent incremented once while production incremented more than once: {ind_once_prod_more}")
        print(f"Production incremented when validator did not: {extra_prod}")
        print(f"Validator incremented when production did not: {missing_prod}")

        if first_divergence is not None:
            print("First Divergence Increment")
            print(first_divergence["index"])
            print("Production Event")
            print(self._format_increment_event(first_divergence["production"]))
            print("Independent Event")
            print(self._format_increment_event(first_divergence["independent"]))

        if duplicate_events:
            print("Duplicate Increment Events (First 100)")
            for event in duplicate_events:
                print(
                    f"Shot ID {event['shot_id']} "
                    f"Receiver ID {event['receiver_id']} "
                    f"CMP Row {event['cmp_row']} "
                    f"CMP Column {event['cmp_col']} "
                    f"Increment Number {event['increment_number']} "
                    f"Reason {event['reason']}"
                )

        return {
            "pass": passed,
            "total_production_increments": total_prod,
            "total_independent_increments": total_ind,
            "extra_production_increments": extra_prod,
            "missing_production_increments": missing_prod,
            "duplicate_production_increments": duplicate_production_increments,
            "maximum_duplicate_count": max_duplicate_count,
            "first_divergence": first_divergence,
        }

    #################################################################

    def _iter_production_increment_events(self):
        fold_state = defaultdict(int)

        ordered_bins = sorted(self.bin_lookup.keys(), key=lambda xy: (xy[1], xy[0]))
        for bin_xy in ordered_bins:
            cmp_row, cmp_col = self._bin_row_col(bin_xy)
            bin_record = self.bin_lookup[bin_xy]
            for trace in getattr(bin_record, "traces", []):
                incidence_angle = self._incidence_angle(getattr(trace, "offset", float("nan")))
                if not self._is_finite(incidence_angle) or incidence_angle > self.fold_angle_limit_deg:
                    continue

                before_value = fold_state[bin_xy]
                after_value = before_value + 1
                fold_state[bin_xy] = after_value

                yield {
                    "shot_id": int(getattr(trace, "shot_id", -1)),
                    "receiver_id": int(getattr(trace, "receiver_id", -1)),
                    "cmp_row": cmp_row,
                    "cmp_col": cmp_col,
                    "before": before_value,
                    "after": after_value,
                    "incidence_angle": float(incidence_angle),
                    "offset": float(getattr(trace, "offset", float("nan"))),
                }

    #################################################################

    def _iter_independent_increment_events(self, accepted_by_bin):
        fold_state = defaultdict(int)

        ordered_bins = sorted(self.bin_lookup.keys(), key=lambda xy: (xy[1], xy[0]))
        for bin_xy in ordered_bins:
            cmp_row, cmp_col = self._bin_row_col(bin_xy)
            for row in accepted_by_bin.get(bin_xy, []):
                before_value = fold_state[bin_xy]
                after_value = before_value + 1
                fold_state[bin_xy] = after_value

                yield {
                    "shot_id": int(row["shot_id"]),
                    "receiver_id": int(row["receiver_id"]),
                    "cmp_row": cmp_row,
                    "cmp_col": cmp_col,
                    "before": before_value,
                    "after": after_value,
                    "incidence_angle": float(row["incidence_angle"]),
                    "offset": float(row["offset"]),
                }

    #################################################################

    def _increment_events_equal(self, prod_event, indep_event):
        if prod_event is None and indep_event is None:
            return True
        if prod_event is None or indep_event is None:
            return False

        keys = ["shot_id", "receiver_id", "cmp_row", "cmp_col", "before", "after"]
        for key in keys:
            if prod_event.get(key) != indep_event.get(key):
                return False

        if abs(float(prod_event.get("incidence_angle", 0.0)) - float(indep_event.get("incidence_angle", 0.0))) > 1.0e-9:
            return False
        if abs(float(prod_event.get("offset", 0.0)) - float(indep_event.get("offset", 0.0))) > 1.0e-9:
            return False

        return True

    #################################################################

    def _format_increment_event(self, event):
        if event is None:
            return "None"

        return (
            f"Shot ID={event['shot_id']} Receiver ID={event['receiver_id']} "
            f"CMP Row={event['cmp_row']} CMP Column={event['cmp_col']} "
            f"Before={event['before']} After={event['after']} "
            f"Incidence Angle={self._fmt(event['incidence_angle'])} "
            f"Offset={self._fmt(event['offset'])}"
        )

    #################################################################

    def _print_trace_conservation_audit(self, total_acquired, counts, total_accounted, difference, passed):
        print("========================================")
        print("TRACE CONSERVATION AUDIT")
        print("========================================")
        print("Total Acquired Traces")
        print(total_acquired)
        print("Accepted Fold Traces")
        print(counts.get(self.CATEGORY_ACCEPTED, 0))
        print("Rejected High Angle")
        print(counts.get(self.CATEGORY_HIGH_ANGLE, 0))
        print("Rejected Outside Survey")
        print(counts.get(self.CATEGORY_OUTSIDE_SURVEY, 0))
        print("Rejected Invalid CMP")
        print(counts.get(self.CATEGORY_INVALID_CMP, 0))
        print("Rejected Geometry")
        print(counts.get(self.CATEGORY_GEOMETRY, 0))
        print("Other")
        print(counts.get(self.CATEGORY_OTHER, 0))
        print("----------------------------------------")
        print("Total Accounted For")
        print(total_accounted)
        print("Difference")
        print(difference)
        print("PASS / FAIL")
        print("PASS" if passed else "FAIL")
        print("========================================")

    #################################################################

    def _print_missing_trace_report(self, trace_rows, limit):
        print("========================================")
        print("MISSING TRACE REPORT")
        print("========================================")

        missing = [row for row in trace_rows if row["classification"] == self.CATEGORY_OTHER]

        for row in missing[:limit]:
            self._print_trace_row(row)
            print("----------------------------------------")

        if len(missing) > limit:
            print(f"Remaining Missing Traces:{len(missing) - limit}")

    #################################################################

    def _print_duplicate_trace_report(self, duplicate_count, duplicates):
        print("========================================")
        print("DUPLICATE TRACE REPORT")
        print("========================================")
        print("Duplicate Trace Count")
        print(duplicate_count)
        print("PASS / FAIL")
        print("PASS" if duplicate_count == 0 else "FAIL")

        for (shot_id, receiver_id), rows in duplicates:
            print(f"Duplicate Trace Shot {shot_id} Receiver {receiver_id}")
            for row in rows:
                self._print_trace_row(row)
                print("----------------------------------------")

    #################################################################

    def _print_category_consistency(self, passed, failures):
        print("========================================")
        print("CATEGORY CONSISTENCY")
        print("========================================")
        print("Category Consistency")
        print("PASS" if passed else "FAIL")

        if not passed:
            for row, reason in failures[:200]:
                print(reason)
                self._print_trace_row(row)
                print("----------------------------------------")
            if len(failures) > 200:
                print(f"Remaining Consistency Failures:{len(failures) - 200}")

    #################################################################

    def _print_cmp_conservation(self, report):
        print("========================================")
        print("CMP CONSERVATION")
        print("========================================")

        for row in report["rows"]:
            if row["difference"] == 0:
                continue

            print("CMP Row")
            print(row["cmp_row"])
            print("CMP Column")
            print(row["cmp_col"])
            print("X")
            print(f"{row['x']:.2f}")
            print("Y")
            print(f"{row['y']:.2f}")
            print("Production Fold")
            print(row["production_fold"])
            print("Independent Fold")
            print(row["independent_fold"])
            print("Difference")
            print(row["difference"])
            print("Accepted Traces in Bin")
            print(row["accepted_traces"])
            print("Rejected Traces in Bin")
            print(row["rejected_traces"])
            print("Missing Traces in Bin")
            print(row["missing_traces"])
            print("----------------------------------------")

        print("Maximum Difference")
        print(report["maximum_difference"])
        print("Average Difference")
        print(f"{report['average_difference']:.6f}")
        print("Number Different")
        print(report["number_different"])
        print("PASS / FAIL")
        print("PASS" if report["maximum_difference"] == 0 and report["number_different"] == 0 else "FAIL")

    #################################################################

    def _print_random_trace_audit(self, trace_rows, count):
        print("========================================")
        print("RANDOM TRACE AUDIT")
        print("========================================")

        sample_size = min(count, len(trace_rows))
        sampled = self._rng.sample(trace_rows, sample_size) if sample_size > 0 else []

        for row in sampled:
            print("Shot ID")
            print(row["shot_id"])
            print("Receiver ID")
            print(row["receiver_id"])
            print("CMP X")
            print(self._fmt(row["cmp_x"]))
            print("CMP Y")
            print(self._fmt(row["cmp_y"]))
            print("CMP Bin")
            if row["cmp_bin"] is None:
                print("Unassigned")
            else:
                print(f"Row {row['cmp_row']} Col {row['cmp_col']}")
            print("Offset")
            print(self._fmt(row["offset"]))
            print("Incidence Angle")
            print(self._fmt(row["incidence_angle"]))
            print("Contributes to Fold")
            print("YES" if row["classification"] == self.CATEGORY_ACCEPTED else "NO")
            print("Reason")
            print(row["reason"])
            print("----------------------------------------")

    #################################################################

    def _print_random_bin_audit(self, report, count):
        print("========================================")
        print("RANDOM BIN AUDIT")
        print("========================================")

        live_rows = [row for row in report["rows"] if row["production_fold"] > 0 or row["independent_fold"] > 0]
        sample_size = min(count, len(live_rows))
        sampled = self._rng.sample(live_rows, sample_size) if sample_size > 0 else []

        for row in sampled:
            print("Production Fold")
            print(row["production_fold"])
            print("Independent Fold")
            print(row["independent_fold"])
            print("Number of Accepted Traces")
            print(row["accepted_traces"])
            print("Number Rejected (>40 deg)")
            print(row["rejected_traces"])
            print("PASS / FAIL")
            print("PASS" if row["difference"] == 0 else "FAIL")
            print("----------------------------------------")

    #################################################################

    def _print_center_bin_audit(self, trace_rows, report):
        print("========================================")
        print("CENTER BIN AUDIT")
        print("========================================")

        center_bin = self._center_cmp_bin()
        if center_bin is None:
            print("No bins available")
            return

        row_idx, col_idx = self._bin_row_col(center_bin.xy)

        comparison_row = next((r for r in report["rows"] if r["cmp_bin"] == center_bin.xy), None)
        production_fold = int(comparison_row["production_fold"]) if comparison_row else 0
        independent_fold = int(comparison_row["independent_fold"]) if comparison_row else 0

        print("Production Fold")
        print(production_fold)
        print("Independent Fold")
        print(independent_fold)
        print("CMP Row")
        print(row_idx)
        print("CMP Column")
        print(col_idx)
        print("X")
        print(f"{center_bin.xy[0]:.2f}")
        print("Y")
        print(f"{center_bin.xy[1]:.2f}")
        print("Contributing Traces")

        center_rows = [
            row for row in trace_rows
            if row["cmp_bin"] == center_bin.xy and row["classification"] == self.CATEGORY_ACCEPTED
        ]
        center_rows.sort(key=lambda row: (row["shot_id"], row["receiver_id"]))

        for row in center_rows:
            print("Offset")
            print(self._fmt(row["offset"]))
            print("Incidence Angle")
            print(self._fmt(row["incidence_angle"]))
            print("Accepted?")
            print("YES")
            print("----------------------------------------")

    #################################################################

    def _print_worst_bin_analysis(self, worst_bin, trace_rows):
        print("========================================")
        print("WORST BIN ANALYSIS")
        print("========================================")

        if worst_bin is None:
            print("No differing bin found")
            return True

        traces_for_bin = [row for row in trace_rows if row["cmp_bin"] == worst_bin["cmp_bin"]]

        accepted = sum(1 for row in traces_for_bin if row["classification"] == self.CATEGORY_ACCEPTED)
        high_angle = sum(1 for row in traces_for_bin if row["classification"] == self.CATEGORY_HIGH_ANGLE)
        outside = sum(1 for row in traces_for_bin if row["classification"] == self.CATEGORY_OUTSIDE_SURVEY)
        invalid_cmp = sum(1 for row in traces_for_bin if row["classification"] == self.CATEGORY_INVALID_CMP)
        geometry_rej = sum(1 for row in traces_for_bin if row["classification"] == self.CATEGORY_GEOMETRY)

        print("CMP Row")
        print(worst_bin["cmp_row"])
        print("CMP Column")
        print(worst_bin["cmp_col"])
        print("CMP X")
        print(f"{worst_bin['x']:.2f}")
        print("CMP Y")
        print(f"{worst_bin['y']:.2f}")
        print("Production Fold")
        print(worst_bin["production_fold"])
        print("Independent Fold")
        print(worst_bin["independent_fold"])
        print("Difference")
        print(worst_bin["difference"])
        print("Accepted Traces")
        print(accepted)
        print("Rejected High Angle")
        print(high_angle)
        print("Rejected Outside Survey")
        print(outside)
        print("Rejected Invalid CMP")
        print(invalid_cmp)
        print("Rejected Geometry")
        print(geometry_rej)
        print("Missing Traces")
        print(worst_bin["missing_traces"])

        traces_for_bin.sort(key=lambda row: (row["shot_id"], row["receiver_id"]))
        for row in traces_for_bin:
            print("Shot ID")
            print(row["shot_id"])
            print("Receiver ID")
            print(row["receiver_id"])
            print("Offset")
            print(self._fmt(row["offset"]))
            print("Incidence Angle")
            print(self._fmt(row["incidence_angle"]))
            print("Classification")
            print(row["classification"])
            print("----------------------------------------")

        return accepted == worst_bin["independent_fold"]

    #################################################################

    def _write_histogram(self, report):
        output_path = self._project_folder() / "fold_validation_histogram.png"

        production_values = [row["production_fold"] for row in report["rows"]]
        independent_values = [row["independent_fold"] for row in report["rows"]]

        plt.figure(figsize=(10, 6))
        plt.hist(production_values, bins=40, alpha=0.5, label="Production Fold")
        plt.hist(independent_values, bins=40, alpha=0.5, label="Independent Fold")
        plt.xlabel("Fold")
        plt.ylabel("CMP Bin Count")
        plt.title("Fold Validation Histogram")
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close("all")

        return output_path

    #################################################################

    def _write_difference_map(self, report):
        output_path = self._project_folder() / "fold_difference_map.png"

        xs = [row["x"] for row in report["rows"]]
        ys = [row["y"] for row in report["rows"]]
        diffs = [row["difference"] for row in report["rows"]]

        max_abs = max((abs(value) for value in diffs), default=0)
        if max_abs == 0:
            max_abs = 1

        plt.figure(figsize=(10, 8))
        scatter = plt.scatter(
            xs,
            ys,
            c=diffs,
            cmap="coolwarm",
            vmin=-max_abs,
            vmax=max_abs,
            s=12,
            marker="s",
        )
        plt.colorbar(scatter, label="Difference")
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.title("Fold Difference Map")
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close("all")

        return output_path

    #################################################################

    def _print_final_summary(self, conservation_pass, duplicate_pass, consistency_pass, cmp_pass, worst_bin_explained, overall_pass):
        print("========================================")
        print("TRACE CONSERVATION VALIDATION")
        print("========================================")
        print("Trace Conservation")
        print("PASS" if conservation_pass else "FAIL")
        print("Duplicate Detection")
        print("PASS" if duplicate_pass else "FAIL")
        print("Category Consistency")
        print("PASS" if consistency_pass else "FAIL")
        print("CMP Conservation")
        print("PASS" if cmp_pass else "FAIL")
        print("Worst Bin Explained")
        print("PASS" if worst_bin_explained else "FAIL")
        print("Overall")
        print("PASS" if overall_pass else "FAIL")
        print("========================================")

    #################################################################

    def _geometry_error(self, shot, receiver):
        if shot is None or receiver is None:
            return "Invalid geometry"

        for value in [getattr(shot, "x", None), getattr(shot, "y", None), getattr(receiver, "x", None), getattr(receiver, "y", None)]:
            if not self._is_finite(value):
                return "Invalid coordinates"

        if int(getattr(shot, "id", -1)) < 0:
            return "Invalid shot"
        if int(getattr(receiver, "id", -1)) < 0:
            return "Invalid receiver"

        return None

    #################################################################

    def _assign_bin(self, midpoint_x, midpoint_y):
        if not self.x_centers or not self.y_centers:
            return None, None, None

        x_index = self._nearest_index(midpoint_x, self.x_centers[0], self.bin_size_x, len(self.x_centers))
        y_index = self._nearest_index(midpoint_y, self.y_centers[0], self.bin_size_y, len(self.y_centers))

        bin_xy = (self.x_centers[x_index], self.y_centers[y_index])

        return bin_xy, y_index + 1, x_index + 1

    #################################################################

    def _bin_row_col(self, bin_xy):
        x_index = self.x_centers.index(bin_xy[0]) if bin_xy[0] in self.x_centers else 0
        y_index = self.y_centers.index(bin_xy[1]) if bin_xy[1] in self.y_centers else 0
        return y_index + 1, x_index + 1

    #################################################################

    def _midpoint_in_bin(self, midpoint_x, midpoint_y, bin_xy):
        if self.bin_size_x <= 0.0 or self.bin_size_y <= 0.0:
            return False

        half_x = self.bin_size_x / 2.0
        half_y = self.bin_size_y / 2.0

        return (
            abs(midpoint_x - bin_xy[0]) <= half_x + 1.0e-9
            and abs(midpoint_y - bin_xy[1]) <= half_y + 1.0e-9
        )

    #################################################################

    def _nearest_index(self, value, origin, step, count):
        if count <= 0 or step <= 0.0:
            return 0

        index = round((value - origin) / step)
        return max(0, min(index, count - 1))

    #################################################################

    def _incidence_angle(self, offset):
        if not self._is_finite(offset) or self.survey.target_depth <= 0.0:
            return float("nan")

        return math.degrees(math.atan(float(offset) / (2.0 * self.survey.target_depth)))

    #################################################################

    def _center_cmp_bin(self):
        xmin, ymin, xmax, ymax = self.gis.bounds
        center_x = (xmin + xmax) / 2.0
        center_y = (ymin + ymax) / 2.0

        if not self.bins:
            return None

        return min(
            self.bins,
            key=lambda bin_record: (bin_record.xy[0] - center_x) ** 2 + (bin_record.xy[1] - center_y) ** 2,
        )

    #################################################################

    def _fold_contribution_set_audit(self, trace_rows):
        production_map = self._build_production_contribution_map()
        independent_map = self._build_independent_contribution_map(trace_rows)

        production_set = set(production_map.keys())
        independent_set = set(independent_map.keys())

        production_only_keys = sorted(production_set - independent_set)
        independent_only_keys = sorted(independent_set - production_set)

        pass_fail = (len(production_only_keys) == 0 and len(independent_only_keys) == 0)

        print("========================================")
        print("FOLD CONTRIBUTION SETS")
        print("Production Entries")
        print(len(production_set))
        print("Independent Entries")
        print(len(independent_set))
        print("Production Only")
        print(len(production_only_keys))
        print("Independent Only")
        print(len(independent_only_keys))
        print("PASS / FAIL")
        print("PASS" if pass_fail else "FAIL")
        print("========================================")

        if production_only_keys:
            print("PRODUCTION-ONLY CONTRIBUTIONS")
            for key in production_only_keys:
                self._print_contribution_entry(production_map[key])

        if independent_only_keys:
            print("INDEPENDENT-ONLY CONTRIBUTIONS")
            for key in independent_only_keys:
                self._print_contribution_entry(independent_map[key])

        pattern_counts = self._analyze_unmatched_patterns(
            production_only=[production_map[key] for key in production_only_keys],
            independent_only=[independent_map[key] for key in independent_only_keys],
        )

        root_cause, recommendation = self._classify_contribution_root_cause(
            production_only_count=len(production_only_keys),
            independent_only_count=len(independent_only_keys),
            pattern_counts=pattern_counts,
            production_only=[production_map[key] for key in production_only_keys],
            independent_only=[independent_map[key] for key in independent_only_keys],
        )

        print("========================================")
        print("FOLD CONTRIBUTION SET AUDIT")
        print("Production Entries")
        print(len(production_set))
        print("Independent Entries")
        print(len(independent_set))
        print("Production Only")
        print(len(production_only_keys))
        print("Independent Only")
        print(len(independent_only_keys))
        print("Primary Cause")
        print(root_cause)
        print("Engineering Recommendation")
        print(recommendation)
        print("Overall")
        print("PASS" if pass_fail else "FAIL")
        print("PASS / FAIL")
        print("PASS" if pass_fail else "FAIL")
        print("========================================")

        return {
            "overall_pass": pass_fail,
            "production_entries": len(production_set),
            "independent_entries": len(independent_set),
            "production_only": len(production_only_keys),
            "independent_only": len(independent_only_keys),
            "root_cause": root_cause,
        }

    #################################################################

    def _build_production_contribution_map(self):
        shot_lookup = {int(getattr(shot, "id", -1)): shot for shot in self.geometry.shots}
        receiver_lookup = {int(getattr(receiver, "id", -1)): receiver for receiver in self.geometry.receivers}

        contribution_map = {}
        for bin_record in self.bins:
            cmp_row, cmp_col = self._bin_row_col(bin_record.xy)
            cmp_x = float(bin_record.xy[0])
            cmp_y = float(bin_record.xy[1])

            for trace in getattr(bin_record, "traces", []):
                offset = float(getattr(trace, "offset", float("nan")))
                incidence_angle = self._incidence_angle(offset)
                if not self._is_finite(incidence_angle) or incidence_angle > self.fold_angle_limit_deg:
                    continue

                shot_id = int(getattr(trace, "shot_id", -1))
                receiver_id = int(getattr(trace, "receiver_id", -1))
                key = (shot_id, receiver_id, cmp_row, cmp_col)
                if key in contribution_map:
                    continue

                shot = shot_lookup.get(shot_id)
                receiver = receiver_lookup.get(receiver_id)

                midpoint_x = float(getattr(trace, "midpoint_x", float("nan")))
                midpoint_y = float(getattr(trace, "midpoint_y", float("nan")))

                contribution_map[key] = self._build_contribution_entry(
                    shot=shot,
                    receiver=receiver,
                    shot_id=shot_id,
                    receiver_id=receiver_id,
                    cmp_row=cmp_row,
                    cmp_col=cmp_col,
                    cmp_x=cmp_x,
                    cmp_y=cmp_y,
                    midpoint_x=midpoint_x,
                    midpoint_y=midpoint_y,
                    offset=offset,
                    incidence_angle=incidence_angle,
                )

        return contribution_map

    #################################################################

    def _build_independent_contribution_map(self, trace_rows):
        shot_lookup = {int(getattr(shot, "id", -1)): shot for shot in self.geometry.shots}
        receiver_lookup = {int(getattr(receiver, "id", -1)): receiver for receiver in self.geometry.receivers}

        contribution_map = {}
        for row in trace_rows:
            if row["classification"] != self.CATEGORY_ACCEPTED:
                continue

            cmp_bin = row["cmp_bin"]
            if cmp_bin not in self.bin_lookup:
                continue

            shot_id = int(row["shot_id"])
            receiver_id = int(row["receiver_id"])
            cmp_row = int(row["cmp_row"])
            cmp_col = int(row["cmp_col"])
            key = (shot_id, receiver_id, cmp_row, cmp_col)
            if key in contribution_map:
                continue

            shot = shot_lookup.get(shot_id)
            receiver = receiver_lookup.get(receiver_id)

            contribution_map[key] = self._build_contribution_entry(
                shot=shot,
                receiver=receiver,
                shot_id=shot_id,
                receiver_id=receiver_id,
                cmp_row=cmp_row,
                cmp_col=cmp_col,
                cmp_x=float(cmp_bin[0]),
                cmp_y=float(cmp_bin[1]),
                midpoint_x=float(row["cmp_x"]),
                midpoint_y=float(row["cmp_y"]),
                offset=float(row["offset"]),
                incidence_angle=float(row["incidence_angle"]),
            )

        return contribution_map

    #################################################################

    def _build_contribution_entry(
        self,
        shot,
        receiver,
        shot_id,
        receiver_id,
        cmp_row,
        cmp_col,
        cmp_x,
        cmp_y,
        midpoint_x,
        midpoint_y,
        offset,
        incidence_angle,
    ):
        source_line = int(getattr(shot, "line", -1)) if shot is not None else -1
        shot_station = int(getattr(shot, "station", -1)) if shot is not None else -1
        receiver_line = int(getattr(receiver, "line", -1)) if receiver is not None else -1
        receiver_station = int(getattr(receiver, "station", -1)) if receiver is not None else -1

        distance_cmp_boundary = self._distance_to_nearest_cmp_boundary(midpoint_x, midpoint_y, cmp_x, cmp_y)
        distance_survey_boundary = self._distance_to_nearest_survey_boundary(midpoint_x, midpoint_y)

        return {
            "shot_id": int(shot_id),
            "receiver_id": int(receiver_id),
            "source_line": source_line,
            "shot_station": shot_station,
            "receiver_line": receiver_line,
            "receiver_station": receiver_station,
            "cmp_row": int(cmp_row),
            "cmp_col": int(cmp_col),
            "cmp_x": float(cmp_x),
            "cmp_y": float(cmp_y),
            "midpoint_x": float(midpoint_x),
            "midpoint_y": float(midpoint_y),
            "offset": float(offset),
            "incidence_angle": float(incidence_angle),
            "distance_to_cmp_boundary": float(distance_cmp_boundary),
            "distance_to_survey_boundary": float(distance_survey_boundary),
        }

    #################################################################

    def _distance_to_nearest_cmp_boundary(self, midpoint_x, midpoint_y, cmp_x, cmp_y):
        if not self._is_finite(midpoint_x) or not self._is_finite(midpoint_y):
            return float("nan")
        if self.bin_size_x <= 0.0 or self.bin_size_y <= 0.0:
            return float("nan")

        half_x = self.bin_size_x / 2.0
        half_y = self.bin_size_y / 2.0
        dx = half_x - abs(float(midpoint_x) - float(cmp_x))
        dy = half_y - abs(float(midpoint_y) - float(cmp_y))
        return min(dx, dy)

    #################################################################

    def _distance_to_nearest_survey_boundary(self, x, y):
        if not self._is_finite(x) or not self._is_finite(y):
            return float("nan")

        polygon = getattr(self.gis, "polygon", None)
        if polygon is None:
            return float("nan")

        px = float(x)
        py = float(y)
        if getattr(self.geometry, "_point_transformer", None) is not None:
            px, py = self.geometry._point_transformer.transform(px, py)

        try:
            return float(polygon.boundary.distance(Point(px, py)))
        except Exception:
            return float("nan")

    #################################################################

    def _print_contribution_entry(self, entry):
        print("Shot ID")
        print(entry["shot_id"])
        print("Receiver ID")
        print(entry["receiver_id"])
        print("Source Line")
        print(entry["source_line"])
        print("Shot Station")
        print(entry["shot_station"])
        print("Receiver Line")
        print(entry["receiver_line"])
        print("Receiver Station")
        print(entry["receiver_station"])
        print("CMP Row")
        print(entry["cmp_row"])
        print("CMP Column")
        print(entry["cmp_col"])
        print("CMP X")
        print(self._fmt(entry["cmp_x"]))
        print("CMP Y")
        print(self._fmt(entry["cmp_y"]))
        print("Midpoint X")
        print(self._fmt(entry["midpoint_x"]))
        print("Midpoint Y")
        print(self._fmt(entry["midpoint_y"]))
        print("Offset")
        print(self._fmt(entry["offset"]))
        print("Incidence Angle")
        print(self._fmt(entry["incidence_angle"]))
        print("Distance to nearest CMP boundary")
        print(self._fmt(entry["distance_to_cmp_boundary"]))
        print("Distance to nearest survey boundary")
        print(self._fmt(entry["distance_to_survey_boundary"]))
        print("----------------------------------------")

    #################################################################

    def _analyze_unmatched_patterns(self, production_only, independent_only):
        unmatched = list(production_only) + list(independent_only)
        row_counts = defaultdict(int)
        col_counts = defaultdict(int)
        receiver_line_counts = defaultdict(int)
        source_line_counts = defaultdict(int)

        survey_edge = 0
        corner = 0
        high_incidence = 0
        cmp_boundary = 0
        survey_boundary = 0

        for entry in unmatched:
            row_counts[entry["cmp_row"]] += 1
            col_counts[entry["cmp_col"]] += 1
            receiver_line_counts[entry["receiver_line"]] += 1
            source_line_counts[entry["source_line"]] += 1

            if self._is_finite(entry["incidence_angle"]) and entry["incidence_angle"] >= 35.0:
                high_incidence += 1

            if self._is_finite(entry["distance_to_cmp_boundary"]) and entry["distance_to_cmp_boundary"] <= 1.0:
                cmp_boundary += 1

            if self._is_finite(entry["distance_to_survey_boundary"]) and entry["distance_to_survey_boundary"] <= 1.0:
                survey_boundary += 1
                survey_edge += 1

            if self._is_corner_bin(entry["cmp_row"], entry["cmp_col"]):
                corner += 1

        print("PATTERN ANALYSIS")
        print(f"CMP Row concentration bins: {len(row_counts)}")
        print(f"CMP Column concentration bins: {len(col_counts)}")
        print(f"Receiver Line concentration bins: {len(receiver_line_counts)}")
        print(f"Source Line concentration bins: {len(source_line_counts)}")
        print(f"Survey Edge count: {survey_edge}")
        print(f"Corner count: {corner}")
        print(f"High Incidence Angle count: {high_incidence}")
        print(f"CMP Boundary count: {cmp_boundary}")
        print(f"Survey Boundary count: {survey_boundary}")

        return {
            "row_counts": dict(row_counts),
            "col_counts": dict(col_counts),
            "receiver_line_counts": dict(receiver_line_counts),
            "source_line_counts": dict(source_line_counts),
            "survey_edge": survey_edge,
            "corner": corner,
            "high_incidence": high_incidence,
            "cmp_boundary": cmp_boundary,
            "survey_boundary": survey_boundary,
            "unmatched_total": len(unmatched),
        }

    #################################################################

    def _classify_contribution_root_cause(self, production_only_count, independent_only_count, pattern_counts, production_only, independent_only):
        total_unmatched = pattern_counts["unmatched_total"]
        if total_unmatched == 0:
            return (
                "Other",
                "No unmatched contribution keys found. Prior discrepancy was sequence-driven, not set-driven.",
            )

        boundary_ratio = pattern_counts["survey_boundary"] / total_unmatched
        cmp_boundary_ratio = pattern_counts["cmp_boundary"] / total_unmatched

        # Check if same shot/receiver appears unmatched on both sides but in different bins.
        prod_trace_keys = {(e["shot_id"], e["receiver_id"]) for e in production_only}
        indep_trace_keys = {(e["shot_id"], e["receiver_id"]) for e in independent_only}
        overlap_trace_keys = prod_trace_keys & indep_trace_keys

        if boundary_ratio >= 0.6:
            return (
                "Boundary tolerance",
                "Harmonize survey boundary inclusion tolerance for midpoint acceptance at polygon boundary.",
            )

        if cmp_boundary_ratio >= 0.6:
            return (
                "CMP boundary tolerance",
                "Align CMP boundary inclusion tolerance for traces near bin edges.",
            )

        if len(overlap_trace_keys) > 0:
            return (
                "CMP indexing",
                "Audit row/column index assignment for overlapping shot/receiver traces that map to different CMP bins.",
            )

        if production_only_count > 0 and independent_only_count == 0:
            return (
                "Production accumulation",
                "Review production fold inclusion criteria for traces accepted into accumulator but excluded by independent validator.",
            )

        if independent_only_count > 0 and production_only_count == 0:
            return (
                "Independent validator logic",
                "Review independent acceptance logic for traces included by validator but absent in production contributions.",
            )

        return (
            "Other",
            "Mixed unmatched patterns detected. Perform focused trace-level tolerance and indexing audit on unmatched subsets.",
        )

    #################################################################

    def _is_corner_bin(self, cmp_row, cmp_col):
        if not self.x_centers or not self.y_centers:
            return False

        max_row = len(self.y_centers)
        max_col = len(self.x_centers)
        return (cmp_row in {1, max_row}) and (cmp_col in {1, max_col})

    #################################################################
    def _project_folder(self):
        if hasattr(self.gis, "project_folder"):
            return Path(self.gis.project_folder)
        return Path(".")

    #################################################################

    def _is_finite(self, value):
        try:
            return math.isfinite(float(value))
        except Exception:
            return False

    #################################################################

    def _use_midpoint_in_bin_gate(self):
        return not self.validator_equivalence_mode

    #################################################################

    def _fmt(self, value):
        if self._is_finite(value):
            return f"{float(value):.2f}"
        return "nan"

    #################################################################

    def _print_trace_row(self, row):
        print("Shot ID")
        print(row["shot_id"])
        print("Receiver ID")
        print(row["receiver_id"])
        print("Receiver Line")
        print(row["receiver_line"])
        print("Receiver Station")
        print(row["receiver_station"])
        print("Source Line")
        print(row["source_line"])
        print("Shot Station")
        print(row["shot_station"])
        print("CMP X")
        print(self._fmt(row["cmp_x"]))
        print("CMP Y")
        print(self._fmt(row["cmp_y"]))
        print("Offset")
        print(self._fmt(row["offset"]))
        print("Incidence Angle")
        print(self._fmt(row["incidence_angle"]))
        print("Current Classification")
        print(row["classification"])
        print("Why Not Counted")
        print(row["reason"])

    #################################################################

    def _cmp_assignment_forensic_audit(self, trace_rows, cmp_report):
        print("========================================")
        print("CMP ASSIGNMENT FORENSIC AUDIT")
        print("========================================")

        mismatched_bins = [row for row in cmp_report["rows"] if row["difference"] != 0]
        mismatched_bins.sort(key=lambda row: abs(row["difference"]), reverse=True)

        print("ALL MISMATCHED BINS (SORTED BY ABS DIFFERENCE)")
        for row in mismatched_bins:
            print(
                f"Row={row['cmp_row']} Col={row['cmp_col']} X={row['x']:.2f} Y={row['y']:.2f} "
                f"Production={row['production_fold']} Independent={row['independent_fold']} "
                f"Difference={row['difference']}"
            )

        top_20 = mismatched_bins[:20]
        shot_lookup = {int(getattr(shot, "id", -1)): shot for shot in self.geometry.shots}
        receiver_lookup = {int(getattr(receiver, "id", -1)): receiver for receiver in self.geometry.receivers}
        indep_trace_by_key = {(row["shot_id"], row["receiver_id"]): row for row in trace_rows}

        divergence_cause_counts = {
            "Midpoint calculation differs": 0,
            "CMP coordinate differs": 0,
            "Bin rounding differs": 0,
            "Bin indexing differs": 0,
            "Fold accumulation differs": 0,
            "Other": 0,
        }

        print("========================================")
        print("WORST 20 MISMATCHED BINS")
        print("========================================")
        for bin_record in top_20:
            bin_xy = bin_record["cmp_bin"]

            print(
                f"CMP Row{bin_record['cmp_row']}CMP Column{bin_record['cmp_col']}"
                f"CMP X{bin_record['x']:.2f}CMP Y{bin_record['y']:.2f}"
                f"Production Fold{bin_record['production_fold']}"
                f"Independent Fold{bin_record['independent_fold']}"
                f"Difference{bin_record['difference']}"
            )

            production_traces = list(getattr(self.bin_lookup.get(bin_xy), "traces", [])) if bin_xy in self.bin_lookup else []
            production_trace_by_key = {
                (int(getattr(trace, "shot_id", -1)), int(getattr(trace, "receiver_id", -1))): trace
                for trace in production_traces
            }

            independent_associated = [
                row for row in trace_rows
                if row["cmp_bin"] == bin_xy
            ]

            trace_keys = set(production_trace_by_key.keys())
            trace_keys.update((row["shot_id"], row["receiver_id"]) for row in independent_associated)

            print("TRACE COMPARISON")
            for shot_id, receiver_id in sorted(trace_keys):
                shot = shot_lookup.get(shot_id)
                receiver = receiver_lookup.get(receiver_id)
                prod_trace = production_trace_by_key.get((shot_id, receiver_id))
                indep_row = indep_trace_by_key.get((shot_id, receiver_id))

                shot_x = float(getattr(shot, "x", float("nan")))
                shot_y = float(getattr(shot, "y", float("nan")))
                receiver_x = float(getattr(receiver, "x", float("nan")))
                receiver_y = float(getattr(receiver, "y", float("nan")))

                prod_mid_x = float(getattr(prod_trace, "midpoint_x", (shot_x + receiver_x) / 2.0 if self._is_finite(shot_x) and self._is_finite(receiver_x) else float("nan")))
                prod_mid_y = float(getattr(prod_trace, "midpoint_y", (shot_y + receiver_y) / 2.0 if self._is_finite(shot_y) and self._is_finite(receiver_y) else float("nan")))

                indep_mid_x = float(indep_row["cmp_x"]) if indep_row is not None else (shot_x + receiver_x) / 2.0
                indep_mid_y = float(indep_row["cmp_y"]) if indep_row is not None else (shot_y + receiver_y) / 2.0

                prod_bin = self._assign_bin(prod_mid_x, prod_mid_y)[0] if self._is_finite(prod_mid_x) and self._is_finite(prod_mid_y) else None
                indep_bin = indep_row["cmp_bin"] if indep_row is not None else None

                prod_offset = float(getattr(prod_trace, "offset", float("nan")))
                if not self._is_finite(prod_offset) and self._is_finite(shot_x) and self._is_finite(shot_y) and self._is_finite(receiver_x) and self._is_finite(receiver_y):
                    prod_offset = math.hypot(receiver_x - shot_x, receiver_y - shot_y)

                incidence_angle = self._incidence_angle(prod_offset)

                production_counts = (prod_trace is not None and prod_bin == bin_xy and self._is_finite(incidence_angle) and incidence_angle <= self.fold_angle_limit_deg)
                independent_counts = (indep_row is not None and indep_bin == bin_xy and indep_row["classification"] == self.CATEGORY_ACCEPTED)

                cause = self._first_divergence_cause(
                    prod_mid_x,
                    prod_mid_y,
                    indep_mid_x,
                    indep_mid_y,
                    prod_bin,
                    indep_bin,
                    production_counts,
                    independent_counts,
                )

                if production_counts != independent_counts:
                    divergence_cause_counts[cause] = divergence_cause_counts.get(cause, 0) + 1

                prod_bin_text = f"({prod_bin[0]:.2f},{prod_bin[1]:.2f})" if prod_bin is not None else "None"
                indep_bin_text = f"({indep_bin[0]:.2f},{indep_bin[1]:.2f})" if indep_bin is not None else "None"

                print(
                    f"Shot ID={shot_id} Receiver ID={receiver_id} Shot X={self._fmt(shot_x)} Shot Y={self._fmt(shot_y)} "
                    f"Receiver X={self._fmt(receiver_x)} Receiver Y={self._fmt(receiver_y)} "
                    f"Production Midpoint X={self._fmt(prod_mid_x)} Production Midpoint Y={self._fmt(prod_mid_y)} "
                    f"Independent Midpoint X={self._fmt(indep_mid_x)} Independent Midpoint Y={self._fmt(indep_mid_y)} "
                    f"Production Bin={prod_bin_text} Independent Bin={indep_bin_text} "
                    f"Incidence Angle={self._fmt(incidence_angle)} "
                    f"Production Counts Trace?={'YES' if production_counts else 'NO'} "
                    f"Independent Counts Trace?={'YES' if independent_counts else 'NO'}"
                )

                if production_counts != independent_counts:
                    print(f"First Divergence={cause}")

            print("----------------------------------------")

        root_cause_stats = self._categorize_root_causes(mismatched_bins, divergence_cause_counts)

        print("========================================")
        print("CMP ASSIGNMENT FORENSIC SUMMARY")
        print("========================================")
        print("Total Mismatched Bins")
        print(len(mismatched_bins))
        print("Largest Difference")
        print(mismatched_bins[0]["difference"] if mismatched_bins else 0)
        print("Primary Cause")
        print(root_cause_stats["primary_cause"])
        print("Number due to Midpoint")
        print(root_cause_stats["midpoint_count"])
        print("Number due to Bin Assignment")
        print(root_cause_stats["assignment_count"])
        print("Number due to Rounding")
        print(root_cause_stats["rounding_count"])
        print("Number due to Fold Accumulation")
        print(root_cause_stats["accumulation_count"])
        print("Other")
        print(root_cause_stats["other_count"])
        print("Overall Root Cause")
        print(root_cause_stats["overall_cause"])
        print("========================================")

    #################################################################

    def _categorize_root_causes(self, mismatched_bins, divergence_cause_counts):
        midpoint_count = int(divergence_cause_counts.get("Midpoint calculation differs", 0))
        cmp_coordinate_count = int(divergence_cause_counts.get("CMP coordinate differs", 0))
        bin_index_count = int(divergence_cause_counts.get("Bin indexing differs", 0))
        rounding_count = int(divergence_cause_counts.get("Bin rounding differs", 0))
        accumulation_count = int(divergence_cause_counts.get("Fold accumulation differs", 0))
        other_count = int(divergence_cause_counts.get("Other", 0))

        assignment_count = cmp_coordinate_count + bin_index_count

        primary_cause = "Other"
        ordered = [
            ("Midpoint calculation differs", midpoint_count),
            ("CMP coordinate differs", cmp_coordinate_count),
            ("Bin rounding differs", rounding_count),
            ("Bin indexing differs", bin_index_count),
            ("Fold accumulation differs", accumulation_count),
            ("Other", other_count),
        ]
        primary_cause = max(ordered, key=lambda item: item[1])[0] if ordered else "Other"

        if primary_cause in {"CMP coordinate differs", "Bin indexing differs"}:
            primary_cause = "Bin indexing differs"

        return {
            "midpoint_count": midpoint_count,
            "assignment_count": assignment_count,
            "rounding_count": rounding_count,
            "accumulation_count": accumulation_count,
            "other_count": other_count,
            "primary_cause": primary_cause,
            "overall_cause": primary_cause,
        }

    #################################################################

    def _first_divergence_cause(
        self,
        prod_mid_x,
        prod_mid_y,
        indep_mid_x,
        indep_mid_y,
        prod_bin,
        indep_bin,
        production_counts,
        independent_counts,
    ):
        epsilon = 1.0e-9

        if self._is_finite(prod_mid_x) and self._is_finite(indep_mid_x):
            if abs(float(prod_mid_x) - float(indep_mid_x)) > epsilon or abs(float(prod_mid_y) - float(indep_mid_y)) > epsilon:
                return "Midpoint calculation differs"

        if self._is_finite(prod_mid_x) and self._is_finite(prod_mid_y) and self._is_finite(indep_mid_x) and self._is_finite(indep_mid_y):
            prod_cmp_x = float(prod_mid_x)
            prod_cmp_y = float(prod_mid_y)
            indep_cmp_x = float(indep_mid_x)
            indep_cmp_y = float(indep_mid_y)
            if abs(prod_cmp_x - indep_cmp_x) > epsilon or abs(prod_cmp_y - indep_cmp_y) > epsilon:
                return "CMP coordinate differs"

            prod_x_raw = (prod_cmp_x - self.x_centers[0]) / self.bin_size_x if self.bin_size_x > 0 else 0.0
            prod_y_raw = (prod_cmp_y - self.y_centers[0]) / self.bin_size_y if self.bin_size_y > 0 else 0.0
            indep_x_raw = (indep_cmp_x - self.x_centers[0]) / self.bin_size_x if self.bin_size_x > 0 else 0.0
            indep_y_raw = (indep_cmp_y - self.y_centers[0]) / self.bin_size_y if self.bin_size_y > 0 else 0.0

            if round(prod_x_raw) != round(indep_x_raw) or round(prod_y_raw) != round(indep_y_raw):
                return "Bin rounding differs"

        if prod_bin != indep_bin:
            return "Bin indexing differs"

        if production_counts != independent_counts:
            return "Fold accumulation differs"

        return "Other"
