

# br-r37-c1-xsrkr: nx Graph uses object's default identity-based
# __eq__ and __hash__. The Rust binding implemented content-based
# __eq__, which (a) made fnx.path_graph(3) == fnx.path_graph(3)
# return True (False on nx) and (b) caused Python to set
# __hash__ = None, breaking ``set([G1, G2])``. Override to match
# nx's drop-in semantics on all four Graph classes.
for _G_cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
    _G_cls.__eq__ = object.__eq__
    _G_cls.__hash__ = object.__hash__
del _G_cls


# br-r37-c1-mpv5x: nx Graph.__str__ includes the graph name when set:
# "Graph named 'foo' with N nodes and E edges". The Rust binding
# returned the name-less form unconditionally.
def _graph_str(self):
    return "".join(
        [
            type(self).__name__,
            f" named {self.name!r}" if self.name else "",
            f" with {self.number_of_nodes()} nodes and {self.number_of_edges()} edges",
        ]
    )


for _G_cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
    _G_cls.__str__ = _graph_str
del _G_cls

Graph.copy = _copy_preserving_insertion_order
DiGraph.copy = _copy_preserving_insertion_order
MultiGraph.copy = _copy_preserving_insertion_order
MultiDiGraph.copy = _copy_preserving_insertion_order
Graph.subgraph = _subgraph_with_view(_GRAPH_SUBGRAPH)
DiGraph.subgraph = _subgraph_with_view(_DIGRAPH_SUBGRAPH)
MultiGraph.subgraph = _subgraph_with_view(_MULTIGRAPH_SUBGRAPH)
MultiDiGraph.subgraph = _subgraph_with_view(_MULTIDIGRAPH_SUBGRAPH)
Graph.to_directed = _graph_to_directed_with_view(_GRAPH_TO_DIRECTED)
DiGraph.to_directed = _digraph_to_directed_with_view(_DIGRAPH_TO_DIRECTED)
MultiGraph.to_directed = _multigraph_to_directed_with_view(_MULTIGRAPH_TO_DIRECTED)
MultiDiGraph.to_directed = _multidigraph_to_directed_with_view(_MULTIDIGRAPH_TO_DIRECTED)
Graph.to_undirected = _to_undirected_with_view(_GRAPH_TO_UNDIRECTED)
DiGraph.to_undirected = _directed_to_undirected_with_view(_DIGRAPH_TO_UNDIRECTED)
MultiGraph.to_undirected = _to_undirected_with_view(_MULTIGRAPH_TO_UNDIRECTED)
MultiDiGraph.to_undirected = _directed_to_undirected_with_view(
    _MULTIDIGRAPH_TO_UNDIRECTED
)


def _digraph_to_directed_deepcopy_fastpath(wrapped):
    # Conversion copies graph data into a mutable graph, independently deep-copying
    # each attribute dictionary. Whole-object deepcopy also carries frozen/custom
    # instance state and shares a memo across dictionaries. Native deepcopy holds
    # a Rust borrow while invoking user callbacks, preventing source mutations.
    # Keep structural cloning for graphs without node/edge attributes; attributed
    # graphs follow the normal construction order so callback changes remain visible.
    import functools as _functools

    @_functools.wraps(wrapped)
    def to_directed(self, as_view=False):
        if (
            as_view is not True
            and type(self) is DiGraph
            and not _has_networkx_private_storage(self)
            and self.to_directed_class() is DiGraph
        ):
            # Preserve the source mode without changing the ambient mode seen by
            # attribute callbacks. Copies start with fresh decision history.
            with compatibility_mode(self.mode):
                result = DiGraph()
            result.graph.update(_deepcopy(self.graph))
            # A graph-attribute callback may have changed the source, including
            # installing private storage. Admit the native route only afterward.
            if (
                not _has_networkx_private_storage(self)
                and not _graph_has_any_attrs(self)
                and type(result.graph) is dict
            ):
                graph_attrs = result.graph
                result = self._native_copy()
                result.graph.clear()
                result.graph.update(graph_attrs)
            else:
                result.add_nodes_from(
                    (node, _deepcopy(attrs)) for node, attrs in self.nodes(data=True)
                )
                result.add_edges_from(
                    (source, target, _deepcopy(attrs))
                    for source in self
                    for target, attrs in self.adj[source].items()
                )
            result.drain_decision_records()
            return result
        return wrapped(self, as_view=as_view)

    return to_directed


DiGraph.to_directed = _digraph_to_directed_deepcopy_fastpath(DiGraph.to_directed)


