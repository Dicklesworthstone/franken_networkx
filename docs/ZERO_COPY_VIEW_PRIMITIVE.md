# Zero-copy cross-language views — design, ownership model, and measured limits

**Owner:** franken_networkx (BlackThrush, cc lane) — Primitive Transfer Bus, 2026-07-26.
**Consumers:** frankenpandas (block storage, O(1) `.values`/transpose), franken_numpy
(Python-surface copy tax).
**Status:** design published before the full win, as instructed, so the consumers do not
rediscover it independently.

---

## 0. Read this before you inherit the premise

I was named owner on the strength of *"CachedSnapshotView Arc-sharing measured 77,795×"*.
I own that result — and **it is not a cross-language zero-copy result.** Publishing the
design without saying so would export a false premise to two repos.

What `br-r37-c1-04z53.9176` actually measured (`docs/NEGATIVE_EVIDENCE.md:279`): cloning a
`GraphSnapshot` 32× for a 2,048-node / 8,192-edge graph cost **589,824 fresh `String`
allocations, 5,308,416 bytes copied, 24,669,654 ns**. Putting the immutable snapshot behind
an `Arc` so derived `Clone` shares it reduced an **O(V+E) deep clone to one atomic refcount
increment**: 31,896,161 ns → 410 ns, 15/15 wins, same-binary, A/A null 1.0001×.

That is **structural sharing of immutable data between Rust clones**. The bytes never
crossed the PyO3 boundary. The 77,795× is a statement about what a deep copy costs, not
about what a language boundary costs. **The magnitude does not transfer.** What transfers is
the *pattern* — and the pattern's payoff is exactly `cost_of_the_copy_you_removed`, which for
frankenpandas (`.values` on a large block) is large, and for a 3-element tuple is nothing.

### The per-entry cost model in the campaign doc is refuted, with numbers

The brief says *"~0.5–1 µs per returned dict entry dominates the tail"*. Measured on HEAD
(n=2000, m=8000, genuine networkx 3.6.1, consistent package, byte-identity proven):

| return shape | nx per entry | fnx per entry | ratio |
|---|---:|---:|---:|
| `edges(data=True)` | 757.8 ns/edge | **452.4 ns/edge** | **1.67× faster** |
| `to_dict_of_lists` | 1689.8 ns/node | **747.2 ns/node** | **2.26× faster** |
| `nodes(data=True)` | 27.6 ns/node | 27.1 ns/node | 1.02× |
| `adjacency()` | 26.8 ns/node | 26.0 ns/node | 1.03× |

The absolute figure is in the right range — ~450 ns/entry — but the conclusion inverts:
**networkx pays more per entry than we do.** Per-entry marshaling is not this repo's wall;
it is a place we already win, because nx must build the same containers in interpreted code
while we build them in Rust. A structural swing aimed at "stop materializing dicts" would
have optimized a surface that already wins.

**The transferable warning for frankenpandas and franken_numpy: measure the boundary before
you build a bridge across it.** In this repo the actual per-call wall turned out to be the
*Python shim wrapper* — 146.4 ns of a 262.6 ns `has_node`, 56% — against a bare PyO3 crossing
of only **41.9 ns**. The boundary is cheap here. If your measured boundary is also cheap, a
zero-copy view buys you nothing and you should go find your real 56%.

---

## 1. How Rust-owned memory reaches Python without materializing

Three tiers. They are different mechanisms with different ownership stories, and conflating
them is how this primitive gets mis-scoped.

### Tier 1 — `Arc`'d immutable snapshot (intra-language; proven here at 77,795×)

```rust
struct CachedSnapshotView {
    snapshot: Arc<GraphSnapshot>,   // immutable; Clone = refcount bump
    cached_revision: u64,           // epoch the snapshot was taken at
}
```

Ownership: every clone co-owns one immutable allocation; nobody may mutate it. Staleness is
detected by comparing `cached_revision` against the live graph's monotonic `revision`;
refresh *replaces the `Arc`* rather than mutating through it, so a sibling clone keeps the
old snapshot and stays independently stale — that independence is a tested contract here.

Use when: you hand out a consistent point-in-time image and the alternative is a deep copy.
This is the tier frankenpandas's block manager wants for `DataFrame.copy()`-shaped
operations. It does **not** cross a language boundary and does not need to.

### Tier 2 — Rust-owned *Python objects*, handed out by refcount (what this repo does)

This is the real cross-boundary primitive in franken_networkx, and it is not the buffer
protocol. The Rust struct owns the Python object:

```rust
pub(crate) node_py_attrs: HashMap<String, Py<PyDict>>,
pub(crate) edge_py_attrs: HashMap<(String, String), Py<PyDict>>,
```

and hands out co-ownership lazily:

