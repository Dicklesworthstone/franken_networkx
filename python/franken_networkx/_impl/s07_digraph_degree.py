

def _digraph_degree(self):
    return _DiGraphDegreeView(self, _DIGRAPH_RAW_DEGREE.__get__(self, type(self)))


Graph.degree = property(_graph_degree)
DiGraph.degree = property(_digraph_degree)

Graph.size = _size_with_unweighted_int(Graph.size)
DiGraph.size = _size_with_unweighted_int(DiGraph.size)
MultiGraph.size = _size_with_unweighted_int(MultiGraph.size)
MultiDiGraph.size = _size_with_unweighted_int(MultiDiGraph.size)


def _edgeview_contains_with_nx_semantics(orig_contains):
    """Wrap ``EdgeView.__contains__`` to match nx's permissive semantics.

    br-r37-c1-dtrpe: ``_fnx.EdgeView`` — the only one of these four classes any
    public graph actually returns — no longer needs this. It implements the
    permissive spec handling itself, so its rebind is gone and ``x in G.edges``
    reaches the C slot directly. The wrapper cost 1114.7 Ir of the probe's
    2451.4 and measured 1.1190x CI [1.1074, 1.1324] on the wall clock.

    The three rebinds below stay because their classes are NOT reachable:
    ``DiGraph.edges`` / ``MultiGraph.edges`` / ``MultiDiGraph.edges`` return the
    Python ``_DiGraphEdgeView`` / ``_MultiGraphEdgeView`` / ``_MultiDiGraphEdgeView``
    defined in this module. Porting semantics into a Rust slot nothing calls
    would be unmeasurable by construction, so it is left for whoever routes
    those classes to native views.

    br-r37-c1-edgeviewcontains: nx's ``EdgeView.__contains__``::

        try:
            u, v = e[:2]
            return v in self._adjdict[u] or u in self._adjdict[v]
        except (KeyError, ValueError):
            return False

    accepts any subscriptable 2+-element value as an edge spec — strings
    of length >= 2 (returns False), 2-element lists (returns membership),
    longer tuples (uses first two), etc.  fnx's Rust ``EdgeView`` was
    too strict, raising ``TypeError("edge must be a (u, v) tuple")`` on
    str / list / non-tuple inputs.  Drop-in code like
    ``if "x" in G.edges:`` (always-False guard) crashed under fnx.

    Wrap the Rust ``__contains__`` so:
      * tuples (the fast path) keep their Rust speed,
      * non-tuple subscriptables go through ``e[:2]`` -> retry path,
      * non-subscriptable values surface a TypeError matching nx's
        ``e[:2]`` error wording (``object is not subscriptable``).
    """

    def __contains__(self, e):
        try:
            return orig_contains(self, e)
        except TypeError:
            pass
        # nx-style: ``e[:2]`` raises TypeError on non-subscriptable
        # (int, None, etc.) — let it propagate with nx's wording;
        # ValueError on length mismatch -> False.
        try:
            slice_ = e[:2]
        except TypeError:
            raise
        try:
            u, v = slice_
        except (TypeError, ValueError):
            return False
        try:
            return orig_contains(self, (u, v))
        except TypeError:
            return False

    return __contains__


_fnx.DiEdgeView.__contains__ = _edgeview_contains_with_nx_semantics(
    _fnx.DiEdgeView.__contains__
)
_fnx.MultiGraphEdgeView.__contains__ = _edgeview_contains_with_nx_semantics(
    _fnx.MultiGraphEdgeView.__contains__
)
_fnx.MultiDiGraphEdgeView.__contains__ = _edgeview_contains_with_nx_semantics(
    _fnx.MultiDiGraphEdgeView.__contains__
)
Graph.remove_node = _remove_node_with_networkx_missing_node_error(
    _GRAPH_REMOVE_NODE, graph_kind="graph"
)
DiGraph.remove_node = _remove_node_with_networkx_missing_node_error(
    _DIGRAPH_REMOVE_NODE, graph_kind="digraph"
)
MultiGraph.remove_node = _remove_node_with_networkx_missing_node_error(
    _MULTIGRAPH_REMOVE_NODE, graph_kind="graph"
)
MultiDiGraph.remove_node = _remove_node_with_networkx_missing_node_error(
    _MULTIDIGRAPH_REMOVE_NODE, graph_kind="digraph"
)
Graph.remove_edge = _remove_edge_with_networkx_missing_edge_error(
    _GRAPH_REMOVE_EDGE, missing_edge_message="The edge {u}-{v} is not in the graph"
)
DiGraph.remove_edge = _remove_edge_with_networkx_missing_edge_error(
    _DIGRAPH_REMOVE_EDGE, missing_edge_message="The edge {u}-{v} not in graph."
)
MultiGraph.remove_edge = _remove_edge_with_networkx_missing_edge_error(
    _MULTIGRAPH_REMOVE_EDGE,
    missing_edge_message="The edge {u}-{v} is not in the graph.",
    supports_key=True,
)
MultiDiGraph.remove_edge = _remove_edge_with_networkx_missing_edge_error(
    _MULTIDIGRAPH_REMOVE_EDGE,
    missing_edge_message="The edge {u}-{v} is not in the graph.",
    supports_key=True,
)
Graph.number_of_edges = _number_of_edges_with_endpoints(_GRAPH_NUMBER_OF_EDGES)
DiGraph.number_of_edges = _number_of_edges_with_endpoints(_DIGRAPH_NUMBER_OF_EDGES)
Graph.neighbors = _neighbors_with_networkx_missing_node_error(_GRAPH_NEIGHBORS)
DiGraph.neighbors = _neighbors_with_networkx_missing_node_error(
    _DIGRAPH_NEIGHBORS, graph_kind="digraph"
)
DiGraph.successors = _neighbors_with_networkx_missing_node_error(
    _DIGRAPH_SUCCESSORS, graph_kind="digraph"
)
DiGraph.predecessors = _neighbors_with_networkx_missing_node_error(
    _DIGRAPH_PREDECESSORS, graph_kind="digraph"
)
MultiGraph.neighbors = _neighbors_with_networkx_missing_node_error(_MULTIGRAPH_NEIGHBORS)
MultiDiGraph.neighbors = _neighbors_with_networkx_missing_node_error(
    _MULTIDIGRAPH_NEIGHBORS, graph_kind="digraph"
)
MultiDiGraph.successors = _neighbors_with_networkx_missing_node_error(
    _MULTIDIGRAPH_SUCCESSORS, graph_kind="digraph"
)
MultiDiGraph.predecessors = _neighbors_with_networkx_missing_node_error(
    _MULTIDIGRAPH_PREDECESSORS, graph_kind="digraph"
)
_EDGE_VIEW_TYPE.__call__ = _edge_view_call_with_nbunch_first(_EDGE_VIEW_CALL)
_DIEDGE_VIEW_TYPE.__call__ = _edge_view_call_with_nbunch_first(_DIEDGE_VIEW_CALL)
_EDGE_VIEW_TYPE.get = _adjacency_view_get
_EDGE_VIEW_TYPE.keys = _adjacency_view_keys
_EDGE_VIEW_TYPE.items = _adjacency_view_items
_EDGE_VIEW_TYPE.values = _adjacency_view_values
_DiGraphEdgeView.get = _adjacency_view_get
_DiGraphEdgeView.keys = _adjacency_view_keys
_DiGraphEdgeView.items = _adjacency_view_items
_DiGraphEdgeView.values = _adjacency_view_values


def _freeze_edge_view_nbunch(graph, args, kwargs):
    """br-r37-c1-af0ig: pin an nbunch to the nodes that exist RIGHT NOW.

    nx resolves the nbunch exactly once, in the data view's ``__init__``::

        nbunch = dict.fromkeys(viewer._graph.nbunch_iter(nbunch))
        self._nodes_nbrs = lambda: [(n, adjdict[n]) for n in nbunch]

    so the node SET is frozen at construction while the adjacency behind it
    stays live. A node named in the nbunch but absent at that moment is
    dropped permanently — adding it later does not make its edges appear.
    Re-resolving the caller's original nbunch on every rebuild would be live
    in one step too many and start reporting those edges, so the resolved
    list is what the rebuild replays.

    Only a non-string iterable is frozen. A single-node nbunch keeps the
    caller's original value, because that form carries its own missing-node
    error contract (br-r37-c1-edges-snnb) which re-resolution must not skip.
    """
    nbunch = kwargs["nbunch"] if "nbunch" in kwargs else (args[0] if args else None)
    if nbunch is None or isinstance(nbunch, (str, bytes)):
        return args, kwargs
    # br-r37-c1-jl8x1: the SECOND place this rule was re-derived, and the one
    # that made the first fix look like it had not worked. A tuple or frozenset
    # that IS a node was dict.fromkeys'd into its elements here, so the frozen
    # nbunch came out empty and the first refresh replaced a correct materialised
    # list with nothing. The docstring above already said a single-node nbunch
    # keeps the caller's value; only the predicate disagreed.
    #
    # `type(nbunch) is not list` first is an ADMISSION TEST, not a second copy of
    # the rule: a list is unhashable and so can never be a node, which is exactly
    # what the helper would answer, so getting this compare wrong could only cost
    # time. It matters because this runs on EVERY edges(nbunch) call and a list is
    # what every hot caller passes - the counted budget for this fix is +2 Python
    # calls per call and this is one of them, for 8.6 ns of `type()` compare.
    if type(nbunch) is not list and _nbunch_names_one_node(graph, nbunch):
        return args, kwargs
    try:
        present = [n for n in dict.fromkeys(nbunch) if n in graph]
    except TypeError:
        # Not iterable (single non-iterable node) or unhashable elements —
        # both keep the original argument and its established contract.
        return args, kwargs
    if "nbunch" in kwargs:
        return args, {**kwargs, "nbunch": present}
    return (present,) + tuple(args[1:]), kwargs


