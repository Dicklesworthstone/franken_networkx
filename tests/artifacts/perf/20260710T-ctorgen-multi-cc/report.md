# br-r37-c1-q86hv — iterator-shaped ctors for DiGraph / MultiGraph / MultiDiGraph

Status: **TARGET CONFIRMED + LEVER PREPARED, NOT LANDED.** Blocked on a remote
build (see "Blocker"). No Rust code committed: the keep-gate requires a
same-worker ORIG-vs-CAND A/B and a parity probe, and neither can be produced
without building the candidate `.so`.

## Baseline — verified-fresh binary

Wheel built from **pristine HEAD `7208ffd57`** in an isolated worktree, so no
peer's uncommitted `ctorskip` work is in the measured binary.
`_fnx.abi3.so` sha256[:16] = `d8abf9c02ca7021d`. networkx 3.6.1.
n=2000, m=10000, min-of-41, gc disabled, `taskset -c 40-47`, fnx and nx
interleaved inside one process so machine drift cancels. Ratio = nx/fnx, so
**>1.0 means fnx is faster**. Three rounds; every row cv < 3.2%.

| row | r1 | r2 | r3 | median | cv% |
|-----|----|----|----|--------|-----|
| `DiGraph(iter(edges))` | 0.787 | 0.792 | 0.789 | **0.789** | 0.3 |
| `DiGraph(iter(attr_edges))` | 0.349 | 0.351 | 0.344 | **0.349** | 0.8 |
| `MultiGraph(iter(edges))` | 0.489 | 0.475 | 0.474 | **0.475** | 1.4 |
| `MultiGraph(iter(attr_edges))` | 0.419 | 0.410 | 0.416 | **0.416** | 0.9 |
| `MultiGraph(iter(keyed))` | 0.312 | 0.302 | 0.322 | **0.312** | 2.5 |
| `MultiDiGraph(iter(edges))` | 0.460 | 0.472 | 0.480 | **0.472** | 1.7 |
| `MultiDiGraph(iter(attr_edges))` | 0.431 | 0.425 | 0.440 | **0.431** | 1.5 |
| `MultiDiGraph(iter(keyed))` | 0.315 | 0.321 | 0.319 | **0.319** | 0.8 |
| `DiGraph(combinations(150,2))` | 0.750 | 0.737 | 0.745 | **0.745** | 0.7 |
| `MultiGraph(combinations(150,2))` | 0.499 | 0.500 | 0.503 | **0.500** | 0.4 |
| GUARD `Graph(iter(edges))` | 0.982 | 0.982 | 0.937 | **0.982** | 2.2 |
| GUARD `Graph(list)` | 0.994 | 1.024 | 0.986 | **0.994** | 1.6 |
| GUARD `DiGraph(list)` | 1.126 | 1.116 | 1.129 | **1.126** | 0.5 |
| GUARD `DiGraph(list_attr)` | 0.955 | 0.994 | 1.028 | **0.994** | 3.0 |
| GUARD `MultiGraph(list)` | 1.159 | 1.161 | 1.152 | **1.159** | 0.3 |
| GUARD `MultiDiGraph(list)` | 1.142 | 1.170 | 1.229 | **1.170** | 3.1 |

## Why this is the mechanism, not a guess

The table carries its own **positive control**. `Graph(iter(edges))` already
received the `materialize_iterator_edge_list` drain (a788fbc9d, br-r37-c1-ctorgen)
and sits at **0.982x**. The byte-identical input shape on the three classes that
did *not* receive it is **0.789x / 0.475x / 0.472x**. Every LIST-shaped guard on
those same classes is at-or-above parity (1.126x / 1.159x / 1.170x). So the loss
is not "DiGraph construction is slow" — it is precisely and only the iterator
shape, on precisely the three ctors that never got the drain.

Cause (already established in the ctorgen ledger entry): every `__new__` edge
batch gates on `downcast::<PyList>()` / `PyTuple`. A generator carries neither,
so the batch declines and the ctor falls to the per-edge `PyIterator` absorb
loop. Draining once into a `PyList` costs ~0.044 ms on m=10000 and buys back the
whole per-edge loop.

