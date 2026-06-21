from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from survey import Survey
from gis import GISProject
from geometry import Geometry
from acquisition import AcquisitionSimulator
from debug_geometry import GeometryDebugger

from production import ProductionModel, ProductionRates
from logistics import LogisticsModel, LogisticsScenario, EquipmentInventory
from node_rental import NodeRentalModel, NodeRentalRates
from cost_model import CostModel

from cmp_analysis import CMPAnalysis
from cmp_populator import CMPPopulator
from plotting import Plotter
from fold_heatmap import FoldHeatMap
from offset_heatmap import OffsetHeatMap
from azimuth_rose import AzimuthRose

from true_fold_analysis import TrueFoldAnalysis
from offset_analysis import OffsetAnalysis
from offset_distribution import OffsetDistributionAnalysis
from azimuth_analysis import AzimuthAnalysis
from ava_analysis import AVAAnalysis
from avaz_analysis import AVAzAnalysis
from illumination_analysis import IlluminationAnalysis

from survey_optimizer import SurveyOptimizer
from optimization_report import OptimizationReport
from config import DEBUG


@dataclass
class PipelineResults:
    survey: object
    gis: object
    geometry: object
    acquisition: object
    acquisition_events: list
    production: object
    logistics: object
    cost_model: object
    node_rental: object
    cmp_grid: object
    true_fold_summary: object
    offset_distribution: object
    azimuth_summary: object
    ava_summary: object
    avaz_summary: object
    illumination_summary: object
    optimization_result: object
    report_text: str


