import numpy as np


class Geometry:

    def __init__(self, survey):
        self.survey = survey

    def generate_receivers(self):

        xs = np.arange(
            0,
            self.survey.width + self.survey.receiver_interval,
            self.survey.receiver_interval
        )

        ys = np.arange(
            0,
            self.survey.receiver_lines * self.survey.receiver_line_spacing,
            self.survey.receiver_line_spacing
        )

        X, Y = np.meshgrid(xs, ys)

        return X.flatten(), Y.flatten()

    def generate_sources(self):

        xs = np.arange(
            0,
            self.survey.width + self.survey.source_line_spacing,
            self.survey.source_line_spacing
        )

        ys = np.arange(
            0,
            self.survey.height + self.survey.source_interval,
            self.survey.source_interval
        )

        X, Y = np.meshgrid(xs, ys)

        return X.flatten(), Y.flatten()