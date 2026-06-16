# Graph.neighbors all-row baseline

Bead: `br-r37-c1-04z53.9124`

Target: `[list(G.neighbors(n)) for n in G.nodes()]` on
`Graph(gnp_random_graph(n=2400, p=0.0045, seed=23))`.

This bundle is before-source-edit evidence only. No source files were edited and
the existing installed release-perf extension was used from
`python/franken_networkx/_fnx.abi3.so`.

## Commands

```bash
mkdir -p tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff
```

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python python3 tests/artifacts/perf/20260616T-graph-neighbor-rowcache-coppercliff/graph_neighbor_rowcache_harness.py golden --output tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff/baseline_golden.json
```

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python python3 tests/artifacts/perf/20260616T-graph-neighbor-rowcache-coppercliff/graph_neighbor_rowcache_harness.py bench-fnx --loops 200 --output tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff/baseline_direct_fnx_loop200.json
```

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python python3 tests/artifacts/perf/20260616T-graph-neighbor-rowcache-coppercliff/graph_neighbor_rowcache_harness.py bench-nx --loops 200 --output tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff/baseline_direct_nx_loop200.json
```

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python python3 tests/artifacts/perf/20260616T-graph-neighbor-rowcache-coppercliff/graph_neighbor_rowcache_harness.py profile-fnx --loops 100 --output tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff/baseline_profile.txt --json-output tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff/baseline_profile.json
```

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python rch exec -- hyperfine --warmup 3 --runs 10 --export-json tests/artifacts/perf/20260616T-graph-neighbor-allrow-coppercliff/baseline_hyperfine_loop300.json 'VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python python3 tests/artifacts/perf/20260616T-graph-neighbor-rowcache-coppercliff/graph_neighbor_rowcache_harness.py bench-fnx --loops 300' 'VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=python python3 tests/artifacts/perf/20260616T-graph-neighbor-rowcache-coppercliff/graph_neighbor_rowcache_harness.py bench-nx --loops 300'
```

## Golden

- Repo HEAD: `4f4367494eb73c30d07333b3fb3da35b8a04089f`
  (`4f4367494 perf(digraph): reject indexed edge-data snapshot`)
- Golden SHA: `6004b33f72639b9ce889bac0ec221ab5628660b82e389843b43fc9d81c4b42bd`
- Neighbor rows: `2400`
- FNX/NX neighbor-row SHA: `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4`
- FNX/NX neighbor-row match: `true`
- Missing node parity: `NetworkXError("The node missing is not in the graph.")`
- Unhashable node parity: `TypeError("unhashable type: 'list'")`
- Active row iterator mutation parity:
  `RuntimeError("dictionary changed size during iteration")`
- Private `_adj` override fallback parity: `[2, 1]`

## Direct Timing

Loop count: `200`

| implementation | elapsed_s | seconds_per_loop | output_sha256 |
| --- | ---: | ---: | --- |
| FNX | `0.3290916060213931` | `0.0016454580301069653` | `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4` |
| NetworkX | `0.17101473599905148` | `0.0008550736799952574` | `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4` |

Direct FNX/NX ratio: `1.924346x`.

## Hyperfine

Loop count per command: `300`; warmup `3`; runs `10`.

| implementation | mean_s | stddev_s | median_s | min_s | max_s |
| --- | ---: | ---: | ---: | ---: | ---: |
| FNX | `0.9526121311200001` | `0.020772768082256563` | `0.95047962922` | `0.9238784332200001` | `0.98217252822` |
| NetworkX | `0.7379475506200001` | `0.015849134456884285` | `0.73432737922` | `0.71375430322` | `0.76293598622` |

Hyperfine FNX/NX ratio: `1.290894x`.

## cProfile

Loop count: `100`

Top cumulative frames from `baseline_profile.txt`:

| ncalls | tottime_s | cumtime_s | frame |
| ---: | ---: | ---: | --- |
| `100` | `0.115` | `0.358` | `graph_neighbor_rowcache_harness.py:77(neighbors_all)` |
| `240000` | `0.158` | `0.243` | `__init__.py:37508(neighbors)` |
| `480200` | `0.044` | `0.044` | `{method 'get' of 'dict' objects}` |
| `240200` | `0.022` | `0.022` | `{built-in method builtins.vars}` |
| `240000` | `0.018` | `0.018` | `{built-in method builtins.iter}` |

Total cProfile time: `0.358s`.

## Blockers

No blocker. `rch exec` warned that `hyperfine` is a non-compilation command, then
ran successfully and exported `baseline_hyperfine_loop300.json`.

## Candidate Pass 1 - Rejected

Lever tried and reverted: bundle `nodes_seq`, `edges_seq`, and the warm
`Graph.neighbors()` row-keydict cache into one graph-dict object. The goal was
to reduce warm all-row scans by removing one tuple allocation and one graph-dict
lookup per node.

Behavior proof while installed:

- Neighbor-row SHA stayed
  `b99171852c6eeb1d713fec332be3c5adae9270e08127abedd6b2ac02014954f4`.
- Missing-node, unhashable-node, active row iterator mutation, and private
  `_adj` override parity stayed matched in `after_golden.json`.

Performance:

| measurement | baseline | candidate |
| --- | ---: | ---: |
| direct FNX loop200 | `0.3290916060213931s` | `0.3228608659701422s` |
| rch hyperfine FNX loop300 mean | `0.9526121311200001s` | `0.9484075833400001s` |
| cProfile `Graph.neighbors` cumulative | `0.243s` | `0.253s` |

Verdict: rejected. The source hunk was reverted because the hyperfine movement
was noise-level and the focused profile regressed. Next route should stop
trimming this warm wrapper and either add a true bulk all-neighbor consumer or
move to another profile-backed residual.
