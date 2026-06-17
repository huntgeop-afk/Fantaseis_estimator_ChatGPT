from survey import Survey
from geometry import Geometry

survey = Survey(

    width=15840,
    height=15840,

    receiver_interval=165,
    receiver_line_spacing=550,
    receiver_lines_active=12,
    receiver_lines_spare=1,

    source_interval=220,
    source_line_spacing=660,

    target_depth=5500
)

geometry = Geometry(survey)

rx, ry = geometry.build_receivers()

sx, sy = geometry.build_sources()

print()

print("Receiver nodes:", len(rx))

print("Shot points:", len(sx))

print()

print("First five receivers")

for i in range(5):
    print(rx[i], ry[i])

print()

print("First five shots")

for i in range(5):
    print(sx[i], sy[i])
