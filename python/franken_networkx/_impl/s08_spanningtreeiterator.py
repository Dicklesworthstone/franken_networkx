

def _detach_row(row, *, removed_before=(), removed_node=None, remove_self=False):
    """Make one held adjacency row serve its current contents forever."""
    if hasattr(row, "_atlas_getter"):
        # A Python AdjacencyView/AtlasView: rebind the getter to a snapshot and
        # cut every native read path, including the caches keyed by a revision
        # that is about to move.
        try:
            snapshot = {
                neighbor: AtlasView(lambda keys=dict(value): keys)
                for neighbor, value in row.items()
                if neighbor not in removed_before
                and (not remove_self or neighbor != removed_node)
            }
        except Exception:  # noqa: BLE001 - a detached row must never break clear()
            return
        row._atlas_getter = lambda snap=snapshot: snap
        # br-r37-c1-fr4me: the captured row is consulted BEFORE the getter, so a
        # detach that rebound only the getter would leave membership reading the
        # live row it was meant to cut loose from.
        row._fnx_captured_row = snapshot
        # br-r37-c1-2ndmw: same reason one level down. `_atlas()` consults the
        # memoised cell atlas BEFORE the getter, so a detach that rebound only
        # the getter would leave a cell reading the live view it was cut from.
        row._fnx_captured_atlas = None
        row._fnx_native_iter = None
        row._fnx_native_len = None
        row._fnx_keys_snapshot = None
        row._fnx_atlas_cache = None
        row._fnx_owner = None
        row._fnx_multi_edge_owner = None
        return
    # A native `_fnx.AtlasView` (br-r37-c1-ey6ob routes simple Graph rows here).
    # Its fields are not writable from Python, but it already has the mechanism:
    # every read checks its own materialised `row` dict first, and `__iter__`
    # is what fills that dict in. So exhausting the iterator IS the detach — no
    # Rust change needed, and the cost is one O(degree) walk per cached row, paid
    # only by callers who actually clear a graph whose rows were handed out.
    try:
        for _ in row:
            pass
    except Exception:  # noqa: BLE001
        pass


def _make_clear_with_attr_override(raw_clear):
    def clear(self):
        # br-r37-c1-s5pxs: BEFORE the storage goes away, not after. All four
        # classes need it -- the bead recorded Graph/DiGraph as already matching,
        # and they do not: they raised KeyError, which is a worse divergence than
        # the multigraphs' empty read.
        _detach_rows_before_clear(self)
        raw_clear(self)
        override = vars(self).get(_GRAPH_ATTR_OVERRIDE, _GRAPH_ATTR_MISSING)
        if override is not _GRAPH_ATTR_MISSING and hasattr(override, "clear"):
            override.clear()
    return clear


for _cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
    _cls.clear = _make_clear_with_attr_override(_cls.clear)


# br-r37-c1-namovr (cycle 222): cycle 220's ``graph_attr_dict_factory``
# fix stores the live attrs in ``vars(obj)[_GRAPH_ATTR_OVERRIDE]`` and
# clears the Rust-side dict to avoid double-tracking.  The Rust-bound
# ``name`` getter reads from the (now-empty) Rust dict, so for
# subclasses with a custom factory:
#
#     class S(Graph): graph_attr_dict_factory = CustomDict
#     g = S(); g.name = 'foo'
#     # nx:  g.name == 'foo'
#     # fnx: g.name == ''       *** DIFF — getter bypassed override
#
# nx defines ``name`` as a property that round-trips through
# ``self.graph['name']``.  Mirror that here so both default and
# override paths share one source of truth: the descriptor's
# ``__get__`` (which already handles the override).
def _graph_name_get(self):
    return self.graph.get("name", "")


def _graph_name_set(self, value):
    self.graph["name"] = value


for _cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
    _cls.name = property(_graph_name_get, _graph_name_set)


def _graph_deepcopy(self, memo=None):
    """br-dcpy: the Rust __deepcopy__ didn't traverse nested attribute
    values, so _deepcopy(G).nodes[n]['x'].append(...) mutated the
    original graph's attrs too. Start from copy.copy's structure-preserving
    clone, then deep-copy every attrs dict without rebuilding adjacency rows.
    """
    from copy import copy as _copy, deepcopy as _dc

    # perf (br-r37-c1-bjomp, cc): when every value in an attrs dict is an
    # immutable scalar (None/bool/int/float/str), copy.deepcopy is observably
    # identical to a shallow dict copy — immutables are never copied and there
    # are no nested containers for the memo to matter. Fast-path those to a plain
    # `dict(attrs)`, falling back to copy.deepcopy (with the shared memo) for ANY
    # non-scalar value so nested-mutable + cross-attr memo sharing is unchanged.
    # Mirrors the deepcopy_py_dict Rust fast-path; cProfile showed copy.deepcopy
    # dominating __deepcopy__ (269k calls / 1.42s on attributed DiGraph(1500)).
    _immut = (bool, int, float, str)

    def _dc_attrs(attrs):
        d = dict(attrs)
        for v in d.values():
            if v is not None and type(v) not in _immut:
                return _dc(d, memo)
        return d

    # br-r37-c1-489mp: when the Rust type exposes a native same-type deepcopy, use
    # it — it clones the structure VERBATIM (matching copy.copy) and deep-copies the
    # node/edge attr dicts under the shared ``memo`` natively, replacing the
    # per-node/edge AtlasView walk below (``out[u][v]`` rebuilt the adjacency row
    # keydict O(E) times — the profiled deepcopy bottleneck). Byte-identical result;
    # graph attrs + frozen + custom instance attrs are applied by the shared tail.
    owner = _shared_unsplit_owner(self)
    if owner is not None:
        _native_deepcopy = getattr(owner, "_native_deepcopy", None)
    elif _SHARED_STORAGE_SOURCE in vars(self):
        _native_deepcopy = None
    else:
        _native_deepcopy = getattr(self, "_native_deepcopy", None)
    if _native_deepcopy is not None:
        out = _native_deepcopy(memo)
    else:
        out = self.copy()
        for node, attrs in self.nodes(data=True):
            out_attrs = out.nodes[node]
            out_attrs.clear()
            out_attrs.update(_dc_attrs(attrs))
        if self.is_multigraph():
            for u, v, key, attrs in self.edges(keys=True, data=True):
                out_attrs = out[u][v][key]
                out_attrs.clear()
                out_attrs.update(_dc_attrs(attrs))
        else:
            for u, v, attrs in self.edges(data=True):
                out_attrs = out[u][v]
                out_attrs.clear()
                out_attrs.update(_dc_attrs(attrs))
    vars(out)[_GRAPH_ATTR_OVERRIDE] = _dc(dict(self.graph), memo)
    # br-r37-c1-9e7gd: nx preserves the frozen-graph flag (and its
    # mutator overrides) across deepcopy because it copies the
    # instance __dict__. fnx's _graph_deepcopy constructs a fresh
    # cls() and populates it, so the frozen attribute and the
    # ``add_node=_frozen`` overrides are lost. Re-apply freeze on
    # the new graph when the source was frozen.
    if getattr(self, "frozen", False):
        freeze(out)
    # br-r37-c1-8nz0x: generalize — copy over any custom
    # Python-side instance attributes the user set (g.custom_attr = ...)
    # that aren't already part of the freshly-constructed graph's
    # state and aren't fnx-internal override slots. nx preserves
    # them via its default __dict__ deepcopy.
    src_dict = vars(self)
    out_dict = vars(out)
    # br-r37-c1-wbwkb: a view memoised by ``_CachedViewDescriptor`` lives under
    # its PUBLIC name (``nodes``/``edges``/``degree``) and so is not caught by
    # the ``_fnx_`` prefix rule, but it is an internal cache bound to THIS
    # graph — copying it would hand the copy a view of the original. Skip it;
    # the descriptor rebuilds it on the copy's first access.
    descriptor_cached = src_dict.get(_DESCRIPTOR_CACHED_VIEWS) or ()
    private_method_shadows = src_dict.get(_PRIVATE_NODE_METHOD_SHADOWS) or {}
    for key, val in src_dict.items():
        if key in out_dict:
            continue
        if key.startswith("_fnx_") or key in descriptor_cached:
            continue
        if key in private_method_shadows and val is private_method_shadows[key]:
            continue
        try:
            out_dict[key] = _dc(val, memo)
        except Exception:
            out_dict[key] = val
    # br-r37-c1-s8obc: assigned private stores are skipped by the ``_fnx_``
    # rule above (they are stashed under ``_fnx_private_*_override``), so
    # re-apply them explicitly. Deep-copied under the shared memo, because this
    # is deepcopy — copy.copy shares them instead, see _graph_shallowcopy.
    private_overrides = _captured_private_overrides(self)
    if private_overrides:
        _reapply_private_overrides(
            out,
            {
                public: _dc(value, memo)
                for public, value in private_overrides.items()
            },
        )
    return out