_EDGE_VIEW_CALL_KWARGS = frozenset(("nbunch", "data", "default", "keys"))


def _called_edge_view_spec(view, graph, args, kwargs):
    """br-r37-c1-ex1s6: what membership in the list a called edge view
    returns needs to answer as networkx's view does - (graph, kind, multi,
    data, default, keys, nbunch nodes, whether networkx returns the edge
    view itself) - or None for a call networkx's (nbunch, data, *,
    default, keys) signature does not describe. `args` / `kwargs` carry the
    nbunch as frozen for the rebuild."""
    # Every view class _live_called_edge_view wraps defines _fnx_edge_kind.
    kind = view._fnx_edge_kind
    if len(args) > 2 or not kwargs.keys() <= _EDGE_VIEW_CALL_KWARGS:
        return None
    nbunch = kwargs["nbunch"] if "nbunch" in kwargs else (args[0] if args else None)
    data = kwargs["data"] if "data" in kwargs else (args[1] if len(args) > 1 else False)
    keys = kwargs.get("keys", False)
    multi = graph.is_multigraph()
    # A dict, as networkx's nbunch: an unhashable probe is worded as a key.
    if nbunch is None:
        nodes = None
    elif isinstance(nbunch, list):
        nodes = dict.fromkeys(nbunch)
    else:  # a single node (see _freeze_edge_view_nbunch)
        try:
            nodes = {nbunch: None}
        except TypeError:
            return None
    view_form = nbunch is None and data is False and (keys is True or not multi)
    return (graph, kind, multi, data, kwargs.get("default"), keys, nodes, view_form)


def _called_edge_view_contains(spec, e):
    graph, kind, multi, data, default, keys, nodes, view_form = spec
    if view_form:
        return _nx_edge_view_contains_by_has_edge(graph, e, kind, multi)
    return _nx_edge_data_view_contains(
        _edge_rows(graph, kind), e, kind, multi, data, default, keys, nodes
    )


def _live_called_edge_view(original_call):
    """br-r37-c1-af0ig: give a materialised ``edges(...)`` result a way back.

    The three non-Graph edge views build their result through ~22 different
    return statements (native kernels, nbunch kernels, adj-walk fallbacks).
    Threading a rebuild through each one would be 22 chances to miss one — and
    a missed path is invisible, because it fails only after a mutation. So the
    thunk is attached HERE, at the single ``__call__`` boundary every one of
    those paths returns through, which also means a path added later inherits
    liveness without anyone remembering to wire it up.

    The call is still made eagerly, so argument validation still raises at call
    time exactly as before (nx raises there too). What changes is only that the
    result can now rebuild itself when read after the graph has moved on.
    """

    def wrapped(self, *args, **kwargs):
        # br-r37-c1-u5tyh: materialise a ONE-SHOT nbunch before the call
        # consumes it. A generator/iterator nbunch was drained by
        # original_call, so the freeze that follows saw an exhausted iterator
        # and recorded an EMPTY frozen nbunch — which then made every rebuild
        # after a mutation (br-r37-c1-af0ig) answer with nothing. It was latent
        # while only the first read mattered; walking the frozen list directly
        # surfaced it immediately.
        if args and not isinstance(
            args[0], (list, tuple, set, frozenset, dict, str, bytes, range)
        ) and args[0] is not None and hasattr(args[0], "__next__"):
            args = (list(args[0]),) + tuple(args[1:])
        elif "nbunch" in kwargs:
            nbunch_kw = kwargs["nbunch"]
            if nbunch_kw is not None and hasattr(nbunch_kw, "__next__"):
                kwargs = {**kwargs, "nbunch": list(nbunch_kw)}
        result = original_call(self, *args, **kwargs)
        # Object-based views (the bare ``edges()`` path returns ``self``) are
        # already live; only the materialised list snapshots need this.
        if type(result) is not type(self) and isinstance(result, _EdgeListWithSetAlgebra):
            # The edges(...) paths record the graph via _guarded_edge_list; the
            # directional ones do not, so fall back to the view's own graph.
            # Deliberately stored under a SEPARATE name: writing
            # _fnx_guard_graph here would also switch on the fail-fast
            # mutation-during-iteration guard for views that never had it,
            # which is a different contract from liveness and not this bead's.
            graph = result._fnx_guard_graph
            if graph is None:
                graph = getattr(self, "_graph", None)
            if graph is not None:
                args, kwargs = _freeze_edge_view_nbunch(graph, args, kwargs)
                result._fnx_live_graph = graph
                # `_guarded_edge_list` has already stamped the materialised
                # result on the common edges(nbunch) routes. No user code can
                # run between that call returning and this decorator attaching
                # the rebuild thunk, so recomputing the same freshness token
                # only repeats two PyO3 revision reads and a private-storage
                # probe. Preserve that authoritative stamp; directional paths
                # which did not use `_guarded_edge_list` still get one here.
                if result._fnx_token is None:
                    result._fnx_token = _edge_list_freshness_token(graph)
                result._fnx_rebuild = lambda: original_call(self, *args, **kwargs)
                # br-r37-c1-p1tyz: `data` is the second parameter of every
                # edge-view call; anything but True / False / None is a key.
                data = kwargs["data"] if "data" in kwargs else (args[1] if len(args) > 1 else False)
                if data is not True and data is not False and data is not None:
                    result._fnx_holds_values = True
                    result._fnx_attr_epoch = _edge_attr_freshness_token(graph)
                # br-r37-c1-ex1s6: what membership needs, resolved on the first
                # `in` (building it here cost 0.5-0.8 us on every call).
                result._fnx_contains_call = (self, graph, args, kwargs)
                # br-r37-c1-2pia7: keep the RESOLVED nbunch so a later read can
                # tell that one of its own nodes has since been removed, which
                # nx reports by raising from adjdict[n] rather than by quietly
                # returning fewer edges.
                frozen = kwargs["nbunch"] if "nbunch" in kwargs else (args[0] if args else None)
                if isinstance(frozen, list):
                    result._fnx_frozen_nbunch = frozen
                    # br-r37-c1-u5tyh: DiGraph's out-edge rows are the same live
                    # PyDict mirrors Graph's are, so the same live-row walk that
                    # gave Graph networkx's iteration semantics works here. Record
                    # what the call asked for; __iter__ does the walking.
                    # OUT-direction only. in_edges walks the PRED rows AND
                    # yields (predecessor, node) rather than (node, neighbour),
                    # so pointing this at "succ" for it produced the wrong edges
                    # entirely — caught by test_graph_utilities' in_edges case.
                    # Rather than special-case the reversed tuple here, the
                    # in-direction keeps the existing path.
                    if (
                        type(graph) is DiGraph
                        and type(self).__qualname__ in ("_DiGraphEdgeView", "_OutEdgeView")
                        and len(frozen) <= _EDGES_NBUNCH_PY_WALK_MAX
                    ):
                        data = kwargs.get("data", args[1] if len(args) > 1 else False)
                        if data is False or data is True:
                            result._fnx_lazy_rows = ("succ", frozen, data)
        return result

    wrapped.__name__ = getattr(original_call, "__name__", "__call__")
    wrapped.__qualname__ = getattr(original_call, "__qualname__", "__call__")
    wrapped.__doc__ = original_call.__doc__
    return wrapped


# br-r37-c1-af0ig: applied to the classes the graph accessors ACTUALLY return
# today, verified by identity rather than by name. The pre-existing live-view
# patch two lines above binds ``_DIEDGE_VIEW_TYPE``, which was captured as
# ``type(DiGraph().edges)`` early in this module — but the directed accessors
# were since rebound to return _DiGraphEdgeView, so that patch now lands on a
# class nothing reaches and the directed views silently went back to being
# snapshots. Probing reachability here keeps that from recurring silently.
for _live_view_cls in (_DiGraphEdgeView, _MultiGraphEdgeView, _MultiDiGraphEdgeView):
    _live_view_cls.__call__ = _live_called_edge_view(_live_view_cls.__call__)
del _live_view_cls


