

_digraph_private_adj_view = _cached_view(
    "_fnx_priv_adj",
    lambda self: _private_marked(
        _private_writable_class(_DIGRAPH_NATIVE_LEN_ADJ_VIEW)(
            lambda: _DIGRAPH_ADJ_DESCRIPTOR.__get__(self, DiGraph),
            owner=self,
            row_kind="succ",
            native_len=_DIGRAPH_ADJ_NATIVE_LEN.__get__(self, DiGraph),
            native_iter=_DIGRAPH_ADJ_NATIVE_ITER.__get__(self, DiGraph),
        ),
        self,
        "succ",
    ),
)


_digraph_private_succ_view = _cached_view(
    "_fnx_priv_succ",
    lambda self: _private_marked(
        _private_writable_class(AdjacencyView)(
            lambda: _DIGRAPH_SUCC_DESCRIPTOR.__get__(self, DiGraph),
            owner=self,
            row_kind="succ",
            native_len=_DIGRAPH_ADJ_NATIVE_LEN.__get__(self, DiGraph),
            native_iter=_DIGRAPH_ADJ_NATIVE_ITER.__get__(self, DiGraph),
        ),
        self,
        "succ",
    ),
)


_digraph_private_pred_view = _cached_view(
    "_fnx_priv_pred",
    lambda self: _private_marked(
        _private_writable_class(AdjacencyView)(
            lambda: _DIGRAPH_PRED_DESCRIPTOR.__get__(self, DiGraph),
            owner=self,
            row_kind="pred",
            native_len=_DIGRAPH_ADJ_NATIVE_LEN.__get__(self, DiGraph),
            native_iter=_DIGRAPH_ADJ_NATIVE_ITER.__get__(self, DiGraph),
        ),
        self,
        "pred",
    ),
)


_multigraph_private_adj_view = _cached_view(
    "_fnx_priv_adj",
    lambda self: _private_marked(
        _private_writable_class(_MULTIGRAPH_NATIVE_LEN_ADJ_VIEW)(
            lambda: _MULTIGRAPH_ADJ_DESCRIPTOR.__get__(self, MultiGraph),
            owner=self,
            native_iter=_MULTIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiGraph),
            native_contains=_MULTIGRAPH_ADJ_NATIVE_CONTAINS.__get__(self, MultiGraph),
            native_len=_MULTIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiGraph),
        ),
        self,
    ),
)


_multidigraph_private_adj_view = _cached_view(
    "_fnx_priv_adj",
    lambda self: _private_marked(
        _private_writable_class(_MULTIDIGRAPH_NATIVE_LEN_ADJ_VIEW)(
            lambda: _MULTIDIGRAPH_ADJ_DESCRIPTOR.__get__(self, MultiDiGraph),
            owner=self,
            row_kind="succ",
            native_iter=_MULTIDIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiDiGraph),
            native_contains=_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS.__get__(
                self, MultiDiGraph
            ),
            native_len=_MULTIDIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiDiGraph),
        ),
        self,
        "succ",
    ),
)


_multidigraph_private_succ_view = _cached_view(
    "_fnx_priv_succ",
    lambda self: _private_marked(
        _private_writable_class(MultiAdjacencyView)(
            lambda: _MULTIDIGRAPH_SUCC_DESCRIPTOR.__get__(self, MultiDiGraph),
            owner=self,
            row_kind="succ",
            native_iter=_MULTIDIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiDiGraph),
            native_contains=_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS.__get__(
                self, MultiDiGraph
            ),
            native_len=_MULTIDIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiDiGraph),
        ),
        self,
        "succ",
    ),
)


_multidigraph_private_pred_view = _cached_view(
    "_fnx_priv_pred",
    lambda self: _private_marked(
        _private_writable_class(MultiAdjacencyView)(
            lambda: _MULTIDIGRAPH_PRED_DESCRIPTOR.__get__(self, MultiDiGraph),
            owner=self,
            row_kind="pred",
            native_iter=_MULTIDIGRAPH_ADJ_NATIVE_ITER.__get__(self, MultiDiGraph),
            native_contains=_MULTIDIGRAPH_ADJ_NATIVE_CONTAINS.__get__(
                self, MultiDiGraph
            ),
            native_len=_MULTIDIGRAPH_ADJ_NATIVE_LEN.__get__(self, MultiDiGraph),
        ),
        self,
        "pred",
    ),
)


def _graph_getitem_from_adj(self, node):
    # br-r37-c1-spg9n: warm fast-path for G[node]. A graph-level
    # (nodes_seq, {node: AtlasView}) cache returns the row view directly,
    # skipping the per-call ``self.adj`` descriptor resolution + AdjacencyView
    # dispatch (6x slower than nx -> parity). The AtlasView live-reads its row,
    # so it survives edge churn; nodes_seq drops it on node add/remove.
    # ``cache.get(node)`` hashes node (TypeError on unhashable, like nx); cold
    # misses go through ``self.adj[node]``, which raises KeyError(node) with the
    # original key object (br-keystr) — so no try/except is needed here.
    cache = self.__dict__.get("_fnx_getitem_atlas_cache")
    seq = self.nodes_seq
    if cache is None or cache[0] != seq:
        cache = (seq, {})
        self.__dict__["_fnx_getitem_atlas_cache"] = cache
    view = cache[1].get(node)
    if view is not None:
        return view
    view = self.adj[node]
    cache[1][node] = view
    return view


