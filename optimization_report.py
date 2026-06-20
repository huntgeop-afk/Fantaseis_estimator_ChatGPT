from dataclasses import dataclass
from datetime import datetime


class OptimizationReport:
    """Generates a formatted engineering report from survey and optimization outputs."""

    def __init__(
        self,
        survey,
        optimization_result,
        true_fold_summary=None,
        offset_distribution=None,
        azimuth_summary=None,
        ava_summary=None,
        avaz_summary=None,
        illumination_summary=None,
    ):
        self.survey = survey
        self.optimization_result = optimization_result
        self.true_fold_summary = true_fold_summary
        self.offset_distribution = offset_distribution
        self.azimuth_summary = azimuth_summary
        self.ava_summary = ava_summary
        self.avaz_summary = avaz_summary
        self.illumination_summary = illumination_summary

    #################################################################

    def generate(self):
        lines = [
            "======================================================",
            "FantaSeis Survey Optimization Report",
            "======================================================",
            f"Generated {datetime.now()}",
            "------------------------------------------------------",
            "Survey Geometry",
            "------------------------------------------------------",
            f"Receiver Line Spacing : {self._format_value(self._survey_value('receiver_line_spacing'))}",
            f"Receiver Interval : {self._format_value(self._survey_value('receiver_interval'))}",
            f"Source Line Spacing : {self._format_value(self._survey_value('source_line_spacing'))}",
            f"Shot Interval : {self._format_value(self._survey_value('shot_interval'))}",
            f"Active Receiver Lines : {self._format_value(self._survey_value('active_receiver_lines'))}",
            f"Target Depth : {self._format_value(self._survey_value('target_depth'))}",
            f"Maximum Incidence Angle Requirement : {self._format_value(self._survey_value('maximum_incidence_angle'))}",
            "------------------------------------------------------",
            "Optimization Result",
            "------------------------------------------------------",
            f"Estimated Cost : {self._format_currency(self._result_value('estimated_cost'))}",
            f"Estimated Days : {self._format_number(self._result_value('estimated_days'))}",
            f"Minimum Fold : {self._format_number(self._result_value('minimum_fold'))}",
            f"Average Fold : {self._format_number(self._result_value('average_fold'))}",
            f"Maximum Fold : {self._format_number(self._result_value('maximum_fold'))}",
            f"Coverage : {self._format_percent(self._result_value('coverage_percent'))}",
            f"Meets Constraints : {self._result_value('meets_constraints')}",
            "------------------------------------------------------",
            "True Fold",
            "------------------------------------------------------",
            self._section_text(self.true_fold_summary),
            "------------------------------------------------------",
            "Offset Distribution",
            "------------------------------------------------------",
            self._section_text(self.offset_distribution),
            "------------------------------------------------------",
            "Azimuth Analysis",
            "------------------------------------------------------",
            self._section_text(self.azimuth_summary),
            "------------------------------------------------------",
            "AVA Analysis",
            "------------------------------------------------------",
            self._section_text(self.ava_summary),
            "------------------------------------------------------",
            "AVAz Analysis",
            "------------------------------------------------------",
            self._section_text(self.avaz_summary),
            "------------------------------------------------------",
            "Illumination",
            "------------------------------------------------------",
            self._section_text(self.illumination_summary),
            "======================================================",
            "End Report",
            "======================================================",
        ]

        return "\n".join(lines)

    #################################################################

    def _section_text(self, summary):
        if summary is None:
            return "Not Available"

        if hasattr(summary, "summary"):
            return summary.summary()

        return str(summary)

    #################################################################

    def _survey_value(self, name):
        return getattr(self.survey, name, None)

    #################################################################

    def _result_value(self, name):
        return getattr(self.optimization_result, name, None)

    #################################################################

    def _format_value(self, value):
        if value is None:
            return "Not Available"

        if isinstance(value, bool):
            return str(value)

        if isinstance(value, int):
            return str(value)

        return f"{value:.1f}"

    #################################################################

    def _format_number(self, value):
        if value is None:
            return "Not Available"

        return f"{value:.1f}"

    #################################################################

    def _format_currency(self, value):
        if value is None:
            return "Not Available"

        return f"${value:.0f}"

    #################################################################

    def _format_percent(self, value):
        if value is None:
            return "Not Available"

        return f"{value:.1f} %"