# br-r37-c1-edvname: nx exposes per-direction × multi class names
# for ``.edges.data()`` / ``.in_edges.data()`` / ``.out_edges.data()``:
#
#   Graph.edges.data()              EdgeDataView
#   DiGraph.edges.data()            OutEdgeDataView
#   DiGraph.in_edges.data()         InEdgeDataView
#   DiGraph.out_edges.data()        OutEdgeDataView
#   MultiGraph.edges.data()         MultiEdgeDataView
#   MultiDiGraph.edges.data()       OutMultiEdgeDataView
#   MultiDiGraph.in_edges.data()    InMultiEdgeDataView
#   MultiDiGraph.out_edges.data()   OutMultiEdgeDataView
#
# Pre-fix fnx returned a plain ``list`` (DiGraph, in/out_edges) or
# ``_EdgeListWithSetAlgebra`` (MultiGraph, MultiDiGraph) — diverging
# on ``type(view).__name__`` for 7 of the 8 combos.  Define
# 5 trivial list subclasses with canonical ``__name__`` and route
# each ``.data()`` method to the right one. _Set-algebra inherits
# from _EdgeListWithSetAlgebra so set-typed expressions still work.

class _OutEdgeDataView(_EdgeListWithSetAlgebra):
    pass
_OutEdgeDataView.__name__ = "OutEdgeDataView"


class _InEdgeDataView(_EdgeListWithSetAlgebra):
    pass
_InEdgeDataView.__name__ = "InEdgeDataView"


class _MultiEdgeDataView(_EdgeListWithSetAlgebra):
    pass
_MultiEdgeDataView.__name__ = "MultiEdgeDataView"


class _OutMultiEdgeDataView(_EdgeListWithSetAlgebra):
    pass
_OutMultiEdgeDataView.__name__ = "OutMultiEdgeDataView"


class _InMultiEdgeDataView(_EdgeListWithSetAlgebra):
    pass
_InMultiEdgeDataView.__name__ = "InMultiEdgeDataView"


# br-r37-c1-hihrf: nx serves ``MG.edges(nbunch, keys=True)`` from
# ``MultiEdgeDataView``, NOT the ``MultiEdgeView`` that serves the no-nbunch
# spelling below, and the two disagree about ``__contains__``. nx's:
#
#     def __contains__(self, e):
#         u, v = e[:2]
#         if self._nbunch is not None and u not in self._nbunch and v not in self._nbunch:
#             return False
#         ... kdict lookup, KeyError -> False ...
#         if self.keys is True:
#             k = e[2]          # <- no length check
#
# so a 2-tuple raises IndexError, but only for an edge this view actually
# carries: a miss returns False before the key is ever read. fnx answered True
# there, which is MORE permissive than the incumbent - the dangerous direction
# for a drop-in, because code that passes here would crash on networkx.
#
# The IndexError is not raised artificially below; the same ``e[2]`` is written
# in the same place, after the same membership test, so it falls out exactly as
# nx's does.

class _MultiEdgeDataKeysView(_EdgeListWithSetAlgebra):
    """``MultiGraph.edges(nbunch, keys=True)`` — items are ``(u, v, key)``.

    Mirrors nx's ``MultiEdgeDataView.__contains__`` for ``keys=True``:
    a 3-tuple is an exact match in either endpoint order, and a 2-tuple raises
    IndexError if the edge is present and returns False if it is not.
    """

    _reverse_ok = True

    def __contains__(self, edge):
        spec = self._fnx_membership_spec()  # br-r37-c1-ex1s6
        if spec:
            return _called_edge_view_contains(spec, edge)
        try:
            u, v = edge[0], edge[1]
        except (TypeError, IndexError, KeyError):
            return list.__contains__(self, edge)
        present = any(
            (item[0] == u and item[1] == v)
            or (self._reverse_ok and item[0] == v and item[1] == u)
            for item in self
        )
        if not present:
            return False
        key = edge[2]  # nx reads e[2] here with no length check
        if list.__contains__(self, (u, v, key)):
            return True
        return self._reverse_ok and list.__contains__(self, (v, u, key))


_MultiEdgeDataKeysView.__name__ = "MultiEdgeDataView"


class _OutMultiEdgeDataKeysView(_MultiEdgeDataKeysView):
    """Directed twin. nx's ``OutMultiEdgeDataView`` never tries the reverse
    orientation - it looks up ``self._adjdict[u][v]`` and stops."""

    _reverse_ok = False


_OutMultiEdgeDataKeysView.__name__ = "OutMultiEdgeDataView"


# br-r37-c1-mekvc (cycle 214): nx's ``MultiGraph.edges(keys=True)``
# returns a ``MultiEdgeView`` whose ``__contains__`` matches BOTH
# 3-tuple ``(u, v, k)`` (exact-key) and 2-tuple ``(u, v)`` (any-key)
# queries.  fnx previously returned a generic
# ``_EdgeListWithSetAlgebra`` (a ``list`` subclass), and
# ``list.__contains__`` rejected ``(u, v) in MG.edges(keys=True)``
# even when (u, v) was an edge — drop-in code that asks
# ``if (u, v) in MG.edges(keys=True): ...`` silently misbehaved.
#
# Sister to the cycle-192/213 wrapping pattern: define dedicated
# subclasses so ``type(view).__name__`` matches nx and override
# ``__contains__`` for the multi-edge any-key semantics.

class _MultiEdgeView(_EdgeListWithSetAlgebra):
    """Returned by ``MultiGraph.edges(keys=True)``.  Items are
    3-tuples ``(u, v, key)``.  ``__contains__`` accepts:

      * 3-tuple ``(u, v, k)`` — exact-key match (parent ``list``)
      * 2-tuple ``(u, v)``   — True if ANY key exists for ``(u, v)``

    Mirrors nx's ``MultiEdgeView.__contains__``.
    """
    def __contains__(self, edge):
        spec = self._fnx_membership_spec()  # br-r37-c1-ex1s6: key 0 for a pair
        if spec:
            return _called_edge_view_contains(spec, edge)
        try:
            n = len(edge)
        except TypeError:
            return list.__contains__(self, edge)
        if n == 3:
            return list.__contains__(self, tuple(edge))
        if n == 2:
            u, v = edge[0], edge[1]
            for e in self:
                if len(e) >= 2 and e[0] == u and e[1] == v:
                    return True
            return False
        return False
_MultiEdgeView.__name__ = "MultiEdgeView"


class _OutMultiEdgesKeysView(_MultiEdgeView):
    """Returned by ``MultiDiGraph.edges(keys=True)`` and
    ``MultiDiGraph.out_edges(keys=True)``.  Inherits the multi-edge
    any-key ``__contains__`` from ``_MultiEdgeView``.

    Distinct from cycle-188's ``_OutMultiEdgeView`` (the
    ``_DiEdgeMethodView`` subclass for the ``MDG.out_edges``
    property) — both expose the same ``__name__``
    (``"OutMultiEdgeView"``) since nx considers the two surfaces
    equivalent, but the underlying machinery differs (method-view
    vs materialised list-of-3-tuples).
    """
    pass
_OutMultiEdgesKeysView.__name__ = "OutMultiEdgeView"


# br-r37-c1-iemvcw (cycle 215): same pattern for ``MDG.in_edges(keys=True)``.
class _InMultiEdgesKeysView(_MultiEdgeView):
    """Returned by ``MultiDiGraph.in_edges(keys=True)``.  Inherits
    multi-edge any-key ``__contains__`` from ``_MultiEdgeView``.

    Distinct from cycle-188's ``_InMultiEdgeView`` for the same
    name-collision reasons described in ``_OutMultiEdgesKeysView``.
    """
    pass
_InMultiEdgesKeysView.__name__ = "InMultiEdgeView"


def _wrap_edge_data_view(result, view_cls):
    """Wrap a list-of-edges result in the canonical nx-named class
    so ``type(view).__name__`` matches.  If the result is already
    an instance of view_cls (or a subclass), return as-is."""
    if isinstance(result, view_cls):
        return result
    wrapped = view_cls(result)
    return wrapped


def _edge_view_data(self, data=True, default=None, nbunch=None):
    """Return an iterable of edges with data, matching upstream
    EdgeView.data(). Delegates to the view's __call__(data=...) path
    which already handles `data=True` (attrs dict), `data='attr'`
    (single attribute with default), and `nbunch` filtering.

    For Graph.edges (returns the proper EdgeDataView via __call__),
    the result needs no rewrapping.  For DiGraph.edges (which
    returns a plain list), wrap in ``_OutEdgeDataView``.
    """
    if nbunch is None:
        result = self(data=data, default=default)
    else:
        result = self(nbunch=nbunch, data=data, default=default)
    # Graph.edges.data() already returns EdgeDataView via __call__
    # — leave untouched to preserve the EdgeDataView semantics that
    # cycle 191's NodeDataView fix mirrors. Only DiGraph.edges.data()
    # falls through here returning a plain list.
    if type(self).__name__ == "OutEdgeView":
        return _wrap_edge_data_view(result, _OutEdgeDataView)
    return result