Graph.__deepcopy__ = _graph_deepcopy
DiGraph.__deepcopy__ = _graph_deepcopy
MultiGraph.__deepcopy__ = _graph_deepcopy
MultiDiGraph.__deepcopy__ = _graph_deepcopy

Graph.to_directed_class = _to_directed_class
Graph.to_undirected_class = _to_undirected_class
DiGraph.to_directed_class = _to_directed_class
DiGraph.to_undirected_class = _to_undirected_class
MultiGraph.to_directed_class = _to_directed_class
MultiGraph.to_undirected_class = _to_undirected_class
MultiDiGraph.to_directed_class = _to_directed_class
MultiDiGraph.to_undirected_class = _to_undirected_class


# br-classpred: nx.utils.misc.check_create_using does
# ``G.is_directed(None) if isinstance(G, type) else G.is_directed()``
# when deciding whether a create_using CLASS matches expected
# directedness. On nx classes, is_directed / is_multigraph are plain
# methods that ignore self, so calling them with self=None works. fnx's
# Rust descriptors require a real instance and raise TypeError, which
# breaks ``nx.gnp_random_graph(..., create_using=fnx.Graph)`` and any nx
# generator that passes a fnx class as create_using.
#
# br-r37-c1-hfn6e: so they are networkx's plain methods returning the class's
# constant (_install_class_predicate below). br-r37-c1-8a89c had cached the
# bound PyO3 method in the instance dict for a C-level hit, which made every
# graph that answered one a reference cycle - its dict held a method holding
# it - freed only by the cyclic GC: native storage lingered (a build-and-drop
# loop peaked near three times networkx's RSS) and its teardown landed in
# whatever ran when the collector fired. The plain method is also faster than
# that cache, and answers for None, a class or any object as networkx's does.
_DESCRIPTOR_CACHED_VIEWS = "_fnx_descriptor_cached_views"
_COMMON_CACHED_PUBLIC_NAMES = frozenset(("nodes", "edges", "degree"))
_DIRECTED_CACHED_PUBLIC_NAMES = _COMMON_CACHED_PUBLIC_NAMES | frozenset(
    ("in_degree", "out_degree", "in_edges", "out_edges")
)


_CLASS_PREDICATE_DOCS = {
    "is_directed": "Returns True if graph is directed, False otherwise.",
    "is_multigraph": "Returns True if graph is a multigraph, False otherwise.",
}


def _install_class_predicate(cls, name, value):
    """networkx's is_directed / is_multigraph: a plain method returning the
    class's constant, whatever self is."""
    if value:
        def predicate(self):
            return True
    else:
        def predicate(self):
            return False
    predicate.__name__ = name
    predicate.__qualname__ = f"{cls.__name__}.{name}"
    predicate.__doc__ = _CLASS_PREDICATE_DOCS[name]
    setattr(cls, name, predicate)


for _cls, _directed, _multigraph in (
    (Graph, False, False),
    (DiGraph, True, False),
    (MultiGraph, False, True),
    (MultiDiGraph, True, True),
):
    _install_class_predicate(_cls, "is_directed", _directed)
    _install_class_predicate(_cls, "is_multigraph", _multigraph)
del _cls, _directed, _multigraph
Graph.adjacency = _simple_graph_adjacency
DiGraph.adjacency = _simple_graph_adjacency
MultiGraph.adjacency = _multigraph_adjacency
MultiDiGraph.adjacency = _multigraph_adjacency


DiGraph.has_successor = _directed_graph_has_successor
DiGraph.has_predecessor = _directed_graph_has_predecessor
MultiDiGraph.has_successor = _directed_graph_has_successor
MultiDiGraph.has_predecessor = _directed_graph_has_predecessor


