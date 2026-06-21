from dataclasses import dataclass
import math

from shapely.geometry import Point
from pyproj import CRS, Transformer


@dataclass
class SurveyNode:
    id: int
    line: int
    station: int
    x: float
    y: float
    inside_boundary: bool


@dataclass
class ReceiverPatch:
    """Represents one active receiver window used during acquisition."""

    patch_number: int
    first_receiver_line: int
    last_receiver_line: int
    trigger_shot_station: int
    receiver_line_count: int


class Geometry:

    def __init__(self, survey, gis):
        self.survey = survey
        self.gis = gis

        self.receivers = []
        self.shots = []

    #################################################################

    def generate(self):
        self._build_basis()
        self._compute_grid_bounds()
        self._configure_boundary_tester()
        self._generate_receivers()
        self._generate_shots()

    #################################################################

    @property
    def receiver_count(self):
        return len(self.receivers)

    #################################################################

    @property
    def shot_count(self):
        return len(self.shots)

    #################################################################

    def receiver_patch(self, patch_number):
        """Return patch geometry for a patch index so acquisition consumes geometry, not formulas."""

        if patch_number < 1:
            raise ValueError("patch_number must be >= 1")

        receiver_lines = sorted({node.line for node in self.receivers})

        if not receiver_lines:
            raise ValueError("Receiver geometry has not been generated")

        total_lines = receiver_lines[-1]
        patch_size = self.survey.active_receiver_lines

        first_receiver_line = patch_number
        last_receiver_line = min(
            first_receiver_line + patch_size - 1,
            total_lines,
        )

        if first_receiver_line > total_lines:
            raise ValueError("patch_number exceeds available receiver lines")

        return ReceiverPatch(
            patch_number=patch_number,
            first_receiver_line=first_receiver_line,
            last_receiver_line=last_receiver_line,
            trigger_shot_station=self.trigger_shot_station(
                first_receiver_line,
                last_receiver_line,
            ),
            receiver_line_count=(last_receiver_line - first_receiver_line + 1),
        )

    #################################################################

    def trigger_shot_station(self, first_receiver_line, last_receiver_line):
        """Compute the patch-roll trigger in Geometry so Acquisition remains sequence-only logic."""

        if first_receiver_line < 1 or last_receiver_line < first_receiver_line:
            raise ValueError("Invalid receiver line range")

        if not self.shots:
            raise ValueError("Shot geometry has not been generated")

        center_line = (first_receiver_line + last_receiver_line) / 2.0

        trigger = round(
            center_line * self.survey.receiver_line_spacing / self.survey.shot_interval
        )

        shot_stations = sorted({shot.station for shot in self.shots})

        return max(
            shot_stations[0],
            min(trigger, shot_stations[-1]),
        )

    #################################################################

    def _build_basis(self):
        theta = math.radians(self.survey.receiver_line_azimuth)

        rx = math.sin(theta)
        ry = math.cos(theta)

        if rx < 0.0 or (rx == 0.0 and ry < 0.0):
            rx = -rx
            ry = -ry

        tx = -ry
        ty = rx

        if ty < 0.0 or (ty == 0.0 and tx < 0.0):
            tx = -tx
            ty = -ty

        self._station_direction = (rx, ry)
        self._line_direction = (tx, ty)

    #################################################################

    def _compute_grid_bounds(self):
        xmin, ymin, xmax, ymax = self.gis.bounds

        ox = xmin
        oy = ymin

        corners = [
            (xmin, ymin),
            (xmin, ymax),
            (xmax, ymin),
            (xmax, ymax),
        ]

        u_values = [
            self._project(x - ox, y - oy, self._station_direction)
            for x, y in corners
        ]

        v_values = [
            self._project(x - ox, y - oy, self._line_direction)
            for x, y in corners
        ]

        self._u_min = min(u_values)
        self._u_max = max(u_values)
        self._v_min = min(v_values)
        self._v_max = max(v_values)

        self._origin = (ox, oy)

    #################################################################

    def _generate_receivers(self):
        station_step = self.survey.receiver_interval
        line_step = self.survey.receiver_line_spacing

        station_min = math.floor(self._u_min / station_step) - 1
        station_max = math.ceil(self._u_max / station_step) + 1
        line_min = math.floor(self._v_min / line_step) - 1
        line_max = math.ceil(self._v_max / line_step) + 1

        receiver_rows = {}
        receiver_id = 1

        for line_index in range(line_min, line_max + 1):
            row = []

            for station_index in range(station_min, station_max + 1):
                x, y = self._grid_point(
                    station_index,
                    line_index,
                    station_step,
                    line_step,
                    self._station_direction,
                    self._line_direction,
                )

                row.append((station_index, SurveyNode(
                    id=receiver_id,
                    line=0,
                    station=0,
                    x=x,
                    y=y,
                    inside_boundary=self._point_inside_boundary(x, y),
                )))

                receiver_id += 1

            receiver_rows[line_index] = row

        sorted_lines = sorted(
            receiver_rows.items(),
            key=lambda item: min(point.y for _, point in item[1])
        )

        self.receivers = []
        line_number = 1

        for _, line_points in sorted_lines:
            sorted_points = sorted(
                (point for _, point in line_points),
                key=lambda point: (point.x, point.y)
            )

            station_number = 1
            for point in sorted_points:
                point.line = line_number
                point.station = station_number
                self.receivers.append(point)
                station_number += 1

            line_number += 1

    #################################################################

    def _generate_shots(self):
        station_step = self.survey.shot_interval
        line_step = self.survey.source_line_spacing

        station_min = math.floor(self._v_min / station_step) - 1
        station_max = math.ceil(self._v_max / station_step) + 1
        line_min = math.floor(self._u_min / line_step) - 1
        line_max = math.ceil(self._u_max / line_step) + 1

        source_rows = {}
        shot_id = 1

        for line_index in range(line_min, line_max + 1):
            row = []

            for station_index in range(station_min, station_max + 1):
                x, y = self._grid_point(
                    line_index,
                    station_index,
                    line_step,
                    station_step,
                    self._station_direction,
                    self._line_direction,
                )

                row.append((station_index, SurveyNode(
                    id=shot_id,
                    line=0,
                    station=0,
                    x=x,
                    y=y,
                    inside_boundary=self._point_inside_boundary(x, y),
                )))

                shot_id += 1

            source_rows[line_index] = row

        sorted_lines = sorted(
            source_rows.items(),
            key=lambda item: min(point.x for _, point in item[1])
        )

        self.shots = []
        line_number = 1

        for _, line_points in sorted_lines:
            sorted_points = sorted(
                (point for _, point in line_points),
                key=lambda point: (point.y, point.x)
            )

            station_number = 1
            for point in sorted_points:
                point.line = line_number
                point.station = station_number
                self.shots.append(point)
                station_number += 1

            line_number += 1

    #################################################################

    def _project(self, dx, dy, direction):
        bx, by = direction
        return dx * bx + dy * by

    #################################################################

    def _grid_point(
        self,
        station_index,
        line_index,
        station_step,
        line_step,
        station_direction,
        line_direction,
    ):
        ox, oy = self._origin

        sx, sy = station_direction
        lx, ly = line_direction

        x = ox + station_index * station_step * sx
        y = oy + station_index * station_step * sy

        x += line_index * line_step * lx
        y += line_index * line_step * ly

        return x, y

    #################################################################

    def _point_inside_boundary(self, x, y):
        polygon = getattr(self.gis, "polygon", None)

        if polygon is None:
            return False

        if self._point_transformer is not None:
            x, y = self._point_transformer.transform(x, y)

        point = Point(x, y)

        try:
            return polygon.covers(point)
        except AttributeError:
            return polygon.contains(point) or polygon.touches(point)

    #################################################################

    def _configure_boundary_tester(self):
        self._point_transformer = None

        boundary_crs = getattr(self.gis, "crs", None)
        geometry_crs = getattr(self, "crs", None)

        if boundary_crs is None or geometry_crs is None:
            return

        boundary_crs = CRS.from_user_input(boundary_crs)
        geometry_crs = CRS.from_user_input(geometry_crs)

        if boundary_crs == geometry_crs:
            return

        self._point_transformer = Transformer.from_crs(
            geometry_crs,
            boundary_crs,
            always_xy=True,
        )

