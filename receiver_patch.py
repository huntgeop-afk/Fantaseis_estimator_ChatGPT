class ReceiverPatch:

    def __init__(self, survey):

        self.survey = survey

        self.south_receiver_line = 1

    @property
    def north_receiver_line(self):

        return (
            self.south_receiver_line
            + self.survey.active_receiver_lines
            - 1
        )

    @property
    def south_y(self):

        return (
            (self.south_receiver_line - 1)
            * self.survey.receiver_line_spacing
        )

    @property
    def north_y(self):

        return (
            (self.north_receiver_line - 1)
            * self.survey.receiver_line_spacing
        )

    @property
    def center_y(self):

        return (
            self.south_y +
            self.north_y
        ) / 2.0

    @property
    def trigger_row(self):

        return round(
            self.center_y /
            self.survey.shot_interval
        ) + 1

    def roll(self):

        self.south_receiver_line += 1