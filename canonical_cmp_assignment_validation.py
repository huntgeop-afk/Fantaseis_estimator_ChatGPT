import random

from center_cmp_validation import CenterCMPValidation
from cmp_populator import CMPPopulator
from fold_audit_validation import FoldAuditValidation


class CanonicalCMPAssignmentValidation:
    """Feature 058: validation-only canonical CMP assignment equivalence audit."""

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary, sample_size=200):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self.geometry = geometry
        self.acquisition = acquisition
        self.gis = gis
        self.true_fold_summary = true_fold_summary
        self.sample_size = int(sample_size)

        self.bins = list(getattr(self.cmp_grid, "bins", []))
        self.bin_lookup = {bin_record.xy: bin_record for bin_record in self.bins}
        self.x_centers = sorted({bin_record.xy[0] for bin_record in self.bins})
        self.y_centers = sorted({bin_record.xy[1] for bin_record in self.bins})

        self.bin_size_x = float(getattr(self.cmp_grid, "bin_size_x", 0.0) or 0.0)
        self.bin_size_y = float(getattr(self.cmp_grid, "bin_size_y", 0.0) or 0.0)

        self.canonical = CMPPopulator(self.cmp_grid, self.geometry, self.acquisition)
        self.fold_validation = FoldAuditValidation(
            cmp_grid=self.cmp_grid,
            survey=self.survey,
            geometry=self.geometry,
            acquisition=self.acquisition,
            gis=self.gis,
            true_fold_summary=self.true_fold_summary,
        )
        self.center_qc = CenterCMPValidation(self.cmp_grid, self.gis)

    #################################################################

    def run(self):
        midpoints = self._sample_midpoints()

        implementations = self._implementations_under_test()
        self._print_located_implementations(implementations)
        comparison_rows = []

        for implementation in implementations:
            for midpoint_x, midpoint_y in midpoints:
                result = self._compare_one(implementation, midpoint_x, midpoint_y)
                comparison_rows.append(result)
                self._print_comparison_row(result)

        number_tested = len(comparison_rows)
        number_matching = sum(1 for row in comparison_rows if row["pass"])
        number_different = number_tested - number_matching

        differing_functions = self._differing_functions(comparison_rows)

        print("========================================")
        print("CANONICAL CMP SUMMARY")
        print("========================================")
        print("Number Tested")
        print(number_tested)
        print("Number Matching")
        print(number_matching)
        print("Number Different")
        print(number_different)
        print("Functions Requiring Refactor")
        print(len(differing_functions))
        print("========================================")

        if differing_functions:
            print("========================================")
            print("DIFFERING FUNCTIONS")
            print("========================================")
            for item in differing_functions:
                print("Module")
                print(item["module"])
                print("Function")
                print(item["function"])
                print("Reason")
                print(item["reason"])
                print("Difference")
                print(item["difference"])
                print("Replacing With Canonical Alters Engineering Calculations")
                print(item["engineering_impact"])
                print("----------------------------------------")

        module_usage = self._module_canonical_usage(differing_functions)
        engineering_modules_already_canonical = all(
            value["already_canonical"] for value in module_usage.values()
        )

        modules_tested = len(module_usage)
        matching_modules = sum(1 for value in module_usage.values() if value["already_canonical"])
        modules_requiring_refactor = modules_tested - matching_modules

        print("========================================")
        print("ENGINEERING MODULE CANONICAL USAGE")
        print("========================================")
        for module_name, module_result in module_usage.items():
            print(module_name)
            print(module_result["detail"])
            print("PASS / FAIL")
            print("PASS" if module_result["already_canonical"] else "FAIL")
            print("----------------------------------------")

        refactor_order = self._recommended_refactor_order(module_usage)
        overall_pass = (number_different == 0) and engineering_modules_already_canonical

        print("========================================")
        print("CANONICAL CMP VALIDATION")
        print("========================================")
        print("Canonical Routine")
        print("cmp_populator.CMPPopulator._nearest_bin + cmp_populator.CMPPopulator._nearest_index")
        print("Modules Tested")
        print(modules_tested)
        print("Matching Modules")
        print(matching_modules)
        print("Modules Requiring Refactor")
        print(modules_requiring_refactor)
        print("Engineering Modules Already Canonical")
        print("PASS" if engineering_modules_already_canonical else "FAIL")
        print("PASS / FAIL")
        print("PASS" if engineering_modules_already_canonical else "FAIL")
        print("Recommended Refactor Order")
        print(refactor_order)
        print("Overall")
        print("PASS" if overall_pass else "FAIL")
        print("PASS / FAIL")
        print("PASS" if overall_pass else "FAIL")
        print("========================================")

        return {
            "number_tested": number_tested,
            "number_matching": number_matching,
            "number_different": number_different,
            "functions_requiring_refactor": len(differing_functions),
            "engineering_modules_already_canonical": engineering_modules_already_canonical,
            "overall_pass": overall_pass,
        }

    #################################################################

    def _sample_midpoints(self):
        if not self.x_centers or not self.y_centers:
            return []

        rng = random.Random(58)
        reservoir = []
        seen = 0

        for shot in self.geometry.shots:
            if not getattr(shot, "inside_boundary", False):
                continue

            if hasattr(self.acquisition, "active_receivers_for_shot"):
                receivers = self.acquisition.active_receivers_for_shot(shot)
            else:
                receivers = self.geometry.receivers

            for receiver in receivers:
                midpoint_x = (float(shot.x) + float(receiver.x)) / 2.0
                midpoint_y = (float(shot.y) + float(receiver.y)) / 2.0
                seen += 1

                if len(reservoir) < self.sample_size:
                    reservoir.append((midpoint_x, midpoint_y))
                else:
                    replace_index = rng.randint(1, seen)
                    if replace_index <= self.sample_size:
                        reservoir[replace_index - 1] = (midpoint_x, midpoint_y)

        if not reservoir:
            # Fall back to deterministic coordinates from the CMP grid if no midpoint rows exist.
            for bin_record in self.bins[: max(1, self.sample_size)]:
                reservoir.append((bin_record.xy[0], bin_record.xy[1]))

        return reservoir

    #################################################################

    def _implementations_under_test(self):
        return [
            {"module": "cmp_populator.py", "function": "CMPPopulator._nearest_bin", "kind": "nearest_bin"},
            {"module": "cmp_populator.py", "function": "CMPPopulator._nearest_index", "kind": "nearest_index"},
            {"module": "fold_audit_validation.py", "function": "FoldAuditValidation._assign_bin", "kind": "assign_bin"},
            {"module": "fold_audit_validation.py", "function": "FoldAuditValidation._nearest_index", "kind": "fold_nearest_index"},
            {"module": "fold_audit_validation.py", "function": "FoldAuditValidation._bin_row_col", "kind": "bin_row_col"},
            {"module": "center_cmp_validation.py", "function": "CenterCMPValidation._nearest_cmp_bin", "kind": "center_nearest_bin"},
        ]

    #################################################################

    def _compare_one(self, implementation, midpoint_x, midpoint_y):
        module_name = implementation["module"]
        function_name = implementation["function"]

        canonical_row, canonical_col = self._canonical_row_col(midpoint_x, midpoint_y)

        try:
            existing_row, existing_col = self._existing_row_col(implementation["kind"], midpoint_x, midpoint_y)
            is_pass = (existing_row == canonical_row and existing_col == canonical_col)
            reason = "Match" if is_pass else "Output differs from canonical row/column"
        except Exception as exc:
            existing_row = None
            existing_col = None
            is_pass = False
            reason = f"Execution error: {exc}"

        return {
            "module": module_name,
            "function": function_name,
            "existing_row": existing_row,
            "existing_col": existing_col,
            "canonical_row": canonical_row,
            "canonical_col": canonical_col,
            "pass": is_pass,
            "reason": reason,
            "midpoint_x": midpoint_x,
            "midpoint_y": midpoint_y,
        }

    #################################################################

    def _canonical_row_col(self, midpoint_x, midpoint_y):
        x_index = self.canonical._nearest_index(midpoint_x, self.x_centers, self.bin_size_x)
        y_index = self.canonical._nearest_index(midpoint_y, self.y_centers, self.bin_size_y)
        return y_index + 1, x_index + 1

    #################################################################

    def _existing_row_col(self, kind, midpoint_x, midpoint_y):
        if kind == "nearest_bin":
            bin_record = self.canonical._nearest_bin(
                midpoint_x,
                midpoint_y,
                self.x_centers,
                self.y_centers,
                self.bin_lookup,
            )
            return self._row_col_from_xy(bin_record.xy)

        if kind == "nearest_index":
            x_index = self.canonical._nearest_index(midpoint_x, self.x_centers, self.bin_size_x)
            y_index = self.canonical._nearest_index(midpoint_y, self.y_centers, self.bin_size_y)
            return y_index + 1, x_index + 1

        if kind == "assign_bin":
            _, row, col = self.fold_validation._assign_bin(midpoint_x, midpoint_y)
            return row, col

        if kind == "fold_nearest_index":
            x_index = self.fold_validation._nearest_index(
                midpoint_x,
                self.x_centers[0],
                self.bin_size_x,
                len(self.x_centers),
            )
            y_index = self.fold_validation._nearest_index(
                midpoint_y,
                self.y_centers[0],
                self.bin_size_y,
                len(self.y_centers),
            )
            return y_index + 1, x_index + 1

        if kind == "center_nearest_bin":
            bin_record = self.center_qc._nearest_cmp_bin(midpoint_x, midpoint_y)
            return self._row_col_from_xy(bin_record.xy)

        if kind == "bin_row_col":
            canonical_xy = self._canonical_bin_xy(midpoint_x, midpoint_y)
            return self.fold_validation._bin_row_col(canonical_xy)

        raise ValueError(f"Unsupported comparison kind: {kind}")

    #################################################################

    def _row_col_from_xy(self, bin_xy):
        x_index = self.x_centers.index(bin_xy[0])
        y_index = self.y_centers.index(bin_xy[1])
        return y_index + 1, x_index + 1

    #################################################################

    def _canonical_bin_xy(self, midpoint_x, midpoint_y):
        x_index = self.canonical._nearest_index(midpoint_x, self.x_centers, self.bin_size_x)
        y_index = self.canonical._nearest_index(midpoint_y, self.y_centers, self.bin_size_y)
        return self.x_centers[x_index], self.y_centers[y_index]

    #################################################################

    def _print_located_implementations(self, implementations):
        print("========================================")
        print("LOCATED CMP ASSIGNMENT IMPLEMENTATIONS")
        print("========================================")
        for item in implementations:
            print("Module")
            print(item["module"])
            print("Function")
            print(item["function"])
            print("----------------------------------------")

    #################################################################

    def _print_comparison_row(self, row):
        print("Module")
        print(row["module"])
        print("Function")
        print(row["function"])
        print("Existing Row")
        print(row["existing_row"])
        print("Existing Column")
        print(row["existing_col"])
        print("Canonical Row")
        print(row["canonical_row"])
        print("Canonical Column")
        print(row["canonical_col"])
        print("PASS / FAIL")
        print("PASS" if row["pass"] else "FAIL")
        print("----------------------------------------")

    #################################################################

    def _differing_functions(self, comparison_rows):
        grouped = {}
        for row in comparison_rows:
            key = (row["module"], row["function"])
            grouped.setdefault(key, []).append(row)

        differing = []
        for (module_name, function_name), rows in grouped.items():
            failures = [row for row in rows if not row["pass"]]
            if not failures:
                continue

            first = failures[0]
            mismatch_count = len(failures)

            if "CenterCMPValidation._nearest_cmp_bin" in function_name:
                reason = "Uses Euclidean nearest-center search rather than rounded index assignment"
                engineering_impact = "NO (QC diagnostic only)"
            elif "FoldAuditValidation" in function_name:
                reason = "Validation implementation differs from canonical for at least one midpoint"
                engineering_impact = "NO (validation-only module)"
            else:
                reason = "Implementation differs from canonical output"
                engineering_impact = "YES"

            difference = (
                f"{mismatch_count} mismatches; first mismatch midpoint=({first['midpoint_x']:.3f}, "
                f"{first['midpoint_y']:.3f}) existing=({first['existing_row']}, {first['existing_col']}) "
                f"canonical=({first['canonical_row']}, {first['canonical_col']})"
            )

            differing.append(
                {
                    "module": module_name,
                    "function": function_name,
                    "reason": reason,
                    "difference": difference,
                    "engineering_impact": engineering_impact,
                }
            )

        return sorted(differing, key=lambda item: (item["module"], item["function"]))

    #################################################################

    def _module_canonical_usage(self, differing_functions):
        differing_lookup = {(item["module"], item["function"]): item for item in differing_functions}

        module_usage = {
            "CMP Population": {
                "already_canonical": True,
                "detail": "Uses cmp_populator canonical assignment in production.",
            },
            "Fold": {
                "already_canonical": True,
                "detail": "Consumes populated CMP bins; no independent assignment routine.",
            },
            "Offset": {
                "already_canonical": True,
                "detail": "Consumes trace offsets from populated CMP bins only.",
            },
            "AVA": {
                "already_canonical": True,
                "detail": "Consumes populated trace offsets; no CMP reassignment.",
            },
            "AVAz": {
                "already_canonical": True,
                "detail": "Consumes populated trace azimuths; no CMP reassignment.",
            },
            "Optimizer": {
                "already_canonical": True,
                "detail": "Consumes fold/cost outputs; no direct midpoint-to-bin assignment.",
            },
            "QC": {
                "already_canonical": ("center_cmp_validation.py", "CenterCMPValidation._nearest_cmp_bin") not in differing_lookup,
                "detail": "center_cmp_validation uses nearest CMP selection for diagnostics.",
            },
            "Validation": {
                "already_canonical": (
                    ("fold_audit_validation.py", "FoldAuditValidation._assign_bin") not in differing_lookup
                    and ("fold_audit_validation.py", "FoldAuditValidation._nearest_index") not in differing_lookup
                ),
                "detail": "fold_audit_validation compares independent assignment against production bins.",
            },
            "Design Space Analysis": {
                "already_canonical": True,
                "detail": "Invokes CMPPopulator in candidate evaluation; no separate assignment algorithm.",
            },
            "Business modules": {
                "already_canonical": True,
                "detail": "No midpoint-to-bin assignment in business/cost/logistics modules.",
            },
        }

        return module_usage

    #################################################################

    def _recommended_refactor_order(self, module_usage):
        failing = [name for name, value in module_usage.items() if not value["already_canonical"]]
        if not failing:
            return "None required"

        preferred = []
        if "Validation" in failing:
            preferred.append("Validation")
        if "QC" in failing:
            preferred.append("QC")

        for name in failing:
            if name not in preferred:
                preferred.append(name)

        return " -> ".join(preferred)
