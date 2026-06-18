import matplotlib.pyplot as plt


class Plotter:

    @staticmethod
    def plot_geometry(rx, ry, sx, sy):

        plt.figure(figsize=(8, 8))

        plt.scatter(
            rx,
            ry,
            s=5,
            label="Receivers"
        )

        plt.scatter(
            sx,
            sy,
            s=8,
            marker="x",
            label="Shots"
        )

        plt.xlabel("X (ft)")
        plt.ylabel("Y (ft)")

        plt.title("Survey Geometry")

        plt.axis("equal")

        plt.legend()

        plt.show()