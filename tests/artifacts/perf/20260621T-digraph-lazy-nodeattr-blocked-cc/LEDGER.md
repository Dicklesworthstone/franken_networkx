# NEGATIVE/BLOCKED — lazy node-attr mirror does NOT extend cleanly to DiGraph/MultiDiGraph

- Agent: `BlackThrush` · 2026-06-21 · MEASURED + code-traced

## Context
The lazy-node-attr lever (drop the eager per-node mirror PyDict alloc+copy in the attributed
add_nodes_from batch; materialize from the inner AttrMap on first read) SHIPPED for:
- PyGraph: add_nodes_from(+attr) 0.59x -> 1.12x WIN (b4f6ee77a)
- PyMultiGraph: 0.84x -> 0.90x marginal (94ede2d5b)

## Why DiGraph/MultiDiGraph are BLOCKED (attempted + reverted this session)
Dropping the eager mirror on PyDiGraph broke node-attr MUTATION:
`G.nodes[5]['w']=999` then `G.nodes[5]['w']` -> KeyError. Root cause: DiGraph's node-attr
accessors do NOT route through the (now inner-reading) materialize_node_py_attrs. There are
~16 INLINE `node_py_attrs.entry(canonical).or_insert_with(|| PyDict::new(py).unbind())` sites in
digraph.rs (the NodeDataView __getitem__ 9964, get 9983, and ~14 more across PyDiGraph +
PyMultiDiGraph) — each creates an EMPTY dict, relying on the eager mirror to have pre-populated
node_py_attrs. With the eager mirror gone they cache empties (and pollute the materialize cache),
so reads/mutations see {}.

## The fix (deferred — broad + borrow-subtle, not worth 0.74x half-done)
Route ALL ~16 inline sites to read the inner: change each `or_insert_with(|| PyDict::new...)` to
`entry(canonical.clone()).or_insert_with(|| match g.inner.node_attrs(&canonical) { Some(a) =>
attr_map_to_pydict(py,a).expect(...), None => PyDict::new(py).unbind() })`, then drop the eager
mirror in both add_attr_node_batch. Each site has slightly different surrounding (return &Py vs
clone_ref, loops, the entry(canonical) move needs a .clone()), so it is a careful 16-site refactor
with a real miss-one-site -> silent-empty-attr risk. PyGraph needed only 1-2 such sites (already
routed through materialize), which is why it flipped cleanly. DiGraph add_nodes_from(+attr) stays
0.74x, MultiDiGraph 0.56x until that refactor lands. digraph.rs left PRISTINE (reverted).
