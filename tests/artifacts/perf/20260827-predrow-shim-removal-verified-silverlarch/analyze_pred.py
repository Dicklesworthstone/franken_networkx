"""Slope + ratio table for the predrow matrix, with a contamination check."""

import re
import subprocess
import sys

BASE = "/data/tmp/claude-1000/-data-projects-franken-networkx/679e0829-b03a-4abc-9192-59f40eb5b65e/scratchpad"


def parse(path):
    out = subprocess.run(
        ["callgrind_annotate", "--auto=no", "--threshold=99.9", path],
        capture_output=True, text=True,
    ).stdout
    d = {}
    for line in out.splitlines():
        m = re.match(r"\s*([\d,]+) \([ \d.]+%\)\s+(.*)", line)
        if not m:
            continue
        fn = m.group(2).strip()
        if fn.startswith("PROGRAM TOTALS"):
            continue
        d[fn] = d.get(fn, 0) + int(m.group(1).replace(",", ""))
    return d


def percall(mod, cls, op):
    lo = parse(f"{BASE}/cg/pr_{mod}_{cls}_{op}_2000.out")
    hi = parse(f"{BASE}/cg/pr_{mod}_{cls}_{op}_4000.out")
    per = {k: (hi.get(k, 0) - lo.get(k, 0)) / 2000 for k in set(lo) | set(hi)}
    # A spin thread's Ir tracks wall time, not the loop; a negative per-call delta
    # is proof the symbol is not driven by the loop and the row is contaminated.
    bad = [(k, v) for k, v in per.items() if v < -20]
    return sum(per.values()), bad


print(f"{'class':<14} {'op':<13} {'fnx Ir/call':>12} {'nx Ir/call':>12} {'ratio nx/fnx':>13}  contam")
rows = []
for cls in ("DiGraph", "MultiDiGraph"):
    for op in ("predecessors", "successors"):
        try:
            f, fbad = percall("fnx", cls, op)
            n, nbad = percall("nx", cls, op)
        except FileNotFoundError as e:
            print(f"{cls:<14} {op:<13}  MISSING: {e.filename}")
            continue
        ratio = n / f if f else float("nan")
        flag = f"{len(fbad)+len(nbad)} neg" if (fbad or nbad) else "clean"
        print(f"{cls:<14} {op:<13} {f:12.0f} {n:12.0f} {ratio:12.4f}x  {flag}")
        rows.append((cls, op, f, n, ratio))

if rows:
    print()
    d = {(c, o): r for c, o, _f, _n, r in rows}
    if ("DiGraph", "predecessors") in d and ("DiGraph", "successors") in d:
        print(f"same-class control  DiGraph successors / predecessors ratio-of-ratios: "
              f"{d[('DiGraph','successors')] / d[('DiGraph','predecessors')]:.3f}")
    if ("MultiDiGraph", "predecessors") in d and ("DiGraph", "predecessors") in d:
        print(f"other-class control MultiDiGraph / DiGraph predecessors ratio-of-ratios: "
              f"{d[('MultiDiGraph','predecessors')] / d[('DiGraph','predecessors')]:.3f}")
    print("\n(bead recorded: DiGraph pred 0.383x, DiGraph succ 0.819x, "
          "MultiDiGraph pred 0.775x, MultiDiGraph succ 0.748x - in NANOSECONDS)")
