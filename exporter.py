from pathlib import Path
import csv


class Exporter:

    def __init__(self, project_folder):

        self.project_folder = Path(project_folder)

    #################################################################

    def export_receivers(self, receivers):

        filename = self.project_folder / "receivers.csv"

        with open(filename, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([
                "ID",
                "Line",
                "Station",
                "X",
                "Y",
                "InsideBoundary"
            ])

            for r in receivers:

                writer.writerow([
                    r.id,
                    r.line,
                    r.station,
                    f"{r.x:.3f}",
                    f"{r.y:.3f}",
                    int(r.inside_boundary)
                ])

        return filename

    #################################################################

    def export_shots(self, shots):

        filename = self.project_folder / "shots.csv"

        with open(filename, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow([
                "ID",
                "Line",
                "Station",
                "X",
                "Y",
                "InsideBoundary"
            ])

            for s in shots:

                writer.writerow([
                    s.id,
                    s.line,
                    s.station,
                    f"{s.x:.3f}",
                    f"{s.y:.3f}",
                    int(s.inside_boundary)
                ])

        return filename

    #################################################################

    def export(self, geometry):

        receivers = self.export_receivers(
            geometry.receivers
        )

        shots = self.export_shots(
            geometry.shots
        )

        return receivers, shots