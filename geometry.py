
import numpy as np
from dataclasses import dataclass
from .models import Survey

@dataclass
class GeometryResult:
    receiver_x: np.ndarray
    receiver_y: np.ndarray
    shot_x: np.ndarray
    shot_y: np.ndarray

class GeometryEngine:
    def __init__(self, survey: Survey):
        self.survey = survey

    def build(self):
        s=self.survey
        nlines=s.receiver_lines_per_patch+s.spare_receiver_lines
        rx_x=np.arange(0,s.width+0.01,s.receiver_interval)
        rx_y=np.arange(nlines)*s.receiver_line_spacing
        RX,RY=np.meshgrid(rx_x,rx_y)

        sx=np.arange(0,s.width+0.01,s.source_line_spacing)
        sy=np.arange(0,s.height+0.01,s.source_interval)
        SX,SY=np.meshgrid(sx,sy)

        return GeometryResult(RX.ravel(),RY.ravel(),SX.ravel(),SY.ravel())