def _graph_to_undirected_deepcopy_fastpath(wrapped):
    # br-r37-c1-dgtodir (cc): symmetric to the DiGraph.to_directed fast path — an
    # already-undirected Graph's to_undirected() is a full deep copy into the same
    # class, so route to a native deep copy. Simple Graph had no native shortcut (MultiGraph already
    # routes to _native_to_undirected_deepcopy). NOTE: only the undirected->Graph
    # case is a deepcopy; DiGraph.to_undirected COLLAPSES reciprocal edges and is
    # left untouched. Subclasses / nx-private storage / custom to_undirected_class /
    # as_view fall through.
    import functools as _functools

    @_functools.wraps(wrapped)
    def to_undirected(self, as_view=False):
        if (
            as_view is not True
            and type(self) is Graph
            and not _has_networkx_private_storage(self)
            and self.to_undirected_class() is Graph
        ):
            native = getattr(self, "_native_to_undirected_deepcopy", None)
            if native is not None:
                return native()
            return _deepcopy(self)
        return wrapped(self, as_view=as_view)

    return to_undirected


Graph.to_undirected = _graph_to_undirected_deepcopy_fastpath(Graph.to_undirected)


# br-r37-c1-methodqualname: align ``method.__qualname__`` (and
# ``__name__``) on the wrapped Graph methods with nx's canonical
# ``Graph.method`` form so:
# (a) ``inspect.signature(method)`` and ``method.__qualname__``
#     introspection looks the same as nx (debug repr, test fixtures,
#     drop-in libraries that branch on qualname)
# (b) Python's auto-generated TypeError on duplicate kwargs uses the
#     nx wording ``Graph.method() got multiple values for ...``
#     instead of leaking the fnx-private wrapper closure name.
#
# Same shape as cycle 173 br-r37-c1-updatename on Graph.update and
# the DegreeView / EdgeView class-name renames in cycles 157 / 166.
def _rename_method(method, name, qualname):
    try:
        method.__name__ = name
        method.__qualname__ = qualname
    except (AttributeError, TypeError):
        pass


# For each (class, method) combination, rename the directly-defined
# method to ``ClassName.method``.  Iteration order Graph -> DiGraph
# -> MultiGraph -> MultiDiGraph means shared function objects (eg.
# ``copy`` is shared across all 4 classes) get the qualname of the
# FIRST class that uses them — matching nx's "Graph.copy"
# convention for the inherited case.  fnx splits most other methods
# (add_edge, remove_edge, has_node, size, etc.) into per-class
# functions, so each class gets its own ``Class.method`` qualname
# matching nx exactly.
_METHOD_NAMES = (
    "add_edge", "remove_edge", "add_edges_from", "remove_edges_from",
    "add_node", "add_nodes_from", "remove_node", "remove_nodes_from",
    "has_node", "has_edge", "number_of_edges", "size", "copy",
    "edge_subgraph", "predecessors", "successors", "reverse",
)
_rename_seen = set()
for _cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
    for _meth_name in _METHOD_NAMES:
        # Only consider methods directly defined on this class
        # (not inherited via MRO).  Methods inherited from a base
        # already had their qualname set when the base was processed.
        _meth = vars(_cls).get(_meth_name)
        if _meth is None or id(_meth) in _rename_seen:
            continue
        _rename_seen.add(id(_meth))
        _rename_method(
            _meth, _meth_name, f"{_cls.__name__}.{_meth_name}",
        )
del _cls, _meth_name, _meth, _rename_seen, _METHOD_NAMES


class _ConversionNodeView(_Mapping):
    def __init__(self, view):
        self._view = view

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        return self._view._graph.nodes[node]

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
        return f"NodeView({tuple(self)})"

    def __and__(self, other):
        return set(self) & set(other)

    def __rand__(self, other):
        return set(other) & set(self)

    def __or__(self, other):
        return set(self) | set(other)

    def __ror__(self, other):
        return set(other) | set(self)

    def __sub__(self, other):
        return set(self) - set(other)

    def __rsub__(self, other):
        return set(other) - set(self)

    def __xor__(self, other):
        return set(self) ^ set(other)

    def __rxor__(self, other):
        return set(other) ^ set(self)


# br-r37-c1-77tw1: networkx's name - nodes() returns this view now.
_ConversionNodeView.__name__ = _ConversionNodeView.__qualname__ = "NodeView"


