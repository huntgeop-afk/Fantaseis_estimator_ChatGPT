from survey_state import SurveyState
from receiver_patch import ReceiverPatch


class AcquisitionSimulator:

    def __init__(self, survey):

        self.survey = survey
        self.state = SurveyState()
        self.patch = ReceiverPatch(survey)

    def complete_shot_row(self):

        direction = "W->E" if self.state.eastbound else "E->W"

        print(
            f"Row {self.state.current_shot_row:3d}   "
            f"{direction:5s}   "
            f"Patch {self.patch.south_receiver_line:2d}-"
            f"{self.patch.north_receiver_line:2d}",
            end=""
        )

        if self.state.current_shot_row == self.patch.trigger_row:

            self.patch.roll()

            self.state.receiver_rolls += 1

            print("   ROLL")

        else:

            print()

        self.state.completed_rows += 1

        self.state.current_shot_row += 1

        self.state.eastbound = not self.state.eastbound