def _multi_edge_view_data(self, data=True, default=None, keys=False, nbunch=None):
    """Multigraph variant of EdgeView.data() that also accepts the
    `keys` kwarg, matching upstream's MultiEdgeView.data().
    """
    if nbunch is None:
        result = self(data=data, default=default, keys=keys)
    else:
        result = self(nbunch=nbunch, data=data, default=default, keys=keys)
    cls_name = type(self).__name__
    if cls_name == "OutMultiEdgeView":
        return _wrap_edge_data_view(result, _OutMultiEdgeDataView)
    if cls_name == "MultiEdgeView":
        return _wrap_edge_data_view(result, _MultiEdgeDataView)
    return result


_EDGE_VIEW_TYPE.data = _edge_view_data
_DiGraphEdgeView.data = _edge_view_data
_MultiGraphEdgeView.data = _multi_edge_view_data
_MultiDiGraphEdgeView.data = _multi_edge_view_data


# br-r37-c1-ef8rt: `_EDGE_VIEW_TYPE.__getitem__` is NOT rebound. The native slot
# implements nx's `__getitem__` itself — the slice guard, the `u, v = e` unpack
# with CPython's own wording, nx's KeyError text carrying the original spec, and
# the hash order that answers a missing edge before the target is hashed. The
# wrapper this replaces unpacked, called `hash()` twice, and looked the owning
# graph up in a weak dict keyed by `id(self)` to recover the object the view
# already holds a reference to, on the worst-measured read row on the surface.
#
# The wrapper factory that used to live here is deleted rather than left unused:
# the DiGraph and multigraph edge views are Python classes with their own
# `__getitem__` bodies, so nothing else called it.


def _view_set_eq(self, other):
    """br-vweqset: nx NodeView/EdgeView inherit from collections.abc.Set
    so `G.edges == {(0,1),(1,2)}` returns True. The Rust-native fnx
    views have no ABC inheritance; this wrapper mimics _Set.__eq__
    semantics — True when `other` is _Set-like and contains the same
    elements, False otherwise.
    """
    if self is other:
        return True
    try:
        if len(self) != len(other):
            return False
    except TypeError:
        return NotImplemented
    try:
        for item in self:
            if item not in other:
                return False
        for item in other:
            if item not in self:
                return False
    except TypeError:
        return NotImplemented
    return True


def _view_set_ne(self, other):
    eq = _view_set_eq(self, other)
    if eq is NotImplemented:
        return NotImplemented
    return not eq


def _view_set_isdisjoint(self, other):
    return not any(item in other for item in self)


# br-vweqset: nx's EdgeView inherits from _Set and supports
# `G.edges == {(0,1), (1,2)}` set-equality. fnx's EdgeView is a bare
# Rust type with no ABC inheritance. Apply _Set.__eq__ semantics to
# EdgeView only. NodeView is a _Mapping in nx — it does NOT compare
# equal to a plain set of nodes (_Mapping.__eq__ returns NotImplemented
# and _Set.__eq__ is False) — so we leave its __eq__ alone.
_EDGE_VIEW_TYPE.__eq__ = _view_set_eq
_EDGE_VIEW_TYPE.__ne__ = _view_set_ne
_EDGE_VIEW_TYPE.isdisjoint = _view_set_isdisjoint
_EDGE_VIEW_TYPE.__hash__ = None  # unhashable once we define __eq__

# br-evsetcmp: EdgeView also missed _Set subset/superset comparisons
# (same fix family as NodeView — br-nvsetcmp below). nx.EdgeView
# inherits collections.abc.Set, so ``{(0,1)} <= G.edges`` works.
# Apply the same _Set-style comparisons to both undirected and
# directed Rust EdgeView types.
def _ev_set_le(self, other):
    try:
        self_len = len(self)
    except TypeError:
        return NotImplemented
    if not hasattr(other, "__contains__") or not hasattr(other, "__iter__"):
        return NotImplemented
    try:
        if self_len > len(other):
            return False
    except TypeError:
        pass
    return all(item in other for item in self)


def _ev_set_ge(self, other):
    if not hasattr(other, "__iter__"):
        return NotImplemented
    try:
        if len(self) < len(other):
            return False
    except TypeError:
        pass
    return all(item in self for item in other)


def _ev_set_lt(self, other):
    try:
        if len(self) >= len(other):
            return False
    except TypeError:
        return NotImplemented
    return _ev_set_le(self, other)


def _ev_set_gt(self, other):
    try:
        if len(self) <= len(other):
            return False
    except TypeError:
        return NotImplemented
    return _ev_set_ge(self, other)


for _ev_type in (
    _EDGE_VIEW_TYPE,
    _DIEDGE_VIEW_TYPE,
    _DiGraphEdgeView,
    _MultiGraphEdgeView,
    _MultiDiGraphEdgeView,
):
    _ev_type.__le__ = _ev_set_le
    _ev_type.__ge__ = _ev_set_ge
    _ev_type.__lt__ = _ev_set_lt
    _ev_type.__gt__ = _ev_set_gt
    _Set.register(_ev_type)
    # br-r37-c1-vmapabc: nx's EdgeView / OutEdgeView / MultiEdgeView /
    # OutMultiEdgeView all inherit from ``collections.abc.Mapping``,
    # so ``isinstance(G.edges, _Mapping)`` returns True. fnx's
    # Rust-bound + Python-wrapped EdgeView types implement the full
    # _Mapping protocol (``__getitem__`` / ``__len__`` / ``__iter__`` /
    # ``__contains__`` / ``keys`` / ``values`` / ``items`` / ``get``)
    # but were not registered as _Mapping virtual subclasses, so the
    # isinstance check returned False — diverging on type-dispatch
    # paths in drop-in code.  Register here to fix.
    _Mapping.register(_ev_type)
_MULTIGRAPH_NODE_VIEW_TYPE.__call__ = _node_view_call_with_attr_support(
    _MULTIGRAPH_NODE_VIEW_CALL
)
_MULTIDIGRAPH_NODE_VIEW_TYPE.__call__ = _node_view_call_with_attr_support(
    _MULTIDIGRAPH_NODE_VIEW_CALL
)
# br-ndvlst: Graph / DiGraph NodeView.__call__ didn't support the string
# ``data='attr'`` form — returning self unchanged. That broke the common
# idiom ``dict(G.nodes(data='attr'))`` because dict() then used keys() +
# __getitem__ (returning the full attrs dict) instead of iterating the
# (node, value) pairs. Extend the same wrapper to Graph/DiGraph views.
_SIMPLE_GRAPH_NODE_VIEW_TYPE = type(Graph().nodes)
_SIMPLE_DIGRAPH_NODE_VIEW_TYPE = type(DiGraph().nodes)
_SIMPLE_GRAPH_NODE_VIEW_CALL = _SIMPLE_GRAPH_NODE_VIEW_TYPE.__call__
_SIMPLE_DIGRAPH_NODE_VIEW_CALL = _SIMPLE_DIGRAPH_NODE_VIEW_TYPE.__call__
_SIMPLE_GRAPH_NODE_VIEW_ITEMS = _SIMPLE_GRAPH_NODE_VIEW_TYPE.items
# br-r37-c1-4b5ie: native (node, attr_dict) bulk builder for DiGraph node
# views — mirrors the Graph fast path so nodes(data='attr') skips the slow
# AllData Python iteration.
_SIMPLE_DIGRAPH_NODE_VIEW_ITEMS = _SIMPLE_DIGRAPH_NODE_VIEW_TYPE.items
# br-r37-c1-4b5ie: native cached items() builders for all four node-view
# types, captured BEFORE the `.items = _mapping_items_view` override below.
# NodeDataView._materialize routes its attr-projection through these so every
# graph class serves the (node, attr_dict) pairs from the nodes_seq-keyed
# node_data_mirror instead of rebuilding them in Python.
_NODE_VIEW_NATIVE_ITEMS = {
    _SIMPLE_GRAPH_NODE_VIEW_TYPE: _SIMPLE_GRAPH_NODE_VIEW_TYPE.items,
    _SIMPLE_DIGRAPH_NODE_VIEW_TYPE: _SIMPLE_DIGRAPH_NODE_VIEW_TYPE.items,
    _MULTIGRAPH_NODE_VIEW_TYPE: _MULTIGRAPH_NODE_VIEW_TYPE.items,
    _MULTIDIGRAPH_NODE_VIEW_TYPE: _MULTIDIGRAPH_NODE_VIEW_TYPE.items,
}
_SIMPLE_GRAPH_NODE_VIEW_TYPE.__call__ = _node_view_call_with_attr_support(
    _SIMPLE_GRAPH_NODE_VIEW_CALL
)
_SIMPLE_DIGRAPH_NODE_VIEW_TYPE.__call__ = _node_view_call_with_attr_support(
    _SIMPLE_DIGRAPH_NODE_VIEW_CALL
)


def _reconstruct_node_view_as_dict(snapshot):
    """Module-level pickle reconstructor for the four Rust-bound
    NodeView types (Graph.nodes, DiGraph.nodes, MultiGraph.nodes,
    MultiDiGraph.nodes). After pickle the value is a plain dict
    `{node: attrs}` — the Rust-bound view type can't be reconstructed
    without a graph backing it, but a dict supports the same iteration,
    indexing, len, and `in`-test protocol as the live NodeView.
    """
    return snapshot


