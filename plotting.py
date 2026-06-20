"""
FantaSeis Survey Designer

Feature 002C

Geometry Plotter
"""

import matplotlib.pyplot as plt


class Plotter:

    """Creates and manages survey figures for interactive use and automated pipelines."""

    def __init__(self, gis, geometry):

        self.gis = gis
        self.geometry = geometry

    ##################################################################

    def plot_geometry(self, show=False, save_path=None, dpi=300):

        fig, ax = plt.subplots(figsize=(10, 10))

        try:
            self._draw_geometry(ax)
            self._format_geometry_axes(ax)

            if save_path is not None:
                fig.savefig(save_path, dpi=dpi, bbox_inches="tight")

            if show:
                plt.show()

        finally:
            plt.close(fig)

    ##################################################################

    def plot_fold_heatmap(self, show=False, save_path=None, dpi=300):

        raise NotImplementedError("Fold heat map plotting is not implemented in Plotter yet.")

    ##################################################################

    def plot_offset_heatmap(self, show=False, save_path=None, dpi=300):

        raise NotImplementedError("Offset heat map plotting is not implemented in Plotter yet.")

    ##################################################################

    def plot_azimuth_rose(self, show=False, save_path=None, dpi=300):

        raise NotImplementedError("Azimuth rose plotting is not implemented in Plotter yet.")

    ##################################################################

    def plot_illumination(self, show=False, save_path=None, dpi=300):

        raise NotImplementedError("Illumination plotting is not implemented in Plotter yet.")

    ##################################################################

    def _draw_geometry(self, ax):

        #
        # -------------------------------------------------------------
        # Survey Boundary
        # -------------------------------------------------------------
        #

        self.gis.boundary.boundary.plot(
            ax=ax,
            color="black",
            linewidth=2.5,
            zorder=5
        )

        #
        # -------------------------------------------------------------
        # Receiver Lines
        # -------------------------------------------------------------
        #

        receiver_lines = {}

        for r in self.geometry.receivers:

            receiver_lines.setdefault(r.line, []).append(r)

        for line in receiver_lines.values():

            line.sort(key=lambda p: p.station)

            x = [p.x for p in line]
            y = [p.y for p in line]

            ax.plot(
                x,
                y,
                color="cornflowerblue",
                linewidth=0.7,
                zorder=1
            )

        #
        # -------------------------------------------------------------
        # Source Lines
        # -------------------------------------------------------------
        #

        source_lines = {}

        for s in self.geometry.shots:

            source_lines.setdefault(s.line, []).append(s)

        for line in source_lines.values():

            line.sort(key=lambda p: p.station)

            x = [p.x for p in line]
            y = [p.y for p in line]

            ax.plot(
                x,
                y,
                color="lightcoral",
                linewidth=0.7,
                zorder=1
            )

        #
        # -------------------------------------------------------------
        # Receiver Nodes
        # -------------------------------------------------------------
        #

        rx_inside_x = []
        rx_inside_y = []

        rx_outside_x = []
        rx_outside_y = []

        for r in self.geometry.receivers:

            if r.inside_boundary:

                rx_inside_x.append(r.x)
                rx_inside_y.append(r.y)

            else:

                rx_outside_x.append(r.x)
                rx_outside_y.append(r.y)

        ax.scatter(
            rx_outside_x,
            rx_outside_y,
            s=8,
            color="lightblue",
            zorder=2
        )

        ax.scatter(
            rx_inside_x,
            rx_inside_y,
            s=10,
            color="blue",
            label="Receiver Nodes",
            zorder=3
        )

        #
        # -------------------------------------------------------------
        # Shot Points
        # -------------------------------------------------------------
        #

        sx_inside_x = []
        sx_inside_y = []

        sx_outside_x = []
        sx_outside_y = []

        for s in self.geometry.shots:

            if s.inside_boundary:

                sx_inside_x.append(s.x)
                sx_inside_y.append(s.y)

            else:

                sx_outside_x.append(s.x)
                sx_outside_y.append(s.y)

        ax.scatter(
            sx_outside_x,
            sx_outside_y,
            marker="+",
            s=18,
            color="pink",
            zorder=2
        )

        ax.scatter(
            sx_inside_x,
            sx_inside_y,
            marker="+",
            s=22,
            color="red",
            label="Shot Points",
            zorder=4
        )

        #
        # -------------------------------------------------------------
        # Survey Origin
        # -------------------------------------------------------------
        #

        xmin, ymin, xmax, ymax = self.gis.bounds

        ax.scatter(
            xmin,
            ymin,
            marker="s",
            s=80,
            color="limegreen",
            edgecolors="black",
            linewidth=1.0,
            label="Survey Origin",
            zorder=10
        )

        #
        # -------------------------------------------------------------
        # RL Labels
        # -------------------------------------------------------------
        #

        for line_number, nodes in receiver_lines.items():

            first = min(nodes, key=lambda p: p.station)

            ax.text(
                first.x - 80,
                first.y,
                f"RL{line_number}",
                fontsize=7,
                ha="right",
                va="center"
            )

        #
        # -------------------------------------------------------------
        # SL Labels
        # -------------------------------------------------------------
        #

        for line_number, shots in source_lines.items():

            first = min(shots, key=lambda p: p.station)

            ax.text(
                first.x,
                first.y - 80,
                f"SL{line_number}",
                fontsize=7,
                ha="center",
                va="top",
                rotation=90
            )

    ##################################################################

    def _format_geometry_axes(self, ax):

        #
        # -------------------------------------------------------------
        # Title
        # -------------------------------------------------------------
        #

        receiver_line_count = len({r.line for r in self.geometry.receivers})
        receiver_station_count = max(
            r.station for r in self.geometry.receivers
        )

        source_line_count = len({s.line for s in self.geometry.shots})
        shot_station_count = max(
            s.station for s in self.geometry.shots
        )

        title = (
            "FantaSeis Survey Geometry\n\n"
            f"Receiver Lines: {receiver_line_count}    "
            f"Stations/Line: {receiver_station_count}    "
            f"Nodes: {len(self.geometry.receivers)}\n"
            f"Source Lines: {source_line_count}    "
            f"Shots/Line: {shot_station_count}    "
            f"Shots: {len(self.geometry.shots)}"
        )

        ax.set_title(title, fontsize=12)

        ax.set_xlabel("X Coordinate (ft)")
        ax.set_ylabel("Y Coordinate (ft)")

        ax.set_aspect("equal")

        ax.grid(True, linestyle="--", linewidth=0.4)

        ax.legend(loc="upper right")

        plt.tight_layout()