from plotting import Plotter
from traces import TraceDatabase
from survey import Survey
from geometry import Geometry

survey = Survey(
    width=15840,
    height=15840,

    receiver_interval=165,
    receiver_line_spacing=550,
    receiver_lines=13,

    source_interval=220,
    source_line_spacing=660
)

geometry = Geometry(survey)

rx, ry = geometry.generate_receivers()
sx, sy = geometry.generate_sources()

print()
print("===== Survey Summary =====")
print(f"Receiver nodes : {len(rx):,}")
print(f"Shot points    : {len(sx):,}")

print()
print("First 10 receiver locations")

for i in range(10):
    print(f"{i+1:2d}: ({rx[i]:7.1f}, {ry[i]:7.1f})")

print()
print("First 10 shot locations")

for i in range(10):
    print(f"{i+1:2d}: ({sx[i]:7.1f}, {sy[i]:7.1f})")
    print()
print("Building trace database...")

traces = TraceDatabase(rx, ry, sx, sy)

cmpx, cmpy, offset, azimuth = traces.build()

print("Done!")

print()
print(f"Number of traces : {len(offset):,}")

print(f"Minimum offset   : {offset.min():.1f} ft")

print(f"Maximum offset   : {offset.max():.1f} ft")

print(f"Average offset   : {offset.mean():.1f} ft")
Plotter.plot_geometry(rx, ry, sx, sy)