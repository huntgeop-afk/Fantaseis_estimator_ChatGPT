from dataclasses import dataclass

@dataclass
class Survey:
    # Survey dimensions (feet)
    width: float
    height: float

    # Receiver geometry
    receiver_interval: float
    receiver_line_spacing: float
    receiver_lines: int

    # Source geometry
    source_interval: float
    source_line_spacing: float
