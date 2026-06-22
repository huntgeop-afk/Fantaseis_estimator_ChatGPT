import sys
import matplotlib.pyplot as plt
from pipeline import SurveyPipeline
from qc_report import QCReport
from config import DEBUG
from business_model import BusinessModel
from optimizer import GridSearchOptimizer
from optimization_diagnostics import OptimizationDiagnostics
from design_space_analysis import DesignSpaceAnalysis


EXECUTION_MODE_FIXED = "fixed"
EXECUTION_MODE_OPTIMIZE = "optimize"


def _print_usage():
    print()
    print("Usage:")
    print("python main.py <project folder> [--fixed|--optimize]")


def _prompt_execution_mode():
    while True:
        print("========================================")
        print("FantaSeis Execution Mode")
        print("========================================")
        print()
        print("1 - Fixed Survey Evaluation")
        print()
        print("2 - Optimization")
        print()

        selection = input("Select Mode: ").strip()

        if selection == "1":
            return EXECUTION_MODE_FIXED
        if selection == "2":
            return EXECUTION_MODE_OPTIMIZE

        print("Invalid selection. Enter 1 or 2.")
        print()


def _resolve_project_and_mode(argv):
    switches = {arg.strip().lower() for arg in argv if arg.startswith("--")}
    positional = [arg for arg in argv if not arg.startswith("--")]

    allowed = {"--fixed", "--optimize"}
    invalid = sorted(switches - allowed)
    if invalid:
        raise ValueError(f"Unknown option(s): {', '.join(invalid)}")

    if "--fixed" in switches and "--optimize" in switches:
        raise ValueError("Use only one mode switch: --fixed or --optimize")

    if len(positional) != 1:
        raise ValueError("Project folder is required.")

    project_folder = positional[0]

    if "--fixed" in switches:
        return project_folder, EXECUTION_MODE_FIXED

    if "--optimize" in switches:
        return project_folder, EXECUTION_MODE_OPTIMIZE

    return project_folder, _prompt_execution_mode()


def _cleanup_resources():
    plt.close("all")


def main():
    try:
        project_folder, execution_mode = _resolve_project_and_mode(sys.argv[1:])
    except ValueError as exc:
        print(str(exc))
        _print_usage()
        raise SystemExit(1)

    business_model = BusinessModel(project_folder)

    pipeline = SurveyPipeline(
        project_folder,
        debug=DEBUG,
        business_model=business_model,
        execution_mode=execution_mode,
    )

    exit_code = 0
    interrupted_optimization = False

    try:
        results = pipeline.run()

        print("Generating QC Report...")
        qc_report_text = QCReport(results).generate()
        print(qc_report_text, end="")

        if execution_mode == EXECUTION_MODE_OPTIMIZE:
            optimizer = GridSearchOptimizer(project_folder, business_model=business_model)
            optimizer.run()

            diagnostics = OptimizationDiagnostics(project_folder)
            diagnostics.run()

            design_space_analysis = DesignSpaceAnalysis(project_folder, business_model=business_model)
            design_space_analysis.run()
        else:
            print("Optimization workflow skipped (Fixed Survey Evaluation mode).")

        print("Survey Completed Successfully.")

    except KeyboardInterrupt:
        if execution_mode == EXECUTION_MODE_OPTIMIZE:
            print("Optimization interrupted by user.")
            print("Cleaning up...")
            interrupted_optimization = True
        exit_code = 130
    except Exception as exc:
        print("Survey execution failed.")
        print(str(exc))
        exit_code = 1
    finally:
        _cleanup_resources()
        if interrupted_optimization:
            print("Cleanup complete.")

    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()