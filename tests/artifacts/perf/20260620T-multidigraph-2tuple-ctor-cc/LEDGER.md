# Perf win — MultiDiGraph 2-tuple constructor batch path (br-r37-c1-ctor2tuple)

- Agent: `BlackThrush` · 2026-06-20 · isolated worktree at origin/main `f6134c6c0`
- File: `crates/fnx-python/src/digraph.rs` (unlocked while CrimsonRiver held the
  binding layer for MST/export work)

## Root cause

`MultiDiGraph([(u, v), ...])` from a bare 2-tuple edge list fell through to the
per-edge `add_edge` loop: `try_absorb_exact_int_str_keyed_ctor_edges` only
accepted 3-tuples `(u, v, key)` / 4-tuples `(u, v, key, data)`. So the common
2-tuple constructor was ~2x nx, while `add_edges_from` (which DOES batch) was a
1.28x WIN. (Clean isolated measurement; the shared install was contaminated by a
peer's WIP — see [[reference_warm_sweep_false_losses_2026]].)

## Lever

Extended the batch path to accept bare 2-tuples as `add_edge(u, v)` with an AUTO
integer key (next free key per pair; each 2-tuple a distinct parallel edge,
matching nx's `new_edge_key`). 2-tuple attrs + key objects stay LAZY (py_edge_key
falls back to the integer key; the attr mirror materializes `{}` on demand),
skipping a per-edge PyDict alloc. 3/4-tuple semantics unchanged.

## Win / loss / neutral vs NetworkX 3.6.1 (clean worktree, warm min-of-20)

| MultiDiGraph(edges), 1500n/7000e | before | after |
| --- | ---: | ---: |
| 2-tuple edge list | 0.73x | **1.34x** (14.4ms -> 8.09ms) |

~1.8x self-speedup. 3-tuple ctor 8.72ms / 4-tuple 9.79ms — unchanged (parity True).

## Parity

1500 random MultiDiGraphs from a MIX of 2/3/4-tuples incl. parallel edges +
self-loops: 0 mismatches (node order, edges(keys=True,data=True), succ adjacency
row order). 2-tuple attr dicts: stable identity, isolated per parallel edge,
empty `{}`. `pytest -k 'ctor or construct or multidigraph or convert'`: 1931
passed (the lone failure `test_delegated_rcm_consumer_...` is PRE-EXISTING — it
fails identically on clean origin/main and uses `fnx.Graph`, not MultiDiGraph).

## Note for the construction frontier

The same ~0.7x loss exists for `Graph`/`DiGraph`/`MultiGraph` constructors, but:
DiGraph already batches 2-tuples (`try_add_plain_edge_batch`, 0.82x residual is
the `__init__` validation); Graph + MultiGraph `__new__` live in `lib.rs`
(reserved by a peer this session). Revisit those when `lib.rs`/`__init__.py` free.