class _ConversionEdgeView:
    def __init__(self, view):
        self._view = view

    def __iter__(self):
        # br-r37-c1-cev-mditer: nx's MultiEdgeView/InMultiEdgeView
        # default `keys=True` for __iter__ but `keys=False` for
        # __call__ (asymmetric). Match that on conversion views too.
        if self._view.is_multigraph():
            return iter(self._list(keys=True))
        return iter(self._list())

    def __len__(self):
        # br-r37-c1-ktsxn: ask the view for its COUNT instead of building the
        # whole edge list to measure it. This is not a micro-fix: CPython's
        # `list(obj)` calls `__len__` for preallocation BEFORE iterating, so with
        # the old body every `list(view.edges)` built the edge list TWICE.
        # Measured on 400 nodes / 1600 edges: `EV()` alone was 469.6us while
        # `list(EV)` was 1463.8us -- the ~1000us difference was the second build,
        # not the copy.
        #
        # `number_of_edges()` is the same number by construction and was verified
        # equal to BOTH `len(self())` and the actual iteration length, against
        # networkx, on all six conversion shapes (Graph/DiGraph/MultiGraph/
        # MultiDiGraph into both directions) -- including the multigraph cases,
        # where the count is the KEYED count and `__iter__` likewise iterates
        # `keys=True`.
        return self._view.number_of_edges()

    def __contains__(self, edge):
        # br-r37-c1-ex1s6: networkx's edge view membership. This ignored a
        # multigraph edge's key - (0, 1, 7) in the view was True - and
        # answered False for a malformed probe where networkx raises.
        view = self._view
        return _nx_edge_view_contains_by_has_edge(
            view, edge, "out" if view.is_directed() else "undirected", view.is_multigraph()
        )

    def __getitem__(self, edge):
        u, v = edge
        if u not in self._view._graph or v not in self._view.adj[u]:
            raise KeyError(edge)
        return self._view.adj[u][v]

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        return _view_edges_call(self, self._view, nbunch, data, keys, default)

    def _list(self, nbunch=None, data=False, keys=False, default=None):
        if isinstance(data, str):
            base = self._view._edges(nbunch=nbunch, data=True, keys=keys)
            if keys:
                return [
                    (u, v, k, attrs.get(data, default))
                    for u, v, k, attrs in base
                ]
            return [
                (u, v, attrs.get(data, default)) for u, v, attrs in base
            ]
        if data is None:
            base = self._view._edges(nbunch=nbunch, data=False, keys=keys)
            if keys:
                return [(u, v, k, default) for u, v, k in base]
            return [(u, v, default) for u, v in base]
        return self._view._edges(nbunch=nbunch, data=data, keys=keys)

    def data(self, data=True, default=None, nbunch=None, keys=False):
        return self(nbunch=nbunch, data=data, keys=keys, default=default)

    def __and__(self, other):
        return set(self) & set(other)

    def __rand__(self, other):
        return set(other) & set(self)

    def __or__(self, other):
        return set(self) | set(other)

    def __ror__(self, other):
        return set(other) | set(self)

    def __sub__(self, other):
        return set(self) - set(other)

    def __rsub__(self, other):
        return set(other) - set(self)

    def __xor__(self, other):
        return set(self) ^ set(other)

    def __rxor__(self, other):
        return set(other) ^ set(self)

    # br-r37-c1-cev-setops: nx's converted-view EdgeView inherits from
    # _Set; the wrapper had |/&/-/^ but missing <=/</>=/>/isdisjoint
    # and __eq__. Same defect family as br-r37-c1-{fbtk0, s89yr};
    # identical fix shape on a different wrapper class.
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

    def __eq__(self, other):
        from collections.abc import Set as _Set
        if isinstance(other, _ConversionEdgeView):
            return set(self) == set(other)
        if isinstance(other, _Set):
            return set(self) == set(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    __hash__ = None

    def __repr__(self):
        # br-r37-c1-77tw1: networkx's EdgeView repr, under the class names the
        # subclasses below carry; edges() returns this view now.
        return f"{type(self).__name__}({list(self)})"

    get = _adjacency_view_get
    keys = _adjacency_view_keys
    items = _adjacency_view_items
    values = _adjacency_view_values


_CONVERSION_EDGE_VIEW_TYPES = {
    (directed, multigraph): type(name, (_ConversionEdgeView,), {})
    for (directed, multigraph), name in (
        ((False, False), "EdgeView"),
        ((True, False), "OutEdgeView"),
        ((False, True), "MultiEdgeView"),
        ((True, True), "OutMultiEdgeView"),
    )
}


class _UnionKeyAtlas(_Mapping):
    """networkx's ``AtlasView(UnionAtlas(succ, pred))``: a pair's key dict in a
    to_undirected(as_view=True) view of a MultiDiGraph - one side ``{}`` when
    the pair runs one way only.

    br-r37-c1-u7szm: networkx iterates ``set(succ.keys()) | set(pred.keys())``,
    hash order; this walked the succ keys and then the rest of the pred keys,
    so a pair with keys 1024 and 5 one way and 0 the other came out
    [1024, 5, 0] where networkx gives [1024, 0, 5]. And it printed as an object
    where networkx prints ``AtlasView(UnionAtlas({...}, {...}))``.
    """

    __slots__ = ("_primary", "_secondary")

    def __init__(self, primary, secondary):
        self._primary = primary
        self._secondary = secondary

    def __iter__(self):
        return iter(set(self._primary.keys()) | set(self._secondary.keys()))

    def __len__(self):
        return len(self._primary.keys() | self._secondary.keys())

    def __getitem__(self, key):
        if key in self._primary:
            return self._primary[key]
        return self._secondary[key]

    def copy(self):
        return {key: self[key].copy() for key in self}

    def _union_repr(self):
        return f"UnionAtlas({dict(self._primary)!r}, {dict(self._secondary)!r})"

    def __repr__(self):
        return f"{type(self).__name__}({self._union_repr()})"

    def __str__(self):
        return str({key: self[key] for key in self})


_UnionKeyAtlas.__name__ = _UnionKeyAtlas.__qualname__ = "AtlasView"


class _ConversionNeighborMap(_Mapping):
    def __init__(self, view, node, *, reverse=False):
        self._view = view
        self._node = node
        self._reverse = reverse

    def __iter__(self):
        if self._reverse:
            yield from self._view._pred_neighbors(self._node)
        else:
            yield from self._view._adj_neighbors(self._node)

    def __len__(self):
        return sum(1 for _ in self)

    def __getitem__(self, neighbor):
        if self._reverse:
            return self._view._pred_neighbor_value(self._node, neighbor)
        return self._view._adj_neighbor_value(self._node, neighbor)

    def copy(self):
        # Copy the mapping/attribute layers, not objects stored as attributes.
        return {neighbor: self[neighbor].copy() for neighbor in self}

    # br-r37-c1-u7szm: networkx's row is AtlasView / AdjacencyView (multigraph)
    # over the mapping it reads - the source's row dict, or, in an undirected
    # view of a directed graph, UnionAtlas / UnionMultiInner of the succ and
    # pred rows - and prints as ``ClassName(<that mapping's repr>)``.
    def _source_rows(self):
        view, node = self._view, self._node
        source = view._graph
        multi = view._multigraph

        def plain(row):
            if multi:
                return {nbr: dict(keydict) for nbr, keydict in row.items()}
            return dict(row)

        if source.is_directed() and not view._directed:
            return plain(source.succ[node]), plain(source.pred[node])
        if source.is_directed():
            return plain((source.pred if self._reverse else source.succ)[node]), None
        return plain(source.adj[node]), None

    def __repr__(self):
        rows, pred = self._source_rows()
        if pred is None:
            return f"{type(self).__name__}({rows!r})"
        union = "UnionMultiInner" if self._view._multigraph else "UnionAtlas"
        return f"{type(self).__name__}({union}({rows!r}, {pred!r}))"

    def __str__(self):
        rows, pred = self._source_rows()
        if pred is None:
            return str(rows)
        if not self._view._multigraph:
            return str({nbr: self[nbr] for nbr in self})
        # UnionMultiInner's str shows each key dict as its bare UnionAtlas.
        inner = ", ".join(f"{nbr!r}: {self[nbr]._union_repr()}" for nbr in self)
        return "{" + inner + "}"


# networkx's row class names, keyed by multigraph.
_CONVERSION_ROW_TYPES = {
    False: type("AtlasView", (_ConversionNeighborMap,), {}),
    True: type("AdjacencyView", (_ConversionNeighborMap,), {}),
}


class _ConversionAdjacencyView(_Mapping):
    def __init__(self, view, *, reverse=False):
        self._view = view
        self._reverse = reverse

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def copy(self):
        return {node: self[node].copy() for node in self}

    def __getitem__(self, node):
        # br-r37-c1-2r06n: the wrapped graph's ADJACENCY decides, not its node
        # view. nx's `to_directed(as_view=True)` builds a view whose `_succ` IS
        # the source graph's `_adj`, so a node carried only by an assigned `_adj`
        # is present here. Asking `node not in self._view._graph` asked the node
        # set, and since `_Mapping.__contains__` routes through this subscript,
        # it also made `u in view.succ` answer False -- which is why rewriting
        # `has_successor` alone changed nothing.
        #
        # The two are the same set on an ordinary graph, one adjacency row per
        # node, so this is the previous behaviour there.
        if node not in self._view._graph.adj:
            # br-r37-c1-ndro1: networkx indexes the wrapped graph's own mapping
            # here (its _adj / _succ dict, or a filtered parent's
            # FilterAdjacency), so the KeyError is that mapping's: KeyError('x')
            # over a graph, "Key x not found" over a filtered view.
            self._view._graph.adj[node]
            raise KeyError(node)
        return _CONVERSION_ROW_TYPES[self._view._multigraph](
            self._view, node, reverse=self._reverse
        )
