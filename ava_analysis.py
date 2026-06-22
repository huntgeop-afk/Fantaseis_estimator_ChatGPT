from dataclasses import dataclass
import math


@dataclass
class AVASummary:
    """Stores survey-wide AVA suitability metrics from populated CMP traces."""

    maximum_offset: float
    maximum_incidence_angle: float
    target_depth: float
    trace_count: int
    meets_requirement: bool

    #################################################################

    def summary(self):
        return "\n".join([
            "AVA Suitability Analysis",
            f"Target Depth : {self.target_depth:.0f} ft",
            f"Maximum Offset : {self.maximum_offset:.0f} ft",
            f"Maximum Incidence Angle : {self.maximum_incidence_angle:.1f}\N{DEGREE SIGN}",
            f"Trace Count : {self.trace_count}",
            f"Meets AVA Requirement : {self.meets_requirement}",
        ])


class AVAAnalysis:
    """Evaluates whether maximum acquired offset supports required AVA incidence angle."""

    def __init__(self, cmp_grid, target_depth, required_angle_deg):
        self.cmp_grid = cmp_grid
        self.target_depth = target_depth
        self.required_angle_deg = required_angle_deg
        self.incidence_angles = []  # Store all incidence angles for validation report

    #################################################################

    def analyze(self):
        if self.target_depth <= 0:
            raise ValueError("Target depth must be greater than zero.")

        maximum_offset = 0.0
        trace_count = 0
        self.incidence_angles = []

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                trace_count += 1
                angle = self._incidence_angle(trace.offset)
                self.incidence_angles.append(angle)

                if trace.offset > maximum_offset:
                    maximum_offset = trace.offset

        if trace_count == 0:
            maximum_incidence_angle = self._incidence_angle(0.0)
            meets_requirement = maximum_incidence_angle >= self.required_angle_deg

            return AVASummary(
                maximum_offset=0.0,
                maximum_incidence_angle=maximum_incidence_angle,
                target_depth=self.target_depth,
                trace_count=0,
                meets_requirement=meets_requirement,
            )

        maximum_incidence_angle = self._incidence_angle(maximum_offset)

        meets_requirement = maximum_incidence_angle >= self.required_angle_deg

        return AVASummary(
            maximum_offset=maximum_offset,
            maximum_incidence_angle=maximum_incidence_angle,
            target_depth=self.target_depth,
            trace_count=trace_count,
            meets_requirement=meets_requirement,
        )

    #################################################################

    def print_ava_validation(self):
        """Print AVA validation report with detailed incidence angle statistics."""
        if not self.incidence_angles:
            print("==================================================")
            print("AVA VALIDATION")
            print("==================================================")
            print("Target Depth           : 0 ft")
            print("Maximum Offset         : 0 ft")
            print("Minimum Angle          : 0.0°")
            print("Average Angle          : 0.0°")
            print("Median Angle           : 0.0°")
            print("Maximum Angle          : 0.0°")
            print("==================================================")
            return

        angles = sorted(self.incidence_angles)
        maximum_offset = max(trace.offset for bin_record in getattr(self.cmp_grid, "bins", [])
                            for trace in getattr(bin_record, "traces", []))

        minimum_angle = angles[0]
        maximum_angle = angles[-1]
        average_angle = math.fsum(angles) / len(angles)
        median_angle = self._percentile(angles, 0.50)

        p05_angle = self._percentile(angles, 0.05)
        p10_angle = self._percentile(angles, 0.10)
        p25_angle = self._percentile(angles, 0.25)
        p75_angle = self._percentile(angles, 0.75)
        p90_angle = self._percentile(angles, 0.90)
        p95_angle = self._percentile(angles, 0.95)

        angles_gt_20 = sum(1 for a in angles if a > 20.0)
        angles_gt_25 = sum(1 for a in angles if a > 25.0)
        angles_gt_30 = sum(1 for a in angles if a > 30.0)
        angles_gt_35 = sum(1 for a in angles if a > 35.0)
        angles_gt_40 = sum(1 for a in angles if a > 40.0)

        print("==================================================")
        print("AVA VALIDATION")
        print("==================================================")
        print(f"Target Depth           : {self.target_depth:.0f} ft")
        print(f"Maximum Offset         : {maximum_offset:.0f} ft")
        print()
        print(f"Minimum Angle          : {minimum_angle:.1f}°")
        print(f"Average Angle          : {average_angle:.1f}°")
        print(f"Median Angle           : {median_angle:.1f}°")
        print(f"Maximum Angle          : {maximum_angle:.1f}°")
        print()
        print(f"5 Percentile           : {p05_angle:.1f}°")
        print(f"10 Percentile          : {p10_angle:.1f}°")
        print(f"25 Percentile          : {p25_angle:.1f}°")
        print(f"75 Percentile          : {p75_angle:.1f}°")
        print(f"90 Percentile          : {p90_angle:.1f}°")
        print(f"95 Percentile          : {p95_angle:.1f}°")
        print()
        print(f"Angles >20°            : {angles_gt_20}")
        print(f"Angles >25°            : {angles_gt_25}")
        print(f"Angles >30°            : {angles_gt_30}")
        print(f"Angles >35°            : {angles_gt_35}")
        print(f"Angles >40°            : {angles_gt_40}")
        print("==================================================")

    #################################################################

    def _incidence_angle(self, offset):
        return math.degrees(
            math.atan(offset / (2.0 * self.target_depth))
        )

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
