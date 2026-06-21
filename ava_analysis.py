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

    #################################################################

    def analyze(self):
        if self.target_depth <= 0:
            raise ValueError("Target depth must be greater than zero.")

        maximum_offset = 0.0
        trace_count = 0

        for bin_record in getattr(self.cmp_grid, "bins", []):
            for trace in getattr(bin_record, "traces", []):
                trace_count += 1

                if trace.offset > maximum_offset:
                    maximum_offset = trace.offset

        if trace_count == 0:
            maximum_incidence_angle = self._incidence_angle(0.0)
            meets_requirement = maximum_incidence_angle >= self.required_angle_deg
            self._print_validation(0.0, maximum_incidence_angle, meets_requirement)

            return AVASummary(
                maximum_offset=0.0,
                maximum_incidence_angle=maximum_incidence_angle,
                target_depth=self.target_depth,
                trace_count=0,
                meets_requirement=meets_requirement,
            )

        maximum_incidence_angle = self._incidence_angle(maximum_offset)

        meets_requirement = maximum_incidence_angle >= self.required_angle_deg
        self._print_validation(maximum_offset, maximum_incidence_angle, meets_requirement)

        return AVASummary(
            maximum_offset=maximum_offset,
            maximum_incidence_angle=maximum_incidence_angle,
            target_depth=self.target_depth,
            trace_count=trace_count,
            meets_requirement=meets_requirement,
        )

    #################################################################

    def _incidence_angle(self, offset):
        return math.degrees(
            math.atan(offset / (2.0 * self.target_depth))
        )

    #################################################################

    def _print_validation(self, maximum_offset, maximum_angle, meets_requirement):
        print("==================================================")
        print("AVA VALIDATION")
        print("==================================================")
        print(f"Target Depth          : {self.target_depth:.0f} ft")
        print(f"Maximum Offset        : {maximum_offset:.0f} ft")
        print(f"Maximum Angle         : {maximum_angle:.1f}\N{DEGREE SIGN}")
        print(f"Required Angle        : {self.required_angle_deg:.1f}\N{DEGREE SIGN}")
        print(f"Pass                  : {meets_requirement}")
