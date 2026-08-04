# br-r37-c1-dsepint — is_d_separator integer-index moralized graph

Status: **SHIP.** 10.35x, byte-identical (bool, 6-config differential parity + fork/collider tests). My
change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`is_d_separator(digraph, x, y, z)` (fnx-algorithms) — d-separation test for Bayesian networks: builds the
**moralized ancestral subgraph** of `x∪y∪z`, removes `z`, and checks whether any `x`-node reaches any
`y`-node. The old kernel built the moralized graph as `HashMap<String, HashSet<String>>` with String cloning
throughout — the ancestors BFS, the undirected/co-parent edge inserts, the z-removal, and the final
reachability BFS all key by node name.

## The lever

Resolve the graph-resident members of `x/y/z` to indices, compute the ancestral set as a `vec![bool; n]`
(BFS over `predecessors_indices`), build the moralized adjacency as `Vec<HashSet<usize>>` (undirected edges
via `successors_indices` + co-parent marriages), remove `z` by index, and BFS reachability `x→y` over
indices.

## Byte-identical argument

The result is a `bool` — "does any x reach any y in the moralized ancestral graph minus z" — which is
**order-independent**, so translating the String-keyed graph to indices gives the identical answer regardless
of HashSet iteration order. The one subtlety is **phantom names** (members of x/y/z not in the graph): they
have no adjacency and are inert in the old kernel **except** a node in `x∩y \ z`, which the old BFS seeds from
x and immediately matches at pop → returns false. That single case is handled by an upfront
`x.any(|xn| y.contains(xn) && !z.contains(xn))` check; every other phantom interaction is inert, so dropping
phantoms (`get_node_index → None`) changes nothing. Verified two ways: (1) a **6-config differential parity**
(inline old-String vs new-integer) covering no-z, z-blocking, `x∩y` overlap, disjoint-reachable, and
disjoint-blocked — all matched; (2) the suite tests `test_is_d_separator_fork` (common cause) and
`test_is_d_separator_collider` (v-structure) pass.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib is_d_separator_int_ab -- --ignored --nocapture`

3000-node layered DAG (node i has parents i-1, i-2), config `x={0}, y={2999}, z={}` (relevant subgraph = the
whole DAG). 61 rounds. Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **10.3488x** | 60/61 | [7.0717, 58.5783] |
| `NULL_int_vs_int` | 0.9768x | 25/61 | [0.7235, 1.4127] |

Decisive: candidate p5 (7.07) ~5x above the NULL p95 (1.41); 60/61 rounds won (one noise-slower). The wide
upper tail reflects the old String path's alloc/GC jitter.

## Clippy note

My change is clippy-clean (0 findings in production ~36839-36955 / test ~70838-71003, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `is_d_separator`.
- Test-only: `is_d_separator_int_ab` A/B.

## Vein status

Fourth win in the "name-keyed structure → integer index" residual sub-family (after lrcidx / lrcdiridx /
isdomint). Unlike those simple visited-set BFS, this was a full String-keyed **moralized-graph** rewrite —
still byte-identical because the output is an order-independent bool, validated by a multi-config differential
parity. The reachable, deterministic name-keyed surface is now largely swept.
