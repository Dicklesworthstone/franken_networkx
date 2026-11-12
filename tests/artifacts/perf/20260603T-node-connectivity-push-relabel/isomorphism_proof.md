# Isomorphism Proof

## Observable Contract

The changed path is `fnx.node_connectivity(G)` for exact simple undirected graphs without self-loops or multiedges. Python prechecks are unchanged: null graph errors, both-or-neither `s`/`t`, missing-node error wording, `flow_func` delegation, self-loop delegation, and multigraph delegation still run before the Rust call.

## Value Preservation

Global node connectivity uses Esfahanian's NetworkX-compatible candidate-pair schedule:

- choose the insertion-order first minimum-degree node `v`;
- start `k` at `deg(v)`;
- check non-neighbors of `v`;
- check non-adjacent pairs among neighbors of `v`, sorted as before.

The new kernel computes `min(local_connectivity, k)` for each candidate pair. This is sufficient because the global algorithm only updates `k` when a pair value is smaller than the current `k`. External node-split arcs are capped at the current cutoff capacity; cuts smaller than `k` must cross unit internal node arcs, so the cap cannot create a false smaller value. If the sink receives `k` units, the true local connectivity is at least `k`, so returning the cutoff is equivalent for the global minimum.

## Ordering And Tie-Breaking

The candidate-pair order is unchanged. No result object contains an augmenting path, residual graph, min-cut partition, or tied predecessor choice. The public output is only an integer. Witness counters are internal and now count push-relabel edge scans and active-heap peak instead of Edmonds-Karp BFS scans and queue peak.

## Floating Point

All capacities are integer-valued `f64` values: unit internal arcs and cutoff-capacity external arcs. The returned value is clamped to the cutoff and rounded only after the flow computation. The benchmark and parity tests verify integer value equality against NetworkX. No user-visible floating-point result is produced.

## RNG

The kernel is deterministic and uses no RNG. The benchmark fixture uses `networkx.random_regular_graph(..., seed=8675309)` identically before and after.

## Golden SHA

Baseline FNX, after FNX, and NetworkX oracle all produced value `4` and digest:

`bbf21a609465999089e8d8f8c525e4235fd561c464d915517e0f6d65063ecb98`
