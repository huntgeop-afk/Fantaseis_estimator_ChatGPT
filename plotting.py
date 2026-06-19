import matplotlib.pyplot as plt


class Plotter:

    def __init__(self, gis, geometry):

        self.gis = gis
        self.geometry = geometry

    ##################################################################

    def plot_geometry(self):

        fig, ax = plt.subplots(figsize=(10, 10))

        #
        # Survey Boundary
        #

        self.gis.boundary.boundary.plot(

            ax=ax,

            color="black",

            linewidth=2

        )

        #
        # Receiver Nodes
        #

        rx_inside_x = []
        rx_inside_y = []

        rx_outside_x = []
        rx_outside_y = []

        for receiver in self.geometry.receivers:

            if receiver.inside_boundary:

                rx_inside_x.append(receiver.x)
                rx_inside_y.append(receiver.y)

            else:

                rx_outside_x.append(receiver.x)
                rx_outside_y.append(receiver.y)

        ax.scatter(

            rx_inside_x,

            rx_inside_y,

            s=10,

            c="blue",

            marker="o",

            label="Receivers (Inside)"

        )

        ax.scatter(

            rx_outside_x,

            rx_outside_y,

            s=10,

            c="lightblue",

            marker="o",

            label="Receivers (Outside)"

        )

        #
        # Shot Points
        #

        shot_inside_x = []
        shot_inside_y = []

        shot_outside_x = []
        shot_outside_y = []

        for shot in self.geometry.shots:

            if shot.inside_boundary:

                shot_inside_x.append(shot.x)
                shot_inside_y.append(shot.y)

            else:

                shot_outside_x.append(shot.x)
                shot_outside_y.append(shot.y)

        ax.scatter(

            shot_inside_x,

            shot_inside_y,

            s=10,

            c="red",

            marker="+",

            label="Shots (Inside)"

        )

        ax.scatter(

            shot_outside_x,

            shot_outside_y,

            s=10,

            c="pink",

            marker="+",

            label="Shots (Outside)"

        )

        #
        # Cosmetic settings
        #

        ax.set_title("FantaSeis Survey Geometry")

        ax.set_xlabel("X")

        ax.set_ylabel("Y")

        ax.set_aspect("equal")

        ax.grid(True)

        ax.legend()

        plt.tight_layout()

        plt.show()