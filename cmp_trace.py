from dataclasses import dataclass


@dataclass
class CMPTrace:
    """Represents one seismic trace contributing to a CMP bin."""

    shot_id: int
    receiver_id: int
    midpoint_x: float
    midpoint_y: float
    offset: float
    azimuth_deg: float

    #################################################################

    def midpoint(self):
        return (self.midpoint_x, self.midpoint_y)

    #################################################################

    def summary(self):
        return (
            f"Shot {self.shot_id}"
            f"Receiver {self.receiver_id}"
            f"Offset {self.offset:.0f} ft"
            f"Azimuth {self.azimuth_deg:.1f}\N{DEGREE SIGN}"
            f"Midpoint ({self.midpoint_x:.1f}, {self.midpoint_y:.1f})"
        )
