import sys
from pipeline import SurveyPipeline
from qc_report import QCReport
from config import DEBUG
from business_model import BusinessModel
from optimizer import GridSearchOptimizer
from optimization_diagnostics import OptimizationDiagnostics
from design_space_analysis import DesignSpaceAnalysis


def main():

    if len(sys.argv) != 2:

        print()
        print("Usage:")
        print("python main.py <project folder>")
        return

    project_folder = sys.argv[1]
    business_model = BusinessModel(project_folder)

    pipeline = SurveyPipeline(project_folder, debug=DEBUG, business_model=business_model)

    try:
        results = pipeline.run()
    except Exception as exc:
        print("Survey execution failed.")
        print(str(exc))
        raise SystemExit(1)

    print("Generating QC Report...")
    qc_report_text = QCReport(results).generate()
    print(qc_report_text, end="")

    optimizer = GridSearchOptimizer(project_folder, business_model=business_model)
    optimizer.run()

    diagnostics = OptimizationDiagnostics(project_folder)
    diagnostics.run()

    design_space_analysis = DesignSpaceAnalysis(project_folder, business_model=business_model)
    design_space_analysis.run()

    print("Survey Completed Successfully.")


if __name__ == "__main__":
    main()