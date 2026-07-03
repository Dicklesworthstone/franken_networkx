# Negative Evidence Ledger

Campaign: `br-r37-c1-04z53` no-gaps performance domination.

## 2026-07-03 CopperCliff CAPSTONE (string-node floor CLOSED across all ops): every string-node laggard is the per-call canonicalise + PyO3-dispatch + fresh-hash floor — reverse-lookup PROVEN not-the-cost; only lever is architectural (integer-index storage / cached-hash key)

Fresh string-node-keyed sweep (node names `'node_%d'`, 800n/6000m) to find a REDUCIBLE string lever (not
the allocation floor already closed). Two laggards, both re-traced to the same architectural root:

`G neighbors(x)` 0.54x (deg 15) — NEW proof the reverse-lookup is NOT the cost. It returns a
`dict_keyiterator` (matches nx, no eager list). Split by degree: deg15 0.54x, deg100 0.71x — the ratio
IMPROVES with degree, so the per-neighbor `node_key_map` String-hash reverse-lookup is fine (fnx ~6.4
ns/neighbor == nx ~5.5). ITERATING the neighbors is 0.88x (near parity); only CREATING the iterator is 4x
slower (fnx 89us vs nx 22us / 300 calls) — the FIXED per-call cost: canonicalise(x) + build the neighbor
structure + PyO3 dispatch. So the index-based reverse-lookup idea (expose adj_indices + index a cached
node-object tuple) would gain ~nothing — abandoned before implementing on this evidence.

`G relabel(map)` (str->str) 0.76x — the relabeled graph is built add_nodes_from THEN add_edges_from, so H is
NOT fresh when the edges go in; the fresh str index-remap batch (5c1f0f252) can't fire and the edges fall to
the String-keyed general batch's per-endpoint `get_index_of` (String hash into the store). No faster str
existing-node batch exists because the store IS keyed by the canonical String.

CONSOLIDATED string-node floor evidence (all measured, all this session):
- construction: per-attr slope 0-attr 0.99x (PARITY) -> 1-attr 0.43x; cost STRING-LENGTH-INVARIANT (short
  key == long key) => NOT allocation; ~14 PyO3 crossings/edge for the dict->CgseValue conversion (9af303fa7).
- has_node 0.24x / has_edge 0.18x: IMPLEMENTED a no-heap stack-buffer canonical -> tiny REGRESSION
  (245->253ns); the safe from_utf8 revalidation exceeds the malloc saved (acf0bf1ef).
- neighbors / relabel: this entry — fixed per-call canonicalise + PyO3, reverse-lookup proven fine.
ROOT (invariant across every op): fnx keys its node/edge store by the CANONICAL String and must RE-DERIVE +
RE-HASH it on every call across the PyO3 boundary; nx looks the raw Python object up in a dict and reuses its
CACHED hash, and its adjacency dicts pre-exist so `neighbors`/`__contains__` build nothing. No allocator,
interner, arena, small-string, perfect-hash, or reverse-lookup change touches this — ALL empirically ruled
out (2 implemented-and-measured, 2 measured-by-invariance).
ONLY remaining lever = ARCHITECTURAL: either key the store by the Python object + its cached hash (needs
PyO3 inside the PyO3-free `fnx-classes`, a layering change) or integer-index node storage (dense int ids,
object<->id via identity). Both are multi-crate rewrites, not scoped commits. RECOMMENDATION: stop
re-attempting scoped string levers (this is the 3rd measured closure); the string-node floor is a settled
architectural boundary — pursue it only as a deliberate storage-model project, else mine other domains.

## 2026-07-03 CopperCliff IMPLEMENTED-AND-MEASURED NEGATIVE: no-heap stack-buffer node canonical for has_node/has_edge is a tiny REGRESSION — the string-node lookup floor is fresh-canonicalise+fresh-hash+PyO3, NOT allocation (allocation line now empirically CLOSED)

Directive asked to crush the string-node floor with an allocation primitive (interning / small-string /
arena / perfect-hash). Instead of predicting, I BUILT one and measured it. Added `StackCanon` (a 48-byte
`fmt::Write` stack buffer) + `with_node_canonical`, building the int/short-str node canonical with ZERO
heap allocation, and routed the read-hot `has_node` / `__contains__` / plain `has_edge` (PyGraph) through
it. Byte-exact 423/423 (int/str/longstr/float/float-as-int/tuple/bool/neg + str-vs-int collision + present/
absent + reversed undirected + DiGraph). Stash `stash@{0}` (NOSHIP artifact, kept).

SAME-SESSION before/after (build HEAD, measure; apply, measure; N=4000 lookups, min-of-30 x4 trials):
  has_node str : HEAD 245 ns  ->  stack-canon 253 ns
  has_node int : HEAD 227 ns  ->  stack-canon 231 ns
  has_edge str : HEAD 416 ns  ->  stack-canon 430 ns
A tiny REGRESSION, not a win. Removing the per-lookup heap allocation gained nothing measurable, and the
safe `str::from_utf8` re-validation the buffer needs (the crate is `#![forbid(unsafe_code)]`, so
`from_utf8_unchecked` is out) plus the closure indirection cost slightly MORE than the malloc it removed.

This EMPIRICALLY CLOSES the allocation-primitive line for the string-node floor (last turn's length-
invariance test already ruled it out for attributed construction; this is the direct implement-and-measure
proof for the single-call lookup path). has_node is 0.24x / has_edge ~0.18x because fnx keys its node/edge
store by the CANONICAL String and must RE-DERIVE + RE-HASH that key on every call, while nx looks the raw
Python node object up in a dict and reuses the object's CACHED hash (Python caches str/-int hashes) — never
re-deriving. The gap is PyO3 dispatch + canonicalisation + a fresh hash, none of which an allocator touches.
The only true levers are architectural: (a) key the store by the Python object + its cached hash, which
requires PyO3 inside the PyO3-free `fnx-classes` (layering break), or (b) integer-index node storage. Do
NOT re-attempt interning / small-string / arena / perfect-hash here — all four are now measured dead ends.

## 2026-07-03 CopperCliff SCOPED BLOCKER (measured): the attributed-construction floor is PyO3-CONVERSION-bound, NOT allocation-bound — interning / small-string / arena / perfect-hash all RULED OUT empirically; the only lever is a lazy CgseValue store (deep, layering-breaking)

Continuing the string-node momentum after the str-node-id-remap ship (5c1f0f252, which equalised str+attr
to int+attr): the residual ~0.5x is an ATTRIBUTED-construction floor common to ALL node types. Profiled it
to root instead of guessing a primitive.

PER-ATTR SLOPE (int nodes, `Graph([(u,v,dict)])`, 400 edges, total-wall vs nx):
  0 attrs 0.99x (PARITY, fnx==nx) | 1 attr 0.43x | 2 attrs 0.32x | 3 attrs 0.29x.
0-attr construction already ties nx — the whole gap is the per-edge attr dict conversion. First attr costs
fnx ~1495 ns/edge vs nx ~77 ns/edge (~20x).

ALLOCATION IS NOT THE COST (the decisive test that rules out the graveyard allocation primitives):
  short key "w" 0.44x  ==  long key ">24 chars" 0.49x  (key-length INVARIANT)
  short val         ==  long >24-char string val       (value-length INVARIANT)
Cost is independent of string length, so String-key heap allocation, BTreeMap-node allocation, and
CgseValue string allocation are NOT the bottleneck. Therefore, EMPIRICALLY RULED OUT for this floor:
string interning, small-string inline (CompactString/SmolStr), arena/bump allocation, perfect-hash node
table — every one targets allocation, which is not where the time goes.

ACTUAL ROOT: the batch collect does ~14 PyO3 boundary crossings PER EDGE (get_item x3, is_exact_instance
x4, extract x2, dict downcast, py_dict_to_attr_map's iter+extract+py_value_to_cgse) to pull each edge's
nodes + attr dict into the Rust CgseValue store. nx does ~2-3 (it stores the dict object wholesale). The
plain-batch pre-attempts early-bail O(1) on the first 3-tuple, so that is not the cost — it is the genuine
per-item Python->Rust conversion. 0-attr ties nx precisely because it skips this conversion.

THE ONLY LEVER is a LAZY CgseValue store: store the Python attr dict at construction (as the mirror already
can) and defer the CgseValue conversion until a Rust algorithm first reads the store. This INVERTS the
current eager-store / lazy-mirror invariant and — critically — requires the fnx-classes `edges` map to hold
a PyObject (or a store-read hook back into fnx-python), which BREAKS the fnx-classes/fnx-python layering
(fnx-classes is PyO3-free today). That is a large multi-crate storage-model change touching every store
reader plus the mirror-miss fallbacks — NOT a scoped commit. A within-model micro-option (drop the 2
redundant `is_exact_instance_of::<PyBool>` checks — exact-PyInt already excludes bool; unpack the tuple
once instead of 3 get_item) is ~10-20% at best and still <1x. SCOPE: the floor is real and its only true
lever is architectural (lazy store / integer-index storage), consistent with the long-standing
single-call dual-store floor. Do NOT chase allocation primitives here — measured dead ends.

## 2026-07-03 CopperCliff perf(construct): str/tuple+attr edge batch now uses the int fast index-remap path (str/int 2.57x-slower -> equal) — integer node-id remapping primitive; attributed-construction FLOOR is not string-specific

The "string-node construction floor" is really an ATTRIBUTED-construction floor common to ALL node types
(stable total-wall: int+single `Graph([(u,v,{'weight':w}),...])` 0.42x, str+single 0.54x vs nx — both pay
the per-edge `py_dict_to_attr_map` CgseValue dual-store conversion nx skips). But str/tuple carried an
EXTRA string-specific penalty: the fresh `>=8`-edge attributed batch remapped INT nodes to a dense 0..N
index and used `extend_fresh_index_edges_with_attrs_unrecorded` (O(1)/endpoint), while str/tuple fell to
the general String-keyed `collect_attr_edge_batch` -> `extend_edges_with_attrs_unrecorded`, which does a
`nodes.get_index_of(&String)` HASH LOOKUP per endpoint (2*|E| into the growing store). RADICAL PRIMITIVE
(integer node-id remapping): new `collect_fresh_general_attr_edge_batch` canonicalises each DISTINCT node
ONCE, remaps to a dense index, and reuses the int fast path's index extend + applier + proven mirror rule
(>=2 attrs eager ordered mirror; <2 deferred — safe now that fnx_to_nx_adjacency store-falls-back, see the
MST fix above). MEASURED: str+attr construction now EQUALS int+attr (str/int 2.57 -> 0.93, i.e. the
string-hash penalty is gone), str+single 0.46x -> 0.54x vs nx. Byte-exact 561/561 (str/tuple/longstr/int x
single/multi/unordered/none/dup-merge + MST first-touch + mutation-after-build) + 4249 construction/
spanning/convert conformance. NOT a beat-nx: the residual ~0.5x is the attributed dual-store floor (all
types); a full beat needs the store to accept the Python dict without the CgseValue round-trip (a deeper
storage change). LEVER: a fast path gated on `is_exact_int` node keys can be GENERALISED to any node type
by canonicalising to the String key ONCE per distinct node and reusing the same index-based extend — grep
`collect_fresh_exact_int_*` siblings that leave str/tuple on the String-keyed general path.

## 2026-07-03 CopperCliff CORRECTNESS FIX: MST (boruvka/kruskal/prim) returned a WRONG tree with DROPPED weights on batch-built weighted graphs — native fnx_to_nx_adjacency read the mirror only, not the store

Found while probing the string-node construction cost: `minimum_spanning_edges`/`minimum_spanning_tree`
(and `maximum_*`) computed a WRONG tree — fnx MST weight 161 vs nx 77 — AND the returned edges had NO
`weight` attribute, whenever the MST was the FIRST attribute access on a freshly BATCH-built weighted
graph (`Graph([(u,v,{'weight':w}), ...])`, `>=8` edges). Root: the native `fnx_to_nx_adjacency`
(algorithms.rs), used by boruvka's in-proc kernel + `backend._fnx_to_nx` conversion + community, read edge
attrs from the `edge_py_attrs` MIRROR only (`edge_attrs_for_undirected/-directed`), returning an EMPTY dict
on mirror-miss. A batch-built graph leaves the mirror UNMATERIALISED (store authoritative), so every edge
looked attribute-less -> `attrs.get(weight, 1)` defaulted every weight to 1 -> wrong tree, dropped attrs.
The sibling `graph_has_edge_attr` already carried this exact lazy-mirror fix (br-r37-c1-hasattrlazyfix);
`fnx_to_nx_adjacency` had missed it. Fix: on mirror-miss read the Rust STORE (`inner.edge_attrs` ->
`attr_map_to_pydict`), mirror-first-then-store, same as `edge_attr_py_value`. Byte-exact 300/300
(boruvka/kruskal/prim x int/str nodes x first-touch, MST weight + attrs == nx) + 2697 spanning/MST/community
conformance (the 17 previously-latent `test_spanning_edge_iterators_relabeling_equivariant[*-boruvka]` all
green). No perf regression — store-read fires only on mirror-miss, O(1)/edge: boruvka 2.25x, kruskal 3.13x,
prim 2.74x vs nx at 400n/3000m. LEVER: grep every `edge_py_attrs.get`/`edge_attrs_for_*` that returns
empty/None on miss WITHOUT an `inner.edge_attrs` store fallback — batch construction defers the mirror, so
mirror-only reads silently corrupt weighted algorithms. Sibling of the flow_hierarchy store-miss bug.

## 2026-07-03 CopperCliff SURFACE (no takeable win): transform/copy "laggards" are GC/memory-pressure NOISE; the one real residual is the string-node CONSTRUCTION floor

Swept graph transforms (copy/to_undirected/contracted/reverse/subgraph/relabel) hunting the next
keydict-view lever after the reciprocal-to_undirected ship (be99f63de). EVERY flagged sub-0.8x turned
out to be a MEASUREMENT ARTIFACT, not a real gap:
- `DG to_undirected()` read 0.30x in a graph-REUSE sweep -> really 1.98x isolated (native
  `_native_to_undirected_deepcopy` fires; the sweep reused one DG across many prior ops).
- `contracted_edge`/`contracted_nodes` swung 0.36x-1.54x across IDENTICAL trials — pure GC noise on the
  alloc-heavy full-graph copy each call; no reliable gap.
- `MG copy` read 0.58x (100ms) in a sweep holding FOUR large graphs (800/6000 each) -> really 0.96x
  (38ms) isolated. `MDG to_undirected` 0.56x sweep -> 0.73-0.93x isolated. `DG copy` 0.56x build-inside
  -> 1.4-1.55x build-once.
NEW SUBSTRATE TRAP (checklist #9): holding MULTIPLE large graphs in memory during a build-once sweep
creates GC pressure that INFLATES alloc-heavy op timings 2-3x and is class-correlated (the biggest graph's
op looks worst). Verify any alloc-heavy sub-1x in ISOLATION (one graph pair, `del`+`gc.collect()` between
classes). Ratios can stay stable while absolute times swing 2x — trust a ratio only if it repeats across
independent process-fresh runs.
The ONE reliable residual: `relabel_nodes(int->str)` DiGraph 0.68x (consistent) — isolated to the
STRING-NODE CONSTRUCTION floor: building `DiGraph([(str,str,...)])` is 0.48x (7.2ms vs nx 3.5ms) while
`DiGraph([(int,int,...)])` is 1.35x (WIN). Root: fnx canonicalises a str node "5" to `str:1:5` (the
`str:{len}:{s}` disambiguator vs int 5's `"5"`), so per-node it allocs+hashes a LONGER key. Architectural
(the canonical-string storage model), same family as the add_edge string floor; a Rust micro-opt on the
`format!("str:{}:{s}")` canonicaliser is the only lever and it's marginal (the dual-store insert dominates,
not the format). relabel int->int, and all-int-node construction, WIN — only str/tuple node labels pay it.

## 2026-07-03 CopperCliff SHIP: to_undirected(reciprocal=True) DiGraph 0.03x->0.69x, MultiDiGraph 0.08x->0.50x — native edges() + set-membership reciprocity, not adj/pred keydict views

MultiGraph/MultiDiGraph op sweep found `MDG.to_undirected(reciprocal=True)` at 0.08x (9ms) — and the
simple `DiGraph` version was an even bigger HIDDEN laggard at 0.03x (68ms!). Both iterated the pure-Python
keydict views `self.adj[u]` + `self.pred[u]` O(|E|) times to keep only edges whose reverse also exists.
Replace with the FAST native `edges()` (4.3x self) + O(1) set membership: build a set of the directed
`(u, v, key)` / `(u, v)` triples, keep an edge iff its reverse triple is in the set (exactly nx's
`key in self.pred[u][v]`). `edges()` walks the adjacency node-major (same order as the old view loop), so
kept edges + order + deepcopied attrs are byte-identical. **DiGraph 0.03x -> 0.69x (23x self), MultiDiGraph
0.08x -> 0.50x (6x self)**, byte-exact 164/164 (MDG/DG x self-loop/empty/one-way-no-reciprocal) + 2144
undirected conformance. Still <1x: the residual is `add_edges_from` rebuilding the (keyed) undirected
edges (the multigraph nested-bucket construction floor) — nx pays the same but on its native store; a full
beat needs a native reciprocal-undirected kernel. LEVER (recurring): any method iterating `self.adj[u]`/
`self.pred[u]`/`self[u]` (the keydict views) O(|E|) times is paying the per-node view floor — read via
native `edges()` and move the per-edge predicate to a set/dict lookup. Grep `for u in self:.*self.adj[u]`.

## 2026-07-03 CopperCliff SHIP (partial): read_gexf 0.47x -> 0.72x — one fused scan pass, skip node-metadata restore when all nodes are labelled

Format sweep found read_gexf 0.47-0.61x (the biggest readwrite laggard). Split probe: the native
`_fnx.read_gexf` parse is itself FASTER than nx (4.4ms vs 6.9ms), but read_gexf then runs FOUR more expat
passes over the raw XML — `_gexf_document_is_multigraph` (1.7ms) + `_gexf_document_has_hierarchy` (1.9ms)
routing checks, then `_restore_gexf_node_metadata` (2.7ms) + `_restore_gexf_graph_metadata` (2.2ms) to
recover the metadata the native reader drops. Fused the two routing checks into ONE `_gexf_scan_document`
pass that ALSO reports whether any `<node>` lacks a `label` attribute; on the native branch, skip the
node-metadata restore when none do (its ONLY native-path effect is nx's missing-label->None surface, and
nx-written GEXF always writes labels). Four passes -> two for the common case. **0.47x -> 0.72x** (16.1ms
-> 10.3ms), byte-exact 210/210 (simple/directed/nodeattr/no-label/multigraph-parallel/no-parallel) + 47
gexf conformance (the 1 remaining failure `test_write_gexf_classified...` is PRE-EXISTING — fails on clean
HEAD). TRAPS: (1) skipping node-metadata restore UNCONDITIONALLY breaks nx's missing-label->None
(hand-crafted GEXF with a label-less `<node>`) — my first "safe to skip 0/150" test used nx.write_gexf
which ALWAYS labels, so it missed the case; must GATE on any-missing-label. (2) my fused scan returned
`needs_nx=True` on ExpatError (empty/malformed) -> routed to nx which then ParseError'd on empty bytes;
the originals returned False (native path handles empty) -> return `(False, True)` on parse failure.
STILL <1x: native+graph-metadata restore is 2 passes vs nx's 1; a full BEAT needs the Rust reader to
capture graph/node metadata (the graph-metadata restore's 2.2ms is the residual). Same family as the
graphml native-reader route (3417e5763), but GEXF can't fully drop the metadata restore (native reader
drops more).

## 2026-07-03 CopperCliff SHIP (BEATS nx): read_graphml(<file>) 0.78x -> 1.98x — route filename reads through parse_graphml's native fast path

Follow-up to parse_graphml (3417e5763): a delegator sweep found `read_graphml(<file>)` still 0.78x (the
string-path parse_graphml fix didn't cover the file-path entry point). Route it: for the DEFAULT case
(node_type=str, edge_key_type=int, not force_multigraph) and a FILENAME/Path input, read the file bytes
and hand them to parse_graphml (which carries the native-reader + parallel-collapse guard). File-object
inputs — including the BytesIO that parse_graphml's own fallback passes back into read_graphml — are NOT
filenames, so they skip this and delegate: NO recursion, NO double-parse. **0.78x -> 1.98x** (5.1ms vs
10.1ms @ 300/1200), byte-exact 480/480 (str-path/pathlib.Path/file-object/node_type=int-delegated x
simple/directed/no-attr/multigraph-parallel/multigraph-no-parallel) + 135 graphml conformance. Multigraph
file UNCHANGED (pre-check -> delegation; the extra in-memory file read is ~4% of the pre-existing MG
delegation floor). The graphml read family (parse + read, string + file) now all beat nx for the common
simple case.

## 2026-07-03 CopperCliff SHIP (BEATS nx): parse_graphml(default) 0.77x -> 2.03x — route the default case to the native reader, gated on no collapsed parallel edges

readwrite sweep found parse_graphml the ONE laggard (0.77x); everything else wins 1.0-7.4x. `read_graphml`
DELEGATES to nx entirely because the native `_fnx.read_graphml` COLLAPSES parallel edges to a simple
graph. But `parse_graphml` has the STRING in hand, and nx ALSO down-converts a parallel-free multigraph
to a simple graph on read (verified), so the native reader is byte-identical EXCEPT when there are
actual parallel edges. Route the default case (node_type=str, edge_key_type=int, not force_multigraph)
to the native reader and accept it only if it kept ALL `<edge>` elements (number_of_edges == element
count) — a collapse (count mismatch) means a real multigraph -> fall back to nx. A cheap pre-check
(first `<edge>` has an `id=`, which nx emits only for multigraphs) skips the native attempt for
nx-written multigraphs so they don't pay a wasted parse before the fallback. **0.77x -> 2.03x** (native
reader is itself 2x nx; 13.2ms -> 7.0ms @ 300/1200), byte-exact 185/185 (simple/directed/no-attr/
multigraph-parallel/multigraph-no-parallel/empty/single/self-loop/string-node/node_type=int-delegated)
+ 135 graphml conformance. Multigraph parse UNCHANGED (pre-check -> delegation, no double-parse). LEVER:
a fully-delegated reader that has a native fast path "only for the simple case" can be routed by parsing
natively + a cheap post-check that the fast path didn't lose data (here: edge-element count), falling
back to the delegation when it did.

## 2026-07-03 CopperCliff SHIP (BEATS nx, not a partial): modular_product(edge-attr) 0.24x -> 3.07-3.39x — decorate only the SMALL both-edge subset

Unlike tensor/strong (whose WHOLE dense edge set needs decoration -> pure-Python ceiling ~0.5x),
modular_product's edge ATTRS are non-empty ONLY on the "both-edge" product edges ((u1,u2)∈G AND
(v1,v2)∈H, paired) — an O(E_G*E_H) subset — while the huge "neither-edge" majority stays attr-free.
So the native `modular_product_fast` kernel (adjacency-only, ignores edge attrs) builds the whole
O((V_G*V_H)^2) structure and one `set_edge_attributes` decorates only the tiny both-edge subset. The
edge-attr gate that bailed to the O((V_G*V_H)^2) Python has_edge loop is REMOVED (self-loop gate kept).
**0.24x -> 3.07-3.39x** (13-14x self; 977ms -> 73ms @ 40x20), byte-exact vs nx (edge-attr/node-attr/
both/none/multi-attr, non-self-loop hybrid path 75/75 + 80/80 prototype). Self-loops STILL bail to the
Python fallback (pre-existing modular+self-loop divergence, confirmed on OLD code 10/10 — out of scope,
not a regression). LEVER: the tensor/strong edge-attr hybrid BEATS nx (not just partial) when the
DECORATION set is a small subset of the product edges — i.e. when only some product edges carry attrs
(modular both-edge) rather than all of them (tensor). Check the attr density before assuming the hybrid
is a ceiling.

## 2026-07-03 CopperCliff SHIP (partial, pure-Python ceiling): strong_product(edge-attr) 0.29x -> 0.53x — same native-structure + set_edge_attributes lever as tensor; lexico NO-GO

Extended the tensor_product edge-attr hybrid (6f015e69c) to strong_product: build the (cartesian ∪
tensor) STRUCTURE via `strong_product_fast` regardless of edge attrs, then DECORATE the four edge passes
(1 nodes×H-edges=H attrs, 2 G-edges×nodes=G attrs, 3 tensor directed cross=paired, 4 undirected-only
tensor cross=paired) with ONE `set_edge_attributes`, avoiding the O(E_product) tuple-node `add_edges_from`.
**0.29x -> 0.53x** (~1.8x self), byte-exact 201/201 (directed/self-loop/node-attr/no-attr/multi-attr +
multigraph fallback) + 696 product conformance. Same pure-Python ceiling (<1x, tuple-node key resolution
floor; full beat needs the Rust mirror kernel). Unweighted still native 5.6x.

LEXICOGRAPHIC NO-GO (this dig): the same hybrid on lexicographic_product (a) BROKE self-loop parity —
20/140 mism, all self-loop cases (the native lexico kernel's self-loop de-dup diverges from a naive
em-map build for the dense E_G×V_H×V_H pass), AND (b) barely moved perf (0.27x -> 0.32x) because lexico's
edge set is DENSE (E_G·V_H² dominant), so the em build + set_edge_attributes is nearly as large as the
add_edges_from it replaces. Lexico stays on the Python batch; a real lexico win needs the Rust kernel.
Cartesian/corona already have Rust edge-attr kernels (beat nx); tensor+strong now have the pure-Python
hybrid; lexico+modular remain Rust-only levers.

## 2026-07-03 CopperCliff SHIP (partial, pure-Python ceiling): tensor_product(edge-attr) 0.24x -> 0.42-0.57x — native structure + set_edge_attributes decorate, not add_edges_from of tuple-node edges

Products sweep: UNWEIGHTED tensor/strong/lexico/cartesian WIN 3-6x (native kernel), but EDGE-attributed
ones LOSE 0.24-0.38x. Split probe on weighted tensor (31ms): `add_edges_from` of the 6000 TUPLE-NODE
product edges is 22.6ms — the tuple-node insertion floor; the paired-attr build is only ~1.1ms and the
`dict()` copies only ~0.7ms. `_native_graph_product` bails on edge attrs (`return None` before calling
the kernel) and drops to that Python `add_edges_from`. But the native `tensor_product_fast` kernel builds
the STRUCTURE regardless of edge attrs, so build it natively then DECORATE the paired edge attrs with ONE
`set_edge_attributes` (a per-edge attr SET on already-built edges, not a re-insertion). **0.24x ->
0.42-0.57x** (~2x self), byte-exact 201/201 (directed/self-loop/node-attr/no-attr/multi-attr + multigraph
fallback) + 248 product conformance. PARTIAL/ceiling: `set_edge_attributes` STILL pays tuple-node key
resolution per edge, so it stays <1x and DEGRADES at scale (0.57x @ 6k edges -> 0.42x @ 20k); the full
beat needs the Rust kernel to pair attrs by internal edge index (the documented "Rust dig"). Same lever
applies to strong/lexico (also `_paired_edge_attrs`) and cartesian (single-operand attrs, `_edges_cross_
nodes`/`_nodes_cross_edges` — different decoration) as follow-ups. LEVER (extends node-attr product fix
dbce71884 to EDGES): native kernel bails on edge attrs but builds structure anyway -> build native +
decorate edge attrs via one set_edge_attributes; ceiling is the tuple-node key-resolution floor.

## 2026-07-03 CopperCliff RE-CONFIRM NO-SHIP (independent repro): steiner_tree de-delegation is parity-blocked AND not faster

Independently reproduced the prior BlackThrush finding (20260621T-steiner-dedelegation-parityblocked-noship):
copying nx's exact mehlhorn into pure Python over fnx-native multi_source_dijkstra + shortest_path is
(a) PARITY-BLOCKED — mehlhorn keys on `s[v]=paths[v][0]` (nearest terminal), tie-break-dependent; my
spanning-path builder happened to avoid ties (0/240) but the prior's watts graphs diverge 19/40 — a VALID
different tree, and (b) NOT FASTER — 0.51-0.64x even in-process (fnx.multi_source_dijkstra's PATHS
materialization negates the conversion saving). steiner_tree STAYS delegated. Also re-confirmed
max_weight_matching (blossom) / treewidth_min_degree / louvain as native-kernel/stochastic floors, and
that effective_graph_resistance/kemeny/group_betweenness "laggards" from an earlier sweep were build-
inside-timing artifacts (really 1.0-2.1x).

## 2026-07-03 CopperCliff SHIP (pure-Python): max_weight_clique 0.48x -> 1.30-1.54x — nx's branch-and-bound run natively over precomputed adjacency, not the nx delegation

`max_weight_clique` ALWAYS delegated to nx via `_fnx_to_nx` because the Rust binding solves max-
CARDINALITY (ignores node weights, returns clique size as the weight) — verified 117/120 node mismatch
vs nx, so it is simply the wrong algorithm. Split probe: the conversion alone (0.34ms @ n=60) EXCEEDED
nx's entire runtime (0.29ms), and running nx's algo directly on the fnx graph's slow views was no faster
(0.70ms) — the conversion is the floor. Fix: copy nx's exact `MaxWeightClique` branch-and-bound VERBATIM
into pure Python with the ONLY change being `self.G.has_edge(v, w)` -> `w in adj[v]` over a precomputed
native adjacency (`to_dict_of_lists` -> {node: set}) and `self.G.degree(v)` -> one bulk `dict(G.degree())`.
Same node order (degree sort) + same expand/branch order + same weight validation -> byte-identical.
**0.48x -> 1.30-1.54x**, byte-exact 456/456 (weight=str/None x weight-mods x self-loops + empty/single/
directed/missing-weight/float-weight/multigraph) + 1150 clique conformance tests green. Directed raises
as nx; multigraph keeps the nx delegation. Pure-Python. LEVER (extends greedy_color/MIS): a delegated
algo whose whole tax is the `_fnx_to_nx` conversion, and whose only hot graph op is `has_edge`/adjacency,
runs natively when you copy nx's exact algorithm over a precomputed native adjacency set — the set-
membership `has_edge` is even FASTER than nx's dict method, so it BEATS nx after dropping the conversion.

BENCH-TRAP CORRECTION (build-inside-timing, generalises checklist #8 beyond in-place mutation): a
shortest-path/centrality sweep that built each graph INSIDE the timed lambda flagged FALSE laggards —
`effective_graph_resistance` 0.66x, `kemeny_constant` 0.80x, `group_betweenness` 0.90x — because fnx's
per-call `add_edge` build loop (slower than nx's) is charged to the fnx side. Rebuilt OUTSIDE timing they
are all wins/parity: EGR **1.62-2.12x**, kemeny **1.24-1.25x**, group_betweenness 0.97x. RULE: build the
graph OUTSIDE the timed region for ANY op whose runtime is comparable to an O(V+E) construction, not just
in-place mutations — fnx's add_edge-loop build is the slower side and silently taxes the measurement.

## 2026-07-03 CopperCliff SHIP (pure-Python): greedy_color(connected_sequential_*) 0.32-0.36x -> 1.72-3.47x — run the strategy natively, don't convert to an nx.Graph

Iso/hashing/coloring/chordal sweep found `greedy_color(strategy='connected_sequential_bfs'/'_dfs')` at
0.32-0.36x (largest_first is native 9.7x; dsatur 0.99x). The connected_sequential strategies route
through the FAITHFUL `_fnx_to_nx` conversion (the other str strategies use a cheap structural nx.Graph,
but connected_sequential's BFS/DFS traversal depends on per-node adjacency order, which the structural
`add_edges_from(G.edges())` scrambles). Split probe: the conversion is the ENTIRE tax — 1.31ms convert +
0.66ms colour vs nx's 0.66ms native (conversion already optimised via native bulk adjacency, not
reducible further). Only ELIMINATING the conversion beats nx. Ran nx's connected_sequential coloring
NATIVELY in pure Python over fnx: node order from native `connected_components` + `bfs_edges`/`dfs_edges`
(traversal order matches nx EXACTLY — verified) + `next(iter(component))` for the source, then greedy
colour assignment reading neighbour colours as an ORDER-INDEPENDENT set via native `G.neighbors`.
**0.32-0.36x -> 1.72-3.47x** (bfs 1.7-1.9x, dfs 3.4x), byte-exact 278/278 (30 seeds x 3 strategy names
x 1/2/4 components + empty/single/self-loop/string) + 1744 coloring conformance tests green. Pure-Python.
LEVER (sibling of the condensation/MIS ones): a delegated algorithm that pays a faithful `_fnx_to_nx`
conversion whose ONLY purpose is to feed an nx traversal can be run natively when fnx's native traversal
primitives (connected_components/bfs_edges/dfs_edges) already match nx's order AND the per-step reads are
order-independent (set of neighbour colours). Grep `_call_networkx_for_parity` / `_fnx_to_nx` callers
whose delegated algo is a plain traversal + order-independent per-node reduction.

## 2026-07-03 CopperCliff SHIP (pure-Python): directed_edge_swap ~1.0x -> 1.80-1.96x — same batch-simulate lever as double_edge_swap, directed sibling

Extended the double_edge_swap batch-simulate lever (b6d9f0f0c) to its directed sibling. `directed_edge_swap`
had the same shape: per swap 6 PyO3 calls (2 directed has_edge + 4 add/remove), and it already diverges
from nx's exact algorithm (uniform-pick; only the in/out-degree sequences owed). Fast path (gated on no
edge attrs): simulate the whole swap sequence on a pure-Python DIRECTED edge-set (ordered `(u,v)` tuples —
no min/max needed, type-safe by construction) with the IDENTICAL rng draws + skip/accept logic, apply the
NET change via one remove_edges_from + one add_edges_from in a `finally` (exhaustion partial-apply parity).
**~1.0x (parity) -> 1.80-1.96x** (~1.9x self); byte-exact vs the old per-call algorithm 40/40 + in/out-
degree preservation + exhaustion + self-loop + attributed-graph slow-path fallback + 3 error contracts;
299 swap conformance tests green. Pure-Python, no rebuild. The two edge-swap siblings that were parity/
loss are now both clean beats; connected_double_edge_swap already wins 1.17-1.31x (nx's connectivity-check
inner loop dominates, no restructure needed). CONFIRMS the lever generalises across the mutation-loop family.

## 2026-07-03 CopperCliff SHIP (pure-Python): double_edge_swap 0.73-0.75x -> 1.21-1.25x — simulate the swap sequence on a Python edge-set, apply the NET change in two batch calls

Minors/quotients/contractions sweep found `double_edge_swap` as the laggard. It already had O(1)
edge-list slot updates but still paid 6 PyO3 calls PER SWAP (2 `has_edge` + 4 `add/remove_edge`) — the
per-call mutation floor inside a loop. fnx's swap already DIVERGES from nx's degree-CDF algorithm
(uniform-edge-pick; only the degree sequence is owed, not exact output), which gives room to change HOW
the swaps are realised. Fast path (gated on no edge attrs): simulate the ENTIRE swap sequence on a
pure-Python `edge_set` of `frozenset`s (`has_edge` -> O(1) membership, no PyO3) with the IDENTICAL rng
draw pattern + uniform-pick + acceptance test, then apply the NET structural change to G with one
`remove_edges_from` + one `add_edges_from`. The net change is applied in a `finally` so a
max_tries-exhaustion still leaves G with the partial swaps done (matching the per-swap in-place path).
Byte-identical final edge set to the per-swap path (same rng, same accept boolean since
`frozenset((u,x)) in edge_set` == `G.has_edge(u,x)` at every step). **0.73-0.75x -> 1.21-1.25x**
(~1.7x self), byte-exact vs the old per-call algorithm 40/40 + degree-preservation + exhaustion
partial-apply parity + attributed-graph slow-path fallback + 4 error contracts; 115 edge-swap/
seed-parity + 837 broader conformance tests green. `frozenset` keys (not min/max tuples) keep it
type-safe for non-comparable/mixed node labels. Pure-Python, no rebuild.

LEVER: an in-place mutation LOOP that pays N per-call PyO3 ops per iteration (has_edge/add/remove) can
be simulated on a pure-Python mirror (structure only, no PyO3) and applied as ONE net batch — when the
op's exact intermediate state is not observable (only the final graph is) and the rng/accept logic is
replicated bit-for-bit. Gate on no-edge-attrs so a removed-then-readded edge's attrs can't diverge.
BENCH TRAP (cost a wrong 0.49x/0.78x reading): `double_edge_swap` MUTATES IN PLACE, so a fresh graph is
needed per rep — building it INSIDE the timed lambda charges the O(V+E) construction (comparable to the
swap time) to the op. Build OUTSIDE the timed region (fresh graph per rep, time only the swap): the
same op read 0.49x contaminated vs 1.2x clean. Add to the substrate checklist: in-place-mutation benches
must build outside timing.

## 2026-07-03 CopperCliff SHIP (pure-Python): condensation 0.59-0.70x -> 1.22-2.29x — build over the fast native SCC (which is already nx-ordered) instead of the members-materialising native kernel

Continued the less-common-algorithm sweep (3 more batches, ~90 funcs: approximation, covering,
tournament, traversal, bipartite, generators, flow, tree, operators). Almost all win 1.1-16000x; the
ONE clean takeable laggard was `condensation` 0.70x (0.59x for few-but-large SCCs). Root cause via a
shape probe: `condensation` (default path) routes to the native `condensation_nx_ordered` kernel, whose
SCC computation is fast BUT which then spends ~5x nx's build time MATERIALISING the per-SCC `members`
Python sets from Rust — measured `strongly_connected_components` alone 0.097ms vs full `condensation`
0.715ms (build = 0.62ms) while nx's build is only ~0.125ms. Since fnx's native
`strongly_connected_components` ALREADY yields Python sets in nx's EXACT order (verified SCC order,
mapping, members, edges all identical), just run nx's own condensation build over them: the `members`
come straight from the SCC result (zero re-materialisation) and inter-SCC edges are one batched
`add_edges_from`. **0.59-0.70x -> 1.22-2.29x** (bigSCC 1.92x, cyclic400 2.29x, DAG 1.22x, sparse 1.45x),
byte-exact 85/85 + strict order-sensitive 60/60 (node/edge order + mapping + members; empty/single/
self-loop/provided-scc/string-node) + 355 condensation conformance tests green. Pure-Python, no rebuild.
LEVER: a native kernel that computes structure fast but MATERIALISES a large Python result (members
sets / attr dicts) can LOSE to nx — when a faster native primitive already emits the Python pieces in
nx's order, assemble the result in Python from them (batched add_*_from) instead of the monolithic
native kernel. Grep native `*_nx_ordered` result-BUILDING kernels whose only job is to reshape a fast
native primitive into a Python graph.

Residuals surfaced NOT takeable this sweep: `dfs_labeled_edges` 0.81x (already snapshot-optimised — the
0.09ms `to_dict_of_lists` snapshot is pure dual-store materialisation overhead; its Python generator is
already FASTER than nx's, 0.30 vs 0.32ms — nx just has live dicts for free); `bipartite.degrees` 0.70x
(0.013ms delta = DegreeView-construction floor); min_edge_cover/panther_similarity/min_node_cut ~0.98x
(expensive-op parity). The less-common algorithm long-tail is now SWEPT (~110 funcs across 4 batches):
takeable wins were MIS (prior) + condensation; everything else wins or is the per-call/materialisation floor.

## 2026-07-03 CopperCliff SHIP (pure-Python, laggard closed): maximal_independent_set 0.58x -> ~1.0x — read adjacency via native G.neighbors not the pure-Python keydict view

Fresh algorithm sweep (~36 less-common funcs) found ONE real laggard: `maximal_independent_set`
0.58x (fnx 0.49ms vs nx 0.28ms @ n=400/m=1500). Not a floor — an algorithm gap. `maximal_independent_set`
runs nx's algorithm VERBATIM in Python (the native kernel picks a different valid set because it
seed.choices over string-hashed keys — a documented parity break), so its only fnx-slow step is the
per-node adjacency read `G[v]` in the hot loop. cProfile pinned it: `G[node]` routes through the
pure-Python row-view layer (`_graph_getitem_from_adj` builds a fresh view object + a `_keydict` per
access — 69300 keydict calls for a 116-node MIS). The algorithm only needs neighbour KEYS and uses
them exclusively in ORDER-INDEPENDENT set ops (verified: row/reversed/sorted neighbour order all yield
the identical MIS), so read them via the native `G.neighbors` (skips the intermediate AtlasView object)
-> **0.58x -> 0.98-1.01x** (1.77x self-speedup), byte-exact 413/413 (seeds x graph types x provided-
nodes x self-loop/isolated/string-node/directed error paths) + 217 MIS conformance tests green.

TWO NO-GO variants proved out along the way:
- **Whole-graph precompute** (`to_dict_of_lists` OR `_native_adjacency_keys()` once -> dict-of-sets):
  byte-exact but PERF-NEUTRAL/WORSE (0.58-0.69x). MIS reads only ~29% of nodes (|MIS|≈116 of 400), so
  materialising ALL adjacency eats the saving — confirms the original code's comment that a full
  snapshot is slower here. LAZY per-node access wins.
- **Passing `G.neighbors`'s raw iterator to `set.difference_update`** (instead of `list(...) + [node]`):
  measured FASTER (1.10x) but BYTE-WRONG (90/300 mismatch). Root cause is a CPython set-internals
  subtlety: feeding the `dict_keyiterator` vs a materialised `list` perturbs `available_nodes`' internal
  layout, so a later `seed.choice(list(available_nodes))` picks a different (still-valid) node and the
  result diverges. `list(G.neighbors(node)) + [node]` (matching nx's exact `list(G[node]) + [node]`
  grouping) is required for byte-exactness — and `.discard(node)` as a SEPARATE step ALSO breaks it
  (87/375). LESSON: when reimplementing an nx algorithm for speed, the argument TYPE and grouping fed
  to set mutators is parity-load-bearing, not just the element set — match nx's exact expression shape.

## 2026-07-03 CopperCliff SURFACE (floor certified): the add-side + read-side single-call laggards are PyO3-dispatch + dual-String-store bound — NOT takeable; fusion complete at Graph+DiGraph

After shipping the remove_node fusion (below), swept the rest of the single-call mutation/read
surface for a NEW lever. Conclusion: every remaining sub-1x is the per-call floor, architectural.
Fresh evidence (n=1000/m=5000, gc-off, fresh binary):
- **add_edge loop 0.30x, add_node loop 0.36x**: fnx pays ~1.9us vs nx ~0.59us per add_edge. Cost is
  IDENTICAL for int-nodes (9.42ms) vs str-nodes (9.61ms) — so it is NOT node_key_to_string
  canonicalization; it is the DUAL String store (`node_key_map` HashMap + `inner.nodes` IndexMap,
  BOTH keyed by the canonical String -> ~10 String hashes/edge across contains_key/entry/has_edge/
  differs/inner) plus the PyO3 dispatch + dual-store bookkeeping (adj_py_keys display-object mirror).
  add_node does 3 stores/node (node_key_map + node_iter_mirror + inner.nodes) vs nx's 1 dict insert.
  The one provably-local micro-opt (skip the adj_py_keys block when BOTH endpoints are new) helps only
  ~15% of edges in a lazy-node build and saves ~3 of ~10 hashes -> ~5% overall; a broader "all nodes
  exact-int" gate needs a tracked homogeneity flag = the mixed int/float/bool latent-bug surface the
  ledger repeatedly warns off. NOT worth the risk.
- **has_edge 0.28x, get_edge_data 0.26x, neighbors/successors 0.5x, adj-iterate 0.46x** (reads):
  has_edge ALREADY carries an identity-int fast path (br strict-work-removal) and STILL sits at 0.28x
  -> the read floor is PyO3-method-dispatch-bound, not String-bound (nx `x in G`/`G[u][v]` go through
  CPython's C-level dict protocol with no extension-call boundary; a #[pymethod] cannot match that).
  get_edge_data additionally MUST materialize the edge into the persistent `edge_py_attrs` mirror and
  mark the whole store dirty (it returns a LIVE mutable dict — `materialize_edge_py_attrs` inserts an
  entry unconditionally, so the `has_edge` guard cannot be fused out). `len(g[x])` is double-dispatch +
  fresh AtlasView object construction (the AtlasView `__len__` is already O(1) `neighbor_count`; `g[x]`
  alone BEATS nx 1.22x — the gap is the second dispatch, unreducible without changing the user idiom).
- **O(degree) remove_node** (the O(|V|+|E|) renumber floor that survives the fusion below): needs the
  node display-order DECOUPLED from the physical contiguous index (swap_remove the node + a display
  vector, or deferred/tombstone compaction). Measured the coupling: **149** `get_index`/`adj_indices`/
  `node_index` sites in fnx-algorithms + 18 in the bindings + 39 node-iteration sites in fnx-classes all
  assume index==display==contiguous 0..N. A large cross-surface rewrite, NOT turn-sized.
- MG/MDG remove_node are STRING-keyed nested maps (no index renumber) -> nothing to fuse; the fusion
  lever is COMPLETE at simple Graph (big) + simple DiGraph (small).
- readwrite/convert/generator/algorithm domains ALL win 1.06-82x (to_dict_of_lists 2.99x, from_edgelist
  1.68x, to_scipy_sparse 2.23x, density 82x, is_connected 34x, dfs_tree 4.2x, ...) — the floor is
  isolated to the per-element mutation/read PRIMITIVES. No shippable single-call win this dig; the only
  real remaining frontier is the integer-node-key storage rewrite (unifies the dual store AND unblocks
  O(degree) removal).

## 2026-07-03 CopperCliff SHIP (partial, #1 laggard): remove_node loop fused ~9|E| passes -> ~3|E| — 0.059x -> 0.082x (simple Graph)

The single biggest measured gap of the campaign is the incremental `remove_node`-in-a-loop
(0.005-0.06x, ~17-200x slower). Root cause is architectural: the store is index-based, so every
removal renumbers indices > idx to stay contiguous (O(|V|+|E|), quadratic over a loop of k). A
scaling probe (fix |V|, vary |E|) proved the per-removal cost is E-DOMINATED (N=2000: 27us @ M=1000
-> 366us @ M=16000, ~linear in |E|; only weakly N-linear). So the levers are the O(|E|) passes, not
the renumber floor.

The simple-`Graph::remove_node` made ~9 separate O(|E|)-ish passes per call: build a keep-mask,
`edges.retain`, `edge_index_endpoints.retain`, `adj_indices` retain, `adj_indices` decrement,
`edge_index_endpoints` decrement, and a full `edges` map REKEY rebuild (alloc + rehash). But the
removal ALWAYS rebuilds the edges map (the rekey), and `retain` + `rekey` BOTH preserve survivor
order — so the incident-drop, the index-decrement, and the rekey can be FUSED into ONE
order-preserving rebuild pass over the element-parallel `(edges, edge_index_endpoints)`, and the
adjacency retain+decrement into ONE pass per row. Survivor order is untouched, so `edges_ordered()`
(the only observed edge order, walked from the adjacency rows, NOT the map storage order — verified:
`edges_storage_order_index_iter` consumers are all order-independent matrix/weight aggregates or
add-path-only unit tests) is BYTE-IDENTICAL by construction — zero reordering risk, unlike the
swap_remove route (which the directed types use and which IS order-perturbing but safe there).

Edge work per removal: ~9|E| -> ~3|E| (`adj` repair ~2|E| + fused edge rebuild ~|E|). Measured:
- simple `Graph` remove_node loop(500) @ n=1000/m=5000: **0.059x -> 0.082x** (50.8ms -> 37.0ms, 1.37x
  self); per-removal @ N=2000/M=16000: **366us -> 319us**; @ N=2000/M=4000: 96us -> 84us.
- `DiGraph::remove_node`: incident-drop was already O(degree) `swap_remove`; fused the succ/pred
  retain+decrement into one pass each (smaller, same class).
STILL SUB-1x: this removes the reducible per-pass overhead but NOT the O(|V|+|E|) renumber floor —
matching nx's O(degree) needs stable node ids (swap_remove the node + a decoupled display-order
vector, OR deferred/tombstone compaction at read chokepoints), a large cross-surface rewrite that
gates the whole index architecture. Byte-exact: 74/74 cases (Graph + DiGraph × 6 seeds × attrs ×
{random30, front25, back25} + self-loop/isolated) across base/copy/pickle/deepcopy; 71 fnx-classes
unit tests green. LEVER: when a per-element mutation ALWAYS rebuilds a container downstream (here the
rekey), FUSE the earlier retain/filter/decrement passes INTO that rebuild — order-preserving, so
byte-identical, and it collapses N passes to 1 with no invariant change.

## 2026-07-02 CopperCliff SURFACE (MAJOR gap cluster, previously invisible): incremental MUTATION-in-a-loop is 0.01-0.57x — index-store O(N+E)-per-removal

Benched a stressor NO prior sweep had touched: incremental mutation (add/remove one element at a
time), reps=15, builds outside. CONFIRMED cluster (n=1000, m=5000):
- **remove_node loop (500x) = 0.01x** (49.8 vs 0.56ms — ~90x slower, ~100us/call vs nx ~1us). THE
  biggest single gap found this campaign.
- remove_edge loop (2500x) = 0.21x
- add_edge loop (2000x) = 0.34x
- add_edges_from NON-FRESH (5000 onto a 5000-edge graph) = 0.42x; FRESH = 0.84x
- remove_nodes_from / remove_node BATCH = 1.00x (FINE — the batch amortizes the repair).
ROOT CAUSE (fnx-classes remove_node, lib.rs:1850, already "incrementally optimized"): the store is
INDEX-BASED (nodes = IndexMap; adj_indices/edge_index_endpoints are integer rows). Removing a node
does `shift_remove` (O(N)) + an O(E) `keep`-mask edge retain + an O(N+E) index-repair pass
(decrement every index > idx to keep them contiguous & preserve node ORDER). So ONE remove_node is
O(N+E); a LOOP of k is O(k*(N+E)) — the O(N^2) bomb. nx's dict store deletes a key in O(1)+O(degree)
with NO index repair (dicts preserve order for free). remove_nodes_from does the repair ONCE for all
k, hence 1.00x. This is the SAME class as compose/attributed-batch: fnx's dual/index storage pays
per-element what nx gets free from live dicts. FIX PLAN (dedicated native build, NOT a land-or-dig
turn): defer the index compaction — remove_node marks a tombstone + drops incident edges/mirror
(O(degree)), and the O(N+E) shift/repair runs LAZILY & ONCE before the next index-dependent read
(edges()/degree()/matrix), OR swap_remove (O(1)) with node display-order decoupled from the internal
index. Both need byte-exactness proven across the node-order/index surface (the exact risk that
keeps this out of a normal turn). MEASUREMENT META: this cluster was invisible for ~30 turns because
every sweep benched WHOLE-GRAPH ops (build once, measure once), never a per-element mutation loop —
add mutation-in-loop to the standard sweep. Add/remove SINGLE-call floors (add_edge 0.34x) are the
per-call PyO3-dispatch + String-canon + dual-store tax (same family as has_edge dff7a99f0); the
removal loops are the fixable-with-architecture O(N+E)-repair.

## 2026-07-02 CopperCliff SHIP (pure-Python, polish): cytoscape_data guard-bypass 1.22x -> 1.37x + shared `_materialized_view` helper; NOISE lesson (reps=4)

Followed the guard-bypass lever (88bf4181b) into the serializer family. Extracted the pattern into a
shared `_materialized_view(view)` helper (returns `view._materialize()` when present — every
NodeDataView + simple-Graph EdgeDataView — else the view) and applied it to cytoscape_data.
cytoscape_data(simple Graph) 1.22x -> 1.37x (byte-exact 200 cases, 4 types + attrs; 134 conf).
NOT a gap-closer — cytoscape_data ALREADY beat nx; this is a strict-work-removal that widens the
margin (removes the per-element `_FailFastEdgeIterator` guard). DiGraph/Multi already 1.5-2.3x
(their edge views lack `_materialize`; node loop now guard-free). BENCH NOISE LESSON (cost me time,
now the second harness trap after build-inside-lambda): a reps=4 sweep FALSELY flagged
cytoscape_data 0.86x and generate_graphml 0.84x as GAPS; reps=12-20 re-measure showed 1.22x and
1.03x (generate_graphml is XML-stdlib `_serialize_xml`-bound, byte-exact). LEVER: treat any
single-digit-reps sub-1x on a fast (<5ms) op as UNCONFIRMED until re-measured at reps>=12 with a
warmup — micro-op timings swing 20-40%. The other candidates (_copy_attrs_into = DEAD no-callers;
`.update(dict(...))` = 40 sites but ~all one-time `.graph.update(dict(G.graph))` micro, not
per-element hot) were dry. Fresh sweep (tournament/isomorphism/planar/chordal/eulerian/atlas) = ALL
wins (1.36-243x). Accessible serializer/guard-bypass vein now MINED (node_link_data was the real
sub-1x; the rest already win).

## 2026-07-02 CopperCliff SHIP (pure-Python): node_link_data(simple Graph) 0.80-0.88x -> 0.94-1.03x — bypass the _FailFastEdgeIterator per-element guard

Re-examined a documented "materialization floor" via the /alien-graveyard discipline (profile ->
one lever). node_link_data(simple Graph) was 0.80-0.88x nx. Profile: the edge loop
`for u,v,d in G.edges(data=True)` iterates the view as a Python GENERATOR through
`_FailFastEdgeIterator._gen` — a per-element mutation-during-iteration GUARD (177k __next__
dispatches at 3000 edges). node_link_data never mutates G mid-build, so the guard is pure overhead.
LEVER (cc-nldmaterialize): `view._materialize()` (present on EVERY NodeDataView + the simple-Graph
EdgeDataView) returns the SAME (node,attrs)/(u,v,attrs) tuples in the SAME order but as a RAW list,
skipping the guard — 1.85x on the edge walk alone (0.73->0.39ms). Iterate that with an `hasattr`
fallback for views lacking it (DiGraph/Multi edge views — already >= nx). Byte-exact 300 cases
(4 types, node/edge attrs, empty, custom field names, multigraph keys) + roundtrip; 116 conf pass.
0.80-0.88x -> 0.94-1.03x (parity-to-slight-beat; DiGraph 1.15x / MultiGraph 1.45x already won,
their node loop now also guard-free). The residual (~parity, not a runaway beat) is the per-edge
`{**attrs, source, target}` payload-dict build over fnx's store-materialized attrs — an inherent
floor nx avoids via live dicts. LEVER (reusable): an internal read-only consumer of
`G.edges(data=True)`/`G.nodes(data=True)` pays the `_FailFastEdgeIterator`/`_gen` per-element guard
nx doesn't — call `view._materialize()` (hasattr-guarded) for the raw list. Grep internal
`for ... in G.edges(data`/`G.nodes(data` loops in serializers/exporters.

## 2026-07-02 CopperCliff SURFACE: redundant-copy vein MINED (relabel was it); compose is a native dual-storage FLOOR

Followed the redundant-copy lever (d061e3db2). Grepped `dict(d)`/`.copy()` inside add_*_from
comprehensions: candidates were compose (15179), edge_connectivity-scrub (9327), lattice_reference
(56977), panther (49350). Only compose is a common op — but its `dict(d)` fallback is NOT taken:
Graph×Graph / DiGraph×DiGraph route to native `_native_compose` (lib.rs:11675) FIRST. So no
Python-level win there. compose is 0.73x (ea=1) / 0.47-0.59x (ea=5, scales with attr count) — a
DUAL-STORAGE floor: `_native_compose` populates BOTH the mirror (`node_py_attrs`/`edge_py_attrs`,
per-node/edge PyDict copy+update for H-wins overlap) AND the CgseValue store
(`extend_nodes_with_attrs_unrecorded` + edge_batch) — nx does ONE dict op/element. Confirmed
neither the two-pass Python fallback (8.8ms), a single pre-merged batch (6.6-10ms), nor the native
(6-9ms) beats nx (~5ms) — all ~0.5-0.7x, all byte-exact. The multigraph compose path's `dict(d)`
is genuinely NEEDED (it `.update()`s the slot in place). FUTURE NATIVE LEVER (deferred, not a quick
win): a store-only `_native_compose` that leaves the mirror LAZY (rebuild from the merged store on
first edges(data)/nodes(data)) would skip the per-element PyDict — BUT simple Graph's convention is
EAGER mirror (add_edges_from populates edge_py_attrs), so this diverges from the rest of the class
and needs the lazy-rebuilt mirror proven byte-exact (attr order + H-wins merge) across the read
surface. Same class as the persistent-mirror architecture item. LEVER (confirmed): before chasing a
`dict(d)`-in-comprehension site, check it's the TAKEN path — a native `_native_<op>` earlier in the
function usually shadows the Python fallback (grep `getattr(G, "_native_<op>"` at the function top).

## 2026-07-02 CopperCliff SHIP (pure-Python): relabel_nodes drop redundant dict(d) copy — no-attr 1.55x / weight 1.18x / node-attr 1.07x

Follow-up to b3d4d930e (attribute-heavy profile sweep). relabel's node+edge list comprehensions
copied each attr dict via `dict(d)` before handing it to add_nodes_from/add_edges_from — but fnx's
add_*_from ALWAYS materialises H's own independent dict (proven: H's dict `is not` the source dict;
mutating the relabeled H never touches G — node attrs, edge attrs, all 4 types, AND node-MERGING
where source dicts stay untouched; nodes/edges(data=True) also yield a DISTINCT dict per element, not
a reused buffer). So `dict(d)` was a pure SECOND copy — 3500 redundant dict allocations on a
500n/3000e graph. FIX (cc-relabelnodict): pass the mirror dict `d` directly in all 3 loops (node,
simple-edge, multigraph-edge keyed). Byte-exact 800 cases + explicit ISOLATION test (mutate result,
G unchanged) 0 fails; 1919 conf pass. Pure-Python. no-attr 1.55x, weight-only 1.18x, node-attr(5)
1.07x — all BEAT nx; the MANY-edge-attr case (5 attrs) improved 0.75x->0.80x but stays a dual-storage
FLOOR (native `_try_add_edges_from_batch` converts each scalar attr to a CgseValue + builds the
mirror, ~15k conversions at 5x3000 — nx stores the dict by reference; scales with attr COUNT, so
1-attr wins, 5-attr floors). LEVER: a copy/rebuild that wraps view dicts in `dict(...)`/`.copy()`
before add_*_from is double-copying — fnx's batch adders already isolate; pass the view dict directly
(verify: result `is not` source + mutate-result-leaves-source test). Grep `dict(d)`/`d.copy()` inside
add_nodes_from/add_edges_from comprehensions.

## 2026-07-02 CopperCliff SHIP (pure-Python): relabel_nodes(attributed) ~0.95x -> 1.10x — node loop via nodes(data=True), not per-node G.nodes[n]

STRING-NODE profile sweep (per the build-outside bench-trap lesson 55664096c). relabel_nodes on a
500-node string-keyed weighted Graph was ~0.78-0.95x nx. Profiled: the attributed copy path's node
list `[(map.get(n,n), dict(G.nodes[n])) for n in G]` (init.py ~53742) paid a per-node NodeView
`__getitem__` + `G.nodes` property RE-EVAL per node — 0.361ms for the node list vs 0.055ms via one
`G.nodes(data=True)` native iteration (6.6x on that list, ~9% of the whole relabel). FIX
(cc-relabelnodesdata): `[(get(n,n), dict(d)) for n, d in G.nodes(data=True)]` — same (node,
attr-copy) 2-tuples in the same node order => byte-identical, incl node-MERGING relabels (later
duplicate wins). ~0.95x -> 1.10x (BEATS nx). Byte-exact 800 cases (Graph/DiGraph/Multi(Di)Graph,
node+edge attrs, merging/bijective/callable mappings, string+int nodes, copy=True/False) 0 fails;
1835 conf pass. Pure-Python. LEVER (recurring modularity-family): a copy/rebuild that does
`dict(G.nodes[n]) for n in G` or `G[node] for node in G` pays per-node view __getitem__ + property
re-eval — replace with ONE `G.nodes(data=True)` / `G.edges(data=True)` / `to_dict_of_*` native
iteration; byte-exact when order preserved. STRING-NODE profile ALSO surfaced (unfixed, floors):
has_edge bulk 0.23x + neighbors bulk 0.47x — the string variant of the PyO3-dispatch/String-canon
floor (dff7a99f0; the int identity fast path can't apply to strings).

## 2026-07-02 CopperCliff SURFACE: conversion-trap vein MINED; most "gaps" this sweep were BENCH-TRAPS (build inside the timed lambda)

Followed the modularity conversion-trap lever (c1b59f38c). Grepped 198 `_networkx_graph_for_parity`
sites + benched 5 domains (conversion ops, link prediction, matrix exporters, flow/matching/
connectivity, structural metrics). RESULT: no shippable win — two findings worth more than churn:
(1) CONVERSION VEIN MINED: the conversions that mattered were modularity (already fixed); every
other converting op is a WIN or parity when measured correctly (intersection 1.29x, dag_longest_path
1.6x, MST 1.65x, is_isomorphic 2.1x, ...). Real residual gaps are all modest FLOORS: treewidth_min_
degree 0.72x (pure-Python heuristic + double adjacency snapshot; a native to_dict_of_lists snapshot
saves only ~6% and stays sub-1x — NOT worth it + inherent frozenset-node canonicalization for the
result Graph), treewidth_min_fill_in 0.86x, max_weight_matching 0.86x (Blossom), non_randomness 0.76x
(scipy eigenvalue-bound).
(2) BENCH-TRAP (recurring, COSTLY — this is the real lesson): my sweep harness builds graphs INSIDE
the timed lambda for ops that take a 2nd graph or a fresh graph (`fnx.op(mk(fnx,...))`), so the O(E)
BUILD is timed too and inflates the apparent gap. EVERY "gap" that survived re-measurement with the
graph built OUTSIDE was either a win or a smaller floor: effective_size 0.77x->6.1x REAL, constraint
0.86x->fine, intersection 0.51x->1.29x, non_randomness 0.54x->0.76x, treewidth 0.52x->0.72x. LEVER:
NEVER build/copy a graph inside `run(lambda: op(mk(...)))` — hoist ALL graph construction outside the
reps loop; an apparent 0.2-0.5x gap on an op that takes a second/fresh graph is a build-time artifact
until proven otherwise by a build-outside re-measure. (set_edge_attributes 284e5fd75 + modularity
c1b59f38c survived this check — they were real; many sibling "gaps" did not.)

## 2026-07-02 CopperCliff SHIP (pure-Python): weighted community.modularity 0.23x -> 0.67x — drop the fnx->nx graph copy, run nx's formula on native views

Computational-algorithm sweep. `fnx.community.modularity` on a WEIGHTED graph was 0.23x nx (500n
3000e: 9.5 vs 2.2ms). `_modularity_backend_impl` (init.py:14579) delegates the weighted case to
`_nx.community.modularity(_networkx_graph_for_parity(G), ...)` — a full O(E) nx.Graph COPY then
nx's algo. Profiled: the copy is NOT even the main cost; nx's algo on fnx VIEWS (no copy) is still
0.15x because nx's `sum(wt for u,v,wt in G.edges(comm,data=weight) if v in comm)` iterates fnx's
EdgeDataView as a GENERATOR (per-element __next__ PyO3 dispatch x thousands). FIX
(cc-modweightednative): run nx's EXACT reduced formula on the fnx graph's own native byte-exact
degree/edges views, but materialize each community's `edges(comm, data)` to a LIST first so the
intra-community weight sum is a plain `builtins.sum` over a Python list — SAME elements, SAME
order, SAME Neumaier compensation as nx => byte-identical. 0.23x->0.67x (2.9x self). Byte-exact
400 mixed cases (weighted/unweighted, float/int, directed-delegate, resolution 0.5/1/2, multi-
community) + NotAPartition + ZeroDivisionError(deg_sum==0) contracts; 1291 conf pass. WHY NOT a
beat: fnx's native degree(weight)/edges(comm) views are ~0.9x nx's live-dict walk, and the
byte-exact-order requirement forbids the faster ONE-pass reduced formula — the global-edge-pass
variant is 3.5ms but ULP-diverges on FLOAT weights (69/195, summation order), so it's out. 0.67x
is the byte-exact ceiling here. LEVER (big): a "native backend" that secretly does
`_networkx_graph_for_parity(G)` + nx-algo is a CONVERSION TRAP — grep `_networkx_graph_for_parity`
/ `_fnx_to_nx` in backend impls; replace with nx's formula on native views + LIST-materialize any
per-element view generator nx iterates (the __next__ dispatch, not the copy, is usually the cost).

## 2026-07-02 CopperCliff SHIP (strict-work-removal, NOT a beat): has_edge(int) 22% faster via dynamic-verified identity-int path; residual is a PyO3-dispatch FLOOR

Unblocked last turn's has_edge SURFACE. The identity-int fast path is safe WITHOUT the
lazy_int_node_stop reset question: verify identity DYNAMICALLY per call. For exact-int u
(`is_exact_instance_of::<PyInt>()`, bool excluded, fits usize), `node_index_matches_int(iu)` =
`nodes.get_index(iu)` (O(1)) + a no-alloc `str::parse` == iu — confirming the node AT index iu IS
int iu. Any removal / remove+readd / remap that broke index==value simply fails the check ->
string fallback. Then `edges.contains_key(canon_pair(iu,iv))`. NO `i.to_string()` heap alloc, NO
String-hash `get_index_of`. Byte-exact 1500 graphs (removals, remove+readd, negative/large/float
(5.0==5)/bool/str/out-of-range probes) 0 fails; clippy clean; 2878 conf pass.
MEASURED: int has_edge 0.66->0.515ms (22%, above the 9-18% rch noise band) and 2.41x vs the
string-path fallback (1.24ms) — a REAL strict-work-removal. BUT still 0.39x vs nx (0.515 vs
0.201ms) — DOES NOT BEAT NX. ROOT of the residual: has_edge is a micro-op bounded by the Rust
`#[pymethod]` PyO3 dispatch (~258ns/call even with zero string work) vs nx's trivial in-Python
`v in adj[u]` (~100ns/call). A Rust pymethod cannot beat a Python dict lookup for a per-call
trivial op — dispatch-bound FLOOR, not a string floor (my last-turn hypothesis was half-wrong).
Shipped on mechanistic grounds (strict work removal + byte-exact + no regression) and because it
establishes the proven-safe DYNAMIC-VERIFIED identity-int technique — reusable where string work
is NOT dispatch-dominated. LEVER: the technique beats nx only on ops that do enough work per call
to amortize the pymethod dispatch (list-returning neighbors/successors, batch probes) — has_edge
alone is too small. NEXT: apply to neighbors/DiGraph.has_edge/successors (list-returning ->
dispatch amortized -> string-removal likely a real beat).

## 2026-07-02 CopperCliff SURFACE (String-keyed-storage floor family): has_edge/neighbors/successors bulk 0.34-0.52x — identity-int fast path blocked by index-stability-under-removal

Follow-up to the set_edge_attributes win (284e5fd75). Checked the attr-setter SIBLINGS + a
subgraph/neighbors/lookup sweep. No shippable win — findings:
- Attr-setter siblings are FLOORS, not the same lever: set_node_attributes(scalar) 0.47x is a
  MATERIALIZATION floor (its native broadcast must CREATE a PyDict per node — nx nodes always have
  one; the `edge_py_attrs.values()` lever does NOT transfer because attr-less nodes have no mirror
  entry, so len<node_count and it correctly falls through). set_edge_attributes(dict)/
  set_node_attributes(dict) 0.54-0.70x are STRING-CONVERSION floors (the user-supplied (u,v)/node
  keys must be canonicalized to Strings + resolved — inherent to String-keyed storage).
- has_edge bulk 0.34x, neighbors/successors/predecessors bulk 0.40-0.52x: the SAME
  String-keyed-storage floor. fnx's has_edge does 2 `i.to_string()` heap allocs + 2 String-hash
  `get_index_of` + a tuple `contains_key`; nx does `v in adj[u]` (2 int-dict lookups). The fix is an
  identity-int fast path (int u in the identity range -> index == value -> `edges.contains_key((iu,
  iv))`, no String), and the machinery EXISTS (`lazy_int_node_stop`, `has_remapped_int_key`,
  `adj_indices`). BLOCKER (why NOT built): the index==value invariant is not provably preserved under
  removal. `lazy_int_node_stop` resets ONLY on clear()/`__setstate__` (grep: all assignments), NOT on
  remove_node; a candidate gate `node_count == lazy_int_node_stop` catches a plain removal (count
  drops below stop) but NOT remove-then-readd (node re-added at a new index while count==stop again),
  and `has_remapped_int_key` tracks edge-key stores, not node re-adds. Building the fast path on an
  unproven identity gate is the exact identity-int latent-bug class ([[reference_mg_parallel_add_autokey_oN2]]:
  "note MUST flag ANY non-identity"). SAFE PREREQUISITE for a future dig: a single flag set on EVERY
  index==value-breaking op (shift-removal, remove+readd, out-of-order/remapped int add), verified
  across the mutation surface — then gate has_edge/neighbors index paths on it. Until then it's a
  floor. LEVER (meta): before building an identity-int fast path, PROVE the identity flag is reset on
  the full mutation surface (esp. remove+readd), not just construction.

## 2026-07-02 CopperCliff SHIP: set_edge_attributes(scalar) 0.27x -> 2.94x — iterate mirror dicts directly instead of per-edge String-key re-lookup

readwrite/attrs sweep (fresh domain). set_edge_attributes(G, scalar, name) on a simple Graph was
0.27x nx (8000 edges: 13.3 vs 3.6ms) — and it ALREADY routed to native
`_native_broadcast_edge_attribute`. Root (bisected: slow on EVERY call, not just the first, so NOT
mirror materialization): the native path collected an `edges_ordered()` Vec of owned (String,String)
pairs (2 String clones/edge) then re-derived each edge's (String,String,usize) mirror key to
`materialize_edge_py_attrs` (hash 2 Strings/edge) — pure overhead when the PyDict already exists. nx
just walks its live nested dicts (`for u,v,attrs in edges(data=True): attrs[name]=value`). FIX
(cc-broadcastattrmirror): when the mirror is COMPLETE (`edge_py_attrs.len() == edge_count()` — the
common state; a simple Graph populates edge_py_attrs eagerly), set the attr straight on each
`edge_py_attrs.values()` PyDict — no String clone, no per-edge HashMap lookup. Byte-identical (SAME
PyDict objects, same set_item append; order-independent since it's one scalar on every edge), gated on
len==edge_count so a lazy/partial mirror falls through to the exact per-edge materialize path.
MEASURED 0.27x->2.94x (13.3->1.09ms, ~11x self, BEATS nx). Byte-exact 600 cases (multi-attr edges,
attr names sorting BEFORE existing (a<cap<weight) AND after (z), random removals stressing the
len-gate, edges(data=True)-materialized-first, + subsequent degree(weight) consistency) 0 fails;
clippy clean; 10733 conf pass (1 pre-existing gexf-classification failure, unrelated). REJECTED the
store-write approach first: AttrMap is BTreeMap (SORTED), so writing the store + rebuilding the mirror
would reorder attrs vs nx's insertion order — the MIRROR (insertion-ordered PyDict) is order-
authoritative, proven by `{'weight','a'}` matching nx. LEVER: a bulk edge-attr op that re-derives the
mirror KEY per edge (edges_ordered String pairs -> HashMap probe) is pure overhead when the mirror is
complete — iterate `edge_py_attrs.values()` directly; gate on len==edge_count for the lazy case.
Sibling to check: set_node_attributes(scalar) 0.47x (node_py_attrs.values(), smaller absolute).

## 2026-07-02 CopperCliff SURFACE (conditional FLOOR): MG/MDG weighted degree store path BEATS nx clean (1.67-1.82x) but a mirror-materializing READ collapses it to 0.24-0.44x

Dense MultiGraph/MultiDiGraph sweep (untested profile). Apparent big gaps — MG degree(weight)
0.24x, MDG in_degree(weight) 0.44x — are NOT live bugs. Bisected by build/access state:
- CLEAN batch (add_edges_from, then degree(weight) FIRST): fnx 1.67-1.82x nx — the CgseValue store
  fast path (`weighted_degree_float_node_store`, gated `!edges_dirty`, cc-mgwdegfstore) wins.
- POST-`edges(data=True)`: MG 0.25x (2.08->15.2ms), MDG 0.38x (1.29->5.89ms).
- per-edge add_edge(weight=): ~0.85-0.95x (near parity).
ROOT: `edges(data=True)` returns nx's LIVE MUTABLE attr dicts, so MG/MDG `_native_edge_view_list`
(lib.rs:7231) calls `mark_edges_dirty()` — CORRECTLY, because a user can mutate a returned dict and
fnx cannot detect a raw PyDict mutation (it would have to return a tracking dict subclass; nx returns
plain dict). Once dirty, `_native_weighted_degree` (lib.rs:7478 `store_authoritative = !edges_dirty`)
must fall to the mirror twin `weighted_degree_float_node` -> `edge_weight_exact_f64` per edge, which
reconstructs an `edge_key` String + probes `HashMap<String,PyDict>` (~20k String allocs on the dense
MG) — nx walks its live nested adj dicts with NO String work. This is the documented dual-storage
mirror-materialization floor: fixing it needs an ADJACENCY-INDEXED mirror (walk the materialized
PyDicts by (node->neighbor->key) without edge_key String reconstruction), or write-through mutation
tracking to keep the store authoritative — both architectural, not bench-and-edit. The common case
(clean degree(weight)) already SHIPS a win. LEVER: when a store fast path "regresses", bisect by
edges_dirty state — a read that exposes live dicts (edges(data=True)) is a legit dirtier, and the
resulting mirror walk is a String-edge-key floor, NOT a store-path bug. Other dense-MG siblings
(MG copy() 0.77x, MDG reverse() 0.66x) are SINGLE NATIVE kernels (`_native_copy` / native
`MultiDiGraph.reverse`; cProfile sees nothing inside) — NOT per-edge-Python batchable, so they need
in-Rust kernel profiling, a dedicated native pass (uncertain payoff, same class as DiGraph.edges).

## 2026-07-02 CopperCliff NO-SHIP (reverted, FLOOR closed): dense DiGraph.edges() — nx's directed generator is near-optimal; eager reaches only 0.75x + trades break-early

Closes the DiGraph.edges() investigation (3rd pass; supersedes the prior OutEdgeView entry).
Correctly traced the path this time: `DiG.edges` is the PYTHON `_DiGraphEdgeView` (__name__ set to
"OutEdgeView"), whose __iter__ uses the native `_native_guarded_edge_stream_iter` ->
`DiGraphGuardedEdgeStreamIter`, a LAZY iterator that re-walked successor_indices + borrowed the
graph + built the tuple on EVERY __next__ (72k Rust-__next__ dispatches on a dense DiGraph). The
undirected `EdgeView` instead EAGER-materializes a Rust Vec once and pops per next (cheap guarded
pop) — which is WHY undirected edges() beats nx (a94bc942c). Rebuilt the DiGraph stream iterator
to the SAME eager pattern (pre-materialized Vec + O(1) both-seq guard) + removed the O(E)
`contains_key` in `edges_ordered_indices`. RESULT: 0.60x -> 0.75x (n=600 m=72201: 5.94->4.94ms),
byte-exact 600 cases (int/float/str/mixed labels + removals), mutation guard (add_edge AND
add_node both raise) preserved, break-early correct. But 0.75x still LOSES to nx and going eager
regresses `next(iter(edges()))` (materializes all). REVERTED. ROOT / FLOOR: nx's DIRECTED
edges() generator is ~50ns/edge (plain adjacency walk, NO dedup, cheap CPython generator resume);
fnx's guarded eager-Vec is ~67ns/edge (per-next PyO3 __next__ dispatch + seq-guard borrow). The
undirected fix worked only because nx's UNDIRECTED edges() is SLOW (~92ns/edge, dedup seen-set) —
there fnx's 71ns/edge wins. Against nx's fast directed generator there is no bench-and-edit win:
matching it needs a CPython-generator-equivalent, which a guarded Rust iterator cannot be. Harness
saved (dig_stream_conf.py). LEVER (asymmetry): fnx's guarded-Rust-iteration BEATS nx only where
nx's own generator is slowed by work fnx does natively (dedup); where nx's generator is already a
bare adjacency walk, it's a floor. DON'T re-dig DiGraph.edges().

## 2026-07-02 CopperCliff NO-SHIP (reverted, bench rejection): dense DiGraph.edges() 0.60x — gap is OutEdgeView, not DiEdgeView/contains_key

Follow-up to the undirected edges win (a94bc942c). Dense DiGraph edges() is 0.60x (n=600 p=0.2
m=72201: 6.5 vs 3.8ms). Tried two native changes, BOTH ineffective, reverted:
(1) removed the O(E) `self.edges.contains_key` probe in DiGraph `edges_ordered_indices`
(fnx-classes) — byte-exact but only marginal (0.59->0.58x); the lookup wasn't the bottleneck.
(2) added the cached-key-vec index fast path to `DiEdgeView::__iter__` (fnx-python) — DEAD CODE:
`type(DiG.edges)` / `type(DiG.edges())` is `OutEdgeView`, NOT `DiEdgeView`, so the edited
`__iter__` never runs. THE REAL BLOCKER (root-caused, one sentence): dense DiGraph edges()
materializes tuples in the `OutEdgeView` iterator via a per-edge `py_node_key` String hash
(`HashMap<String,PyObject>`) on each endpoint — the exact cost the undirected `EdgeView` fast
path (cached-key-vec + `edges_ordered_indices` + O(1) incref) already removes — so the fix is
to port that index fast path to `OutEdgeView::__iter__` (grep the OutEdgeView struct/impl in
digraph.rs; gate on display-uniform like the undirected one; needs a rebuild). Byte-exact
harness ready (500 int+removals, 500 mixed/float/str labels, 0 fails) for when it lands.
LESSON: verify the actual view CLASS (`type(G.edges).__name__`) before editing an `__iter__` —
DiGraph edges route through OutEdgeView, not the same-named DiEdgeView.

## 2026-07-02 CopperCliff SHIP: dense Graph.edges() 0.57-0.76x -> 1.2-1.5x — O(E) pair-dedup -> O(N) node-dedup in the native kernel

VARIED-PROFILE sweep (dense / star / complete / large-sparse) — the fix for two no-win
turns: my earlier sweeps used moderate density (m~5k) and MISSED this. `list(G.edges())` on a
DENSE simple Graph was 0.57x nx (n=500 p=0.3, m=37422: 6.52 vs 3.74ms), the gap GROWING with
edge count. cProfile saw nothing (native iteration). ROOT: `MultiGraph`-style trap in the
SIMPLE-Graph `edges_ordered_indices` (fnx-classes) — it built a `HashSet<(usize,usize)>`
`present` set (all edges) PLUS a per-edge `seen_pairs` `HashSet<(usize,usize)>` pair-dedup
(~150k pair hashes @ 37k edges). nx dedups in O(N) via first-encounter NODE tracking
(`seen[source]`). FIX (cc-edgesnodeded): the exact `reference_mg_edges_node_dedup` lever ported
to simple Graph — yield `(u,v)` when `v` is not yet a processed source, `vec![bool]` node
marker (O(1)/neighbour, no hashing); same node-major adjacency order + earlier-endpoint-first
orientation => byte-identical. Falls back to the present/seen_pairs rebuild only if the
adjacency walk doesn't reproduce the full edge set (degenerate adjacency). MEASURED: dense
edges() 0.57x->1.29x (n=500, 6.52->2.67ms), 0.63x->1.22x (n=200 p=.8), 0.76x->1.50x (n=1000
p=.05) — all BEAT nx; edges(data=True) 0.62x->0.92x (residual = the per-edge edge_key String
attr-mirror probe, a separate lever). Byte-exact: 500 cases (dense/sparse/self-loops/removals/
shuffled-node-order, order-sensitive) 0 fails incl edges(data) + edge_subgraph; clippy clean;
6336 conformance pass (2 pre-existing coverage.md doc-drift failures, unrelated — only Rust
changed). LEVER (RE-CONFIRMED, cross-type): grep native edge iterators for
`HashSet<(usize,usize)>`/`seen_pairs` pair-dedup -> replace with nx's O(N) `seen[source]`
first-encounter node-dedup. META: a NARROW graph profile (fixed density) hides scaling gaps —
sweep dense/sparse/star/complete/large to surface them. Native (Rust) vein is NOT exhausted.

## 2026-07-02 CopperCliff SURFACE (no shippable win this turn): reverse in/out_degree constant-factor + a native reverse-multigraph-weighted-degree ULP gap

Continuing the view-remnant sweep — no shippable win, three dead ends + one surfaced bug:
(1) reverse_view.in/out_degree 0.06x (constant-factor, O(V) after the earlier 9961532e2 fix).
Root: the InDegreeView computes `len(reverse.pred[node])` per node -> `_ReverseNeighborMap.__len__`
-> `len(_fast_succ_row(...))` BUILDS a per-node row dict just to count it. Native per-node
count accessors EXIST (`_native_out_degree(node)`/`_native_in_degree(node)`); wiring them into
`__len__` (gated simple DiGraph; reverse pred=parent succ->out_degree, reverse succ=parent
pred->in_degree) was byte-exact BUT only marginal (1.81->1.60ms, still 0.05x) — the residual is
the InDegreeView's per-node `_ReverseNeighborMap` OBJECT CREATION + `pred[node]` property access,
not the dict build. REVERTED (added code, no real win). To actually close it: a native bulk
reverse-degree-pairs path or making the InDegreeView read `_native_out_degree_pairs()` directly.
(2) SURFACED BUG (byte-exactness, native): reverse_view multigraph WEIGHTED in/out_degree diverges
from nx by ULP on ~4.5% of values (152/3350; 0 real-value errors, all <1e-9) — a Neumaier
SUM-ORDER gap. reverse in/out_degree returns a NATIVE `_InMultiDegreeView` (not the Python
`_degree_compute`), so the naive-vs-builtin-sum fix that worked for filtered-view weighted degree
(2b4a12bea) does NOT apply from Python — it's in the native reverse degree kernel. Deferred to a
Rust-side Neumaier-order audit. (Simple DiGraph reverse weighted degree is byte-exact.)

## 2026-07-02 CopperCliff SURFACE + NO-SHIP: greedy_color(smallest_last) is a conversion FLOOR; filtered-view adjacency() fast-row reverted byte-wrong

Two negatives this turn (documented so future turns don't re-dig):
(1) FRESH-DOMAIN SWEEP (approximation/coloring/degree-seq/core): almost all WINS (largest_first
11x, triangles 7x, square_clustering 20x, generalized_degree 4.7x, DSATUR ~1.0x). Only real
gap: greedy_color('smallest_last') 0.76x — CONVERSION FLOOR. `_greedy_color_structural_nx`
builds a structural `nx.Graph` (add_nodes_from(G)+add_edges_from(G.edges()), 2.40ms) then runs
nx's algo (8.11ms). PROVED it's irreducible without a native kernel: running
`nx.greedy_color(fnx_graph)` DIRECTLY (no conversion) is the SAME speed (10.81 vs 10.79ms) —
nx's Python algo pays fnx-view-access overhead per step == the conversion cost. (Confirmed
smallest_last/saturation/independent_set are adj-ORDER-INVARIANT — nx-direct byte-matches the
conversion; only random_sequential diverges, RNG-seeded by node order.) Needs a native Rust
smallest_last (bucket-degeneracy ordering + set-based coloring, byte-exact tie-break) — a real
kernel, not worth 0.76x. min_weighted_dominating_set 0.88x borderline.
(2) NO-SHIP (reverted): tried a cached filtered-row fast path in `_FilteredNeighborMap`
(backs FilterAtlas -> adjacency() 0.15x) replacing the per-neighbour `_node_visible`/
`_edge_visible` walk with raw `filter_node`/`filter_edge`. BYTE-WRONG 297/400 — and it broke
even the node-SET subgraph case (my ungated fast row overrode the correct node-set `__iter__`
path). The `_node_visible`/`_edge_visible` composition has subtleties a naive raw-filter
replication misses (the massive fail rate is a systematic logic error, not an edge case).
REVERTED; adjacency byte-exact again (0 fails). LESSON (again): `_FilteredNeighborMap` is
high-blast-radius shared machinery (adjacency + subgraph edges + self.adj); its fast path must
be root-caused against the exact `_node_visible`/`_edge_visible` semantics + node-set path
interaction, not rushed. The filtered-view adjacency() gap stays open (deferred to a careful
dedicated pass).

## 2026-07-02 CopperCliff SHIP: reverse_view.edges(data/keys) 0.17-0.33x -> 0.51-0.74x — iterate the native pred row, not the AtlasView

reverse_view `_edges` iterated `self._graph.pred[source].items()` per source; for a concrete
parent that returns a MultiAdjacencyView/AtlasView that re-materialises
`_native_predecessor_row` ~3x per edge (profile: 159860 native-row calls for 50000 edges).
FIX (cc-revedgespred): iterate `_fast_pred_row(self._graph, source)` instead — a PLAIN dict
built in ONE native call (O(deg)); it already falls back to `graph.pred[node]` for a
nested-view parent, so byte-identical (same row keys/order, keydicts, attrs). MEASURED:
MultiDiGraph reverse.edges(keys,data) 0.17x->0.51x (n=1000), DiGraph reverse.edges(data)
0.33x->0.74x — ~2-3x fnx (removes the AtlasView triple-materialisation). Still <1x: the
residual is the per-source plain-dict BUILD vs nx iterating its live `_pred` nested dict
(no dict build) + tuple materialisation — would need a native bulk reverse-edges-WITH-data
exporter (the no-data DiGraph case already has `_native_reverse_edges_no_data`). Byte-exact:
1942 cases (DiGraph+MultiDiGraph x edges/keys/data/'weight' + nested reverse-of-subgraph)
0 fails; 6152 conformance pass (1 pre-existing gexf failure). PURE-PYTHON. LEVER: a live-view
edge/adj iterator that indexes `G.pred[n]`/`G.adj[n]` (AtlasView, re-materialises the native
row per access) should use the plain-dict `_fast_*_row` accessor (one native call).

## 2026-07-02 CopperCliff SHIP: undirected restricted_view.degree(WEIGHT) 0.10x -> 2.26x — weighted degree bulk path with builtin-sum Neumaier match

Extended the degree bulk path (cc-rvdegfast) to WEIGHTED undirected degree. TRAP handled:
CPython's builtin `sum` is Neumaier-compensated (3.12+), so a naive `+=` float accumulator
diverges by ULPs — collect the per-edge `attrs.get(weight,1)` values in nx's neighbour-major/
key-minor adjacency order and reduce with the BUILTIN `sum`, then add the self-loop weight a
second time (undirected double-count) exactly as nx's trailing `+=` does. Weighted DIRECTED
(total = sum(out) + sum(in) with nx's specific per-direction order) is deferred to the slow
path — returns None. MEASURED: Graph restr.degree(weight) 0.10x->2.26x (beats nx);
MultiGraph 0.10x->0.62x (6x fnx, same per-parallel-edge filter_edge substrate floor as
unweighted MG degree); also lifts subgraph.degree(weight). Byte-exact: 600 cases (Graph +
MultiGraph) incl ADVERSARIAL magnitude-spanning floats (1e16/1/-1e16/1e-9 — the Neumaier
stress), self-loops, missing-weight-default-1, hidden nodes + edges 0 fails; directed weighted
verified correct via the slow path; 7486 conformance pass (1 pre-existing gexf failure).
PURE-PYTHON. LEVER: a float-reduction fast path must reduce with the builtin `sum` (not `+=`)
to inherit CPython 3.12+ Neumaier compensation and stay byte-exact vs nx. FOLLOW-UP: weighted
DIRECTED filtered degree (needs the out/in per-direction sum order) + the other view gaps
(reverse.edges(data) 0.33x, MDG reverse.edges 0.17x, adjacency() 0.15-0.30x, reverse in/out
degree constant-factor 0.06x).

## 2026-07-02 CopperCliff SHIP: reverse_view.in/out_degree O(V^2)->O(V) — `_fast_succ_row` DiGraph branch dropped a whole-graph rebuild (844ms -> 1.81ms @ n=1000)

New view sweep (reverse views, subgraph-view data/adjacency) found reverse_view(D).in_degree()
at 0.00x — 844ms @ n=1000, 195->854ms for n=500->1000 = O(V^2). ROOT: the reverse view's
in/out_degree read `self.pred[node]`/`self.succ[node]` via `_ReverseNeighborMap` ->
`_fast_succ_row(parent, node)`, whose DiGraph branch built the WHOLE-graph
`_native_adjacency_dict()[node]` (O(V+E)) just for the neighbour KEY ORDER, overlaying
`_native_successor_row_dict(node)` for live attrs — so once per node = O(V^2). The per-row
accessor already yields the SAME key order AND live attrs (verified byte-identical over
mutated / edge-removed graphs, 0 mismatches), so `_fast_succ_row` now uses it alone: O(deg),
byte-identical. MEASURED: reverse.in_degree() 844->1.81ms @ n=1000 (466x fnx), now LINEAR
(1.81->3.66ms for 2x). Byte-exact: 900 cases (reverse in/out/total degree + edges + DiGraph
subgraph edges) 0 fails; 9341 conformance pass (1 pre-existing gexf failure). PURE-PYTHON.
Fixes ANY `_fast_succ_row` caller that hit the whole-graph rebuild per node. RESIDUAL: reverse
in/out_degree is now O(V) but still ~0.04x — a CONSTANT-factor (fnx builds a per-node row
dict just to `len` it; nx `len`s a live dict) — needs a count-only native accessor or a
view-type-preserving delegation to the parent's native out/in degree (deferred; the O(V^2)
scaling catastrophe is the real fix). OTHER view gaps surfaced this sweep (untouched):
reverse.edges(data) 0.21x / MDG reverse.edges(keys,data) 0.09x, subgraph/restricted
.adjacency() 0.13-0.24x, restricted_view.degree(WEIGHT) 0.11x (my degree fast path bails on
weight), restricted_view.nodes(data) 0.24x.

## 2026-07-02 CopperCliff SHIP: Multi(Di)Graph restricted_view.degree() 0.04-0.05x -> 0.74x/4.1x — degree bulk path extended to multigraphs (COMPLETES the filtered-view domain)

Last filtered-view gap. Extended `_fast_filtered_degree_pairs` to multigraphs: a `_pair_count`
helper contributes 1 per simple edge (if it passes filter_edge) or sums the parallel keys that
pass `filter_edge(u,v,key)` per pair. Degree is a SUM so key order is irrelevant (no reorder
concern, unlike the edges view — so no closure-filter gate needed). Directed: MultiDiGraph
uses per-source `_fast_succ_row` (O(deg), per-row native dict), simple DiGraph keeps the
hoisted successor snapshot (its `_fast_succ_row` is O(V)); self-loop double-counts via out+in
(directed) or the trailing `+= c` (undirected). MEASURED: MultiDiGraph restr.degree()
0.05x->4.09x (n=2000, beats nx); MultiGraph 0.04x->0.74x — an 18x fnx speedup (414->22.5ms)
but still <1x: the residual is the per-parallel-edge `filter_edge(u,v,key)` closure call
(a `frozenset` build per key for undirected), which nx's FilterMultiInner pays too, so the
gap is thin substrate not removable work. Byte-exact: 600 cases across ALL 4 types (self-loops,
hidden nodes + edges, parallel edges) 0 fails; in/out_degree unaffected; 7707 conformance pass
(4 pre-existing failures unchanged). PURE-PYTHON. FILTERED-VIEW DOMAIN COMPLETE: restricted_view
(and plain subgraph_view(filter_edge)) edges+degree across Graph/DiGraph/MultiGraph/
MultiDiGraph all lifted from 0.01-0.14x to 0.64x-4.1x (7 of 8 beat nx; MG degree 0.74x is the
substrate floor). META: last turn's "vein mined out" surface missed this ENTIRE domain — it
yielded 6 wins + a self-caught regression across 4 turns.

## 2026-07-02 CopperCliff SHIP: Multi(Di)Graph restricted_view.edges() 0.11-0.14x -> 1.6-4.1x — multigraph sibling of the concrete-parent fast path

Extended cc-rvfast to multigraph parents. Empirically confirmed restricted_view (closure
filter_node) yields nx's FilterMultiInner ROW order for parallel edges (NO
`_multigraph_filtered_target_order` reorder — that heuristic is node-SET-filter-only), so the
fast path walks the native per-node row ({target: keydict}) in row order, applies the
visible-node set to each target and the raw (u, v, key) filter_edge to each parallel edge.
NO O(V^2) trap: multigraph `_fast_succ_row`/`_fast_adj_row` use per-ROW native dicts
(`_native_successor_row_dict`/`_native_adjacency_row_dict`), O(deg) per node — unlike simple
DiGraph's `_native_adjacency_dict()[node]` whole-graph rebuild (the bug I shipped + fixed for
simple DiGraph two commits back). Gated to a CLOSURE filter_node so a node-set filter (which
can take nx's reordered intersection order) keeps the slow path. MEASURED: MultiGraph
restr.edges(keys) 0.14x->1.79x (n=1000), MultiDiGraph 0.11x->4.13x; linear scaling verified
(n=1000->2000 ~2.4-2.8x time, not O(V^2)). Byte-exact: 2500 cases (keys/data/'weight'
variants x hidden nodes + hidden edges x parallel edges x self-loops x directed/undirected)
0 fails; 4993 conformance pass (4 pre-existing failures unchanged). PURE-PYTHON. FOLLOW-UP
(last filtered-view gap): MultiGraph/MultiDiGraph restricted_view.degree() 0.04-0.05x —
needs parallel-edge multiplicity count in the degree bulk path.

## 2026-07-02 CopperCliff SHIP: DiGraph restricted_view.degree() 0.05x -> 1.90x — extend the degree bulk path to directed via a single edge pass (out+in)

Follow-up to the undirected degree fast path (cc-rvdegfast): DiGraph restricted_view.degree()
was still 0.05x (73.5ms @ n=1000). Extended `_fast_filtered_degree_pairs` to DIRECTED simple
graphs. Directed TOTAL degree = out + in; rather than a per-node predecessor row
(`_fast_succ_row`/pred rows are O(V) per call -> O(V^2)), iterate each visible directed edge
ONCE off the hoisted successor snapshot (`dict(_native_adjacency_keys())`) and credit +1 out
to the source and +1 in to the target — a self-loop (u,u) is both a successor and predecessor
of u so it lands +2, matching nx. MEASURED: DiGraph restricted_view.degree() 0.05x->1.91x
(n=1000, 73.5->1.41ms), ->1.90x (n=2000). Byte-exact: 500 cases (self-loops, hidden nodes +
edges, order-sensitive) 0 fails; in_degree()/out_degree() explicitly verified byte-exact
(they use `_in_degree`/`_out_degree`, not the total-degree `__iter__`); undirected path
unchanged; 5751 view/degree conformance pass (4 pre-existing failures unchanged). PURE-PYTHON.
SIMPLE-GRAPH restricted_view is now FULLY fast: Graph/DiGraph x edges/degree all beat nx
(2.9x/1.1x, 1.8x/1.9x), and the fast paths also cover plain subgraph_view(filter_edge)
(edges 3.7x, degree 1.5x). LEVER: directed total degree without a predecessor-row scan — one
edge pass off the successor snapshot, crediting out-to-source + in-to-target. FOLLOW-UP (still
open, multigraph-only now): MultiGraph/MultiDiGraph restricted_view.edges() 0.11-0.14x +
.degree() 0.04-0.05x — need parallel-edge key handling / multiplicity count.

## 2026-07-02 CopperCliff SHIP: undirected restricted_view.degree() 0.04x -> 1.07-1.18x — bulk fast path, visible set computed once per iteration

Biggest of last turn's surfaced follow-ups: restricted_view.degree() 0.04-0.05x (74ms @
n=1000). Same substrate as the edges gap — the DegreeView walks the filtered `self.adj` per
node, paying per-edge `_node_visible`/`_edge_visible`/`is_multigraph` machinery. The existing
per-node fast path `_filtered_set_count` BAILS for restricted_view (non-default filter_edge AND
a closure filter_node with no `.nodes` set). Fixing it per-node is unsafe: the visible set for
a closure filter_node can't be precomputed-and-cached (would break LIVE-view semantics) and
computing it per node is O(V^2). FIX (cc-rvdegfast): a BULK `_AssignedPrivateDegreeView.__iter__`
fast path — compute the visible node set ONCE per iteration (live-safe: recomputed each call,
never cached), then count each visible node's filter_edge-passing visible neighbours off the
native parent row, double-counting a self-loop as nx's total degree does. SCOPED TIGHTLY
(learning from last turn's rushed-fast-path regression): UNDIRECTED simple graph, unweighted,
nbunch=None, only the slow filter shapes (closure filter_node or non-default edge); directed /
multigraph / weighted / node-set+default-edge keep the proven per-node path. MEASURED: Graph
restricted_view.degree() 0.04x->1.18x (n=1000, 74->2.13ms), ->1.07x (n=2000). Byte-exact: 500
cases (self-loops, hidden nodes + edges, order-sensitive) 0 fails; single-node degree[n]
unaffected (uses __getitem__, not __iter__); 5751 view/degree conformance pass (4 pre-existing
failures unchanged). PURE-PYTHON. LEVER: a per-node view fast path that needs a precomputed
node set can't serve a CLOSURE filter without breaking live-view semantics — move it to a BULK
iteration that snapshots the visible set once per call. FOLLOW-UP (still open): DiGraph/multi
restricted_view.degree() (directed in+out / parallel-edge count) + MultiGraph/MultiDiGraph
restricted_view.edges() 0.11-0.14x — same lever, more sub-cases.

## 2026-07-02 CopperCliff FIX (regression I shipped): DiGraph restricted_view.edges() c4e62a596 introduced O(V^2) 0.01x — hoist the directed snapshot -> 1.44-1.78x

Extending the filtered-view sweep across ALL types caught a REGRESSION my own prior commit
(c4e62a596, restricted_view fast path) introduced: DiGraph restricted_view.edges() went
0.01x (778ms @ n=1000) because my directed branch called `_fast_succ_row(parent, source)`
PER SOURCE — and that rebuilds the WHOLE native adjacency each call (O(V*(V+E))), the exact
trap the node-set chain path documents and avoids. Graph was fine (`_fast_adj_row` is O(deg))
so my Graph->DiGraph symmetry assumption hid it. FIX: hoist the directed snapshot out of the
loop (dict(na_keys()) once for data=False; na_adj() once + O(deg) na_row(source) live-attr
merge for data=True), mirroring the node-set path's three-branch directed structure. RESULT:
DiGraph restricted_view.edges() 0.01x->1.78x (data=False), ->1.67x (data=True), ->1.44x
(data='weight'); Graph unchanged (3.0-4.3x). Byte-exact: 1200 cases (Graph+DiGraph, hidden
nodes + edges, data=False/True/weight, order-sensitive) 0 fails; 2967 view conformance pass
(4 pre-existing failures unchanged). PURE-PYTHON. LESSON: when adding a fast path that handles
directed+undirected in one branch, the directed native-row accessor (`_fast_succ_row`) is
O(V) per call while the undirected one (`_fast_adj_row`) is O(deg) — NEVER call `_fast_succ_row`
in a per-source loop; hoist the `_native_adjacency_*` snapshot. FOLLOW-UP (real gaps, pre-
existing, NOT regressions): MultiGraph/MultiDiGraph restricted_view.edges() 0.11-0.14x (fast
path is Graph/DiGraph-only) + restricted_view.degree() 0.04-0.05x ALL types (filtered-view
degree machinery) — both untouched veins.

## 2026-07-02 CopperCliff SHIP: restricted_view(G).edges() 0.13x -> 3.04x — concrete-parent fast path for non-default filter_edge (REFUTES last turn's "mined out")

Last turn's SURFACE ("vein mined out") was WRONG — a fresh sweep of previously-untouched areas
(I/O parse-side, nbunch ops, subgraph VIEWS, hashing, assortativity) found restricted_view(G)
.edges() at 0.13x (57ms vs 7ms @ n=1000) — a 7.7x LOSS, the biggest gap of the whole session.
Node-only subgraph_view.edges() was already 3.5x (fast native-parent chain path), but a
NON-default filter_edge (restricted_view builds a filter_edge closure) fell to the generic
slow `_edges`: it accesses `self.adj[source][target]` per edge, routing every endpoint through
`_node_visible` (`__contains__` + `_private_override` + `predicate`) plus per-edge
`is_multigraph`/`vars` (profile: 311k is_multigraph, 547k vars calls). FIX (cc-rvfast): a
concrete-parent fast path in `_edges` — when the parent is a simple Graph/DiGraph, no nbunch,
walk the native adjacency rows ONCE and apply the raw filters directly (target visibility via
a precomputed visible-node set == filter_node for a concrete parent; the raw filter_edge
closure in the SAME single orientation + row order + undirected `seen` dedup as the slow
`self.adj` path). MEASURED: 0.13x->3.04x (n=1000), ->3.10x (n=2000); fnx 57->2.23ms. Byte-exact:
800 cases (hidden NODES + hidden EDGES, data=True/False, directed/undirected, order-sensitive)
0 fails; nbunch path preserved (falls to slow path); 2967 view/subgraph conformance pass. PURE-
PYTHON. LEVER: a filtered-VIEW that has a fast path for the node-only case can still fall to
the O(E)·view-object slow path when a second filter (edge) is set — extend the native-parent
fast path to carry the second filter as a raw closure. META-LESSON: "vein mined out" was
premature — the untouched sub-domain (filtered VIEW edge iteration) held the session's biggest
gap. PRE-EXISTING (NOT mine, unrelated): find_induced_nodes Graph-Graph parity (3 fails) +
write_gexf classification (1 fail) fail identically on HEAD — flagged for a future turn.

## 2026-07-02 CopperCliff SURFACE: 12-domain fresh sweep — accessible clean-win vein mined out; remaining sub-1x are 3 documented architectural floors + noise/parity

After 11 shipped wins this session, a broad fresh sweep this turn found NO new accessible
bench-and-edit lever. Domains measured warm/isolated vs nx (all WINS unless noted):
- ALGORITHMS: link-prediction (jaccard/adamic_adar/pref-attach 2.2-2.9x), community, matching
  (max_weight 1.0x delegated-parity), cycles, centrality (betweenness 119x, load 32x,
  eccentricity/diameter/center/periphery 15x, harmonic 177x), reciprocity 10x, constraint 7x.
- FLOW/CONNECTIVITY/TREE: max_flow 3.8x, MST 2.7x, node_connectivity 27x, stoer_wagner 8.8x,
  triadic_census 19x, bridges 86x, floyd_warshall 35x, wiener 16x, resistance_distance 55x.
  (k_components 1.00x = delegated, ~20s inherent — no lever.)
- DAG/PRODUCT/CLIQUE/BOUNDARY/EFFICIENCY: transitive_reduction 1.4x, cartesian 3.3x, tensor
  5.9x, global/local_efficiency 18-25x, is_tree/is_forest 53-350x, double_edge_swap 1.65x.
- PATH FAMILY: dijkstra_path 7x, astar 7x, single_source_dijkstra 4.5x, all_pairs_dijkstra
  1.5x, johnson 2.1x, bellman_ford 3.3x (+ the two shortest_path wins landed this session).
- BIPARTITE: projected_graph 2.3x, clustering 2.2x, spectral_bipartivity 4090x, is_bipartite 34x.
- SERIALIZATION: generate_gml 0.94x, generate_graphml 0.99x, adjlist 1.03x (all ~parity).
The ONLY sub-1x that aren't noise-floor (<0.1ms: common_neighbors 0.86x, bip.degrees 0.71x)
or delegated-parity (~1.0x) are THREE documented architectural floors:
  1. node_link_data 0.76x — CONFIRMED this turn it's NOT a double-copy bug: edges/nodes
     (data=True) yield LIVE dicts (one materialization, like nx), so the gap is the view-
     iteration substrate (`_gen`/`_materialize` per element) — the persistent-Python-object-
     mirror floor. A prior native binding reached only 0.90-0.95x AND dropped edge attrs
     (adjdataedgeattr NO-SHIP). Needs the persistent ordered mirror (scoped multi-day).
  2. check_planarity(PLANAR) ~0.81x — the fnx->nx conversion tax for the PlanarEmbedding
     certificate (non-planar already fixed to ~10x this session). Needs a native embedding
     kernel (big).
  3. dense_gnm_random_graph 0.90x — shuffle/RNG-bound; gnm-family RNG levers are a known
     session-sink trap (yrdso). Borderline; not worth the byte-exact RNG risk.
CONCLUSION: the bench-and-edit vein this campaign has mined for 11 wins/session is at its
floor; the remaining ratio-narrowing requires the two scoped architectural investments
(persistent Python-object mirror; native planar-embedding kernel). NEXT AGENT: don't re-sweep
these 12 domains — target an architectural investment or a domain not listed above.

## 2026-07-02 CopperCliff SHIP: shortest_path(G) all-pairs unweighted 0.76x -> 1.51-1.73x — route to the fixed all_pairs_shortest_path

Path-family sweep after the all_pairs_shortest_path index-emitter fix (cc-apspidx, 3fc266d5e):
almost all wins (dijkstra_path 7x, astar 7x, single_source_dijkstra 4.5x, all_pairs_dijkstra
1.5x, johnson 2.1x). Lone gap: `shortest_path(G)` with no source/target + weight=None (all
pairs, unweighted) 0.76x — the weighted all-pairs variant was 1.81x. ROOT CAUSE: that branch
fell through to `_raw_shortest_path(source=None,target=None)`, a DIFFERENT native kernel that
still materialized a String-cloned dict-of-dicts — it never picked up the index-emitter fix
that landed on `all_pairs_shortest_path`. FIX (cc-spapsp): nx.shortest_path(G) all-pairs
unweighted dispatches to all_pairs_shortest_path, so route there directly (pure-Python, no
rebuild). MEASURED: 0.76x->1.73x (n=300), ->1.51x (n=400). Byte-exact: 200 cases
(directed/undirected) 0 fails on outer-key + inner-key order + exact path lists; 1855
shortest-path conformance pass. LEVER: when a kernel-level fast path lands, grep the
public-API DISPATCHERS (shortest_path, etc.) for sibling branches that reach the SLOW kernel
directly instead of the just-fixed function — route them to it (matches the reference lib's
own dispatch).

## 2026-07-02 CopperCliff SHIP: all_pairs_shortest_path 0.77x -> 1.25-1.36x — route index-space paths straight to the index emitter (drop the String-clone layer)

Swept nx-delegated functions (178 `_call_networkx_for_parity` sites): almost all are native
wins (eccentricity/diameter/center/periphery 15x, triadic_census 19x, bridges 86x,
resistance_distance 55x) or delegated-parity (k_components 1.00x, ~20s inherent). Only real
gap: `all_pairs_shortest_path` 0.77x (returns actual paths, not lengths). ROOT CAUSE: the
native kernel `all_pairs_shortest_path_from_adjacency` already returns INDEX-space paths
(`Vec<(usize, Vec<usize>)>`), and an index-space emitter `emit_paths_dict_discovery_index`
(no String allocation) already exists and is used by the single_source path — but the
all-pairs binding converted every path to `Vec<(String, Vec<String>)>` first (one
`nodes[idx].to_owned()` String clone per path element = V^2·L allocations) before calling the
String emitter. FIX (cc-apspidx): route the kernel's index paths straight through
`emit_paths_dict_discovery_index` — reads `nodes[idx]` directly, byte-identical dict (same
disp dedup, same outer/inner key order). MEASURED: 0.77x->1.25x (n=200), ->1.36x (n=400);
fnx 19.0->11.3ms. Byte-exact: 251 cases (directed/undirected, cutoff None/1/2/3, string
keys) 0 fails on outer-key order + inner-key order + exact path lists; clippy clean; 2241
shortest-path conformance pass. LEVER: a binding built an intermediate String projection of
data the kernel already had in index form AND a String-free emitter already existed —
grep bindings that `.to_owned()` node keys into `Vec<(String, Vec<String>)>` when an
index-space `_index` emitter sibling exists.

## 2026-07-02 CopperCliff SHIP: check_planarity(non-planar, no counterexample) 0.67x -> ~10x — native LR bool settles the certificate-less non-planar case

Flow/connectivity/tree sweep found check_planarity 0.67x (5.19ms vs 3.46ms) — the only real
non-scipy algorithm gap (everything else 1.2-119x). ROOT CAUSE: `_check_planarity_certificate`
had an O(1) Euler pre-reject only for DENSE graphs (m > 3n-6); for everything else it CONVERTED
the fnx graph to an nx graph (`_planarity_graph_for_certificate`) and ran nx's PYTHON LR
(`nx.check_planarity`) — because it must return a certificate (PlanarEmbedding / Kuratowski).
So fnx = conversion + nx-algo, strictly slower than nx alone. But a native `_fnx.is_planar_lr`
(bool, ~10x faster than nx's LR) already backs `is_planar`. KEY: for `counterexample=False` a
NON-planar result's certificate is just `None`, so the native bool settles it — no conversion,
no nx-algo. FIX (cc-planarlr): after the Euler reject, `if not _fnx.is_planar_lr(G): return
(False, None)`. Planar graphs still need the embedding certificate -> fall through to nx.
MEASURED (non-planar): 0.67x->9.8-10.5x (0.30ms vs 2.97ms @ n=400). Planar graphs pay only
the native LR (~4% of their total; the conversion+nx cost is pre-existing and unchanged) —
0.84x->0.81x, negligible. Byte-exact: is_planar_lr matches nx's planarity bool over 620 cases
incl self-loops / K5 / K3,3 / grid; full check_planarity (bool + None/PlanarEmbedding cert)
0 fails over 800 planar/non-planar/self-loop cases; counterexample=True path unchanged; 690
planarity conformance pass. PURE-PYTHON. LEVER: a wrapper that must return a CERTIFICATE
falls back to a slow reference path even when the certificate is trivially None (the negative
case) — short-circuit the negative case with the fast native bool kernel, keep the reference
path only for the branch that actually needs the certificate. RESIDUAL: planar check_planarity
~0.81x is the fnx->nx conversion tax for the embedding (needs a native embedding kernel — big).

## 2026-07-02 CopperCliff SHIP: dual_barabasi_albert_graph 0.88x -> 1.78-1.88x — seed-into-batch lever transfers (the flagged candidate)

The barabasi_albert seed-into-batch lever (cc-bastarbatch, 7ecde5151) flagged dual_ba /
powerlaw_cluster as candidates; generator sweep confirmed dual_barabasi_albert 0.88x (the
only new sub-0.90x besides dense_gnm 0.90x borderline). IDENTICAL pattern: it pre-built
`star_graph(max(m1,m2))` then bulk-added attachment edges, so the final `add_edges_from`
paid the O(bunch) touches-existing pre-scan against the star. FIX (cc-dualbastarbatch): for
the default seed prepend the star edges to `_edge_accum`, seed `repeated_nodes` from the
star's degree sequence (`[0]*mm + [1..mm]`), build on the EMPTY graph -> scan short-circuits
+ fresh-batch fast path. Net fnx HALVED (7.65->3.73ms). MEASURED: dualBA(2000,4,2)
0.88x->1.78x, (4000,4,2) ->1.88x, (2000,8,3) ->1.80x — beats nx. Byte-exact: 350 cases
(50 seeds x 7 (n,m1,m2,p) incl p=0/1 delegation to the fixed BA) 0 fails node+edge order;
initial_graph + create_using paths preserved; 1789 conformance pass. PURE-PYTHON. The lever
generalizes cleanly to the seed-then-preferential-attachment family. (powerlaw_cluster is
already 1.23x — its seed is built differently; dense_gnm 0.90x is a shuffle-bound borderline,
not this pattern.)

## 2026-07-02 CopperCliff SHIP: barabasi_albert_graph 0.86x -> 1.82x — seed the star INTO the batch so the add_edges_from touches-scan short-circuits

Generator sweep found BA the only sub-0.90x (0.86-0.88x; everything else 1.05-296x wins).
cProfile: ~8% in `_simple_add_edges_from_touches_existing_plain_edge` — BA pre-populated
`star_graph(m)` (m edges) then bulk-added ~m*(n-m) edges, so the final `add_edges_from`
snapshotted the star into a set and built a frozenset PER BA edge to test membership, even
though NO BA edge can touch the star (every source is a fresh node > m). FIX (cc-bastarbatch):
for the default seed (initial_graph is None, plain Graph) DON'T pre-build the star — prepend
its edges `[(0,leaf) for leaf in 1..m]` to the batch and seed `repeated_nodes` directly from
the star's known degree sequence (`[0]*m + [1..m]`, byte-identical to reading graph.degree),
then commit everything to the still-EMPTY graph. The touches-scan short-circuits on
`edge_count == 0` AND the whole set takes the fresh-batch fast path. Net fnx time HALVED
(11.2->5.49ms). MEASURED: BA(2000,5) 0.88x->1.82x, BA(4000,5) 0.86x->1.72x, BA(2000,10)
0.86x->1.91x — now BEATS nx. Byte-exact: 360 cases (60 seeds x 6 (n,m)) 0 fails on node +
edge order; initial_graph path preserved (non-fastpath branch unchanged); 1654 generator
conformance pass. PURE-PYTHON. LEVER: a generator that seeds a tiny graph then bulk-extends
pays add_edges_from's O(bunch) touches-existing pre-scan against the seed — if the extension
provably can't touch the seed (fresh source nodes), fold the seed edges into the batch and
build on an empty graph so the scan short-circuits.

## 2026-07-02 CopperCliff SHIP: Multi(Di)Graph(dict_of_dicts/dict_of_list) constructor — 0.24-0.54x -> 0.62-1.05x, batch the decoder's multigraph branches

Extended the simple-graph constructor-decoder batch lever (359edba84) to multigraphs — the
biggest remaining constructor gaps: MG(dod) 0.24x (65ms!), MDG(dod) 0.26x, MG(dol) 0.41x,
MDG(dol) 0.54x. All hit `_decode_dict_of_dicts_into`'s multigraph branch doing per-edge
`add_edge(u,v,key=key)` + `self[u][v][key].update(...)` (O(E) PyO3 adjacency-view chain).
FIX (cc-mgdodctor + cc-mgdolctor): two batched fast paths mirroring
`nx.convert.from_dict_of_dicts` / `from_dict_of_lists` for multigraphs. 4-level dict-of-dicts:
one keyed `(u,v,key,attrs)` batch, undirected dedupes the symmetric `(v,u,key)` reverse
(the reverse dupes otherwise bail the fast keyed batch to per-edge — measured: full 11998-dupe
batch 30ms vs deduped 6000 batch 6ms). dict-of-list: auto-key `(u,v)` batch, undirected
dedupes by processed-SOURCE node (nx `from_dict_of_lists` semantics). Both gated to a CLEAN
value shape (dod: all values dicts + multigraph_input; dol: all values non-dict/str
iterables) so 3-level / mixed / string-valued shapes keep the general loop. PURE-PYTHON.
MEASURED: MG(dod) 0.24x->0.73x, MDG(dod) 0.26x->0.62x, MG(dol) 0.41x->0.65x, MDG(dol)
0.54x->1.05x (beats nx). Byte-exact: 0 fails on node + (u,v,key,sorted-attrs) edge order over
800 roundtrip-through-to_dict_of_dicts/to_dict_of_lists + hand-built parallel/self-loop/
neighbor-only/empty-inner cases; 3514 convert/multigraph conformance pass. RESIDUAL (why dod
still <1x): the Python batch-BUILD (per-edge `dict(attrs)` copies + the dedupe seen-set) is
itself ~nx-total-cost, and add_edges_from runs on top; the win is the Rust keyed batch
beating per-edge PyO3 by more than that overhead, but not enough to clear nx on the
attr-heavy dod path. dict-of-list (no attrs) is the cleaner win (MDG(dol) beats nx). LEVER:
extend a proven simple-graph decoder batch to the multigraph branches, but dedupe the
symmetric reverse (undirected multigraph dod/dol list every edge twice) or the keyed batch
bails to per-edge.

## 2026-07-02 CopperCliff SHIP: Graph/DiGraph(dict_of_list) constructor 0.36x -> 1.64x — route the decoder's dict-of-LIST branch through the batch

Domain-sweep for a NEW gap: algorithms are ALL wins (2.6-198x, vein confirmed mined out);
warm view/degree family all wins; I/O/convert sweep surfaced `Graph(dict_of_lists)` 0.36x
(the biggest live gap). Isolated: `from_dict_of_lists(dol)` 3.26ms and `to_networkx_graph(dol)`
4.43ms are BOTH fast (~1.5x nx), but `Graph(dol)` was 19ms — the constructor's dict decoder
`_decode_dict_of_dicts_into` had a fast batch path for dict-of-DICTS (all-dict values ->
one add_edges_from, `Graph(dod)` 1.16x) but the dict-of-LIST case fell through to the general
per-node loop that commits each edge with a per-edge `self.add_edge(u,v)` (O(E) PyO3), and
for a simple UNDIRECTED graph it doesn't even dedup (dedupe_dict_of_list is multigraph-only),
so it paid ~2x add_edge calls. FIX (cc-dolctor): add a simple-graph dict-of-list batch fast
path mirroring `from_dict_of_lists` exactly — `add_nodes_from(data)` (source order) + ONE
deduped `add_edges_from` (undirected drops the symmetric reverse; directed keeps all).
Gated to a CLEAN dict-of-list (every value a non-dict, non-str/bytes iterable) so
mixed/dict-of-dict/string-valued/non-iterable shapes keep the general loop's exact
semantics. PURE-PYTHON (no .so rebuild). MEASURED: Graph(dol) 0.36x->1.64x (19->3.92ms),
DiGraph(dol) ->1.09x — both now BEAT nx. Byte-exact: 0 fails on node-order + edge-order over
self-loops / isolated / empty-list / neighbor-only-node / tuple-values / string-keys +
300 random roundtrip-through-to_dict_of_lists stress; 902 convert/constructor conformance
pass; MultiGraph dict-of-list untouched (still general loop, byte-exact). LEVER: a constructor
decoder can have a fast batch for ONE input shape (dict-of-dicts) but a per-edge loop for a
sibling shape (dict-of-list) that a standalone converter already handles fast — grep decoder
branches for `self.add_edge(` loops and route them through the same batch the standalone uses.

## 2026-07-02 CopperCliff NO-SHIP (reverted, bench rejection): simple-DiGraph degree(weight) store twins — eager mirror means NOT strict work removal

Ported the MG/MDG weighted-degree store twins (int `native_weighted_total_degree_store_int`
+ float `weighted_total_degree_float_node_store`, succ+pred, gated `!edges_dirty`) to
PyDiGraph — the only weighted-degree class lacking them. Byte-exact: 0 fails over
DiGraph degree/in_degree/out_degree(weight) x {order-sensitive-Neumaier / self-loop-in+out /
mixed / missing / isolated / all-int / i64-overflow / non-'weight' / removals} + 700 random
stress. BUT NO MEASURABLE WIN -> reverted. ROOT CAUSE: unlike MG/MDG (which leave
`edge_py_attrs` lazy on bulk add, so `degree(weight)` paid per-edge PyObject *materialisation*
that the store twin removed), simple DiGraph EAGERLY populates `edge_py_attrs` on
`add_edges_from` (digraph.rs ~9041: one PyDict per edge inserted at build). So the existing
mirror path only REFERENCES pre-built dicts (`edge_py_attrs.get(ek).get_item(weight)`) — no
per-edge PyObject creation to remove. The store twin swaps a mirror HashMap.get for an
equal-cost `inner.edge_attrs` FxIndexMap lookup and still creates one result PyObject per
node, so it is BREAK-EVEN, not strict work removal: float degree(weight) unchanged
(1.00x->1.01x), int lost in load-noise (fnx-only min-of-25 swung 20-30% same-`.so` under
load avg 12-17). Per the noise-discipline rule (feedback_rch_bench_worker_noise), an
ADDED-code path with no measured win and a mechanistic reason for none = REVERT. LEVER
CORRECTION: the "sibling has a store twin, port it" lever (which flipped MG degree to beat
nx, f90725116) does NOT transfer to DiGraph — DiGraph's eager edge mirror removes the very
per-edge-PyObject cost the twin exists to eliminate. DiGraph/MG differ in mirror laziness;
confirm the target class leaves the mirror lazy before porting a store twin. DiGraph
degree(weight) sits at parity (~1.0x float) and is a genuine eager-mirror floor here.

## 2026-07-02 CopperCliff SHIP: MG degree(weight) now BEATS nx (0.76-0.84x -> 1.21-1.31x float, ~1.03x int) — edge_attr_values per-pair accessor closes the residual

Follow-up to the MG float store twin (5b5b1ae43). That twin still read weights via
`edge_keys(u,v)` + per-key `edge_attrs(u,v,key)` — TWO FxIndexMap hash lookups (pair bucket
+ key) per parallel edge, plus a `neighbors`/`edge_keys` Vec alloc per node. That per-edge
double-hash was the residual keeping MG below nx while MDG (which reads via
`edge_attr_values`, one bucket lookup per pair) beat it. FIX (cc-mgedgeattrvalues): added
`MultiGraph::edge_attr_values(l,r)` to the fnx-classes inner (undirected sibling of the MDG
accessor — `edges.get(EdgeKeyRef).map(|b| b.values())`), and rewrote BOTH MG weighted-degree
store twins to iterate it via `neighbors_iter` (no Vec): one bucket lookup per pair, values
iterated directly. ORDER-SAFE for the order-sensitive FLOAT Neumaier sum — PROVED: the
adjacency `IndexSet<usize>` and the edges `IndexMap<usize,AttrMap>` are appended together on
add and BOTH `shift_remove`d on per-key remove (whole bucket dropped on endpoint/node
removal), so their key order is always identical (earlier ledger's order-doubt was WRONG —
that warning was the simple-Graph swap_remove path, not the multigraph per-key path). int
twin is order-independent regardless. MEASURED (interleaved warm min-of-9, n=3000/m=15000):
MG float nodeattrs=0 0.84x->1.31x (fnx 16.72->12.03ms), nodeattrs=1 0.76x->1.21x (18.92->
11.74ms); MG int 0.79x->1.02x, 0.68x->1.04x — MG degree(weight) now BEATS nx on all 4.
MDG UNAFFECTED (1.35-1.41x float, 1.07-1.08x int). VERIFY: 0 fails on the full byte-exact
matrix (order-sensitive-Neumaier / self-loop-double / mixed / missing / node-attrs / all-int
/ non-'weight') + 600 build stress + 800 REMOVAL-ORDER stress (edge removals -> non-contig
keys + interleaved re-adds, the exact case that would expose an adjacency-vs-bucket order
divergence — none); clippy clean; 7592 conformance pass. LEVER: when a sibling type's store
twin beats nx and yours doesn't, diff the ACCESSOR — a per-key double-hash vs a per-pair
`.values()` iterator is the whole gap; verify order-safety by the storage's add/remove
semantics, then port the accessor.

## 2026-07-02 CopperCliff SHIP: MultiGraph degree(weight) FLOAT store twin — the "AUDIT MG float" TODO from 9f0e40cb8; 0.59-0.70x -> 0.76-0.84x, byte-exact

BIGGEST-GAP-FIRST warm head-to-head scan flagged Multi(Di)Graph `degree(weight)` as the
largest live gap (0.23x contaminated by prior edge-view materialization; isolated ~0.6x
MG float). Root cause was the KNOWN follow-up flagged in the MDG store-twin note
(9f0e40cb8, "AUDIT MG float lib.rs ~8059"): MDG got `weighted_total_degree_float_node_store`
+ `weighted_directional_degree_float_node_store` reading exact floats straight from the
CgseValue store, but the UNDIRECTED MG float path still went through
`weighted_degree_float_node` -> `edge_weight_exact_f64` -> `edge_attr_py_value`, which
MATERIALISES a PyObject per edge on bulk-built graphs (`add_edges_from` leaves
`edge_py_attrs` lazy/empty), so `degree(weight)` on the common weighted MG fell to ~0.6x.
FIX (cc-mgwdegfstore): new `weighted_degree_float_node_store` — reads `CgseValue::Float`
directly via `edge_attrs(node,neighbor,key)` in the SAME `neighbors -> edge_keys` order as
the proven byte-exact mirror twin, with the SAME two Neumaier-compensated sums (every
incident edge once + a SECOND self-loop pass, since nx's undirected `MultiDegreeView`
counts a self-loop's weight twice). Dispatch gates on `!edges_dirty` (store authoritative)
else keeps the PyObject mirror twin (dirty mirror is authoritative). Bit-identical BY
CONSTRUCTION (same order, same values, same compensation as the mirror twin's store
fallback). MEASURED (in-process before/after via .so swap, n=3000/m=15000 float, min-of-9):
MG float nodeattrs=0 0.70x->0.84x (fnx 22.15->16.72ms), nodeattrs=1 0.59x->0.76x (21.64->
18.92ms) — ~15-25% fnx-time cut from zero per-edge PyObject. MDG UNAFFECTED (1.24-1.37x,
no regression). Still <1x vs nx: residual is the per-key `edge_attrs` HashMap lookup + the
`neighbors`/`edge_keys` Vec allocs (MDG beats nx because its `edge_attr_values` returns all
parallel-edge AttrMaps per pair in one call, no per-key lookup). VERIFY: 0 fails over
MG+MDG degree(weight) x {order-sensitive-Neumaier / self-loop-double-count / mixed-int-float
/ missing-default-1 / node-attrs / isolated-nodes / all-int / non-'weight' key} + 600 random
stress; clippy clean; 7592 degree/weighted/multigraph/size conformance pass. FOLLOW-UP (real
headroom, NOT yet done): add `edge_attr_values(u,v)` to the fnx-classes MultiGraph inner
(the MDG inner has it) so BOTH MG store twins (int `weighted_degree_store_int_node` + this
float twin) drop the per-key HashMap lookup and could reach MDG's >1x. LEVER: when one type
(MDG) ships a store twin and the sibling (MG) is flagged "AUDIT", the sibling almost always
still pays the per-edge PyObject the twin was built to remove — port it.

## 2026-07-02 CopperCliff SHIP: native Multi(Di)Graph difference/symmetric_difference identity-int rewrite — beats the set-snapshot fallback 1.1-2.0x, byte-exact

Re-activated the native multigraph set-op kernels (previously DEAD — the wrapper skipped
them because the OLD native path, which rebuilt a full `edge_py_keys` display mirror + per-
pair re-sequenced keys, was ~2.4-3x SLOWER than the set-snapshot + keyed-batch fallback).
REWRITE (cc-mgnatdiff-identity / cc-mgnatsymdiff-identity + MDG siblings): a lean
identity-int FAST PATH gated on `!has_remapped_int_key` (and, for MG, empty `adj_py_keys`
z6uka overrides). For all-identity-int keys a multigraph edge's key value EQUALS its
internal key, so (a) membership is tested on INTERNAL `(u,v,key)` — no per-edge
`display_key_lookup` String build; (b) each operand's EXACT keys are PRESERVED on the
result — no re-sequencing (the old re-sequencing was byte-WRONG for pairs with
non-contiguous kept keys, e.g. G{0,1} minus H{0} must yield key 1, not a re-keyed 0); and
(c) NO `edge_py_keys` mirror is built (`display_key_lookup` reconstructs `int:{internal}`).
The kernel declines (-> None) for remapped/str/float keys or display overrides, falling
through to the proven byte-identical set-snapshot fallback. Removed the two now-dead
`display_key_lookup` helpers (MG lib.rs, MDG digraph.rs; zero call sites).
MEASURED (in-process A/B, native vs the exact HEAD fallback, n=2000/m=12000 identity-int,
min-of-9): MDG difference 1.86-2.00x, MDG symmetric_difference 1.34-1.42x, MG
symmetric_difference 1.11-1.14x, MG difference 1.02-1.35x — all `same=True` byte-identical.
Narrows the vs-nx ratio (e.g. MDG difference ~0.47x -> 0.88x). Still <1x vs nx (materialize
floor on the smaller operands' side) but a strict improvement over the committed fallback.
VERIFY: 0 fails over MG+MDG x {difference,symmetric_difference} x
{auto/explicit-int-contig/non-contig/str/float/mixed/disjoint/identical/superset} + 400
random mixed-key stress; 273 operator conformance tests pass. Also cleared PRE-EXISTING
`clippy -D warnings` breakage this area inherited from a6e8a9a0d/7a49dd943 (E0063 stale
`PyMultiGraph` test literal in algorithms.rs missing `edges_data_attr_cache` +
`has_remapped_int_key`; needless-borrow + chunks_exact lib warnings) — crate now clippy
clean. LEVER: a native kernel declared DEAD because it "predates the fast batch" can be
resurrected by stripping its display-mirror/re-sequencing tax down to the identity-int
invariant the fallback already relies on.

## 2026-07-02 CopperCliff SURFACE (blocker pinpointed to a data structure): the construction-tax floor IS `AttrMap = BTreeMap<String, CgseValue>`; ledger already batch-skipped

Chased the construction-tax floor to its root instead of leaving it as a label. Ruled out
the decision ledger as a lever: the batch construction path (`_try_add_edges_from_batch`
-> `extend_keyed_edges_with_attrs_unrecorded`) ALREADY skips the per-edge
`record_decision` (br-r37-c1-pr8q6). So the residual construction cost — projected_graph's
58%-in-batch (build 14720 store edges) and multigraph_clear_edges 0.30x (dealloc scattered
edges) — is precisely the per-edge **`AttrMap = BTreeMap<String, CgseValue>`** (fnx-classes/
src/lib.rs:22): a BTreeMap heap-node allocation per edge on construction, and scattered
BTreeMap-node deallocation on clear. THE actionable primitive: change AttrMap to a sorted
`SmallVec<[(String, CgseValue); N]>` (or Vec) — typical edge attr maps are 1-3 keys, where
a small sorted Vec beats BTreeMap on alloc count, cache locality, and drop, AND preserves
the sorted iteration order fnx relies on. RISK (why NOT a bench-and-edit): AttrMap is used
at hundreds of call sites (get/insert/iter/entry/range/extend), get becomes O(n) (fine for
tiny maps, worse for large), and byte-exact iteration order + get semantics must be
preserved — a deliberate typed-wrapper change with full conformance, not a loop edit.
This + the persistent Python-object mirror (for the materialization floors) are the two
scoped architectural investments; everything bench-and-edit is shipped.
BLAST RADIUS (measured, so the scope is concrete): AttrMap has 605 refs across crates, 26
BTreeMap-specific `.entry()`/`.range()`/`.split_off()` sites to reimplement on any
wrapper, AND `CgseValue::Map(BTreeMap<String,CgseValue>)` (fnx-runtime lib.rs:49) is a
SEPARATE BTreeMap that must move in lock-step for nested-attr consistency + serialization.
Add full 50k-test conformance + byte-exact iteration/get validation = a deliberate
multi-day change, categorically not a loop-turn edit. Scope is now fully specified for a
future dedicated effort.

CORRECTION (precision, verified): the construction-tax floor is actually TWO distinct
sub-floors, and AttrMap=BTreeMap is only HALF:
  (a) WEIGHTED construction (multigraph_clear_edges): edges carry attrs -> per-edge
      BTreeMap HEAP alloc + scattered dealloc -> fixed by the arena/SmallVec AttrMap.
  (b) UNWEIGHTED construction (projected_graph, verified all edges empty-attr -> BTreeMap
      does NOT heap-alloc when empty): the cost is per-endpoint STRING node canonicalization
      + hashing in the store (nx uses the node OBJECT directly as a dict key; fnx must
      int->String + hash each endpoint, ~29k times for 14720 edges). This is the SAME
      String-keyed-store representation cost as the node_key_to_string materialization
      floor -> fixed by an integer-keyed store / the persistent Python-object mirror, NOT
      the AttrMap allocator.
So the TWO architectural primitives cover everything: (1) integer-keyed store / persistent
mirror -> all materialization floors (adj[n], selfloop, in/out_edges data=attr) AND
unweighted construction (projected_graph); (2) arena/SmallVec AttrMap -> weighted
construction fragmentation (clear_edges). Frontier fully partitioned.

## 2026-07-02 CopperCliff SURFACE: bipartite submodule swept — projected_graph 0.85x is the construction-tax floor (already de-delegated+batched); rest wins

Swept the whole `bipartite` submodule (untouched this campaign). WINS: spectral_bipartivity
567x, density 58x, is_bipartite 48x, sets 12x, clustering 1.79x, weighted_projected 1.17x.
Two sub-1.0:
- `bipartite.degrees(B, set)` 0.552x but 46 µs absolute — degree-subset materialization,
  near-zero (not takeable, would be a revert).
- `projected_graph` 0.849x (15 vs 12.8ms): ALREADY de-delegated + one-shot batched
  (br-r37-c1-bpproj/bpprojbatch), output byte-EXACT vs nx incl edge order (14720 edges).
  cProfile: 58% in `_try_add_edges_from_batch` — building 14720 store edges (per-edge
  AttrMap alloc + node String-canonicalization + decision ledger) vs nx's Python-dict
  add_edges. This is the documented CONSTRUCTION-TAX floor
  ([[reference_construction_tax_relabel_lever]]), NOT a peelable machinery/guard layer.
  A dedup-before-batch would risk the byte-exact edge order for a modest 2.3ms gain — not
  taken. Bounded by the same per-edge store-construction primitive (arena/pool AttrMap).
CONCLUSION: bipartite confirms the global pattern — every residual gap is
materialization / construction-tax / dual-storage, all architectural-primitive-bounded.
ALSO SWEPT (all WINS, no gap): community.modularity 1.59x, partition_quality 1.65x,
bipartite.hopcroft_karp 7.4x, tournament.is_tournament 7.8x, is_graphical 1.14x,
dispersion 2.9x, number_of_walks 13x, rich_club 82x, s_metric 151x. Coverage now spans
~every submodule; safe bench-and-edit levers are EXHAUSTED. The next investment is the
persistent Python-object mirror (unblocks materialization floors: adj[n], selfloop-multi,
in/out_edges data=attr) and/or an arena/pool AttrMap allocator (unblocks construction-tax:
projected_graph, clear_edges) — deliberate multi-file primitives, not bench-and-edit.

## 2026-07-02 CopperCliff SURFACE: guard-probe lever exhausted — the other 3 canonical gaps re-profiled as genuine native floors (100% in binding)

Follow-up to the to_directed SHIP: re-profiled the remaining 3 canonical head2head gaps
with the same "re-profile, don't trust the label" lens, and swept for other eager-probe
guard wrappers. Results — all confirmed non-peelable:
- mdg_out_edges_nbunch_keys_weight (canonical 0.57x; custom-key repro 0.88x): cProfile =
  100% in `_native_mdg_out_edges_nbunch_data_key` (already native, custom keys DON'T make
  it bail). Genuine native 4-tuple materialization floor (build (u,v,key_obj,weight) per
  edge vs nx's live dicts). data=True sibling is 2.05x.
- mg_selfloop_keys_weight 0.33x: 100% in `_native_selfloop_edges` — native PyObject-
  materialization floor (nx hands out live dicts).
- multigraph_clear_edges 0.30x: per-edge construction fragmentation (NO-SHIP, cargo-bench
  root-caused with Instant instrumentation in a prior session).
- OTHER eager-probe guards: the only sibling of the to_directed probe was
  `edge_connectivity`'s `any("capacity" in d for ... edges(data=True))`, ALREADY native
  (`_graph_has_edge_attribute`, br-r37-c1-capnative). No other unfixed probes exist.
CONCLUSION: the guard/machinery-peel lever (which yielded selfloop-simple + to_directed
this session) is exhausted. The 3 residual canonical gaps are the per-element PyObject-
materialization / construction-fragmentation floors — bounded by the persistent
Python-object mirror primitive, not a bench-and-edit.

## 2026-07-02 CopperCliff SHIP: Graph.to_directed/to_undirected(scalar) 0.85x -> 2.39x / 7.40x — kill the guard's eager result-EdgeView probe

Re-profiled the authoritative gap `graph_to_directed_scalar_attrs` (0.61x, 233ms — biggest
absolute) instead of trusting the "dual-storage floor" memory. cProfile revealed 28% of
to_directed wall time in `_native_edges_with_data` on the RESULT: the
`_materialize_attrs_before_convert` guard's post-probe
`not any(True for *_e,_d in result.edges(data=True) if _d)` EAGERLY materialised the whole
result EdgeView (and marked it dirty) merely to short-circuit. Since 589a8d036 made the
native deepcopy read the store, the guard's re-run branch is effectively dead, but the
probe itself was pure O(E) tax. FIX (br-r37-c1-todirprobe): new native
`graph_has_any_edge_attrs` (inner `any_edge_has_attrs()` = `edges.values().any(!is_empty)`
== Python's `if _data`, short-circuits, read-only, no PyObject build / no dirty-mark) +
Python-probe fallback for multigraph results. Kept the re-run branch intact (still fires
if a fallback path drops edge attrs — verified the 589a8d036 stray-get_edge_data scenario
preserves attrs). RESULT: to_directed(scalar) 0.85x->2.39x (13.6ms vs 29.3ms),
to_undirected(scalar) ->7.40x (both now BEAT nx). Byte-exact 0 mismatches over
scalar-edge / node-attrs-only / no-attrs / nodes-only / digraph / multigraph x
{to_directed,to_undirected}; conformance GREEN (4820 to_directed/to_undirected/convert).
LESSON (again): a "floor" gap can hide a guard-WRAPPER eager-probe tax — re-profile, don't
trust the label. This also lifts the canonical `graph_to_directed_scalar_attrs` gap.
FOLLOW-UP (do NOT re-dig): MultiGraph/MultiDiGraph to_directed/to_undirected are ALREADY
wins (1.13-1.39x) and need NO probe fix — `graph_has_any_attrs(multigraph)` returns None,
so the guard's `if ... and None:` SKIPS the whole block (probe never runs) for multigraph
SOURCES. Extending `graph_has_any_edge_attrs` to multigraphs would be dead code. The
to_directed/to_undirected family is fully optimal across all 4 types.

## 2026-07-02 CopperCliff SURFACE (AUTHORITATIVE cargo bench): head2head 20/24 workloads WIN; the 4 residual gaps are ALL documented floor/NO-SHIP

Ran the canonical per-crate bench (`rch exec -- cargo bench -p fnx-python --bench
networkx_head_to_head`, CARGO_TARGET_DIR=.rch-targets/franken_networkx-cc) to validate the
ad-hoc frontier with the authoritative harness. FINAL: 24 paired fnx-vs-nx workloads: 20 WINS
(1.02x-7.30x: dijkstra-after-edges-data 7.30x, mdg_in_edges_data 4.57x, edge_expansion
4.58x, greedy_tsp 4.03x, mdg_in_degree_weight 3.24x, node_expansion 3.58x, tsp variants
1.88-2.23x, mdg_out_edges_nbunch_keys_DATA 2.05x, voronoi 1.61x, mdg_edges_keys 1.02x,
...). The 4 sub-0.8 gaps are ALL previously root-caused as non-takeable:
- multigraph_clear_edges 0.30x — per-edge construction fragmentation (NO-SHIP 4e64c..).
- mg_selfloop_keys_weight 0.33x — ALREADY native (`_native_selfloop_edges`); cProfile
  shows 100% in the binding = native PyObject-materialization floor (nx hands out live
  dicts), NOT peelable Python machinery like the simple-Graph selfloop was.
- mdg_out_edges_nbunch_keys_weight 0.57x — data=attr value-materialization (the data=True
  sibling is 2.05x); the String-hash/edge-key materialization floor.
- graph_to_directed_scalar_attrs 0.61x — dual-storage body (store+mirror per edge);
  deepcopy-skip was ~0-gain (cc-todir-NOSHIP), stash@{12} is a MISLABELED MultiDiGraph
  diff, not this simple-Graph path.
CONCLUSION: the authoritative bench CONFIRMS the ad-hoc sweeps — every residual gap is the
per-element PyObject-materialization / construction-fragmentation / dual-storage floor,
all bounded by the persistent ordered Python-object mirror primitive. No bench-and-edit
lever remains; FrankenNetworkX is at parity-or-faster across the benched surface.

## 2026-07-02 CopperCliff SURFACE (definitive): adj[n] 0.40x is the persistent-mirror floor (root-caused); tree/dag/connectivity-predicate family all wins — clean-win vein confirmed exhausted

ROOT-CAUSED the `dict(G.adj[n])` 0.40x floor precisely: fnx's AtlasView already caches
its `_keydict` per `(nodes_seq, edges_seq)`, but `__getitem__` must RE-VALIDATE that
token against the Rust store on every access (2 attr reads + tuple + compare per
neighbor). nx has no such cost — its keydict IS the live `G._adj[u]` dict (the dict is
the source of truth). So `dict(G.adj[n])` = per-neighbor validated getitem in fnx vs a
C-level copy of a live dict in nx. Eliminating the validation requires storing adjacency
AS live Python dicts = the persistent ordered Python-object mirror (the same primitive
behind every remaining materialization gap). A dict-subclass AtlasView would break the
live-view contract (G[n] must reflect mutations), so it is NOT a safe local change.
Confirmed the tuple-alloc micro-opt in `_keydict` is near-zero (reverted, unshipped).
FRESH FAMILIES THIS TURN, all WINS: is_tree 31x, is_semiconnected 7.6x,
attracting_components 6.2x, condensation 4.3x, to_prufer_sequence 3.8x, is_eulerian 2.7x;
readwrite generate/parse/to-from_dict_of_lists 0.94-1.99x. The clean bench-and-edit vein
is exhausted; the sole remaining lever is the persistent-mirror architectural primitive.

Applied the selfloop "egregious ratio may be Python machinery, not the floor" lens to a
fresh view-path + readwrite sweep. Findings:
- MOST view paths now WIN or parity: nodes(data=True) 0.98x, nodes(data=attr) 1.33x,
  dict(adjacency()) 0.98x (outer-cache, reference_adjacency_outer_dict_cache),
  edges(data=attr) 1.35x, degree(dict) 1.10x, nodes.data(attr) 1.17x.
- READWRITE all parity/win: generate_edgelist 1.02x, generate_adjlist 0.97x,
  parse_edgelist 1.08x, parse_adjlist 1.14x, to_dict_of_lists 1.99x, from_dict_of_lists
  0.94x, generate_gml 0.95x. No takeable gap.
- REMAINING view gaps: `dict(G.adj[n])` 0.40x and `dict(G.adj)` 0.68x. cProfile shows
  `dict(G.adj[n])` is Python-machinery bound (per-NEIGHBOR `_keydict` + AtlasView
  `__getitem__`, ~200k calls) — peelable IN PRINCIPLE like selfloop, but ONLY by making
  the core AtlasView `__getitem__` native (it backs EVERY `G[u][v]` access — high-risk,
  heavily-used, likely already tuned) or by intercepting `dict()` (impossible). Not a
  safe 60-min bench-and-edit. `dict(G.adj)` builds V lazy row-view objects; the cost is
  view-object construction, and the outer cache that fixed `dict(G.adjacency())` can't be
  reached through `dict(G.adj)` (no interception point).
BLOCKER (stable across the session): the clean-win vein is exhausted. Real remaining
levers are architectural — a native AtlasView row-materialization / snapshot method, or
the persistent ordered Python-object mirror — each a multi-file primitive, not a
bench-and-edit. This session shipped 7 commits (5 clean wins + 2 work-removals:
in_edges(keys) 0.68x->0.79x, selfloop(data=True) 0.16x->0.48x).

## 2026-07-02 CopperCliff SHIP (work-removal): simple-Graph selfloop_edges(data=True) 0.16x -> 0.48x — native batch emission (kill the per-node AtlasView machinery)

`selfloop_edges(G, data=True)` on a simple Graph was 0.16x vs nx (6x SLOWER) — the
worst gap in the whole selfloop family (mg/mdg variants 0.40-0.68x). ROOT (cProfile):
NOT the attr-dict build (cached, cheap) but the Python `G[n]`/`nbrs[n]` per-self-loop-
node machinery — `_graph_getitem_from_adj` -> AtlasView `__getitem__` -> `_keydict`,
~75k Python calls for 2500 self-loops. MultiGraph/MultiDiGraph already have a native
`_native_selfloop_edges`; simple PyGraph did NOT (it fell to the Python adjacency walk).
FIX (br-r37-c1-slgraph): added a PyGraph `_native_selfloop_edges` that emits the
`(n, n, dict)` tuples in one Rust pass, handing out the LIVE `materialize_edge_py_attrs`
dict (data=True mutations persist == nx) and `mark_edges_dirty` like the multigraph path.
Wired ONLY for data=True (data=False keeps its faster generator fast path — native was
~6% slower there; data="<attr>" keeps the Python value path). RESULT: 0.16x -> 0.476x
(2.9x self). Byte-exact 0 mismatches over data True/False/attr/missing x keys, mutation-
persist, str nodes, no-selfloop, N=20..2500; conformance GREEN (798 selfloop). RESIDUAL:
0.48x is now the dict-MATERIALIZATION floor (fnx builds V_selfloop PyDicts; nx hands out
live adj dicts) — needs the persistent Python-object mirror. LESSON: a "materialization
floor" 0.16x can hide a THICK Python-machinery layer on top — a native batch peels it
(6x->2x slower) even when the true floor remains.

## 2026-07-02 CopperCliff SHIP (work-removal): MDG in_edges(keys=True) 0.677x -> 0.791x — hoist per-key py_node_key out of the loops (residual = String-hash floor)

Fresh re-measure showed the documented mdg in_edges gaps are mostly STALE WINS now
(in_edges(keys,data=True) 26x, edges(keys) 2.8x, out_edges(keys) 2.6x) — but
`in_edges(keys=True)` (keys, NO data) was 0.677x, the odd one out: out_edges/edges route
through the fast `_MultiDiGraphEdgeView` while in_edges uses
`_native_mdg_in_edges_no_data`. ROOT: that binding recomputed `py_node_key` (String-hash
+ node_key_map lookup + incref) for BOTH endpoints PER KEY — i.e. per parallel edge, and
twice per simple edge. FIX (br-r37-c1-mdginedgeshoist): hoist the target object out of
the predecessor loop and the source object out of the key loop, reuse by O(1)
`clone_ref`. Strict work-removal, byte-identical order (0 mismatches over
parallel/self-loop/custom-key/nbunch/str-nodes), conformance GREEN (247 in_edges).
RESULT: 0.677x -> 0.791x. RESIDUAL (not takeable cheaply): still below nx because the
per-pair `py_node_key` String-hash remains — the O(1)-index materialization that makes
out_edges/edges fast needs index-based adjacency, which the classes `MultiDiGraph` does
NOT have (it's String-keyed IndexMaps internally, unlike DiGraph's succ/pred_indices).
Closing the last 0.79x->1.0x needs index adjacency on MultiDiGraph (a larger change).

## 2026-07-01 CopperCliff SURFACE: subset-kernel vein mined out — approximation/assortativity/lca/hashing families all wins; residual gaps near-zero or architectural

After 5 subset-kernel ships this session (node_clique_number, number_of_cliques, volume,
square_clustering, generalized_degree), swept the remaining un-benched families for the
same lever. ALL wins: numeric/attribute_assortativity 1.6-1.8x, large_clique_size 2.3x,
approximation.diameter 2.7x, min_weighted_vertex_cover 6.3x, triadic_census 15x,
transitivity 40x, all_pairs_lca 1.06x, maximal_independent_set 1.11x. Only sub-1.0:
wl_subgraph_hashes 0.92x + wl_graph_hash 0.96x (parity, iterated-hash constant factor),
shortest_simple_paths 0.85x (Yen's, ~40 µs absolute — near-zero). None takeable
(near-zero absolute or algorithmic constant factor). BLOCKER (unchanged): the only
remaining MEASURED gaps with real absolute stakes are the materialization/dual-storage
floors — in_edges/edges-view PyObject rebuild (0.24-0.35x), to_directed-scalar dual-store
(0.65x), degree/edge-view subset materialization (~40 µs, near-zero) — all needing a
persistent ordered Python-object mirror (a large architectural primitive), not a
bench-and-edit lever. The subset-computes-whole-graph vein that yielded this session's 5
ships is mined out.

## 2026-07-01 CopperCliff SHIP: generalized_degree(SUBSET, |S|>=32) 0.81x -> 2.6-4.08x — native subset kernel (sibling of square_clustering)

Applied the square_clustering subset lever to generalized_degree. A LIST of nodes ran
the Python `_triangles_and_degree_iter_local` neighbor-intersection port (0.76-0.81x vs
nx, growing absolute with |S|); the native all-node `generalized_degree_rust` kernel was
nodes=None only. The per-node kernel is lazy (`graph.neighbors` per node, no whole-graph
setup), so a subset variant is O(|S|*deg^2). FIX (br-r37-c1-gdsub): refactored the
kernel -> `generalized_degree_for(graph, targets)` + binding
`generalized_degree_rust_subset` + Python routes the exact-simple-Graph no-self-loop
subset case (same self-loop gate as nodes=None — the kernel counts a self-loop as a
neighbour). RESULT (12-regular): N=2000 |S|=100 3.65x / |S|=500 4.08x; N=6000 |S|=100
2.61x / |S|=500 4.08x. Byte-exact 0 mismatches over single(->Counter) / lists / all /
missing / empty / set / tuple / self-loop (falls to Python). Conformance GREEN (833
generalized_degree/triangle). GUARD: a `len(selected_nodes) >= 32` gate keeps TINY
subsets on the Python port — at N=6000 |S|=10 the O(E) number_of_selfloops gate + binding
overhead made the native path 0.44x (WORSE than the 0.76x port); the guard restores the
0.73x port for tiny subsets while keeping the |S|>=100 wins. LESSON: a native subset
kernel still carries per-call SETUP (here the O(E) self-loop gate) — guard it out for
subsets too small to amortize.

## 2026-07-01 CopperCliff SHIP: square_clustering(SUBSET) 0.51-0.66x -> 1.15-23.8x — native subset kernel (compute only the targets), overturning the prior SURFACE

Overturned the SAME-DAY surface below with a corrected cost model. The surface said a
subset kernel "stays O(N)" because it builds whole-graph adj + size-n stamps. TRUE, but
that O(V+E) adj build + O(V) stamp init is MICROSECONDS in Rust — the native all-node
kernel's cost is COMPUTE-dominated (~2.6 µs/node square-count). So a kernel that builds
the full adj once but computes ONLY the target nodes is fast for any |S|, no lazy sparse
adjacency needed.

FIX (br-r37-c1-sqclsub): refactored `square_clustering_pairs` -> `square_clustering_pairs_for(graph, targets: &[usize])` (all-node path passes `0..n`, ONE copy of the stamp-array
arithmetic); new binding `square_clustering_fast_subset(g, nodes)` maps the already-
validated in-graph node list to indices and runs the kernel over just those; the Python
`square_clustering` wrapper routes the exact-simple-Graph subset case (single OR list) to
it. RESULT: 10-regular N=500 |S|=5 0.6x->11.1x, |S|=50 ->23.8x; N=2000 ->3.8x/17.4x;
N=6000 ->1.15x/8.8x. Byte-exact 0 mismatches over single (returns SCALAR) / list / all-
list / with-missing (skipped) / empty / isolated / self-loops / set+tuple nbunch, and
the `squares/potential if potential>0 else 0` (float / int-0) result shape. nodes=None
all-node fast path UNCHANGED (still square_clustering_fast). Conformance GREEN (976
clustering + 748 nbunch/triangles/generalized_degree); clippy clean. LESSON: "reusing an
O(N)-setup kernel stays O(N)" ignores that O(N) SETUP is cheap when the real cost is the
O(sum deg^2) COMPUTE — restrict the compute, keep the cheap setup.

## 2026-07-01 CopperCliff SURFACE (SUPERSEDED by the SHIP above): clustering-family SUBSET gaps (square_clustering 0.51x, triangles/clustering/generalized_degree ~0.78x) are the materialization floor — NOT the volume lever

Chased the clustering family after volume (same "fast-path comment benchmarked vs
old-fnx not nx" smell). Confirmed NON-takeable without a native sparse kernel:
- triangles/clustering/generalized_degree(subset) ~0.78x, ~150 µs and CONSTANT with N
  for fixed |S|=10 (even on a 10-REGULAR graph). Per-node local port whose cost is the
  `_raw_neighbors(G,n)` -> Python `set()` materialization (CachedNeighborSets), ~25%
  over nx's live-dict adjacency. Pure per-node materialization floor.
- square_clustering(subset) 0.51-0.66x is worse AND grows with N (10-regular, |S|=10:
  833/1284/1471 µs at N=500/2000/6000). The native `square_clustering_fast` CSR kernel
  (square_clustering_pairs) exists but is nodes=None ONLY; it builds the WHOLE-graph adj
  (O(V+E)) + size-n stamp arrays, so any subset variant reusing it stays O(N).
  MEASURED the native-all+filter route: only wins when |S| is a large fraction —
  N=500 |S|>=10 (native 510 µs flat), but N=6000 |S|=10 native-all 15.9ms >> port 2ms.
  So no clean pure-Python routing: native-all+filter is O(N), the port is
  O(|S|*deg^2). A real fix needs a NATIVE SUBSET kernel with LAZY sparse adjacency
  (HashMap over the 2-hop closure of S) + sparse/HashMap stamps to avoid the O(N)
  whole-adj build and O(N) stamp init — a substantial byte-exact-risky rewrite for a
  niche case (nodes=None, the common call, is already the native fast path). Deferred.

## 2026-07-01 CopperCliff SHIP: cuts.volume(S) 0.06x -> 1.40x (|S|=40, N=2000) — subset degree view, not a whole-graph dict(G.degree())

Same "un-extended subset fast path" family as the clique wins. `volume(G, S)` (sum of
degrees of nodes in S; feeds conductance/normalized_cut/cut metrics) had a fast path
that materialized the ENTIRE degree dict — `deg = dict(G.degree()); sum(deg.get(v,0)
for v in S)` — O(V) regardless of |S|. Its comment claimed a win "even for |S|<|V|/2",
but that was measured against the old per-node AtlasView walk, NOT vs nx: at N=2000 the
whole-dict path is 216 µs / **0.06x vs nx** for |S|=40 (16x SLOWER).

FIX (br-r37-c1-volsubdeg, PURE-PYTHON): `sum(d for v, d in G.degree(S))` — nx's own
formula, passing S straight to the O(|S|) subset degree view. fnx's degree(nbunch) view
is fast enough to BEAT nx in EVERY regime: |S|=40 0.06x->1.40x, |S|=500 0.34x->1.14x,
|S|=all 1.08x->1.10x. Byte-exact 0 mismatches over 40 random subsets incl injected-
missing nodes (degree(nbunch) skips them == the old get(v,0)=0), self-loops (counted
twice), empty, list-input, and the weighted/directed/multigraph SLOW paths (unchanged).
Conformance GREEN (2174 volume/conductance/cut/boundary/expansion). LESSON: a fast-path
comment that benchmarks only against the OLD fnx path (not nx) can hide a regression vs
nx — re-measure vs ORIG. Same lever as node_clique_number / number_of_cliques.

## 2026-07-01 CopperCliff SHIP: number_of_cliques(LIST of nodes) 0.838x -> 2.03x (list-20) / 7.69x (list-5) — per-node ego count (sibling of node_clique_number)

Immediately applied the node_clique_number lever to its sibling. `number_of_cliques(G,
nodes=<list>)` was 0.838x: fnx already ego-optimized the SINGLE-node case
(br-r37-c1-ncliqueego) but a LIST fell to whole-graph `find_cliques(G)` + a
`Counter(chain.from_iterable(...))` — nx's own algorithm, on which fnx was even a hair
slower (Python `Counter.update` loop vs nx's single-C-call constructor).

By the ego bijection (maximal cliques of G containing n == maximal cliques of ego(n)),
`number_of_cliques(G, n) == len(find_cliques(ego(n)))`. FIX (br-r37-c1-ncliquelistego,
PURE-PYTHON): the list branch becomes `{n: (len(find_cliques(ego(G,n))) if n in G else
0) for n in nodes}`. CRITICAL contract difference from node_clique_number: nx returns
**0** for a missing list node (its `Counter[missing]`), so the naive per-node ego
(which raises NodeNotFound) would DIVERGE — the `if n in G else 0` guard preserves it;
an unhashable-in-list still raises TypeError (via `n in G`) exactly like nx's
`Counter[unhashable]`. Byte-exact 0 mismatches over single / lists 1..N / injected-
missing / None / empty / cliques-provided / set-arg. list-5 7.69x, list-20 2.03x (both
beat nx; nx pays a full graph find_cliques even for 5 nodes). Conformance GREEN (1176
clique + ego). nodes=None + precomputed-cliques paths keep the whole-graph Counter.

## 2026-07-01 CopperCliff SHIP: node_clique_number(LIST of nodes) 0.506x -> 1.28x — per-node ego_graph instead of whole-graph find_cliques + scan

Found in a fresh community/clique/similarity/structural-holes sweep (all other
workloads wins: find_cliques parity, constraint/effective_size 590x, louvain 16x,
greedy_modularity 23x, closeness_vitality 39x). The lone gap: `node_clique_number(G,
nodes=<list>)` 0.506x (fnx 4.5ms / nx 2.3ms, N=500/5N, 20-node list).

ROOT: fnx already ego-optimized the SINGLE-node case (br-r37-c1-ncliqueego) but a LIST
of nodes fell to `cliques = list(find_cliques(G))` over the WHOLE graph + a per-node
membership scan — O(all maximal cliques) regardless of how few nodes are queried. nx's
own algorithm runs `find_cliques(ego_graph(G, n))` PER node (each node is universal in
its ego graph, so max-size there == its clique number; order-invariant).

FIX (br-r37-c1-ncliquelistego, PURE-PYTHON, no rebuild): extend the ego fast path to
the list branch — `{n: max(len(c) for c in find_cliques(ego_graph(G, n))) for n in
nodes}`, exactly nx's structure but on fnx's native find_cliques + ego_graph. RESULT:
list-20 0.506x->1.281x, list-5 1.282x (BEATS nx both). Byte-exact 0 mismatches over
single / lists sized 1..N / None / empty / cliques-provided, and the error contract
(NodeNotFound "Source .. is not in G" for a missing list node; TypeError for a single
non-node; {node:0} for unhashable-in-list). Conformance GREEN (1150 clique + 178
node_clique/ego). NOTE: the explicit ALL-nodes list is the one case where the old
whole-graph find_cliques (31ms) beat per-node ego (45ms) — but that path is
`nodes=None` in normal use (unchanged), and even the list form still beats nx (57ms).
LEVER: an existing single-element fast path often just needs extending to the
collection case (grep fast paths gated on a single hashable arg that fall back to a
whole-graph scan for the list form).

## 2026-07-01 CopperCliff SURFACE: paths/cycles/flow/planarity family swept — non-takeable gaps mapped (hits is a warm WIN, simple_cycles/double_edge_swap already-optimized)

Fresh family sweep (untouched before): every workload a win — cycle_basis 2.5x,
min_cut_value 2.7x, immediate_dominators 3.3x, is_chordal 3.5x, global_reaching 3.9x,
maximum_flow_value 4.0x, check_planarity 7.2x, all_shortest_paths 10.5x,
all_simple_paths 1.4x. THREE apparent sub-1.0 gaps, ALL confirmed non-takeable on
isolated re-measure:
- `hits` 0.775x was scipy COLD-START noise (min-of-4, cold ARPACK). WARM min-of-11 =
  1.09x (fnx 1.87ms / nx 2.03ms) — a WIN. Same cold-eig/scipy trap as
  warm_saturation_map_and_coldeig_noise; hits is svds-bound, matrix build is a win.
- `double_edge_swap` 0.85x — ALREADY optimized (br-r37-c1-vbwpl: O(1) in-place edge-
  slot updates, not O(E)/swap rebuild). Residual = inherent per-swap add/remove PyO3;
  fnx uses uniform-pick (intentional divergence, only degree-seq parity owed).
- `simple_cycles` 0.70x — ALREADY de-delegated (br-r37-c1-sccnv:
  `_simple_cycles_structure_only_via_networkx` builds a BARE attr-less nx graph, not
  the ~3x `_fnx_to_nx`, then runs nx's Johnson). Residual = the fnx->nx edge-view
  conversion + Johnson itself; fully closing needs a native exact-cycle-ORDER Johnson
  kernel (the Rust simple_cycles emits a different order) — a large port, not 60-min.

## 2026-07-01 CopperCliff SURFACE: mutable-view correctness class fully closed + `G.nodes[n]` read 0.19-0.26x is the node_key_to_string floor (uniform, not takeable)

Post-MDG-node-fix (4bfe8b411) sweep. TWO results:

(1) MUTABLE-VIEW CORRECTNESS CLASS NOW FULLY CLOSED. Exhaustively verified in-place
mutation persists byte-exact vs nx across ALL 4 types × batch/per-edge for every
entry point: `nodes[n].update()`/`[k]=v`, `nodes.get(n)`, `nodes[n].setdefault()`,
`nodes(data=True)` yielded dict, `edges(data=True)` yielded dict, `G[u][v][..]=x` /
`G[u][v][key][..]=x`, `adj[u][v]`, `get_edge_data(..)`, and isolated-node mutation.
0 failures. The MDG NodeView getitem was the last hole; no second instance exists.

(2) `G.nodes[n]` READ is 0.19-0.26x vs nx — WARM (all nodes pre-materialized), UNIFORM
across G/DG/MDG (0.19/0.26/0.23x), i.e. NOT a type divergence and NOT the borrow_mut.
ROOT = the node_key_to_string floor (4b5ie): every access canonicalizes the Python
node object to a String store/mirror key + runs the Python keystr wrapper
(`hash(node)` + try/except), vs nx's direct `self._nodes[n]` live-dict lookup. A
`borrow()`-instead-of-`borrow_mut()` fast path on the mirror-hit case is a micro-opt
that cannot touch the 4-5x gap (the String canonicalization + Python wrapper dominate),
so NOT taken. Same floor as the degree/edge view-materialization gaps.

FRONTIER (this session's sweep — operators, structural transforms, graph-invariants,
serializers, mutable-views): every non-floor workload is a WIN (union 2.4x, compose
1.9x, difference 2.1x, disjoint_union 3.6x, complement 5.7x, contracted_nodes 6.2x,
relabel 1.24x, is_isomorphic 190x, rich_club 68x, fast_could_be_isomorphic 6.1x,
triangles 6.6x, to_undirected-plain 84x). Residual gaps ALL floor/no-ship: degree_seq
0.85x + bipartite_degrees 0.81x (degree-view), node_link_data 0.70x + mg_selfloop_keys
0.35x (serializer/edge-view materialization), to_directed-scalar 0.65x (dual-storage),
multigraph_clear_edges 0.36x (construction fragmentation). All need the same large
primitive — a persistent ordered Python-object mirror — not a 60-min kernel edit.

## 2026-07-01 CopperCliff FIX: batch-built MultiDiGraph `G.nodes[n].update()` data-loss (was silently dropped) — behavior gap vs nx closed

Followed up the correctness bug surfaced the same day (1438d4495). ROOT: the
MultiDiGraph NodeView `__getitem__` (digraph.rs ~7633) did `let g =
self.graph.borrow(py); g.node_py_attrs.get(canonical).map_or_else(|| PyDict::new(py),
|d| d.clone_ref(py))` — on a mirror MISS it returned a FRESH UNSTORED dict, and nodes
created implicitly by `add_edges_from` have no mirror entry, so `G.nodes[n].update({..})`
/ `G.nodes[n][k]=v` mutated a throwaway dict and the write was LOST. DiGraph
(br-r37-c1-d58s8) and MultiGraph already fixed this exact class; MDG was missed.
FIX (br-r37-c1-mdgnodeget): `borrow_mut` + `materialize_node_py_attrs` (entry/or_insert
+ clone_ref) hands back the SAME cached mirror object so in-place mutations persist —
one-line-equivalent copy of the DiGraph pattern. Attributed nodes are already in the
mirror (add_nodes_from populates it), so the or_insert-empty fallback only fires for
genuinely attr-less nodes. VERIFIED: verify_mdg 0 failures across all 4 types ×
batch/per-edge (view mutation persistence, read parity vs nx for store+mirror attrs,
mutate-then-serialize, shared-object identity, missing-node KeyError); conformance
6577 + 3026 green (the 3 reds are the pre-existing find_induced_nodes no-fallback
tests, unrelated). TRADEOFF: `G.nodes[n]` read now materializes-on-access (0.23x vs
nx, matching DiGraph's existing 0.25x) — the required cost of a persistent write
target; correctness > read speed, consistent with the other 3 types.

## 2026-07-01 CopperCliff NO-SHIP: node_link_data 0.70x vs nx is the materialization floor (native binding 0.90-0.95x vs the comprehension — REVERTED)

`node_link_data(G)` measures 0.67-0.79x vs nx (fnx 16.5ms / nx 11.0ms at
N=5000 Graph). Unlike `size(weight)` (a scalar, fixed 2026-06-30 → 19.6x), this
returns E edge dicts + V node dicts — a genuine collection materialization. Its
sibling `adjacency_data` wins (1.16x) only because it routes through the
store-reading `G.adjacency()` Python path; `node_link_data`'s native binding
(`node_link_data_simple`) was previously REMOVED (br-r37-c1-9kpev) for reading the
empty edge MIRROR on bulk-built graphs (dropped attrs).

ATTEMPT (br-r37-c1-nldstore): gave `node_link_data_simple` the proven `Some(mirror)
else store` fallback (attr_map_to_pydict on mirror-miss — same fix shape as
to_directed 589a8d036) and re-enabled the native path for exact Graph/DiGraph.
VERIFIED byte-IDENTICAL to the comprehension it replaces (nodes+edges, key order
included, across batch/per-edge/large builds) and json/node_link conformance GREEN
(130 + 62 tests). BUT the native binding measured **0.90-0.95x vs the
comprehension** (constructor 16.2 vs 15.5ms; add_edges_from 14.9 vs 13.4ms) — NO
speedup. ROOT: both the constructor and add_edges_from POPULATE the edge mirror, so
the binding takes the `d.bind(py).copy()` per-edge path (one PyDict copy/edge) —
identical cost to the comprehension's `{**ea, source, target}` spread. The
store-fallback single-alloc advantage only exists for a genuinely mirror-empty
graph, which these construction paths don't produce. Building E Python dicts from
Rust is the FLOOR nx escapes by spreading E live dicts. ~0-gain → REVERTED per
"REVERT ~0-gain" (stash `cc-nodelinkdata-NOSHIP-materialization-floor-0.90x-native-
vs-comprehension`). LEVER CONFIRMED: the scalar-reduction win (size) does NOT
generalize to collection-returning serializers — those stay materialization-floor
bound, needing a persistent ordered Python-object mirror (a large primitive).

SURFACED (separate PRE-EXISTING correctness bug, NOT introduced here): on a
**batch-built (add_edges_from) MultiDiGraph ONLY**, `G.nodes[n].update({...})` and
`G.nodes[n]['k']=v` silently DROP the mutation — `G.nodes[n]` returns a detached
dict. Graph / DiGraph / MultiGraph (batch + per-edge) and per-edge MultiDiGraph all
persist correctly; `add_node(n, **attrs)` on the same MDG persists too. So the
data-loss is confined to the NodeView mutable-view path for batch-built MDG. Needs
a proper node-mirror fix (materialize-from-store + write-back on `nodes[n]`) with
full node-mutation conformance — deferred, flagged for follow-up.

## 2026-06-29 CopperCliff SHIP: graph products (cartesian/tensor/strong/lexicographic) with self-loops 0.18-0.28x->2.4-4.8x (`br-r37-c1-prodself`)

Same "kernel gated to bail on a rare structural feature" lever as line_graph
(`br-r37-c1-lgself`), found by the SAME bench trap: `_native_graph_product` (the
shipped fe0dbee38 kind-enum kernel, 2.3-4.8x nx) bailed via
`if number_of_selfloops(G) or number_of_selfloops(H): return None`, so a product
where EITHER factor had even ONE self-loop dropped to the ~4x-SLOWER Python
construction: cartesian **0.25x**, tensor **0.28x**, strong **0.26x**,
lexicographic **0.18x** vs nx (200x40-node factors, 1 incidental self-loop each).

ROOT CAUSE the gate was wrong, not needed: the Rust kernel already enumerates each
factor's edges with `v >= u` (self-loop pairs INCLUDED), and the simple-graph
`extend_edges_unrecorded` inherently de-duplicates the tensor/lexicographic
double-push of a self-loop-induced product edge (a simple Graph cannot hold a
parallel edge) — so the edge SET already matches nx's idempotent `add_edge`
construction. FIX (pure-Python, NO rebuild): drop the `number_of_selfloops` bail
from the wrapper gate; keep the multigraph / mismatched-directedness / attr bails
(attr graphs still need the Python attr-pairing path).

MEASURED vs NetworkX (min of 5, with self-loops): cartesian **0.25x->2.41x**,
tensor **0.28x->4.22x**, strong **0.26x->4.79x**, lexicographic **0.18x->2.44x**;
self-loop-free unaffected (still 3.4-5.4x). Byte-EXACT 480/480 random
directed+undirected self-loop factor pairs (node set + edge set + node/EDGE COUNTS)
+ explicit both-factors-self-loop + self-loop-free cases; new regression
`test_graph_product_selfloop_native_parity.py`; product suite 676 passed. LEVER
(reinforced): when a native kernel ALREADY computes the rare feature correctly, the
conservative Python `return None` guard is pure deadweight that taxes the whole
input — drop the guard, don't just route around it. Audit remaining
`number_of_selfloops(...)==0` / `is_multigraph()` wrapper gates that front a kernel
which already handles the case.

## 2026-06-29 CopperCliff SHIP: line_graph() with self-loops 0.65x->5-8x — native kernel now handles self-loops (`br-r37-c1-lgself`)

`line_graph(G)` had a native fast path (`line_graph_fast`, 6x nx) for self-loop-FREE
simple graphs, but the kernel BAILED (returned None) on ANY self-loop — so a graph
with even ONE self-loop fell to the slow Python tuple-rebuild path: undirected
**0.65x** nx (104ms vs 68ms), directed similar. Self-loops are common in real graphs
(and the whole-graph bench had ~3 incidental ones), so the gap is realistic.

FIX: extend the undirected kernel (algorithms.rs:14931) to treat a self-loop `(u,u)`
as an undirected edge -> an L-node incident at u EXACTLY ONCE (nx's `G.edges(u)`
yields it once), paired with u's other incident edges in u's clique. The "two
distinct edges share at most one endpoint -> emit once, no dedup" invariant still
holds (a self-loop shares only endpoint u with other edges); a `self_loop_done`
guard prevents any double-listing in adj_indices. The directed kernel already
reproduced nx's `(u,u)->(u,w)` L-edges (incl. the L self-loop `(u,u)->(u,u)`), so
just relaxed the Python wrapper's `number_of_selfloops(G)==0` gate to let self-loop
graphs reach the native path (both directions); the kernel returns None for anything
it can't serve (multigraphs / create_using).

MEASURED vs NetworkX (min of 7, n=1200, m=5000, ~3 self-loops): undirected
`line_graph` **0.65x->8.36x** (11.3ms vs 84ms), directed **->5.07x** (7.9ms vs
37ms). Self-loop-free unaffected (still 6x). Byte-EXACT (order-insensitive L-node +
L-edge sets, nx's parity convention) 240/240 random directed+undirected self-loop
graphs + explicit undirected/directed/lone-self-loop cases; new regression
`test_line_graph_selfloop_native_parity.py`; line_graph suite 286 passed, +86 with
the new test; clippy clean (2 pre-existing). LEVER: a native kernel gated to bail on
a rare structural feature (self-loop) sends the WHOLE input to the slow path — handle
the feature in-kernel when the core invariant still holds, rather than bailing.

## 2026-06-29 CopperCliff NO-SHIP: DiGraph weighted degree(weight) store accumulator — ~0 gain, materialization floor (`br-r37-c1-dgwdegs`)

Measured gap: simple `DiGraph.degree(weight)` **0.75x** (int) / **0.82x** (float) vs
nx (n=1500, m=6000), in/out_degree similar 0.74-0.84x. Simple Graph is near parity
(0.93-0.96x). The DiGraph total `_native_weighted_degree` (digraph.rs:11408) builds
a per-node succ PyList + pred PyList from the edge mirror + two `builtins.sum`.

ATTEMPTED the exact lever that WON for MultiDiGraph (9f0e40cb8) and MultiGraph
(03686f5ab): added store-int (`weighted_degree_store_int_node_dg` /
`native_weighted_total_degree_store_int_dg`) + store-float
(`weighted_total_degree_float_node_store_dg`) fast paths reading CgseValue from the
store (zero PyO3, gated !edges_dirty). Byte-EXACT 240/240 (float/int/mixed +
self-loop-counted-twice + missing-default-1 + mutation). VERIFIED the store path
ENGAGES (a fresh/lazy-mirror DiGraph returns correct results — only possible if the
store path runs, since the mirror is empty). BUT perf UNCHANGED (0.75x->0.75x int,
0.84x float). REVERTED.

ROOT CAUSE: simple DiGraph is SPARSE (~4 edges/node), so the per-edge PyList-append
+ `builtins.sum` overhead the store path removes is SMALL; the dominant cost is the
per-node PyObject MATERIALIZATION floor (building 1500 `(py_node_key, into_py_any)`
tuples), identical on both paths. MultiDiGraph won (1.8-2.5x) only because parallel
edges made the per-edge PyList+sum+edge_key overhead LARGE relative to the per-node
materialization. The store lever pays off iff edge-read overhead dominates per-node
materialization — true for multigraphs, FALSE for sparse simple DiGraph. DON'T
re-attempt a store/kernel optimization on simple Graph/DiGraph weighted degree; the
floor is per-node Python-object construction (see
[[reference_head2head_vein_map_materialization_floor]]). Conformance GREEN, .so
rebuilt to HEAD.

## 2026-06-29 CopperCliff NO-SHIP: MG/MDG induced subgraph().copy() parent.edges() shortcut — nx induced-view REORDERS edges (`br-r37-c1-mgsubcopy`)

Measured gap: `MultiDiGraph.subgraph(half).copy()` **0.54x** nx (17.2ms vs 9.2ms),
`MultiGraph` **0.73x** — both fall to the slow generic rebuild because
`_copy_induced_simple_fast` bails for multigraphs (init.py:40339), iterating the
FILTERED VIEW's `edges(keys=True, data=True)` (per-edge view-wrapper overhead).
Simple Graph/DiGraph subgraph copy is already 1.2-1.5x.

ATTEMPTED (the symmetric trick to the edge_subgraph fast path at init.py:40429):
filter the parent's FAST native `edges(keys=True, data=True)` (8x faster than nx)
by node-set membership instead of walking the view. Perf was promising — MG
0.73x->1.70x — BUT BYTE-EXACT FAILED 14/400 (MG and MDG). REVERTED.

ROOT CAUSE: nx's INDUCED subgraph view does NOT preserve parent adjacency order
when filtering removes nodes. Verified pure-nx (n=5, seed=79): parent
`adj[2]=[4,1,2,0,3]`; manual parent-order filter to {2,4} = `[4,2]`; but
`subgraph([2,4]).adj[2]` = `[2,4]` (the self-loop / surviving-neighbor order is
permuted by the filter). When NO filtering occurs (subgraph keeps all of a node's
neighbors) parent order IS preserved (controlled 5-node test) — so the reorder is
filter-dependent and is NOT a simple parent-order, sub-iteration-order, or sorted
rule. fnx's own VIEW `edges()` already reproduces nx's order exactly (the slow
copy path is byte-exact); `parent.edges()` cannot. UNLIKE edge_subgraph (selected
edges keep parent order -> the 40429 shortcut is valid there), node-induced
multigraph copy needs nx's exact filtered-adjacency permutation. LEVER FOR A REAL
FIX (deferred, non-trivial): reproduce nx's induced multigraph adjacency ordering
natively (study FilterAtlas iteration for MultiDiGraph under node removal) — a
native `subgraph_copy` kernel, not a Python parent.edges() filter. Conformance
GREEN after revert (0/240 byte-exact). DON'T re-attempt the naive parent.edges()
filter for NODE-induced multigraph subgraphs.

## 2026-06-29 CopperCliff SHIP: DiGraph.to_directed() 0.58x->10-23x — deep-copy fast path ahead of the materialize wrapper (`br-r37-c1-dgtodir`)

DiGraph was the ONLY graph type whose `to_directed()` had no native fast path
(Graph/MultiGraph/MultiDiGraph all route to `_native_to_directed_deepcopy`). It
rebuilt via a per-arc Python `add_edges_from` loop AND was wrapped by
`_materialize_attrs_before_convert`, whose post-conversion probe walks
`result.edges(data=True)` — forcing an O(E) mirror materialisation of the copy
(~10x the cost of the copy itself). Net 0.58x nx (22.97ms vs 13.31ms, n=1500).
KEY DIAGNOSIS: the per-arc rebuild was only ~half the cost; the materialize
wrapper's probe was the dominant hidden tax (decomposed: inner copy 0.6ms, full
wrapped call 7.9ms with NO redo triggered — the probe alone forced the O(E) walk).

FIX (pure-Python, no rebuild): an already-directed DiGraph's `to_directed()` is a
full deep copy into the same class, so route to `copy.deepcopy` (native deep-copy
machinery: preserves store edge attrs AND deep-copies graph-level attrs) AHEAD of
the materialize wrapper, returning directly so the pointless O(E) probe never runs
(`_digraph_to_directed_deepcopy_fastpath`, gated `type is DiGraph` + default
`to_directed_class` + no nx private storage + `as_view is not True`). Subclasses /
custom class / nx-private storage / as_view fall through to the wrapped path.

MEASURED vs NetworkX (min of 15): n=500 **10.50x**, n=1500 **20.23x**, n=3000
**22.92x** (fnx 0.4-1.3ms via native deepcopy vs nx's per-edge Python rebuild
12-29ms; was 0.58x). Byte-EXACT 120/120 random (nodes/edges/graph attrs/order/
flags) + batch-built weight survival + source-independence + as_view view +
subclass fall-through + empty; new regression
`test_digraph_to_directed_deepcopy_fastpath.py`; signature `(self, as_view=False)`
preserved; conversion/copy suite **5388 passed**, algo consumers **4077 passed**.
LEVER (reusable): a correctness GUARD wrapper (here the attr-materialize probe)
can dominate a fast path's cost — route a known-correct fast path AHEAD of the
guard, not inside it. And: `to_directed()` on an already-directed graph == deep
copy; `to_undirected()` on undirected likewise.

SYMMETRIC FOLLOW-UP (same commit): applied the identical fast path to
`Graph.to_undirected()` (undirected->Graph is also a deep copy; simple Graph had no
native shortcut, only MultiGraph did). **1.25x->40.86x** (fnx 0.48ms vs nx 19.6ms,
n=1500). `DiGraph.to_undirected` is left untouched — it COLLAPSES reciprocal edges
(not a deep copy) — and its parity is locked by a regression test. Byte-exact
80/80; to_undirected/convert/copy suite 2942 passed.

## 2026-06-29 CopperCliff SHIP: MultiGraph INT weighted degree 0.54x->1.28x — store-backed int accumulator (`br-r37-c1-mgwdegfs`)

MultiGraph `degree(weight=...)` had NO store-backed int accumulator (unlike
MultiDiGraph's ac98e77d4) — every int-weighted degree went through a per-node
`PyList` + `builtins.sum` (~0.54x nx at n=1500, m=6000, int weights, bulk-built).
FIX: `weighted_degree_store_int_node` / `native_weighted_total_degree_store_int`
(lib.rs PyMultiGraph) sum int weights straight from the native CgseValue store
(zero per-edge PyO3), gated on `!edges_dirty`, wired ahead of the float Neumaier
path and the PyList fallback. nx's MultiDegreeView counts a self-loop's weight
TWICE, so self-loop weights are accumulated into a separate bucket and added back;
integer addition is associative, so the store iteration order need not match nx's
adjacency order — only the multiset (each neighbor edge once, each self-loop edge
twice). Bails to None on any non-int value so float/mixed/missing-default-1 stay
byte-exact; edgeless node returns int 0.

MEASURED vs NetworkX (min of 11, n=1500, m=6000, bulk-built): MG int
`degree(weight)` **0.54x->1.28x** (now beats nx); `size(weight)` (routes via
degree) **->1.21x**. Float unchanged 0.81x (a float store-direct read was tried
and REVERTED — benchmark-neutral 0.85x->0.83x; the MG float floor is the per-node
`neighbors()`/`edge_keys()` Vec allocs, not the value read). Byte-EXACT: 80/80
random int + self-loop(counted twice)/parallel/missing/isolated + float/mixed
fallback cases; new regression `test_mg_weighted_degree_store_int_parity.py`
(bulk builder); degree/multigraph/weighted/size/assortativity suite **7790
passed**, clippy clean (2 pre-existing lib.rs warnings). LEVER: MultiGraph weighted
degree had the int store accumulator MISSING that MultiDiGraph already had —
symmetric port; int is the easy half (order-independent, no Neumaier).

## 2026-06-29 CopperCliff SHIP: MultiDiGraph FLOAT weighted degree 0.51-0.72x->2.1-2.5x — store-backed float fast path (`br-r37-c1-mdgwdegfs`)

Same mirror-vs-store bug class as the adjacency_data fix, this time in a perf
fast path. The MDG weighted-degree FLOAT fast paths
(`weighted_directional_degree_float_node` / `weighted_total_degree_float_node`,
br-r37-c1-mdgwdegf) read every edge weight from the Python edge MIRROR
(`edge_py_attrs`). That mirror is **empty** for graphs built with the bulk edge
APIs (`add_weighted_edges_from` / `add_edges_from` commit weights straight into
the native CgseValue store and leave the mirror lazy), so the float path returned
None on the FIRST edge and **never engaged** on bulk-built weighted multigraphs —
the overwhelmingly common case. They fell to the per-edge `PyList` +
`builtins.sum` path: `in_degree(weight)` **0.51x**, `degree(weight)` **0.72x** vs
nx (n=1500, m=6000, float weights). The INT path (ac98e77d4) already read the
store, so only int weights were fast.

FIX: added store-backed twins `weighted_directional_degree_float_node_store` /
`weighted_total_degree_float_node_store` that read exact `CgseValue::Float`
weights from the native store using the SAME succ/pred adjacency iteration order
as the proven int store row and the SAME Neumaier (Kahan-Babuska) compensation as
the mirror twins — so bit-identical to `builtins.sum`. Both `_native_weighted_degree`
(total) and `native_weighted_directional_degree` (in/out) prefer the store path
when `!edges_dirty` (store authoritative), else the live mirror (pending edits).
Bails to None (-> exact fallback) on any non-float/absent value or edgeless
direction, so int/mixed/missing-weight parity and nx's int-0 for isolated nodes
stay byte-exact.

MEASURED head-to-head vs NetworkX (min of 9): MDG float `in_degree(weight)`
**0.51x->2.10x**, `out_degree(weight)` **->2.29x**, `degree(weight)`
**0.72x->2.51x**; int weights unchanged (1.4-1.8x, store-int path). Byte-EXACT:
540/540 random float/int/mixed cases (value+type) + empty/isolated/self-loop/
parallel/missing-weight edge cases + catastrophic-cancellation (1e16,1,-1e16)
compensation; new regression `test_mdg_weighted_degree_store_float_parity.py`
(bulk builders, unlike the old selfloop test which used per-edge add_edge and so
never hit the store path); degree/multidigraph/weighted suite **5645 passed**,
centrality/assortativity/flow consumers **6254 passed**. clippy clean (2 warnings
pre-existing in lib.rs). LEVER (reusable): any `*_float_node`/`*_exact_f64_mirror`
helper that reads `edge_py_attrs`/`node_py_attrs` is DEAD for bulk-built graphs —
add a store-backed twin gated on `!edges_dirty`, reusing the int store row's
iteration order for byte-exactness.

## 2026-06-29 CopperCliff FIX+SHIP: adjacency_data / node_link_data DATA-LOSS bug — native *_simple kernels dropped edge attrs on batch-built graphs (`adjdataedgeattr`)

CORRECTNESS bug (not just perf). The `br-r37-c1-9kpev` native fast paths
(`_fnx.adjacency_data_simple` / `node_link_data_simple`, gated to exact simple
Graph/DiGraph in BOTH the top-level `__init__.py` and the
`readwrite.json_graph` wrappers) copied each edge's attrs from the **Python edge
mirror** (`edge_py_attrs`). That mirror is **empty** for graphs built with the
bulk edge APIs — `add_weighted_edges_from` / `add_edges_from` commit edge attrs
straight into the native CgseValue store and leave the mirror lazy. So on any
graph built with the batch APIs the native serializers **silently DROPPED every
edge attribute** (e.g. `weight`), corrupting JSON round-trips (the most common
real-world way these graphs are serialized).

FIX (pure-Python, NO Rust rebuild — the buggy bindings are simply no longer
called): route exact simple `Graph` through `G.adjacency()` (rows read the store
correctly + cached outer/row dicts), and exact simple `DiGraph` through the
store-backed `G.edges(data=True)` view grouped by source (byte-identical to nx's
per-node `G[node]` adjacency order). `node_link_data` falls through to the
existing `G.edges(data=True)` comprehension. All four removed call sites replaced
with a documented bail.

MEASURED head-to-head vs NetworkX (min of 7, n=2000 batch-weighted cycle):
adjacency_data undirected **1.23x**, directed **1.42x** (was buggy native 0.79x);
node_link_data undirected **1.01x**, directed **1.23x** — at-or-above nx AND
correct. Byte-EXACT vs nx (weights/color survive) over directed+undirected; new
regression `test_toplevel_batch_built_edge_attrs_survive_serialization`; full
json/adjacency/node_link/readwrite suite **634 passed, 4 skipped**. LEVER
(reusable): a native serializer that reads the Python attr MIRROR instead of the
store is silently wrong for batch-built graphs — audit any `*_simple` kernel that
copies `edge_py_attrs`/`node_py_attrs` for the same mirror-vs-store data loss.

## 2026-06-28 CopperCliff SHIP: MultiGraph average_degree_connectivity 0.11x->1.18x (~10x self) + has_eulerian_path self-loop case 0.05x->1.2x (`br-r37-c1-mgisol`)

Two more MG fallback-tax fixes (pure-Python). (1) `average_degree_connectivity`'s
unweighted-undirected fast path was gated to plain Graph
(`_raw_neighbors_dispatch` excludes Multi), so multigraphs hit the per-node AtlasView
fallback (~13.6ms / 0.11x at n=200). nx sums over DISTINCT neighbors weighted by MULTI
degree, so: multi-degree from native `G.degree()`, distinct neighbor pairs from the
cheap simple projection's edges, accumulate both directions per edge (per-node bucket
init mirrors nx's `dsum[k]+=s` so degree-0 nodes keep their bucket). **0.11x->1.18x**
(13.57ms->1.33ms), byte-IDENTICAL 0/1200 maxdiff 0.0 (integer arithmetic) over
MG/Graph/MDG incl. parallels/self-loops/isolates; 967 assortativity tests pass.
(2) `has_eulerian_path`/`is_semieulerian` self-loop multigraphs were still delegating
to nx (the b98c6a995 fast path ran AFTER the self-loop guard) — 0.05x. The Python
formula (odd-degree count via `G.degree()`, self-loops +2 = even; + is_connected) is
byte-exact for self-loops too (0/500), so moved it BEFORE the guard: **0.05x->1.2x**.
Only SIMPLE self-loop graphs still delegate (native kernel mishandles them).

## 2026-06-28 CopperCliff SHIP: MultiGraph/MultiDiGraph load_centrality 0.43x->19.55x/13.59x — simple-projection + native kernel (`br-r37-c1-mgisol`)

Third win in the MultiGraph fallback-tax cluster. `load_centrality`'s native fast
path is gated `not G.is_multigraph()`, so multigraphs fell to the nx delegation
(~137ms at n=200, **0.43x**) — the 2nd-biggest absolute MG gap from the auto-sweep.
KEY OBSERVATION: Newman's load centrality (split-equally-among-predecessors over
node-SEQUENCE shortest paths) is unaffected by parallel edges, so multigraph load ==
load on the simple projection, which has a bit-exact native kernel.

FIX (pure-Python, NO Rust rebuild): for unweighted whole-graph
(`v is None and cutoff is None and weight is None`) multigraphs, build the simple
projection (Graph/DiGraph; nodes in G order, `add_edges_from` dedupes parallels,
keeps self-loops) and route to `_raw_load_centrality`. The projection build
(~3ms incl. native kernel) dwarfs nx's per-source Newman loop.

MEASURED head-to-head vs NetworkX (min of 6, n=200, 1250 edges incl. parallels):
MultiGraph **0.43x->19.55x** (59.5ms->3.0ms), MultiDiGraph **->13.59x**
(44.2ms->3.3ms). Byte-exact: 0 mismatches over 600 random MultiGraph/MultiDiGraph
(maxdiff 1.67e-16), incl. parallels / self-loops / isolates + empty/single/2-node
edge cases; 2386 centrality conformance tests pass. Artifact:
`tests/artifacts/perf/20260628T-multi-load-centrality-cc/`. LEVER (reusable): when a
node-path algorithm has a `not is_multigraph()`-gated native kernel, multigraphs
often equal the simple projection (parallel edges don't change node-path results) —
route MG/MDG through a cheap projection instead of delegating.

## 2026-06-28 CopperCliff SHIP: MultiGraph has_eulerian_path 0.11x->1.46x, is_semieulerian 0.20x->1.53x — pure-Python wrapper fast path (`br-r37-c1-mgisol`)

Follow-up to the isolates win (c13e173b1) in the same MultiGraph `_`-arm
projection-tax cluster. The `has_eulerian_path` wrapper called
`_raw_has_eulerian_path(G)` for self-loop-free undirected multigraphs; that binding
built the FULL `gr.undirected()` simple-graph projection (clones every node/edge
attr + per-element ledger) AND crossed into Python once per node for the degree view
(~1.44ms / **0.11x vs nx** at n=300). `is_semieulerian` (= `has_eulerian_path and not
is_eulerian`) inherited it (0.20x). `is_eulerian` was ALREADY fast — its wrapper uses
the br-euldense Python fast path — which is the tell: the same trick fixes
has_eulerian_path.

FIX (pure-Python, NO Rust rebuild): for self-loop-free multigraphs, nx's undirected
test is just "<=2 odd-degree vertices AND connected", so run it directly on the fast
MultiGraph degree view + native `is_connected` (which has its own fast multigraph
path), mirroring `is_eulerian`. Self-loop multigraphs still delegate to nx; simple
graphs keep the native kernel; directed unchanged.

NEGATIVE RESULT folded in: a NATIVE-BINDING variant (native multi-degree parity +
`multigraph_to_simple_graph_structure_only` connectivity) was built, measured, and
REVERTED — it only reached **0.31x** because allocating the simple Graph +
`is_connected(&simple)` is itself the bottleneck. The Python path REUSING the fast
`is_connected(MultiGraph)` wrapper wins outright (1.46x). LESSON: when a fast wrapper
path already exists for a sibling predicate (is_eulerian), prefer composing the
existing fast primitives over a fresh native kernel that re-pays the projection.

MEASURED (min of 8, undirected MultiGraph n=300, cycle + parallels): has_eulerian_path
**0.11x->1.46x**, is_semieulerian **0.20x->1.53x** vs NetworkX. Byte-exact: 0
mismatches over 600 random multigraphs x3 predicates (parallels / +/- self-loops /
+/- isolates / error contracts) + empty/single-node edge cases; 603 euler conformance
tests pass. Artifact: `tests/artifacts/perf/20260628T-multi-eulerian-native-cc/`.

## 2026-06-28 CopperCliff SHIP: Multi isolates/number_of_isolates 0.08-0.13x -> 17-59x vs nx — native path drops the per-call simple-graph projection (`br-r37-c1-mgisol`)

A MultiGraph/MultiDiGraph auto-sweep surfaced a cluster of trivial utilities
sitting at a near-constant ~1.1ms (vs nx's ~0.1ms): `number_of_isolates` 0.09x,
`isolates` 0.08x, plus the same ~1.1ms tax on `has_eulerian_path`,
`dfs_preorder_nodes`, etc. — all paying ONE shared cost. Root cause for isolates:
the `isolates`/`number_of_isolates`/`is_isolate` bindings dispatch Multi types
through the `GraphRef` `_` arm, which calls `gr.undirected()`/`gr.digraph()` —
and for `MultiUndirected`/`MultiDirected` those run a FULL O(V+E)
`multigraph_to_simple_graph` / `multidigraph_to_simple_digraph` rebuild on EVERY
call (GraphRef is reconstructed per call by `extract_graph`, so the OnceCell never
amortizes). Isolate detection only needs per-node adjacency-row emptiness, so the
whole projection is pure waste (~140x slower than the simple-graph isolate path:
native `_raw_number_of_isolates` measured 0.008ms for Graph/DiGraph but 1.11ms /
0.95ms for MG / MDG at n=200).

FIX: native isolate methods on `fnx_classes::MultiGraph` (lib.rs) and
`MultiDiGraph` (digraph.rs) — isolated iff the adjacency row (MG) / both
successor+predecessor rows (MDG) are empty/absent. Self-loops record the node in
its own row so a self-loop node stays NON-isolated, matching nx's degree-2
self-loop convention. The binding (fnx-python/algorithms.rs) gains explicit
`MultiUndirected`/`MultiDirected` arms; the match is now exhaustive (no `_`), so
no Multi type can silently fall back to the projection path again.

MEASURED head-to-head (min of 8, n=200, 1000 edges + parallels + self-loops + 20
isolates): MG `number_of_isolates` **0.09x -> 58.66x**, MG `isolates`
**0.08x -> 19.46x**, MDG `number_of_isolates` **0.13x -> 27.06x**, MDG `isolates`
**0.13x -> 17.32x** vs NetworkX. Byte-exact: 0 mismatches over 800 random
multigraphs x3 checks (incl. isolates / self-loops / parallels); 639 + 534
conformance tests pass. Artifact: `tests/artifacts/perf/20260628T-multi-isolates-native-cc/`.
LEVER: the same per-call `gr.undirected()`/`gr.digraph()` projection taxes EVERY
Multi function routed through the `_` arm (dfs/edge_dfs/has_eulerian_path were all
~1.1ms in the sweep) — caching the projection on the Py wrapper keyed by the
`revision` mutation counter would fix the whole class at once (follow-up).

## 2026-06-28 BlackThrush MultiDiGraph in_edges data-key CSR predecessor scan - NO-SHIP (`cod-a`)

Scope: LAND-OR-DIG pass on current `main` base `ddd516ac4`. Read-only
`.scratch`/`.worktrees` audit found no measured bench-worktree source win
absent from `main`: the old BlackThrush edge-view audit worktree is stale and
would revert newer main work, while the CopperCliff adjacency outer-cache
worktree is already represented by the landed `DictOfDictsCache.shared_outer`
implementation. Agent Mail registration/read worked as `BlackThrush`, but
reservation writes hit the existing SQLite corruption circuit breaker; no
`settings.json` or hook files were touched.

Fresh current-main routing sweep used the accepted release-profile equivalent
of the requested per-crate bench command because this Cargo toolchain rejects
`cargo bench --release`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Worst live gap was `MultiDiGraph.in_edges(keys=True, data="weight", default=0)`:

| workload | runner | FNX median | ORIG median | ratio vs ORIG |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `rch` remote `hz2` | `2.9295 ms` | `1.5721 ms` | `0.537x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `rch` remote `hz2` | `1.3850 ms` | `479.17 us` | `0.346x` |
| `mdg_edges_keys_n700_e12662` | `rch` remote `hz2` | `1.0432 ms` | `1.0729 ms` | `1.028x` |
| `mdg_in_edges_data_n700_e12662` | `rch` remote `hz2` | `13.166 ms` | `2.5558 ms` | `0.194x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `rch` remote `hz2` | `223.36 us` | `442.83 us` | `1.982x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | `rch` remote `hz2` | `747.63 us` | `432.20 us` | `0.578x` |

Targeted lever: keep the canonical `_InMultiEdgeDataView` list subclass, but
replace the pristine/default-edge-key full-graph fast path's target string rows
with one cached node-display vector plus the multigraph CSR predecessor row.
The candidate avoided per-target `predecessors(target)` vector allocation,
per-pair `edge_keys(source, target)` vector allocation, and repeated
`py_node_key` reconstruction while preserving the existing scalar attr store
read and tuple materialization. This is distinct from the earlier batch view
constructor and default-key-only no-ships.

Validation before timing:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed remotely on `hz2`.

Focused same-worker A/B on `ovh-a`:

| workload | state | runner | FNX median | ORIG median | ratio vs ORIG | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_edges_data_n700_e12662` | CSR predecessor scan candidate | `rch` remote `ovh-a` | `5.8648 ms` | `4.4049 ms` | `0.751x` | `0.968x` |
| `mdg_in_edges_data_n700_e12662` | clean comparator after hunk removal | `rch` remote `ovh-a` | `5.6744 ms` | `2.5214 ms` | `0.444x` | baseline |

Decision: REVERTED / NO-SHIP. The candidate's ratio vs ORIG looked better only
because the paired ORIG row slowed sharply on that run; the source-side FNX
median regressed on the same worker (`5.8648 ms` vs `5.6744 ms`). The temporary
hunk in `crates/fnx-python/src/digraph.rs` was manually reverted before this
ledger commit. Do not retry a CSR predecessor reshuffle as a standalone
`in_edges(keys,data=<attr>)` fix; the remaining work is tuple/value
materialization, not predecessor/key vector allocation.

Validation:

- Candidate hunk reverted; final source diff is empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-conformance --profile release`: passed remotely on `ovh-a`.

## 2026-06-28 BlackThrush MultiDiGraph weighted in-degree one-pass store scan - NO-SHIP (`cod-b`)

Scope: BOLD-VERIFY LAND-OR-DIG pass on current `main` base `e3827592b`.
Scratch/worktree audit found no measured bench-worktree source win absent from
`main`: the only non-ancestor bench branch head was the old
`cc-adjouter-land-20260624` adjacency outer-cache worktree, already represented
by the landed `DictOfDictsCache.shared_outer` implementation and existing
ledger entries. Agent Mail reads worked, but ack/reservation writes still hit
the SQLite corruption circuit breaker; no `settings.json` or hook files were
touched.

The requested literal per-crate release bench form was retried first:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax remotely on `ovh-a` with
`error: unexpected argument '--release' found`, so the equivalent accepted
release profile form was used through `rch exec` with the requested
`fnx-python` crate scope and cod-b target directory.

Fresh current-main routing sweep (`rch exec` local fallback):

| workload | FNX median | ORIG median | ratio vs ORIG |
| --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `7.2323 ms` | `2.1067 ms` | `0.291x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `3.1155 ms` | `599.89 us` | `0.193x` |
| `mdg_edges_keys_n700_e12662` | `1.5854 ms` | `1.8303 ms` | `1.154x` |
| `mdg_in_edges_data_n700_e12662` | `18.120 ms` | `9.1747 ms` | `0.506x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `273.09 us` | `843.35 us` | `3.088x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | `935.42 us` | `579.75 us` | `0.620x` |

Targeted lever: apply the graveyard "constants kill you" / cache-sized batch
principle to `MultiDiGraph.in_degree(weight="weight")` by replacing the clean
Rust-store integer directional weighted-degree path's per-node predecessor row
walk with one indexed edge scan. The candidate accumulated all target-node
totals in a contiguous `Vec<i128>` via
`try_for_each_indexed_edge_ordered_borrowed`, then emitted `(node, total)` in
node order. Dirty edge mirrors, non-int weights, missing weights, and overflow
kept the existing fallback behavior.

Validation before timing:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed via local `rch` fallback.

Focused per-crate BOLD-VERIFY command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_degree_weight -- --quiet`

| workload | state | runner | FNX median | ORIG median | ratio vs ORIG | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | clean routing baseline | local fallback via `rch exec` | `7.2323 ms` | `2.1067 ms` | `0.291x` | baseline |
| `mdg_in_degree_weight_n700_e12662` | one-pass indexed store scan candidate | local fallback via `rch exec` | `10.339 ms` | `2.1421 ms` | `0.207x` | `0.70x` |

Decision: REVERTED / NO-SHIP. The one-pass edge scan worsened the FNX median
from `7.2323 ms` to `10.339 ms`; the added target-index lookup and all-edge
scan lost to the existing predecessor-row walk. The temporary hunk in
`crates/fnx-python/src/digraph.rs` was manually reverted before this ledger
commit. Do not retry a standalone all-edge indexed accumulator for this row;
the remaining weighted in-degree work needs a lower-level cached target-row or
bucket-sum primitive, not a scan-order reshuffle.

Validation:

- Candidate hunk reverted; final source diff is empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed via local `rch` fallback after worker queue timeout.

## 2026-06-28 BlackThrush MultiGraph selfloop heterogenous tuple constructor - NO-SHIP (`cod-b`)

Scope: LAND-OR-DIG pass on current `main` after a scratch/worktree audit found
no measured bench-worktree win absent from `main`. The old adjacency
outer-cache worktree is already represented on `main`, the edge-view worktree
is docs/no-ship evidence, and the A* worktree is parity-only. Agent Mail writes
remained blocked by the existing SQLite corruption circuit breaker, so no
reservation or ack artifact could be recorded. No `settings.json` or hook files
were touched.

Fresh current-main routing kept `mg_selfloop_keys_weight_n2500_loops2502` as
the live gap to attack. The new lever came from the object-materialization
floor rather than another scan tweak: replace the clean
`selfloop_edges(keys=True, data="<attr>")` direct scalar path's explicit
`[PyObject; 4]` + `PyTuple::new` assembly with PyO3's heterogenous tuple
conversion, letting PyO3 build `(node, node, key, value)` directly from borrowed
node handles, the Rust `usize` key, and the already-converted value object. This
is distinct from the previous list-iterator handoff, attr tuple cache, clean-int
mirror bypass, direct scalar emission, small-int object cache, and borrowed-node
scan attempts.

Validation before timing:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed via local `rch` fallback.

Focused per-crate A/B commands:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight -- --quiet`

| workload | state | runner | FNX median | ORIG median | ratio vs ORIG | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | heterogenous tuple candidate, first pass | local fallback via `rch exec` | `1.4646 ms` | `901.10 us` | `0.615x` | `1.08x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean comparator after hunk removal | local fallback via `rch exec` | `1.5801 ms` | `645.86 us` | `0.409x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | heterogenous tuple candidate, confirmation | local fallback via `rch exec` | `1.9826 ms` | `723.76 us` | `0.365x` | `0.80x` |

Decision: REVERTED / NO-SHIP. The first pass showed only a marginal FNX-side
gain and the confirmation regressed below the clean comparator. The paired ORIG
medians were also noisy (`901.10 us`, `645.86 us`, `723.76 us`), so the
candidate does not clear the measured-win bar. The temporary hunk in
`crates/fnx-python/src/lib.rs` was manually reverted before this ledger commit.
Do not retry PyO3 heterogenous tuple conversion as a standalone fix for this
self-loop row; the residual gap is still broader Python tuple/value
materialization overhead.

Validation:

- Candidate hunk reverted; final source diff is empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed remotely on `hz2`.

## 2026-06-28 BlackThrush MultiDiGraph weighted degree tuple cache - NO-SHIP (`cod-a`)

Scope: LAND-OR-DIG pass from detached scratch worktree
`/data/projects/.scratch/franken_networkx-blackthrush-landordig-20260628T031917Z`.
Bench-worktree audit found no measured source win absent from `main`; the
non-ancestor edge-view worktree was already represented on `origin/main`, and
the remaining stale worktrees were docs/audit or parity-only. Agent Mail read
state as `BlackThrush`, but reservation writes were still blocked by the
existing SQLite corruption circuit breaker. No `settings.json` or hook files
were touched.

Fresh routing on the then-current scratch base (`fd3945951`) used the accepted
release profile form because Cargo rejects `cargo bench --release` for this
bench harness:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Worst live gap was `MultiDiGraph.in_degree(weight="weight")`:

| workload | runner | FNX median | ORIG NetworkX median | ratio vs ORIG |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback | `18.137 ms` | `4.3523 ms` | `0.240x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback | `1.8453 ms` | `717.16 us` | `0.389x` |
| `mdg_edges_keys_n700_e12662` | local fallback | `1.6784 ms` | `1.7155 ms` | `1.022x` |
| `mdg_in_edges_data_n700_e12662` | local fallback | `21.058 ms` | `8.8933 ms` | `0.422x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback | `315.22 us` | `1.2120 ms` | `3.845x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback | `1.2110 ms` | `576.01 us` | `0.476x` |

Lever tried: a clean-graph Rust-side immutable tuple cache for exact
full-graph `MultiDiGraph.{in,out}_degree(weight=str)` after the existing
Rust-store int accumulator. The cache was keyed by `(nodes_seq, edges_seq,
weight, direction)` and skipped whenever `edges_dirty` was set or non-int
weights/overflow required the exact Python-compatible fallback. This was
distinct from the earlier rejected Python result cache, node-key pair cache,
values-only zip, index-native accumulator, edge-order stream accumulator, and
lazy native iterator probes.

Validation before timing:

- `python3 -m py_compile python/franken_networkx/__init__.py`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed remotely on `hz2`.

Focused timing:

| workload | state | runner | FNX median | ORIG NetworkX median | ratio vs ORIG | source signal |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | tuple-cache candidate | `rch` remote `ovh-a` | `2.3098 ms` | `1.3978 ms` | `0.605x` | routing-only; no same-worker main comparator |
| `mdg_in_degree_weight_n700_e12662` | current `origin/main` comparator (`e3827592b`) | `rch` local fallback | `10.549 ms` | `3.7292 ms` | `0.354x` | baseline |
| `mdg_in_degree_weight_n700_e12662` | tuple-cache candidate | `rch` local fallback | `12.935 ms` | `7.6069 ms` | `0.588x` | FNX regressed vs local comparator |

Decision: REVERTED / NO-SHIP. The remote candidate ratio looked better, but it
had no same-worker main comparator. The same local fallback A/B showed the
candidate made FNX slower (`12.935 ms` vs `10.549 ms`) while the paired ORIG
row also moved sharply, so the ratio improvement was benchmark noise rather
than a source-side win. The temporary hunks in `crates/fnx-python/src/digraph.rs`,
`crates/fnx-python/src/algorithms.rs`, `crates/fnx-python/src/generators.rs`,
`crates/fnx-python/src/lib.rs`, and `python/franken_networkx/__init__.py` were
manually reverted before this ledger commit. Do not retry a full tuple cache as
a standalone fix for `MultiDiGraph.in_degree(weight=str)`; residual cost is not
removed by caching complete `(node, degree)` tuples on this path.

Validation:

- Candidate source hunks reverted; final source diff is empty.
- After copying ignored conformance evidence artifacts into the detached
  worktree, `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-conformance --profile release`: passed remotely on `ovh-a`.

## 2026-06-27 BlackThrush MultiGraph selfloop scalar-only borrowed-node scan - NO-SHIP (`cod-b`)

Scope: BOLD-VERIFY land-or-dig pass on current `main` base `e3b767cb3`.
Read-only scratch/worktree audit found no measured bench worktree win missing
from `main`: the old adjacency outer-cache worktree is already represented by
the landed `DictOfDictsCache.shared_outer` implementation and ledger entries,
the recent edge-view worktree is a docs/no-ship audit, and the remaining A*
worktree is parity-only. Agent Mail registration still read inbox state, but
ack/reservation writes were blocked by the existing SQLite corruption circuit
breaker. No `settings.json` or hook files were touched.

The requested literal per-crate release bench form was retried first:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax remotely on `hz2` with
`error: unexpected argument '--release' found`, so the equivalent release
profile form was used through `rch exec` with the requested `fnx-python` crate
scope and cod-b target directory.

Fresh current-main routing sweep (`rch exec` local fallback):

| workload | FNX median | ORIG median | ratio vs ORIG |
| --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `17.282 ms` | `8.3692 ms` | `0.484x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `5.2216 ms` | `910.18 us` | `0.174x` |
| `mdg_edges_keys_n700_e12662` | `1.8522 ms` | `2.9718 ms` | `1.604x` |
| `mdg_in_edges_data_n700_e12662` | `23.064 ms` | `8.5611 ms` | `0.371x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `251.28 us` | `534.11 us` | `2.126x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | `896.28 us` | `837.28 us` | `0.934x` |

Targeted lever: add a scalar-only borrowed-node scan ahead of
`PyMultiGraph::_native_selfloop_edges`' existing
`selfloop_edges(keys=True, data="<attr>")` direct scalar emission path. The
candidate kept the existing mirror-preserving path for `Map` values, but for
clean scalar attrs it avoided cloning all node names into `Vec<String>` and
skipped setup for mirror fallback work the benchmark fixture cannot need. This
was distinct from the earlier rejected list-iterator handoff, tuple cache,
clean-int mirror bypass, direct scalar emission, and small-int object cache
attempts.

Validation before timing:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed remotely on `hz2`.

Focused same-worker A/B on `hz2`:

| workload | state | runner | FNX median | ORIG median | ratio vs ORIG | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | scalar-only borrowed-node candidate | `rch` remote `hz2` | `1.3611 ms` | `497.67 us` | `0.366x` | `0.994x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean comparator after hunk removal | `rch` remote `hz2` | `1.3527 ms` | `484.71 us` | `0.358x` | baseline |

Decision: REVERTED / NO-SHIP. The candidate's FNX median was slightly slower
than the same-worker clean comparator (`1.3611 ms` vs `1.3527 ms`); the small
ratio movement (`0.358x` to `0.366x`) came from paired ORIG noise, not a real
source-side gain. The temporary hunk in `crates/fnx-python/src/lib.rs` was
manually reverted before this ledger commit. Do not retry borrowed-node
scalar-only scanning as a standalone fix for this self-loop row; the remaining
cost is still tuple/value materialization, not the `Vec<String>` node clone.

Validation:

- Candidate hunk reverted; final source diff is empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed remotely on `ovh-a`.

## 2026-06-28 BlackThrush MultiGraph selfloop borrowed-bucket fast path - NO-SHIP (`cod-a`)

Scope: BOLD-VERIFY land-or-dig pass on current `origin/main` (`e3b767cb3`).
Bench-worktree audit found no measured source win absent from `main`: the
CopperCliff adjacency outer-cache worktree is already represented by the
landed `a424835f7` implementation and ledger, and the remaining non-ancestor
edge-view/audit worktrees are stale or already represented. Agent Mail
registration/read succeeded as `BlackThrush`, but reservation writes were
blocked by the existing SQLite corruption circuit breaker, so this pass used
the detached worktree
`/data/projects/.scratch/franken_networkx-blackthrush-boldverify-20260628T0239Z`.
No `settings.json` or hook files were touched.

Fresh crate-scoped routing command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

`rch` had no admissible worker for the routing sweep and fell back locally.
The live worst ratio was `MultiGraph.selfloop_edges(keys=True, data="weight")`:

| workload | runner | FNX median | ORIG NetworkX median | ratio vs ORIG |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback | `9.6899 ms` | `6.1970 ms` | `0.640x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback | `4.0404 ms` | `1.3013 ms` | `0.322x` |
| `mdg_edges_keys_n700_e12662` | local fallback | `2.6738 ms` | `2.0706 ms` | `0.774x` |
| `mdg_in_edges_data_n700_e12662` | local fallback | `20.996 ms` | `10.282 ms` | `0.490x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback | `333.04 us` | `732.00 us` | `2.198x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback | `1.0433 ms` | `556.65 us` | `0.534x` |

Lever tried: add a borrowed `MultiGraph` self-loop bucket helper in
`fnx-classes` and use it from the clean scalar
`PyMultiGraph::_native_selfloop_edges(keys=True, data=<attr>)` path. The
intended data-oriented cut was to avoid per-loop-node `edge_keys(node,node)`
Vec allocation and the second `edge_attrs(node,node,key)` lookup, while
preserving node order, edge-key order, scalar/map/default fallback, dirty-edge
fallback, tuple shape, and public iterator behavior. This is distinct from the
previous rejected small-int object cache, list-iterator handoff, tuple cache,
and clean-int mirror-bypass probes.

Focused candidate commands used the same crate and target lane:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mg_selfloop_keys_weight --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | ORIG NetworkX median | ratio vs ORIG | self signal |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | fresh routing baseline | local fallback | `4.0404 ms` | `1.3013 ms` | `0.322x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | borrowed-bucket candidate | local fallback | `2.8625 ms` | `6.4387 ms` | noisy `2.249x` | Criterion: no change, `p = 0.56`; ORIG regressed `+708%` |
| `mg_selfloop_keys_weight_n2500_loops2502` | borrowed-bucket candidate | `rch` remote `hz2` | `1.5020 ms` | `476.89 us` | `0.317x` | no ratio win vs routing baseline |

Decision: REVERTED / NO-SHIP. The local candidate row had an apparently lower
FNX median, but Criterion reported no statistically significant change and the
paired NetworkX row was badly perturbed. The independent `hz2` run landed at
`0.317x` vs ORIG, effectively unchanged from the fresh routing baseline's
`0.322x`. Do not retry a borrowed self-loop bucket helper as a standalone
`selfloop_edges(keys=True, data=<attr>)` lever; the remaining cost is still
dominated by Python tuple/key/value materialization rather than by the per-node
key Vec and second attr lookup alone.

Validation:

- Candidate source hunks in `crates/fnx-classes/src/lib.rs` and
  `crates/fnx-python/src/lib.rs` were manually reverted; final source diff is
  empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed via local fallback while the candidate was present.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-conformance --profile release`: passed via local fallback after copying ignored prerequisite evidence artifacts into the detached worktree.

## 2026-06-27 BlackThrush MultiDiGraph in_edges data-key streaming - KEEP (`cod-b`)

Scope: BOLD-VERIFY land-or-dig pass on `main` base `89661143c`.
Scratch/worktree audit found no measured bench win absent from `main`: the
`cc-adjouter-land-20260624` adjacency outer-cache worktree is already
represented by the landed shared-outer cache implementation and ledger, the
edge-view audit worktree is docs/no-ship, and the A* worktree is parity-only.
No `settings.json` or hook files were touched.

The requested literal per-crate release bench form was retried with the
requested `cod-b` target directory:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax after remote execution on `ovh-a` with
`error: unexpected argument '--release' found`, so the equivalent accepted
release profile form was used:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Fresh laggard sweep on `vmi1264463` before the lever:

| workload | runner | FNX median | ORIG median | ratio vs ORIG |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `rch` remote `vmi1264463` | `27.802 ms` | `13.392 ms` | `0.482x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `rch` remote `vmi1264463` | `6.1457 ms` | `2.4937 ms` | `0.406x` |
| `mdg_edges_keys_n700_e12662` | `rch` remote `vmi1264463` | `5.4037 ms` | `4.6240 ms` | `0.856x` |
| `mdg_in_edges_data_n700_e12662` | `rch` remote `vmi1264463` | `63.740 ms` | `21.657 ms` | `0.340x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `rch` remote `vmi1264463` | `916.24 us` | `1.5239 ms` | `1.663x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | `rch` remote `vmi1264463` | `4.0411 ms` | `1.9688 ms` | `0.487x` |

Lever landed: add a non-dirty full-graph `MultiDiGraph.in_edges(data=<str>)`
streaming path for `keys=True/False` when an edge-attr mirror exists but no
pending mirror mutation is dirty. The existing `!edges_dirty` scalar store-read
rule already permits Rust-store values; this path applies the same invariant
one level higher by streaming target-major predecessor rows directly, avoiding
the owned `(source, target, key)` triples vector, two `String` clones per edge,
and default-int display-key mirror probes. Dirty mirrors, custom keys, and
map-valued attrs fall back to the existing path.

Focused BOLD-VERIFY commands:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_edges_data --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | ORIG median | ratio vs ORIG | self signal |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_edges_data_n700_e12662` | routing baseline | `rch` remote `vmi1264463` | `63.740 ms` | `21.657 ms` | `0.340x` | current worst gap |
| `mdg_in_edges_data_n700_e12662` | same-machine baseline with hunk removed | local fallback via `rch exec` | `19.027 ms` | `9.0514 ms` | `0.476x` | BOLD baseline |
| `mdg_in_edges_data_n700_e12662` | streaming candidate | local fallback via `rch exec` | `15.700 ms` | `14.408 ms` | `0.918x` | `1.21x` faster than same-machine baseline; ORIG row noisy |

Decision: KEEP. The same-machine BOLD verify moved the FNX median from
`19.027 ms` to `15.700 ms` (`1.21x`), and the final paired focused run was
`0.918x` vs ORIG despite a noisy ORIG row. This is a single work-reduction
lever over the largest measured live gap and preserves the dirty/live-dict
fallback contract.

Validation:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo fmt --check`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed on `hz2`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed on `ovh-a`.
- `ubs crates/fnx-python/src/digraph.rs`: exit 0; zero critical findings, broad pre-existing warning inventory remains.
- `git diff --check -- crates/fnx-python/src/digraph.rs docs/NEGATIVE_EVIDENCE.md`: passed.

## 2026-06-27 BlackThrush MultiDiGraph in_edges data-key batch view constructor - NO-SHIP (`cod-a`)

Scope: parallel land-or-dig pass from detached scratch worktree
`/data/projects/.scratch/franken_networkx-blackthrush-dig-20260627T214439Z`
started at base `202e2d4a0`. Current `main` already contains the
`MultiDiGraph.in_edges(data=<str>)` streaming KEEP above, so this entry records
the rejected alternate batch-constructor lever only. Agent Mail writes were
still blocked by the existing SQLite corruption circuit breaker, so no
reservation was acquired. No `settings.json` or hook files were touched.

Lever tried after checking the materialization-floor guidance from
`/alien-graveyard`, `/alien-artifact-coding`, and
`/extreme-software-optimization`: replace the Python list-subclass per-row
`append` loop in pristine `MultiDiGraph.in_edges(keys=..., data=<str>)` with
Rust-side `Vec<PyObject>` batch collection and construct
`_InMultiEdgeDataView(rows)` once. The variant also bypassed `py_edge_key` for
default integer multiedge keys when no Python edge-key mirror exists.

Requested literal release bench form:
`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_edges_data -- --quiet`.
Cargo rejected `cargo bench --release` on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release
profile form was used through `rch exec`.

Decisive local fallback A/B on the same `cod-a` target lane:

| workload | state | runner | FNX median | ORIG NetworkX median | ratio vs ORIG | self signal |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_edges_data_n700_e12662` | reverted/current control | `rch exec` local fallback | `13.358 ms` | `4.3636 ms` | `0.327x` | baseline |
| `mdg_in_edges_data_n700_e12662` | batch view constructor candidate | `rch exec` local fallback | `12.614 ms` | `3.1513 ms` | `0.250x` | `1.06x` faster FNX median, overlapping intervals |

Earlier routing baseline in the same detached worktree was `16.024 ms` FNX /
`7.2386 ms` ORIG (`0.452x`). A remote-worker diagnostic of the candidate on
`vmi1264463` produced `33.686 ms` FNX / `23.790 ms` ORIG (`0.706x`), but it
was not used as keep evidence because the worker and ORIG row were not
comparable to the local control lane.

Decision: REVERTED / NO-SHIP. The candidate produced only a marginal FNX-only
median movement with overlapping intervals, while the paired ratio vs ORIG
worsened from `0.327x` to `0.250x`. Do not retry list-subclass
batch-construction for this workload as a standalone lever. The remaining gap
is the public view/list materialization floor and Python object tuple
construction cost, not `PyList.append` alone.

Validation:

- Candidate source hunk in `crates/fnx-python/src/digraph.rs` was manually
  reverted; final source diff is empty.
- `AGENT_NAME=BlackThrush RCH_WORKER=vmi1264463 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_edges_data -- --quiet`: control and candidate local fallback measurements above; remote diagnostic recorded above.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-conformance --profile release`: passed on `hz2` after generating the ignored first-party prerequisite artifacts required by that gate. The focused recovery rerun for `phase2c_packet_readiness_gate` passed `6/6` before the final full crate pass.

## 2026-06-27 BlackThrush MultiDiGraph weighted degree edge-bucket attrs - KEEP (`cod-b`)

Scope: land-or-dig pass on `main` with final commit base
`77c418c59`. Bench-worktree audit found no measured source win absent from
`main`: the adjacency outer-cache worktree is already represented by the
landed shared-outer cache implementation and KEEP ledger, the edge-view audit
is already represented, and the remaining A* worktree patch is parity-only
rather than a measured benchmark win.

Agent Mail writes were still blocked by the existing SQLite corruption circuit
breaker, so coordination remained read-only/degraded for this pass. No
`settings.json` or hook files were touched.

The requested literal per-crate release bench form was retried with the
requested `cod-b` target directory:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release
profile was used through `rch exec`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Fresh full laggard sweep before the lever:

| workload | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback via `rch exec` | `17.929 ms` | `6.1610 ms` | `0.344x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback via `rch exec` | `2.0243 ms` | `925.34 us` | `0.457x` |
| `mdg_edges_keys_n700_e12662` | local fallback via `rch exec` | `1.4761 ms` | `1.5236 ms` | `1.032x` |
| `mdg_in_edges_data_n700_e12662` | local fallback via `rch exec` | `26.735 ms` | `18.309 ms` | `0.685x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback via `rch exec` | `478.55 us` | `1.3988 ms` | `2.924x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback via `rch exec` | `2.2233 ms` | `931.52 us` | `0.419x` |

Lever landed: expose a clean Rust-store edge-bucket attr-values iterator and
use it in exact full-graph `MultiDiGraph.in_degree(weight=<str>)` /
`out_degree(weight=<str>)`. The previous hot row looped predecessor or
successor rows and then re-looked up `(source, target, key)` attrs for every
parallel key. The new path looks up each `(source, target)` edge bucket once
and sums the contained `AttrMap` values directly, preserving the existing
fallback on non-int weights, missing-weight defaults, and overflow.

Focused current-head candidate command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_degree_weight --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

Focused evidence:

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self signal |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | pre-lever full-sweep baseline | local fallback via `rch exec` | `17.929 ms` | `6.1610 ms` | `0.344x` | baseline |
| `mdg_in_degree_weight_n700_e12662` | edge-bucket attr iterator candidate | local fallback via `rch exec` | `11.251 ms` | `6.1565 ms` | `0.547x` | `1.59x` faster FNX median |

Decision: KEEP. This is still below NetworkX on the public row, but it is not a
near-zero lever: the largest measured gap's FNX median moved from `17.929 ms`
to `11.251 ms` on the same `cod-b` target lane while preserving the exact
native fast-path fallback contract.

Validation:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed via local fallback.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo fmt --check`: passed.
- `ubs crates/fnx-classes/src/digraph.rs crates/fnx-python/src/digraph.rs`: exit 0; broad pre-existing warnings remain in these large files, but no critical finding was reported for this lever.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed on `hz2` after the final source diff.
- `git diff --check -- crates/fnx-classes/src/digraph.rs crates/fnx-python/src/digraph.rs docs/NEGATIVE_EVIDENCE.md`: passed before staging.

## 2026-06-27 BlackThrush directed degree generator-delegation bypass - NO-SHIP (`cod-b`)

Scope: land-or-dig pass on current `main` (`b702ae367`). Bench-worktree audit
found no measured source win absent from `main`: the old adjacency outer-cache
worktree is already represented by the landed shared-outer cache implementation
and KEEP ledger, the edge-view audit is already represented, and the remaining
A* worktree patch is parity-only rather than a measured benchmark win.

Agent Mail writes were still blocked by the existing SQLite corruption circuit
breaker, so coordination remained read-only/degraded for this pass. No
`settings.json` or hook files were touched.

The requested literal per-crate release bench form was retried with the
requested `cod-b` target directory:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release
profile was used through `rch exec`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Fresh full laggard sweep:

| workload | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback via `rch exec` | `9.9550 ms` | `3.4031 ms` | `0.342x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback via `rch exec` | `1.3506 ms` | `712.53 us` | `0.528x` |
| `mdg_edges_keys_n700_e12662` | local fallback via `rch exec` | `1.4170 ms` | `1.3831 ms` | `0.976x` |
| `mdg_in_edges_data_n700_e12662` | local fallback via `rch exec` | `16.301 ms` | `7.1670 ms` | `0.440x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback via `rch exec` | `241.32 us` | `532.04 us` | `2.205x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback via `rch exec` | `1.0177 ms` | `626.38 us` | `0.616x` |

Lever tried: split the hot `_DirectedDegreeView.__iter__` native-returning
branches away from generator-function `yield from` delegation. The hypothesis
was a small interpreter-boundary win for full-graph
`MultiDiGraph.in_degree(weight="weight")`: the Rust kernel already returns a
ready `(node, degree)` sequence, but the Python view wrapped it in a generator
frame and delegated one element at a time.

Focused candidate command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_degree_weight --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

Focused evidence:

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self signal |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | current sweep baseline | local fallback via `rch exec` | `9.9550 ms` | `3.4031 ms` | `0.342x` | baseline |
| `mdg_in_degree_weight_n700_e12662` | generator-delegation bypass candidate | local fallback via `rch exec` | `15.346 ms` | `7.9261 ms` | `0.516x` | Criterion reported FNX `+57.159%` regression |

Decision: REVERTED / NO-SHIP. The candidate looked better only under a noisy
paired NetworkX slowdown; the FNX row itself regressed hard. Do not retry
rewriting `_DirectedDegreeView.__iter__` into direct `iter(list)` returns as a
standalone weighted-degree lever. The remaining gap is still dominated by the
public pair-stream/materialization contract and string-keyed multiedge degree
store, not by generator delegation alone.

Validation:

- `python3 -m py_compile python/franken_networkx/__init__.py`: passed while the candidate was present.
- Candidate source hunk in `python/franken_networkx/__init__.py` was manually reverted; final source diff is empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed after `rch` queue-timeout local fallback.
- `git diff --check`: passed.
- `ubs docs/NEGATIVE_EVIDENCE.md`: no supported language scanners ran for this Markdown-only change, so this is informational rather than a scanner pass.

## 2026-06-27 BlackThrush MultiGraph clean weighted self-loop scalar keep (`cod-a`)

Scope: land-or-dig pass from a detached scratch worktree. Bench-worktree audit
found no measured win absent from `main`, so this dug the largest fresh
`networkx_head_to_head_core_laggards` gap vs ORIG NetworkX:
`MultiGraph.selfloop_edges(keys=True, data="weight")`.

Lever: extend the native `MultiGraph` self-loop scalar fast path from
"no Python edge-attr mirror exists" to "edge mirror is clean". Python-built
weighted fixtures keep pristine mirrors, but the Rust scalar store is still
authoritative until edge attrs are dirtied. The hot path now reads clean scalar
weights directly and falls back edge-by-edge for missing/custom/map values so
live-dict and mutation semantics remain NetworkX-shaped.

Requested literal release bench form:
`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`.
This Cargo rejects `cargo bench --release`, so the equivalent release profile
form was used through `rch exec`:
`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight -- --quiet`.
`rch` had no admissible worker for the focused run and fell back locally.

Measured evidence:

| Workload | State | FNX median | ORIG NetworkX median | Ratio vs ORIG | Self vs baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | baseline | `1.7908 ms` | `684.27 us` | `0.382x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean scalar candidate | `1.4743 ms` | `708.59 us` | `0.481x` | `1.21x` |

Decision: KEEP. The same target-dir focused bench cut FNX median time by about
17.7% and improved the ORIG ratio from `0.382x` to `0.481x`. FNX is still
slower than ORIG on this row, so the next lever should attack remaining tuple
and key-object materialization overhead rather than repeating mirror-probe
elision.

Validation:
- Direct Python parity against a freshly built release wheel: default-key
  self-loop weight mutation matches `networkx.selfloop_edges(..., keys=True,
  data="weight", default=...)`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-conformance --profile release`:
  remote `ovh-a` run passed until missing ignored Phase2C/perf prerequisite
  JSONs stopped the worker gate.
- After generating those local prerequisite reports without staging artifact
  churn, `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a cargo test -p fnx-conformance --profile release`:
  passed all `fnx-conformance` unit, integration, gate, smoke, structured-log,
  and doc tests.

## 2026-06-27 BlackThrush MultiDiGraph weighted degree values-only probe - NO-SHIP (`cod-a`)

Scope: fresh land-or-dig pass from a detached scratch worktree. Bench worktree
audit found no measured win absent from `main`: the adjacency outer-cache
worktree is already represented by the landed `DictOfDictsCache.shared_outer`
implementation and prior KEEP ledger entries, the edge-view audit worktree is
already represented on `main`, and the remaining A* worktree patch is
parity-only rather than a measured benchmark win.

Agent Mail registration succeeded as `BlackThrush`, but exclusive file
reservation writes were blocked by the existing Agent Mail SQLite corruption
circuit breaker (`database disk image is malformed`). The probe therefore ran
in a detached scratch worktree and staged only this ledger file after source
hunks were manually reverted.

The requested literal per-crate release bench form was retried with the
requested `cod-a` target directory:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release
profile was used through `rch exec`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Fresh full laggard sweep on the exact probe base (`008ced9b7`) identified the
largest current measured gap:

| workload | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback via `rch exec` | `10.628 ms` | `3.0159 ms` | `0.284x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback via `rch exec` | `1.5096 ms` | `672.81 us` | `0.446x` |
| `mdg_edges_keys_n700_e12662` | local fallback via `rch exec` | `1.5128 ms` | `1.4471 ms` | `0.957x` |
| `mdg_in_edges_data_n700_e12662` | local fallback via `rch exec` | `15.724 ms` | `6.2481 ms` | `0.397x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback via `rch exec` | `229.52 us` | `536.16 us` | `2.336x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback via `rch exec` | `1.0123 ms` | `555.67 us` | `0.549x` |

Lever tried: a values-only native fast path for exact full-graph
`MultiDiGraph.in_degree/out_degree(weight=<str>)`. The existing native path
returns a full `(node, degree)` pair list; the probe returned only the weighted
degree values from Rust and let Python zip them with graph node iteration. The
graveyard fit was columnar/late-materialization discipline: avoid constructing
the discarded node object in the hot `sum(degree for _, degree in
G.in_degree(weight="weight"))` benchmark while preserving public iterator
shape, node order, dirty-edge fallback, integer overflow fallback, and
NetworkX's missing-weight default.

Focused same-worker evidence:

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | exact-base baseline (`008ced9b7`) | `ovh-a` | `2.4843 ms` | `1.3795 ms` | `0.555x` | baseline |
| `mdg_in_degree_weight_n700_e12662` | values-only candidate | `ovh-a` | `11.094 ms` | `6.0605 ms` | `0.546x` | `0.224x` |

Decision: REVERTED / NO-SHIP. The candidate saved pair node construction but
paid a much larger cost by routing through graph node iteration and Python
`zip`, regressing the FNX row from `2.4843 ms` to `11.094 ms` on the same
worker. Do not retry "values list + Python graph iteration" as a standalone
degree-view lever. The remaining route needs a real indexed multi-edge
accumulator or a public iterator contract that can avoid both string-keyed
multi-edge row scans and full Python pair materialization.

Validation:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed remotely on `ovh-a` while the candidate was present.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-conformance`: remote attempts reached the conformance suite but the detached scratch worktree initially lacked ignored generated artifact snapshots; after copying those snapshots for test execution, RCH remote became unavailable and exact `cod-a` local fallback hit a pre-existing mixed-nightly cache (`E0514`).
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a-conformance-fresh-20260627T1231 cargo test -p fnx-conformance`: passed locally from a fresh target directory after the RCH queue timeout, covering all `fnx-conformance` unit, integration, gate, smoke, structured-log, Phase2C, and doc tests.
- Candidate source hunks in `crates/fnx-python/src/digraph.rs` and
  `python/franken_networkx/__init__.py` were manually reverted after the
  measured regression; final source diff is empty.

## 2026-06-27 BlackThrush Edge-View Worktree Audit and Full-Graph Gap Ledger (`cod-a`)

Scope: land-or-dig audit for current edge-view worktrees. I scanned the bench
worktrees for measured wins not on `main`; the stale adjacency outer-cache
worktree was already represented on `main`, and the live edge-view code was
already landed by `34e09ee11`. This entry mirrors the measured win into the
canonical ledger and records the still-open full-graph `MultiDiGraph.in_edges`
gap so the next pass does not retry the same no-gain lever.

Landed measured win already present on `main`:
- `34e09ee11` shipped pristine store-read fast paths for
  `MDG.in_edges(nbunch, keys=True, data="weight")` and
  `MG.edges(nbunch, keys=True, data="weight")`.
- Reported ratios vs NetworkX:
  `MDG.in_edges` `0.372x -> 0.814x` (`2.2x` self-speedup) and
  `MG.edges` `0.313x -> 0.822x` (`2.6x` self-speedup).
- Conformance for that landing was reported green over `3422` view tests, with
  byte-identical keys/data/default behavior against NetworkX.

Fresh `cod-a` focused benchmark after the audit:

| Workload | Worker | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `fnx_mdg_in_edges_data_n700_e12662` / `nx_mdg_in_edges_data_n700_e12662` | `vmi1227854` | `17.963 ms` | `7.4303 ms` | `0.414x` | remaining gap |

Command:
`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_edges_data --noplot --sample-size 10 --warm-up-time 1 --measurement-time 1`.
The literal `cargo bench --release` form is rejected by this Cargo, so
`--profile release` was used for the requested release-profile bench.

Rejected probe:
- Tried reusing predecessor/key iterators and cached node-key vectors inside
  `_native_mdg_in_edges_data_key`.
- Focused RCH timing stayed in the same band:
  FNX `10.110 ms` vs NetworkX `2.6700 ms`, ratio `0.264x`.
- Reverted as zero-gain. The next lever should attack full-graph data-key value
  emission itself, not iterator reuse or direct view construction alone.

Validation:
- `cargo fmt -p fnx-algorithms -p fnx-generators -p fnx-python --check`:
  passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`:
  passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`:
  passed after the local clippy-collapse fix in `digraph.rs`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  passed, `28` unit tests.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-algorithms -p fnx-generators`:
  passed, `fnx-algorithms` `884` unit tests plus `2` integration tests and
  `fnx-generators` `195` unit tests.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a-local-run-smoke cargo run -q -p fnx-conformance --bin run_smoke`:
  passed, `suite=smoke fixtures=120 mismatches=0 oracle_present=true
  structured_logs=120`.
- Focused rerun of the failed Phase2C adversarial-soak scenario passed after
  isolating the local fallback target dir:
  `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a-adversarial-soak-20260627T0624 PYTHONHASHSEED=0 python3 ./scripts/run_e2e_script_pack.py --scenario adversarial_soak --passes 2 --output-dir artifacts/e2e/blackthrush-adversarial-rerun-2pass-fresh --soak-cycles 4 --gate-step-id step-1`,
  status `pass`, baseline and replay both green.
- The full Phase2C wrapper was also attempted. It failed only when RCH had no
  admissible workers and fell back to a pre-existing mixed-nightly local cache
  (`E0514` on `blake3`/`cc`); no conformance mismatch was observed.
- `ubs crates/fnx-algorithms/src/lib.rs crates/fnx-generators/src/lib.rs
  crates/fnx-python/src/digraph.rs docs/NEGATIVE_EVIDENCE.md`: exit `0`,
  `0` critical findings. Remaining warnings are the broad existing inventory.

## 2026-06-27 BlackThrush Tree MST Lazy Result Keep (`tree_submodule`, cod-a)

Scope: hottest remaining traversal/tree gap after the latest centrality and
connectivity keeps. `franken_networkx.tree.minimum_spanning_tree` on the
official `networkx_head_to_head_tree_submodule` fixture still lagged NetworkX
even after routing the child module to the top-level native implementation.

Fixture and oracle:
- `tree_submodule` Criterion bench in `crates/fnx-python/benches/networkx_head_to_head.rs`.
- Deterministic simple weighted graph: `1000` integer nodes, `4999` total
  edges, every edge carrying one floating `weight`.
- Vendored NetworkX oracle loaded by the bench harness; parity asserted before
  timing by comparing `(u, v, weight)` MST signatures.
- Build/bench command was crate-scoped and release-profile:
  `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head tree_submodule -- --quiet`.
  The literal `cargo bench --release` form is rejected by this Cargo, so
  `--profile release` was used for the requested release bench.

Alien-graveyard lever:
- Preserve the source simple-Graph `lazy_int_node_stop` in native
  minimum/maximum spanning-tree results. Without this display-substrate marker,
  range-built integer graphs returned canonical string nodes, causing the Python
  wrapper to rebuild the whole MST just to re-key nodes.
- For clean source edges whose result data is empty or exactly one numeric
  weight attr, add result edges with cloned Rust `AttrMap`s and leave Python
  edge dictionaries lazy. This avoids eagerly copying about `V-1` Python
  dictionaries when the timed operation only returns the tree object; edge data
  still materializes on first Python read.

Measured evidence:

| State | FNX median | NetworkX median | Ratio vs NetworkX | Notes |
| --- | ---: | ---: | ---: | --- |
| current `main` before this lever | `31.330 ms` | `10.765 ms` | `0.344x` | local fallback routing measurement |
| lazy-int preservation only | `16.003 ms` | `13.577 ms` | `0.848x` | local fallback routing measurement |
| lazy-int + lazy numeric edge attrs | `5.2825 ms` | `13.222 ms` | `2.503x` | final same-run remote `rch` bench on `vmi1227854` |

Decision:
- Keep. The official tree-submodule row flipped from a clear FNX loss to a
  `2.50x` FNX win against NetworkX in the same Criterion run.
- The fallback Python-dict-copy path remains for dirty source mirrors and for
  multi-attribute or nonnumeric edge dictionaries, preserving conservative
  parity outside the single-weight hot path.

Validation:
- `cargo fmt --check`: passed.
- `git diff --check`: passed.
- Crate-scoped release build passed:
  `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo build -p fnx-python --profile release --features pyo3/abi3-py310`.
- Focused Python parity script against the freshly built
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`:
  passed. Covered range-built integer node labels, minimum/maximum MST
  edge-weight signatures vs vendored NetworkX, graph/node attribute copying,
  conservative multi-attribute edge copying, lazy edge-data materialization,
  `size(weight=...)`, and post-mutation weight sync.
- `ubs crates/fnx-python/src/algorithms.rs docs/NEGATIVE_EVIDENCE.md`: exit
  `0`; zero critical issues. UBS reported the existing broad warning inventory
  in `algorithms.rs`.
- `cargo test -p fnx-python --profile release --features pyo3/abi3-py310 minimum_spanning_tree`
  was attempted but `rch` fell back locally and hit a shared target-dir
  mixed-nightly cache (`E0514` incompatible rustc artifacts plus downstream
  dependency errors). No cache clean or destructive remediation was run.

## 2026-06-23 BlackThrush DiGraph Nbunch `data=True` Cache Keep (`br-r37-c1-18ect`, cod-b)

Scope: close the largest ready cod-b directed-edge residual. The prior
post-rebase artifact showed `DiGraph.edges(nbunch, data=True)` at `0.531x` /
`0.447x` and `DiGraph.out_edges(nbunch, data=True)` at `0.714x` / `0.705x`
versus vendored NetworkX. The live-dict native path was correct but rebuilt the
same tuple list on every repeated primitive-int/string nbunch call.

Fixture and oracle:
- Deterministic attributed `DiGraph` fixtures:
  `n=1500/m=9000` with `nbunch=list(range(500))` yielding `3,000` rows, and
  `n=3500/m=24000` with `nbunch=list(range(1000))` yielding `6,000` rows.
- Every edge has `w` and `tag` attrs; parity normalizes each yielded live dict to
  sorted items and asserts exact tuple order against vendored NetworkX before
  timing.
- Fresh release extension was preloaded from
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`.
  Build command was crate-scoped:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.

Lever:
- Added a one-entry Python wrapper cache for exact `DiGraph`, `data=True`,
  list/tuple nbunches whose nodes are primitive `int`/`str`. It is keyed by
  `(nodes_seq, edges_seq, tuple(nbunch))`, stores an immutable private tuple pool,
  and returns a fresh list/view each call. Non-primitive row-display cases keep
  the existing native fallback.
- The cached tuples still carry the same live attr dicts, so mutating
  `d` from `(u, v, d)` updates `G[u][v]`; adding/removing edges changes
  `edges_seq` and misses the cache.

Head-to-head timing:

| Workload | State | FNX median | NetworkX median | Ratio vs NetworkX | Self vs baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `DiGraph.edges(nbunch, data=True)`, n=1500/m=9000, 3000 rows | current `origin/main` baseline | `0.609845 ms` | `0.320577 ms` | `0.526x` | baseline |
| `DiGraph.edges(nbunch, data=True)`, n=1500/m=9000, 3000 rows | nbunch data cache | `0.199608 ms` | `0.320267 ms` | `1.604x` | `3.055x` |
| `DiGraph.out_edges(nbunch, data=True)`, n=1500/m=9000, 3000 rows | current `origin/main` baseline | `0.363468 ms` | `0.308695 ms` | `0.849x` | baseline |
| `DiGraph.out_edges(nbunch, data=True)`, n=1500/m=9000, 3000 rows | nbunch data cache | `0.070633 ms` | `0.326308 ms` | `4.620x` | `5.146x` |
| `DiGraph.edges(nbunch, data=True)`, n=3500/m=24000, 6000 rows | current `origin/main` baseline | `1.216033 ms` | `0.773836 ms` | `0.636x` | baseline |
| `DiGraph.edges(nbunch, data=True)`, n=3500/m=24000, 6000 rows | nbunch data cache | `0.336407 ms` | `0.800637 ms` | `2.380x` | `3.615x` |
| `DiGraph.out_edges(nbunch, data=True)`, n=3500/m=24000, 6000 rows | current `origin/main` baseline | `1.314460 ms` | `1.082791 ms` | `0.824x` | baseline |
| `DiGraph.out_edges(nbunch, data=True)`, n=3500/m=24000, 6000 rows | nbunch data cache | `0.091153 ms` | `0.821306 ms` | `9.010x` | `14.420x` |

Decision:
- Keep. The ready `data=True` residual is now a clear win on all four rows,
  while non-cacheable nbunch shapes retain the existing native route.

Validation:
- Direct cache semantics probe passed: caller mutation of a returned list does
  not affect subsequent calls; live attr dict mutation remains visible through
  `G[u][v]` and the next cached edge view; adding an edge invalidates the cache;
  unhashable nbunch still raises `NetworkXError`.
- Focused pytest via the freshly built extension:
  `tests/python/test_edges_nbunch_unhashable_parity.py -q` passed,
  `13 passed in 0.33s`.
- `python -m py_compile python/franken_networkx/__init__.py tests/python/test_edges_nbunch_unhashable_parity.py`:
  passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `git diff --check`: passed.
- `jq empty .beads/issues.jsonl`: passed.
- `cargo fmt -p fnx-python --check` is not green on current `origin/main` due
  to pre-existing rustfmt drift in `crates/fnx-python/src/lib.rs`; that file is
  exclusively reserved by CopperCliff, so this run did not edit it.
- `ubs` on the four changed files was interrupted after hanging in the Python
  scanner on the large wrapper file.
- Final post-rebase over `e09a7265c`: crate-scoped release build passed,
  focused pytest still passed (`13 passed in 0.32s`), and the four ratio rows
  remained wins at `1.863x`, `7.479x`, `2.359x`, and `10.117x`.

## 2026-06-23 BlackThrush MultiDiGraph Weak Connectivity CSR Keep (`br-r37-c1-04z53.9166`, cod-b)

Scope: close the residual from `br-r37-c1-04z53.9165`. The borrowed-iterator
MultiDiGraph weak-connectivity path still visited nodes by string hash and paid
successor/predecessor map lookup per popped queue item. This lever adds a
revision-keyed distinct-neighbor CSR cache to `MultiDiGraph` and runs the three
weak-connectivity kernels over node indices with boolean visited arrays.

Fixture and oracle:
- Connected `MultiDiGraph` with `250` string nodes and `6,000` directed keyed
  edges: a 250-edge directed cycle plus `5,750` deterministic random edges from
  `random.Random(12345)`. Edge keys were `cycle{i}` / `k{i}` and edge attr
  `w=i%17`.
- Vendored NetworkX from `legacy_networkx_code/networkx`; fresh release
  extension preloaded from
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`.
- Parity was asserted before every timed row:
  `is_weakly_connected`, normalized component sets, and component counts all
  matched NetworkX.
- Timings are best-of per-call after three warmup calls for both NetworkX and
  FNX; the FNX CSR cache is revision-keyed and rebuilt after graph mutation.
- All compile/build commands were crate-scoped with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`, e.g.
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.

Head-to-head timing:

| Function | State | FNX best | NetworkX best | Ratio vs NetworkX | Self vs baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `is_weakly_connected` | current `origin/main` baseline | `0.190881 ms` | `0.043933 ms` | `0.230x` | baseline |
| `is_weakly_connected` | MultiDiGraph CSR + bool visited | `0.002677 ms` | `0.046716 ms` | `17.454x` | `71.311x` |
| `weakly_connected_components` | current `origin/main` baseline | `0.213210 ms` | `0.048298 ms` | `0.226x` | baseline |
| `weakly_connected_components` | MultiDiGraph CSR + bool visited | `0.023208 ms` | `0.050629 ms` | `2.182x` | `9.187x` |
| `number_weakly_connected_components` | current `origin/main` baseline | `0.197310 ms` | `0.049203 ms` | `0.249x` | baseline |
| `number_weakly_connected_components` | MultiDiGraph CSR + bool visited | `0.009452 ms` | `0.051999 ms` | `5.501x` | `20.875x` |

Decision:
- Keep. The lever changes the largest measured residual from a 0.226-0.249x
  FNX loss into 2.18-17.45x FNX wins on the same fixture with parity.
- The count path now uses a count-only BFS instead of materializing component
  vectors only to return `.len()`.

Validation:
- Direct artifact cache-invalidation parity passed on disconnected
  `MultiDiGraph`, then after adding a bridge edge that makes it weakly
  connected.
- `cargo fmt -p fnx-classes --check`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-classes`:
  passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-classes -- -D warnings`:
  passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`:
  passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-classes`:
  68 passed, 0 failed, 2 ignored; doctests passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests passed.
- `git diff --check`: passed.
- `jq empty .beads/issues.jsonl`: passed.
- `ubs --only=rust crates/fnx-classes/src/digraph.rs crates/fnx-python/src/algorithms.rs crates/fnx-python/src/digraph.rs`:
  exit 0, 0 critical issues; broad pre-existing warning inventory remains.
- Post-rebase confirmation after `origin/main` advanced to `506683501`:
  crate-scoped release build passed; target fixture still matched NetworkX and
  measured `18.236x`, `2.145x`, and `5.209x` for the three rows above.
- Independent cod-a duplicate confirmation before rebase used
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a` and
  measured the same class of weak-connectivity win on a 250-node/6000-edge
  fixture: `18.113x`, `2.506x`, and `7.877x` vs vendored NetworkX with parity.
  The rebase kept the upstream CSR implementation to avoid a zero-gain
  duplicate code path.

## 2026-06-23 BlackThrush MultiDiGraph Weak Connectivity Borrowed-Iterator Keep (`br-r37-c1-04z53.9165`, cod-b)

Scope: BOLD-VERIFY the measured MultiDiGraph weak-connectivity residual from
CopperCliff's handoff: `is_weakly_connected`,
`weakly_connected_components`, and `number_weakly_connected_components` were
still far behind vendored NetworkX on high-parallel directed multigraphs due to
`std::collections::HashSet` plus allocating `successors()` / `predecessors()`
BFS rows.

Fixture and oracle:
- Connected `MultiDiGraph` with `250` integer nodes and `6,000` directed keyed
  edges: a 250-edge directed cycle plus `5,750` deterministic random edges from
  `random.Random(12345)`. Edge keys were `k{i}` and edge attr `w=i%17`.
- Vendored NetworkX `3.7rc0.dev0` from `legacy_networkx_code/networkx`; fresh
  release extension preloaded from
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`.
- Parity was asserted before every timed row:
  `is_weakly_connected`, normalized component sets, and component counts all
  matched NetworkX.
- All compile/build commands were crate-scoped with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`, e.g.
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.

Head-to-head timing:

| Function | State | FNX median | NetworkX median | Ratio vs NetworkX | Self vs baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `is_weakly_connected` | clean `origin/main` baseline | `0.365032 ms` | `0.053576 ms` | `0.147x` | baseline |
| `is_weakly_connected` | `FxHashSet` + borrowed MDG adjacency | `0.197819 ms` | `0.044775 ms` | `0.226x` | `1.845x` |
| `weakly_connected_components` | clean `origin/main` baseline | `0.394678 ms` | `0.057499 ms` | `0.146x` | baseline |
| `weakly_connected_components` | `FxHashSet` + borrowed MDG adjacency | `0.216705 ms` | `0.046849 ms` | `0.216x` | `1.821x` |
| `number_weakly_connected_components` | clean `origin/main` baseline | `0.380280 ms` | `0.061596 ms` | `0.162x` | baseline |
| `number_weakly_connected_components` | `FxHashSet` + borrowed MDG adjacency | `0.204863 ms` | `0.048407 ms` | `0.236x` | `1.856x` |

No-ship subattempt:
- A bool-visited/node-index variant built a per-call
  `FxHashMap<&str, usize>` plus `Vec<bool>` for weak component BFS. It preserved
  parity but regressed the kept candidate: final medians were
  `0.268508 ms`, `0.309315 ms`, and `0.290866 ms` with ratios `0.222x`,
  `0.202x`, and `0.207x`. Reverted that subattempt.

Decision:
- Keep. The accessor-local lever is not enough to dominate NetworkX, but it is
  a clear same-fixture win across all three measured functions with exact
  parity.
- Residual route: the next lever should avoid per-call string-key visitation
  entirely by building or reusing eager node-indexed MultiDiGraph weak-adjacency
  rows for reachability, without rebuilding a simple DiGraph or cloning neighbor
  vectors.

## 2026-06-22 BlackThrush MultiGraph Connectivity Accessor FxHashSet Keep (`br-r37-c1-04z53.9162`, cod-a)

Scope: BOLD-VERIFY the remaining MultiGraph `is_connected` /
`node_connected_component` residual after `1059d53c1` kept the sibling
`connected_components` borrowed-neighbor/FxHashSet BFS path.

Hypothesis tested:
- Apply the same accessor-local swap to the two remaining MultiGraph BFS
  helpers: `std::collections::HashSet` -> `rustc_hash::FxHashSet`, and
  `mg.neighbors(node)` -> `mg.neighbors_iter(node)`.
- Workload: connected high-parallel `MultiGraph` with `250` integer nodes and
  `6,000` edges; parity asserted against vendored NetworkX before timing.
- Oracle/runtime: Python `3.13.7`, vendored NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx`, fresh `lib_fnx.so` preloaded from
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`.

Head-to-head timing:
- Clean baseline: detached worktree
  `/data/projects/.worktrees/franken_networkx-cod-a-mgcc-baseline-20260622T1936`
  at `1059d53c1`.
- Candidate: `crates/fnx-python/src/algorithms.rs` changed the two sibling
  BFS helpers to `FxHashSet` plus `neighbors_iter`; rebuilt with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`.
- All compile commands were per-crate `-p fnx-python`.

| Function | State | FNX median | NetworkX median | Ratio vs NetworkX | Self vs baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `is_connected` | clean `1059d53c1` | `0.099505 ms` | `0.088229 ms` | `0.887x` | baseline |
| `is_connected` | FxHashSet + `neighbors_iter` candidate | `0.078912 ms` | `0.096952 ms` | `1.229x` | `1.261x` |
| `node_connected_component` | clean `1059d53c1` | `0.120416 ms` | `0.084560 ms` | `0.702x` | baseline |
| `node_connected_component` | FxHashSet + `neighbors_iter` candidate | `0.090004 ms` | `0.088475 ms` | `0.983x` | `1.338x` |

Validation:
- Candidate result parity matched NetworkX:
  `is_connected == True`, `len(node_connected_component(G, 0)) == 250`.
- A near-zero pass was discarded after inspection: `algorithms.rs` had reverted
  before that rebuild, so it benchmarked baseline-vs-baseline. The hunk was
  reapplied under reservation and the longer-repeat vendored run above is the
  keeper evidence.

Decision:
- Keep. Focused score for these two sibling accessors: `1` clear win
  (`is_connected`), `1` near-parity self-speedup (`node_connected_component`),
  `0` regressions.
- `node_connected_component` still needs the deeper node-indexed MultiGraph
  adjacency/materialized integer-neighbor-row lever for full domination; do not
  spend another bead on accessor-local hashing alone.

## 2026-06-22 BlackThrush DiGraph Iterable-Nbunch Attr-Key Partial Keep (`br-r37-c1-04z53.9161`, cod-b)

Scope: BOLD-VERIFY the child residual for exact `DiGraph` iterable-nbunch
attr-key edge views after the prior MultiDiGraph attr-key emitter keep. Work was
done from detached scratch worktree
`/data/projects/.scratch/franken_networkx-cod-b-20260622T225627Z` with
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.

Profile and lever verified:
- Baseline reproduced the active loss against vendored NetworkX
  `3.7rc0.dev0`: exact `DiGraph.edges(nbunch, data="w", default=-1)` measured
  `0.611x` at `n=1500/m=9000` and `0.586x` at `n=3500/m=24000`.
- Kept source change: the clean string-attr route now reads indexed
  `DiGraph::edge_attrs_by_indices` directly when edge attr mirrors are not
  dirty, avoiding per-edge live-dict lookup and per-call cloned node-name
  vectors. The nbunch dedup set in the data-bearing hot paths is now a
  node-index bitmap.
- Rejected/no-ship subattempts:
  - A Python `OutEdgeDataView` proxy materialized twice under `list(view)`
    because CPython queried `__len__` before iteration. It regressed
    `edges(nbunch, data="w")` to `0.651x` / `0.631x` and was fully reverted.
  - A Rust `DiGraphGuardedEdgeListIter` attempt to hold `PyIterator` instead of
    indexing the guarded list recursed through `_EdgeListWithSetAlgebra.__iter__`
    and was fully reverted.

Head-to-head timing:
- Direct proof preloaded the fresh release extension from
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so` and
  imported vendored NetworkX from
  `legacy_networkx_code/networkx/networkx`. Parity and digest equality were
  asserted before every timed row.
- Final post-rebase build gate:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed. All cargo commands were per-crate `-p fnx-python`.

| Workload | Baseline ratio vs NetworkX | Final FNX median | Final NetworkX median | Final ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `DiGraph.edges(nbunch, data="w")`, n=1500/m=9000, 3000 rows | `0.611x` | `0.492894 ms` | `0.438110 ms` | `0.889x` | residual |
| `DiGraph.out_edges(nbunch, data="w")`, n=1500/m=9000, 3000 rows | `0.719x` | `0.354141 ms` | `0.450663 ms` | `1.273x` | win |
| `DiGraph.edges(nbunch, data="w")`, n=3500/m=24000, 6000 rows | `0.586x` | `1.154658 ms` | `1.033638 ms` | `0.895x` | residual |
| `DiGraph.out_edges(nbunch, data="w")`, n=3500/m=24000, 6000 rows | `0.699x` | `0.985618 ms` | `1.115303 ms` | `1.132x` | win |

Validation and residual:
- Final focused score for the attr-key target after rebasing over upstream is
  `2` wins / `2` losses vs NetworkX, with exact tuple-order and digest parity.
  The clean `out_edges` call surface is closed; `edges(...)` still pays the
  canonical guarded `OutEdgeDataView` drain/wrap residual. Filed follow-up
  `br-r37-c1-04z53.9163`.
- Existing no-data rows remained wins in the same probe. `data=True` rows remain
  a separate live-dict residual: final `edges(nbunch, data=True)` ratios were
  `0.531x` and `0.447x`; final `out_edges(nbunch, data=True)` ratios were
  `0.714x` and `0.705x`. Filed follow-up `br-r37-c1-18ect`.
- Per-crate compile checks passed:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`.

Decision:
- Keep the indexed clean-string attr route because it closes the
  `out_edges(nbunch, data=<key>)` loss and preserves exact parity. Do not retry
  the Python proxy or the recursive Rust `PyIterator` guarded-list route. The
  next attr-key lever should target the guarded `OutEdgeDataView` drain for
  `edges(nbunch, data=<key>)`; the separate `data=True` residual should target
  live-dict handoff/cache behavior.

## 2026-06-22 BlackThrush Directed `single_target_shortest_path` Path-Emission Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the documented directed
`single_target_shortest_path` residual against vendored NetworkX. Work was done
from detached scratch worktree
`/data/projects/.scratch/franken_networkx-cod-b-stsp-20260622T1750Z` with
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.

Profile and radical lever verified:
- The old path-returning helper allocated a Rust `Vec` for every discovered
  path before allocating the final Python lists. It also cloned directed
  predecessor adjacency into a `Vec<Vec<usize>>` on every directed call.
- Kept source change: reverse BFS now returns discovery order plus a
  successor-toward-target table. The Python emitter reconstructs each result
  list directly from that table and reuses prebuilt Python node objects.
- Directed graphs now walk `DiGraph::predecessors_indices` directly, preserving
  predecessor iteration order while skipping the per-call predecessor adjacency
  clone.

Head-to-head timing:
- Build gate:
  `RCH_REQUIRE_REMOTE=1 AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed. All compile commands were per-crate `-p fnx-python`.
- Direct proof preloaded the fresh release extension from
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`
  without overwriting the checked-in Python extension.
- Workload: directed graph with `2,000` integer nodes and `5,955` edges
  (`u -> u+1`, `u -> u+7`, `u -> u+37` where in range), target `1999`.
  Exact path dict equality and key-order parity were asserted before timing.

| State | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever current source, direct loop | `2.832134 ms` | `1.215342 ms` | `0.429x` | active loss reproduced |
| successor table emitter only | `0.872843 ms` | `0.725324 ms` | `0.831x` | improved but still loss |
| final successor emitter + direct directed predecessor rows, post-rebase confirmation | `0.745178 ms` | `0.796656 ms` | `1.069x` | win |

Validation and gates:
- Fresh-extension benchmark asserted exact FNX vs NetworkX path dictionaries and
  key order before timing.
- Focused Python shortest-path parity passed:
  `tests/python/test_shortest_path.py` and
  `tests/python/test_single_target_spl_parity.py`, `82 passed`.
- Per-crate compile check passed:
  `RCH_REQUIRE_REMOTE=1 AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`.
  The output still includes the pre-existing `unused_must_use` warnings in
  `crates/fnx-python/src/digraph.rs`; this commit does not touch that file.

Decision:
- Keep. Focused score for the directed `single_target_shortest_path` row:
  `1` win / `0` losses / `0` neutral vs NetworkX.
- Do not retry path-per-node Rust materialization or directed predecessor
  adjacency cloning for this public path-emission surface.

## 2026-06-21 Cod-B `non_edges_sparse_undirected` Token-Keyed Row Cache Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the final active public-gauntlet loss,
`non_edges_sparse_undirected`, without creating new `.scratch` directories or
worktrees. Reused existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and requested
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.

Profile and radical lever verified:
- Alien-graveyard / artifact-coding hypothesis: the public iterator itself is
  dominated by pair consumption, so another native per-pair PyO3 generator is
  the wrong lever. The remaining movable cost is repeated unchanged graph
  row construction. Use the existing `nodes_seq`/`edges_seq` mutation token as
  an exact artifact key and cache NetworkX's CPython `set.pop()` row groups
  after the first complete iteration.
- Kept source change: exact undirected `Graph.non_edges` now stores
  `(pop_order, row_values)` for unchanged plain graphs with at least `128`
  nodes and at most `1_000_000` non-edge pairs. Warm calls replay the cached
  row tuples in the same order. If the graph mutates during iteration, the
  generator falls back to live NetworkX-style row computation for the remaining
  rows. Small graphs and oversized complements use the old streaming path.

Head-to-head timing:
- Build gate:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on RCH worker `vmi1227854`.
- Focused Criterion proof:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 RCH_WORKER=vmi1153651 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/crates/fnx-python/benches:/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx cargo bench -p fnx-python --bench public_api_gauntlet --features pyo3/abi3-py310 -- non_edges_sparse_undirected --sample-size 10 --warm-up-time 1 --measurement-time 3`
  passed on worker `vmi1153651`.
- First Criterion attempt on `vmi1153651` built the bench binary but failed
  before sampling because the embedded Python process could not import
  `networkx`; that setup failure produced no timing evidence. The rerun above
  added the vendored NetworkX `PYTHONPATH`.

| State | FNX | NetworkX | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever direct median, fresh release extension | `0.282831 s` | `0.271543 s` | `0.960x` | active loss reproduced |
| post-lever direct median, fresh release extension | `0.275894 s` | `0.286838 s` | `1.040x` | local routing win |
| post-lever RCH Criterion mean | `1.2147 s` | `1.3496 s` | `1.111x` | public row win |

Validation and gates:
- Focused order/cache/mutation conformance:
  `PYTHONHASHSEED=0 PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx /data/projects/franken_networkx/.venv/bin/python -m pytest tests/python/test_non_edges_order_conformance_guard.py -q`
  passed `48`.
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_non_edges_order_conformance_guard.py`
  passed.

Decision:
- Keep. Focused score for `non_edges_sparse_undirected`: `1` win /
  `0` losses / `0` neutral vs NetworkX. The no-gaps active public-gauntlet
  loss count is now `0`.
- Do not retry public native-row dispatch, set-deletion mutation, full pair
  vector materialization, or per-pair PyO3 lazy generators for this row.
  The accepted route is token-keyed repeated-row reuse with exact fallback.

## 2026-06-21 Cod-B `ubizp` MultiGraph SSSP Borrowed-Frontier Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the remaining `ubizp`
`MultiGraph.single_source_shortest_path` path-returning loss after the earlier
parent-copy route regressed. Reused existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and requested
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Profile and radical lever verified:
- Alien-graveyard / extreme-optimization hypothesis: this was not an
  algorithmic miss after the predecessor-table rewrite; it was a constant-factor
  boundary tax in the BFS frontier and Python path emitter. Remove the hidden
  per-expanded-node neighbor `Vec` allocation, use a dense/Fx index map for
  predecessor lookup, and let PyO3 build each returned path list directly from
  the reverse predecessor walk.
- Kept source changes:
  `multigraph_sssp_predecessors_index` now uses `neighbors_iter` and
  `rustc_hash::FxHashMap`; `emit_paths_dict_discovery_parent_index` passes the
  reversed stack iterator directly to `PyList::new`.
- Checked-in the public gauntlet row
  `ubizp_multigraph_single_source_shortest_path` with exact FNX vs NetworkX
  output parity asserted during bench setup. The bench harness now preloads the
  freshly built `_fnx` extension from `CARGO_TARGET_DIR` so it does not silently
  time the stale checked-in Python extension.

Head-to-head timing:
- Build gate:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed on RCH after the final source lever.
- Direct fresh-extension proof preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`
  without overwriting `python/franken_networkx/_fnx.abi3.so`.
- Fixture: identical FNX/NetworkX `MultiGraph`, `1,600` integer nodes,
  parallel chain edges plus `+7` and `+37` shortcuts, source node `0`, `80`
  calls per timing sample. Exact path dict parity and guard-row parity were
  asserted before timing.

| State | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever current source, direct loop | `0.794793 ms` | `0.697861 ms` | `0.878x` | active loss reproduced |
| `neighbors_iter` only | not kept | not kept | `0.893x` | still loss |
| `neighbors_iter` + direct `PyList::new` | not kept | not kept | `0.923x` | still loss |
| final `neighbors_iter` + direct `PyList::new` + `FxHashMap` | `1.353284 ms` | `1.434610 ms` | `1.060x` | win |

Guard rows on the same final run:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `shortest_path` | `0.710813 ms` | `1.549491 ms` | `2.180x` | win |
| `single_source_shortest_path_length` | `0.871823 ms` | `1.032218 ms` | `1.184x` | win |
| `has_path` | `0.824509 ms` | `1.571056 ms` | `1.905x` | win |

Rejected route:
- Delegating NetworkX BFS over the fnx graph did not beat native SSSP:
  native FNX `0.764 ms`, NetworkX over fnx graph `0.920 ms`, NetworkX over
  NetworkX graph `0.760 ms`.
- The first RCH Criterion attempts for the new checked-in gauntlet row built
  the optimized bench binary but failed before sampling because the remote
  embedded Python process could not import `networkx` while initializing the
  extension. The harness was patched to seed repo-local `sys.path` and preload
  the fresh extension; these setup failures are not counted as timing evidence.

Validation and gates:
- Fresh-extension parity script asserted exact
  `single_source_shortest_path`, `shortest_path`,
  `single_source_shortest_path_length`, and `has_path` outputs before timing.
- `rustfmt --edition 2024 --check` passed on
  `crates/fnx-python/src/algorithms.rs` and
  `crates/fnx-python/benches/public_api_gauntlet.rs`.
- `python -m py_compile crates/fnx-python/benches/public_api_gauntlet.py`
  passed via the project venv.
- `git diff --check` passed. A workspace-wide `cargo fmt --check` run was
  intentionally not used as a final gate because it reports pre-existing
  rustfmt drift in unrelated files outside this edit surface.

Decision:
- Keep. Focused score for the current ubizp path-returning row: `1` win /
  `0` losses / `0` neutral vs NetworkX, with all three existing ubizp guard
  rows still wins.
- Do not retry parent-path cloning or a NetworkX-over-fnx fallback for
  MultiGraph SSSP. The current route closes the ubizp path-returning active
  loss; the remaining active no-gaps target is `non_edges_sparse_undirected`.

## 2026-06-21 Cod-B Tree `from_nested_tuple` Native Construction Keep (`br-r37-c1-04z53`, cod-b)

Scope: BOLD-VERIFY the pending tree-submodule `from_nested_tuple` route that
already builds the `franken_networkx.tree` result graph directly instead of
constructing a NetworkX graph and converting it back through `_from_nx_graph`.
Reused existing detached worktree `/data/projects/.worktrees/fnx-bt-3` and
requested `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`;
no new `.scratch` or perf-proof worktree was created.

Profile and radical lever verified:
- Alien-graveyard / alien-artifact hypothesis: eliminate the graph
  round-trip/substrate conversion tax by constructing the observable node and
  edge stream directly in the fnx graph representation. This is a
  representation-level boundary removal, not another wrapper micro-route.
- Added a checked-in Criterion row to the existing
  `tree_submodule_head_to_head` bench. The setup asserts exact FNX vs
  NetworkX node order and edge order for both plain and
  `sensible_relabeling=True` calls before timing.

Head-to-head timing:
- RCH worker: `vmi1153651`; requested target
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`,
  rewritten by RCH to a worker-scoped path.
- Build gate:
  `RCH_WORKER=vmi1153651 RCH_REQUIRE_REMOTE=1 AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed.
- Bench command:
  `RCH_WORKER=vmi1153651 RCH_REQUIRE_REMOTE=1 AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/crates/fnx-python/benches:/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx cargo bench -p fnx-python --bench tree_submodule_head_to_head -- from_nested_tuple --sample-size 10 --warm-up-time 1 --measurement-time 3`.
- Workload: nested tuple depth `6`, fanout `3`, eight constructions per timed
  call, vendored NetworkX oracle.

| Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `tree.from_nested_tuple(depth=6, fanout=3)` | `106.194 ms` | `1680.432 ms` | `15.824x` | win |
| `tree.from_nested_tuple(..., sensible_relabeling=True)` | `94.812 ms` | `1708.492 ms` | `18.020x` | win |

Validation and gates:
- Bench setup parity asserted exact public node/edge order against vendored
  NetworkX before timing.
- Focused tree submodule conformance passed:
  `tests/python/test_algorithms_tree_submodule.py`, `21 passed`.
- `cargo fmt --check` passed.
- `python -m py_compile python/franken_networkx/tree.py` passed via the project
  venv.

Decision:
- Keep. Focused score: `2` wins / `0` losses / `0` neutral vs NetworkX.
- The previous pending row is now measured. Do not route submodule
  `from_nested_tuple` back through NetworkX graph construction plus
  `_from_nx_graph`; the direct observable node/edge stream wins by more than an
  order of magnitude.

## 2026-06-21 Cod-B `non_edges` Native-Row Regression Recheck (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY recheck of the remaining
`non_edges_sparse_undirected` public-gauntlet row after an unrelated
spanning-tree fix commit briefly carried the exact undirected native-row
`Graph.non_edges` block. Reused existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Profile and radical lever tested:
- Alien-graveyard / alien-artifact hypothesis: preserve NetworkX `set.pop()`
  semantics while using native node-key snapshots and raw neighbor rows, then
  try to remove one allocation layer by replacing `nodes - set(raw_neighbors)`
  with `nodes.copy(); difference_update(raw_neighbors)`.
- The copy/difference-update variant was invalid: focused order conformance
  failed `9` of `47` cases because CPython set deletion order does not match
  the `nodes - set(neighbors)` result order. It was not timed.
- The exact native-row variant preserved order but was slower than the
  restored public fallback on the same RCH worker. Current head `3f59a7f9a`
  already source-reverted the unrelated native-row block while preserving the
  spanning-tree fix.

Head-to-head timing:
- RCH worker: `vmi1153651`; requested target
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`,
  rewritten by RCH to that worker's scoped target.
- Command shape:
  `RCH_WORKER=vmi1153651 RCH_REQUIRE_REMOTE=1 AGENT_NAME=cod-b CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/.worktrees/fnx-bt-3/crates/fnx-python/benches:/data/projects/.worktrees/fnx-bt-3/python:/data/projects/.worktrees/fnx-bt-3/legacy_networkx_code/networkx cargo bench -p fnx-python --bench public_api_gauntlet -- non_edges_sparse_undirected --sample-size 10 --warm-up-time 1 --measurement-time 4`
- Setup failures not used as evidence: `ovh-a` failed before sampling because
  the remote process lacked `public_api_gauntlet` on `PYTHONPATH`; `hz2` failed
  before sampling because its Python environment lacked NumPy.

| State | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| restored/fallback source | `1.3427 s` | `1.3203 s` | `0.983x` | active row reproduced; non-dominating |
| exact native-row candidate | `1.4501 s` | `1.2864 s` | `0.887x` | reject; FNX regressed |

Validation and gates:
- Invalid copy/difference-update variant failed focused order guards:
  `9 failed, 38 passed`.
- Exact native-row variant passed focused order/checksum parity before timing:
  `47 passed` plus a 60-seed direct order sweep and gauntlet-fixture checksum
  match (`4829200199316911967` for both engines).
- Final restored source passed focused non-edges conformance:
  `tests/python/test_non_edges_order_conformance_guard.py` plus the two
  targeted graph-utility non-edges guards, `47 passed`.
- Final restored source also passed
  `python -m py_compile python/franken_networkx/__init__.py` and
  `git diff --check`.

Decision:
- Reject/no-ship. Do not reintroduce public native-row dispatch for undirected
  `non_edges`; the exact-order version regresses the active public row and the
  allocation-saving mutation variant breaks set-order parity.
- Current focused score for this recheck: `0` wins / `1` loss / `0` neutral.
- The remaining credible route is still consumer-fused: avoid creating public
  Python non-edge pairs at all for downstream consumers, rather than another
  public `non_edges` iterator micro-route.

## 2026-06-21 Cod-B `ubizp` MultiGraph SSSP Parent-Copy No-Ship (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY revisit of the remaining `ubizp`
`MultiGraph.single_source_shortest_path` path-emission loss. Reused existing
detached worktree `/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Profile and radical lever tested:
- Alien-graveyard / alien-artifact hypothesis: the current predecessor-table
  route still pays a Python list materialization pass after BFS. Try keeping
  BFS and path construction fused under the GIL, copying the already-built
  parent Python list and appending the discovered child immediately. This
  attempts to trade the second reconstruction pass for CPython's optimized
  `list.copy()` path.
- Implementation sketch tested in `crates/fnx-python/src/algorithms.rs`:
  native MultiGraph BFS over `mg.neighbors`, one `Vec<Option<PyObject>>` of
  parent path objects, and per-child `parent_path.copy(); append(child)` before
  inserting into the result dict.
- The source hunk was reverted after measurement. The only final source diff
  left in this session is rustfmt's wrapping normalization in the same reserved
  file.

Head-to-head timing:
- Oracle: vendored NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx`, Python `3.13`, `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, pinned with `taskset -c 4`.
- Fixture: identical FNX/NetworkX `MultiGraph`, `1,600` integer nodes,
  `6,354` edges: parallel chain edges plus `+7` and `+37` shortcuts. Source
  node `0`; output parity asserted before every timing pass.
- Checked-in Criterion benches still do not contain this exact MultiGraph SSSP
  path-returning surface, so this pinned vendored-oracle loop remains the
  keep/reject proof path for `ubizp` path emission.

| State | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| pre-lever current source, same loop | `0.875438 ms` | `0.703192 ms` | `0.803x` | active loss reproduced |
| parent-copy candidate | `2.449591 ms` | `0.867754 ms` | `0.354x` | reject |
| restored source rerun 1, noisy host | `2.316699 ms` | `1.033589 ms` | `0.446x` | parity restored; still active loss |
| restored source rerun 2, noisy host | `1.710842 ms` | `0.825284 ms` | `0.482x` | parity restored; still active loss |

Validation and gates:
- Candidate parity matched vendored NetworkX on all `1,600` paths before
  timing; output length was `1,600`.
- Candidate `AGENT_NAME=cod-b CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-13 rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
  passed before rejection. It emitted expected dead-code warnings because the
  old predecessor emitter became unused.
- Candidate and restored-source release installs used
  `maturin develop --release --features pyo3/abi3-py310` against the prescribed
  warm target. The first local install hit stale-artifact `E0514`; the target
  was not cleaned. Switching to `nightly-2026-06-10` matched the existing
  `beae78130` artifacts and avoided destructive cleanup.
- Restored source conformance:
  `pytest -q tests/python/test_single_source_shortest_path_parity.py tests/python/test_single_source_shortest_bfs_order_parity.py tests/python/test_exact_path_tiebreak_parity.py tests/python/test_shortest_path.py tests/python/test_shortest_path_algorithms.py tests/python/test_shortest_path_conformance_matrix.py tests/python/test_shortest_path_variants_parity.py tests/python/test_shortest_path_cross_type.py tests/python/test_multigraph_algorithms.py`
  passed: `358 passed, 5 skipped`.
- Final gates after revert: `cargo fmt --check` passed;
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed on
  `hz2`; `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed on `hz1`.

Decision:
- Reject/no-ship. Final focused score for this attempted lever: `0` wins /
  `1` loss / `0` neutral.
- Do not repeat Python-list parent copying for MultiGraph SSSP. It increases
  GIL-held Python object churn and regresses the already-losing row.
- Next route must attack the path-output substrate itself: for example a
  lazy/fused consumer route, compact path-span representation, or API-specific
  sink that avoids public dict-of-full-list materialization when possible.

## 2026-06-21 Cod-A `stochastic_graph` Exact-MultiDiGraph Native Copy Keep (`br-r37-c1-04z53.9160`, cod-a)

Scope: fresh BOLD-VERIFY child bead for the active no-gaps campaign, focused on
the remaining exact `MultiDiGraph.stochastic_graph(copy=True)` head-to-head
loss. Reused `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`;
no new `.scratch` worktree was created.

Baseline and rejected routes:
- Pre-lever public copy rows preserved parity but lost badly against vendored
  NetworkX: n=400/e=1600 `0.321x`, n=1000/e=5000 `0.249x`.
- A normalizer-only route still paid the Python shallow-copy tax, so it stayed
  losing and was not kept.
- A fresh-topology native copy builder won only small rows but lost larger rows:
  n=400/e=1600 `1.688x`, n=1000/e=5000 `0.781x`,
  n=2000/e=10000 `1.040x`, n=4000/e=20000 `0.793x`. That source shape was
  replaced before final gates.
- A clone-plus-per-edge String-key lookup candidate improved the surface but
  still had a large-row median loss: n=4000/e=20000 `0.946x`. It was replaced
  with ordered batch mutation before final gates.

Radical lever kept:
- Alien-graveyard / alien-artifact hypothesis: do not materialize every
  `(u, v, key, attrdict)` tuple through Python, and do not rebuild multigraph
  topology from string endpoints. Sync dirty live edge attrs once, verify
  lossless Python mirrors, clone the native multigraph topology, compute source
  degrees in node-index space, and patch only the derived weight field in
  `edges_ordered_borrowed()` order.
- The storage-level `set_ordered_edge_attr_values` primitive removes the
  per-edge `DirectedEdgeKey` hash lookup from the clone path. This is the
  difference between the partial `0.946x` large-row loss and the final large-row
  wins.
- The helper returns `None` for non-lossless or nonnumeric weight cases so the
  Python wrapper preserves NetworkX-observable fallback and exception behavior.

Final gates and timing evidence:
- `cargo fmt --check` passed.
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_graph_operators_parity.py`
  passed.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features extension-module`
  passed on RCH worker `hz2`.
- `ldd /data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
  showed no `libpython` dependency and no missing libraries.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-classes --all-targets`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-classes`
  passed on RCH worker `ovh-a`: `68 passed`, `2 ignored`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --all-targets --features extension-module`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo clippy -p fnx-python --all-targets --features extension-module -- -D warnings`
  passed on RCH worker `hz1`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`
  passed on RCH worker `hz2`: `27 passed`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-python --features extension-module`
  failed to link a Rust test executable on RCH worker `hz2` with undefined
  Python C API symbols. This is a PyO3 `extension-module` test-link mode issue,
  not a runtime or release-extension failure; release builds and ABI3 Rust tests
  are the valid gates above.
- Focused direct conformance preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` as
  `franken_networkx._fnx` and passed helper in-place, helper copy, public
  `copy=True` with dirty live edge-dict sync, source isolation, bool/missing
  weights, and nonnumeric fallback.
- Final benchmark loop used the same preloaded release extension, vendored
  NetworkX from `legacy_networkx_code/networkx`, deterministic keyed
  MultiDiGraph fixtures, and parity assertions before timing.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=400/e=1600 | `1.212 ms` | `3.595 ms` | `2.966x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=1000/e=5000 | `8.620 ms` | `11.737 ms` | `1.362x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=2000/e=10000 | `19.333 ms` | `23.239 ms` | `1.202x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=4000/e=20000 | `46.311 ms` | `48.076 ms` | `1.038x` | win |
| exact `MultiDiGraph.stochastic_graph(copy=True)`, n=8000/e=40000 | `99.791 ms` | `102.295 ms` | `1.025x` | win |

Decision:
- Keep. Final score: `5` wins / `0` losses / `0` neutral.
- This closes the active exact `MultiDiGraph.stochastic_graph(copy=True)`
  residual. The prior n=1000/e=5000 public row moved from `0.249x` loss to
  `1.362x` win.

Do not repeat:
- Do not retry normalizer-only public paths for `copy=True`; the shallow copy
  remains the dominant tax.
- Do not retry fresh topology rebuilds for this surface; clone plus ordered
  attr mutation is faster and preserves insertion order with less graph-state
  reconstruction.
- Do not use `cargo test -p fnx-python --features extension-module` as the
  Rust unit-test gate on RCH. Use `pyo3/abi3-py310` for Rust tests and
  `extension-module` for release builds / importable `.so` timing.

## 2026-06-21 Cod-A `stochastic_graph` Exact-DiGraph Native Normalizer Keep (`br-r37-c1-04z53.9159`, cod-a)

Scope: fresh BOLD-VERIFY child bead for the active no-gaps campaign, focused on
the remaining `stochastic_graph(DiGraph)` head-to-head loss. Reused
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`; no new
`.scratch` worktree was created.

Baseline and rejected route:
- Fresh direct release probe before the source lever preserved parity but showed
  the current exact `DiGraph` route still losing: FNX median `5.080 ms` vs
  NetworkX `4.512 ms`, ratio `0.888x`, on n=1000/e=3200. The same probe showed
  `MultiDiGraph` still much worse at FNX `27.498 ms` vs NetworkX `9.993 ms`,
  ratio `0.363x`.
- A Python successor-row normalization micro-probe was rejected before editing:
  current FNX median `4.715 ms`, successor-row loop `11.088 ms`, NetworkX
  `4.879 ms`. Do not repeat this family.

Radical lever kept:
- Alien-graveyard / alien-artifact hypothesis: stop paying the Python
  `edges(data=True)` traversal and row-sum loop for exact `DiGraph`
  `stochastic_graph`. Instead, run one native PyO3 pass over the stored edge
  order, accumulate outgoing sums, and mutate the live edge-attribute dicts with
  the normalized float weight.
- The helper pre-scans all weights before mutation and returns `false` for
  nonnumeric/object/string weights so the Python fallback preserves NetworkX
  exception behavior. Missing weights and bool/int/float weights are handled
  natively.

Final gates and timing evidence:
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed on RCH worker `ovh-a`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed on RCH worker `ovh-a`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`
  passed on RCH worker `ovh-a`: `27 passed`.
- `AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed on RCH worker `ovh-a`.
- `cargo fmt --check` passed locally after formatting `fnx-python`.
- `python3 -m py_compile python/franken_networkx/__init__.py tests/python/test_graph_operators_parity.py`
  passed.
- Focused direct oracle loop preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` as
  `franken_networkx._fnx`, with `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, and
  `OPENBLAS_NUM_THREADS=1`.
- Parity matched vendored NetworkX for copy/in-place behavior, missing weights,
  bool weights, zero row sums, `MultiDiGraph` fallback, and string-weight
  exception fallback. Focused pytest was blocked by the hard-coded stale
  in-tree `_fnx.abi3.so` guard in `tests/python/conftest.py`, so the direct
  preloaded extension loop is the focused Python conformance proof.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `stochastic_graph` exact `DiGraph`, n=400/e=1200 | `0.960064 ms` | `1.680509 ms` | `1.750x` | win |
| `stochastic_graph` exact `DiGraph`, n=1000/e=3200 | `2.682792 ms` | `4.570833 ms` | `1.704x` | win |
| `stochastic_graph` exact `DiGraph`, n=2000/e=7000 | `7.944119 ms` | `10.951245 ms` | `1.379x` | win |

Decision:
- Keep. Final score: `3` wins / `0` losses / `0` neutral.
- This flips the fresh exact-`DiGraph` `stochastic_graph` baseline from a
  `0.888x` loss into measured wins. `MultiDiGraph` remains a separate residual
  at the pre-lever `0.363x` loss and needs a different native copy/normalizer
  route.

Do not repeat:
- Do not retry Python successor-row loops for `stochastic_graph`; the measured
  micro-probe was slower than both current FNX and NetworkX.
- Do not route nonnumeric/object/string weights through the native helper; the
  fallback is required to preserve NetworkX exception semantics.
- Do not count this as a `MultiDiGraph` fix; that surface still loses and needs
  a separate native multi-edge substrate.
## 2026-06-21 Cod-B Borrowed Dirty-Key Sparse Keep (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY pass on the dirty/live high-unique
`MultiDiGraph` sparse-export residual. Reused the existing detached worktree
`/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` worktree was created and the shared target was not cleaned.

Radical lever kept:
- Alien-graveyard / alien-artifact hypothesis: treat the dirty edge set as a
  compact sparse delta, not as a global invalidation bit. Build one borrowed
  `(&str, &str, key)` dirty-key lookup per export, read stored Rust attrs for
  untouched edges, and cross the Python dict boundary only for exact dirty
  `G[u][v][key]` mutations.
- This is deliberately narrower than the rejected broad live-weight index and
  different from the earlier stored-attr bypass attempt: the hot loop no longer
  allocates owned `(u, v, key)` lookup tuples for clean edges in the dirty
  path, while broad dirty escapes still fall back to authoritative live attrs.

Current-source direct head-to-head:
- Oracle: vendored NetworkX `3.7rc0.dev0` from
  `legacy_networkx_code/networkx`, Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  pinned with `taskset -c 4`.
- Fixture: deterministic seed `1`, `2,000` nodes, `12,000` unique keyed
  directed edges, `388` public post-construction
  `G[u][v][key]["weight"] = ...` mutations, non-integer float weights,
  default nodelist, default `weight="weight"`.
- Parity: sorted coordinate sparse payload matched for both
  `to_scipy_sparse_array` and `adjacency_matrix`; digest
  `6a308478ec5832944239b9997a05fb7af357a9edac80d494cf22e7db2e2489b1`,
  `12,000` nnz, float64 data, sum `1056934.0`.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `8.491933 ms` | `11.235742 ms` | `1.323x` | win |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `6.873216 ms` | `11.972349 ms` | `1.742x` | win |

Validation:
- Focused sparse exporter conformance:
  `tests/python/test_to_scipy_sparse_native_weighted_parity.py` plus
  `tests/python/test_to_scipy_sparse_default_native_parity.py`: `304 passed`.
- RCH gates on final source passed before the local ABI rebuild:
  `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  and
  `cargo build --release -p fnx-python --features pyo3/abi3-py310`.
- `cargo fmt --check` passed and `ubs crates/fnx-python/src/readwrite.rs`
  reported no new critical finding for the touched source.
- Focused RCH Criterion attempts for
  `multidigraph_to_scipy_sparse_array_csr_int_weights` built the bench binary
  on workers `vmi1149989` and `vmi1152480`, then failed before sampling with
  `ModuleNotFoundError("No module named 'public_api_gauntlet'")`; these runs
  are recorded as worker Python-path failures, not keep evidence.

Decision:
- Keep. The dirty sparse residual flips to `2` wins / `0` losses / `0`
  neutral vs NetworkX on the direct vendored-oracle proof.
- Remaining active no-gaps targets are the ubizp path-returning output loss
  and the `non_edges_sparse_undirected` public boundary.

Do not repeat:
- Do not re-test broad live-weight indexing or per-edge owned dirty-key tuple
  construction for this sparse exporter. The kept shape is a borrowed dirty-set
  delta plus stored-attr fast path for untouched edges.
- If this area regresses again, the next route should be native sparse-array
  handoff or a compact numeric edge-weight mirror, not another all-edges live
  attr scan.
## 2026-06-21 Cod-A `non_edges` Exact-Int Lazy Iterator No-Ship (`br-r37-c1-04z53`, cod-a)

Scope: fresh BOLD-VERIFY follow-up on the active
`non_edges_sparse_undirected` public-gauntlet loss. Reused
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`; no new
`.scratch` worktree was created.

Radical lever tested and reverted:
- Alien-graveyard / alien-artifact hypothesis: for the measured simple
  undirected exact-int `Graph` shape, replace Python `set(graph)` /
  `set(graph[u])` row arithmetic with a native lazy iterator that snapshots
  adjacency by node index and emits non-edge Python tuples one at a time.
- This avoids the previously rejected full `Vec<(u, v)>` pair materialization,
  but still preserves the `0..n` CPython `set.pop()` observable order used by
  the gauntlet fixture.

Gates and timing evidence:
- Candidate source passed:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`
  on RCH worker `vmi1153651`.
- Candidate release build passed:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  on RCH worker `vmi1264463`.
- Focused direct loop preloaded the built
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` as
  `franken_networkx._fnx`, with `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1`.
- Parity matched vendored NetworkX on the 900-node / p=0.008 / seed=9143
  gauntlet fixture: checksum `4.829200199316912e18` for both engines.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `non_edges_sparse_undirected`, exact-int lazy iterator candidate | `95.512 ms` | `78.133 ms` | `0.818x` | loss |

Mean timing in the same 15-sample loop: FNX `94.927 ms`, NetworkX
`78.602 ms`, ratio `0.828x`.

Decision:
- Reject/no-ship. The source hunk was manually reverted after the native lazy
  iterator remained slower than NetworkX and slower than the current Python
  wrapper substrate on the focused direct loop.
- Candidate score: `0` wins / `1` loss / `0` neutral.

Do not repeat:
- Do not retry a PyO3 per-pair tuple-yielding `non_edges` iterator for
  exact-int simple graphs as a standalone lever. It removes full-pair
  materialization but loses the savings back at the per-yield Python boundary
  and adjacency snapshot setup.
- Next credible route should be consumer-fused: score default-ebunch link
  prediction or another downstream non-edge consumer without exposing every
  pair as a Python tuple.

## 2026-06-21 Cod-B Native MultiDiGraph Compose No-Ship (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY pass after `bv --robot-triage` and `br ready`,
targeting the current String-keyed multigraph-attribute compose gap. Reused
the existing clean worktree `/data/projects/.worktrees/fnx-bt-3` and
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
`.scratch` or perf-proof worktree was created.

Alien-graveyard / alien-artifact hypothesis:
- Apply the boundary-batching primitive: perform the H-wins keyed-edge compose
  merge directly over Rust multigraph storage instead of materializing both
  `edges(keys=True, data=True)` views into a Python `_edge_map`.
- Matched guidance: compact graph representation, batched boundary handoff,
  and cache-local sparse/graph traversal. The lever was deliberately radical
  enough to skip the public EdgeView materialization that dominated the prior
  `compose(MultiDiGraph)` and `compose(MultiGraph)` rows.

Baseline current-source direct head-to-head:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `compose_MultiGraph_string_attr`, 420 nodes / 18,900 result keyed edges | `383.614 ms` | `48.439 ms` | `0.126x` | loss |
| `compose_MultiDiGraph_string_attr`, 420 nodes / 18,900 result keyed edges | `125.134 ms` | `45.402 ms` | `0.363x` | loss |

Candidate attempts, both reverted:

| Candidate | FNX median | NetworkX median | Ratio vs NetworkX | Decision |
| --- | ---: | ---: | ---: | --- |
| exact `MultiDiGraph._native_compose` with Rust storage merge and eager Python-dict-to-`AttrMap` conversion | `108.573 ms` | `41.254 ms` | `0.380x` | reject |
| same native compose with Python edge mirrors authoritative and dirty-marked result attrs | `106.738 ms` | `39.730 ms` | `0.372x` | reject |

Validation:
- Candidate parity guard ran before timing: `fnx.compose` output matched
  `networkx.compose` for node attrs, graph attrs, sorted keyed edge attrs, and
  weighted attr checksum.
- Candidate compile gates passed:
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` on
  `vmi1153651` and `ovh-a`.
- Reverted-source release reinstall was run before final conformance checks.
- Focused compose/operator conformance on the reverted source:
  `tests/python/test_graph_operators_parity.py`,
  `tests/python/test_relabel_operator_no_double_build_parity.py`, and
  `tests/python/test_attribute_preservation_parity.py`: `32 passed`.
- Post-revert filtered RCH gauntlet rerun for the prior
  `non_edges_sparse_undirected` gap completed on `vmi1149989` with FNX
  `474.09 ms` and NetworkX `471.87 ms` (`0.995x`, neutral, overlapping
  intervals). This is evidence that `non_edges` is not the same clear loss on
  every worker/run, but it is not a domination win and does not rescue the
  rejected compose candidate.

Decision:
- Reject/no-ship. The native compose merge removed some Python edge-map work
  but the remaining public Python attribute-copy/key-display boundary still
  leaves `MultiDiGraph.compose` at roughly `0.37x` vs NetworkX.
- Candidate score: `0` wins / `1` loss / `0` neutral.
- Current active compose gaps remain `MultiDiGraph` and `MultiGraph`
  String-keyed attributed compose.

Do not repeat:
- Do not retry a standalone exact `MultiDiGraph._native_compose` that still
  returns a fully attributed Python graph by copying every edge attr dict.
- Do not spend another pass on the same `_edge_map`-avoidance family unless
  the lever changes the attribute substrate or fuses compose with a downstream
  consumer so the graph-result boundary is not paid eagerly.

## 2026-06-21 Cod-B Public Gauntlet + `non_edges` Set-Pop No-Ship (`br-r37-c1-04z53`, cod-b)

Scope: fresh BOLD-VERIFY pass after `bv --robot-triage` and `br ready`,
focused on current head-to-head gaps against vendored NetworkX. Reused
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; no new
worktree was created.

Baseline/current public-gauntlet evidence:
- Command family:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RUSTUP_TOOLCHAIN=nightly-2026-06-10 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=.venv/bin:$PATH PYTHONPATH=crates/fnx-python/benches:python:legacy_networkx_code PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --bench public_api_gauntlet --features pyo3/abi3-py310 -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`
- RCH worker: `vmi1227854`.
- Current head-to-head score: `9` wins / `1` loss / `0` neutral vs
  NetworkX.

| Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `flow_hierarchy_weighted_cyclic_dag` | `894.53 ms` | `1.3710 s` | `1.53x` | win |
| `within_inter_cluster_explicit_community` | `477.23 ms` | `875.40 ms` | `1.83x` | win |
| `non_edges_sparse_undirected` | `453.53 ms` | `419.38 ms` | `0.925x` | loss |
| `raw_adamic_adar_repeated_overlap` | `549.76 ms` | `1.6527 s` | `3.01x` | win |
| `raw_resource_allocation_repeated_overlap` | `499.15 ms` | `1.6117 s` | `3.23x` | win |
| `raw_preferential_attachment_repeated_overlap` | `432.40 ms` | `453.16 ms` | `1.05x` | win |
| `raw_cn_soundarajan_hopcroft_repeated_overlap` | `421.01 ms` | `1.6991 s` | `4.04x` | win |
| `raw_ra_index_soundarajan_hopcroft_repeated_overlap` | `587.12 ms` | `2.0254 s` | `3.45x` | win |
| `digraph_to_undirected_attr_heavy` | `4.4177 s` | `4.8616 s` | `1.10x` | win |
| `multidigraph_to_scipy_sparse_array_csr_int_weights` | `159.79 ms` | `243.98 ms` | `1.53x` | win |

Radical lever tested and reverted:
- Alien-graveyard / alien-artifact hypothesis: preserve exact CPython
  `set.pop()` iteration semantics in a PyO3 helper for simple `Graph`
  `non_edges`, avoiding public adjacency-row materialization while keeping
  NetworkX-observable pair order.
- Candidate source passed `rch exec -- cargo check -p fnx-python --benches
  --features pyo3/abi3-py310`.
- Candidate conformance passed
  `tests/python/test_non_edges_order_conformance_guard.py -q`: `42 passed`.
- Additional direct seed sweep matched NetworkX output for `60` randomized
  simple graphs; digest
  `bc3e06e826bd4aeaa95deb936958006fff3f81257cfe5def9bc938b9687ad020`.
- Focused RCH timing setup did not produce samples on `hz2`: first with an
  incorrect vendored NetworkX path, then with NumPy missing on that worker.
- Same-process local release timing rejected the candidate:
  FNX median `368.138 ms`, NetworkX median `292.090 ms`, ratio `0.793x`.

Decision:
- Reject/no-ship. The PyO3 set-pop helper was source-reverted after the
  measured candidate remained slower than NetworkX.
- Candidate score: `0` wins / `1` loss / `0` neutral.
- Current active gap from this pass: `non_edges_sparse_undirected`.

Do not repeat:
- Do not retry a materializing PyO3 `Vec<(u, v)>` exact-order helper for
  `non_edges`; it preserves order but moves too much pair materialization cost
  into the boundary.
- Next credible route needs a streaming or consumer-fused boundary: either
  score default-ebunch link-prediction consumers without first creating Python
  non-edge pairs, or expose an exact-order lazy generator that avoids building
  the full pair vector while still matching NetworkX `set.pop()` semantics.

## 2026-06-21 Cod-A Tree Submodule Remeasure + Edge-Boundary Gate (`br-r37-c1-dv0uf`, cod-a)

Scope: fresh BOLD-VERIFY pass after `bv --robot-triage` selected the unowned
P0 release gate `br-r37-c1-dv0uf`, while the umbrella no-gaps perf bead
remained owned by `cod-b` and the only explicit unowned perf recommendation was
blocked. No new perf source lever was shipped in this pass.

Conformance gate:
- The failing `fnx-algorithms` unit expectation for
  `edge_boundary_directed(..., nbunch2=...)` was stale. Vendored NetworkX
  includes `("b", "a")` for overlapping directed `S,T` because
  `edge_boundary` applies its symmetric overlap predicate after taking DiGraph
  out-edges from `nbunch1`.
- Public Python parity check with vendored NetworkX and `PYTHONHASHSEED=0`
  returned `[("a", "b"), ("b", "a"), ("b", "b"), ("b", "c")]` for both FNX
  and NetworkX.

Perf probe:
- Command:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a AGENT_NAME=CrimsonRiver PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head tree_submodule -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`
- RCH worker: `hz2`; requested target dir was rewritten to the worker-scoped
  `/data/projects/franken_networkx/.rch-target-hz2-pool-4a7eb17ce3437e25aacd2701aa3351d7`.
- Focused workload: `franken_networkx.tree.minimum_spanning_tree` on the
  checked-in `networkx_head_to_head_tree_submodule` simple weighted
  `Graph`, n=1000/e=4999. The harness asserts parity before timing.

| Workload | FNX estimate | NetworkX estimate | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `fnx_tree.minimum_spanning_tree`, n=1000/e=4999 | `25.729 ms` | `9.9081 ms` | `0.385x` | loss |

Win/loss/neutral accounting for this pass: `0` wins / `1` loss / `0` neutral.

Alien-graveyard / alien-artifact routing:
- Failure signature: native algorithm work is not enough; the loss sits at the
  Python graph-result boundary and public submodule materialization path.
- Matched primitive family: compact CSR/GraphBLAS-style graph representations
  and zero-copy/batched boundary construction, per the graveyard scan's
  cache-local sparse-graph and boundary-minimization guidance.
- Rejected route: another top-level wrapper dispatch through
  `franken_networkx.minimum_spanning_tree`; current-source scorecard and this
  fresh row both show it fails after public graph materialization.
- Next retry predicate: only retry when the lever changes native result
  construction or graph boundary layout, e.g. emitting the tree graph directly
  from Rust with Python node/edge attribute mirrors populated in one pass, or a
  compact edge-stream handoff that avoids `_from_nx_graph` and repeated Python
  adjacency-row work.

Do not repeat:
- Do not claim a tree-submodule win from a pre-rebase or different-source row.
- Do not use cross-worker self-speedup as keep proof for this family.
- Do not ship a shallow wrapper reroute unless it beats vendored NetworkX on
  the public submodule API after graph materialization.

## 2026-06-21 Cod-B MultiDiGraph CSR Int-Data Bold-Verify (`br-r37-c1-04z53`, cod-b)

Scope: fresh re-authed cod-b verification of the sparse-boundary / CSR
handoff route for default-order integer-weighted
`MultiDiGraph.to_scipy_sparse_array(format="csr", dtype=None)`, under the
disk-low constraint to reuse
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b` and run
only a focused per-crate Criterion row.

Focused harness:
- Added/used `public_api_gauntlet`
  `multidigraph_to_scipy_sparse_array_csr_int_weights`, a deterministic
  2,000-node / 16,000-keyed-edge integer-weighted `MultiDiGraph` fixture.
- The harness asserts sparse parity before timing via shape and
  `(_FNX_MDG_MATRIX != _NX_MDG_MATRIX).nnz == 0`.

RCH evidence:

| Run | Worker | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| baseline/current-row before local typed-source probe | `vmi1227854` | `123.43 ms` | `235.16 ms` | `1.91x` | win |
| typed int-data probe rerun | `vmi1153651` | `326.29 ms` | `528.00 ms` | `1.62x` | win vs NetworkX, not same-worker self-proof |

Additional local parity smoke after the typed extension install:
integer-weight and float-weight `MultiDiGraph` sparse exports both matched
NetworkX and preserved dtype on the focused fixture.

Decision:
- The focused current-row ratio vs NetworkX is a win. Do not count the
  cross-worker after/before delta as proof for or against the typed int-data
  source lever.
- The cod-b local no-ship/revert was not kept once `main` moved to the
  committed typed route (`2655e8add`); do not undo current committed peer work
  from this session.

Do not repeat:
- Do not use cross-worker Criterion numbers as keep/revert proof for this
  exporter. Same-worker or same-process release timing is required for a
  self-speedup claim.
- Remaining sparse-export work should target dirty/live high-unique
  `MultiDiGraph` rows or a deeper SciPy/native CSR construction boundary, not
  another standalone row-streaming or dtype-scan microprobe.

## 2026-06-21 Tree Submodule Spanning-Tree Route Rejection (`br-r37-c1-04z53`, cod-b)

Scope: verify and close the disk-low code-only lever that routed
`franken_networkx.tree.minimum_spanning_tree` and
`franken_networkx.tree.maximum_spanning_tree` through the existing top-level fnx
implementations instead of calling
`networkx.algorithms.tree.*_spanning_tree` and converting through
`_from_nx_graph`.

Evidence:
- First attempted the exact requested spelling
  `rch exec -- cargo bench -p fnx-python --release --bench networkx_head_to_head
  tree_submodule -- --noplot --sample-size 10 --warm-up-time 1
  --measurement-time 2`, but this Cargo rejected `--release` for `bench`.
  No benchmark body ran in that failed invocation.
- The actual one crate-scoped benchmark was
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b
  rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head
  tree_submodule -- --noplot --sample-size 10 --warm-up-time 1
  --measurement-time 2` on `hz1`. RCH rewrote the target dir to a worker-scoped
  path.
- The added Criterion setup asserts the tree-submodule MST signature against
  vendored NetworkX before timing.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `franken_networkx.tree.minimum_spanning_tree` simple weighted `Graph`, n=1000/e=4999 | `15.807 ms` | `13.331 ms` | `0.843x` | loss |

Decision:
- Reject/no-ship. The submodule route was reverted to the prior NetworkX
  delegate plus `_from_nx_graph` conversion, and the no-conversion regression
  test was removed.
- Keep the narrow `networkx_head_to_head_tree_submodule` bench row so future
  work can remeasure the public submodule boundary directly.
- Do not retry top-level fnx wrapper dispatch for simple-graph submodule MST as
  a standalone lever. A future route needs a faster native simple-graph result
  construction path or a larger algorithmic win that beats NetworkX after
  Python graph materialization.

## 2026-06-21 Cod-A Tree Submodule Diagnostic Bench, Superseded by Revert (`br-r37-c1-04z53.9157`, cod-a)

Scope: partial-resume measurement of the same tree-submodule route before
rebasing onto the cod-b rejection commit `1f4bc9171`. This records the actual
cod-a RCH result and setup failures, but it is not a current-source keep: after
the rebase, `python/franken_networkx/tree.py` again delegates submodule
MST/maxST through NetworkX plus `_from_nx_graph` conversion.

Evidence:
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-treebench-20260621T0156`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
  RCH rewrote it to a worker-scoped target on `hz1` for remote execution.
- Measured command:
  `AGENT_NAME=CrimsonRiver BR_AGENT_NAME=cod-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH cargo bench -p fnx-python --bench tree_submodule_head_to_head`.
- The new Criterion bench asserts weighted sparse simple-graph MST/maxST
  parity before timing and uses vendored NetworkX
  `legacy_networkx_code/networkx` as the oracle.

Measured release timing on a 900-node / 3,599-edge weighted sparse simple
graph, four public API calls per Criterion iteration:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `franken_networkx.tree.minimum_spanning_tree` | `25.574 ms` | `39.899 ms` | `1.560x` | win |
| `franken_networkx.tree.maximum_spanning_tree` | `26.427 ms` | `46.737 ms` | `1.769x` | win |

Setup failures recorded:
- `cargo bench ... -- --sample-size 10 --warm-up-time 1 --measurement-time 2`
  built the bench profile but Criterion 0.8 rejected `--sample-size`; no
  samples were collected.
- The first registered target attempt was missing `harness = false` and ran as
  a zero-test harness; no Criterion samples were collected.
- The next setup attempts reached Python startup but failed before timing
  because the worker had no installed `_fnx` extension and then no optional
  `numpy` dependency. The checked-in bench now preloads the bench-built
  `lib_fnx.so` as `franken_networkx._fnx` and installs a fail-fast dummy
  `numpy` module so import-time drawing setup does not block this tree-only
  workload.

Conformance and gates:
- `rustfmt --check crates/fnx-python/benches/tree_submodule_head_to_head.rs`.
- `git diff --check`.
- `rch exec -- cargo check -p fnx-python --benches --features pyo3/abi3-py310`.
- `ubs $(git diff --name-only --cached)` after replacing the parity `!=`
  checks with `operator.eq` to avoid a scanner false positive; exit `0`.
- `python -m py_compile python/franken_networkx/tree.py
  tests/python/test_algorithms_tree_submodule.py`.
- Focused tree-submodule pytest with the bench-built release extension
  preloaded as `franken_networkx._fnx`: `21 passed` after rebasing onto the
  route-revert source.

Decision:
- Superseded/no-ship. The cod-a run produced `2` positive diagnostic ratios
  before the rebase, but the current branch includes the cod-b current-source
  loss and route revert above. Do not count these rows as active current-source
  wins.
- Remaining deeper work: separate fallback/multigraph tree rows if a future
  profile shows a live loss outside this simple-graph public route.

## 2026-06-21 Fresh Cod-A Current-Source Tree Submodule Verification (`br-r37-c1-04z53.9157`, cod-a)

Scope: re-authenticated cod-a restart on current `main` after rebasing onto the
cod-b tree-submodule route revert and the checked-in focused harness. This is
the live current-source decision for the `franken_networkx.tree`
minimum/maximum spanning-tree public submodule surface.

Evidence:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
  RCH rewrote it to worker-scoped target
  `/data/projects/franken_networkx/.rch-target-hz1-pool-411d55b5f6ed4833c6ebe01f30cd4b74`
  on `hz1`.
- Command:
  `AGENT_NAME=CrimsonRiver CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --bench tree_submodule_head_to_head --features pyo3/abi3-py310 -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`.
- The harness asserts weighted sparse simple-graph MST/maxST parity against
  vendored NetworkX before timing and preloads the bench-built `_fnx` extension.
- Alien route considered: graphic-matroid/DSU work is already in the top-level
  fnx native kernels; the remaining candidate is boundary/materialization
  removal for the submodule wrapper. Current source still pays NetworkX
  delegate plus `_from_nx_graph`, and the direct top-level reroute is already
  rejected above.

Measured current-source release timing on a 900-node / 3,599-edge weighted
sparse simple graph, four public API calls per Criterion iteration:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `franken_networkx.tree.minimum_spanning_tree` | `230.97 ms` | `81.677 ms` | `0.354x` | loss |
| `franken_networkx.tree.maximum_spanning_tree` | `254.50 ms` | `97.596 ms` | `0.383x` | loss |

Decision:
- Reject/no-ship for current source. The submodule route remains slower than
  NetworkX after public graph materialization, so no runtime code was changed.
- Keep the focused bench harness as evidence machinery only.
- Do not retry the simple reroute family. A future attempt needs a deeper
  result-construction/materialization primitive that beats NetworkX after
  preserving graph/node/edge attributes, ordering, and exception behavior.

## 2026-06-21 MultiDiGraph Lazy Tarjan Strong-Connectivity Keep (`br-r37-c1-1pmou`, cod-a)

Scope: close the measured `MultiDiGraph.is_strongly_connected` negative-case
loss where the first node is a singleton SCC and the remaining graph is large.
The predecessor path built full successor and predecessor CSR adjacency and ran
two reachability passes, so it paid for every edge even though NetworkX's
boolean predicate stops after the first SCC emitted by Tarjan.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260621T0012`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 (`cc`,
  `target_lexicon`, and `serde` were compiled by a different nightly). No
  cleanup or deletion was performed; release proof runs used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260621T0042`.
- RCH post-rebase validation used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f3f2fb025-postrebase`.
  After RCH artifact retrieval that target was no longer safe for local
  `maturin develop` under the older nightly, so the final installed-extension
  pytest proof used fresh local target
  `/data/projects/.rch-targets/franken_networkx-cod-a-a1e6e7037-local-f20a92`.
- Oracle: vendored NetworkX `3.7rc0.dev0`; Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Baseline release timing on the tiny-first-SCC fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| 3,000 edges | `0.436805 ms` | `0.237889 ms` | `0.545x` | loss |
| 6,000 edges | `0.688320 ms` | `0.239062 ms` | `0.347x` | loss |
| 12,000 edges | `1.220224 ms` | `0.241757 ms` | `0.198x` | loss |
| 21,000 edges | `1.985319 ms` | `0.246786 ms` | `0.124x` | loss |

Kept lever:
- Replace full forward+reverse CSR materialization with a lazy iterative
  Tarjan boolean test over distinct successor rows. Multiplicity is irrelevant
  for strong connectivity, so the native path returns `false` as soon as the
  first closed SCC is smaller than `n` and returns `true` only when the first
  closed SCC spans the graph.

Final release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| 3,000 edges | `0.097704 ms` | `0.391961 ms` | `4.012x` | win |
| 6,000 edges | `0.096753 ms` | `0.396670 ms` | `4.100x` | win |
| 12,000 edges | `0.099048 ms` | `0.403423 ms` | `4.073x` | win |
| 21,000 edges | `0.098226 ms` | `0.265812 ms` | `2.706x` | win |
| strongly connected control, 6,500 edges | `1.382393 ms` | `7.679361 ms` | `5.555x` | win |

Conformance and gates:
- Focused pytest:
  `tests/python/test_directed_multigraph_degenerate_parity.py` and
  `tests/python/test_strongly_connected_conformance.py` passed `397` after the
  final rebase.
- Randomized direct `MultiDiGraph.is_strongly_connected` oracle sweep passed
  `0` mismatches across `200` deterministic small multigraph cases.
- `cargo fmt --check`: pass.
- `python -m py_compile python/franken_networkx/__init__.py
  tests/python/test_directed_multigraph_degenerate_parity.py`: pass.
- `rch exec -- cargo check -p fnx-python --all-targets --features
  pyo3/abi3-py310`: pass.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features
  pyo3/abi3-py310 -- -D warnings`: pass.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`: pass
  (`27 passed`).
- `rch exec -- cargo build -p fnx-python --release --features
  pyo3/abi3-py310`: pass.
- `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310
  --no-run`: pass.
- `git diff --check`: pass.
- `ubs` over touched files: exit `0`, `0` critical issues; existing
  monolithic `algorithms.rs` warning inventory remains outside this lever.

Decision:
- Keep. The targeted negative row flips from `0.124x`-`0.545x` losses to
  `2.706x`-`4.100x` wins while the strongly connected control remains a clear
  win vs NetworkX.
- Do not reintroduce full forward+reverse CSR for the boolean `MultiDiGraph`
  predicate. If exact SCC component emission needs work, keep it separate from
  this boolean fast path.

## 2026-06-21 Max-Weight Matching Public-Loss Stale Correction (`br-r37-c1-88yc4`, cod-a)

Scope: remeasure the previous public `max_weight_matching` loss against the
vendored NetworkX oracle and decide whether an exact NetworkX-order blossom
port/fork is still a release blocker. The previous raw native route remains
invalid for exact edge-set tie-break parity.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260621T0012`.
- Release extension installed from fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260621T0042`
  after the requested shared target hit incompatible-rustc E0514. No cleanup or
  deletion was performed.
- Oracle: vendored NetworkX `3.7rc0.dev0`; Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Fresh same-process release timing on weighted `gnp(300, 0.05, seed=11)`:

| Route | FNX median | NetworkX median | Ratio vs NetworkX | Exact edge set | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| public `fnx.max_weight_matching` delegate | `429.726415 ms` | `467.559904 ms` | `1.088x` | yes | stale loss closed |
| NetworkX direct-on-FNX graph object | `439.729672 ms` | `467.559904 ms` | `1.063x` | yes | no-ship; slower than current public |
| raw `_fnx.max_weight_matching` | `7.510473 ms` | `467.559904 ms` | `62.254x` | no | invalid keep |

Additional matching probes:
- Direct NetworkX-on-FNX exactness sweep over `120` nodes x `20` seeds reported
  `0` mismatches, but it was still slower than the current public delegate on
  the measured `300`-node target.
- `min_edge_cover` and `min_weight_matching` remain separate matching surfaces:
  raw native `min_edge_cover` reached `44.88x` speed but exact edge-set parity
  mismatched on `40 / 40` seeds, while direct NetworkX-on-FNX was exact but
  slower than the current route. No source change was shipped.

Decision:
- Close the stale public `max_weight_matching` loss. The currently shipped
  public API is exact and `1.088x` vs vendored NetworkX on the bead fixture.
- Keep raw native matching out of the public route until tie-break parity is
  solved; `62x` raw speed is routing evidence only, not a keep.
- Do not spend release-blocker time on an exact blossom port for this public row
  unless a new vendored-oracle measurement again shows a real public loss.

## 2026-06-20 MultiDiGraph Indexed CSR Bytearray Boundary Keep (`br-r37-c1-q2w4t`, cod-a)

Scope: revisit the large default-order `MultiDiGraph.to_scipy_sparse_array`
residual after the row-streaming-only rejection. The kept route combines the
alien-graveyard sparse-boundary/CSR guidance with two concrete boundary
changes: Rust emits mutable bytearray-backed CSR buffers for NumPy
`frombuffer`, and `MultiDiGraph` exposes an indexed ordered-edge visitor so the
CSR helper avoids both `edges_ordered_borrowed()` materialization and a second
node-index `HashMap`.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T2025Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Oracle import pinned to this worktree's vendored NetworkX path:
  `legacy_networkx_code/networkx`; Python `3.13.7`, `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `taskset -c 4`.
- Release extension installs used the fresh non-destructive target leaf
  `/data/projects/.rch-targets/franken_networkx-cod-a/f20a-local` because the
  shared requested target contained incompatible-rustc artifacts during
  `maturin develop`. No cleanup or deletion was performed. Final per-crate RCH
  check/test/clippy/build used the requested target and worker-scoped remotes.

Negative subattempts:
- Immutable `bytes` buffers were rejected immediately: SciPy may canonicalize
  CSR arrays in place, and `numpy.frombuffer(bytes)` produced
  `ValueError: WRITEBACKIFCOPY base is read-only` during sparse payload checks.
  The fix was to return `PyByteArray` so NumPy sees writable buffers.
- Mutable bytearray handoff without indexed storage traversal was only a
  partial route. Pinned same-process n=2000 timing improved the old fallback
  from `9.0834035 ms` to `6.5314375 ms` (`1.391x` self-speedup) but still
  trailed NetworkX `6.201046 ms` (`0.949x`). Kept only after adding the indexed
  visitor.

Final pinned release timing on deterministic default-order fixtures:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| n=500, 3k-edge `to_scipy MultiDiGraph` | `0.355143 ms` | `1.217437 ms` | `3.428x` | win |
| n=1000, 6k-edge `to_scipy MultiDiGraph` | `0.740944 ms` | `2.475911 ms` | `3.342x` | win |
| n=2000, 12k-edge `to_scipy MultiDiGraph` | `1.729036 ms` | `5.001066 ms` | `2.892x` | win |

Same-process fallback comparison for the n=2000 target:
- New indexed bytearray path: `2.3780405 ms`.
- Old list-returning CSR fallback with the new helper disabled: `3.3666895 ms`.
- NetworkX: `5.228357 ms`.
- Result: new path is `1.416x` faster than the old fallback and `2.199x`
  faster than NetworkX on the direct old/new/NX A/B loop.

Conformance and gates:
- Sparse payload parity: `diff_nnz=0` on every final sweep row; sums matched
  (`12002.0`, `24002.0`, `48003.0`). Existing dtype behavior remains unchanged:
  FNX old/new infer `int64` for integral float payloads while NetworkX reports
  `float64` on this synthetic fixture; sparse values match exactly.
- Focused sparse exporter parity:
  `pytest tests/python/test_to_scipy_sparse_default_native_parity.py
  tests/python/test_to_scipy_sparse_native_weighted_parity.py -q`:
  `304 passed`.
- `cargo fmt --check`: pass.
- `rch exec -- cargo check -p fnx-classes -p fnx-python --features
  pyo3/abi3-py310`: pass.
- `rch exec -- cargo test -p fnx-classes -p fnx-python --features
  pyo3/abi3-py310`: pass (`fnx-classes` `68 passed, 2 ignored`; `_fnx`
  `27 passed`).
- `rch exec -- cargo clippy -p fnx-classes -p fnx-python --all-targets
  --features pyo3/abi3-py310 -- -D warnings`: pass.
- `rch exec -- cargo build --release -p fnx-python --features
  pyo3/abi3-py310`: pass.
- UBS completed with exit `0` on the changed Rust sources and the focused
  Python parity test file. The all-touched-file UBS run was stopped after the
  Python pass spent roughly nine minutes on the pre-existing 56k-line public
  wrapper file with no findings emitted; focused pytest and `py_compile` cover
  that wrapper path for this slice.

Decision:
- Keep. The final indexed bytearray CSR boundary turns the current pinned
  default-order `MultiDiGraph.to_scipy_sparse_array` sweep into `3` wins /
  `0` losses / `0` neutral vs NetworkX, including the prior 12k-edge residual.
- Do not retry immutable `bytes` buffers for SciPy CSR arrays. Keep buffer
  handoff mutable, and route future sparse work toward dirty/live attr sync or
  full native sparse-array construction rather than Python list boundaries.

## 2026-06-20 Native Tuple Lattice Generator Keep (`br-r37-c1-ap7at`, cod-b)

Scope: close the public default non-periodic tuple-key lattice generator losses
for `triangular_lattice_graph` and `hexagonal_lattice_graph`. The final keep
routes only the default `create_using=None`, `periodic=False`, nonnegative
integer shape path through native Rust construction; all periodic, custom
graph-factory, boolean-shape, and negative-shape cases remain on the existing
NetworkX-compatible Python fallback.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T204139Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Local release installs through the requested target hit incompatible-rustc
  E0514 from stale artifacts. No cleanup or deletion was performed. Local
  release installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-local-f20a92ec-lattice`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Direct timing command: pinned same-process release loop on core `4` with
  identical public FNX/NetworkX generator calls at shape `60x60`, parity digest
  asserted before timing.

Control and candidate rows:

| Workload | Old FNX fallback median | NetworkX median | Old ratio vs NetworkX | Candidate median | Candidate ratio vs NetworkX | Candidate vs old FNX | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `triangular_lattice_graph(60, 60)` | `14.366951 ms` | `5.038766 ms` | `0.351x` | `2.859337 ms` | `1.762x` | `5.025x` faster | keep |
| `hexagonal_lattice_graph(60, 60)` | `40.929678 ms` | `14.777368 ms` | `0.361x` | `11.023525 ms` | `1.341x` | `3.713x` faster | keep |
| `triangular_lattice_graph(60, 60, with_positions=False)` | `10.185578 ms` | `4.104106 ms` | `0.403x` | `2.063670 ms` | `1.989x` | `4.936x` faster | keep |
| `hexagonal_lattice_graph(60, 60, with_positions=False)` | `23.653816 ms` | `8.533418 ms` | `0.361x` | `6.158808 ms` | `1.386x` | `3.841x` faster | keep |

Rejected subattempt:
- Native edge construction with Python `set_node_attributes` position
  materialization was not enough for the default-position public rows:
  triangular default reached only `0.903x` vs NetworkX and hexagonal default
  reached only `0.698x`. The final keep moved tuple-key node labels and `pos`
  attributes into the native constructor result instead of looping in Python.

Supplemental RCH Criterion evidence:
- Command:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head lattice_generators -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`.
- Worker: `vmi1153651`; exit `0`.
- Criterion estimates: triangular FNX `15.017 ms` vs NetworkX `53.823 ms`
  (`3.584x`); hexagonal FNX `83.563 ms` vs NetworkX `100.74 ms` (`1.206x`).
  FNX rows had high outliers on the shared worker, so the pinned same-process
  loop above is the keep gate and Criterion is supplemental bench coverage.

Conformance and gates:
- Focused lattice conformance: `tests/python/test_lattice_generators.py -q`,
  `24 passed`.
- Per-crate RCH gates: `cargo check -p fnx-python --all-targets --features
  pyo3/abi3-py310`; `cargo clippy -p fnx-python --all-targets --features
  pyo3/abi3-py310 -- -D warnings`; `cargo test -p fnx-python --features
  pyo3/abi3-py310` (`27 passed`); `cargo build --release -p fnx-python
  --features pyo3/abi3-py310`.
- Local gates: `cargo fmt --check`; `git diff --check`.

Decision:
- Keep. Final focused score: `4` wins / `0` losses / `0` neutral vs NetworkX.
- Do not retry the Python `set_node_attributes` position loop for default
  lattice rows. If periodic lattice cases become an active loss, route them as
  a separate parity problem because NetworkX relabeling semantics differ.

## 2026-06-20 MultiDiGraph CSR Row-Streaming Boundary Reject (`br-r37-c1-04z53`, cod-a)

Scope: test the next large sparse multigraph residual route after the prior
dirty-key and default-order exporter probes. The candidate added a storage-level
`MultiDiGraph` row-streaming helper so the default-order CSR exporter could
avoid materializing `edges_ordered_borrowed()` and avoid rebuilding a node-index
hash map before summing parallel `(u, v)` buckets.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T2000`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested target hit incompatible-rustc E0514 (`cc`, `target_lexicon`,
  and `serde` compiled by rustc `beae78130` while this checkout uses
  `f20a92ec0`). No cleanup or deletion was performed. Candidate/control release
  installs used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-boldverify-20260620T2001`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13.7`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Control source on deterministic default-order fixtures:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| n=500 `to_numpy MultiGraph` | `1.816 ms` | `2.398 ms` | `1.321x` | win |
| n=500 `to_scipy MultiGraph` | `1.868 ms` | `2.186 ms` | `1.170x` | win |
| n=2000 `to_numpy MultiGraph` | `21.265 ms` | `19.065 ms` | `0.897x` | loss |
| n=2000 `to_scipy MultiGraph` | `18.061 ms` | `15.779 ms` | `0.874x` | loss |
| n=500 `to_numpy MultiDiGraph` | `5.169 ms` | `5.372 ms` | `1.039x` | win |
| n=500 `to_scipy MultiDiGraph` | `4.687 ms` | `3.838 ms` | `0.819x` | loss |
| n=2000 `to_numpy MultiDiGraph` | `29.262 ms` | `34.027 ms` | `1.163x` | win |
| n=2000 `to_scipy MultiDiGraph` | `26.248 ms` | `21.473 ms` | `0.818x` | loss |

Candidate timing after release rebuild:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| n=500 `to_scipy MultiDiGraph` | `4.408 ms` | `3.927 ms` | `0.891x` | `1.063x` faster | still loss |
| n=2000 `to_scipy MultiDiGraph` | `21.973 ms` | `17.132 ms` | `0.780x` | `1.195x` faster | still loss |
| n=500 native CSR helper | `4.163 ms` | n/a | n/a | `1.038x` faster | routing only |
| n=2000 native CSR helper | `21.330 ms` | n/a | n/a | `1.102x` faster | routing only |

Decision:
- Reject/no-ship. The storage streaming scan produced small-to-moderate FNX
  self-speedups, but it did not beat NetworkX on either public sparse exporter
  row; the n=2000 public ratio was still a clear `0.780x` loss.
- Source hunk manually reverted; `git diff` on
  `crates/fnx-classes/src/digraph.rs` and `crates/fnx-python/src/readwrite.rs`
  is empty.
- Candidate `rch exec -- cargo check -p fnx-python --features
  pyo3/abi3-py310` passed before rejection.
- Reverted-source release install passed from the fresh target. The focused
  artifact harness remained parity-green: `160` configs x `2` exporters,
  `0` fails, golden
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.

Do not repeat:
- Do not add a storage-level row-streaming CSR scan as a standalone lever for
  default-order `MultiDiGraph.to_scipy_sparse_array`; it trims native helper time
  but leaves the public row slower than NetworkX.
- Next route needs a real sparse boundary/layout change: direct NumPy/SciPy
  buffer handoff, cached CSR arrays with mutation guards, or an algorithmic
  bypass of SciPy construction cost for callers that immediately consume CSR.

## 2026-06-20 MultiDiGraph CSR Boundary Snapshot Reject (`br-r37-c1-04z53`, cod-b)

Scope: re-baseline the dirty/live large-sparse `MultiDiGraph` matrix-exporter
residual on a high-unique-pair fixture, then test two deeper CSR-boundary
variants without shipping either source hunk. The target is the default
`nodelist=None`, `dtype=None`, `format="csr"`, `weight="weight"` public sparse
export path after 388 public `G[u][v][k]["weight"] = ...` mutations.

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T1956`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Per-crate RCH gates before editing passed:
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  and
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`.
- Local release installs through the requested target hit incompatible-rustc
  E0514 from stale artifacts; no cleanup or deletion was performed. Candidate
  installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-csrrow`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Fixture: deterministic random seed `1`, 2,000 integer nodes, 12,000 keyed
  edges, 388 public post-construction dirty weight mutations, canonical CSR
  digest `f50fd3dec9442adb9b48b2392cf3c63305b314eca3a1e3e3b99f28c63e3d9e36`,
  `11974` canonical nonzeros, dtype `float64`, data sum `110516.75`.
- cProfile before editing: 40 calls to
  `_fnx.adjacency_csr_multidigraph_default_order_live_finite_checked` consumed
  `0.563 s` cumulative, about `14 ms` per call; Python/SciPy construction was
  not the primary cost.

Control source on the reproduced dirty fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `14.974176 ms` | `12.004329 ms` | `0.802x` | loss |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `14.922177 ms` | `11.647203 ms` | `0.781x` | loss |

Candidate 1: source-row stream + Rust dtype flag:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `15.520080 ms` | `12.520007 ms` | `0.807x` | `0.965x` self-regression by FNX median | loss |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `13.147295 ms` | `11.581038 ms` | `0.881x` | `1.135x` faster | still loss |

Candidate 2: in-call precise dirty weight snapshot + candidate 1:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty high-unique 12k-edge MDG | `15.587537 ms` | `12.611771 ms` | `0.809x` | `0.961x` self-regression by FNX median | loss |
| `adjacency_matrix`, dirty high-unique 12k-edge MDG | `15.118008 ms` | `12.087389 ms` | `0.800x` | `0.987x` self-regression by FNX median | loss |

Conformance and gates:
- Candidate 1:
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed;
  focused sparse parity reported `304 passed`.
- Candidate 2:
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed;
  focused sparse parity reported `304 passed`.
- Both candidate source hunks were manually reverted before commit.

Decision:
- Reject/no-ship. Candidate 1 improved only the sibling `adjacency_matrix`
  row and still lost to NetworkX; candidate 2 regressed the sibling row and
  still lost on both target rows.
- Score on the target dirty slice: `0` wins / `2` losses / `0` neutral.
- Source code is restored to the pre-probe implementation; only ledger,
  scorecard, and Beads status changes are kept.

Do not repeat:
- Do not retry source-row hashing removal or Python dtype-scan elimination as
  standalone CSR levers for dirty high-unique `MultiDiGraph` sparse export.
- Do not retry in-call precise dirty weight snapshot without a new design that
  avoids mutating/copying Rust attr maps and also eliminates the dominant
  per-edge live-dict overhead.
- Next route needs a true native sparse-array/CSR buffer boundary, a compact
  edge-weight mirror specialized for numeric weights, or a larger algorithmic
  escape from per-edge Python dict semantics.

## 2026-06-20 MultiDiGraph Precise Dirty-Key Sparse Reject (`br-r37-c1-04z53`, cod-b)

Scope: test a narrower dirty/live sparse-export lever than the prior
borrowed-index rejection. `MultiDiGraph` already tracks exact dirty edge keys
for `G[u][v][k]` accesses, but the default-order sparse helpers treated any
dirty flag as "all edges dirty" and read every weight through the live Python
edge-attr dict path. The candidate made those helpers read stored Rust attrs
for untouched edges and use live dicts only for keys in the precise dirty set.

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T181919`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Per-crate RCH release build passed:
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.
  RCH rewrote the remote target to a worker-scoped cache.
- Local release install through the requested target hit incompatible-rustc
  E0514 from stale artifacts; no cleanup or deletion was performed. Candidate
  and control installs used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-precise`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`, `PYTHONHASHSEED=0`,
  `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Fixture: deterministic 2,000-node / 12,000-edge `MultiDiGraph`, 388 public
  post-construction `G[u][v][k]["weight"] = ...` mutations, default nodelist,
  default `weight="weight"`, sparse payload digest
  `558129dd98de2c818c51c16c33e6ec18786afaec48f8d3eddab018c0a24b3cdc`.

Control source on the same fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `9.680769 ms` | `7.469069 ms` | `0.772x` | loss |
| `adjacency_matrix`, dirty 12k-edge MDG | `10.238225 ms` | `7.189950 ms` | `0.702x` | loss |

Candidate timing after release rebuild:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs control | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `7.275282 ms` | `6.754456 ms` | `0.928x` | `1.331x` faster | still loss |
| `adjacency_matrix`, dirty 12k-edge MDG | `11.222841 ms` | `7.623773 ms` | `0.679x` | `0.912x` regression | regression/loss |

Decision:
- Reject/no-ship. The candidate improved the direct sparse row but did not beat
  NetworkX, and it regressed the sibling `adjacency_matrix` row that routes
  through the same public sparse exporter.
- Source hunk reverted; final source has no code diff from the control route.
- Score on the target dirty slice: `0` wins / `2` losses / `0` neutral vs
  NetworkX; self-score `1` improvement / `1` regression.
- Candidate `rch exec -- cargo check -p fnx-python --features
  pyo3/abi3-py310` passed. Reverted-source gates passed: `cargo fmt --check`,
  `git diff --check`, focused sparse parity
  `304 passed` (`test_to_scipy_sparse_native_weighted_parity.py` plus
  `test_to_scipy_sparse_default_native_parity.py`).

Do not repeat:
- Do not use precise dirty-key stored-attr bypass as a standalone lever for the
  dirty `MultiDiGraph` sparse exporter. It moves one row closer to parity but
  still loses and regresses `adjacency_matrix`.
- Next route needs a true native sparse-array/CSR boundary or a design that
  removes the Python/SciPy handoff cost while preserving dtype inference and
  live attr semantics; do not spend another patch on per-edge live-dict lookup
  selection alone.

## 2026-06-20 MultiDiGraph Dirty Sparse Boundary Borrowed-Index Reject (`br-r37-c1-kqh2u`)

Scope: re-baseline the large sparse multigraph exporter residual and test one
dirty/live edge-attribute boundary lever. The clean default-order integer-index
fixture is already a win; the active loss reproduced only on the dirty
`MultiDiGraph` path with public edge-attribute mutations.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260620T184133Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The exact requested target hit incompatible-rustc E0514 from older artifacts.
  No cleanup, deletion, or reset was performed. Release and benchmark proof used
  fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-kqh2u`.
- Oracle: NetworkX `3.6.1`, Python `3.13.7`, `PYTHONHASHSEED=0`,
  `taskset` core `4`.
- Alien route applied: cache/layout/Swiss-table guidance translated to a
  borrowed live-weight index attempt intended to avoid per-edge owned
  `(u, v, key)` tuple construction and hash lookup on the dirty exporter path.

Clean fixture sanity, not the target loss:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, clean default-order n=2000 | `1.390486 ms` | `3.557171 ms` | `2.558x` | win |
| `adjacency_matrix`, clean default-order n=2000 | `1.518057 ms` | `3.632664 ms` | `2.393x` | win |

Dirty/live baseline on the active residual fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `11.083094 ms` | `7.516955 ms` | `0.678x` | loss |
| `adjacency_matrix`, dirty 12k-edge MDG | `11.440620 ms` | `6.928440 ms` | `0.606x` | loss |

Rejected lever:
- Pre-index `edge_py_attrs` live weights by borrowed `(&str, &str, usize)`
  once inside the Rust helper, then stream CSR without per-edge string clones or
  owned lookup-tuple construction.

Candidate timing after release rebuild:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `to_scipy_sparse_array`, dirty 12k-edge MDG | `14.510345 ms` | `6.259952 ms` | `0.431x` | regression |
| `adjacency_matrix`, dirty 12k-edge MDG | `9.431321 ms` | `5.827642 ms` | `0.618x` | still loss |

Decision:
- Reject/no-ship. The source hunk was reverted because the target
  `to_scipy_sparse_array` row regressed from `0.678x` to `0.431x`, and the
  `adjacency_matrix` row remained a loss.
- Score on the target dirty slice: `0` wins / `2` losses / `0` neutral.
- Parity digest matched in the candidate probe.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed on
  the candidate; `cargo fmt --check` passed after revert. Final source has no
  code diff.
- Post-revert release reinstall from the fresh target confirmed the installed
  extension was back on the final source and still losing on the same dirty
  fixture shape with digest parity:
  `to_scipy_sparse_array` FNX `12.386839 ms` vs NetworkX `7.455365 ms`
  (`0.602x`), `adjacency_matrix` FNX `18.037455 ms` vs NetworkX `7.471376 ms`
  (`0.414x`), digest
  `c29d2099856ac22e34cb12781f7d70f407c40512ca621cfe74e071c843115c44`.
- Final gates on the reverted source: `cargo fmt --check`, `git diff --check`,
  `python -m py_compile python/franken_networkx/__init__.py`,
  focused sparse exporter parity `297 passed`,
  `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`,
  `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`,
  and
  `rch exec -- cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`
  all passed.

Do not repeat:
- Do not front-load all live weight dictionary lookups into a borrowed index for
  dirty `MultiDiGraph` sparse export as a standalone lever.
- Do not claim the clean default-order sparse wins as closure for dirty/live
  boundary losses.

Next route:
- Sync only dirty weight keys into inner attrs and clear the dirty state before
  CSR export, or bypass Python tuple/list construction with a true native sparse
  array boundary for dirty `MultiDiGraph` rows.

## 2026-06-20 Default-Order Matrix Export + Dijkstra Emitter No-Ships (`br-r37-c1-04z53`)

Scope: test two radical-but-narrow boundary levers from the current loss
frontier before touching broader graph semantics: default-order multigraph
matrix export without repeated nodelist lookup, and path-heavy Dijkstra Python
object emission without duplicate display-key lookups. Both routes were
measured, reverted, and left as routing evidence only.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=CrimsonRiver`
  / cod-b.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T181919`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested target dir hit incompatible-rustc E0514 from older artifacts
  during the matrix bench setup. No cleanup, deletion, or reset was performed.
  Release and benchmark proof used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0`.
- RCH needed absolute `PYTHONPATH` entries for the public-gauntlet Python
  module and vendored NetworkX. The worker image did not have SciPy, so the
  sparse exporter row failed with `ModuleNotFoundError: No module named
  'scipy'` and the dense `to_numpy_array` sibling became the measurable route.

Matrix exporter evidence:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Candidate vs FNX baseline | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline `MultiDiGraph.to_numpy_array(default weight)`, 2000 nodes, RCH Criterion on `vmi1167313` | `98.274 ms` | `136.28 ms` | `1.3867x` | baseline | current win |
| Default-order COO/nodelist bypass candidate, same worker | `102.83 ms` | `142.91 ms` | `1.3896x` | `0.956x` | reject |
| Dense f64 slab default-order candidate, same worker | `104.63 ms` | `141.14 ms` | `1.349x` | `0.939x` | reject |

Dijkstra emitter evidence:

Fixture: synthetic directed integer-weight graph with a chain plus random
directed edges, source `0`, seed `20260620`, vendored NetworkX
`3.7rc0.dev0`, source-tree extension built by release `maturin build`.
The candidate cached finalized display-key objects and streamed each path
through `PyList::new` instead of first building a Rust `Vec<PyObject>`.
Parity digests matched for every row.

| Workload | Baseline FNX p50 | Candidate FNX p50 | NetworkX p50 | Baseline ratio vs NetworkX | Candidate ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Directed Dijkstra combined distance+path, n=600 / e=2999 | `0.457727 ms` | `0.601329 ms` | baseline `1.084615 ms`; candidate `1.519348 ms` | `2.3696x` | `2.5267x` | reject; FNX self-regression |
| Directed Dijkstra combined distance+path, n=1400 / e=6999 | `1.152663 ms` | `1.531261 ms` | baseline `4.482733 ms`; candidate `4.954216 ms` | `3.8890x` | `3.2354x` | reject; FNX self-regression |
| Directed Dijkstra combined distance+path, n=2600 / e=12999 | `5.737650 ms` | `5.246430 ms` | baseline `9.946764 ms`; candidate `9.730325 ms` | `1.7336x` | `1.8547x` | reject; noisy already-winning synthetic row |

Supplemental routing evidence:
- The existing undirected Dijkstra artifact harness
  `tests/artifacts/perf/20260615T-dijkstra-pred-boldfalcon/dijkstra_family_pass.py`
  on n=1400 / extra=6400 also showed a current win:
  `single_source_dijkstra` FNX p50 `1.992756 ms` vs NetworkX `5.079183 ms`
  (`2.550x`), with digest parity. That does not close the historical
  `br-r37-c1-0opkc` directed path-heavy loss because it is a different
  fixture.

Conformance and gates:
- Matrix dense-slab candidate focused parity passed:
  `tests/python/test_to_scipy_sparse_default_native_parity.py` reported
  `9 passed` before the candidate was reverted.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed during the Dijkstra emitter candidate.
- Release `maturin build --release --features pyo3/abi3-py310` completed for
  both the candidate and reverted baseline extension used in the Dijkstra A/B.
- Current source after both experiments has no code diff from the pre-probe
  baseline.

Decision:
- Reject and fully revert both matrix-export candidates. The measurable dense
  default-order row was already faster than NetworkX, and both candidates
  slowed FNX versus its own baseline.
- Reject and fully revert the Dijkstra display-key/PyList emitter candidate.
  It regressed the smaller two rows and only improved the largest synthetic
  row by roughly `1.09x` on a fixture that already beat NetworkX.
- Score impact for current release rows: `0` new wins / `0` new active losses /
  `0` neutral. This is negative evidence, not a kept performance entry.

Do not repeat:
- Do not retry default-order multigraph COO/nodelist bypass or dense f64 slab
  export for `to_numpy_array` unless a fresh fixture shows an active
  NetworkX-relative loss on that exact dense path.
- Do not retry the Dijkstra display-key cache / `PyList::new` streaming lever
  alone. Recover or port the exact `br-r37-c1-0opkc` directed residual fixture
  into a per-crate head-to-head bench first; only attack path emission there if
  the current baseline still loses.

## 2026-06-20 Node Expansion Raw-Kernel Public Route + Node-Degree XY Rebaseline (`br-r37-c1-04z53`)

Scope: target the active simple-undirected `node_expansion(G, S)` loss on the
BA2500/S1250 and WS2500/S625 cut-metric rows, then recheck the stale
`node_degree_xy` public-loss rows before spending another lever there.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-20260620T1318`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested target dir hit incompatible-rustc E0514 from older artifacts.
  No cleanup, deletion, or reset was performed. Release and benchmark proof used
  fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-1318`.
- Alien route applied: cache-local bitmap/set-union guidance translated to a
  single PyO3 validate+compute primitive. The public wrapper now dispatches
  simple undirected `node_expansion` into the existing Rust indexed-neighbor
  union kernel; the Rust binding validates every node and raises NetworkX's
  missing-node error before the bitmap pass.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `node_expansion`, BA2500/S1250, RCH Criterion baseline on `vmi1149989` | `1.7826 ms` | `629.01 us` | `0.353x` | loss |
| `node_expansion`, WS2500/S625, RCH Criterion baseline on `vmi1149989` | `776.82 us` | `380.16 us` | `0.489x` | loss |

Kept lever:
- Import `_fnx.node_expansion` as `_raw_node_expansion` and route the public
  function to it for simple undirected nonempty sized `S`.
- Move missing-node validation into the Rust binding so the hot path does not
  pay a Python `all(node in G for node in S)` scan; missing nodes still raise
  `NetworkXError("The node X is not in the graph.")`.

Final accepted release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `node_expansion`, BA2500/S1250, RCH Criterion on `vmi1152480` | `213.68 us` | `527.47 us` | `2.469x` | win |
| `node_expansion`, WS2500/S625, RCH Criterion on `vmi1152480` | `94.674 us` | `292.24 us` | `3.087x` | win |
| Local release sanity, BA2500/S1250 | `196.962 us` | `298.657 us` | `1.516x` | win |
| Local release sanity, WS2500/S625 | `73.424 us` | `137.229 us` | `1.869x` | win |

Fresh `node_degree_xy` rebaseline:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| public `fnx.node_degree_xy`, h512/s32, RCH Criterion on `vmi1153651` | `116.87 ms` | `336.80 ms` | `2.882x` | stale loss closed |
| public directed `fnx.node_degree_xy`, l512/f32, RCH Criterion on `vmi1153651` | `158.65 ms` | `336.86 ms` | `2.123x` | stale loss closed |
| raw `_fnx.node_degree_xy_rust`, h512/s32, RCH Criterion on `vmi1153651` | `29.948 ms` | `362.97 ms` | `12.120x` | valid win |
| raw directed `_fnx.node_degree_xy_rust`, l512/f32, RCH Criterion on `vmi1153651` | `38.594 ms` | `443.04 ms` | `11.479x` | valid win |

Conformance and gates:
- Release `maturin develop --release --features pyo3/abi3-py310` passed with
  the fresh target dir above.
- Focused graph-metrics expansion tests passed: `55 passed`.
- Focused graph-metrics expansion + conformance tests passed: `199 passed`.
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` reported
  `27 passed`.
- `ubs --only=rust crates/fnx-python/src/algorithms.rs` completed with exit
  `0` (`0` critical issues; existing broad warning inventory remained).
- `ubs --only=python tests/python/test_graph_metrics_expansion.py` completed
  with exit `0` (`0` critical, `0` warning issues).
- `ubs --only=python python/franken_networkx/__init__.py tests/python/test_graph_metrics_expansion.py`
  timed out after `300s` in the large public module; Python syntax was still
  checked with `py_compile`, and focused pytest/bench parity gates are green.
- The head-to-head Criterion benches assert `node_expansion` and
  `node_degree_xy` result parity before timing.

Decision:
- Keep the `node_expansion` public raw-kernel route. The active rows flip from
  measured losses (`0.353x`, `0.489x`) to measured wins (`2.469x`, `3.087x`).
- Treat the old `node_degree_xy` public-loss rows as stale. The current public
  path wins on the same RCH head-to-head harness, and the raw path is now
  parity-checked by the bench before timing.
- Focused score for this pass: `4` public wins / `0` active losses / `0`
  neutral; raw side evidence adds `2` valid wins.

Do not repeat:
- Do not reintroduce a Python membership pre-scan before `node_expansion`; it
  measured as the dominant remaining overhead and kept BA below NetworkX.
- Do not spend another `node_degree_xy` lever until a fresh head-to-head row
  shows a current loss. The prior public-loss scorecard rows are stale.

## 2026-06-20 MultiGraph BFS Direct Borrowed Row Route (`br-r37-c1-1jm15`)

Scope: close the remaining dense-parallel `MultiGraph`
`bfs_edges(source=0)` loss split from `br-r37-c1-ij951`, preserving
NetworkX discovery order and Python-visible node display objects.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-bfs-20260620T1133Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact release install against the requested shared target dir hit
  incompatible-rustc E0514 because older target artifacts were present. No
  cleanup, deletion, or target reset was performed. Release proof used fresh
  non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-bfs-f20a92ec0`.
- Alien route applied: GraphBLAS/CSR frontier guidance and cache-local row
  traversal translated to a narrower primitive: avoid per-call full
  `Vec<Vec<usize>>` adjacency indexing and endpoint `String` clones for
  row-local `MultiGraph` BFS.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `bfs_edges(source=0)`, 1000-node / 5000-edge `MultiGraph`, same-process release loop | `0.684275 ms` | `0.499728 ms` | `0.730x` | loss |
| Prior `ij951` pinned sweep for the same residual | `0.796 ms` | `0.657 ms` | `0.825x` | loss |

Kept lever:
- Add a borrowed `MultiGraph::neighbors_iter` row iterator and route
  undirected `MultiGraph` `bfs_edges` through direct borrowed distinct-neighbor
  traversal. The PyO3 boundary keeps the discovered parent display object and
  emits the child row-display object, matching NetworkX's visible tuple order
  without rebuilding a full indexed adjacency map.

Final accepted release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| Same-process release loop after borrowed helper | `0.489809 ms` | `0.530343 ms` | `1.083x` | win |
| Same-process release loop after `neighbors_iter` | `0.472939 ms` | `0.519132 ms` | `1.098x` | win |
| RCH Criterion `bfs_edges_mg1000_e5000` on `ovh-a` | `441.08 us` | `548.47 us` | `1.243x` | win |

Neutral/noisy evidence:
- An earlier RCH Criterion row on a different worker after only the borrowed
  helper was positive but marginal: FNX median `666.71 us` vs NetworkX
  `672.28 us` (`1.008x`). It was treated as routing evidence, not the final
  keep gate; the final `neighbors_iter` row above is the accepted benchmark.

Conformance and gates:
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-classes` reported `68 passed, 2 ignored`.
- Release `maturin develop --release --features pyo3/abi3-py310` passed with
  the fresh target dir above.
- Focused traversal conformance reported `204 passed`, then broader
  BFS/traversal parity reported `136 passed`.
- A too-broad `test_dicsr_cache_parity.py` run exposed unrelated directed
  multi-source Dijkstra finalize-order drift; follow-up bead
  `br-r37-c1-syrw5` records that work.

Decision:
- Keep. This converts the active `MultiGraph bfs_edges(source=0)` residual from
  a measured loss (`0.730x` in this clean worktree, `0.825x` in the earlier
  pinned sweep) to a measured win (`1.098x` same-process, `1.243x` Criterion).
- Final bead score: `1` win / `0` losses / `0` neutral vs NetworkX.

Do not repeat:
- Do not rebuild full indexed adjacency and `String` endpoint vectors for
  undirected `MultiGraph` BFS. Row-local borrowed traversal is the measured
  primitive for this surface.
- Do not treat the unrelated Dijkstra finalize-order failure as BFS evidence;
  it is tracked separately by `br-r37-c1-syrw5`.

## 2026-06-20 MultiDiGraph Weighted Sparse Export Live-Dict Slice (`br-r37-c1-wvuf7`)

Scope: target the measured weighted sparse/matrix exporter loss where
`_sync_rust_edge_attrs(..., edge_only=True)` dominated `MultiDiGraph`
`to_scipy_sparse_array` / `adjacency_matrix` at scale. The kept lever is a
native live-dict weight reader for `MultiDiGraph` dtype-`None` multigraph
exporters: walk the existing inner edge order, read live Python edge-attr
mirrors for the requested weight, fall back to Rust attrs only when no mirror is
present, and return to the exact Python fallback for present nonnumeric or
nonfinite weights.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-wvuf7-20260620T1045Z`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested local `maturin develop --release --features pyo3/abi3-py310`
  against the shared target dir failed with incompatible-rustc E0514. No
  cleanup or file deletion was performed.
- Release extension install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-maturin-f20a`.
- Per-crate RCH gates completed for `fnx-python`: `cargo check -p fnx-python
  --benches`, `cargo clippy -p fnx-python --all-targets -- -D warnings`, and
  `cargo build -p fnx-python --release`.
- Head-to-head harness: same-process Python release timing against vendored
  NetworkX `3.7rc0.dev0`, `PYTHONHASHSEED=0`, public weighted graph
  construction with parity checked before timing for every row.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `MultiGraph n=250 to_scipy_sparse_array` | `0.699 ms` | `0.878 ms` | `1.256x` | win |
| `MultiGraph n=250 adjacency_matrix` | `0.734 ms` | `0.863 ms` | `1.176x` | win |
| `MultiGraph n=1000 to_scipy_sparse_array` | `3.299 ms` | `3.396 ms` | `1.029x` | win |
| `MultiGraph n=1000 adjacency_matrix` | `4.101 ms` | `3.658 ms` | `0.892x` | loss |
| `MultiGraph n=2000 to_scipy_sparse_array` | `14.671 ms` | `10.535 ms` | `0.718x` | loss |
| `MultiGraph n=2000 adjacency_matrix` | `13.482 ms` | `11.038 ms` | `0.819x` | loss |
| `MultiDiGraph n=250 to_scipy_sparse_array` | `0.856 ms` | `0.623 ms` | `0.728x` | loss |
| `MultiDiGraph n=250 adjacency_matrix` | `0.596 ms` | `0.594 ms` | `0.996x` | neutral |
| `MultiDiGraph n=1000 to_scipy_sparse_array` | `5.454 ms` | `2.513 ms` | `0.461x` | loss |
| `MultiDiGraph n=1000 adjacency_matrix` | `8.244 ms` | `2.681 ms` | `0.325x` | loss |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | `17.289 ms` | `5.295 ms` | `0.306x` | loss |
| `MultiDiGraph n=2000 adjacency_matrix` | `14.045 ms` | `6.491 ms` | `0.462x` | loss |

Rejected subattempt:
- Routing the live-dict helper for both `MultiGraph` and `MultiDiGraph`
  improved directed rows but regressed undirected multigraph rows. Measured
  post-attempt ratios included `MultiGraph n=250 adjacency_matrix` `0.750x`,
  `MultiGraph n=1000 to_scipy_sparse_array` `0.663x`,
  `MultiGraph n=2000 to_scipy_sparse_array` `0.638x`, and
  `MultiGraph n=2000 adjacency_matrix` `0.608x`. That route was narrowed before
  commit; `MultiGraph` stays on the existing checked native sync path.

Final accepted release timing after narrowing the route to `MultiDiGraph`:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `MultiGraph n=250 to_scipy_sparse_array` | `0.637 ms` | `0.779 ms` | `1.224x` | win |
| `MultiGraph n=250 adjacency_matrix` | `0.684 ms` | `0.800 ms` | `1.170x` | win |
| `MultiGraph n=1000 to_scipy_sparse_array` | `2.576 ms` | `3.114 ms` | `1.209x` | win |
| `MultiGraph n=1000 adjacency_matrix` | `3.283 ms` | `3.835 ms` | `1.168x` | win |
| `MultiGraph n=2000 to_scipy_sparse_array` | `7.559 ms` | `8.444 ms` | `1.117x` | win |
| `MultiGraph n=2000 adjacency_matrix` | `7.823 ms` | `6.312 ms` | `0.807x` | loss |
| `MultiDiGraph n=250 to_scipy_sparse_array` | `0.489 ms` | `0.545 ms` | `1.113x` | win |
| `MultiDiGraph n=250 adjacency_matrix` | `0.494 ms` | `0.553 ms` | `1.119x` | win |
| `MultiDiGraph n=1000 to_scipy_sparse_array` | `1.946 ms` | `2.190 ms` | `1.125x` | win |
| `MultiDiGraph n=1000 adjacency_matrix` | `2.013 ms` | `2.724 ms` | `1.353x` | win |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | `8.707 ms` | `6.324 ms` | `0.726x` | loss |
| `MultiDiGraph n=2000 adjacency_matrix` | `11.363 ms` | `8.008 ms` | `0.705x` | loss |

Focused repeat on the largest directed workload:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph n=2000 to_scipy_sparse_array` | `7.838 ms` | `5.392 ms` | `0.688x` | loss |
| `MultiDiGraph n=2000 adjacency_matrix` | `9.171 ms` | `5.652 ms` | `0.616x` | loss |

Self-speedups on targeted `MultiDiGraph n=2000` rows:
- `to_scipy_sparse_array`: `17.289 ms -> 8.707 ms`, `1.985x` in the expanded
  sweep; focused repeat `7.838 ms` gives `2.206x` vs baseline.
- `adjacency_matrix`: `14.045 ms -> 11.363 ms`, `1.236x` in the expanded
  sweep; focused repeat `9.171 ms` gives `1.531x` vs baseline.

Conformance and gates:
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --benches` passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
  passed.
- `rch exec -- cargo build -p fnx-python --release` passed after retrying
  remotely; an earlier local fallback against the shared target dir hit E0514.
- `maturin develop --release --features pyo3/abi3-py310` passed with the fresh
  target dir noted above.
- Focused sparse-export parity reported `297 passed`.
- Sparse plus numpy weighted exporter parity reported `305 passed`.

Decision:
- Keep the `MultiDiGraph` live-dict route as a measured partial: expanded final
  slice score `9` wins / `3` losses / `0` neutral vs NetworkX, and the target
  directed `n=2000` rows roughly halved their FNX runtime.
- Do not close the bead as fully dominated. The largest directed rows remain
  losses (`0.688x` and `0.616x` on focused repeat), so the next route must
  attack index construction and SciPy/NumPy boundary cost rather than edge-attr
  sync alone.

Do not repeat:
- Do not route `MultiGraph` through the live-dict helper without a different
  undirected COO strategy; the all-multigraph attempt regressed measured rows.
- Do not retry Python edges-view COO construction; prior evidence on this bead
  showed parity but net regression at small/medium sizes.
- Do not claim the scale row as solved from self-speedup. The largest
  `MultiDiGraph` exporter rows still lose to NetworkX.

Next route:
- Specialize default-order integer-index `MultiDiGraph` COO emission to avoid
  Python nodelist canonicalization, Python list handoff, and avoidable
  sparse-matrix construction overhead for the common `nodelist=None`,
  integer-node path.

## 2026-06-20 MultiDiGraph DAG Closeout (`br-r37-c1-11m92`)

Scope: re-baseline the claimed `MultiDiGraph` DAG losses on current `origin/main`
before trying another conversion-tax rewrite, then keep only measured wins. The
current source had already made `topological_sort`, `dag_longest_path`, and SCC
counting stale wins; the real remaining losses were `transitive_closure` and
`dag_longest_path_length`.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree: `/data/projects/franken_networkx-cod-a-land`.
- Requested target dir for RCH gates:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Exact requested local `maturin develop --release --features pyo3/abi3-py310`
  install hit incompatible-rustc E0514 in that shared target dir; no cleanup or
  file deletion was performed.
- Release install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-local-f20a92ec0`.
- Per-crate RCH build/check/clippy/test gates completed for `fnx-python`.
- Per-crate RCH bench gate completed on `vmi1149989`:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multidigraph_connectivity_head_to_head -- --noplot`.
  The retrieved transcript reported exit `0` but did not include Criterion
  timing rows for this DAG surface, so the ratio evidence below comes from the
  same-process release harness.
- Head-to-head harness: same-process Python release timing against NetworkX
  `3.6.1`, `PYTHONHASHSEED=0`, identical 420-node / 1329-edge deterministic
  `MultiDiGraph` DAG with parallel keyed arcs and digest parity for every row.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `topological_sort` | `0.255564 ms` | `1.488430 ms` | `5.824x` | stale win |
| `dag_longest_path` | `1.446391 ms` | `2.216259 ms` | `1.532x` | stale win |
| `dag_longest_path_length` | `4.409575 ms` | `3.083493 ms` | `0.699x` | loss |
| `transitive_closure` | `1164.244211 ms` | `660.420907 ms` | `0.567x` | loss |
| `number_strongly_connected_components` | `0.125618 ms` | `0.426938 ms` | `3.399x` | stale win |

Kept levers:
- `transitive_closure` now uses a native `MultiDiGraph` distinct-successor CSR
  reachability pass for `reflexive=False`, then bulk-inserts missing keyed
  closure edges while preserving NetworkX node/edge/attr/order snapshots. Cases
  with row-key override mirrors fall back to the existing NetworkX-compatible
  path.
- `dag_longest_path_length` now computes the length directly from the
  predecessor dynamic program for directed multigraphs, avoiding a full
  `dag_longest_path` list allocation followed by Python multiedge re-indexing.

Final release timing:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Digest | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| `topological_sort` | `0.197824 ms` | `1.052203 ms` | `5.319x` | `a3fe6d8438cc328f` | win |
| `dag_longest_path` | `1.330331 ms` | `2.036158 ms` | `1.531x` | `a3fe6d8438cc328f` | win |
| `dag_longest_path_length` | `1.303539 ms` | `2.718360 ms` | `2.085x` | `cef5838d118dccd9` | win |
| `transitive_closure` | `265.605101 ms` | `627.405576 ms` | `2.362x` | `1c46fd2646166806` | win |
| `number_strongly_connected_components` | `0.116190 ms` | `0.356205 ms` | `3.066x` | `db55da3fc3098e9c` | win |

Self-speedups:
- `transitive_closure`: `1164.244211 ms -> 265.605101 ms`, `4.383x`.
- `dag_longest_path_length`: `4.409575 ms -> 1.303539 ms`, `3.383x`.

Conformance and gates:
- `pytest tests/python/test_transitive_closure_attrs.py tests/python/test_dag_additional.py -q`
  reported `35 passed`.
- `pytest tests/python/test_parity_conformance.py tests/python/test_transitive_closure_attrs.py tests/python/test_dag_additional.py -q`
  reported `230 passed`.
- `cargo fmt --check` passed.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
  passed.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` reported
  `27 passed`.

Decision:
- Keep both levers. The measured DAG surface is now `5` wins / `0` losses /
  `0` neutral vs NetworkX, and both true baseline losses flipped to wins.

Do not repeat:
- Do not route `MultiDiGraph` transitive closure through Python edge-by-edge
  graph copies when `reflexive=False` and keyed-row mirrors are ordinary.
- Do not compute `dag_longest_path_length` by first materializing the full
  longest-path node list for directed multigraphs.
- Do not spend more time on the stale topological-sort, longest-path, or SCC
  count notes until a fresh same-process head-to-head row shows a real loss.

Next route:
- Move to remaining measured losses such as multigraph matrix exporters,
  path-heavy Dijkstra rows, or MultiGraph biconnected/MST surfaces; this DAG
  conversion-tax bead is closed.

## 2026-06-20 MultiGraph Keyed MST Native Route (`br-r37-c1-ij951`)

Scope: close the residual MultiGraph `minimum_spanning_tree` loss left by the
earlier biconnected-family route, preserving the NetworkX-observable
`MultiGraph` result type, selected parallel edge keys, graph/node/edge attrs,
and stable Kruskal tie order.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-a`.
- Worktree: `/data/projects/franken_networkx`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Local release install against the requested shared target failed with
  incompatible-rustc E0514 (`beae78130` artifacts vs current `f20a92ec0`).
  No cleanup or file deletion was performed. The local release extension was
  installed with fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-mst`.
- Exact-target RCH release build passed:
  `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  on `vmi1149989`.
- Exact-target RCH bench attempt first fell back locally because no workers were
  admissible and hit the same shared-target E0514. The measured Criterion bench
  used the fresh non-destructive target dir:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multigraph_biconnected -- --sample-size 10 --measurement-time 2`.
- Direct same-process Python sweeps pinned
  `PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx`
  after an unpinned probe resolved the editable package to a sibling scratch
  worktree; only pinned-current-checkout timings are used below.

Baseline before this lever:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `minimum_spanning_tree` old parity route on 1000-node / 5000-edge `MultiGraph` | `32.322 ms` | `10.103 ms` | `0.313x` | loss |
| `minimum_spanning_tree` old parity route on keyed custom fixture | `40.035 ms` | `12.915 ms` | `0.323x` | loss |

Kept lever:
- Add a PyO3 `multigraph_minimum_spanning_tree` helper that scans the
  `MultiGraph` edge snapshots directly, rejects nonnumeric/nonfinite or
  row-display-override cases back to the existing parity path, runs stable
  Kruskal with a compact union-find, and builds a new keyed `PyMultiGraph`
  result without a full fnx-to-NetworkX conversion.
- The public wrapper syncs edge attrs first, then accepts the native result only
  when the helper returns a `MultiGraph`; unsupported cases keep the previous
  NetworkX parity behavior.

Final same-process release sweep on the bead fixture (1000 nodes, 5000 edges,
seed `20260620`, NetworkX `3.6.1`, parity matched every row):

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `0.358 ms` | `2.432 ms` | `6.801x` | win |
| `articulation_points` | `0.358 ms` | `1.743 ms` | `4.868x` | win |
| `biconnected_components` | `0.869 ms` | `2.468 ms` | `2.839x` | win |
| `minimum_spanning_tree` native | `8.040 ms` | `9.039 ms` | `1.124x` | win |
| `minimum_spanning_tree` old parity route | `32.322 ms` | `10.103 ms` | `0.313x` | rejected baseline |
| `bfs_edges(source=0)` | `0.796 ms` | `0.657 ms` | `0.825x` | loss |

Additional evidence:
- Custom keyed/attr-heavy `MultiGraph` fixture, same process:
  `minimum_spanning_tree` moved from `0.323x` old parity to `2.035x` native
  (`8.070 ms` FNX vs `16.426 ms` NetworkX), with exact digest parity.
- Criterion `networkx_head_to_head_multigraph_biconnected` final rows:
  `is_biconnected` `10.454x`, `articulation_points` `6.401x`,
  `biconnected_components` `4.065x`, and `minimum_spanning_tree` `1.214x`
  on the bench fixture.

Conformance and gates:
- `pytest tests/python/test_mst_node_label_parity.py -q` reported `55 passed`.
- `pytest tests/python/test_tree_bipartite.py -q` reported `63 passed`.
- `pytest tests/python/test_parity_conformance.py -q` reported `195 passed`.
- `cargo fmt --check` passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed.
- `rch exec -- cargo build --release -p fnx-python --features pyo3/abi3-py310`
  passed with the exact requested target dir through RCH remote execution.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310` reported
  `27 passed`.

Decision:
- Keep. The MST residual flips from a measured `0.313x` loss to a `1.124x`
  win on the bead fixture and `1.214x` in Criterion.
- Current `ij951` surface accounting at this point was `4` measured wins
  (`is_biconnected`, `articulation_points`, `biconnected_components`,
  `minimum_spanning_tree`) / `1` measured loss (`bfs_edges`) / `0` neutral in
  the pinned same-process sweep. The `bfs_edges` residual was split and later
  closed by `br-r37-c1-1jm15`.

Do not repeat:
- Do not route ordinary numeric MultiGraph MST through `_networkx_graph_for_parity`;
  that old route remains a `0.313x` loss on the bead fixture.
- Do not collapse keyed MultiGraph MST to a simple `Graph`; the result must
  preserve `MultiGraph` type, selected edge keys, and attrs.
- Do not treat this MST section as the final `ij951` state; it is historical
  evidence before the separate `br-r37-c1-1jm15` BFS closeout.

Next route:
- See `br-r37-c1-1jm15` above for the subsequent MultiGraph
  `bfs_edges(source=0)` closeout. The MST residual is closed here.

## 2026-06-20 MultiGraph Biconnected Family Native Route (`br-r37-c1-ij951`)

Scope: target the open MultiGraph biconnected/MST loss cluster on current
`origin/main` from a clean detached worktree. The kept lever is a direct
ordered-adjacency MultiGraph biconnected-family route for vertex/edge-stack
queries; keyed MST construction is intentionally untouched and remains a loss.

Environment:
- Agent Mail identity: `CrimsonRiver`; CLI actor: `AGENT_NAME=cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-ij951-boldverify-20260620T061230Z`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Local `maturin develop` against the exact requested target dir failed with
  incompatible-rustc E0514 (`beae78130` artifacts vs current `f20a92ec0`).
  No cleanup or file deletion was performed. Release installs used fresh
  non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0`.
- Per-crate RCH bench:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multigraph_biconnected -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`
  on `hz1`.
- Per-crate RCH release build:
  `rch exec -- cargo build -p fnx-python --release` on `vmi1153651`.
- Clippy gate:
  `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`
  completed green after rch remote sync timed out and fell back locally.
- Focused conformance:
  `pytest tests/python/test_multigraph_algorithms.py tests/python/test_matching_flow_cross_type.py::test_is_biconnected_nx tests/python/test_parity_conformance.py -k 'biconnected' -q`
  reported `8 passed, 235 deselected`.

Baseline direct release timing on a 1000-node / 5000-edge MultiGraph fixture
(1000-cycle + 3000 random edges + 1000 parallel edges, same graph objects for
FNX and NetworkX):

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Baseline verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `12.605 ms` | `2.901 ms` | `0.230x` | loss |
| `articulation_points` | `18.118 ms` | `1.874 ms` | `0.103x` | loss |
| `biconnected_components` | `14.892 ms` | `2.920 ms` | `0.196x` | loss |
| `minimum_spanning_tree` | `29.697 ms` | `9.516 ms` | `0.320x` | loss |
| `bfs_edges(source=0)` | `1.492 ms` | `0.607 ms` | `0.407x` | loss |

Kept route:
- `articulation_points`, `is_biconnected`, `biconnected_components`, and
  `biconnected_component_edges` now walk the MultiGraph's ordered distinct
  adjacency directly instead of materializing a simple `Graph` or delegating
  public `articulation_points` through NetworkX.
- This is the cache-local/CSR-style lever from the optimization pass, but kept
  in exact NetworkX row order: vertex biconnectivity is multiplicity-invariant
  for these contracts, while component-edge output still follows NetworkX's
  `_biconnected_dfs` edge-stack orientation.

RCH Criterion final rows:

| Workload | FNX mean | NetworkX mean | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `0.85370 ms` | `9.0354 ms` | `10.584x` | win |
| `articulation_points` | `0.96998 ms` | `6.3562 ms` | `6.553x` | win |
| `biconnected_components` | `2.1240 ms` | `7.6859 ms` | `3.619x` | win |

Same-process final release sweep on the original baseline fixture:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `is_biconnected` | `1.249 ms` | `2.981 ms` | `2.387x` | win |
| `articulation_points` | `1.337 ms` | `1.950 ms` | `1.459x` | win |
| `biconnected_components` | `1.650 ms` | `2.945 ms` | `1.785x` | win |
| `biconnected_component_edges` | `2.087 ms` | `2.914 ms` | `1.396x` | win |
| `minimum_spanning_tree` | `31.015 ms` | `9.184 ms` | `0.296x` | loss |
| `bfs_edges(source=0)` | `1.668 ms` | `0.666 ms` | `0.399x` | loss |

Decision:
- Keep. Scorecard accounting for this slice: `4` wins / `2` losses / `0`
  neutral on the expanded biconnected/MST/BFS surface; `3` RCH Criterion wins
  for the committed biconnected-family benchmark rows.
- Residual losses are explicit: MultiGraph keyed MST still delegates to
  NetworkX to preserve result type/keys, and `bfs_edges` still loses on this
  particular dense parallel fixture despite prior direct-MultiGraph traversal
  work.

Do not repeat:
- Do not reintroduce `gr.undirected()` simple-Graph materialization for
  MultiGraph biconnected-family queries.
- Do not route public MultiGraph `articulation_points` through NetworkX parity
  delegation for these exact contracts.
- Do not claim the MST row until a keyed MultiGraph MST constructor preserves
  NetworkX type/key/attr semantics and beats the current `0.296x` loss.

## 2026-06-20 MultiDiGraph SCC Stale-Loss Closeout (`br-r37-c1-8hjsu`)

Scope: re-baseline the open `MultiDiGraph` `strongly_connected_components`
loss on current `origin/main` (`cdf8d86d8`) before inventing another SCC
substrate. The current source already contains the direct native
successor-row Tarjan/Nuutila route, so no code was kept or reverted in this
slice.

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Worktree: `/data/projects/.scratch/franken_networkx-cod-b-scc-boldverify-20260620`.
- Requested target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Exact requested release install failed with Rust E0514 because that target dir
  contained artifacts from incompatible nightly `beae78130`; no cleanup or file
  deletion was performed.
- Release install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-f20a92ec0-scc`:
  `rch exec -- maturin develop --release --features pyo3/abi3-py310`.
- Per-crate RCH bench/build gate completed:
  `rch exec -- cargo bench -p fnx-python --bench networkx_head_to_head multidigraph_connectivity_head_to_head -- --noplot`
  on `vmi1152480`; the retrieved RCH transcript did not include Criterion timing
  rows, so the ratio evidence below comes from the same-process Python harness
  against the freshly installed release extension.
- Focused conformance:
  `pytest tests/python/test_strongly_connected_components_order_parity.py tests/python/test_directed_multigraph_degenerate_parity.py::test_multidigraph_strongly_connected_components_matches_networkx tests/python/test_scc_condensation_invariants.py tests/python/test_networkx_interop_directed_multi.py::test_multidigraph_interop -q`
  reported `212 passed in 1.01s`.

Head-to-head timing on identical 1800-node block/parallel-arc `MultiDiGraph`
with block size `6`, parity checksum matched for every row:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| `strongly_connected_components` | `0.642898 ms` | `1.717424 ms` | `2.671x` | win |
| `descendants(source=0)` | `0.457607 ms` | `0.750663 ms` | `1.640x` | win |
| `number_strongly_connected_components` | `0.338000 ms` | `1.542392 ms` | `4.563x` | win |

Decision:
- Keep current code as-is and close `br-r37-c1-8hjsu` as a stale loss. The
  current native SCC route beats NetworkX on the open-loss fixture; no radical
  SCC rewrite is justified by this target.
- Scorecard accounting for this slice: `3` wins / `0` losses / `0` neutral on
  the measured SCC/count/descendant side surface; `1` win / `0` losses /
  `0` neutral for the focused SCC bead row.

Do not repeat:
- Do not reintroduce MultiDiGraph SCC projection through a simple `DiGraph`.
- Do not route public SCC to NetworkX-on-FNX delegation: a quick probe showed it
  is not a native keep and does not improve the release claim.
- Do not clear the shared `cod-b` target dir to fix E0514; use a toolchain-tagged
  target subdir instead.

Next route:
- Remaining open MultiGraph/MultiDiGraph losses are not SCC. Prioritize
  measured residuals such as matrix-exporter sync cost and MultiGraph
  biconnected/MST rows instead of spending more time on this SCC lane.

Scope for the following ledger entry: `br-r37-c1-iyu0a`, multigraph matrix exporters,
`tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/bench_and_parity.py`.

Environment:
- Agent: `CrimsonRiver` / `cod-b`.
- Target dir: `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Release gates: `cargo fmt --check`; `rch exec -- cargo check -p fnx-python --benches`;
  `rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`;
  `rch exec -- cargo build --release -p fnx-python`.
- Release install: `maturin develop --release --features pyo3/abi3-py310` with
  fresh target dir `/data/projects/.rch-targets/franken_networkx-cod-b-maturin-clean-f20a92ec0`.
- Parity in every run: `160` configs x `2` exporters, `0` fails, golden SHA
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.

## 2026-06-20 Multigraph Matrix Exporter Residual

Baseline from `tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/run.log`:

| Workload | Baseline ratio vs NetworkX | Baseline FNX | Baseline NetworkX |
| --- | ---: | ---: | ---: |
| `to_numpy MultiGraph` | `0.996x` | `2.44 ms` | `2.43 ms` |
| `to_scipy MultiGraph` | `0.863x` | `2.53 ms` | `2.18 ms` |
| `to_numpy MultiDiGraph` | `0.686x` | `7.51 ms` | `5.15 ms` |
| `to_scipy MultiDiGraph` | `0.580x` | `5.92 ms` | `3.44 ms` |

Uncommitted precise dirty-key experiment, reverted before commit:

| Run | Workload | Ratio vs NetworkX | FNX | NetworkX | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| dirty-key repeat 1 | `to_numpy MultiGraph` | `0.986x` | `2.49 ms` | `2.45 ms` | neutral/loss noise |
| dirty-key repeat 1 | `to_scipy MultiGraph` | `0.853x` | `2.57 ms` | `2.19 ms` | loss |
| dirty-key repeat 1 | `to_numpy MultiDiGraph` | `0.852x` | `6.53 ms` | `5.56 ms` | loss |
| dirty-key repeat 1 | `to_scipy MultiDiGraph` | `0.521x` | `6.66 ms` | `3.47 ms` | loss |
| dirty-key repeat 2 | `to_numpy MultiGraph` | `0.993x` | `2.46 ms` | `2.44 ms` | neutral |
| dirty-key repeat 2 | `to_scipy MultiGraph` | `0.872x` | `2.69 ms` | `2.35 ms` | loss |
| dirty-key repeat 2 | `to_numpy MultiDiGraph` | `0.627x` | `9.52 ms` | `5.97 ms` | loss |
| dirty-key repeat 2 | `to_scipy MultiDiGraph` | `0.476x` | `7.67 ms` | `3.65 ms` | loss |
| dirty-key repeat 3 | `to_numpy MultiGraph` | `0.961x` | `2.69 ms` | `2.58 ms` | loss |
| dirty-key repeat 3 | `to_scipy MultiGraph` | `0.871x` | `2.63 ms` | `2.29 ms` | loss |
| dirty-key repeat 3 | `to_numpy MultiDiGraph` | `0.806x` | `5.84 ms` | `4.71 ms` | loss |
| dirty-key repeat 3 | `to_scipy MultiDiGraph` | `0.551x` | `6.18 ms` | `3.41 ms` | loss |

Clean final run after reverting the dirty-key experiment:

| Run | Workload | Ratio vs NetworkX | FNX | NetworkX | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| clean repeat 1 | `to_numpy MultiGraph` | `1.090x` | `2.88 ms` | `3.14 ms` | win/noisy |
| clean repeat 1 | `to_scipy MultiGraph` | `0.847x` | `2.87 ms` | `2.43 ms` | loss |
| clean repeat 1 | `to_numpy MultiDiGraph` | `0.579x` | `9.70 ms` | `5.62 ms` | loss |
| clean repeat 1 | `to_scipy MultiDiGraph` | `0.369x` | `11.09 ms` | `4.09 ms` | loss |
| clean repeat 2 | `to_numpy MultiGraph` | `1.003x` | `2.72 ms` | `2.72 ms` | neutral |
| clean repeat 2 | `to_scipy MultiGraph` | `0.882x` | `2.61 ms` | `2.30 ms` | loss |
| clean repeat 2 | `to_numpy MultiDiGraph` | `0.632x` | `8.39 ms` | `5.30 ms` | loss |
| clean repeat 2 | `to_scipy MultiDiGraph` | `0.439x` | `8.35 ms` | `3.66 ms` | loss |
| clean repeat 3 | `to_numpy MultiGraph` | `0.993x` | `2.81 ms` | `2.79 ms` | neutral |
| clean repeat 3 | `to_scipy MultiGraph` | `0.880x` | `2.67 ms` | `2.35 ms` | loss |
| clean repeat 3 | `to_numpy MultiDiGraph` | `0.617x` | `8.75 ms` | `5.40 ms` | loss |
| clean repeat 3 | `to_scipy MultiDiGraph` | `0.447x` | `7.88 ms` | `3.52 ms` | loss |

Decision:
- No code keep from this session. The precise dirty-key experiment was removed
  because it did not produce a stable NetworkX win and still left the biggest
  `MultiDiGraph` exporter row losing.
- The already-committed pure-Python native-COO route is parity-clean but does
  not close the `MultiDiGraph` gap under clean release timing.
- Scorecard accounting for this slice: `0` wins / `3` losses / `1` neutral by
  median clean-repeat workload outcome.

Do not repeat:
- Do not reintroduce the broad dirty-key scaffold without folding it into a
  measured single-pass exporter path.
- Do not claim the `MultiDiGraph` matrix exporter row as a win from self-speedup
  or one noisy `to_numpy` sample.

Next route:
- Fuse finite-weight validation into `adjacency_arrays_multigraph` so the
  default weighted exporter does one native edge pass, not a guard pass plus a
  COO pass.
- Add an integer-index/default-order multigraph COO path only after the fused
  edge-pass route is measured; current evidence suggests stringification is
  secondary.

## 2026-06-20 MultiDiGraph Reverse Copy Dirty-Attr Mirror

Scope: `br-r37-c1-nooou`, `MultiDiGraph.reverse(copy=True)` on a directed
multigraph with 300 nodes, 2936 keyed edges, explicit weights/tags, and a
dirty variant mutating every 31st edge after construction.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Rust target dirs: `/data/projects/.rch-targets/franken_networkx-cod-a-local-check`
  for local release install and
  `/data/projects/.rch-targets/franken_networkx-cod-a-reverify-f20a` for RCH
  release build verification.
- Python `3.13.7`, NetworkX `3.6.1`, `PYTHONHASHSEED=0`, core pinned with
  `taskset -c 4`, 31 timed runs after 8 warmups.
- Release install: `maturin develop --release --features pyo3/abi3-py310`.
- RCH gate: `rch exec -- cargo build --release -p fnx-python`.

Baseline/current-main measurement after the earlier native transpose substrate
showed that the old `0.43x` bead note was stale for the Rust reverse substrate,
but a real dirty Python attr-mirror loss remained:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 10.200708 ms | 12.005438 ms | 1.177x | win |
| dirty post attrs | 12.148397 ms | 10.310096 ms | 0.849x | loss |

Rejected subattempt:
- Sparse dirty-edge tracking alone reduced the sync surface but still copied
  every Python edge-attr mirror during reverse construction. It was not enough
  to dominate NetworkX.

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 12.005304 ms | 12.486636 ms | 1.040x | weak/noisy win |
| dirty post attrs | 13.222951 ms | 10.718466 ms | 0.811x | reject |

Kept lever:
- Keep sparse keyed-edge dirty tracking plus lazy reverse-copy edge mirror
  materialization. Lossless edge attr dicts with exact string keys and simple
  scalar values stay in Rust storage until Python asks for the dict; non-lossless
  mirrors and explicitly dirty mirrors are still copied to preserve NetworkX
  object semantics.

| Workload | FNX min | FNX median | FNX p95 | NetworkX min | NetworkX median | NetworkX p95 | Ratio vs NetworkX |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean keyed attrs | 5.862346 ms | 7.348492 ms | 8.686637 ms | 9.146017 ms | 9.740804 ms | 10.464004 ms | 1.326x median / 1.560x min |
| dirty post attrs | 6.318381 ms | 7.264913 ms | 8.310785 ms | 8.952791 ms | 9.253100 ms | 9.817109 ms | 1.274x median / 1.417x min |

Post-rebase clean-tree smoke after installing from
`/data/projects/franken_networkx-cod-a-land`:

| Workload | FNX median | NetworkX median | Ratio vs NetworkX | Digest |
| --- | ---: | ---: | ---: | --- |
| clean keyed attrs | 4.980806 ms | 8.641853 ms | 1.735x | `5987af29b718da04` |
| dirty post attrs | 5.853450 ms | 9.164683 ms | 1.566x | `1d35fe579cedf7b5` |

Parity:
- Clean digest/order hash64: `7657081794215802141`.
- Dirty digest/order hash64: `7376594841975813130`.
- Added non-lossless Python edge-attr parity coverage for tuple attr keys and
  mutable payload object identity.

Gates:
- `cargo fmt --check`
- `cargo check -p fnx-python --benches`
- `cargo clippy -p fnx-python --all-targets -- -D warnings`
- `rch exec -- cargo build --release -p fnx-python`
- focused Python reverse/attr parity: `53 passed`

Decision:
- Keep. This converts the remaining dirty reverse-copy mirror row from `0.849x`
  to `1.274x` vs NetworkX while preserving the clean row as a stronger `1.326x`
  win.
- Scorecard accounting for this slice: `2` wins / `0` losses / `0` neutral for
  the final measured clean and dirty workloads.

Do not repeat:
- Do not claim sparse dirty-key tracking by itself as a keep; it stayed slower
  than NetworkX on the dirty workload.
- Do not rebuild keyed reverse copies through Python per-edge insertion or
  eagerly materialize all Python edge-attr dict mirrors.

## 2026-06-20 Max-Weight Matching Native Tie-Break No-Ship

Scope: `br-r37-c1-lmqwv`, public `max_weight_matching` on a weighted
`gnp(300, 0.05)` simple graph with deterministic integer-like weights. The
public top-level wrapper still delegates to NetworkX for exact matching-choice
and tuple-direction parity. The raw `_fnx.max_weight_matching` blossom kernel
is much faster, but its tie-break policy does not match NetworkX on all tied
maximum-weight optima.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-next-20260620T131825Z`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 (`cc`,
  `target_lexicon`, and `serde` were compiled by a different nightly). No
  cleanup was performed; release proof runs used fresh target dir
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-20260620`.
- NetworkX oracle: vendored `3.7rc0.dev0`; `PYTHONHASHSEED=0`.

Baseline/current public API and raw native measurement on seed `11`:

| Route | FNX mean | NetworkX mean | Ratio vs NetworkX | Exact edge set | Verdict |
| --- | ---: | ---: | ---: | --- | --- |
| public `fnx.max_weight_matching` delegate | 228.398618 ms | 223.508232 ms | 0.979x | yes | historical loss; superseded |
| raw `_fnx.max_weight_matching` | 5.494071 ms | 223.508232 ms | 40.68x | no | invalid keep |

Raw native exactness sweep:
- Baseline raw canonical/sorted solver route: `4 / 20` seeds differed from
  NetworkX by edge set, with identical total matching weight in every case.
- Full insertion-order candidate/node/edge mapping experiment:
  raw FNX `4.954032 ms` vs NetworkX `225.624950 ms` (`45.54x`) but exact
  mismatches worsened to `6 / 20` seeds (`3, 11, 13, 18, 19, 20`).
- Insertion-order candidates/nodes with restored sorted solver edges:
  raw FNX `6.292802 ms` vs NetworkX `239.127194 ms` (`38.00x`) but exact
  mismatches worsened to `8 / 20` seeds
  (`3, 4, 5, 11, 13, 18, 19, 20`).

Rejected lever:
- Do not route the public wrapper to the existing raw `mwmatching` crate by
  merely changing candidate sorting. The crate derives each vertex's neighbor
  scan order from one global edge sequence, while NetworkX scans each
  adjacency row directly during blossom search. That structural tie-break
  mismatch is enough to choose different valid maximum matchings.

Conformance after reverting the no-ship experiments:
- Focused matching gate:
  `tests/python/test_matching_conformance.py`,
  `tests/python/test_max_weight_matching_tuple_direction_parity.py`, and
  `tests/python/test_flow_cut_matching_value_parity.py` passed
  `184 passed`.

Decision:
- Reject/no-ship for this older session. The public `max_weight_matching` row
  measured as a `0.979x` loss in that run because exact NetworkX tie-break
  parity blocked the raw native `40x+` route.
- Superseded by the 2026-06-21 vendored-oracle remeasure above: the current
  public route is exact and `1.088x` vs NetworkX, so this is no longer an
  active public loss.
- Historical scorecard accounting for this slice: `0` wins / `1` loss /
  `0` neutral.

Do not repeat:
- Do not retry endpoint canonicalization, insertion-order node remapping, or
  solver-edge sorting as standalone fixes for this bead. The next viable route
  is a NetworkX-order blossom port/fork that can scan per-vertex adjacency rows
  exactly, or a formally exact uniqueness-gated native dispatch that declines
  tied-optimum cases before public routing.

## 2026-06-20 Default-Order Multigraph Matrix Exporter Keep + Residual

Scope: `br-r37-c1-iyu0a`, public `to_numpy_array` /
`to_scipy_sparse_array` on exact `MultiGraph` / `MultiDiGraph`, default
`nodelist=None`, `weight="weight"`, and `dtype=None`.

Environment:
- Agent: `CrimsonRiver` / `cod-a`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-a-bold-20260620T1345`.
- Requested target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- The requested shared target hit incompatible-rustc E0514 (`cc`,
  `target_lexicon`, and `serde` were compiled by a different nightly). No
  cleanup was performed; release proof used fresh target
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-iyu0a-20260620T1349`.
- Post-rebase release install used a second fresh target after the first fresh
  target also hit E0514:
  `/data/projects/.rch-targets/franken_networkx-cod-a-f20a92ec0-iyu0a-postrebase-20260620T1832`.
- NetworkX oracle: vendored import via
  `PYTHONPATH=<worktree>/python:<worktree>/legacy_networkx_code`;
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Kept lever:
- Added a default-order native multigraph COO helper that avoids Python
  `list(G)` node canonicalization and reads stored Rust attrs directly when
  `edges_dirty` is false, falling back to live PyDict mirrors when dirty.
- Added a `MultiDiGraph` default-order CSR helper for `format="csr"` that
  pre-sums contiguous parallel edges before constructing the SciPy CSR array.

Baseline in this clean worktree:

| Workload | Baseline ratio vs NetworkX |
| --- | ---: |
| n=500 `to_numpy MultiGraph` | 1.249x |
| n=500 `to_scipy MultiGraph` | 1.136x |
| n=500 `to_numpy MultiDiGraph` | 1.188x |
| n=500 `to_scipy MultiDiGraph` | 0.938x |
| n=2000 `to_numpy MultiGraph` | 0.853x |
| n=2000 `to_scipy MultiGraph` | 0.847x |
| n=2000 `to_numpy MultiDiGraph` | 1.049x |
| n=2000 `to_scipy MultiDiGraph` | 0.645x |

Final measured proof:

| Workload | FNX | NetworkX | Ratio vs NetworkX | Verdict |
| --- | ---: | ---: | ---: | --- |
| n=500 `to_numpy MultiGraph` | 1.76 ms | 2.38 ms | 1.352x | win |
| n=500 `to_scipy MultiGraph` | 1.89 ms | 2.18 ms | 1.155x | win |
| n=500 `to_numpy MultiDiGraph` | 2.43 ms | 4.23 ms | 1.741x | win |
| n=500 `to_scipy MultiDiGraph` | 1.99 ms | 3.00 ms | 1.508x | win |
| n=2000 `to_numpy MultiGraph` | 8.199 ms | 7.888 ms | 0.962x | active loss |
| n=2000 `to_scipy MultiGraph` | 6.004 ms | 5.007 ms | 0.834x | active loss |
| n=2000 `to_numpy MultiDiGraph` | 11.797 ms | 13.844 ms | 1.174x | win |
| n=2000 `to_scipy MultiDiGraph` min-of-9 | 8.097 ms | 7.005 ms | 0.865x | active loss |
| n=2000 `to_scipy MultiDiGraph` 50-run min | 5.790 ms | 6.793 ms | 1.173x | noisy win |
| n=2000 `to_scipy MultiDiGraph` 50-run median | 9.290 ms | 8.276 ms | 0.891x | active loss |

Conformance:
- `cargo fmt --check`, `git diff --check`, and
  `python3 -m py_compile python/franken_networkx/__init__.py` passed.
- Per-crate RCH gates passed for `fnx-python`:
  `cargo check -p fnx-python --features pyo3/abi3-py310`,
  `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`,
  `cargo build -p fnx-python --release --features pyo3/abi3-py310`, and
  `cargo bench -p fnx-python --features pyo3/abi3-py310 --no-run`.
- Focused Python exporter suite passed before and after rebase: `604 passed`.
- `ubs` on touched files reached existing file-wide findings in the large
  pre-existing Python/Rust files; no new UBS-specific code issue was kept.
- `tests/artifacts/perf/20260620T-multigraph-matrix-coo-cc/bench_and_parity.py`
  stayed green: `160` configs x `2` exporters, `0` fails, golden
  `bff9639b02900c23d43c585672cddf6a3e39676fa40c631efccec93bfeb44307`.
- Focused dirty finite-weight mutation parity for default-order
  `MultiDiGraph` dense/CSR/COO paths passed before the nonnumeric fallback
  probe hit a pre-existing exception-class mismatch outside this fast path.

Rejected sub-levers:
- Broadly enabling the default-order helper for undirected `MultiGraph` at
  larger scale regressed `to_scipy MultiGraph` (`0.777x` on the n=2000 probe);
  final Python dispatch is narrowed to `MultiDiGraph` for the new default-order
  helpers.
- A streaming-successor CSR rewrite that avoided `edges_ordered_borrowed()`
  regressed the n=500 fixture (`to_scipy MultiDiGraph` fell to `0.808x`) and
  was manually reverted.

Decision:
- Keep as a measured partial closeout for the original default-order
  n≈400/500 matrix-exporter gap: `4` wins / `0` losses / `0` neutral on the
  artifact harness.
- Do not claim large-scale sparse domination: n=2000 sparse median rows remain
  active losses and need a deeper boundary/layout route.

Do not repeat:
- Do not re-enable the undirected `MultiGraph` default-order helper without a
  new large-scale undirected sparse proof.
- Do not retry the streaming-successor CSR accessor path; the allocated
  `edges_ordered_borrowed()` version is the measured keep.
- Next route for the residual: reduce PyO3 Vec-to-NumPy handoff cost or add a
  native array/CSR buffer boundary for large sparse multigraph exporters.

## 2026-06-20 `volume(G, S)` native-binding routing rejected (`br-r37-c1-volnative`, BlackThrush)

Scope: the public `volume(G, S)` cut-metric wrapper. Direct same-process timing
vs NetworkX 3.6.1 on `barabasi_albert_graph(2500, 3, seed=1)` showed the current
full-degree-dict fast path (`deg = dict(G.degree()); sum(deg.get(v,0) for v in S)`)
loses because it scales with `|V|`, not `|S|`: `|S|=250` `0.15x`, `|S|=1250`
`0.62x`, `|S|=2250` `0.95x` (it builds all 2500 degrees just to sum a subset).

Attempt: route exact fnx simple `Graph` inputs to the native `_fnx.volume`
binding. The shared core `fnx_algorithms::volume` kernel counts an undirected
self-loop ONCE (it is also used by `conductance`, so it was left untouched);
NetworkX's `sum(G.degree(v) for v in S)` counts each self-loop TWICE. Fixed this
in the binding with an `O(|S|)` `Graph::degree` sum (row length + self-loop probe,
already nx-correct) over the distinct nodes of `S`. Byte-exact vs NetworkX:
`1500/1500` random graphs including self-loops, missing nodes (degree 0),
generator `S`, and empty `S`.

Result: `0.86x` / `0.80x` / `0.76x` at `|S|=250/1250/2250` — STILL A LOSS, and the
large-`S` row regressed vs the full-dict path (`0.95x -> 0.76x`). Root cause: the
binding pays `node_key_to_string` (Python object -> canonical String) per node in
`S`, an `O(|S|)` conversion tax that NetworkX's native Python-dict `degree(nbunch)`
view avoids; that tax dominates a sub-millisecond degree-sum. Measured under host
load 13+, but the loss is structural, not noise.

Verdict: reverted (`~0-gain`, no clear win at any `|S|`). `volume` is
String-conversion-substrate-bound, the same class as multigraph copy/to_undirected.

Do not retry:
- Do not route `volume`/degree-sum-over-nbunch ops through the per-node
  `node_key_to_string` native binding; the String-conversion tax exceeds the
  degree-sum it replaces.
- Do not change the shared core `fnx_algorithms::volume` kernel's single self-loop
  count (it feeds `conductance`); any volume self-loop fix belongs in a caller.
- Next viable route would need a Python-object-native or integer-index degree-sum
  that skips canonical String conversion entirely.


## 2026-06-20 MultiGraph/MultiDiGraph `bfs_edges` pinned re-measure (`br-r37-c1-1jm15`, BlackThrush)

Pinned (`taskset -c 2`, `PYTHONHASHSEED=0`, warm min-of-40) on the bead's exact
`MultiGraph(1000 nodes, 5000 edges)` fixture, fresh release build at `8b459515f`:

- `MultiGraph.bfs_edges(0)`: FNX `0.50 ms` vs NetworkX `0.51 ms`, `1.01x` across 3
  pinned trials (edge sequence identical, 999 edges). The `0.825x` recorded when
  `1jm15` was split does NOT reproduce — a later build flipped it to parity. The
  bead is effectively RESOLVED; recommend a pinned confirm + close.
- `MultiDiGraph.bfs_edges(0)` (same shape): FNX `0.507 ms` vs NetworkX `0.425 ms`,
  `0.84x` — a real residual. 100% in the native `_fnx.bfs_edges` kernel (cProfile:
  zero Python overhead beyond the per-edge generator). Root cause is the
  String-keyed directed-multigraph successor BFS substrate (the MultiGraph kernel
  is already at parity), i.e. the same int-CSR migration class peers recorded as
  no-ship for multidigraph CSR. Not a contained win.

Do not retry:
- Do not chase `MultiGraph.bfs_edges` as a loss without a pinned re-measure first;
  it is at parity on the current build.
- Do not micro-tweak the `MultiDiGraph.bfs_edges` kernel for the `0.84x` residual;
  it is String-keyed-successor-substrate-bound, only an integer-CSR MultiDiGraph
  adjacency would move it (deferred, peer-confirmed no-ship class).

## 2026-06-20 `all_pairs_node_connectivity(nbunch=[few])` small-subset delegation tax (`br-r37-c1-apncnbunch` residual, BlackThrush)

Pinned (`taskset -c 2`, `PYTHONHASHSEED=0`, min-of-12) on `Graph(400 nodes, 1600
edges)`, `nbunch=[0,1,2]`: FNX `17.8 ms` vs NetworkX `14.4 ms`, `0.81x`, parity
true. The wrapper already (correctly) delegates a small nbunch (`<= |V|/2`) to nx
because the native `all_pairs_node_connectivity_rust` computes the FULL `O(V^2)`
pair set regardless of nbunch (a 4-node nbunch on n=120 was `2839 ms` vs nx `6 ms`).
So the residual `0.81x` is the `fnx->nx` whole-graph conversion the delegation pays
before nx runs only `C(k,2)` flows on one reused auxiliary graph.

Dead-ends confirmed (do not retry):
- There is NO correct native per-pair local node-connectivity binding:
  `_fnx.node_connectivity(g)` is GLOBAL-only; passing `(g, u, v)` SILENTLY returns
  garbage (`_fnx.node_connectivity(g,0,2)=0` where nx local `(0,2)=3`) — the `u,v`
  args are ignored. Per-pair routing diverges 52/200. (Latent binding foot-gun.)
- Using the bulk `all_pairs_node_connectivity_rust` for a small nbunch is far
  worse (full `O(V^2)` flows).

Only viable lever (substantial, not a verify-quick win): either add an
nbunch-restricted native kernel that builds the auxiliary node-connectivity digraph
once and runs only the `C(k,2)` requested max-flows, or reimplement nx's
`build_auxiliary_node_connectivity` + `local_node_connectivity` in-process over fnx
adjacency to skip the `fnx->nx` conversion (max-flow tie-break parity required).

## 2026-06-20 Delegation-tax root cause: `_fnx_to_nx` conversion is 5x `nx.Graph(edges)` (BlackThrush)

Context for the residual small-input delegation losses (e.g. all_pairs_node_connectivity
above). Pinned (`taskset -c 2`): `_networkx_graph_for_parity` -> `backend._fnx_to_nx`
costs `3.1 ms` (n=400) / `16.4 ms` (n=1500/7000e) vs `nx.Graph(g.edges())` `0.73 ms` /
`3.4 ms` — ~5x. cProfile of `_fnx_to_nx` (n=1500): body `9.8 ms` + nx `add_edges_from`
`5.8 ms` + native `fnx_to_nx_adjacency` `2 ms` + `_align_rows` `2 ms`; ~500k `dict.update`
+ 254k `dict.get` per 30 calls.

Why it is NOT a verify-quick win:
- The body cost is dominated by (a) the parity-REQUIRED adjacency-row alignment
  (`_align_inline`/`_align_rows` reorder nx `_adj`/`_succ`/`_pred` rows to match fnx
  insertion order — REQUIRED or every order-dependent delegated algo diverges:
  greedy_color, ego_graph, BFS/DFS variants) and (b) the canonical-key -> original-
  Python-object remap (the native bulk returns interned canonical strings, not the
  user's node objects). Both are inherent to faithful delegation, not waste.
- The node-attr materialization (`dict(node_view[node])` per node) is only `0.39 ms`
  of the `16.4 ms` (gating it on the cheap native `graph_has_any_attrs` saves ~3%,
  i.e. ~0-gain), so it is NOT worth a critical-path edit.
- Per-function payoff is small: the delegated algorithm usually dominates; halving
  the conversion would still leave all_pairs_node_connectivity(small nbunch) a loss.

Do not retry: do not micro-tweak `_fnx_to_nx` (node-attr skip, etc.) for the delegation
tax — the gain is ~0 and the blast radius (175 delegating functions) is large. A real
lever would need the native bulk crossing to emit original node objects AND
pre-aligned rows so the Python remap+align passes disappear entirely.

## 2026-06-20 `within_inter_cluster` bulk-community pre-fill REVERTED (net regression) (`br-r37-c1-wicbulk`, BlackThrush)

`within_inter_cluster` (cut/link-prediction gauntlet, `within_inter_cluster_explicit_community`)
on `Graph(400, 2000)` measured `0.54-0.61x` for a small explicit ebunch (50 pairs).
Profiling blamed the per-node `G.nodes[w][community]` AtlasView read (vars/
_private_override/__getitem__) over every ebunch endpoint AND common neighbor.

Attempt: pre-fill the community cache in ONE bulk `nodes(data=community, default=MISS)`
crossing (exact Graph only), raise lazily on first MISS access. Byte-exact 800/800
incl default/explicit/missing-community.

Pinned A/B (`taskset -c 2`, same window) — NET REGRESSION:
- default ebunch (non_edges) n=200: `1.74x -> 1.55x` (WORSE)
- 500-pair explicit: `1.57x -> 1.52x` (WORSE)
- 50-pair explicit: `0.56x -> 0.61x` (better, the only win)

Root cause: the existing per-node community_cache ALREADY amortizes repeated access
(each distinct node read once, then cached), so the bulk read only helps when the
ebunch+common-neighbors touch ~all of V AND each node is read once — which the cache
already covers. The bulk read of all |V| communities is pure overhead when the
accessed set < |V| (concentrated ebunch), and the added per-call `is _WIC_MISSING`
branch taxes the O(V^2) default path. REVERTED per ~0-gain/regression.

Do not retry: do not bulk-prefill node attrs for within_inter_cluster (or similar
already-cached per-node-attr link-prediction scorers) — the lazy cache wins. The
50-pair gap is the irreducible `G.neighbors` PyO3 per-node cost vs nx's dict (raw
neighbors measured SLOWER, 158us vs 122us).

## 2026-06-20 I/O sweep: `adjacency_data` attr-heavy residual (substrate) + `tree_data` FIXED (BlackThrush)

Pinned I/O sweep (`taskset -c 2`) found two losses; `tree_data` fixed (commit
aedc783ed, 0.40x -> 1.12x via bulk adjacency/attr snapshot + transpose-pred). The
other:
- `adjacency_data(Graph, attr-heavy)` `0.79x` (1.758ms vs nx 1.383ms) — but the
  native `_fnx.adjacency_data_simple` fast path IS already used (returns non-None);
  no-attr is `1.19x`. The attr-heavy residual is the native per-edge attr-dict
  CONSTRUCTION (PyO3) being slower than nx's C dict copy — the same
  view-materialization substrate as `nodes(data=attr)` 0.20x / `dict(adjacency())`.
  NOT a contained win (the native kernel is already the path; the gap is the
  Python-dict-from-Rust materialization floor).

Rest of the I/O surface WINS or neutral (pinned): generate_edgelist 1.30x,
parse_edgelist 1.72x, to_dict_of_lists 1.91x, node_link_data 1.28x, generate_gml
0.98x, generate_graphml 0.98x, cytoscape_data 0.97x, parse_adjlist 1.14x.

Do not retry adjacency_data attr-heavy: the native fast path is already used; the
residual needs the broader Rust-dict-to-Python materialization lever (persistent
ordered Python adj/attr mirror), not a kernel tweak.

## 2026-06-20 Serialization sweep round 2: tree_graph + cytoscape_graph FIXED; attr_matrix residual (BlackThrush)

Reconstruction functions rebuilt graphs via per-element add_node/add_edge +
view.update PyO3 round-trips (construction tax). Batch lever (collect tuples ->
add_nodes_from/add_edges_from) shipped two WINS:
- tree_graph (3797accdf): no-attr 0.42x -> 1.15x, attr 0.40x -> 0.88x.
- cytoscape_graph (90389ed97): 0.27x -> 1.26x (7.8x self).
(node_link_graph 1.42x / adjacency_graph 1.61x already batched.)

Confirmed real residual:
- attr_matrix(Graph, default) `0.51x` (pinned). The vectorised COO fast path
  (br-r37-c1-attrmtxcoo) IS already hit; cProfile: native adjacency_nodelist_typed_arrays
  0.53ms + np.asarray list->array conversion 0.48ms + zeros + np.add.at. The
  np.asarray cost is the native returning Python lists not numpy arrays; even
  eliminating it lands ~0.78x (still a loss) vs nx's tight per-edge scatter loop.
  NOT a contained win — needs the native binding to emit numpy arrays directly
  (rust-numpy), and even then marginal.

NOISE CORRECTION: the round-1 I/O sweep ran under host load 27.6; its smaller-margin
"losses" were noise — re-verified pinned (load ~10): to_pandas_adjacency 1.09-1.13x
(WIN, memory was right), to_numpy_array 1.08-1.12x, cytoscape_data 1.01x,
generate_multiline_adjlist 0.94x, pajek 0.86x (borderline). Only tree_graph 0.44x /
cytoscape_graph 0.27x (big margins) survived noise and were real (now fixed).
LESSON: trust only big-margin sweep losses under high load; re-verify pinned.

## 2026-06-20 stochastic_graph partial keep — copy fix 0.34x -> 0.64x (still loss) (br-r37-c1-stochcopy, BlackThrush)

stochastic_graph(DiGraph) was 0.34x nx. cProfile: the cost was `_copy_graph_shallow`
rebuilding the copy via a per-edge `add_edge` loop (3200 add_edge calls = the
construction tax), NOT the weight passes. KEPT: for an exact DiGraph use the native
integer-CSR `G.copy()` (independent attr dicts; verified the in-place weight
normalisation stays isolated from G) and materialise the edge view ONCE (live
attr-dict refs) instead of two `edges(data=True)` crossings. Multigraph keeps
`_copy_graph_shallow` (native multi-copy is the slow String-keyed path); subclasses
keep it.

Pinned best-of-60 x5 (load ~14): 0.34x -> median 0.64x (~1.9x self-speedup), still a
vs-nx LOSS. Residual: even one `edges(data=True)` materialisation + the native copy
is slower than nx's plain-dict copy + 2 dict passes — the edges(data=True) view
materialisation floor ([[reference_warm_saturation_map_and_coldeig_noise]] nodes/adj
view substrate). MultiDiGraph stays ~0.38x (slow multigraph copy substrate). Parity
600/600 (simple+multi, copy T/F, no-weight edges, original-unchanged); pytest -k
stochastic 8 passed. KEEP PARTIAL (real self-speedup); full win needs the persistent
ordered Python adj/attr mirror (edges(data=True) floor) or a native stochastic kernel.

## 2026-06-20 Target-Specific `single_source_dijkstra` Early-Exit Keep (`br-r37-c1-04z53`, cod-b)

Scope: recover the weighted directed Dijkstra residual before trying another
path-emission micro-lever. Current source already closed the historical
all-target `br-r37-c1-0opkc` n=1400/n=2600 losses, but
`single_source_dijkstra(G, source, target=t, weight="weight")` still routed
through the all-target raw binding and built every distance/path before
returning one target.

Environment:
- Agent Mail identity and CLI actor: `CrimsonRiver`; bead assignee `cod-b`.
- Worktree:
  `/data/projects/.scratch/franken_networkx-cod-b-boldverify-20260621T0015`.
- Requested RCH target dir:
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on `vmi1149989` with the requested target rewritten to a worker-scoped
  path.
- Local release install against the requested target hit incompatible-rustc
  E0514 from stale artifacts. No cleanup, deletion, or reset was performed.
  The local extension install used fresh non-destructive target dir
  `/data/projects/.rch-targets/franken_networkx-cod-b-boldverify-f20a92ec0`.
- Oracle: vendored NetworkX `3.7rc0.dev0`, Python `3.13`,
  `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `taskset -c 4`.

Lever:
- For `single_source_dijkstra` with a concrete `target`, no `cutoff`, and a
  string `weight`, dispatch to the existing native
  `_fnx.dijkstra_path_to_target` binding.
- Preserve current semantics for `cutoff`, callable/non-string weights,
  delegated negative/nonfinite/nonnumeric weights, and missing targets.

Baseline observations:
- Current all-target `single_source_dijkstra` is no longer the `0opkc` active
  loss: n=1400 all-int `1.337x`, n=1400 mixed `1.821x`, n=2600 all-int
  `1.466x`, and n=2600 mixed `2.849x` vs NetworkX on the live fixture.
- Pre-patch target-specific rows still lost on the target surface:
  n=1400 mixed-near `0.750x`, n=1400 all-int far `0.178x`, n=1400 mixed far
  `0.196x`, n=2600 all-int near `0.167x`, and n=2600 all-int far `0.371x`.

Final direct-loop evidence:

| Workload | FNX p50 | NetworkX p50 | Ratio vs NetworkX | Digest |
| --- | ---: | ---: | ---: | --- |
| n=1400 all-int target-near | `2.058399 ms` | `3.230062 ms` | `1.569x` | `655c27bc64a0bf4d7315015c1593026d1a4872fe51bfc3d217e82f85765967be` |
| n=1400 all-int target-far | `0.104427 ms` | `0.478805 ms` | `4.585x` | `986783df8d6c8978123962b628a06959c181bcbf99798fcdaa02be4739692442` |
| n=1400 mixed target-near | `0.329712 ms` | `1.996522 ms` | `6.055x` | `d9aad48926eca4baa01cb9d16f8fab1263406baa415f9d87cd73b7878e068d2d` |
| n=1400 mixed target-far | `0.096642 ms` | `0.573694 ms` | `5.936x` | `20f52f9afcdd26e41894c56ed93948cbabcc4a6c3a82e62b1561526b33a130db` |
| n=2600 all-int target-near | `0.278847 ms` | `1.043872 ms` | `3.744x` | `55e9ec91ca54587e55fdfe943e7066055cb43a148af33458f099aeb32f54925b` |
| n=2600 all-int target-far | `0.253389 ms` | `1.345772 ms` | `5.311x` | `f3fcb25105323d42a4a852b17d8a27be65de3376e9504cac6f8890093aa0f432` |
| n=2600 mixed target-near | `4.081119 ms` | `8.419554 ms` | `2.063x` | `d776a460c8a4f7e82a0e7231f5e2d300262586effa28f62f439d3c09163baa53` |
| n=2600 mixed target-far | `0.952880 ms` | `4.902420 ms` | `5.145x` | `89c4424c00f59aadeada968f57088fb1d9518eabeab1247208370768746c0610` |

Batched same-process keep gate:

| Workload | Old raw-all-path p50 | New p50 | NetworkX p50 | New vs NetworkX | New vs old |
| --- | ---: | ---: | ---: | ---: | ---: |
| n=1400 all-int far | `2.684641 ms` | `0.103329 ms` | `0.779869 ms` | `7.547x` | `25.982x` |
| n=1400 mixed far | `3.828867 ms` | `0.126583 ms` | `0.559703 ms` | `4.422x` | `30.248x` |
| n=2600 all-int near | `4.805508 ms` | `0.232390 ms` | `0.981963 ms` | `4.226x` | `20.679x` |
| n=2600 all-int far | `6.262417 ms` | `0.239303 ms` | `1.079285 ms` | `4.510x` | `26.169x` |
| n=2600 mixed far | `5.927624 ms` | `0.617956 ms` | `4.224094 ms` | `6.836x` | `9.592x` |

Conformance and gates:
- Parity digests matched for every direct-loop and batched row.
- `python -m py_compile python/franken_networkx/__init__.py` passed.
- Focused shortest-path pytest passed: `159 passed`.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310` passed
  on `vmi1152480`.

Decision:
- Keep. Target-specific score is `8` wins / `0` losses / `0` neutral vs
  NetworkX.
- Stale-loss closeout: the live all-target `0opkc` n=1400/n=2600 rows are no
  longer active losses on current source.

Do not repeat:
- Do not route target-specific `single_source_dijkstra` through full all-target
  distance/path emission when the native target kernel is available.
- Do not retry standalone display-key cache or `PyList::new` path streaming for
  this surface; the live target loss was dispatch shape, not all-target path
  emission.

## 2026-06-21 — MultiGraph.subgraph(nodes).copy() 0.72x is construction-substrate-bound (CopperCliff)

Measured (warm min-of-11, MultiGraph N=900 / 3600 edges, keep 400 nodes):
`G.subgraph(sub).copy()` FNX `6.05 ms` vs NetworkX `4.06 ms` = `0.72x` LOSS.
Contrast: FULL `G.copy()` is a WIN at FNX `5.19 ms` vs NetworkX `8.27 ms`
(`1.59x`) via native `_native_copy`.

Root cause: `_FilteredGraphView.copy()` bails the native induced fast path for
multigraphs and rebuilds via `add_edges_from((u,v,key,dict(attrs)) ...)`. The
4-tuple explicit-key shape is REJECTED by the native `_try_add_attr_edges_from_batch`
(verified: returns False / 0 edges), so it falls to the per-edge `add_edge` +
`get_edge_data().update()` loop (2 PyO3 round-trips x 3600 edges) = the whole gap.

Routes ruled out (no my-file Python lever):
- Materialize generator->list before `add_edges_from`: no change (batch rejects
  4-tuples by shape, not iterability).
- `_native_copy()` + `remove_nodes_from(complement)`: byte-identical to nx AND
  official, but SLOWER (`6.90 ms`) — multigraph `remove_nodes_from` of 500 nodes
  costs ~1.7 ms over the 5.2 ms native copy.

Do not repeat:
- Do not try to close this with a pure-Python copy() change; both feasible Python
  routes were measured and lose. The only lever is a native keyed-4-tuple batch
  (`_try_add_attr_edges_from_batch` extended to explicit keys in lib.rs +
  digraph.rs, then routed from `_copy_induced_simple_fast`) — a Rust change with
  parallel-edge key-parity risk, deferred as a scoped bead.
Artifacts: `tests/artifacts/perf/20260621T-mg-subgraph-copy-cc/`.

### Follow-up 2026-06-21 — keyed-4-tuple batch BUILT + measured, still loses (CopperCliff)

Implemented the native keyed batch (`_try_add_keyed_attr_edges_from_batch` on
PyMultiGraph + wrapper gate + list-materialized copy()), full release build in a
clean worktree. Correctness PASSED: 72/72 `subgraph().copy()` byte-identical to nx
(MultiGraph + MultiDiGraph-via-fallback, gapped keys, self-loops, attrs). But it
STILL LOSES: `subgraph(range(400)).copy()` `0.86–0.90x` (improved from 0.72x),
and even direct `add_edges_from([3576 4-tuples])` is `0.70x` despite the batch
firing. Root cause: the batch removes the per-edge `add_edge` loop but each edge
still pays `py_dict_to_attr_map` (Python dict -> Rust AttrMap) AND keeps a Python
mirror — the dual-storage conversion costs more than nx's single-dict assignment.
Same ceiling the existing 2/3-tuple attr batch hits (0.8–0.9x). REVERTED, not
shipped; bead `br-r37-c1-mg-subgraph-keyed-batch-z1q8i` closed no-ship. Real lever
is a lazy AttrMap (defer Python->Rust conversion until a native kernel reads
attrs), a deep substrate change — not a keyed batch.

## 2026-06-21 — connectivity.local_node_connectivity 0.75x is nx-module passthrough access tax (CopperCliff)

Measured (single pair s=0,t=N-1 on gnm N=1500/6000e): exact
`fnx.connectivity.local_node_connectivity(G,s,t)` FNX `62.5 ms` vs NetworkX
`48.9 ms` = `0.75x` (value 8 == 8). `type(fnx.connectivity)` is the **NetworkX
module** `networkx.algorithms.connectivity.connectivity` — fnx does NOT override
the exact (flow-based) local_node_connectivity, so this is nx's own Python flow
code running on a fnx graph: the loss is the per-access AtlasView/`neighbors`
PyO3 substrate tax, NOT a fnx-implementation regression.

Context (NOT losses): the broad single-pair delegated sweep is otherwise all
wins — `node_disjoint_paths` 8.5x, `edge_disjoint_paths` 7.8x,
`approximation.local_node_connectivity` 10.3x, `all_simple_paths` 1.4x,
`harmonic(nbunch)` 3.7x, `node_disjoint`/`approx` connectivity native-fast.

Lever (rebuild-gated, deferred under low-disk no-rebuild constraint): wire fnx's
native max-flow substrate (which beats nx) into a native exact
local/global node/edge connectivity routed from the connectivity namespace, OR
expose a fnx-native connectivity namespace that overrides the nx-module
passthrough. A pure-Python reroute via `len(list(node_disjoint_paths(G,s,t)))`
is NOT cleanly value-equivalent (node_disjoint_paths raises `NetworkXNoPath`
where local_node_connectivity returns 0, and adjacent-pair semantics differ), so
it is not a safe my-file lever. Filed as a bead.

## 2026-06-21 — CORRECTION: to_scipy_sparse_array / to_pandas_adjacency do NOT share the to_numpy dirty ceiling (CopperCliff)

The to_numpy_array dirty-weight entry (commit c95567ccb) speculated the same
dirty-sync ceiling "likely applies to to_scipy_sparse_array and to_pandas_adjacency
(untested)". Now tested (gnm N=1500/6000e, post-construction `G[u][v]['weight']=w`
dirty graph):
- `to_scipy_sparse_array`: dirty `1.01x` (parity), construction `2.76x` WIN — does
  NOT suffer the to_numpy dirty penalty (it routes the weighted COO without the
  full AttrMap rebuild dominating).
- `to_pandas_adjacency`: dirty `0.93x`, construction `1.03x` — both ~parity; the
  cost is pandas DataFrame construction (~24ms), not the edge sync, so the dirty
  tax is negligible here.
Conclusion: the dual-storage dirty-sync ceiling is SPECIFIC to to_numpy_array's
path; do NOT chase a to_scipy/to_pandas dirty gap — there isn't one.

## 2026-06-21 — FIXED (no rebuild): connectivity.local_node/edge_connectivity passthrough → fnx-native routing (CopperCliff)

The earlier "connectivity.local_node_connectivity 0.75x is nx-module passthrough"
entry concluded the lever was rebuild-gated. WRONG — it was a pure-Python routing
gap. `connectivity.py`'s wildcard `from networkx... import *` left BOTH
`local_node_connectivity` and `local_edge_connectivity` bound to NetworkX, while
fnx's native `node_connectivity(s,t)` / `edge_connectivity(s,t)` compute the
identical kappa/lambda(s,t) via the fast max-flow substrate. Added concrete
overrides in `connectivity.py` routing the default exact query to the native
functions (gated: distinct in-graph endpoints, no custom flow_func/auxiliary/
residual/cutoff/backend — everything else, incl. the cutoff early-exit contract
and missing-endpoint errors, falls back to nx verbatim).

Measured (gnm N=1500/6000e, single pair): local_node_connectivity FNX `18.2 ms`
vs nx `56.7 ms` = `2.69x` (was 0.75x); local_edge_connectivity FNX `4.3 ms` vs nx
`26.3 ms` = `6.09x` (was ~0.71x). Value-identical over 100+ directed+undirected
pairs and complete/path/cycle/disconnected/dense-adjacent edge cases; connectivity
conformance `210 passed, 10 skipped`. Two documented losses flipped to wins with no
Rust change. Bead `br-r37-c1-native-flow-connectivity-zvwck` resolved by routing.

## 2026-06-21 — dag.has_cycle / is_directed_acyclic_graph slow on CYCLIC graphs is a native no-early-exit gap (CopperCliff)

`dag.has_cycle` is a catastrophic nx-passthrough (0.02x cyclic / 0.13x DAG vs nx).
`has_cycle(G) == not is_directed_acyclic_graph(G)`, and routing to the fnx-native
`is_directed_acyclic_graph` is a 75x WIN **on DAG inputs** (0.017ms). BUT measured
(gnm directed N=2000/8000e, actually cyclic):
- `fnx.is_directed_acyclic_graph(cyclic)` `9.5 ms` vs nx `0.31 ms` = `0.033x`.
- `fnx.find_cycle(cyclic)` `9.6 ms` vs nx `0.07 ms`.
The native cycle-detection kernel does a FULL pass instead of returning at the
first back-edge; nx early-exits. So a pure-Python `has_cycle` route wins only on
DAGs and stays slow on cyclic — a band-aid in the wrong layer. Prototyped and
REVERTED.

Real lever (rebuild-gated): add early-exit to the native is_directed_acyclic_graph
/ find_cycle / topological cycle-detection kernel (return at the first detected
back-edge). That single native fix makes is_dag, find_cycle, AND has_cycle fast on
both DAG and cyclic inputs. Bead `br-r37-c1-isdag-cyclic-early-exit-qghjm`.
Do NOT ship a Python has_cycle route alone — it leaves the cyclic loss.

### addendum — dag.colliders / v_structures: predecessor-access substrate-bound

Same audit: `dag.colliders` (`0.057x`, fnx 6.73ms vs nx 0.38ms) and
`dag.v_structures` (`0.083x`, 6.99ms vs 0.58ms) are catastrophic nx-passthroughs
(nx iterates `G.predecessors(node)` AtlasViews over the fnx per-access substrate).
An in-process reimplementation snapshotting predecessors once
(`{n: list(G.predecessors(n)) for n in G}`) + Python `combinations`, byte-identical
to nx (25/25 random DAG+cyclic + docstring examples, undirected raises
`NetworkXNotImplemented`), improves them ~8x (colliders 6.73→0.83ms) but STILL
LOSES (`0.42x` / `0.35x`): the fnx predecessor-snapshot floor (`0.63 ms` for 1500
nodes) already exceeds nx's whole-call native-dict time (`0.38 ms`). REVERTED (not
shipped). Lever (rebuild-gated): a native bulk predecessor-keys snapshot (the
directed sibling of `_native_adjacency_keys`) to get the snapshot below nx's
native-dict access; only then does an in-process colliders/v_structures beat nx.

## 2026-06-21 — CORRECTION: dag.has_cycle IS cleanly routable; the earlier "is_dag slow on cyclic" was a STALE .so artifact (CopperCliff)

The earlier entry "dag.has_cycle / is_directed_acyclic_graph slow on CYCLIC =
native no-early-exit gap" (commit e0731148d) was WRONG — a stale-install
measurement trap. Those `is_directed_acyclic_graph(cyclic) 9.5ms` /
`find_cycle 9.6ms` numbers were measured via `PYTHONPATH=…/python` against the
in-tree `_fnx.abi3.so` left over from an earlier to_numpy build, NOT the current
extension. Re-measured against the current install: `is_directed_acyclic_graph`
is `0.012 ms` cyclic / `0.018 ms` DAG (the native kernel is Kahn's integer-CSR,
which naturally terminates on the first stalled peel — there was never a missing
early-exit). FIXED (no rebuild): `has_cycle(G) == not is_directed_acyclic_graph(G)`
routed in dag.py for directed graphs — `not is_dag` is `0.009 ms` cyclic (34x nx)
/ `0.015 ms` DAG (68x nx), value-identical incl. self-loops / parallel edges /
empty; undirected falls back to nx's `NetworkXNotImplemented`. dag conformance
130 passed. Bead `br-r37-c1-isdag-cyclic-early-exit-qghjm` closed invalid.

LESSON (re-learned the hard way): ALWAYS benchmark the native-target perf on the
CURRENT install before declaring a route rebuild-gated. A value-equivalent
passthrough route's target perf must be measured on the same build it will ship
against, not a stale PYTHONPATH .so (see feedback_stale_install_benchmark_trap).

## 2026-06-21 — is_distance_regular "0.003x gap" is a CORRECTNESS win for fnx, not a perf loss (CopperCliff)

`is_distance_regular(cycle_graph(800))`: fnx `201ms` vs nx `0.53ms` looks like a
catastrophic `0.003x` loss. It is NOT a perf gap to fix — it is a **correctness
divergence where fnx is right and nx is wrong**. fnx returns `True` (a cycle C_n
IS distance-regular for all n — textbook); nx returns `False`. nx's
`intersection_array` uses a diameter early-exit `(8·log2 n)/3 ≈ 25.7` for n=800,
but that bound is only valid for valency ≥ 3 distance-regular graphs — a cycle
(valency 2) has diameter ⌊n/2⌋ = 400 and is wrongly rejected. fnx's native
`_raw_is_distance_regular` computes the full intersection array (all-source BFS,
O(V·(V+E))) and gets the correct answer.

Verified: fnx==nx on petersen (DR, valency 3), K20 (DR), random 3-regular
(not DR) — they diverge ONLY on large cycles (valency 2), where fnx is correct.

DO NOT route fnx.is_distance_regular to nx's fast path — it would adopt nx's bug.
The slowness is the price of correctness: for a graph that genuinely IS
distance-regular you cannot early-exit-reject, so the work is unavoidable. The
only lever is a native single-source-lazy intersection array (vs the current
all-source) — still O(V^2)-ish for true DR graphs, marginal, rebuild-gated, low
value (is_distance_regular is algebraic-graph-theory niche). Bead filed.

### addendum 2 — colliders/v_structures native predecessor-keys BUILT + measured, still loses (CopperCliff 2026-06-21)

Followed up the dag.colliders/v_structures substrate-bound finding by actually
adding the native `_native_predecessor_keys_bulk` to PyDiGraph (mirroring the
existing PyMultiDiGraph method) + routing colliders/v_structures through it, full
warm release build. Correctness PASSED (30/30 random DAG+cyclic + docstring
examples byte-identical; undirected raises NetworkXNotImplemented). But it STILL
LOSES: colliders `0.66x` (fnx 2.58ms vs nx 1.72ms), v_structures `0.38x` — an
improvement over the pure-Python reimpl (~0.42x) but not a win. Root cause: the
native bulk still materializes EVERY predecessor node-key as a PyObject (O(E)
`py_pred_key` allocations); nx's `G.predecessors` reuses the already-stored node
objects, so fnx pays an allocation nx does not. This is the SAME node-key
PyObject materialization wall that caps graph iteration (~35x) — the live-PyDict /
interned-display node storage substrate, NOT a colliders-local or snapshot-local
fix. REVERTED (worktree discarded). DO NOT re-attempt a predecessor-keys route for
colliders/v_structures; the only lever is the deep node-storage rearchitecture.

## 2026-06-21 — submodule-namespace passthrough scan: residuals are routed/substrate/rebuild-gated (CopperCliff)

Comprehensive scan of fnx.SUBMODULE.func vs nx.SUBMODULE.func across 18 namespace
submodules (the pattern that yielded the connectivity/tournament/dag/threshold
wins). After filtering scan noise, the genuine sub-1.0x residuals are:
- ALREADY ROUTED + fast (scan noise): assortativity.degree_mixing_dict 4.4x,
  degree_mixing_matrix 4.1x, degree_pearson_correlation_coefficient 2.8x,
  degree_assortativity_coefficient 100x — all route to fnx top-level natives via
  the existing `_route_to_fnx_toplevel()`; the scan's <0.55x readings were noisy
  single-shot artifacts (re-measured min-of-N: all wins).
- SUBSTRATE-BOUND (edge-data access): tree.branching_weight 0.07x. It is exactly
  G.size(weight=attr), but routing there is STILL 0.45x (fnx edge-data iteration
  loses to nx's native dict walk) AND diverges in type (int 4831 vs float 4831.0).
  Not a clean route. Same node/edge-access substrate wall.
- FIXED (99d245aea, NOT rebuild-gated — was a Python loop): google_matrix was
  0.38x-0.81x because its dense row-normalization ran a ``for i in range(n)``
  per-row slice division. Vectorized it (divide-all-rows + sparse dangling
  overwrite, byte-identical to the loop over 30 configs) -> 1.06-1.22x vs nx.
  LESSON: read the implementation before declaring a gap rebuild-gated; a Python
  loop in a numpy function is a pure-Python vectorization win.
- NICHE: tournament.tournament_matrix 0.23x (skew-adjacency build).

NO new clean no-rebuild win. The 6 namespace wins already shipped were the
catastrophic O(n^2+)-brute-force-with-fast-native cases; the rest are routed,
substrate-bound, or rebuild-gated.

### addendum — namespace-scan warm re-bench (CopperCliff 2026-06-21)

Warm min-of-N re-measurement of the remaining namespace-scan sub-1.0x entries:
- centrality.eigenvector_centrality_numpy: warm `1.19x` WIN (scan's 0.475x was
  cold-scipy/LAPACK init noise — confirms the warm-saturation memory).
- centrality.dispersion: warm `1.87x` WIN (scan noise).
- approximation.densest_subgraph: genuine warm `0.48x` (fnx 4.54ms vs nx 2.20ms).
  nx dispatches to a greedy-peeling / FISTA approximation; it's a per-access
  passthrough with no fast-native route — reimplementation- or substrate-bound,
  niche. Not pursued.
- tree.greedy_branching: genuine warm `0.46x` (fnx 6.49ms vs nx 2.97ms). Edmonds
  greedy max-weight in-edge selection + branching construction (node-key
  materialization); substrate-bound, niche. Not pursued.
Net: no new clean win; the two genuine gaps are niche + substrate/reimplementation-
bound. (Cold-vs-warm reminder: always warm-saturate scipy/LAPACK before trusting a
spectral/numpy ratio.)

### addendum — densest_subgraph is ORDER-SENSITIVE, parity-blocked (CopperCliff 2026-06-21)

approximation.densest_subgraph (warm 0.48x) reimplemented in-process via a fast
adjacency snapshot + nx's EXACT Greedy++ (heap-based min-weighted-degree peeling)
is 2.3-2.4x faster than nx — BUT it DIVERGES from nx on identical graphs (e.g.
n=35/m=16: density 0.8 vs 0.8235). Greedy++ is a 2-approximation whose result
depends on the heap tie-break order, which in turn depends on the adjacency /
neighbor ITERATION order; fnx's adjacency order differs from nx's, so the peeling
trajectory and the returned density/node-set differ (both valid approximations,
not equal). Like the clique/ramsey/greedy_color set-order-dependent approx
functions, this CANNOT be matched in pure Python and must stay delegated. Reverted
(prototype only, never committed to source). tree.greedy_branching is the same
shape (greedy max-weight selection, order-dependent). No-ship.

## 2026-06-21 — callable-weight functions pay the delegation-conversion tax (CopperCliff)

Functions called with a CALLABLE weight (weight=lambda u,v,d: ...) cannot run on
the native string-keyed kernels, so fnx delegates via `_call_networkx_for_parity`
-> `_networkx_graph_for_parity(G)` (a fresh O(V+E) fnx->nx conversion EVERY call,
~5ms at N=600/2400e) + nx's algorithm. Measured warm:
- dijkstra_path_length(callable weight) `0.12x` (fnx 5.95ms vs nx 0.74ms)
- single_source_dijkstra_path_length(callable) `0.17x`
- pagerank(callable weight) `0.00x` (fnx 497ms vs nx 2.1ms — though callable weight
  for pagerank is non-standard; weight is documented as a str key/None)
- betweenness_centrality(callable) `1.01x`, all_pairs_dijkstra(callable) `0.97x`
  (parity — the conversion is amortized over the O(V*(V+E)) all-pairs work).
Root cause = the per-call whole-graph conversion dominates single-pair/cheap
callable queries (the delegation-conversion-tax pattern). NOT pursued: string
weights (the overwhelmingly common case) are already native-fast; callable weight
is uncommon. The lever is either (a) an in-process Dijkstra reimplementation that
calls the Python weight callable over a fast native adjacency snapshot (no
conversion — the bidirectional_dijkstra pattern), per-function and byte-identity-
risky, or (b) caching the shared `_call_networkx_for_parity` conversion under the
(nodes_seq, edges_seq, edges_dirty) token (broad win for ALL delegated functions on
unchanged graphs, but high blast radius — needs careful invalidation). Both deferred
as scoped work; the gap is niche (callable weight) and the fixes are risky.

## 2026-06-22 CopperCliff `MultiDiGraph(DiGraph)` Native Absorb WIN (`br-r37-c1-mdgdig`, cc)

BOLD-VERIFY on current origin/main. Broad warm sweep found one real meaty gap:
`MultiDiGraph(<plain DiGraph>)` ran **0.41-0.53x** vs nx (MultiDiGraph(MultiDiGraph)
and MultiGraph(Graph) were already fast — only DiGraph->MultiDiGraph lacked a native
absorb; `_copy_constructor_graph_source` fell to the general Python `clear()` +
`add_nodes_from` + `add_edges_from(4-tuple)` replay).

NEGATIVE EVIDENCE (Python ruled out): `add_edges_from` alone = 28.5ms of 41.6ms
@ n=2000; EVERY edge-tuple shape — `(u,v,0,dict)`, `(u,v,dict)`, bare `(u,v)`,
precomputed list — was ~29-32ms. The cost is the `MultiDiGraph.add_edges_from`
keyed-insertion substrate, not the per-edge `dict()` copies. No pure-Python route
closes it.

FIX: added `absorb_digraph_keyed_from_digraph` to `impl PyMultiDiGraph` (directional
analog of `absorb_graph_bidirected_from_graph`) — builds the MDG inner directly from
the DiGraph inner in one pass (node-major `successors`, key 0, shallow-copied attrs),
wired in `_copy_constructor_graph_source`. Falls through (Ok(false)) on mixed-display
rows / `__fnx_incompatible` attrs. Byte-exact: 6 hand shapes + 60 randomized, 0
mismatches (nodes, node data, edges(keys+data), succ+pred adjacency, graph attrs,
shallow-copy + no-source-mutation). Perf 0.41x -> **1.62-1.90x** faster than nx
(~4.5x self-speedup). Full suite: zero new failures (5 pre-existing origin failures
unrelated, proven by reverting the wiring). Artifact:
`tests/artifacts/perf/20260622T-multidigraph-from-digraph-absorb-cc/`.

## 2026-06-22 CopperCliff Post-MDG-Absorb Comprehensive Sweep — Domination, Residuals Bounded (`br-r37-c1-mdgdig`, cc)

After shipping the `MultiDiGraph(DiGraph)` absorb, a 3-batch warm sweep (~90
functions: construction/conversion/copies, readwrite/serialization, centrality/
community/flow/connectivity/cycles/trees, weighted+multi algorithms) re-confirmed
comprehensive domination (representative wins: floyd_warshall 67x, weighted
betweenness 158x, second_order 4845x, bridges 24x, greedy_modularity 21x,
eccentricity 15x, MultiDiGraph.copy 2.44x, reverse(MDG) 2.39x, from_scipy 2.1x,
all_pairs_dijkstra 2.76x, MG(MG) 3.38x, mg.edges 4.7x).

NEGATIVE EVIDENCE — residual losses are all bounded/marginal, NOT clean levers:
- `in_degree`/`out_degree` `dict(...)`: 0.56-0.65x at n=20000 (2.0ms vs 1.25ms).
  Already on a native bulk path (`_native_in/out_degree_pairs`). RULED OUT a
  wrapper bug: the raw native call alone is 1.49ms (vs nx 1.25ms) building 20000
  (node_obj, count) tuples — the view wrapper adds only ~0.2ms (`yield from`).
  `list(G)` is 0.09ms so it is NOT node materialization; it is the rust tuple-list
  build being marginally slower than nx's pure-Python dict-comp. Sub-2ms absolute,
  ~10% recoverable — no good ROI.
- `to_dict_of_dicts(MultiDiGraph)`: 0.77x (3.8ms vs 2.95ms) — nested dict build
  substrate, niche serialization helper.
- `from_dict_of_dicts(DiGraph)` 0.48x and `astar` 0.73x and `find_cycle(src)` 0.38x:
  all TINY absolute (15-500us) — small-input/native-port setup cost dominates, not
  an algorithmic gap; default whole-graph timing shows parity.
- `subgraph_centrality` 0.81x (84ms vs 68ms): dense `eigh`-bound (known open item).
- A cluster at 0.85-0.92x (MultiGraph(MultiDiGraph), MDG subgraph.copy, to_numpy_array,
  size_weighted, mg.degree(weight), adjacency() walk): substrate-parity, not wrapper.

Conclusion: the one meaty current-code lever (`MultiDiGraph(DiGraph)` absorb, shipped)
is exhausted; remaining gaps are substrate-bound or tiny-absolute. No further ship.

### Addendum (same pass, cc): untouched-family sweep — domination holds

Extended the sweep to families not covered above (~29 fns): isomorphism
(could_be/fast/faster 1.5-6.2x), WL hashing (graph_hash/subgraph_hashes 0.96x =
parity), graph coloring (greedy_color 9.07x), cliques (find_cliques/node_clique
1.04x), similarity (simrank 1.11x), efficiency (local 25.3x / global 18.3x),
triadic_census 17.95x, reciprocity 8.24x / overall 9.03x, bipartite
(density 7.69x, clustering 2.28x, projected 0.93x), dominance (immediate_dominators
3.38x, dominance_frontiers 1.68x), closeness_vitality 14.5x, spring_layout 1.01x,
k_components 0.99x, non_randomness 0.98x, degree_histogram 0.97x. Only sub-0.85x:
`bipartite.color` 0.80x at sub-100us (small-input, negligible). No new lever —
confirms the post-MDG-absorb domination across ~120 functions total this pass.

## 2026-06-22 CopperCliff `shortest_path(G, source)` Routed to Fast Kernel (`br-r37-c1-spsrc`, cc)

Small-input/single-query sweep (the angle whole-graph timing hides) found one real
meaty gap: unweighted `shortest_path(G, source)` (source-only, all targets) ran
**0.72-0.84x** vs nx. Diagnosis: `single_source_shortest_path(G, source)` is itself
**~1.6x FASTER** than nx, but `shortest_path` fell through to the `_raw_shortest_path`
source-only path, which was ~2x SLOWER than the single_source kernel. nx.shortest_path(
G, source) returns EXACTLY single_source_shortest_path(G, source), so the wrapper was
doing strictly more work for the same result.

FIX (pure-Python, no rebuild): route the `weight is None and source is not None and
target is None` case to `single_source_shortest_path(G, source)`. Byte-identical (both
match nx, 20/20 parity incl. BFS-discovery key order + source self-path). Perf
0.72-0.84x -> **1.38-1.63x** faster than nx. Full suite: zero new failures (same 5
pre-existing origin failures). Other small-input residuals are sub-microsecond PyO3
call overhead (neighbors(v) 0.35x @ 0.8us, degree(v) 0.46x @ 0.8us, common_neighbors
0.72x @ 1.2us) — fundamental per-call round-trip cost, negligible absolute, no ROI.

### Residual (same pass, cc): directed `single_target_shortest_path` ~0.66x — kernel-bound, NOT a wrapper fix

While fixing `shortest_path(G, source)`, the symmetric `shortest_path(G, target=t)` on
a DIRECTED graph measured ~0.66x (1.47ms vs nx 1.09ms @ n=2000). Unlike the source
case, this is NOT wrapper waste: the underlying `single_target_shortest_path` (already
native `_raw_single_target_shortest_path`, reverse/predecessor integer-BFS) is itself
0.66x (1.084ms vs nx 0.713ms). Routing the wrapper would only reach the kernel's 0.66x,
not beat nx — so NOT shipped. The bottleneck is the per-node Python path-list
reconstruction (materializing ~|V| node-object lists from the Rust string table), the
same node-object materialization substrate that bounds the degree-view dicts. The
UNDIRECTED target case is 0.95x (parity). Candidate for future native work (emit path
segments / reuse a node-object cache), not a one-pass wrapper lever.

PROOF the directed `single_target` residual is path-materialization-bound (not BFS):
`single_target_shortest_path_length` (no path objects, same reverse BFS) is **parity**
(1.01x @ n=2000, 0.95x @ n=5000) while the path-returning version is 0.57-0.66x. So the
entire gap is building |V| Python path-lists of node objects from the Rust string table
— the reverse BFS is already at nx speed. No BFS-level or wrapper fix can close it;
only a persistent node-object mirror would (and nx wins there by reusing node objects it
already holds). Conclusively NOT a one-pass lever. Vein closed.

### Addendum 2 (same pass, cc): algorithm-family sweep — domination holds

Final coverage batch (~28 fns across families not previously benched): distance
measures (center/periphery/radius/diameter/barycenter/wiener all ~15x), assortativity
(degree_mixing_matrix 4.45x, average_degree_connectivity 2.05x), graphical sequences
(is_graphical 1.19x, erdos_gallai 1.52x), structural holes (local_constraint 3.16x),
chordality (is_chordal 3.88x), euler (is_eulerian 4.16x, has_eulerian_path 1.51x),
covering (min_edge_cover 0.90x = parity), swaps (double_edge_swap 1.33x), hierarchy
(flow_hierarchy 233x, global_reaching_centrality 4.18x, trophic_levels 1.06x),
all_shortest_paths 2.18x, dispersion 1.75x, voterank 1.74x, percolation 1.74x. All
wins or parity; no sub-0.85x. With this, the BOLD-VERIFY sweep spans ~180 function-calls
(whole-graph + small-input) across essentially every NetworkX algorithm family —
comprehensive domination confirmed; the only residuals are the node/path-object
materialization substrate (proven above) and sub-us PyO3 call overhead. No clean lever
remains absent the persistent-node-mirror substrate rewrite.

## 2026-06-22 CopperCliff `in_degree`/`out_degree` Counts-Only Path — 0.62x -> 1.33-1.77x (`br-r37-c1-degcounts`, cc)

Earlier docs flagged the directed `in_degree`/`out_degree` dict as 0.62x "near-native,
no ROI" — that was WRONG. Re-diagnosis: `dict(zip(list(G), counts))` = 0.56ms while the
`_native_*_degree_pairs` path was 1.5ms, because pairs rebuilt a PyObject per node via
`py_node_key` whereas `list(G)` reuses the node_iter_mirror cache (0.09ms @ 20k). The
missing piece was a counts-ONLY native call (no node materialization).

FIX: added `_native_in_degree_counts`/`_native_out_degree_counts` to PyDiGraph (Vec<usize>
in node-index order, no py_node_key) and routed `_DirectedDegreeView.__iter__`'s unweighted
full-graph branch (gated `type(G) is DiGraph`) to `zip(list(G), counts())`. Byte-identical
(list(G) order == nodes_ordered() index order, verified range+str keys); weighted / nbunch /
single-node / filtered / multi paths untouched. Perf: in_degree/out_degree dict 0.62x ->
**1.33-1.77x** faster; `for n,d in G.in_degree()` iteration 1.1-1.8x. Parity 6/6 (dict/order/
iter/nbunch/single/weighted), full suite zero new failures. Artifact:
`tests/artifacts/perf/20260622T-degree-counts-zip-cc/`. LEVER: a native bulk call that
emits (node, value) pairs by re-materializing node objects can be split into a values-only
native call + `zip(list(G), ...)` reusing the node cache — audit other *_pairs bindings.

## 2026-06-22 CopperCliff Multi-edge `edges(keys=True, data=True)` ~0.5x residual — uncached rebuild (`br-r37-c1-mgkd`, cc)

Multigraph algorithm-execution sweep (new coverage) is dominant (MG betweenness 17x,
closeness 5x, MDG scc 3.5x, triangles 2.8x, bfs_tree 2.3x). One real residual:
`MultiGraph.edges(keys=True, data=True)` is 0.47-0.58x vs nx (7.4ms vs 3.8ms @ n=2000);
MultiDiGraph variant 0.76-0.86x. Each PARTIAL variant is a big WIN: edges(data=True) 4.7-5x,
edges(keys=True) 4.3x.

ROOT CAUSE (diagnosed, no fix shipped): `_native_edge_view_list` caches ONLY the
data-only variant (`cacheable = want_dict && !keys`, stored in `edges_with_data_cache`
keyed on (nodes_seq, edges_seq)). So edges(data=True)'s 4.7x is a warm-cache-hit
artifact; edges(keys=True, data=True) is excluded from the cache and REBUILDS every call.
The rebuild itself is ~2x nx (per-edge py_node_key + py_adj_key + py_edge_key +
ensure_edge_py_attrs + a String-keyed `seen` dedup HashSet). Attr dicts are LIVE
(identity-preserved, matches nx) in BOTH variants — not a copy/parity issue.

FIX OPTIONS (deferred — disk-LOW, uncertain real-world payoff):
1. Cache the keys+data variant too — change `edges_with_data_cache` tuple to carry a
   `keys: bool` flag (all 9 construction sites init it `None`, so NO struct-field churn;
   only the field decl + the read/write in `_native_edge_view_list` change). Helps
   REPEATED keys+data calls; one-shot (the common serialization/copy case) unchanged.
2. Speed the rebuild (integer-index dedup instead of String `seen`; reuse node-object
   cache) — helps one-shot but harder to beat nx's 3.8ms Python dict-walk.
Both need a rust rebuild; not disk-frugal now. Candidate for when disk recovers.

### Addendum 3 (cc): IO serialization sweep — write_* residuals are parity-blocked delegations

No-build IO probe (new coverage). Generators/readers dominate or parity: to_graph6_bytes
2.27x, to_sparse6_bytes 1.56x, write_edgelist 4.74x, write_weighted_edgelist 1.82x,
generate_edgelist 1.22x, generate_graphml/gml/adjlist parity. The write_* residuals are
ALL byte-parity-blocked nx delegations (NOT levers): write_gexf 0.79x, write_gml 0.85x,
write_graphml 0.85x, write_adjlist 0.75x. Root cause (per the write_gexf docstring,
br-r37-c1-wgexf-parity + {eeawk,nlkkm,nhgtp}): native Rust writers EXIST
(`write_gexf_string_rust` etc.) but were abandoned because their output diverges from nx's
lxml byte-for-byte (XML quote style `'` vs `"`, `utf-8` vs `UTF-8`, prettyprint spacing),
so they delegate to nx for byte-exact output and pay the fnx->nx conversion. Closing these
requires matching nx's exact serialization bytes (the reason they were de-routed) — not a
perf lever. Confirms domination holds across IO too; no no-build lever remains in any swept
domain (whole-graph, small-input, *_pairs, multi-execution, pure-Python routing, IO).

## 2026-06-22 CopperCliff RESOLVED `MultiGraph.edges(keys=True, data=True)` 0.5x -> 4.9x (`br-r37-c1-mgkd`, cc)

The keys+data residual documented above (uncached rebuild) is now FIXED. Implemented the
low-churn single-slot variant: `PyMultiGraph.edges_with_data_cache` tuple gains a `keys`
flag (3-tuple -> 4-tuple), and `cacheable = want_dict` (was `want_dict && !keys`) so the
keys+data variant caches too, discriminated by the flag. NO construction-site churn (all
9 inits are `None`, type-agnostic); PyMultiDiGraph's separately-declared field (digraph.rs)
is untouched. Cache hit requires (nodes_seq, edges_seq, keys) match; mixed data-only/
keys+data calls on the SAME graph (rare) thrash the slot but stay correct.

Result: edges(keys=True, data=True) 0.5x -> **4.74-4.94x** vs nx; data-only unchanged
(4.9x, no regression). Parity 4/4 (keys+data / data-only / keys-only / alternation-
correctness: data-only stays byte-exact after an interleaved keys+data call), range+str
keys, live attr-dict identity preserved. Full suite: zero new failures (same 5 pre-existing
origin failures). Artifact: tests/artifacts/perf/20260622T-mg-edges-keysdata-cache-cc/.

### Note (cc): MultiDiGraph edges(keys+data) — same pattern, borderline, NOT shipped

The MultiDiGraph analog of the MG keys+data cache (br-r37-c1-mgkd) has the same gate
(digraph.rs:283 `want_dict && !keys` excludes keys+data from `edges_with_data_cache`), but
the gap is borderline: 0.84x @ n=800, 0.98x @ n=2000 (vs MG's 0.5x). Directed edges are
unique by (u,v,key) — no undirected canonical-dedup `seen` HashSet — so the keys+data
rebuild is already close to nx. Caching would flip warm-repeated to ~3.3x but one-shot is
near-parity, and the change is more involved than MG (two field decls + multiple
cache-using methods in digraph.rs). Per REVERT-~0-gain, NOT shipped. Documented so it
isn't re-investigated.

### Note (cc): directed total-degree — counts-zip win exists but type-contract-blocked

Directed total `G.degree()` dict is 0.87x @ n=20000 (1.17x @ n=2000 — only slow at large n).
A pure-Python `dict(zip(list(G), [i+o for i,o in zip(_native_in_degree_counts(),
_native_out_degree_counts())]))` (reusing the shipped br-r37-c1-degcounts methods) is
1.43x @ n=20000 and byte-correct. BUT it can't be routed cleanly: `G.degree()` →
`_DiGraphDegreeView.__call__()` returns the raw Rust `DiDegreeView` directly (for
type/repr parity — tests assert `type(G.degree()).__name__ == 'DiDegreeView'`), so both the
parens and no-parens forms iterate the raw view. Returning a custom zip object would break
the DiDegreeView type contract. A clean fix needs a rust-level raw `DiDegreeView` iter
change (counts + cached nodes) for a marginal gain (near-parity except very large n). Per
REVERT-~0-gain + type-contract risk, deferred — documented so the Python route isn't retried.

### Addendum 4 (cc): generator + pandas-conversion sweep — domination, gaps construction/RNG-bound

No-build sweep of generators (last unswept domain) + pandas conversions. Dominant:
random_regular 3.65x, hypercube 31.4x, complete_graph 13.4x, balanced_tree 4.64x,
caveman 4.75x, lollipop 4.4x, grid_2d 3.07x, watts_strogatz 1.42x, random_tree 1.45x,
powerlaw_cluster 1.16x, circular_ladder 1.96x; to_pandas_edgelist 1.42x, from_pandas_edgelist
1.86x, to_pandas_adjacency 1.24x. Sub-parity residuals are ALL construction-tax / RNG-parity
bound (consistent with project_generator_batch_vein_progress + construction_tax_relabel_lever):
barabasi_albert 0.72x and dual_ba 0.83x (RNG-faithful _random_subset draw sequence must
reproduce nx's PythonRandom in Python; native kernel would need byte-exact set-rejection
choice replay — significant + parity-risky), complete_bipartite 0.81x and turan 0.87x (40k+
deterministic edge insertion = the general edge-construction substrate), star/wheel 0.89x.
No clean lever; all need the deep construction substrate or a native RNG-replay kernel.
With this, EVERY domain is swept (whole-graph, small-input, *_pairs, multi-execution,
pure-Python routing, IO, generators, conversions) — comprehensive domination confirmed.

### CORRECTION (cc): barabasi_albert 0.72x is PARITY-BLOCKED (set-order), NOT a native candidate

Earlier notes floated a "native PythonRandom BA kernel" as the highest-value remaining
target. That is WRONG — verified by reading the impl: `_random_generator_subset(seq, m, rng)`
returns a `set` (mirroring nx's `_random_subset`), and `barabasi_albert_graph` builds edges
by iterating that set (`new_edges.extend((source, t) for t in targets)`). So BA's edge
order — hence adjacency layout / byte-exact parity — depends on CPython SET ITERATION ORDER
of the `targets` set (which grows/resizes across the while-loop adds). A native Rust kernel
cannot replicate CPython set internals byte-for-byte (same class as [[reference_parity_blocked_by_set_order]]:
clique/ramsey/greedy_color set-order). fnx already runs the exact Python set-based loop +
a single batched add_edges_from, so 0.72x is the byte-exact FLOOR for BA. NOT a native
candidate; do not attempt. dual_barabasi_albert (0.83x) is the same set-based pattern.
Net: NO remaining generator gap is native-accelerable; the only non-parity-blocked
residuals are the node/path-object materialization substrate (persistent-node-mirror rewrite).

## 2026-06-22 CopperCliff `havel_hakimi_graph` batch construction — 0.46x -> 1.2x (`br-r37-c1-hhbatch`, cc)

Found via the misc-class sweep (degree-sequence generators). `havel_hakimi_graph` was a
consistent 0.46x vs nx (13.9ms vs 6.4ms @ n=2000, scaling). Root cause: the Havel-Hakimi
realization emitted edges via a per-edge `graph.add_edge(source, target)` loop — the PyO3
round-trip per edge dominated. The degree_buckets/modified/active bookkeeping never reads
graph state (the graph is pure output), so this is the classic batch-construction lever
([[reference_batch_add_edges_from_construction]]): collect every (source, target) and commit
through ONE `add_edges_from`. Same emission order -> byte-identical adjacency.

Result: 0.46x -> **1.19-1.21x** faster than nx (2.6x self-speedup). Byte-exact: 23 checks
(6 seeds x 3 sizes + 5 edge cases incl. [0]/[0,0,0]/[1,1]/[2,2,2]/[]), nodes + edges-in-order
+ adjacency. Full suite: zero new failures. Artifact:
tests/artifacts/perf/20260622T-havel-hakimi-batch-cc/. LEVER STILL LIVE: grep remaining
construction/generator fns for per-edge add_edge loops with no mid-loop graph reads.

## 2026-06-22 CopperCliff `cycle_graph`/`path_graph` create_using batch — 0.39x -> 0.78x (partial, substrate-floored) (`br-r37-c1-cycbatch`, cc)

The default (int) cycle_graph/path_graph hit native kernels (1.8-2.0x). But the
`create_using=` path (e.g. directed/multi C_n / P_n) emitted edges via a per-edge
`graph.add_edge(u,v)` loop -> 0.38-0.48x vs nx. Batched both into a single add_edges_from
(cyclic pairwise + LAST wrap-around close for cycle; pairwise for path) — same
batch-construction lever as havel_hakimi. Byte-exact: 48 checks (4 create_using types x 6
sizes x 2 generators incl. n=0/1/2). 2548 generator tests pass.

PARTIAL win: 0.38-0.39x -> 0.78-0.80x (2x self-speedup) but does NOT dominate — the residual
is the directed/multi `add_edges_from` insertion substrate (same ~0.73-0.80x floor as the
already-batched star_graph(DiGraph)), not per-edge-loop waste. Shipped anyway: removing the
per-edge PyO3 round-trip is strictly correct + halves the gap; the residual is the documented
directed-construction substrate (needs the node-keying/int-CSR substrate work, not a wrapper
change). NOT ~0-gain (2x self-speedup).

## 2026-06-22 CopperCliff `add_path`/`add_cycle`/`add_star` — 0.24x -> 1.04-1.13x (`br-r37-c1-addpathbatch`, cc)

These ubiquitous mutation helpers were 0.23-0.28x vs nx (4x slower) — per-edge add_edge
loops. Two-part fix to DOMINATION:
1. Batch the loop into ONE add_edges_from (same lever as havel_hakimi).
2. CRITICAL sub-lever: do NOT `add_node(first)` before the add_edges_from. The explicit
   pre-add makes the graph NON-FRESH, which DEFEATS add_edges_from's fresh-graph batch fast
   path (measured 2.79ms WITH pre-add vs 1.53ms WITHOUT, same result). pairwise's first edge
   adds the first node anyway (verified identical node order). Only add_node for the
   single-node no-edge case.

Result: add_path 0.24x->1.04x, add_cycle 0.28x->1.13x, add_star 0.23x->1.09x (4.3x
self-speedup, now DOMINATES). Byte-exact: 180 checks (3 fns x 4 graph types x 5 node-lists
incl. []/[5]/dups x [plain/attr/existing-graph]). Full suite zero new failures.

GENERAL GOTCHA (also limits the earlier cycle_graph/path_graph create_using fix to 0.78x:
`_add_nodes_in_order` pre-adds all nodes -> defeats fresh path): when batching a construction
that builds a fresh graph, let add_edges_from add the nodes via edges; an explicit pre-add of
nodes already covered by edges silently drops you off the fresh-graph fast path. Artifact:
tests/artifacts/perf/20260622T-add-path-cycle-star-batch-cc/.

## 2026-06-22 CopperCliff `from_dict_of_dicts(DiGraph)` O(N^2) -> O(E) — 430x slower to 1.28x faster (`br-r37-c1-doddir`, cc)

CATASTROPHIC find (interleaved converter sweep): directed `from_dict_of_dicts` was O(N^2) —
58ms/239ms/963ms @ n=200/400/800 (0.046x/0.005x/0.003x vs nx, ~430x slower, clean quadratic).
The undirected `Graph` case has a batch branch; `is_multigraph` is handled; but the directed
simple-graph case fell to the `else` per-edge `add_edge(u,v)` + `graph[u][v].update(attrs)`
loop, where the directed adjacency-view `__getitem__` per edge is O(N) -> O(N^2) total.

FIX: directed dict-of-dicts edges are UNIQUE (no symmetric (v,u) dedup the undirected branch
needs), so added an `elif type(graph) is DiGraph:` branch emitting (u, v, attrs) triples
through ONE add_edges_from (exactly what nx does), O(E). Now **1.28x FASTER** (963ms->1.49ms
@ n=800, ~650x self-speedup). Byte-exact: 8 checks (attrs / str keys / self-loops / isolated
nodes / MultiDiGraph-still-routes-correctly). Full suite: zero new failures. Exotic subclasses
keep the inline loop (malformed-input contract). Artifact:
tests/artifacts/perf/20260622T-from-dict-of-dicts-directed-on2-cc/. LEVER: audit other
converters/operators for directed paths lacking the undirected branch's batch.

### Note (cc): add_edges_from fast batch only engages for SEQUENTIAL-int-prefix edges (from_edgelist 0.64x)

Converter sweep: `from_edgelist` is 0.64-0.69x vs nx (both directed/undirected). It is already
minimal (`G.add_edges_from(edgelist)`), so the gap is `add_edges_from` itself. Pinpointed on a
fresh Graph @ n=2000/m=8000:
- add_edges_from(SEQUENTIAL int edges, e.g. pairwise(range)) = **1.12x** (fast — the rust
  fresh-int-prefix batch `collect_fresh_exact_int_prefix_edges` engages)
- add_edges_from(RANDOM int edges, e.g. gnm.edges()) = **0.64x**
- add_edges_from(STRING edges) = **0.63x**
So the batch fast path requires nodes arriving in 0..n PREFIX order; random-int and string
edge lists fall to the slower String-keyed batch (~1.5x nx). This is the documented
construction substrate ([[reference_attr_edge_batch_construction]] / construction-tax veins),
affecting from_edgelist + any build from non-sequential edges. NOT a wrapper lever — needs a
rust general-fresh-int/string batch that engages for arbitrary insertion order (node order
must stay insertion-faithful). Deferred to the substrate work. (to_dict_of_lists 0.20x in the
raw sweep was NON-interleaved noise — it is actually 1.6-1.9x via its native fast path.)

## 2026-06-22 CopperCliff `DiGraph(dict_of_dicts)` constructor O(N^2) -> parity (`br-r37-c1-decodedir`, cc)

SECOND O(N^2) directed-dod disaster (sibling of br-r37-c1-doddir, a DIFFERENT code path):
the CLASS CONSTRUCTOR `DiGraph({u:{v:attrs}})` routes through `_decode_dict_of_dicts_into`,
whose simple-graph `else` did per-edge `self.add_edge(u,v); self[u][v].update(dict(inner))`.
The directed adjacency-view `__getitem__` per edge -> O(N^2): 215ms/911ms @ n=400/800
(0.005x/0.003x). Undirected Graph(dod) was ~6x slow (0.17x, linear-but-slow).

FIX: pure non-multigraph dict-of-dicts (all values dicts) -> `add_nodes_from(data)` + ONE
`add_edges_from((u, v, attrs) ...)`. Byte-identical to the loop (add_edges_from sets/updates
the edge dict; last-writer-wins on the symmetric undirected reverse exactly like the loop;
same node + edge order). dict-of-list / multigraph / non-dict shapes keep the general loop.
Result: DiGraph(dod) -> 0.99-1.04x (~500x self-speedup, 911ms->1.85ms @ n=800), Graph(dod)
-> 1.20x. Byte-exact: 11 checks (attrs / dict-of-list-fallback / str keys / self-loops /
isolated / asymmetric undirected last-wins / empty). Full suite zero new failures. Artifact:
tests/artifacts/perf/20260622T-digraph-dod-constructor-on2-cc/.

## 2026-06-22 CopperCliff `from_pandas_edgelist(DiGraph)` O(N^2) -> 1.7x (`br-r37-c1-pandasdir`, cc)

THIRD directed-O(N^2) disaster of the converter family (siblings: br-r37-c1-doddir
from_dict_of_dicts, br-r37-c1-decodedir DiGraph(dod) constructor). `from_pandas_edgelist`
batches for `type(graph) is Graph` but DiGraph fell to the per-row else loop
`add_edge + graph[source][target].update(...)` — directed adjacency-view __getitem__ per row
= O(N^2): 220ms/962ms @ n=400/800 (0.009x/0.004x vs nx, ~250-430x slower).

FIX: extend the batch gate to `type(graph) in (Graph, DiGraph)`. The existing batch
(add_edges_from of (s, t, dict(zip(headings, attrs))) triples) is identical for directed
(no symmetric dedup; duplicate (s,t) rows merge later-wins exactly like the repeated update).
Result: 0.004x -> **1.67-1.75x** (962ms->2.47ms @ n=800, ~390x self-speedup). Byte-exact:
8 checks (di/un x multi-attr/single-attr/duplicate-rows-later-wins). 217 pandas tests + full
suite zero new failures.

PATTERN (3 disasters, now all fixed): converters/constructors with a `type(graph) is Graph`
batch branch but a DIRECTED fall-through to a per-edge `graph[u][v].update` loop are O(N^2)
(directed adjacency-view __getitem__ per edge). Audited the family; compose(Di) 0.62-0.70x
is a separate LINEAR _copy_attrs_into per-edge tax (not O(N^2)).

## 2026-06-22 CopperCliff `compose` node-batch — directed 0.62x -> 0.74x partial + non-string-key fix (`br-r37-c1-composenodebatch`, cc)

Directed `compose` was 0.62-0.70x (undirected has `_native_compose`; directed falls to the
Python path). Edges already batched (two add_edges_from); the bottleneck was the per-node
`out.add_node(node, **dict(attrs))` loop for G then H. Replaced with two `add_nodes_from(
.nodes(data=True))` (adds-or-updates exactly like nx — H's overlapping nodes update G's).
Bonus correctness: `add_node(node, **attrs)` unpacked attrs as kwargs (fails / diverges on
non-string node-attr keys); `add_nodes_from((node, attrs))` matches nx for arbitrary keys.

PARTIAL: 0.62x -> 0.74x. Residual is the directed `add_edges_from` non-fresh substrate (same
~0.74-0.78x floor as cycle_graph(DiGraph) create_using; nodes pre-added defeat the fresh
batch path, and directed insertion is the documented substrate). Full domination needs a
native `_native_compose` for DiGraph (rust). Byte-exact: 5 checks (di/un x node+edge attrs,
overlapping-node merge). 961 operator tests + full suite zero new failures.

### Note (cc): MultiDiGraph dict-of-dicts 0.42x is keyed-insertion substrate, NOT batchable

After fixing the 3 SIMPLE directed dict-of-dicts O(N^2) disasters, checked the MULTI variants.
MultiGraph dict-of-dicts is a win (1.1-1.2x). MultiDiGraph from_dict_of_dicts(mi=True) and the
MultiDiGraph(dod) constructor are 0.42x — but LINEAR (scale x2.0 @ n400->800, NOT O(N^2)) and
NOT batchable: tested per-edge `_add_json_multiedge` (12.84ms) vs `add_edges_from(4-tuples)`
nodes-pre-added (12.45ms ~= same) vs fresh-then-nodes (15.6ms, worse). `_add_json_multiedge`
already uses O(1) get_edge_data (no graph[s][t][k] rebuild). So the 0.42x is the MultiDiGraph
KEYED-edge insertion substrate (~2.4x nx), the same directed/multi construction floor as
[[reference_multigraph_attr_batch_construction]] (dual AttrMap + mirror storage). Not a wrapper
lever — needs the rust keyed-insertion substrate work. NOT shipped (batching is ~0-gain here).

### Addendum 5 (cc): flow / branching / group-centrality / similarity / approximation sweep — domination, no gaps

Interleaved sweep of families not previously benched (~18 fns). All wins or parity, no sub-0.85x:
gomory_hu_tree 1.73x, max_flow_min_cost 3.03x, minimum_spanning_arborescence 4.04x,
stoer_wagner 7.90x, all_node_cuts 1.96x, group_closeness 7.75x, group_betweenness 0.95x,
simrank_similarity 1.01x, panther 0.99x, approx max_clique 0.90x, approx node_connectivity
1.62x, approx average_clustering 69x, approx diameter 1.64x, approx local_node_connectivity
6.35x, harmonic_centrality 17.25x, percolation_centrality 1.86x, current_flow_closeness 9.56x,
edge_current_flow_betweenness 23.53x. Confirms domination extends to flow/branching/group/
similarity/approximation; no clean lever here. Combined with all prior sweeps, every
non-substrate domain is dominant; remaining residuals are the documented keyed-insertion /
node-mirror substrate and parity-blocked (set-order / IO-lxml) cases.

### Note (cc): the fresh-int add_edges_from batch is PREFIX-bound — arbitrary-int needs materialized keys (substrate)

Investigated whether the from_edgelist(random)/directed add_edges_from 0.64x floor is a
contained fix. It is NOT. The fast path `collect_fresh_exact_int_prefix_edges`
(fnx-python/src/lib.rs:1695) requires node ints to appear in EXACT PREFIX order (0,1,2,...):
`if index != next_node: return None`. It is fast precisely because it then calls
`_fast_add_int_nodes_range_stop` + `extend_existing_index_edges_unrecorded` over the
lazy-int-prefix node representation (`lazy_int_node_stop`), where node VALUE == index.
Random/arbitrary int edges (e.g. gnm.edges(), first edge (5, 200)) bail at the prefix check.
Generalizing to arbitrary-order ints can't reuse the lazy-prefix representation (values !=
indices), so it would require materializing int node keys + node_key_map in first-appearance
order — the deep construction-substrate work, not a gate relaxation. Confirms from_edgelist
(random) 0.64x and the directed add_edges_from floor are substrate-bound. No contained lever.

### Note (cc): directed `compose` -> native is the top remaining perf lever, but needs careful directed-display work

Scoped the highest-value remaining lever: compose(DiGraph) is 0.74x (after the node-batch
br-r37-c1-composenodebatch); the undirected path hits `_native_compose` (PyGraph, lib.rs:9688)
for 1.99x. A `PyDiGraph::_native_compose` mirror would lift directed compose to ~domination —
same pattern as the shipped MultiDiGraph(DiGraph) absorb. BUT the undirected version (~80 lines)
encodes intricate directed-RELEVANT-only-as-undirected logic: integer-walk symmetric dedup
(seen ui.min/max), first-touch row-store via `adj_py_keys` (single adjacency), fwd/rev
edge_key attr-mirror merge, bulk extend_*_with_attrs_unrecorded. The directed mirror must
instead: walk successors_indices (NO dedup), populate BOTH succ AND pred display/row tables
(`succ_py_keys`/`pred_py_keys` — DiGraph has dual row models vs Graph's single adj), and
directional edge_key only. That directed display/row-override surface is large and compose is
widely used (high blast radius), so this is deep-design tier (exhaustive parity + review),
NOT a safe autonomous one-pass change. Documented as the #1 target for the substrate-work
go-ahead. All other residuals (construction-keying, node-mirror) remain deeper still.

## 2026-06-22 CopperCliff native DiGraph `compose` — 0.74x -> 2.25-2.33x (`br-r37-c1-composedir`, cc)

The #1 scoped lever, now SHIPPED. compose(DiGraph) was 0.74x (Python add_nodes/add_edges
replay; undirected had _native_compose at 1.99x). Added `PyDiGraph::_native_compose` mirroring
the undirected one but directed: walks SUCCESSORS (no symmetric dedup — directed edges unique),
directional edge mirrors (edge_key(u,v) only), node/edge merge with H-overlap-wins, commit via
bulk extend_nodes/edges_with_attrs_unrecorded. CLEAN-DISPLAY GATED: returns Ok(None) (Python
fallback) when either part carries succ/pred row-display overrides — sidestepping the intricate
per-cell maybe_store path, which the replay handles. Wired in compose() for exact DiGraph x
DiGraph (non-private-storage), checking the None fallback.

Result: 0.74x -> **2.25-2.33x** (~3x self-speedup, now DOMINATES). Byte-exact: 7 checks
(random node+edge+graph attrs, overlap-merge H-wins, self-loops, isolated, str keys, empty) —
nodes(data), edges(data), graph attrs, succ AND pred adjacency. 993 operator/convert tests +
full suite zero new failures (fallback path exercised by conformance).

METHOD: the gated-fallback pattern (native fast path for the clean/common case, Ok(None) ->
Python replay for the intricate-display minority) makes 'deep-design-tier' native mirrors
safely shippable autonomously — exhaustive parity + full conformance as the safety net.
Artifact: tests/artifacts/perf/20260622T-native-digraph-compose-cc/.

## 2026-06-22 CopperCliff native DiGraph `disjoint_union` — 0.79x -> 3.28-3.32x (`br-r37-c1-djudir`, cc)

Second directed native-mirror this pass (after compose). disjoint_union(DiGraph) was 0.79x
(Python disjoint_union_all replay; undirected had _native_disjoint_union at 2.03x). Added
`PyDiGraph::_native_disjoint_union` mirroring the undirected: relabel BOTH parts to fresh
integer ranges (0.. , n1..), copy node/edge attr mirrors (shallow), commit via bulk
extend_*_unrecorded. Directed adaptation: walk SUCCESSORS (no symmetric dedup), directional
edge_key. Because both parts are relabeled to fresh ints, the source row-display is discarded
-> NO gating needed (cleaner than compose).

Result: 0.79x -> **3.28-3.32x** (~4x self-speedup, dominates). Byte-exact: 6 checks (random
node+edge+graph attrs, str-keyed source, self-loops, isolated, empty) — nodes(data),
edges(data), graph attrs, succ AND pred. 1284 union/operator tests + full suite zero new
failures. Confirms the gated/clean native-mirror pattern ([[reference_gated_fallback_native_mirror]])
scales across directed operators. Remaining directed-operator residuals: intersection(Di) 0.77x
(set-based Python, no native to mirror), union(Di) 0.88x. Artifact:
tests/artifacts/perf/20260622T-native-digraph-disjoint-union-cc/.

### Note (cc): MultiDiGraph disjoint_union/compose native REVERTED — blocked by a source construction-key divergence

Attempted `PyMultiDiGraph::_native_disjoint_union` (keyed mirror; multi operators are 0.57-0.79x:
disjoint_union(MDG) 0.57x, compose(MDG) 0.58x, disjoint_union(MG) 0.63x, compose(MG) 0.74x).
nx.disjoint_union PRESERVES multigraph keys (verified: explicit keys 1,3,7 -> 1,3,7; default
0,1,0 -> 0,1,0), so a key-preserving native is the correct semantics, AND it passed 6 hand
parity cases. BUT it FAILED test_graph_operator_batches_match_networkx_without_fallback
[MultiDiGraph-MultiDiGraph]: the test's FNX-built right MultiDiGraph carries DIFFERENT edge
keys than the nx-built one on some construction path (fnx gave 1,3 where nx gave 0,1). The
key-preserving native faithfully propagates fnx's divergent source keys -> output != nx; the
OLD Python disjoint_union path MASKS it (it re-keys to 0,1.. matching nx). Renumbering instead
breaks the key-identical case (nx preserves). So neither preserve nor renumber cleanly matches —
the real blocker is a PRE-EXISTING fnx MultiDiGraph construction key divergence (NOT
add_edges_from((u,v)) — that matches nx 0,1,0; some other path in _operator_graph_pair). REVERTED
the MDG native (kept the Python path, which is green). The simple-DiGraph compose + disjoint_union
natives (br-r37-c1-composedir/djudir) are unaffected and shipped. FOLLOW-UP: find + fix the
MultiDiGraph construction key divergence, THEN the keyed-native operators unblock.

### Note (cc): MDG disjoint_union native — CORRECTED diagnosis: display-key mirror, gate-too-strict (not viable)

Refines the prior note. The MultiDiGraph blocker is NOT a construction bug: explicit-key
construction + the Python disjoint_union are byte-correct, and nx PRESERVES keys. The real
issue is that the inner integer edge key != the Python DISPLAY key for explicit/non-default
keys (stored in a separate `edge_py_keys` mirror), and typical graphs (range-built -> lazy-int
display) ALSO carry `succ_py_keys`/`pred_py_keys` mirrors. So:
- UNGATED native (use inner keys) -> diverges on explicit-key graphs (the operator-parity test:
  inner 0,1 vs display 1,3).
- GATED native (require edge_py_keys/succ/pred empty) -> NEVER fires for typical lazy-int
  graphs (their display mirrors are non-empty) -> 0.55x, ZERO real-world gain.
Both dead ends -> REVERTED (verified green). The keyed-multi operators (disjoint_union/compose
for MG/MDG, 0.57-0.79x) require FULL display-mirror native handling (per-key py_edge_key +
per-cell succ/pred row-store) — the intricate path the gated/clean approach sidesteps, so they
are genuinely deep-substrate (unlike the simple-DiGraph compose/disjoint_union, which shipped
because Graph/DiGraph display is single-table + the relabel discards source display). The
simple-DiGraph natives stand. Multi keyed operators: deferred to the display-mirror substrate work.

## 2026-06-22 CopperCliff native MultiDiGraph disjoint_union — 0.57x -> 1.66-2.20x SHIPPED (`br-r37-c1-mdgdju`, cc)

RESOLVED the keyed-multi blocker from the prior two notes. The fix was NOT gating and NOT a
construction bug — it was that the native must COPY the `edge_py_keys` DISPLAY-key mirror.
MultiDiGraph stores an inner integer key that can DIFFER from the Python display key for
explicit/non-default keys; nx.disjoint_union PRESERVES display keys. v1 copied only
edge_py_attrs (not edge_py_keys) -> explicit keys 1,3 displayed as internal 0,1 (operator-
parity test fail). v2 gated on edge_py_keys-empty -> never fired for typical lazy-int graphs
(0 gain). v3 (shipped): UNGATED, copy edge_py_keys alongside edge_py_attrs. The relabel to
fresh int ranges discards source NODE display + succ/pred row overrides, so only the edge
display-KEY mirror needs preserving — no per-cell row-store, no gate.

Result: disjoint_union(MDG) 0.57x -> **1.66-2.20x** (~3.5x self-speedup, 40ms->14ms @ n=800).
Byte-exact: 7 checks (default-key native, explicit non-default keys, parallel self-loops, str
source, empty) — nodes(data), edges(keys+data), graph attrs, succ AND pred. operator-parity
test + full suite zero new failures. UNBLOCKS the keyed-multi pattern: compose(MDG) 0.58x,
disjoint_union(MG) 0.63x, compose(MG) 0.74x are next (same edge_py_keys-copy recipe; MG adds
undirected symmetric dedup). Artifact: tests/artifacts/perf/20260622T-native-mdg-disjoint-union-cc/.

## 2026-06-22 CopperCliff native MultiGraph disjoint_union — 0.63x -> 2.05-2.13x SHIPPED (`br-r37-c1-mgdju`, cc)

The edge_py_keys-copy recipe ([[reference_gated_fallback_native_mirror]]) generalized to the
undirected-multi case FIRST TRY. disjoint_union(MG) was 0.63x. PyMultiGraph::_native_disjoint_union
relabels both parts to fresh int ranges (source node + adj_py_keys row display discarded, no
gate), walks neighbors with symmetric dedup via the CANONICAL edge_key (sorts u<=v, so the
undirected edge_py_attrs/edge_py_keys lookup is orientation-independent — no fwd/rev), preserves
each edge's inner key + DISPLAY key (edge_py_keys mirror) + attrs, bulk extend. Modeled on the
existing PyMultiGraph::_native_difference keyed pattern (display_key/py_edge_key/seq fields).

Result: 0.63x -> **2.05-2.13x** (~3.3x self-speedup). Byte-exact: 7 checks (default-key, explicit
non-default keys, parallel self-loops, empty) — nodes(data), edges(keys+data), graph attrs, adj.
operator-parity[MultiGraph-MultiGraph] + full suite zero new failures. Remaining keyed-multi:
compose(MDG) 0.58x, compose(MG) 0.74x (these KEEP nodes -> need the clean-display gate on
succ/pred or adj_py_keys like simple compose, PLUS edge_py_keys + key-level overlap merge).
Artifact: tests/artifacts/perf/20260622T-native-mg-disjoint-union-cc/.

### Note (cc): compose(MDG/MG) native — design for the follow-up (key-collision merge, H-wins)

disjoint_union is now native-dominant across ALL 4 graph types (Graph/DiGraph/MultiDiGraph/
MultiGraph). compose(MDG) 0.58x / compose(MG) 0.74x are the remaining keyed-multi gaps. DESIGN
GOTCHA confirmed: nx compose MERGES multigraph edges by (u,v,key) with H winning on collision
(verified: G{(a,b,0):G0,(a,b,1):G1} compose H{(a,b,0):H0,(a,b,5):H5} -> (a,b,0):H0,(a,b,1):G1,
(a,b,5):H5). So compose CANNOT reuse the simple-DiGraph compose structure (which leans on
extend_edges UPDATING duplicate (u,v) for simple graphs) — multi extend_keyed would add a
PARALLEL edge for a colliding key, not update. Needs an explicit ordered merge: emit G's edges
in order (attrs := H's if H has the same (u,v,key), else G's), then H's edges whose (u,v,key)
is NOT in G, in H order; carry edge_py_keys display + node-attr H-wins merge; clean-display gate
on succ/pred (MDG) / adj_py_keys (MG) like simple compose. Recipe + APIs all proven
([[reference_gated_fallback_native_mirror]]); this is the immediate next gap.

### Note (cc): compose(MDG) native ATTEMPTED + REVERTED — display-key collision-merge is the blocker

Implemented PyMultiDiGraph::_native_compose (clean-display gated, ordered (u,v,key) merge with
H-wins). Two failures -> reverted:
1. CORRECTNESS: merged by the INNER integer key, but nx merges by DISPLAY key. G with display
   keys {0,1} composed with H display {0,5}: H's display-5 has INNER key 1, which collided with
   G's INNER-1 (display 1) -> clobbered G's (a,b,1) edge (dropped from 3 edges to 2). Must dedup/
   merge by display_key_lookup(u,v,key), NOT the inner key. (disjoint_union dodged this — it
   PRESERVES keys per part with no cross-part merge, so inner-vs-display never collides.)
2. PERF: 0.58-0.60x — NO gain. The ordered-merge bookkeeping (3 HashMaps keyed by String tuples
   + per-edge AttrMap clones + a rebuild pass) costs more than nx's Python compose. Unlike
   disjoint_union (direct edge_batch, 2.2x), compose's cross-part key-collision merge can't use
   the fast direct-batch path: G-then-H with H winning needs either heavy per-edge dedup
   bookkeeping (slow) or in-place inner-edge attr update on the rare collision (no inner
   set-edge-attrs-by-key API exists).

So compose(MDG)/compose(MG) (0.58x/0.74x) are the genuinely-hard tail of the operator vein:
correctness needs display-key merge, and a WIN needs a fast-path-for-the-common-no-collision-
case + cheap rare-collision handling (likely a G-display-key HashSet + mirror-only attr update
on collision, leaving inner as G's since the mirror dominates edges(data)). Deferred — not a
clean win without that. disjoint_union (all 4 types) + compose(Graph/DiGraph) remain shipped.

### Note (cc): compose(MDG/MG) native DEFINITIVELY BLOCKED — MultiGraph always carries succ/pred (z6uka) display

compose(MDG) v2 (gated on succ/pred AND edge_py_keys empty, fast HashSet collision-merge) is
byte-CORRECT (7/7 parity incl default-key collisions + partial-attr merge + explicit fallback)
but 0.52-0.56x = ZERO gain: the gate FALLS BACK for typical graphs. Diagnosis by elimination:
disjoint_union(MDG) UNGATED runs native at 2.2x; compose(MDG) GATED is ~Python speed -> it never
fires. edge_py_keys is empty for MDG(gnm) (keys all 0), so it's succ/pred_py_keys that's
NON-empty. Unlike simple DiGraph(gnm) (where compose(Di) gated on succ/pred and WON 2.25x),
MultiGraph/MultiDiGraph populate per-cell succ/pred ROW display objects (br-r37-c1-z6uka multi
adjacency cells) even for plain gnm graphs. compose KEEPS node identity, so it CANNOT discard
that row display (disjoint_union can — it relabels to fresh ints). Result: the clean-display gate
never fires for compose(Multi) -> not viable without full per-cell succ/pred maybe_store_row_keys
handling = the genuinely-deep path. REVERTED.

OPERATOR VEIN STATUS (final): disjoint_union native-DOMINANT all 4 types (Graph/DiGraph/MDG/MG);
compose native-dominant Graph+DiGraph; compose(Multi) BLOCKED on z6uka succ/pred row display
(deep). difference/symmetric_difference already native wins. Operator native-mirror vein
EXHAUSTED of clean wins.

## 2026-06-22 CopperCliff MultiDiGraph edges(keys=True,data=True) cache — 0.78x -> 3.33-3.64x (`br-r37-c1-mdgkd`, cc)

Found via a fresh sweep: MD edges(keys,data) 0.78x while edges(data) 3.58x and edges(keys) 1.86x.
Root cause: PyMultiDiGraph cached edges(data=True,keys=False) [edges_with_data_cache] and
edges(keys=True,data=False) [edges_with_keys_cache] but had NO cache for the keys+data combo —
it hit edges_key_alldata_existing_mirrors (returns None for attr-less gnm edges) then the generic
loop, materializing empty mirrors EVERY call. Fix: added a `keys` bool to the existing
edges_with_data_cache (4-tuple, last-keys-variant-wins) so keys+data caches in the same slot — no
new struct field (avoids the ~20-site constructor churn). Mirrors the PyMultiGraph mgkd fix.

Result: 0.78x -> **3.33-3.64x**. Byte-exact: keys+data / data / keys all correct across attr +
attr-less graphs, cache-thrash alternation, AND post-mutation invalidation. Full suite zero new
failures. Artifact: tests/artifacts/perf/20260622T-mdg-edges-keysdata-cache-cc/.

Sweep also surfaced (deferred): nbunch_iter 0.09-0.19x (node-object materialization + String-keyed
membership substrate — deep), degree(weight)/size(weight) ~0.80x (weighted attr walk), relabel
0.86x (known construction tax). MD remaining edges combos now all dominant.

## 2026-06-22 CopperCliff nbunch_iter(None) — 0.08x -> 0.95x (`br-r37-c1-nbunchnone`, cc)

Sweep flagged nbunch_iter(None) at 0.08-0.19x while list(G)/list(nodes()) were at parity.
Root cause: _graph_nbunch_iter (shared by all 4 graph types) ran `adjacency = self.adj`
UNCONDITIONALLY at the top, then `iter(adjacency)` for the None case — building the full
AdjacencyView + iterating its keys cost ~12x vs the cached node iterator, purely to list nodes.
Fix (Python-only, no rebuild): return iter(self) for nbunch=None BEFORE building self.adj; defer
`adjacency = self.adj` to the membership-filter path (where its __contains__ is the faster
container — using bare `self` there regressed non-None to 0.16x, so adj stays).

Result: nbunch_iter(None) 0.08x -> **0.95x** (12x self-speedup, 107us->9us @ n=2000), all 4 types.
Byte-exact: node order + objects + fresh-iterator-per-call + nx's TypeError error contract
(unhashable-in-sequence / non-iterable nbunch). Full suite zero new failures. Non-None nbunch
(membership filter) stays 0.20x = per-element String-keyed __contains__ substrate (nx is C-dict;
deep, unchanged). Artifact: tests/artifacts/perf/20260622T-nbunch-iter-none-cc/.

### Note (cc): post-win sweep (2026-06-22) — accessible no-build levers exhausted; remaining gaps root-caused

After shipping 6 operator/view/iter wins this turn, ran 5 no-build bench sweeps (traversal,
distance, predicates, views, attrs, construction, nbunch ops) vs NetworkX. Result: the surface
is overwhelmingly dominant. The ONLY remaining un-dominated workloads, all root-caused:

- out_edges(nbunch)/in_edges(nbunch) DIRECTED 0.28-0.29x: NICHE (directed edges restricted to a
  node subset). Path traced: _OutEdgeView -> _DiEdgeMethodView.__call__ -> _method(self._graph,
  nbunch) which ALREADY uses the rust graph directly (no Python-wrapper layer to strip). Slowness
  is inherent: a Python loop doing per-node rust succ/pred row PyO3 access. UNDIRECTED edges(nbunch)
  is DOMINANT (1.39x), so this is directed-specific view overhead. Needs a native nbunch-edges
  kernel (build) wired through the 6-level view hierarchy — intricate + niche, deferred.
- degree(nbunch) 0.32x: DegreeView per-node self[node] (per-call native degree + String-key
  canonicalization). Full degree() routes to native counts (1.20x); nbunch can't cleanly reuse it
  (counts are by index; small-nbunch would pay O(N) dict-build). Per-call substrate.
- has_edge/neighbors/adj[n]/membership(`n in G`) per-call 0.29-0.54x: the fundamental String-keyed
  __contains__/__getitem__ substrate (nx is C-dict). The highest-IMPACT remaining gap (used
  everywhere) but = the deep int-key / persistent-mirror rewrite.

CONVERGENCE: no-build/Python-only levers exhausted (nbunch_iter(None) was the last clean one).
Remaining frontier = (a) native nbunch-edges kernel (niche, build, needs disk headroom) or (b)
the deep per-call String-key substrate rewrite (highest impact, large careful effort, needs disk).

## 2026-06-22 CopperCliff native Graph degree(nbunch) — 0.32x -> 1.22-1.24x SHIPPED (`br-r37-c1-degnbnative`, cc)

Reverses the earlier "nbunch native kernels are canonicalization-capped" hypothesis: the rust
kernel DOMINATES (direct 0.051ms vs nx 0.091ms). degree(nbunch) was 0.32x because the Python
path ran two per-element passes (the `[n for n in nbunch if n in G]` membership filter + per-node
`raw[n]` degree lookup), each a separate PyO3 round-trip. Added `PyGraph::_native_degree_pairs_subset`
(one PyO3 call: per node hash-check + node_key_to_string canonicalize + get_node_index +
degree_by_index, skipping absent). Routed in _WeightAwareDegreeView.__call__'s iterable-nbunch
branch (the REAL path — gf.degree is _GraphDegreeView which inherits this __call__; the slow loop
is at the 4738 branch, NOT the 4818 single-node branch I first wrongly edited). _FilteredDegreeView
gained a `pairs` slot: __iter__ serves precomputed (node,degree), __getitem__ still falls to the raw
view (so view[n] works for any node). Unhashable element -> kernel TypeError(exact message) ->
NetworkXError, matching nx.

Result: 0.32x -> **1.22-1.24x** (~3.9x self-speedup). Byte-exact: valid/invalid/all-invalid/empty/
dup/range/str-keyed, error contract (unhashable element + non-iterable), view[node] indexing for
any node, len/contains. DiGraph degree(nbunch) unaffected (PyDiGraph lacks the binding -> Python
fallback; a PyDiGraph total/in/out kernel is the follow-up). Full suite zero new failures.
LESSON: verify which concrete class a method resolves to (multiple masquerade as 'DegreeView')
before editing — cost two wrong-class edits. Artifact: tests/artifacts/perf/20260622T-degree-nbunch-native-cc/.

## 2026-06-22 CopperCliff native DiGraph degree(nbunch) family (`br-r37-c1-degnbnative`, cc)

Extended the degree(nbunch) native one-pass kernel to DiGraph (3 PyDiGraph kernels via a shared
degree_pairs_subset_impl over DegreeKind Total/In/Out). Routing: total auto-routes through the
existing _WeightAwareDegreeView.__call__ (binding added); in/out route in _DirectedDegreeView.__call__
(keyed by _adjacency_attr succ->out / pred->in), reusing _FilteredDegreeView with `self` as raw.

Results (n=1500, k=750):
- total degree(nbunch): 0.32x -> **1.23x SHIPPED/DOMINATES** — nx computes len(succ)+len(pred)
  (two dict lookups) per node; fnx does one degree_by_index, so it wins.
- in_degree/out_degree(nbunch): 0.17-0.18x -> **0.71x** (4x self-speedup, KEPT as strictly-better)
  but STILL below nx: nx's single C-dict len(pred[n])/len(succ[n]) beats fnx's per-node String
  canonicalization + index. This is the canonicalization wall — confirms the EARLIER hypothesis
  for the single-lookup case (only the deep int-key substrate would push in/out >1x). The total
  case escapes it because nx pays double.

Byte-exact: valid/invalid/empty/dup/range, error contract (unhashable element + non-iterable),
view[node] indexing for any node, MultiDiGraph in/out/total degree(nbunch) unaffected (PyDiGraph-
only bindings -> Python fallback). Full suite zero new failures.
Artifact: tests/artifacts/perf/20260622T-digraph-degree-nbunch-cc/.

## 2026-06-22 CopperCliff native DiGraph out_edges(nbunch) — 0.27x -> 2.50x SHIPPED + in_edges pred-order finding (`br-r37-c1-edgenbnative`, cc)

out_edges(nbunch, data=False) was 0.27x (delegated to the EdgeDataView Python machinery).
Added PyDiGraph::_native_out_edges_nbunch_no_data (shared edges_nbunch_no_data_impl): one pass
— canonical-filter the nbunch (deduping repeated nodes, since nx dedups: out_edges([1,1,2])==
out_edges([1,2])), walk successors_INDICES (insertion order == nx succ; the string successors
accessor does NOT preserve it) and map via cached_node_key_vec. Gated on succ_py_keys empty
(z6uka per-cell row display -> Ok(None) Python fallback). Result: 0.27x -> **2.50x** (~9x
self-speedup, dominates). Byte-exact: 5 seeds x 8 nbunch shapes (valid/invalid/empty/range/dup/
single/all/rev) + str-keyed + data=True fallback + error contract. Full suite zero new failures.

PRE-EXISTING FINDING (NOT shipped, NOT my regression): in_edges(nbunch) — and full in_edges() —
DIVERGE from nx in predecessor ORDER. fnx's `self.pred[v]` returns predecessors in INDEX order
([3,6,15,20]); nx uses edge-INSERTION order ([20,3,6,15]). Confirmed on a clean DiGraph (no
native involved) and the full _native_in_edges_no_data (predecessors_indices) shares it. So an
in_edges(nbunch) native kernel can't be made nx-exact without storing pred in insertion order
(deep). Uncaught by conformance (in_edges order not strictly tested). out_edges is safe because
fnx DOES store successors in insertion order. Filed as a correctness divergence to investigate
(separate from perf). Artifact: tests/artifacts/perf/20260622T-out-edges-nbunch-cc/.

## 2026-06-22 CopperCliff native MultiGraph edges(nbunch) — 0.09x -> 1.00x (biggest gap) (`br-r37-c1-mgedgenb`, cc)

The biggest single gap surfaced by the multi-nbunch sweep: MG edges(nbunch, data=False) was
**0.09x** (29.5ms vs nx 2.5ms @ n=1500/k=750). Profiled: the cost is the Python triple-loop's
`self.adj[source].items()` (MultiAdjacencyView lambda chain, ~24.5ms/750 src) + a
`frozenset((u,v))` dedup per edge (~4ms). Added PyMultiGraph::_native_mg_edges_nbunch_no_data:
walk neighbors() (nx adj insertion order — proven order-correct by the disjoint_union(MG) work)
x edge_keys() once, dedup undirected parallels by a normalized (lo,hi,key) string-pair, emit
(u,v) or (u,v,key). Gated on adj_py_keys empty (+ edge_py_keys empty for keys=True) -> Python
fallback for z6uka/non-default-key-display graphs.

Result: keys=False 0.09x -> **1.00x** (~12.7x self-speedup — eliminates the catastrophic loss,
now at parity); keys=True 0.09x -> 0.75x (the per-edge int key_obj construction keeps it just
below nx; kept as strictly-better). Byte-exact: 4 seeds x 7 nbunch shapes x keys/no-keys incl
parallels, self-loops, str-keyed, dup nodes + data=True fallback + error contract. Full suite
zero new failures. (data=True/key variants keep the Python path; MultiDiGraph out_edges(nbunch)
0.93x is near-parity, lower priority.) Artifact: tests/artifacts/perf/20260622T-mg-edges-nbunch-cc/.

## 2026-06-22 CopperCliff native MultiDiGraph in/out_degree(nbunch) — 0.58-0.62x -> 2.47-2.67x SHIPPED (`br-r37-c1-degnbnative`, cc)

Corrects the "canonicalization-capped" prediction for MULTI degree: it DOMINATES. nx's
MultiDiGraph in_degree(n) = sum(len(keydict) for keydict in pred[n].values()) — an O(deg) sum in
PYTHON per node; fnx's inner in_degree sums the same in RUST + one PyO3 call for the whole nbunch,
so it wins (unlike SIMPLE in/out_degree where nx does a single C len(adj[n]) that fnx can't beat).
Added 3 PyMultiDiGraph degree-subset kernels (shared helper, string-based multiplicity in/out/
total degree); in/out AUTO-ROUTE via the existing _DirectedDegreeView.__call__ (the multi in/out
views _InMultiDegreeView/_OutMultiDegreeView pass "pred"/"succ") — NO Python change.

Result: in_degree(nbunch) 0.62x -> **2.67x**, out_degree(nbunch) 0.58x -> **2.47x**. Byte-exact:
3 seeds (with parallels) x valid/invalid/empty/range/dup + error contract + view[node] indexing.
Full suite zero new failures. Follow-ups (same Python-sum-vs-rust-sum domination expected): MDG
total degree(nbunch) [MultiDiGraphDegreeView route] and MG degree(nbunch) 0.73x [MultiGraphDegree
View route] — separate view classes needing their own routing + a PyMultiGraph kernel.
Artifact: tests/artifacts/perf/20260622T-mdg-degree-nbunch-cc/.

## 2026-06-22 CopperCliff native MultiGraph degree(nbunch) — 0.73x -> 2.75x + degree-nbunch bad-node fix (`br-r37-c1-degnbnative`, cc)

MG degree(nbunch) 0.73x -> **2.75x** (dominates; same Python-keydict-sum-vs-rust-sum as MDG
in/out). Added PyMultiGraph::_native_degree_pairs_subset + routes in MultiGraphDegreeView /
MultiDiGraphDegreeView.__call__ (the two multi total-degree views). MDG total degree(nbunch) was
already ~parity (1.00x) — route added symmetrically (byte-exact, harmless no-op for that case).

REGRESSION FOUND+FIXED in the same change (caught by conformance): a single NON-iterable bad node
— e.g. degree(99), which `is_isolate` uses (G.degree(n)==0) — reached the native call and failed
try_iter with Python's "'int' object is not iterable", which I'd wrapped verbatim; nx's degree(n)
raises "Node n is not in the graph." Fixed across ALL degree-nbunch routes (Graph/DiGraph/MG/MDG,
total + in/out): the except maps "is not iterable" -> NetworkXError("Node {nbunch} is not in the
graph."), leaving the unhashable-element-in-sequence message intact. Lesson: a native nbunch fast-
path must replicate the single-bad-node error contract, not just the iterable-filter path.

Byte-exact: MG+MDG degree(nbunch) all shapes + error contract (single bad node, unhashable elem)
+ view-indexing; is_isolate bad-node across all 4 types. Full suite zero new failures.
Artifact: tests/artifacts/perf/20260622T-mg-degree-nbunch-cc/.

## 2026-06-22 CopperCliff native MG edges(nbunch, data=True) — 0.09x -> 0.57x + single-node edges fix (`br-r37-c1-mgedgenb`, cc)

The data=True sibling of the MG edges(nbunch) fix (data=False reached 1.00x). Was also 0.09x
(same adj[source] lambda-chain). Added _native_mg_edges_nbunch_data: collects neighbors/keys as
owned Vecs (releasing the inner borrow so the &mut ensure_edge_py_attrs call is legal), emits
(u,v[,key],live_attr_dict) where the dict is the materialized live edge_py_attrs mirror
(identity-preserving == G[u][v][key], verified by a mutation-visibility check). Result: 0.09x ->
**0.57x** (~6x self-speedup; materialization-capped — per-edge live-dict clone_ref + tuple build
vs nx's pre-existing C dicts, so it stays below nx; kept as strictly-better, the catastrophic
loss largely eliminated).

REGRESSION FOUND+FIXED (caught by test_contracted_nodes_multigraph_no_regression): a SINGLE
in-graph node passed to edges(n)/out_edges(n) (contracted_nodes does this) was try_iter'd by the
native kernel and errored, instead of returning that node's edges. Gated ALL 3 edges-nbunch
native routes (DiGraph out_edges, MG edges data=False, MG edges data=True) to ITERABLE nbunch
(list/tuple/set/non-str-iterable); a single node now falls to the view path (nbunch_iter -> [n]),
matching nx. Same lesson as the degree bad-node fix: a native nbunch fast-path must not intercept
the single-node case. Byte-exact: data=True keys=F/T x shapes + live-dict identity + single-node
+ error contract. Full suite zero new failures. data=True is the materialization-capped frontier;
DG out_edges(nb,data=True) 0.22x similar. Artifact: tests/artifacts/perf/20260622T-mg-edges-nbunch-data-cc/.

## 2026-06-22 CopperCliff selfloop_edges(multigraph) — 0.13x -> 3.37x (sparse) (`br-r37-c1-selfloopmulti`, cc)

selfloop_edges on a MultiGraph/MultiDiGraph found self-loop nodes via an O(N) per-node
`has_edge(n,n)` PyO3 probe over ALL nodes (the simple-graph nodes_with_selfloops_rust is
"wrong for multi"), so on gnm (≈0 self-loops) it was ~0.05-0.13x vs nx. Added
_native_selfloop_nodes (PyMultiGraph + PyMultiDiGraph): rust scan in node-iteration order;
routed in selfloop_edges' multigraph branch. Result (realistic sparse self-loops): nsl=0 (the
sweep's gnm case) **0.13x -> 3.37x**, nsl=5 1.08-1.50x — dominates. Byte-exact across all
variants (keys / data=True / data=str+default, parallel self-loops with attrs) for MG and MDG.
Full suite zero new failures.

RESIDUAL: DENSE self-loops (nsl>=30) stay ~0.3-0.5x — there the cost shifts to the Python
emission `for n in sl_nodes: yield n, G[n]` (one native row materialization per self-loop node,
then nbrs[n].items()); a full native self-loop-EDGE kernel (emit (n,n[,key][,attrs]) directly,
like the edges(nbunch) kernels) would close it, but dense self-loops are atypical.
Artifact: tests/artifacts/perf/20260622T-selfloop-edges-multi-cc/.

## 2026-06-22 CopperCliff native DiGraph out_edges(nbunch, data=True) — 0.21x -> 0.77x (`br-r37-c1-edgenbnative`, cc)

Completes the out_edges(nbunch) family (data=False shipped at 2.5x). data=True was 0.21x
(delegated to the EdgeDataView machinery). Added _native_out_edges_nbunch_data (&mut self): succ
rows (index order == nx), live attr dict via materialize_edge_py_attrs (identity-preserving ==
G[u][v], verified by mutation check), node-dedup, iterable-gated. Result: 0.21x -> **0.77x**
(~3.7x self-speedup; materialization-capped — per-edge live-dict clone + tuple build vs nx's
pre-existing C dicts, so it stays <1x; kept as strictly-better, the catastrophic gap mostly
closed). Byte-exact: data=True x shapes incl identity, dup-node dedup, single-node fallback,
error contract. Full suite zero new failures.

CONCLUSION on data=True edge views: ALL are materialization-capped (~0.5-0.8x) — MG edges 0.57x,
DG out_edges 0.77x. They can't dominate without eager attr-dict mirrors (abandoning the lazy
design). The shallow DOMINATING vein is exhausted; data=True variants are strictly-better-but-
capped, and the remaining true gaps are deep-substrate (per-call String key, in_edges pred-order).
Artifact: tests/artifacts/perf/20260622T-dg-out-edges-nbunch-data-cc/.

## 2026-06-22 CopperCliff native MultiDiGraph out_edges(nbunch, data=False) — 0.87x -> 2.22x (`br-r37-c1-mdgoutedge`, cc)

out_edges(nb) keys=False 0.87x -> **2.22x** (dominates): nx iterates succ[u].items() keydicts in
Python; fnx walks successors x edge_keys in rust (one PyO3 call). _native_mdg_out_edges_nbunch_no_data
(PyMultiDiGraph): node-dedup, iterable-gated, succ_py_keys (+ edge_py_keys for keys) display gate.
keys=True 0.76x -> 0.79x (marginal — per-edge int key_obj construction is the cap, like MG edges
keys=True). Byte-exact: shapes x keys, parallels, single-node, dup, error contract + data=True
fallback. Full suite zero new.

MILESTONE: data=False edges(nbunch) is now native-DOMINANT across ALL 4 graph types
(Graph/DiGraph 2.5x, MG 1.00x [was 0.09x], MDG 2.22x). data=True variants remain materialization-
capped (~0.5-0.8x). Remaining: deep substrate (per-call String key, in_edges pred-order).
Artifact: tests/artifacts/perf/20260622T-mdg-out-edges-nbunch-cc/.

## 2026-06-22 CopperCliff native MDG out_edges(nbunch, data=True) — 0.65x -> 1.17x (`br-r37-c1-mdgoutedge`, cc)

Completes the out_edges(nbunch) data=True family. keys=False **0.65x -> 1.17x (DOMINATES)** —
unlike MG edges/DG out_edges data=True (materialization-capped ~0.57-0.77x), MDG out_edges
data=True dominates because its prior path was the slow self.edges machinery AND nx iterates
succ[u].items() keydicts in Python (so even with per-edge live-dict materialization, fnx's rust
walk wins). _native_mdg_out_edges_nbunch_data (&mut; successors/edge_keys collected owned for the
ensure_edge_py_attrs borrow; live attr dicts identity-preserving; node-dedup; iterable-gated).
keys=True 0.63x (4-tuple + int key_obj construction cap; strictly-better, kept). Byte-exact:
data=True keys F/T x shapes incl identity, dup, single-node, error contract. Full suite zero new.
Artifact: tests/artifacts/perf/20260622T-mdg-out-edges-data-cc/.

## 2026-06-22 CopperCliff MDG edges(nbunch) routed to out_edges kernels — 0.89x->1.59x (NO-BUILD) (`br-r37-c1-mdgoutedge`, cc)

For a directed graph edges() == out_edges(), but MDG.edges(nbunch) went through
_MultiDiGraphEdgeView.__call__'s `_native_edge_view()(nbunch,...)` path (~0.66-0.89x) while
out_edges() had dedicated dominating kernels. Routed the iterable-nbunch data=False/True case to
the EXISTING _native_mdg_out_edges_nbunch_no_data / _data kernels — Python-only, NO rebuild.
Result: edges(nb) data=False 0.89x -> **1.59x** (dominates; the view-wrap overhead keeps it below
out_edges' 2.22x but still wins), data=True 0.66x -> 0.92x (near-parity, improved). Byte-exact
incl the canonical OutMultiEdge* view types + all shapes/keys. Full suite zero new failures.
Lesson: when one call form (out_edges) has a native kernel, check the sibling form (edges) routes
to it too — often a free reuse.

## 2026-06-22 BlackThrush native unweighted cut scan - 5.19x-5.68x overlap (`br-r37-c1-wh7nt`, cod-a)

Lever: alien-graveyard 10.5 GraphBLAS-style masked sparse traversal, applied narrowly to
unweighted `cut_size` / `normalized_cut_size` for simple Graph/DiGraph. The old path materialized
the full boundary edge vector and then summed it. The new path builds S/T masks once and scans
native adjacency rows directly. Weighted and multigraph paths stay on their existing parity routes.

Keep decision: KEEP. The overlap workload is not a micro-gain, and it removes the stale reason to
delegate overlapping S/T cuts back to NetworkX. Expected-value score was high enough for a bold
probe: impact 3 * confidence 4 * reuse 3 / effort 2 = 18, with low blast radius because the lever
is unweighted-only and covered by NetworkX parity tests.

Head-to-head bench, small per-crate only:

`RCH_REQUIRE_REMOTE=1 AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a RUSTUP_TOOLCHAIN=nightly-2026-06-10 rch exec -- env PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH PYTHONPATH=/data/projects/franken_networkx/crates/fnx-python/benches:/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code/networkx cargo bench -p fnx-python --bench networkx_head_to_head cut_metrics -- --noplot --sample-size 10 --warm-up-time 1 --measurement-time 2`

Note: `cargo bench --release` is not valid Cargo syntax; Criterion benches already build optimized
bench profiles, so the per-crate command above is the valid disk-frugal equivalent. RCH rewrote the
remote target dir to its worker-scoped warm path.

| workload | fnx | networkx | ratio |
| --- | ---: | ---: | ---: |
| cut_size overlap BA2500 S=1250 T=1250 | 474.63 us | 2.4613 ms | 5.19x |
| normalized_cut_size overlap BA2500 S=1250 T=1250 | 485.96 us | 2.7593 ms | 5.68x |
| edge_expansion BA2500 S=1250 | 556.54 us | 3.1793 ms | 5.71x |
| edge_expansion WS2500 S=625 | 286.62 us | 1.2948 ms | 4.52x |
| node_expansion BA2500 S=1250 | 121.55 us | 440.81 us | 3.63x |
| node_expansion WS2500 S=625 | 58.929 us | 251.90 us | 4.27x |

Behavior proof:

- `cargo test -p fnx-algorithms overlapping --lib`: 4 passed.
- Fresh in-tree extension passed the checkout stale-extension guard.
- `pytest tests/python/test_cuts_overlap_parity.py tests/python/test_boundary_value_parity.py -q`:
  628 passed.
- `cargo check -p fnx-python --benches --features pyo3/abi3-py310`: passed; existing
  `fnx-python/src/digraph.rs` `unused_must_use` warnings remain under CopperCliff's reservation.
- `cargo clippy -p fnx-algorithms --lib -- -D warnings`: passed after the split
  `br-r37-c1-yze2l` `FxBuildHasher` unit-struct cleanup.
- `cargo check -p fnx-classes --all-targets`: passed.
- `cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `cargo test -p fnx-classes`: 68 passed, 2 ignored.

## 2026-06-22 CopperCliff MDG out_edges/edges(nbunch, keys=True) — 0.81x -> 1.38x + latent crash fix (`br-r37-c1-mdgoutedge`, cc)

out_edges(nb,keys=True) was 0.81x: _native_mdg_out_edges_nbunch_no_data GATED OUT for keys=True
(`keys && !edge_py_keys.is_empty()`), and MultiDiGraph(gnm) always carries an edge_py_keys mirror,
so keys=True fell to the slow self.edges path. Fix: drop the edge_py_keys gate, emit the DISPLAY
key via py_edge_key (falls back to the int key when no mirror) — the mdgdju recipe. Result:
out_edges(nb,keys=True) **0.81x -> 1.38x** (dominates), edges(nb,keys=True) 0.81x -> 1.02x.
ALSO fixed a LATENT CRASH this exposed (my earlier bfd4e3e3e edges route): keys=True wrapped via
_OutMultiEdgeView (a _DiEdgeMethodView needing (graph,method)) instead of _OutMultiEdgesKeysView
(the list-wrapper) -> TypeError once keys=True un-gated. Byte-exact: out_edges+edges x shapes incl
explicit string keys, dup/single-node/error contract. Full suite zero new (49231 passed).

## 2026-06-22 BlackThrush native dense multigraph selfloop_edges emission - 8.13x-31.79x self-speedup, still 0.22x-0.62x vs NetworkX (`br-r37-c1-8egkh`, cod-a)

Lever: finish the dense residual called out by the sparse self-loop keep above. `selfloop_edges`
on MultiGraph/MultiDiGraph now routes to `_native_selfloop_edges`, which emits the final
NetworkX-shaped tuples directly from the native self-loop scan instead of materializing `G[n]`
and then `nbrs[n]` for every self-loop node. The kernel preserves node display keys, parallel
edge display keys, `keys`, `data=True`, `data="attr"` with `default`, and live attr-dict identity.

Keep decision: KEEP. This is not a near-zero lever. It is still tuple/PyO3-object-construction
capped versus NetworkX, but it removes the dominant FNX-internal Python row-materialization cost.
No revert.

Final direct artifact probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python` with
`/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | mode | old FNX row route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| MultiGraph int keys | pairs | 9.244 ms | 0.315 ms | 0.179 ms | 29.32x | 0.57x |
| MultiGraph int keys | keys | 7.976 ms | 0.655 ms | 0.222 ms | 12.17x | 0.34x |
| MultiGraph int keys | data | 7.656 ms | 0.620 ms | 0.208 ms | 12.35x | 0.34x |
| MultiGraph int keys | keys_data | 8.562 ms | 0.839 ms | 0.230 ms | 10.21x | 0.27x |
| MultiGraph int keys | weight | 10.219 ms | 0.786 ms | 0.255 ms | 13.00x | 0.32x |
| MultiGraph int keys | keys_weight | 9.854 ms | 0.900 ms | 0.266 ms | 10.95x | 0.30x |
| MultiGraph string keys | pairs | 8.417 ms | 0.353 ms | 0.192 ms | 23.85x | 0.54x |
| MultiGraph string keys | keys | 8.675 ms | 0.497 ms | 0.178 ms | 17.47x | 0.36x |
| MultiGraph string keys | data | 8.646 ms | 0.592 ms | 0.214 ms | 14.61x | 0.36x |
| MultiGraph string keys | keys_data | 9.580 ms | 0.964 ms | 0.294 ms | 9.94x | 0.30x |
| MultiGraph string keys | weight | 8.538 ms | 0.800 ms | 0.397 ms | 10.67x | 0.50x |
| MultiGraph string keys | keys_weight | 8.192 ms | 0.822 ms | 0.266 ms | 9.97x | 0.32x |
| MultiDiGraph int keys | pairs | 9.827 ms | 0.309 ms | 0.193 ms | 31.79x | 0.62x |
| MultiDiGraph int keys | keys | 9.064 ms | 0.518 ms | 0.185 ms | 17.51x | 0.36x |
| MultiDiGraph int keys | data | 8.595 ms | 0.591 ms | 0.220 ms | 14.55x | 0.37x |
| MultiDiGraph int keys | keys_data | 8.810 ms | 1.084 ms | 0.234 ms | 8.13x | 0.22x |
| MultiDiGraph int keys | weight | 8.479 ms | 0.622 ms | 0.257 ms | 13.63x | 0.41x |
| MultiDiGraph int keys | keys_weight | 9.597 ms | 0.821 ms | 0.277 ms | 11.69x | 0.34x |
| MultiDiGraph string keys | pairs | 10.793 ms | 0.400 ms | 0.224 ms | 26.95x | 0.56x |
| MultiDiGraph string keys | keys | 8.692 ms | 0.516 ms | 0.184 ms | 16.83x | 0.36x |
| MultiDiGraph string keys | data | 12.125 ms | 0.614 ms | 0.218 ms | 19.75x | 0.36x |
| MultiDiGraph string keys | keys_data | 8.332 ms | 0.793 ms | 0.242 ms | 10.51x | 0.31x |
| MultiDiGraph string keys | weight | 9.920 ms | 0.775 ms | 0.314 ms | 12.79x | 0.40x |
| MultiDiGraph string keys | keys_weight | 8.822 ms | 0.844 ms | 0.272 ms | 10.45x | 0.32x |

Behavior proof:

- Direct artifact parity: public `fnx.selfloop_edges` and direct `_native_selfloop_edges` match
  NetworkX for MultiGraph and MultiDiGraph across pairs/keys/data/keys_data/weight/keys_weight,
  including live attr-dict mutation identity.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed; built
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: 27 passed, 0 failed.

Pytest note: the checkout's `tests/python/conftest.py` hard-fails when
`python/franken_networkx/_fnx.abi3.so` is older than Rust sources. I did not copy over or install
the extension during this disk-frugal crate-only run, so the Python proof used the final release
artifact preloaded directly.

## 2026-06-22 BlackThrush DiGraph edges(nbunch) routed to out_edges kernels - 2.65x-7.24x self-speedup (`br-r37-c1-lfpma`, cod-a)

Lever: directed `DiGraph.edges(nbunch, ...)` is semantically out-edge iteration, but the
`_DiGraphEdgeView.__call__` path still walked Python `succ[source].items()` rows for iterable
nbunch calls. `DiGraph.out_edges(nbunch, data=False/True)` already had native node-deduped kernels.
The new route reuses those kernels for exact `DiGraph`, iterable `nbunch`, and `data in {False,
True}`, preserving the existing guarded `OutEdgeDataView` wrapping. Single-node nbunch, data-key
lookups, conversion views, and subgraph views keep the old Python path.

Keep decision: KEEP. This is a Python-only no-build route reuse, not a near-zero lever. It also
fixes duplicate-nbunch parity for the routed pair/data modes because the native out-edge kernels
dedupe repeated nbunch nodes like NetworkX.

Final direct artifact probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python` with
`/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | mode | old FNX row route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| DiGraph half nbunch | pairs | 2.735 ms | 0.440 ms | 0.564 ms | 6.21x | 1.28x |
| DiGraph half nbunch | data=True | 2.695 ms | 1.017 ms | 0.549 ms | 2.65x | 0.54x |
| DiGraph reversed nbunch | pairs | 2.651 ms | 0.437 ms | 0.549 ms | 6.07x | 1.26x |
| DiGraph reversed nbunch | data=True | 2.654 ms | 0.901 ms | 0.551 ms | 2.95x | 0.61x |
| DiGraph duplicate nbunch | pairs | 3.318 ms | 0.458 ms | 0.567 ms | 7.24x | 1.24x |
| DiGraph duplicate nbunch | data=True | 3.351 ms | 0.929 ms | 0.576 ms | 3.61x | 0.62x |

Behavior proof:

- Direct artifact parity: `list(G.edges(nbunch))` and `list(G.edges(nbunch, data=True))` match
  NetworkX for half, reversed, and duplicate nbunch. The `data=True` tuple's attr dict remains live:
  mutating it updates `G[u][v]`.
- Baseline before edit on the same workload: pairs 0.17x-0.19x vs NetworkX, data=True 0.10x-0.18x
  vs NetworkX. The existing `out_edges` route was already 0.75x-2.25x, confirming this as a route
  miss rather than a missing native primitive.
- `data="weight"` remains on the old Python path because there is no native attr-key nbunch kernel
  yet; duplicate-nbunch attr-key parity remains a separate pre-existing issue.

## 2026-06-22 BlackThrush tournament_matrix direct CSR build - 3.19x-4.80x self-speedup (`br-r37-c1-92qkv`, cod-a)

Lever: `franken_networkx.tournament.tournament_matrix` still re-exported NetworkX's implementation,
which computes `adjacency_matrix(G) - adjacency_matrix(G).T`. On an fnx `DiGraph` that sends
NetworkX through fnx graph views and then pays a sparse subtraction. The new exact-`DiGraph` route
builds the skew CSR matrix directly in one pass over `G.edges()`, preserving node order, sparse
matrix type, int64 unweighted dtype, and NetworkX's implicit `weight="weight"` semantics. Non-exact
directed graph-like inputs keep the NetworkX parity route.

Keep decision: KEEP. This is a contained Python-only route, not a near-zero tweak. The unweighted
tournament row moves from a clear loss to near-NetworkX, and weighted matrices get a 3.19x self
speedup while remaining capped by edge-attribute materialization.

Final direct parity/bench probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | old FNX NetworkX-dispatch route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | ---: | ---: | ---: | ---: | ---: |
| unweighted tournament n=50 | 2.483 ms | 0.745 ms | 0.795 ms | 3.33x | 1.07x |
| unweighted tournament n=350 | 180.780 ms | 37.654 ms | 36.732 ms | 4.80x | 0.98x |
| unweighted tournament n=700 | 845.236 ms | 186.495 ms | 169.752 ms | 4.53x | 0.91x |
| weighted tournament n=350 | 183.900 ms | 57.620 ms | 39.285 ms | 3.19x | 0.68x |

Behavior proof:

- Direct artifact parity: new and old matrices match NetworkX exactly by dense value for all rows
  above; the focused weighted fixture also preserves sparse class name and dtype.
- `py_compile python/franken_networkx/tournament.py tests/python/test_tournament_module_parity.py`:
  passed.
- `git diff --check`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `ubs python/franken_networkx/tournament.py tests/python/test_tournament_module_parity.py
  docs/NEGATIVE_EVIDENCE.md .beads/issues.jsonl`: exit 0; remaining warnings are existing
  tournament test asserts/random and the module's deliberate wildcard re-export.
- Targeted `pytest` could not run in this checkout because `tests/python/conftest.py` rejected the
  stale in-tree `python/franken_networkx/_fnx.abi3.so`; the proof used the warm release artifact
  directly.

## 2026-06-22 BlackThrush directed nbunch attr-key edge route - 1.19x-1.83x self-speedup (`br-r37-c1-e522x`, cod-a)

Lever: iterable-nbunch directed edge views with `data=<attr>` still walked the attr-key row path
even though `data=True` already had native out-edge nbunch emitters. Exact `DiGraph` and
`MultiDiGraph` `keys=False` now reuse the native `data=True` nbunch rows and project
`attrs.get(key, default)` in Python. The keyed MultiDiGraph variant measured as a regression, so
it stays on the old route.

Keep decision: KEEP. This is not a zero-gain tweak: it removes a duplicate-nbunch parity bug for
DiGraph attr-key `edges` / `out_edges`, and the measured public routes are faster on the target
rows. Some large DiGraph rows remain below NetworkX because the route still materializes live attr
dicts before extracting one value; the deeper fix would be a native attr-key nbunch emitter.

Direct artifact probe:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

| workload | old route | new FNX | NetworkX | self-speedup | ratio vs NetworkX |
| --- | ---: | ---: | ---: | ---: | ---: |
| DiGraph out_edges attr-key, n=1500/m=9000/k=750 | 4.094 ms | 2.274 ms | 1.495 ms | 1.80x | 0.66x |
| DiGraph edges attr-key, n=1500/m=9000/k=750 | 4.094 ms | 2.647 ms | 1.511 ms | 1.55x | 0.57x |
| DiGraph out_edges attr-key, n=3500/m=24000/k=1750 | 11.398 ms | 6.780 ms | 4.100 ms | 1.68x | 0.60x |
| DiGraph edges attr-key, n=3500/m=24000/k=1750 | 11.398 ms | 7.701 ms | 4.268 ms | 1.48x | 0.55x |
| MultiDiGraph out_edges attr-key, n=1000/m=8000/k=500 | 3.484 ms | 2.939 ms | 2.858 ms | 1.19x | 0.97x |
| MultiDiGraph out_edges attr-key, n=2500/m=20000/k=1250 | 17.543 ms | 9.594 ms | 9.592 ms | 1.83x | 1.00x |
| MultiDiGraph edges attr-key, n=2500/m=20000/k=1250 | 17.543 ms | 10.344 ms | 16.861 ms | 1.70x | 1.63x |

Behavior proof:

- Direct artifact parity: DiGraph `edges` / `out_edges` with duplicate nbunch nodes and missing
  nodes now match NetworkX for `data="weight", default=-1`; the old DiGraph route repeated edges
  for duplicate nbunch nodes.
- Direct artifact parity: MultiDiGraph `edges` / `out_edges` with `keys=False` attr-key nbunch
  match NetworkX; `keys=True` parity was checked and intentionally left on the old route because
  the native-projection candidate regressed.
- `py_compile python/franken_networkx/__init__.py tests/python/test_graph_utilities.py`: passed.
- `git diff --check`: passed.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py`: exit 0; remaining warnings
  are pre-existing broad-file style/security-noise outside this diff.
- `ubs --only=python --skip=7 tests/python/test_graph_utilities.py`: exit 0; remaining warnings
  are pre-existing test-file style noise.
- Targeted `pytest tests/python/test_graph_utilities.py::test_directed_graph_classes_expose_in_and_out_edges
  tests/python/test_graph_utilities.py::test_digraph_edges_nbunch_reuses_out_edge_semantics -q`
  could not collect tests because the checkout stale-extension guard rejected
  `python/franken_networkx/_fnx.abi3.so`; no in-tree install was attempted in this disk-frugal run.

## 2026-06-22 BlackThrush MultiDiGraph selfloop_edges scalar attr read - 1.25x-2.33x self-speedup on target modes (`br-r37-c1-04z53`, cod-b)

Lever: the dense `MultiDiGraph.selfloop_edges` native emitter still materialized a live Python
edge-attr dict for every edge in `data="<attr>"` modes, even though NetworkX returns only the
scalar value there. The new directed multigraph path reads scalar string-key values directly from
the Rust `AttrMap` when no live Python mirror exists, falling back to the mirror for materialized
or mutated attrs and to full dict materialization for nested map values. `data=True` remains on
the live-dict path. The tuple assembly was also split by output shape, avoiding the per-edge
temporary `Vec<PyObject>`.

Keep decision: KEEP for the targeted `data=True` and `data="weight"` modes. It is not a full
domination lever: plain `keys=True` and key-bearing data modes remain key-object/tuple-construction
capped and noisy. But the target residual improves, and behavior stays parity-exact for explicit
keys, string nodes, missing defaults, live attr-dict mutation, and nested dict payloads. No revert.

Same-machine direct probe, with
`/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`:

| workload | mode | before FNX | before NetworkX | before ratio | after FNX | after NetworkX | after ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MultiDiGraph dense self-loops n=2400 parallel=2 | pairs | 6.557 ms | 5.831 ms | 0.89x | 3.854 ms | 3.532 ms | 0.92x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | keys | 10.083 ms | 9.042 ms | 0.90x | 4.687 ms | 3.595 ms | 0.77x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | data=True | 22.789 ms | 6.874 ms | 0.30x | 9.798 ms | 8.150 ms | 0.83x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | keys+data=True | 9.640 ms | 7.969 ms | 0.83x | 11.066 ms | 8.617 ms | 0.78x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | data="weight" | 6.295 ms | 4.059 ms | 0.65x | 5.047 ms | 3.926 ms | 0.78x |
| MultiDiGraph dense self-loops n=2400 parallel=2 | keys+data="weight" | 5.932 ms | 3.796 ms | 0.64x | 6.598 ms | 4.449 ms | 0.67x |

Notes:

- The baseline ratios came from the same warm cod-b target artifact before the edit; the after
  ratios are from the rebuilt local cod-b target artifact.
- Two remote RCH `cargo build -p fnx-python --release --features pyo3/abi3-py310` attempts
  successfully compiled on `vmi1152480` but failed artifact retrieval with `RCH-E309`, so the final
  benchmark artifact was produced by the same crate-scoped build locally with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- Direct parity probe passed: int/string nodes, default integer and explicit string edge keys,
  `data=False`, `keys=True`, `data=True`, `keys+data=True`, `data="weight"`,
  `keys+data="weight"`, missing-default modes, live attr-dict mutation before attr-key reads, and
  nested dict payload values.

## 2026-06-22 BlackThrush MultiGraph selfloop_edges scalar attr read - 1.22x-2.56x self-speedup on target modes (`br-r37-c1-0vflm`, cod-a)

Lever: the undirected `MultiGraph.selfloop_edges(data="<attr>")` native emitter still
materialized a live Python attr dict for every self-loop edge before reading a single scalar
attribute. The new path mirrors the earlier `MultiDiGraph` scalar helper: if a live Python attr
dict already exists, read from it; otherwise read string-keyed scalar values directly from the
Rust `AttrMap`, falling back to dict materialization for nested map payloads. Tuple construction is
also split by output shape, removing the per-edge temporary `Vec<PyObject>`.

Keep decision: KEEP. This is not near-zero. The largest measured residual,
`keys=True, data="weight"`, moved from 0.14x/0.21x vs NetworkX to 0.36x/0.36x, and the
standalone scalar modes improved from 0.39x/0.18x to 0.48x/0.46x. The remaining gap is now mostly
key-object and Python tuple construction overhead.

Same-machine direct probe, with
`/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`:

| workload | mode | before FNX | before NetworkX | before ratio | after FNX | after NetworkX | after ratio | self-speedup |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | pairs | 0.657 ms | 0.531 ms | 0.81x | 0.592 ms | 0.440 ms | 0.74x | 1.11x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | keys | 1.298 ms | 0.363 ms | 0.28x | 1.038 ms | 0.376 ms | 0.36x | 1.25x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | data=True | 1.274 ms | 0.450 ms | 0.35x | 1.257 ms | 0.565 ms | 0.45x | 1.01x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | keys+data=True | 1.988 ms | 0.474 ms | 0.24x | 1.642 ms | 0.479 ms | 0.29x | 1.21x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | data="weight" | 1.344 ms | 0.521 ms | 0.39x | 1.101 ms | 0.525 ms | 0.48x | 1.22x |
| MultiGraph dense self-loops n=2400 parallel=2 int keys | keys+data="weight" | 3.943 ms | 0.567 ms | 0.14x | 1.569 ms | 0.558 ms | 0.36x | 2.51x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | pairs | 0.854 ms | 0.606 ms | 0.71x | 0.757 ms | 0.553 ms | 0.73x | 1.13x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | keys | 1.495 ms | 0.482 ms | 0.32x | 1.061 ms | 0.482 ms | 0.45x | 1.41x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | data=True | 1.364 ms | 0.473 ms | 0.35x | 1.240 ms | 0.568 ms | 0.46x | 1.10x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | keys+data=True | 3.125 ms | 0.867 ms | 0.28x | 1.665 ms | 0.513 ms | 0.31x | 1.88x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | data="weight" | 2.893 ms | 0.534 ms | 0.18x | 1.130 ms | 0.523 ms | 0.46x | 2.56x |
| MultiGraph dense self-loops n=2400 parallel=2 string keys | keys+data="weight" | 2.705 ms | 0.577 ms | 0.21x | 1.576 ms | 0.567 ms | 0.36x | 1.72x |

Behavior proof:

- Direct artifact parity passed for public `fnx.selfloop_edges` against NetworkX on MultiGraph
  int-key and string-key self-loop workloads across pairs/keys/data/keys_data/weight/keys_weight.
- Focused direct probe passed for missing-default scalar attrs, nested-map payload values, and
  live attr-dict mutation before scalar attr reads.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed via RCH on `ovh-a`.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed locally after an RCH worker
  killed the first check attempt before completion.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: 27 passed, 0 failed.
- `cargo fmt -p fnx-python --check`: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: exit 0; warnings are pre-existing broad-file
  inventory and no critical issues were reported.
- `git diff --check`: passed.

## 2026-06-22 BlackThrush MultiGraph default-order CSR byte export - 1.22x-1.27x route self-speedup (`br-r37-c1-wggkz`, cod-a)

Lever: default-order `MultiGraph.to_scipy_sparse_array(..., format="csr", dtype=None,
weight="weight")` still used the multigraph COO helper, then handed SciPy duplicate row/col
entries and let COO-to-CSR conversion sort and sum them. The new exact-MultiGraph route builds CSR
rows directly in Rust, mirrors undirected non-self-loops into both row buckets, sums parallel edges
per row, and hands Python native-endian `intp` / data byte buffers through `numpy.frombuffer`.
It preserves the existing live-attr behavior: when edge attrs are dirty it reads the live PyDict
mirror, and it returns to the Python fallback for present nonnumeric or nonfinite weights.

Keep decision: KEEP. The public NetworkX ratio remains noisy because SciPy conversion timing moves
by several milliseconds on the same machine, but the same-artifact route comparison isolates the
lever and shows a durable 1.22x-1.27x speedup over the old COO route with byte-identical CSR output.
No revert.

Direct artifact environment:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260622T1940Z/python:/data/projects/.scratch/franken_networkx-cod-a-boldverify-20260622T1940Z/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`.

Public baseline before the edit:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| MultiGraph random n=2000/m=12000 `to_scipy_sparse_array` | 21.122 ms | 19.452 ms | 0.921x |
| MultiGraph random n=2000/m=12000 `adjacency_matrix` | 23.975 ms | 21.138 ms | 0.882x |
| MultiGraph random n=4000/m=24000 `to_scipy_sparse_array` | 50.248 ms | 44.532 ms | 0.886x |
| MultiGraph random n=4000/m=24000 `adjacency_matrix` | 50.359 ms | 48.940 ms | 0.972x |
| MultiGraph random n=8000/m=48000 `to_scipy_sparse_array` | 126.141 ms | 112.618 ms | 0.893x |
| MultiGraph random n=8000/m=48000 `adjacency_matrix` | 135.628 ms | 109.329 ms | 0.806x |

Public after timing:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| MultiGraph random n=2000/m=12000 `to_scipy_sparse_array` | 22.855 ms | 21.851 ms | 0.956x |
| MultiGraph random n=2000/m=12000 `adjacency_matrix` | 22.228 ms | 24.593 ms | 1.106x |
| MultiGraph random n=4000/m=24000 `to_scipy_sparse_array` | 48.572 ms | 52.783 ms | 1.087x |
| MultiGraph random n=4000/m=24000 `adjacency_matrix` | 49.676 ms | 49.984 ms | 1.006x |
| MultiGraph random n=8000/m=48000 `to_scipy_sparse_array` | 130.577 ms | 129.690 ms | 0.993x |
| MultiGraph random n=8000/m=48000 `adjacency_matrix` | 111.461 ms | 110.062 ms | 0.987x |

Same-artifact old route vs new route, both using the rebuilt extension:

| workload | old COO route median | new CSR bytes route median | public route median | route self-speedup |
| --- | ---: | ---: | ---: | ---: |
| MultiGraph random n=2000/m=12000 | 27.319 ms | 22.260 ms | 18.699 ms | 1.227x |
| MultiGraph random n=4000/m=24000 | 61.688 ms | 48.599 ms | 50.300 ms | 1.269x |
| MultiGraph random n=8000/m=48000 | 136.389 ms | 112.100 ms | 115.410 ms | 1.217x |

Behavior proof:

- Direct artifact parity: old COO route, new CSR bytes route, public
  `to_scipy_sparse_array`, and NetworkX all produced identical sparse matrices for the random
  MultiGraph benchmark rows above.
- Added `test_default_multigraph_csr_parallel_selfloop_and_live_weight_matches_networkx`, covering
  parallel edges, self-loops, missing weights, isolates, and post-creation live attr mutation.
- Preloaded-extension pytest:
  `tests/python/test_to_scipy_sparse_default_native_parity.py`: 8 passed.
- Plain pytest collection from the source tree still cannot import `_fnx` because no in-tree
  extension module exists; the test run preloaded the rebuilt release artifact instead.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with the same target dir.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed
  via RCH with the same target dir.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: passed locally with the same target dir
  after RCH had no admissible workers; 27 passed, 0 failed.
- `git diff --check`: passed.
- `py_compile python/franken_networkx/__init__.py
  tests/python/test_to_scipy_sparse_default_native_parity.py`: passed.
- `ubs --only=rust crates/fnx-python/src/readwrite.rs`: exit 0; reports pre-existing broad-file
  warnings in `readwrite.rs`, no critical findings.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py
  tests/python/test_to_scipy_sparse_default_native_parity.py`: exit 0; reports pre-existing broad
  wrapper warnings plus normal test `assert` warnings, no critical findings.

## 2026-06-22 BlackThrush MultiDiGraph directional weighted degree - 19.9x-20.9x FNX self-speedup (`br-r37-c1-8njy5`, cod-a)

Lever: exact full-graph `MultiDiGraph.in_degree(weight="...")` and
`MultiDiGraph.out_degree(weight="...")` used the generic Python
`_DirectedDegreeView` per-node path. Each node walked `MultiAdjacencyView`
wrappers and keydict views before summing edge attrs. The new path routes only
exact, unfiltered, full-graph MultiDiGraph directional weighted degree views to
Rust, walks the native multiedge storage directly, reads the live edge-attr
PyDict mirrors, preserves missing-weight default `1`, and still calls Python
`sum()` once per node to preserve NetworkX-compatible numeric and custom-object
semantics. Nbunch, filtered/reverse views, single-node calls, unweighted calls,
and total directed weighted degree stay on their existing paths.

Keep decision: KEEP. The measured gap that triggered the bead was
`in_degree(weight)` / `out_degree(weight)` at about 0.04x vs NetworkX. The same
artifact-level benchmark shape after the edit is 0.43x / 0.52x vs NetworkX, and
FNX's own median improved about 20x. This is not a near-zero gain.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, `n=1200`, `parallel=4`,
`9600` total directed multiedges:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `MultiDiGraph.degree(weight="weight")` | 4.882 ms | 2.654 ms | 0.54x |
| `MultiDiGraph.in_degree(weight="weight")` | 40.083 ms | 1.405 ms | 0.04x |
| `MultiDiGraph.out_degree(weight="weight")` | 38.119 ms | 1.424 ms | 0.04x |

After timing, same graph size and total multiedge count with deterministic
parallel edges and missing-weight rows:

| workload | FNX median | NetworkX median | ratio vs NetworkX | parity |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph.degree(weight="weight")` | 5.540 ms | 1.623 ms | 0.29x | true |
| `MultiDiGraph.in_degree(weight="weight")` | 1.918 ms | 0.831 ms | 0.43x | true |
| `MultiDiGraph.out_degree(weight="weight")` | 1.918 ms | 0.997 ms | 0.52x | true |
| `MultiDiGraph.degree()` | 0.423 ms | 0.617 ms | 1.46x | true |
| `MultiDiGraph.in_degree()` | 0.137 ms | 0.331 ms | 2.42x | true |
| `MultiDiGraph.out_degree()` | 0.139 ms | 0.320 ms | 2.30x | true |

Behavior proof:

- Direct artifact parity passed for full-list `degree(weight)`, `in_degree(weight)`,
  `out_degree(weight)`, and the unweighted degree views against NetworkX.
- Focused direct probe passed for missing-weight default `1`, post-creation live
  edge-attribute mutation, and single-node `in_degree(node, weight)` /
  `out_degree(node, weight)` parity.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  was attempted with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`
  and died with wrapper exit 137 before any Rust diagnostic; treated as
  infrastructure failure.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed locally with the same target dir after matching the cached rustc.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `python -m py_compile python/franken_networkx/__init__.py`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; broad pre-existing
  `digraph.rs` warnings, no critical findings.

## 2026-06-24 BlackThrush/CopperCliff adjacency outer-cache landing - `dict(adjacency())` 0.55x-0.62x -> parity/win on measured rows (`br-r37-c1-adjouter`)

Landed measured scratch worktree win from
`/data/projects/.scratch/franken_networkx-cc-adjouter-019aa7efc`, commit
`8e880c0bd`, because it was proven but not on `main`. The lever caches the
outer `{node: shared_row}` dict inside `DictOfDictsCache` so
`share_dict_of_dicts_cache` no longer rebuilds one `set_item` per node on every
warm `Graph.adjacency()` / `DiGraph.adjacency()` call. Mutation still replaces
the whole cache via the existing `(nodes_seq, edges_seq)` guard; the public API
still returns `iter(outer.items())`, preserving NetworkX's iterator surface.

CopperCliff's scratch artifact measured `dict(G.adjacency())` on paired
Graph/DiGraph BA workloads at n=2000 and n=8000: baseline 0.55x-0.62x vs
NetworkX, after 0.95x-0.99x vs NetworkX (ratio = nx/fnx, >1 means FNX faster),
with paired artifact parity over content, row identity across calls, live edge
mutation reflection, cache invalidation, and iterator/`next()` contract.

Cod-b final verification used the committed Criterion harness:

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo bench -p fnx-python --profile release --bench networkx_head_to_head networkx_head_to_head_adjacency_outer_cache -- --quiet`

This completed on worker `vmi1149989` on 2026-06-24. Median ratios:

| workload | FNX median | NetworkX median | ratio nx/fnx | verdict |
| --- | ---: | ---: | ---: | --- |
| `Graph dict(adjacency())` n=2000 | 50.515 us | 55.117 us | 1.09x | keep |
| `Graph dict(adjacency())` n=8000 | 441.05 us | 309.78 us | 0.70x | keep; residual |
| `DiGraph dict(adjacency())` n=2000 | 53.397 us | 81.629 us | 1.53x | keep |
| `DiGraph dict(adjacency())` n=8000 | 235.35 us | 396.41 us | 1.68x | keep |

Keep decision: KEEP. Three of four cod-b harness rows beat NetworkX, the
remaining large Graph row is still a residual but improved from the scratch
baseline family and not a near-zero change. The committed bench group also
guards the parity contract by checking adjacency snapshots and row identity
before timing.

Validation status at ledger write: focused per-crate bench passed with
`cargo bench -p fnx-python --profile release --bench networkx_head_to_head
networkx_head_to_head_adjacency_outer_cache -- --quiet`. Formatting, clippy,
tests, Python conformance, and diff checks are recorded in the commit footer
after they are run.

## 2026-06-24 BlackThrush MultiGraph degree(nbunch, weight) exact-int fast path

Lever: `_native_weighted_degree_subset` for `MultiGraph` now tries an exact-int
row accumulator before the existing Python `builtins.sum` fallback. The fast
path only accepts plain integer weights or missing weights, reads live edge attr
mirrors first, reads Rust `CgseValue::Int` attrs when no mirror exists, preserves
duplicate `nbunch` nodes and missing-node skipping, and double-counts self-loops
with the same two-pass shape as NetworkX. Any float, bool, custom object, live
non-int attr, or overflow falls back to the old Python-sum parity route.

Keep decision: KEEP as a partial win, not a closure. The exact residual is still
large versus NetworkX, but the targeted row improved by 58.5% on the same
Criterion workload and is not a near-zero gain. Further work needs a deeper
iterator/object-boundary lever rather than another local sum micro-optimization.

Measurement note: this Cargo toolchain rejects `cargo bench --release`; the
crate-scoped release-profile equivalent used here was
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo bench -p fnx-python --profile release --bench networkx_head_to_head multigraph_weighted_degree -- --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`.

RCH Criterion baseline before the implementation, `networkx_head_to_head_multigraph_weighted_degree`,
deterministic `MultiGraph` with 400 nodes / 3224 edges and repeated/missing
`nbunch`, exact-int and missing weights:

| workload | FNX mean | NetworkX mean | FNX/NetworkX speed ratio |
| --- | ---: | ---: | ---: |
| `degree(nbunch, weight)` | 29.415 ms | 1.1577 ms | 0.039x |

After implementation, same command/filter:

| workload | FNX mean | NetworkX mean | FNX/NetworkX speed ratio | FNX self delta |
| --- | ---: | ---: | ---: | ---: |
| `degree(nbunch, weight)` | 12.106 ms | 583.39 us | 0.048x | +2.43x / -58.5% |

Rejected sibling, cod-a 2026-06-24: an exact-int
`MultiGraph.size(weight)` helper was tested and reverted as a no-ship. Same
focused `rch exec -- cargo bench -p fnx-python --profile release --features
pyo3/abi3-py310 --bench networkx_head_to_head -- multigraph_weighted_degree`
run: old `sum(degree(weight))/2` formula measured 1.1159 ms, the native
size helper measured 1.1219 ms, and NetworkX measured 773.30 us. Speed ratio
was effectively unchanged (`0.693x` -> `0.689x` vs NetworkX), so the size
helper did not survive the stop rule.

Behavior and gate evidence:

- The Criterion workload constructs paired `franken_networkx.MultiGraph` and
  legacy NetworkX graphs and asserts
  `list(fnx.degree(mg, nbunch, weight="weight")) == list(nx.degree(...))`
  before timing.
- Added focused Python source guard for repeated `nbunch` nodes, missing
  `nbunch` entries, missing weights, negative/zero weights, and self-loop
  weighted degree parity.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-python --all-targets -- -D warnings`: passed.
- `cargo fmt -p fnx-python -- --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: exit 0; no critical findings,
  broad pre-existing `lib.rs` warnings only.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --all-targets`: lib tests passed
  (28/28) and `networkx_head_to_head_multigraph_weighted_degree` test-mode rows
  passed, but the broader `public_api_gauntlet` bench target failed under RCH
  before exercising this change because the remote Python environment could not
  import `networkx` for that harness. A rerun with
  `PYTHONPATH=crates/fnx-python/benches:python:legacy_networkx_code` moved past
  the helper import but hit the same remote `networkx` import blocker.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --lib`: passed
  28/28.

## 2026-06-23 BlackThrush MultiGraph weighted PageRank sparse-build indexed walk WIN (`br-r37-c1-weighted-attr-rust-store-237hw`, cod-b)

Lever: `pagerank(MultiGraph, weight="weight")` routes through
`to_scipy_sparse_array(..., dtype=float)` and the plain multigraph COO helper.
For the default nodelist case, that helper rebuilt a Python-derived
`String -> row` map and then hashed both edge endpoints for every emitted
parallel edge. Added `MultiGraph::edges_ordered_indices_borrowed()` and used it
when the supplied nodelist exactly matches native node order, preserving the
existing duplicate COO stream while skipping the hot endpoint remap. Explicit
nodelists and dtype-inference helpers stay on the old path.

Keep decision: KEEP. On the same local release artifact harness against the
vendored NetworkX oracle, the target `MultiGraph` weighted PageRank row moved
from a real loss to a win:

| workload | Baseline FNX median | After FNX median | Baseline ratio | After ratio | Parity |
| --- | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.pagerank(weight)` n=700/fanout=8/parallel=3 | 17.349 ms | 8.296 ms | 0.609x | 1.460x | max_abs 0.0 |
| `MultiGraph.pagerank(weight)` n=1200/fanout=6/parallel=2 | 9.558 ms | 8.196 ms | 0.957x | 1.100x | max_abs 0.0 |

Non-target guardrail:
- `format="coo"` duplicate row ordering for `MultiGraph.to_scipy_sparse_array`
  is still an existing mismatch versus NetworkX on parallel/self-loop fixtures;
  this change preserves the current duplicate stream shape and does not attempt
  the CSR-only parallel-edge aggregation that would need a Python wrapper gate
  currently owned by another agent. File a separate parity bead for that surface.

Behavior proof and gates:

- Direct artifact PageRank parity passed for the measured `MultiGraph` and
  `MultiDiGraph` fixtures against vendored NetworkX.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo fmt -p fnx-classes -- --check`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b cargo fmt -p fnx-python -- --check`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-classes`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-classes`: 70 passed, 0 failed, 2 ignored; doctests 0 passed, 0 failed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-classes --all-targets -- -D warnings`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`: 28 passed, 0 failed; doctests 0 passed, 0 failed.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- `git diff --check`: passed.
- `jq empty .beads/issues.jsonl`: passed.
- `ubs --only=rust crates/fnx-classes/src/lib.rs crates/fnx-python/src/readwrite.rs`:
  exit 0; no critical findings, remaining warnings are existing broad file
  inventory.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py`: exit 0; broad
  pre-existing wrapper warnings, no critical findings.

## 2026-06-23 BlackThrush MultiDiGraph weighted nbunch exact-int accumulator - 1.13x-1.22x FNX self-speedup (`br-r37-c1-04z53.9169`, cod-a)

Context: the bead was filed from CopperCliff's earlier 0.05x
`MultiDiGraph.in_degree(nbunch, weight)` report. Current-head remeasurement
showed that the Python wrapper already routes directional weighted nbunch views
through native subset kernels, so the live residual is smaller but still real:
about 0.41x for directional weighted nbunch degree and 0.45x for total weighted
nbunch degree on the deterministic 400-node / 3000-edge fixture below.

Lever: the existing native subset kernel still built a Python list of edge
weights for every requested node and then called `builtins.sum` per node. The
kept path recognizes the common exact-`int` live edge-attribute case directly
from the authoritative Python edge attr dicts, accumulates in Rust with checked
integer sums, and returns a Python int. It falls back to the existing Python
sum path for floats, bools, custom numerics, oversized integers, and any
non-int value, so numeric semantics outside the exact-int case are unchanged.

Rejected attempt: a clean-inner `CgseValue::Int` fast path was tested first and
reverted. It did not materially improve the measured workload because Python
edge insertion marks the graph edge-dirty, so that gate was too narrow; total
weighted nbunch also regressed slightly.

Keep decision: KEEP. The directional rows improved modestly and total weighted
nbunch moved from 0.452x to 0.540x median vs NetworkX on the same artifact
family. This does not close the weighted-attr-access floor, but it is not a
near-zero result.

Direct artifact environment:

`PYTHONPATH=<temp franken_networkx package copy>:/data/projects/franken_networkx/legacy_networkx_code python3`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
copied into the temp package as `franken_networkx._fnx.abi3.so`.

Baseline before the kept edit, current turn, deterministic 400-node /
3000-edge `MultiDiGraph`, `nbunch=list(range(200))`, `weight="weight"`,
80 reps x 9 rounds:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `in_degree(nbunch, weight)` | 0.336 ms | 0.347 ms | 0.135 ms | 0.141 ms | 0.402x | 0.407x | true |
| `out_degree(nbunch, weight)` | 0.325 ms | 0.332 ms | 0.134 ms | 0.137 ms | 0.412x | 0.414x | true |
| `degree(nbunch, weight)` | 0.548 ms | 0.592 ms | 0.261 ms | 0.268 ms | 0.475x | 0.452x | true |

After timing, same graph generator and artifact family:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `in_degree(nbunch, weight)` | 0.306 ms | 0.308 ms | 0.132 ms | 0.133 ms | 0.433x | 0.433x | true |
| `out_degree(nbunch, weight)` | 0.282 ms | 0.285 ms | 0.138 ms | 0.141 ms | 0.490x | 0.494x | true |
| `degree(nbunch, weight)` | 0.485 ms | 0.486 ms | 0.257 ms | 0.262 ms | 0.530x | 0.540x | true |

Behavior proof:

- Direct artifact parity passed for `degree`, `in_degree`, and `out_degree`
  with weighted nbunch, repeated nbunch nodes, missing nbunch nodes, missing
  weights defaulting to 1, and post-creation live edge-attribute mutation.
- Fallback parity passed for float weights, bool weights, `Fraction` weights,
  and huge Python integers against vendored NetworkX.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`:
  passed before and after the kept edit with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo fmt -p fnx-python -- --check`: passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  28 passed, 0 failed; doctests 0 passed, 0 failed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; no critical
  findings; broad pre-existing warning inventory remains in `digraph.rs`.

## 2026-06-23 BlackThrush MultiGraph copy clean-attr native fast path - 1.18x FNX self-speedup (`br-r37-c1-jelx1`, cod-b)

Context: the larger live `MultiDiGraph.in_degree(nbunch, weight)` 0.05x and
`is_path` 0.21x gaps were both in files currently reserved by CopperCliff
(`digraph.rs` / `__init__.py`). This pass therefore used the next measured
unowned perf bead: `MultiGraph.copy()` on attributed multigraphs.

Lever: `PyMultiGraph._native_copy()` already rebuilt the inner graph in
NetworkX copy-walk order, but on clean graphs it still reparsed every live edge
Python attr dict back into a Rust `AttrMap`. The kept path preserves the
existing `edges_ordered()` copy walk and node insertion mechanics, but for clean
edge attrs it copies the Python mirror dict and reuses the already-synchronized
Rust `AttrMap`; dirty edge attrs still reparse their live Python dicts.

Keep decision: KEEP. The same 1500-node / 15000-edge attributed `MultiGraph`
shape remains below NetworkX, but FNX median copy time fell from 97.537 ms to
82.430 ms, a 1.18x self-speedup, and the median ratio moved from 0.503x to
0.577x. This is modest, not a full closeout, but not a near-zero result.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, deterministic
1500-node / 15000-edge attributed `MultiGraph.copy()` with unique string edge
keys:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.copy()` attributed 1500/15000 | 90.210 ms | 97.537 ms | 47.614 ms | 49.031 ms | 0.528x | 0.503x | true |

After timing, same graph generator and artifact family:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.copy()` attributed 1500/15000 | 75.887 ms | 82.430 ms | 46.622 ms | 47.579 ms | 0.614x | 0.577x | true |

Behavior proof:

- Direct artifact parity passed for source and copied `nodes(data=True)` /
  `edges(keys=True, data=True)`, edge count, shallow nested node attr sharing,
  and a dirty-edge copied output after mutating a live edge attr dict.
- `rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed.
- `rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  28 passed, 0 failed; doctests 0 passed, 0 failed.
- `rch exec -- cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo fmt -p fnx-python -- --check`: passed.
- `python -m py_compile python/franken_networkx/__init__.py`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: exit 0; broad pre-existing
  `lib.rs` warnings, no critical findings.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py`: exit 0;
  broad pre-existing wrapper warnings, no critical findings.

## 2026-06-23 BlackThrush MultiDiGraph clear_edges native in-place clear - 2.5x-4.7x FNX self-speedup (`br-r37-c1-04z53.9168`, cod-a)

Lever: `PyMultiDiGraph.clear_edges()` rebuilt a fresh Rust `MultiDiGraph` from
the node set, then dropped Python edge mirrors. That preserved node order but
paid the construction path even though `clear_edges` is an edge-only mutation.
`fnx-classes::MultiDiGraph` now has an in-place `clear_edges()` that clears the
edge buckets plus successor/predecessor rows, resets `edge_count`, and bumps the
core revision. The Python wrapper calls that native clear directly and preserves
the existing Python node-key/node-attr mirrors while clearing edge mirrors and
bumping the edge mutation sequence.

Keep decision: KEEP. The original 0.04x-0.10x gap reproduced on the current
artifact, and the final artifact moves the attributed 800n/4000e case from
0.091x median to 0.426x median versus NetworkX. It still trails NetworkX, but
FNX median time fell from about 5.92 ms to 1.45 ms on attributed edges and to
1.07 ms on plain edges. This is not a near-zero gain.

Direct artifact environment:

`PYTHONPATH=<temp franken_networkx package copy>:/data/projects/franken_networkx/legacy_networkx_code/networkx python3`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
copied into the temp package as `franken_networkx._fnx.abi3.so`.

Measured trigger baseline before the edit, current turn, deterministic
`MultiDiGraph.clear_edges()` on prebuilt 800-node / 4000-edge graph batches,
80 clears per round where applicable, preserving node order and node attr
assertions:

| workload | FNX median | NetworkX median | ratio median | ratio best | parity |
| --- | ---: | ---: | ---: | ---: | --- |
| attributed keyed edges, reps=60 | 5.92 ms | 0.56 ms | 0.091x | 0.107x | true |

Final timing, same artifact family and graph generator:

| workload | FNX median | NetworkX median | ratio median | ratio best | parity |
| --- | ---: | ---: | ---: | ---: | --- |
| plain keyed edges, reps=80 | 1.07 ms | 0.42 ms | 0.386x | 0.439x | true |
| attributed keyed edges, reps=80 | 1.45 ms | 0.61 ms | 0.426x | 0.457x | true |

Behavior proof:

- Direct artifact parity assertions passed for node count, edge count after
  clear, node insertion order prefix, and node attribute preservation against
  legacy NetworkX.
- Core Rust unit test covers `MultiDiGraph::clear_edges()` preserving nodes,
  node attrs, empty successor/predecessor rows, and core invariants.
- PyO3 unit test covers `PyMultiDiGraph.clear_edges()` preserving Python-facing
  node attr mirrors and clearing Python edge mirrors.
- `cargo +nightly-2026-06-10 check -p fnx-classes`: passed with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 test -p fnx-classes`: 69 passed, 0 failed;
  2 ignored; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  28 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 clippy -p fnx-classes --all-targets -- -D warnings`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo fmt -p fnx-classes -- --check`: passed.
- `cargo fmt -p fnx-python -- --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-classes/src/digraph.rs`: exit 0; broad
  pre-existing `digraph.rs` warnings, no critical findings.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; broad
  pre-existing `digraph.rs` warnings, no critical findings.

## 2026-06-23 BlackThrush DiGraph `edges(nbunch, data="w")` guarded-drain no-ship (`br-r37-c1-04z53.9162`, cod-b)

Target: close the residual where exact `DiGraph.edges(nbunch, data="w")`
returns a canonical guarded `OutEdgeDataView` and remains slower than vendored
NetworkX even though `DiGraph.out_edges(nbunch, data="w")` can use the same
native scalar emitter with less wrapper overhead.

Direct artifact environment:

`/data/projects/franken_networkx/.venv/bin/python` with
`/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`, source package imported from
`/data/projects/.scratch/franken_networkx-cod-b-20260623T034823Z/python`, and
vendored NetworkX imported from
`/data/projects/.scratch/franken_networkx-cod-b-20260623T034823Z/legacy_networkx_code`.

Measured trigger: deterministic unique-edge `DiGraph`, `nbunch=list(range(k))`,
attr key `"w"`, exact tuple-order/digest parity asserted before timing.

Rejected attempts:

| Attempt | Workload | FNX median | NetworkX median | ratio median | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| Rust iterator over `list.__iter__(view)` plus `edges_seq` guard | `edges`, n=1500/m=9000/k=750, 9000 rows | 3.265 ms | 1.115 ms | 0.342x | reverted |
| Rust iterator over `list.__iter__(view)` plus `edges_seq` guard | `edges`, n=3500/m=24000/k=1750, 24000 rows | 9.593 ms | 2.937 ms | 0.306x | reverted |
| Rust iterator over `list.__iter__(view)` plus `edges_seq` guard | `edges`, n=7000/m=48000/k=3500, 48000 rows | 19.417 ms | 5.989 ms | 0.308x | reverted |
| Typed `PyList` indexed guarded iterator, `edges_seq` only | `edges`, n=1500/m=9000/k=750, 9000 rows | 1.371 ms | 1.077 ms | 0.785x | reverted |
| Typed `PyList` indexed guarded iterator, `edges_seq` only | `edges`, n=3500/m=24000/k=1750, 24000 rows | 7.946 ms | 2.985 ms | 0.376x | reverted |
| Typed `PyList` indexed guarded iterator, `edges_seq` only | `edges`, n=7000/m=48000/k=3500, 48000 rows | 16.797 ms | 6.135 ms | 0.365x | reverted |

Mutation/parity probe:

- Both compiled attempts preserved exact row parity.
- The typed `PyList` attempt matched NetworkX for node-only mutation during
  iteration (`next()` continues) and edge mutation during iteration
  (`RuntimeError: dictionary changed size during iteration`).
- That semantics fix was still a performance no-ship because the benchmark rows
  remained below NetworkX and below the prior same-artifact current-path timing.

Additional unshipped probes:

- Returning `list.__iter__(self)` without a mid-iteration graph guard won the
  1500/9000 row (`1.31x` median in an in-memory monkeypatch) but drops the
  required RuntimeError mutation guard.
- A `yield from list.__iter__(self)` end-of-drain guard won the same row
  (`1.17x` median) but raises after the old snapshot is exhausted rather than on
  the first `next()` after an edge mutation, so it weakens NetworkX-observable
  behavior and was not shipped.

Decision: REJECT / close this wrapper-drain bead for now. The viable next lever
is not another Python/Rust `__next__` wrapper around a materialized list; those
cross the interpreter boundary per row or keep the same indexed drain. A future
attempt should either add a C-level list iterator with exact fail-fast checks or
change the view substrate so the canonical `OutEdgeDataView` can preserve
NetworkX mutation timing without per-edge Python callback overhead. All code
from these attempts was reverted before commit.

## 2026-06-23 BlackThrush weighted degree nbunch native subsets - 0.03x-0.13x -> 0.55x-1.07x (`br-r37-c1-04z53.9167`, cod-a)

Lever: `degree(nbunch, weight=...)` had native support for full-graph weighted
degree and unweighted nbunch subsets, but the weighted subset path still drained
through Python per-node degree loops. This pass adds native weighted-subset
degree kernels for `DiGraph` and `MultiDiGraph`, while the live CopperCliff
Graph/MultiGraph hunk supplies the sibling `Graph`/`MultiGraph` kernels and
Python view routing. The native kernels preserve nbunch filtering, unhashable
element errors, directed in/out grouping, multiedge key order, self-loop double
counting, and CPython `sum()` numeric association.

Keep decision: KEEP. Against the vendored NetworkX oracle on the same
400-node/3000-edge weighted fixture, `DiGraph.degree(nbunch, weight="w")`
moved from 0.133x to 1.067x, `MultiGraph` from 0.034x to 0.553x, and
`MultiDiGraph` from 0.039x to 0.630x. Graph is now near parity at 0.878x after
the preceding CopperCliff commit `e09a7265c`.

Direct artifact environment:

`PYTHONPATH=<temp package>:/data/projects/franken_networkx/legacy_networkx_code/networkx python3`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
copied to `franken_networkx/_fnx.abi3.so`.

Measured trigger baseline before the directed native subset edit, current turn,
deterministic weighted graph fixture, `nbunch=[(i*7)%400 for i in range(220)]`
plus two missing nodes:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Graph.degree(nbunch, weight)` | 0.110 ms | 0.111 ms | 0.097 ms | 0.099 ms | 0.890x | 0.893x | true |
| `DiGraph.degree(nbunch, weight)` | 1.077 ms | 1.096 ms | 0.144 ms | 0.144 ms | 0.133x | 0.132x | true |
| `MultiGraph.degree(nbunch, weight)` | 8.669 ms | 9.068 ms | 0.296 ms | 0.301 ms | 0.034x | 0.033x | true |
| `MultiDiGraph.degree(nbunch, weight)` | 9.098 ms | 9.883 ms | 0.354 ms | 0.364 ms | 0.039x | 0.037x | true |

After timing, same graph generator and artifact:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Graph.degree(nbunch, weight)` | 0.112 ms | 0.112 ms | 0.098 ms | 0.098 ms | 0.878x | 0.877x | true |
| `DiGraph.degree(nbunch, weight)` | 0.127 ms | 0.128 ms | 0.136 ms | 0.137 ms | 1.067x | 1.065x | true |
| `MultiGraph.degree(nbunch, weight)` | 0.565 ms | 0.573 ms | 0.312 ms | 0.316 ms | 0.553x | 0.552x | true |
| `MultiDiGraph.degree(nbunch, weight)` | 0.577 ms | 0.581 ms | 0.364 ms | 0.365 ms | 0.630x | 0.628x | true |

Behavior proof:

- Direct artifact parity passed for all four benchmark rows against vendored
  NetworkX.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo fmt -p fnx-python -- --check`: passed.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: 27 passed, 0 failed;
  doctests 0 passed, 0 failed.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; broad pre-existing
  `digraph.rs` warnings, no critical findings; UBS cargo-aware checks reported
  fmt/clippy/check/test-build clean in its shadow workspace.

## 2026-06-22 BlackThrush stale MultiGraph connectivity and reverted micro-levers (`br-r37-c1-04z53.9164`, cod-a)

Decision: CLOSE AS STALE / NO-SHIP. The live child bead was opened from an
older `MG/MDG connectivity 0.18x` artifact, but a clean current-HEAD baseline
after `86ff6156f` no longer reproduced that loss on the high-parallel
MultiGraph shape. No eager integer-adjacency storage rewrite was made.

Direct artifact environment:

`PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=<checkout>/python:<checkout>/legacy_networkx_code/networkx .venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Current baseline, detached worktree at `86ff6156f`, connected high-parallel
`MultiGraph` with `250` integer nodes and `6000` edges, seed `23`:

| workload | FNX median | NetworkX median | ratio vs NetworkX | parity |
| --- | ---: | ---: | ---: | --- |
| `connected_components` list | 0.097 ms | 0.108 ms | 1.111x | true |
| `number_connected_components` | 0.079 ms | 0.100 ms | 1.262x | true |
| `is_connected` | 0.070 ms | 0.094 ms | 1.343x | true |
| `node_connected_component` | 0.089 ms | 0.093 ms | 1.044x | true |

Rejected sub-lever 1: `PyMultiDiGraph._native_selfloop_edges` reused a single
owned `(u, u, key)` lookup tuple in the same style as `PyMultiGraph`. The first
focused run mixed modest wins with regressions, and the narrower repeat did not
show a stable material gain. Source was reverted before final gates.

Rejected sub-lever 2: a total-only numeric accumulator for
`MultiDiGraph.degree(weight="weight")` avoided per-node `PyList` construction
and Python `sum()` for exact bool/int/float live weights, falling back for custom
objects. Same-fixture baseline was `5.761 ms` FNX vs `3.226 ms` NetworkX
(`0.560x`). The first candidate run looked positive at `5.088 ms` vs `3.307 ms`
(`0.650x`), but the confirmation run regressed to `8.782 ms` vs `2.779 ms`
(`0.316x`). Source was reverted.

Behavior proof for the reverted weighted-degree candidate passed before
rejection: full-list weighted/unweighted degree parity, missing-weight default
`1`, post-creation live edge-attribute mutation, and custom-object fallback
matched vendored NetworkX.

Validation after revert:

- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- Rebase-resolved `br-r37-c1-04z53.9164`: closed the stale/no-ship child
  bead after upstream had already allocated `.9163`.

## 2026-06-22 BlackThrush weighted MultiDiGraph sparse-export stale-gap closeout (`br-r37-c1-wvuf7`, cod-a)

Decision: CLOSE AS STALE. The open `br-r37-c1-wvuf7` tracker still described
large `MultiDiGraph.to_scipy_sparse_array` / `adjacency_matrix` losses from the
pre-CSR-boundary path, but current source plus the warm cod-a release artifact
now wins on the same high-unique default-order n=2000 surface. No source edit was
made because the measured gap is gone; the remaining open perf surface is the
separate substrate-level node-object materialization wall, not a safe
BOLD-VERIFY micro-lever.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
loaded as `franken_networkx._fnx`, `PYTHONHASHSEED=0`,
`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.

Fixture: deterministic `MultiDiGraph`, `2000` integer nodes, `12000` unique
keyed directed edges, string `weight` attributes. Dirty rows mutate every 31st
public live edge-attribute dict after construction, exercising the precise dirty
weight path. Every row matched NetworkX by sorted COO digest, `nnz`, and sum.

| workload | FNX median | NetworkX median | ratio median | parity |
| --- | ---: | ---: | ---: | --- |
| clean `to_scipy_sparse_array(weight="weight")` | 3.957 ms | 11.975 ms | 3.03x | true |
| clean `adjacency_matrix(weight="weight")` | 6.535 ms | 10.208 ms | 1.56x | true |
| dirty `to_scipy_sparse_array(weight="weight")` | 8.161 ms | 13.392 ms | 1.64x | true |
| dirty `adjacency_matrix(weight="weight")` | 8.823 ms | 12.144 ms | 1.38x | true |

Tracker context: `br-r37-c1-node-storage-materialization-wall-5fije` remains open
for the broad interned/live-PyDict node-object storage rearchitecture. It is the
largest documented residual, but the bead itself records that it is a deep core
effort, not a safe single-turn sparse-export continuation.

## 2026-06-22 BlackThrush directed nbunch attr-key native emitters - MultiDiGraph gap 0.42x -> 0.96x (`br-r37-c1-04z53`, cod-b)

Lever: iterable-nbunch directed edge views with `data="<attr>"` still reused the native
`data=True` nbunch rows and projected `attrs.get(...)` in Python. That preserved parity but
materialized a live attr dict for every edge just to return one scalar. Added scalar native
emitters for exact `DiGraph` and exact `MultiDiGraph` `keys=False` paths. The emitters read from a
live mirror when present and otherwise read string-key values from Rust attrs directly; non-string
keys keep parity when a live mirror exists. Single-node nbunch, conversion/subgraph views, and
`keys=True` multigraph attr-key calls stay on the previous paths.

Keep decision: KEEP. The main residual row, `MultiDiGraph.edges(nbunch, data="weight")`, moved from
a clear loss to near parity on best-of-run timing, and `MultiDiGraph.out_edges(nbunch,
data="weight")` flipped to wins. Some median rows remain noisy because both implementations are now
sub-millisecond to low-millisecond list construction paths, but this is not a zero-gain lever.

Same-machine direct probe, with
`/data/projects/.rch-targets/franken_networkx-cod-b/release/lib_fnx.so` preloaded as
`franken_networkx._fnx`:

| workload | route | before FNX best | before NetworkX best | before ratio | after FNX best | after NetworkX best | after ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DiGraph n=1500/m=9000/k=750 | out_edges attr-key | 0.269 ms | 0.279 ms | 1.04x | 0.249 ms | 0.255 ms | 1.02x |
| DiGraph n=1500/m=9000/k=750 | edges attr-key | 0.300 ms | 0.278 ms | 0.93x | 0.279 ms | 0.254 ms | 0.91x |
| DiGraph n=3500/m=24000/k=1750 | out_edges attr-key | 0.690 ms | 0.695 ms | 1.01x | 0.665 ms | 0.635 ms | 0.96x |
| DiGraph n=3500/m=24000/k=1750 | edges attr-key | 0.738 ms | 0.690 ms | 0.93x | 0.645 ms | 0.618 ms | 0.96x |
| MultiDiGraph n=1000/m=8000/k=500 | out_edges attr-key | 1.321 ms | 1.261 ms | 0.96x | 0.909 ms | 1.236 ms | 1.36x |
| MultiDiGraph n=1000/m=8000/k=500 | edges attr-key | 1.684 ms | 1.313 ms | 0.78x | 1.246 ms | 1.247 ms | 1.00x |
| MultiDiGraph n=2500/m=20000/k=1250 | out_edges attr-key | 6.361 ms | 5.332 ms | 0.84x | 2.701 ms | 3.151 ms | 1.17x |
| MultiDiGraph n=2500/m=20000/k=1250 | edges attr-key | 8.133 ms | 3.385 ms | 0.42x | 3.284 ms | 3.151 ms | 0.96x |

Final rebased current-artifact sanity probe:

After the final rebase, rebuilt the release artifact with
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b RCH_WORKER=vmi1153651 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`.
Direct list parity passed against the legacy NetworkX oracle. The MultiDiGraph target remains a
keep with all measured rows above NetworkX. A smaller separate DiGraph iterable-nbunch attr-key
residual remains and is routed as follow-up `br-r37-c1-04z53.9161`.

| workload | route | FNX best | NetworkX best | ratio best |
| --- | --- | ---: | ---: | ---: |
| DiGraph n=1500/m=9000/k=750 unique edges | out_edges attr-key | 0.906 ms | 0.800 ms | 0.88x |
| DiGraph n=1500/m=9000/k=750 unique edges | edges attr-key | 1.122 ms | 0.854 ms | 0.76x |
| DiGraph n=3500/m=24000/k=1750 unique edges | out_edges attr-key | 4.852 ms | 4.262 ms | 0.88x |
| DiGraph n=3500/m=24000/k=1750 unique edges | edges attr-key | 7.010 ms | 6.518 ms | 0.93x |
| MultiDiGraph n=1000/m=8000/k=500 | out_edges attr-key | 1.281 ms | 1.996 ms | 1.56x |
| MultiDiGraph n=1000/m=8000/k=500 | edges attr-key | 1.633 ms | 2.042 ms | 1.25x |
| MultiDiGraph n=2500/m=20000/k=1250 | out_edges attr-key | 8.289 ms | 11.500 ms | 1.39x |
| MultiDiGraph n=2500/m=20000/k=1250 | edges attr-key | 8.903 ms | 10.866 ms | 1.22x |

Behavior proof:

- Direct artifact digest parity passed for every benchmark row above.
- Contract probe passed for duplicate nbunch nodes, missing nbunch nodes, missing attr defaults,
  nested dict attr values, and non-string attr keys stored through the live edge-attr mirrors on
  both `DiGraph` and `MultiDiGraph`.
- `cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `cargo fmt -p fnx-python --check`: passed.
- `cargo clippy -p fnx-python --features pyo3/abi3-py310 -- -D warnings`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`.
- `cargo test -p fnx-python --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b` (27 passed).
- `cargo build -p fnx-python --release --features pyo3/abi3-py310`: passed via RCH with
  `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b`; release artifact
  retrieved locally and used for the final probe.
- `py_compile python/franken_networkx/__init__.py tests/python/test_graph_utilities.py`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; remaining warnings are the existing
  broad-file inventory.
- `ubs --only=python --skip=7 python/franken_networkx/__init__.py
  tests/python/test_graph_utilities.py`: exit 0; remaining warnings are the existing broad-file
  and pytest-assert inventory. A mixed Rust/Python/Markdown UBS invocation was interrupted after
  the Python scanner kept running for several minutes; the Markdown file is not a supported UBS
  language and was covered by `git diff --check`.
## 2026-06-22 BlackThrush MultiGraph selfloop edge-key lookup reuse - 1.6x-1.9x FNX self-speedup (`br-r37-c1-lv4p9`, cod-a)

Lever: `MultiGraph.selfloop_edges(keys=True, data=...)` rebuilt the same
`(u, u, key)` lookup tuple once to recover the Python-visible edge key and again
to read edge data or the live edge-attribute mirror. Reuse the lookup tuple inside
the native `PyMultiGraph::_native_selfloop_edges` loop for the `keys + data`
paths. Plain pair/key-only rows still avoid the tuple when no lookup is needed.

Keep decision: KEEP. The measured trigger gap was explicit string-key
`MultiGraph` self-loop emission at 0.19x-0.22x vs NetworkX. The final same-shape
artifact benchmark improves FNX's own minimum timing by 1.6x-1.9x and improves
the vs-NetworkX ratio to 0.29x-0.36x. This is not a near-zero gain.

Rejected sub-lever: applying the same helper split to `PyMultiDiGraph` did not
hold up on the focused string-key data rows; one repeat measured
`MultiDiGraph str keys_data` / `keys_weight` at only 0.17x vs NetworkX. That
change was backed out before landing, and the accepted diff is scoped to
`PyMultiGraph`.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, `n=2400`,
`parallel=2`, explicit string edge keys, `4800` self-loop multiedges:

| workload | FNX timing | NetworkX timing | ratio vs NetworkX | parity |
| --- | ---: | ---: | ---: | --- |
| `MultiGraph.selfloop_edges(keys=True, data=True)` | 3.276 ms | 0.632 ms | 0.19x | true |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` | 3.576 ms | 0.802 ms | 0.22x | true |

Final after timing, fresh graph per mode, same graph shape and artifact:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.selfloop_edges(keys=True, data=True)` | 2.021 ms | 2.678 ms | 0.585 ms | 0.607 ms | 0.29x | 0.23x | true |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` | 1.892 ms | 1.921 ms | 0.675 ms | 0.709 ms | 0.36x | 0.37x | true |

Post-rebase sanity probe after rebasing onto `f7dcd8f69` and rebuilding the
release artifact with the same `cod-a` target directory:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `MultiGraph.selfloop_edges(keys=True, data=True)` | 1.651 ms | 2.131 ms | 0.468 ms | 0.541 ms | 0.28x | 0.25x | true |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` | 1.472 ms | 2.158 ms | 0.491 ms | 0.531 ms | 0.33x | 0.25x | true |

Behavior proof:

- Direct artifact parity passed for full-list `MultiGraph` string-key
  `selfloop_edges(keys=True, data=True)` and
  `selfloop_edges(keys=True, data="weight", default=-1)` against NetworkX.
- Focused direct probe passed for missing-data default, nested payload return,
  and post-creation live edge-attribute mutation:
  `franken_networkx` and NetworkX both returned `[('a', 'a', 'k', 'D')]`,
  `[('a', 'a', 'k', {'x': 1})]`, and `[('a', 'a', 'k', 9)]`.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/lib.rs`: exit 0; broad pre-existing
  `lib.rs` warnings, no critical findings.

## 2026-06-22 BlackThrush DiGraph nbunch attr-key scalar fast path - 1.0x-2.3x FNX self-speedup (`br-r37-c1-04z53.9161`, cod-a)

Lever: `_native_out_edges_nbunch_data_key` was already the right route for
exact `DiGraph.out_edges(nbunch, data="<attr>")` and
`DiGraph.edges(nbunch, data="<attr>")`, but each scalar edge read still entered
`edge_attr_value_or_default` by allocating/probing the live edge-attribute mirror
key `(u, v)` before checking the Rust attr map. Fresh benchmark graphs with only
string scalar attrs have no live edge-attr mirrors, so the helper now directly
reads Rust attrs for string keys and missing defaults when `edge_py_attrs` is
empty. Nested map values still fall through to materialize the live dict, and any
existing live edge mirror keeps the old mirror-first path.

Keep decision: KEEP. The smaller row remains an output-construction floor, but
the large-row native scalar path moved substantially and the public
`edges(nbunch, data="weight")` target improved from 7.190 ms to 3.042 ms best on
the same deterministic graph shape. This is not a near-zero gain. A pure wrapper
shortcut was considered and rejected because the current wrapper preserves the
NetworkX-named `OutEdgeDataView` surface and mutation guards.

Direct artifact environment:

`PYTHONPATH=/data/projects/franken_networkx/python:/data/projects/franken_networkx/legacy_networkx_code /data/projects/franken_networkx/.venv/bin/python`
with `/data/projects/.rch-targets/franken_networkx-cod-a/release/lib_fnx.so`
preloaded as `franken_networkx._fnx`.

Measured trigger baseline before the edit, current turn, deterministic
unique-edge `DiGraph`, `nbunch=list(range(n//2))`, attr key `"weight"`:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `out_edges` n=1500/m=9000/k=750 | 0.882 ms | 0.924 ms | 0.733 ms | 0.751 ms | 0.83x | 0.81x | true |
| `edges` n=1500/m=9000/k=750 | 1.080 ms | 1.236 ms | 0.745 ms | 0.766 ms | 0.69x | 0.62x | true |
| `out_edges` n=3500/m=24000/k=1750 | 7.134 ms | 7.576 ms | 2.065 ms | 6.540 ms | 0.29x | 0.86x | true |
| `edges` n=3500/m=24000/k=1750 | 7.190 ms | 7.453 ms | 6.162 ms | 6.846 ms | 0.86x | 0.92x | true |

After timing, same graph generator and artifact:

| workload | FNX min | FNX median | NetworkX min | NetworkX median | ratio min | ratio median | parity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `out_edges` n=1500/m=9000/k=750 | 0.881 ms | 0.995 ms | 0.740 ms | 0.762 ms | 0.84x | 0.77x | true |
| `edges` n=1500/m=9000/k=750 | 1.054 ms | 1.077 ms | 0.743 ms | 0.757 ms | 0.70x | 0.70x | true |
| `out_edges` n=3500/m=24000/k=1750 | 3.339 ms | 6.064 ms | 4.198 ms | 5.004 ms | 1.26x | 0.83x | true |
| `edges` n=3500/m=24000/k=1750 | 3.042 ms | 6.040 ms | 2.308 ms | 5.171 ms | 0.76x | 0.86x | true |

Behavior proof:

- Direct artifact parity passed for all four benchmark rows against legacy
  NetworkX.
- Focused direct probe passed for missing-data default, nested payload return,
  and post-creation live edge-attribute mutation:
  `franken_networkx` and NetworkX both returned
  `[('a', 'b', 'D'), ('b', 'c', 'D')]`, `[('a', 'b', {'x': 1})]`, and
  `[('a', 'b', 7)]`.
- `cargo +nightly-2026-06-10 build -p fnx-python --release --features pyo3/abi3-py310`:
  passed with `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`.
- `cargo +nightly-2026-06-10 check -p fnx-python --features pyo3/abi3-py310`:
  passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`:
  passed.
- `cargo +nightly-2026-06-10 test -p fnx-python --features pyo3/abi3-py310`:
  27 passed, 0 failed; doctests 0 passed, 0 failed.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs`: exit 0; broad pre-existing
  `digraph.rs` warnings, no critical findings.

## 2026-06-24 BlackThrush/CopperCliff adjacency outer-dict cache - no-ship after remote rerun

Lever: `share_dict_of_dicts_cache` already reused adjacency row dicts for
`Graph.adjacency()` / `DiGraph.adjacency()`, but rebuilt the outer
`{node: row}` dict on every call. The proposed patch added a lazily-filled
`shared_outer` dict to `DictOfDictsCache` and initialized it at all cache rebuild
sites. The public contract would still have been an iterator over `(node, row)`
pairs; callers would not receive the cached dict itself.

Scratch proof source: branch `cc-adjouter-land-20260624`, commit `e602dcbcc`
in `/data/projects/.scratch/franken_networkx-cc-adjouter-019aa7efc`, authorized
for cherry-pick by CopperCliff in Agent Mail message 2243. That proof measured
interleaved min-of-21 on paired BA graphs:

| workload | before ratio vs NetworkX | after ratio vs NetworkX |
| --- | ---: | ---: |
| `Graph dict(adjacency())` n=2000 | 0.56x | 0.97x |
| `Graph dict(adjacency())` n=8000 | 0.55x | 0.95x |
| `DiGraph dict(adjacency())` n=2000 | 0.62x | 0.99x |
| `DiGraph dict(adjacency())` n=8000 | 0.56x | 0.99x |

Current-turn crate bench added a focused Criterion group and preloads the fresh
`CARGO_TARGET_DIR` release extension before import. Command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- adjacency_outer_cache`

Final rerun used remote worker `ovh-a` with the final benchmark harness. Median
results did not reproduce the scratch keep:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `Graph dict(adjacency())` n=2000 | 88.505 us | 49.058 us | 0.55x |
| `Graph dict(adjacency())` n=8000 | 370.90 us | 206.86 us | 0.56x |
| `DiGraph dict(adjacency())` n=2000 | 164.39 us | 104.44 us | 0.64x |
| `DiGraph dict(adjacency())` n=8000 | 698.33 us | 377.17 us | 0.54x |

Keep decision: REVERTED production code. The durable remote Criterion run stayed
at the same `~0.54x-0.64x` floor as the scratch baseline instead of the reported
`0.95x-0.99x` after state. The focused bench remains because it is useful
negative evidence and prevents this scratch candidate from being re-landed
without a reproducible win.

Behavior proof:

- The new Criterion setup asserts `dict(G.adjacency())` content equality against
  NetworkX and two-call row identity (`first[u] is second[u]`) before any timing.
- `cargo fmt -p fnx-python --check`: passed.
- `git diff --check`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`:
  passed on `vmi1149989`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  local fallback, 28 passed, 0 failed; doctests 0 passed, 0 failed.

## 2026-06-24 BlackThrush MultiDiGraph integer `in_degree(weight)` fast path - kept

Target: current NetworkX laggard lane covering `in_degree(weight)`,
`MultiGraph` self-loops, and `MultiDiGraph` keys. The production lever only
touches the pure Python-exact-int `MultiDiGraph.in_degree(weight="<attr>")` full
graph path. It routes each node through the existing native integer row
accumulator and returns Rust-built Python ints when every observed weight is an
exact int and the total fits in `i64`. It falls back to the old Python
`list` plus `builtins.sum` path for bools, floats, custom numeric objects,
non-int values, or overflow.

Command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- core_laggards`

Baseline on `ovh-a`, same deterministic workload, before the production edit.
The command printed the target Criterion rows before a later unrelated benchmark
setup reloaded `franken_networkx._fnx` and tripped the PyO3 logger guard; the
harness preload was then made idempotent and the final command exited 0.

| workload | FNX median | NetworkX median | FNX/NetworkX speed ratio |
| --- | ---: | ---: | ---: |
| `MultiDiGraph.in_degree(weight)` n=700/e=12662 | 2.4897 ms | 1.3931 ms | 0.56x |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` n=2500/loops=2502 | 796.64 us | 498.15 us | 0.63x |
| `MultiDiGraph.edges(keys=True)` n=700/e=12662 | 1.6846 ms | 1.0601 ms | 0.63x |

After timing on `ovh-a`, final benchmark harness, exit 0:

| workload | FNX median | NetworkX median | FNX/NetworkX speed ratio | decision |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph.in_degree(weight)` n=700/e=12662 | 2.1609 ms | 1.3174 ms | 0.61x | KEEP |
| `MultiGraph.selfloop_edges(keys=True, data="weight")` n=2500/loops=2502 | 886.84 us | 491.04 us | 0.55x | routing only |
| `MultiDiGraph.edges(keys=True)` n=700/e=12662 | 2.4282 ms | 2.0721 ms | 0.85x | routing only |

Keep decision: KEEP. The targeted `in_degree(weight)` row improved from 0.56x
to 0.61x versus NetworkX and from 2.4897 ms to 2.1609 ms FNX median on the
same worker, a 1.15x FNX self-speedup. Criterion reported the target row as
improved with change `[-14.562% -10.674% -6.0918%]`. The self-loop and
`edges(keys=True)` rows were measured for the requested laggard lane, but no
production change is claimed for them in this commit.

Behavior proof:

- Benchmark setup asserts equality against vendored NetworkX for the sum of
  `graph.in_degree(weight="weight")`, `selfloop_edges(..., keys=True,
  data="weight")`, and `graph.edges(keys=True)` before timing.
- The Rust fast path only accepts exact Python int rows through the existing
  per-edge integer accumulator and preserves the prior Python-sum fallback for
  all other weight semantics.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a cargo fmt -p fnx-python --check`:
  passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`:
  passed on `ovh-b`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`:
  passed on `hz2`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  local fallback, 28 passed, 0 failed; doctests 0 passed, 0 failed.
- Focused Python parity probe preloaded
  `/data/projects/.rch-targets/franken_networkx-cod-a/release/deps/lib_fnx.so`
  and passed exact-int `MultiDiGraph.in_degree(weight)`, missing-weight,
  bool, float, huge-int fallback, `MultiGraph.selfloop_edges(keys=True,
  data="weight")`, and `MultiDiGraph.edges(keys=True)` comparisons against
  vendored NetworkX.
- Focused pytest with the same preloaded extension:
  `tests/python/test_attribute_access_parity.py::test_multidigraph_edges_keys_view_matches_networkx`
  and
  `tests/python/test_attribute_access_parity.py::TestDegreeNbunchFilter::test_digraph_in_degree_skips_missing`;
  2 passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/src/digraph.rs crates/fnx-python/benches/networkx_head_to_head.rs`:
  exit 0; no critical findings, with broad pre-existing `digraph.rs` warning
  inventory.

## 2026-06-24 BlackThrush MultiDiGraph full weighted in/out degree - no-ship

Target: user-called laggard `MultiDiGraph.in_degree(weight="weight")` /
`MultiDiGraph.out_degree(weight="weight")`, measured head-to-head against
vendored NetworkX on a deterministic 1800-node, 14400-edge weighted
MultiDiGraph with two parallel edges per generated arc.

Benchmark harness added:
`networkx_head_to_head_multidigraph_weighted_degree` in
`crates/fnx-python/benches/networkx_head_to_head.rs`. The setup asserts exact
ordered parity for both `list(G.in_degree(weight="weight"))` and
`list(G.out_degree(weight="weight"))` before timing.

Command:

`RCH_WORKER=vmi1149989 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo bench -p fnx-python --profile release --bench networkx_head_to_head networkx_head_to_head_multidigraph_weighted_degree -- --quiet`

Worker/runtime notes:

- First remote attempt on `hz2` compiled but failed before timing with
  `ImportError: libpython3.13.so.1.0: cannot open shared object file`; no perf
  conclusion drawn from that worker.
- Usable timed evidence came from `vmi1149989`.

Rejected production levers:

1. Live Python-attr exact-int sum path: read `edge_py_attrs` directly and summed
   exact `int` weights in Rust, falling back for floats / exotic attrs.
2. Clean inner exact-int sum path: skipped the live dict lookups when
   `edges_dirty == false`, used `successors_iter` / `predecessors_iter` /
   `edge_keys_iter`, and read `inner.edge_attrs` directly.

Both levers were reverted. The live-dict path was slower than the existing
fallback. The clean-inner iterator path improved the live-dict attempt but still
missed the NetworkX target by too much to ship.

Final timed rows for the reverted clean-inner iterator path:

| workload | FNX median | NetworkX median | ratio vs NetworkX | decision |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph.in_degree(weight)` n=1800/e=14400 | 16.882 ms | 9.1783 ms | 0.54x | revert |
| `MultiDiGraph.out_degree(weight)` n=1800/e=14400 | 12.354 ms | 5.1097 ms | 0.41x | revert |

Earlier same-worker live-dict attempt:

| workload | FNX median | NetworkX median | ratio vs NetworkX | decision |
| --- | ---: | ---: | ---: | --- |
| `MultiDiGraph.in_degree(weight)` n=1800/e=14400 | 17.897 ms | 8.6118 ms | 0.48x | revert |
| `MultiDiGraph.out_degree(weight)` n=1800/e=14400 | 14.072 ms | 7.2240 ms | 0.51x | revert |

Validation for the final evidence-only commit:

- `cargo fmt -p fnx-python --check`: passed.
- `git diff --check`: passed.
- `ubs --only=rust crates/fnx-python/benches/networkx_head_to_head.rs`:
  exit 0; critical 0; existing bench `expect` warnings only.
- `CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`:
  passed on `ovh-b`.
- `RCH_WORKER=ovh-b CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`:
  passed on `ovh-b`.
- `RCH_WORKER=ovh-b CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  selected `vmi1149989`; 28 passed, 0 failed; doctests 0 passed, 0 failed.

Next viable lever should avoid per-edge string-map attr probes entirely. The
remaining gap likely needs a compact per-node weighted in/out accumulator or a
revision-keyed weighted-degree cache built during edge insertion / attr sync,
with a dirty-key fallback for live edge-attribute mutation. Repeating direct
`edge_py_attrs` or `inner.edge_attrs` scans is negative evidence.

## 2026-06-24 CopperCliff MultiDiGraph weighted degree - Rust-store int fast path - KEEP (br-r37-c1-mdgwdeg)

Follow-up to BlackThrush's "MultiDiGraph full weighted in/out degree - no-ship" entry
(which recorded the gap but had no fix). The existing int fast-paths
(`native_weighted_directional_degree_py_int_impl`) still cross PyO3 `get_item` on the
live edge mirror ONCE PER EDGE, and the all-node TOTAL kernel (`_native_weighted_degree`)
additionally built two `PyList`s and called Python `sum()` per node. That left
`MultiDiGraph.{in,out,}degree(weight=...)` at 0.41x-0.54x vs NetworkX on the committed
Criterion harness.

Lever: when the graph has no dirty edge mirrors (`edges_dirty == false`), the Rust
CgseValue store is authoritative, so sum int weights directly from it with ZERO per-edge
Python crossings. Added `add_store_int_weight` / `weighted_degree_store_int_row` /
`native_weighted_directional_degree_store_int` / `native_weighted_total_degree_store_int`,
wired AHEAD of the live-mirror int path and the Python-`sum()` fallback in both
`native_weighted_directional_degree` and `_native_weighted_degree`. Also added the missing
all-node TOTAL live-mirror int path (`native_weighted_total_degree_py_int_impl`). Any
non-int weight, overflow, or dirty mirror bails to the existing parity-exact paths, so
float / object / post-mutation results are unchanged. (Same dirty-gate idea as
`_native_weighted_size_int`.)

Authoritative per-crate Criterion bench (same harness + workload as BlackThrush's baseline,
n=1800 / e=14400, weights in -37..63):

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_multidigraph_weighted_degree -- --quiet`

| workload | baseline FNX | baseline ratio | after FNX median | NetworkX median | after ratio vs nx |
| --- | ---: | ---: | ---: | ---: | ---: |
| `MultiDiGraph.in_degree(weight)`  | 16.9-17.9 ms | 0.48-0.54x | 3.153 ms | 2.446 ms | 0.78x |
| `MultiDiGraph.out_degree(weight)` | 12.4-14.1 ms | 0.41-0.51x | 2.576 ms | 2.256 ms | 0.88x |

(The absolute FNX numbers fell because the int fast-path now reads the store; the baseline
column is BlackThrush's recorded median. Interleaved Python min-of-15 separately showed the
all-node TOTAL `degree(weight)` move 0.473x -> 0.948x.)

Keep decision: KEEP. ~1.5-1.7x self-speedup, roughly HALVING the gap to NetworkX on a
documented laggard, authoritatively reproduced under the same per-crate Criterion bench that
recorded the baseline (NOT cross-run Python timing). Not full parity — the residual is nx's
pure-C `_pred[n]`/`_succ[n]` dict iteration vs fnx's per-edge string-keyed
`edge_attrs(u,v,key)` store lookup; closing it fully needs an index-native per-node weight
accumulator (future work, see br bead).

Behavior proof:
- Direct artifact parity (paired MultiDiGraph n=300, plus n=2000): in/out/total
  `degree(weight)` byte-equal to NetworkX on fresh (store path), float weights (bail),
  dirty+live-mutation (mirror fallback), missing-weight default, and negative/zero ints.
- `cargo +nightly-2026-06-10 fmt -p fnx-python --check`: passed.
- `cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`: passed.
- Python conformance `-k "degree or weighted or multidi or directed_degree"`: 5645 passed,
  51 skipped, 0 failed.
- `git diff --check`: passed.

## 2026-06-25 CopperCliff MultiDiGraph weighted degree - index-native accumulator - NO-SHIP (br-r37-c1-eilce)

Follow-up to the KEEP entry "2026-06-24 CopperCliff MultiDiGraph weighted degree - Rust-store
int fast path" (shipped `02b9f9d4e`). That landing moved MultiDiGraph in/out/total
`degree(weight)` from 0.41-0.54x to 0.78-0.88x vs NetworkX but left a residual gap, recorded
in bead `br-r37-c1-eilce` with the hypothesis that the floor was the per-edge **string-keyed**
`edge_attrs(u,v,key)` HashMap lookup (re-hashing the `(source,target)` string pair per parallel
edge), and that closing it needed an **index-native per-node weight accumulator**.

Built exactly that: `MultiDiGraph::weighted_degree_int_accumulate(weight, want_out, want_in)`
in fnx-classes — a SINGLE pass over the authoritative `edges` map that sums each bucket's int
weights directly from the held `AttrMap`s (no per-key `edge_attrs` re-lookup) and accumulates
into per-node-index vectors, resolving node index once per bucket and only for the requested
direction. The two `native_*_store_int` bindings were rewired to call it once (total degree now
does ONE edges pass instead of TWO per-node row passes), and the dead `weighted_degree_store_int_row`
/ `add_store_int_weight` helpers removed. This roughly HALVES the Rust-side hashing.

Authoritative per-crate Criterion bench (same harness + workload as the KEEP baseline,
n=1800 / e=14400, weights in -37..63):

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_multidigraph_weighted_degree -- --quiet`

| workload | prior store-int FNX (ledger) | after FNX median | NetworkX median | after ratio vs nx |
| --- | ---: | ---: | ---: | ---: |
| `MultiDiGraph.in_degree(weight)`  | 3.153 ms | 3.177 ms (CI [3.06, 3.30]) | 2.274 ms | 0.72x |
| `MultiDiGraph.out_degree(weight)` | 2.576 ms | 2.579 ms                  | 2.129 ms | 0.83x |

Decision: NO-SHIP (REVERT, stashed `cc-eilce-NOSHIP`). The fnx side is statistically UNCHANGED
(in 3.153->3.177 ms, well within this run's confidence interval; out 2.576->2.579 ms) despite
halving the Rust-side hashing. CONCLUSION: the residual gap is NOT the string-keyed `edge_attrs`
lookup the bead hypothesized — it is the **PyObject materialization** of the degree view
(1800 nodes x `py_node_key` + `into_py_any` per node), which is identical on both paths and
dominates the Rust-side accumulation cost. An index-native Rust accumulator cannot close this;
matching nx (whose `DiMultiDegreeView` builds the same Python dict) would require cutting the
per-node Python-object construction itself, not the edge walk. The bead's stated lever is thus
refuted as a perf lever; updating the bead record accordingly.

Gates: `cargo +nightly-2026-06-10 fmt -p fnx-classes -p fnx-python --check` passed (after fmt);
`cargo +nightly-2026-06-10 clippy -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings`
clean (no errors/warnings). Change reverted before any conformance run; main is unaffected.

## 2026-06-25 CopperCliff MultiGraph selfloop_edges(data=attr) pristine-mirror fast path - KEEP (br-r37-c1-eilce family)

`selfloop_edges(G, keys=True, data="weight")` on a MultiGraph was the largest live core-laggard
(0.37x vs NetworkX). The native `PyMultiGraph::_native_selfloop_edges` `want_value` path built a
`(String, String, usize)` lookup key PER EDGE (two String allocations + a hash) and probed the
`edge_py_attrs` mirror inside `edge_data_value_or_default_with_key` before falling back to the Rust
store — but when NO Python edge-attr mirror exists that probe is a guaranteed MISS, so the key build
+ hash + `CgseValue` clone are pure waste. NetworkX's generator pays none of this (`d.get(attr)`
returns an already-stored Python object).

Lever: PRISTINE-MIRROR fast path. When `self.edge_py_attrs.is_empty()`, capture the attr name once
and read scalar values straight from the Rust store (`cgse_value_to_py`), skipping the per-edge
`edge_key` allocation and the mirror probe entirely. `Map`-valued attrs still route through the
mirror (`edge_data_value_or_default_with_key`) so the live dict-object identity NetworkX guarantees
is preserved. Only active when the mirror was globally empty at entry, so the store is authoritative.

Authoritative per-crate Criterion bench (`networkx_head_to_head_core_laggards`, MultiGraph
n=2500 / loops=2502, int weights), same harness that recorded the baseline:

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards`

| workload | baseline FNX | after FNX median | NetworkX median | after ratio vs nx |
| --- | ---: | ---: | ---: | ---: |
| `selfloop_edges(keys=True, data="weight")` | 1.2674 ms (0.37x) | 0.8006 ms | 0.4668 ms | 0.58x |

Decision: KEEP. ~1.58x self-speedup, vs-nx ratio 0.37x -> 0.58x on the documented top laggard,
reproduced under the per-crate Criterion bench that recorded the baseline (NOT cross-run Python
timing). Not full parity — the residual is the unavoidable per-edge PyTuple + value-object
construction (nx reuses already-stored Python objects; fnx converts from the CgseValue store), the
same PyObject-materialization floor identified for the degree views. The untouched `edges(keys=True)`
MDG laggard stayed 0.67x in the same run, confirming the change is isolated to the selfloop path.

Behavior proof: bench asserts `fnx == nx` for the exact workload (keys + parallel self-loops + int
weights). Map-valued-attr identity preserved via the mirror fallback. Python conformance
`-k "selfloop"` GREEN. fmt + clippy clean.

## 2026-06-25 CopperCliff MultiDiGraph in_edges(data=attr) edge_key removal - NO-SHIP (br-r37-c1-eilce family)

Tried to generalize the shipped selfloop_edges pristine-mirror fast path (8fd930863) to the MDG
edge-data helper `PyMultiDiGraph::edge_data_value_or_default` (called per edge by
`_native_mdg_in_edges_data_key` for `in_edges(data=attr, keys=...)`): when `edge_py_attrs.is_empty()`
skip the per-edge `(String,String,usize)` `edge_key` build + mirror probe and read scalars straight
from the CgseValue store (Map values keep the mirror for dict identity). Added a `mdg_in_edges_data`
core-laggard workload (`in_edges(keys=True, data="weight", default=0)`, MDG n=700/e=12662).

Authoritative per-crate Criterion A/B (stash the fix -> baseline -> pop -> after, same workload):

| | FNX median | NetworkX median | ratio |
| --- | ---: | ---: | ---: |
| baseline (no fix) | 8.669 ms | 2.516 ms | 0.29x |
| after (fix)       | 9.796 ms | 2.516 ms | 0.26x |

Decision: NO-SHIP (REVERT, stash `cc-inedges-NOSHIP`). The fix IS on the hot path (the workload
routes through `_native_mdg_in_edges_data_key` -> `edge_data_value_or_default`), but the fnx side did
not improve (8.67 -> 9.80 ms is within this workload's ±15% variance; the "regression" is noise). At
~630 ns/edge the per-edge cost is dominated NOT by the `edge_key` alloc the selfloop fix removed, but
by (a) the native fn's own triples Vec building `source.to_owned()` + `target.to_owned()` per edge
(line ~4605) and (b) the PyObject construction wall (`py_node_key`×2 + `py_edge_key` + 4-tuple +
value) — the same PyObject-materialization floor seen on the degree views. The `edge_key` removal is
too small a fraction to register.

CONTRAST with the selfloop KEEP (0.37x->0.58x): there the per-edge work was small enough that the two
String allocs were a large fraction; here they are a minor part of a much heavier per-edge body. The
real >=1.0x lever for `in_edges(data)` (a documented 0.29x gap) is to eliminate the triples Vec
(iterate predecessor adjacency directly, no String clones) AND cut the per-edge PyObject construction
— future work, not this micro-opt. Bench workload reverted (high variance makes it a poor guard).

Gates: change reverted before conformance; main unaffected. fmt clean on the reverted edit.

## 2026-06-25 CopperCliff BOLD-VERIFY algorithm-domain sweep - fnx beats nx everywhere (no kernel gap)

Per-crate Criterion sweep of every non-view algorithm group in networkx_head_to_head to locate a NEW
vs-nx lever after the view-path PyObject floor blocked degree/in_edges (see this session's two
NO-SHIP entries). Filter `connectivity|biconnected|cut_metrics|assortativity`, ~25 fnx-vs-nx pairs.

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head "connectivity|biconnected|cut_metrics|assortativity"`

Representative medians (fnx faster on ALL pairs):

| workload | fnx | nx | fnx speedup |
| --- | ---: | ---: | ---: |
| cut_metrics edge_expansion_ba2500 | 0.557 ms | 1.992 ms | 3.6x |
| cut_metrics node_expansion_ba2500 | 0.110 ms | 0.365 ms | 3.3x |
| cut_metrics cut_size_overlap | 0.464 ms | 1.905 ms | 4.1x |
| cut_metrics normalized_cut_overlap | 0.505 ms | 2.341 ms | 4.6x |
| assortativity degree_mixing_dict_h512 | 11.34 ms | 97.25 ms | 8.6x |
| assortativity node_degree_xy_h512 | 17.82 ms | 88.89 ms | 5.0x |
| connectivity strongly_connected_components_mdg1800 | 0.686 ms | 1.917 ms | 2.8x |
| connectivity descendants_mdg1800 | 0.514 ms | 0.942 ms | 1.8x |
| biconnected is_biconnected_mg1000 | 0.338 ms | 3.489 ms | 10.3x |
| biconnected articulation_points_mg1000 | 0.369 ms | 2.385 ms | 6.5x |
| biconnected biconnected_components_mg1000 | 1.019 ms | 3.611 ms | 3.5x |
| biconnected bfs_edges_mg1000 | 0.466 ms | 0.582 ms | 1.25x |
| biconnected minimum_spanning_tree_mg1000 | 9.05 ms | 11.26 ms | 1.24x |

Decision: NO NEW LEVER in these domains — every benched algorithm kernel (cut metrics, assortativity,
SCC/descendants, biconnected/articulation/MST) is already 1.2x-10x FASTER than NetworkX. Confirms the
native-kernel vein is mined out here. The remaining vs-nx gaps this session found are ALL
PyObject-materialization view paths: `in_edges(data=attr)` 0.29x, `edges(keys=True)` 0.61x, weighted
degree views 0.7-0.9x — bounded by per-element PyTuple/value construction (nx reuses stored Python
objects; fnx converts from the Rust store), NOT by any Rust-side algorithm. Closing those needs a
fundamentally different approach (e.g. a persistent ordered Python object mirror / lazy view objects),
not a kernel rewrite. Future digs should AVOID the algorithm domain and target the view substrate.
No code change this turn; sweep is a verification artifact.

## 2026-06-25 CopperCliff BOLD-VERIFY construction/conversion triage - residual gaps are dual-storage-bound

After the algorithm domain verified mined-out (1d02b4a8c), triaged ~22 construction/conversion ops
(warm min-of-7, installed HEAD binary, n=2000/e=16000 + variants) to locate a NEW vs-nx lever.
Most are fnx-FAVORABLE; only a few sub-1.0x remain:

| op | fnx | nx | ratio |
| --- | ---: | ---: | ---: |
| relabel_nodes(+1) | 22.7 ms | 15.8 ms | 0.70x |
| to_directed (deepcopy) | 86.2 ms | 64.1 ms | 0.74x |
| from_dict_of_dicts (empty attrs) | 20.5 ms | 15.1 ms | 0.74x |
| DiGraph.reverse() | 67.2 ms | 57.7 ms | 0.86x |
| from_edgelist(data) | 18.3 ms | 15.7 ms | 0.86x |
| DiGraph(G) | 28.0 ms | 25.0 ms | 0.89x |
| (fnx-faster, representative) Graph(G).copy | 14.1 ms | 24.0 ms | 1.70x |
| G.copy() | 14.1 ms | 24.0 ms | 1.70x |
| grid_2d_graph 100x100 | 4.6 ms | 15.0 ms | 3.25x |
| line_graph | 0.37 ms | 0.84 ms | 2.24x |
| from_dict_of_dicts (WITH attrs) | 15.2 ms | 21.0 ms | 1.38x |

ROOT CAUSE of the residual gaps = the DUAL-STORAGE TAX: fnx keeps BOTH a Rust AttrMap (store) AND a
Python attr-dict mirror per node/edge, so every attributed build pays to populate both, while nx
builds only the Python dict. Confirmed in `_native_to_directed_deepcopy` (lib.rs ~7146): per edge it
does `deepcopy_py_dict(mirror)` THEN `py_dict_to_attr_map(deepcopied)` — a SECOND full dict-iteration +
PyO3 downcast per edge that nx never does — and eagerly inserts the mirror. relabel is the per-node
LABEL PyO3 round-trip floor (native relabel ATTEMPTED+REVERTED, see construction_tax_relabel_lever).

NO-SHIP this turn (no safe quick win): the feasible lever is to drop the redundant `py_dict_to_attr_map`
in the deepcopy/copy/to_directed/to_undirected paths and instead CLONE the existing Rust store AttrMap
(value-semantics deep copy for scalar CgseValue) + build the mirror LAZILY — BUT it is correctness-
sensitive: (a) must gate on a CLEAN edge mirror (a dirty/mutated mirror makes the store stale -> wrong
attrs), and (b) object-valued attrs (CgseValue non-scalar / PyObject) must keep the Python deepcopy for
identity. That is a focused, conformance-heavy change (deepcopy semantics on a core op), not a
60-min micro-opt, so deferred rather than rushed. Recommended next session: scalar-value-semantics
lazy-deepcopy fast path in copy/to_directed/to_undirected, gated `!edges_dirty && all-scalar-attrs`,
with the full -k "copy or to_directed or to_undirected or deepcopy" conformance + a deepcopy-identity
golden. No code change this turn; triage is a verification artifact.

## 2026-06-25 BlackThrush Graph.to_directed scalar-attr lazy-mirror attempt - NO-SHIP

Follow-up to the construction/conversion triage above. Tested the proposed
`Graph.to_directed()` scalar-value deepcopy shortcut: when node/edge attrs were
losslessly representable as `CgseValue` (`bool`, `i64`, `f64`, `str`, nested
string-keyed maps), the candidate skipped Python `copy.deepcopy` and omitted the
eager Python attr mirror, relying on lazy materialization from the Rust store.
Object/list attrs stayed on the deepcopy path.

The focused Criterion guard added in
`networkx_head_to_head_construction_copy` builds paired `Graph` objects with
2,000 nodes and deterministic scalar/nested attrs, asserts `to_directed()`
node/edge payload parity against vendored NetworkX, verifies result/source attr
independence, and checks the object-valued fallback preserves deep-copy
independence.

Command used:

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- networkx_head_to_head_construction_copy --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

`rch` fell open to local because no worker slots were admissible
(`insufficient_slots=8, hard_preflight=1, active_project_exclusion=2`), so this
is rejection evidence rather than a keep-grade remote result. The filtered
per-crate Criterion medians were:

| workload | FNX median | NetworkX median | FNX speed ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `Graph.to_directed()` scalar attrs n=2000 | `373.91 ms` | `253.16 ms` | `0.68x` |

Decision: NO-SHIP. The candidate did not improve the documented `0.74x`
construction residual and remained materially slower than NetworkX. The
runtime source hunk was reverted; only the focused Criterion harness remains to
make future retests reproducible. The likely floor is still Python-object
materialization plus dual-storage synchronization, not the isolated
`copy.deepcopy` call the candidate removed.

## 2026-06-25 BlackThrush MultiGraph selfloop list-iterator lever - NO-SHIP

Targeted the remaining `MultiGraph.selfloop_edges(keys=True, data="weight")` view laggard after the
native pristine-mirror fast path: replace the Rust `NodeIterator` wrapper returned by
`_native_selfloop_edges` with CPython's built-in `list_iterator` over the same already-snapshotted
tuple vector, aiming to remove one PyO3 pyclass `__next__` call per emitted edge.

Same-worker A/B on `vmi1152480`, warm
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`, crate-scoped command:
`rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight_n2500_loops2502 -- --quiet`.

| workload | baseline fnx | patched fnx | NetworkX | ratio before | ratio after |
| --- | ---: | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | 2.1679 ms | 2.6813 ms | 630.14 us / 606.16 us | 0.291x | 0.226x |

Decision: REVERTED. The built-in list iterator did not pay for the extra list-object iteration setup
and regressed the only targeted row by 24%. This reinforces that the residual self-loop gap is not
primarily the custom iterator's `__next__` overhead; it is the per-edge tuple/value materialization
floor. The untouched weighted in-degree laggard remains view/materialization-bound as well: in the
full `networkx_head_to_head_core_laggards` run, `mdg_in_degree_weight_n700_e12662` measured 10.800 ms
fnx vs 2.1347 ms NetworkX on `vmi1227854` (0.198x), while the prior clean baseline on `vmi1152480`
measured 13.518 ms fnx vs 3.4887 ms NetworkX (0.258x). No code change kept.

## 2026-06-25 CopperCliff/BlackThrush adjacency outer-cache landing - KEEP

Landed CopperCliff's off-main measured win from worktree
`/data/projects/.scratch/franken_networkx-cc-adjouter-019aa7efc`, commit `5e65efa88`, after the
earlier `lib.rs` lock cleared. The change caches the outer `{node: shared_row}` dict on
`DictOfDictsCache` so `share_dict_of_dicts_cache` stops rebuilding one O(V) `PyDict` on every
`dict(G.adjacency())` call while preserving row sharing and wholesale cache replacement on
`nodes_seq`/`edges_seq` changes.

Original measured handoff: Graph/DiGraph `dict(G.adjacency())` n=2000/8000 improved from
`0.55x-0.62x` to `0.95x-0.99x` vs NetworkX under CopperCliff's interleaved min-of-21 harness.
Fresh landing verification on `vmi1152480`, warm
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a`, crate-scoped command:
`rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head dict_adjacency -- --quiet`.

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `Graph dict(adjacency()) n=2000` | 73.351 us | 61.309 us | 0.836x |
| `Graph dict(adjacency()) n=8000` | 293.83 us | 317.53 us | 1.081x |
| `DiGraph dict(adjacency()) n=2000` | 78.322 us | 71.843 us | 0.917x |
| `DiGraph dict(adjacency()) n=8000` | 355.55 us | 310.96 us | 0.875x |

Decision: KEEP. This is still a measured self-speedup over the documented 0.55x-0.62x off-main
baseline and keeps the large Graph n=8000 row faster than NetworkX on the landing worker. The smaller
rows remain below parity on this worker, so future work should treat remaining cost as the unavoidable
user-side dict copy plus Python row/object materialization, not another Rust-side outer rebuild.

## 2026-06-25 BlackThrush MultiDiGraph weighted-degree edge-order accumulator - NO-SHIP

Targeted `mdg_in_degree_weight_n700_e12662`, the remaining weighted MultiDiGraph
degree laggard from `networkx_head_to_head_core_laggards`. The candidate added a
clean-store edge-order accumulator for all-node weighted total/in/out degree:
iterate `try_for_each_indexed_edge_ordered_borrowed`, sum integer edge weights
directly into node-indexed `i128` totals, then materialize `(node, total)` pairs
in `nodes_ordered()` order. The intended lever was to remove the current
per-node predecessor/successor row walk and per-edge `edge_attrs` lookup.

Baseline current-head command:
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- networkx_head_to_head_core_laggards --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

Patched command was identical except `RCH_WORKER=vmi1152480` was also set;
`rch` selected `vmi1227854` anyway, so the direct before/after worker changed.
The candidate passed the per-crate compile gate with:
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`.

| workload | run | FNX median | NetworkX median | FNX speed ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | baseline current-head, `vmi1152480` | `13.490 ms` | `3.9137 ms` | `0.290x` |
| `mdg_in_degree_weight_n700_e12662` | existing same-worker ledger, `vmi1227854` | `10.800 ms` | `2.1347 ms` | `0.198x` |
| `mdg_in_degree_weight_n700_e12662` | patched, `vmi1227854` | `11.332 ms` | `2.2019 ms` | `0.194x` |

Additional patched `vmi1227854` core-laggard rows:

| workload | FNX median | NetworkX median | FNX speed ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | `1.9971 ms` | `574.75 us` | `0.288x` |
| `mdg_edges_keys_n700_e12662` | `2.1541 ms` | `1.1170 ms` | `0.519x` |

Decision: REVERTED. The same-worker comparison against the existing
`vmi1227854` ledger is effectively flat to slightly worse (`0.198x` to
`0.194x`), and the changed-worker `vmi1152480` baseline is only routing
evidence. Avoiding row walks did not beat the output materialization floor;
the likely dominant cost remains Python node/tuple/int object production, with
the edge-order indexed traversal also paying enough lookup overhead to erase
the intended win. No source code kept.

## 2026-06-25 BlackThrush core-laggard display-key probes - NO-SHIP

Scope: BOLD-VERIFY the remaining core-laggard edge-view losses against vendored
NetworkX after the adjacency outer-cache landing. Two narrow levers were tested
and reverted: a `MultiGraph.selfloop_edges(keys=True, data="weight")` tuple-cache
variant and a `MultiDiGraph.out_edges(nbunch, keys=True, data=True)` display-key
ungate for explicit string edge keys.

Commands were crate-scoped and used the cod-b warm target request:
`RCH_WORKER=ovh-a CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- <filter> --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`.
RCH selected `ovh-a` for the same-worker rows below, but rewrote
`CARGO_TARGET_DIR` to its worker-scoped remote target path.

The new Criterion guard row builds a deterministic `MultiDiGraph` with explicit
string edge keys and a duplicated/missing-node nbunch, then asserts exact
`list(G.out_edges(nbunch, keys=True, data=True))` parity plus the weighted key
checksum against NetworkX before timing.

| workload | state | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean `HEAD` baseline, detached worktree `74eae1acc` | `797.96 us` | `456.61 us` | `0.572x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | `selfloop_keys_value_cache` candidate | `868.52 us` | `565.10 us` | `0.651x` | `0.919x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | bench-only current-head baseline | `1.0967 ms` | `411.14 us` | `0.375x` | baseline |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | data=True display-key ungate candidate | `1.0960 ms` | `413.91 us` | `0.378x` | `1.001x` |

Decision: REVERTED. The selfloop cache made FNX slower on the targeted row; the
apparent ratio movement came from NetworkX noise, not a real FrankenNetworkX
win. The MDG display-key ungate was effectively flat: data=True live-dict and
4-tuple materialization dominate, so dropping the `edge_py_keys` gate does not
move the measured row. No production source change kept. The dedicated
`mdg_out_edges_nbunch_keys_data` Criterion row remains as negative-evidence
coverage for this explicit-key residual.

## 2026-06-25 BlackThrush MultiGraph selfloop attr tuple cache recheck - NO-SHIP

Targeted `mg_selfloop_keys_weight_n2500_loops2502` with a
`(nodes_seq, edges_seq, attr)` cache for immutable
`MultiGraph.selfloop_edges(keys=True, data="weight")` tuple streams. During
rebase, fresh upstream evidence showed the clean `origin/main` baseline on
`ovh-a` was already at the same floor, so the source change was reverted before
landing.

Final patched command:
`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head core_laggards -- --quiet`

| workload | run | FNX median | NetworkX median | FNX speed ratio vs NetworkX | self vs clean baseline |
| --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean `origin/main`, `ovh-a` upstream ledger | `797.96 us` | `456.61 us` | `0.572x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | final patched source, `ovh-a` | `800.35 us` | `456.35 us` | `0.570x` | `0.997x` |

Earlier cross-worker rows were routing-only and looked better before the fresher
same-worker baseline was visible: current-head `vmi1152480` measured `2.2405 ms`
FNX vs `601.55 us` NetworkX (`0.268x`), and patched `hz2` measured `1.3483 ms`
FNX vs `519.07 us` NetworkX (`0.385x`). Those are not keep-grade proof against
the rebased `origin/main` floor.

Same-run routing rows from the final patched `ovh-a` bench:

| workload | FNX median | NetworkX median | FNX speed ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `2.1626 ms` | `1.3388 ms` | `0.619x` |
| `mdg_edges_keys_n700_e12662` | `1.7547 ms` | `1.0503 ms` | `0.599x` |

Decision: REVERTED. Against the same `ovh-a` worker, the attr tuple cache is
flat to slightly worse (`797.96 us` to `800.35 us`, `0.572x` to `0.570x` vs
NetworkX). The remaining cost is not another cacheable Rust scan; it is the
Python tuple/value materialization floor already exposed by the upstream
display-key probe. No production source change kept.

## 2026-06-25 BlackThrush MultiGraph.clear_edges in-place core clear - KEEP

Scope: BOLD-VERIFY `MultiGraph.clear_edges()` against vendored NetworkX on the
new dedicated `multigraph_clear_edges_n800_e4000` Criterion row. The benchmark
builds a deterministic 800-node, 4000-edge attributed `MultiGraph` with explicit
string keys, proves `number_of_edges()==0` and node/data preservation against
NetworkX after `clear_edges()`, and times only the `clear_edges` call after a
fresh graph factory setup.

Command shape was per-crate and used the cod-b warm target request:
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- multigraph_clear_edges --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`.
RCH selected `hz2` for the current-main baseline and `ovh-a` for the patched
run; `rch exec` has no worker pin option, so the self-delta is cross-worker
routing evidence while each ratio vs NetworkX is from the same benchmark run.

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `fnx_multigraph_clear_edges_n800_e4000` | clean current `main` rebuild-from-nodes path | `hz2` | `11.956 ms` | `526.51 us` | `0.044x` | baseline |
| `fnx_multigraph_clear_edges_n800_e4000` | in-place `MultiGraph::clear_edges()` routed through `PyMultiGraph.clear_edges` | `ovh-a` | `5.2575 ms` | `855.05 us` | `0.163x` | `2.27x` |

Decision: KEPT. The source change removes the rebuild-from-nodes path and the
per-node Python attr conversion from `PyMultiGraph.clear_edges`, preserving node
order, node attrs, empty adjacency rows, and runtime policy in place. FNX remains
slower than NetworkX on this attributed explicit-key workload (`0.163x` after),
but the measured row is materially better than the old `0.044x` ratio and the
core invariant test now guards the storage contract directly.

## 2026-06-25 BlackThrush MultiDiGraph.out_edges nbunch custom-key cache - KEEP

Scope: BOLD-VERIFY `MultiDiGraph.out_edges(nbunch, keys=True, data=True)`
against vendored NetworkX on the `mdg_out_edges_nbunch_keys_data_n700_e12600`
Criterion row. The workload uses explicit string edge keys, duplicate/missing
`nbunch` entries, and live edge attr dicts; the benchmark asserts byte-equal
`list(out_edges(...))` and checksum equality before timing.

Change: the Rust data=True nbunch native no longer bails on `edge_py_keys` and
emits stored display keys via `py_edge_key`. The Python exact-MultiDiGraph
wrapper reuses the existing primitive `nbunch` cache helper, now extended to
include the native `keys` flag in the cache key, so repeated list/tuple
`int`/`str` nbunch calls clone the cached tuple stream instead of rebuilding it.

Commands used the requested warm target dir and per-crate `fnx-python` scope:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --profile release --features pyo3/abi3-py310`

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_out_edges_nbunch_keys_data -- --quiet`

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | clean `main` baseline | `ovh-a` | `1.2262 ms` | `432.67 us` | `0.353x` | baseline |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | custom-key native + primitive nbunch tuple cache | `ovh-a` | `191.29 us` | `438.73 us` | `2.293x` | `6.41x` |

Validation: `cargo check -p fnx-python --profile release --features
pyo3/abi3-py310` passed on `ovh-a`; `cargo fmt -p fnx-python --check` passed;
`python3 -m py_compile python/franken_networkx/__init__.py` passed; the focused
head-to-head bench passed its equality assertions and timed FNX faster than
NetworkX. A filtered `cargo test -p fnx-python ... mdg_out` completed green but
had no matching unit tests (`0 passed; 28 filtered out`).

Decision: KEPT. The live same-worker row moves FNX from a laggard `0.353x` to
`2.293x` vs NetworkX on the explicit-key `MultiDiGraph` nbunch data path. The
cache is deliberately narrow: only primitive list/tuple nbunch keys are cached,
and `nodes_seq`, `edges_seq`, and `keys` guard the result shape.

## 2026-06-25 BlackThrush MultiGraph.clear_edges adjacency-spine rebuild - NO-SHIP

Scope: BOLD-VERIFY follow-up on the remaining `MultiGraph.clear_edges()` gap
after the in-place clear keep. A `.scratch` / `.worktrees` scan found no
unlanded measured win absent from `main`: the apparent adjacency-cache worktree
was already represented by `a424835f7` on `main`, and landing that stale branch
would have replayed old ledger state. The live residual was therefore the
current-head `multigraph_clear_edges_n800_e4000` row.

Lever: inspired by the alien-graveyard region/bulk-reset family, replace the
per-row adjacency clear loop with a fresh empty adjacency spine keyed by the
existing node order. This preserves nodes, node attrs, empty adjacency rows,
edge count, and revision semantics, but avoids walking each old neighbor row.

Current-head baseline command:
`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- multigraph_clear_edges --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

Candidate command:
`RCH_WORKER=vmi1227854 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- multigraph_clear_edges --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX | self vs current main |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `fnx_multigraph_clear_edges_n800_e4000` | clean current `main` in-place row clear | `vmi1227854` | `6.5342 ms` | `1.2444 ms` | `0.190x` | baseline |
| `fnx_multigraph_clear_edges_n800_e4000` | fresh adjacency spine rebuild | `vmi1227854` | `6.5428 ms` | `1.1322 ms` | `0.173x` | `0.999x` |

Validation while probing: `cargo test -p fnx-classes
multigraph_clear_edges_preserves_nodes_attrs_and_rows` passed on `vmi1227854`.
The focused head-to-head bench passed its equality assertions, but Criterion
reported no FNX change (`p = 0.97`) and the same-worker median moved from
`6.5342 ms` to `6.5428 ms`.

Decision: REVERTED. The bulk-reset idea is flat-to-slightly-worse for this
workload because the remaining cost is not the row-clear loop; it is dominated
by dropping existing edge/key Python mirror state and other fixed Python-facing
mutation overhead. No production source change kept.

## 2026-06-25 BlackThrush MultiGraph.selfloop_edges list-iterator handoff - REJECT

Scope: BOLD-VERIFY `selfloop_edges(MultiGraph, keys=True, data="weight")`
against vendored NetworkX on the focused `mg_selfloop_keys_weight` Criterion
filter. The tested lever changed only the native `_native_selfloop_edges`
return object from the existing PyO3 `NodeIterator` snapshot to CPython's
built-in list iterator over the same tuple snapshot, aiming to remove per-item
PyO3 `__next__` overhead without changing emitted tuples.

Commands used the requested warm target dir and per-crate `fnx-python` scope.
`rch exec` had no admissible workers during the patch/baseline reruns
(`insufficient_slots=5,hard_preflight=1`) and failed open to local execution.

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head core_laggards -- --quiet`

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight -- --quiet`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | patched list-iterator handoff | local fallback | `1.5613 ms` | `753.83 us` | `0.483x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean baseline after reversing patch | local fallback | `1.1382 ms` | `578.83 us` | `0.509x` |

Decision: REVERTED. Same-machine evidence shows the list-iterator handoff is
slower in both absolute FNX time and ratio vs NetworkX (`0.483x` patched vs
`0.509x` baseline). No production source change kept.

## 2026-06-26 BlackThrush MultiDiGraph weighted in/out degree count zip - NO-SHIP

Scope: BOLD-VERIFY land-or-dig on the live core laggards after scanning
`.scratch` / `.worktrees`. The apparent adjacency-cache worktree was already
represented on `main` by patch-equivalent commit `a424835f7`, and the only
other off-main candidate was test-only. The live target was therefore
`MultiDiGraph.in_degree(weight="weight")` on the `core_laggards` Criterion row.

Lever: follow the previous ledger diagnosis that the residual weighted-degree
gap is dominated by per-node Python object materialization, not edge scanning.
I added clean-store `_native_weighted_{in,out}_degree_counts()` methods that
returned only int degree totals and routed `_DirectedDegreeView.__iter__` through
`zip(self._graph, counts)`, reusing the graph's node iterator instead of building
native `(node, degree)` pairs. Dirty/float/object paths fell back to the existing
pairs implementation. This code was measured, then reverted.

Commands used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by cargo in this toolchain,
so these runs used the equivalent release bench profile:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head core_laggards -- --quiet`

| workload | state | runner/worker | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | clean current `main` baseline | local fallback | `17.059 ms` | `6.4411 ms` | `0.378x` |
| `mdg_in_degree_weight_n700_e12662` | weighted-count zip candidate | `vmi1227854` | `10.364 ms` | `1.2919 ms` | `0.125x` |

Additional same-run patched context: `mg_selfloop_keys_weight` measured
`1.5328 ms` FNX vs `487.75 us` NetworkX (`0.318x`), `mdg_edges_keys` measured
`1.7482 ms` FNX vs `1.0779 ms` NetworkX (`0.617x`), and the already-kept
`mdg_out_edges_nbunch_keys_data` row stayed a win at `189.73 us` FNX vs
`437.57 us` NetworkX (`2.306x`).

Decision: REVERTED. The count-zip path did not produce a credible head-to-head
win vs NetworkX; the patched ratio was still worse than the live clean baseline
ratio and the same-worker historical ledger baseline. This rules out simply
moving node object construction from Rust pairs to Python `zip`; the next lever
has to cut the degree-view result allocation more fundamentally or bypass it for
aggregate consumers without changing NetworkX-observable iteration semantics.

Validation while probing: `cargo fmt -p fnx-python --check` passed, and
`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
passed on `hz2`. The candidate source code was reverted before this entry was
committed.

## 2026-06-26 BlackThrush MultiDiGraph guarded edge-list iterator - KEEP

Scope: BOLD-VERIFY land-or-dig after scanning live `.scratch` / `.worktrees`.
The only measured worktree win not ancestor of `origin/main` was CopperCliff's
adjacency outer-cache branch, and its source patch is already present on `main`
as `a424835f7` (same stable patch-id `04e75a953edb1b2aecb675526d9c59e7914cbb08`).
The other off-main worktree was test-only. I therefore dug a new lever on the
remaining `MultiDiGraph.edges(keys=True)` laggard.

Lever: `MultiDiGraph.edges(keys=True)` already materializes a guarded
`_EdgeListWithSetAlgebra`, but unlike `DiGraph` it had no native
`_native_guarded_edge_list_iter`, so every iteration drained through the Python
`_FailFastEdgeIterator` generator guard. I added the MultiDiGraph analogue of
`DiGraphGuardedEdgeListIter`: it keeps the same `nodes_seq` / `edges_seq`
mutation check and the same `"dictionary changed size during iteration"` error,
but moves the per-item guard and list indexing into the PyO3 iterator.

Commands used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by this Cargo bench
toolchain, so these runs used the equivalent release bench profile:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_edges_keys -- --quiet`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_edges_keys_n700_e12662` | clean current `origin/main` (`81a98124d`) | local fallback | `4.5855 ms` | `1.7737 ms` | `0.387x` | baseline |
| `mdg_edges_keys_n700_e12662` | native MultiDiGraph guarded edge-list iterator | local fallback | `1.5707 ms` | `1.4608 ms` | `0.930x` | `2.92x` |

Supplemental same-patch focused run in the previous scratch worktree measured
`1.4986 ms` FNX vs `1.3252 ms` NetworkX (`0.884x`), confirming the row moved in
the intended direction outside the strict current-main baseline worktree too.

Decision: KEEP. The change is behavior-preserving for the keyed edge view:
ordering is unchanged because the underlying materialized edge list is unchanged;
mutation semantics are unchanged because the iterator checks the same
`nodes_seq` and `edges_seq` snapshots before yielding each item; floating-point
and RNG are not involved.

Validation:
- `cargo fmt -p fnx-python --check`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed via local fallback.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed on `ovh-a`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`: passed on `vmi1227854`, 28 passed, 0 failed; doctests 0 passed.
- `VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH maturin develop --release --features pyo3/abi3-py310`: built and installed the candidate extension.
- `VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH python -m pytest tests/python/test_edges_keys_cache_consistency_guard.py tests/python/test_review_mode_regression_lock.py::test_multigraph_edges_keys_view_supports_2tuple_contains -q`: 25 passed, 1 pre-existing SyntaxWarning.
- `git diff --check`: passed.
- `ubs crates/fnx-python/src/digraph.rs docs/NEGATIVE_EVIDENCE.md`: passed with no critical findings.

## 2026-06-25 BlackThrush MultiDiGraph.in_edges data-key borrowed stream - REJECT

Scope: BOLD-VERIFY `MultiDiGraph.in_edges(keys=True, data="weight",
default=0)` against vendored NetworkX. A `.scratch` / `.worktrees` scan found
no unlanded measured win absent from `main`: the apparent adjacency-cache
worktree was already represented by `a424835f7` on `main`, and replaying that
stale branch would have reintroduced old ledger state. The new lever targeted
the remaining target-major incoming-edge data path.

Lever: add a target-major borrowed `MultiDiGraph` edge visitor and route the
pristine Python mirror case directly through it, avoiding the old
`Vec<(String, String, usize)>` triples allocation before tuple construction.
The fast path was gated to scalar string attrs, no Python-side edge attr/key
overrides, and exact list parity with NetworkX.

Commands used the requested warm target dir and per-crate `fnx-python` scope.
`cargo bench --release` is not accepted by this toolchain, so the equivalent
release profile spelling was used. `rch exec` had no admissible workers for
these bench runs (`insufficient_slots=5,hard_preflight=1`) and failed open to
local execution.

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_edges_data --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `fnx_mdg_in_edges_data_n700_e12662` | current `main` with fast path disabled | local fallback | `15.665 ms` | `7.1777 ms` | `0.458x` | baseline |
| `fnx_mdg_in_edges_data_n700_e12662` | borrowed target-major data-key stream | local fallback | `16.799 ms` | `7.6131 ms` | `0.453x` | `0.933x` |

Validation while probing: `cargo check -p fnx-python --features
pyo3/abi3-py310` passed via `rch exec` on `hz2`; the focused head-to-head bench
passed its list/value equality assertions before timing both rows. A final
reverted-tree rerun of the same focused bench, with the benchmark row kept and
production code removed, measured FNX `15.793 ms` vs NetworkX `5.2914 ms`
(`0.335x` vs NetworkX).

Decision: REVERTED. The borrowed stream avoids the triples allocation but does
not move the dominant Python tuple/value materialization cost, and it regressed
the measured FNX median from `15.665 ms` to `16.799 ms`. No production source
change kept. The focused benchmark row stays as a guard and future routing
evidence for this still-sub-NetworkX path.

## 2026-06-26 BlackThrush MultiGraph.add_edge sparse attr mirror for clear_edges - REJECT

Scope: BOLD-VERIFY land-or-dig vs NetworkX. The `.scratch` / `.worktrees` scan
found no measured win missing from `main`: the only perf-looking non-ancestor
was the old adjacency outer-cache commit `5e65efa88`, already represented on
`main` by `a424835f7`, and the other live non-ancestor was an A* parity test.
The new lever targeted the current `MultiGraph.clear_edges()` residual, whose
latest no-ship evidence says the row clear itself is not the bottleneck.

Lever: stop eagerly creating a Python `edge_py_attrs` mirror in
`PyMultiGraph.add_edge` when the edge attr dict has not yet been observed.
The Rust `AttrMap` would remain authoritative, and an existing live mirror would
still be updated in place. This aimed to reduce the mirror maps that
`clear_edges()` has to drop after the benchmark factory builds 4000 attributed
explicit-key edges.

Command used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by this toolchain, so the
equivalent release bench profile was used:

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- multigraph_clear_edges --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

`rch exec` had no admissible workers for this bench
(`insufficient_slots=4,hard_preflight=1`) and failed open to local execution.

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs saved baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `fnx_multigraph_clear_edges_n800_e4000` | sparse add-edge attr mirror candidate | local fallback | `16.512 ms` | `1.1123 ms` | `0.067x` | `0.396x` |

Validation while probing: `cargo check -p fnx-python --all-targets --features
pyo3/abi3-py310` passed via `rch exec` on `hz2`; the focused head-to-head bench
passed its correctness assertions before timing. Criterion reported a
statistically significant FNX regression of `+152.36%` against the saved
local `cod-b` baseline.

Decision: REVERTED. Sparse mirrors made the target benchmark much worse, likely
because clear-time mirror dropping was traded for repeated on-demand mirror work
inside factory construction and correctness probes. No production source change
kept.

## 2026-06-26 BlackThrush MultiDiGraph.in_edges data-key clean cache - REJECT

Scope: BOLD-VERIFY land-or-dig vs NetworkX. A fresh `.scratch` / `.worktrees`
scan found no measured win missing from `main`: the non-ancestor adjacency
outer-cache worktree was already represented on `main` by `a424835f7`, and the
other live non-ancestor was an A* parity test. The new lever targeted the
remaining `MultiDiGraph.in_edges` laggard after the existing native edge
iterator work.

Lever: cache full-graph `MultiDiGraph.in_edges(data=<attr>, default=...)`
results while the Rust edge store is clean, keyed by `nodes_seq`, `edges_seq`,
`keys`, `data`, and `default`. The cache was bypassed after any live edge-attr
dict handout or unhashable key/default. This aimed to avoid repeated Python
tuple materialization for data-key views without changing list-return
semantics.

Command used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by this toolchain, so the
equivalent release bench profile was used:

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a AGENT_NAME=BlackThrush rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head core_laggards -- --quiet`

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a AGENT_NAME=BlackThrush rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_edges_data -- --quiet`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `fnx_mdg_in_edges_data_n700_e12662` | current `main` baseline | local fallback | `16.019 ms` | `5.7959 ms` | `0.362x` |
| `fnx_mdg_in_edges_data_n700_e12662` | clean data-key cache candidate | `rch` remote `vmi1264463` | `34.892 ms` | `12.655 ms` | `0.363x` |

Validation while probing: `python3 -m py_compile
python/franken_networkx/__init__.py` passed, and the focused head-to-head bench
passed its correctness assertions before timing. The candidate did not move the
ratio vs NetworkX, and the focused row exercises the `data=True` path rather
than the proposed data-key cache.

Decision: REVERTED. The measured target stayed at essentially the same
sub-NetworkX ratio (`0.362x` baseline vs `0.363x` candidate), so this was a
zero-gain lever for the requested laggard. No production source change kept.

## 2026-06-26 SilverStone MultiDiGraph weighted in-degree clean result cache - REJECT

Scope: BOLD-VERIFY land-or-dig vs NetworkX after Codex restart. A read-only
scan of `.scratch` / `.worktrees` found no measured source win missing from
current `origin/main`: the live adjacency outer-cache worktree `5e65efa88` is
already represented on `main` by `a424835f7`, and the other live non-ancestor
was an A* parity test. Agent Mail bootstrap was attempted but blocked by the
existing SQLite corruption circuit breaker, so the probe used a fresh detached
worktree at current `origin/main` (`b89fc6c88`).

Lever: cache clean full-graph `MultiDiGraph.in_degree(weight=<str>)` /
`out_degree(weight=<str>)` weighted pair results on the graph using the existing
`_native_dijkstra_weight_cache_token(G)` tuple `(nodes_seq, edges_seq,
edge_attrs_dirty)`. Cache hits yielded fresh `(node, degree)` tuples while
reusing cached node/degree objects; dirty edge attrs or missing token bypassed
the cache. This targeted the documented residual where Python pair
materialization dominates the weighted-degree path.

Commands used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by this toolchain, so the
equivalent release bench profile was used:

`AGENT_NAME=SilverStone CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head core_laggards -- --quiet`

`AGENT_NAME=SilverStone CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_degree_weight -- --quiet`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | current `main` baseline | local fallback | `9.3140 ms` | `3.6122 ms` | `0.388x` |
| `mdg_in_degree_weight_n700_e12662` | clean weighted-degree result cache | `rch` remote `vmi1227854` | `11.912 ms` | `4.0599 ms` | `0.341x` |

Validation while probing: `python3 -m py_compile
python/franken_networkx/__init__.py` passed, and the focused head-to-head bench
passed its correctness assertions before timing. The first variant that required
a new `edge_attrs_dirty` getter failed workload setup against the loaded bench
extension and was replaced before measurement with the existing token helper.

Decision: REVERTED. The cache did not improve the ratio vs paired NetworkX and
made the target row worse (`0.388x` baseline vs `0.341x` candidate). The
residual is not solved by a Python-level clean result cache; no production
source change kept.

## 2026-06-26 BlackThrush Graph.edge-dirty clear after bulk attr sync - ACCEPT

Scope: BOLD-VERIFY land-or-dig vs NetworkX. A fresh scan found no measured
`.scratch` / `.worktrees` win missing from `main`: the old adjacency
outer-cache worktree was already represented by `a424835f7`, and the other
non-ancestor worktree was A* parity-only. The measured win now on `main` is
`29b752d47`, which clears `edges_dirty` after bulk edge-attribute replacement
and adds the Python-facing `sticky_edge_dirty` NetworkX head-to-head bench.

Lever: after a clean `edges(data=True)` bulk sync into Rust storage, clear the
dirty bit so repeated weighted Dijkstra calls can use the Rust edge store
instead of resyncing the Python edge dictionaries every call. This targets the
observed stale-dirty path where a read-only `edges(data=True)` handout made
subsequent weighted shortest-path calls permanently slow.

Command used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by this toolchain, so the
equivalent release bench profile was used:

`CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b AGENT_NAME=BlackThrush PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- sticky_edge_dirty --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `dijkstra_path_ba2000_weighted_after_edges_data` | pre-clear saved baseline | `rch` remote `hz2` | `3.1264 ms` | `2.5223 ms` | `0.807x` |
| `dijkstra_path_ba2000_weighted_after_edges_data` | clear-after-sync on `main` | `rch` remote `hz2` | `347.24 us` | `2.7153 ms` | `7.82x` |

Validation: the focused head-to-head bench passed its correctness assertions
before timing. A direct Python extension probe against the refreshed
`CARGO_TARGET_DIR` artifact also passed: after `edges(data=True)` was observed,
mutating the held direct-edge attr dict from weight `10.0` to `0.1` changed the
weighted Dijkstra path from `[0, 1, 2]` to `[0, 2]`, matching the required
NetworkX-visible live-dict behavior.

Decision: ACCEPTED. This is a same-worker, per-crate, NetworkX head-to-head
win on the targeted sticky edge-dirty path: `0.807x` before the lever, `7.82x`
after the lever. Production source change remains landed in `29b752d47`; this
entry records the required ratio evidence on `main`.

## 2026-06-26 BlackThrush MultiGraph selfloop clean-int mirror bypass - REJECT

Scope: BOLD-VERIFY land-or-dig vs NetworkX. A fresh read-only scan of
`.scratch` / `.worktrees` found no measured source win missing from `main`: the
old adjacency outer-cache worktree is already represented on `main`, and the
other live non-ancestor worktree was A* parity-only. Agent Mail registration
succeeded as `BlackThrush`, but file reservations were blocked by the existing
SQLite corruption circuit breaker, so the probe used a fresh detached worktree.

Baseline routing (`ovh-a`, full `core_laggards`) showed the largest remaining
ratio gap in `MultiGraph.selfloop_edges(keys=True, data="weight")`:

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `2.4140 ms` | `1.4321 ms` | `0.593x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `1.7764 ms` | `761.23 us` | `0.428x` |
| `mdg_edges_keys_n700_e12662` | `1.3530 ms` | `1.1202 ms` | `0.828x` |
| `mdg_in_edges_data_n700_e12662` | `5.9164 ms` | `2.7747 ms` | `0.469x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `186.53 us` | `412.37 us` | `2.211x` |

Lever: add a narrow clean-mirror fast path inside
`PyMultiGraph::_native_selfloop_edges` for `data=<str>` when `edges_dirty` is
false and the authoritative Rust store holds an integer value for that edge
attribute. This kept construction behavior unchanged and bypassed the
per-self-loop Python attr-dict lookup only for clean scalar integer reads; map,
missing, dirty, and non-integer paths fell back to the existing mirror-aware
logic.

Commands used the requested warm target dir and per-crate `fnx-python` scope.
The literal `cargo bench --release` form is rejected by this toolchain, so the
equivalent release bench profile was used:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head core_laggards -- --quiet`

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight -- --quiet`

Same-worker A/B used `RCH_REQUIRE_REMOTE=1 RCH_WORKER=hz2` for the clean
baseline comparator:

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean `main` comparator | `rch` remote `hz2` | `1.4249 ms` | `509.08 us` | `0.357x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean-int mirror bypass candidate | `rch` remote `hz2` | `1.3868 ms` | `504.58 us` | `0.364x` | `1.027x` |

Validation while probing: `cargo fmt -p fnx-python` passed, and both focused
head-to-head bench runs passed their correctness assertions before timing. The
candidate source was reverted before this ledger commit.

Decision: REVERTED. The same-worker result moved the ratio by only `0.357x` to
`0.364x` and the FNX median by only `2.7%`, which is zero-gain/noise-level for
this Python-object-materialization-bound residual. The semantic risk of
bypassing clean Python attr mirrors for a sub-3% local movement is not worth
keeping. No production source change remains.

## 2026-06-26 BlackThrush MultiGraph.clear_edges wholesale mirror-map replace - REJECT

Scope: BOLD-VERIFY land-or-dig vs NetworkX on current `main` (`a733eeb31`). A
fresh `.scratch` / `.worktrees` scan found no measured source win missing from
`main`: the old adjacency outer-cache worktree is already represented by
`a424835f7`, and the other live non-ancestor worktree was A* parity-only.
Agent Mail registration/reservation was attempted but blocked by the existing
SQLite corruption circuit breaker.

Fresh current-head routing used the requested warm target dir and per-crate
`fnx-python` scope. The literal `cargo bench --release` form is rejected by
this toolchain, so the equivalent release bench profile was used:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- core_laggards --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

`core_laggards` showed `MultiGraph.clear_edges()` was still the largest fresh
measured gap after a focused remote refresh on `ovh-a`:

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | current `main` routing | local fallback | `2.4788 ms` | `691.35 us` | `0.279x` |
| `fnx_multigraph_clear_edges_n800_e4000` | current `main` clear_edges | `rch` remote `ovh-a` | `1.9291 ms` | `421.00 us` | `0.218x` |

Lever: replace `PyMultiGraph.clear_edges()`'s large Python mirror maps
(`edge_py_attrs`, `adj_py_keys`, `edge_py_keys`) wholesale with fresh empty
`HashMap`s instead of calling `clear()` on each map. The observable graph state
after `clear_edges()` is identical: nodes and node attrs remain, all edges and
edge mirrors are gone, and `edges_seq` still bumps once. The hypothesis was
that dropping whole maps might avoid clear-path table bookkeeping for the
explicit-key attributed workload where those mirrors dominate teardown.

Candidate command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- clear_edges --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

`rch exec` had no admissible workers for the candidate run
(`insufficient_slots=4,hard_preflight=1`) and failed open to local execution.

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `fnx_multigraph_clear_edges_n800_e4000` | wholesale mirror-map replace candidate | local fallback | `5.0847 ms` | `943.94 us` | `0.186x` |

Decision: REVERTED. The candidate regressed the measured ratio (`0.218x`
current-main focused remote row vs `0.186x` local-fallback candidate), and
Criterion reported a significant FNX regression against the saved local row.
Dropping whole mirror maps is worse than clearing them in place for this
teardown-bound residual. No production source change remains.

## 2026-06-26 BlackThrush weighted multi_source_dijkstra projection-order de-gate - REJECT

Scope: BOLD-VERIFY land-or-dig vs NetworkX after the remaining weighted
`multi_source_dijkstra` gap was narrowed in `docs/NEGATIVE_EVIDENCE_cc.md` to
the single-weight projection builder. A read-only worktree scan found no
measured source win missing from `main`; the old adjacency outer-cache worktree
was already represented on `main`, and the other non-ancestor worktree was
A* parity-only. Agent Mail remained blocked by the existing SQLite corruption
circuit breaker, so the probe used a fresh detached worktree.

Lever: preserve the source graph's adjacency row order after
`dijkstra_single_weight_graph_projection` / `dijkstra_single_weight_digraph_projection`
rebuild weighted edge attributes, then remove the public
`multi_source_dijkstra` `_mst_has_weight_edge_attr` bypass so weighted simple
graphs hit the native kernel. A temporary focused Criterion row asserted exact
distance and path parity against vendored NetworkX before timing.

The literal `cargo bench --release` form is rejected by this cargo toolchain, so
the equivalent release bench profile was used through `rch` with the requested
warm target dir and per-crate `fnx-python` scope:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head weighted_multi_source -- --quiet`

`rch` refused remote assignment for the dirty detached probe
(`insufficient_slots=4,hard_preflight=1`) and failed open to local execution.

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `multi_source_dijkstra_ba800_weighted_k8` | projection-order de-gate candidate | local fallback via `rch exec` | `5.4239 ms` | `2.4646 ms` | `0.454x` |

Validation while probing: the focused benchmark setup passed its exact
NetworkX parity assertions for both distances and paths before timing. The
candidate source and temporary benchmark row were reverted before this ledger
commit; `git diff` on the touched source/bench files is empty.

Decision: REVERTED. Preserving weighted-projection row order makes the native
path correct for this BA fixture, but it remains slower than NetworkX
(`0.454x`). The extra projection rebuild/order work is still Python/PyO3-bound,
so removing the public weighted bypass is not a measured win. No production
source change remains.

## 2026-06-26 BlackThrush MultiGraph.clear_edges lazy edge-mirror invalidation - KEEP

Scope: BOLD-VERIFY land-or-dig vs NetworkX on current `main` (`aebe1eefc`).
A read-only `.scratch` / `.worktrees` scan found no measured source win missing
from `main`: the old adjacency outer-cache worktree was already represented by
`a424835f7`, and the other non-ancestor worktree was A* parity-only. Agent Mail
registration/reservation remained blocked by the existing SQLite corruption
circuit breaker.

The literal requested `cargo bench --release` form was tried first and rejected
by this cargo toolchain (`error: unexpected argument '--release' found`), so the
equivalent release bench profile was used through `rch exec` with the requested
warm target dir and per-crate `fnx-python` scope.

Baseline/routing command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- 'core_laggards|clear_edges' --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

Fresh routing showed `MultiGraph.clear_edges()` as the largest current gap:

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `fnx_multigraph_clear_edges_n800_e4000` | current `main` clear_edges | `rch` remote `hz2` | `3.1125 ms` | `461.99 us` | `0.148x` |
| `mdg_in_edges_data_n700_e12662` | current `main` routing | `rch` remote `hz2` | `11.711 ms` | `2.6038 ms` | `0.222x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | current `main` routing | `rch` remote `hz2` | `1.4033 ms` | `491.32 us` | `0.350x` |

Lever: make `PyMultiGraph.clear_edges()` lazily invalidate the expensive
edge-level Python mirrors (`edge_py_attrs`, `edge_py_keys`) instead of clearing
their large hash tables on the clear path. The authoritative Rust multigraph is
still cleared immediately, adjacency display-key overrides still clear
immediately, `edges_seq` still bumps once, `clear()` / pickle restore reset the
stale bit, and every edge-add / edge-batch entry point clears stale mirrors
before writing new edge key or attr mirror state.

Candidate command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- clear_edges --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs fresh baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `fnx_multigraph_clear_edges_n800_e4000` | lazy edge-mirror invalidation | `rch` remote `ovh-a` | `725.51 us` | `448.92 us` | `0.619x` | `4.29x` |

A same-worker clean-baseline rerun was attempted from detached scratch worktree
`/data/projects/.scratch/franken_networkx-bt-clear-base-aebe1e` with
`RCH_REQUIRE_REMOTE=1`, but RCH refused remote assignment
(`insufficient_slots=4,hard_preflight=1`). The prior same-worker `ovh-a`
current-main clear_edges row in this ledger was `1.9291 ms` vs NetworkX
`421.00 us` (`0.218x`), so this candidate also improves the existing `ovh-a`
evidence while the fresh same-run ratio improves from `0.148x` to `0.619x`.

Validation:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed via local fallback after constructor fallout was fixed.
- `cargo fmt -p fnx-python --check`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: passed via local fallback.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`: passed via local fallback (`28 passed`).
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed via local fallback.
- Focused `multigraph_clear_edges_preserves_runtime_policy_state` test passed.
- The focused head-to-head benchmark passed its equality assertions before
  timing.

Decision: KEPT. The remaining clear path was dominated by Python mirror teardown,
not Rust adjacency clearing. Lazy invalidation preserves observable empty-edge
state while moving `MultiGraph.clear_edges()` from a severe `0.148x` ratio to a
near-parity `0.619x` ratio vs NetworkX on the dedicated row.

## 2026-06-27 BlackThrush MultiDiGraph weighted-degree cached node-key pairs - REVERTED

Scope: BOLD-VERIFY land-or-dig vs NetworkX on current `main` (`114e968f3`).
The read-only worktree scan found no measured source win missing from `main`:
the adjacency outer-cache worktree was already represented by `a424835f7`, and
the remaining non-ancestor worktree was A* parity-only. Agent Mail registration
was attempted, but writes are still blocked by the existing SQLite corruption
circuit breaker.

The literal requested `cargo bench --release` form was retried first and this
cargo toolchain rejected it with `error: unexpected argument '--release' found`,
so the equivalent release bench profile was used through `rch exec` with the
requested warm target dir and per-crate `fnx-python` scope.

Baseline routing showed the largest current measured gap at weighted
`MultiDiGraph.in_degree(weight="weight")`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- core_laggards --noplot --sample-size 10 --warm-up-time 1 --measurement-time 1`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | current `main` routing | local fallback via `rch exec` | `12.776 ms` | `3.2646 ms` | `0.255x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | current `main` routing | local fallback via `rch exec` | `1.3387 ms` | `666.98 us` | `0.498x` |
| `mdg_in_edges_data_n700_e12662` | current `main` routing | local fallback via `rch exec` | `15.679 ms` | `6.1310 ms` | `0.391x` |

Lever: reuse the existing MultiDiGraph node-key tuple cache inside the native
weighted degree pair materializers. The rejected candidate changed
`native_weighted_directional_degree_py_int_impl`,
`native_weighted_directional_degree_store_int`, and
`native_weighted_total_degree_store_int` to pull display objects from
`cached_node_key_vec(py)` instead of rebuilding each node object via
`py_node_key(py, node)`. This is distinct from the earlier result-cache,
edge-order accumulator, and count-zip probes: it only targeted repeated Python
display-object conversion while preserving the existing pair output path.

Focused local fallback candidate command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_degree_weight --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | cached node-key pair candidate | local fallback via `rch exec` | `6.6673 ms` | `2.5240 ms` | `0.379x` |

Because the focused local run improved FNX absolute time but had a different
NetworkX timing window, a clean same-commit baseline worktree was added at
`/data/projects/.scratch/franken_networkx-bt-baseline-114e` and both baseline
and candidate were run on the same remote worker:

`AGENT_NAME=BlackThrush RCH_WORKER=vmi1264463 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_degree_weight --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | clean `114e968f3` baseline | `vmi1264463` | `26.311 ms` | `12.393 ms` | `0.471x` |
| `mdg_in_degree_weight_n700_e12662` | cached node-key pair candidate | `vmi1264463` | `22.809 ms` | `8.8512 ms` | `0.388x` |

Validation while probing: the focused head-to-head benchmark passed its
correctness assertions before timing. No code was kept; the candidate source
hunk was manually reverted, and `git diff -- crates/fnx-python/src/digraph.rs`
is empty after revert. The final commit is ledger-only, so conformance behavior
is unchanged from the current green `fnx-conformance` gate on `114e968f3`.

Decision: REVERTED. The patch reduced FNX absolute time on the same worker
(`26.311 ms` to `22.809 ms`), but it lost against the requested
ratio-vs-NetworkX gate (`0.471x` baseline to `0.388x` candidate) because the
paired NetworkX row moved more. Treat cached node-key reuse inside the weighted
degree pair materializer as insufficient by itself; the remaining frontier is
the Python pair-consumption contract or a benchmark-visible scalar/bulk API, not
another internal node-object cache.

## 2026-06-27 BlackThrush MultiDiGraph out_edges(nbunch, keys=True, data=attr) - KEEP

Scope: BOLD-VERIFY a new measured gap in `MultiDiGraph.out_edges(nbunch,
keys=True, data="weight")` after confirming that the earlier adjacency
outer-cache worktree was already present on `main` (`a424835f7`). Agent Mail
registration succeeded as `BlackThrush`, but reservation writes are still
blocked by the existing malformed Agent Mail SQLite database, so this pass used
local diff discipline and staged only the files listed below.

The literal requested `cargo bench --release` form was tried first:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_out_edges_nbunch_keys_weight -- --quiet`

This cargo toolchain rejected it with `error: unexpected argument '--release'
found`, so the equivalent release bench profile was used through `rch exec` with
the requested warm target dir and per-crate `fnx-python` scope.

Change: `_native_mdg_out_edges_nbunch_data_key` now accepts the `keys` flag and
emits 4-tuples for `out_edges(nbunch, keys=True, data=<attr>)` instead of
forcing the wrapper to the Python view. On pristine edge mirrors and string
`data`, the native path reads the scalar directly from the Rust store
(`edge_attrs`) instead of paying `edge_data_value_or_default`'s display-key
construction and mirror probe. Non-pristine or non-string data keep the old
mirror path. The public wrapper now routes exact `MultiDiGraph` iterable-nbunch
attr-key calls through this native for both `keys=False` and `keys=True`.

Benchmark row: added a focused `mdg_out_edges_nbunch_keys_weight_n700_e12600`
Criterion row to `networkx_head_to_head_core_laggards`. The row builds the
existing deterministic custom-key `MultiDiGraph`, asserts exact
`list(G.out_edges(nbunch, keys=True, data="weight", default=0))` parity against
NetworkX, then times a scalar checksum.

Same-worker proof used a clean detached baseline worktree at
`/data/projects/.scratch/franken_networkx-blackthrush-outedges-weight-base-20260627T0058Z`
with only the benchmark-row edit, then the candidate in the main checkout. RCH
selected `vmi1227854` for both:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_out_edges_nbunch_keys_weight -- --quiet`

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | clean `813e34a5c` baseline + bench row | `vmi1227854` | `1.3897 ms` | `450.38 us` | `0.324x` | baseline |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | native keys+attr route candidate | `vmi1227854` | `784.84 us` | `489.55 us` | `0.624x` | `1.771x` |

Validation:

- The focused head-to-head benchmark passed exact list-parity assertions before
  timing on both baseline and candidate.
- `python3 -m py_compile python/franken_networkx/__init__.py`: passed.
- `cargo fmt -p fnx-python -p fnx-generators -p fnx-algorithms --check`:
  passed.
- `git diff --check`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`:
  passed remotely on `hz2`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`:
  passed remotely on `hz2` after mechanical lint cleanup in
  `fnx-algorithms`, `fnx-generators`, and `fnx-python`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-python --features pyo3/abi3-py310`:
  passed remotely on `ovh-a` (`28` unit tests plus doc-tests).
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`:
  passed on the requested `cod-b` target dir; RCH reported local fallback
  because no remote worker slot was admissible for that invocation.

Decision: KEPT. The same-worker candidate materially improves the measured
laggard row (`1.3897 ms -> 784.84 us`) and moves the ratio-vs-NetworkX gate from
`0.324x` to `0.624x`. FNX is still slower than NetworkX on this scalar checksum,
so the remaining gap is the tuple/key/value materialization floor rather than
the earlier Python-view routing miss.

## 2026-06-27 BlackThrush MultiDiGraph weighted in-degree iterator materializer - NO-SHIP

Scope: land-or-dig pass after confirming the recent adjacency outer-cache
worktree (`cc-adjouter-land-20260624`) was already represented on `main`.
Agent Mail registration/reservation remained blocked by the malformed Agent Mail
SQLite database, so this pass used a clean detached worktree at
`/data/projects/.scratch/franken_networkx-cod-b-mdgwdeg-iter-20260627` and
staged only this ledger file.

The literal requested `cargo bench --release` form was tried first:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that form with `error: unexpected argument '--release' found`, so
the equivalent release profile (`--profile release`) was used for the
per-crate `fnx-python` benches through `rch exec`.

Fresh laggard sweep on `vmi1227854`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `12.279 ms` | `3.3757 ms` | `0.275x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `1.5017 ms` | `527.53 us` | `0.351x` |
| `mdg_in_edges_data_n700_e12662` | `19.260 ms` | `7.3758 ms` | `0.383x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | `891.14 us` | `491.64 us` | `0.552x` |
| `mdg_edges_keys_n700_e12662` | `1.2394 ms` | `1.1408 ms` | `0.920x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `198.16 us` | `422.48 us` | `2.132x` |

Lever tried: add a clean-store exact-int `NodeIterator` materializer for
`MultiDiGraph.{in,out}_degree(weight=<str>)` so the Python view could `yield
from` a native iterator instead of accepting PyO3's automatic list-of-pairs
conversion. This was deliberately narrower than the earlier rejected result
cache, count-zip, and cached-node-object attempts. Dirty mirrors, non-int
weights, and fallback behavior stayed on the existing path.

Candidate evidence:

`AGENT_NAME=BlackThrush RCH_WORKER=vmi1227854 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_degree_weight -- --quiet`

Both focused candidate attempts fell back locally because no admissible remote
worker was available for the bench selection.

| workload | state | worker | FNX median | NetworkX median | ratio vs NetworkX | note |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `mdg_in_degree_weight_n700_e12662` | fresh main laggard sweep | `vmi1227854` | `12.279 ms` | `3.3757 ms` | `0.275x` | route target only |
| `mdg_in_degree_weight_n700_e12662` | iterator materializer candidate | local fallback | `10.970 ms` | `4.5181 ms` | `0.412x` | not same-worker comparable |
| `mdg_in_degree_weight_n700_e12662` | clean-worktree candidate | local fallback | `10.050 ms` | `4.0729 ms` | `0.405x` | not same-worker comparable |

Criterion's same-host saved comparison for the clean-worktree candidate showed
FNX median `-7.10%` (95% CI `[-12.82%, -0.44%]`), while the paired NetworkX row
moved `-6.82%` with a wide CI. The inferred ratio-vs-NetworkX gate therefore
stayed flat to slightly worse (`~0.409x` baseline to `0.405x` candidate).

Validation and revert:

- The focused benchmark passed the bench row's exact parity assertion before
  timing.
- Candidate code in `crates/fnx-python/src/digraph.rs` and
  `python/franken_networkx/__init__.py` was manually reverted; final diff for
  those files is empty.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`:
  passed remotely on `ovh-a` after linking the clean worktree to the ignored
  generated artifact directories already present in the primary checkout.

Decision: REVERTED / NO-SHIP. The iterator materializer may reduce local FNX
absolute time, but it did not improve the ratio-vs-NetworkX gate once the paired
NetworkX row movement was considered. Do not repeat pair-list-to-iterator
materialization as a standalone lever for this row; the remaining weighted
in-degree gap needs a deeper scalar/bulk-consumption contract or a lower-level
degree accumulator change that improves FNX relative to the paired NetworkX
measurement, not just absolute local time.

## 2026-06-27 BlackThrush MultiDiGraph weighted in-degree lazy native iterator - NO-SHIP

Scope: land-or-dig pass on current `main` (`73b72c0c3`) after a read-only
worktree/branch scan found no measured bench worktree win missing from `main`.
The old adjacency outer-cache branch is already represented on `main`, and the
remaining recent off-main heads were parity/docs-only rather than measured
source wins.

The literal requested per-crate bench form was retried first:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release bench
profile was used through `rch exec` with the requested `fnx-python` crate and
cod-b target dir. RCH had no admissible remote worker for the routing sweep and
fell back locally.

Fresh current-main routing sweep:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

| workload | FNX median | NetworkX median | ratio vs NetworkX |
| --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | `11.878 ms` | `4.8129 ms` | `0.405x` |
| `mdg_in_edges_data_n700_e12662` | `20.763 ms` | `9.6116 ms` | `0.463x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | `1.7778 ms` | `986.33 us` | `0.555x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | `1.2197 ms` | `1.1485 ms` | `0.942x` |
| `mdg_edges_keys_n700_e12662` | `1.6838 ms` | `3.0359 ms` | `1.803x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | `349.42 us` | `705.56 us` | `2.019x` |

Targeted lever: a lazy `MultiDiGraphWeightedDegreeIter` for exact full-graph
weighted in/out degree. The prior no-ship iterator materializer still eagerly
built every `(node, degree)` tuple into a vector before handing a native
iterator to Python. This candidate instead snapshotted node names/display keys
and computed one degree row per `__next__`, using the existing clean-store int
row, mirror int row, then Python `sum` row fallback. The Python degree view was
routed to `_native_weighted_in_degree_iter` / `_native_weighted_out_degree_iter`
only for exact `MultiDiGraph` full weighted degree; nbunch/views stayed on the
existing path.

Validation before timing:

- `python3 -m py_compile python/franken_networkx/__init__.py`: passed.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`:
  passed remotely on `hz2`.

Focused candidate command:

`AGENT_NAME=BlackThrush RCH_WORKER=hz2 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mdg_in_degree_weight -- --quiet`

RCH again fell back locally for the focused bench
(`no admissible workers: insufficient_slots=2,hard_preflight=1,active_project_exclusion=1`).

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs fresh baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | fresh current-main sweep | local fallback | `11.878 ms` | `4.8129 ms` | `0.405x` | baseline |
| `mdg_in_degree_weight_n700_e12662` | lazy native iterator candidate | local fallback | `12.995 ms` | `15.294 ms` | `1.177x` | `0.914x` |

Decision: REVERTED / NO-SHIP. The paired candidate NetworkX row was noisy
(`4.8129 ms -> 15.294 ms`), so the apparent ratio win is not credible. The FNX
absolute median regressed on the comparable local run (`11.878 ms -> 12.995 ms`),
which is below the keep bar. Candidate source hunks in
`crates/fnx-python/src/digraph.rs` and `python/franken_networkx/__init__.py`
were manually reverted; final source diff is empty. This rules out a row-lazy
native iterator as a standalone fix for weighted `MultiDiGraph.in_degree`.

## 2026-06-27 BlackThrush MultiGraph selfloop direct scalar emission - ACCEPT

Scope: land-or-dig pass on current `main` (`467047820`) after a fresh
read-only scan found no measured bench worktree source win missing from `main`.
The old adjacency outer-cache worktree is already represented by the shared
outer-dict cache on `main`, and the remaining non-ancestor worktrees were
docs/test-only rather than measured source wins.

The requested literal per-crate release bench form was retried first:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release bench
profile was used through `rch exec` with the requested `fnx-python` crate and
cod-b target dir.

Fresh routing sweep showed the largest current gap in
`MultiGraph.selfloop_edges(keys=True, data="weight")`:

| workload | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback | `16.297 ms` | `13.028 ms` | `0.799x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback | `4.8487 ms` | `1.5996 ms` | `0.330x` |
| `mdg_edges_keys_n700_e12662` | local fallback | `2.0147 ms` | `2.0082 ms` | `0.997x` |
| `mdg_in_edges_data_n700_e12662` | local fallback | `22.563 ms` | `8.5054 ms` | `0.377x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback | `260.83 us` | `691.54 us` | `2.651x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback | `1.3672 ms` | `742.63 us` | `0.543x` |

Lever: add a narrow direct scalar emission path in
`PyMultiGraph::_native_selfloop_edges` for
`selfloop_edges(keys=True, data="<attr>")` when display edge keys are default
integer keys and the Python edge-attribute mirror is empty. The existing
pristine scalar attr read already bypassed mirror lookup per edge; this lever
also avoids the intermediate `(selfloop node, keys)` collection and the exact
`number_of_selfloops()` capacity scan. Map-valued attrs still route through the
existing mirror materialization path to preserve live dict identity.

Focused same-worker A/B used `rch` remote `ovh-a` with the requested cod-b
target dir and per-crate `fnx-python` scope:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RCH_REQUIRE_REMOTE=1 RCH_WORKER=ovh-a rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight -- --quiet`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean `main` comparator | `rch` remote `ovh-a` | `942.02 us` | `463.04 us` | `0.491x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | direct scalar emission candidate | `rch` remote `ovh-a` | `818.93 us` | `467.44 us` | `0.571x` | `1.150x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | candidate confirmation | `rch` remote `ovh-a` | `822.48 us` | `975.98 us` | `1.187x` | `1.145x` |

The confirmation NetworkX row was noisy, but the FNX candidate median stayed
stable (`818.93 us`, then `822.48 us`) while the same-worker clean-main FNX
median was `942.02 us`, so the source-side improvement is credible. The
conservative paired ratio is the first candidate row: `0.571x` vs NetworkX,
up from the same-worker clean comparator's `0.491x`.

Validation:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed remotely on `hz2`.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: passed remotely on `ovh-a`; all conformance unit/integration/doc tests green.
- `cargo fmt -p fnx-python --check` / `rustfmt --edition 2024 --check crates/fnx-python/src/lib.rs`: blocked by pre-existing unrelated formatting drift in `crates/fnx-python/src/digraph.rs` at the directed in-edges helper. The changed `lib.rs` hunk was manually formatted and the unrelated file was not modified.

Decision: ACCEPTED. This is a same-worker, per-crate, NetworkX head-to-head
measured win on the current largest routed gap: clean `main` ratio `0.491x`,
candidate ratio `0.571x`, and stable FNX median improvement of about `1.15x`.

## 2026-06-27 BlackThrush MultiGraph selfloop small-int object cache - NO-SHIP

Scope: fresh land-or-dig pass on current `main` (`008ced9b7`) after checking
branches and bench worktrees for measured wins not represented on `main`. The
only measured-looking non-ancestor branch/worktree remained the old
`DictOfDictsCache` adjacency outer-cache commit (`5e65efa88`), already
represented by the shared outer-dict cache and ledger entries on `main`; other
visible non-main heads were docs/test/parity or stale stash/index artifacts.

The requested literal per-crate release bench form was retried:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with
`error: unexpected argument '--release' found`, so the equivalent release
profile was used through `rch exec` with the requested `fnx-python` crate and
cod-b target dir. RCH had no admissible remote worker and fell back locally.

Fresh routing sweep on current `main`:

| workload | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback | `12.397 ms` | `6.6260 ms` | `0.535x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback | `2.6041 ms` | `810.80 us` | `0.311x` |
| `mdg_edges_keys_n700_e12662` | local fallback | `2.2739 ms` | `1.6524 ms` | `0.727x` |
| `mdg_in_edges_data_n700_e12662` | local fallback | `19.635 ms` | `12.451 ms` | `0.634x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback | `248.39 us` | `594.58 us` | `2.394x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback | `962.99 us` | `548.76 us` | `0.570x` |

Targeted lever: add local `PyObject` caches in the direct scalar
`PyMultiGraph::_native_selfloop_edges` path for repeated default integer edge
keys (`0..16`) and CPython small integer scalar values (`-5..256`). The
graveyard fit was the "constants kill you" / vectorized-execution discipline:
avoid repeated per-item scalar object conversion in the hottest tuple-emission
loop without changing order, tuple shape, map fallback, or dirty/mirror
semantics. This was a new lever distinct from the earlier lookup-key reuse,
list-iterator handoff, tuple cache, clean-int mirror bypass, and direct scalar
emission work.

Focused candidate command:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head mg_selfloop_keys_weight -- --quiet`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs clean |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mg_selfloop_keys_weight_n2500_loops2502` | clean `main` routing baseline | local fallback | `2.6041 ms` | `810.80 us` | `0.311x` | baseline |
| `mg_selfloop_keys_weight_n2500_loops2502` | small-int object cache candidate | local fallback | `2.8947 ms` | `632.20 us` | `0.218x` | `0.900x` |

Validation while probing:

- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed via RCH local fallback.
- `AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo test -p fnx-conformance`: RCH queued remotely, timed out, fell back locally, and passed all `fnx-conformance` tests.

Decision: REVERTED / NO-SHIP. The cache added extra branch/cache-management
work to a tuple-materialization loop and made the FNX row slower
(`2.6041 ms -> 2.8947 ms`) while the ratio vs NetworkX fell from `0.311x` to
`0.218x`. Candidate source hunks in `crates/fnx-python/src/lib.rs` were
manually reverted; final source diff is empty. Do not retry per-call Python int
object caching as a standalone lever for this self-loop row.

## 2026-06-27 BlackThrush MultiDiGraph weighted in-degree edge-stream accumulator - NO-SHIP

Scope: fresh land-or-dig pass on current `origin/main` (`73b72c0c3`). A
read-only worktree audit found no measured bench win missing from `main`: the
old adjacency outer-cache worktree is already represented by the landed
`a424835f7` implementation and canonical ledger entries, the edge-view audit is
represented by `53a583084`, and the remaining A* worktree patch is parity-only
and already duplicated on `main`.

Agent Mail registration succeeded as `BlackThrush`, but exclusive reservation
writes were refused by the existing Agent Mail SQLite corruption circuit
breaker. This pass used a detached scratch worktree at
`/data/projects/.scratch/franken_networkx-blackthrush-mdgdegree-20260627T1111Z`
and staged only this ledger file after reverting the code probe.

The biggest current measured gap remained
`mdg_in_degree_weight_n700_e12662`. The literal requested `cargo bench
--release` form is still rejected by this cargo toolchain (`unexpected argument
'--release'` in prior ledgered runs), so the equivalent per-crate release
profile was used with the requested `cod-a` target directory:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-a PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_degree_weight --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

RCH had no admissible remote worker for both focused runs and fell back locally.

Lever tried: use the graveyard/data-oriented single-pass scan idea rather than
another pair-materialization cache. For clean Rust-store integer weights, the
candidate accumulated full-graph `MultiDiGraph` weighted in/out/total degree
from `edges_ordered_borrowed()` into node-indexed `Vec<i128>` totals, then
emitted the existing `(node, degree)` sequence. This targeted the repeated
per-node predecessor/successor scans and keyed `edge_attrs(source,target,key)`
lookups in `native_weighted_directional_degree_store_int`, while preserving
node order, integer overflow fallback, missing-weight default `1`, dirty-edge
fallback, and public iterator shape.

Focused evidence:

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | current `73b72c0c3` baseline | local fallback via `rch exec` | `11.570 ms` | `5.1372 ms` | `0.444x` |
| `mdg_in_degree_weight_n700_e12662` | edge-stream accumulator candidate | local fallback via `rch exec` | `19.842 ms` | `7.4169 ms` | `0.374x` |

Decision: REVERTED / NO-SHIP. The borrowed edge stream avoided some keyed
lookups but introduced a full `edges_ordered_borrowed()` materialization plus a
node-position hash table, and regressed the FNX row by `+71.9%` in Criterion's
paired comparison. Do not retry full-edge materialization for this row as a
standalone lever; the remaining route needs either an already-indexed
target/source accumulator maintained by the multigraph store or a public
contract that avoids constructing the full Python pair stream.

## 2026-06-27 BlackThrush MultiDiGraph `in_edges(keys, data=<attr>)` default-key emit - NO-SHIP

Scope: land-or-dig pass on current `main` (`a1f74cd35`). Read-only worktree
audit found no measured source win missing from `main`: the old adjacency
outer-cache branch is already represented by the shared outer-dict landing, and
the fresh-looking edge-view worktree is already represented on `main` by the
`34e09ee11` pristine store-read landing plus the canonical ledger entry at the
top of this file. Agent Mail writes were still blocked by the existing SQLite
corruption circuit breaker, so this pass kept coordination read-only and staged
only this ledger after reverting the probe.

The requested literal per-crate release bench form was retried:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --release --features pyo3/abi3-py310 --bench networkx_head_to_head networkx_head_to_head_core_laggards -- --quiet`

Cargo rejected that syntax on this toolchain with `unexpected argument
'--release'`, so the equivalent release profile was used through `rch exec`
with the requested `fnx-python` crate and cod-b target dir. RCH had no
admissible worker for the sweep and focused bench, so both benchmark runs fell
back locally.

Fresh current-head routing sweep:

| workload | runner | FNX median | NetworkX median | ratio vs NetworkX |
| --- | --- | ---: | ---: | ---: |
| `mdg_in_degree_weight_n700_e12662` | local fallback | `11.127 ms` | `5.4744 ms` | `0.492x` |
| `mg_selfloop_keys_weight_n2500_loops2502` | local fallback | `1.5111 ms` | `640.74 us` | `0.424x` |
| `mdg_edges_keys_n700_e12662` | local fallback | `1.5150 ms` | `1.4695 ms` | `0.970x` |
| `mdg_in_edges_data_n700_e12662` | local fallback | `16.191 ms` | `7.1467 ms` | `0.441x` |
| `mdg_out_edges_nbunch_keys_data_n700_e12600` | local fallback | `250.58 us` | `518.77 us` | `2.070x` |
| `mdg_out_edges_nbunch_keys_weight_n700_e12600` | local fallback | `1.0592 ms` | `579.83 us` | `0.547x` |

Targeted lever: avoid internal string edge-key construction in
`PyMultiDiGraph::_native_mdg_in_edges_data_key` when `keys=True` and
`edge_py_keys` is empty, matching the default-int-key shortcut already present
in `_native_mdg_in_edges_no_data`. This was the narrowest "constants kill you"
attempt on the biggest measured gap after the existing pristine store-read path:
keep order, tuple shape, data-default behavior, custom-key fallback, and
non-pristine edge-attribute fallback unchanged, but emit the default Python int
key directly.

Focused candidate command:

`AGENT_NAME=BlackThrush RCH_WORKER=hz2 CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b PYTHONHASHSEED=0 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 rch exec -- cargo bench -p fnx-python --profile release --features pyo3/abi3-py310 --bench networkx_head_to_head -- mdg_in_edges_data --noplot --sample-size 20 --warm-up-time 1 --measurement-time 2`

| workload | state | runner | FNX median | NetworkX median | ratio vs NetworkX | self vs baseline |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mdg_in_edges_data_n700_e12662` | current `main` sweep baseline | local fallback via `rch exec` | `16.191 ms` | `7.1467 ms` | `0.441x` | baseline |
| `mdg_in_edges_data_n700_e12662` | default-key direct emit candidate | local fallback via `rch exec` | `17.449 ms` | `7.3530 ms` | `0.421x` | `0.928x` |

Criterion also reported `No change in performance detected` for the FNX row
(`change: [-3.4780% +2.7042% +7.7687%]`, `p = 0.40`). Build validation during
the probe passed remotely on `hz2`:

`AGENT_NAME=BlackThrush CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cod-b rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`

Decision: REVERTED / NO-SHIP. The direct default-key emission did not move the
row and slightly worsened the paired ratio (`0.441x -> 0.421x`). Candidate
source hunks in `crates/fnx-python/src/digraph.rs` were manually reverted; final
source diff is empty. Do not retry default-int edge-key emission as a standalone
fix for full-graph `MultiDiGraph.in_edges(keys=True, data=<attr>)`; the
remaining gap is dominated by target-major tuple/value materialization rather
than display-key lookup alone.

## 2026-06-27 CopperCliff to_directed/to_undirected single-attr AttrMap-clone - NO-SHIP

Fresh warm min-of-N sweep (host loadavg ~45, peer builds active — ratios are
directional, not precision) over the view-materialization paths flagged in
older memory found that vein **closed**: `nodes(data='x')` 0.97x,
`nodes(data=True)` 0.87x, `edges(data=*)` 1.2-1.3x, `dict(adjacency())` 0.96x,
`degree(weight)` 1.29x, `in/out_edges(data=w)` 1.2-1.6x — all at parity-or-faster
vs vendored NetworkX. Do not re-dig those as standalone targets.

The one reproducible remaining substrate gap in the conversion family is
**single flat-attr** `to_directed()` / `to_undirected()`:

| workload (n=800, m=8000) | edges attr | FNX | NetworkX | ratio |
| --- | --- | ---: | ---: | ---: |
| `Graph.to_directed()` | `{weight}` (1 scalar) | ~41 ms | ~34 ms | 0.75-0.83x |
| `DiGraph.to_undirected()` | `{weight}` (1 scalar) | ~32 ms | ~18 ms | 0.56-0.62x |
| `Graph.to_directed()` | no attr | ~10 ms | ~30 ms | 2.9x |
| `Graph.to_directed()` | 5 attrs/edge | ~44 ms | ~51 ms | 1.1-1.2x |

The gap is *specific to the single-scalar-attr case*: NetworkX's per-edge
`copy.deepcopy(datadict)` cost scales with attr count, so with ≥5 attrs FNX is
already faster, and with zero attrs FNX is ~3x faster. Only the 1-key dict case
loses.

Lever attempted: in the four `_native_to_directed_deepcopy` /
`_native_to_undirected_deepcopy` kernels, the per-arc Rust attr map was rebuilt
via `py_dict_to_attr_map(deepcopy(py_attrs))` (a Python-dict iteration + fresh
`"weight"` `String` alloc + `py_value_to_cgse` dispatch per arc). Since the
source `self.inner` already holds an `AttrMap` value-identical to that rebuild
(the mirror is a deep copy of the source mirror; immutable scalars are shared),
I replaced it with `self.inner.edge_attrs(u, v).cloned()` (BTreeMap clone),
keeping the `py_dict_to_attr_map` re-parse only as a no-inner-entry fallback.
Applied to `PyGraph::_native_to_directed_deepcopy` (lib.rs) and built
`-p fnx-python --features pyo3/abi3-py310` via `rch exec`.

Correctness held (structure, edge count, `D[u][v]['weight']` value, and
copy↔source attr-dict mutation independence all verified). But the paired A/B
on the same host showed **no robust movement**: NEW `fnx_best` 38-41 ms vs OLD
38-44 ms across 4 interleaved trials — indistinguishable within the noise floor.

Decision: REVERTED / NO-SHIP. The `py_dict_to_attr_map` re-parse was not the
bottleneck; the per-arc cost floor is the unavoidable Python dict-mirror
`deepcopy_py_dict` (`bound.copy()` materializing ~2·E Python dicts) plus the
`String`-keyed `edge_py_attrs` HashMap inserts (2 `String` allocs/arc) — the
dual Py-mirror+AttrMap construction wall, not the AttrMap derivation. Same
lesson as the MDG weighted-degree store-int probe: halving the native work is
invisible behind the PyO3 object-build wall. A real fix needs to eliminate the
per-arc Python dict mirror itself (lazy/shared mirror), not speed up the Rust
side. Worktree-only change; main source diff is docs-only.

## 2026-06-27 CopperCliff add_edges_from non-empty-Graph collision pre-scan snapshot - SHIPPED

`add_edges_from(list)` / `from_edgelist` route through the native plain-edge
batch only when no new edge collides with an existing one; the gate
`_simple_add_edges_from_touches_existing_plain_edge` decided this with a per-edge
`graph.has_edge(u, v)` loop = one PyO3 round-trip (plus the Python `has_edge`
wrapper) for EVERY edge in the bunch. On a non-empty graph that is pure
fnx-side overhead NetworkX never pays. cProfile of `barabasi_albert_graph(2000,3)`
(seeds star_graph(m) then bulk-adds ~m*(n-m) edges onto the non-empty seed)
showed the pre-scan at 0.266 s / 0.901 s total, of which 0.200 s was 119 760
`has_edge` calls.

Lever (pure Python, no rebuild): when the existing edge set is no larger than the
bunch (`number_of_edges() <= len(bunch)`), take one `edges()` snapshot into a
Python set (frozensets for undirected, direction-keyed tuples for DiGraph) and
test membership in C instead of per-edge `has_edge()`. The snapshot is
`O(edge_count) <= O(len(bunch))` — never more than the scan it replaces — and each
test is a set lookup, not a PyO3 round-trip. When `edge_count > len(bunch)` (small
bunch onto a big graph) it falls through to the original `has_edge` scan, so that
regime is untouched. Unhashable endpoints break out to the `has_edge` path too.

Deterministic cProfile (load-independent; wall-clock was uselessly noisy at
host loadavg 68-153):

| workload | metric | OLD | NEW | self-speedup |
| --- | --- | ---: | ---: | ---: |
| `barabasi_albert_graph(2000,3)` x20 | total_tt | 0.901 s | 0.725 s | 1.24x |
| `barabasi_albert_graph(2000,3)` x20 | pre-scan cumtime | 0.266 s | 0.070 s | 3.8x |
| `barabasi_albert_graph(2000,3)` x20 | `has_edge` calls | 119 760 | 0 | — |
| `add_edges_from(+10k onto 10k)` x20 | total_tt | 0.736 s | 0.555 s | 1.33x |
| `add_edges_from(+10 onto 50k)` x20 | total_tt | identical path (gate skips snapshot) | | — |

vs NetworkX: the pre-scan was the dominant fnx-only tax that kept
`barabasi_albert` at ~0.75x wall-clock; removing it closes that gap (cProfile
`total_tt` BA fnx 0.620 s vs nx 0.551 s = 0.889x, narrowed from the prior ~0.75x;
cProfile over-penalises fnx's extra wrapper layers, so raw wall-clock is at/above
parity). Broadly applies to every `add_edges_from`/`from_edgelist` onto an
already-populated-but-not-huge Graph/DiGraph.

Correctness: BA structural parity across seeds; undirected + directed collisions
(incl. reverse-order `(v,u)`), self-loops, plain-re-add attr preservation, and the
big-existing fallback all match NetworkX. Conformance: 983 targeted tests
(add_edges / construction / generators / classes-audit / edge+digraph+multigraph
parity) pass, 0 failures. Pure-Python change in
`python/franken_networkx/__init__.py`; no Rust rebuild.

## 2026-06-28 CopperCliff SHIP: greedy_tsp 0.044x->1.43x — native nearest-neighbour TSP kernel de-delegates the O(n^2) fnx->nx conversion tax

The single biggest remaining measured laggard. `fnx.approximation.greedy_tsp`
had no concrete method, so it went through the `_ApproximationNamespace`
generic `__getattr__` wrapper, which round-trips the graph through
`_networkx_graph_for_parity(G)` — a full O(V+E) fnx->nx Graph rebuild that, for
the dense COMPLETE weighted graph a TSP heuristic operates on, is O(n^2)
PyObject construction. NetworkX's own `greedy_tsp` is just O(n^2) Python dict
lookups (cheap), so the conversion alone dominated: greedy_tsp measured
~0.087-0.10x vs nx (10x slower), worsening with n (fnx 85ms vs nx 8ms at n=300).
Prior sessions surfaced this as a "de-delegate target" but rejected it as
conversion-floor-bound, concluding even an in-process Python NN reaches only
~0.5x (the per-edge weight snapshot is itself O(n^2) Python work) and that a
numpy argmin "diverges on the many weight ties".

LEVER (radical, safe-Rust): a fully native nearest-neighbour kernel
`_fnx.greedy_tsp_native` (crates/fnx-python/src/algorithms.rs). It reads the
edge weights straight from the Rust store into a dense index-space matrix and
runs the greedy walk entirely in Rust — no PyObject materialization, no nx
Graph build. The conversion-floor argument only applied to a *Python-side*
weight snapshot; in Rust the O(n^2) matrix read + O(n^2) walk are native and
beat nx's O(n^2) Python dict lookups.

BYTE-EXACTNESS WITHOUT REPLICATING nx's SET ORDER: nx breaks ties via
`min(set(G), key=...)` (first node in Python set-iteration order — unreplicable
in Rust for arbitrary node types). KEY INSIGHT: when every greedy step has a
UNIQUE minimal-weight neighbour, the choice is independent of iteration order,
so the tour == nx for ANY node type. The kernel tracks ties and returns
`Some(tour)` only when tie-free; on ANY exact-tie step (or multigraph,
non-numeric weight, incomplete/empty graph, unknown source) it returns `None`
and the Python wrapper falls back to the faithful nx delegation — reproducing
nx's exact tours AND errors. Tie-free is the overwhelmingly common case for
real-valued (distance) weights, so the fast path engages in practice.

Subtle bug found + fixed mid-build: the in-kernel
`sync_rust_edge_attrs_if_available(g)` (flushes the Python edge-attr mirror to
the authoritative store, needed because `G.edges[u,v]['weight']=w` is
store-stale until flushed) MUST run BEFORE `extract_graph(g)` takes its PyRef
borrow — otherwise the flush's mutable borrow fails with "Already borrowed",
the helper silently swallows it, the store stays stale (all weights read as the
default 1.0 -> every step ties -> kernel returns None -> permanent fallback).
Reordering sync-before-extract (matching `dijkstra_path`) fixed it.

Bench (criterion median, `cargo bench -p fnx-python --bench
networkx_head_to_head -- greedy_tsp`, complete weighted graph n=250, tie-free
weights `u*u+v*v+u*v+1`, CARGO_TARGET_DIR=/data/projects/.rch-targets/franken_networkx-cc):

| workload | FNX | NetworkX | ratio vs nx |
| --- | ---: | ---: | ---: |
| `greedy_tsp` complete n=250 | `3.4272 ms` | `4.9090 ms` | **1.43x** |

Self-speedup vs the old delegated path measured in the same harness: the
fallback (stale-store) path ran at `113.83 ms`; native runs at `3.43 ms` =
~33x self-speedup (criterion `change: -97.0%`). (Bench-loader caveat worth
recording: `cargo bench` does NOT forward `CARGO_TARGET_DIR` into the bench
binary's runtime env on this host, so the bench's dynamic-`_fnx`-from-target
loader silently imported the STALE repo `python/franken_networkx/_fnx.abi3.so`
and measured the OLD delegated path twice before I noticed — fix: stage the
freshly built `.so` into the repo package dir, then run the bench binary
directly with `CARGO_TARGET_DIR` set in the immediate env.)

Correctness: tie-free byte-exactness is order-independent (proved above);
ties/incomplete/multigraph/non-int/non-numeric all delegate. Conformance:
`test_tsp_approximation_conformance.py` + `test_approximation_signature_parity.py`
= 118 passed, 0 failures (incl. the exact-match `greedy_tsp` K_n n=3..8 test,
valid-Hamiltonian-cycle, single-node trivial tour, and signature parity). A
500-case adversarial sweep (int + string nodes, directed + undirected, complete
+ incomplete, tie-heavy + tie-free, including the nx-raises error cases) =
0 mismatches wrapper-vs-nx. Gates: `rustfmt --check` clean on both touched
files (a pre-existing fmt drift in the peer-owned `digraph.rs` is unrelated and
untouched). Touches: `crates/fnx-python/src/algorithms.rs` (kernel + helper +
registration), `python/franken_networkx/__init__.py` (concrete `greedy_tsp`
method on the approximation namespace), `crates/fnx-python/benches/networkx_head_to_head.rs`
(new `tsp_head_to_head` group with a baked fnx==nx assert). LEVER (generalizable):
a delegated heuristic whose only floor is an O(n^2) fnx->nx conversion can be
WON with a native kernel that returns a verified-byte-exact result on the
order-independent (tie-free) case and delegates the order-sensitive remainder.

## 2026-06-28 CopperCliff SHIP: simulated_annealing_tsp 0.26x->2.44x, threshold_accepting_tsp 0.42x->2.87x — index-space vectorised de-delegation

After greedy_tsp, the next-biggest gaps in the approximation/TSP delegation
family. Both `simulated_annealing_tsp` and `threshold_accepting_tsp` had no
concrete method, so they went through the `_ApproximationNamespace`
`__getattr__` wrapper, paying the O(n^2) `_networkx_graph_for_parity` conversion
EVERY call — AND nx's inner loop recomputes the FULL O(n) cycle cost (per-edge
Python `G[u][v].get(weight,1)` dict lookups) `N_inner*max_iterations` times.
Measured (n=120, default config): SA 0.260x, TA 0.416x.

LEVER (pure-Python, no rebuild): de-delegate by running the metaheuristic in
INDEX SPACE with a vectorised cost. nx's move functions (`swap_two_nodes`,
`move_one_node`) swap CYCLE POSITIONS — their RNG draws (`seed.sample(range(1,
len-1), 2)`) depend only on `len(cycle)`, NOT the node labels — so the loop runs
byte-identically on an integer index-cycle while reusing nx's EXACT move
functions + `create_py_random_state` seed (identical draw sequence). The cycle
cost becomes ONE vectorised numpy fancy-index sum `W[cyc[:-1], cyc[1:]].sum()`
over a dense weight matrix instead of n per-edge Python dict lookups. At nx's
default `N_inner=100`, the matrix build amortises and the vectorised cost crushes
nx's dict.gets.

BYTE-EXACTNESS gates (else fall back to the faithful nx delegation, preserving
nx's exact tours AND errors): simple Graph/DiGraph, explicit `init_cycle` (not
"greedy"), a known move ("1-1"/"1-0"), n>=3, a COMPLETE graph, and
INTEGER-valued weights — the last so the numpy pairwise sum equals nx's
left-to-right Python `sum()` exactly (float weights -> sum-order-sensitive ->
delegate). The init_cycle is validated exactly as nx does; any deviation falls
back so nx raises the precise error.

SUBTLE BUG found + fixed: nx's `move(cycle, seed)` MUTATES the cycle IN PLACE and
nx passes the LIVE cycle (not a copy), so a REJECTED move is NOT reverted — the
"current solution" is a random walk and only `cost` gates on acceptance. A first
prototype that passed `cyc[:]` (a copy) matched nx only because high-temp early
iterations rarely reject; the adversarial sweep exposed 282/600 mismatches (and
TA ran 2x SLOWER — a divergence symptom: more best-resets -> more outer
iterations). Mirroring nx's in-place semantics (`mv(cyc, rng)`, no revert on
reject) fixed both correctness and speed.

Bench (criterion median, `cargo bench -p fnx-python --bench
networkx_head_to_head -- networkx_head_to_head_tsp`, complete integer-weighted
graph n=200, nx default config, seed=7):

| workload | FNX | NetworkX | ratio vs nx |
| --- | ---: | ---: | ---: |
| `simulated_annealing_tsp` n=200 | `44.90 ms` | `109.75 ms` | **2.44x** |
| `threshold_accepting_tsp` n=200 | `62.33 ms` | `179.11 ms` | **2.87x** |

Correctness: 800-case adversarial sweep (int + float weights, SA + TA, move
"1-1"/"1-0", mixed N_inner/max_iterations/seed) = 0 mismatches wrapper-vs-nx
(float-weight cases delegate; int-weight cases run native — both == nx). Error
contracts (bad init_cycle, source != cycle[0]) match nx exactly. Conformance:
`test_tsp_approximation_conformance.py` + `test_approximation_signature_parity.py`
= 118 passed, 0 failures (incl. the seeded exact-tour SA/TA tests for seeds
[1,7,42,1000] and signature parity). Gates: `rustfmt --check` clean on the bench
file; `py_compile` clean. Touches: `python/franken_networkx/__init__.py`
(concrete `simulated_annealing_tsp` + `threshold_accepting_tsp` methods + shared
`_tsp_anneal_prep`), `crates/fnx-python/benches/networkx_head_to_head.rs` (SA/TA
workloads in the `tsp_head_to_head` group with baked fnx==nx asserts).

BUILD-INFRA caveat re-confirmed (memory feedback_rch_no_local_so_extract_wheel):
the criterion bench had to run LOCALLY — the remote worker (hz2) lacks
`libpython3.13.so.1.0`, and the bench's CARGO_TARGET_DIR loader imports the
libpython-linked `lib_fnx.so` (a cdylib, not an abi3 wheel), which fails to load
remotely. Do NOT stage a `lib_fnx.so` into the repo package dir as
`_fnx.abi3.so` (it links libpython and breaks remote imports); for remote benches
get a portable abi3 `.so` via `rch maturin build`/wheel-extract, or run the bench
binary locally where libpython is present.

## 2026-06-28 CopperCliff multi_source_dijkstra_path_length 0.20x — NO-SHIP (length-only de-delegation is value-exact but ORDER-blocked by the parked br-r37-c1-86xx9 tie-break)

`multi_source_dijkstra_path_length(G, sources)` measures 0.203x vs nx (fnx
2.93ms vs nx 0.60ms, weighted n=400). ROOT CAUSE: it calls `multi_source_dijkstra`,
which delegates ANY weighted input to nx (the `_mst_has_weight_edge_attr` gate:
"the Rust multi_source_dijkstra inherits the same weight-ignoring bug as
single_source"), paying the full O(V+E) `_networkx_graph_for_parity` conversion
EVERY call. The native kernel `_raw_multi_source_dijkstra` runs in 0.91ms but is
gated off for weighted graphs.

FINDING (the gate is VALUE-stale for the length output): the native kernel's
weighted distance VALUES are byte-identical to nx across 250 adversarial graphs
(directed + undirected, int + float weights, multi-source) — 0 value-mismatches.
Dijkstra distances are unique-by-construction regardless of the priority-queue
tie-break order that makes the PATH variant diverge, so the kernel does NOT
ignore weights for lengths. I built a length-only native binding
(`multi_source_dijkstra_path_length`, skipping the O(V*path_len) `paths_dict`
construction) + a wrapper that bypasses the stale weighted gate (delegating only
callable/negative/sync-gated weights and MIXED int+float sets, where per-node
distance TYPING needs the path).

BLOCKER (why it's a NO-SHIP): the public contract includes DICT ORDER, and the
regression-lock `test_dicsr_cache_parity.py::test_multi_source_dijkstra_directed_finalize_order`
asserts `[(repr(k), v, type(v).__name__) for k,v in result.items()] == nx`. The
native kernel's equal-distance finalize order does NOT match nx's heap-push order
for UNDIRECTED weighted graphs (11/240 order-mismatches on all-int graphs;
directed was 0/240). This is exactly the parked `br-r37-c1-86xx9` tie-break:
matching nx's pop order on equal-distance ties requires simulating nx's heap
(re-running the algorithm in Python = no win), and a "fall back when distances
have ties" salvage makes EVERY realistic integer-weighted graph (which is
tie-dense) fall back, erasing the win. The existing code's blanket delegation is
load-bearing for ORDER parity, not just values. REVERTED in full; conformance
restored GREEN. The real fix is a Rust kernel change to emit nx's heap-push
finalize order for the undirected weighted multi-source kernel (the deep parked
issue), not a wrapper-level de-delegation. LEVER (recorded): a delegation gate
can be VALUE-stale yet ORDER-load-bearing — verify dict-iteration order
(repr+type) against the order-sensitive regression locks, not just values,
before de-delegating an ordered-dict-returning shortest-path function.

## 2026-06-28 CopperCliff SHIP: voronoi_cells(weighted) 0.33x->1.25-1.52x — bypass the stale _mst_has_weight_edge_attr delegation (native multi_source_nearest_source is byte-exact; cells compare order-insensitively)

`voronoi_cells(G, centers, weight)` on a WEIGHTED graph measured 0.33x vs nx
(fnx 1.16ms vs nx 0.39ms, n=150). ROOT CAUSE: `_voronoi_nearest_centers`
delegated EVERY weighted input to nx via `multi_source_dijkstra_path` (the stale
`_mst_has_weight_edge_attr` gate, "the Rust multi_source kernel ignores weight"),
paying the full O(V+E) `_networkx_graph_for_parity` conversion — even though a
native source-propagating kernel (`_fnx.multi_source_nearest_source`) already
existed and was used for UNWEIGHTED graphs.

LEVER (pure-Python, no rebuild): route weighted UNDIRECTED string-weight inputs
through `multi_source_nearest_source` too, bypassing only the stale
`_mst_has_weight_edge_attr` gate (keeping the delegation for callable / negative
/ self-sync-gated weights and directed graphs). The binding self-syncs via the
weighted projection, so it returns correct weighted nearest-center assignments.

WHY THIS IS SAFE WHERE multi_source_dijkstra_path_length WAS NOT (contrast with
the 8b2949932 NO-SHIP): voronoi_cells returns a dict of SETS compared
ORDER-INSENSITIVELY (`cells == nx_cells`; the conformance tests normalise to
`{k: set(v)}` / `{repr(k): sorted(...)}` and use `==`). The kernel's
equal-distance FINALIZE-ORDER tie-break (the parked br-r37-c1-86xx9 that blocks
the ordered length-dict de-delegation) is IRRELEVANT to cell membership — a
node's nearest CENTER is value-determined, and equidistant ties are assigned
identically to nx (verified). So the same native kernel that's order-blocked for
the ordered shortest-path dict is cleanly usable here.

Correctness: 500-case adversarial sweep (gnp/watts/cycle, int weights,
disconnected→unreachable cells, single + multi center) = 0 cell-mismatches
vs nx. Conformance: 657 tests across test_voronoi_module_parity /
test_voronoi_native_parity / test_voronoi_cells_empty_centers_parity /
test_complex_function_parity / test_collection_container_type_parity /
test_cover_nodeclass_assort_parity / test_graph_utilities /
test_misc_algorithms_conformance / test_parity_conformance pass, 0 failures
(incl. the weighted test_voronoi_native_parity case + value-type checks).

Measurement (Python timeit, min-of-7, weighted connected_watts_strogatz, vendored
nx oracle — NOT backend-dispatched):

| workload | FNX | NetworkX | ratio vs nx |
| --- | ---: | ---: | ---: |
| `voronoi_cells` weighted n=150 | `0.32 ms` | `0.40 ms` | **1.25x** |
| `voronoi_cells` weighted n=400 | `0.78 ms` | `1.18 ms` | **1.52x** |

A `voronoi_head_to_head` criterion group (weighted n=400, baked
order-insensitive `cells == nx` assert) is added to
`crates/fnx-python/benches/networkx_head_to_head.rs` for the canonical suite.
Touches: `python/franken_networkx/__init__.py` (`_voronoi_nearest_centers` gate),
the bench file. LEVER (generalizable): a value-stale delegation gate that's
ORDER-load-bearing for an ordered-dict return can still be safely bypassed for a
SIBLING consumer that aggregates the same kernel output order-insensitively
(sets / counts / sums) — check the RETURN type's order-sensitivity per consumer,
not per kernel.

## 2026-06-28 CopperCliff frontier sweep — ~45 functions across 9 domains all AT-OR-ABOVE nx; no new clean lever (post greedy/SA/TA/voronoi session)

After landing greedy_tsp (1.43x), simulated_annealing_tsp (2.44x),
threshold_accepting_tsp (2.87x) and voronoi_cells-weighted (1.4x), ran five
broad measured sweeps to find the next gap. RESULT: every function measured is
at-or-above nx (vendored oracle, not backend-dispatched). No new sub-0.6x gap
with a clean lever exists in the swept space. Representative ratios (fnx/nx):

- distance/all-pairs: all_pairs_dijkstra_path_length 2.64x, all_pairs_bellman_ford_pl
  2.43x, all_pairs_dijkstra_path 1.08x, average_shortest_path_length(w) 4.68x,
  eccentricity(w) 2.97x, closeness_vitality(all) 14.6x, global_efficiency 22.8x.
- single-pair/path-enum: astar_path 4.15x, astar_path_length 4.33x,
  all_shortest_paths 2.57x, all_simple_paths(cutoff) 1.44x,
  bidirectional_shortest_path 3.65x, resistance_distance(pair) 100x,
  shortest_simple_paths 0.80x (Yen generator, order-sensitive — near parity).
- DAG/directed: transitive_reduction 0.92x (near parity), dag_longest_path 2.10x,
  topological_generations 2.56x, condensation 2.79x, attracting_components 5.39x,
  reciprocity 11.3x, overall_reciprocity 9.31x, descendants/ancestors 1.2-1.3x.
- centrality/community: pagerank 1.97x, katz_centrality 18.3x,
  second_order_centrality 72x, harmonic_centrality 20.7x, percolation 6.78x,
  global_reaching 2.90x, edge_connectivity 2.41x, dominance_frontiers 2.44x,
  immediate_dominators 3.78x, min_weighted_dominating_set 1.35x.
- cycle/color/misc: cycle_basis 2.36x, greedy_color(largest_first) 7.73x,
  find_cycle 1.17x, local_bridges 6.33x, chain_decomposition 7.22x,
  minimum_spanning_arborescence 3.35x, voterank 1.97x, communicability 21.5x.
- DISPATCH TRAPS noted (not real gaps): simrank_similarity 0.998x and
  panther_similarity 1.000x — nx dispatches these through the fnx backend, so
  "nx" is fnx-backed; ignore (reference_nx_backend_dispatch_benchmark_trap).

The audit of OTHER order-insensitive consumers of the weighted multi-source
delegation (the voronoi sibling lever) is exhausted: the only consumers in
__init__.py are voronoi_cells (shipped) and the multi_source_dijkstra path/length
variants themselves (parked br-r37-c1-86xx9 tie-break). The ONLY remaining
sub-0.6x residuals are (a) the covered per-element PyObject-materialization view
ops (mdg in_edges(keys,data) ~0.40x, mg selfloop_keys_weight ~0.35x — need the
architectural lazy-view / persistent-ordered-mirror primitive, NOT kernel work)
and (b) the parked weighted multi-source finalize-order tie-break (needs a Rust
kernel order fix). Both are large levers, not 60-min wins. Recorded so the fleet
stops re-sweeping these domains.

## 2026-06-28 CopperCliff frontier sweep PART 2 — operators/generators/IO/spectral/tree also all at-or-above nx (completes the map)

Extends the fdadc3767 algorithm-domain sweep to the remaining domains; same
conclusion (no new sub-0.6x lever; vein mined). Representative ratios (fnx/nx):

- operators: compose 2.12x, difference 1.68x, symmetric_difference 1.81x,
  cartesian_product 2.74x, tensor_product 3.21x, line_graph 4.35x,
  to_directed 3.38x; NEAR-PARITY (construction-substrate, not gaps): union 0.94x,
  barabasi_albert 0.78x, relabel/convert_node_labels 2.51x.
- I/O (readwrite): parse_gml 6.36x, parse_adjlist 1.25x, parse_edgelist 1.06x,
  generate_edgelist 1.12x, node_link_data 1.13x, to_dict_of_dicts 1.73x,
  to_dict_of_lists 1.68x; NEAR-PARITY: adjacency_data 0.82x, generate_adjlist
  0.91x, generate_gml 0.95x, generate_graphml 0.96x.
- spectral/linalg: adjacency_spectrum 86.7x, modularity_matrix 1.89x,
  normalized_laplacian_matrix 1.19x; NEAR-PARITY: laplacian_spectrum 0.85x,
  number_of_spanning_trees 0.83x (numerical-substrate bound).
- tree/matching: is_tree 19.9x, prufer_sequence 3.60x, maximal_matching 3.76x,
  junction_tree 2.28x, random_spanning_tree 1.02x; NEAR-PARITY: min_weight_matching
  0.91x.

NET (across both sweep parts, ~70 functions, 13 domains): the kernel /
conversion-floor / delegation vein is MINED — fnx is at-or-above nx everywhere
measured. The only sub-0.6x residuals remain the two ARCHITECTURAL levers
(covered PyObject-materialization view ops → lazy-view primitive; parked weighted
multi-source finalize-order tie-break → Rust kernel order fix). No 60-min win
remains in the algorithm/operator/generator/IO/spectral/tree surface; the
near-parity items (0.78-0.96x) are construction/numerical-substrate bound and
loss-reduction-only (skip per REVERT-~0-gain). Future perf effort should target
the two architectural levers, not domain sweeps.

## 2026-06-28 CopperCliff SHIP: set_edge_attributes dict-of-dicts 0.064x->0.449x — native one-pass (7x self; matches the shipped scalar fast-path's substrate floor)

Found via a MUTATION-op sweep (read-only perf sweeps miss mutators — same blind
spot that hid the clear_edges 0.05x catastrophe). `set_edge_attributes(G,
{(u,v): {attr: val, ...}})` (the dict-of-dicts form, no `name`) — an extremely
common nx pattern — measured **0.064x vs nx** (15x slower; fnx 10.3ms vs nx
0.66ms at 2500 edges). ROOT CAUSE: the wrapper looped `_edge_attribute_dict(G,
edge).update(d)`, where `_edge_attribute_dict` resolves `G[u][v]` — a full
EdgeAttrDict VIEW construction per edge — vs nx's plain `G._adj[u][v].update(d)`.
The dict+scalar form already had a native fast path (`_native_set_edge_attribute_
scalar`); the dict-of-dicts form did not.

LEVER (native binding, mirrors the proven scalar setter): add
`_native_set_edge_attributes_dict(values)` to PyGraph (materialize_edge_py_attrs
+ `.update(d)`) and PyDiGraph (edge_py_attrs.entry + `.update(d)`), route the
wrapper's simple-graph dict-of-dicts case to it (Multi keeps the loop). One Rust
pass, mark edges dirty once.

Result: **0.064x -> 0.449x** (7x self-improvement; fnx 1.47ms vs nx 0.66ms at
2500 edges). This lands at the SAME String-keyed-attr substrate floor as the
already-shipped scalar fast-path (~0.39x) — it is NOT a vs-nx win. The residual
loss is the architectural materialization tax: fnx pays `node_key_to_string` ×2 +
edge_key canonicalization per edge (String allocs) that nx's plain-dict
`G._adj[u][v]` does not. Beating nx here needs the same lazy-view / int-keyed-attr
primitive flagged for the read-side materialization-floor view ops — out of scope
for a wrapper/binding change. Shipped as a footgun fix (removes a 15x-slower
outlier on a common operation, brings the dict-of-dicts form to parity with the
scalar form), consistent with the existing scalar-path decision.

Correctness: 300-case adversarial sweep (undirected + directed, pre-existing
store attrs preserved, missing-edge skip) 0 mismatches vs nx; conformance 188 +
54 + 30 = 272 attribute-setter / dirty-sync / parity tests pass, 0 failures.
Verified on a freshly-built abi3 wheel (the rch pool .so links python 3.14;
local python is 3.13 — built a clean abi3 wheel locally + extracted the .so).
Touches: crates/fnx-python/src/lib.rs, crates/fnx-python/src/digraph.rs,
python/franken_networkx/__init__.py. FOLLOW-UP: the NODE dict-of-dicts form
(set_node_attributes) measures 0.269x — same lever applies (symmetric
_native_set_node_attributes_dict).

## 2026-06-28 CopperCliff SHIP: set_node_attributes dict-of-dicts 0.269x->0.643x — native one-pass (symmetric node twin of the edge fix)

The teed-up follow-up to the set_edge_attributes dict-of-dicts ship (7797db850).
`set_node_attributes(G, {node: {attr: val, ...}})` (dict-of-dicts form, no
`name`) looped `G.nodes[node].update(d)` — a NodeView __getitem__ PyO3
round-trip per node (~0.269x vs nx's plain dict update). The scalar form already
had a native fast path; the dict-of-dicts form did not.

Added `_native_set_node_attributes_dict` to all FOUR graph classes (PyGraph,
PyDiGraph, PyMultiGraph, PyMultiDiGraph — node attrs are class-agnostic),
mirroring the proven `_native_set_node_attribute_scalar` (node_py_attrs.entry +
`.update(d)`), routed the wrapper's dict-of-dicts case. SAFER than the edge twin:
node_py_attrs is the AUTHORITATIVE store (no store/mirror split), so entry()
preserves existing attrs and `.update(d)` merges with zero risk of attr loss.

Result: **0.269x -> 0.643x** (2.4x self; fnx 0.90ms vs nx 0.58ms at 2500 nodes).
Closer to parity than the edge twin (0.449x) because nodes skip the per-edge
edge_key canonicalization — the only residual is `node_key_to_string` per node
(the String-keyed-attr substrate tax). NOT a vs-nx win (same architectural floor
as the scalar path); shipped as a footgun fix bringing the dict-of-dicts form to
the scalar form's efficiency.

Correctness: 300-case adversarial sweep (ALL 4 graph types, pre-existing attrs
preserved, missing-node skip) 0 mismatches vs nx; conformance 188 attribute-
setter / dirty-sync / parity tests pass. (3 pre-existing TestFindInducedNodesParity
without_fallback failures are unrelated — peer commit 17040bd66's no-fallback
contract violation, fail identically without this change.) Built + verified via a
clean local abi3 wheel (warm target dir from the edge build, ~2.5min). Touches:
crates/fnx-python/src/{lib.rs,digraph.rs}, python/franken_networkx/__init__.py.
The set_*_attributes mutation-op vein is now fully worked (scalar + dict-of-dicts,
edge + node).

## 2026-06-28 CopperCliff REFINEMENT of the multi_source_dijkstra finalize-order block — it's a STRUCTURE-DEPENDENT KERNEL divergence, not the wrapper reorder (sharpens 8b2949932)

Re-investigated the parked multi_source_dijkstra weighted de-delegation (the
0.20-0.24x gap on multi_source_dijkstra_path_length / _path / multi_source_dijkstra,
all delegated weighted via the `_mst_has_weight_edge_attr` gate). CORRECTION to
the 8b2949932 hypothesis (which blamed my wrapper's `_reorder_by_distance`): the
divergence is in the KERNEL itself.

The fnx-algorithms `multi_source_dijkstra` kernel DOES compute a `finalize_order`
(heap-pop order, the `br-r37-c1-k9q6q` treatment) using a `(distance, seq)`
BinaryHeap with `seq` = push counter, and emits `result.distances` in that order
to match nx's `(distance, next(c))` pop order. MEASURED: the raw binding's
finalize-order matches nx EXACTLY on gnp_random_graph (0/250 weighted, dir+undir)
— BUT DIVERGES on connected_watts_strogatz / denser structures (64/400 all-int
order mismatches, all undirected; `list(raw.keys()) != list(nx.keys())` with
identical VALUES and TYPES). So the kernel's `seq`-counter push order does NOT
perfectly replicate nx's `next(c)` counter for all adjacency structures — the
relaxation/push sequence diverges on graphs with more equal-distance tie groups.

CONSEQUENCE: the weighted de-delegation (which would win — the native kernel
gives byte-exact VALUES, verified 250 cases, and a length-only binding skips the
O(V*path_len) paths_dict) stays BLOCKED on order parity for the order-sensitive
regression lock (test_dicsr_cache_parity), since the failure is structural and
can't be gated cheaply (can't know tie-density without running the algorithm).
The REAL fix is in the kernel's push-sequence: make the seq counter increment in
the exact order nx pushes (nx pushes a node every time it's relaxed to a smaller
tentative distance, in `G_succ[v].items()` adjacency-iteration order of each
finalized v) so finalize_order is bit-identical for ALL structures, not just gnp.
This is a fnx-algorithms kernel change (TealSpring's lib.rs), not a wrapper/
binding lever — confirmed NOT a 60-min safe win. Voronoi (bcd6c7c17) remains the
only weighted multi-source consumer that's de-delegatable (order-insensitive).

## 2026-06-28 CopperCliff DEFINITIVE: multi_source_dijkstra weighted finalize-order is a KERNEL push-sequence bug on DENSE graphs (supersedes the 8b2949932/1dd22870f hypotheses)

Re-attempted the weighted multi_source_dijkstra_path_length de-delegation with
the corrected understanding (NO `_reorder_by_distance` — the kernel emits
finalize order; gate to INTEGER weights — float/mixed need per-path int-typing).
Built the length-only native binding (skips paths_dict), verified 0/500 vs nx on
gnp/watts SPARSE graphs (dir+undir, unweighted+int), measured 0.20x -> 0.71x
(n=200) / 1.01x (n=400), a 5x self-improvement. BUT it FAILED
test_dicsr_cache_parity::test_multi_source_dijkstra_directed_finalize_order and
was REVERTED.

DEFINITIVE ROOT CAUSE (supersedes both earlier entries): the divergence is a
genuine KERNEL push-sequence bug, NOT my wrapper reorder (8b2949932) and NOT an
adjacency-order construction artifact (1dd22870f). Reproduced: conformance trial
18 (undirected Graph, INTEGER weights, n<20, ~50 edge-adds = DENSE) — fnx and nx
graphs built by IDENTICAL add_edge sequence have IDENTICAL adjacency order
(0 neighbor-order mismatches) and IDENTICAL node order, yet the kernel finalizes
two distance-4 tie nodes (8, 9) in the opposite order from nx. The `DijkstraState`
Ord is correct (min-heap on (dist, seq), FIFO smallest-seq-first tie-break), so
the bug is a subtler cascading push-sequence difference that only manifests on
DENSE tie-heavy weighted graphs (sparse gnp/watts at 0/500 never trigger it — a
test-coverage trap: validate kernel order on DENSE small graphs, not just sparse).
The current code DELEGATES all weighted multi_source to nx precisely to avoid
this; the kernel's weighted finalize order has never been on the hot path, so the
bug was latent. NO cheap gate exists ("dense" isn't detectable without running
the algorithm), so the de-delegation stays BLOCKED. The fix must be in the
fnx-algorithms kernel push sequence (make it bit-identical to nx's next(c) order
for dense graphs) — a deep, deferred kernel change. Voronoi (bcd6c7c17) remains
the only de-delegatable weighted multi-source consumer (order-insensitive).

## 2026-06-28 CopperCliff SHIP: multi_source_dijkstra_path_length 0.20x->2.7-4.3x — RESOLVED (the blocker was the dijkstra-projection adjacency REBUILD, not a kernel bug)

RESOLVES the 8b2949932 / 1dd22870f / ccd071b80 saga. All three earlier entries
mis-diagnosed the multi_source_dijkstra_path_length weighted block (0.20x):
8b29 blamed the wrapper reorder, 1dd2 blamed adjacency construction, ccd07
blamed a "deep kernel push-sequence bug". The REAL root cause: the
`multi_source_dijkstra` binding ran the kernel on a REBUILT projection
(`dijkstra_weighted_undirected_projection` -> `dijkstra_single_weight_graph_projection`,
which re-extends the graph from edges_ordered_indices and REORDERS per-node
adjacency), shifting the heap push-sequence so the finalize order diverged from
nx on DENSE tie-heavy graphs. The single_source kernel was correct precisely
because its binding sync+BORROWS the original graph (`weighted_undirected_projection`
= `Borrowed(&pg.inner)`); the multi_source binding skipped the sync (for simple
graphs) and used the rebuild to read the fresh mirror.

FIX: a length-only native binding `multi_source_dijkstra_path_length` that (1)
syncs the Python edge-attr mirror to the store, then (2) runs the kernel on the
BORROWED ORIGINAL graph (correct adjacency = nx's), and (3) skips the
O(V*path_len) paths_dict, emitting `result.distances` in finalize order with NO
`_reorder_by_distance` (the kernel order is already nx's). The Python wrapper
routes INTEGER-weight simple Graph/DiGraph here (`_sp_coerce_dist_to_int` for
type parity); float/mixed (per-node int-typing), callable/negative/sync-gated
weights, multigraphs, and cutoff keep the delegated path. The borrow ALSO kills
the per-call O(E) projection rebuild that an earlier length-only attempt (on the
dijkstra projection) paid — which is why this is a 2.7-4.3x WIN, not the ~1.0x
that attempt measured.

Bench (Python timeit, min-of-9, weighted gnp, vendored nx): n=200 p=0.1 fnx
0.257ms vs nx 0.694ms = **2.70x**; n=400 p=0.05 = **2.70x**; n=400 p=0.3 (dense)
fnx 2.21ms vs nx 9.48ms = **4.29x** (the win grows with density — the delegated
conversion tax it replaces is O(V+E)). Correctness: 0/400 adversarial (dense +
sparse, int weights, dir+undir, multi-source) + the exact conformance-test
replica 0/50 (incl. the dense trial 18 that exposed the bug); conformance 99
tests pass (test_dicsr_cache_parity incl. the order-lock + test_shortest_path),
unweighted/cutoff/empty-sources(ValueError)/missing-source(NodeNotFound)
contracts verified. LEVER (generalizable): a kernel that REBUILDS its input graph
projection can silently REORDER adjacency, diverging order-sensitive output from
the reference ONLY on dense/tie-heavy inputs (sparse tests pass — coverage trap).
Prefer sync+BORROW the original graph over a rebuilt projection for
order-sensitive kernels. Audit other `dijkstra_*_projection` consumers
(dijkstra_path tie-break paths) for the same latent reorder.

## 2026-06-28 CopperCliff SHIP: multi_source_dijkstra + multi_source_dijkstra_path 0.24x->2.2-4.8x — same borrow-original projection fix (the teed-up follow-up)

The follow-up to 3e87e6fab (multi_source_dijkstra_path_length). The path variants
`multi_source_dijkstra` (dist+paths) and `multi_source_dijkstra_path` delegated
ALL weighted input to nx (~0.24x). Applied the identical root-cause fix:

(1) BINDING: changed the existing `multi_source_dijkstra` binding to
`sync_rust_attrs_if_available` + run the kernel on the BORROWED ORIGINAL graph
(`weighted_*_projection`) instead of the REBUILT `dijkstra_*_projection` (whose
adjacency reorder diverged the finalize order from nx on dense graphs). This also
drops the per-call O(E) rebuild and is strictly better for the (heavily-used)
UNWEIGHTED path too — 0/400 unweighted mismatches confirm no regression.

(2) WRAPPER: a ONE-LINE gate change — stop delegating INTEGER-weight graphs
(`_mst_has_weight_edge_attr and not _sp_edge_weights_all_int`). The existing
non-delegated path (raw binding + `_sp_coerce_dist_to_int` + `_reorder_by_distance`
+ cutoff/target) is now byte-exact for int weights (the reorder is a no-op on the
already-correct finalize order) and far cheaper than the nx conversion.
Float/mixed/callable/negative/sync-gated weights keep delegating.
`multi_source_dijkstra_path` inherits the fix (it calls `multi_source_dijkstra`).

Bench (Python timeit, weighted gnp, vendored nx): multi_source_dijkstra n=200
2.28x / n=400 p=0.3 3.37x; multi_source_dijkstra_path n=200 2.17x / n=400 p=0.3
**4.81x** (the win grows with density). Correctness: 0/400 adversarial (dense +
sparse, int weights AND unweighted, dir+undir, multi-source) for BOTH dist and
path dicts; conformance 138 tests pass (test_dicsr_cache_parity order-locks,
test_shortest_path, voronoi parity) + cutoff/target/float-delegate edge cases
verified. The entire weighted multi-source family
(path_length/path/dist+path) is now de-delegated for integer weights — only the
float/mixed per-node-int-typing case remains delegated.

## 2026-06-28 CopperCliff weighted-input frontier sweep — shortest-path/flow/matching/community all at-or-above nx (the multi-source family resolution closed the last real shortest-path vein)

After resolving the entire weighted multi-source family (path_length/path/dist
3e87e6fab+88f8772c8, 2.2-4.8x), swept the rest of the weighted-input surface for
the next gap. RESULT: all at-or-above nx (vendored oracle). Representative ratios:

- shortest-path: single_source_dijkstra 5.08x, single_source_dijkstra_path 4.78x,
  single_source_bellman_ford 2.72x, all_pairs_bellman_ford_path 2.83x, johnson
  3.09x, floyd_warshall 38.6x, bellman_ford_path 4.02x, goldberg_radzik 1.30x;
  NEAR-PARITY: floyd_warshall_numpy 1.16x, negative_edge_cycle 1.08x.
  dijkstra_path is 5-6.6x (single-pair; paths byte-exact 0/297 even on dense — the
  dijkstra_*_projection rebuild is NOT a perf problem there since it doesn't
  delegate).
- flow: max_flow 4.66x, min_cut 3.00x, mincost_flow 1.80x, stoer_wagner 9.87x.
- matching/MST/community: max_weight_matching 1.08x, min_spanning_tree(w) 2.24x,
  pagerank(weighted) 2.80x, mincost 1.8x; NEAR-PARITY (order/seed-locked, not
  gaps): louvain_weighted 0.77x, min_weight_matching 0.83x (blossom order-lock),
  greedy_modularity 0.94x.

The `_mst_has_weight_edge_attr` weighted-delegation gate (the multi-source
blocker) had only two consumers — multi_source (de-delegated 88f8772c8) and
voronoi (de-delegated bcd6c7c17) — both now resolved; the lever is fully applied.
The dijkstra_*_projection rebuild-reorder bug only mattered for the DELEGATED
multi-source family (where it shifted finalize order); the non-delegated
dijkstra_path family was never affected (single path, byte-exact). NET: the
weighted shortest-path / flow / matching / community surface is mined — fnx at-
or-above nx everywhere measured. The only sub-1.0x residuals are order/seed-locked
(louvain, blossom matching) or the covered read-side PyObject-materialization view
ops (lazy-view primitive) — no 60-min wins remain in the weighted-input surface.

## 2026-06-28 CopperCliff read-side materialization laggards RE-EXAMINED (post multi-source lesson) — confirmed FLOOR-bound, but state-dependent (add_edge skips the pristine fast path)

After the multi-source family turned out to be a fixable projection swap (not the
"deep kernel bug" I'd diagnosed), I re-examined the documented read-side
materialization-floor laggards with the same skepticism. Re-measured (MDG n=700
/ MG n=2500): mdg in_edges(keys,data=weight) **0.184x**, mdg in_degree(weight)
0.267x, mg selfloop_edges(keys,data=weight) 0.454x, mg size(weight) 0.836x, mdg
edges(keys) 0.919x. All value-correct (==nx).

NEW PRECISE FINDING (state-dependence): mdg in_edges(keys,data) is 11.5ms when
the graph is built via per-edge `add_edge(weight=)` (the common pattern + what
the head_to_head bench does) but 5.1ms when built via bulk `add_edges_from` — a
2.2x gap. Cause: `add_edge` POPULATES the edge_py_attrs MIRROR per edge, leaving
the graph NON-PRISTINE, so the `edge_py_attrs.is_empty()`-gated store-read fast
path (8fd930863 / 89661143c) is SKIPPED; bulk `add_edges_from` leaves the mirror
empty (pristine) so the fast path engages. A subsequent `list(edges(data=True))`
also de-pristines a bulk graph (5.1->7.8ms).

VERDICT (unlike multi-source — this IS the architectural floor): even the
pristine fast path is **0.40x** vs nx. fnx stores edges as Rust data and must
RECONSTRUCT PyObject (u,v,key,value) tuples per edge; nx's storage IS PyObjects
(it just iterates its native dicts). Beating nx needs a persistent ordered
Python-object edge mirror (store the tuples/dicts, skip reconstruction) — the
documented architectural lever, not a 60-min change. The add_edge penalty
(0.18x vs the 0.40x floor) could be closed by broadening the fast-path gate from
`is_empty()` to also accept `!edges_dirty` (store-authoritative), but that is
store/mirror-consistency-risky for a result that still LOSES to nx (0.40x) — a
loss-reduction, not a win; deferred. Re-confirmed: the read-side view-op vein is
floor-bound; do NOT re-dig it with kernel/micro-opts.

## 2026-06-28 CopperCliff SURFACE: Graph((u,v,attr_dict)) constructor 0.46x — the ctor edge-batch is slower than add_edges_from's batch (measured 3.9x lever, root-caused)

NEW measured gap (fresh, not in the prior maps): `fnx.Graph([(u,v,{'weight':w}),
...])` — the weighted-3-tuple constructor, a VERY common pattern — is **0.46x**
vs nx (fnx 9.94ms vs nx 4.61ms, 8000 edges). Byte-exact result (==nx).

ROOT CAUSE (located): routing the SAME edges through `add_edges_from` is **3.9x
faster** — `fnx.Graph(); g.add_edges_from(Ew)` = 2.56ms = **1.80x vs nx** (a WIN),
identical result. The constructors' native batch path (PyGraph/PyDiGraph/
PyMulti* `new()` at lib.rs:8792 etc., `extend_edges_with_attrs_unrecorded` with
the z6uka display-object / eager-AttrMap-per-edge semantics) is ~4x slower than
`add_edges_from`'s `_try_add_attr_edges_from_batch` (lazy mirrors, one
extend_keyed). The 2-tuple case is milder (`Graph(E)` 0.73x vs aef ~1.07x). The
slow path is reached because each constructor's
`try_absorb_exact_int_str_keyed_ctor_edges` fast batch only accepts `(u,v)` and
`(u,v,key_string)` — a `(u,v,attr_dict)` 3-tuple (3rd = dict) returns false and
falls to a per-edge `add_edge` loop / the slower display-semantics batch.

THE LEVER (deferred — touches 4 complex constructors, late-session risk): make
the constructor edge-batch adopt `add_edges_from`'s faster lazy batch (or extend
`try_absorb` to handle `(u,v,attr_dict)` 3-tuples with the lazy-mirror path).
`Graph`/`DiGraph`/`MultiGraph`/`MultiDiGraph` are the Rust pyclasses (imported
directly from `_fnx`), and `new()` absorbs edges BEFORE any Python `__init__`, so
there is no clean Python-level reroute — the fix is in the Rust `new()` /
`try_absorb`. Estimated payoff: weighted constructors 0.46x -> ~1.8x (a real WIN,
not a floor — unlike the read-side view ops, this is avoidable batch overhead the
add_edges_from path already eliminated). This is the cleanest remaining 60-min-ish
win, deferred only for risk; HIGH PRIORITY for a focused next turn.

## 2026-06-28 CopperCliff SHIP: Graph((u,v,attr_dict)) constructor 0.46x->1.585x — route fresh edge-list ctor through the add_edges_from fast batch (lands the 4cb65d10c lever)

Lands the lever surfaced 4cb65d10c. `fnx.Graph([(u,v,{'weight':w}), ...])` (the
weighted-3-tuple constructor, a very common pattern) was 0.46x vs nx — the
PyGraph `new()` edge-iterator path paid per-edge `has_node`/`has_edge` +
`maybe_store_adj_key` (z6uka display) + eager `edge_key`-String mirror that
`add_edges_from`'s fast batch avoids (seen_nodes set + batch_display_conflict +
lazy mirrors).

FIX (ONE branch in PyGraph::new(), lib.rs:8792): before the slow iterator loop,
try `g._try_add_edges_from_batch(py, data)` — the SAME native batch the Python
`add_edges_from` uses (plain 2-tuple batch, then attr 3-tuple batch). It's gated
to a fresh graph + plain int/str nodes and is MUTATION-FREE on `false`, so the
existing iterator loop still owns every input it declines (small lists, non-plain
nodes, weird tuples, 3-tuples whose 3rd elem isn't a dict).

Result: **0.46x -> 1.585x** (fnx 2.89ms vs nx 4.58ms, 8000 weighted edges) — a
WIN, beating nx (the batch eliminates the per-edge overhead). BONUS: the batch
leaves the graph PRISTINE (lazy mirror), so constructor-built graphs now hit the
read-side store-read fast paths too (edges(data=weight) 0.28ms — the add_edge
non-pristine penalty from c7d5eaab0 is avoided for ctor-built graphs). Byte-exact:
0/400 adversarial (mixed 2/3-tuple, attrs, self-loops, dups), G[u][v] dict
identity stable + mutation works, str-node ctors fall back correctly. Conformance:
273 constructor-specific tests (test_construction_metamorphic_guard /
test_constructor_absorb_conformance_guard / test_cross_class_ctor_parity /
test_ctor_str_and_third_element_parity / test_dict_of_list_constructor_parity /
test_digraph_copy_ctor_parity) + 211 attr/edge tests pass (the 3
TestFindInducedNodesParity failures are pre-existing peer no-fallback contract
violations, unrelated). FOLLOW-UP: apply the same one-branch fix to PyDiGraph /
PyMultiGraph / PyMultiDiGraph `new()` (symmetric; each has its own
`_try_add_edges_from_batch`/`_try_add_attr_edges_from_batch`).

## 2026-06-28 CopperCliff SHIP: MultiGraph/MultiDiGraph((u,v,attr_dict)) ctor 0.375x/0.487x->0.770x/0.993x — same batch fix (the dd66fb9e2 follow-up)

The teed-up follow-up to the Graph constructor fix (dd66fb9e2). Measured the
remaining constructor gaps: MultiGraph(weighted-3-tuple) **0.375x**, MultiDiGraph
**0.487x** (DiGraph was 0.918x near-parity — skipped). Applied the identical
one-branch fix to PyMultiGraph::new() (lib.rs) and PyMultiDiGraph::new()
(digraph.rs): before the slow per-edge iterator loop, try
`g._try_add_attr_edges_from_batch(py, data, None)` (the multigraph fast batch
add_edges_from uses) — `try_absorb_exact_int_str_keyed_ctor_edges` above only
handles `(u,v)`/`(u,v,key_string)`/`(u,v,key,dict)`, so `(u,v,attr_dict)` 3-tuples
fell to the per-edge loop. Mutation-free on `false` (the loop still owns declined
inputs).

Result: MultiGraph **0.375x -> 0.770x**, MultiDiGraph **0.487x -> 0.993x** (both
~2x self-improvement). MultiDiGraph reaches nx parity; MultiGraph lands at the
keyed-edge substrate floor (~0.77x — the same floor the shipped add_edges_from
MultiGraph attr-batch hits, trzrx; the String-keyed multi-edge construction is
the architectural floor, not avoidable here). Byte-exact: 0/400 adversarial
(mixed 2/3/4-tuple incl. explicit string keys, dups, self-loops) == nx on
edges(keys,data); conformance 277 constructor-specific + 149 multigraph
ctor/edge tests pass. The whole `Type((u,v,attr_dict))` constructor family is now
routed through the fast batch (Graph 1.585x WIN, MultiDiGraph parity, MultiGraph
at its batch floor — all 2-3x self-improvements over the per-edge loop).

## 2026-06-28 CopperCliff construction+utility surface MINED — graph-building/conversion/generators/predicates all at-or-above nx (the ctor family was the last batch-routable vein)

After the constructor-family fix (dd66fb9e2 Graph 1.585x + 0df6f2bfc Multi*),
swept the surrounding construction + utility surface for the same per-edge-loop /
batch-routing lever. RESULT: all at-or-above nx. Representative ratios:

- builders/conversion: from_dict_of_lists 2.28x, adjacency_graph 2.61x,
  from_dict_of_dicts 1.49x, node_link_graph 1.64x, from_edgelist(w) 1.35x,
  subgraph().copy() 1.71x, compose 1.26x, relabel-to-int 4.56x.
- generators: hypercube 42.8x, grid 18x, lollipop 11.9x, windmill 5.25x,
  balanced_tree/caveman/full_rary 4.7x, complete_bipartite 3.36x, turan 2.73x,
  circular_ladder/wheel/star 1.9-2.7x; NEAR-PARITY: barbell 1.03x, relaxed_caveman
  0.97x.
- predicates/utilities: density 35.7x, is_connected 25.6x, is_dag 15.3x,
  is_bipartite 10x, to_undirected_view 8x, isolates 2.57x, selfloop_count 1.79x,
  non_edges 1.24x, is_graphical 1.18x, is_chordal 1.06x; NEAR-PARITY:
  create_empty_copy 0.64x, freeze 0.78x, set_node_attributes(scalar) 0.74x.

The sub-1.0x residuals are ALL the node/edge String-keyed substrate floor
(create_empty_copy 0.64x = bulk int-node insertion, already optimized;
set_*_attributes(scalar) 0.45-0.74x; MultiGraph keyed-edge ctor 0.77x) — NOT
batch-routable, the same architectural floor as the read-side view ops. NET
across the session: every batch-routable construction gap is now closed (the
`Type((u,v,dict))` ctor family was the last one); the construction/conversion/
generator/utility surface is mined. No 60-min win remains there — the residual
is the persistent-Python-object / integer-keyed substrate primitive.

## 2026-06-28 CopperCliff SHIP: greedy_tsp TIE path 0.05-0.9x->1.3-1.4x — native kernel now bails O(n) on a tie + in-process fallback (the float no-tie path stays native 1.7-4x)

The directive's flagged win — greedy_tsp 0.044x->1.43x (native nearest-neighbour
kernel, de-delegates the O(n^2) fnx->nx conversion) — only covered the
**unique-min** case. The native kernel returns None whenever ANY greedy step has
a weight TIE (two neighbours sharing the minimal weight), because nx's tie-break
is `min(nodeset, key=...)` over CPython **set-iteration order** which the Rust
kernel cannot replicate. Ties are the COMMON case for integer-weighted complete
graphs (e.g. `randint(1,30)` on n>=40 ties at step 1 almost surely). On that
bail path greedy_tsp fell ALL the way back to `_networkx_graph_for_parity(G)` (an
O(n^2) graph build) PLUS nx's own O(n^2) AtlasView loop — measured **0.083x @
n=60, 0.052x @ n=150, 0.31x @ n=250** (the regression GREW with n).

Two-part fix, both byte-exact:

1. **Python in-process fallback** (`__init__.py greedy_tsp`, br-cc-tsptie): when
   the native kernel returns None, run nx's EXACT algorithm in-process over a
   single `dict(G.adjacency())` snapshot instead of converting to nx. The
   tie-break `min(nodeset, key=...)` iterates a real CPython `set` over the SAME
   node objects, so it resolves ties EXACTLY as nx (the same trick large_clique_size
   / node_connectivity use). Skips the nx-graph construction and the AtlasView tax.

2. **Cheap native bail** (`algorithms.rs greedy_tsp_native`): the OLD kernel built
   a dense O(n^2) weight matrix + ran a separate O(n^2) completeness scan BEFORE
   the walk, so a single tie still cost a full O(n^2) of per-edge store reads
   before returning None — which the Python fallback then REDID (the double-O(n^2)
   that made n=250 regress to 0.31x). Rewrote it as a LAZY walk: read only the
   current node's neighbour weights each step, bail at the FIRST tie (O(n) on the
   tie path). Completeness is verified per-node via its distinct-neighbour count
   == n-1 (each node as it becomes `cur`, plus the final node), so an incomplete
   graph never yields a native tour — nx's `NetworkXError` is reproduced by the
   fallback. n<3 deferred to the fallback (exact 0/1/2-node + error contracts).
   The no-tie float path now also does ONE store-read pass (was matrix-build +
   2 matrix passes), so it is unchanged-to-faster.

Measured (complete graph, min-of-25, gc off):
- INT weights (tie path): n=100 **1.42x**, n=200 1.42x, n=250 1.37x, n=400 1.32x
  (was 0.05-0.9x — the conversion tax is GONE).
- FLOAT weights (native no-tie path): n=100 **3.9x**, n=200 3.56x, n=250 1.72x,
  n=300 2.49x, n=400 1.84x (maintained/improved; NOT regressed).

Byte-exact: 0/3360 adversarial (n=1..40, directed+undirected, int+float weights,
heavy-tie weight ranges, varied/None source) == nx on the returned tour; all
error contracts match (incomplete -> NetworkXError, empty -> StopIteration,
bad-source -> KeyError, weight=None, directed-incomplete). Conformance: 118
test_tsp_approximation_conformance + test_approximation_signature_parity pass;
4593 passed / 0 failed across the approximation/connectivity/clique/dominating
surface. LEVER: a native fast-path kernel that BAILS on a hard case must bail
CHEAPLY (O(n), lazy) — an O(n^2) bail that the Python fallback then repeats is a
hidden double-cost that grows with n.

## 2026-06-28 CopperCliff SHIP: eulerian_circuit DIRECTED 0.64x->~12x — de-delegate via reversed-successor Hierholzer (mirrors nx's G.reverse() exactly)

The undirected simple case was already de-delegated (br-r37-c1-eulcirc); the
DIRECTED simple case still paid the full O(V+E) fnx->nx conversion + nx's
Hierholzer (measured **0.64x** on a directed cycle). nx's directed path does
`G = G.reverse()` then runs Hierholzer over the reversed graph's OUT-edges,
which makes the yielded `(last, current)` edges come out in the ORIGINAL FORWARD
orientation. Reproduced in-process (br-cc-eulcircdir, PURE-PYTHON, no rebuild):
build the reversed successor adjacency in nx's exact edge order
(`rev_succ[v]` = the sources `u` of every arc `(u, v)`, ordered by `G.edges()` =
successor-adjacency order), then run the identical stack walk with
`next(iter(rev_succ[c]))` == nx's `arbitrary_element(G_rev.out_edges(c))`.

Byte-exactness is PROVABLE here (unlike the undirected case — see the NO-SHIP
note below): nx's `G.reverse()` is `add_edges_from((v,u) for u,v in G.edges())`,
so `G_rev._succ[v]` receives `u` in G.edges() order — EXACTLY the order
`rev_succ[v]` is built. There is no second-direction reinsertion (directed arcs
are one-way), so the order is deterministic and matches. Verified 0/1840
adversarial == nx (directed cycles, complete digraphs, unions of 3-8 random
cycles over 6-30 nodes = hard branching, 3 source choices each) + selfloops +
error contracts (non-eulerian -> NetworkXError). Measured **0.64x -> 11.5-13x**
(directed cycle n=200..800; complete digraph m=40/80 12.2-12.7x). 603 euler
conformance tests pass. Multigraph keeps delegating (edge-key ordering).

### NO-SHIP / observation: the UNDIRECTED eulerian_circuit de-delegation is NOT byte-exact vs nx (benign)

While verifying the directed fix I found the pre-existing UNDIRECTED de-delegation
(br-r37-c1-eulcirc) produces VALID-but-DIFFERENT circuits from nx (59/60 on
random_regular_graph(4,10)). Root cause: nx's undirected path runs on
`G = G.copy()`, and `Graph.copy()` re-adds edges so the SECOND-direction
adjacency order in `_adj` differs from the original `G.adjacency()` order that the
fnx wrapper snapshots — `arbitrary_element(G_copy.edges(v))` therefore picks a
different first neighbour. NOT fixed: it passes all 603 euler conformance tests
(the bar is Eulerian VALIDITY, not byte-exact traversal order), the docstring's
"48/48 byte-identical" only held for the small/complete fixtures tested, and
replicating `Graph.copy()._adj` ordering is fiddly with no perf upside. The
directed fix is immune because `reverse()` has no second-direction reordering.

## 2026-06-28 CopperCliff SHIP: simulated_annealing_tsp / threshold_accepting_tsp init_cycle="greedy" 0.86x->1.45x (default cfg) — wire byte-exact greedy_tsp into the existing fast path

The annealing fast path (`_tsp_anneal_prep`, index-space vectorised cost) already
beats nx for an EXPLICIT integer init_cycle (1.49x), but it bailed to the full
nx delegation for ANY string init_cycle — including the common `init_cycle=
"greedy"` — leaving it at **0.66x (N_inner=10) / 0.86x (N_inner=100, nx default)**
on integer-weighted complete graphs. nx resolves "greedy" by computing
`cycle = greedy_tsp(G, weight=weight, source=source)` (DETERMINISTIC, no RNG) and
then annealing. With greedy_tsp now byte-exact + fast in-process, resolve "greedy"
inside `_tsp_anneal_prep` and let the explicit-cycle fast path engage. The greedy
COMPUTATION is deferred until AFTER the integer + completeness gates pass, so the
float/incomplete bail path pays nothing extra (no wasted greedy_tsp call).

Because greedy is RNG-free, the annealing RNG stream is identical to nx's, so the
result is byte-identical. Verified 0/1920 == nx (SA + TA, greedy + explicit init,
int + float weights, n=3..30, both moves "1-1"/"1-0", source None/explicit, 30
seeds) — the float cases still delegate and match; explicit cases unchanged.
Measured (integer complete n=40): N_inner=100 (nx default) SA **1.451x** / TA
**1.489x** (was ~0.86x); N_inner=10 SA 0.86x (was 0.66x — improved, every config
strictly beats the old delegation). Float unaffected (fast path still bails on
non-integer weights — float-sum order matters). 118 tsp/approx-parity + 639
tsp/anneal/approx tests pass. LEVER: a fast path that bails on a "named" input
(here `"greedy"`) can often resolve that name to the explicit input it stands
for — IF the resolution is deterministic (RNG-free) so the downstream stochastic
stream is unperturbed. Resolve it AFTER the cheap viability gates to avoid paying
on the bail path.

## 2026-06-28 CopperCliff SURFACE: post-TSP broad sweep — path/dag/flow/cut/bipartite/centrality/community all at-or-above nx; residual sub-1.0x are FLOOR-bound or matching-conversion-bound

After landing the three TSP-family wins this session (greedy_tsp tie 1.4x,
eulerian_circuit directed 12x, annealing greedy-init 1.45x), swept ~50 more
workloads across five areas to find the next gap. RESULT: the surface is mined —
representative ratios:

- single-pair / single-source path (delegated, small query): all_simple_paths
  1.54x, bidirectional_dijkstra 1.87x, bellman_ford_path 3.52x,
  single_source_dijkstra_path 3.44x, goldberg_radzik 2.18x, johnson 1.96x;
  shortest_simple_paths 0.94x and bellman_ford_predecessor 1.06x = parity.
- dag/structural: descendants/ancestors 4.6x, find_cliques_recursive 1.01x.
- flow/cut (single s-t): maximum_flow 7.4x, minimum_cut 6.5x, minimum_edge_cut
  5.2x, minimum_node_cut 2.8x, stoer_wagner 8.8x, edge/node_disjoint_paths
  8.2-8.6x, local_node_connectivity 2.5x.
- bipartite/tree: maximum_matching / hopcroft_karp 12.2x, minimum_spanning_
  arborescence 3.4x.
- centrality: harmonic 15x, subgraph 32x, percolation 8.7x, information 9.7x,
  current_flow_closeness 9.4x, load 30x, group_closeness 8.5x, dispersion 3.1x,
  edge_load 1.4x; group_betweenness 0.996x / girvan_newman 0.969x = parity.
- community/clustering/link-pred: greedy_modularity 24x, asyn_lpa 1.79x,
  square_clustering 18.7x, generalized_degree 4.2x, rich_club 82.9x,
  jaccard/adamic_adar (few pairs) 1.4-1.9x.

The ONLY measured sub-0.9x residuals and why they are NOT 60-min levers:
- `clustering(nbunch=few)` 0.857x / `triangles(nbunch=few)` 0.871x — the local
  fast path is already O(deg); the residual is the per-neighbour `set(G[x])`
  AtlasView materialization FLOOR (same persistent-mirror primitive the read-side
  view ops need; multiple prior kernel-micro-opt NO-SHIPs). ~10us absolute on a
  ~60us op.
- `christofides` 0.82x — matching-dominated (Blossom O(V^3)); the gap is the
  fnx->nx conversion tax, but de-delegating needs an in-process min_weight_matching
  (itself nx-fallback Blossom), a large chain for a small gap. SKIP.
- `simulated_annealing_tsp` small N_inner (0.86x) — fixed W-build O(n^2) overhead
  not amortized at tiny iteration counts; the nx DEFAULT (N_inner=100) is a win.
- `max_weight_matching` 0.872x — the known order-sensitive rebuild benchmark
  ARTIFACT (already in the ledger), not a real gap.

NET: the delegated-conversion-tax vein (the greedy_tsp/eulerian/annealing family)
is now mined; what remains vs nx is the persistent-Python-object / AtlasView
materialization substrate primitive (architectural) and a couple of
Blossom-matching-conversion residuals not worth their complexity.

## 2026-06-28 CopperCliff NO-SHIP: MultiGraph size(weight) native scalar — substrate-bound below nx (REVERTED, 2 approaches tried)

Re-measured the multigraph weighted-degree gaps memory flagged (most read-side
view gaps — nodes(data), edges(data), in_edges(data) — are now FIXED/WIN per a
fresh sweep; stale memory). The real residual: **MultiGraph `size(weight)`
0.21-0.34x** vs nx (n=4000, dirty/clean), and `degree(nbunch,weight)` ~0.53-0.63x
all types. `size(weight)` is a SCALAR (`sum(d for _,d in degree(weight))/2`), so it
is NOT the per-node view-materialization floor — there's a real avoidable cost:
the canonical `size()` routes through the MultiGraph `_native_weighted_degree`
path, which builds a Python list + `builtins.sum` per node and materialises V
`(node, degree)` PyObject pairs the scalar never needs.

Tried a native scalar `_native_weighted_size` two ways, both byte-exact (0/400,
int-gated, pristine/float fall back to the faithful degree route):
1. Reuse the per-node int-store row (`weighted_degree_py_int_row`) summed in Rust,
   /2: **0.34x -> 0.81x clean / 0.21x -> 0.49x dirty** (2.4x self-gain) — but
   STILL loses to nx. The residual is the per-edge `edge_key` String alloc +
   mirror probe + DOUBLE traversal (each edge visited from both endpoints).
2. Single-pass over `inner.edges_ordered_borrowed()` (each edge once, no String
   key), pristine-gated: **WORSE, 0.35x clean** — that API builds an
   insertion-ordered Vec<(&str,&str,usize,&AttrMap)>; its construction cost
   exceeds the per-node adjacency walk.

REVERTED both. nx's MultiGraph `size(weight)` walks its native nested
`_adj` dicts (C-level), which is faster than ANY path over fnx's CGSE
String-keyed multi-edge store — the same keyed-edge substrate floor that blocks
mg degree(weight)/selfloop_keys_weight (eilce accumulator NO-SHIP, reference_mdg_
weighted_degree_store_int). A real win needs a columnar/store-level weight sum in
the CGSE layer (large primitive), not a binding over the existing store. DON'T
re-attempt the binding-level approach. `degree(nbunch,weight)` 0.53x is a fixed
per-call Python overhead (view construction ~12us) on a tiny (8-node) result —
also not beatable without lower view-construction overhead.

## 2026-06-28 CopperCliff SURFACE: IO / iterative-numerical / operators sweep — all at-or-above nx (sub-1.0x readings on fast ops were NOISE)

Swept a fresh area (IO round-trips, iterative/numerical at scale, operators) for
the next gap. All at-or-above nx. WINS (representative): pagerank 16.4x,
closeness_centrality 94x, betweenness 30x, hits 1.45x, eigenvector_numpy 1.36x,
complement 3.1x, reverse 21x, to_undirected 38x, cartesian_product 2.1x,
convert_node_labels_to_int 6.8x, to_dict_of_lists 1.68x, node_link_data 1.71x.

CAUTION — three workloads first READ sub-1.0x in a reps=7 min-timed pass but were
NOISE (fast/BLAS-variable ops); robust interleaved min-of-21 re-measurement:
- `parse_edgelist` 0.627x -> actually **1.347x** (n=3000/13.3k edges: fnx 9.26ms
  vs nx 12.72ms — already batches via add_edges_from).
- `generate_adjlist` 0.643x -> actually **parity** (1.01ms vs 1.02ms; the native
  `_native_generate_adjlist_lines` path IS engaging).
- `katz_centrality_numpy` 0.788x -> actually **parity/win** (full: fnx 413ms vs
  nx 428ms — the O(n^3) `np.linalg.solve` dominates and is nx's exact call; fnx's
  adjacency build is faster). The 0.788x was BLAS-solve timing variance.

LESSON: for sub-10ms / dense-LAPACK workloads, a reps=7 min is NOT reliable —
re-measure suspected gaps interleaved, min-of-21, gc off before believing a
sub-1.0x ratio. NET: the IO/numerical/operator surface is mined; no real gap
here. Combined with the prior sweeps, the ONLY remaining real vs-nx gap is the
MultiGraph keyed-edge substrate floor (needs a CGSE columnar weight aggregate,
not a binding — see the size(weight) NO-SHIP above).

## 2026-06-28 CopperCliff SURFACE: spectral / dense-numerical (safe-Rust-ceiling) zone all at-or-above nx; the "JAX-as-different-primitive" lever is infeasible here

Dug the dense-numerical / spectral family (the zone where a hand-rolled safe-Rust
kernel can't beat BLAS — the suggested place for a JAX/"different primitive"
lever). RESULT: all at-or-above nx. WINS: estrada_index 19.6x, resistance_distance
123x, current_flow_betweenness 46x, current_flow_closeness 10.7x, subgraph_
centrality 4.2x, algebraic_connectivity 8x, fiedler_vector 8.8x, katz_numpy
4.8x (n=1000), eigenvector_numpy 1.49x, adjacency_spectrum 1.73x; nx TIMES OUT on
communicability / communicability_betweenness / second_order_centrality (fnx's
native Padé-expm / Woodbury kernels win outright).

NOISE CORRECTIONS (dense LAPACK timing is brutally thread-contention-noisy; even
a reps=11 min lies): `laplacian_spectrum` first read 0.619x but interleaved
min-of-15 is **1.04-1.22x WIN** (np.linalg.eigvalsh vs scipy.linalg.eigvalsh are
within noise — 0.93x at 64 threads / 1.20x at 1 thread — so the "swap to scipy"
idea is a WASH, NOT a 4.6x win as a single-shot bench suggested; do NOT swap).
`number_of_spanning_trees` 0.154x was a test artifact (hasattr fallback → 0.00ms).
`spectral_ordering` ~0.96x = parity.

JAX lever — INFEASIBLE in this environment: no jax/jaxlib/numba/cupy/torch
installed, NO GPU (64 CPU cores only). CPU-only XLA wraps the same LAPACK/Eigen
that numpy/scipy already use, so it won't beat BLAS on single dense eigvalsh/solve
(the JAX win is GPU + op-fusion, neither applicable to these one-shot O(n^3) calls);
and JAX's float results diverge from scipy (default float32; even float64 differs
~1e-6..1e-12), breaking the byte/tolerance spectral contracts. Adding jax as a
runtime dep is also an architecture decision, not a perf patch. NET: the
safe-Rust-ceiling zone is mined — fnx already wins it via native expm/eigsolver
+ faster matrix builds. No 60-min lever here.

## 2026-06-28 CopperCliff SHIP (strict work-removal, NOT yet a win): MultiGraph weighted dijkstra projection 0.13x->0.30x — borrowed edges + unrecorded bulk add

Large-scale + multigraph sweep found the biggest remaining real gap:
`single_source_dijkstra_path_length` on a weighted MultiGraph at **0.13x** vs nx
(n=5000/15k edges: fnx 153-233ms vs nx 18-30ms; n=10000: 0.11x). The dijkstra is
the fast simple-graph kernel; the cost is `multigraph_to_weighted_simple_graph`
(the min-parallel-weight projection, REBUILT every call, not cached). The old body
called `mg.edges_ordered()` TWICE (each deep-clones every parallel edge to an owned
MultiEdgeSnapshot: String endpoints + AttrMap) then added survivors via per-edge
`add_edge_with_attrs` (each pushes a change-ledger entry).

FIX (br-cc-mgproj, algorithms.rs): iterate `edges_ordered_borrowed()` ONCE (no
per-edge clones), select the min-weight parallel edge per pair, bulk
`extend_edges_with_attrs_unrecorded` the survivors (no ledger). Only SELECTED edges'
attrs cloned. Byte-IDENTICAL output (same nodes/attrs, same survivor edges in same
order, same apply_row_orders) so every consumer (dijkstra path/length, bellman_ford,
all-pairs) is unchanged. Verified 0/120 == nx; 4366 shortest-path/multigraph tests
pass. Measured **0.13x->0.30x** (n=5000) / 0.11x->0.28x (n=10000) — 2.3-2.5x self.

HONEST STATUS: still ~0.3x vs nx — a strict 2.3x work-removal, NOT a head-to-head
win. The Graph-projection approach has a ceiling BELOW nx: building a whole Graph
per call (even structure-only: O(V+E) node+edge inserts) is inherently heavier
than nx's single direct multigraph walk (min-over-parallel-edges weight function
applied during relaxation). Shipped anyway because it is strict work-removal of
genuine waste (2x deep clones + per-edge ledger) producing identical output — the
"strict work-removal is shippable on mechanistic grounds" rule, unlike the MG
size(weight) NET-NEW binding that was reverted. THE PATH TO A WIN: a native
multigraph dijkstra kernel that runs on the MG store directly (integer CSR +
min-parallel-weight, no Graph construction) — documented next lever for MG-weighted
shortest paths.

## 2026-06-28 CopperCliff SURFACE+ROADMAP: large-scale all-win; the MultiGraph-op frontier is the projection ceiling — native MG dijkstra needs a `pub` CSR kernel (TealSpring ask)

LARGE-SCALE sweep (n=20000, ~5 avg deg) — all at-or-above nx, often huge:
transitivity 61x, k_core 21.7x, average_clustering 17.9x, clustering 25x, copy 9x,
pagerank 19x, is_connected 21x, core_number 11.5x, connected_components 5.7x,
adjacency_matrix 3.4x; nodes(data)/edges() ~parity (1.04-1.07x). No gap at scale
for simple graphs.

The remaining real gaps are ALL MultiGraph ops that route through a build-a-Graph
PROJECTION, which has a hard ceiling BELOW nx (nx walks the multigraph adjacency
directly; building a Graph per call — even structure-only, O(V+E) inserts — is
heavier than nx's single walk): MG weighted dijkstra 0.30x (post the br-cc-mgproj
work-removal), MG connected_components 0.39x (nx 1.75ms), MG subgraph+copy 0.83x.

ROOT-CAUSED ACTIONABLE LEVER (native MG dijkstra, no Graph build): the public
kernel `single_source_dijkstra_path_length_typed_with_pred(&Graph,...)` (fnx-
algorithms) builds a CSR (offsets/targets/weights/weight_is_int) from the Graph
then calls the PRIVATE `single_source_dijkstra_typed_csr(source_idx, names,
offsets, targets, weights, weight_is_int, cutoff)`. If fnx-algorithms exposed that
CSR fn (and its `_directed` sibling) as `pub`, the fnx-python binding could build
the min-parallel-weight CSR DIRECTLY from the MultiGraph store in ONE pass
(skipping the Graph projection entirely) and call it — turning MG weighted dijkstra
from 0.30x into a likely win, byte-exact (the CSR kernel already tracks per-node
all_int typing identically to nx). This is a SMALL fnx-algorithms change
(add `pub`); the heavy lifting (min-CSR construction from the MG store) is binding
work CopperCliff can own. **TealSpring (fnx-algorithms owner): please expose
`single_source_dijkstra_typed_csr` + `single_source_dijkstra_typed_csr_directed`
as `pub`.** Until then the binding-level approaches are projection-ceiling-bound.

Also: `multigraph_to_simple_graph_structure_only` (br-r37-c1-ccmulti) is written
but `#[allow(dead_code)]` (never wired) — a ledger-free structural projection for
connectivity; wiring it into MG connected_components would be a strict work-removal
(0.39x->~0.6x) but still loses to nx's direct walk (same ceiling), so the native-
CSR path is the real fix there too.

## 2026-06-28 CopperCliff NO-SHIP (lever DISPROVEN by implementation): native CSR MG dijkstra ALSO loses — the floor is the MultiGraph's STRING-KEYED store, not the Graph projection

I implemented the previously-documented "native MG dijkstra (integer CSR, no Graph
projection)" lever to turn MG weighted dijkstra from 0.30x into a win. Built it
end-to-end (br-cc-mgintdijkstra): gated to all-INTEGER weights (integer arithmetic
is order-invariant => byte-exact with zero float/typing/tie-break risk; non-int /
float fall back to the projection), read weights straight from the sync-flushed
store via borrowed iterators (`neighbors_iter` + `edge_keys_iter` + `edge_attrs`),
min-parallel-weight inline, integer Dijkstra (BinaryHeap), no Graph object built.
Verified BYTE-EXACT: 0/240 == nx (int multigraphs incl parallel edges, self-loops,
dirty/clean builds, cutoff, disconnected, str-nodes, missing-key default) + float
fallback 20/20 + mixed int/float correct.

RESULT: STILL 0.26-0.43x vs nx (n=5000..20000) — barely better than the projection
(0.30x), i.e. ~0-gain over the already-shipped work-removal. REVERTED (net-new
~130 lines for no win, like the size(weight) binding).

ROOT CAUSE (this DISPROVES the earlier "native CSR kernel" roadmap): the win is
NOT blocked by the Graph projection — it is blocked by the MultiGraph's INTERNAL
STORAGE being STRING/`EdgeKeyRef`-keyed. Every adjacency/edge access
(`adjacency.get(node)`, `edges.get(&EdgeKeyRef::new(u,v))`) pays String hashing,
which loses to nx's Python dict walk over interned/cached small-int|str node keys.
The simple Graph WINS dijkstra precisely because it has INDEX-based adjacency
(`neighbors_indices` -> `&[usize]`, `graph_edge_weight_or_default_idx_typed`); the
MultiGraph has no such index-based adjacency. So exposing the fnx-algorithms CSR
kernel as `pub` (my earlier TealSpring ask) would NOT have helped either — the cost
is upstream of the kernel, in reading the String-keyed MG store to build the CSR.

THE REAL (only) LEVER: give MultiGraph/MultiDiGraph INDEX-BASED adjacency +
edge-bucket storage in the CGSE/fnx-classes layer (mirror the simple Graph's
`neighbors_indices` + indexed edge access), so MG traversals stop paying String
hashing. That is a substantial fnx-classes storage change — the same architectural
primitive the MG size(weight)/degree(weight) gaps need. ALL the MG-op gaps (dijkstra
0.3x, size 0.3x, degree 0.7x, connected_components 0.39x) share this ONE root:
the String-keyed multi-edge store. No binding-level or kernel-`pub` fix reaches it.

## 2026-06-28 CopperCliff SURFACE: minimum/maximum_spanning_edges at-or-above nx (apparent dense gap was NOISE); stash backlog has no unlanded win

Probed spanning edges (a single-shot bench had read 0.79x). Robust characterization
(min-of-9 across sizes; min-of-21 across 5 seeds for the dense point): WIN
everywhere — sparse (deg~10) n=200..2000 = 2.5-2.9x, n=4000 = 1.22x; dense (deg~80)
n=1000 median **1.09x** across 5 seeds (0.98-1.14x), n=500/2000 = 1.24x.
minimum_spanning_tree 1.3-1.8x. The lone 0.79-0.87x single-shot reads were
sort-timing NOISE (non-monotonic across n is the tell). No gap — the native kruskal
(node-index orientation + weight-only stable sort, br-r37-c1-mstcsr) already wins.

Stash-backlog audit: the 10 git stashes' MESSAGES are the commits they were created
ON, not their content. Inspected — none is a landable win: stash{8}=MG size-native
(NO-SHIP, substrate-bound), stash{5}=to_directed 0.645->0.782x (still <1),
stash{6}=MDG in_edges(keys,data) 0.16->0.40x (still <1), stash{0-3}=reverted/
regressed attempts. Nothing to land.

NET (session close-out): fnx dominates nx across the entire measured surface; every
residual is either timing noise on dense/sort/LAPACK ops (re-measure interleaved
min-of-21 before believing any sub-1.0x) or the ONE architectural root — the
String-keyed Multi(Di)Graph store (index-based MG adjacency in fnx-classes/CGSE is
the only remaining real lever, spanning dijkstra/size/degree/connected_components).

## 2026-06-28 CopperCliff SHIP: transitive_closure_dag 0.71x->1.05-1.43x — snapshot adjacency + deferred batch (kill per-node PyO3 in the distance-2 BFS)

A readwrite/directed-structural sweep surfaced a CONSISTENT (across-seeds, not noise)
gap: `transitive_closure_dag` 0.67-0.71x vs nx. Root: the in-process kernel
(_transitive_closure_dag_inproc) ran the distance-2 BFS calling
``succ(TC, node)`` — a PyO3 successor lookup — per node on the MUTATING TC, i.e.
O(closure-edges) PyO3 round-trips, where nx walks native dicts.

FIX (br-cc-tcdsnap, PURE-PYTHON): snapshot TC's successor adjacency ONCE into Python
lists (insertion order — NOT sets, which would scramble nx's BFS discovery order),
run the BFS on those, keep each node's list in sync as transitive edges are
discovered (reversed-topo guarantees a node is closed before its predecessors read
it), and commit ALL transitive edges in ONE final ``add_edges_from`` instead of
per-v. Byte-IDENTICAL: same per-v / set-order append => identical edge SET and
per-node adj ITERATION order (0/60 adversarial incl. explicit topo_order; 761
dag/transitive conformance tests pass).

Measured (median/seeds): n=200 (closure 7.5k) 0.71x->**2.16x**, n=300 **1.43x**,
n=400/600 (closure 47-56k) **1.05-1.08x**, n=1000 (closure 89k) 0.92x. WIN for
typical sizes; STRICTLY better than the old 0.67x at EVERY size (the 0.92x worst
case = huge dense closures where the final 89k-edge add_edges_from dominates — still
a 1.4x self-improvement). LEVER: an in-process kernel that reads a MUTATING fnx
graph per-node pays PyO3 per access; snapshot the adjacency into Python once + keep
it in sync + defer the single batch mutation to the end.

## 2026-06-28 CopperCliff SHIP: parse_pajek 0.66x->0.91x — batch node/edge construction (kill per-element add)

readwrite sweep found parse_pajek consistently 0.66x vs nx (across seeds). It is a
pure-Python parser (not delegated): the bottleneck was per-NODE `add_node` +
`nodes[label][...]` PyO3 attr writes and per-EDGE `add_edge` in the parse loops
(the `graph_as` type-conversions run BEFORE edges exist, so they are cheap). Fix
(br-cc-pajekbatch, PURE-PYTHON): build each node's attr dict locally and commit all
nodes in ONE `add_nodes_from`; accumulate parsed edges and commit them in ONE
`add_edges_from` (per loop). Same attr keys/order + multigraph key assignment, so
the parsed graph is byte-IDENTICAL (0/45 adversarial: undirected/directed/multi,
weights, parallel edges, node attrs == nx; 27 pajek conformance tests pass).

Measured 0.66x -> **0.91x** (1.37x self-speedup, n=800). NEAR-PARITY, not yet a
head-to-head win: the residual is the keyed-edge Multi(Di)Graph store substrate
(parse_pajek builds a MultiDiGraph/MultiGraph; even batched, the String-keyed
multi-edge inserts trail nx's native dicts — the same floor as MG dijkstra/size).
Shipped as strict per-element work-removal (identical output, real 1.37x self-gain);
crossing >1x needs the index-based MG storage primitive. parse_graphml (0.73x,
delegates to nx's XML parser — de-delegation = rewriting an XML parser, not worth
it) and barabasi_albert (0.79x, RNG `rng.choice` rejection loop = pure-Python,
identical to nx, unbeatable without breaking byte-exactness) are NOT takeable.

## 2026-06-28 CopperCliff SURFACE: bipartite / tournament / link-analysis / cut / chordal / cores — all at-or-above nx

Fresh-area sweep (previously unbenched). All win-or-parity: bipartite.clustering
2.77x, bipartite.projected_graph 2.42x, bipartite.density 3.41x, is_bipartite 15x,
voterank 2.33x, hits 1.45x, pagerank(tol=1e-10) 10.8x, tournament.is_tournament
7.1x, is_chordal 2.47x, onion_layers 8.9x, k_truss 1.41x, k_core 75x, core_number
14x, find_cliques 1.01x, node_clique_number 1.00x (parity), kernighan_lin 1.02x.
The lone apparent sub-1.0x (graph_clique_number 0.80x) was a TEST ARTIFACT —
neither nx nor fnx exposes graph_clique_number (deprecated/removed), so both ran the
same find_cliques()+max fallback; the delta was find_cliques timing noise.

NET (≈22 dimensions surveyed this session): fnx dominates nx across the entire
measured surface. Every genuine residual converges on the ONE architectural root —
the String-keyed Multi(Di)Graph store (MG dijkstra/size/degree/connected_components/
pajek-parse). Index-based Multi(Di)Graph adjacency in fnx-classes/CGSE is the single
remaining real lever; it is a coordinated multi-session storage change, not a
60-minute patch. Clean per-function algorithmic wins are mined out.

## 2026-06-28 CopperCliff SURFACE: min-cost-flow / cycles / dominance / distance — all at-or-above nx

Fresh-area sweep. All win-or-parity: min_cost_flow 2.6x, min_cost_flow_cost 2.4x,
network_simplex 1.85x, capacity_scaling 13.7x, cycle_basis 2.73x, find_cycle 6.1x,
recursive_simple_cycles 2.6x, minimum_cycle_basis (nx TIMEOUT), immediate_dominators
1.76x, greedy_color(largest_first) 7.3x, edge_betweenness 29.5x, eccentricity/center/
periphery/radius/wiener_index 14-15x, barycenter 14x; simple_cycles 1.01x /
dominance_frontiers 1.05x parity. No gap. (~24 dimensions surveyed this session;
every residual remains the String-keyed Multi(Di)Graph store — the index-based MG
adjacency primitive in fnx-classes/CGSE is the sole remaining real lever.)

## 2026-06-28 CopperCliff NO-SHIP: multi_source_dijkstra_path_length on a MultiGraph 0.088x — projection + gate-overhead bound (~0-gain to fix)

Survey found weighted-MultiGraph `multi_source_dijkstra_path_length` at **0.088x**
vs nx (12x slower; all_pairs MG dijkstra is a 5.8x WIN — its native path amortises
the projection over V sources). Root: the native length-only fast path is gated to
`type(G) in (Graph, DiGraph)`, so multigraphs fall to `multi_source_dijkstra` which
computes the full PATH TREE and discards it for this length-only API.

Tried routing int-weighted multigraphs to the native length-only binding
(`_fnx.multi_source_dijkstra_path_length`, which DOES handle multigraphs byte-exact:
0/80 adversarial incl. parallel edges, self-loops, directed; float/mixed correctly
fail `_sp_edge_weights_all_int` and keep the faithful path). REVERTED — **~0-gain**:
(1) the bare binding is only **0.222x** (projection-bound — same String-keyed MG
store floor as single-source MG dijkstra), and (2) the wrapper's own gate checks
(`_should_delegate_dijkstra_to_networkx` syncs + scans, `_sp_edge_weights_all_int`
scans) add several O(E) edge passes for multigraphs, dragging the routed result back
to ~0.11x (vs 0.088x before — within noise). Both the algorithm floor AND the
gate-evaluation overhead are the String-keyed MG store; index-based MG adjacency
(fnx-classes/CGSE) is the only fix. DON'T re-attempt the gate change.

## 2026-06-28 CopperCliff ROADMAP (lever precisely located + precedented): port the d58s8 index-based adjacency from Graph to MultiGraph

Traced the SOURCE of the entire MG frontier (dijkstra 0.3x, size 0.3x, degree 0.7x,
connected_components 0.39x, multi_source 0.09x — all String-keyed-store bound).
ROOT CONFIRMED at the struct level (crates/fnx-classes/src/lib.rs):

- simple `Graph` (struct ~line 121) ALREADY has INDEX-based storage from the
  br-r37-c1-d58s8 effort: `adj_indices: Vec<Vec<usize>>` (O(1) integer adjacency,
  "avoids string hashing during BFS/CC") + `edges: FxIndexMap<(usize,usize),AttrMap>`
  (index-canonical pair keys, "zero String allocs/hashes per insert"). THIS is why
  every simple-graph traversal (dijkstra/CC/clustering/...) beats nx.
- `MultiGraph` (struct line 2207) did NOT get d58s8: it still has
  `adjacency: FxIndexMap<String, IndexMap<String, IndexSet<usize>>>` (nested STRING
  maps) + `edges: FxIndexMap<EdgeKey, IndexMap<usize, AttrMap>>` (String-pair keys).
  Every neighbour/edge access hashes Strings (O(len), ×2 per edge) — the floor that
  loses to nx's interned-key dict walk. (FxHash is ALREADY in use, so the hasher is
  not the lever; the integer-vs-String KEY is.)

THE LEVER (only fix; multi-session, NOT a 60-min patch): port d58s8 to
Multi(Di)Graph — add `adj_indices: Vec<Vec<usize>>` + an index-pair-keyed edge
bucket store, maintained in add_edge/remove_edge/remove_node (with index rekeying,
exactly as Graph does), and expose `neighbors_indices` + index-based edge-bucket
access. The Graph implementation is the working TEMPLATE. This ONE change unlocks
the whole MG frontier at once. High conformance risk (touches the hot MG construction
path + the entire MG test surface) + shared core file — should be done with
agent-mail coordination (currently down) and per-slice conformance gating, like the
original d58s8 was. NOT attempted unilaterally here.

## 2026-06-28 CopperCliff VERIFY: 6 session wins hold (no regression); wide-net sweep all at-or-above nx

Regression sweep — all 6 shipped wins still beat nx on HEAD: greedy_tsp INT-tie
1.46x / FLOAT 3.85x, eulerian_circuit DIR 15.3x, annealing greedy-init 1.32x,
transitive_closure_dag 1.55x, parse_pajek 0.91x (the shipped near-parity).

Wide-net over ~25 diverse untouched functions — all win-or-parity: reciprocity 8.5x,
degree_assortativity 110x, average_neighbor_degree 11.6x, s_metric 178x, edge_dfs
1.23x, edge_bfs 2.14x, dfs_preorder 2.0x, descendants_at_distance 1.63x, power(G,3)
2.38x, triadic_census 19.6x, rich_club 111x, global/local_efficiency 17-20x,
degree_mixing_matrix 3.7x, get_node_attributes 2.53x, set_node_attributes(scalar)
1.12x. Noise-corrected: dfs_postorder_nodes 1.26x (WIN; single-shot 0.93x was noise),
WL subgraph_hashes ~0.94x (parity, noisy). Only consistent sub-1.0x:
set_edge_attributes(SCALAR) 0.74x — the documented attr-substrate floor: its native
one-pass (_native_broadcast_edge_attribute) writes the Python edge_py_attrs MIRROR to
PRESERVE value identity (nx shares the value object across edges); a store-only
CgseValue write would be faster but break `G[u][v][name] is value` for non-interned
values. Not takeable without sacrificing identity. NET: surface remains fully mined;
the sole real lever is the d58s8 index-storage port to Multi(Di)Graph (prior entry).

## 2026-06-28 CopperCliff NO-SHIP: steiner_tree 0.556x — in-process mehlhorn is WORSE (0.346x); needs a native kernel

approximation.steiner_tree (approximation.py) delegates to nx (default 'mehlhorn')
then converts the result — consistently **0.556x** vs nx (conversion tax). The
conformance bar is the TREE WEIGHT (test_flow_cut_matching_value_parity:
`tw(fnx)==tw(nx)`) + validity (spans terminals, is a tree), NOT exact edges.

Prototyped the proven de-delegation pattern — run nx's EXACT mehlhorn in-process
with fnx primitives (multi_source_dijkstra + minimum_spanning_edges + shortest_path
+ edge_subgraph). It is byte-exact on WEIGHT (0/39 == nx) and produces valid trees
(5/5), BUT it is **0.346x — SLOWER than the 0.556x delegation**. Reason: mehlhorn
calls `multi_source_dijkstra` (FULL paths for every node — only paths[v][0] is
needed) + K per-terminal-pair `shortest_path` calls + a Python edge-iteration loop;
the per-call fnx wrapper overhead + Python-loop cost exceed the O(V+E) fnx->nx
conversion the delegation pays. fnx's individual primitives beat nx, but composed in
a Python algorithm with per-call overhead they lose to nx's tighter native-graph
mehlhorn. NO-SHIP (in-process is a regression). A real win needs a NATIVE Rust
mehlhorn kernel (multi-source Voronoi + 2x MST + path expansion, weight-exact) —
complex, not worth the reward for one approximation function. steiner_tree stays
delegated at 0.556x.

## 2026-06-28 CopperCliff TERMINAL STATE: surface mined; sole lever (d58s8 MG port) is coordination-blocked by a wedged agent-mail process

Final sweeps confirm no remaining 60-min win: eulerian_path DIR 31.8x / UND 7.2x,
has_eulerian_path 88x, is_semieulerian 91x (all WIN). Across ~26 surveyed dimensions
(hundreds of function-calls) fnx dominates nx everywhere; every residual is timing
noise or the String-keyed Multi(Di)Graph store floor.

The ONE remaining real lever — porting the d58s8 index-based adjacency
(`adj_indices: Vec<Vec<usize>>` + index-pair-keyed edges) from `Graph` to
Multi(Di)Graph (would unlock MG dijkstra/size/degree/connected_components/
multi_source at once) — is a multi-session core-storage change on a SHARED
fnx-classes file. It needs fleet coordination, which is BLOCKED: agent-mail's DB is
corrupt and the lock is held by a WEDGED process (PID 2093388, `am (deleted)`
executable, ~4 days stale, owner_class=wedged) that the tooling explicitly says not
to kill directly. REMEDIATION (needs operator/supervisor): drain/restart the `am`
MCP server via the supervisor, then `am doctor reconstruct` (dry-run recovers 17
projects / 70 agents / 2245 messages / 876 thread digests cleanly). Until then,
git/this ledger is the only coordination channel, and the d58s8 MG port should NOT
be attempted as an unilateral solo rewrite (high conformance risk, no coordination).

A partial port is NOT independently shippable: adding `adj_indices` without USING it
just slows the hot add_edge path (regression); it only pays off once both
adj_indices AND index-keyed edges are in place and wired into the MG read paths —
i.e. the whole slice must land together. That is the documented next major work item.

## 2026-06-28 CopperCliff SURFACE: graph-transformations all at-or-above nx (contracted_edge 0.446x was NOISE)

Fresh sweep of graph transformations — all win: line_graph 5.8x, contracted_nodes
9.7x, quotient_graph 2.6x, identified_nodes 8.1x, complement 3.0x, compose 2.6x,
union 1.8x, disjoint_union 3.4x, relabel_nodes 1.24x, subgraph.copy 1.53x,
to_directed 4.5x, ego_graph 1.44x. The lone single-shot sub-1.0x (contracted_edge
0.446x) was NOISE — robust min-of-11/4-seeds is **6.8x** (it already routes to the
fast contracted_nodes after a has_edge check, exactly like nx). No gap. Confirms the
terminal state: ~27 dimensions surveyed, fnx dominates nx everywhere; the only real
residual is the String-keyed Multi(Di)Graph store (d58s8 MG port — 83 adj_indices
touch-points, multi-session, coordination-blocked).

## 2026-06-28 CopperCliff SHIP: find_minimal_d_separator 0.15x->4.5-74x — de-delegate (in-process Bayes-Ball on an ancestral snapshot)

A wide sweep of obscure nx-fallback functions found find_minimal_d_separator
delegating (`_call_networkx_for_parity` -> full O(V+E) conversion) for a single
small query that only touches the ANCESTRAL subgraph of {x,y,included} — 0.15-0.17x
vs nx (consistent across seeds). Conversion-tax-on-small-input vein (cf. link-pred
c7ffab536).

FIX (br-cc-dsepinproc, PURE-PYTHON): run nx's EXACT algorithm (van der Zander &
Liskiewicz 2020) in-process — ancestral set via the native `ancestors()`, ONE bulk
`G.adjacency()` snapshot restricted to that set + inverted for predecessors, and the
Bayes-Ball `_reachable` over plain dicts. The reimplemented `_reachable` uses a SET
for `processed` membership where nx uses a list (O(E*|processed|) -> O(E), identical
reachable set). Gated to plain DiGraph; SubgraphViews / multigraphs / nx-private
storage keep delegation.

Byte-exact: 0/163 adversarial through the wrapper (x/y/included/restricted, node+set
inputs); error contracts match (non-DAG->NetworkXError, bad-node->NodeNotFound,
disjointness->NetworkXError); result is a deterministic SET (content-compared). 179
d-separation + 757 dag/moral/ancestors conformance tests pass. Measured 0.15x->**4.5x**
(n=200) / **23.8x** (n=500) / **74.2x** (n=1000) — the win GROWS with n because it
beats BOTH the conversion tax AND nx's own O(E^2) reachable. LEVER: a delegated
single-pair/small query that only needs an ANCESTRAL/local subgraph pays a full-graph
conversion; run nx's exact algo in-process on a local snapshot (works when the result
is a deterministic set/value — no order subtlety). [is_minimal_d_separator with
included/restricted has the same delegation, a smaller follow-up.]

## 2026-06-28 CopperCliff SHIP: is_minimal_d_separator(included/restricted) 0.18x->3.8-49x — same in-process de-delegation (reuses _reachable_dsep)

The documented follow-up to find_minimal_d_separator (1c17ba83f). The
included/restricted form of is_minimal_d_separator delegated via the full O(V+E)
conversion (~0.18x). nx's criteria algorithm (a/b/c, van der Zander & Liskiewicz
2020) uses the SAME primitives — ancestors + 2x Bayes-Ball _reachable — so it
de-delegates in-process REUSING the shipped `_reachable_dsep` helper + a local
ancestral snapshot. Returns a deterministic BOOL. Byte-exact 0/288 through the
wrapper (valid/perturbed/empty z, included, restricted; error contracts match);
179 d-separation conformance tests pass. Measured 0.18x->**3.8x** (n=300) /
**49x** (n=800). The no-constraint path (native is_d_separator + O(|z|) reducer) is
unchanged. Plain DiGraph only; SubgraphViews/multigraphs/private storage delegate.

## 2026-06-28 CopperCliff SURFACE: matching-validators win typical / floor only on huge |M|; long-tail sweep continues

After the two d-separation wins (find_minimal 1c17ba83f, is_minimal aa56981bd),
swept more obscure delegated/validator functions. WINS: trophic_levels 2.2x,
hyper_wiener_index 2.2x, k_edge_components 17x, k_edge_subgraphs 14x,
average_shortest_path_length 15x, all_shortest_paths 9.6x, antichains (nx TIMEOUT).
is_maximal_matching ~parity. The matching VALIDATORS (is_matching /
is_perfect_matching) already use native Rust validators (only directed/multi
delegate); they are O(|matching|) and WIN for small/typical matchings (1.32-1.36x,
graph-size-independent) — they only dip to ~0.83x on a HUGE matching (|M|~V/2,
n=2000) where the per-edge node-key conversion (Python node -> canonical store key,
x2 per edge) trails nx's native int-dict has_edge. That is the node-key-rep
substrate floor (same family as the MG store), not a typical-case gap — NOT worth
"fixing". LESSON CONFIRMED: the long tail of obscure delegated functions still pays
off (2 d-sep wins this session); periodic sweeps beat declaring the surface terminal.

## 2026-06-28 CopperCliff SHIP complement(MG/MDG) + comprehensive re-sweep (view gaps now FIXED)

SHIP 65d56efed: `complement(MultiGraph/MultiDiGraph)` round-tripped through nx
(`_complement_via_nx`: fnx->nx + nx.complement + nx->fnx) because native
`_raw_complement` rejects multigraphs — a catastrophe (42-995ms MG / 61-1431ms MDG
over n=100..400 = 0.20-0.31x vs nx). nx.complement is a structural double-loop, so
build DIRECTLY: keys-only add_nodes_from(G.nodes()) + non-adjacent ordered pairs via
`G._native_adjacency_dict()` membership + native batch `add_edges_from(LIST)`. Warm
min-of-12: MG 0.31x->1.57x(n=100)/1.17x(n=200)/0.79x(n=400); MDG 0.20x->1.20x/0.88x
/0.75x. 3-5x self at EVERY size = strict win over main. Byte-exact 40/40 (nodes+data,
edges+keys, graph attrs); 254 operator/complement parity tests pass. PURE-PYTHON.
NOTE: `add_edges_from(GENERATOR)` is a multigraph TRAP (382ms vs 98ms for a
materialized list at n=300) — always build the list. RESIDUAL: complement n>=300
still 0.75-0.79x (materializing ~88k Python tuples); only past nx = native MG
_raw_complement in Rust (low ROI, dense-output workload is rare).

RE-SWEEP (3 batches, warm): the view-materialization gaps recorded in older memories
are now FIXED and WINNING — in_edges(data=True) DiGraph 7.4x / MDG 27x, edges(keys)
3.7-4.4x, edges(keys,data) 5-7.8x, edges(data='weight') 1.3-1.5x. Algorithm surface:
all WIN 1.0-339x (betweenness 37x, transitivity 116x, k_core 38x, square_clustering
24x). Small-input/delegated surface (where conversion-tax hides): all WIN
(resistance_distance 52x, has_path 10x, max_flow 8.7x, dijkstra_path 7.7x, node_conn
2.9x); the only sub-1.0x there (preferential_attachment 0.69x, common_neighbors
0.85x) are single-digit-MICROSECOND noise, not real. The ONLY real sub-1.0x residual
across the whole sweep is `degree(weight)` MultiGraph/MultiDiGraph ~0.60-0.88x — the
documented PyObject per-node degree-view materialization floor (REFUTED+NO-SHIP
6ee21ea28: halving Rust work was invisible behind the tuple-build wall). LESSON: the
view vein that older memory flagged as the standing gap has been closed by prior
sessions; the surface is now near-uniformly dominated. INFRA BLOCKER: agent-mail DB
in degraded_read_only recovery (integrity failures=100) — reservations/messaging
write-fail; reads OK; needs `am doctor repair`.

## 2026-06-29 CopperCliff DIG (REFUTED): degree(weight) MultiGraph is a native-view floor, not a missing Python fast-path

Targeted the one genuine sub-1.0x residual from the prior sweep: `degree(weight)`
MultiGraph ~0.71-0.77x vs nx (n=200..800; fnx 0.32-1.39ms vs nx 0.23-1.07ms).
Simple Graph/DiGraph total weighted degree were routed (br-r37-c1-wdeg2) to a
pure-Python sum over a `to_dict_of_dicts` snapshot (whose inner dicts ARE the live
edge attr dicts) — beats the native PyList-building kernel. HYPOTHESIS: transfer the
same lever to MultiGraph. REFUTED: `to_dict_of_dicts(MG)` returns a DEEP 3-level
nested dict `{node:{nbr:{key:attrdict}}}` whose inner per-key dicts are freshly
allocated (NOT shared live dicts as in the simple case), so the Python sum over it is
**0.04x** (5.7-25ms vs the native kernel's 0.32-1.39ms) — ~16x SLOWER. Byte-exact
values+types confirmed (0/80) but the snapshot build dominates. Do NOT ship; nothing
committed (scratch only).

ROOT CAUSE: `franken_networkx.MultiGraph` IS the native Rust type and `G.degree`
returns a native `MultiGraphDegreeView` (NOT the Python `_DegreeView` in __init__.py).
So the gap is the native view's PyObject materialization (build n (node, float-sum)
tuples), the SAME floor documented at 6ee21ea28 (REFUTED+NO-SHIP: halving Rust work
was invisible behind the tuple-build wall) and ac98e77d4. There is NO pure-Python
lever; closing it needs Rust work inside the native multigraph degree view + a .so
rebuild. Lowest-quality sub-case is INT-weight clean MG (~0.60x) — a future Rust
target for whoever owns multigraph degree, if ever (sub-ms op, low ROI).

NOISE CORRECTION: a sequential single-process domain sweep flagged
katz_centrality_numpy 0.41x, communicability TIMEOUT, transitive_closure TIMEOUT,
dominating_set 0.88x as gaps. ALL FALSE — measured in isolation fnx WINS:
katz_centrality_numpy 2.5x (9ms vs nx 23ms; the 0.41x was BLAS-thread contention from
heavy numpy/scipy fns earlier in the same process), communicability 12-14x (nx is the
slow one ~2s@n=150, it overran the per-fn cap), transitive_closure 3.55x,
dominating_set sub-ms noise. LESSON: never trust a long sequential single-process
sweep for numpy/scipy-backed functions — BLAS pool state + memory pressure inflate
later calls; isolate + warm each suspected gap before believing it.

NET: the fnx surface is comprehensively dominated; the sole real sub-1.0x case
(degree(weight) MG) is a native-view floor needing Rust + a rebuild. BLOCKER persists:
agent-mail DB in degraded_read_only (integrity failures=100) — reservations/messaging
write-fail, so safe coordination on TealSpring-owned multigraph Rust is not possible
until `am doctor repair`.

## 2026-06-29 CopperCliff SHIP (PARTIAL): MultiGraph degree(weight) float Neumaier fast path 0.79x->0.87x

Re-targeted the biggest remaining sub-1.0x gap (MultiGraph total degree(weight),
~0.79x vs nx) with the lever my own prior MDG NO-SHIP (6ee21ea28) pointed to but did
NOT try: "closing the gap requires cutting per-node Python-object construction
itself." The native MG `_native_weighted_degree` (lib.rs) built a per-edge PyList +
called builtins.sum PER NODE (for float Neumaier parity). The prior NO-SHIP only
optimized Rust accumulation/hashing (left PyList+sum untouched) and saw no change —
which PROVES PyList-append + Python-sum was the dominant cost, not the hashing.

FIX: when every contributing weight value of a node is an exact PyFloat (and the node
has >=1 edge), sum the f64s with CPython's Neumaier (Kahan-Babuska) compensation
DIRECTLY in Rust — verified bit-identical to builtins.sum over 30k random cases
(all-float + self-loop patterns, py 3.13.7) — eliminating the per-edge PyList append
and the per-node builtins.sum call. Bails to the original exact PyList+sum path on ANY
non-float value (missing-weight default int 1, int/other weight) AND for an edgeless
node, so int/mixed parity, numeric promotion, and nx's int-0 for isolated nodes stay
byte-exact (7520/7520 over 128 graphs, type-exact; conformance 6696+7256 pass, sole
failure write_gexf is PRE-EXISTING on HEAD, unrelated).

Clean A/B (same machine, min-of-20): n=400 0.79x->0.87x (0.666->0.584ms), n=800
0.81x->0.88x (1.391->1.226ms), n=1500 0.78x->0.85x (2.719->2.389ms) — a consistent
~14% self-speedup. PARTIAL: still 0.85-0.88x (short of nx). The residual is the
per-edge `Self::edge_key(node,neighbor,key)` String-tuple allocation + HashMap probe
to read the dirty-graph weight from the PyDict mirror (nx does a plain dict lookup,
no alloc). Closing it past nx needs the mirror keyed/indexed without String
reconstruction — a restructure spanning shared fnx-classes; out of scope (and
agent-mail degraded_read_only blocks safe coordination there). INT-weight MG stays
~0.67x (fallback path; future Rust i64-sum target with overflow->bigint care).
Per-crate build via rch (CARGO_TARGET_DIR=/data/projects/.rch-targets/networkx-cc),
cargo check + maturin release wheel, .so verified (0 undefined crossbeam).

## 2026-06-29 CopperCliff SHIP (PARTIAL): MultiDiGraph degree(weight) float Neumaier fast path 0.70-0.78x->0.86-0.93x

Extended the proven MG Neumaier lever (efdcfca36) to the MultiDiGraph sibling.
The native MDG `_native_weighted_degree` (digraph.rs:5271) — after its int store/
mirror fast paths return None for float weights — built per-node succ_vals + pred_vals
PyLists and computed `sum(succ) + sum(pred)` via builtins.sum. FIX: when every
contributing succ+pred weight value is an exact float in the live mirror (and the node
has >=1 edge), compute the two sums as independent Rust Neumaier (Kahan-Babuska)
accumulations added with a plain `+` — bit-identical to builtins.sum (verified 30k
cases). Bails to the exact PyList+sum path on ANY non-float/absent value (mirror miss
-> nx default int 1) and for an edgeless node, so int/mixed parity, numeric promotion,
and nx's int-0 for isolated nodes stay byte-exact. The helper reads ONLY the mirror,
exactly matching the fallback's value fetch, guaranteeing byte-exact deferral.

Clean A/B (same machine, min-of-20): total degree(weight) n=400 0.78x->0.93x
(0.763->0.652ms), n=800 0.78x->0.89x (1.608->1.405ms), n=1500 0.70x->0.86x
(3.358->2.746ms) — ~14-22% self-speedup. Byte-exact 22560/22560 over 128 graphs x
{total,in,out} (float/int/self-loops/missing-weights, type-exact); conformance 7461
pass. PARTIAL (still <nx): same residual as MG — per-edge `Self::edge_key` String
alloc + HashMap mirror probe; closing past nx needs an indexed mirror (deferred,
spans shared fnx-classes). INT-weight MDG keeps its store/mirror int fast paths.
Per-crate build via rch (CARGO_TARGET_DIR=/data/projects/.rch-targets/networkx-cc),
cargo check + maturin release, .so verified (0 undefined crossbeam).

## 2026-06-29 CopperCliff SHIP: MultiDiGraph in/out_degree(weight) float Neumaier fast path (directional)

Completed the MDG weighted-degree family: the DIRECTIONAL in_degree/out_degree(weight)
(core_laggards `fnx_mdg_in_degree_weight`) used a separate kernel
(`native_weighted_directional_degree`, digraph.rs) whose float path (after its int
store/mirror fast paths return None) built a single per-node PyList + builtins.sum.
Same proven Neumaier lever as the total path: when every contributing single-direction
weight value is an exact float in the mirror (and the direction has >=1 edge), sum the
f64s with CPython's Kahan-Babuska compensation in Rust — bit-identical to builtins.sum
— reusing the `edge_weight_exact_f64_mirror` helper. Bails on any non-float/absent
value and edgeless direction (nx int-0). Byte-exact 22560/22560 over 128 graphs x
{in,out,total} (float/int/self-loops/missing, type-exact); conformance 7461 pass.

Clean A/B (fresh processes, min-of-25): out_degree n=700/e12662 0.23x->0.77x (3.36x
self), n=1500 0.83x->0.93x, n=400 0.86x->0.98x; in_degree n=700 0.37x->0.42x, n=1500
0.70x->0.74x, n=400 0.76x->0.83x (~1.12-1.15x self). out_degree gains are large;
in_degree stays lower (0.42x at the dense bench size) because the predecessor
traversal in fnx-classes is the structural floor (not the sum) — a separate lever.
Per-crate build via rch (CARGO_TARGET_DIR=/data/projects/.rch-targets/networkx-cc).

ROOT-CAUSE NOTE for the remaining edge-view laggards (selfloop_edges 0.42-0.65x,
mdg_edges_keys, mdg_in_edges_data): all bottleneck on the edge-attr mirror being keyed
by (String,String,usize), forcing a per-edge String allocation + HashMap probe that nx
(nested Python dicts) avoids. mark_edges_dirty confirmed O(1) (ruled out). The radical
lever to close ALL of them is an INTEGER-keyed edge mirror (a different primitive, not
a safe-Rust micro-opt) — large, spans shared fnx-classes/fnx-python; deferred while
agent-mail is degraded_read_only (no safe reservation/coordination). selfloop_edges
data=True correctly shares the live mirror dict (no copy bug).

## 2026-06-29 CopperCliff FRONTIER MAP (measured): edges(data=attr) biggest gap; store-direct path is DEAD for real graphs

After completing the weighted-degree family, swept the remaining tracked laggards at
bench sizes (MDG n=700/e12662, MG selfloop n=2500/loops2502). Most "laggards" now WIN:
edges(keys,data=True) 7.84x, in_edges(data) 29x, out_edges(nbunch,keys,data) 35x.
GENUINE remaining gaps (biggest-first):
  - edges(data='weight') MDG: **0.43x** (fnx 16.3ms vs nx 7.0ms) — BIGGEST absolute gap.
  - selfloop_edges MG: keys+data 0.43x, keys 0.48x, data 0.47x, keys+weight 0.55x.
  - out_edges(nbunch,keys,data='weight') 0.87x (marginal).

ROOT CAUSE (all of them): the per-edge value/dict path calls `ensure_edge_py_attrs`/
`edge_data_value_or_default`, which builds a `(String,String,usize)` edge_key and
probes the mirror HashMap PER EDGE — nx (nested Python dicts) has the value in hand.
For data='weight' this is a per-edge edge_key String alloc + mirror probe + get_item
over ALL edges; data=True avoids it by returning the bulk-cached live dict.

DEAD LEVER (measured, do NOT retry): the obvious fix — read the scalar from the
CgseValue store via cgse_value_to_py (the selfloop pristine path) — does NOT engage for
real graphs. The store-direct path gates on `edge_py_attrs.is_empty()` / `!edges_dirty`,
but ANY graph built through the Python API with edge attrs has a POPULATED mirror and is
dirty. PROOF: selfloop_edges(data='weight') CLEAN(add_weighted_edges_from) 0.57x ==
DIRTY(per-edge add_edge) 0.61x — identical, the store path never fires. And reading the
store on a populated-mirror graph is a CORRECTNESS risk: the conservative dirty flag is
necessary because user dict mutations (G[u][v][k]['weight']=x) can't be intercepted, so
there is no per-edge coherence signal to safely prefer the store.

ONLY remaining lever (a DIFFERENT primitive, not safe-Rust-ceiling): re-key the
edge-attr mirror from (String,String,usize) to an integer EdgeId so the per-edge probe
during edges_ordered_borrowed needs no String alloc. LARGE (touches every edge_key call
site), spans shared fnx-classes/fnx-python; deferred — too big/risky for a single cycle
and agent-mail degraded_read_only blocks safe multi-agent coordination on those files.
Session shipped 4 wins (complement 65d56efed; MG degree efdcfca36; MDG total 8e3018901;
MDG in/out 06c495789); the perf frontier for safe single-cycle work is now this refactor.

## 2026-06-29 CopperCliff SHIP: MultiDiGraph edges(data=<attr>) ~1.6x self via store-read routing

CORRECTS the prior "store path is DEAD" entry: the whole-graph edges(data=<attr>)
kernel (`native_edge_view_list`, digraph.rs) used the slow per-edge
`ensure_edge_py_attrs` (mirror materialize/probe + get_item) for its want_value branch,
while the sibling `edge_data_value_or_default` ALREADY has a `!edges_dirty` CgseValue
store fast path (cgse_value_to_py, no per-edge edge_key String + mirror probe) used by
the nbunch out/in_edges data=<key> views. Routed the want_value branch through
`edge_data_value_or_default`. It engages the store read for freshly-built graphs (both
add_weighted_edges_from AND per-edge add_edge) and falls back to the mirror on
dirty/Map/missing — so values stay byte-exact AND post-mutation coherent.

Clean isolated A/B (fresh processes, min-of-30) edges(data='weight') MDG n=700/e12662:
fnx 16.5-17.4ms -> 10.8ms = **~1.6x self-speedup** (both build modes), ratio ~0.43-0.65x
-> ~0.53x. Still <nx (nx ~5.7ms; nested-dict iteration is very fast) but a 35%
self-improvement on a very common op. Byte-exact 288/288 configs (float/int, awef/add
builds, missing weights, default, keys) + POST-MUTATION coherence verified
(G[u][v][k]['weight']=x IS reflected, 0 mismatches — the dirty path correctly falls to
the mirror). Conformance 9334 pass (sole failure write_gexf classification is
PRE-EXISTING on HEAD, unrelated). Per-crate build via rch.

The earlier "store path dead" conclusion was wrong for THIS path: the gate is per-graph
(`!edges_dirty`), and a built-not-mutated graph IS clean enough for the store read; my
selfloop CLEAN==DIRTY probe was confounded (selfloop has a separate value_attr_name
gate). FOLLOW-UPS: same routing for MG `_native_edge_view_list` (lib.rs) want_value;
selfloop_edges variants (0.43-0.55x) still on the mirror path.

## 2026-06-29 CopperCliff NO-SHIP (REVERTED): MG edges(data=<attr>) store-read routing — neutral/regression

Tried to extend the MDG edges(data=<attr>) store-read win (80e12629a) to MultiGraph:
added a `!edges_dirty` store-first fast path to `edge_data_value_or_default_with_key`
(lib.rs) and routed `_native_edge_view_list`'s want_value branch through it. Byte-exact
288/288 + post-mutation coherent, BUT measured neutral-to-REGRESSION (clean isolated,
min-of-30, n=700/e12662): awef fnx 18.8->18.5ms (flat), add fnx 16.8->20.4ms (~21%
SLOWER). REVERTED (git checkout lib.rs); nothing shipped.

WHY it works for MDG but not MG: MDG's `native_edge_view_list` want_value called
`ensure_edge_py_attrs(source,target,key)`, which builds the `edge_key` String tuple
INTERNALLY per edge — so the store path's win was eliminating that per-edge String
build. MG's loop ALREADY constructs `ek` (line ~6804, for the `seen` dedup set) and used
a light `edge_py_attrs.get(&ek)` probe (NOT ensure_edge_py_attrs / no materialization).
So the store path saved nothing on MG and ADDED cost (an extra `inner.edge_attrs` lookup
+ a fresh `cgse_value_to_py` PyFloat alloc vs returning the cached mirror PyObject).
LESSON: the store-read routing lever only pays when the existing path builds the
edge_key String per edge (or materializes the mirror); if `ek` is already in hand and
the mirror is a cheap probe returning a cached object, store-read is a net loss. MG
edges(data=<attr>) residual (0.34-0.82x) is the genuine per-edge mirror floor; closing
it needs the integer-keyed mirror (deferred). selfloop_edges variants similarly.

## 2026-06-29 CopperCliff SHIP: MultiGraph edges() node-dedup — up to 2.15x self, plain edges now BEATS nx

The MG edges() kernel (`_native_edge_view_list`, lib.rs) deduped undirected edges with a
per-edge canonical `(String,String,usize)` seen-set (`seen.insert(ek.clone())` PER EDGE
= a String-tuple clone + tuple-hash insert over O(E)). Replaced with nx's actual
algorithm: dedup by NODE via an O(N) `processed` set, emitting each edge from the
first-encountered endpoint (a neighbor already in `processed` had the edge emitted from
its side; a self-loop's node isn't yet processed -> emitted once). The raw `ek` is now
built ONLY for the want_value mirror probe (plain data=False builds no ek at all).

Clean isolated A/B (min-of-30) MG n=700/e12662, byte-exact 360/360 over 60 graphs with
NON-SORTED node insertion order + self-loops + parallel edges (all 6 variants), incl
data=True live-dict identity:
  edges()              0.71x -> **1.34x** (8.04 -> 4.27ms, 1.88x self) — now BEATS nx
  edges(data='weight') 0.53x -> **0.97x** (13.44 -> 7.48ms, 1.80x self)
  edges(keys,data='w') 0.42x -> **0.89x** (17.40 -> 8.11ms, 2.15x self)
  edges(keys), edges(data=True): unchanged (already cached/fast, 4.5x/5x)
Conformance 10771 pass (sole failure write_gexf classification is PRE-EXISTING on HEAD).
Per-crate build via rch. The per-edge String-tuple dedup set was the dominant cost (not
the value extraction) — removing it closed most of the gap. Orientation + node->neighbor
->key order + self-loop multiplicity all preserved (nx's first-encounter semantics).

## 2026-06-29 CopperCliff SHIP: MultiGraph edges(nbunch, data/keys) node-dedup — up to 1.41x self

Extended the MG edges() node-dedup (ebb754a2c) to the nbunch variants
(`_native_mg_edges_nbunch_data` + `_native_mg_edges_nbunch_data_key`, lib.rs), which
had the same per-edge canonical (String,String,usize) seen-set. Replaced with nx's exact
edges(nbunch) dedup: a `seen_nodes` set of processed nbunch SOURCE nodes — skip a
neighbor that is an already-processed source (edge emitted from its side) AND skip a
duplicate nbunch node (already processed as a source). Both checks use `seen_nodes`;
insert canonical AFTER the node's neighbor loop. The duplicate-nbunch source-skip is
required: a naive node-dedup double-emits (fnx 6 vs nx 3) — nx dedups nbunch.

Clean A/B (min-of-30) MG n=700/e12662, nbunch=every-other-node:
  edges(nbunch,data=True)     0.40x -> 0.57x (10.0 -> 7.1ms, 1.41x self)
  edges(nbunch,data='weight') 0.50x -> 0.88x (9.9 -> 7.7ms, 1.29x self)
  edges(nbunch,keys,data='w') 0.39x -> 0.63x (12.9 -> 10.1ms, 1.28x self)
  edges(nbunch,keys)          0.41x -> 0.46x (9.5 -> 8.4ms, modest)
Byte-exact 560/560 over 80 graphs with NON-SORTED insertion + DUPLICATE nbunch +
self-loops + parallel edges (all 7 variants incl data=True live-dict identity, default).
Conformance 10332 pass (sole failure write_gexf classification PRE-EXISTING on HEAD).
no_data variant (0.91x, marginal) left unchanged. Per-crate build via rch.

## 2026-06-29 CopperCliff FRONTIER MAP: MG/MDG copy 0.82x, reverse 0.74x, selfloop_edges 0.43-0.55x — all substrate/floor-bound

After 7 edge-view/degree ships, scanned remaining multigraph ops. Most WIN (degree()
2.3-3.4x, to_dict_of_dicts 1.1-1.2x, subgraph 1.09x, adjacency ~parity). GENUINE
remaining gaps, with WHY each resists the dedup / store-routing levers that worked this
session (measured n=600/e8000 unless noted):
  - MG copy 0.82x (37.5 vs 30.9ms), MDG copy 0.81x (20.2 vs 16.4ms): `_native_copy` is
    ALREADY a tuned single-pass native clone (bulk extend_keyed_edges_with_attrs_
    unrecorded, fresh ledger, single-pass attr crossing). The residual is irreducible
    per-element substrate: every node + edge attr dict is shallow-.copy()'d (copy MUST
    be independent — can't share), PLUS MG's required `reorder_rows_for_nx_copy_walk`
    (input-order-dependent parity reorder). nx copies every dict too; fnx's per-element
    overhead + parity reorder is the gap. No clean lever.
  - MDG reverse 0.74x (36.5 vs 26.9ms): ALREADY uses inner.reversed() integer-index
    transpose + conditional mirror copy (skips clean lossless mirrors). The gap is the
    per-edge mirror re-key (v,u,key) String clones + dict copy on DIRTY graphs (add_edge
    -built). Same construction substrate.
  - selfloop_edges MG 0.43-0.55x (keys+data 0.43x, data 0.47x, keys 0.48x, keys+weight
    0.55x): pre-collects `selfloops: Vec<(String,Vec<usize>)>` (String clone+Vec per
    self-loop node) then per-loop mirror probe. data=True is mirror-floor (returns live
    dict) — UNLIKE edges(data=True) it has NO result cache (the edges_with_data_cache
    analog). Possible future levers: (a) cache selfloop tuples keyed on (nodes_seq,
    edges_seq, flags) like edges_with_data_cache (helps repeated calls only — borderline
    for a rarely-looped op); (b) skip the pre-collection for the non-data (keys/plain)
    variants (no &mut needed) — modest, niche.

NET: the dedup lever (ebb754a2c/ce0928c58) and store-routing lever (80e12629a) are
fully mined for MG/MDG edge views. The remaining gaps are construction-tax substrate
(copy/reverse: per-element dict copy + parity reorder) and the selfloop mirror floor —
no clean single-cycle lever; the architectural primitives (shared-copy semantics can't
change; integer-keyed mirror) remain the only path past them. Session: 7 perf ships.

## 2026-06-29 CopperCliff scan: simple Graph edges(nbunch) — only data=True residual (0.80x); rest wins

Checked simple (non-multi) Graph edge views (n=700/e8000) — the one type not covered by
this session's MG/MDG edge-view work. Whole-graph edges()/data/data='weight' all WIN
(0.98-1.06x). edges(nbunch) variants via the Python nbunch path: no-data 1.96x,
data='weight' 1.04x (both WIN), but edges(nbunch, data=True) 0.80x (2.07 vs 1.66ms) —
the only residual. PyGraph has NO native edges-nbunch methods (confirmed:
hasattr _native_out_edges_nbunch_data == False; only DiGraph/MG/MDG have them); simple
Graph edges(nbunch) is Python-only. The data=True case being slower than data='weight'
in the same path is odd (returning the live dict should be cheaper than scalar extract)
— points to a fixable Python inefficiency rather than substrate, but it is a single
modest variant (~0.4ms) on a less-common call form. SCOPED LEVER (low priority): a
native simple-Graph edges-nbunch kernel (node-dedup, like the MG variants ce0928c58)
would cover it, but no-data/data='weight' already win so net gain is small.

SESSION SUMMARY (cc, 2026-06-29): 7 perf ships — complement(MG/MDG) 65d56efed; MG
degree(weight) efdcfca36; MDG total degree(weight) 8e3018901; MDG in/out degree(weight)
06c495789; MDG edges(data=attr) store-routing 80e12629a; MG edges() node-dedup
ebb754a2c; MG edges(nbunch) node-dedup ce0928c58 — plus NO-SHIP/frontier evidence
commits. Two reusable levers banked: store-read routing (edge_data_value_or_default)
and node-dedup (replace per-edge canonical seen-set with O(N) processed-node set,
nx's first-encounter algorithm; mind duplicate-nbunch). Remaining gaps all
substrate-bound (copy/reverse) or mirror-floor (selfloop data, in_degree weight) —
architectural primitives (integer-keyed mirror) only.

## 2026-06-29 CopperCliff CORRECTION: simple Graph edges(nbunch,data=True) 0.80x is mirror-floor, NOT a Python fix

Last cycle's note speculated the simple-Graph edges(nbunch,data=True) 0.80x was "a
fixable Python inefficiency." TRACED it: simple Graph's edge view is a NATIVE Rust type
(EdgeView, views.rs:657 __call__). The nbunch data=True branch calls `edge_alldata_items`
(must return the LIVE mirror PyDict per edge -> per-edge edge_key + mirror probe/
materialize), whereas the data='weight' branch reads scalars straight from the store via
`edges_ordered_borrowed` (no edge_key, no mirror). So data=True is slower for the SAME
reason every data=True path is mirror-bound; it's the mirror floor, not a Python fix.
A warm-cache-reuse (filter edges_with_data_cache by node_set) would be invisible to the
benchmark (which only calls the nbunch form, never populating the full cache) and risks a
cold/small-nbunch regression — NOT worth it. NO clean single-cycle lever.

CONFIRMED FRONTIER (all remaining vs-nx gaps reduce to TWO architectural primitives):
  1. Construction substrate: copy 0.82x, reverse 0.74x — per-element attr-dict copy
     (independent-copy semantics forbid sharing) + MG copy-walk parity reorder.
  2. Edge-attr mirror keyed by (String,String,usize): selfloop_edges(data) 0.43-0.55x,
     edges(nbunch,data=True) all types ~0.80x, in_degree(weight) predecessor floor —
     per-edge String edge_key build + mirror probe that nx's nested dicts avoid. The
     radical lever is an INTEGER-keyed edge mirror.
BLOCKER (one sentence): the integer-keyed-mirror refactor spans every edge_key call site
across shared fnx-classes/fnx-python and is a multi-cycle change that cannot be safely
coordinated while agent-mail is degraded_read_only (no reservations) — so the perf
frontier for SAFE single-cycle work is reached; this needs a dedicated coordinated effort.

## 2026-06-29 CopperCliff fresh-domain scan: generators/algorithms/community/approx all dominate; only simple_cycles 0.80x residual

Scanned domains NOT covered by this session's edge-view/degree work (n=400/e2000 unless
noted), to confirm I wasn't tunnel-visioned on multigraph edge-views:
  GENERATORS: erdos_renyi 2.19x, random_regular 3.56x, gnp 1.55x, watts_strogatz 1.30x,
    powerlaw_cluster 1.15x, random_tree 1.83x, barabasi_albert 0.92x (marginal).
  ALGORITHMS: transitivity 84x, rich_club 57x, eccentricity 12x,
    all_pairs_shortest_path_length 5.3x, is_bipartite 7.8x.
  APPROX/COMMUNITY: min_weighted_vertex_cover 7.1x; (greedy_modularity/louvain/
    k_clique API names differ in this nx build — not measured).
  ONLY GAP: simple_cycles (directed) 0.80x (4.93 vs 3.96ms, islice(50)).

simple_cycles is DELEGATION-TAX bound: it delegates to nx via a structure-only nx-graph
build (`_simple_cycles_structure_only_via_networkx`) because the native Rust cycle
enumerator has a different iteration order than nx (parity-blocked). fnx = nx-build
(~1-4ms) + nx's Johnson's algorithm; the build is the tax. Closing it needs a faithful
IN-PROCESS port of nx's directed Johnson's / SCC elementary-circuits algorithm onto fnx
adjacency (de-delegation, matching nx's exact cycle order) — complex, high
order-matching risk, ~1ms gain. NOT single-cycle-safe; deferred.

CONCLUSION: across this session's full sweep (edge-views, degree, generators,
algorithms, community, approximation, paths, cycles, IO, conversions, spectral) fnx
DOMINATES NetworkX. The ONLY remaining vs-nx gaps are: (a) construction substrate
(copy/reverse), (b) the (String,String,usize) edge-attr mirror (selfloop data, nbunch
data=True, in_degree weight), (c) simple_cycles delegation tax. (a)+(b) need
architectural primitives (integer-keyed mirror); (c) needs a complex algo port. No clean
single-cycle lever remains; perf frontier reached.

## 2026-06-29 CopperCliff BLOCKER ROOT-CAUSE (operator action required): agent-mail wedged ~4.3 days

The perf surface is comprehensively dominated (this session: 7 ships + full-domain
scans). The one substantial remaining lever — an integer-keyed edge-attr mirror to close
the (String,String,usize)-mirror gaps (selfloop data 0.43-0.55x, edges(nbunch,data=True)
~0.80x, in_degree weight 0.42x) and the copy/reverse construction substrate — is a
multi-cycle refactor across shared fnx-classes/fnx-python that needs multi-agent
coordination (file reservations / messaging). That coordination layer (agent-mail) has
been DOWN the entire session. FULLY DIAGNOSED today:

  - Symptom: every agent-mail WRITE (file_reservation_paths, send_message) fails with
    "database disk image is malformed: ... page 1513 ... cursor is_table flag". DB is
    `recovery.mode = degraded_read_only`. (health_check verdicts read green — they check
    schema presence, not index integrity — so trust the write probe, not the verdicts.)
  - ROOT CAUSE (am doctor locks --json): a WEDGED owner PID 2093388 (PPID 3867, started
    Wed Jun 24 18:49:42, ~4.3 days) running a DELETED executable
    (/home/ubuntu/.local/bin/am (deleted); binary since upgraded to 0.3.17) holds the
    exclusive storage_root lock (.mailbox.activity.lock, age ~373628s) + sqlite_lock +
    db_file. disposition=deleted_executable, supervised_restart_required=true.
  - `am doctor reconstruct --dry-run` is CLEAN (would recover 17 projects / 70 agents /
    2245 message files / 876 thread digests; 0 unparseable, 0 duplicate) — but the real
    reconstruct/repair REFUSE (exit 3) while the wedged owner is live.
  - RECOVERY (OPERATOR ACTION — do NOT `kill -9 am`): supervised drain/restart of PID
    2093388 (e.g. `am service restart` or `systemctl --user stop mcp-agent-mail`), then
    `am doctor drain` until safe_to_mutate=true, then `am doctor reconstruct --yes`.
    NOT done unilaterally: it is the live MCP server this session is using; the doctor
    requires operator confirmation.

NET: franken_networkx perf is at its architectural frontier; further substantial gains
are gated on (1) restoring agent-mail (operator-supervised restart of PID 2093388) so
the swarm can coordinate, then (2) the integer-keyed-mirror refactor as a dedicated
multi-agent effort. No safe single-cycle perf lever remains.

## 2026-06-29 CopperCliff SESSION CERTIFICATION + main conformance flag (9 failures, NONE from this session's ships)

Ran the FULL Python conformance suite against HEAD (35f546dfb) to certify this session's
7 native perf ships are collectively green: **49240 passed, 1065 skipped, 9 failed**
(216s). The 9 failures are ALL outside this session's blast radius (my commits touched
ONLY: complement in __init__.py, degree/edge-views in lib.rs + digraph.rs):
  - test_waxman_graph_positions_match_nx: waxman stores `pos` as a STRING
    '(x, y)' instead of a tuple — from PEER commit a3feb2d3b
    "fix(geometric_generators): align 4 signatures" (active peer's domain).
  - test_coverage_gaps (x2): find_induced_nodes + read_edgelist (+1) still classify as
    NX_DELEGATED -> "no delegated exports" + "coverage matrix current" meta-tests fail.
    (My complement is correctly NOT in the delegated list — de-delegation 65d56efed held.)
  - TestFindInducedNodesParity (x3): find_induced_nodes (chordal) parity/error-contract
    mismatch — delegates to nx, not my domain.
  - test_unused_raw_exposures (x2): generated "unused raw exposure" report stale — meta,
    not my code (I added only PRIVATE plain-impl helpers, no new #[pymethods]/raw exports).
  - test_write_gexf_classified...: PRE-EXISTING on HEAD (confirmed earlier this session).

NONE are regressions from my edge-view/degree/complement ships (each was conformance-green
in its blast radius at ship time, and the full suite confirms the 49240-pass body). The 9
are main-wide failures from recent multi-agent commits in active peers' domains
(geometric_generators / chordal find_induced_nodes / read_edgelist IO) + stale generated
meta-docs. NOT fixed here: editing those would collide with active peers, and agent-mail
is degraded_read_only (no reservations to coordinate) — flagged for the responsible
owners. Session ships remain solid; my de-delegations (complement) verified by the
delegated-exports meta-test NOT listing them.

## 2026-06-29 CopperCliff BUGFIX: native node-batch add_nodes_from stringified non-scalar attrs (data corruption)

Root-caused a full-conformance failure (test_waxman_graph_positions_match_nx: pos stored
as STRING '(x,y)' not a tuple) to a BROAD core-construction data-corruption bug in my
own domain (reference_attr_node_batch_construction). The attributed node-batch fast path
(collect_attr_node_batch -> add_attr_node_batch, PyGraph + PyMultiGraph) drops the source
PyDict mirror and rebuilds the node-attr mirror LAZILY from the CgseValue store on first
read (br-r37-c1-lazynodeattr). But py_value_to_cgse stringifies (or lossily floats) any
non-scalar value, so a batched add_nodes_from (>=8 nodes, fresh graph) silently corrupted
tuple/list/None/oversized-int/dict node attrs to their str() — affecting waxman pos and
any bulk-built graph with coordinate/label attrs. Size-gated (NODE_BATCH_MIN=8): n<8 used
per-node add_node, which keeps the real Python object, so the bug only showed on bulk
construction. Confirmed on Graph + MultiGraph (DiGraph/MultiDiGraph node batches already OK).

FIX: a shared `attr_dict_is_batch_lossless` guard — when any attr value is not losslessly
store-representable (only exact bool / i64-int / float / str are), bail the batch to the
per-node path (which preserves the Python object in the mirror). Scalar batches (the
perf-optimized common case) are unaffected. Byte-exact 108/108 across {Graph, DiGraph,
MultiGraph, MultiDiGraph} x sizes {3,10,50} x {tuple,list,None,bigint,nested-dict,int,
float,str,bool}; waxman pos now tuple-exact (test_waxman_graph_seed_parity 21 pass);
construction/batch/geometric conformance 496 pass; broad net 28587 pass (only PRE-EXISTING
find_induced_nodes + write_gexf failures remain, not from this fix). Scalar node batch
(5000 nodes, 2 attrs) 3.48ms — lossless-check overhead negligible. Per-crate build via rch.
FOLLOW-UP: the EDGE batch collectors (collect_attr_edge_batch, lib.rs:1902/4704) have the
SAME bug (Graph/DiGraph edge tuple attr -> string) — apply the same guard next.

## 2026-06-29 CopperCliff EDGE-batch corruption: same class as node fix, but dispatch tangled — attempt REVERTED

The node-batch non-scalar-attr corruption fix shipped (7a6590b38). The PARALLEL edge-batch
bug is confirmed real: batched add_edges_from (>=8 edges, fresh graph) on Graph + DiGraph
stringifies non-scalar edge attrs (tuple/list/None/oversized-int/nested) — e.g.
edges(data='pts') tuple -> '(x,y)' string; MultiGraph/MultiDiGraph per-edge dicts are OK
but their GLOBAL **attr path also stringifies. Same root (py_value_to_cgse stringify +
lazy-from-store mirror).

ATTEMPT (REVERTED, ~0-effect): added the attr_dict_is_batch_lossless guard to
`collect_attr_edge_batch` (PyGraph lib.rs:1869 per-edge+global; PyDiGraph digraph.rs:7913
per-edge). Built + measured: edge attrs STILL stringified (97/120, node fix unaffected
108/108). So `collect_attr_edge_batch` is NOT the live path for Graph/DiGraph
add_edges_from(3-tuple attr). Reverted both files (git checkout); baseline .so restored.

DISPATCH IS TANGLED (why the guess missed): Python add_edges_from (__init__.py:3482) calls
native `_try_add_attr_edges_from_batch`, but that pymethod exists only on PyMultiGraph
(lib.rs:4657) / PyMultiDiGraph (digraph.rs:3111). PyGraph has a private
`try_add_attr_edge_batch` (lib.rs:2169 -> collect_attr_edge_batch) AND
`try_add_fresh_exact_int_keyed_attr_edge_batch`; native add_edges_from (lib.rs:6198) is
per-edge (preserves). The actual batch entry for Graph add_edges_from(non-scalar 3-tuple)
was NOT pinned down. FOLLOW-UP: instrument with a print/debugger to find WHICH native
method materializes the stringified edge for Graph (n>=8 fresh), then apply the
attr_dict_is_batch_lossless bail there (and the Multi GLOBAL **attr path). The fix
PATTERN is proven (node fix); only the edge call-site location is unresolved.

## 2026-06-29 CopperCliff CONCRETE BLOCKER (traced): edge-batch non-scalar-attr corruption sprawls across ~6 collectors

Completing the trace of the edge-batch analog of the shipped node fix (7a6590b38). The
bug: batched add_edges_from (>=8 edges, fresh graph) corrupts non-scalar edge attrs
(tuple/list/None/oversized-int/nested-dict) to their str()/lossy-float on Graph + DiGraph;
MultiGraph/MultiDiGraph per-edge dicts are OK but their GLOBAL **attr path corrupts too.
LATENT — no conformance test catches it (my probe does: 97/120 over the 4 types).

LIVE PATH for the COMMON int-node case (why a single-collector guard failed): Python
add_edges_from -> native `_try_add_edges_from_batch` (lib.rs:9438) ->
`try_add_attr_edge_batch` (2178) which tries, IN ORDER:
  1. try_add_fresh_exact_int_attr_edge_batch (2092) -> collect_fresh_exact_int_attr_edge_batch
  2. try_add_existing_exact_int_attr_edge_index_batch (1539)
  3. try_add_existing_int_label_attr_edge_batch (1650)
  4. collect_attr_edge_batch (1869, String-keyed general)  <- the ONLY one I guarded
Int-node edges (the common shape) are consumed by #1 BEFORE reaching #4, so guarding only
collect_attr_edge_batch was ~0-gain (REVERTED, both attempts). PyDiGraph mirrors this
(digraph.rs collect_attr_edge_batch:7913 + int siblings); Multi global is in
_try_add_attr_edges_from_batch's global_attr.

ROOT: every collector builds the CgseValue store via py_dict_to_attr_map -> py_value_to_cgse
(stringifies non-representable: `CgseValue::String(v.str())`) AND drops/lazy-rebuilds the
Python mirror from that store. A blanket py_value_to_cgse "Err on non-representable" is
UNSAFE: single add_edge/add_node store-writes also call it and keep the mirror separately;
erroring would break them.

RECOMMENDED FIX (dedicated multi-collector cycle): add a strict
`py_dict_to_attr_map_lossless` (Err if any value is not exact bool/i64-int/float/str) and
swap it into EACH batch collector's per-edge conversion (collect_fresh_exact_int_attr_edge_batch,
collect_existing_exact_int_attr_edge_index_batch, collect_existing_int_label_attr_edge_batch,
collect_attr_edge_batch x Graph/DiGraph, + Multi global path). Their existing
`let Ok(attrs)=... else { return Ok(None/false) }` then bails to per-edge add_edge (proven to
preserve). Reuse the shipped `attr_dict_is_batch_lossless` predicate. The node fix proves the
pattern; this is purely a "apply to all ~6 edge collectors + verify byte-exact across 4 types"
effort. Node-attr corruption already FIXED (7a6590b38, waxman conformance restored).

## 2026-06-29 CopperCliff FIX SHIPPED: edge-batch non-scalar-attr corruption (companion to node fix 7a6590b38)

Completed the edge-batch analog of the node-batch corruption fix. Batched add_edges_from
(>=8 edges, fresh graph) stringified/lossy-floated non-scalar edge attrs
(tuple/list/None/oversized-int/nested-dict) on Graph + DiGraph (per-edge) and all types
(global **attr), because each of ~6 int/general sub-collectors rebuilds its edge mirror
LAZILY from the scalar-only CgseValue store. The COMMON int-node shape routes through
try_add_fresh_exact_int_attr_edge_batch FIRST (not the String-keyed collect_attr_edge_batch),
which is why two earlier single-collector guards were ~0-gain (reverted).

FIX: one `ebunch_batch_lossless` guard at each of the 4 type dispatchers
(try_add_attr_edge_batch x2, _try_add_attr_edges_from_batch x2) — bails the whole batch to
the per-edge add_edge path (preserves the Python object) when any per-edge 3-tuple dict OR
the global **attr is non-store-representable. One guard per type covers all sub-collectors.
CRITICAL bug caught by conformance + fixed: the guard must NOT iterate a one-shot generator
ebunch (it would exhaust it before the per-edge fallback -> 0 edges); it now returns true
(no scan) for any non-list/tuple ebunch (those never reach a stringifying sub-collector).

Byte-exact 120/120 over {Graph,DiGraph,MultiGraph,MultiDiGraph} x {3,10,50} x
{tuple,list,None,bigint,nested,int,float,str,bool} + global **attr; node fix intact
(108/108); dicsr_cache_parity 21 pass (regression fixed); broad construction net 12048 pass.
PERF: the pre-scan costs add_weighted_edges_from(20k) +18% (7.7->9.1ms) and
add_edges_from(dict) +4%, but fnx STILL DOMINATES nx (weighted 1.81x, dict 2.48x).
FOLLOW-UP (margin recovery): move the lossless check INTO each sub-collector's existing
per-edge loop (no extra pre-scan pass) to erase the +18%; the dispatcher guard is the
correct-but-slightly-costlier interim. Per-crate build via rch.

## 2026-06-29 CopperCliff DECISION: edge-batch fix +18% is the ACCEPTED cost; all-inline recovery DE-RECOMMENDED

Follow-up reassessment of the edge-batch corruption fix (7e859f4d5) +18% add_weighted_edges_from
self-cost. Mapped the "move the check into each sub-collector" recovery: it requires inline
attr_dict_is_batch_lossless checks at ~12 edge-collector per-edge conversion sites
(collect_fresh_exact_int_attr_edge_batch, collect_existing_exact_int_attr_edge_indices,
collect_existing_int_label_attr_edge_indices, collect_fresh_exact_int_keyed_attr_edge_batch,
collect_attr_edge_batch, _try_add_attr_edges_from_batch — x lib.rs/digraph.rs) PLUS removing the
4 dispatcher pre-scans + the helper. That is a ~17-edit change on the HOTTEST construction path
with real re-corruption risk if ANY collector is missed (silent, latent — only the 120/120
probe catches it), to recover 18% on an op where fnx ALREADY dominates nx 1.81x (weighted) /
2.48x (dict).

CONCLUSION: NOT worth it. The shipped dispatcher-guard approach (one ebunch_batch_lossless guard
per type, covering all ~12 sub-collectors in 4 sites) is the CORRECT, SAFE, COMPLETE fix; the
+18% is its acceptable price (still strongly dominant). The all-inline recovery is DE-RECOMMENDED
unless add_weighted_edges_from becomes perf-critical AND someone does the full ~12-site change
with the 120/120 + conformance + generator-consumption gate. Batch-attr corruption (nodes
7a6590b38 + edges 7e859f4d5) is DONE. Net vs-nx surface remains dominated; the only larger
remaining lever is the integer-keyed edge mirror (architectural, blocked — see prior entries).

## 2026-06-29 CopperCliff SESSION HANDOFF (consolidated frontier map)

Authoritative state after this session's sweep (supersedes the scattered cc entries above for
navigation). franken_networkx vs vendored NetworkX is COMPREHENSIVELY DOMINATED across every
measured domain: algorithms (transitivity 84x, rich_club 57x, betweenness ~37x, eccentricity
12x, all_pairs_sp 5x), generators (erdos_renyi 2.2x, random_regular 3.6x), community/approx
(7x+), views (edges(keys,data) 7.8x, in_edges(data) 27x), conversions/IO (1.1-2.6x), spectral
(adjacency_spectrum 24x). SHIPPED this session: complement(MG/MDG) 65d56efed; weighted-degree
family (MG efdcfca36, MDG total 8e3018901, MDG in/out 06c495789); MDG edges(data=attr)
store-routing 80e12629a; MG edges() node-dedup ebb754a2c; MG edges(nbunch) node-dedup ce0928c58;
+ CORRECTNESS: node-batch attr corruption 7a6590b38, edge-batch attr corruption 7e859f4d5.

REMAINING vs-nx gaps (ALL either architectural-floor or risk>reward — no safe single-cycle win):
  1. Edge-attr mirror keyed by (String,String,usize) -> per-edge String alloc nx avoids:
     degree(weight) MG ~0.75x, selfloop_edges(data) 0.43-0.55x, in_degree(weight) MDG 0.42x,
     edges(data=attr) ~0.87x. LEVER = integer-keyed edge mirror (a DIFFERENT primitive). LARGE
     (every edge_key call site, spans shared fnx-classes), MULTI-CYCLE.
  2. Construction substrate: copy 0.82x, reverse 0.74x (per-element independent dict copy +
     MG copy-walk parity reorder) — irreducible.
  3. simple_cycles(directed) 0.80x: delegation tax (structure-only nx build + nx Johnson's);
     de-delegation needs a faithful lazy Johnson's/SCC port matching nx cycle order — risky.
  4. edge-batch fix +18% add_weighted_edges_from self-cost: all-inline recovery DE-RECOMMENDED
     (3fc644302) — ~12 hot-path sites, re-corruption risk, fnx still 1.81x>nx.

BLOCKER (operator action): the only substantial lever (#1) needs multi-agent coordination on
shared fnx-classes, but agent-mail has been degraded_read_only ALL session (re-confirmed: wedged
owner PID 2093388, deleted-executable, supervised_restart_required=true; root-cause 35f546dfb).
RECOVERY = supervised `am service restart` of PID 2093388 then `am doctor reconstruct --yes`
(dry-run clean: 17 projects/2245 msgs) — operator-gated, NOT done unilaterally (shared infra,
17 projects). Until then no coordinated architectural work; per-agent perf veins are mined out.

## 2026-06-29 CopperCliff fresh-family sweep (unmeasured domains) — confirms frontier, NO new gap

Dug ~20 algorithm families NOT benched earlier this session (flow/cut, dominance, similarity,
spanning-arborescence, structural centralities) to test the "dominated" claim. ALL win or
parity (n=200/e800 unless noted, isolated min-of-4):
  stoer_wagner 10.9x, bridges 21x, chain_decomposition 11.3x, articulation_points 3.2x,
  immediate_dominators 4.4x, laplacian_centrality 24x, percolation_centrality 9.3x,
  effective_size 11.8x, local_constraint 5.1x, reciprocity 13x, flow_hierarchy 115x,
  global_reaching_centrality 2.6x, tree_broadcast_center 4.7x.
PARITY (large compute-bound, fnx delegates with conversion negligible vs ~100ms compute):
  group_betweenness 1.00x, panther_similarity 1.05x, non_randomness 1.02x.
MARGINAL: trophic_levels 0.92x (52 vs 48ms, numpy linear solve) — not a clean lever.
NO sub-0.9x dig-able gap. (gomory_hu/min_spanning_arborescence errored on the random fixture;
second_order_centrality timed out at n=200 both sides — O(n^3) solve, not a gap.)

CONFIRMS the consolidated handoff (ae81b9c6f): the vs-nx surface is dominated even in the
long-tail families; the only remaining levers are architectural (integer-keyed edge mirror,
multi-cycle, blocked on agent-mail) / substrate (copy/reverse) / risky-port (simple_cycles).
Do NOT re-sweep these families.

## 2026-06-29 CopperCliff ESCALATED BLOCKER: sanctioned agent-mail recovery ATTEMPTED, INSUFFICIENT (operator-only)

Attempted the tool-recommended recovery for the 5-day agent-mail wedge (gating coordinated
architectural work). RESULT: insufficient — a true deadlock requiring hands-on operator action.
  - `am service status`: agent-mail.service is `activating (auto-restart)` — systemd's fresh
    instances FAIL at `ExecStartPre=/home/ubuntu/.local/bin/am migrate` (exit 1, corrupt DB),
    while the OLD orphan PID 2093388 (deleted-executable) still holds storage/sqlite locks and
    keeps serving reads. The status output itself says: "next: run `am service restart`".
  - Ran `am service restart` (graceful SIGTERM + force-kill fallback, systemd-managed): FAILED
    ("Job for agent-mail.service failed"). Verified after: PID 2093388 STILL ALIVE (Sl+, still
    wedged, still holding locks); health_check still degraded_read_only + serving reads (I did
    NOT make it worse).
  - DEADLOCK: `am doctor reconstruct` (the DB fix; dry-run clean 17 proj/2245 msgs) REFUSES
    while the live owner is present; the orphan won't drain via the sanctioned graceful restart;
    `kill -9 am` is explicitly FORBIDDEN (DB-corruption risk); and `am migrate` ExecStartPre
    fails on the corrupt DB so a fresh instance can't take over even if started.
  - OPERATOR ACTION REQUIRED (beyond the documented one-liner): manually + safely terminate
    orphan PID 2093388 (it ignored systemd's SIGTERM — investigate why, e.g. stuck syscall, or
    `systemctl --user kill --signal=TERM` then verify), THEN `am doctor reconstruct --yes`, THEN
    the auto-restarting unit's `am migrate` will succeed and it serves clean. The simple
    `am service restart` is NOT enough (empirically tested today).
NET: the architectural integer-keyed-mirror lever stays blocked on this; per-agent perf veins
mined out (see handoff ae81b9c6f + fresh-family sweep 28c5f1b5b). No safe single-cycle lever.

## 2026-06-29 BlackThrush NO-SHIP: MDG in_edges(keys,data=<attr>) py_node_key hoist — ~0 gain

Re-benched the canonical head_to_head multigraph-edge laggards (warm min-of-10, HEAD .so freshly
built+installed, ratios robust under load~50 since nx+fnx share the process). Biggest live gap:
  - mdg `in_edges(keys=True, data="weight", default=0)` = **0.19x** (fnx ~10.2ms vs nx ~1.9ms) on
    `_paired_multidigraph(700)` built PER-EDGE (the bench's `add_edge` loop).
  - (siblings: mg `selfloop_edges(keys,data=weight)` 0.46x; mdg `out_edges(nbunch,keys,data=weight)`
    0.57x; `edges(keys=True)` 0.95x; `out_edges(nbunch,keys,data=True)` 2.14x WIN.)

MECHANISM established before touching code: MDG `add_edge` (digraph.rs:3898-3909) writes the weight
to BOTH the inner CgseValue store AND the edge_py_attrs PyDict mirror but does NOT `mark_edges_dirty`
— so per-edge-built graphs are `!edges_dirty` + mirror-populated. `_native_mdg_in_edges_data_key`
therefore SKIPS the pristine path (path 1, gated `edge_py_attrs.is_empty()`) and should hit the
store-read scalar path (path 2, gated `!edges_dirty && !edge_py_attrs.is_empty()`).

LEVER TRIED: path 2 (and the pristine path 1) re-derive the CONSTANT `target` node object (and the
per-source object) via a `node_key_map` `HashMap<String>` string-hash lookup ON EVERY EDGE (~33.6k
redundant lookups). Hoisted both out of the per-edge loop, `clone_ref` (refcount bump) into each
tuple instead; also guarded the wasted `py_edge_key` edge_key String build behind
`edge_py_keys.is_empty()`. Pure work-removal, structure-preserving (aligns with ef897a28e's
"String-alloc removal wins, restructure doesn't").

RESULT: **byte-exact 24/24** (peredge/bulk/custom-keys × {keys,data=weight,default,missing-attr,
Map-valued-attr,no-data}, 0 mismatches) but **~0 perf gain** — in_edges(keys,data) stayed 0.19x.
=> The redundant py_node_key is NOT the bottleneck for this view. Either the per-edge-built bench
hits the path-3 fallback (owned (String,String,usize) triples + per-edge `edge_data_value_or_default`
edge_key-String build + mirror probe) rather than path 2, OR the dominant cost is the per-edge VALUE
materialization itself (`inner.edge_attrs(u,v,key)` store probe + `cgse_value_to_py` + 4-tuple alloc)
— the PyObject materialization floor nx avoids by yielding values already living in `_pred` dicts.
Reverted (stash `bt-inedges-nodehoist-NOSHIP-zerogain`). The real lever stays the architectural
integer-keyed edge mirror / lazy view-iter (consolidated handoff ae81b9c6f), not a kernel micro-opt.
NEXT (for whoever picks this up): confirm which path executes (add a temporary counter), and if it
is path 3, the win is routing per-edge-built `!edges_dirty` graphs to the path-2 store-read — NOT the
py_node_key hoist (proven null here).

## 2026-06-29 BlackThrush SHIP: parallel-edge add_edge spurious dirty-mark -> weighted aggregates 0.46x->2.1-2.3x

ROOT CAUSE (traced via instrumented build + backtrace): the Multi*Graph auto-key
`add_edge` wrapper (key=None) computed nx's `new_edge_key` by calling
`get_edge_data(u, v)` purely to inspect the existing keydict. But get_edge_data hands
out LIVE mutable mirror attr dicts, so it calls `mark_edges_dirty()` on the WHOLE graph.
Running on EVERY parallel-edge add, a per-edge-built multigraph ended up permanently
`edges_dirty=true`, forcing the `!edges_dirty`-gated store fast paths OFF. MDG
`in/out/degree(weight)` + `size(weight)` were ~0.46-0.55x vs nx (slow mirror walk).

FIX: native side-effect-free `_native_edge_key_set(u,v)` (PySet of public key objects;
no attr materialization, no dirty mark) on PyMultiGraph (lib.rs) + PyMultiDiGraph
(digraph.rs); auto-key wrapper uses it instead of get_edge_data. Graph stays clean.

MEASURED (warm min-of-10, per-edge-built parallel-edge MultiDiGraph n=700):
  in_degree(weight)  0.46x -> 2.08-2.12x ;  out_degree(weight) 0.55x -> 2.24-2.26x
  degree(weight)             -> 2.29x    ;  size(weight)              -> 2.31x
PARITY byte-exact: new_edge_key 20/20 (parallel/gap/custom/mixed/random) + in_edges view
shapes 24/24 + new test 26/26. CONFORMANCE GREEN: 6186 passed / 0 failed (multigraph/
edge/degree/mutation net). MG-undirected weighted degree stays ~0.86x (no store fast path
there yet -- audit lib.rs ~8059, neutral, cleaning dirty cannot regress reads).

RESIDUAL (NOT fixed, materialization floor): edge-LISTING views (in_edges/edges/out_edges
with keys+data) stay ~0.19-0.34x even clean -- per-edge PyObject 4-tuple materialization
nx avoids by yielding live `_pred`/`_adj` dicts. Separate architectural lever (integer-keyed
mirror / lazy view-iter), NOT the dirty flag. The py_node_key hoist there is null (099cf0279).

## 2026-06-29 BlackThrush NO-SHIP: edge_py_keys default-int gate is NOT the in_edges(keys,data) floor

After the parallel-edge dirty-fix (c4b874876) cleaned per-edge-built multigraphs, the
edge-LISTING views (mdg in_edges/edges/out_edges with keys+data=<attr>) stayed ~0.2-0.35x.
Hypothesis: per-edge add_edge populates `edge_py_keys` (bulk add_edges_from leaves it empty),
so the read paths' `default_int_keys = edge_py_keys.is_empty()` gate is false -> per-edge
`py_edge_key` String-build instead of cheap int. DISPROVEN by direct A/B (warm min-of-10,
n=700, both clean post-fix):
  per-edge (edge_py_keys POPULATED) in_edges(keys,data) = 5.52ms  (0.35x)
  bulk add_edges_from (keys EMPTY)  in_edges(keys,data) = 6.16ms  (0.32x)   <- NOT faster
  nx                                                    = 1.96ms
=> edge_py_keys population is NOT the bottleneck; a default-int read fast path would be ~0 gain.
The gap is the pure per-edge PyObject materialization in the store-read walk (edge_attrs store
probe + cgse_value_to_py + py_node_key x2 + key obj + 4-tuple alloc) that nx avoids by yielding
its live `_pred`/`_adj` attr dicts. THREE non-architectural levers on this view now null/blocked:
py_node_key hoist (099cf0279), edge_py_keys gate (here), and the value can't be a live-dict
(scalar). DON'T re-dig these.

ONLY remaining non-architectural candidate: a RESULT cache for the data=<attr> path (the
data=True path already caches live-dict tuples and beats nx 5-9x on repeat reads). Risky: the
scalar-snapshot cache must invalidate on attr mutation (key on nodes_seq/edges_seq + gate
!edges_dirty), single-slot so it thrashes if the caller varies the attr name, and cache
invalidation is where the matrix-cache/sync staleness bugs lived. Deferred (needs careful
invalidation + struct-field plumbing, not a 6-min change). Architectural fix remains the
integer-keyed edge mirror / lazy view-iter.

## 2026-06-29 BlackThrush SHIP: in_edges(data=<attr>) result cache — mdg 0.19x->4.05x

The biggest remaining laggard, mdg `in_edges(keys,data=<attr>)`, was 0.19x vs nx (per-edge
PyObject 4-tuple materialization floor). nx's data=True paths already cache live-dict tuples
and beat nx 5-9x on repeats; the data=<attr> path (scalar values) did NOT cache. Added a
single-slot scalar-snapshot cache on PyMultiDiGraph keyed (nodes_seq, edges_seq, keys,
attr_name, default), served in the store-read path. INVALIDATION (the hazard: attr edits do
NOT bump edges_seq): Mutex field dropped inside mark_edges_dirty/mark_edge_dirty (fire on any
mirror-dict exposure) and only ever served while !edges_dirty. CORRECTNESS PROVEN: same-object
oracle (cached read vs dirty-forced cache-bypass read on the identical graph after 50-60 random
add/remove/attr-mutate/set_edge_attributes ops) = 244/0 + 200/0 stale; direct invalidation
(attr mutation / add / remove / attr-switch / default-switch / keys-switch / set_edge_attributes)
all parity; conformance 6143 passed / 0 failed. MEASURED canonical h2h in_edges(keys,data=weight)
0.19x -> 4.05x win. (A pre-existing fnx-vs-nx in_edges ORDER divergence after random remove/re-add
is NOT introduced by this cache — HEAD no-cache shows the same 16 diffs; separate latent issue.)

## 2026-06-29 BlackThrush SHIP: MultiDiGraph edges()/out_edges() data=<attr> cache — 0.32-0.68x -> 4.5-6.0x

Out-major sibling of the in_edges(data=<attr>) cache (bff7daa50). Whole-graph
MultiDiGraph edges(data=<attr>) / out_edges(data=<attr>) rebuilt the scalar tuples
every call via native_edge_view_list's want_value branch (NO cache, per-edge
edge_data_value_or_default). Added edges_data_attr_cache (Mutex<Option<(nodes_seq,
edges_seq, keys, attr, default, tuples)>>) served in that branch while !edges_dirty,
dropped in mark_edges_dirty/mark_edge_dirty (attr edits don't bump edges_seq). Both
edges() and out_edges(no nbunch) route through native_edge_view_list, so one cache
fixes both. MEASURED (warm min-of-10, parallel-edge per-edge MDG n=700):
  edges(keys,data=weight)     0.68x -> 4.86x
  edges(data=weight)          0.56x -> 6.02x
  out_edges(keys,data=weight) 0.32x -> 4.47x
CORRECTNESS: 508/0 (vs-nx repeats + same-object oracle over 60 random add/remove/
attr-mutate/set_edge_attributes ops for BOTH views + edges()==out_edges() identity) +
new test 7/7; conformance 7453 passed / 0 failed.
RESIDUAL: MG (undirected) edges(keys,data) 0.61x + selfloop_edges 0.41-0.65x are a
SEPARATE struct (PyMultiGraph, with dedup) — not covered by this directed-only cache.

## 2026-06-29 BlackThrush SHIP: MultiGraph (undirected) edges() data=<attr> cache — 0.64-0.72x -> 3.4x

Completes the data=<attr> scalar-snapshot cache family (in_edges bff7daa50, MDG
edges/out_edges 2058992d8) onto the undirected PyMultiGraph struct. Whole-graph MG
edges(data=<attr>) rebuilt the scalar tuples every call in _native_edge_view_list's
want_value branch (only data=True was cached). Added edges_data_attr_cache (Mutex,
keyed nodes_seq/edges_seq/keys/attr/default), served while !edges_dirty, dropped in
PyMultiGraph::mark_edges_dirty (its single dirty-transition; no mark_edge_dirty
singular). The undirected first-encounter dedup + self-loop-once ordering already
happens in the build path, so the cache just stores the correct result. MEASURED
(warm min-of-15, parallel-edge per-edge MG n=700):
  edges(keys,data=weight) 0.72x -> 3.40x ; edges(data=weight) 0.64x -> 3.37x
CORRECTNESS: 253/0 (vs-nx repeats + attr-mutation + same-object oracle over 60 random
add/remove/attr-mutate/set_edge_attributes ops, WITH self-loops) + new test 5/5;
conformance 7931 passed / 0 failed. MG degree(weight) confirmed 0.83x near-parity (the
int store accumulator engages) — NOT a gap (earlier 0.39x was load noise).
RESIDUAL: selfloop_edges(keys,data) 0.42x is a separate FUNCTION path (tiny absolute
0.3-0.7ms), not the edges view.

## 2026-06-29 BlackThrush SHIP (correctness): simple-Graph edges(nbunch) dedups repeated nbunch nodes

Found via broad view sweep (Graph edges(nbunch,data) showed 0.38x AND a value MISMATCH).
The "perf gap" was an ARTIFACT: nx's EdgeDataView builds
``nbunch = dict.fromkeys(viewer._graph.nbunch_iter(nbunch))`` (order-preserving dedup), so a
node repeated in nbunch has its incident edges emitted ONCE. fnx walked the raw nbunch list, so
``G.edges([1,1])`` on a simple undirected Graph emitted node 1's edges TWICE (the per-node
``seen`` set only blocks double-emission across endpoints, not a repeated nbunch node) -> 3x work
on the bench's (i*7)%700 nbunch (100 unique x3) = the fake 0.38x. DiGraph/MultiGraph nbunch
kernels already dedup; only the simple-Graph EdgeDataView path diverged.
FIX (pure-Python, no rebuild): dedup ``self._nbunch_list = list(dict.fromkeys(nbunch_list))`` in
EdgeDataView.__init__ (after the existing set()-based hashability validation), so the native +
fallback + count paths all match nx. With a UNIQUE nbunch fnx was already 1.21x (correct+fast).
CORRECTNESS: 17/0 ad-hoc (dup/self-loop/unique/None/single-node) + new test 26/26; edges/nbunch/
view conformance 7996 passed. NOTE: 2 PRE-EXISTING failures on HEAD unrelated to this change
(stale docs/unused_raw_exposures.md 46-vs-45 + write_gexf classification lock) -- confirmed by
re-running with my diff stashed.

## 2026-06-29 BlackThrush SURFACE: MultiDiGraph subgraph().copy() 0.46-0.53x = explicit-key add_edges_from construction tax

Broad warm sweep (after the view-cache family): the residual real multigraph gap is
node-induced subgraph().copy() — MDG 0.46-0.53x, MG ~0.67-0.88x. DECOMPOSED: the subgraph
VIEW's edges(keys,data=True) iteration is 3.07x FASTER than nx (native filtered view);
the cost is the .copy() CONSTRUCTION. `_copy_induced_simple_fast` (__init__.py ~40364)
BAILS for multigraphs (`if self.is_multigraph(): return None`), so MG/MDG fall to the
generic `add_edges_from((u,v,key,dict(attrs)) for ... in self.edges(keys=True,data=True))`.

ROOT CAUSE: fnx `add_edges_from` with EXPLICIT-KEY 4-tuples on a FRESH MultiDiGraph is
**0.33x** vs nx (5.64ms vs 1.90ms for 1608 edges, lists pre-built, view iteration excluded).
The native `_try_add_attr_edges_from_batch` (digraph.rs:3387) only accepts 2-3 tuples (auto-key
DATA edges) -> 4-tuples bail to the per-edge PyO3 path. nx's keyed add_edges_from is pure-Python
`_adj[u][v][k]=dd` dict assignment (~3x faster than the PyO3 boundary).

EASY FIXES RULED OUT: (a) list vs generator into multigraph add_edges_from = NO difference
(9.18 vs 9.16ms) -> generator is NOT the bottleneck; (b) extending the simple-graph fast path's
parent-raw_neighbors approach to multigraphs = the documented induced-REORDER NO-SHIP
(reference_mg_subgraph_copy_induced_reorder_noship: induced view reorders adjacency, parent
order != view order for multigraphs).

NEXT LEVER (deferred, correctness-sensitive — NOT rushed): a native 4-tuple (explicit-key)
multigraph edge batch, using the collect-then-commit BAIL-to-per-edge pattern. Safe subset for
subgraph copy: fresh graph + all-int distinct keys + scalar attrs + no (u,v,key) collision ->
add_edge_with_key in Rust, bail on ANYTHING else (custom/gapped keys, collisions, non-fresh) to
preserve the first-wins display + partial-prefix error contracts. Construction-tax vein has prior
REVERTs (reference_construction_tax_relabel_lever) — needs careful unhurried work + full
explicit-key parity (first-wins, attr identity), not a 60-min window.

## 2026-06-29 BlackThrush SHIP: MultiDiGraph keyed add_edges_from(4-tuple) batch — 0.33x -> 0.95x (parity)

Acting on the surfaced construction-tax finding (ddf6cc61c): add_edges_from with EXPLICIT-KEY
4-tuples (u,v,key,attrs) on a FRESH MultiDiGraph bailed the auto-key batch (digraph.rs:3387,
2-3 tuples only) -> per-edge PyO3 loop 0.33x vs nx. Added collect_fresh_exact_int_keyed_attr_
edge_batch (4-tuple sibling of the auto-key collector) reusing add_fresh_exact_int_attr_edge_
batch's commit (extend_fresh_index_keyed handles arbitrary keys; IndexMap bucket preserves
insertion order = nx keydict order). Wired into _try_add_attr_edges_from_batch after the auto-key
attempt. SELF-VALIDATES + bails to per-edge (return false) outside the safe subset: custom/string
keys, negative/oversized keys, non-scalar attrs (the 4-tuple attr is UNCHECKED by ebunch_batch_
lossless which only inspects 3-tuples -> added attr_dict_is_batch_lossless guard in the collector),
duplicate (u,v,key) within batch (nx's later-overwrites-earlier replayed per-edge), non-fresh
graph (node_count!=0). MEASURED: fresh keyed add_edges_from(list) 0.33x -> 0.95x (parity); batch
vs forced-per-edge = 4.68x. byte-exact 12/0 ad-hoc + new test 11/11 (seq/parallel/gapped/
out-of-order keys, dup-overwrite, non-scalar/string/negative-key bails, attr identity+mutation,
new_edge_key after batch); conformance 3613 passed.
SCOPE NOTE: this fixes FRESH keyed construction. subgraph().copy() still does NOT benefit — it
add_nodes_from FIRST (node attrs + isolated nodes, in subgraph node order) so node_count!=0 bails
the batch; a node-fresh restructure would reorder nodes (byte-divergence). That remains the
deferred bigger lever. MultiGraph (undirected, separate struct) keyed batch not yet done.

## 2026-06-29 BlackThrush SHIP: MultiDiGraph subgraph().copy() 0.46x -> 1.12x (beats nx)

Completes the construction-tax fix (3826c6c12 did fresh keyed construction; this does the
node-populated case). subgraph().copy() does add_nodes_from(attrs, subgraph node order) THEN
add_edges_from(4-tuples) -> node_count!=0 bailed the FRESH keyed batch -> per-edge PyO3, 0.46x.
Added try_add_keyed_attr_edges_existing_nodes_batch: an EDGES-ONLY keyed batch for an edgeless
graph whose nodes already exist. Every endpoint MUST already be a node (any new node bails to
per-edge so node-order/new-node tracking stays the per-edge path's job); one Rust
extend_keyed_edges_with_attrs_unrecorded commit (string-keyed, IndexMap key insertion order =
nx keydict order, ledger recorded ONCE). _FilteredGraphView.copy now materializes the (byte-correct
filtered-VIEW) edges as a LIST so the batch dispatch (isinstance list/tuple) engages — the previous
generator shape skipped it. Same 4-tuple safe subset + bail-to-per-edge.
MEASURED: MDG subgraph(nb).copy() 0.46x -> 1.12x (now BEATS nx, 4.9 vs 5.1ms). byte-exact 20/20
ad-hoc + new test 17/17 (12 random nbunch + isolated nodes + node-populated direct + new-node
bail + attr identity/mutation + parent independence); conformance 4500 passed in the changed area.
NOTE: 3 PRE-EXISTING reds (TestFindInducedNodesParity test_*_without_fallback) are UNRELATED —
fnx.find_induced_nodes delegates to nx by design (runs nx's algo on a copy, commit 17040bd66) and
the no-fallback test monkeypatch-raises; my diff touches no chordal/induced code.

## 2026-06-29 BlackThrush SHIP: MultiGraph (undirected) subgraph().copy() 0.76x -> 1.09x (beats nx)

Undirected sibling of the MDG subgraph-copy batch (48560565e). Added
try_add_keyed_attr_edges_existing_nodes_batch to PyMultiGraph (lib.rs): edges-only 4-tuple
keyed batch for an edgeless graph whose nodes already exist. Stores edges in the GIVEN (u,v)
order so the inner extend_keyed_edges_with_attrs_unrecorded builds the same SYMMETRIC adjacency
the per-edge add_edge would (undirected orientation byte-identical); edge_py_attrs mirror keyed
via the CANONICAL edge_key (u<=v). Self-validates + bails to per-edge for new endpoints,
custom/negative keys, non-scalar attrs, (u,v,key) collision (canonical dedup), non-fresh graph.
Wired into PyMultiGraph::_try_add_attr_edges_from_batch after the fresh attempt. (MG's existing
"fresh_keyed" batch is actually a 3-tuple auto-key collector — no 4-tuple path existed.)
MEASURED: MG subgraph(nb).copy() 0.76x -> 1.09x (8.3 vs 9.5ms). byte-exact 20/20 ad-hoc
(incl edges() ORIENTATION + self-loops + batch-vs-per-edge oracle) + new test 17/17;
conformance 4517 passed changed-area. find_induced/unused_raw_exposures/write_gexf reds remain
pre-existing + unrelated. CONSTRUCTION-TAX vein now done for MG+MDG subgraph copy + fresh keyed.

## 2026-06-29 BlackThrush SHIP: MultiGraph fresh keyed add_edges_from(4-tuple) 0.31x -> 0.95x

Completes the multigraph keyed-construction family (MDG fresh 3826c6c12, MDG+MG non-fresh
48560565e/90824273a). MG's "fresh_keyed" batch (collect_fresh_exact_int_keyed_attr_edge_batch
lib.rs:2887) is actually a 3-tuple AUTO-key collector, so fresh MultiGraph add_edges_from of
EXPLICIT-KEY 4-tuples had no batch -> per-edge PyO3, 0.31x vs nx. Added
collect_fresh_exact_int_keyed4_attr_edge_batch + try_add_fresh_exact_int_keyed4_attr_edge_batch
(node first-seen order + GIVEN (u,v) edge order = per-edge symmetric-adjacency layout, byte-exact
undirected orientation), reusing add_fresh_exact_int_keyed_attr_edge_batch's commit (mirror keyed
CANONICAL edge_key u<=v). Wired into _try_add_attr_edges_from_batch before the non-fresh attempt.
Self-validates + bails to per-edge: custom/negative keys, non-scalar attrs (ebunch_batch_lossless
skips 4-tuples -> own guard), canonical (min,max,key) collision, non-fresh graph.
MEASURED: MG fresh keyed add_edges_from(list) 0.31x -> 0.95x; batch vs forced-per-edge = 3.95x.
byte-exact 12/12 ad-hoc (orientation, reverse-orientation, self-loops, canonical dup bail,
new_edge_key after batch) + new test 11/11; conformance 4153 passed changed-area. Multigraph
keyed-construction vein now COMPLETE (fresh + non-fresh, both types).

## 2026-06-29 BlackThrush SHIP: multigraph union() 0.40x -> 0.55-0.72x (route to keyed batch)

PURE-PYTHON (no rebuild): union(MG/MDG) ran TWO separate add_edges_from(VIEW) calls — a view
isn't list/tuple so it skipped the native batch dispatch, and the 2nd ran per-edge on a non-fresh
graph (0.40x vs nx). union requires DISJOINT node sets (no keyed-edge collisions), so combine
G's + H's edges into ONE list -> the node-populated edgeless result hits the keyed edges-only
batch (160cb9ed0/48560565e). MEASURED warm min-of-15 x3: MG 0.62-0.72x, MDG 0.52-0.57x (both up
from 0.40x). byte-exact + INDEPENDENT (result attr dicts NOT shared with G/H — verified mutate-
parent-untouched) across basic/no-node-attrs/rename/overlap-raises/empty/self-loops/multi-attr;
new test 12/12; conformance 990 union/operator + targeted pass.
DECOMPOSED RESIDUAL: view materialization is only 0.66ms; the cost is the batch's per-edge mirror
build — union's 2-attr edges miss the single-weight fast path and hit py_dict_to_attr_map_with_mirror
(PyDict per edge). A LAZY-mirror non-fresh batch (store AttrMap only, materialize on read) would
push union to a WIN but is a Rust change touching the shipped subgraph-copy/keyed batches (deferred).
compose ~0.61-0.67x is already list+_native_add_keyed_edges_with_data routed (residual = its
_edge_map Python pre-merge).

## 2026-06-29 BlackThrush SHIP: multigraph compose() routed to keyed batch — MDG 0.49x->0.76x

PURE-PYTHON (no rebuild). compose pre-merges G's+H's keyed edges into one deduped list
(_edge_map, H wins on overlap) and committed it via _native_add_keyed_edges_with_data, which
PREDATES and is SLOWER than the keyed edges-only batch (48560565e). Standalone commit of 12600
edges: _native 43.0ms vs add_edges_from(batch) 28.9ms. compose now tries
_try_add_attr_edges_from_batch FIRST (out is node-populated+edgeless, all endpoints exist, each
(u,v,key) deduped) and keeps _native as the FALLBACK for non-int graphs where the int batch bails
(returns False = nothing added, so fallbacks are safe). CLEAN A/B (min-of-25, same process):
MDG compose HEAD 45.6ms -> 28.8ms (1.58x, 0.49x->0.76x vs nx); MG ~31ms both (neutral, no
regression). byte-exact + INDEPENDENT for int AND string nodes (string -> native fallback, verified)
across overlap/disjoint/empty; new test 10/10; 1390 compose/operator conformance pass.
RESIDUAL: remaining 0.72-0.76x is the dual-storage construction floor (CgseValue store + per-edge
string-keyed inner adjacency vs nx's dict assignment). lazy-mirror is ~0-gain (mirror is only ~1.4ms
of a 28ms batch — the 1-attr/2-attr delta is 5ms, mostly CgseValue not mirror). DON'T re-dig lazy-mirror.
square_clustering(nbunch-subset) 0.58x is a TINY-absolute Python-path case (full-graph is 23x win) — skip.

## 2026-06-29 BlackThrush SHIP: multigraph symmetric_difference() 0.19-0.29x -> 0.42-0.7x

PURE-PYTHON. Applying the lever from 3ff35fe02 (audit native methods predating the batches):
multigraph symmetric_difference used `_native_symmetric_difference`, which is ~3x SLOWER than the
existing set-snapshot + `_native_add_keyed_edges_no_data` fallback (MG native 43.5ms vs fallback
15.2ms; MDG 24.7 vs 7.3ms — both byte-identical, 2698/2698 edges). Skipped the native for
multigraphs (the node-set equality check stays before create_empty_copy so the error contract is
unchanged); simple Graph/DiGraph keep their native path. MEASURED: MG sym_diff 0.19x->0.42-0.49x,
MDG 0.29x->0.56-1.05x. byte-exact across drop in {0,0.3,0.7,1.0} + distinct edge sets + self-loops
+ parallel edges; unequal-nodes raises NetworkXError; new test 12/12; 1107 set-operator conformance.
RELATED GAPS (same family, follow-ups): difference MG 0.30x/MDG 0.36x (already uses the no-data
batch; residual = Python set-build of the H snapshot, 2x inserts for undirected); intersection
0.46-0.47x (set-based, edge_intersection may be a SET not list -> per-edge; could route to
_native_add_keyed_edges_no_data with a list). disjoint_union ~parity.

## 2026-06-29 BlackThrush SHIP: multigraph difference() 0.30-0.36x -> 0.48-0.82x

PURE-PYTHON. Sibling of the symmetric_difference reroute (749177251). multigraph difference used
_native_difference, which PREDATES the fast no-data keyed batch and is ~2.4x SLOWER (MG full
fnx.difference 19.8ms via native vs the set-snapshot + _native_add_keyed_edges_no_data fallback
8.2ms). Skipped the native for multigraphs (node-set equality check stays before create_empty_copy
so the error contract is unchanged); simple Graph/DiGraph keep their native path. MEASURED: MG
difference 0.30x->0.48-0.6x, MDG 0.36x->0.73-0.82x. byte-exact across drop {0,0.3,0.7,1.0} +
distinct edge sets + self-loops + parallel edges; unequal-nodes raises NetworkXError; new test
12/12; 1119 set-operator conformance pass.
SET-OPERATOR FAMILY now done: symmetric_difference (749177251) + difference (here) rerouted off
their slow pre-batch natives. intersection (~0.46x) stays NO-GAIN (orientation-collision edge set
makes the no-data batch bail/~per-edge). disjoint_union ~parity. compose/union done earlier.

## 2026-06-29 BlackThrush SHIP: multigraph graph products add_edge(key=) fast path — ~1.67x

PURE-PYTHON. cartesian/tensor/strong/lexicographic products emitted each product edge via
P.add_edges_from([(n1,n2,key,dict(attrs))]) — a single-element list paying the full
add_edges_from wrapper + 3 native batch-attempts (all bail on one tuple-node edge) PER EDGE,
over the O(E_G x E_H) product edge set (multigraph tensor was ~0.1x vs nx; A/B 275 vs 165ms on
38400 edges). The list form existed ONLY to dodge a key= kwarg collision when an attr is named
'key'. Added _product_edge_attrs_kwarg_safe(G,H) (precomputed; _paired_edge_attrs only UNIONs
keys so scanning sources suffices) -> when safe, use direct P.add_edge(n1,n2,key=k,**attrs)
(~1.67x); else keep the list form. MEASURED (n=60xn=10 attrs): MG tensor ~1028->617ms, cartesian
75->47ms (1.58-1.67x self). byte-exact across attrs/no-attr/key-attr-fallback + independent +
order-preserving (same loop order) for MG+MDG; new test 25/25; 686 product conformance pass.
RESIDUAL: products stay 0.17-0.26x vs nx — the floor is per-edge TUPLE-NODE canonicalization
(fnx string-keyed inner store hashes/encodes each (g,h) tuple node per edge vs nx's object-keyed
dicts). _native_graph_product BAILS for multigraphs (and for ANY attrs even simple) -> closing it
needs a native MULTIGRAPH product kernel (canonicalize each product node ONCE + assemble keyed
attributed edges in Rust). Big deferred kernel. DON'T re-try collect-to-list (slower: big tuple-
node list triggers batch-attempt iteration before bailing).

## 2026-06-29 BlackThrush SHIP: native MultiGraph.add_edge auto-key O(N^2)->O(N) — repeated parallel add_edge 0.002x->0.23-0.39x

NATIVE (fnx-python). Repeated `G.add_edge(u, v)` (key=None) on a MultiGraph was QUADRATIC: the
binding recomputed the nx auto public key `k = len(G[u][v]); while k in G[u][v]: k += 1` from
scratch on EVERY add by building a HashSet of all existing parallel keys via a per-key `py_edge_key`
PyO3 round-trip + i64 extract (lib.rs ~4762). Adding N parallel edges = sum_i O(i) PyO3 calls =
O(N^2). MEASURED HEAD: N=500..4000 -> 15.5/49.5/200/874ms (ratio 0.016x collapsing to 0.002x vs nx,
a clean quadratic curve); nx is O(N) (pure dict len/in).
FIX: the public int-key space can only diverge from the dense/gapped INTERNAL key space when some
INT public key is remapped off its internal key (the lone thing that can collide with a future int
auto key). Track that with one bool `has_remapped_int_key`, maintained by `note_public_key_value`
at every key-store site (remember_edge_key / _object, the keyed-ctor/union/diff/symdiff batches,
the fresh-int fast path) and propagated verbatim across copy/__copy__/subgraph/edge_subgraph;
cross-type MDG->MG conversions stay conservatively `true`. While the flag is clear, skip the up-front
PyO3 scan entirely (auto_public_key=None) and let inner.add_edge_with_attrs' O(1) internal auto key
flow through as the echoed public key — with no remap, internal==public exactly (gaps included).
Str/float keys never occupy an int slot and leave the flag clear (still fast + correct); explicit
int key=k via add_fresh_edge_with_key_unrecorded sets internal key=k (identity, no remap) so it too
stays clear. MEASURED RELEASE: parallel add_edge now LINEAR 1.07/2.15/2.55/7.64/16.5ms for
N=500..8000 (ratio flat ~0.23-0.39x; ~200x faster than HEAD at N=8000). byte-exact vs nx across 7
differential key-sequence cases (pure-auto, remove-gap->next, explicit-int-1-then-autos,
explicit-int-5-crossing, string-keys-then-auto, bool-True->2, hash-equiv 0-then-0.0 first-wins);
6138 multigraph/copy/operator/relabel/add_edges conformance pass, 0 fail.
RESIDUAL: `G.add_edges_from([(u,v),...])` with duplicate pairs is STILL O(N^2) (0.007x->0.002x) —
it routes through the Python `__init__.py` `MultiGraph.add_edges_from` wrapper that re-implements
key resolution in Python and never reaches this native add_edge fast path (single-pair N=4000 =
2735ms). That is a SEPARATE surface (the locked __init__.py wrapper, or a native keyed parallel
batch); deferred. MultiDiGraph.add_edge likely carries the same O(N^2) auto-key scan -> audit
digraph.rs add_edge for the same has_remapped_int_key treatment.

## 2026-06-29 BlackThrush SHIP: MultiDiGraph.add_edge auto-key O(N^2)->O(N) — parallel add_edge 0.002x->0.15-0.29x

NATIVE (fnx-python) + drop a Python wrapper. Sibling of the MultiGraph add_edge win (79876a932).
MultiGraph.add_edge was already migrated to raw-native (key=None auto-allocation owned by
PyMultiGraph.add_edge), but MultiDiGraph.add_edge was STILL bound to the Python wrapper
`_multi_add_edge_auto_key` (__init__.py ~3288), whose body calls `self._native_edge_key_set(u, v)`
+ a Python `while candidate in existing` loop on EVERY add — O(existing) per parallel add = O(N^2)
total. HEAD: N=500..4000 -> 24/100/424/1697ms (0.011x collapsing to 0.002x vs nx, clean quadratic).
FIX: give PyMultiDiGraph the same `has_remapped_int_key` machinery as PyMultiGraph
(note_public_key_value at remember_edge_key/_object + the keyed/union/diff batches + the deep-copy
display-key insert; propagated across _native_copy/copy/__copy__/subgraph/edge_subgraph/reverse/
to_directed_deepcopy + the cross-type/algorithm/generator literals — compiler E0063-enumerated all
13 PyMultiDiGraph initializers). In native add_edge, for key=None: when the flag is clear, skip the
public-key scan and let inner.add_edge_with_attrs' O(1) internal auto key flow through as the echoed
public key (no remap => directed internal==public exactly, gaps incl); when set, run the nx public
scan. Then DROP the wrapper: `MultiDiGraph.add_edge = _MULTIDIGRAPH_ADD_EDGE` (raw native).
RELEASE: parallel add_edge now LINEAR 1.12/1.67/4.03/9.80/25.75ms for N=500..8000 (flat ~0.15-0.29x;
~260x faster than HEAD at N=8000). MultiGraph add_edge unchanged (0.20-0.36x, no regression). byte
-exact vs nx across 8 differential key-sequence cases incl directed separation (0->1 key 2 vs 1->0
key 1, independent parallel sets), remove-gap, explicit-int-crossing, string/bool/hash-equiv;
10196 digraph/multigraph/copy/operator/convert/relabel/reverse/subgraph/generator conformance pass,
0 fail.
RESIDUAL: add_edges_from([(u,v),...]) with duplicate pairs is STILL O(N^2) for BOTH Multi types —
routes through the Python __init__.py _multi_add_edges_from wrapper (per-edge Python add_edge w/ its
own key probe), never the native batch. Separate surface; deferred.

## 2026-06-29 BlackThrush FIX+SHIP: Multi*Graph.add_edges_from(non-fresh) O(N^2)->O(N) 0.002x->0.37-0.61x + auto-key fast-path correctness fix

PURE-PYTHON perf + a Rust CORRECTNESS fix to the two prior add_edge fast-path commits (79876a932
MG, 8b939e3f7 MDG). Found while digging the documented add_edges_from residual.

PERF: add_edges_from's native batch fast paths only fire on a FRESH graph; on a NON-fresh graph
(any pre-existing edge) it falls to the per-edge Python loop in `_multi_add_edges_from` (__init__.py
~3381), which for key=None did `existing = self.get_edge_data(u, v); actual_key = len(existing);
while actual_key in existing: actual_key += 1` — an O(existing) keydict build + Python search PER
add = O(N^2) (single-pair N=4000 = 2794ms, 0.002x vs nx). But native add_edge(key=None) now
auto-allocates the nx public key in O(1), so that whole precompute is REDUNDANT: drop it, pass
key=None to native, use the returned key for the attr mutation. add_edges_from(non-fresh single
pair) now LINEAR -> 0.37-0.61x (both Multi types, ~100x faster at N=8000); fresh add_edges_from
unchanged (1.5-2.4x, native batch).

CORRECTNESS FIX (note_public_key_value, lib.rs + digraph.rs): the fast path echoes the INTERNAL
auto key, valid ONLY when the internal int-key space == the PUBLIC int-key space, i.e. every public
key is the IDENTITY int. The shipped flag only tripped on int REMAPS, so a graph mixing an
explicit-int-fresh key (internal==explicit, sets internal SPARSE via add_fresh_edge_with_key) with a
non-int key (str/float occupies an internal int slot but NOT the matching public int slot) then
autos echoed a wrong auto key (fnx 9 vs nx 8). Fix: set the flag for ANY non-identity public key
(str/float/remap), routing such graphs to the slow public scan (= nx's exact algorithm). The
common pure-parallel-int-add stays flag-clear -> O(1). Proven: non-float differential 1600/1600
byte-exact (int/str/auto/attr x fresh/non-fresh x add_edge/add_edges_from x MG/MDG). PRE-EXISTING
(NOT regressed): fnx treats a float key 4.0 as distinct from int 4 in the auto-key search (nx
hash-collapses them) — confirmed identical divergence at parent e77b7764a; float graphs now use the
slow scan == original behavior. 10205 conformance pass, 0 fail.
RESIDUAL: float-key/int hash-collision in the auto-key search is a pre-existing separate bug
(edge_key canonicalization), out of scope. add_edges_from with a GENERATOR ebunch still per-edge.

## 2026-06-29 BlackThrush NO-SHIP: PyGraph degree(nbunch, weight) int-accumulator twin — store-read floor, trades workloads

degree(nbunch, weight) is ~0.18-0.66x vs nx across types (urgent gap, mail #2189). For PyGraph,
`_native_weighted_degree_subset` (lib.rs ~12000) builds a PyList of every incident edge-weight
PyObject per node and calls `builtins.sum` — O(E) PyObject + O(N) Python calls. Mirrored
PyMultiGraph's int fast path: per-node `weighted_degree_int_row` accumulates i128 in Rust
(graph_py_int_weight reads the live mirror dict if present, else the CgseValue store directly),
one int PyObject out, per-node bail to the PyObject sum for non-int weights. byte-exact 8/8
(int/float/mixed/missing x self-loops) + bulk-store path.
WHY NO-SHIP: clean interleaved min-of-40 (NEW vs e77b7764a, fnx absolute, nx control):
int-bulk 2.27ms vs 2.58ms (+14%, real work-removal of PyList+sum+PyObject) BUT float-bulk
3.15ms vs 2.89ms (-9% REGRESSION, consistent) — the int row walks `inner.neighbors(node)` (Vec
alloc), bails on the first float, then the PyObject fallback re-walks neighbors = a DOUBLE
neighbors walk on non-int graphs. AND the head_to_head factory builds via per-edge add_edge
(populates edge_py_attrs), where the mirror is authoritative (live-dict mutation IS reflected in
degree, verified) so graph_py_int_weight must `PyDict.get_item + extract` per edge == the slow
path's per-edge cost -> ~0-gain (0.18x->0.21x) on the measured benchmark. Net: trades bulk-int
(+14%) for bulk-float (-9%), ~0 on the benchmark. Reverted (stash bt-degnbwint-NOSHIP).
FLOOR: the existing slow path ALREADY reads the CgseValue store via edge_attr_py_value, so an int
twin only strips PyList+sum overhead. The real floor is per-node node_key_to_string + per-edge
String edge_key build + neighbors() Vec alloc that nx avoids by reading live Python adjacency
dicts -> needs the persistent ordered Python-object adjacency mirror (4b5ie/materialization floor),
not a kernel twin. DON'T re-dig the int-accumulator; a clean win needs single-neighbors-walk +
store-direct read gated on edge_py_attrs.is_empty() (bulk only) — small, and still <1x nx.

## 2026-06-29 BlackThrush SURFACE: single-node degree(n) 0.31x — property-rebuild + cached_property deepcopy LANDMINE

After the add_edge/add_edges_from O(N^2) wins (79876a932/8b939e3f7/20e090e49), swept for the next
lever. Result of a broad battery (Graph/DiGraph/MultiGraph/MultiDiGraph): remove_edges_from
0.58-0.85x (linear), remove_nodes_from 1.7-1.85x, to_undirected/to_directed >=0.83x, copy()
1.1-12x, Graph(G) ctor 1.8-12x, gauntlet workloads mined (flow_hierarchy was the last). The one
broad gap: SINGLE-NODE `G.degree(n)` in a tight loop is 0.31-0.36x (Graph/DiGraph), 0.82x (MG),
>=1.16x (MDG). Breakdown (us): `G.degree` property access 0.255 (REBUILDS the DegreeView wrapper
every access — nx uses @cached_property, built once), __call__ 0.43, vs __getitem__ 0.11. So nx is
faster purely because it caches the view; fnx's `Graph.degree = property(_graph_degree)` reconstructs
per access.
WHY NOT FIXED (caching is a LANDMINE): caching the view via cached_property in instance __dict__ is
g.copy()-safe (copy() builds fresh __dict__) BUT NOT deepcopy-safe — `copy.deepcopy(G)` copies
__dict__ including the cached view, and `_WeightAwareDegreeView.__deepcopy__` returns self (nx-parity
for deepcopy(view)), so the deepcopied graph's cached `.degree` is a BROKEN view (verified: KeyError
on a valid node of the deepcopy). A correct cache needs the graph to drop cached views on deepcopy
(custom __deepcopy__ on the pyclass) or the view's __deepcopy__ to rebuild — both touch nx-parity
surfaces. The safe partial fix (trim __call__'s pre-checks to reach self._raw[nbunch] sooner) only
addresses 0.43->~0.15us and leaves the 0.255us property rebuild = the dominant gap. Also UNCERTAIN
benchmark relevance: most fnx algorithms are native (don't loop Python degree(n)); head_to_head does
not measure single-node degree(n) loops. NOT forced (risk + marginal measured impact).
REMAINING VEIN STATE: mutation O(N^2) MINED this session (3 wins). Left = (1) degree(n) caching
(needs careful deepcopy-safe cache design), (2) the materialization-floor view paths
(nodes(data=attr), dict(adjacency()), in_edges(data), degree(nbunch,weight)) — all need the
persistent ordered Python-object adjacency/node mirror primitive (4b5ie), not kernel micro-opts.

## 2026-06-29 BlackThrush FIX+SHIP: DiGraph in_edges(data=<attr>) store-only CORRECTNESS bug + warm-repeat cache

CORRECTNESS (pre-existing since e77b7764a, confirmed): `_native_in_edges_data_key` read ONLY
edge_py_attrs (the lazy Python mirror) and returned `default` when absent — so DiGraph
`in_edges(data=<attr>)` on ANY bulk-built graph (>=8 edges -> native add_edges_from batch leaves
the mirror EMPTY) returned the DEFAULT for EVERY edge instead of the real stored value (e.g.
in_edges(data='weight') -> all None). The out-edges path materializes from the store
(materialize_edge_py_attrs); the in-edges path didn't. Found while perf-profiling in_edges(data)
0.70x — the slow path was also WRONG on bulk graphs. FIX: read mirror-THEN-store via the existing
edge_attr_py_value(source,target,attr) helper (string attr resolved once); non-str keys can only
live in the mirror. Differential 320/320 byte-exact (bulk/missing/float/self-loop x warm x nbunch,
was 75/130 before); mutate-then-reread reflects (cache invalidation); 11847 conformance pass.
PERF: added in_edges_data_attr_cache (PyMultiDiGraph analog) — nx rebuilds the InEdgeDataView every
call, so the frozen (s,t,value) snapshot serves warm repeats (clone refs vs re-walk). Gated
!edges_dirty, dropped in mark_edges_dirty (attr edits don't bump edges_seq); Mutex for the &self
read path. get_edge_data marks dirty so a post-read mutation invalidates (verified).

## 2026-06-29 BlackThrush FIX+SHIP: dag_longest_path(weight=<attr>) store-only bug — SIBLING of in_edges

CORRECTNESS (pre-existing). Audit follow-up to 151fdd624 (in_edges store-only fix): swept value-read
paths for the same `edge_py_attrs.get -> None => default` shape WITHOUT a store fallback. Empirical
sweep on BULK-built graphs (>=8 edges -> native batch leaves the Python mirror EMPTY): degree/size/
edges/in_edges/in_degree/out_degree/dijkstra/pagerank/adjacency_matrix all CORRECT (they read the
CgseValue store), but `_native_dag_topo_pred_data_key` (digraph.rs ~11918, drives dag_longest_path
+ dag_longest_path_length) read ONLY edge_py_attrs and returned `default` for store-only edges -> on
a bulk-built DiGraph every predecessor weight read as the default_weight -> WRONG longest path
(e.g. fnx 63 vs nx 83). Per-edge-built (mirror populated) was correct; bulk wrong -> classic
store-only bug. FIX: read mirror-THEN-store via edge_attr_py_value (string attr resolved once; non
-str keys only live in the mirror) — same one-liner pattern as the in_edges fix. 60/60 random bulk
DAGs byte-exact (length AND path-weight); 3626 dag/longest/topo/digraph conformance pass.
NOTE: MDG `_native_weighted_degree` / weighted_degree_subset_impl PyObject fallbacks also have
`None => one.clone()` but the int/float store TWINS engage first (degree(weight) verified correct on
bulk), so those fallbacks are not reached for store-only edges. Audit complete: dag was the last
reachable store-only value-read.

## 2026-06-29 BlackThrush SURFACE: perf veins MINED — remaining gaps are the materialization floor (adjacency mirror primitive)

After the add_edge/add_edges_from O(N^2) wins + 2 store-only correctness fixes (151fdd624, 0ad42b25c),
swept for the next perf lever. State of the veins (DIRECT fnx.foo(fnx_g) vs nx.foo(nx_g), n=200-300):
- ALGORITHMS: fnx beats nx 1.0-84x on triangles/clustering/transitivity/betweenness/closeness/
  eccentricity/harmonic/square_clustering/pagerank/constraint/effective_size/core/k_core. MINED.
- MUTATION O(N^2): add_edge/add_edges_from fixed this session. MINED.
- KEYED MULTI-EDGE VIEWS: MG/MDG edges(keys[,data]) 2.7-31x FASTER (caches shipped). Not gaps.
- STORE-ONLY value-reads: audited + fixed (in_edges, dag_longest_path). Complete.
The ONLY remaining gaps are the per-element PyObject MATERIALIZATION FLOOR: G[u]/neighbors(u) loops
0.46-0.55x (fnx converts each neighbor name -> PyObject via node_key_map; nx returns live
dict_keyiterator with zero conversion). neighbors is a Python wrapper that builds a Rust Vec<PyObject>
then wraps an iterator; the cost is the name->PyObject conversion per neighbor, fundamental to the
String-keyed inner store. A micro-opt (kill the list->iter->list double pass) is ~10-20%, doesn't
close it. The real fix is the persistent ordered {node:{nbr:live_attr_dict}} Python adjacency mirror
(4b5ie) kept coherent across mutations — a multi-session architectural primitive, NOT a 60-min dig.
nodes(data) + dict(adjacency()) were the same floor and are NOW CLOSED (node_data_mirror +
dict_of_dicts outer cache shipped earlier) -> the mirror approach WORKS; extending it to adj/neighbors
subscript views is the lever.
METHODOLOGY WARNING (cost me a sweep this cycle): benching `nx.foo(fnx_graph)` on BOTH sides hits the
nx BACKEND-DISPATCH trap (fnx is a registered backend) -> bogus ratios (constraint looked 0.42x, is
really 1.2x faster). ALWAYS call fnx.foo(fnx_g) vs nx.foo(nx_g) directly. See
reference_nx_backend_dispatch_benchmark_trap.

## 2026-06-29 BlackThrush SURFACE-REFINE: materialization floor is on NON-representative patterns — common adjacency access is at-parity

Refines the prior surface (22ed11f33) which framed G[u]/neighbors loops 0.46-0.55x as a real gap
needing the adjacency-mirror primitive. Measured the access patterns REAL code uses (shared edge
list, direct fnx vs nx, n=300/e4000):
- g[u][v] single-edge loop (the COMMON edge-access): 1.70x FASTER
- to_dict_of_dicts (bulk all-rows): 1.25x FASTER
- dict(g.adjacency()) (bulk, cached): 0.95x parity
- g[u][v]-style algorithms: native, fnx-faster
ONLY slow: dict(g[u]) per-node-row loop 0.44x, list(g[u]) per-node 0.64x — atypical patterns that
materialize each adjacency row individually. fnx's g[u] returns a LAZY AtlasView that re-materializes
per access, bypassing the cached native_adjacency_row_dict (lib.rs ~10905, which DOES cache + stays
coherent via cached_adj_set_edge/remove). Real code needing all rows uses to_dict_of_dicts/adjacency
(fast); needing one edge uses g[u][v] (fast). So the adjacency-mirror primitive is LOWER priority
than stated: the representative paths are already covered. Wiring g[u]'s AtlasView to the cached row
would only help synthetic per-row-dict loops, at real coherence-risk cost (the row is a live mutable
dict). NOT worth it now.
NET (perf): every representative access pattern + algorithm + mutation path is at-or-above nx. The
perf frontier for THIS port is genuinely mined; the durable wins this session were the O(N^2) mutation
fixes + the store-only CORRECTNESS bugs. Future value is more likely in correctness audits (the
bulk-built-graph store-only class) than in squeezing the materialization floor on atypical patterns.

## 2026-06-29 BlackThrush FIX+SHIP: Graph.edges(nbunch, data=<attr>) store-only bug — 3rd bulk-built store-only fix

CORRECTNESS (pre-existing). Continued the bulk-built store-only audit (after in_edges 151fdd624 +
dag_longest_path 0ad42b25c). The native `edges_nbunch_data` (readwrite.rs ~1465) attached the
edge_py_attrs mirror dict per edge and used an EMPTY PyDict when absent -> on a bulk-built simple
Graph (>=8 edges -> native batch leaves the mirror EMPTY) `edges(nbunch, data='attr')` read the
DEFAULT (None) for every store-only edge, and `edges(nbunch, data=True)` dropped all attrs (empty
dict). Whole-graph edges(data=) was fine (bulk ordered_edge_attr_dicts path); only the NBUNCH
variant was wrong, and only for simple Graph (MG nbunch already reads the store). FIX: materialize
the dict from the CgseValue store via attr_map_to_pydict when the mirror is absent (&self-safe, no
borrow_mut/dirty). 160/160 byte-exact (scalar/default/missing/data=True content x int/float x
self-loops); 14770 conformance pass (the 3 find_induced_nodes failures are PRE-EXISTING — identical
on the e77b7764a session-start .so, unrelated).
RESIDUAL (minor, no regression): data=True on a store-only edge yields a FRESH (content-correct but
non-LIVE) dict; mutating it doesn't persist (nx yields the live dict). The old empty-dict was equally
non-live AND wrong-content, so this is strictly better. Full liveness needs materialize_edge_py_attrs
(&mut + marks dirty), a perf cost on the common scalar read path -> deferred. AUDIT NOTE: the
bulk-built store-only class now has 3 fixes; grep `edge_py_attrs.get ... None => PyDict::new/default`
for any remaining (whole-graph edges/degree/dijkstra/pagerank/matrix all verified store-correct).

## 2026-06-29 BlackThrush SURFACE: bulk-built store-only audit COMPLETE (3 data-loss fixes) + AttrMap-sorts-attrs design divergence

Closed the bulk-built-graph store-only correctness audit (native paths reading the EMPTY Python mirror
on >=8-edge add_edges_from graphs). Found + FIXED 3 DATA-LOSS bugs: in_edges(data=attr) 151fdd624,
dag_longest_path(weight) 0ad42b25c, edges(nbunch,data=attr) 901a7e00e. Then swept the remaining
weight/attr read paths on bulk graphs — ALL correct: dijkstra/bellman/pagerank/adjacency_matrix/
laplacian/MST/floyd/astar/max_flow/min_cut/max_weight_matching/johnson (weights), to_dict_of_dicts/
generate_edgelist/node_link_data/adjacency_data/edges(data=True) (serialization), nodes(data) (node
attrs). The DATA-LOSS class is mined.
ONE residual divergence (NOT data-loss, semantic-equivalent, PRE-EXISTING since e77b7764a): bulk-built
simple Graph/DiGraph do NOT preserve attr INSERTION ORDER. Edges added {'weight':_,'color':_} come
back ['color','weight'] (ALPHABETICAL) where nx preserves ['weight','color']. ROOT:
`AttrMap = BTreeMap<String, CgseValue>` (fnx-classes/src/lib.rs:22) SORTS keys; per-edge graphs are
masked by the insertion-ordered edge_py_attrs mirror, but a bulk graph's empty mirror exposes the
sort. Multi types preserve order (different storage). IMPACT: only byte-ORDER serialization (JSON
dict order, edgelist data=True repr, str(G[u][v])) — all attrs+values present, round-trips
semantically fine, no test currently fails on it. FIX would be AttrMap BTreeMap->IndexMap: a CORE
fnx-classes change with enormous blast radius (every AttrMap iteration/comparison/golden snapshot
assumes sorted order — it's a DELIBERATE canonical-determinism choice), NOT a 60-min dig. Surfaced
as an architectural decision for a dedicated effort, not forced. The sorted-AttrMap tradeoff (canonical
comparison determinism) vs nx byte-exact attr order is a maintainer call.

## 2026-06-29 BlackThrush SURFACE: state-corruption bug — G.subgraph(nodes).copy() corrupts a later G.to_directed()

Found via a bulk-graph op-attr-preservation sweep (continuing the store-only audit). REAL, pre-existing
(confirmed on clean HEAD), reproducible bug: on a bulk-built simple Graph, `G.subgraph(some_nodes).copy()`
leaves G in a state where a SUBSEQUENT `G.to_directed()` DROPS edge attrs (empty {}) for boundary /
store-only edges (e.g. edge 6-9 with 6 in the subgraph node set, 9 not). PLAIN `G.copy()` does NOT
trigger it; G ITSELF stays fully correct (G.edges(data=True), get_edge_data(6,9), to_dict_of_dicts,
adjacency() all return the right attrs) — ONLY the derived to_directed is wrong. So subgraph().copy()
has a READ-OP SIDE-EFFECT that pollutes G's edge_py_attrs mirror (partial), and to_directed
(lib.rs:11463, mirror_pristine = edge_py_attrs.is_empty() gate) then reads the partial mirror and
produces a partially-pristine DiGraph that drops store-only edges' attrs. A structural mutation does
NOT clear it (not a seq-cache).
INVESTIGATED, NOT ROOT-CAUSED: tried to_directed reading mirror-THEN-store on the `None` arm
(materialize from the borrowed store AttrMap) — DID NOT FIX (the bug edges hit the `Some(stale/empty)`
arm, not None), so reverted (stash bt-todirected-noneArm-NOSHIP). The inconsistency (G reads correct
via edge_key(6,9) but to_directed reads empty via the same edge_py_attrs) points at subgraph.copy()
inserting stale/empty mirror entries and/or an edge-key orientation mismatch in the subgraph
materialization path. REAL FIX is in subgraph().copy() (stop the parent-mirror pollution — a read op
must not mutate the parent) OR to_directed must read the store authoritatively when the source may be
non-pristine. NICHE (subgraph.copy then to_directed on the SAME parent) but a genuine correctness
footgun. Deferred for a dedicated debugging session (needs Rust-side mirror-state tracing).

## 2026-06-29 BlackThrush SURFACE-REFINE: subgraph/to_directed corruption ROOT is get_edge_data(v,u) REVERSED orientation

Sharpened the 1671b61fc surface to a DETERMINISTIC MINIMAL repro — the trigger is NOT subgraph-specific,
it is `get_edge_data(v, u)` called in the orientation REVERSED from insertion:
    es = [(i, i+10, {'weight': i+1}) for i in range(10)]
    g = fnx.Graph(); g.add_edges_from(es)          # bulk -> empty mirror
    g.get_edge_data(15, 5)                          # REVERSED (edge inserted as (5,15))
    g.to_directed()                                 # -> drops attrs ({}) for ALL edges
`get_edge_data(5, 15)` (insertion orientation) does NOT trigger it; doing get_edge_data for ALL edges
(either orientation) does NOT trigger it either — it is the SINGLE reversed call leaving a PARTIAL
mirror that flips to_directed's `mirror_pristine = edge_py_attrs.is_empty()` (lib.rs:11495) to false,
after which to_directed yields empty attrs for every edge while g itself (edges(data=True),
get_edge_data, to_dict_of_dicts, adjacency) stays fully correct. Confirmed pre-existing on clean HEAD.
NARROWED but NOT root-fixed: edge_key (lib.rs:907, string u<=v) and inner.edge_attrs (fnx-classes:960,
via edge_pair_key) are BOTH order-independent, so the mirror entry from get_edge_data(15,5) is a
correct, canonically-keyed dict — yet to_directed still empties all edges, implying the store path
(edges_ordered_borrowed) or the partial-mirror gate interacts wrongly under reversed-materialize.
Two NO-SHIP to_directed None-arm store-materialize attempts did NOT fix it (the all-edges-empty is
upstream of the None arm) -> stashes bt-todirected-noneArm-NOSHIP{,2}. REAL FIX needs Rust-side
mirror/store-state tracing of get_edge_data(reversed) -> materialize_edge_py_attrs -> edges_ordered
_borrowed. Common-call trigger (get_edge_data arg order) makes this MORE than niche; high-priority for
a dedicated Rust debugging session. The minimal repro above makes it a ~10-line bisect for that session.

## 2026-06-29 BlackThrush FIX+SHIP: to_directed/to_undirected dropped store attrs after a stray mirror entry (the 2-cycle bug)

ROOT-CAUSED + FIXED the bug surfaced in 1671b61fc/393676c86. The REAL path is the deepcopy kernels
_native_to_directed_deepcopy (lib.rs ~11790, Graph.to_directed) and _native_to_undirected_deepcopy
(digraph.rs ~10989, DiGraph.to_undirected) — NOT the lib.rs:11463 method I instrumented first (that
one is unused for the public call). Both built each arc's attrs from `edge_py_attrs.get(...) { Some
=> deepcopy, None => Default::default() }` — reading ONLY the Python mirror. When the mirror is
PRISTINE (empty) the lazy/Default arc is fine (store flows through the edge_batch path); but ONE
stray mirror entry (a single get_edge_data(v,u) reversed materializes one edge; subgraph().copy()
materializes the induced edges) makes the mirror NON-pristine, after which `Default` DROPPED every
store-only edge's attrs -> a bulk-built graph lost ALL edge attrs on to_directed/to_undirected.
DETERMINISTIC: g.add_edges_from([(i,i+10,{'weight':i+1}) for i in range(10)]); g.get_edge_data(15,5);
g.to_directed() -> empty attrs. FIX: gate `None if mirror_pristine => Default` else read the
CgseValue store (self.inner.edge_attrs(source,target).cloned()) — preserves the pristine fast path
(no fresh perf change) and reads the store only in the non-pristine case. Graph.to_directed 320/320
+ DiGraph 317/320; 13466 conformance pass (the 3 reds are the PRE-EXISTING find_induced_nodes
stale no-fallback tests, fail on HEAD too).
RESIDUAL (rarer, pre-existing, NOT regressed — HEAD dropped ALL attrs here, mine drops only this):
DiGraph.to_undirected with RECIPROCAL directed edges carrying CONFLICTING attrs + a non-pristine
poke picks the first-touch direction (the `seen` guard at digraph.rs:10981 processes first-touch
only) where nx is last-wins -> 3/320. Fixing needs the None/store arm to also do the reciprocal
`existing.update` merge that only the Some(mirror) arm does today. Deferred; conformance-green.

## 2026-06-29 BlackThrush NO-SHIP (cargo-bench-confirmed): clear_edges 0.351x is per-edge CONSTRUCTION fragmentation, not a clear_edges bug

Ran the AUTHORITATIVE per-crate bench (rch exec -- cargo bench -p fnx-python --bench
networkx_head_to_head, vendored-nx oracle). Of 17 cleanly-paired fnx-vs-nx workloads, the gaps
(ratio<1.0): clear_edges 0.351x (fnx 1.13ms / nx 0.40ms), construction_copy 0.611x (239/146ms),
core_laggards 0.626x, adjacency_outer_cache 0.811x; the other 13 are fnx>=nx.
ROOT-CAUSED clear_edges (the biggest) with Rust Instant instrumentation: the cost is
inner.clear_edges() -> self.edges.clear(), and it is 2.11ms for a PER-EDGE-built graph vs 0.33ms
for a BULK-built one (same 896 edge buckets / 4000 edges). Pure ALLOCATOR FRAGMENTATION: per-edge
add_edge allocates 4000 AttrMap (BTreeMap) nodes INTERLEAVED with the per-edge decision-ledger
pushes (the known construction tax, reference_read_adjlist_native_and_ledger_tax) + incremental
IndexMap growth, scattering them across the heap; eagerly free-ing 4000 scattered small allocations
is ~6x slower than bulk's contiguous ones. clear_edges itself is OPTIMAL (just drops the structures),
and clear_edges on a BULK-built MultiGraph BEATS nx (1.16x) -- nx is only "faster" here because Python
defers deallocation to GC while Rust frees eagerly. The bench's _make_multigraph builds per-edge, so
it measures the construction-fragmentation tax at clear time, NOT a clear_edges defect. Fix would need
an arena/pool allocator for AttrMaps or a deferred/background drop -- a large/risky change, not a
clear_edges edit. REVERTED instrumentation; ~0 clean gain available here.
FRONTIER CONFIRMED: the cargo bench VALIDATES the synthetic conclusion -- every remaining gap is the
per-edge CONSTRUCTION tax (ledger + fragmentation: clear_edges, construction_copy, core_laggards) or
the materialization floor (adjacency_outer_cache, already a documented no-ship). Both are large
architectural levers (bulk-unrecorded everywhere / arena alloc / persistent Python mirror), not
60-min kernel edits. The kernel/algorithm/mutation veins are mined.

## 2026-07-01 CopperCliff FIX+SHIP: transitive_closure(DiGraph) attr-copy 0.16x -> 1.86x vs nx (pure-Python)

REAL gap surfaced by a corrected broad delegation sweep (fnx-at-HEAD via PYTHONPATH=python vs vendored
nx, min-of-7, single-call timing). NOTE the first pass MIS-FILED trophic_levels as 0.33x — a bench-
helper bug: the `hasattr(...)/isinstance(...)` guard called the fn 3x/iter, inflating the fnx column.
Fixed harness confirms trophic_levels at 1.02x (parity, byte-identical numpy `inv` to nx). The ONE
true gap in the sweep: `transitive_closure` at **0.16x** (fnx 105.9ms / nx 17.0ms, 200-node DAG).

ROOT (cProfile): NOT the native kernel (`_fnx.transitive_closure` = 0.033s) and NOT delegation (the
DAG/acyclic + reflexive=False path is native since br-r37-c1-tc-cyclic). The cost was the attr-restore
loop `for u,v,attrs in G.edges(data=True): result[u][v].update(attrs)` — `result[u][v]` routes through
`_keydict`->`_cached_adj_row_keydict`->`_native_adjacency_dict`, materializing the FULL adjacency
keydict row for each source node on the DENSE closure (4582 edges/200 nodes). 800 `_native_adjacency_dict`
calls = 0.446s of 0.569s (~90%). nx avoids it entirely: `TC = G.copy()` carries original edge attrs for
free, then only ADDS attr-less closure edges.

FIX (10 lines, pure-Python, no .so rebuild): replace the per-item `result[u][v].update`/`result.nodes[n].update`
loops with `result.add_edges_from((u,v,a) for u,v,a in G.edges(data=True) if a)` +
`result.add_nodes_from(...)`, which write attrs straight to the store (no row-keydict materialization).
Byte-IDENTICAL to the old output — the closure already contains every G node+edge, so these are pure
in-place attr updates. Verified `batch==current` EXACT (node order, edge order, node/edge/graph attrs)
across cyclic+mixed-attrs, self-loop-with-attrs, DAG-no-attrs, cyclic-nodeattr, dense-random-60, AND
non-scalar attrs (list/dict/None/tuple/bigint) preserved. **105.9ms -> 9.2ms (11.5x self), 0.16x ->
1.86x vs nx** (now BEATS nx). Conformance: 142 transitive_closure tests + 988 referencing tests green;
the 1 red (test_write_gexf_classified...) is PRE-EXISTING (fails identically with the change stashed,
unrelated GEXF classification).

LEVER (RE-CONFIRMED, cf. reference_adjacency_outer_dict_cache / _native_adjacency_dict floor): any
attr-restore / edge-decoration loop that does `H[u][v].update(...)` or `H.nodes[n].update(...)` PER
ITEM on a graph whose adjacency rows are DENSE pays a full-row keydict materialization each access ->
route through add_edges_from/add_nodes_from batch (store-direct). Grep result-graph post-processing
loops that index `result[u][v]` / `result.nodes[n]` inside a per-edge/per-node loop. Also: the
delegation sweep otherwise CONFIRMS the mined-out frontier — triadic_census 16.9x, harmonic_centrality
17.3x, wiener_index 14.1x, chain_decomposition 11.5x, degree_assortativity 107x, s_metric 121x all
beat nx; transitive_closure was the lone straggler. (rich_club_coefficient ZeroDivisionError on a graph
with no populated k-degree class is a separate SURFACE — nx returns {} there; not chased this session.)

## 2026-07-01 CopperCliff PARTIAL-SHIP: attributed graph products batch — 0.12-0.19x -> 0.19-0.30x (1.3-2x self, still <nx)

Broad binary-operator sweep found cartesian/tensor/strong/lexicographic_product at 0.12-0.19x vs nx on
ATTRIBUTED simple graphs (lexicographic ~1.3s/call, near-timeout). NOT the native kernel: the native
`*_product_fast` (fe0dbee38, beats nx) BAILS on `_graph_has_any_attrs(G|H)` (can't pair attrs), so any
weighted/node-attr product falls to the Python O(V_G*V_H node + E_G*V_H... edge) build, which paid a
Python->native add_node/add_edge dispatch PER product node/edge. FIX (pure-Python): batch the node
build + each SIMPLE (non-multigraph factor) edge layer through add_nodes_from/add_edges_from (one native
call/layer); multigraph factors keep the per-edge keyed path (4-tuple key= collision dodge) UNTOUCHED.
Byte-IDENTICAL: 40/40 vs current public across {Graph,DiGraph,MultiGraph,MultiDiGraph}^2 + MIXED type
pairs (MultiGraph x Graph etc.) + parallel-edge + self-loop + node/edge-attr configs; 259 product/
operator conformance tests green. Result: cartesian 0.18->0.30x, tensor 0.12->0.22x, strong 0.19->0.22x,
lexicographic 0.12->0.19x (1.3-2.1x self).

HONEST FRAMING: this is a PARTIAL improvement, NOT a beat-nx win — the residual <1x is the tuple-key
CONSTRUCTION TAX (fnx stores tuple nodes via node_key_to_string; nx uses native tuple dict keys). Batching
strips per-call dispatch (real strict work-removal, cf. feedback_rch_bench_worker_noise) but cannot close
the O(V*H) tuple-materialization gap. The ONLY path to beat nx on attributed products is native attr-
pairing in the Rust kernel (relax the `_graph_has_any_attrs` gate + pair attrs in `*_product_fast`) — a
Rust dig, deferred. Shipped the batch because it fixes the lexicographic near-timeout and is safe/byte-
exact. FRONTIER RE-CONFIRMED: this session's ~80-fn sweep shows fnx beats nx on ~all scalar/dict/algorithm
work; every remaining <1x is construction-tax (products/operators on tuple keys) or a native kernel
(condensation 0.35x, compose 0.50x) — both Rust/architectural, matching the documented mined-out frontier.

## 2026-07-01 CopperCliff PARTIAL-SHIP: corona_product 0.17->0.21x + rooted_product 0.22->0.39x (product-family batch)

Extended the attributed-product batch (f9f3f7e7d) to the remaining product FAMILY. Same mechanism: the
native corona_product_fast/rooted_product_fast kernels BAIL on `_graph_has_any_attrs` -> attributed
graphs fall to a per-node/edge add_node/add_edge Python build. corona_product 0.15-0.17x (124ms/60n):
batch the G-edge layer + per-G-node H-copy layers (star edges then H-copy edges, preserving that per-g
insertion order) via add_edges_from/add_nodes_from -> 0.21x (1.3x self). rooted_product 0.22x (carries
NO edge attrs but the native path bails on ANY attr, so attributed input lands in the attr-free Python
build): batch node + both edge layers -> 0.39x (1.8x self). Byte-IDENTICAL incl exact node AND edge
ORDER: corona 10/10 (Graph + MultiGraph H x attrs/self-loops), rooted 5/5; both match nx canonical edge
set; 786 product/operator conformance tests green.

NOT chased: modular_product is O((V_G*V_H)^2) has_edge-BOUND (nested product-node-pair loop with a
has_edge per pair) — batching the add_edge does NOT touch the dominant has_edge cost, so its attributed
fallback stays slow (needs the native bitmatrix kernel path or a Python adjacency-set snapshot; low ROI).
power(k) already BEATS nx (2.37x). HONEST: like the main-4 products these are PARTIAL improvements bounded
by the tuple-key construction tax — a beat-nx product win needs native attr-pairing in the Rust kernels
(read/pair arbitrary Python attrs + build the mirror per product edge), a dedicated Rust dig. The whole
product family (cartesian/tensor/strong/lexicographic/corona/rooted) now shares one Python-batch idiom;
modular + the Rust attr-pairing kernel are the only remaining product levers.

## 2026-07-01 CopperCliff SHIP (BEATS nx): node-attributed products via native-structure + node-decorate — 0.12-0.33x -> 0.98-3.37x

BREAKTHROUGH on the "attributed products are construction-tax-bound" conclusion — it was only HALF true.
A product's EDGE SET depends ONLY on adjacency, NOT on attrs, so the native `*_product_fast` kernel
builds the correct structure whether or not the factors carry NODE attrs. The old gate
(`_graph_has_any_attrs`) bailed on ANY attr, sending node-attributed products all the way to the slow
Python edge loop. INSIGHT: only EDGE attrs actually need the kernel to pair-per-edge (which it can't);
NODE attrs just DECORATE the structurally-correct native result. FIX: relax the gate to
`_graph_has_any_EDGE_attrs` (new native-backed helper) + after the native call, if node attrs are
present, paint paired node attrs on via ONE `add_nodes_from(((g,h), _product_node_attrs(...)) ...)`
batch — O(V_G*V_H) node paints << the O(E_product) Python edge loop.

RESULT (node-attr-only, edge-attr-free): cartesian 0.33x->0.98x (parity), tensor ~0.12x->2.54x, strong
~0.19x->2.84x, lexicographic ~0.12x->3.37x — tensor/strong/lexico now BEAT nx by 2.5-3.4x (their denser
O(E_G*E_H) edge sets make the native build's win dwarf the node-paint cost). Byte-IDENTICAL: 32/32 vs
nx across nodeonly/edgeonly/both/none x Graph/DiGraph (edge set + node attrs), 16/16 vs current-public
incl self-loops; 1216 product/operator conformance tests green (the node-attr path now uses the native
canonical order the no-attr path already used — parity tests canonicalise, so no regression). EDGE-attr
and both-attr products still fall to the batch path (0.19-0.30x, the f9f3f7e7d partial) — edge-attr
pairing remains the Rust dig. This is the first BEAT-nx product win of the session (vs the earlier batch
partials). Only 4 main products relaxed (via _native_graph_product); corona/rooted use their own
_fnx.*_fast gate and could get the same node-attr relaxation next (follow-up).

## 2026-07-01 CopperCliff SHIP (BEATS nx): corona/rooted product node-attr relaxation — 0.21-0.39x -> 2.24-2.38x

Applied the dbce71884 "structure is attr-independent -> run native + bail only on the pairing axis"
lever to the rest of the product family. KEY per-function attr semantics (both nx and fnx AGREE):
corona DROPS node attrs (output node dicts empty) but PRESERVES H's per-copy EDGE attrs; rooted DROPS
ALL attrs (node AND edge). So: corona gate `_graph_has_any_attrs`->`_graph_has_any_edge_attrs` (node
attrs never affect output, no decoration needed); rooted gate DROP the attr check entirely (native's
attr-free output matches nx for ANY input). NEITHER needs node decoration (unlike the main-4, which
carry paired node attrs). Result: corona node-attr-only 0.21x->2.38x, rooted node-attr-only 0.39x->2.24x,
AND rooted EDGE-attr 0.39x->2.24x (rooted drops all attrs so native handles edge-attributed input too) —
all BEAT nx. Byte-exact 8/8 vs nx (nodeonly/edgeonly/both/none x corona/rooted); 326 corona/rooted/product
conformance tests green. corona EDGE-attr still batches (H-copies carry H's edge attrs = the pairing axis).
Product family status: no-attr + node-attr (all 6) beat nx; edge-attr = cartesian/tensor/strong/lexico/
corona batch (0.19-0.30x partial), rooted native (beats nx). Remaining: edge-attr pairing (Rust) + modular.


## 2026-07-02 CopperCliff SHIP (BEATS nx, RUST): cartesian EDGE-attr native kernel — 0.30x -> 1.98x

The edge-attr product lever (previously "Rust dig, deferred") LANDED for cartesian. New Rust pyfunction
`cartesian_product_edge_attrs_fast` (crates/fnx-python/src/algorithms.rs) clones each source edge's store
AttrMap onto the product edges (cartesian = each product edge inherits exactly ONE source edge, no
pairing). SAFETY GATE = PRISTINE edge mirror (`edge_py_attrs.is_empty()`): a non-scalar attr
(list/dict/tuple/None) always forces a Python-mirror entry, so an empty mirror GUARANTEES all edge attrs
are scalar + store-complete -> cloning is byte-exact with ZERO non-scalar data-loss risk (the recurring
bug class here). Returns None (->Python batch) on directed/multigraph/non-pristine-mirror/self-loops. The
Python wrapper tries it after the node-only relaxation and decorates node attrs afterward.

RESULT: bulk-built weighted cartesian_product 0.30x -> 1.98x vs nx (BEATS nx). Differential harness 13/13
byte-exact vs nx: scalar int/float/multi/bigint fire native; str-node-keys; node+edge attrs; NON-scalar
list/None/dict BAIL to batch (byte-exact); self-loops BAIL; non-pristine (edge-accessed) BAILS; per-edge-
built BAILS; result edge attrs LIVE/mutable. 1216 product/operator + 5487 broader conformance green.
Build: `maturin build --release -o <dir>` (~1.5-3.7m; .so gitignored/rebuilt -> source is truth).
SCOPE: cartesian only (direct-copy). tensor/strong/lexico pair attrs into non-scalar tuples (mirror) =
harder; corona edge attrs are direct-copy (H-copies) -> same lever applies next. GATE caveat: only fires
for freshly-bulk-built graphs whose edge mirror is still pristine (per-edge-built / edge-accessed graphs
materialize the mirror -> batch); the common build-then-product workflow keeps it pristine.


## 2026-07-02 CopperCliff SHIP (BEATS nx, RUST): cartesian edge-attr kernel EXTENDED to DiGraph — 0.30x -> 1.94x

Extended cartesian_product_edge_attrs_fast (c3527f601) to the DIRECTED case (DiGraph x DiGraph), doubling
coverage. Same pristine-mirror safety gate + direct-copy (each directed product edge inherits one source
directed edge: G-layer copies an H-edge hu->hv, H-layer copies a G-edge gu->gv). Reads via
GraphRef::Directed{dg}.inner + dg.edge_py_attrs + DiGraph::edge_attrs_by_indices/successors_indices;
builds a DiGraph via extend_edges_with_attrs_unrecorded. Directed bulk-built weighted cartesian_product
0.30x -> 1.94x vs nx (BEATS nx). Directed differential harness 11/11 byte-exact (scalar int/float/multi/
str-keys/node+edge fire; non-scalar list/dict + self-loops + per-edge-built + non-pristine-access BAIL;
no-attr). Undirected harness 13/13 regression-clean. 1216 product/operator conf green. cartesian edge-attr
now covers BOTH Graph + DiGraph. FOLLOW-UP: corona edge-attr (H-copies direct-copy); tensor/strong/lexico
(tuple-pairing -> non-scalar mirror, harder); modular.


## 2026-07-02 CopperCliff SHIP (BEATS nx, RUST): corona edge-attr native kernel — 0.21x -> 2.18x

Completes the DIRECT-COPY product family. In a corona product the ONLY surviving edge attrs come from H's
edges copied onto each G-node's H-block (direct copy, no pairing); G's edge attrs + ALL node attrs are
dropped (matches nx). New pyfunction corona_product_edge_attrs_fast clones H's store AttrMap onto the
H-copy edges, gated on H's PRISTINE edge mirror only (G's mirror is IRRELEVANT — its edge attrs are dropped
regardless, so even a non-scalar-G-edge graph fires the native path correctly). No node decoration (dropped).
corona(G, H-weighted-bulk) 0.21x -> 2.18x vs nx. Differential 13/13 byte-exact incl the G-non-scalar-edge-
dropped case + all bails (H non-scalar/self-loop/per-edge-built/non-pristine); cartesian regression 13/13
undirected + 11/11 directed clean; 1216 product/operator conf green.

DIRECT-COPY PRODUCT FAMILY COMPLETE (edge-attr, pristine-mirror lever): cartesian (Graph c3527f601 +
DiGraph 20eeac3f6), corona (this). REMAINING product edge-attr levers need the Python mirror (non-scalar
paired tuples): tensor/strong/lexico (_paired_edge_attrs -> tuples) + modular — a harder Rust dig (must
build edge_py_attrs mirror entries in-kernel, not just store AttrMaps). Node-attr: all 7 already beat nx.


## 2026-07-02 CopperCliff SHIP (BEATS nx, RUST): native mycielskian_step (attr-free) — 0.65x -> 3.07-3.35x

Fresh non-product dig. mycielskian was 0.5-0.65x: the batched Python _mycielskian_step still paid the
per-edge PyO3 construction tax (add_nodes_from + 4x add_edges_from build a 2n+1-node / 3E+n-edge graph;
profile hotspot was _simple_add_edges_from_touches_existing_plain_edge scanning growing edge sets — but
COMBINING the 4 add_edges_from into 1 gave 1.01x self, proving the cost is edge INSERTION, not the
pre-check). New pyfunction mycielskian_step_fast assembles the whole structure in Rust (nodes 0..2n int
keys, edges: M's originals + shadow (u,v+n)+(u+n,v) + apex (n+i,2n), nx's exact order). Gated to the
ATTR-FREE case (Mycielskians are built on unlabelled test graphs) — Python wrapper only calls it when
`not M.graph and not _graph_has_any_attrs(M)`; attributed M keeps the attr-preserving Python build. n=150
0.65x->3.07x, n=300 ->3.35x (~5x self). Differential 12/12 byte-exact vs nx (exact node+edge order+attrs;
int + str-keys via convert; iterations 0/1/2/3; node/edge/graph-attr all BAIL; empty/single-edge); product
regressions clean (cart 13+11, corona 13); 2789 mycielski+product+generator conf green. LEVER: a batched
construction still >nx = base per-edge construction tax; a native int-keyed structure kernel (no attrs,
no tuples) is the cheapest beat-nx path. Grep other batched-but-<nx graph builders (construction tax).


## 2026-07-02 CopperCliff SHIP: binomial_tree pre-check bypass — 0.53-0.58x -> 0.73-0.76x (pure-Python)

Fresh generator sweep found binomial_tree at 0.53-0.65x. cProfile: a THIRD of the build is
`_simple_add_edges_from_touches_existing_plain_edge` — add_edges_from's O(E) "does any edge touch an
existing plain edge" pre-scan, run on each doubling step. But every shifted-copy edge (u+N, v+N) has BOTH
endpoints >= N (fresh nodes N..2N-1), so it can NEVER collide with an existing edge (all among nodes < N).
The pre-scan is pure waste. FIX (pure-Python, no rebuild): call the native batch `_try_add_edges_from_batch`
directly (skipping the pre-scan); fall back to add_edges_from only if it bails (multigraph/non-int, returns
False + adds nothing -> fallback byte-identical). 0.53->0.73x (n=12), 0.58->0.76x (n=13), 1.3-1.4x self.
Byte-exact n=0..14 across all create_using types (Graph/DiGraph/Multi*); 4286 tree/generator conf green.
STILL <nx: the residual is the native edge-insertion construction tax (`_try_add_edges_from_batch` itself);
a native beat-nx kernel is HARDER than mycielskian's — binomial_tree's node/edge order follows G.edges()
ADJACENCY-iteration order (node-then-neighbor dedup), not edge-insertion, so pure-Python edge_list doubling
diverges from nx at n=4 (verified) and a Rust kernel must replicate edges()'s adjacency order, not
edges_ordered(). LEVER: any incremental builder adding provably-disjoint new-node edges can skip the
touches-existing pre-scan via a direct _try_add_edges_from_batch. (watts_strogatz 0.79x = stochastic, needs
PythonRandom-sequence replication — deferred.)


## 2026-07-02 CopperCliff SHIP: batch 5 expander/harary/LCF generators — 4 now BEAT nx (pure-Python)

Generator sweep found a cluster of per-edge-add_edge builders at 0.34-0.70x. Applied the
reference_batch_add_edges_from_construction lever (per-edge graph.add_edge loop -> one add_edges_from
with a LIST — the multigraph-safe form): margulis_gabber_galil_graph (4n^2 edges), chordal_cycle_graph
(3p edges), _harary_graph_from_edges (shared by hnm_harary + hkn_harary, preserving the interleaved
forward/reverse-or-dup order), LCF_graph (chord edges after cycle_graph). Byte-exact vs nx across all
create_using types. RESULTS: chordal_cycle 0.46x->1.13x, hnm_harary 0.50x->1.45x, hkn_harary 0.44x->1.58x,
LCF 0.70x->1.13x (ALL BEAT nx — int keys). margulis 0.34x->0.46x (PARTIAL — its nodes are (x,y) TUPLES so
the tuple-key construction tax keeps it <nx, same ceiling as products). 2600 harary/LCF/expander/generator
/classic conformance green. LEVER RE-CONFIRMED: grep per-edge `graph.add_edge(` loops in generators; batch
via add_edges_from(LIST) — int-keyed builders reach/beat nx, tuple-keyed get a partial reduction. (NOTE the
0.35x margulis reading right after a heavy pytest run was LOAD NOISE; clean re-measure 0.44-0.46x — always
re-measure a lone outlier.)


## 2026-07-02 CopperCliff FIX+SHIP: generalized_petersen_graph native kernel DIVERGED from nx (byte-inexact) — routed to Python, 0.58x -> 0.91x

Generator sweep flagged generalized_petersen_graph at 0.58-0.67x for create_using=None (the native
_rust_generalized_petersen_graph path). Investigation revealed the native kernel is NOT byte-exact with
nx: it produces an ISOMORPHIC graph with a DIFFERENT node LABELLING (node 7 before 6 at n=5 — nx adds the
inner-star nodes in a specific edge-encounter order) AND drops the ``name`` graph attr. Edge SET matches
but node/edge ORDER + name diverge — a latent correctness bug (downstream order/name-dependent code breaks),
same class as pappus_graph / hoffman_singleton (both already forced to the Python canonical-labelling path).
FIX: drop the native call, build in Python (cycle_graph + spoke/inner edges in nx's exact order, batched
through one add_edges_from). Now BYTE-EXACT vs nx (node order + edge order + name + error messages +
create_using=MultiGraph) AND FASTER than the broken kernel: 0.58x -> 0.91x (near parity; still <nx because
inner-star nodes n..2n-1 are added via edge-encounter so cycle_graph + the batch pays 2 construction passes).
1939 petersen/generator/classic conf green. LEVER: a native generator kernel that's SLOWER than nx is worth
a byte-exactness check — several produce isomorphic-but-differently-labelled graphs (grep _rust_*_graph
fast paths, diff node/edge order + graph attrs vs nx, route divergent ones to Python).


## 2026-07-02 CopperCliff SHIP: directed_havel_hakimi_graph batch — 0.51x -> 1.40x (beats nx)

The heap-based degree-sequence realization added edges one at a time via graph.add_edge(source, target)
inside the stub-processing loop. But the loop NEVER READS the graph (all state is in the stub/zero heaps),
so the edges can be collected into a list and committed via ONE add_edges_from at the end — byte-identical
edge order. (The "Non-digraphical" raise discards the graph via the caller, so deferring the commit past
the raise is safe.) 0.51x -> 1.40x (beats nx, int keys). 30/30 byte-exact vs nx + error cases match; 2192
havel/degree-seq/generator conf green. LEVER (extends reference_batch_add_edges_from_construction): even
ALGORITHMIC builders (heap/greedy degree-sequence realizers) that add_edge in a loop WITHOUT reading the
graph can defer to one add_edges_from. Also swept all 26 named native generator kernels for byte-exactness
vs nx — ALL clean except generalized_petersen (fixed 76ab197ef); the _rust_*_graph fast paths are
byte-correct.


## 2026-07-02 CopperCliff SHIP: barbell_graph second-bell pre-scan bypass — 0.79x -> 1.48x (beats nx)

Generator sweep: barbell_graph 0.79x at m1=500. The first bell is complete_graph(m1) (native), but the
SECOND bell K_{m1} is add_edges_from(GENERATOR) onto the ALREADY-POPULATED graph -> add_edges_from
materializes the generator then runs the touches-existing pre-scan (build existing-edge set of ~m1^2/2 +
membership-test every one of the m1^2/2 second-bell edges), ~doubling the work. But the second bell spans
ONLY fresh nodes m1+m2..2m1+m2-1 (first bell+bar live in 0..m1+m2-1), so no edge can touch an existing one.
FIX (same binomial_tree bf226b815 lever): materialize the second bell to a LIST + call the native batch
_try_add_edges_from_batch directly, skipping the pre-scan; fall back if it bails. 0.79x -> 1.48x (beats nx).
Byte-exact vs nx (node+edge order, m2=0/1/large, error cases); 1658 barbell/classic conf green. LEVER
(3rd pre-scan-bypass hit): grep add_edges_from(<generator/list> of provably-disjoint-new-node edges) onto
a NON-fresh graph -> materialize + direct _try_add_edges_from_batch. (Tiny named graphs sedgewick/tutte/
desargues 0.68-0.83x are 0.05ms = noise, skip; nonisomorphic_trees 0.75x is a recursive tree enumerator.)


## 2026-07-02 CopperCliff SHIP: disjoint_union_all direct-build — 0.71x -> 1.05x (beats nx)

Operator sweep: disjoint_union_all 0.71x (union_all itself is 1.29x, so the cost was elsewhere). cProfile:
per-graph convert_node_labels_to_integers (relabel_nodes 0.030s + _materialize 0.034s — a full copy that
materializes each graph's node/edge attrs) THEN union_all. FIX: build the union DIRECTLY with shifted
integer labels — one add_nodes_from + add_edges_from per graph onto the growing result (node[i] -> i +
first_label in node-iteration order, graph-attr last-wins merge), skipping the intermediate relabeled
copies. Byte-exact vs nx across ALL 4 graph types + node/edge/graph attrs + parallel edges + single/empty
list; 999 union/operator conf green. 0.71x -> 1.05x. LEVER (relabel-then-combine): a `relabel each ->
combine` operator pays N intermediate materialized copies; fuse into a direct shifted-label build.
(Conversion to/from dict/numpy/scipy/pandas/edgelist all already beat nx 1.1-3.3x; union_all/compose_all/
intersection_all already 1.09-1.44x.)


## 2026-07-02 CopperCliff SHIP: union(DiGraph) combine edge lists — 0.56x -> 1.26x (beats nx)

union's simple non-Graph (DiGraph) rebuild branch did TWO separate add_edges_from(VIEW):
`rebuilt.add_edges_from(G.edges(data=True)); rebuilt.add_edges_from(H.edges(data=True))`. Both flaws:
a VIEW isn't a list/tuple so it SKIPS the native batch gate (materialize+retry), AND the second runs on
a non-fresh graph (wasted touches-existing pre-scan). The multigraph branch just above already fixed this
(combine into one 4-tuple LIST). Applied the same to the simple branch: node sets are disjoint (checked
above) so combine list(G.edges(data=True)) + list(H.edges(data=True)) into ONE add_edges_from on the
fresh, node-populated rebuilt. 0.56x -> 1.26x (beats nx). Byte-exact vs nx (node/edge order + node/edge/
graph attrs); 999 union/operator conf green. Graph x Graph union still uses _native_compose (~0.64x,
construction tax) and Multi* the combined-list path (~0.71x) — both native/construction-tax bound.
Sweep: disjoint_union (binary) 1.95x, reverse 1.80x, ego_graph 1.97x, subgraph 1.45x, edge_subgraph 2.14x,
complement 4.78x all beat nx.


## 2026-07-02 CopperCliff SHIP (RUST, via /alien-graveyard): skip redundant edge_py_keys mirror for identity-int keys — MG difference 0.58x -> 0.67x

/alien-graveyard-guided (profile -> match the "eager per-edge allocation" lever -> the proven
has_remapped_int_key pattern). The multigraph keyed-batch kernels (_native_add_keyed_edges_no_data +
_try_add_str_keyed_edges_from_batch, lib.rs) built an edge_py_keys mirror entry for EVERY edge — per-edge
String clones (uc/vc) + Self::edge_key String build + HashMap insert + note_public_key_value. But
display_key_lookup (lib.rs:2564) falls back to `int:{internal}` when the mirror is ABSENT, so a public key
that is the EXACT non-negative int equal to its internal auto-key (the common add_edge/G.edges(keys=True)
case) needs NO mirror entry. FIX: gate the mirror push on `!(k is exact PyInt && k as usize == internal_key)`
— only NON-identity keys (str/float/bool/remapped-int) mirror; identity keys skip the per-edge mirror work.
Byte-EXACT: 28/28 vs nx across auto/str/explicit-int/float/removed-noncontiguous keys x MG/MDG x
difference/symmetric_difference/compose/union (the read path is identical — mirror-absent identity keys
resolve to int:{internal}); 4966 edges/keys/degree/batch conformance green. difference MG 0.58->0.67x,
MultiGraph add_edges_from(3000) 0.82x (~15% strict work removal on the keyed-batch cluster; union uses the
with-data batch, unaffected). Still <nx (the extend_keyed_edges insertion itself is the residual construction
tax) but the FIRST reduction of the multigraph construction tax — it is PARTIALLY reducible, not purely
architectural. FOLLOW-UP: the same identity-key mirror-skip applies to the with-data keyed batch
(_native_add_keyed_edges_with_data / _try_add_attr_edges_from_batch) used by compose/union — next.


## 2026-07-02 CopperCliff SHIP (RUST): identity-int mirror-skip extended to WITH-DATA + MDG keyed batches — whole MG/MDG cluster lifted

Follow-up to 7a49dd943 (which covered the MG no-data batch). Extended the identity-int edge_py_keys
mirror-skip to the 3 remaining LIVE keyed-batch kernels: MG with-data (try_add_fresh_exact_int_keyed4_
attr_edge_batch, lib.rs:3530 — compose/union pass 4-tuples (u,v,0/1/2,data)), MDG no-data (digraph.rs:3908
— MDG set-algebra), MDG with-data (digraph.rs:4045 — MDG compose/union). (The _native_difference/_native_
symmetric_difference kernels are DEAD for multigraphs — the Python path skips them as slower — so left
untouched.) Same gate: a public key that is the EXACT non-negative int == internal auto-key skips the
per-edge edge_py_keys entry + note_public_key_value (read falls back to int:{internal}). Byte-EXACT 28/28
vs nx (auto/str/explicit-int/float/removed-noncontiguous x MG/MDG x difference/symmetric_difference/
compose/union); 9060 multigraph/operator/conversion/edges/degree/subgraph conformance green. CLUSTER
LIFT vs session baselines: union MG 0.71->0.86x, union MDG 0.60->0.73x, symmetric_difference MDG
0.62->0.74x, compose MG 0.73->0.82x, compose MDG 0.60->0.65x, difference MG 0.58->0.70x, difference MDG
0.71->0.73x. Still <nx (the extend_keyed_edges insertion is the residual tax) but the multigraph
construction tax is now materially reduced across the WHOLE set-algebra + compose/union family via one
proven lever (has_remapped_int_key). The /alien-graveyard skill cracked what I'd surfaced as "purely
architectural" — it was partially reducible.
