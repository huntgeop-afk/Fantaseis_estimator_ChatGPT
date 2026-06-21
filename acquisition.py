from dataclasses import dataclass
from survey_state import SurveyState


@dataclass
class AcquisitionEvent:
    event_type: str
    description: str


class AcquisitionSimulator:

    def __init__(self, survey, geometry):
        self.survey = survey
        self.geometry = geometry
        self.state = SurveyState()
        self.shot_patch_lookup = {}

    #################################################################

    def active_receivers_for_shot(self, shot):
        key = (shot.line, shot.station)

        if key not in self.shot_patch_lookup:
            raise KeyError(
                "No active receiver patch recorded for "
                f"shot line {shot.line}, station {shot.station}."
            )

        first_receiver_line, last_receiver_line = self.shot_patch_lookup[key]

        return [
            receiver
            for receiver in self.geometry.receivers
            if (
                first_receiver_line
                <= receiver.line
                <= last_receiver_line
            )
        ]

    #################################################################

    def generate_schedule(self):
        self.shot_patch_lookup = {}
        self.state.begin_survey()
        self.state.first_active_receiver_line = 1
        self.state.last_active_receiver_line = self.survey.active_receiver_lines
        self.state.current_shot_station = 1

        events = [
            AcquisitionEvent(
                event_type="BEGIN_SURVEY",
                description="Begin acquisition sequence.",
            )
        ]

        receiver_line_numbers = sorted(
            {receiver.line for receiver in self.geometry.receivers}
        )

        shot_station_numbers = sorted(
            {shot.station for shot in self.geometry.shots}
        )

        source_line_numbers = sorted(
            {shot.line for shot in self.geometry.shots}
        )

        if not receiver_line_numbers or not shot_station_numbers or not source_line_numbers:
            self.state.finish_survey()
            events.append(
                AcquisitionEvent(
                    event_type="END_SURVEY",
                    description="End acquisition sequence (no geometry available).",
                )
            )
            return events

        self.state.last_active_receiver_line = min(
            self.state.last_active_receiver_line,
            receiver_line_numbers[-1],
        )

        events.append(
            AcquisitionEvent(
                event_type="DEPLOY_PATCH",
                description=(
                    f"Deploy receiver patch RL{self.state.first_active_receiver_line}"
                    f"-RL{self.state.last_active_receiver_line}."
                ),
            )
        )

        center_line = (
            self.state.first_active_receiver_line +
            self.state.last_active_receiver_line
        ) / 2.0
        center_station = round(
            center_line * self.survey.receiver_line_spacing / self.survey.shot_interval
        )
        center_station = max(
            shot_station_numbers[0],
            min(center_station, shot_station_numbers[-1]),
        )

        max_shot_station = shot_station_numbers[-1]

        while self.state.current_shot_station <= max_shot_station:
            shot_station = self.state.current_shot_station
            south_line = self.state.first_active_receiver_line
            north_line = self.state.last_active_receiver_line

            if self.state.current_source_direction == "WEST_TO_EAST":
                line_sequence = source_line_numbers
                direction = "west->east"
            else:
                line_sequence = list(reversed(source_line_numbers))
                direction = "east->west"

            first_source = line_sequence[0]
            last_source = line_sequence[-1]

            for source_line in line_sequence:
                self.shot_patch_lookup[(source_line, shot_station)] = (
                    self.state.first_active_receiver_line,
                    self.state.last_active_receiver_line,
                )

            events.append(
                AcquisitionEvent(
                    event_type="SHOOT_SHOT_STATION",
                    description=(
                        f"Shoot shot station SS{shot_station}: "
                        f"SL{first_source} to SL{last_source} ({direction}) "
                        f"with active patch RL{south_line}-RL{north_line}."
                    ),
                )
            )

            self.state.advance_shot_station()

            if (
                shot_station == center_station and
                self.state.last_active_receiver_line < receiver_line_numbers[-1]
            ):
                old_south = self.state.first_active_receiver_line
                next_north = self.state.last_active_receiver_line + 1

                events.append(
                    AcquisitionEvent(
                        event_type="ROLL_RECEIVER_LINE",
                        description=(
                            f"Roll receiver line RL{old_south} to become next "
                            f"northern line RL{next_north}."
                        ),
                    )
                )

                self.state.roll_receiver_patch()

                center_line = (
                    self.state.first_active_receiver_line +
                    self.state.last_active_receiver_line
                ) / 2.0
                center_station = round(
                    center_line * self.survey.receiver_line_spacing / self.survey.shot_interval
                )
                center_station = max(
                    shot_station_numbers[0],
                    min(center_station, shot_station_numbers[-1]),
                )

        final_south = self.state.first_active_receiver_line
        final_north = self.state.last_active_receiver_line

        events.append(
            AcquisitionEvent(
                event_type="ROLL_RECEIVER_LINE",
                description=(
                    "Roll off north end: release active patch "
                    f"RL{final_south}-RL{final_north}."
                ),
            )
        )

        self.state.finish_survey()

        events.append(
            AcquisitionEvent(
                event_type="END_SURVEY",
                description="End acquisition sequence.",
            )
        )

        return events
