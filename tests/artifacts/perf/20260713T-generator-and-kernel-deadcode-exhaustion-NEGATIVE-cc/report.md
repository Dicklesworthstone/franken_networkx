# Generator-core + kernel dead-code / exhaustion sweep — NEGATIVE (cc, 2026-07-13)

Negative-ledger record so peers do not re-mine these. The clean, reachable,
byte-identical, cargo-testable lever surface is comprehensively mined for the cc
lane. Every remaining candidate checked this session is done, dead, diluted,
float-risky, or floor-dominated.

## THE REACHABILITY RULE (proven 4× this session)

Before optimizing ANY `fnx_algorithms::<fn>` / `GraphGenerator::<fn>` Rust kernel,
read the actual Python wrapper `python/franken_networkx/<module>.py def <fn>`:

- If it does `_nx_*.<fn>(...)` it DELEGATES to networkx → the Rust kernel is DEAD.
- If it reimplements the algorithm in Python → the Rust kernel is DEAD.
- Grep `_fnx.<fn>(` / `_raw_<fn>(` / `_rust_<fn>(` WITH PAREN in the `.py`.
  Import-only (no paren call) or absent = DEAD, even with a registered pyo3
  `#[pyfunction]` wrapper.

A registered pyo3 wrapper does NOT prove reachability.

## VERIFIED-DEAD this session (do not optimize)

- `write_graphml_string_config_with_graph_attrs` (fnx-algorithms) — reachable only
  via `write_graphml_string_rust`, which lives only in `_fnx.pyi`; real
  `write_graphml` routes through fnx-readwrite `EdgeListEngine`. (Shipped a 1.36x
  "perf" then REVERTED.)
- `GraphGenerator::barabasi_albert_graph` / `dual_barabasi_albert_graph` /
  `extended_barabasi_albert_graph` (fnx-generators) — the Python wrappers
  reimplement BA in pure Python (`_random_generator_subset` + `add_edges_from`);
  `_rust_barabasi_albert_graph` is imported but never called.
- `random_subset_python` (fnx-generators) — called only by the three dead BA cores
  above. **Shipped a false 672x (br-r37-c1-rsubcap) then REVERTED (fe1db6e80)** —
  the O(n^2) `unique_cap` it "fixed" existed only in dead code; the live Python
  path uses the pure-Python `_random_generator_subset` (no such bug).
- `k_core` / `k_shell` / `k_crust` / `k_corona` (fnx-algorithms) — `core.py` does
  `nx_result = _nx_core.k_core(G, ...)` (delegates to nx). The `k_core_rust`
  bindings are dead.

## VERIFIED-LIVE but ALREADY-OPTIMAL (no lever)

`rich_club_coefficient` (O(V+E) integer sweep, br-r37-c1-richclub);
`voterank_directed` (integer adjacency built once); `floyd_warshall`(+pred) (int
matrix DP); `distance_measures`, `wiener_index`(+directed), `s_metric`,
`average_shortest_path_length_directed` (bit-parallel); the whole link-prediction
family (`CommonNeighborScratch`); subset-betweenness unweighted; `is_semiconnected`
/ `is_aperiodic` (condensation family, closed by attracting_components).

## FLOOR-DOMINATED / DILUTED (assessed, not worth a build)

- pyo3 `centrality_to_dict` (in/out_degree_centrality throwaway `to_owned`) — the
  PyDict build (`py_node_key` + `set_item` per node) dominates and is common to
  both arms; the String saving is a small fraction. Needs a `Python::with_gil` A/B
  harness for a marginal, below-gate win.
- `gn_graph` / `scale_free_graph` weighted samplers — genuinely O(n^2)
  (`weighted_choice_python` rebuilds an O(|weights|) cdf per call over a growing
  degree_sequence), but a Fenwick fix compares `cumsum >= sample*total` where the
  current code compares `cumsum/total < sample` — NOT bit-identical (IEEE754
  div-vs-mul rounding), and `test_gn_graph_matches_networkx` pins the exact vs-nx
  edge set. Float-risky.

## SHIPPED WINS this session (reachability-verified, still valid)

`edge_boundary` 2.19x (d730bcaff), `group_in/degree_centrality` 2.73/2.46x
(2f3543484), cut-measure family conductance 15.44x / boundary_expansion 10.16x /
volume 9.79x / mixing_expansion 9.37x (529ab0c93), `attracting_components` 1.59x
(e4e41ac75).

## NEXT PRODUCTIVE SURFACE (multi-turn, not a clean one-turn cargo-test lever)

1. Route a fully-delegated LIVE function (e.g. `k_core`, which currently == nx
   speed via delegation) to its native Rust kernel for the simple case — the
   `native_reader_collapse_guard` pattern (parse_graphml precedent). Requires
   byte-exact nx-parity verification (the reason it delegates is unconfirmed) and
   `.so`-level benching, not a cargo-test A/B.
2. `Python::with_gil` pyo3 A/B harness to make binding-layer levers measurable.
3. MultiGraph tuple/view materialization — BlackThrush's active peer lane
   (agent-mail coordination first).