```rust
fn materialize_node_py_attrs(&mut self, py: Python<'_>, canonical: &str) -> Py<PyDict> {
    self.node_py_attrs
        .entry(canonical.to_owned())
        .or_insert_with(|| attr_map_to_pydict(py, self.inner.node_attrs(canonical)))
        .clone_ref(py)          // atomic refcount increment — NOT a copy
}
```

**The Python object IS the storage.** First touch builds it once; every later touch is a
refcount bump. That is what makes `G.nodes[n]['color'] = 'red'` write through: the caller is
mutating the very dict the graph owns, not a copy of it.

Ownership/lifetime story, precisely:
* Rust holds a strong reference for the graph's lifetime; Python holds additional strong
  references while the object is reachable. Neither side can free it out from under the
  other — CPython's refcount is the arbiter, and `Py<T>` is exactly a strong reference.
* No `'py` lifetime escapes: `Py<PyDict>` is GIL-independent, so it can live in a Rust
  container across calls. `Bound<'py, T>` may **not**.
* Invalidation is by eviction, not by dangling: removing a node drops the map entry; any
  Python reference still held keeps that dict alive but detached, which matches networkx
  (`d = G.nodes[n]; G.remove_node(n)` leaves `d` usable in nx too).
* Reference cycles (graph → PyDict → …) are collectable only if the pyclass participates in
  GC. If your Python-visible objects can reference back into the owner, implement `__traverse__`
  /`__clear__` or you leak. franken_networkx's attr dicts hold only scalars, so it does not.

Use when: the payload is a Python object the caller may mutate and expects to be *the same
object* next time. Cost model: `O(payload)` once, `O(1)` refcount thereafter.

### Tier 3 — buffer protocol / `__array_interface__` over contiguous numeric memory

**franken_networkx has none of this** — no `PyBuffer`, no `memoryview`, no `Arc` crossing
into Python anywhere in `crates/fnx-python/`. I am not going to claim experience I do not
have. But this is the tier frankenpandas and franken_numpy actually need, so here is the
design and the trap:

```rust
#[pyclass]
struct ColumnView { data: Arc<Vec<f64>>, offset: usize, len: usize }
// expose __buffer__ (PEP 688) / __releasebuffer__, or __array_interface__ for numpy
```

* The exporter must keep the backing allocation alive for as long as **any** exported buffer
  exists. `Arc<Vec<T>>` gives you that: each export clones the `Arc`, and the Vec dies when
  the last buffer is released. Do **not** export a pointer into a `Vec` you can `push` to —
  reallocation invalidates every outstanding view. Freeze it (`Arc<[T]>`) or version it.
* Exported memory must be **immutable for the export's lifetime**, or you must expose it
  read-only. NumPy will happily write through a writable buffer; if Rust also writes, you
  have a data race that `#![forbid(unsafe_code)]` will not save you from, because the race is
  across the FFI boundary, not inside Rust.
* Strides/layout must be declared exactly. A pandas block is 2-D and often column-major
  relative to the row-major numpy default; getting this wrong produces a silently transposed
  result, not a crash.
* This tier only works for **POD element types**. The moment an element is a Python object,
  you are back in Tier 2.

---

## 2. Keeping observable parity while doing it

Parity is not a property of the view; it is a property of what the view *iterates*.

1. **Insertion order is contractual.** Node and edge order come from `IndexMap`/`IndexSet`
   iteration, and networkx's order is an observable output — several tie-break contracts in
   this repo (`edges_ordered` emission orientation, copy-walk row order, snapshot/pickle
   order) are pinned by tests. Therefore **a view must iterate the ordered storage, never a
   `HashMap` derived from it.** The single most common way to break parity while "just adding
   a view" is to key the view by hash for O(1) lookup and then let iteration inherit that
   hash order.
2. **Algorithmic tie-breaks must stay in the kernel.** `DijkstraState.seq` — the monotonic
   counter that breaks equal-distance ties — is part of the answer, not an implementation
   detail. A view may transport results; it may never *re-derive* an ordering the kernel
   already decided. If a lazy view recomputes on access, it must recompute with the same
   sequence discipline or it will disagree with the eager path on ties.
3. **Identity is contractual where the container is mutable.** `G.nodes[n] is G.nodes[n]`
   must hold, and mutation through the returned object must be visible. Tier 2 gives this for
   free (it is the same object); Tier 3 cannot give it at all for object payloads.
4. **Prove it before timing.** Every claim in this document was gated on a canonical
   order-preserving digest of the full result compared between arms *before* any timing ran.
   Order-insensitive comparison (sets, sorted keys) will pass while parity is broken.
5. **Mutation-during-iteration.** nx raises `RuntimeError: dictionary changed size during
   iteration`. A lazy view over Rust storage will not raise unless you make it: carry the
   epoch, check it on `__next__`, raise the same error type. Silently returning a coherent
   answer where nx raises is a parity break in the direction users will not notice until it
   corrupts their result.

---

## 3. Where this does NOT work

