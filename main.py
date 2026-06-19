import sys

import matplotlib.pyplot as plt

from survey import Survey
from gis import GISProject


def main():

    if len(sys.argv) != 2:

        print()

        print("Usage:")

        print("python main.py <project folder>")

        return

    project = sys.argv[1]

    survey = Survey.load(project)

    gis = GISProject(project)

    boundary = gis.load_boundary()

    print()

    print("---------------------------------------")

    print("Survey Parameters")

    print("---------------------------------------")

    print(survey)

    print()

    print("---------------------------------------")

    print("GIS Information")

    print("---------------------------------------")

    print("CRS")

    print(gis.crs)

    print()

    print("Bounds")

    print(gis.bounds)

    ax = boundary.plot(figsize=(8,8))

    ax.set_title("Survey Boundary")

    plt.show()


if __name__ == "__main__":

    main()