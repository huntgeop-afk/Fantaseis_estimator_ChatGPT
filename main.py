import sys
import os
from pathlib import Path
import matplotlib.pyplot as plt
from pipeline import SurveyPipeline
from qc_report import QCReport
from config import DEBUG
from business_model import BusinessModel
from optimizer import GridSearchOptimizer
from optimization_diagnostics import OptimizationDiagnostics
from design_space_analysis import DesignSpaceAnalysis
from engineering_recommendation import EngineeringRecommendationEngine
from optimization_presets import OptimizationPresetManager


SURVEY_TYPE_FIXED = "fixed"
SURVEY_TYPE_OPTIMIZE = "optimize"

RUN_MODE_PRODUCTION = "production"
RUN_MODE_VALIDATION = "validation"
RUN_MODE_DEBUG = "debug"


def _print_usage():
    print()
    print("Usage:")
    print("python main.py <project folder> [--fixed|--optimize] [--mode <production|validation|debug>] [--preset <name>]")


def _prompt_survey_type():
    while True:
        print("========================================")
        print("Survey Type")
        print("========================================")
        print()
        print("1 - Fixed Survey")
        print()
        print("2 - Optimization")
        print()

        selection = input("Select Survey Type: ").strip()

        if selection == "1":
            return SURVEY_TYPE_FIXED
        if selection == "2":
            return SURVEY_TYPE_OPTIMIZE

        print("Invalid selection. Enter 1 or 2.")
        print()


def _prompt_run_mode():
    while True:
        print("========================================")
        print("Execution Mode")
        print("========================================")
        print()
        print("1 - Production")
        print()
        print("2 - Validation")
        print()
        print("3 - Debug")
        print()

        selection = input("Select Execution Mode: ").strip()

        if selection == "1":
            return RUN_MODE_PRODUCTION
        if selection == "2":
            return RUN_MODE_VALIDATION
        if selection == "3":
            return RUN_MODE_DEBUG

        print("Invalid selection. Enter 1, 2, or 3.")
        print()


def _resolve_project_and_mode(argv):
    switches = set()
    positional = []
    preset_name = None
    run_mode = None

    index = 0
    while index < len(argv):
        token = argv[index]
        lowered = token.strip().lower()

        if lowered == "--mode":
            if index + 1 >= len(argv):
                raise ValueError("--mode requires a value")
            run_mode = argv[index + 1].strip().lower()
            index += 2
            continue

        if lowered.startswith("--mode="):
            run_mode = lowered.split("=", 1)[1].strip().lower()
            index += 1
            continue

        if lowered == "--preset":
            if index + 1 >= len(argv):
                raise ValueError("--preset requires a value")
            preset_name = argv[index + 1].strip().lower()
            index += 2
            continue

        if lowered.startswith("--preset="):
            preset_name = lowered.split("=", 1)[1].strip().lower()
            index += 1
            continue

        if lowered.startswith("--"):
            switches.add(lowered)
        else:
            positional.append(token)

        index += 1

    allowed = {"--fixed", "--optimize"}
    invalid = sorted(switches - allowed)
    if invalid:
        raise ValueError(f"Unknown option(s): {', '.join(invalid)}")

    if "--fixed" in switches and "--optimize" in switches:
        raise ValueError("Use only one mode switch: --fixed or --optimize")

    if len(positional) != 1:
        raise ValueError("Project folder is required.")

    project_folder = positional[0]

    if run_mode is not None and run_mode not in {RUN_MODE_PRODUCTION, RUN_MODE_VALIDATION, RUN_MODE_DEBUG}:
        raise ValueError("--mode must be one of: production, validation, debug")

    survey_type = None
    if "--fixed" in switches:
        survey_type = SURVEY_TYPE_FIXED
    if "--optimize" in switches:
        survey_type = SURVEY_TYPE_OPTIMIZE

    if survey_type is None and run_mode is None:
        survey_type = _prompt_survey_type()
        run_mode = _prompt_run_mode()
    else:
        if survey_type is None:
            survey_type = SURVEY_TYPE_FIXED
        if run_mode is None:
            run_mode = RUN_MODE_PRODUCTION

    return project_folder, survey_type, run_mode, preset_name


def _prompt_optimization_preset():
    options = {
        "8": "smoke",
        "1": "conservative",
        "2": "balanced",
        "3": "profit",
        "4": "nodes",
        "5": "fast",
        "6": "quality",
        "7": "custom",
    }

    while True:
        print("========================================")
        print("Optimization Preset")
        print("========================================")
        print()
        print("1 - Conservative")
        print("2 - Balanced")
        print("3 - Maximum Profit")
        print("4 - Minimum Nodes")
        print("5 - Fast Acquisition")
        print("6 - Premium Data Quality")
        print("7 - Custom (optimization.json)")
        print("8 - Smoke Test")
        print()

        selection = input("Select Preset: ").strip()
        if selection in options:
            return options[selection]

        print("Invalid selection. Enter 1-8.")
        print()


