import sys
from pipeline import SurveyPipeline
from qc_report import QCReport
from config import DEBUG
from optimizer import GridSearchOptimizer
from optimization_diagnostics import OptimizationDiagnostics


def main():

    if len(sys.argv) != 2:

        print()
        print("Usage:")
        print("python main.py <project folder>")
        return

    project_folder = sys.argv[1]

    pipeline = SurveyPipeline(project_folder, debug=DEBUG)

    try:
        results = pipeline.run()
    except Exception as exc:
        print("Survey execution failed.")
        print(str(exc))
        raise SystemExit(1)

    print("Generating QC Report...")
    qc_report_text = QCReport(results).generate()
    print(qc_report_text, end="")

    optimizer = GridSearchOptimizer(project_folder)
    optimizer.run()

    diagnostics = OptimizationDiagnostics(project_folder)
    diagnostics.run()

    print("Survey Completed Successfully.")


if __name__ == "__main__":
    main()