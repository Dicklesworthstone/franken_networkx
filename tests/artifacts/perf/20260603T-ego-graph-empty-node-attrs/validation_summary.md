# ego_graph empty node attrs validation summary

Validation commands:
- `rch exec -- python3 -m py_compile python/franken_networkx/__init__.py`
- `rch exec -- python3 tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py sample --impl fnx --op ego_graph_r2 --repeat 30 --n 3000 --m 4`
- `rch exec -- hyperfine --warmup 3 --runs 15 ...`

Outcome:
- Syntax validation passed for candidate and restored source.
- Golden SHA matched FNX before, FNX after, and NetworkX.
- Candidate rejected because the direct sample regressed and the measured win did not meet Score >= 2.0.
- No source change kept.
