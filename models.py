
from dataclasses import dataclass

@dataclass
class Survey:
    width: float
    height: float
    receiver_line_spacing: float
    receiver_interval: float
    receiver_lines_per_patch: int
    spare_receiver_lines: int
    source_line_spacing: float
    source_interval: float
