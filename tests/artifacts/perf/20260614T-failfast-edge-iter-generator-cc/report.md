# _FailFastEdgeIterator → generator function: DiGraph edges(data=True) 1.46x→0.90x (beats nx), edges() 1.28x self

Bead: br-r37-c1-2a00r (substrate lever, part 4 of N — the iterator-drain half)
Agent: cc / 2026-06-14

## Problem

The mutation-guarded edge iterator (`_FailFastEdgeIterator`) was a CLASS with a
per-element `__next__`. Every consumer (`_DiGraphEdgeView.__iter__`,
`EdgeDataView.__iter__`, OutEdgeView, …) returned an instance; `for`/`list`
drove it via `next(instance)` → bound-method dispatch + a `self._graph` /
`self._expected_*` LOAD_ATTR chain PER EDGE. Profiling `list(DiGraph.edges())`
(40k edges): the kernel `_native_edges_no_data()` was 5.4ms but the
`_FailFastEdgeIterator` drain was ~6.8ms — the bigger half.

## Fix (one lever: class → generator function, same baseline timing)

Rewrote `_FailFastEdgeIterator` as a regular FUNCTION that captures the guard
baseline eagerly (call time == the old `__init__`, so `it = iter(view);
G.add_node(); list(it)` still raises identically) and returns an inner
generator. Consumers now drain via the C-level generator protocol with the
guard values as cell-locals — no per-element bound-method dispatch, no
re-resolving `self.*`. Per-element semantics (raise condition, message, timing)
are byte-identical. Pure-Python; no rebuild.

## Proof (deterministic)

- DiGraph parity: 40-seed sweep edges() / edges(data=True) / edges(data="weight")
  — **0 mismatches** vs nx.
- Undirected edges(data=True): 30-seed sweep — 0 mismatches.
- Mutation guards: DiGraph edges(), Graph edges(data=True), AND the
  `iter();mutate;drain` baseline-at-call-time case all raise `RuntimeError`
  exactly as before.
- Suite: 5961 passed, only the 1 known pre-existing gexf fail.

## Timing (interleaved min-of-10, warm)

| op | before | after | nx | result |
|----|--------|-------|-----|--------|
| DiGraph edges(data=True) n=2000 (40k E) | 5.73ms | 3.81ms | 4.22ms | 1.46x → **0.90x (beats nx)** |
| undirected edges(data=True) n=2000 | 7.10ms | 6.11ms | 5.79ms | 1.24x → **1.05x** |
| DiGraph edges() n=2000 (40k E) | 12.19ms | 9.55ms | 2.19ms | **1.28x self** (residual = kernel) |

Helps every `_FailFastEdgeIterator` consumer at once.

## Residual (2a00r)

DiGraph edges() (NoData) is still 4.36x vs nx: `_native_edges_no_data()` kernel
(5.4ms, py_node_key String-hash tax — same index fix as undirected, DiGraph has
`edges_ordered_indices()`) + the guard's 2 PyO3 getattrs/element (nodes_seq +
edges_seq; a combined single-FFI guard token would halve it). Those are the next
two sub-levers.
