import numpy as np

class Geometry:

    def __init__(self, survey):
        self.survey = survey

    def build_receivers(self):

        s = self.survey

        total_lines = s.receiver_lines_active + s.receiver_lines_spare

        x = np.arange(
            0,
            s.width + s.receiver_interval,
            s.receiver_interval
        )

        y = np.arange(total_lines) * s.receiver_line_spacing

        X, Y = np.meshgrid(x, y)

        return X.flatten(), Y.flatten()

    def build_sources(self):

        s = self.survey

        x = np.arange(
            0,
            s.width + s.source_line_spacing,
            s.source_line_spacing
        )

        y = np.arange(
            0,
            s.height + s.source_interval,
            s.source_interval
        )

        X, Y = np.meshgrid(x, y)

        return X.flatten(), Y.flatten()
