import math

from cmp_trace import CMPTrace


class CMPPopulator:
    """Populates a CMP grid with trace records derived from generated survey points."""

    def __init__(self, cmp_grid, geometry, acquisition):
        self.cmp_grid = cmp_grid
        self.geometry = geometry
        self.acquisition = acquisition

    #################################################################

    def populate(self):
        if not self.acquisition.shot_patch_lookup:
            self.acquisition.generate_schedule()

        survey = self.acquisition.survey

        accepted_traces = 0
        rejected_traces = 0
        total_shots_processed = 0
        total_active_receivers = 0
        valid_bin_assignments = 0
        invalid_bin_assignments = 0
        populated_bin_keys = set()
        shot_offset_audit = {}

        x_centers, y_centers, bin_lookup = self._build_bin_lookup()

        for shot in self.geometry.shots:
            if not shot.inside_boundary:
                continue

            if hasattr(self.acquisition, "active_receivers_for_shot"):
                active_receivers = self.acquisition.active_receivers_for_shot(shot)
            else:
                active_receivers = self.geometry.receivers

            total_shots_processed += 1
            total_active_receivers += len(active_receivers)

            for receiver in active_receivers:
                dx = receiver.x - shot.x
                dy = receiver.y - shot.y

                midpoint_x = (shot.x + receiver.x) / 2.0
                midpoint_y = (shot.y + receiver.y) / 2.0

                offset = math.hypot(dx, dy)

                shot_data = shot_offset_audit.setdefault(
                    shot.id,
                    {
                        "shot": shot,
                        "active_count": len(active_receivers),
                        "theoretical_max": 0.0,
                        "theoretical_min": None,
                        "generated_offsets": [],
                    },
                )
                if offset > shot_data["theoretical_max"]:
                    shot_data["theoretical_max"] = offset
                if shot_data["theoretical_min"] is None or offset < shot_data["theoretical_min"]:
                    shot_data["theoretical_min"] = offset

                azimuth_deg = math.degrees(math.atan2(dy, dx))
                if azimuth_deg < 0.0:
                    azimuth_deg += 360.0

                trace = CMPTrace(
                    shot_id=shot.id,
                    receiver_id=receiver.id,
                    midpoint_x=midpoint_x,
                    midpoint_y=midpoint_y,
                    offset=offset,
                    azimuth_deg=azimuth_deg,
                )

                x_index = self._nearest_index(
                    midpoint_x,
                    x_centers,
                    self.cmp_grid.bin_size_x,
                )
                y_index = self._nearest_index(
                    midpoint_y,
                    y_centers,
                    self.cmp_grid.bin_size_y,
                )
                assigned_xy = (x_centers[x_index], y_centers[y_index])

                if assigned_xy in bin_lookup:
                    valid_bin_assignments += 1
                else:
                    invalid_bin_assignments += 1
                    print("ERROR:")
                    print("Trace assigned to non-existent CMP bin.")

                bin_record = self._nearest_bin(
                    midpoint_x,
                    midpoint_y,
                    x_centers,
                    y_centers,
                    bin_lookup,
                )

                traces = self._trace_bucket(bin_record)
                traces.append(trace)
                shot_data["generated_offsets"].append(offset)
                bin_record.trace_count += 1
                accepted_traces += 1
                populated_bin_keys.add(bin_record.xy)

        total_cmp_bins = len(self.cmp_grid.bins)
        live_cmp_bins = len(populated_bin_keys)

        if live_cmp_bins > 0:
            average_traces_per_live_bin = accepted_traces / live_cmp_bins
            maximum_traces_per_live_bin = max(
                bin_lookup[xy].trace_count for xy in populated_bin_keys
            )
        else:
            average_traces_per_live_bin = 0.0
            maximum_traces_per_live_bin = 0

        print("==================================================")
        print("CMP BIN VALIDATION")
        print("==================================================")
        print(f"Total CMP Bins            : {total_cmp_bins}")
        print(f"Live CMP Bins             : {live_cmp_bins}")
        print(f"Accepted Traces           : {accepted_traces}")
        print(f"Rejected Traces           : {rejected_traces}")
        print(f"Average Traces / Live Bin : {average_traces_per_live_bin:.1f}")
        print(f"Maximum Traces / Live Bin : {maximum_traces_per_live_bin}")
        print(f"Valid Bin Assignments     : {valid_bin_assignments}")
        print(f"Invalid Bin Assignments   : {invalid_bin_assignments}")
        print("==================================================")

        self._print_live_receiver_patch_audit(shot_offset_audit)

        return self.cmp_grid

    #################################################################

    def _print_live_receiver_patch_audit(self, shot_offset_audit):
        if not shot_offset_audit:
            return

        survey = self.acquisition.survey
        representative_ids = self._representative_shot_ids(shot_offset_audit)

        print("==================================================")
        print("LIVE RECEIVER PATCH SUMMARY")
        print("==================================================")

        for shot_id in representative_ids:
            shot_data = shot_offset_audit[shot_id]
            shot = shot_data["shot"]

            first_line, last_line = self.acquisition.shot_patch_lookup[(shot.line, shot.station)]
            active_receivers = self.acquisition.active_receivers_for_shot(shot)
            line_numbers = sorted({receiver.line for receiver in active_receivers})
            receiver_counts_by_line = {
                line_number: sum(1 for receiver in active_receivers if receiver.line == line_number)
                for line_number in line_numbers
            }
            configured_stations_per_line = max(receiver_counts_by_line.values(), default=0)
            configured_receiver_lines = len(line_numbers)
            configured_receivers = configured_receiver_lines * configured_stations_per_line
            receivers_removed_by_boundary = configured_receivers - len(active_receivers)
            patch_completeness = (
                (100.0 * len(active_receivers) / configured_receivers)
                if configured_receivers > 0
                else 0.0
            )

            generated_offsets = shot_data["generated_offsets"]
            generated_min = min(generated_offsets) if generated_offsets else 0.0
            generated_max = max(generated_offsets) if generated_offsets else 0.0
            theoretical_max = shot_data["theoretical_max"]
            difference = theoretical_max - generated_max
            maximum_offset_status = "PASS" if abs(difference) <= 1.0 else "FAIL"

            print(f"Shot Number                  : {shot.id}")
            print(f"Shot X                       : {shot.x:.2f}")
            print(f"Shot Y                       : {shot.y:.2f}")
            print(f"First Active Receiver Line   : {first_line}")
            print(f"Last Active Receiver Line    : {last_line}")
            print(f"Number of Active Receiver Lines : {configured_receiver_lines}")
            print(f"Receiver Stations per Line (configured) : {configured_stations_per_line}")
            print(f"Configured Receivers         : {configured_receivers}")
            print(f"Total Active Receivers       : {len(active_receivers)}")
            print(f"Receivers Removed by Boundary : {receivers_removed_by_boundary}")
            print(f"Patch Completeness (%)       : {patch_completeness:.1f}")
            print(f"Minimum Offset               : {generated_min:.2f}")
            print(f"Maximum Offset               : {generated_max:.2f}")
            print(f"Theoretical Maximum Offset   : {theoretical_max:.2f}")
            print(f"Difference                   : {difference:.2f}")
            print(f"Maximum Offset Check         : {maximum_offset_status}")
            print(f"Boundary Clipping            : {receivers_removed_by_boundary} receivers removed")
            print("--------------------------------------------------")

        print("==================================================")

    #################################################################

    def _representative_shot_ids(self, shot_offset_audit):
        ordered_ids = sorted(shot_offset_audit)
        if len(ordered_ids) <= 3:
            return ordered_ids

        first_id = ordered_ids[0]
        middle_id = ordered_ids[len(ordered_ids) // 2]
        last_id = ordered_ids[-1]

        representative = []
        for shot_id in [first_id, middle_id, last_id]:
            if shot_id not in representative:
                representative.append(shot_id)

        return representative

    #################################################################

    def _build_bin_lookup(self):
        bins = self.cmp_grid.bins

        if not bins:
            return [], [], {}

        x_centers = sorted({bin_record.xy[0] for bin_record in bins})
        y_centers = sorted({bin_record.xy[1] for bin_record in bins})

        lookup = {bin_record.xy: bin_record for bin_record in bins}

        return x_centers, y_centers, lookup

    #################################################################

    def _nearest_bin(self, midpoint_x, midpoint_y, x_centers, y_centers, bin_lookup):
        if not bin_lookup:
            raise ValueError("CMP grid does not contain any bins")

        x_index = self._nearest_index(midpoint_x, x_centers, self.cmp_grid.bin_size_x)
        y_index = self._nearest_index(midpoint_y, y_centers, self.cmp_grid.bin_size_y)

        return bin_lookup[(x_centers[x_index], y_centers[y_index])]

    #################################################################

    def _nearest_index(self, value, centers, step):
        if not centers:
            raise ValueError("CMP grid axis has no centers")

        origin = centers[0]
        index = round((value - origin) / step)

        return max(0, min(index, len(centers) - 1))

    #################################################################

    def _trace_bucket(self, bin_record):
        if not hasattr(bin_record, "traces"):
            bin_record.traces = []

        return bin_record.traces