def _node_view_reduce(self):
    """br-r37-c1-nv-pkl: the Rust-bound NodeView types crashed
    pickle with TypeError("cannot pickle 'franken_networkx.NodeView'
    object"). nx pickles G.nodes successfully and restores as a
    NodeView wrapping the snapshotted node dict. fnx's NodeView is
    Rust-bound and can't be reconstructed without a Graph reference,
    so snapshot to a plain dict — preserves data and read protocol
    (iteration, indexing, len, `in`)."""
    snapshot = {node: dict(attrs) for node, attrs in self(data=True)}
    return (_reconstruct_node_view_as_dict, (snapshot,))


_SIMPLE_GRAPH_NODE_VIEW_TYPE.__reduce__ = _node_view_reduce
_SIMPLE_DIGRAPH_NODE_VIEW_TYPE.__reduce__ = _node_view_reduce
_MULTIGRAPH_NODE_VIEW_TYPE.__reduce__ = _node_view_reduce
_MULTIDIGRAPH_NODE_VIEW_TYPE.__reduce__ = _node_view_reduce


# br-r37-c1-vcopy: nx's NodeView preserves type through
# ``copy.copy(G.nodes)`` / ``copy._deepcopy(G.nodes)`` — both return
# a NodeView instance.  fnx's ``__reduce__`` snapshot path made
# copy.copy / _deepcopy return a plain ``dict`` (the snapshot
# product), so ``isinstance(copy.copy(G.nodes), NodeView)`` was
# False.  Rust-bound NodeView types don't allow direct
# instantiation, so:
#   - ``__copy__`` returns self (live wrapper — matches nx's
#     ``copy.copy`` semantic where mutations to G are visible
#     through the copied view).
#   - ``__deepcopy__`` builds a NEW graph populated from the
#     current snapshot and returns its NodeView (matches nx's
#     ``copy._deepcopy`` snapshot semantic — independent of
#     subsequent G mutations).
def _node_view_copy(self):
    return self


_NODE_VIEW_TYPE_TO_GRAPH_CLASS = {}


def _node_view_deepcopy(self, memo):
    # br-r37-c1-vcopydc: nx's _deepcopy of NodeView is a SNAPSHOT
    # — independent of subsequent G mutations.  Materialise via
    # the existing __reduce__ snapshot pattern, but build a new
    # fnx Graph (of the matching class) and return ITS NodeView so
    # ``isinstance(c, NodeView)`` still holds AND mutations to the
    # original G aren't visible through c.
    snapshot = [(node, dict(attrs)) for node, attrs in self(data=True)]
    GraphCls = _NODE_VIEW_TYPE_TO_GRAPH_CLASS.get(type(self), Graph)
    G_new = GraphCls()
    G_new.add_nodes_from((n, a) for n, a in snapshot)
    return G_new.nodes


for _nv_type, _g_cls in (
    (_SIMPLE_GRAPH_NODE_VIEW_TYPE, Graph),
    (_SIMPLE_DIGRAPH_NODE_VIEW_TYPE, DiGraph),
    (_MULTIGRAPH_NODE_VIEW_TYPE, MultiGraph),
    (_MULTIDIGRAPH_NODE_VIEW_TYPE, MultiDiGraph),
):
    _nv_type.__copy__ = _node_view_copy
    _nv_type.__deepcopy__ = _node_view_deepcopy
    _NODE_VIEW_TYPE_TO_GRAPH_CLASS[_nv_type] = _g_cls


def _node_view_eq(self, other):
    """br-r37-c1-nv-eq: nx's NodeView inherits from BOTH _Mapping AND
    _Set (via multiple inheritance), but `__eq__` comes from _Mapping —
    so `G.nodes == G.nodes` is True only when the dict representation
    `{node: attrs}` matches on both sides (same keys AND same
    per-node attribute dicts). `G.nodes == G2.nodes` is False if the
    nodes overlap but attrs differ. `G.nodes == set([0,1])` is False
    because a set has no _Mapping interface.

    The Rust-bound NodeView types fell through to default
    `object.__eq__` (identity), so two view accesses returned False
    even when the node-attr content matched. Match nx's _Mapping
    semantics exactly via dict equality."""
    from collections.abc import Mapping as _Mapping
    if type(other) in _ALL_NODE_VIEW_TYPES:
        return dict(self) == dict(other)
    if isinstance(other, _Mapping):
        return dict(self) == dict(other)
    return NotImplemented


def _node_view_ne(self, other):
    eq = _node_view_eq(self, other)
    if eq is NotImplemented:
        return NotImplemented
    return not eq


_ALL_NODE_VIEW_TYPES = (
    _SIMPLE_GRAPH_NODE_VIEW_TYPE,
    _SIMPLE_DIGRAPH_NODE_VIEW_TYPE,
    _MULTIGRAPH_NODE_VIEW_TYPE,
    _MULTIDIGRAPH_NODE_VIEW_TYPE,
)


def _node_view_isdisjoint(self, other):
    """br-r37-c1-nv-isdisjoint: nx's NodeView inherits from
    `collections.abc.Set` which provides `.isdisjoint(other)`. The
    Rust-bound NodeView types don't have it, so
    `G.nodes.isdisjoint(H.nodes)` raised AttributeError on fnx
    while nx returned True/False. The _Set comparison/algebra
    OPERATORS already work on NodeView (because Python's `<=`,
    `&`, etc. bridge _Mapping-keys-iter to set semantics), but
    `isdisjoint` is a method-name and needs explicit binding."""
    return set(self).isdisjoint(other)


for _nv_type in _ALL_NODE_VIEW_TYPES:
    _nv_type.__eq__ = _node_view_eq
    _nv_type.__ne__ = _node_view_ne
    # br-r37-c1-viewhash: nx's NodeView inherits from
    # ``collections.abc.Mapping``, which sets ``__hash__ = None``.
    # That makes ``hash(G.nodes)`` raise ``TypeError: unhashable
    # type: 'NodeView'`` and forbids using a NodeView as a dict
    # key or set element. fnx previously assigned an id-based
    # ``__hash__`` here, silently accepting the view as hashable
    # — diverging on a contract that drop-in callers rely on
    # (``except TypeError: ...`` around accidental view-in-set
    # patterns).  _Set ``__hash__ = None`` so fnx matches nx.
    # _Set protocol operators (``&``, ``|``, ``<=``, ``isdisjoint``)
    # still work because they iterate the view, not hash it.
    _nv_type.__hash__ = None
    _nv_type.isdisjoint = _node_view_isdisjoint


def _edge_view_reduce(self):
    """br-r37-c1-ev-pkl: the Rust-bound Graph.edges EdgeView crashes
    pickle with TypeError("cannot pickle 'franken_networkx.EdgeView'
    object"). nx pickles G.edges successfully and restores as an
    EdgeView with the same edge sequence. fnx's Rust EdgeView can't
    be reconstructed without a Graph reference, so snapshot to a
    plain list of (u, v) 2-tuples — preserves data and the iteration
    protocol expected by `for u, v in G.edges:` style usage."""
    return (list, (list(self),))


_EDGE_VIEW_TYPE.__reduce__ = _edge_view_reduce


# br-r37-c1-vcopy: same reasoning as _node_view_copy above —
# preserve EdgeView type through copy.copy / copy._deepcopy.
# br-r37-c1-vcopydc: __deepcopy__ must produce a SNAPSHOT
# independent of subsequent G mutations (matches nx).
def _edge_view_copy(self):
    return self


def _edge_view_deepcopy(self, memo):
    # Materialise the edges into a new Graph and return its EdgeView.
    snapshot = [(u, v, dict(attrs)) for u, v, attrs in self(data=True)]
    G_new = Graph()
    # Add all source-graph nodes too so EdgeView reflects same
    # universe (some edge-set operations care about isolated nodes).
    G_new.add_edges_from(snapshot)
    return G_new.edges


_EDGE_VIEW_TYPE.__copy__ = _edge_view_copy
_EDGE_VIEW_TYPE.__deepcopy__ = _edge_view_deepcopy


# br-r37-c1-k147g: Rust-bound view classes had reprs that either
# stringified node IDs (NodeView, DegreeView showed ('0', '1', ...)
# instead of (0, 1, ...)) or showed an opaque _count (EdgeView shows
# "EdgeView(2 edges)"). Override __repr__ to match nx's contract:
# repr lists the actual node/edge content with original types.
# br-r37-c1-mpv5x: nx __str__ on these views returns bare data
# (no class wrapper); add explicit __str__ to match.
def _view_str_list(self):
    return str(list(self))


def _node_view_repr(self):
    return f"NodeView({tuple(self)!r})"


