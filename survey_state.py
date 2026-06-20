from dataclasses import dataclass


@dataclass
class SurveyState:

    current_receiver_patch: int = 0
    first_active_receiver_line: int = 0
    last_active_receiver_line: int = 0

    current_shot_station: int = 0

    current_source_direction: str = "WEST_TO_EAST"

    shots_completed: int = 0
    receiver_rolls_completed: int = 0

    deployed_nodes: int = 0
    picked_up_nodes: int = 0

    total_receivers: int = 0
    total_shots: int = 0

    survey_complete: bool = False

    #################################################################

    def begin_survey(self):
        self.current_receiver_patch = 1
        self.current_source_direction = "WEST_TO_EAST"
        self.shots_completed = 0
        self.receiver_rolls_completed = 0
        self.deployed_nodes = 0
        self.picked_up_nodes = 0
        self.survey_complete = False

    #################################################################

    def advance_shot_station(self):
        self.current_shot_station += 1
        self.shots_completed += 1

        if self.current_source_direction == "WEST_TO_EAST":
            self.current_source_direction = "EAST_TO_WEST"
        else:
            self.current_source_direction = "WEST_TO_EAST"

    #################################################################

    def roll_receiver_patch(self):
        self.current_receiver_patch += 1
        self.first_active_receiver_line += 1
        self.last_active_receiver_line += 1
        self.receiver_rolls_completed += 1

    #################################################################

    def finish_survey(self):
        self.survey_complete = True

    #################################################################

    def summary(self):
        return "\n".join([
            f"Receiver Patch: {self.current_receiver_patch}",
            f"Active Receiver Lines: {self.first_active_receiver_line}-{self.last_active_receiver_line}",
            f"Current Shot Station: {self.current_shot_station}",
            f"Source Direction: {self.current_source_direction}",
            f"Shots Completed: {self.shots_completed}",
            f"Receiver Rolls: {self.receiver_rolls_completed}",
            f"Survey Complete: {self.survey_complete}",
        ])