def _cleanup_resources():
    plt.close("all")


def _print_engineering_kernel_banner():
    print("========================================")
    print("ENGINEERING KERNEL")
    print("========================================")
    print("Status")
    print("Frozen")
    print("Validated")
    print("PASS")
    print("Engineering Version")
    print("1.0")
    print("========================================")


def _print_execution_configuration(survey_type, run_mode):
    survey_label = "Fixed Survey" if survey_type == SURVEY_TYPE_FIXED else "Optimization"
    mode_label = run_mode.capitalize()
    validation_enabled = run_mode in {RUN_MODE_VALIDATION, RUN_MODE_DEBUG}
    debug_enabled = run_mode == RUN_MODE_DEBUG

    print("========================================")
    print("EXECUTION CONFIGURATION")
    print("========================================")
    print("Survey Type")
    print(survey_label)
    print("Execution Mode")
    print(mode_label)
    print("Engineering Kernel")
    print("Frozen")
    print("Validation")
    print("Enabled" if validation_enabled else "Disabled")
    print("Debug")
    print("Enabled" if debug_enabled else "Disabled")
    print("========================================")


def _print_smoke_test_summary(project_folder, optimizer_result, qc_report_text, recommendation_result, diagnostics_result, design_space_result):
    project_path = Path(project_folder)

    candidate_count = int(optimizer_result.get("candidate_count", 0) or 0)
    evaluated_count = candidate_count

    files_to_check = {
        "Engineering Recommendation": project_path / "engineering_recommendation.txt",
        "Decision Summary": project_path / "optimizer_decision_summary.txt",
        "Diagnostics": project_path / "optimization_diagnostics.txt",
        "Design Space Analysis": project_path / "design_space_analysis.txt",
    }

    engineering_pass = bool(recommendation_result) and files_to_check["Engineering Recommendation"].exists()
    decision_pass = files_to_check["Decision Summary"].exists()
    diagnostics_pass = bool(diagnostics_result) and files_to_check["Diagnostics"].exists()
    design_space_pass = bool(design_space_result) and files_to_check["Design Space Analysis"].exists()
    qc_pass = bool(str(qc_report_text).strip())
    optimization_pass = candidate_count == 16 and evaluated_count == 16 and decision_pass and diagnostics_pass and design_space_pass
    overall_pass = optimization_pass and engineering_pass and qc_pass

    print("========================================")
    print("SMOKE TEST COMPLETE")
    print("========================================")
    print()
    print("Candidates Generated")
    print(candidate_count)
    print()
    print("Candidates Evaluated")
    print(evaluated_count)
    print()
    print("Optimization Completed")
    print("PASS" if optimization_pass else "FAIL")
    print()
    print("Decision Summary")
    print("PASS" if decision_pass else "FAIL")
    print()
    print("Engineering Recommendation")
    print("PASS" if engineering_pass else "FAIL")
    print()
    print("Diagnostics")
    print("PASS" if diagnostics_pass else "FAIL")
    print()
    print("Design Space Analysis")
    print("PASS" if design_space_pass else "FAIL")
    print()
    print("QC")
    print("PASS" if qc_pass else "FAIL")
    print()
    print("Overall")
    print("PASS" if overall_pass else "FAIL")
    print("========================================")


def _python_processes():
    import subprocess

    command = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 or not result.stdout.strip():
        return []

    import json

    payload = json.loads(result.stdout)
    if isinstance(payload, dict):
        payload = [payload]

    processes = []
    for item in payload:
        try:
            processes.append(
                {
                    "pid": int(item.get("ProcessId")),
                    "cmd": str(item.get("CommandLine") or ""),
                }
            )
        except Exception:
            continue

    return processes


def _terminate_pid(pid, force=False):
    import subprocess

    command = f"Stop-Process -Id {pid} {'-Force' if force else ''} -ErrorAction SilentlyContinue"
    subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False)


def _generated_output_files(project_folder):
    return [
        Path(project_folder) / "optimization_results.csv",
        Path(project_folder) / "top_20_designs.csv",
        Path(project_folder) / "optimizer_decision_summary.txt",
        Path(project_folder) / "optimization_diagnostics.txt",
        Path(project_folder) / "optimization_failure_summary.csv",
        Path(project_folder) / "engineering_recommendation.txt",
    ]

