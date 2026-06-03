# dfs_edges indexed traversal benchmark report

Bead: `br-r37-c1-04z53.37`

Date: 2026-06-03

Agent: `TealSpring`

## Profile-backed target

The current traversal residual sweep left `dfs_edges` as a measurable residual target:

- `tests/artifacts/perf/20260603T-current-residual-sweep/traversal_sweep.jsonl`
- `tests/artifacts/perf/20260603T-dfs-edges-current/profile_baseline_fnx.txt`

Fresh pass-local cProfile confirmed the native call was in the timed path:

- Baseline: `{built-in method franken_networkx._fnx.dfs_edges}` was `0.334s` cumulative over 100 calls.
- After: `{built-in method franken_networkx._fnx.dfs_edges}` was `0.099s` cumulative over 100 calls.

## Lever

Rewrite undirected Rust `Graph` `dfs_edges` to traverse by node index:

- Resolve `source` once with `get_node_index`.
- Use `nodes_ordered` for output labels and CGSE decisions.
- Use a dense `Vec<bool>` for visited state instead of string-keyed `HashSet<&str>`.
- Use `neighbors_indices` directly instead of allocating `neighbors(node)` vectors.
- Keep the stack shape and reverse-neighbor push order so observable DFS order is unchanged.

Directed `DiGraph` DFS and Python wrapper behavior were not changed.

## Baseline and after

Direct repeat-100 sample, `n=3000`, `m=4`, `graph_seed=42`:

| Metric | Baseline | After | Ratio |
| --- | ---: | ---: | ---: |
| FNX direct mean | `0.002140505210554693s` | `0.0008844071408384479s` | `2.42x faster` |
| FNX direct p50 | `0.0021003279834985733s` | `0.0008126689936034381s` | `2.58x faster` |
| Native cProfile cumulative, 100 calls | `0.334s` | `0.099s` | `3.37x faster` |

Process-level hyperfine, same benchmark command with `repeat=50`:

| Run | Mean | Stddev | Median | Ratio vs baseline |
| --- | ---: | ---: | ---: | ---: |
| Baseline | `0.5674150867333334s` | `0.02675308347206743s` | `0.5683106096s` | `1.00x` |
| After | `0.49713454514s` | `0.03093705027262086s` | `0.50342313114s` | `1.14x faster` |
| After confirm | `0.48957940547999995s` | `0.016309392476133167s` | `0.4888220246800001s` | `1.16x faster` |

## Score

Impact 3 x Confidence 4 / Effort 2 = `6.0`.

Verdict: keep. The lever exceeds the Score >= 2.0 threshold and has a confirmed hyperfine process-level win.