# br-r37-c1-iev-pkl: in_edges / out_edges were bound as plain methods
# instead of view objects. nx exposes them as `InEdgeView` /
# `OutEdgeView` (callable + iterable + len-able + pickle-able).
# `for u, v in G.in_edges:` is the documented idiom and worked on nx
# but raised `TypeError: 'method' object is not iterable` on fnx.
# Pickle of the bound method also failed with `AttributeError: ...
# has no attribute '_digraph_in_edges'`. Wrap each as a callable
# view that delegates to the underlying method.
class _DiEdgeMethodView:
    """Callable+iterable+len-able view backed by a graph + edge-method.

    Iterating yields the no-args call result; `__call__` delegates to
    the bound method with user-supplied args. Pickle snapshots to a
    plain list of edge tuples (matches nx's snapshot semantics on
    restored InEdgeView/OutEdgeView)."""

    __slots__ = ("_graph", "_method")
    # br-r37-c1-ex1s6: the rows membership reads - succ, or pred for the in
    # views (see _nx_edge_view_contains).
    _fnx_edge_kind = "out"

    def __init__(self, graph, method):
        self._graph = graph
        self._method = method

    # br-r37-c1-dfivn: THE MAPPING SURFACE. networkx's In/OutEdgeView are
    # Mappings — `G.out_edges[u, v]` returns the edge attribute dict and
    # `get`/`keys`/`values`/`items` all work. This class had none of it, so
    # `G.out_edges[u, v]` raised TypeError ("not subscriptable") and the rest
    # raised AttributeError, on both directed classes.
    #
    # It hid because `G.edges` is a DIFFERENT class that happens to share the
    # name `OutEdgeView` and does have the surface: every check of
    # `type(...).__name__`, iteration, length, containment and the call forms
    # agreed. Only a protocol sweep separated them.
    #
    # Subscripting DELEGATES to `G.edges`, which is correct rather than merely
    # convenient: networkx keys both views by the edge tuple in natural
    # (source, target) order — `InEdgeView.__getitem__` is `self._adjdict[v][u]`
    # over `G._pred`, i.e. the same attrs `G.edges[u, v]` yields. Delegating
    # also inherits the arity behaviour, where a multigraph raises ValueError
    # for a 2-tuple and resolves a 3-tuple.
    def __getitem__(self, edge):
        return self._graph.edges[edge]

    def get(self, edge, default=None):
        # Mapping.get semantics: a MISSING key yields the default, but a
        # malformed one still raises. networkx propagates the ValueError a
        # bad-arity multigraph key produces, so only KeyError is caught here.
        try:
            return self[edge]
        except KeyError:
            return default

    # Built from THIS view's own iteration, not from `G.edges`: the in and out
    # views iterate in different orders (networkx walks `_pred` for one and
    # `_succ` for the other) and the existing tests pin fnx matching each view's
    # order. The ABC wrappers give real view objects, as networkx returns,
    # rather than lists.
    def keys(self):
        return _KeysViewABC(self)

    def values(self):
        return _ValuesViewABC(self)

    def items(self):
        return _ItemsViewABC(self)

    def __iter__(self):
        # br-r37-c1-iev-mditer: nx's MultiInEdgeView/MultiOutEdgeView
        # default `keys=True` for __iter__ but `keys=False` for
        # __call__. Asymmetric. Match that exactly so
        # `for u, v, k in MDG.in_edges:` works (the documented idiom)
        # while `MDG.in_edges()` still yields 2-tuples (callable
        # backward compat from before this change).
        if self._graph.is_multigraph():
            return iter(self._method(self._graph, keys=True))
        return iter(self._method(self._graph))

    def __len__(self):
        # br-r37-c1-edgelen: ``len(self._method(...))`` rebuilt the ENTIRE edge
        # list just to count it — and CPython calls __len__ for the size hint
        # before __iter__, so ``list(DG.edges())`` materialized the edges TWICE
        # (~2x nx). An InEdgeView/OutEdgeView spans every directed edge (parallel
        # edges counted for multigraphs), so the length is the O(1) native edge
        # count. Mirrors nx.OutEdgeView/InEdgeView.__len__ (== G.number_of_edges())
        # and the sibling NodeDataView fix.
        return self._graph.number_of_edges()

    def __contains__(self, item):
        # br-r37-c1-iemvcontains: nx.InEdgeView / OutEdgeView /
        # InMultiEdgeView / OutMultiEdgeView all use the bare
        # ``u, v = e`` unpack pattern matching the parent OutEdgeView.
        # fnx previously delegated to ``item in self._method(...)``
        # which materialized the result as a list and used
        # element-equality, so:
        #   - ``[0, 1] in DG.in_edges`` returned False (list != tuple)
        #   - ``"foo" in DG.in_edges`` returned False
        #   - ``123 in DG.in_edges`` returned False
        # nx accepts list (length 2) as an edge spec and propagates
        # ValueError on length mismatch + TypeError on non-iterable.
        # br-r37-c1-ex1s6: and it is ONE row lookup, u in pred[v] / v in
        # succ[u] (k in the pair's keydict on a multigraph, k = 0 for a
        # pair). This scanned every edge per probe, and compared a
        # multigraph probe against key-less pairs: (0, 1, 1) in
        # MDG.in_edges was False for an edge the view lists.
        graph = self._graph
        return _nx_edge_view_contains_by_has_edge(
            graph, item, self._fnx_edge_kind, graph.is_multigraph()
        )

    def __call__(self, *args, **kwargs):
        # br-r37-c1-iemvcall: for non-multigraph DiGraph, nx's
        # InEdgeView / OutEdgeView implement ``__call__`` such that
        # no-args returns ``self`` (so ``DG.in_edges() is DG.in_edges``
        # holds in nx).  fnx's __call__ materialized to a Python list
        # even when no filtering args were passed, so:
        #   - ``[0,1] in DG.in_edges()`` returned False (plain list ==)
        #   - ``DG.in_edges()`` was a stale snapshot, not a live view
        # For MultiDiGraph nx's call form returns a *different* class
        # (InMultiEdgeDataView) with stricter ``e == self._report(...)``
        # tuple-equality semantics — keep the snapshot list there.
        if not args and not kwargs and not self._graph.is_multigraph():
            return self
        result = self._method(self._graph, *args, **kwargs)
        # br-r37-c1-iemvcw (cycle 215): nx's
        # ``DG.in_edges(data=...)`` / ``DG.out_edges(data=...)`` and
        # the entire ``MDG.in_edges(...)`` / ``MDG.out_edges(...)``
        # call surface return canonical view classes
        # (InEdgeDataView / OutEdgeDataView / InMultiEdgeDataView /
        # OutMultiEdgeDataView / InMultiEdgeView / OutMultiEdgeView).
        # fnx returned a plain ``list`` for every args case,
        # diverging on ``type(view).__name__`` AND breaking
        # ``(u, v) in MDG.{in,out}_edges(keys=True)`` 2-tuple
        # containment (sister of cycle 214 ``MG.edges(keys=True)``).
        # Sister of cycle 213 ``MG.edges(data=...)`` wrap.
        cls_name = type(self).__name__
        is_multi = self._graph.is_multigraph()
        data = kwargs.get("data", False)
        if len(args) >= 2:
            data = args[1]
        keys = kwargs.get("keys", False)
        if is_multi and len(args) >= 3:
            keys = args[2]
        if is_multi:
            if data is not False:
                wrap = (_InMultiEdgeDataView if cls_name == "InMultiEdgeView"
                        else _OutMultiEdgeDataView)
            elif keys:
                wrap = (_InMultiEdgesKeysView if cls_name == "InMultiEdgeView"
                        else _OutMultiEdgesKeysView)
            else:
                # no-args / nbunch-only: nx returns the canonical
                # ``In/OutMultiEdgeDataView`` class.
                wrap = (_InMultiEdgeDataView if cls_name == "InMultiEdgeView"
                        else _OutMultiEdgeDataView)
        else:
            if data is False and (
                kwargs["nbunch"] if "nbunch" in kwargs else (args[0] if args else None)
            ) is None:
                # networkx: `if nbunch is None and data is False: return self`
                return self
            # br-r37-c1-ex1s6: an nbunch-only call is networkx's
            # In/OutEdgeDataView reporting (u, v); it was a bare list - no
            # class name, no liveness, membership by scan.
            wrap = (_InEdgeDataView if cls_name == "InEdgeView"
                    else _OutEdgeDataView)
        return _wrap_edge_data_view(result, wrap)

    def __reduce__(self):
        return (list, (list(self),))

    # br-r37-c1-vcopy: nx's InEdgeView / OutEdgeView / InMultiEdgeView
    # / OutMultiEdgeView preserve type through copy.copy /
    # copy._deepcopy.  __copy__ returns self (live wrapper).
    # br-r37-c1-vcopydc: __deepcopy__ must be a SNAPSHOT independent
    # of subsequent G mutations (matches nx).  Deep-copy the
    # underlying graph and return its in_edges or out_edges
    # property based on the cycle-188 subclass name.
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        new_graph = _deepcopy(self._graph, memo)
        cls_name = type(self).__name__
        if cls_name in ("InEdgeView", "InMultiEdgeView"):
            return new_graph.in_edges
        # OutEdgeView / OutMultiEdgeView (and any other subclasses)
        return new_graph.out_edges

    def __repr__(self):
        # br-r37-c1-emvname: nx's InEdgeView / OutEdgeView /
        # InMultiEdgeView / OutMultiEdgeView each repr as
        # ``<ClassName>([(u, v), ...])``. fnx previously returned
        # bare ``[(u, v), ...]`` (no class wrapper) — diverging on
        # any drop-in code that parses the repr as a class hint.
        # Use ``type(self).__name__`` so the four subclasses below
        # pick up the canonical nx name.
        return f"{type(self).__name__}({list(self)!r})"

    # br-r37-c1-iev-eq-data: CROSS-REVIEW gaps in br-r37-c1-7gej0.
    # nx.InEdgeView is set-like (inherits from _Set), so two view
    # accesses on the same graph compare equal. fnx's wrapper used
    # default `object.__eq__` (identity), so `G.in_edges == G.in_edges`
    # was False — a real parity break for any code that compares
    # views.
    def __eq__(self, other):
        # Match nx's _Set-inheritance semantics exactly: equal only to
        # another set-like view of the same edges. Lists / tuples are
        # NOT equal to a view (nx's `view == [...]` returns False).
        from collections.abc import Set as _Set
        if isinstance(other, _DiEdgeMethodView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __hash__(self):
        return id(self._graph) ^ id(self._method)

    # nx.InEdgeView/OutEdgeView expose a `.data()` method returning an
    # EdgeDataView. Used by `for u, v, attrs in G.in_edges.data():`
    # and `G.in_edges.data('weight', default=0)`. Delegate to the
    # underlying method with the appropriate kwargs.
    def data(self, data=True, default=None, nbunch=None):
        # `data` parameter: True -> yield (u, v, attrs); a string ->
        # yield (u, v, attr_value_or_default); False -> yield (u, v).
        # Match nx's signature exactly.
        result = self._method(
            self._graph,
            nbunch=nbunch,
            data=data,
            default=default,
        )
        # br-r37-c1-edvname: wrap in canonical-named DataView class so
        # ``type(DG.in_edges.data()).__name__`` matches nx's
        # ``InEdgeDataView`` / ``OutEdgeDataView`` /
        # ``InMultiEdgeDataView`` / ``OutMultiEdgeDataView`` based on
        # this view's class name (set per-direction × multi by the
        # cycle-188 subclass split).
        cls_name = type(self).__name__
        if cls_name == "InEdgeView":
            return _wrap_edge_data_view(result, _InEdgeDataView)
        if cls_name == "OutEdgeView":
            return _wrap_edge_data_view(result, _OutEdgeDataView)
        if cls_name == "InMultiEdgeView":
            return _wrap_edge_data_view(result, _InMultiEdgeDataView)
        if cls_name == "OutMultiEdgeView":
            return _wrap_edge_data_view(result, _OutMultiEdgeDataView)
        return result

    # br-r37-c1-iev-setops: nx.InEdgeView inherits from _Set so all set
    # comparison + algebra operators work (`<=`, `<`, `>=`, `>`,
    # `isdisjoint`, `&`, `|`, `-`, `^`). The wrapper had iter/contains/
    # len + custom __eq__ but no comparison-or-algebra operators —
    # `H.in_edges <= G.in_edges` raised TypeError, breaking the
    # documented subset/superset idiom.
    def __le__(self, other):
        if isinstance(other, _DiEdgeMethodView):
            return set(self) <= set(other)
        from collections.abc import Set as _Set
        if isinstance(other, _Set):
            return set(self) <= set(other)
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, _DiEdgeMethodView):
            return set(self) < set(other)
        from collections.abc import Set as _Set
        if isinstance(other, _Set):
            return set(self) < set(other)
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, _DiEdgeMethodView):
            return set(self) >= set(other)
        from collections.abc import Set as _Set
        if isinstance(other, _Set):
            return set(self) >= set(other)
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, _DiEdgeMethodView):
            return set(self) > set(other)
        from collections.abc import Set as _Set
        if isinstance(other, _Set):
            return set(self) > set(other)
        return NotImplemented

    def isdisjoint(self, other):
        return set(self).isdisjoint(other)

    def __and__(self, other):
        return set(self) & set(other)

    def __or__(self, other):
        return set(self) | set(other)

    def __sub__(self, other):
        return set(self) - set(other)

    def __xor__(self, other):
        return set(self) ^ set(other)


# br-r37-c1-emvname: instantiate concrete subclasses per direction ×
# multi so ``type(view).__name__`` matches nx's ``InEdgeView`` /
# ``OutEdgeView`` / ``InMultiEdgeView`` / ``OutMultiEdgeView``.
class _OutEdgeView(_DiEdgeMethodView):
    pass
_OutEdgeView.__name__ = "OutEdgeView"


