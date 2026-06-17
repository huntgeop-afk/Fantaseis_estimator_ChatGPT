from dataclasses import dataclass

@dataclass
class Survey:
    width: float
    height: float

    receiver_interval: float
    receiver_line_spacing: float
    receiver_lines_active: int
    receiver_lines_spare: int

    source_interval: float
    source_line_spacing: float

    target_depth: float
