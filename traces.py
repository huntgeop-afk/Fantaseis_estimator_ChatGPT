import numpy as np


class TraceDatabase:

    def __init__(self, rx, ry, sx, sy):

        self.rx = rx
        self.ry = ry
        self.sx = sx
        self.sy = sy

    def build(self):

        # Every shot paired with every receiver

        SX, RX = np.meshgrid(self.sx, self.rx)
        SY, RY = np.meshgrid(self.sy, self.ry)

        # Midpoints

        cmpx = (SX + RX) / 2.0
        cmpy = (SY + RY) / 2.0

        # Offset

        offset = np.sqrt((SX - RX) ** 2 + (SY - RY) ** 2)

        # Azimuth (degrees)

        azimuth = np.degrees(
            np.arctan2(
                RY - SY,
                RX - SX
            )
        )

        return (
            cmpx.flatten(),
            cmpy.flatten(),
            offset.flatten(),
            azimuth.flatten()
        )