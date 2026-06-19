from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class Survey:

    receiver_line_spacing: float
    receiver_interval: float

    source_line_spacing: float
    shot_interval: float

    active_receiver_lines: int

    target_depth: float

    maximum_incidence_angle: float

    @classmethod
    def load(cls, project_folder):

        filename = Path(project_folder) / "survey.json"

        with open(filename) as f:

            data = json.load(f)

        return cls(**data)