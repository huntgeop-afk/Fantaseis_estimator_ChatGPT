class GeometryQC:
    """Builds a read-only quality-control summary from a generated Geometry object."""

    def __init__(self, geometry):
        self.geometry = geometry

    #################################################################

    def summary(self):
        receivers = list(getattr(self.geometry, "receivers", []))
        shots = list(getattr(self.geometry, "shots", []))

        receiver_line_count, receiver_station_min, receiver_station_max = self._line_station_stats(receivers)
        source_line_count, source_station_min, source_station_max = self._line_station_stats(shots)

        receiver_x_min, receiver_x_max, receiver_y_min, receiver_y_max = self._xy_ranges(receivers)
        shot_x_min, shot_x_max, shot_y_min, shot_y_max = self._xy_ranges(shots)

        overall_x_min, overall_x_max, overall_y_min, overall_y_max = self._overall_ranges(
            receiver_x_min,
            receiver_x_max,
            receiver_y_min,
            receiver_y_max,
            shot_x_min,
            shot_x_max,
            shot_y_min,
            shot_y_max,
        )

        receiver_inside, receiver_outside = self._inside_outside_counts(receivers)
        shot_inside, shot_outside = self._inside_outside_counts(shots)

        first_receiver = self._first_node(receivers)
        last_receiver = self._last_node(receivers)
        first_shot = self._first_node(shots)
        last_shot = self._last_node(shots)

        lines = [
            "==================================================",
            "Geometry QC",
            "==================================================",
            "Receivers",
            f"Total Receiver Nodes: {len(receivers)}",
            f"Receiver Lines: {receiver_line_count}",
            f"Receiver Stations per Line (min/max): {receiver_station_min}/{receiver_station_max}",
            f"Receiver X Range: {self._range_text(receiver_x_min, receiver_x_max)}",
            f"Receiver Y Range: {self._range_text(receiver_y_min, receiver_y_max)}",
            "--------------------------------------------",
            "Sources",
            f"Total Shot Points: {len(shots)}",
            f"Source Lines: {source_line_count}",
            f"Shot Stations per Line (min/max): {source_station_min}/{source_station_max}",
            f"Source X Range: {self._range_text(shot_x_min, shot_x_max)}",
            f"Source Y Range: {self._range_text(shot_y_min, shot_y_max)}",
            "--------------------------------------------",
            "Survey Extents",
            f"Overall X Range: {self._range_text(overall_x_min, overall_x_max)}",
            f"Overall Y Range: {self._range_text(overall_y_min, overall_y_max)}",
            "--------------------------------------------",
            "Inside Survey Boundary",
            f"Receiver Nodes Inside: {receiver_inside}",
            f"Receiver Nodes Outside: {receiver_outside}",
            f"Shot Points Inside: {shot_inside}",
            f"Shot Points Outside: {shot_outside}",
            "--------------------------------------------",
            "First Receiver",
            self._node_text(first_receiver),
            "Last Receiver",
            self._node_text(last_receiver),
            "First Shot",
            self._node_text(first_shot),
            "Last Shot",
            self._node_text(last_shot),
        ]

        return "\n".join(lines)

    #################################################################

    def _line_station_stats(self, nodes):
        if not nodes:
            return 0, 0, 0

        lines = {}
        for node in nodes:
            lines.setdefault(node.line, []).append(node.station)

        station_counts = [len(stations) for stations in lines.values()]

        return len(lines), min(station_counts), max(station_counts)

    #################################################################

    def _xy_ranges(self, nodes):
        if not nodes:
            return None, None, None, None

        xs = [node.x for node in nodes]
        ys = [node.y for node in nodes]

        return min(xs), max(xs), min(ys), max(ys)

    #################################################################

    def _overall_ranges(
        self,
        receiver_x_min,
        receiver_x_max,
        receiver_y_min,
        receiver_y_max,
        shot_x_min,
        shot_x_max,
        shot_y_min,
        shot_y_max,
    ):
        x_mins = [value for value in [receiver_x_min, shot_x_min] if value is not None]
        x_maxs = [value for value in [receiver_x_max, shot_x_max] if value is not None]
        y_mins = [value for value in [receiver_y_min, shot_y_min] if value is not None]
        y_maxs = [value for value in [receiver_y_max, shot_y_max] if value is not None]

        if not x_mins or not x_maxs or not y_mins or not y_maxs:
            return None, None, None, None

        return min(x_mins), max(x_maxs), min(y_mins), max(y_maxs)

    #################################################################

    def _inside_outside_counts(self, nodes):
        inside = sum(1 for node in nodes if getattr(node, "inside_boundary", False))
        outside = len(nodes) - inside

        return inside, outside

    #################################################################

    def _first_node(self, nodes):
        if not nodes:
            return None

        return nodes[0]

    #################################################################

    def _last_node(self, nodes):
        if not nodes:
            return None

        return nodes[-1]

    #################################################################

    def _range_text(self, minimum, maximum):
        if minimum is None or maximum is None:
            return "Not Available"

        return f"{minimum:.3f} to {maximum:.3f}"

    #################################################################

    def _node_text(self, node):
        if node is None:
            return "Not Available"

        return (
            f"Line {node.line}, Station {node.station}, "
            f"X={node.x:.3f}, Y={node.y:.3f}"
        )