def _multigraph_getitem_from_native_row(self, node):
    if type(self) is not MultiGraph:
        return _graph_getitem_from_adj(self, node)
    # br-r37-c1-fy913: the row wrapper remains live across edge churn, so reuse
    # it exactly as the simple-graph path above does.  Node mutations advance
    # nodes_seq and discard the cache before the next lookup.
    storage = vars(self)
    cache = storage.get("_fnx_getitem_atlas_cache")
    seq = self.nodes_seq
    if cache is None or cache[0] != seq:
        # br-r37-c1-gcreg: register only when we actually PUT something in the
        # instance dict. This ran on every `G[n]` including cache hits, and
        # `_fnx_register_gc_dict(vars(self))` re-registers the same dict object
        # every time - the identical per-call bookkeeping that made freeze()
        # 0.0768x (br-r37-c1-frzsetattr). On a hit there is nothing new to
        # track, so the registration belongs on the miss branch beside the
        # assignment it exists for.
        cache = (seq, {})
        storage["_fnx_getitem_atlas_cache"] = cache
        self._fnx_register_gc_dict(storage)
        self._fnx_set_getitem_row_cache(seq, cache[1])
    view = cache[1].get(node)
    if view is not None:
        return view
    # br-r37-c1-2r06n: assigned private storage is the authority, and the native
    # row below cannot see it — `G['ZZ']` raised KeyError for a node carried only
    # by an assigned `_adj`, where the simple classes answer it because their
    # `_graph_getitem_from_adj` reads the private-aware `self.adj[node]`.
    #
    # Placed AFTER the cache probe on purpose: the warm path — the same node
    # looked up again — returns above and pays nothing for this. Only a MISS,
    # which already costs a native call, tests the two keys, and `storage` is a
    # dict already in hand.
    #
    # The private result is deliberately NOT cached. The assigned mapping is an
    # ordinary dict the caller may mutate, and this cache is keyed on nodes_seq,
    # which such a mutation does not advance; a cached row would go stale with
    # nothing to invalidate it. `_set_private_override` also drops this cache, so
    # a row cached BEFORE the assignment cannot be served afterwards.
    if (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _SHARED_STORAGE_SOURCE in storage
    ):
        return self.adj[node]
    try:
        row = self._native_adjacency_row(node)
    except KeyError as exc:
        raise KeyError(node) from exc
    # br-r37-c1-124xl: CAPTURE the row instead of re-fetching it. The fetch
    # above already had to happen (it is what raises KeyError for a missing
    # node), and the object it returns is a native MultiAtlasView that stays
    # LIVE across edge churn — verified: a captured row sees a later add_edge
    # and remove_edge. The previous lambda called back into
    # `_native_adjacency_row` on EVERY access of this cached wrapper, so a
    # single `len(G[u][v])` crossed the PyO3 boundary twice for one row.
    # Node mutation still advances nodes_seq and drops the wrapper cache above,
    # which is what keeps a captured row from outliving its node.
    view = AdjacencyView(
        lambda row=row: row,
        multi_edge_owner=self,
        native_iter=lambda graph=self, n=node: graph._native_neighbors_iter(n),
    )
    # br-r37-c1-2ndmw: br-r37-c1-fr4me added `_fnx_captured_row` and wired it on
    # the `G.adj[u]` row builder but NOT here on `G[u]`, so the two spellings of
    # the same row disagreed and the `G[u][v]` form kept paying `_atlas()` plus
    # the constant lambda on every cell lookup. The getter above is a closure
    # over a FIXED object, which is exactly the precondition that attribute
    # documents.
    view._fnx_captured_row = row
    cache[1][node] = view
    _register_held_multigraph_row(self, node, view)
    return view


def _digraph_getitem_from_native_row(self, node):
    if type(self) is not DiGraph or _has_networkx_private_storage(self):
        return _graph_getitem_from_adj(self, node)
    _HASH_PROBE.get(node)
    try:
        self._native_adjacency_dict()[node]
    except KeyError as exc:
        raise KeyError(node) from exc
    return AtlasView(lambda: self._native_adjacency_dict()[node])


def _multidigraph_getitem_from_native_row(self, node):
    if type(self) is not MultiDiGraph:
        return _graph_getitem_from_adj(self, node)
    # Directed sibling of br-r37-c1-fy913.  The cached AdjacencyView calls the
    # native successor-row binding lazily, so structural edge updates stay live.
    storage = vars(self)
    cache = storage.get("_fnx_getitem_atlas_cache")
    seq = self.nodes_seq
    if cache is None or cache[0] != seq:
        # br-r37-c1-gcreg: register only when we actually PUT something in the
        # instance dict. This ran on every `G[n]` including cache hits, and
        # `_fnx_register_gc_dict(vars(self))` re-registers the same dict object
        # every time - the identical per-call bookkeeping that made freeze()
        # 0.0768x (br-r37-c1-frzsetattr). On a hit there is nothing new to
        # track, so the registration belongs on the miss branch beside the
        # assignment it exists for.
        cache = (seq, {})
        storage["_fnx_getitem_atlas_cache"] = cache
        self._fnx_register_gc_dict(storage)
        self._fnx_set_getitem_row_cache(seq, cache[1])
    view = cache[1].get(node)
    if view is not None:
        return view
    # br-r37-c1-2r06n: the directed twin of the note in the undirected version —
    # same authority, same cache-miss placement, same reason for not caching the
    # private result. `_succ` counts here as well as `_adj`, since `G[n]` on a
    # directed graph reads the successor side.
    if (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _SHARED_STORAGE_SOURCE in storage
    ):
        return self.adj[node]
    try:
        row = self._native_successor_row(node)
    except KeyError as exc:
        raise KeyError(node) from exc
    # br-r37-c1-124xl: capture the row, as the undirected twin does. The fetch
    # above already happened to raise KeyError for a missing node, and the
    # native successor row stays live across edge churn.
    view = AdjacencyView(
        lambda row=row: row,
        row_kind="succ",
        multi_edge_owner=self,
        native_iter=lambda graph=self, n=node: graph._native_neighbors_iter(n),
    )
    # br-r37-c1-2ndmw: directed twin of the capture note in the undirected
    # builder — the same missing wiring, and the same reason it is sound here.
    view._fnx_captured_row = row
    cache[1][node] = view
    _register_held_multigraph_row(self, node, view)
    return view


_fnx._set_multigraph_getitem_fallbacks(
    _multigraph_getitem_from_native_row,
    _multidigraph_getitem_from_native_row,
)


def _to_directed_class(self):
    return MultiDiGraph if self.is_multigraph() else DiGraph


def _to_undirected_class(self):
    return MultiGraph if self.is_multigraph() else Graph


