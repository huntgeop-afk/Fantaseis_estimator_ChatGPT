from pathlib import Path
import geopandas as gpd


class GISProject:

    def __init__(self, project_folder):

        self.project_folder = Path(project_folder)

        self.boundary = None

    def load_boundary(self):

        shapefile = self.project_folder / "boundary.shp"

        self.boundary = gpd.read_file(shapefile)

        return self.boundary

    @property
    def crs(self):

        return self.boundary.crs

    @property
    def bounds(self):

        return self.boundary.total_bounds