Stated plainly, because the failure modes are what cost time:

* **Heterogeneous / object-typed payloads** cannot use Tier 3 at all. Graph attribute dicts
  hold arbitrary Python objects; there is no buffer to export. This is why franken_networkx
  lives in Tier 2 and always will for attributes.
* **Anything the caller may mutate independently.** If the contract says the caller gets a
  *copy* they can scribble on without affecting the source, a shared view is a correctness
  bug, not an optimization. Check the incumbent's contract, not its docstring.
* **Results computed on demand.** A view over `all_pairs_shortest_path` is not zero-copy —
  the data does not exist until you compute it. You can make it *lazy*, but that is a
  different primitive (deferred computation) with a different risk: it moves the cost to an
  unexpected place and breaks the caller's timing assumptions.
* **Small returns.** Below roughly a few hundred elements the view's own construction and
  attribute-lookup overhead exceeds the copy it avoids. Measured here: `nodes(data=True)` and
  `adjacency()` are already at 1.02–1.03× — there is nothing to win, and a view would add a
  Python object per access on a path that currently allocates none.
* **Growable backing storage.** Any exported buffer pins the allocation; a graph or frame
  that can reallocate mid-view must either freeze, copy-on-write, or version-and-invalidate.
* **When the boundary is not the wall.** Measured here: bare PyO3 crossing 41.9 ns versus a
  Python shim wrapper of 146.4 ns on the same call. We would have built a bridge across the
  cheap part.

---

## 4. The per-entry cost actually eliminated

Honest accounting, all measured on HEAD:

**Tier 1 (proven, 77,795×):** eliminated 589,824 String allocations and 5.3 MB of copying per
32 clones — i.e. the entire O(V+E) duplication — replaced by one atomic increment. Per-entry:
~**410 ns → ~0 ns per node+edge per clone**. This is the real number and it is enormous
*because deep-copying a graph is enormous*, not because a boundary was crossed.

**Tier 2 (in production here):** first touch of a node's attr dict costs **911.5 ns** (lazy
build + cache); every repeat touch costs **741.8 ns**, of which the marshaling component is
gone. **~169.7 ns/node, 19% of first-touch cost, amortized away**, with object identity
preserved (`G.nodes[n] is G.nodes[n]` → True). Note what the residual 741.8 ns is: *not*
marshaling — it is the Python shim wrapper plus key canonicalization, which is the actual
target (`br-r37-c1-qmi5w`).

**Tier 3:** zero, because this repo has not built it. Do not cite franken_networkx as
evidence for buffer-protocol zero-copy.

### What I would tell each consumer

* **frankenpandas** — your case is the strongest in the fleet and it is Tier 1 + Tier 3, not
  Tier 2. `.values`/transpose on a block is contiguous POD memory whose incumbent (pandas)
  genuinely returns an O(1) view; you are copying where they do not, so the copy you remove
  is the whole gap. The ledgered "non-incremental STRUCTURAL blocker" framing is right: block
  storage cannot be landed incrementally because the *layout* is the change. Land it
  default-off behind a flag, prove `.values` parity including the writable-view semantics
  (pandas lets you write through some of them — check which), then flip.
* **franken_numpy** — your own TSQR REJECT concluded "the Python-surface copy plus residual
  recompute IS the wall, not the kernel". That is a Tier 3 statement and it is the right
  diagnosis. But note the trap it walked into and that I nearly repeated: confirm the copy is
  the wall *by measuring it*, not by inferring it from the kernel being fast. A cheap way to
  test it before building anything: time the same operation returning a scalar (no surface
  copy) versus returning the array. If the delta is not most of your gap, the copy is not
  your wall.
* **Both** — the ownership rule that will bite you is the same one: **an exported buffer pins
  its allocation, and a growable container cannot export.** Decide up front whether your
  storage is frozen-on-export (`Arc<[T]>`), copy-on-write, or epoch-invalidated. Retrofitting
  that decision after the first view ships is a rewrite.

---

## 5. What franken_networkx will actually build, and when

Given §0, the honest answer is that **this repo is not currently boundary-bound**, so I am
not going to build Tier 3 here to justify owning the primitive. What I will do:

1. Keep Tier 2 correct and documented — it is load-bearing for attribute write-through.
2. Take `br-r37-c1-qmi5w` (Python shim wrapper, 56% of per-call cost) — measured, and the
   actual wall.
3. Re-open Tier 3 here **only** if a returning API is measured with ≥20% exact self-time in
   PyO3 container construction. Current candidates, both already measured and neither
   marshaling-bound: `dict(G[u])` 0.5159× (Python keydict machinery) and dense
   `DiGraph.edges()` 0.5850×.

The design above is the deliverable; the ownership and parity rules are the parts that
transfer. If either consumer wants a review of a concrete buffer export, ask — I will read it
against §1 Tier 3 and §2.
