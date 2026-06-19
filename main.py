import sys

from survey import Survey
from gis import GISProject
from geometry import Geometry
from plotting import Plotter


def main():

    if len(sys.argv) != 2:

        print()
        print("Usage:")
        print("python main.py <project folder>")
        return

    project = sys.argv[1]

    survey = Survey.load(project)

    gis = GISProject(project)

    gis.load_boundary()

    geometry = Geometry(survey, gis)

    geometry.generate()

    print()
    print("---------------------------------------")
    print("Survey Parameters")
    print("---------------------------------------")
    print(survey)

    print()
    print("---------------------------------------")
    print("GIS Information")
    print("---------------------------------------")

    print(f"CRS : {gis.crs}")

    xmin, ymin, xmax, ymax = gis.bounds

    print()
    print("Bounds")
    print(f"West  : {xmin:.2f}")
    print(f"South : {ymin:.2f}")
    print(f"East  : {xmax:.2f}")
    print(f"North : {ymax:.2f}")

    print()
    print("---------------------------------------")
    print("Generated Geometry")
    print("---------------------------------------")

    print(f"Receiver Nodes : {geometry.receiver_count}")
    print(f"Shot Points    : {geometry.shot_count}")

    inside_receivers = sum(r.inside_boundary for r in geometry.receivers)
    inside_shots = sum(s.inside_boundary for s in geometry.shots)

    print(f"Receivers Inside Boundary : {inside_receivers}")
    print(f"Shots Inside Boundary     : {inside_shots}")

    #
    # Display geometry
    #

    plotter = Plotter(gis, geometry)

    plotter.plot_geometry()


if __name__ == "__main__":
    main()