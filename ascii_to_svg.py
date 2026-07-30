from html import escape
from pathlib import Path

INPUT = "portrait.txt"
OUTPUT = "portrait_tspan.txt"

START_X = -10
START_Y = -30
LINE_HEIGHT = 9

TRIM_LEFT = 0
TRIM_RIGHT = 0

REMOVE_EMPTY = False

lines = Path(INPUT).read_text(encoding="utf-8", errors="ignore").splitlines()

lines = [l.rstrip() for l in lines]

if REMOVE_EMPTY:
    lines = [l for l in lines if l.strip()]

processed = []
for line in lines:
    if TRIM_RIGHT > 0:
        line = line[:-TRIM_RIGHT]
    if TRIM_LEFT > 0:
        line = line[TRIM_LEFT:]
    processed.append(line)

y = START_Y
svg = []
for line in processed:
    svg.append(f'<tspan x="{START_X}" y="{y}">{escape(line)}</tspan>')
    y += LINE_HEIGHT

Path(OUTPUT).write_text("\n".join(svg), encoding="utf-8")
print(f"Generated {len(svg)} tspans -> {OUTPUT}")

