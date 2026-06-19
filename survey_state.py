from dataclasses import dataclass


@dataclass
class SurveyState:

    current_shot_row: int = 1

    eastbound: bool = True

    completed_rows: int = 0

    receiver_rolls: int = 0