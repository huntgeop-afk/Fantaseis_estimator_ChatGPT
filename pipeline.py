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
from center_cmp_validation import CenterCMPValidation
from survey_qc import SurveyQC
from fold_audit_validation import FoldAuditValidation

from survey_optimizer import SurveyOptimizer
from optimization_report import OptimizationReport
from config import DEBUG
from business_model import BusinessModel


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
    business_model: object


class SurveyPipeline:
    """Orchestrates the end-to-end FantaSeis workflow using existing project modules."""

    def __init__(self, project_folder, debug=DEBUG, business_model=None):
        self.project_folder = Path(project_folder)
        self.show_plots = False
        self.debug = debug
        self.business_model = business_model if business_model is not None else BusinessModel(project_folder)

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
            lambda: ProductionModel(
                ProductionRates(
                    shots_per_day=self.business_model.production.shots_per_day,
                    node_deployments_per_day=self.business_model.production.node_deployments_per_day,
                    node_pickups_per_day=self.business_model.production.node_pickups_per_day,
                )
            ).estimate([], geometry),
        )

        self._log("Running Logistics Model...")
        logistics_summary = self._run_step(
            "Logistics model",
            lambda: self._run_logistics(gis, geometry, production_summary),
        )

        self._log("Running Node Rental Model...")
        node_rental_summary = self._run_step(
            "Node rental model",
            lambda: NodeRentalModel(
                NodeRentalRates(
                    daily_rental_rate=self.business_model.node_logistics.node_rental_per_node_day,
                    prep_fee_per_node=0.0,
                    download_fee_per_node=0.0,
                )
            ).estimate(
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

        print(
            self.business_model.business_model_summary(
                gis_project=gis,
                acquisition_days=production_summary.critical_path_days,
                receiver_nodes=geometry.receiver_count,
                node_rental_days=logistics_summary.expected_node_rental_days,
                internal_cost=cost_summary.total_project_cost,
            )
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

        print("==================================================")
        print("SURVEY QC")
        print("==================================================")
        qc = SurveyQC(cmp_grid, survey)

        center_cmp_validation = CenterCMPValidation(cmp_grid, gis)
        center_cmp_validation.print_center_cmp_validation()

        self._log("Computing Fold...")
        true_fold_summary = self._run_step(
            "True fold analysis",
            lambda: TrueFoldAnalysis(cmp_grid).analyze(),
        )
        print(true_fold_summary.summary())

        fold_audit = FoldAuditValidation(
            cmp_grid=cmp_grid,
            survey=survey,
            geometry=geometry,
            acquisition=acquisition,
            gis=gis,
            true_fold_summary=true_fold_summary,
        )
        fold_audit.run_all()

        self._log("Computing Offset Statistics...")
        offset_analysis = OffsetAnalysis(survey, cmp_grid=cmp_grid)
        offset_analysis.print_offset_validation()

        offset_distribution = self._run_step(
            "Offset distribution analysis",
            lambda: OffsetDistributionAnalysis(cmp_grid).analyze(),
        )

        self._log("Computing Azimuth Statistics...")
        azimuth_analysis = AzimuthAnalysis(cmp_grid, geometry)
        azimuth_summary = self._run_step(
            "Azimuth analysis",
            lambda: azimuth_analysis.analyze(),
        )
        azimuth_analysis.print_azimuth_validation()

        self._log("Computing AVA Suitability...")
        ava_analysis = AVAAnalysis(
            cmp_grid,
            survey.target_depth,
            survey.maximum_incidence_angle,
        )
        ava_summary = self._run_step(
            "AVA analysis",
            lambda: ava_analysis.analyze(),
        )
        ava_analysis.print_ava_validation()

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
            center_cmp_validation,
            qc,
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
            business_model=self.business_model,
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

    def _generate_figures(self, results_dir, gis, geometry, cmp_grid, offset_analysis, center_cmp_validation, qc):
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

        print("Saving azimuth_distribution.png")
        self._run_step(
            "azimuth_distribution",
            lambda: plotter.plot_azimuth_distribution(save_path=results_dir / "azimuth_distribution.png"),
        )

        print("Saving orientation_distribution.png")
        self._run_step(
            "orientation_distribution",
            lambda: plotter.plot_orientation_distribution(save_path=results_dir / "orientation_distribution.png"),
        )

        print("Saving center_cmp_offsets.png")
        self._run_step(
            "center_cmp_offsets",
            lambda: center_cmp_validation.plot_center_cmp_offsets(save_path=results_dir / "center_cmp_offsets.png"),
        )

        print("Saving center_cmp_orientations.png")
        self._run_step(
            "center_cmp_orientations",
            lambda: center_cmp_validation.plot_center_cmp_orientations(save_path=results_dir / "center_cmp_orientations.png"),
        )

        print("Generating Fold Map...")
        fold_map_figure = qc.generate_fold_map(save_path=results_dir / "fold_map.png")
        print("Saved fold_map.png")
        plt.close(fold_map_figure)

        print("Generating Maximum Offset Map...")
        max_offset_figure = qc.generate_max_offset_map(save_path=results_dir / "max_offset_map.png")
        print("Saved max_offset_map.png")
        plt.close(max_offset_figure)

        print("Generating Minimum Offset Map...")
        min_offset_figure = qc.generate_min_offset_map(save_path=results_dir / "min_offset_map.png")
        print("Saved min_offset_map.png")
        plt.close(min_offset_figure)

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

    def _run_logistics(self, gis, geometry, production_summary):
        inventory = EquipmentInventory(
            receiver_nodes=geometry.receiver_count,
            node_weight_kg=self.business_model.node_logistics.node_weight_lb * 0.45359237,
            empty_pallet_weight_kg=self.business_model.node_logistics.pallet_weight_lb * 0.45359237,
            maximum_payload_per_pallet_kg=self.business_model.node_logistics.maximum_payload_per_pallet_lb * 0.45359237,
        )

        shipping = self.business_model.node_shipping_options(geometry.receiver_count)
        mobilization_cost = self.business_model.mobilization_cost(gis)
        field_days = production_summary.critical_path_days
        transport_cost = (
            mobilization_cost
            + shipping["selected_shipping_cost"]
            + self.business_model.hotel_cost(field_days)
            + self.business_model.per_diem_cost(field_days)
            + self.business_model.total_equipment_cost(field_days)
            + self.business_model.total_crew_cost(field_days)
        )

        scenario = LogisticsScenario(
            name="Default",
            transport_method="Truck",
            outbound_days_min=shipping["selected_outbound_days"],
            outbound_days_most_likely=shipping["selected_outbound_days"],
            outbound_days_max=shipping["selected_outbound_days"],
            return_days_min=shipping["selected_return_days"],
            return_days_most_likely=shipping["selected_return_days"],
            return_days_max=shipping["selected_return_days"],
            transport_cost=transport_cost,
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

