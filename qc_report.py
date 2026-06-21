class QCReport:
    """Builds a production QC report from completed pipeline results."""

    def __init__(self, results):
        self.results = results

    #################################################################

    def generate(self):
        lines = [
            "==================================================",
            "QUALITY CONTROL REPORT",
            "==================================================",
            "",
        ]

        lines.extend(self._section("Survey", str(self.results.survey)))
        lines.extend(self._section("Geometry", self._geometry_text()))
        lines.extend(self._section("Boundary", self._boundary_text()))
        lines.extend(self._section("Acquisition", self._acquisition_text()))
        lines.extend(self._section("CMP", self._cmp_text()))
        lines.extend(self._section("Fold", self.results.true_fold_summary.summary()))
        lines.extend(self._section("Offset", self.results.offset_distribution.summary()))
        lines.extend(self._section("Azimuth", self.results.azimuth_summary.summary()))
        lines.extend(self._section("AVA", self.results.ava_summary.summary()))
        lines.extend(self._section("Logistics", self.results.logistics.summary()))
        lines.extend(self._section("Cost", self.results.cost_model.summary()))

        return "\n".join(lines).rstrip() + "\n"

    #################################################################

    def _section(self, title, content):
        return [
            "==================================================",
            title,
            "==================================================",
            content,
            "",
        ]

    #################################################################

    def _geometry_text(self):
        geometry = self.results.geometry

        receiver_lines = len({node.line for node in geometry.receivers})
        shot_lines = len({node.line for node in geometry.shots})

        receiver_stations = self._stations_per_line(geometry.receivers)
        shot_stations = self._stations_per_line(geometry.shots)

        return "\n".join([
            f"Receiver Nodes : {geometry.receiver_count}",
            f"Shot Points : {geometry.shot_count}",
            f"Receiver Lines : {receiver_lines}",
            f"Source Lines : {shot_lines}",
            f"Receiver Stations/Line (min-max) : {receiver_stations[0]}-{receiver_stations[1]}",
            f"Shot Stations/Line (min-max) : {shot_stations[0]}-{shot_stations[1]}",
        ])

    #################################################################

    def _boundary_text(self):
        geometry = self.results.geometry
        gis = self.results.gis

        receiver_inside = sum(1 for node in geometry.receivers if node.inside_boundary)
        shot_inside = sum(1 for node in geometry.shots if node.inside_boundary)

        receiver_total = len(geometry.receivers)
        shot_total = len(geometry.shots)

        xmin, ymin, xmax, ymax = gis.bounds

        return "\n".join([
            f"Boundary CRS : {gis.crs}",
            f"Boundary Bounds : X[{xmin:.3f}, {xmax:.3f}] Y[{ymin:.3f}, {ymax:.3f}]",
            f"Receivers Inside Boundary : {receiver_inside} / {receiver_total}",
            f"Shots Inside Boundary : {shot_inside} / {shot_total}",
        ])

    #################################################################

    def _acquisition_text(self):
        acquisition = self.results.acquisition
        events = self.results.acquisition_events

        patches = list(acquisition.shot_patch_lookup.values())
        unique_patches = sorted(set(patches))

        if unique_patches:
            first_patch = unique_patches[0]
            last_patch = unique_patches[-1]
            patch_range_text = (
                f"RL{first_patch[0]}-RL{first_patch[1]} to "
                f"RL{last_patch[0]}-RL{last_patch[1]}"
            )
        else:
            patch_range_text = "Not Available"

        return "\n".join([
            f"Schedule Events : {len(events)}",
            f"Shot Stations Scheduled : {len({key[1] for key in acquisition.shot_patch_lookup})}",
            f"Shot Locations Scheduled : {len(acquisition.shot_patch_lookup)}",
            f"Unique Receiver Patches : {len(unique_patches)}",
            f"Patch Range : {patch_range_text}",
        ])

    #################################################################

    def _cmp_text(self):
        cmp_grid = self.results.cmp_grid
        bins = cmp_grid.bins

        live_bins = sum(1 for bin_record in bins if bin_record.trace_count > 0)
        dead_bins = len(bins) - live_bins
        trace_count = sum(bin_record.trace_count for bin_record in bins)

        return "\n".join([
            f"CMP Bin Size X : {cmp_grid.bin_size_x:.1f} ft",
            f"CMP Bin Size Y : {cmp_grid.bin_size_y:.1f} ft",
            f"Total CMP Bins : {len(bins)}",
            f"Live CMP Bins : {live_bins}",
            f"Dead CMP Bins : {dead_bins}",
            f"Total Traces Populated : {trace_count}",
        ])

    #################################################################

    def _stations_per_line(self, nodes):
        if not nodes:
            return 0, 0

        counts = {}
        for node in nodes:
            counts.setdefault(node.line, 0)
            counts[node.line] += 1

        values = list(counts.values())
        return min(values), max(values)