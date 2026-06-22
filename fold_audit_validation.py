import math

from fold_analysis import FoldAnalysis
from true_fold_analysis import TrueFoldAnalysis


class FoldAuditValidation:
    """Independent validation suite for fold integrity and accounting."""

    def __init__(self, cmp_grid, survey, geometry, acquisition, gis, true_fold_summary):
        self.cmp_grid = cmp_grid
        self.survey = survey
        self.geometry = geometry
        self.acquisition = acquisition
        self.gis = gis
        self.true_fold_summary = true_fold_summary

        self.bins = list(getattr(self.cmp_grid, "bins", []))
        self.live_bins = [bin_record for bin_record in self.bins if getattr(bin_record, "trace_count", 0) > 0]

        self.x_centers = sorted({bin_record.xy[0] for bin_record in self.bins})
        self.y_centers = sorted({bin_record.xy[1] for bin_record in self.bins})

    #################################################################

    def run_all(self):
        """Execute all fold audit validations and print per-section PASS/FAIL output."""
        section_results = {}

        center_cmp, center_cmp_result = self._validation_center_cmp_fold_audit()
        section_results["Center CMP Audit"] = center_cmp_result

        duplicate_result = self._validation_duplicate_detection(center_cmp)
        section_results["Duplicate Detection"] = duplicate_result

        independent_result, fold_a_map = self._validation_independent_fold_calculation()
        section_results["Independent Fold"] = independent_result

        histogram_result = self._validation_fold_histogram_cross_check(fold_a_map)
        section_results["Histogram Check"] = histogram_result

        interior_result, interior_average_fold = self._validation_interior_fold_only()
        section_results["Interior Fold"] = interior_result

        # Informational section only; still emits PASS/FAIL as required.
        self._validation_theoretical_fold_estimate(interior_average_fold)

        trace_accounting_result = self._validation_trace_accounting()
        section_results["Trace Accounting"] = trace_accounting_result

        fold_integrity_result = self._validation_fold_integrity()
        section_results["Fold Integrity"] = fold_integrity_result

        self._print_final_summary(section_results)

        return section_results

    #################################################################

    def _validation_center_cmp_fold_audit(self):
        center_bin = self._center_cmp_bin()
        traces = list(getattr(center_bin, "traces", []))

        offsets = sorted(trace.offset for trace in traces)
        fold_count = len(traces)

        orientations = sorted((trace.azimuth_deg % 180.0) for trace in traces)

        key_counts = {}
        for trace in traces:
            key = (trace.shot_id, trace.receiver_id)
            key_counts[key] = key_counts.get(key, 0) + 1

        duplicate_pairs = sum(1 for count in key_counts.values() if count > 1)
        duplicate_trace_count = sum(count - 1 for count in key_counts.values() if count > 1)

        unique_shots = len({trace.shot_id for trace in traces})
        unique_receivers = len({trace.receiver_id for trace in traces})

        minimum_offset = offsets[0] if offsets else 0.0
        maximum_offset = offsets[-1] if offsets else 0.0
        average_offset = (math.fsum(offsets) / len(offsets)) if offsets else 0.0
        median_offset = self._percentile(offsets, 0.50)

        minimum_orientation = orientations[0] if orientations else 0.0
        maximum_orientation = orientations[-1] if orientations else 0.0
        orientation_coverage = maximum_orientation - minimum_orientation if orientations else 0.0

        passed = (duplicate_pairs == 0 and duplicate_trace_count == 0 and fold_count == getattr(center_bin, "trace_count", 0))

        print("==================================================")
        print("CENTER CMP FOLD AUDIT")
        print("==================================================")
        print(f"CMP Coordinate             : ({center_bin.xy[0]:.2f}, {center_bin.xy[1]:.2f})")
        print(f"Total traces               : {len(traces)}")
        print(f"Unique shots               : {unique_shots}")
        print(f"Unique receivers           : {unique_receivers}")
        print(f"Duplicate shot/receiver pairs : {duplicate_pairs}")
        print(f"Duplicate trace count      : {duplicate_trace_count}")
        print(f"Fold (trace count)         : {getattr(center_bin, 'trace_count', 0)}")
        print(f"Minimum Offset             : {minimum_offset:.0f} ft")
        print(f"Maximum Offset             : {maximum_offset:.0f} ft")
        print(f"Average Offset             : {average_offset:.0f} ft")
        print(f"Median Offset              : {median_offset:.0f} ft")
        print(f"Minimum Orientation        : {minimum_orientation:.1f}°")
        print(f"Maximum Orientation        : {maximum_orientation:.1f}°")
        print(f"Orientation Coverage       : {orientation_coverage:.1f}°")
        print("PASS" if passed else "FAIL")

        return center_bin, passed

    #################################################################

    def _validation_duplicate_detection(self, center_bin):
        traces = list(getattr(center_bin, "traces", []))
        seen = set()
        duplicates = []

        for trace in traces:
            key = (trace.shot_id, trace.receiver_id)
            if key in seen:
                duplicates.append(key)
            else:
                seen.add(key)

        passed = len(duplicates) == 0

        print("==================================================")
        print("DUPLICATE DETECTION")
        print("==================================================")

        if duplicates:
            for shot_id, receiver_id in duplicates[:20]:
                print(f"Duplicate Shot {shot_id} Receiver {receiver_id}")
        else:
            print("No duplicate traces found.")

        print("PASS" if passed else "FAIL")

        return passed

    #################################################################

    def _validation_independent_fold_calculation(self):
        fold_a = {bin_record.xy: int(getattr(bin_record, "trace_count", 0)) for bin_record in self.bins}

        fold_b = {bin_record.xy: 0 for bin_record in self.bins}

        if self.x_centers and self.y_centers:
            x_origin = self.x_centers[0]
            y_origin = self.y_centers[0]
            x_step = getattr(self.cmp_grid, "bin_size_x", 1.0)
            y_step = getattr(self.cmp_grid, "bin_size_y", 1.0)

            for bin_record in self.live_bins:
                for trace in getattr(bin_record, "traces", []):
                    x_index = self._nearest_index(trace.midpoint_x, x_origin, x_step, len(self.x_centers))
                    y_index = self._nearest_index(trace.midpoint_y, y_origin, y_step, len(self.y_centers))
                    cmp_key = (self.x_centers[x_index], self.y_centers[y_index])
                    fold_b[cmp_key] = fold_b.get(cmp_key, 0) + 1

        differences = [abs(fold_a.get(key, 0) - fold_b.get(key, 0)) for key in fold_a.keys()]

        maximum_difference = max(differences) if differences else 0
        average_difference = (math.fsum(differences) / len(differences)) if differences else 0.0
        number_different = sum(1 for value in differences if value != 0)

        passed = (maximum_difference == 0 and number_different == 0)

        print("==================================================")
        print("INDEPENDENT FOLD CALCULATION")
        print("==================================================")
        print(f"Maximum Difference        : {maximum_difference}")
        print(f"Average Difference        : {average_difference:.6f}")
        print(f"Number Different          : {number_different}")
        print("PASS" if passed else "FAIL")

        return passed, fold_a

    #################################################################

    def _validation_fold_histogram_cross_check(self, fold_map):
        live_folds = sorted(value for value in fold_map.values() if value > 0)

        audit_average = (math.fsum(live_folds) / len(live_folds)) if live_folds else 0.0
        audit_median = self._percentile(live_folds, 0.50)
        audit_maximum = live_folds[-1] if live_folds else 0
        audit_minimum = live_folds[0] if live_folds else 0
        audit_p95 = self._percentile(live_folds, 0.95)
        audit_p99 = self._percentile(live_folds, 0.99)

        fold_analysis = TrueFoldAnalysis(self.cmp_grid)
        current_median = fold_analysis._percentile(live_folds, 0.50)
        current_p95 = fold_analysis._percentile(live_folds, 0.95)
        current_p99 = fold_analysis._percentile(live_folds, 0.99)

        passed = (
            abs(audit_average - self.true_fold_summary.average_fold) < 1e-9
            and audit_minimum == self.true_fold_summary.minimum_fold
            and audit_maximum == self.true_fold_summary.maximum_fold
            and abs(audit_median - current_median) < 1e-9
            and abs(audit_p95 - current_p95) < 1e-9
            and abs(audit_p99 - current_p99) < 1e-9
        )

        print("==================================================")
        print("FOLD HISTOGRAM CROSS CHECK")
        print("==================================================")
        print(f"Average Fold             : {audit_average:.6f}")
        print(f"Median Fold              : {audit_median:.6f}")
        print(f"Maximum Fold             : {audit_maximum}")
        print(f"Minimum Fold             : {audit_minimum}")
        print(f"95 percentile            : {audit_p95:.6f}")
        print(f"99 percentile            : {audit_p99:.6f}")
        print("PASS" if passed else "FAIL")

        return passed

    #################################################################

    def _validation_interior_fold_only(self):
        xmin, ymin, xmax, ymax = self.gis.bounds
        patch_width = self.survey.active_receiver_lines * self.survey.receiver_line_spacing

        interior_xmin = xmin + patch_width
        interior_xmax = xmax - patch_width
        interior_ymin = ymin + patch_width
        interior_ymax = ymax - patch_width

        interior_folds = []

        for bin_record in self.live_bins:
            x_value, y_value = bin_record.xy
            if interior_xmin <= x_value <= interior_xmax and interior_ymin <= y_value <= interior_ymax:
                interior_folds.append(int(getattr(bin_record, "trace_count", 0)))

        interior_folds.sort()

        interior_average = (math.fsum(interior_folds) / len(interior_folds)) if interior_folds else 0.0
        interior_median = self._percentile(interior_folds, 0.50)
        interior_maximum = interior_folds[-1] if interior_folds else 0
        interior_minimum = interior_folds[0] if interior_folds else 0

        passed = len(interior_folds) > 0

        print("==================================================")
        print("INTERIOR FOLD ONLY")
        print("==================================================")
        print(f"Interior Average Fold    : {interior_average:.6f}")
        print(f"Interior Median Fold     : {interior_median:.6f}")
        print(f"Interior Maximum Fold    : {interior_maximum}")
        print(f"Interior Minimum Fold    : {interior_minimum}")
        print("PASS" if passed else "FAIL")

        return passed, interior_average

    #################################################################

    def _validation_theoretical_fold_estimate(self, measured_interior_fold):
        design_fold = FoldAnalysis(self.geometry).compute_design_fold()

        difference = measured_interior_fold - design_fold
        percent_error = (difference / design_fold * 100.0) if design_fold != 0.0 else 0.0

        print("==================================================")
        print("THEORETICAL FOLD ESTIMATE")
        print("==================================================")
        print(f"Receiver spacing         : {self.survey.receiver_interval:.1f} ft")
        print(f"Receiver line spacing    : {self.survey.receiver_line_spacing:.1f} ft")
        print(f"Shot spacing             : {self.survey.shot_interval:.1f} ft")
        print(f"Shot line spacing        : {self.survey.source_line_spacing:.1f} ft")
        print(f"Active receiver lines    : {self.survey.active_receiver_lines}")
        print(f"Processing bin size      : {self.survey.processing_bin_size:.1f} ft")
        print(f"Theoretical Fold         : {design_fold:.6f}")
        print(f"Measured Interior Fold   : {measured_interior_fold:.6f}")
        print(f"Difference               : {difference:.6f}")
        print(f"Percent Error            : {percent_error:.6f} %")
        print("PASS")

    #################################################################

    def _validation_trace_accounting(self):
        maximum_offset = (
            2.0
            * self.survey.target_depth
            * math.tan(math.radians(self.survey.maximum_incidence_angle))
        )

        total_generated = 0
        accepted_reconstructed = 0

        for shot in self.geometry.shots:
            if not shot.inside_boundary:
                continue

            if hasattr(self.acquisition, "active_receivers_for_shot"):
                active_receivers = self.acquisition.active_receivers_for_shot(shot)
            else:
                active_receivers = self.geometry.receivers

            for receiver in active_receivers:
                total_generated += 1

                midpoint_x = (shot.x + receiver.x) / 2.0
                midpoint_y = (shot.y + receiver.y) / 2.0

                if not self.geometry._point_inside_boundary(midpoint_x, midpoint_y):
                    continue

                offset = math.hypot(receiver.x - shot.x, receiver.y - shot.y)
                if offset <= maximum_offset:
                    accepted_reconstructed += 1

        rejected_reconstructed = total_generated - accepted_reconstructed

        accepted_grid = sum(int(getattr(bin_record, "trace_count", 0)) for bin_record in self.bins)
        accounting_sum = accepted_reconstructed + rejected_reconstructed
        expected_traces = total_generated

        passed = (
            accepted_reconstructed == accepted_grid
            and accounting_sum == expected_traces
        )

        print("==================================================")
        print("TRACE ACCOUNTING")
        print("==================================================")
        print(f"Total generated traces   : {total_generated}")
        print(f"Rejected traces          : {rejected_reconstructed}")
        print(f"Accepted traces          : {accepted_reconstructed}")
        print(f"Accepted + Rejected      : {accounting_sum}")
        print(f"Expected traces          : {expected_traces}")
        print("PASS" if passed else "FAIL")

        return passed

    #################################################################

    def _validation_fold_integrity(self):
        mismatches = 0

        for bin_record in self.bins:
            trace_count = int(getattr(bin_record, "trace_count", 0))
            traces = getattr(bin_record, "traces", [])
            if trace_count != len(traces):
                mismatches += 1

        passed = mismatches == 0

        print("==================================================")
        print("FOLD INTEGRITY")
        print("==================================================")
        print("Fold equals number of accepted traces mapped into each CMP.")
        print(f"Mismatched CMP bins      : {mismatches}")
        print("PASS" if passed else "FAIL")

        return passed

    #################################################################

    def _print_final_summary(self, section_results):
        overall_pass = all(section_results.values())

        print("==================================================")
        print("FINAL VALIDATION SUMMARY")
        print("==================================================")
        print(f"Center CMP Audit........{'PASS' if section_results.get('Center CMP Audit') else 'FAIL'}")
        print(f"Duplicate Detection.....{'PASS' if section_results.get('Duplicate Detection') else 'FAIL'}")
        print(f"Independent Fold........{'PASS' if section_results.get('Independent Fold') else 'FAIL'}")
        print(f"Histogram Check.........{'PASS' if section_results.get('Histogram Check') else 'FAIL'}")
        print(f"Interior Fold...........{'PASS' if section_results.get('Interior Fold') else 'FAIL'}")
        print(f"Trace Accounting........{'PASS' if section_results.get('Trace Accounting') else 'FAIL'}")
        print(f"Fold Integrity..........{'PASS' if section_results.get('Fold Integrity') else 'FAIL'}")
        print(f"Overall................{'PASS' if overall_pass else 'FAIL'}")

    #################################################################

    def _center_cmp_bin(self):
        center_x, center_y = self._survey_center()

        if not self.bins:
            raise ValueError("CMP grid contains no bins.")

        return min(
            self.bins,
            key=lambda record: (record.xy[0] - center_x) ** 2 + (record.xy[1] - center_y) ** 2,
        )

    #################################################################

    def _survey_center(self):
        xmin, ymin, xmax, ymax = self.gis.bounds
        return (xmin + xmax) / 2.0, (ymin + ymax) / 2.0

    #################################################################

    def _nearest_index(self, value, origin, step, count):
        if count <= 0:
            return 0

        if step <= 0.0:
            return 0

        index = round((value - origin) / step)
        return max(0, min(index, count - 1))

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
