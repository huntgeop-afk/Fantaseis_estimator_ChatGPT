import sys

from survey import Survey
from gis import GISProject
from geometry import Geometry
from plotting import Plotter
from exporter import Exporter


def main():

    if len(sys.argv) != 2:

        print()
        print("Usage:")
        print("python main.py <project folder>")
        return

    project = sys.argv[1]

    #
    # Load survey
    #

    survey = Survey.load(project)

    gis = GISProject(project)

    gis.load_boundary()

    #
    # Generate geometry
    #

    geometry = Geometry(survey, gis)

    geometry.generate()

    #
    # Export CSV files
    #

    exporter = Exporter(project)

    receiver_file, shot_file = exporter.export(geometry)

    #
    # Console summary
    #

    print()
    print("=========================================")
    print("FantaSeis Survey Designer")
    print("=========================================")

    print()
    print("Survey Parameters")
    print("------------------------------")

    print(survey)

    print()
    print("Survey Bounds")
    print("------------------------------")

    xmin, ymin, xmax, ymax = gis.bounds

    print(f"West :  {xmin:.2f}")
    print(f"South:  {ymin:.2f}")
    print(f"East :  {xmax:.2f}")
    print(f"North:  {ymax:.2f}")

    #
    # Geometry summary
    #

    receiver_lines = max(r.line for r in geometry.receivers)
    receiver_stations = max(r.station for r in geometry.receivers)

    source_lines = max(s.line for s in geometry.shots)
    shot_stations = max(s.station for s in geometry.shots)

    print()
    print("Generated Geometry")
    print("------------------------------")

    print(f"Receiver Lines     : {receiver_lines}")
    print(f"Stations / Line    : {receiver_stations}")
    print(f"Receiver Nodes     : {geometry.receiver_count}")

    print()

    print(f"Source Lines       : {source_lines}")
    print(f"Shots / Line       : {shot_stations}")
    print(f"Shot Points        : {geometry.shot_count}")

    inside_receivers = sum(r.inside_boundary for r in geometry.receivers)
    inside_shots = sum(s.inside_boundary for s in geometry.shots)

    print()
    print(f"Receivers Inside Boundary : {inside_receivers}")
    print(f"Shots Inside Boundary     : {inside_shots}")

    print()
    print("Files Written")
    print("------------------------------")

    print(receiver_file)
    print(shot_file)

    #
    # Plot geometry
    #

    plotter = Plotter(gis, geometry)

    plotter.plot_geometry()


if __name__ == "__main__":
    main()