def _edge_view_repr(self):
    # Match nx's class-name conventions (br-r37-c1-k147g):
    # Graph -> EdgeView, DiGraph -> OutEdgeView,
    # MultiGraph -> MultiEdgeView, MultiDiGraph -> OutMultiEdgeView.
    #
    # br-r37-c1-evrname: previously this dispatched on the private
    # ``_DiGraphEdgeView`` / ``_MultiGraphEdgeView`` /
    # ``_MultiDiGraphEdgeView`` qualnames — but elsewhere we already
    # rename ``__name__`` to the canonical nx form, so by the time
    # repr() runs ``type(self).__name__`` is e.g. ``"OutEdgeView"``
    # and the private-name branches never matched, falling through
    # to the default ``EdgeView`` label.  Use ``__name__`` directly
    # since it's already the canonical nx form.
    return f"{type(self).__name__}({list(self)!r})"


def _degree_view_repr(self):
    # br-r37-c1-mdvname: previously hardcoded ``DegreeView`` as the
    # repr label, but nx exposes per-class names — ``DegreeView``
    # (Graph), ``DiDegreeView`` (DiGraph), ``MultiDegreeView``
    # (MultiGraph), ``DiMultiDegreeView`` (MultiDiGraph). Use
    # ``type(self).__name__`` so each picks up its canonical name
    # (the wrapper classes have ``__name__`` set above).
    return f"{type(self).__name__}({dict(self)!r})"


for _nv_cls in (
    type(Graph().nodes),
    type(DiGraph().nodes),
    _MULTIGRAPH_NODE_VIEW_TYPE,
    _MULTIDIGRAPH_NODE_VIEW_TYPE,
):
    _nv_cls.__repr__ = _node_view_repr
    _nv_cls.__str__ = _view_str_list
del _nv_cls

for _ev_cls in (
    type(Graph().edges),
    _DiGraphEdgeView,
    _MultiGraphEdgeView,
    _MultiDiGraphEdgeView,
):
    _ev_cls.__repr__ = _edge_view_repr
    _ev_cls.__str__ = _view_str_list
del _ev_cls

for _dv_cls in (
    type(Graph().degree),
    type(DiGraph().degree),
    type(MultiGraph().degree),
    type(MultiDiGraph().degree),
):
    _dv_cls.__repr__ = _degree_view_repr
    _dv_cls.__str__ = _view_str_list
del _dv_cls


# br-nvrsub: nx.NodeView inherits from collections.abc.Set so
# ``some_set - G.nodes`` works (via _Set.__rsub__). fnx's Rust-native
# NodeView isn't a _Set ABC subclass, so Python's set protocol falls
# back to `set.__sub__(NodeView) -> NotImplemented` then attempts
# `NodeView.__rsub__(set)` which doesn't exist — raising TypeError.
# Broke nx.group_betweenness_centrality's `if set_v - G.nodes:` check.
# Add the missing reflected set-operator methods that mirror a _Set
# protocol over iteration.
def _nv_rsub(self, other):
    return set(other) - set(self)


def _nv_rand(self, other):
    return set(other) & set(self)


def _nv_ror(self, other):
    return set(other) | set(self)


def _nv_rxor(self, other):
    return set(other) ^ set(self)


for _node_view_type in (
    type(Graph().nodes),
    type(DiGraph().nodes),
    _MULTIGRAPH_NODE_VIEW_TYPE,
    _MULTIDIGRAPH_NODE_VIEW_TYPE,
):
    _node_view_type.__rsub__ = _nv_rsub
    _node_view_type.__rand__ = _nv_rand
    _node_view_type.__ror__ = _nv_ror
    _node_view_type.__rxor__ = _nv_rxor


# br-nvsetcmp: nx.NodeView inherits from collections.abc.Set and
# therefore supports ``G.nodes <= {0,1,2}``, ``G.nodes >= other``,
# and the strict variants ``<`` ``>``. fnx's Rust-native NodeView
# only inherits _Mapping, so _Set-style comparisons raised TypeError
# ("not supported between NodeView and set"). Also register as a
# virtual subclass of collections.abc.Set so isinstance(nv, _Set)
# is True (third-party code in nx.algorithms sometimes branches on
# that).
def _nv_set_le(self, other):
    try:
        it_len = len(self)
    except TypeError:
        return NotImplemented
    if not hasattr(other, "__contains__") or not hasattr(other, "__iter__"):
        return NotImplemented
    try:
        if it_len > len(other):
            return False
    except TypeError:
        pass
    return all(item in other for item in self)


def _nv_set_ge(self, other):
    if not hasattr(other, "__iter__"):
        return NotImplemented
    try:
        if len(self) < len(other):
            return False
    except TypeError:
        pass
    return all(item in self for item in other)


def _nv_set_lt(self, other):
    try:
        if len(self) >= len(other):
            return False
    except TypeError:
        return NotImplemented
    return _nv_set_le(self, other)


def _nv_set_gt(self, other):
    try:
        if len(self) <= len(other):
            return False
    except TypeError:
        return NotImplemented
    return _nv_set_ge(self, other)


for _node_view_type in (
    type(Graph().nodes),
    type(DiGraph().nodes),
    _MULTIGRAPH_NODE_VIEW_TYPE,
    _MULTIDIGRAPH_NODE_VIEW_TYPE,
):
    _node_view_type.__le__ = _nv_set_le
    _node_view_type.__ge__ = _nv_set_ge
    _node_view_type.__lt__ = _nv_set_lt
    _node_view_type.__gt__ = _nv_set_gt
    _Set.register(_node_view_type)
    # br-r37-c1-vmapabc: nx's NodeView inherits from
    # ``collections.abc.Mapping`` and ``_Set``. fnx already registers
    # the Rust-bound NodeView types as _Set virtual subclasses (above),
    # but missed _Mapping — so ``isinstance(G.nodes, _Mapping)``
    # returned False, diverging on type-dispatch paths in drop-in
    # code.  The full _Mapping protocol is already implemented
    # (__getitem__ / __len__ / __iter__ / __contains__ / keys /
    # values / items / get), so virtual registration is safe.
    _Mapping.register(_node_view_type)


# br-r37-c1-vkeysview: nx's NodeView (Graph/DiGraph/MultiGraph/
# MultiDiGraph) and MultiEdgeView types return ``KeysView`` /
# ``ValuesView`` / ``ItemsView`` instances from ``.keys()`` /
# ``.values()`` / ``.items()`` (via _Mapping inheritance) — so
# ``G.nodes.keys() & {0, 1, 99}`` returns the set intersection.
# fnx's Rust-bound NodeView ``.keys()`` etc. returned plain
# ``list`` (or generators on Multi*Graph.edges), breaking _Set
# algebra on the result:
#
#   G.nodes.keys() & {0, 1}  →  TypeError(unsupported operand)
#
# Now that the views are registered as _Mapping virtual subclasses
# (above + the EdgeView block), wrap each ``.keys`` / ``.values``
# / ``.items`` to return the proper ``cabc.KeysView`` / ``cabc
# .ValuesView`` / ``cabc.ItemsView`` so set algebra works.
from collections.abc import (
    KeysView as _MapKeysView,
    ValuesView as _MapValuesView,
    ItemsView as _MapItemsView,
)


def _mapping_keys_view(self):
    return _MapKeysView(self)


def _mapping_values_view(self):
    return _MapValuesView(self)


def _mapping_items_view(self):
    return _MapItemsView(self)


# br-r37-c1-nvdata: nx's NodeView.data() returns a ``NodeDataView``
# instance (set-like, supports indexing as _Mapping AND tuple-membership
# semantics). The Rust-bound NodeView's ``data`` method returned the
# underlying NodeView directly, so ``type(G.nodes.data()).__name__``
# was ``NodeView`` instead of ``NodeDataView`` and tuple-form
# membership checks ``(node, attrs) in G.nodes.data()`` raised
# TypeError(unhashable) instead of returning a boolean.  The
# ``__call__(data=True)`` path was already wrapped via
# ``_node_view_call_with_attr_support`` to return NodeDataView; do
# the same for the ``.data()`` method here.
def _node_view_data_method(self, data=True, default=None):
    if data is False:
        return self
    return NodeDataView(
        type(self).__call__, self, data=data, default=default
    )


# nx's NodeDataView inherits from collections.abc.Set so
# ``isinstance(view, _Set)`` returns True. Register the fnx wrapper
# as a _Set virtual subclass to match.  NodeDataView already
# implements __contains__/__iter__/__len__ so the registration is
# safe (no abstract-method gap).
_Set.register(NodeDataView)


for _nv_type in _ALL_NODE_VIEW_TYPES:
    _nv_type.keys = _mapping_keys_view
    _nv_type.values = _mapping_values_view
    _nv_type.items = _mapping_items_view
    _nv_type.data = _node_view_data_method

# Multi*Graph.edges return generators / list_iterator from keys/items/
# values — also wrap to KeysView / ValuesView / ItemsView so set
# algebra works (matching nx's MultiEdgeView _Mapping inheritance).
_MultiGraphEdgeView.keys = _mapping_keys_view
_MultiGraphEdgeView.values = _mapping_values_view
_MultiGraphEdgeView.items = _mapping_items_view
_MultiDiGraphEdgeView.keys = _mapping_keys_view
_MultiDiGraphEdgeView.values = _mapping_values_view
_MultiDiGraphEdgeView.items = _mapping_items_view


