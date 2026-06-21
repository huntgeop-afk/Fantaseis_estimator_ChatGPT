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
        maximum_offset = (
            2.0
            * survey.target_depth
            * math.tan(math.radians(survey.maximum_incidence_angle))
        )

        accepted_traces = 0
        rejected_traces = 0
        total_shots_processed = 0
        total_active_receivers = 0
        valid_bin_assignments = 0
        invalid_bin_assignments = 0
        populated_bin_keys = set()

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

                if not self.geometry._point_inside_boundary(midpoint_x, midpoint_y):
                    continue

                offset = math.hypot(dx, dy)

                if offset > maximum_offset:
                    rejected_traces += 1
                    continue

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

        return self.cmp_grid

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