class _InEdgeView(_DiEdgeMethodView):
    _fnx_edge_kind = "in"
_InEdgeView.__name__ = "InEdgeView"


class _OutMultiEdgeView(_DiEdgeMethodView):
    def data(self, data=True, default=None, nbunch=None, keys=False):
        return self(nbunch=nbunch, data=data, keys=keys, default=default)
_OutMultiEdgeView.__name__ = "OutMultiEdgeView"


class _InMultiEdgeView(_DiEdgeMethodView):
    _fnx_edge_kind = "in"

    def data(self, data=True, default=None, nbunch=None, keys=False):
        return self(nbunch=nbunch, data=data, keys=keys, default=default)
_InMultiEdgeView.__name__ = "InMultiEdgeView"


# br-r37-c1-af0ig: G.in_edges(...) / G.out_edges(...) were frozen snapshots in
# exactly the same way G.edges(...) was. All four direction × multi classes
# above are empty subclasses of _DiEdgeMethodView, so patching the base once
# covers every one of them — and covers any future sibling for free. This is
# deliberately here rather than beside the _DiGraphEdgeView patch: these
# classes do not exist yet at that point in the module.
_DiEdgeMethodView.__call__ = _live_called_edge_view(_DiEdgeMethodView.__call__)


def _make_edge_method_view_property(method, view_cls):
    def getter(self):
        owner = _shared_unsplit_owner(self)
        return view_cls(owner if owner is not None else self, method)
    return property(getter)


DiGraph.out_edges = _make_edge_method_view_property(_digraph_out_edges, _OutEdgeView)
DiGraph.in_edges = _make_edge_method_view_property(_digraph_in_edges, _InEdgeView)
MultiDiGraph.out_edges = _make_edge_method_view_property(_multidigraph_out_edges, _OutMultiEdgeView)
MultiDiGraph.in_edges = _make_edge_method_view_property(_multidigraph_in_edges, _InMultiEdgeView)


def _nan_filtered_graph(G, weight, ignore_nan):
    # br-r37-c1-s8w2p: SubgraphView class can't be empty-constructed.
    H = _concrete_class_for(G)()
    H.graph.update(dict(G.graph))
    H.add_nodes_from(G.nodes(data=True))

    if G.is_multigraph():
        for u, v, key, attrs in G.edges(keys=True, data=True):
            edge_weight = attrs.get(weight, 1)
            if isinstance(edge_weight, float) and _math.isnan(edge_weight):
                if ignore_nan:
                    continue
                raise ValueError(
                    f"NaN found as an edge weight. Edge {(u, v, dict(attrs))}"
                )
            H.add_edges_from([(u, v, key, dict(attrs))])
    else:
        for u, v, attrs in G.edges(data=True):
            edge_weight = attrs.get(weight, 1)
            if isinstance(edge_weight, float) and _math.isnan(edge_weight):
                if ignore_nan:
                    continue
                raise ValueError(
                    f"NaN found as an edge weight. Edge {(u, v, dict(attrs))}"
                )
            H.add_edge(u, v, **dict(attrs))

    return H


class SpanningTreeIterator:
    """Iterate over all spanning trees of a graph in weight-sorted order.

    Keeps a frontier of edge partitions and selects each candidate with the
    spanning-tree selector, using its native kernel for supported weights.
    Consuming a prefix does not enumerate the remaining trees.

    Parameters
    ----------
    G : Graph
        Undirected graph.
    weight : str, default "weight"
        Edge attribute used as weight.
    minimum : bool, default True
        If True, yield trees in increasing weight order; otherwise decreasing.
    ignore_nan : bool, default False
        If False, raise when a NaN edge weight is encountered. If True, skip
        NaN-weighted edges before enumeration.
    """

    @_dataclass(order=True)
    class Partition:
        """A candidate spanning-tree partition ordered by its tree weight."""

        mst_weight: float
        partition_dict: dict = _field(compare=False)

        def __copy__(self):
            return SpanningTreeIterator.Partition(
                self.mst_weight, self.partition_dict.copy()
            )

    def __init__(self, G, weight="weight", minimum=True, ignore_nan=False):
        self.G = _coerce_arg_to_fnx_graph(G).copy()
        self.weight = weight
        self.minimum = minimum
        self.ignore_nan = ignore_nan
        self.partition_key = "SpanningTreeIterators super secret partition attribute name"

    def __iter__(self):
        from franken_networkx._fnx import NetworkXNotImplemented

        if self.G.is_directed():
            raise NetworkXNotImplemented("not implemented for directed type")
        if self.G.is_multigraph():
            # br-r37-c1-ho3db: nx supports MultiGraph in
            # SpanningTreeIterator; the Rust kernel is simple-only.
            # Delegate to nx so MultiGraph callers keep working.
            import networkx as _nx_local
            self._iterator = iter(
                _nx_local.SpanningTreeIterator(
                    _networkx_graph_for_parity(self.G),
                    weight=self.weight,
                    minimum=self.minimum,
                    ignore_nan=self.ignore_nan,
                )
            )
            return self
        self._iterator = None
        self.partition_queue = []
        self._partition_serial = 0
        self._queue_partition({}, self._select_partition({}))
        return self

    def _select_partition(self, constraints):
        for u, v, attrs in self.G.edges(data=True):
            attrs[self.partition_key] = constraints.get((u, v), EdgePartition.OPEN)
        tree = partition_spanning_tree(
            self.G,
            minimum=self.minimum,
            weight=self.weight,
            partition=self.partition_key,
            ignore_nan=self.ignore_nan,
        )
        for _, _, attrs in tree.edges(data=True):
            attrs.pop(self.partition_key, None)
        return tree

    def _queue_partition(self, constraints, tree):
        from heapq import heappush

        # Graph.size(weight) divides by two, rounding integer totals to float.
        # Distinct costs beyond 2**53 must not become arbitrary heap ties.
        # Keep the established degree-sum arithmetic for other numeric types.
        cost = 0
        if self.weight is None:
            cost = tree.size()
        else:
            for _, _, attrs in tree.edges(data=True):
                value = attrs.get(self.weight, 1)
                if type(value) not in (int, bool):
                    cost = tree.size(weight=self.weight)
                    break
                cost += value
        self._partition_serial += 1
        heappush(
            self.partition_queue,
            (cost if self.minimum else -cost, self._partition_serial, tree, constraints),
        )

    def __next__(self):
        if not hasattr(self, "_iterator"):
            raise AttributeError(
                "'SpanningTreeIterator' object has no attribute 'partition_queue'"
            )
        try:
            if self._iterator is not None:
                return next(self._iterator)
            if not self.partition_queue:
                raise StopIteration
            from heapq import heappop

            _, _, tree, constraints = heappop(self.partition_queue)
            prefix = constraints.copy()
            # Every alternative first differs at one open tree edge. Exclude
            # that edge and include the preceding ones, producing disjoint
            # partitions without constructing the unconsumed search space.
            for edge in tree.edges:
                if edge in constraints:
                    continue
                alternative = prefix.copy()
                alternative[edge] = EdgePartition.EXCLUDED
                candidate = self._select_partition(alternative)
                if is_connected(candidate):
                    self._queue_partition(alternative, candidate)
                prefix[edge] = EdgePartition.INCLUDED
            return tree
        except StopIteration:
            del self.G
            del self._iterator
            if hasattr(self, "partition_queue"):
                del self.partition_queue
            raise


class ArborescenceIterator:
    """Iterate over all spanning arborescences of a digraph in weight-sorted order.

    Uses the incremental partition scheduler with native arborescence
    selection on simple graphs, retaining only the current search frontier.

    Parameters
    ----------
    G : DiGraph
        Directed graph.
    weight : str, default "weight"
        Edge attribute used as weight.
    minimum : bool, default True
        If True, yield arborescences in increasing weight order.
    init_partition : tuple, optional
        ``(included_edges, excluded_edges)`` to constrain the enumeration.
    """

    @_dataclass(order=True)
    class Partition:
        """A candidate arborescence partition ordered by its tree weight."""

        mst_weight: float
        partition_dict: dict = _field(compare=False)

        def __copy__(self):
            return ArborescenceIterator.Partition(
                self.mst_weight, self.partition_dict.copy()
            )

    def __init__(self, G, weight="weight", minimum=True, init_partition=None):
        self.G = _coerce_arg_to_fnx_graph(G).copy()
        self.weight = weight
        self.minimum = minimum
        self.init_partition = (
            None if init_partition is None
            else (tuple(init_partition[0]), tuple(init_partition[1]))
        )

    def __iter__(self):
        from franken_networkx._fnx import NetworkXPointlessConcept
        import networkx as _nx_local

        if not self.G.is_directed():
            from franken_networkx._fnx import NetworkXNotImplemented

            raise NetworkXNotImplemented("not implemented for undirected type")
        if self.G.is_multigraph():
            # br-r37-c1-ho3db: nx supports MultiDiGraph in
            # ArborescenceIterator; the Rust kernel is simple-only.
            # Delegate to nx so MultiDiGraph callers keep working.
            self._iterator = iter(
                _nx_local.ArborescenceIterator(
                    _networkx_graph_for_parity(self.G),
                    weight=self.weight,
                    minimum=self.minimum,
                    init_partition=self.init_partition,
                )
            )
            return self
        if self.G.number_of_nodes() == 0:
            raise NetworkXPointlessConcept("G has no nodes.")
        scheduler = _nx_local.ArborescenceIterator(
            self.G,
            weight=self.weight,
            minimum=self.minimum,
            init_partition=self.init_partition,
        )
        # Reuse the scheduler without replacing any NetworkX globals. Its
        # working graph and every selected arborescence remain FNX graphs.
        scheduler.method = (
            minimum_spanning_arborescence if self.minimum
            else maximum_spanning_arborescence
        )
        self._iterator = iter(scheduler)
        return self

    def __next__(self):
        if not hasattr(self, "_iterator") or self._iterator is None:
            raise AttributeError(
                "'ArborescenceIterator' object has no attribute 'partition_queue'",
            )
        try:
            return next(self._iterator)
        except StopIteration:
            del self.G
            del self._iterator
            raise StopIteration


