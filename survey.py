from dataclasses import dataclass
import math


@dataclass
class Survey:

    # Survey dimensions (feet)

    survey_width: float
    survey_height: float

    # Geometry

    receiver_line_spacing: float
    receiver_interval: float

    source_line_spacing: float
    shot_interval: float

    active_receiver_lines: int

    @property
    def receiver_lines(self):

        return (
            math.floor(
                self.survey_width /
                self.receiver_line_spacing
            ) + 1
        )

    @property
    def source_lines(self):

        return (
            math.floor(
                self.survey_width /
                self.source_line_spacing
            ) + 1
        )

    @property
    def receiver_stations(self):

        return (
            math.floor(
                self.survey_height /
                self.receiver_interval
            ) + 1
        )

    @property
    def shot_rows(self):

        return (
            math.floor(
                self.survey_height /
                self.shot_interval
            ) + 1
        )