# NodeView update support lives on _PrivateNodeFacade (below) rather
# than the view types, since NodeView has no parent-graph attribute.
_DIGRAPH_ADJACENCY_VIEW_TYPE.get = _adjacency_view_get
_DIGRAPH_ADJACENCY_VIEW_TYPE.keys = _adjacency_view_keys
_DIGRAPH_ADJACENCY_VIEW_TYPE.items = _adjacency_view_items
_DIGRAPH_ADJACENCY_VIEW_TYPE.values = _adjacency_view_values
_GRAPH_ADJACENCY_VIEW_TYPE.get = _adjacency_view_get
_GRAPH_ADJACENCY_VIEW_TYPE.keys = _adjacency_view_keys
_GRAPH_ADJACENCY_VIEW_TYPE.items = _adjacency_view_items
_GRAPH_ADJACENCY_VIEW_TYPE.values = _adjacency_view_values
MultiAdjacencyView.get = _adjacency_view_get
MultiAdjacencyView.keys = _adjacency_view_keys
MultiAdjacencyView.items = _adjacency_view_items
MultiAdjacencyView.values = _adjacency_view_values
AdjacencyView.get = _adjacency_view_get
AdjacencyView.keys = _adjacency_view_keys
AdjacencyView.items = _adjacency_view_items
AdjacencyView.values = _adjacency_view_values
AtlasView.get = _adjacency_view_get
AtlasView.keys = _adjacency_view_keys
AtlasView.items = _adjacency_view_items
AtlasView.values = _adjacency_view_values
Graph.adjlist_inner_dict_factory = dict
Graph.adjlist_outer_dict_factory = dict
Graph.edge_attr_dict_factory = dict
Graph.graph_attr_dict_factory = dict
Graph.node_attr_dict_factory = dict
Graph.node_dict_factory = dict
Graph.adj = property(_graph_adj_view)
Graph.__getitem__ = _graph_getitem_from_adj
DiGraph.adjlist_inner_dict_factory = dict
DiGraph.adjlist_outer_dict_factory = dict
DiGraph.edge_attr_dict_factory = dict
DiGraph.graph_attr_dict_factory = dict
DiGraph.node_attr_dict_factory = dict
DiGraph.node_dict_factory = dict
DiGraph.adj = property(_digraph_adj_view)
DiGraph.__getitem__ = _graph_getitem_from_adj
DiGraph.succ = property(_digraph_succ_view)
DiGraph.pred = property(_digraph_pred_view)
MultiGraph.adjlist_inner_dict_factory = dict
MultiGraph.adjlist_outer_dict_factory = dict
MultiGraph.edge_attr_dict_factory = dict
MultiGraph.graph_attr_dict_factory = dict
MultiGraph.node_attr_dict_factory = dict
MultiGraph.node_dict_factory = dict
MultiGraph.edge_key_dict_factory = dict
MultiGraph.new_edge_key = _multigraph_new_edge_key
Graph.edge_subgraph = _multigraph_edge_subgraph
DiGraph.edge_subgraph = _multigraph_edge_subgraph
MultiGraph.edge_subgraph = _multigraph_edge_subgraph
MultiGraph.adj = property(_multigraph_adj_view)
MultiGraph.edges = property(_multigraph_edges)
MultiDiGraph.edges = property(_multidigraph_edges)
MultiGraph.degree = property(MultiGraphDegreeView)
DiGraph.edges = property(_digraph_edges)
# br-r37-c1-b3cnf follow-up: cache DiGraph in/out_degree wrappers
# (same pattern as MultiDiGraph variants below).
def _digraph_in_degree(self):
    cache = vars(self)
    view = cache.get("_fnx_view_in_degree")
    if view is None:
        view = _InDegreeView(self, "pred")
        cache["_fnx_view_in_degree"] = view
    return view


def _digraph_out_degree(self):
    cache = vars(self)
    view = cache.get("_fnx_view_out_degree")
    if view is None:
        view = _OutDegreeView(self, "succ")
        cache["_fnx_view_out_degree"] = view
    return view


DiGraph.in_degree = property(_digraph_in_degree)
DiGraph.out_degree = property(_digraph_out_degree)
MultiDiGraph.adjlist_inner_dict_factory = dict
MultiDiGraph.adjlist_outer_dict_factory = dict
MultiDiGraph.edge_attr_dict_factory = dict
MultiDiGraph.graph_attr_dict_factory = dict
MultiDiGraph.node_attr_dict_factory = dict
MultiDiGraph.node_dict_factory = dict
MultiDiGraph.edge_key_dict_factory = dict
MultiDiGraph.new_edge_key = _multigraph_new_edge_key
MultiDiGraph.edge_subgraph = _multigraph_edge_subgraph
MultiDiGraph.succ = property(_multidigraph_succ_view)
MultiDiGraph.pred = property(_multidigraph_pred_view)
MultiDiGraph.adj = property(_multidigraph_adj_view)
MultiDiGraph.degree = property(MultiDiGraphDegreeView)
# br-r37-c1-b3cnf follow-up: cache MultiDiGraph in/out_degree wrappers
# (Graph.degree + DiGraph.in/out_degree already cache via their
# private-aware property; multi variants need their own caching path
# since they go through a different factory).
def _multidigraph_in_degree(self):
    cache = vars(self)
    view = cache.get("_fnx_view_in_degree")
    if view is None:
        view = _InMultiDegreeView(self, "pred")
        cache["_fnx_view_in_degree"] = view
    return view


def _multidigraph_out_degree(self):
    cache = vars(self)
    view = cache.get("_fnx_view_out_degree")
    if view is None:
        view = _OutMultiDegreeView(self, "succ")
        cache["_fnx_view_out_degree"] = view
    return view


MultiDiGraph.in_degree = property(_multidigraph_in_degree)
MultiDiGraph.out_degree = property(_multidigraph_out_degree)

# br-privadj: many nx internals reach into the private `G._adj`, `G._node`,
# `G._succ`, `G._pred` dict storage (e.g. connected_components._plain_bfs,
# bipartite.is_bipartite_node_set). Alias the private names to the public
# views so nx's internal read paths work on fnx graphs; writes through
# these aliases fall back to the AdjacencyView which already forwards to
# the Rust storage.
class _PrivateNodeFacade:
    """br-nvupdt: nx internals (relabel._relabel_copy) do
    ``H._node.update((node, attrs_dict) for ...)`` — a dict-style bulk
    insert. The NodeView has no way to reach the parent graph, so the
    public ``_node`` alias returns this thin facade that wraps the
    NodeView for reads and forwards bulk writes back through
    ``graph.add_node``.
    """

    __slots__ = ("_graph",)

    def __init__(self, graph):
        self._graph = graph

    def __iter__(self):
        return iter(self._graph.nodes)

    def __len__(self):
        return len(self._graph.nodes)

    def __contains__(self, node):
        return node in self._graph.nodes

    def __getitem__(self, node):
        return self._graph.nodes[node]

    def __setitem__(self, node, attrs):
        if node in self._graph:
            existing = self._graph.nodes[node]
            existing.clear()
            if attrs:
                existing.update(attrs)
        else:
            self._graph.add_node(node, **(dict(attrs) if attrs else {}))

    def __delitem__(self, node):
        self._graph.remove_node(node)

    def update(self, other=None, **kwargs):
        if other is not None:
            if hasattr(other, "items"):
                iterable = other.items()
            else:
                iterable = other
            for node, attrs in iterable:
                self[node] = attrs
        if kwargs:
            for node, attrs in kwargs.items():
                self[node] = attrs

    def get(self, node, default=None):
        if node in self._graph:
            return self._graph.nodes[node]
        return default

    def keys(self):
        return list(iter(self))

    def items(self):
        return [(n, self._graph.nodes[n]) for n in self]

    def values(self):
        return [self._graph.nodes[n] for n in self]


Graph._adj = property(_graph_adj_view)
Graph._node = property(lambda self: _PrivateNodeFacade(self))
DiGraph._adj = property(_digraph_adj_view)
DiGraph._node = property(lambda self: _PrivateNodeFacade(self))
DiGraph._succ = property(_digraph_succ_view)
DiGraph._pred = property(_digraph_pred_view)
MultiGraph._adj = property(_multigraph_adj_view)
MultiGraph._node = property(lambda self: _PrivateNodeFacade(self))
MultiDiGraph._adj = property(_multidigraph_adj_view)
MultiDiGraph._node = property(lambda self: _PrivateNodeFacade(self))
MultiDiGraph._succ = property(_multidigraph_succ_view)
MultiDiGraph._pred = property(_multidigraph_pred_view)


# br-grattrset: nx internals (subgraph_view, restricted_view, and any
# code that builds a new graph and does ``newG.graph = G.graph``) need
# ``G.graph`` to be assignable. The Rust-native ``.graph`` is a
# read-only ``getset_descriptor`` (only a getter), so the assignment raised
# ``AttributeError``. Upstream assignment aliases the new graph dict by
# reference; keep that behavior through a Python-side override.
_GRAPH_ATTR_OVERRIDE = "_fnx_graph_attr_override"
_GRAPH_ATTR_MISSING = object()