The multigraph rows are the worst (0.312x / 0.319x on `(u,v,key,dict)`) because
their per-edge fallback also pays key allocation and mirror bookkeeping per edge.

## The lever (prepared, in `lever.patch`)

`materialize_iterator_edge_list` becomes `pub(crate)`; each of
`PyMultiGraph::__new__` (lib.rs), `PyDiGraph::__new__` and
`PyMultiDiGraph::__new__` (digraph.rs) drains a true iterator once and passes the
resulting `PyList` to the batch attempts and the per-edge fallback loop. 25
insertions, 10 deletions, three call sites.

Deliberate invariants carried over from the Graph twin:

* The drain fires only for a `__next__` carrier, which is exactly the input set
  the Python `__init__` edge-list validator skips, so no second walk appears.
* `fnx_graph_instance_mode` and the graph-copy `extract::<PyRef<...>>()` arms keep
  receiving the ORIGINAL `data`.
* The peer's uncommitted `ctor_edge_list_absorb_is_discarded(data)` arm also keeps
  receiving the ORIGINAL `data`, so the two levers compose. `digraph.rs` calls
  `crate::materialize_iterator_edge_list` fully-qualified, touching **no import
  block** — the peer holds an uncommitted hunk there.
* `snapshot_iterator_edge_item` already shallow-copies a tuple's trailing dict, so
  the multigraph `(u,v,key,dict)` 4-tuple shape is covered by the existing
  yield-time-semantics fix.

## What is NOT yet proven (why nothing was committed)

* No ORIG-vs-CAND A/B — the candidate `.so` was never built.
* No differential parity probe (fnx-vs-nx and ORIG-vs-CAND) across ctor shapes.
* The patch has never been compiled. `cargo check`/`clippy`/`fmt` unrun.

Anyone resuming: apply `lever.patch`, build ORIG and CAND wheels, run
`bench_ctorgen_multi.py` under each, and run the shared-mutable-dict probe
(a generator yielding the SAME dict each step, for both `(u,v,d)` and
`(u,v,key,d)`) before believing any number. That probe is what caught the
near-miss on the Graph twin; 49488 passing tests did not.

## Blocker

`maturin` is **not** an rch-intercepted command:

```
$ rch diagnose -- maturin build --release -m crates/fnx-python/Cargo.toml
Worker Selection (simulated)
  Skipped: Command would not be intercepted
$ rch diagnose -- cargo build --release -p fnx-python
  Effective worker: vmi1264463
```

`rch exec -- maturin build` therefore offloads only maturin's *inner* `cargo`
invocation, and when that inner call cannot get a worker it **fails open to a
local build**. Observed directly this session: the ORIG build offloaded (its
`CARGO_TARGET_DIR` holds only `maturin/lib_fnx.so` + `wheels/`, 18 MB, **no
`release/` tree**), while the CAND build launched minutes later fell open and
wrote a **179 MB local `release/` tree** before being killed. `rch exec` exposes
no strict-remote / no-local-fallback flag, so a build cannot be made to fail
closed. Under an active disk constraint the candidate build was not retried.

## Second finding: every maturin wheel is broken (filed separately)

`.gitignore` lines 147-148 are `core` and `core.*` — intended for core dumps.
maturin's ignore-aware packager applies them to the Python source tree and
silently drops **`python/franken_networkx/core.py`** from the wheel, even though
the file is tracked by git. A wheel-installed `franken_networkx` dies at import:

```
ImportError: cannot import name 'core' from partially initialized module
'franken_networkx' (most likely due to a circular import)
```

Diff of the HEAD package vs the wheel package: 86 files vs 85; `./core.py` is the
only omission. This is invisible to `maturin develop` (which drops the `.so` next
to the already-complete repo package) and to any bench that extracts only the
`.so`, which is why it has survived. The baseline above was measured after
copying `core.py` into the venv by hand.
