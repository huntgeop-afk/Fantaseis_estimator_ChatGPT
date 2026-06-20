import sys
from pipeline import SurveyPipeline


def main():

    if len(sys.argv) != 2:

        print()
        print("Usage:")
        print("python main.py <project folder>")
        return

    project_folder = sys.argv[1]

    pipeline = SurveyPipeline(project_folder)

    try:
        results = pipeline.run()
    except Exception as exc:
        print("Survey execution failed.")
        print(str(exc))
        raise SystemExit(1)

    print()
    print("======================================================")
    print("Survey Completed Successfully")
    print("======================================================")
    print()
    print(results.report_text)


if __name__ == "__main__":
    main()