_GRAPH_ATTR_FACTORY_CACHE = {}


class _GraphAttrsDescriptor:
    """Descriptor that adds an assignment path to the Rust-native
    read-only ``graph`` attribute."""

    __slots__ = ("_raw",)

    def __init__(self, raw):
        self._raw = raw

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        override = vars(obj).get(_GRAPH_ATTR_OVERRIDE, _GRAPH_ATTR_MISSING)
        if override is not _GRAPH_ATTR_MISSING:
            return override
        # br-r37-c1-gattfact (cycle 220): nx's documented subclass
        # extension point ``graph_attr_dict_factory`` allows callers
        # to define a custom graph-attribute container type:
        #
        #     class MyGraph(nx.Graph):
        #         graph_attr_dict_factory = MyDictType
        #
        # nx invokes the factory in ``__init__`` (``self.graph =
        # self.graph_attr_dict_factory()``).  fnx ignored the factory
        # and exposed the Rust-native attr-dict directly, so
        # ``MyGraph().graph`` was always a plain ``dict`` — drop-in
        # subclasses with a custom factory silently lost their
        # custom container type and any default contents.
        #
        # Lazily materialize through the factory on first access
        # (only when the subclass overrode it; the default ``dict``
        # path still uses the Rust-native fast path).
        # br-r37-c1-7q6wh: whether a class overrides the factory cannot
        # differ between instances of it, but this ran a full MRO walk on EVERY
        # `G.graph` read — and `G.name` is `self.graph.get("name", "")`, so it
        # paid it too. Measured at 0.0372us of a 0.2067us access. Memoised per
        # class, the same shape as br-r37-c1-vaayu's shadow-installer memo and
        # br-r37-c1-8itxk before it; the per-INSTANCE override check above is
        # untouched. Same staleness envelope as those: it goes stale only if a
        # CLASS's factory is rebound after an instance of it has been read, and
        # module-level patching happens at import, before any instance exists.
        factory = _GRAPH_ATTR_FACTORY_CACHE.get(objtype, _GRAPH_ATTR_MISSING)
        if factory is _GRAPH_ATTR_MISSING:
            factory = getattr(objtype, "graph_attr_dict_factory", dict)
            _GRAPH_ATTR_FACTORY_CACHE[objtype] = factory
        if factory is not dict:
            existing = self._raw.__get__(obj, objtype)
            new_attrs = factory()
            if existing:
                new_attrs.update(existing)
                # Clear the Rust-side dict so we don't double-track.
                if hasattr(existing, "clear"):
                    existing.clear()
            setattr(obj, _GRAPH_ATTR_OVERRIDE, new_attrs)
            return new_attrs
        return self._raw.__get__(obj, objtype)

    def __set__(self, obj, value):
        # br-grattrident: the attribute's own test pins an in-place
        # clear-then-update contract ("before = G.graph; G.graph = {...};
        # assert before is G.graph"). A straight store breaks that
        # identity. Mutate the existing dict object (Rust-native or
        # previously-stored override) instead, so external references
        # continue to see the updated contents.
        current = self.__get__(obj, type(obj))
        # br-r37-c1-iorgrf (cycle 223): Python's in-place dict
        # operators (``g.graph |= other``, ``g.graph |= {...}``)
        # desugar to ``g.graph = dict.__ior__(g.graph, other)``.
        # ``dict.__ior__`` mutates the dict in-place and returns
        # ``self`` — so ``value is current``.  The
        # ``current.clear()`` line below would then clear the very
        # dict whose merged-in contents we want to keep.  Detect
        # this and short-circuit.
        if current is value:
            setattr(obj, _GRAPH_ATTR_OVERRIDE, current)
            return
        if isinstance(current, dict) and isinstance(value, dict):
            current.clear()
            current.update(value)
            setattr(obj, _GRAPH_ATTR_OVERRIDE, current)
        else:
            setattr(obj, _GRAPH_ATTR_OVERRIDE, value)

    def __delete__(self, obj):
        vars(obj).pop(_GRAPH_ATTR_OVERRIDE, None)
        self._raw.__get__(obj, type(obj)).clear()


for _cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
    _cls.graph = _GraphAttrsDescriptor(_cls.__dict__["graph"])


# br-r37-c1-clrovr (cycle 221): the cycle-220 ``graph_attr_dict_factory``
# override stores the live attrs dict in ``vars(obj)[_GRAPH_ATTR_OVERRIDE]``.
# The Rust-bound ``clear()`` clears the Rust-side attrs but doesn't know
# about the override, so subclasses with a custom factory saw stale
# attrs after ``g.clear()``.  nx's ``Graph.clear`` does ``self.graph.clear()``
# in-place — the dict identity is preserved, contents emptied.  Wrap
# ``clear`` here to mirror that contract for the override.
def _detach_rows_before_clear(graph):
    """br-r37-c1-s5pxs: let a HELD adjacency row outlive clear().

    networkx's ``G.adj[u]`` wraps the inner ``_adj[u]`` dict, and ``clear()``
    rebinds ``_adj`` to a fresh dict — so a reference someone already holds keeps
    its old contents: stale, but alive and readable. Graph and DiGraph already
    match, because their rows are backed by a Rust-maintained live PyDict that
    ``clear()`` drops from the map without emptying the dict object itself
    (br-r37-c1-v9auw says so in as many words).

    The multigraph rows are native views onto the graph's storage, so clearing
    the storage emptied them — ``list(row)`` read ``[]`` where networkx reads
    ``['b']``. Before br-r37-c1-znpkv captured the row it raised ``KeyError``
    instead; neither answer was parity.

    Snapshotting at CLEAR time rather than at capture time is what keeps the
    liveness contracts that already match: a captured row must still see later
    ``add_edge``/``remove_edge``/parallel-edge churn, and it does, because
    nothing is frozen until the clear actually happens.

    br-r37-c1-wdgb8: TWO CACHES, NOT ONE, and missing the second made the fix
    above hold for ``G.adj[u]`` and not for ``G[u]``. The adjacency view keeps
    its rows on itself (``_fnx_row_cache`` / ``_fnx_atlas_cache``), but
    ``G[u]`` is served by ``_multigraph_getitem_from_native_row`` and its
    siblings, which cache on the GRAPH's instance dict under
    ``_fnx_getitem_atlas_cache``. The sweep below walks ``vars(graph)`` looking
    for views with those attributes, and that entry is a plain
    ``(nodes_seq, {node: row})`` tuple, so ``getattr(tuple, ...)`` skipped it
    silently. Measured before the fix: ``G.adj[u][v]`` served its snapshot on
    all four classes while ``G[u][v]`` raised ``KeyError('vvv')``, where
    networkx serves the snapshot for both.

    The weak, node-indexed registry also reaches rows whose lookup cache was
    replaced by an unrelated mutation. It retains neither dead rows nor their
    node buckets; a held row is tracked only for its actual lifetime.
    """
    storage = vars(graph)
    registry = storage.get("_fnx_held_multigraph_rows")
    if registry:
        rows = [reference() for bucket in registry.values() for reference in bucket.values()]
        registry.clear()
        for row in rows:
            if row is not None:
                _detach_row(row)
    # br-r37-c1-wdgb8: the `G[u]` cache, which lives on the graph itself.
    own_rows = storage.get("_fnx_getitem_atlas_cache")
    if own_rows:
        for row in tuple(own_rows[1].values()):
            _detach_row(row)
    for view in tuple(storage.values()):
        for cache_name in ("_fnx_row_cache", "_fnx_atlas_cache"):
            cache = getattr(view, cache_name, None)
            if not cache:
                continue
            for row in tuple(cache[1].values()):
                _detach_row(row)


def _detach_rows_before_node_removal(graph, node, *, removed_before=()):
    """Detach only cached rows whose own node is about to disappear.

    A held NetworkX ``G.adj[node]`` is backed by that node's inner dict. Node
    removal detaches the dict, so re-adding the same node must not make the old
    view identify the new row. Rows for every other node remain live, including
    across the index renumbering caused by this removal.
    """
    storage = vars(graph)
    registry = storage.get("_fnx_held_multigraph_rows", {})
    rows = [reference() for reference in registry.pop(node, {}).values()]
    caches = [storage.get("_fnx_getitem_atlas_cache")]
    caches.extend(
        getattr(view, cache_name, None)
        for view in tuple(storage.values())
        for cache_name in ("_fnx_row_cache", "_fnx_atlas_cache")
    )
    for cache in caches:
        if not cache:
            continue
        row = cache[1].get(node)
        if row is not None:
            rows.append(row)
    for row in rows:
        if row is None:
            continue
        # Batch compaction happens later, but a retired row must reflect
        # the removals before its own turn, never those after it. Graph's
        # loop deletes its own self entry; DiGraph only does so in pred.
        remove_self = (
            not graph.is_directed()
            or getattr(row, "_fnx_row_kind", "adj") == "pred"
        )
        _detach_row(
            row,
            removed_before=removed_before,
            removed_node=node,
            remove_self=remove_self,
        )
