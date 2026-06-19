from dataclasses import dataclass
from shapely.geometry import Point


@dataclass
class ReceiverNode:

    id: int
    line: int
    station: int

    x: float
    y: float

    inside_boundary: bool


@dataclass
class ShotPoint:

    id: int
    line: int
    station: int

    x: float
    y: float

    inside_boundary: bool


class Geometry:

    def __init__(self, survey, gis):

        self.survey = survey
        self.gis = gis

        self.receivers = []
        self.shots = []

    #################################################################

    def generate(self):

        self.generate_receivers()
        self.generate_shots()

    #################################################################

    def generate_receivers(self):

        xmin, ymin, xmax, ymax = self.gis.bounds

        polygon = self.gis.polygon

        receiver_id = 1

        line = 1

        y = ymin

        while y <= ymax + 0.01:

            station = 1

            x = xmin

            while x <= xmax + 0.01:

                inside = polygon.covers(Point(x, y))

                self.receivers.append(

                    ReceiverNode(

                        id=receiver_id,

                        line=line,

                        station=station,

                        x=x,

                        y=y,

                        inside_boundary=inside

                    )

                )

                receiver_id += 1
                station += 1

                x += self.survey.receiver_interval

            line += 1

            y += self.survey.receiver_line_spacing

    #################################################################

    def generate_shots(self):

        xmin, ymin, xmax, ymax = self.gis.bounds

        polygon = self.gis.polygon

        shot_id = 1

        line = 1

        x = xmin

        while x <= xmax + 0.01:

            station = 1

            y = ymin

            while y <= ymax + 0.01:

                inside = polygon.covers(Point(x, y))

                self.shots.append(

                    ShotPoint(

                        id=shot_id,

                        line=line,

                        station=station,

                        x=x,

                        y=y,

                        inside_boundary=inside

                    )

                )

                shot_id += 1
                station += 1

                y += self.survey.shot_interval

            line += 1

            x += self.survey.source_line_spacing

    #################################################################

    @property
    def receiver_count(self):

        return len(self.receivers)

    @property
    def shot_count(self):

        return len(self.shots)