from survey import Survey
from acquisition_simulator import AcquisitionSimulator


def main():

    survey = Survey(

        survey_width=15840,
        survey_height=15840,

        receiver_line_spacing=550,
        receiver_interval=165,

        source_line_spacing=660,
        shot_interval=220,

        active_receiver_lines=12
    )

    sim = AcquisitionSimulator(survey)

    while sim.state.current_shot_row <= survey.shot_rows:

        sim.complete_shot_row()

    print()
    print("------------------------------------")
    print("Simulation Complete")
    print("------------------------------------")

    print(f"Receiver Lines : {survey.receiver_lines}")
    print(f"Source Lines   : {survey.source_lines}")
    print(f"Shot Rows      : {survey.shot_rows}")
    print(f"Receiver Rolls : {sim.state.receiver_rolls}")


if __name__ == "__main__":

    main()