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

        x_centers, y_centers, bin_lookup = self._build_bin_lookup()

        for shot in self.geometry.shots:
            if not shot.inside_boundary:
                continue

            if hasattr(self.acquisition, "active_receivers_for_shot"):
                active_receivers = self.acquisition.active_receivers_for_shot(shot)
            else:
                active_receivers = self.geometry.receivers

            for receiver in active_receivers:
                if not receiver.inside_boundary:
                    continue

                dx = receiver.x - shot.x
                dy = receiver.y - shot.y

                midpoint_x = (shot.x + receiver.x) / 2.0
                midpoint_y = (shot.y + receiver.y) / 2.0
                offset = math.hypot(dx, dy)

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