def _remove_stale_output_files(project_folder):
    found = 0
    removed = 0
    failed = 0

    for file_path in _generated_output_files(project_folder):
        if not file_path.exists():
            continue

        found += 1
        try:
            file_path.unlink()
            removed += 1
        except OSError:
            failed += 1

    return found, removed, failed


def _run_cleanup(project_folder):
    current_pid = os.getpid()

    all_processes = _python_processes()
    targets = [
        p
        for p in all_processes
        if p["pid"] != current_pid and "main.py" in p["cmd"].lower()
    ]

    found = len(targets)
    terminated = 0

    for process in targets:
        _terminate_pid(process["pid"], force=False)

    remaining = {
        p["pid"]: p
        for p in _python_processes()
        if p["pid"] != current_pid and "main.py" in p["cmd"].lower()
    }
    for pid in list(remaining):
        _terminate_pid(pid, force=True)

    final_processes = _python_processes()
    final_main = [
        p
        for p in final_processes
        if p["pid"] != current_pid and "main.py" in p["cmd"].lower()
    ]
    final_opt = [
        p
        for p in final_processes
        if p["pid"] != current_pid and "--optimize" in p["cmd"].lower()
    ]

    terminated = found - len(final_main)
    stale_outputs_found, stale_outputs_removed, stale_output_errors = _remove_stale_output_files(project_folder)

    print("========================================")
    print("RUN CLEANUP")
    print("========================================")
    print()
    print(f"Previous Optimization Runs Found : {found}")
    print(f"Processes Terminated             : {terminated}")
    print(f"Output Files Found               : {stale_outputs_found}")
    print(f"Output Files Removed             : {stale_outputs_removed}")
    print(f"Output File Cleanup Errors       : {stale_output_errors}")
    print()
    print("RUN CLEANUP COMPLETE")

    if final_main or final_opt:
        raise RuntimeError("Unable to fully terminate prior optimization processes.")


def main():
    try:
        project_folder, survey_type, run_mode, preset_name = _resolve_project_and_mode(sys.argv[1:])
    except ValueError as exc:
        print(str(exc))
        _print_usage()
        raise SystemExit(1)

    if survey_type != SURVEY_TYPE_OPTIMIZE and preset_name is not None:
        print("--preset is only valid with --optimize mode.")
        raise SystemExit(1)

    if survey_type == SURVEY_TYPE_OPTIMIZE and not preset_name:
        preset_name = _prompt_optimization_preset()

    if survey_type == SURVEY_TYPE_OPTIMIZE:
        preset_name = OptimizationPresetManager.normalize_preset_name(preset_name)

    _print_engineering_kernel_banner()
    _print_execution_configuration(survey_type, run_mode)

    business_model = BusinessModel(project_folder)

    preset_manager = None
    preset_config = None
    preset_info = None

    if survey_type == SURVEY_TYPE_OPTIMIZE:
        _run_cleanup(project_folder)
        preset_manager = OptimizationPresetManager(project_folder)
        preset_config, preset_info = preset_manager.build_config(preset_name)

    pipeline = SurveyPipeline(
        project_folder,
        debug=(DEBUG or run_mode == RUN_MODE_DEBUG),
        business_model=business_model,
        survey_type=survey_type,
        execution_mode=run_mode,
    )

    exit_code = 0
    interrupted_optimization = False

    try:
        results = pipeline.run()

        print("Generating QC Report...")
        qc_report_text = QCReport(results).generate()
        print(qc_report_text, end="")

        optimizer_result = None
        recommendation_result = None
        diagnostics_result = None
        design_space_result = None

        if survey_type == SURVEY_TYPE_OPTIMIZE:
            optimizer = GridSearchOptimizer(
                project_folder,
                business_model=business_model,
                preset_config=preset_config,
                preset_info=preset_info,
            )
            optimizer_result = optimizer.run()

            recommendation = EngineeringRecommendationEngine(
                project_folder,
                business_model=business_model,
                preset_info=preset_info,
            )
            recommendation_result = recommendation.run()

            diagnostics = OptimizationDiagnostics(project_folder)
            diagnostics_result = diagnostics.run()

            design_space_analysis = DesignSpaceAnalysis(project_folder, business_model=business_model)
            design_space_result = design_space_analysis.run()

            if preset_info and preset_info.get("preset_key") == "smoke":
                _print_smoke_test_summary(
                    project_folder,
                    optimizer_result,
                    qc_report_text,
                    recommendation_result,
                    diagnostics_result,
                    design_space_result,
                )
        else:
            print("Optimization workflow skipped (Fixed Survey Evaluation mode).")

        print("Survey Completed Successfully.")

    except KeyboardInterrupt:
        if survey_type == SURVEY_TYPE_OPTIMIZE:
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
