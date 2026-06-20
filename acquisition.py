from dataclasses import dataclass


@dataclass
class AcquisitionEvent:
    event_type: str
    description: str


class AcquisitionSimulator:

    def __init__(self, survey, geometry):
        self.survey = survey
        self.geometry = geometry

    #################################################################

    def generate_schedule(self):
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
            events.append(
                AcquisitionEvent(
                    event_type="END_SURVEY",
                    description="End acquisition sequence (no geometry available).",
                )
            )
            return events

        patch_size = self.survey.active_receiver_lines

        south_index = 0
        north_index = min(patch_size - 1, len(receiver_line_numbers) - 1)

        events.append(
            AcquisitionEvent(
                event_type="DEPLOY_PATCH",
                description=(
                    f"Deploy receiver patch RL{receiver_line_numbers[south_index]}"
                    f"-RL{receiver_line_numbers[north_index]}."
                ),
            )
        )

        south_line = receiver_line_numbers[south_index]
        north_line = receiver_line_numbers[north_index]

        center_line = (south_line + north_line) / 2.0
        center_station = round(
            center_line * self.survey.receiver_line_spacing / self.survey.shot_interval
        )
        center_station = max(
            shot_station_numbers[0],
            min(center_station, shot_station_numbers[-1]),
        )

        for shot_station in shot_station_numbers:
            south_line = receiver_line_numbers[south_index]
            north_line = receiver_line_numbers[north_index]

            if shot_station % 2 == 1:
                line_sequence = source_line_numbers
                direction = "west->east"
            else:
                line_sequence = list(reversed(source_line_numbers))
                direction = "east->west"

            first_source = line_sequence[0]
            last_source = line_sequence[-1]

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

            if shot_station == center_station and north_index < len(receiver_line_numbers) - 1:
                old_south = receiver_line_numbers[south_index]
                next_north = receiver_line_numbers[north_index + 1]

                events.append(
                    AcquisitionEvent(
                        event_type="ROLL_RECEIVER_LINE",
                        description=(
                            f"Roll receiver line RL{old_south} to become next "
                            f"northern line RL{next_north}."
                        ),
                    )
                )

                south_index += 1
                north_index += 1

                south_line = receiver_line_numbers[south_index]
                north_line = receiver_line_numbers[north_index]
                center_line = (south_line + north_line) / 2.0
                center_station = round(
                    center_line * self.survey.receiver_line_spacing / self.survey.shot_interval
                )
                center_station = max(
                    shot_station_numbers[0],
                    min(center_station, shot_station_numbers[-1]),
                )

        final_south = receiver_line_numbers[south_index]
        final_north = receiver_line_numbers[north_index]

        events.append(
            AcquisitionEvent(
                event_type="ROLL_RECEIVER_LINE",
                description=(
                    "Roll off north end: release active patch "
                    f"RL{final_south}-RL{final_north}."
                ),
            )
        )

        events.append(
            AcquisitionEvent(
                event_type="END_SURVEY",
                description="End acquisition sequence.",
            )
        )

        return events
