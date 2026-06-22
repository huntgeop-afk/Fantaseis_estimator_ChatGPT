from dataclasses import dataclass
import math


@dataclass
class AzimuthSummary:
    """Stores survey-wide azimuth statistics computed from populated CMP traces."""

    minimum_azimuth: float
    maximum_azimuth: float
    average_azimuth: float
    trace_count: int

    #################################################################

    def summary(self):
        return "\n".join([
            "Azimuth Analysis",
            f"Minimum Azimuth : {self.minimum_azimuth:.1f}\N{DEGREE SIGN}",
            f"Average Azimuth : {self.average_azimuth:.1f}\N{DEGREE SIGN}",
            f"Maximum Azimuth : {self.maximum_azimuth:.1f}\N{DEGREE SIGN}",
            f"Trace Count : {self.trace_count}",
        ])


class AzimuthAnalysis:
    """Analyzes azimuth distribution from accepted CMP traces using engineering convention."""

    def __init__(self, cmp_grid, geometry):
        self.cmp_grid = cmp_grid
        self.geometry = geometry
        self.azimuth_values = []

    #################################################################

    def analyze(self):
        self.azimuth_values = []

        shot_lookup = {shot.id: shot for shot in self.geometry.shots}
        receiver_lookup = {receiver.id: receiver for receiver in self.geometry.receivers}

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                shot = shot_lookup.get(trace.shot_id)
                receiver = receiver_lookup.get(trace.receiver_id)

                if shot is None or receiver is None:
                    continue

                dx = receiver.x - shot.x
                dy = receiver.y - shot.y

                # Engineering convention: 0=N, 90=E, 180=S, 270=W
                azimuth_deg = math.degrees(math.atan2(dx, dy))
                azimuth_deg = azimuth_deg % 360.0

                self.azimuth_values.append(azimuth_deg)

        if not self.azimuth_values:
            return AzimuthSummary(
                minimum_azimuth=0.0,
                maximum_azimuth=0.0,
                average_azimuth=0.0,
                trace_count=0,
            )

        minimum_azimuth = min(self.azimuth_values)
        maximum_azimuth = self._display_azimuth(max(self.azimuth_values))
        average_azimuth = math.fsum(self.azimuth_values) / len(self.azimuth_values)

        return AzimuthSummary(
            minimum_azimuth=minimum_azimuth,
            maximum_azimuth=maximum_azimuth,
            average_azimuth=average_azimuth,
            trace_count=len(self.azimuth_values),
        )

    #################################################################

    def print_azimuth_validation(self):
        if not self.azimuth_values:
            print("==================================================")
            print("AZIMUTH VALIDATION")
            print("==================================================")
            print("Accepted Traces        : 0")
            print("==================================================")
            return

        azimuths = sorted(self.azimuth_values)

        minimum_azimuth = azimuths[0]
        maximum_azimuth = azimuths[-1]
        average_azimuth = math.fsum(azimuths) / len(azimuths)
        median_azimuth = self._percentile(azimuths, 0.50)

        p05_azimuth = self._percentile(azimuths, 0.05)
        p10_azimuth = self._percentile(azimuths, 0.10)
        p25_azimuth = self._percentile(azimuths, 0.25)
        p75_azimuth = self._percentile(azimuths, 0.75)
        p90_azimuth = self._percentile(azimuths, 0.90)
        p95_azimuth = self._percentile(azimuths, 0.95)

        count_0_45 = sum(1 for a in azimuths if 0.0 <= a < 45.0)
        count_45_90 = sum(1 for a in azimuths if 45.0 <= a < 90.0)
        count_90_135 = sum(1 for a in azimuths if 90.0 <= a < 135.0)
        count_135_180 = sum(1 for a in azimuths if 135.0 <= a < 180.0)
        count_180_225 = sum(1 for a in azimuths if 180.0 <= a < 225.0)
        count_225_270 = sum(1 for a in azimuths if 225.0 <= a < 270.0)
        count_270_315 = sum(1 for a in azimuths if 270.0 <= a < 315.0)
        count_315_360 = sum(1 for a in azimuths if 315.0 <= a < 360.0)

        print("==================================================")
        print("AZIMUTH VALIDATION")
        print("==================================================")
        print()
        print(f"Accepted Traces        : {len(azimuths)}")
        print()
        print(f"Minimum Azimuth        : {minimum_azimuth:.1f}°")
        print(f"Maximum Azimuth        : {self._display_azimuth(maximum_azimuth):.1f}°")
        print(f"Average Azimuth        : {average_azimuth:.1f}°")
        print(f"Median Azimuth         : {median_azimuth:.1f}°")
        print()
        print(f"5 Percentile           : {p05_azimuth:.1f}°")
        print(f"10 Percentile          : {p10_azimuth:.1f}°")
        print(f"25 Percentile          : {p25_azimuth:.1f}°")
        print(f"75 Percentile          : {p75_azimuth:.1f}°")
        print(f"90 Percentile          : {p90_azimuth:.1f}°")
        print(f"95 Percentile          : {p95_azimuth:.1f}°")
        print()
        print(f"0-45°                  : {count_0_45}")
        print(f"45-90°                 : {count_45_90}")
        print(f"90-135°                : {count_90_135}")
        print(f"135-180°               : {count_135_180}")
        print(f"180-225°               : {count_180_225}")
        print(f"225-270°               : {count_225_270}")
        print(f"270-315°               : {count_270_315}")
        print(f"315-360°               : {count_315_360}")
        print("==================================================")

    #################################################################

    def _display_azimuth(self, value):
        # Keep printed azimuths strictly within 0 <= azimuth < 360 at 0.1-degree display precision.
        if value >= 359.95:
            return 359.9
        return value

    #################################################################

    def _percentile(self, sorted_values, fraction):
        if not sorted_values:
            return 0.0

        if fraction <= 0.0:
            return sorted_values[0]

        if fraction >= 1.0:
            return sorted_values[-1]

        position = (len(sorted_values) - 1) * fraction
        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        if lower_index == upper_index:
            return sorted_values[lower_index]

        weight = position - lower_index
        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]

        return lower_value + (upper_value - lower_value) * weight