def _multigraph_new_edge_key(self, u, v):
    try:
        keydict = self.adj[u][v]
    except KeyError:
        return 0
    key = len(keydict)
    while key in keydict:
        key += 1
    return key


def _multigraph_edge_subgraph(self, edges):
    return edge_subgraph(self, edges)


def _direct_multi_edge_iter(view, exact_graph_type):
    """Reuse the private keyed-edge materialization for direct view iteration.

    ``MultiEdgeView.__iter__`` yields keyed triples, so the former path called
    ``view(keys=True)`` on every iterator creation.  The Rust tuple cache made
    tuple construction cheap, but crossing it still cloned every tuple
    reference into two fresh list wrappers before the first ``next()``.

    Keep one guarded list private to the graph and invalidate it with the same
    structural sequence pair as the native keyed-tuple cache.  Public
    ``edges(keys=True)`` calls remain fresh lists, and private-storage graphs or
    subclasses retain the generic materialization path.
    """
    graph = view._graph
    if (
        type(graph) is exact_graph_type
        and not _has_networkx_private_storage(graph)
    ):
        state = (graph.nodes_seq, graph.edges_seq)
        graph_vars = vars(graph)
        cached = graph_vars.get("_fnx_direct_multi_edge_iter_cache")
        if cached is None or cached[0] != state:
            # This is deliberately the native keyed materialization rather
            # than ``view(keys=True)``.  The public no-nbunch keyed call is
            # the view itself, as it is in NetworkX; refilling this private
            # iterator cache through that public call would therefore recurse
            # through ``MultiEdgeView.__iter__``.
            cached = (state, graph._native_edge_view_list(False, True, None))
            graph_vars["_fnx_direct_multi_edge_iter_cache"] = cached
        return _FailFastEdgeIterator(
            graph,
            iter(cached[1]),
            guard_edge_count=True,
        )
    return _FailFastEdgeIterator(
        graph,
        view(keys=True),
        guard_edge_count=True,
    )


