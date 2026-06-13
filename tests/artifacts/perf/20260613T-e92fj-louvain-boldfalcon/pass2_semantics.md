# br-r37-c1-e92fj Pass 2: Louvain Semantic Map

Date: 2026-06-12
Agent: BoldFalcon
Target: raw Rust Louvain parity before routing

## Source Comparison

NetworkX 3.6.1 reference:

- `louvain_partitions` starts with `partition = [{u} for u in G.nodes()]`.
- It converts the graph with `graph.add_nodes_from(G)` and `graph.add_weighted_edges_from(G.edges(data=weight, default=1))`.
- `_one_level` builds `node2com = {u: i for i, u in enumerate(G.nodes())}`.
- `_one_level` shuffles `rand_nodes = list(G.nodes)` with the same `seed` object at every level.
- `_one_level` mutates `partition` and `inner_partition` in place, then returns `list(filter(len, ...))` in surviving slot order.
- `_gen_graph` assigns coarsened community ids by enumerating `inner_partition` in that filtered order.

Rust raw kernel:

- Builds an index graph from `graph.nodes_ordered()` and `graph.edges_ordered_borrowed()`.
- Uses `louvain_seed_rng(seed)` plus `louvain_randbelow` and `louvain_shuffle`.
- `louvain_randbelow` computes the bit count from `upper_bound - 1`.
- Existing `ApproxRandom` in the same module already documents and implements CPython-compatible `_randbelow_with_getrandbits` with bit count from `upper`.
- Rebuilds non-empty partitions from grouped community ids and sorts final communities by smallest node name.

## Probe Results

From `baseline_golden.json`, comparing normalized members:

| Case | Ordered raw equals public | Unordered raw equals public | Interpretation |
| --- | --- | --- | --- |
| `karate` | false | true | Output order mismatch only |
| `ws150` | false | false | Membership mismatch |
| `ws300` | false | false | Membership mismatch |
| `ba300` | false | false | Membership mismatch |
| `ws150_weighted` | false | true | Output order mismatch only |
| `ws150_resolution` | false | false | Membership mismatch |

## First Lever

Replace the Louvain-specific RNG/shuffle with the existing CPython-compatible `ApproxRandom` path.

Rationale:

- NetworkX uses `random.Random(seed).shuffle`, which consumes `_randbelow(n)` draws with `n.bit_length()`.
- The current Louvain path consumes fewer bits whenever the shuffle upper bound is a power of two because it uses `(upper_bound - 1).bit_length()`.
- Different shuffle order changes the local-gain move sequence and explains membership divergence on the larger benchmark cases.

Expected outcome:

- Large-case memberships should move toward the NetworkX oracle.
- Remaining failures, if any, should isolate partition survival order, coarsened graph insertion order, or floating-point/tie semantics.

Score for this lever:

| Impact | Confidence | Effort | Score |
| ---: | ---: | ---: | ---: |
| 4 | 4 | 2 | 8.0 |

Proof plan:

- Run `cargo test -p fnx-algorithms louvain --lib` via `rch`.
- Rebuild the extension with isolated `CARGO_TARGET_DIR` via `rch exec -- maturin develop --release --features pyo3/abi3-py310`.
- Re-run `louvain_pass1.py golden` and compare `baseline_golden.sha256` plus per-case equality.
- Re-run loop baselines for `ws150` and `ws300`; keep only if public output remains unchanged and the raw route becomes parity-safe or the semantic residual shrinks.