# Exception hierarchy
from franken_networkx._fnx import (
    HasACycle,
    NetworkXAlgorithmError,
    NetworkXError,
    NetworkXNoCycle,
    NetworkXNoPath,
    NetworkXNotImplemented,
    NetworkXPointlessConcept,
    NetworkXUnbounded,
    NetworkXUnfeasible,
    # br-r37-c1-4asgt: NotAPartition lives at nx.algorithms.community.
    # quality.X but not at nx top level. Aliased privately so internal
    # raises still work; the public surface stays fnx.community.X.
    NotAPartition as _NotAPartition,
    NotATree,
    NodeNotFound,
    PowerIterationFailedConvergence,
)

# br-nxexcbase: the Rust module doesn't expose the upstream-compatible
# ``NetworkXException`` base class in the currently-built .so (a
# rebuild-lag state that may persist across review rounds). Fall back
# to ``NetworkXError`` — it's the closest Rust-side equivalent and lets
# the import succeed so the rest of the module loads.
try:
    from franken_networkx._fnx import NetworkXException
except ImportError:
    NetworkXException = NetworkXError


def _nx_exception_cls():
    """Return the upstream-compatible base ``NetworkXException`` class.

    A few wrapper sites (e.g. ``is_graphical`` method guard,
    ``non_randomness`` precondition checks) need to raise the exact
    upstream base class so that both fnx's parity tests and code
    catching ``nx.NetworkXException`` work.
    """
    return NetworkXException


class NetworkXTreewidthBoundExceeded(NetworkXError):
    """Raised when a chordal search exceeds the requested treewidth bound."""

# Algorithm functions — shortest path
from franken_networkx._fnx import (
    average_shortest_path_length as _raw_average_shortest_path_length,
    bellman_ford_path as _raw_bellman_ford_path,
    dijkstra_path as _raw_dijkstra_path,
    has_path as _raw_has_path,
    multi_source_dijkstra as _raw_multi_source_dijkstra,
    shortest_path as _raw_shortest_path,
    shortest_path_length as _shortest_path_length_raw,
)


def _networkx_graph_for_parity(G):
    if isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        from franken_networkx.backend import _fnx_to_nx

        return _fnx_to_nx(G)
    return G


def _networkx_graph_for_traversal_parity(G):
    """Structural snapshot for chordless_cycles, in source adjacency order.

    The upstream consumer reads topology and parallel-edge counts, never
    attributes. Avoid rebuilding an attributed graph one edge at a time.
    """
    if not isinstance(G, (Graph, DiGraph, MultiGraph, MultiDiGraph)):
        return G

    directed = G.is_directed()
    multigraph = G.is_multigraph()
    if multigraph:
        graph = _nx.MultiDiGraph() if directed else _nx.MultiGraph()
    else:
        graph = _nx.DiGraph() if directed else _nx.Graph()

    # Exact types only: the Rust base of a view is empty, and assigned private
    # mappings override even a concrete graph's native storage.
    rows = None
    if type(G) in (Graph, DiGraph) and not _has_networkx_private_storage(G):
        rows = _fnx.to_dict_of_dicts_undirected(G)
    if rows is None:
        if multigraph:
            # Copy keydict topology as well: holding the adapter across a
            # source mutation must not change its parallel-edge counts.
            rows = {
                u: {v: {key: {} for key in keys} for v, keys in G.adj[u].items()}
                for u in G
            }
        else:
            rows = {u: {v: {} for v in G.adj[u]} for u in G}

    graph._node = {node: {} for node in rows}
    graph._adj = rows
    if directed:
        # DiGraph's _adj descriptor also installs _succ. Keep the predecessor
        # rows consistent and sharing the same per-edge dictionaries.
        graph._pred = {node: {} for node in rows}
        for u, neighbors in rows.items():
            for v, data in neighbors.items():
                graph._pred[v][u] = data
    return graph


def _path_query_has_missing_nodes(G, source=None, target=None):
    return (source is not None and source not in G) or (
        target is not None and target not in G
    )


