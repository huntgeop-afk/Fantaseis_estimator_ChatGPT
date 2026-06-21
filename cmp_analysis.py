from dataclasses import dataclass


@dataclass
class CMPBin:
    """Represents a single CMP bin center and its trace count placeholder."""

    xy: tuple[float, float]
    trace_count: int = 0


@dataclass
class CMPGrid:
    """Stores a regularly spaced CMP bin grid generated from survey geometry."""

    bin_size_x: float
    bin_size_y: float
    bins: list[CMPBin]

    #################################################################

    def bin_count(self):
        return len(self.bins)


class CMPAnalysis:
    """Builds an empty CMP grid scaffold for future common-midpoint analysis."""

    def __init__(self, survey, geometry):
        self.survey = survey
        self.geometry = geometry

    #################################################################

    def generate(self):
        xmin, ymin, xmax, ymax = self._bounds()

        bin_size_x = self.survey.processing_bin_size
        bin_size_y = self.survey.processing_bin_size

        bins = []

        x = xmin + (bin_size_x / 2.0)
        while x <= xmax:
            y = ymin + (bin_size_y / 2.0)
            while y <= ymax:
                bins.append(CMPBin(xy=(x, y), trace_count=0))
                y += bin_size_y
            x += bin_size_x

        return CMPGrid(
            bin_size_x=bin_size_x,
            bin_size_y=bin_size_y,
            bins=bins,
        )

    #################################################################

    def _bounds(self):
        if hasattr(self.geometry, "gis") and hasattr(self.geometry.gis, "bounds"):
            return self.geometry.gis.bounds

        if hasattr(self.geometry, "bounds"):
            return self.geometry.bounds

        raise AttributeError("Geometry does not expose bounds for CMP grid generation")
