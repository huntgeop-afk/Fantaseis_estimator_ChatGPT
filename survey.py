from dataclasses import dataclass
import json
from pathlib import Path
import math


@dataclass
class Survey:

    #
    # Receiver Geometry
    #

    receiver_line_spacing: float
    receiver_interval: float
    receiver_line_azimuth: float

    #
    # Source Geometry
    #

    source_line_spacing: float
    shot_interval: float

    #
    # Acquisition
    #

    active_receiver_lines: int

    #
    # Survey Design
    #

    target_depth: float
    maximum_incidence_angle: float

    #################################################################

    @classmethod
    def load(cls, project_folder):

        filename = Path(project_folder) / "survey.json"

        with open(filename) as f:

            data = json.load(f)

        return cls(**data)

    #################################################################
    #
    # Unit vectors
    #
    # Coordinate System:
    #
    # X increases East
    # Y increases North
    #
    # Azimuth:
    #
    # 0°   = North
    # 90°  = East
    # 180° = South
    # 270° = West
    #
    #################################################################

    @property
    def receiver_station_vector(self):

        theta = math.radians(self.receiver_line_azimuth)

        return (

            math.sin(theta),

            math.cos(theta)

        )

    #################################################################

    @property
    def receiver_line_vector(self):

        #
        # Rotate receiver direction
        # 90° counter-clockwise
        #
        # Gives line numbering that
        # increases to the LEFT of
        # station direction.
        #

        theta = math.radians(
            self.receiver_line_azimuth + 90.0
        )

        return (

            math.sin(theta),

            math.cos(theta)

        )

    #################################################################

    @property
    def source_station_vector(self):

        #
        # Source stations are
        # perpendicular to receiver lines.
        #

        theta = math.radians(
            self.receiver_line_azimuth + 90.0
        )

        return (

            math.sin(theta),

            math.cos(theta)

        )

    #################################################################

    @property
    def source_line_vector(self):

        theta = math.radians(
            self.receiver_line_azimuth
        )

        return (

            math.sin(theta),

            math.cos(theta)

        )

    #################################################################

    def __str__(self):

        lines = [

            f"Receiver Line Spacing : {self.receiver_line_spacing:.1f} ft",
            f"Receiver Interval     : {self.receiver_interval:.1f} ft",
            f"Receiver Azimuth      : {self.receiver_line_azimuth:.1f}°",

            "",

            f"Source Line Spacing   : {self.source_line_spacing:.1f} ft",
            f"Shot Interval         : {self.shot_interval:.1f} ft",

            "",

            f"Active Receiver Lines : {self.active_receiver_lines}",

            "",

            f"Target Depth          : {self.target_depth:.1f} ft",
            f"Maximum AVO Angle     : {self.maximum_incidence_angle:.1f}°"

        ]

        return "\n".join(lines)