try:
    from franken_networkx._fnx import (
        graph_has_negative_edge_weight as _native_has_negative_edge_weight,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_has_negative_edge_weight = None

try:
    from franken_networkx._fnx import (
        check_dijkstra_edge_weights_fast as _native_check_dijkstra_weights_fast,
        dijkstra_weight_cache_token as _native_dijkstra_weight_cache_token,
        graph_has_explicit_nonunit_weight_fast as _native_has_explicit_nonunit_weight_fast,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_check_dijkstra_weights_fast = None
    _native_dijkstra_weight_cache_token = None
    _native_has_explicit_nonunit_weight_fast = None

from franken_networkx._fnx import WeightRowsUnverified as _WeightRowsUnverified

# br-r37-c1-svsam: see _cached_native_weight_scan. _CHECK_ROWS stands in for a
# scan the caller's native search replaces by checking the rows it expands;
# _WEIGHT_ROWS.full_scan is raised while a call that met _WeightRowsUnverified
# re-runs, so that re-run takes the whole scan instead.
_CHECK_ROWS = object()
_WEIGHT_ROWS = _threading.local()
_ROW_CHECKS_PER_REVISION = 8


def _dijkstra_weight_route(G, weight):
    """br-r37-c1-svsam: ``"networkx"``, ``"native"``, or ``"rows"`` - run the
    native search with ``check_rows=True`` and re-run on
    ``_WeightRowsUnverified`` (see _rerun_with_weight_scan). Row checking is
    simple-graph only; multigraphs use a full scan. The answer is
    ``_should_delegate_dijkstra_to_networkx``'s."""
    if callable(weight) or not isinstance(weight, str):
        return "networkx"
    scan = _cached_native_weight_scan(G, weight, rows_ok=not G.is_multigraph())
    if scan is _CHECK_ROWS:
        return "rows"
    if scan is None:
        return "networkx" if _should_delegate_dijkstra_to_networkx(G, weight) else "native"
    return "networkx" if any(scan) else "native"


def _bellman_ford_weight_route(G, weight):
    """Bellman-Ford's counterpart of _dijkstra_weight_route: negative weights
    stay native (see _should_delegate_bellman_ford_path_to_networkx)."""
    if callable(weight) or not isinstance(weight, str):
        return "networkx"
    scan = _cached_native_weight_scan(G, weight, rows_ok=not G.is_multigraph())
    if scan is _CHECK_ROWS:
        return "rows"
    if scan is None:
        delegate = _should_delegate_bellman_ford_path_to_networkx(G, weight)
        return "networkx" if delegate else "native"
    _has_negative, has_nonfinite, has_nonnumeric = scan
    return "networkx" if (has_nonfinite or has_nonnumeric) else "native"


def _rerun_with_weight_scan(fn, *args, **kwargs):
    """br-r37-c1-svsam: a row-checked native search met a weight the gate must
    see (or read too many rows to check them one by one). Run the public call
    again from the top, gated by the whole-graph scan as before the change."""
    _WEIGHT_ROWS.full_scan = getattr(_WEIGHT_ROWS, "full_scan", 0) + 1
    try:
        return fn(*args, **kwargs)
    finally:
        _WEIGHT_ROWS.full_scan -= 1

try:
    from franken_networkx._fnx import (
        bidirectional_dijkstra as _native_bidirectional_dijkstra,
    )
except ImportError:  # pragma: no cover — defensive for partial builds
    _native_bidirectional_dijkstra = None


def _has_negative_edge_weight_for_dijkstra(G, weight, *, _skip_sync=False):
    if not isinstance(weight, str):
        return False

    # br-r37-c1-644fx: route the scan through a native O(|E|) Rust
    # helper for simple Graph/DiGraph (the common dispatcher hot path).
    # The previous Python iteration over G.edges() cost ~50 ms on
    # BA5000 — it dominated dijkstra_path wall time even though the
    # Rust algorithm itself is faster than nx.
    #
    # br-r37-c1-mgnegscan-8l53h: the `not G.is_multigraph()` gate that stood
    # here is GONE. The native helper used to return None for multigraphs, so
    # both multigraph classes fell to the Python walk below on EVERY weighted
    # shortest-path call — 1635 and 1236 Python frames for one guard call on a
    # 400-edge graph, against 4 for the simple classes. Both multigraph arms
    # are now wired natively and walk PARALLEL edges individually, so the gate
    # only forced a slow path. `native is None` below still handles anything
    # the native layer cannot extract, which is what keeps the Python fallback
    # correct rather than dead.
    if _native_has_negative_edge_weight is not None:
        try:
            native = _native_has_negative_edge_weight(G, weight)
        except Exception:
            native = None
        if native is True:
            return True
        # br-r37-c1-djk-neginf: the native helper only counts FINITE
        # negative weights (it filters with isfinite for SIMD-friendly
        # comparison).  ``-inf`` slips through both the native scan
        # and the prior Python ``isfinite(value) and value < 0``
        # check, so dijkstra ran on a -inf-weighted graph and
        # silently returned a -inf-cost path.  nx detects the
        # contradiction during relaxation and raises
        # ``ValueError: Contradictory paths found: negative
        # weights?``.  Fall through to the Python scan below
        # specifically for the -inf case so we delegate to nx.
        if native is False:
            # br-r37-c1-8cqeh: if the broader nonfinite-scan also
            # returns False, every weight is a finite numeric — so
            # there's no -inf either. Skip the Python -inf sweep
            # entirely. Cuts the gate from ~60 ms to ~15 ms on
            # BA5000-density graphs.
            # br-r37-c1-mgnegscan-8l53h: multigraph gate removed here too. The
            # shim consults BOTH helpers, so leaving this one gated would have
            # kept the per-edge Python -inf sweep for multigraphs even with the
            # negative scan native.
            if _native_has_nonfinite_edge_weight is not None:
                if not _skip_sync:
                    _sync_rust_edge_attrs(G)
                try:
                    nonfinite = _native_has_nonfinite_edge_weight(G, weight)
                except Exception:
                    nonfinite = None
                if nonfinite is False:
                    return False
            # br-r37-c1-4m4wb RE-LANDED, and the revert note it replaces had the
            # trade the wrong way round. `data=True` hands out the live attr
            # dicts, which marks the weighted store dirty for the LIFE OF THE
            # GRAPH; `data=weight` yields values and marks nothing. The revert
            # kept `data=True` because the key spelling measured 2.88x the dict
            # spelling ON THIS SCAN -- but that is a ONE-TIME cost on a scan that
            # only runs when the graph already has a non-finite weight, and what
            # it bought was a PERMANENT ~5x on every later size(weight=...) /
            # degree(weight=...) the caller makes (br-r37-c1-igdzi). A one-off
            # 2.88x on a rare path is not worth a permanent whole-graph penalty.
            #
            # REPRODUCED before changing it, load-independently: on a `Graph`
            # carrying a +inf or -inf weight, calling this guard left
            # `size(weight=...)` taking the whole-graph to_dict_of_dicts fallback;
            # on an all-finite graph the sweep is skipped and nothing happens,
            # which is why an ordinary dijkstra call never showed it. DiGraph does
            # not reach that fallback at all, so `Graph` is the case that pays.
            #
            # Equivalent by construction: the old code read `attrs.get(weight, 1)`
            # and `data=weight, default=1` yields exactly that value, so the
            # -inf test below is unchanged. Pinned by
            # tests/python/test_dijkstra_guard_keeps_store_clean.py.
            for _, _, value in G.edges(data=weight, default=1):
                if isinstance(value, _numbers.Real) and value == -_math.inf:
                    return True
            return False

    if G.is_multigraph():
        edge_iter = G.edges(keys=True, data=True)
        attrs_iter = (attrs for _, _, _, attrs in edge_iter)
    else:
        edge_iter = G.edges(data=True)
        attrs_iter = (attrs for _, _, attrs in edge_iter)

    for attrs in attrs_iter:
        value = attrs.get(weight, 1)
        # br-r37-c1-djk-neginf: also catches ``-inf`` (drop the
        # isfinite filter — ``-inf < 0`` is True, NaN comparisons
        # all yield False so neither broken case re-enters here).
        if isinstance(value, _numbers.Real) and not _math.isnan(value) and value < 0:
            return True
    return False


def _has_positive_infinity_edge_weight_for_dijkstra(G, weight, *, _skip_sync=False):
    """br-r37-c1-z35td: detect ``+inf`` edge weights.

    The Rust ``edge_weight_or_default`` helper filters out non-finite
    values with ``.filter(|value| value.is_finite() && *value >= 0.0)``
    and falls back to the unit default of ``1.0``. That silently turns
    an ``inf``-weighted edge into a ``1.0``-weighted edge, so the
    dijkstra kernel routes through it as if it were the cheapest path
    — diverging from nx, which correctly treats ``inf`` as "edge
    exists but is never relaxed" and routes around it via any finite
    alternative.

    The cleanest scoped fix is to detect ``+inf`` weights in the
    Python wrapper and delegate to nx (mirroring the existing
    ``-inf`` / negative-weight delegation path). Mutating the Rust
    helper would touch ~50 call sites across matching / mst /
    bellman-ford / flow algorithms, each with its own implicit
    contract about how the default kicks in.

    br-r37-c1-8cqeh: route the scan through the existing native
    ``graph_has_nonfinite_edge_weight`` helper for non-multigraphs.
    The native scan returns False fast for finite-only graphs (the
    common case), eliminating ~50 ms of Python iteration on
    BA5000-sized inputs. Only graphs with at least one non-finite
    weight pay the Python scan to disambiguate +inf from -inf/NaN.
    """
    if not isinstance(weight, str):
        return False
    # Fast path: native scan returns False for graphs whose every
    # weight attr value is finite — covers the common case and skips
    # the ~50 ms Python iteration entirely. Sync Python edge attrs
    # into the Rust inner graph first (post-creation
    # ``G[u][v]['weight'] = ...`` mutations don't otherwise reach the
    # native scan; see br-r37-c1-sjf4t for the sync helper rationale).
    # br-r37-c1-mgnegscan-8l53h: multigraph gate removed, same as in the
    # negative-weight guard. This runs on the same weighted shortest-path calls,
    # so leaving it gated would have kept the per-edge Python walk for both
    # multigraph classes and left the bead's actual cost in place. The
    # `_sync_rust_edge_attrs` call stays inside this branch and now applies to
    # multigraphs too, which is required: a post-creation `G[u][v]['weight'] = x`
    # does not otherwise reach the native scan.
    if _native_has_nonfinite_edge_weight is not None:
        if not _skip_sync:
            _sync_rust_edge_attrs(G)
        try:
            native = _native_has_nonfinite_edge_weight(G, weight)
        except Exception:
            native = None
        if native is False:
            return False
        # native is True or None — fall through to the Python scan
        # to specifically detect +inf (vs -inf / NaN).
    if G.is_multigraph():
        attrs_iter = (attrs for _, _, _, attrs in G.edges(keys=True, data=True))
    else:
        attrs_iter = (attrs for _, _, attrs in G.edges(data=True))
    # br-r37-c1-4m4wb REVERTED: this guard reads one key and `data=weight` would
    # avoid handing out live attr dicts (which permanently poisons the weighted
    # store, br-r37-c1-igdzi) -- but MEASURED, fnx's `edges(data=key)` costs
    # 2.88x its own `edges(data=True)` (7.27ms vs 2.52ms on 4000 edges), where
    # networkx charges 1.07x. The contamination fix was paid for with a 2.9x
    # slowdown on this scan, which is not a trade worth making blind. The
    # prerequisite is fixing `edges(data=key)` itself, which is 0.14x vs
    # networkx and a far larger loss than this guard's contamination.
    for attrs in attrs_iter:
        value = attrs.get(weight, 1)
        if isinstance(value, _numbers.Real) and not _math.isnan(value) and _math.isinf(value) and value > 0:
            return True
    return False


def _has_nonnumeric_edge_weight(G, weight, *, _skip_sync=False):
    """Detect non-numeric edge weight values (str, list, dict, None, etc.).

    br-r37-c1-djk-strw: when ``weight`` is a string but the actual
    value at that key on any edge is non-numeric, nx propagates a
    TypeError from the natural ``+`` operation in its accumulation
    loop.  The Rust dijkstra silently treats the value as 1.0,
    masking the type error.  Callers that pass garbage weights
    deserve to fail loudly.

    Notes on native helper: the Rust ``graph_has_nonfinite_edge_weight``
    cannot safely short-circuit this gate. Its ``as_f64()`` call
    accepts string-numeric values like ``"5"`` (parses to 5.0,
    considered finite) and therefore returns False on graphs whose
    Python weight attrs are strings — but the Python kernels then
    raise ``TypeError`` because ``int + "5"`` is not defined. So we
    *cannot* use the native False as evidence of no-nonnumeric. The
    Python scan must run.
    """
    if not isinstance(weight, str):
        return False
    # br-gauntlet-perf1: for simple Graph/DiGraph, route through the native
    # O(E) ``is_strictly_numeric()`` variant scan instead of materializing the
    # Python EdgeView edge-by-edge (the dominant cost in the weighted-Dijkstra
    # slowdown). The native helper checks the ``CgseValue`` variant (Bool/Int/
    # Float = numeric; String/Map = non-numeric), which matches this function's
    # ``bool or numbers.Real`` semantics exactly and — crucially — does NOT use
    # ``as_f64`` (so a string weight like ``"5"`` is correctly non-numeric).
    # Requires the Rust ``inner`` adjacency to be current; callers sync first
    # (``_skip_sync=True`` means the sync already ran). Multigraphs keep the
    # Python scan (no native multigraph variant).
    if (
        _native_has_nonnumeric_edge_weight is not None
        and not G.is_multigraph()
        and hasattr(G, "_fnx_sync_attrs_to_inner")
    ):
        if not _skip_sync:
            _sync_rust_edge_attrs(G)
        try:
            native = _native_has_nonnumeric_edge_weight(G, weight)
        except Exception:
            native = None
        if native is not None:
            return bool(native)
    if G.is_multigraph():
        attrs_iter = (attrs for _, _, _, attrs in G.edges(keys=True, data=True))
    else:
        attrs_iter = (attrs for _, _, attrs in G.edges(data=True))
    for attrs in attrs_iter:
        if not isinstance(attrs, dict) or weight not in attrs:
            continue
        value = attrs[weight]
        if isinstance(value, bool):
            # bools are ints; leave to the numeric path
            continue
        if not isinstance(value, _numbers.Real):
            return True
    return False


def _cached_native_weight_scan(
    G, weight, require_exact_string_nodes=False, rows_ok=False,
    *, allow_exact_integer_nodes=False
):
    """The native single-pass weight scan, ``(has_negative, has_nonfinite,
    has_nonnumeric)``, or None when it is unavailable or declines.

    br-gauntlet-perf1-fast: the scan skips the expensive _sync_rust_edge_attrs;
    live Python edge dicts are authoritative and lazy store-only multigraph attrs
    are read in the Rust store. It is O(E), so the answer is cached on the graph
    under its generation token while no Python edge dict is dirty.

    br-r37-c1-qnj0n: ONE cache for every gate that asks. The Dijkstra and
    Bellman-Ford gates each kept their own copy of this logic, and the
    type-parity gate had none, so every weighted Bellman-Ford call rescanned
    all E weights (17 ms beside a 32k-node component, before the walk began).

    br-r37-c1-svsam: with ``rows_ok`` a cache MISS returns ``_CHECK_ROWS``
    instead of scanning - the caller's native search then checks the weights
    on the rows it expands, which are the only weights networkx reads. The
    cache is keyed by revision, so every graph write missed it, and a bounded
    query after one write re-scanned all E weights (18 ms beside a 32k ring,
    against networkx's 13 us). A revision gets ``_ROW_CHECKS_PER_REVISION``
    such searches; after that the whole scan runs and is cached, so repeated
    queries on an unchanged graph go back to costing nothing here.
    """
    if _native_check_dijkstra_weights_fast is None:
        return None
    cache_key = None
    token = None
    if _native_dijkstra_weight_cache_token is not None:
        try:
            token = _native_dijkstra_weight_cache_token(G)
        except Exception:
            token = None
        if token is not None:
            # br-r37-c1-urjxk: the 4th slot moves on every store rewrite
            # from the attr dicts, so a synced held write is a new key.
            nodes_seq, edges_seq, edge_attrs_dirty, attr_rewrites = token
            if not edge_attrs_dirty:
                cache_key = (
                    weight,
                    nodes_seq,
                    edges_seq,
                    attr_rewrites,
                    require_exact_string_nodes,
                    allow_exact_integer_nodes,
                )
                cached = vars(G).get("_fnx_weight_scan_cache")
                if cached is not None and cached[0] == cache_key:
                    return cached[1]
    if rows_ok and token is not None and not getattr(_WEIGHT_ROWS, "full_scan", 0):
        revision = (weight, token[0], token[1], token[3])
        checks = vars(G).get("_fnx_weight_row_checks")
        count = checks[1] if checks is not None and checks[0] == revision else 0
        if count < _ROW_CHECKS_PER_REVISION:
            vars(G)["_fnx_weight_row_checks"] = (revision, count + 1)
            return _CHECK_ROWS
    try:
        scan = _native_check_dijkstra_weights_fast(
            G, weight, require_exact_string_nodes, allow_exact_integer_nodes
        )
    except Exception:
        scan = None
    if scan is not None and cache_key is not None:
        vars(G)["_fnx_weight_scan_cache"] = (cache_key, scan)
    return scan


def _should_delegate_dijkstra_to_networkx(
    G, weight, *, _require_exact_string_nodes=False, _allow_exact_integer_nodes=False
):
    if callable(weight):
        return True
    if not isinstance(weight, str):
        return True
    scan = _cached_native_weight_scan(
        G, weight, _require_exact_string_nodes,
        allow_exact_integer_nodes=_allow_exact_integer_nodes,
    )
    if scan is not None:
        has_negative, has_nonfinite, has_nonnumeric = scan
        return bool(has_negative or has_nonfinite or has_nonnumeric)
    # Native-helper fallback: retain the established shared MultiGraph scan
    # unless the bidirectional-only exact-domain flag is set. In that domain,
    # only exact built-in bool/int/float weights within the f64 exact-integer
    # envelope may enter the native kernel; custom numerics, non-finite values,
    # and non-string attr keys retain NetworkX as the authority.
    if G.is_multigraph():
        if not _require_exact_string_nodes:
            # Preserve the established shared fallback for unrelated
            # MultiGraph Dijkstra APIs when the native helper is unavailable.
            for _u, _v, _k, _attrs in G.edges(keys=True, data=True):
                if isinstance(_attrs, dict) and weight in _attrs:
                    _raw = _attrs[weight]
                    if not isinstance(_raw, bool) and not isinstance(
                        _raw, _numbers.Real
                    ):
                        return True
                _value = _attrs.get(weight, 1)
                # br-r37-c1-kn5cu: NaN DELEGATES, and this is the root of the
                # bead. `and not _math.isnan(_value)` excluded NaN from the
                # question entirely, so this predicate answered False for a
                # multigraph carrying one - while the simple classes answered
                # True, because their gate runs through the native scan's
                # non-finite flag. Every dijkstra entry point that asks this
                # question then handed the graph to a native kernel that
                # substitutes the DEFAULT WEIGHT 1 for a NaN, which is how
                # `single_source_dijkstra_path_length` returned 1.0 and 2.0
                # where networkx returns nan and nan.
                #
                # The exact-domain multigraph branch immediately below has
                # always been right (`not _math.isfinite(_raw)` covers NaN), so
                # the two halves of the same predicate disagreed about the same
                # weight depending on a flag that has nothing to do with weights.
                if isinstance(_value, _numbers.Real):
                    if _math.isnan(_value):
                        return True
                    if _value < 0 or (_math.isinf(_value) and _value > 0):
                        return True
            return False
        _node_types = (str, int) if _allow_exact_integer_nodes else (str,)
        if G._native_has_adj_py_keys() or any(type(_node) not in _node_types for _node in G):
            return True
        _max_path_edges = max(1, len(G) - 1)
        for _u, _v, _k, _attrs in G.edges(keys=True, data=True):
            if any(type(_key) is not str for _key in _attrs):
                return True
            if weight in _attrs:
                _raw = _attrs[weight]
                if type(_raw) is bool:
                    continue
                if type(_raw) is int:
                    if _raw < 0 or abs(_raw) * _max_path_edges > 2**53:
                        return True
                    continue
                if type(_raw) is float:
                    if _raw < 0 or not _math.isfinite(_raw):
                        return True
                    continue
                # NetworkX preserves arithmetic and result types for custom
                # numeric objects; the native Cgse/f64 path cannot.
                return True
        return False
    # Non-multigraph fallback: sync once, then run three gates with _skip_sync
    # (each has its own native fast path for simple graphs).
    _sync_rust_edge_attrs(G)
    if _has_negative_edge_weight_for_dijkstra(G, weight, _skip_sync=True):
        return True
    if _has_positive_infinity_edge_weight_for_dijkstra(G, weight, _skip_sync=True):
        return True
    if _has_nonnumeric_edge_weight(G, weight, _skip_sync=True):
        return True
    return False


def _networkx_graph_for_dijkstra_parity(G):
    if (
        type(G) not in (Graph, DiGraph)
        or _native_dijkstra_weight_cache_token is None
    ):
        return _networkx_graph_for_parity(G)
    try:
        token = _native_dijkstra_weight_cache_token(G)
    except Exception:
        token = None
    if token is None:
        return _networkx_graph_for_parity(G)
    nodes_seq, edges_seq, edge_attrs_dirty, attr_rewrites = token
    if edge_attrs_dirty:
        return _networkx_graph_for_parity(G)
    cache_key = (type(G), nodes_seq, edges_seq, attr_rewrites)
    cached = vars(G).get("_fnx_dijkstra_nx_graph_cache")
    if cached is not None and cached[0] == cache_key:
        return cached[1]
    graph = _networkx_graph_for_parity(G)
    vars(G)["_fnx_dijkstra_nx_graph_cache"] = (cache_key, graph)
    return graph


def _sync_rust_edge_attrs(G, *, edge_only=False):
    """br-r37-c1-sjf4t: push Python-visible edge/node attribute dicts
    back into the Rust ``inner`` graph so native algorithms see
    post-creation mutations.

    The Python edge dict (returned by ``G[u][v]``) is the same
    persistent ``Py<PyDict>`` stored in ``edge_py_attrs``, so user
    mutations like ``G[u][v]['weight'] = 1.5`` or ``attrs[k] = v``
    inside ``for u,v,attrs in G.edges(data=True)`` ARE visible to the
    Python side. They are however invisible to the Rust ``inner``
    graph's parallel ``AttrMap`` storage (used by Rust algorithm
    kernels). This helper rebuilds ``inner``'s AttrMap from the Python
    dicts, eliminating the need for the ``_graph_has_nonunit_weight``
    nx-fallback that previously defended against the staleness bug.

    Cost is O(E + N). For shortest-path algorithms (E log N or worse),
    this does not change asymptotic complexity, but does eliminate
    the catastrophic perf hit of the nx fallback.

    Caller is responsible for invoking this before any Rust kernel
    that reads attrs — it cannot be called from the Rust side without
    a ``&mut PyGraph`` reference, which the algorithm bindings do not
    have.

    br-r37-c1-z9lpk: thread-safety. The PyO3 ``&mut self`` borrow on
    ``_fnx_sync_attrs_to_inner`` is exclusive — concurrent calls from
    Python threads (with the GIL released inside ``py.allow_threads``
    by the algorithm kernel that *we* are about to invoke) collide
    on the borrow and raise ``RuntimeError: Already borrowed``.

    Catch that race and treat it as benign: if another thread is
    holding the borrow it is *also* syncing the same Python attr
    dicts, so the resulting Rust state after that thread finishes is
    identical to what we would have written. Spin briefly with a
    bounded retry to give the holder time to drop the borrow, then
    proceed without sync (any subsequent algorithm read will see the
    other thread's sync result, which is correct for the same input
    Python state).
    """
    sync = None
    if edge_only:
        sync = getattr(G, "_fnx_sync_edge_attrs_to_inner", None)
    if not callable(sync):
        sync = getattr(G, "_fnx_sync_attrs_to_inner", None)
    if not callable(sync):
        return
    # br-syncdirty (cc): if a cached scipy PageRank matrix exists AND the edge
    # attrs are dirty, this sync is about to flush Python-side mutations
    # (``G[u][v]['weight'] = w``) into ``inner``. The cached CSR was built from the
    # pre-flush state and is now stale, so drop it; the next consumer rebuilds from
    # the freshly synced ``inner``. This also closes a pre-existing correctness gap
    # (present for undirected Graph too): the matrix cache key tracks structure
    # (nodes_seq/edges_seq), not attr VALUES, so its invalidation had silently
    # relied on ``edges_dirty`` never being cleared — once we clear it (so repeat
    # weighted calls stay fast) the cache must be invalidated explicitly here. Gated
    # on the cache already existing, so graphs that never ran PageRank pay nothing.
    if _native_dijkstra_weight_cache_token is not None:
        gd = vars(G)
        if "_fnx_pagerank_scipy_matrix_cache" in gd:
            try:
                _tok = _native_dijkstra_weight_cache_token(G)
            except Exception:
                _tok = None
            if _tok is None or _tok[2]:
                gd.pop("_fnx_pagerank_scipy_matrix_cache", None)
    # Retry budget: a sync of a 200-node path graph takes well under
    # a millisecond, so even 8 yields is enough to win the race in
    # practice without risking lockup if the holder is genuinely slow.
    for _ in range(8):
        try:
            sync()
            return
        except RuntimeError as exc:
            if "Already borrowed" not in str(exc):
                raise
            # Yield to the holder; once it drops the &mut borrow we
            # can re-acquire. Pure Python "yield" via a no-op sleep
            # releases the GIL and lets the other thread progress.
            import time as _time
            _time.sleep(0)
    # Last-ditch: bail out without sync. Another thread's sync of the
    # same Python attr dicts has been or will be applied — the Rust
    # state will reflect the user's Python edits either way.


def _graph_has_nonunit_weight(G, weight):
    """br-dijkignoreweight (historical): originally signaled "Rust
    saw stale weights, fall back to nx". Now superseded by
    :func:`_sync_rust_edge_attrs` (br-r37-c1-sjf4t).

    The function is preserved for any external callers but its body
    is now: sync the Python attrs into the Rust ``inner`` graph and
    return ``False`` (no fallback needed). The Rust kernel sees fresh
    data and produces the correct weighted distances.

    NOTE: callers whose native kernel does NOT self-sync (e.g.
    ``_raw_cut_size`` / ``_raw_normalized_cut_size``) RELY on this sync
    side effect — keep using this gate for them. Callers whose binding
    self-syncs via ``sync_rust_attrs_if_available`` should use the
    cheaper :func:`_binding_self_syncs_gate` instead (br-r37-c1-tqqzq).
    """
    _sync_rust_edge_attrs(G)
    return False


def _binding_self_syncs_gate(G, weight):
    """No-op delegation gate (always ``False``, NO sync) — br-r37-c1-tqqzq.

    Use ONLY in shortest-path wrappers whose native binding already calls
    ``sync_rust_attrs_if_available`` (the identical ``_fnx_sync_attrs_to_inner``
    pessimistic re-sync) before reading ``inner``. For those, the historical
    ``_graph_has_nonunit_weight`` gate performed a redundant SECOND full
    O(E+N) AttrMap rebuild on every call — a provable double-sync (no Python
    runs between the two syncs). Dropping it is byte-identical for default and
    custom weight names, including post-construction weight mutation, while the
    binding's own re-sync preserves the held-reference mutation contract.
    Self-speedup ~1.4x on voronoi_cells / multi_source_dijkstra_path /
    single_source_bellman_ford / all_pairs_bellman_ford.

    Do NOT use for kernels that do NOT self-sync (``_raw_cut_size`` etc.).
    """
    return False


def _graph_has_explicit_nonunit_weight(G, weight):
    if not isinstance(weight, str):
        return True
    if (
        _native_has_explicit_nonunit_weight_fast is not None
        and type(G) in (Graph, DiGraph)
    ):
        try:
            native = _native_has_explicit_nonunit_weight_fast(G, weight)
        except Exception:
            native = None
        if native is not None:
            return bool(native)
    for edge in G.edges(data=True):
        attrs = edge[-1]
        if not isinstance(attrs, dict) or weight not in attrs:
            continue
        try:
            if attrs[weight] != 1:
                return True
        except Exception:
            return True
    return False


def _has_nan_or_inf_edge_weight(G, weight):
    """Detect NaN or +/-inf numeric edge weights at ``weight`` key.

    br-r37-c1-bfnannumeric: nx's bellman-ford uses ``candidate < current``
    on every relaxation step, and ``candidate < inf`` is False for NaN
    (so NaN edges never relax → unreachable) and False for ``inf``
    (likewise).  fnx's Rust impl writes NaN through to the distance
    map as a first-visit value (because ``current is None`` was the
    only short-circuit), and returned ``inf`` / ``-inf`` paths instead
    of treating them as unreachable / negative-cycle.  Delegating to
    nx when any edge carries NaN / inf restores parity in one shot.
    """
    if not isinstance(weight, str):
        return False
    if G.is_multigraph():
        attrs_iter = (attrs for _, _, _, attrs in G.edges(keys=True, data=True))
    else:
        attrs_iter = (attrs for _, _, attrs in G.edges(data=True))
    for attrs in attrs_iter:
        if not isinstance(attrs, dict) or weight not in attrs:
            continue
        value = attrs[weight]
        if isinstance(value, bool):
            continue
        if isinstance(value, float) and (_math.isnan(value) or _math.isinf(value)):
            return True
    return False