class SurveyPipeline:
    """Orchestrates the end-to-end FantaSeis workflow using existing project modules."""

    def __init__(self, project_folder, debug=DEBUG):
        self.project_folder = Path(project_folder)
        self.show_plots = False
        self.debug = debug

    #################################################################

    def run(self):
        print("Loading Survey...")
        survey = self._run_step(
            "Survey loading",
            lambda: Survey.load(self.project_folder),
        )

        print("Loading GIS...")
        gis = self._run_step(
            "GIS loading",
            lambda: self._load_gis(),
        )

        print("Generating Geometry...")
        geometry = self._run_step(
            "Geometry generation",
            lambda: self._generate_geometry(survey, gis),
        )

        acquisition = AcquisitionSimulator(survey, geometry)

        print("Running Analyses...")
        self._log("Generating Acquisition Schedule...")
        acquisition_events = self._run_step(
            "Acquisition scheduling",
            lambda: acquisition.generate_schedule(),
        )

        self._log("Running Production Model...")
        production_summary = self._run_step(
            "Production model",
            lambda: ProductionModel(ProductionRates()).estimate([], geometry),
        )

        self._log("Running Logistics Model...")
        logistics_summary = self._run_step(
            "Logistics model",
            lambda: self._run_logistics(geometry, production_summary),
        )

        self._log("Running Node Rental Model...")
        node_rental_summary = self._run_step(
            "Node rental model",
            lambda: NodeRentalModel(NodeRentalRates()).estimate(
                geometry.receiver_count,
                logistics_summary.expected_node_rental_days,
            ),
        )

        self._log("Running Cost Model...")
        cost_summary = self._run_step(
            "Cost model",
            lambda: CostModel().estimate(
                geometry,
                production_summary,
                logistics_summary,
                node_rental_summary,
            ),
        )

        self._log("Generating CMP Grid...")
        cmp_grid = self._run_step(
            "CMP grid generation",
            lambda: CMPAnalysis(survey, geometry).generate(),
        )

        self._log("Populating CMP Grid...")
        cmp_grid = self._run_step(
            "CMP population",
            lambda: CMPPopulator(cmp_grid, geometry, acquisition).populate(),
        )

        self._log("Computing Fold...")
        true_fold_summary = self._run_step(
            "True fold analysis",
            lambda: TrueFoldAnalysis(cmp_grid).analyze(),
        )
        print(true_fold_summary.summary())

        self._log("Computing Offset Statistics...")
        offset_distribution = self._run_step(
            "Offset distribution analysis",
            lambda: OffsetDistributionAnalysis(cmp_grid).analyze(),
        )

        self._log("Computing Azimuth Statistics...")
        azimuth_summary = self._run_step(
            "Azimuth analysis",
            lambda: AzimuthAnalysis(cmp_grid).analyze(),
        )

        self._log("Computing AVA Suitability...")
        ava_summary = self._run_step(
            "AVA analysis",
            lambda: AVAAnalysis(
                cmp_grid,
                survey.target_depth,
                survey.maximum_incidence_angle,
            ).analyze(),
        )

        self._log("Computing AVAz Suitability...")
        avaz_summary = self._run_step(
            "AVAz analysis",
            lambda: AVAzAnalysis(cmp_grid).analyze(),
        )

        self._log("Computing Illumination...")
        illumination_summary = self._run_step(
            "Illumination analysis",
            lambda: IlluminationAnalysis(cmp_grid).analyze(),
        )

        self._log("Evaluating Current Design...")
        optimization_result = self._run_step(
            "Current design evaluation",
            lambda: self._evaluate_current_design(
                survey,
                geometry,
                production_summary,
                cost_summary,
                true_fold_summary,
                illumination_summary,
            ),
        )

        report_text = self._run_step(
            "Report generation",
            lambda: OptimizationReport(
                survey,
                optimization_result,
                true_fold_summary=true_fold_summary,
                offset_distribution=offset_distribution,
                azimuth_summary=azimuth_summary,
                ava_summary=ava_summary,
                avaz_summary=avaz_summary,
                illumination_summary=illumination_summary,
            ).generate(),
        )

        results_dir = self._results_directory()

        print("Generating Figures...")
        offset_analysis = OffsetAnalysis(survey, cmp_grid=cmp_grid)
        self._generate_figures(
            results_dir,
            gis,
            geometry,
            cmp_grid,
            offset_analysis,
        )

        self._log("Saving optimization_report.txt")
        self._run_step(
            "Optimization report write",
            lambda: self._write_text_file(results_dir / "optimization_report.txt", report_text),
        )

        return PipelineResults(
            survey=survey,
            gis=gis,
            geometry=geometry,
            acquisition=acquisition,
            acquisition_events=acquisition_events,
            production=production_summary,
            logistics=logistics_summary,
            cost_model=cost_summary,
            node_rental=node_rental_summary,
            cmp_grid=cmp_grid,
            true_fold_summary=true_fold_summary,
            offset_distribution=offset_distribution,
            azimuth_summary=azimuth_summary,
            ava_summary=ava_summary,
            avaz_summary=avaz_summary,
            illumination_summary=illumination_summary,
            optimization_result=optimization_result,
            report_text=report_text,
        )

    #################################################################

    def _run_step(self, module_name, step):
        try:
            return step()
        except Exception as exc:
            raise RuntimeError(f"{module_name} failed: {exc}") from exc

    #################################################################

    def _log(self, message):
        if self.debug:
            print(message)

    #################################################################

    def _results_directory(self):
        results_dir = self.project_folder / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        return results_dir

    #################################################################

    def _load_gis(self):
        gis = GISProject(self.project_folder)
        gis.load_boundary()
        return gis

    #################################################################

    def _generate_geometry(self, survey, gis):
        geometry = Geometry(survey, gis)
        geometry.generate()

        if self.debug:
            debugger = GeometryDebugger(geometry)
            debugger.run()

        return geometry

    #################################################################

    def _generate_figures(self, results_dir, gis, geometry, cmp_grid, offset_analysis):
        plotter = Plotter(gis, geometry, cmp_grid)

        self._run_step(
            "Geometry figure generation",
            lambda: plotter.plot_geometry(save_path=results_dir / "geometry.png"),
        )

        self._save_figure(
            "fold_heatmap",
            results_dir / "fold_heatmap.png",
            lambda: FoldHeatMap(cmp_grid, gis).plot(),
        )

        self._save_figure(
            "offset_heatmap",
            results_dir / "offset_heatmap.png",
            lambda: OffsetHeatMap(cmp_grid, gis).plot(),
        )

        print("Saving offset_distribution.png")
        self._save_figure(
            "offset_distribution",
            results_dir / "offset_distribution.png",
            offset_analysis.plot_offset_distribution,
        )

        self._save_figure(
            "azimuth_rose",
            results_dir / "azimuth_rose.png",
            lambda: AzimuthRose(cmp_grid).plot(),
        )

    #################################################################

    def _save_figure(self, figure_name, output_path, plot_callable):
        self._log(f"Saving {output_path.name}")

        original_show = plt.show
        figure = None

        try:
            if not self.show_plots:
                plt.show = lambda *args, **kwargs: None

            plot_callable()
            figure = plt.gcf()
            figure.savefig(output_path, dpi=300, bbox_inches="tight")
        except Exception as exc:
            raise RuntimeError(f"Failed generating {figure_name} figure: {exc}") from exc
        finally:
            plt.show = original_show
            if figure is not None:
                plt.close(figure)
            else:
                plt.close("all")

    #################################################################

    def _write_text_file(self, file_path, text):
        file_path.write_text(text, encoding="utf-8")

    #################################################################

    def _run_logistics(self, geometry, production_summary):
        inventory = EquipmentInventory(receiver_nodes=geometry.receiver_count)

        scenario = LogisticsScenario(
            name="Default",
            transport_method="Truck",
            outbound_days_min=1.0,
            outbound_days_most_likely=2.0,
            outbound_days_max=3.0,
            return_days_min=1.0,
            return_days_most_likely=2.0,
            return_days_max=3.0,
            transport_cost=0.0,
            crew_members=0,
            crew_daily_cost=0.0,
            vehicle_cost_per_mile=0.0,
            round_trip_miles=0.0,
        )

        return LogisticsModel(inventory, scenario).estimate(
            production_summary.critical_path_days
        )

    #################################################################

    def _evaluate_current_design(
        self,
        survey,
        geometry,
        production_summary,
        cost_summary,
        true_fold_summary,
        illumination_summary,
    ):
        optimizer = SurveyOptimizer(
            survey,
            geometry,
            production_summary,
            cost_summary,
        )

        result = optimizer.evaluate_current_design()

        result.minimum_fold = true_fold_summary.minimum_fold
        result.average_fold = true_fold_summary.average_fold
        result.maximum_fold = true_fold_summary.maximum_fold
        result.coverage_percent = illumination_summary.coverage_percent

        return result
