# edge_connectivity: value-only max-flow (skip discarded min-cut partition)

Bead: `br-r37-c1-value-only-maxflow-connectivity-rn20l`.

## Gap

After the prior integer-residual commit (`br-flowint`, 6b4c7b8f7) the Edmonds-Karp
inner loop was integer-fast and `maximum_flow_value` beat networkx, but
`edge_connectivity` was still ~2-3x slower. Cause: `global_edge_connectivity`
(and the local s-t paths) call `minimum_cut_edmonds_karp` |D| times -- which, per
call, re-materializes the string-keyed residual, rebuilds a String-keyed
`reverse_residual`, and runs a String-sorted reachability BFS to recover a min-cut
PARTITION -- yet the connectivity callers read only `cut.value` and DISCARD the
partition (and the flow dict).

## Lever (one)

Add `compute_max_flow_value`: the SAME integer augmenting search as
`compute_max_flow_residual`, returning only the flow value (which equals the
minimum s-t cut value by the max-flow/min-cut theorem) plus the witness counters
-- no string-residual round-trip, no per-edge flow list, no partition BFS. Route
the four edge_connectivity callers (local + global, undirected + directed) to it.
`maximum_flow` / `minimum_cut` are untouched (they still need the residual).

## Isomorphism / golden proof

100 random graphs (global + local s-t, directed + undirected):

    golden_fnx = c2694ffeaca8218fd6ddbf57225970a340ec831f66e79fc14de4ddf4aad3067e
    golden_nx  = c2694ffeaca8218fd6ddbf57225970a340ec831f66e79fc14de4ddf4aad3067e
    ISOMORPHISM: PASS

max_flow_value / min_cut_value unchanged vs nx. Python test (6/6):
tests/python/test_edge_connectivity_value_only_flow_parity.py.

## Benchmark (edge_connectivity, gnp p=0.04 undirected, warm min-of-4)

    n      nx        orig            br-flowint       THIS (value-only)
    150    0.0099s   0.0346s 3.29x   0.0200s 2.05x    0.0057s 0.57x FASTER
    300    0.0418s   0.1971s 4.55x   0.0989s 2.33x    0.0331s 0.79x FASTER
    500    0.1138s   0.8156s 6.72x   0.3655s 3.12x    0.1185s 1.04x parity

edge_connectivity goes from 6.7x SLOWER (original) to FASTER-or-equal to networkx
-- the gap is CLOSED. Score: ~3x over the previous commit x Confidence 1.0 (exact
golden) / Effort ~1.5 >= 2.0.

## Files
- `crates/fnx-algorithms/src/lib.rs`: `compute_max_flow_value` + 4 caller reroutes.
- `tests/python/test_edge_connectivity_value_only_flow_parity.py`.