class _DiGraphEdgeView(_fnx.DiEdgeView):
    _fnx_edge_kind = "out"  # br-r37-c1-ex1s6: see _nx_edge_view_contains

    def __init__(self, graph):
        self._graph = graph

    def __getnewargs__(self):
        return (self._graph,)

    def _materialize(self):
        # br-r37-c1-acuub: native ordered no-data edge materialization. The
        # Rust helper walks node order then successor insertion order, matching
        # the loop this replaces while avoiding Python AtlasView traversal.
        return self._graph._native_edges_no_data()

    def __iter__(self):
        # br-r37-c1-msf5j: walk adj directly so __call__ can return
        # self (a live view) without causing __iter__ → __call__
        # recursion when called with default args.
        native_stream = getattr(self._graph, "_native_guarded_edge_stream_iter", None)
        if native_stream is not None and not _has_networkx_private_storage(self._graph):
            stream = native_stream()
            if stream is not None:
                return stream
        native_iter = getattr(self._graph, "_native_guarded_edge_list_iter", None)
        if native_iter is not None and not _has_networkx_private_storage(self._graph):
            return native_iter(self._materialize())
        return _FailFastEdgeIterator(
            self._graph,
            self._materialize(),
            guard_edge_count=True,
        )

    def __len__(self):
        return self._graph.number_of_edges()

    def __contains__(self, edge):
        # br-r37-c1-edgeviewcontains: nx.OutEdgeView.__contains__ does
        # ``u, v = e`` (no slice) and only catches KeyError, so non-2-
        # element iterables raise ValueError and non-iterables raise
        # TypeError.  fnx previously used ``e[:2]`` and caught both
        # TypeError and ValueError, returning False — too lenient.
        u, v = edge
        # br-r37-c1-lvlu7: TypeError is NOT caught. nx is
        # `return v in self._adjdict[u]` inside `except KeyError`, so an
        # unhashable endpoint raises out of the dict. `has_edge` hashes `u`
        # first and answers False for an absent `u` without touching `v`, which
        # is what keeps `("missing", Unhashable()) in D.edges` False.
        try:
            return self._graph.has_edge(u, v)
        except KeyError:
            return False

    def __call__(self, nbunch=None, data=False, default=None):
        # br-r37-c1-msf5j: when called with default args, return self
        # so the resulting "view" stays live with respect to subsequent
        # graph mutations — matches nx's OutEdgeView.__call__ contract:
        #
        #   v = G.edges(); G.add_edge(...); list(v)  # sees the new edge
        #
        # The data/nbunch-filtered paths still snapshot to a list (a
        # full EdgeDataView would be needed for live data views; out of
        # scope here, and nx's EdgeDataView is also itself snapshot-ish
        # in practice for many of its consumers).
        if nbunch is None and data is False:
            return self
        # br-r37-c1-deg-data: all-edges data=True routes to the native
        # (u, v, attrs) builder (same node x successor order, live attr dicts)
        # instead of the per-source succ[source].items() AtlasView walk (~58x).
        if nbunch is None and data is True:
            native = getattr(self._graph, "_native_edges_with_data", None)
            if native is not None:
                # br-r37-c1-pdkrl: nx returns OutEdgeDataView (not OutEdgeView)
                # for every edges() form except the bare live view, so wrap the
                # materialised result so type(view).__name__ matches nx.
                return _guarded_edge_list(
                    _wrap_edge_data_view(native(), _OutEdgeDataView),
                    self._graph,
                    guard_edge_count=True,
                )
        # br-r37-c1-deg-datakey: all-edges data=<key> (e.g. data='weight')
        # routes to the native (u, v, attrs.get(key, default)) builder instead
        # of the per-source succ[source].items() AtlasView walk (~40x). data is
        # a key here (not the True/False sentinels).
        if nbunch is None and data is not False and data is not True:
            native = getattr(self._graph, "_native_edges_data_key", None)
            if native is not None:
                return _guarded_edge_list(
                    _wrap_edge_data_view(native(data, default), _OutEdgeDataView),
                    self._graph,
                    guard_edge_count=False,
                )
        # br-r37-c1-lfpma: directed ``edges(nbunch, ...)`` is out-edge
        # iteration, but this call form still walked Python succ rows while
        # ``out_edges(nbunch, ...)`` already has native iterable-nbunch kernels.
        # Reuse those kernels for exact DiGraph only; single-node nbunch and
        # conversion/subgraph views keep the Python nbunch_iter path.
        iterable_nbunch = nbunch is not None and _nbunch_is_iterable_bunch(
            self._graph, nbunch
        )
        # br-r37-c1-124sk: the native nbunch kernels below are O(V) — they cost
        # the same whether you ask for one row or all of them, so at n=8000 a
        # ONE-node nbunch takes 61us where networkx takes 2.3us and the ratio
        # falls without bound (0.35x at n=250, 0.034x at n=8000). For a small
        # nbunch, walk the cached succ rows instead: they are the same live
        # PyDict mirrors Graph's adjacency rows are, so this is O(rows asked
        # for) like networkx, with no PyO3 crossing when warm.
        if (
            type(self._graph) is DiGraph
            and iterable_nbunch
            and (data is False or data is True)
            and isinstance(nbunch, (list, tuple))
            and len(nbunch) <= _EDGES_NBUNCH_PY_WALK_MAX
        ):
            rows = []
            for source in nbunch:
                # br-r37-c1-w5sa7: an UNHASHABLE nbunch element is nx's
                # NetworkXError, not a silent skip. fnx's `in` swallows the
                # TypeError and answers False, so without this the walk dropped
                # the bad element and returned a short answer.
                try:
                    _HASH_PROBE.get(source)
                except TypeError:
                    raise NetworkXError(
                        f"Node {source} in sequence nbunch is not a valid node."
                    )
                if source not in self._graph:
                    continue
                row = _cached_adj_row_keydict(
                    self._graph, "succ", source, lambda: self._graph.succ[source]
                )
                if row is None:
                    rows = None
                    break
                rows.append((source, row))
            if rows is not None:
                if data is True:
                    walked = [(u, v, attrs) for u, row in rows for v, attrs in row.items()]
                else:
                    walked = [(u, v) for u, row in rows for v in row]
                return _guarded_edge_list(
                    _wrap_edge_data_view(walked, _OutEdgeDataView),
                    self._graph,
                    guard_edge_count=True,
                    nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                )
        if type(self._graph) is DiGraph and iterable_nbunch and (data is False or data is True):
            native_name = (
                "_native_out_edges_nbunch_data"
                if data is True
                else "_native_out_edges_nbunch_no_data"
            )
            native = getattr(self._graph, native_name, None)
            if native is not None:
                try:
                    if data is True:
                        native_result = _digraph_out_edges_data_cache(
                            self._graph, nbunch, native
                        )
                    else:
                        native_result = _nbunch_data_cache(
                            self._graph, "_fnx_out_edges_nb_nodata_cache",
                            nbunch, native,
                        )
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_result is not None:
                    return _guarded_edge_list(
                        _wrap_edge_data_view(native_result, _OutEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        if (
            type(self._graph) is DiGraph
            and iterable_nbunch
            and data is not False
            and data is not True
        ):
            native = getattr(self._graph, "_native_out_edges_nbunch_data_key", None)
            if native is not None:
                try:
                    # br-r37-c1-p1tyz: values are not memoized (they go stale).
                    native_result = native(nbunch, data, default)
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_result is not None:
                    return _guarded_edge_list(
                        _wrap_edge_data_view(native_result, _OutEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        result = []
        for source in self._graph.nbunch_iter(nbunch):
            for target, attrs in self._graph.succ[source].items():
                if data is True:
                    result.append((source, target, attrs))
                elif data is False:
                    result.append((source, target))
                else:
                    result.append((source, target, attrs.get(data, default)))
        # br-r37-c1-pdkrl: this path is only reached for nbunch-filtered or
        # data-bearing calls (the bare ``edges()`` returned ``self`` above), all
        # of which nx types as OutEdgeDataView.
        # br-r37-c1-8c7m5: ALL FOUR nbunch returns above and this one carry
        # `nbunch_rows`. None of them did, and the multigraph views beside them
        # have passed it on every return since br-r37-c1-hihrf — the classic
        # N-1-of-N family split, with the directed simple class as the laggard.
        #
        # Without it `_FailFastEdgeIterator` falls to its COARSE guard, which
        # asks "did ANYTHING change" rather than networkx's "was the row I am
        # standing in resized". That is not a subtle difference: it raised
        # RuntimeError for `G.add_node('zz')` and for removing an unrelated
        # node, both of which networkx completes straight through. The
        # `data=False`/`data=True` spellings hid it because the decorator gives
        # them a live-row walk that skips the guard entirely; `data=<key>` has
        # no such walk and took the coarse path alone.
        #
        # `_resolved_nbunch_rows` returns None for a None nbunch, so the
        # no-nbunch callers that reach this same return are unaffected.
        return _guarded_edge_list(
            _wrap_edge_data_view(result, _OutEdgeDataView),
            self._graph,
            guard_edge_count=True,
            nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
        )

    def __or__(self, other):
        return set(self) | set(other)

    def __and__(self, other):
        return set(self) & set(other)

    def __sub__(self, other):
        return set(self) - set(other)

    def __xor__(self, other):
        return set(self) ^ set(other)

    def __eq__(self, other):
        # br-r37-c1-eveq: nx's OutEdgeView inherits from _Set, so
        # `DG.edges == DG.edges` is True (content-based) and
        # `DG.edges == set_of_edges` works. fnx's _DiGraphEdgeView
        # had set-algebra operators (|/&/-/^) but no __eq__, falling
        # through to default object.__eq__ (identity) — two accesses
        # to `DG.edges` returned False, breaking dedup / set-equality
        # logic. Match nx's _Set semantics: equal to another view of
        # the same edges OR any collections.abc.Set with matching
        # contents. NOT equal to lists/tuples (parity with nx).
        from collections.abc import Set as _Set
        if isinstance(other, _DiGraphEdgeView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    # br-r37-c1-viewhash: nx's OutEdgeView / MultiEdgeView /
    # OutMultiEdgeView all inherit from ``collections.abc.Mapping``
    # (``__hash__ = None``), so ``hash(G.edges)`` raises TypeError.
    # fnx previously returned ``id(self._graph)`` here, silently
    # accepting the view as hashable — diverging on a contract that
    # drop-in callers rely on (``except TypeError: ...`` around
    # accidental view-in-set patterns).
    __hash__ = None

    # br-r37-c1-iev-setops: see _DiEdgeMethodView. _Set comparison
    # operators (`<=`, `<`, `>=`, `>`, isdisjoint) — the existing
    # __or__/__and__/__sub__/__xor__ already exist; this just adds
    # the comparison + isdisjoint set.
    def __le__(self, other):
        return set(self) <= set(other) if hasattr(other, "__iter__") else NotImplemented

    def __lt__(self, other):
        return set(self) < set(other) if hasattr(other, "__iter__") else NotImplemented

    def __ge__(self, other):
        return set(self) >= set(other) if hasattr(other, "__iter__") else NotImplemented

    def __gt__(self, other):
        return set(self) > set(other) if hasattr(other, "__iter__") else NotImplemented

    def isdisjoint(self, other):
        return set(self).isdisjoint(other)


def _digraph_edges(self):
    return _DiGraphEdgeView(self)


def _multi_edge_keys(self):
    # Upstream MultiEdgeView yields (u, v, k) keys for the _Mapping contract.
    return iter(self(keys=True))


def _multi_edge_items(self):
    # Each (u, v, k) key maps to the corresponding edge attrs dict.
    return ((key, self[key]) for key in self.keys())


def _multi_edge_values(self):
    return (self[key] for key in self.keys())


def _multi_edge_get(self, key, default=None):
    try:
        return self[key]
    except KeyError:
        return default


class _LiveMultiEdgeCallView:
    """br-r37-c1-msf5j: result of ``MG.edges()`` (no args) on a (Multi)
    graph. Mirrors nx's ``MultiEdgeDataView`` for the default-args
    case: yields 2-tuples on iteration, stays live with respect to
    subsequent graph mutations (re-walks ``adj`` / ``succ`` on every
    iter), and supports ``len`` / ``in``. The ``MG.edges`` (no parens)
    direct view continues to yield 3-tuples via ``_MultiGraphEdgeView``.
    """

    __slots__ = ("_graph", "_directed")

    def __init__(self, graph, *, directed):
        self._graph = graph
        self._directed = directed

    def _walk(self):
        graph = self._graph
        if self._directed:
            for source in graph:
                for target, keyed_attrs in graph.succ[source].items():
                    for _key in keyed_attrs:
                        yield (source, target)
        else:
            seen = set()
            for source in graph:
                for target, keyed_attrs in graph.adj[source].items():
                    for _key in keyed_attrs:
                        marker = (frozenset((source, target)), _key)
                        if marker in seen:
                            continue
                        seen.add(marker)
                        yield (source, target)

    def __iter__(self):
        # br-r37-c1-tmuly: for a MultiDiGraph, materialize the (u, v) 2-tuples
        # (one per edge incl. parallel, nx node x target x key order) from the
        # native edge view instead of self._walk()'s pure-Python triple-loop over
        # the succ AtlasView lambda chain (~3000x slower than nx). Identical
        # output. Undirected MultiGraph keeps _walk (no native view bound here).
        if self._directed and hasattr(self._graph, "_native_edge_view"):
            return _FailFastEdgeIterator(
                self._graph,
                iter(self._graph._native_edge_view()(None, False, False, None)),
                guard_edge_count=True,
            )
        # br-r37-c1-mgedges: undirected MultiGraph MG.edges() materializes the
        # (u, v) 2-tuples (one per parallel edge, node-major canonical-dedup
        # order) from the native edge-list builder instead of _walk()'s
        # pure-Python triple-loop over the adj AtlasView (~7000x slower than nx).
        if not self._directed:
            native = getattr(self._graph, "_native_edge_view_list", None)
            if native is not None:
                return _FailFastEdgeIterator(
                    self._graph,
                    iter(native(False, False, None)),
                    guard_edge_count=True,
                )
        return _FailFastEdgeIterator(
            self._graph,
            self._walk(),
            guard_edge_count=True,
        )

    def __len__(self):
        return self._graph.number_of_edges()

    def __contains__(self, edge):
        # br-r37-c1-rbu5n: networkx opens with `u, v = e[:2]` and lets both
        # failures out — TypeError for something that cannot be sliced, and
        # ValueError for a sequence shorter than two. The guard that used to
        # stand here (`isinstance(edge, tuple) and len(edge) >= 2, else False`)
        # swallowed both and answered False, so `42 in MG.edges()` and
        # `() in MG.edges()` were silent where networkx raises. Spelling it the
        # way networkx does gets every one of those cells right without a table
        # of them, and a `list` or a `str` still answers False — it reaches the
        # equality test below and fails it, exactly as it does there.
        u, v = edge[:2]
        graph = self._graph
        if self._directed:
            present = u in graph.succ and v in graph.succ[u]
        else:
            adj = graph.adj
            present = (u in adj and v in adj[u]) or (v in adj and u in adj[v])
        # br-r37-c1-rbu5n: networkx does not ask "is there an edge between these
        # two nodes", it asks "is this exactly one of the items I yield" —
        # `any(e == self._report(u, v, k, dd) for k, dd in kdict.items())`, and
        # `_report` here is `(u, v)`. So every 3-tuple is False, including one
        # whose key is real. This view yields 2-TUPLES; `keys=True` is a
        # different view with a different rule.
        #
        # Ignoring everything past index 1 made `('a','b',9) in MG.edges()`
        # answer True for a key that does not exist, which is the sharp end of
        # it: a WRONG TRUE, not merely a looser contract. Comparing to the
        # yielded shape reproduces networkx exactly and needs no length test.
        return present and edge == (u, v)

    def __repr__(self):
        # br-r37-c1-ih59i: the two concrete subclasses below already carry these
        # exact names, so this could read `type(self).__name__` — it does not,
        # deliberately. The base class is still constructible directly, and a
        # repr that derived the name from the type would then print the PRIVATE
        # one, which is the defect this bead is about. Deriving it from the
        # direction keeps the two spellings independent.
        name = "OutMultiEdgeDataView" if self._directed else "MultiEdgeDataView"
        return f"{name}({list(self)!r})"

    def __eq__(self, other):
        if isinstance(other, (set, frozenset)):
            return set(self) == other
        if isinstance(other, _LiveMultiEdgeCallView):
            return list(self) == list(other)
        try:
            return list(self) == list(other)
        except TypeError:
            return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    __hash__ = None


# br-r37-c1-ih59i: `MG.edges()` and `MDG.edges()` both returned the PRIVATE
# `_LiveMultiEdgeCallView`, where networkx reports `MultiEdgeDataView` and
# `OutMultiEdgeDataView` respectively. Only the type NAME leaked — the repr,
# the contents, the length and the containment all already matched — but
# `type(v).__name__` is exactly what a name-based parity check reads, so a
# private name here reads as a different class to any caller that looks.
#
# TWO subclasses rather than one renamed class, because networkx uses two
# different names for the two directions and a single class cannot carry both.
# `__slots__ = ()` keeps them slot-only like the base; adding attributes here
# would silently give every `edges()` result a `__dict__`.
#
# A sweep of 76 accessor forms across the four classes — edges / nodes / degree
# / adj / succ / pred / out_edges / in_edges and their called, data-bearing,
# nbunch and keys spellings — reports these two as the ONLY class-name
# divergences left.
class _MultiEdgeDataCallView(_LiveMultiEdgeCallView):
    __slots__ = ()


_MultiEdgeDataCallView.__name__ = "MultiEdgeDataView"
_MultiEdgeDataCallView.__qualname__ = "MultiEdgeDataView"


class _OutMultiEdgeDataCallView(_LiveMultiEdgeCallView):
    __slots__ = ()


_OutMultiEdgeDataCallView.__name__ = "OutMultiEdgeDataView"
_OutMultiEdgeDataCallView.__qualname__ = "OutMultiEdgeDataView"



class _MultiGraphEdgeView(_fnx.MultiGraphEdgeView):
    _fnx_edge_kind = "undirected"  # br-r37-c1-ex1s6: see _nx_edge_view_contains

    def __init__(self, graph):
        self._graph = graph

    def __getnewargs__(self):
        return (self._graph,)

    def __iter__(self):
        # br-multiiterkeys: nx.MultiEdgeView default iteration yields
        # 3-tuples ``(u, v, key)`` (as opposed to the ``G.edges()`` call
        # form which defaults to 2-tuples). fnx's __iter__ called
        # self() (keys=False) and yielded 2-tuples, so _Set comparisons
        # and direct iteration consumers (including downstream nx
        # algorithms) got a different edge _count than nx on multigraphs
        # with parallel edges.
        # br-r37-c1-c5zn8: the direct view owns a private mutation-token
        # materialization; public ``edges(keys=True)`` still returns a fresh
        # list and therefore cannot mutate this cache.
        return _direct_multi_edge_iter(self, MultiGraph)

    def __len__(self):
        return self._graph.number_of_edges()

    keys = _multi_edge_keys
    items = _multi_edge_items
    values = _multi_edge_values
    get = _multi_edge_get

    def __contains__(self, edge):
        # br-r37-c1-edgeviewcontains: nx's MultiEdgeView.__contains__
        # uses ``len(e)`` then unpacks via ``u, v = e`` / ``u, v, k = e``,
        # accepting any 2- or 3-element iterable (tuple, list, etc.).
        # The previous ``isinstance(edge, tuple)`` guard rejected lists,
        # so ``[0, 1] in M.edges`` returned False where nx returns True.
        # Lengths other than 2 or 3 raise ValueError; non-sized values
        # propagate TypeError from len(); KeyError on missing nodes
        # is caught and surfaces as False.
        try:
            N = len(edge)
        except TypeError:
            raise
        # br-r37-c1-6fs77: a 2-element spec means key ZERO, not "any key".
        # nx's body is ``k = 0`` then ``k in self._adjdict[u][v]``, so
        # ``('a','b') in M.edges`` is False for an edge added with key='x'.
        # Returning True as soon as the PAIR existed reported edges that are
        # not there, on every multigraph whose keys are not 0.
        # br-r37-c1-ki2ni: UNPACK, do not subscript. networkx's
        # MultiEdgeView.__contains__ does `u, v, k = e`, and indexing here was a
        # real divergence as well as slower: a 3-element SET is Sized but not
        # subscriptable, so `{'a','b',0} in M.edges` raised
        # `TypeError: 'set' object is not subscriptable` where networkx unpacks
        # it and answers False. One UNPACK_SEQUENCE also replaces three
        # BINARY_SUBSCR on the hot path, which matters because the wrapper — not
        # the lookup — is the cost here: measured 503.3ns for `t in M.edges`
        # against 261.7ns for the bound `has_edge` underneath it, i.e. 241.6ns of
        # Python, where networkx's own wrapper is 34.9ns.
        if N == 3:
            u, v, key = edge
        elif N == 2:
            u, v = edge
            key = 0
        else:
            raise ValueError("MultiEdge must have length 2 or 3")
        # br-r37-c1-6fs77 perf half: `has_edge(u, v, key)` is one native call
        # and answers exactly `key in adj[u][v]`, including `key=0` against an
        # edge whose only key is something else. Walking `self._graph.adj`
        # instead cost five Python frames and two view constructions per probe
        # — measured 0.1082x against networkx, the worst row on the surface.
        # A graph carrying networkx private storage keeps the walk, because
        # then the assigned mapping, not the native store, is the authority.
        # br-r37-c1-lvlu7: TypeError is NOT caught. nx's body is
        # `k in self._adjdict[u][v]` inside `except KeyError`, so an unhashable
        # endpoint raises out of the dict and must raise here too — and
        # `has_edge` now hashes `u` first and short-circuits on an absent `u`
        # before touching `v`, which is the order that keeps
        # `("missing", Unhashable()) in M.edges` False rather than a TypeError.
        # br-r37-c1-ki2ni: the private-storage WALK below was UNREACHABLE, and
        # the `_has_networkx_private_storage` probe that selected it could never
        # be True on this class. Assigning ANY private attribute swaps
        # `G.edges` for `_AssignedPrivateEdgeView` — verified for `_adj`,
        # `_node`, `_succ` and `_pred` on both multigraph classes — so a
        # `MultiEdgeView` instance only ever exists on a graph with no private
        # storage. The probe was 91.9ns, 38% of this wrapper, spent on every
        # call to choose a branch that could not be taken.
        #
        # Dead-code removal, so no behaviour can change: the 48-cell matrix
        # (2 classes x up to 5 override kinds x 6 edge shapes) is identical
        # before and after. Measured 500.3ns -> 349.9ns on the probe row.
        #
        # NB it does NOT fix the divergences that matrix shows — those live in
        # `_AssignedPrivateEdgeView` and are filed as br-r37-c1-x3rj1. I first
        # wrote this comment claiming the removal fixed one of them; it does
        # not, because the override cases never reach this code at all.
        #
        # br-r37-c1-lvlu7: TypeError is still NOT caught. nx's body is
        # `k in self._adjdict[u][v]` inside `except KeyError`, so an unhashable
        # endpoint raises out of the dict and must raise here too — and
        # `has_edge` hashes `u` first and short-circuits on an absent `u` before
        # touching `v`, which is the order that keeps
        # `("missing", Unhashable()) in M.edges` False rather than a TypeError.
        try:
            return self._graph.has_edge(u, v, key)
        except KeyError:
            return False
        except TypeError:
            # br-r37-c1-ex1s6: but networkx hashes the KEY only inside a pair
            # that exists: (2, 99, [0]) is False. has_edge(u, v) raises
            # networkx's TypeError for an unhashable u / v itself.
            if self._graph.has_edge(u, v):
                raise
            return False

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        # br-r37-c1-msf5j: when called with all-default args, return a
        # live wrapper that yields 2-tuples on iter and re-walks the
        # graph each time so subsequent edge mutations are visible.
        # Matches nx's MultiEdgeView.__call__() returning a live
        # MultiEdgeDataView.
        if nbunch is None and data is False and keys is False:
            return _MultiEdgeDataCallView(self._graph, directed=False)
        if (
            nbunch is None
            and data is False
            and keys is True
            and type(self._graph) is MultiGraph
            and not _has_networkx_private_storage(self._graph)
        ):
            return self
        # br-r37-c1-mgedges: all-edges path builds the result natively
        # (node-major over adjacency with canonical dedup, matching nx exactly)
        # instead of triple-looping self.adj[source] via the MultiAdjacencyView
        # lambda chain (~10000x). Wrap in the same canonical view type so
        # ``type(MG.edges(...)).__name__`` and set-algebra still match nx.
        if nbunch is None:
            native = getattr(self._graph, "_native_edge_view_list", None)
            if native is not None:
                result = _EdgeListWithSetAlgebra(native(data, keys, default))
                if data is not False:
                    return _guarded_edge_list(
                        _wrap_edge_data_view(result, _MultiEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                    )
                if keys:
                    # br-r37-c1-p1dbu: nx returns `self` here (its
                    # `MultiEdgeView.__call__` short-circuits whenever there is
                    # no nbunch and no data), so `G.edges(keys=True) is G.edges`
                    # and the result keeps the Mapping surface. This returns a
                    # LIST SUBCLASS carrying the same class NAME instead, so
                    # `.items()` / `.keys()` / `.values()` are missing.
                    #
                    # DO NOT "fix" this by returning `self`: `__iter__` reaches
                    # `_direct_multi_edge_iter`, which caches this call's result
                    # and iterates it, so `return self` is infinite recursion.
                    # Attempted and reverted — see the bead.
                    return _guarded_edge_list(
                        _wrap_edge_data_view(result, _MultiEdgeView),
                        self._graph,
                        guard_edge_count=True,
                    )
                return _guarded_edge_list(result, self._graph, guard_edge_count=True)
        # br-r37-c1-mgcall (cycle 213): when ``data`` is anything
        # other than False, nx returns ``MultiEdgeDataView``
        # (canonical class).  fnx previously returned a generic
        # ``_EdgeListWithSetAlgebra`` regardless of args, so
        # ``type(MG.edges(data=True)).__name__`` was wrong.  Wrap
        # in ``_MultiEdgeDataView`` (cycle-192's subclass with
        # canonical name) when data is requested.
        # br-r37-c1-mgedgenb (cc): native one-pass for data=False (the heavy
        # adj[source] lambda-chain + frozenset dedup path, ~0.09x vs nx). Returns
        # None for row-display / non-default key-display graphs -> Python loop below.
        _iterable_nb = _nbunch_is_iterable_bunch(self._graph, nbunch)
        if data is False and _iterable_nb:
            native = getattr(self._graph, "_native_mg_edges_nbunch_no_data", None)
            if native is not None:
                try:
                    native_res = _nbunch_data_cache(
                        self._graph, "_fnx_mg_edges_nbunch_nodata_cache",
                        nbunch, native, keys,
                    )
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_res is not None:
                    result = _EdgeListWithSetAlgebra(native_res)
                    if keys:
                        # br-r37-c1-hihrf: nbunch spelling -> nx's
                        # MultiEdgeDataView semantics, not MultiEdgeView's.
                        return _guarded_edge_list(
                            _wrap_edge_data_view(result, _MultiEdgeDataKeysView),
                            self._graph,
                            guard_edge_count=True,
                            nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                        )
                    # br-r37-c1-hihrf: nx names this MultiEdgeDataView. THIS is
                    # the live return for `MG.edges(nbunch)` - the native
                    # no-data fast path - and it was handing back an unnamed
                    # list. The Python fallback below needed the same fix and
                    # is NOT the one that runs.
                    return _guarded_edge_list(
                        _wrap_edge_data_view(result, _MultiEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        # br-r37-c1-mgedgenb (cc): data=True one-pass (same lambda-chain path was
        # ~0.09x). Emits live attr dicts; None -> Python loop for display-override.
        if data is True and _iterable_nb:
            native = getattr(self._graph, "_native_mg_edges_nbunch_data", None)
            if native is not None:
                try:
                    native_res = _nbunch_data_cache(
                        self._graph, "_fnx_mg_edges_nbunch_data_cache",
                        nbunch, native, keys,
                    )
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_res is not None:
                    result = _EdgeListWithSetAlgebra(native_res)
                    return _guarded_edge_list(
                        _wrap_edge_data_view(result, _MultiEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        # br-r37-c1-mgedgenbdk (cc): data=<key> one-pass (was the Python adj-chain,
        # ~0.11x). Projects attrs.get(data, default) per edge; None -> Python loop.
        if data is not False and data is not True and _iterable_nb:
            native = getattr(self._graph, "_native_mg_edges_nbunch_data_key", None)
            if native is not None:
                try:
                    # br-r37-c1-p1tyz: values are not memoized (they go stale).
                    native_res = native(nbunch, data, default, keys)
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                if native_res is not None:
                    result = _EdgeListWithSetAlgebra(native_res)
                    return _guarded_edge_list(
                        _wrap_edge_data_view(result, _MultiEdgeDataView),
                        self._graph,
                        guard_edge_count=True,
                        nbunch_rows=_resolved_nbunch_rows(self._graph, nbunch),
                    )
        result = _EdgeListWithSetAlgebra()
        seen = set()
        for source in self._graph.nbunch_iter(nbunch):
            for target, keyed_attrs in self._graph.adj[source].items():
                for key, attrs in keyed_attrs.items():
                    marker = (frozenset((source, target)), key)
                    if marker in seen:
                        continue
                    seen.add(marker)
                    if data is True and keys:
                        result.append((source, target, key, attrs))
                    elif data is True:
                        result.append((source, target, attrs))
                    elif data is False and keys:
                        result.append((source, target, key))
                    elif data is False:
                        result.append((source, target))
                    elif keys:
                        result.append((source, target, key, attrs.get(data, default)))
                    else:
                        result.append((source, target, attrs.get(data, default)))
        if data is not False:
            return _guarded_edge_list(
                _wrap_edge_data_view(result, _MultiEdgeDataView),
                self._graph,
                guard_edge_count=True,
                nbunch_rows=(
                    _resolved_nbunch_rows(self._graph, nbunch)
                ),
            )
        # br-r37-c1-mekvc (cycle 214): keys=True (data=False) wraps
        # in canonical ``MultiEdgeView`` so both
        # ``type(view).__name__`` and ``(u, v) in view`` match nx.
        #
        # br-r37-c1-hihrf: NOT changed to MultiEdgeDataView even though that is
        # what nx names this spelling WITH an nbunch. The wrapper also carries
        # the any-key ``__contains__``, and swapping it would move a second
        # thing: nx RAISES IndexError for ``(u, v) in MG.edges(nb, keys=True)``
        # (its __contains__ reads e[2] without a length check) where fnx answers
        # True. Name and containment have to be decided together there; the
        # plain-nbunch return below has no such coupling.
        if keys:
            return _guarded_edge_list(
                _wrap_edge_data_view(result, _MultiEdgeView),
                self._graph,
                guard_edge_count=True,
                nbunch_rows=(
                    _resolved_nbunch_rows(self._graph, nbunch)
                ),
            )
        # br-r37-c1-hihrf: nx returns MultiEdgeDataView here, not a bare list.
        # The two data spellings above already wrap; this one was left unnamed,
        # so `type(MG.edges(nbunch)).__name__` read `_EdgeListWithSetAlgebra`.
        # Pure naming - `_MultiEdgeDataView` is `pass` over the same list base,
        # and the containment table for this spelling already matches nx on
        # every query, so only the name and repr move.
        return _guarded_edge_list(
            _wrap_edge_data_view(result, _MultiEdgeDataView),
            self._graph,
            guard_edge_count=True,
            nbunch_rows=(
                _resolved_nbunch_rows(self._graph, nbunch)
            ),
        )

    def __eq__(self, other):
        # br-r37-c1-eveq: see _DiGraphEdgeView.__eq__. nx's
        # MultiEdgeView inherits from _Set; lock content-based
        # equality matching nx exactly.
        from collections.abc import Set as _Set
        if isinstance(other, _MultiGraphEdgeView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    # br-r37-c1-viewhash: nx's OutEdgeView / MultiEdgeView /
    # OutMultiEdgeView all inherit from ``collections.abc.Mapping``
    # (``__hash__ = None``), so ``hash(G.edges)`` raises TypeError.
    # fnx previously returned ``id(self._graph)`` here, silently
    # accepting the view as hashable — diverging on a contract that
    # drop-in callers rely on (``except TypeError: ...`` around
    # accidental view-in-set patterns).
    __hash__ = None

    # br-r37-c1-iev-setops: see _DiEdgeMethodView. _Set comparison +
    # algebra operators for nx parity (_Set inheritance on
    # MultiEdgeView).
    def __le__(self, other):
        return set(self) <= set(other) if hasattr(other, "__iter__") else NotImplemented

    def __lt__(self, other):
        return set(self) < set(other) if hasattr(other, "__iter__") else NotImplemented

    def __ge__(self, other):
        return set(self) >= set(other) if hasattr(other, "__iter__") else NotImplemented

    def __gt__(self, other):
        return set(self) > set(other) if hasattr(other, "__iter__") else NotImplemented

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

    # networkx's MultiEdgeView is a collections.abc.Set, so a plain set on the
    # LEFT works there too; without the reflected operators
    # ``{...} & MG.edges(keys=True)`` raised TypeError
    # (tests/python/test_multi_keyed_edges_set_algebra_parity.py).
    __rand__ = __and__
    __ror__ = __or__
    __rxor__ = __xor__

    def __rsub__(self, other):
        return set(other) - set(self)
