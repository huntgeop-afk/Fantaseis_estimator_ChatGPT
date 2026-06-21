class GeometryDebugger:
    """Temporary developer utility for printing geometry diagnostics."""

    def __init__(self, geometry):
        self.geometry = geometry

    #################################################################

    def run(self):
        receivers = list(getattr(self.geometry, "receivers", []))
        shots = list(getattr(self.geometry, "shots", []))

        self._print_receiver_summary(receivers)
        self._print_node_slice("First Ten Receivers", receivers[:10])
        self._print_node_slice("Last Ten Receivers", receivers[-10:])

        self._print_shot_summary(shots)
        self._print_node_slice("First Ten Shots", shots[:10])
        self._print_node_slice("Last Ten Shots", shots[-10:])

        self._print_boundary_summary(receivers, shots)

        self._print_sanity_checks(receivers, shots)

    #################################################################

    def _print_receiver_summary(self, receivers):
        line_count, station_min, station_max = self._line_station_stats(receivers)
        x_min, x_max, y_min, y_max = self._ranges(receivers)

        print("==============================")
        print("RECEIVERS")
        print("==============================")
        print(f"Total Receivers: {len(receivers)}")
        print(f"Receiver Lines: {line_count}")
        print(f"Stations / Line (min): {station_min}")
        print(f"Stations / Line (max): {station_max}")
        print(f"Minimum X: {self._fmt_number(x_min)}")
        print(f"Maximum X: {self._fmt_number(x_max)}")
        print(f"Minimum Y: {self._fmt_number(y_min)}")
        print(f"Maximum Y: {self._fmt_number(y_max)}")

    #################################################################

    def _print_shot_summary(self, shots):
        line_count, station_min, station_max = self._line_station_stats(shots)
        x_min, x_max, y_min, y_max = self._ranges(shots)

        print("==============================")
        print("SHOTS")
        print("==============================")
        print(f"Total Shots: {len(shots)}")
        print(f"Source Lines: {line_count}")
        print(f"Stations / Line (min): {station_min}")
        print(f"Stations / Line (max): {station_max}")
        print(f"Minimum X: {self._fmt_number(x_min)}")
        print(f"Maximum X: {self._fmt_number(x_max)}")
        print(f"Minimum Y: {self._fmt_number(y_min)}")
        print(f"Maximum Y: {self._fmt_number(y_max)}")

    #################################################################

    def _print_node_slice(self, title, nodes):
        print(title)
        print("Line, Station, X, Y, Inside Boundary")

        if not nodes:
            print("Not Available")
            return

        for node in nodes:
            print(
                f"{node.line}, {node.station}, {node.x:.3f}, {node.y:.3f}, "
                f"{bool(getattr(node, 'inside_boundary', False))}"
            )

    #################################################################

    def _print_sanity_checks(self, receivers, shots):
        receiver_lines = {node.line for node in receivers}
        shot_lines = {node.line for node in shots}

        duplicate_receiver_coords = self._duplicate_count(receivers)
        duplicate_shot_coords = self._duplicate_count(shots)

        receiver_range = self._coordinate_range_text(receivers)
        shot_range = self._coordinate_range_text(shots)

        print("==============================")
        print("SANITY CHECKS")
        print("==============================")
        print(f"Unique Receiver Lines: {len(receiver_lines)}")
        print(f"Unique Source Lines: {len(shot_lines)}")
        print(f"Duplicate Receiver Coordinates: {duplicate_receiver_coords}")
        print(f"Duplicate Shot Coordinates: {duplicate_shot_coords}")
        print(f"Receiver Coordinate Range: {receiver_range}")
        print(f"Shot Coordinate Range: {shot_range}")

    #################################################################

    def _print_boundary_summary(self, receivers, shots):
        receivers_inside = sum(1 for node in receivers if getattr(node, "inside_boundary", False))
        receivers_outside = len(receivers) - receivers_inside

        shots_inside = sum(1 for node in shots if getattr(node, "inside_boundary", False))
        shots_outside = len(shots) - shots_inside

        receiver_percent_inside = 0.0
        if receivers:
            receiver_percent_inside = 100.0 * receivers_inside / len(receivers)

        shot_percent_inside = 0.0
        if shots:
            shot_percent_inside = 100.0 * shots_inside / len(shots)

        print("==================================================")
        print("BOUNDARY SUMMARY")
        print("==================================================")
        print(f"Receivers Inside Boundary : {receivers_inside}")
        print(f"Receivers Outside Boundary: {receivers_outside}")
        print(f"Shots Inside Boundary     : {shots_inside}")
        print(f"Shots Outside Boundary    : {shots_outside}")
        print(f"Receiver % Inside         : {receiver_percent_inside:.1f}%")
        print(f"Shot % Inside             : {shot_percent_inside:.1f}%")

    #################################################################

    def _line_station_stats(self, nodes):
        if not nodes:
            return 0, 0, 0

        counts_by_line = {}

        for node in nodes:
            counts_by_line.setdefault(node.line, []).append(node.station)

        station_counts = [len(stations) for stations in counts_by_line.values()]

        return len(counts_by_line), min(station_counts), max(station_counts)

    #################################################################

    def _ranges(self, nodes):
        if not nodes:
            return None, None, None, None

        xs = [node.x for node in nodes]
        ys = [node.y for node in nodes]

        return min(xs), max(xs), min(ys), max(ys)

    #################################################################

    def _duplicate_count(self, nodes):
        seen = set()
        duplicates = 0

        for node in nodes:
            key = (node.x, node.y)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)

        return duplicates

    #################################################################

    def _coordinate_range_text(self, nodes):
        x_min, x_max, y_min, y_max = self._ranges(nodes)

        if x_min is None:
            return "Not Available"

        return (
            f"X={x_min:.3f} to {x_max:.3f}, "
            f"Y={y_min:.3f} to {y_max:.3f}"
        )

    #################################################################

    def _fmt_number(self, value):
        if value is None:
            return "Not Available"

        return f"{value:.3f}"
