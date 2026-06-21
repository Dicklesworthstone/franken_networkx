# RADICAL LEVER (scoped, not yet landed) — switch the graph-storage hasher SipHash -> FxHash

- Agent: `BlackThrush` · 2026-06-21 · ANALYSIS + SCOPE (a substrate refactor, deliberately deferred from session-tail)

## The lever
fnx-classes stores `nodes: IndexMap<String, AttrMap>` and `edges: IndexMap<(usize,usize), AttrMap>`
with the DEFAULT hasher = std `RandomState` = SipHash (a CRYPTOGRAPHIC hash, ~20ns for 16 bytes).
Every has_edge / edge_attrs / get_index_of / construction insert hashes a key with SipHash. For
the `(usize,usize)` EDGE keys this is especially wasteful — FxHash (rustc-hash) hashes a usize
in ~3ns. Switching the hasher would speed up EVERY edge/node lookup AND construction across the
whole library (not one function) — the broadest single perf lever left after the int-batch /
multi-call / RNG / str-memo levers are all mined.

## Why it is SAFE (order-preserving)
IndexMap preserves INSERTION order via its internal Vec; the hasher only affects the key->index
HashMap (lookup speed), NOT iteration order. So nodes()/edges()/edges_ordered() stay byte-
identical. rustc-hash 2.1.2 is ALREADY in Cargo.lock (transitive) — no new download. FxBuildHasher
is Default + BuildHasher so IndexMap's serde derive still works.

## Why DEFERRED (it is a refactor, not a turn-sized change)
- ~37 `IndexMap::new()/with_capacity` sites in lib.rs+digraph.rs; ~10-12 are the nodes/edges
  fields (the rest are adjacency/successor/view maps left on the default hasher) but each needs
  `::new()` -> `FxIndexMap::default()` / `with_capacity_and_hasher`.
- 4 structs (Graph/DiGraph/MultiGraph/MultiDiGraph) x 2 fields, compiler-guided.
- serde derive + any `&IndexMap<..>` param/return signatures must be re-typed via a `FxIndexMap`
  alias; needs a full conformance pass (byte-exact, ~50k tests) because it touches CORE storage.
Landing this half-done at a 26-turn session tail risks breaking the graph backbone. It deserves
a dedicated, careful pass.

## Plan (for the focused follow-up)
1. fnx-classes/Cargo.toml: `rustc-hash = "2"` (already in lock).
2. `type FxIndexMap<K,V> = indexmap::IndexMap<K,V,rustc_hash::FxBuildHasher>;` in lib.rs + digraph.rs.
3. nodes/edges fields -> FxIndexMap; `::new()`->`::default()`, `with_capacity(n)`->
   `with_capacity_and_hasher(n, FxBuildHasher::default())`. Compiler-guided.
4. cargo build + FULL conformance (byte-exact) + perf head-to-head on has_edge / construction /
   lookup-heavy algos (betweenness, shortest-path) — expected 5-30% broad.
Pairs with the str-key memo already shipped (08f7fc686) which handles the string-FORMAT half;
this handles the string/int-HASH half. Together they chip the construction-substrate ceiling
(bead 4b5ie/9hkgu) without the full persistent-dict storage rewrite.
