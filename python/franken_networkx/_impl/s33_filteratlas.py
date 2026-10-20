

class _ReverseEdgeView:
    def __init__(self, view):
        self._view = view

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        return _view_edges_call(self, self._view, nbunch, data, keys, default)

    def _list(self, nbunch=None, data=False, keys=False, default=None):
        if (
            nbunch is None
            and data is False
            and keys is False
            and type(self._view._graph) is DiGraph
        ):
            native = getattr(self._view._graph, "_native_reverse_edges_no_data", None)
            if native is not None:
                return native()
        return self._view._edges(nbunch=nbunch, data=data, keys=keys, default=default)

    def __iter__(self):
        # br-r37-c1-rev-mditer: nx's MultiEdgeView/InMultiEdgeView
        # default keys=True for __iter__ but keys=False for __call__
        # (asymmetric). Match across reverse views too.
        if self._view._graph.is_multigraph():
            return iter(self._list(keys=True))
        return iter(self._list())

    def __len__(self):
        return self._view._graph.number_of_edges()

    def __contains__(self, edge):
        # reverse_view iterates (u, v) where v is in the original graph's pred[u]
        # (original edge v -> u becomes reversed edge u -> v).
        # br-r37-c1-ex1s6: networkx's (Out)(Multi)EdgeView membership over
        # those rows (_nx_edge_view_contains): a malformed probe raises, a
        # multigraph pair is key 0 and a triple's key counts.
        graph = self._view._graph
        return _nx_edge_view_contains(graph.pred, edge, "out", graph.is_multigraph())

    def __getitem__(self, edge):
        u, v = edge
        if u not in self._view._graph:
            raise KeyError(edge)
        pred_u = self._view._graph.pred[u]
        if v not in pred_u:
            raise KeyError(edge)
        return pred_u[v]

    def data(self, data=True, default=None, nbunch=None, keys=False):
        return self(nbunch=nbunch, data=data, keys=keys, default=default)

    # br-r37-c1-rev-setops: nx's reverse view edges inherit from _Set;
    # the wrapper had no _Set protocol at all. Same defect family as
    # br-r37-c1-{fbtk0, s89yr, ovudh}; identical fix shape on a
    # different wrapper class.
    def __eq__(self, other):
        from collections.abc import Set as _Set
        if isinstance(other, _ReverseEdgeView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

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

    __hash__ = None

    def __repr__(self):
        # br-r37-c1-revadjname: nx's reverse-view edges repr as
        # ``OutEdgeView([...])`` / ``OutMultiEdgeView([...])``.
        # Subclasses below set ``__name__`` to the canonical form.
        return f"{type(self).__name__}({list(self)!r})"

    # br-r37-c1-revvcopy: __copy__ returns self (live wrapper —
    # matches nx).  __deepcopy__ snapshots via deep-copy of the
    # underlying directed graph + reverse + .edges (cycle 200 dual;
    # snapshot semantics for _deepcopy).
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        new_graph = _deepcopy(self._view._graph, memo)
        new_reverse = new_graph.reverse(copy=False)
        return new_reverse.edges

    get = _adjacency_view_get
    keys = _adjacency_view_keys
    items = _adjacency_view_items
    values = _adjacency_view_values


_FILTERED_VIEW_MUTATORS = (
    "add_node",
    "add_nodes_from",
    "remove_node",
    "remove_nodes_from",
    "add_edge",
    "add_edges_from",
    "add_weighted_edges_from",
    "remove_edge",
    "remove_edges_from",
    "clear",
    "clear_edges",
    "update",
)


# br-r37-c1-revadjname: 2 trivial _ReverseEdgeView subclasses with
# canonical nx ``__name__`` so ``type(R.edges).__name__`` matches
# nx's ``OutEdgeView`` / ``OutMultiEdgeView``.  Factory in
# _ReverseDirectedViewBase.edges dispatches based on multi-ness.
class _ReverseOutEdgeView(_ReverseEdgeView):
    pass
_ReverseOutEdgeView.__name__ = "OutEdgeView"


class _ReverseOutMultiEdgeView(_ReverseEdgeView):
    pass
_ReverseOutMultiEdgeView.__name__ = "OutMultiEdgeView"


# br-r37-c1-revouter: outer class name parity for reverse-view —
# nx returns ``DiGraph`` / ``MultiDiGraph`` from
# ``DG.reverse(copy=False)``. fnx's wrappers had private names.
_ReverseDirectedView.__name__ = "DiGraph"
_ReverseMultiDirectedView.__name__ = "MultiDiGraph"


def _fast_pred_row(graph, node):
    # br-r37-c1-r3gjb/gchm1: G.pred[node] re-materialises the whole
    # predecessor adjacency (O(N+E)); the native per-node row accessor is
    # O(deg). Prefer the *_dict variant (DiGraph) which returns a PLAIN
    # dict-of-dicts identical to nx's exposed type; fall back to the
    # AtlasView-returning _native_predecessor_row (MultiDiGraph) for the
    # count-only callers (subgraph degree), else the slow view.
    # br-r37-c1-kum9v: only call the native row accessors on a CONCRETE
    # graph. A filtered/reverse VIEW inherits these methods from its base
    # class but has an EMPTY Rust base, so native_dict(node) raises KeyError
    # for a nested subgraph's view parent. type() (not getattr) gates it; the
    # view falls through to graph.pred[node] (the filter-aware adjacency).
    if type(graph) in (DiGraph, MultiDiGraph) and not _has_networkx_private_storage(graph):
        native_dict = getattr(graph, "_native_predecessor_row_dict", None)
        if native_dict is not None:
            return native_dict(node)
        native = getattr(graph, "_native_predecessor_row", None)
        if native is not None:
            return native(node)
    return graph.pred[node]


def _fast_succ_row(graph, node):
    # br-r37-c1-gchm1: type-correct O(deg) successor row (plain dict-of-dicts)
    # for reverse/filtered views; falls back to G[node] (native succ).
    # cc-succrowoV: the DiGraph branch used to build the whole-graph
    # `_native_adjacency_dict()[node]` (O(V+E)) merely for the neighbour KEY
    # ORDER, then overlay `_native_successor_row_dict(node)` for live attrs — so
    # every per-node caller (reverse-view in/out_degree hit it once per node ->
    # reverse.in_degree was O(V^2), 844ms @ n=1000) paid a whole-graph rebuild.
    # The per-row accessor already yields the SAME key order AND live attrs
    # (verified byte-identical over mutated / edge-removed graphs), so use it
    # alone — O(deg), byte-identical output.
    if _has_networkx_private_storage(graph):
        return graph.succ[node]
    if type(graph) is DiGraph:
        native_row = getattr(graph, "_native_successor_row_dict", None)
        if native_row is not None:
            return native_row(node)
    if type(graph) is MultiDiGraph:  # br-r37-c1-kum9v: views -> G[node]
        native_dict = getattr(graph, "_native_successor_row_dict", None)
        if native_dict is not None:
            return native_dict(node)
    return graph[node]


def _fast_adj_row(graph, node):
    # br-r37-c1-r3gjb: plain dict-of-dicts adjacency row (O(deg), O(1)
    # per-neighbour lookup) vs G[node] (AtlasView, ~15x slower per fetch).
    if type(graph) in (Graph, MultiGraph):  # br-r37-c1-kum9v: views -> G[node]
        native_dict = getattr(graph, "_native_adjacency_row_dict", None)
        if native_dict is not None:
            return native_dict(node)
    return graph[node]


class _FilteredNeighborMap(_Mapping):
    def __init__(self, view, node, *, reverse=False):
        self._view = view
        self._node = node
        self._reverse = reverse
        if _point_query_uses_private_rows(view._graph):
            adjacency = view._graph._pred if reverse and view.is_directed() else view._graph._adj
            self._private_row = adjacency[node]

    def _raw_neighbors(self):
        if "_private_row" in self.__dict__:
            return self._private_row
        # br-r37-c1-subadjrow: use the parent graph's native per-node
        # __getitem__ (G[node]) instead of G.adj[node] / G.succ[node].
        # The latter go through the (Multi)AdjacencyView whose _atlas()
        # RE-MATERIALISES the entire parent adjacency on EVERY call
        # (~22ms for a 2k-node multigraph), so a filtered subgraph copy
        # — which hits this once per visible (node, neighbour) — was
        # O(E * (N+E)) (MultiGraph subgraph().copy() was 16305x nx /
        # timed out >8s). G[node] is the native O(deg) row accessor
        # (~0.001ms) and returns the identical neighbour mapping. The
        # reverse (predecessor) direction has no native getitem
        # equivalent, so it keeps pred[node] (slower; see follow-up).
        if self._view.is_directed():
            if self._reverse:
                return _fast_pred_row(self._view._graph, self._node)
            return self._view._graph[self._node]
        return self._view._graph[self._node]

    def _edge_visible(self, neighbor, key=None):
        if self._reverse:
            return self._view._edge_visible(neighbor, self._node, key)
        return self._view._edge_visible(self._node, neighbor, key)

    def __iter__(self):
        if "_private_row" in self.__dict__ and not self._view.is_multigraph():
            # FilterAtlas constructs its row iterator now; FilterMultiInner's
            # generator instead delays that operation until its first next().
            return (neighbor for neighbor in self._private_row
                    if self._view._node_visible(neighbor) and self._edge_visible(neighbor))
        return self._iter_neighbors()

    def _iter_neighbors(self):
        row = self._raw_neighbors()
        view = self._view
        # br-r37-c1-ag2sx: DEFAULT edge filter + set node filter — a neighbour
        # is visible iff BOTH endpoints are in the keep-set. self._node is
        # constant here, so check it once, then gate each neighbour with a C
        # `in keep` membership instead of the per-neighbour _node_visible /
        # _edge_visible Python method calls (MultiGraph subgraph copy/edges
        # walk this once per (node, neighbour) — ~6.8x nx). Row/keep iteration
        # ORDER is preserved exactly (same node_ok_shorter branch as nx's
        # FilterMultiInner), so edge order is unchanged.
        keep = getattr(view._filter_node, "nodes", None)
        if keep is not None and view._filter_edge_is_default:
            if self._node not in keep:
                return
            if view.is_multigraph():
                node_ok_shorter = 2 * len(keep) < len(row)
                if node_ok_shorter:
                    for neighbor in keep:
                        if neighbor in row:
                            yield neighbor
                    return
                for neighbor in row:
                    if neighbor in keep:
                        yield neighbor
                return
            for neighbor in row:
                if neighbor in keep:
                    yield neighbor
            return
        if view.is_multigraph():
            # br-r37-c1-0ek49: nx's FilterMultiInner.__iter__ receives the
            # view's NODE_OK (which carries the keep-set as `.nodes`) and
            # switches to iterating that SET — CPython set order, not row
            # order — whenever `2 * len(keep) < len(row)`. Simple-graph rows
            # get a bare closure in nx (no `.nodes`), so only MULTIGRAPH
            # rows take this branch. Metamorphic seed 1157 diverged on
            # exactly this (`subgraph([1, 3]).copy()` over a 5-neighbor row).
            keep = getattr(view._filter_node, "nodes", None)
            node_ok_shorter = False
            if keep is not None:
                try:
                    node_ok_shorter = 2 * len(keep) < len(row)
                except TypeError:
                    node_ok_shorter = False
            # br-r37-c1-k3vnp: this loop needs only the edge KEYS of each
            # (node, neighbour) pair, to ask whether ANY of them is visible.
            # Reaching them through `row.items()` / `row[neighbour]` builds the
            # whole keydict VALUE view per neighbour — cProfile put
            # `AdjacencyView.__getitem__` and `_multi_edge_keydict` at 14.7 calls
            # each per single `adj[u]` lookup, and the row measured 0.0860x
            # against networkx. `_native_edge_key_set` answers the same question
            # in 1.45us against 16.85us for five neighbours, an 11.6x cheaper
            # accessor for exactly the fact being asked for.
            #
            # It returns a SET, which is sound here because the result is fed to
            # `any()`: only whether SOME key passes matters, not the order they
            # are tried in. A filter_edge with side effects could observe the
            # evaluation order, but nx calls filter_edge repeatedly and treats it
            # as a pure predicate throughout. Key-set equality with
            # `row[neighbour]` was verified over ~26000 pairs across both
            # multigraph classes at two sizes, including self-loops, and the
            # directed orientation was checked not to answer for the reverse arc.
            # CONCRETE parents only. A reverse/filtered view DELEGATES
            # `_native_edge_key_set` to something underneath it without
            # reorienting, and on a reverse view it answers the empty set for
            # BOTH orientations — so a `getattr` probe finds a method that is
            # present, callable, and silently wrong. Caught by
            # test_reverse_view_supports_edge_subgraph_without_fallback, which
            # went red on exactly this: reverse_view(G).edge_subgraph([(b,a,1)])
            # returned no edges at all. `type(...) is` rather than isinstance for
            # the same reason the rest of this file uses it.
            parent = view._graph
            key_set = (
                getattr(parent, "_native_edge_key_set", None)
                if type(parent) in (MultiGraph, MultiDiGraph)
                and not _has_networkx_private_storage(parent)
                else None
            )
            if key_set is not None:
                # The stored arc runs neighbour -> self._node in the reverse
                # (predecessor) direction, so the endpoints must be swapped to
                # match; `_edge_visible` does the same swap for the same reason.
                if self._reverse:
                    def _keys(neighbor):
                        return key_set(neighbor, self._node)
                else:
                    def _keys(neighbor):
                        return key_set(self._node, neighbor)

                if node_ok_shorter:
                    for neighbor in keep:
                        if neighbor in row and any(
                            self._edge_visible(neighbor, key)
                            for key in _keys(neighbor)
                        ):
                            yield neighbor
                    return
                for neighbor in row:
                    if not view._node_visible(neighbor):
                        continue
                    if any(
                        self._edge_visible(neighbor, key) for key in _keys(neighbor)
                    ):
                        yield neighbor
                return
            if node_ok_shorter:
                for neighbor in keep:
                    if neighbor in row and any(
                        self._edge_visible(neighbor, key) for key in row[neighbor]
                    ):
                        yield neighbor
                return
            for neighbor, edge_data in row.items():
                if not view._node_visible(neighbor):
                    continue
                if any(self._edge_visible(neighbor, key) for key in edge_data):
                    yield neighbor
            return
        # br-r37-c1-k3vnp: the simple-graph branch bound `edge_data` from
        # `row.items()` and never used it — `_edge_visible(neighbor)` takes no
        # key here, because a simple graph has one edge per pair. Materialising
        # every neighbour's attribute dict to discard it is the same
        # build-the-value-to-yield-the-key defect as the multigraph branch
        # above, in its plainest form: iterating `row` yields the same
        # neighbours in the same order and touches no values.
        for neighbor in row:
            if not view._node_visible(neighbor):
                continue
            if self._edge_visible(neighbor):
                yield neighbor

    def __len__(self):
        return sum(1 for _ in self)

    def __getitem__(self, neighbor):
        if not self._view._node_visible(neighbor):
            # br-r37-c1-ex1s6: networkx's FilterAtlas tests `key in atlas`
            # first, a dict lookup - TypeError for an unhashable key.
            _HASH_PROBE.get(neighbor)
            raise KeyError(f"Key {neighbor} not found")

        if self._view.is_multigraph():
            keydict = self._raw_neighbors()[neighbor]
            filtered = _FilteredKeyDict(
                (key, attrs)
                for key, attrs in keydict.items()
                if self._edge_visible(neighbor, key)
            )
            if filtered:
                return filtered
        else:
            if self._edge_visible(neighbor):
                return self._raw_neighbors()[neighbor]

        raise KeyError(f"Key {neighbor} not found")


class _FilteredKeyDict(dict):
    """br-r37-c1-ex1s6: a filtered multigraph pair's {key: attrs}.
    networkx's is a FilterAtlas, which words a missing key 'Key k not
    found' (and hashes the key first, as a dict does); a plain dict raised
    KeyError(k). Still a dict, named and pickled as one, as before."""

    __slots__ = ()

    def __missing__(self, key):
        raise KeyError(f"Key {key} not found")

    def __reduce__(self):
        return (dict, (dict(self),))


_FilteredKeyDict.__name__ = _FilteredKeyDict.__qualname__ = "dict"


class FilterAtlas(_Mapping):
    def __init__(self, view, node, *, reverse=False):
        self._neighbors = _FilteredNeighborMap(view, node, reverse=reverse)

    def __iter__(self):
        return iter(self._neighbors)

    def __len__(self):
        return len(self._neighbors)

    def __getitem__(self, key):
        return self._neighbors[key]


class _NodeSetFilter:
    """Callable node filter carrying the selected set for sparse iteration."""

    __slots__ = ("nodes",)

    def __init__(self, nodes, *, copy_nodes=True):
        if copy_nodes or not isinstance(nodes, set):
            self.nodes = set(nodes)
        else:
            self.nodes = nodes

    def __call__(self, node):
        return node in self.nodes


class _FilteredAdjacencyView(_Mapping):
    def __init__(self, view, *, reverse=False):
        self._view = view
        self._reverse = reverse

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        if not self._view._node_visible(node):
            raise KeyError(f"Key {node} not found")
        private_rows = _point_query_uses_private_rows(self._view)
        if private_rows:
            row = _FilteredNeighborMap(self._view, node, reverse=self._reverse)
            atlas_getter = lambda: row
        else:
            atlas_getter = lambda: _FilteredNeighborMap(
                self._view, node, reverse=self._reverse
            )
        if self._view.is_multigraph():
            if private_rows:
                return AdjacencyView(atlas_getter, native_iter=lambda: iter(row))
            return AdjacencyView(atlas_getter)
        return AtlasView(atlas_getter)


def _filtered_public_adjacency_view(view, *, reverse=False):
    atlas_getter = lambda: _FilteredAdjacencyView(view, reverse=reverse)
    if view.is_multigraph():
        return MultiAdjacencyView(atlas_getter)
    return AdjacencyView(atlas_getter)


def _node_attrs_for_view_graph(graph, node):
    graph_nodes = graph.nodes
    try:
        return graph_nodes[node]
    except TypeError:
        pass
    except KeyError:
        raise
    if callable(graph_nodes):
        for current_node, attrs in graph_nodes(data=True):
            if current_node == node:
                return attrs
    raise KeyError(f"Key {node} not found")


class _ViewEdgeDataView:
    """br-r37-c1-77tw1: what a VIEW's ``edges(nbunch, data=..., keys=...)``
    call returns - networkx's EdgeDataView contract over the view. It was a
    plain list: no liveness, no networkx class name, and ``(v, u) in``
    answered by list scan. Live (each read walks the view again), nbunch
    resolved once, at the call, through ``nbunch_iter`` (networkx's
    ``dict.fromkeys(viewer._graph.nbunch_iter(nbunch))``: its errors, its
    dedup), membership by lookup under networkx's rules: an undirected
    edge in either orientation, touching nbunch at either end; a directed
    one starting in nbunch; a multiedge by its key when ``keys``, else any
    of its keys. The subclasses carry networkx's class names."""

    __slots__ = ("_view", "_nbunch", "_nbset", "_data", "_default", "_keys", "_produce")

    def __init__(self, view, nbunch, data, default, keys, produce):
        self._view = view
        if nbunch is None:
            self._nbunch = self._nbset = None
        else:
            # br-r37-c1-ex1s6: kept as networkx keeps it, a dict - membership
            # words an unhashable probe as a dict key.
            self._nbset = dict.fromkeys(view.nbunch_iter(nbunch))
            self._nbunch = list(self._nbset)
        self._data = data
        self._default = default
        self._keys = keys
        self._produce = produce

    def __iter__(self):
        return iter(self._produce(self._nbunch))

    def __len__(self):
        # br-r37-c1-pgpg1: list() asks for the length before it iterates, so
        # this walked the view twice. A conversion view's whole edge count is
        # its number_of_edges (br-r37-c1-ktsxn checked the two equal on all
        # six conversions), which most of them answer without the walk.
        if self._nbunch is None and isinstance(self._view, _ConversionGraphViewBase):
            return self._view.number_of_edges()
        return len(self._produce(self._nbunch))

    def __contains__(self, e):
        # br-r37-c1-ex1s6: the graph classes' data-view membership, one
        # implementation of networkx's rules for both; the in-edge views
        # (a reverse view's in_edges(...)) look the edge up in pred[v].
        view = self._view
        kind = self._kind
        return _nx_edge_data_view_contains(
            _edge_rows(view, kind),
            e,
            kind,
            view.is_multigraph(),
            self._data,
            self._default,
            self._keys,
            self._nbset,
        )

    def __str__(self):
        return str(list(self))

    def __repr__(self):
        return f"{type(self).__name__}({list(self)})"


_VIEW_EDGE_DATA_VIEW_TYPES = {
    (kind, multigraph): type(name, (_ViewEdgeDataView,), {"__slots__": (), "_kind": kind})
    for (kind, multigraph), name in (
        (("undirected", False), "EdgeDataView"),
        (("out", False), "OutEdgeDataView"),
        (("in", False), "InEdgeDataView"),
        (("undirected", True), "MultiEdgeDataView"),
        (("out", True), "OutMultiEdgeDataView"),
        (("in", True), "InMultiEdgeDataView"),
    )
}


def _view_edges_call(edge_view, view, nbunch, data, keys, default):
    """br-r37-c1-77tw1: networkx's ``EdgeView.__call__`` for a view's edge
    view: the view itself for a plain call (a multigraph's only with
    ``keys=True``), else a live data view over ``edge_view._list``."""
    if nbunch is None and data is False and (keys is True or not view.is_multigraph()):
        return edge_view
    kind = getattr(edge_view, "_fnx_edge_kind", None) or (
        "out" if view.is_directed() else "undirected"
    )
    return _VIEW_EDGE_DATA_VIEW_TYPES[(kind, view.is_multigraph())](
        view,
        nbunch,
        data,
        default,
        keys,
        lambda frozen: edge_view._list(frozen, data, keys, default),
    )


class _ViewNodeDataView(_Set):
    """br-r37-c1-77tw1: what a VIEW's ``nodes(data=...)`` call returns -
    networkx's NodeDataView over the view's node mapping (it was a list):
    a live Set, ``(n, d) in`` and ``[n]`` by lookup, networkx's repr."""

    __slots__ = ("_nodes", "_data", "_default")

    def __init__(self, nodes, data, default):
        self._nodes = nodes
        self._data = data
        self._default = default

    @classmethod
    def _from_iterable(cls, it):
        try:
            return set(it)
        except TypeError as err:
            if "unhashable" in str(err):
                msg = " : Could be b/c data=True or your values are unhashable"
                raise TypeError(str(err) + msg) from err
            raise

    def __len__(self):
        return len(self._nodes)

    def __iter__(self):
        data = self._data
        if data is True:
            return iter(self._nodes.items())
        default = self._default
        return (
            (n, dd[data] if data in dd else default) for n, dd in self._nodes.items()
        )

    def __contains__(self, n):
        try:
            node_in = n in self._nodes
        except TypeError:
            n, d = n
            return n in self._nodes and self[n] == d
        if node_in is True:
            return node_in
        try:
            n, d = n
        except (TypeError, ValueError):
            return False
        return n in self._nodes and self[n] == d

    def __getitem__(self, n):
        if isinstance(n, slice):
            raise NetworkXError(
                f"{type(self).__name__} does not support slicing, "
                f"try list(G.nodes.data())[{n.start}:{n.stop}:{n.step}]"
            )
        ddict = self._nodes[n]
        data = self._data
        if data is True:
            return ddict
        return ddict[data] if data in ddict else self._default

    def __str__(self):
        return str(list(self))

    def __repr__(self):
        if self._data is True:
            return f"NodeDataView({dict(self)})"
        return f"NodeDataView({dict(self)}, data={self._data!r})"


_ViewNodeDataView.__name__ = _ViewNodeDataView.__qualname__ = "NodeDataView"


class NodeView(_Mapping):
    def __init__(self, view):
        self._view = view

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        # br-r37-c1-sc825: sibling of the reverse-adjacency guard — nx's
        # FilterAtlas hashes the key, so an unhashable index is a TypeError
        # here too, not a KeyError about a node that was never valid.
        _HASH_PROBE.get(node)
        if not self._view._node_visible(node):
            raise KeyError(f"Key {node} not found")
        return _node_attrs_for_view_graph(self._view._graph, node)

    def __call__(self, data=False, default=None):
        # br-r37-c1-77tw1: networkx's NodeView.__call__ - the view itself, or
        # a live NodeDataView; this returned lists.
        if data is False:
            return self
        return _ViewNodeDataView(self, data, default)

    def data(self, data=True, default=None):
        if data is False:
            return self
        return _ViewNodeDataView(self, data, default)

    def __repr__(self):
        # br-r37-c1-snvrepr: nx's subgraph-view NodeView repr is
        # ``NodeView((node1, node2, ...))`` — same format as the
        # graph-level NodeView. fnx's subgraph NodeView is a
        # different class (``franken_networkx.NodeView`` defined
        # alongside _FilteredEdgeView; not the Rust-backed NodeView
        # used on plain Graph) and had no ``__repr__``, falling
        # through to default ``<...object at 0x...>``.
        return f"NodeView({tuple(self)!r})"

    def __copy__(self):
        # Live wrapper — matches nx's copy.copy semantics.
        return self

    def __deepcopy__(self, memo):
        # br-r37-c1-vcopydc (cycle 201 follow-up): default _deepcopy
        # recursively copied ``self._view`` (the subgraph view),
        # which materialises to a plain frozen Graph via
        # _FilteredGraphView.__deepcopy__ — that Graph lacks
        # ``_node_visible``, so subsequent NodeView attribute access
        # raised AttributeError.  Snapshot via the deep-copied
        # subgraph and return its ``.nodes`` (Rust-bound NodeView,
        # ``__name__ == "NodeView"`` matching nx).
        new_graph = _deepcopy(self._view, memo)
        return new_graph.nodes


class _FilteredEdgeView:
    # br-r37-c1-ex1s6: the view's shape, set by the subclasses below.
    _fnx_edge_kind = _fnx_multi = None

    def __init__(self, view):
        self._view = view

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        return _view_edges_call(self, self._view, nbunch, data, keys, default)

    def _list(self, nbunch=None, data=False, keys=False, default=None):
        if isinstance(data, str):
            base = self._view._edges(nbunch=nbunch, data=True, keys=keys)
            if keys:
                return [
                    (u, v, k, attrs.get(data, default)) for u, v, k, attrs in base
                ]
            return [
                (u, v, attrs.get(data, default)) for u, v, attrs in base
            ]
        # br-edgesnone: `data=None, default=X` yields 3-tuples with the
        # default as the third element for every edge (matches nx).
        if data is None:
            base = self._view._edges(nbunch=nbunch, data=False, keys=keys)
            if keys:
                return [(u, v, k, default) for u, v, k in base]
            return [(u, v, default) for u, v in base]
        return self._view._edges(nbunch=nbunch, data=data, keys=keys)

    def __iter__(self):
        # br-r37-c1-fev-mditer: nx's MultiEdgeView/InMultiEdgeView/etc.
        # default `keys=True` for __iter__ but `keys=False` for
        # __call__ (asymmetric). Match that exactly so
        # `for u, v, k in sg.edges:` works on MultiGraph/MultiDiGraph
        # subgraph views — parity with the canonical-class fix
        # br-r37-c1-bnydo on _DiEdgeMethodView.
        if self._view.is_multigraph():
            return iter(self._list(keys=True))
        return iter(self._list())

    def __len__(self):
        return len(self._list())

    def __contains__(self, edge):
        # br-r37-c1-j0oc5: on a multigraph view the KEY is part of the edge's
        # identity: `(u, v, bogus) in view` is False.
        # br-r37-c1-ex1s6: networkx's edge view membership - a bare pair means
        # key 0, as in networkx's MultiEdgeView (j0oc5 answered False for
        # it), and a malformed probe raises what networkx's unpacking raises.
        # The view's shape is its class's (the four subclasses below); two
        # is_directed / is_multigraph calls per probe cost 20 percent.
        view = self._view
        kind = self._fnx_edge_kind
        if kind is None:
            kind = "out" if view.is_directed() else "undirected"
            multi = view.is_multigraph()
        else:
            multi = self._fnx_multi
        return _nx_edge_view_contains_by_has_edge(view, edge, kind, multi)

    def __getitem__(self, edge):
        # br-r37-c1-j0oc5: same split. nx indexes a multigraph edge view by
        # (u, v, key) and raises KeyError when that key is absent; the
        # unconditional two-way unpack here raised ValueError for every
        # multigraph subscript, including the well-formed one.
        if self._view.is_multigraph():
            u, v, key = edge
            if not self._view.has_edge(u, v, key):
                raise KeyError(key)
            return self._view.adj[u][v][key]
        u, v = edge
        if not self._view.has_edge(u, v):
            raise KeyError(edge)
        return self._view.adj[u][v]

    def data(self, data=True, default=None, nbunch=None, keys=False):
        return self(nbunch=nbunch, data=data, keys=keys, default=default)

    get = _adjacency_view_get
    keys = _adjacency_view_keys
    items = _adjacency_view_items
    values = _adjacency_view_values

    # br-filtedgeop: nx.EdgeView inherits from _Set, so `G.edges - some_iter`
    # works via _Set.__sub__. fnx's _FilteredEdgeView had no set-operator
    # methods, breaking nx._min_cycle_basis which does
    # `chords = G.edges - tree_edges - {(v, u) for u, v in tree_edges}`.
    def __sub__(self, other):
        return set(self) - set(other)

    def __rsub__(self, other):
        return set(other) - set(self)

    def __or__(self, other):
        return set(self) | set(other)

    def __ror__(self, other):
        return set(other) | set(self)

    def __and__(self, other):
        return set(self) & set(other)

    def __rand__(self, other):
        return set(other) & set(self)

    def __xor__(self, other):
        return set(self) ^ set(other)

    def __rxor__(self, other):
        return set(other) ^ set(self)

    def __eq__(self, other):
        # br-r37-c1-fev-eq: subgraph view's edges crashed `view==view`
        # because each `sg.edges` access creates a fresh
        # _FilteredEdgeView instance. The previous __eq__ only
        # handled set/frozenset, falling through to NotImplemented
        # for another _FilteredEdgeView — Python then used default
        # identity comparison which returned False. nx's
        # filtered EdgeView is set-like; match its content-based
        # equality across all set-like types.
        from collections.abc import Set as _Set
        if isinstance(other, _FilteredEdgeView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    # br-r37-c1-fev-setops: nx's filtered EdgeView inherits from _Set
    # so all comparison + isdisjoint work. The previous fnx wrapper
    # had partial coverage (-, |, &, ^) but missing <=, <, >=, >,
    # and isdisjoint.
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

    __hash__ = None

    def __repr__(self):
        # br-r37-c1-fevname: nx's subgraph-view edges repr matches the
        # parent class form ``EdgeView([...])`` / ``OutEdgeView([...])``
        # / ``MultiEdgeView([...])`` / ``OutMultiEdgeView([...])``.
        # fnx previously fell through to default ``<...object at
        # 0x...>``. Use ``type(self).__name__`` so the four subclasses
        # below pick up the canonical nx label.
        if self._view.is_multigraph():
            return f"{type(self).__name__}({self._list(keys=True)!r})"
        return f"{type(self).__name__}({self._list()!r})"

    def __copy__(self):
        # Live wrapper — matches nx's copy.copy semantics.
        return self

    def __deepcopy__(self, memo):
        # br-r37-c1-vcopydc (cycle 211): default _deepcopy recursively
        # copied ``self._view`` (the subgraph view), which materialises
        # to a plain frozen Graph via _FilteredGraphView.__deepcopy__
        # — that Graph lacks ``_edges`` (the filter machinery), so
        # subsequent .edges attribute access raised AttributeError.
        # Snapshot via the deep-copied subgraph and return its
        # ``.edges`` (Rust-bound EdgeView, ``__name__`` matches nx).
        new_graph = _deepcopy(self._view, memo)
        return new_graph.edges


# br-r37-c1-fevname: per-direction × multi subclasses with canonical
# nx __name__ so type(S.edges).__name__ matches nx for subgraph
# views.  The factory at SubgraphView.edges dispatches based on
# is_directed() / is_multigraph().
class _FilteredGraphEdgeView(_FilteredEdgeView):
    _fnx_edge_kind, _fnx_multi = "undirected", False
_FilteredGraphEdgeView.__name__ = "EdgeView"


class _FilteredOutEdgeView(_FilteredEdgeView):
    _fnx_edge_kind, _fnx_multi = "out", False
_FilteredOutEdgeView.__name__ = "OutEdgeView"


class _FilteredMultiEdgeView(_FilteredEdgeView):
    _fnx_edge_kind, _fnx_multi = "undirected", True
_FilteredMultiEdgeView.__name__ = "MultiEdgeView"


class _FilteredOutMultiEdgeView(_FilteredEdgeView):
    _fnx_edge_kind, _fnx_multi = "out", True
_FilteredOutMultiEdgeView.__name__ = "OutMultiEdgeView"


def _default_node_set_filter_chain(view):
    graph = view
    chain = []
    while isinstance(graph, _FilteredGraphView):
        if not graph._filter_edge_is_default:
            return None, None, None
        keep = getattr(graph._filter_node, "nodes", None)
        if keep is None:
            return None, None, None
        chain.append(keep)
        graph = graph._graph
    if type(graph) not in (Graph, DiGraph, MultiGraph, MultiDiGraph):
        return None, None, None
    chain.reverse()
    visible = set(chain[0])
    for keep in chain[1:]:
        visible.intersection_update(keep)
    return graph, chain, visible


def _multigraph_filtered_target_order(row, filter_chain):
    targets = list(row)
    for keep in filter_chain:
        try:
            keep_is_shorter = 2 * len(keep) < len(targets)
        except TypeError:
            keep_is_shorter = False
        if keep_is_shorter:
            present = set(targets)
            targets = [target for target in keep if target in present]
        else:
            targets = [target for target in targets if target in keep]
    return targets


# br-r37-c1-fvgetattr: memoised one-edge graphs, keyed by the PARENT class,
# used to answer "could this attribute exist?" without copying the parent.
_FILTERED_VIEW_ATTR_PROBE = {}
