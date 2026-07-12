# br-r37-c1-nonnbrint — non_neighbors HashSet<&str> build+probe → bool-row

Status: **SHIP.** 16.35x, byte-identical. Undirected `cc` sibling of the `neighbors_indices` bool-row
family (`compedgeidx`/`compedgedirint`). My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`non_neighbors(graph, node)` (fnx-algorithms) returns every node that is neither `node` nor one of its
neighbours. The original built a `HashSet<&str>` of the neighbour **names** (one String hash per neighbour to
insert) and then probed it for **every** node in the graph (one String hash per node). On a dense hub the
HashSet build + the O(V) probe dominate the small tail sort.

## The lever — bool-row via neighbors_indices

Resolve `node` to its internal index once (`get_node_index`), mark its neighbours in a reusable
`is_nbr: vec![false; n]` row (via `neighbors_indices(ni)`, zero-alloc), then filter `0..n` with an O(1) array
read `!is_nbr[i]`, excluding the self index. No String hashing on the hot path.

## Byte-identical argument

`nodes[i]` sits at internal index `i`, so `neighbors_indices(ni)` are exactly the indices of `node`'s
neighbours → `is_nbr[i]` ⟺ `nodes[i]` is a neighbour of `node`. Self-exclusion `Some(i) != node_idx` matches
the old `n != node` (node names are unique, so name-match ⟺ index-match). Both paths `sort_unstable()` the
result, so collection order is irrelevant — the returned name set is identical.

Absent-node case preserved: `get_node_index` → `None`, so no neighbour is marked and `Some(i) != None` is
always true → every node returned, exactly like the old empty-`nbrs` path (`n != node` keeps all when `node`
is absent).

Verified: A/B **output-list parity** `assert_eq!(old_fn, new_fn)` (inline original HashSet build+probe vs new
bool-row, exact `Vec<String>` equality) passed across a dense hub node, a sparse ring node, and an absent node
before timing.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib non_neighbors_idx_ab -- --ignored --nocapture`

Dense hub (50k nodes; node `0` has ~48000 neighbours → the HashSet build + O(V) probe dominate). 61 rounds.
Ratio = hashset/bool-row, **>1 = bool-row faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BOOLROW_vs_hashset` | **16.3514x** | 61/61 | [11.5706, 21.5864] |
| `NULL_boolrow_vs_boolrow` | 0.9801x | 24/61 | [0.6856, 1.2526] |

Decisive: candidate p5 (11.57) is ~9x above the NULL p95 (1.25); all 61 rounds won; the NULL control is
centred on 1.0.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `non_neighbors`.
- Test-only: `non_neighbors_idx_ab` A/B.

## Vein status

Another win in the `HashSet<&str>`-of-neighbour-names / `has_edge`-in-loop sub-family: any per-node/per-pair
membership test over neighbour **names** → mark one endpoint's `neighbors_indices`/`successors_indices` in a
reusable bool row, test with an O(1) array read. (`non_neighbors_directed` — the DiGraph twin using
`successors`/`predecessors` — is a natural next candidate; scoped separately.)
