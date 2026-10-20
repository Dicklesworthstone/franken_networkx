

class _ConversionDegreeView:
    """br-r37-c1-fabqo: networkx's degree view over a to_directed /
    to_undirected(as_view=True) view - the contract of
    ``reportviews.DiDegreeView``: ``G.degree`` iterates (node, degree)
    pairs, ``G.degree[n]`` is one degree, ``G.degree(weight=...)`` and
    ``G.degree(nbunch)`` are views again and ``G.degree(n)`` is an int. The
    view's ``degree`` was a plain method returning a generator, so
    ``dict(view.degree)`` and ``describe(view)`` raised TypeError. The count
    is still the view's own routine (``_compute`` names it), which keeps the
    native count for the unweighted degree of an undirected view of a
    DiGraph.
    """

    __slots__ = ("_graph", "_nodes", "_weight")
    _compute = "_degree_compute"

    def __init__(self, G, nbunch=None, weight=None):
        self._graph = G
        self._nodes = G if nbunch is None else list(G.nbunch_iter(nbunch))
        self._weight = weight

    def __call__(self, nbunch=None, weight=None):
        if nbunch is None:
            if weight == self._weight:
                return self
            return type(self)(self._graph, None, weight)
        try:
            if nbunch in self._nodes:
                if weight == self._weight:
                    return self[nbunch]
                return type(self)(self._graph, None, weight)[nbunch]
        except TypeError:
            pass
        return type(self)(self._graph, nbunch, weight)

    def __getitem__(self, n):
        G = self._graph
        # networkx indexes a plain dict: its TypeError for an unhashable node,
        # KeyError(n) for a missing one.
        _HASH_PROBE.get(n)
        if n not in G:
            raise KeyError(n)
        return getattr(G, self._compute)(n, self._weight)

    def __iter__(self):
        if self._nodes is self._graph:
            return iter(getattr(self._graph, self._compute)(None, self._weight))
        return ((n, self[n]) for n in self._nodes)

    def __len__(self):
        return len(self._nodes)

    def __str__(self):
        return str(list(self))

    def __repr__(self):
        return f"{type(self).__name__}({dict(self)})"


def _conversion_degree_view_type(name, compute):
    return type(name, (_ConversionDegreeView,), {"__slots__": (), "_compute": compute})


# networkx's reportviews class names, keyed (directed, multigraph) for degree
# and (direction, multigraph) for in_degree / out_degree.
_CONVERSION_DEGREE_VIEW_TYPES = {
    (False, False): _conversion_degree_view_type("DegreeView", "_degree_compute"),
    (False, True): _conversion_degree_view_type("MultiDegreeView", "_degree_compute"),
    (True, False): _conversion_degree_view_type("DiDegreeView", "_degree_compute"),
    (True, True): _conversion_degree_view_type("DiMultiDegreeView", "_degree_compute"),
    ("in", False): _conversion_degree_view_type("InDegreeView", "_in_degree_compute"),
    ("in", True): _conversion_degree_view_type("InMultiDegreeView", "_in_degree_compute"),
    ("out", False): _conversion_degree_view_type("OutDegreeView", "_out_degree_compute"),
    ("out", True): _conversion_degree_view_type("OutMultiDegreeView", "_out_degree_compute"),
}


_NOT_A_ROW_DEGREE_VIEW = object()


def _undirected_row_degrees(view, nbunch, weight, factor):
    """br-r37-c1-gue3i: degrees of a to_directed(as_view=True) view of a
    concrete Graph / MultiGraph, from the source's native degree.

    networkx's view has succ = pred = the source's rows, so a node's in- and
    out-degree are both the sum over its row, s, and its degree is s + s
    (``factor`` 1 or 2). The source's own degree is s too for every node
    WITHOUT a self-loop (an undirected self-loop counts twice there, once
    in the row); those few nodes are summed over their row directly, in row
    order, rather than corrected by subtraction, so float weights come out
    as networkx's sums do. The Python walk over the view's synthesized rows
    this replaces was 0.02x networkx for list(view.degree).

    Returns _NOT_A_ROW_DEGREE_VIEW for any other shape (a directed or
    private-storage source, a subclass), which keeps the generic walk.
    """
    src = view._graph
    if type(src) not in (Graph, MultiGraph) or _has_networkx_private_storage(src):
        return _NOT_A_ROW_DEGREE_VIEW
    multi = src.is_multigraph()

    def row_sum(node):
        nbrs = src[node]
        if multi:
            if weight is None:
                return sum(len(keydict) for keydict in nbrs.values())
            return sum(
                attrs.get(weight, 1)
                for keydict in nbrs.values()
                for attrs in keydict.values()
            )
        if weight is None:
            return len(nbrs)
        return sum(attrs.get(weight, 1) for attrs in nbrs.values())

    def scaled(s):
        return s + s if factor == 2 else s

    def single(node, looped):
        if looped:
            return scaled(row_sum(node))
        if weight is None:
            return scaled(src.degree[node])
        return scaled(src.degree(node, weight=weight))

    if nbunch is None:
        pairs = src.degree(weight=weight)
        loops = set(_selfloop_nodes_gen(src))
        if not loops:
            if factor == 2:
                return ((node, degree + degree) for node, degree in pairs)
            return iter(pairs)
        return (
            (node, scaled(row_sum(node)) if node in loops else scaled(degree))
            for node, degree in pairs
        )
    try:
        if nbunch in src:
            return single(nbunch, src.has_edge(nbunch, nbunch))
    except TypeError:
        pass
    loops = set(_selfloop_nodes_gen(src))
    return ((node, single(node, node in loops)) for node in view._nbunch(nbunch))


class _ConversionViewAccessor:
    """A conversion view's nodes / edges / adj / succ / pred without a view
    stored under that name: the graph base class's accessor, as the
    property's super() branch answered (succ / pred of an undirected view,
    an instance mid-construction)."""

    def __init__(self, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(super(_ConversionGraphViewBase, obj), self._name)


class _ConversionGraphViewBase:
    _directed = False
    _multigraph = False
    _adj_view_type = _ConversionAdjacencyView

    def __bool__(self):
        return _view_bool(self)

    def __repr__(self):
        return _view_repr(self)
    adjlist_inner_dict_factory = dict
    adjlist_outer_dict_factory = dict
    edge_attr_dict_factory = dict
    graph_attr_dict_factory = dict
    node_attr_dict_factory = dict
    node_dict_factory = dict

    def __new__(cls, graph=None, *args, **kwargs):
        # br-r37-c1-y2b8t: build an EMPTY Rust base. The conversion-view classes
        # mix this in with the canonical PyO3 Graph/DiGraph (for isinstance
        # parity), whose __new__ eagerly copies the parent graph's entire node +
        # edge set into the view's own Rust storage on every to_directed() /
        # to_undirected() call — O(|V|+|E|). That storage is dead weight: every
        # query method below (nodes/edges/adj/succ/pred/neighbors/number_of_*/
        # size/degree/has_edge/adjacency/copy/__iter__/__len__/__contains__) is
        # overridden to answer through self._graph. super().__new__(cls) (cls's
        # MRO routes to the Graph/DiGraph base) allocates an empty graph in O(1);
        # __init__ wires up the live conversion view. Same fix as
        # _FilteredGraphView.__new__ (br-r37-c1-pgfd2).
        if (
            graph is None
            and not args
            and not kwargs
            and cls.__new__ is _ConversionGraphViewBase.__new__
        ):
            return _new_empty_graph_for_view_class(cls)
        return super().__new__(cls)

    def __init__(self, graph):
        # Register before adding wrappers: native GC must also see their cycles
        # if setup raises before the canonical __init__ / __setattr__ hooks run.
        self._fnx_register_gc_dict(self.__dict__)
        self.__dict__["_graph"] = graph
        self.__dict__["frozen"] = True
        self.__dict__["_nodes_view"] = _ConversionNodeView(self)
        self.__dict__["_edges_view"] = _CONVERSION_EDGE_VIEW_TYPES[
            (self._directed, self._multigraph)
        ](self)
        self.__dict__["_adj_view"] = self._adj_view_type(self)
        # br-r37-c1-fabqo: register the view's adjacency as the graph's private
        # storage, as filtered and reverse views do, so an inherited accessor
        # (the `_adj` fallback to_scipy_sparse_array / bellman_ford read) and
        # the native private-override flag answer from the view instead of the
        # EMPTY Rust base: to_scipy_sparse_array(view) was all zeros and
        # johnson(view) raised KeyError. Written straight to the instance
        # dict with the native markers; the full _set_private_overrides funnel
        # would add ~2-5 us to a construction networkx does in 6.4 us, and the
        # one method it would shadow, get_edge_data, is defined below.
        self.__dict__[_PRIVATE_ADJ_OVERRIDE] = self._adj_view
        self._fnx_set_private_adj_override()
        storage = self.__dict__
        storage["nodes"] = storage["_nodes_view"]
        storage["edges"] = storage["_edges_view"]
        storage["adj"] = storage["_adj_view"]
        if self.is_directed():
            self.__dict__["_succ_view"] = self._adj_view
            self.__dict__["_pred_view"] = _ConversionAdjacencyView(self, reverse=True)
            self.__dict__[_PRIVATE_SUCC_OVERRIDE] = self._adj_view
            self.__dict__[_PRIVATE_PRED_OVERRIDE] = self.__dict__["_pred_view"]
            storage["succ"] = storage["_succ_view"]
            storage["pred"] = storage["_pred_view"]
            self._fnx_set_private_dir_override()

    def _fnx_native_graph(self):
        # br-r37-c1-4rhw0: the converted graph, for native kernels (see
        # _FilteredGraphView._fnx_native_graph) - this view's Rust storage is
        # empty (br-r37-c1-y2b8t).
        return _materialize_view(self)

    # br-r37-c1-cvempty: these must test the cached view for *presence*,
    # not truthiness.  The view objects define ``__len__``, so an empty
    # conversion view (0 nodes / 0 edges) is falsy — ``X or super().Y``
    # then fell through to the inherited canonical accessor, which on
    # the synthetic view recursed (number_of_edges -> edges -> empty,
    # falsy -> super().edges -> EdgesView.__len__ -> number_of_edges)
    # and blew the stack.  ``is not None`` resolves the cached view
    # regardless of emptiness; the ``super()`` branch survives only for
    # succ/pred on undirected views (where the view is never cached).
    #
    # br-r37-c1-pgpg1: and they are read as networkx reads its cached_property:
    # __init__ stores each view under its public name too, and these non-data
    # descriptors only answer when the instance dict has no entry, so a warm
    # read is a dict hit with no Python frame (view.adj was 86 ns against
    # networkx's 20 ns).
    nodes = _ConversionViewAccessor("nodes")
    edges = _ConversionViewAccessor("edges")
    adj = _ConversionViewAccessor("adj")
    succ = _ConversionViewAccessor("succ")
    pred = _ConversionViewAccessor("pred")

    @property
    def graph(self):
        # br-r37-c1-9ut0c: the fnx Graph base class exposes ``graph`` as a
        # ``_GraphAttrsDescriptor`` (a data descriptor), so an instance
        # ``__dict__`` entry cannot shadow it.  Surface the source graph's
        # attribute dict directly — a conversion view shares structure
        # with its source, so ``to_directed``/``to_undirected`` must
        # preserve graph-level attributes (parity with networkx).
        return self._graph.graph

    def __iter__(self):
        return iter(self._graph)

    def __len__(self):
        return len(self._graph)

    def __contains__(self, node):
        return node in self._graph

    def __getitem__(self, node):
        return self.adj[node]

    def __getattr__(self, name):
        if name in _FILTERED_VIEW_MUTATORS:
            return _frozen
        # br-r37-c1-fvgetattr: an attribute MISS must not materialise the parent.
        # The old body was `return getattr(self.copy(), name)`, and copy() walks
        # the PARENT: hasattr on a four-node subgraph of a 3200-node parent cost
        # 394us and raised AttributeError anyway - 0.0008x against networkx,
        # growing linearly in the parent with no floor. Misses are ordinary:
        # hasattr, duck-typing probes, copy, pickle and repr machinery all ask
        # for names a graph does not have.
        #
        # When this runs the name is already absent from the whole MRO, so the
        # copy can only help for attributes that exist as INSTANCE state. A
        # memoised ONE-EDGE graph of the parent's class carries that state and
        # costs nothing, so it answers "could this exist?" without the parent.
        # If there is no `_graph` (an object mid-construction, or a view shape
        # that does not keep one) the old behaviour is kept unchanged.
        if name.startswith("__") or name == "_graph":
            raise AttributeError(name)
        parent = self.__dict__.get("_graph")
        if parent is not None:
            # br-r37-c1-dvvme: probe the VIEW's class, not the parent's - a
            # conversion view is the other directedness (networkx builds it as
            # to_undirected_class() / to_directed_class()), so the parent's
            # class answered yes for in_degree / out_degree / reverse on an
            # undirected view, and the miss came from the concrete copy as
            # "'franken_networkx.Graph' object has no attribute ..." where
            # networkx says 'Graph'.
            probe_cls = _concrete_class_for(self)
            probe = _FILTERED_VIEW_ATTR_PROBE.get(probe_cls)
            if probe is None:
                probe = probe_cls()
                probe.add_edge("__fnx_attr_probe_u__", "__fnx_attr_probe_v__")
                _FILTERED_VIEW_ATTR_PROBE[probe_cls] = probe
            if not hasattr(probe, name):
                raise AttributeError(
                    f"{type(self).__name__!r} object has no attribute {name!r}"
                )
        return getattr(self.copy(), name)

    # br-r37-c1-cvfrz: a conversion view's class is built with the
    # canonical Graph type as a second base (for isinstance parity), so
    # the inherited Rust mutators (add_node, add_edge, update, ...) sit
    # in the MRO ahead of ``__getattr__`` — exactly the defect fixed for
    # _FilteredGraphView in br-r37-c1-fgvfrz.  Calling them on the view
    # mutated its uninitialised Rust state as a silent no-op instead of
    # raising NetworkXError("Frozen graph can't be modified").  Shadow
    # every mutator on the base so it is resolved before the inherited
    # canonical method.
    add_node = _frozen
    add_nodes_from = _frozen
    remove_node = _frozen
    remove_nodes_from = _frozen
    add_edge = _frozen
    add_edges_from = _frozen
    add_weighted_edges_from = _frozen
    remove_edge = _frozen
    remove_edges_from = _frozen
    clear = _frozen
    clear_edges = _frozen
    update = _frozen

    def is_directed(self):
        return self._directed

    def is_multigraph(self):
        return self._multigraph

    def _nbunch(self, nbunch):
        if nbunch is None:
            return list(self)
        if nbunch in self._graph:
            return [nbunch]
        try:
            return [node for node in nbunch if node in self._graph]
        except TypeError:
            return []

    def _adj_neighbors(self, node):
        raise NotImplementedError

    def _adj_neighbor_value(self, node, neighbor):
        raise NotImplementedError

    def _pred_neighbors(self, node):
        yield from self._adj_neighbors(node)

    def _pred_neighbor_value(self, node, neighbor):
        return self._adj_neighbor_value(node, neighbor)

    def _edges(self, nbunch=None, data=False, keys=False):
        nodes = self._nbunch(nbunch)
        result = []
        if self.is_directed():
            # br-r37-c1-ktsxn: walk the SOURCE's adjacency, not the conversion
            # view's, when the view is a DIRECTED view of an UNDIRECTED simple
            # source. `self.adj[source]` is a `_ConversionAdjacencyView` row that
            # is SYNTHESIZED IN PYTHON per node; the source's row is the native
            # one. For this conversion the two are equal element-for-element AND
            # in order -- a directed view's successors of `u` ARE `u`'s
            # undirected neighbours -- which was verified per node across plain,
            # self-loop, only-self-loop, star and random fixtures, together with
            # the resulting edge ORDER against networkx's own view.
            #
            # This is the ITERATION half of the row above, which fixed the COUNT:
            # `to_directed(g).number_of_edges()` went `0.0416x -> 11.1483x` while
            # `len(list(view.edges))` stayed at `0.0464x` because walking still
            # rebuilt every row in Python. Same view, same conversion, the other
            # spelling.
            #
            # Gated to the exact case that was proven equal. Multigraph views,
            # undirected views and directed SOURCES keep the generic row below,
            # where the conversion genuinely has to merge or dedup.
            #
            # br-r37-c1-ktsxn: the `data=True` spelling takes it too, and the
            # earlier `not data` restriction is LIFTED because the premise behind
            # it was wrong. That gate assumed `self.adj[source][target]` was a
            # conversion-view MERGE that had to be rebuilt; for THIS conversion
            # it is not. `view.adj[u][v] IS src.adj[u][v]` -- the identical
            # object, not a copy -- checked over 607 edges across plain,
            # self-loop and random fixtures, and networkx shares the same way, so
            # emitting the source's attr dict is the same object a caller got
            # before. That lets the data walk read `row.items()` once per source
            # instead of rebuilding the row AND re-subscripting it per edge.
            rows = self.adj
            native_rows = False
            if not self.is_multigraph():
                src = self._graph
                src_directed = getattr(src, "is_directed", None)
                if (
                    src_directed is not None
                    and not src_directed()
                    and not src.is_multigraph()
                ):
                    rows = src.adj
                    native_rows = True
            if native_rows and data:
                for source in nodes:
                    for target, attrs in rows[source].items():
                        result.append((source, target, attrs))
                return result
            # br-r37-c1-ktsxn: `self.is_multigraph()` was evaluated PER EDGE here.
            # It is a plain attribute read but still a bound-method call at
            # 83.3 ns, which on this fixture is ~266us of pure loop-invariant
            # work across 3,200 edges. Hoisted; the undirected branch below
            # already tests it once.
            multi = self.is_multigraph()
            for source in nodes:
                for target in rows[source]:
                    if multi:
                        for key, attrs in self.adj[source][target].items():
                            if data and keys:
                                result.append((source, target, key, attrs))
                            elif data:
                                result.append((source, target, attrs))
                            elif keys:
                                result.append((source, target, key))
                            else:
                                result.append((source, target))
                    else:
                        # br-cvedges (cc): only materialize the conversion-view attr
                        # dict (self.adj[u][v] is a per-edge merge/copy) when data is
                        # actually requested — list(view.edges()) was fetching+dropping
                        # it per edge.
                        if data:
                            result.append((source, target, self.adj[source][target]))
                        else:
                            result.append((source, target))
            return result

        # br-r37-c1-ktsxn: NODE-level dedup for the simple case, which is what
        # networkx itself does. The generic path below builds a
        # `frozenset((source, target))` PER EDGE purely to notice the second
        # sighting of an undirected pair; on this fixture the walk visits ~3,200
        # endpoint pairs and so allocates ~3,200 frozensets, which measured as
        # the DOMINANT cost of the row -- the conversion rows themselves are
        # 1169us of a 4431us walk, the rest is this loop.
        #
        # networkx's own undirected edge iteration marks the SOURCE node after
        # its row is walked and skips any neighbour already marked, which needs
        # one set membership test per edge and no allocation at all. Verified
        # OUTPUT-IDENTICAL to the frozenset path -- same tuples in the same order
        # -- across eight nbunch shapes (none, empty, single, pair, a reciprocal
        # pair, a self-loop node, a contiguous slice and a strided slice) on a
        # fixture carrying reciprocal edges and a self-loop.
        #
        # Simple graphs only. The multigraph branch keys its marker on
        # (pair, key) and genuinely needs the pair identity, so it is untouched.
        if not self.is_multigraph():
            seen_nodes = set()
            for source in nodes:
                row = self.adj[source]
                for target in row:
                    if target in seen_nodes:
                        continue
                    if data:
                        result.append((source, target, row[target]))
                    else:
                        result.append((source, target))
                seen_nodes.add(source)
            return result

        # br-r37-c1-pgpg1: an undirected view of a concrete MultiDiGraph walks
        # the source's own rows, as networkx's view does, instead of a
        # synthesized row per node and a frozenset marker per key.
        if _is_concrete_multidigraph(self._graph):
            return _union_multi_edges(self._graph, dict.fromkeys(nodes), data, keys)

        seen = set()
        for source in nodes:
            for target in self.adj[source]:
                if self.is_multigraph():
                    for key, attrs in self.adj[source][target].items():
                        marker = (frozenset((source, target)), key)
                        if marker in seen:
                            continue
                        seen.add(marker)
                        if data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
                else:
                    marker = frozenset((source, target))
                    if marker in seen:
                        continue
                    seen.add(marker)
                    # br-cvedges (cc): skip the per-edge attr materialization
                    # (self.adj[u][v] merges/copies attrs) when data not requested.
                    if data:
                        result.append((source, target, self.adj[source][target]))
                    else:
                        result.append((source, target))
        return result

    def neighbors(self, node):
        if node not in self._graph:
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.adj[node])

    def successors(self, node):
        if not self.is_directed():
            return self.neighbors(node)
        if node not in self._graph:
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.succ[node])

    def predecessors(self, node):
        if not self.is_directed():
            return self.neighbors(node)
        if node not in self._graph:
            raise NetworkXError(f"The node {node} is not in the graph.")
        return iter(self.pred[node])

    def number_of_nodes(self):
        return len(self)

    def order(self):
        # br-r37-c1-fabqo: the inherited order() read the empty Rust base (0).
        return len(self)

    # br-r37-c1-fabqo: the inherited get_edge_data read the empty Rust base
    # (None for every edge); this is the method the private-override funnel
    # installs on a graph whose adjacency is assigned (multigraph views
    # override it below).
    get_edge_data = _assigned_private_get_edge_data_simple

    def number_of_edges(self, u=None, v=None):
        if u is not None:
            # br-r37-c1-fabqo: networkx's edge count between u and v - the
            # override took no arguments. A simple graph asks `v in _adj[u]`
            # of a plain dict, so a missing u raises KeyError(u); a multigraph
            # counts the keys and answers 0 for any missing endpoint.
            if self.is_multigraph():
                try:
                    return len(self.adj[u][v])
                except KeyError:
                    return 0
            _HASH_PROBE.get(u)
            if u not in self:
                raise KeyError(u)
            return 1 if v in self.adj[u] else 0
        # br-cvundeg (cc): an UNDIRECTED view of a simple DiGraph can count edges
        # natively (sum(undirected_degree)//2) instead of materializing the whole
        # conversion-view edge list (per-edge tuple build + reciprocal dedup in
        # Python) — ~16x slower than nx. The native sequence dedups succ∪pred and
        # counts self-loops twice, so sum//2 is the exact undirected edge count.
        src = self._graph
        if (
            not self.is_directed()
            and not self.is_multigraph()
            and getattr(src, "is_directed", None)
            and src.is_directed()
            and not src.is_multigraph()
        ):
            native = getattr(src, "_native_undirected_degree_counts", None)
            if native is not None:
                return sum(native()) // 2
        # br-r37-c1-ktsxn: THE MIRROR OF THE BRANCH ABOVE, which was missing. That
        # one converts an UNDIRECTED view of a directed source; this one converts
        # a DIRECTED view of an UNDIRECTED source, and without it the count fell
        # through to `len(self.edges())` and materialised the whole conversion-view
        # edge list in Python. Measured on 400 nodes / 1600 edges:
        # `to_directed(g).number_of_edges()` read 0.0521x against networkx
        # (812.26us against 39.12us) while BUILDING the same view read 2.3053x --
        # the view was never the problem, counting through it was.
        #
        # Every undirected edge becomes TWO directed edges except a self-loop,
        # which becomes ONE, so the count is exactly `2E - selfloops`. That is not
        # an approximation: it was checked against networkx's own view on graphs
        # with none / one / two / only self-loops and on an isolated node, and
        # matches in every case. `number_of_edges()` is O(1) on the source and the
        # self-loop count is the only scan, which is why this is ~10.5us where the
        # materialisation was 812us.
        src_directed = getattr(src, "is_directed", None)
        if (
            self.is_directed()
            and not self.is_multigraph()
            and src_directed is not None
            and not src_directed()
            and not src.is_multigraph()
        ):
            return 2 * src.number_of_edges() - number_of_selfloops(src)
        # br-r37-c1-pgpg1: networkx's count is size(), half the degree sum, so
        # a reciprocal pair's key held both ways counts once.
        if not self.is_directed() and self.is_multigraph() and _is_concrete_multidigraph(src):
            return sum(degree for _, degree in _union_multi_degrees(src, src, None)) // 2
        # br-r37-c1-77tw1: count the edge list, not edges(): that call returns
        # the edge view now, whose len is this method.
        return len(self._edges(keys=self.is_multigraph()))

    def size(self, weight=None):
        # br-r37-c1-cvempty: the canonical Graph.size routes string
        # ``weight`` through the Rust ``size_impl``, which reads the
        # synthetic view's empty Rust backing and returns 0.  Compute
        # from the view's own (source-backed) ``degree`` instead — nx's
        # exact formula ``sum(d for _, d in degree(weight=...)) / 2``.
        if weight is None:
            return self.number_of_edges()
        s = sum(d for _, d in self.degree(weight=weight))
        return s / 2

    def adjacency(self):
        return ((node, self.adj[node]) for node in self)

    # Cache the live wrapper, not degree values: source mutations still flow
    # through _degree_compute. Public assignment/deletion matches NetworkX.
    @_cached_property
    def degree(self):
        return _CONVERSION_DEGREE_VIEW_TYPES[(self._directed, self._multigraph)](self)

    def _degree_compute(self, nbunch=None, weight=None):
        if self.is_directed():
            degrees = _undirected_row_degrees(self, nbunch, weight, 2)
            if degrees is not _NOT_A_ROW_DEGREE_VIEW:
                return degrees
        # br-cvundeg (cc): the whole-graph unweighted degree of an UNDIRECTED view
        # of a simple DiGraph routes to the native merged succ∪pred count (node
        # order) instead of iterating the Python-synthesized conversion-view
        # adjacency per node (which materializes attr dicts) — ~19x slower than nx.
        # Same native sequence that backs number_of_edges; weighted / nbunch /
        # multigraph / other conversions fall through to the generic path below.
        if (
            nbunch is None
            and weight is None
            and not self.is_directed()
            and not self.is_multigraph()
        ):
            src = self._graph
            if (
                getattr(src, "is_directed", None)
                and src.is_directed()
                and not src.is_multigraph()
            ):
                native = getattr(src, "_native_undirected_degree_counts", None)
                if native is not None:
                    return zip(self, native())

        # br-r37-c1-gue3i: a to_undirected view of a concrete DiGraph reads a
        # node's degree off the source's rows (_union_node_degree); one node
        # is answered before anything below is built.
        union_source = union_degree = None
        if not self.is_directed():
            source = self._graph
            union_degree = _UNION_NODE_DEGREE.get(type(source))
            if union_degree is not None and not _has_networkx_private_storage(source):
                union_source = source
                # br-r37-c1-pgpg1: every node's degree from one read of the
                # MultiDiGraph's rows.
                if nbunch is None and union_degree is _union_multi_node_degree:
                    return _union_multi_degrees(source, source, weight)
                try:
                    if nbunch is not None and nbunch in source:
                        return union_degree(source, nbunch, weight)
                except TypeError:
                    pass

        def edge_weight(attrs):
            return attrs.get(weight, 1)

        def node_degree(node):
            if union_source is not None:
                return union_degree(union_source, node, weight)
            if self.is_multigraph():
                if self.is_directed():
                    if weight is None:
                        total = sum(len(keydict) for keydict in self.succ[node].values())
                        total += sum(len(keydict) for keydict in self.pred[node].values())
                        return total

                    total = 0
                    for keydict in self.succ[node].values():
                        for attrs in keydict.values():
                            total += edge_weight(attrs)
                    for keydict in self.pred[node].values():
                        for attrs in keydict.values():
                            total += edge_weight(attrs)
                    return total

                total = 0
                for neighbor, keydict in self.adj[node].items():
                    edge_total = len(keydict) if weight is None else sum(
                        edge_weight(attrs) for attrs in keydict.values()
                    )
                    total += edge_total * 2 if neighbor == node else edge_total
                return total

            if self.is_directed():
                if weight is None:
                    return len(self.succ[node]) + len(self.pred[node])

                total = 0
                for attrs in self.succ[node].values():
                    total += edge_weight(attrs)
                for attrs in self.pred[node].values():
                    total += edge_weight(attrs)
                return total

            total = 0
            for neighbor, attrs in self.adj[node].items():
                edge_total = 1 if weight is None else edge_weight(attrs)
                total += edge_total * 2 if neighbor == node else edge_total
            return total

        if nbunch is None:
            return ((node, node_degree(node)) for node in self)

        try:
            if nbunch in self._graph:
                return node_degree(nbunch)
        except TypeError:
            pass

        nodes = self._nbunch(nbunch)
        return ((node, node_degree(node)) for node in nodes)

    def _directed_degree(self, adjacency, nbunch=None, weight=None):
        def edge_weight(attrs):
            return attrs.get(weight, 1)

        def node_degree(node):
            if self.is_multigraph():
                if weight is None:
                    return sum(len(keydict) for keydict in adjacency[node].values())

                total = 0
                for keydict in adjacency[node].values():
                    for attrs in keydict.values():
                        total += edge_weight(attrs)
                return total

            if weight is None:
                return len(adjacency[node])

            total = 0
            for attrs in adjacency[node].values():
                total += edge_weight(attrs)
            return total

        if nbunch is None:
            return ((node, node_degree(node)) for node in self)

        try:
            if nbunch in self._graph:
                return node_degree(nbunch)
        except TypeError:
            pass

        nodes = self._nbunch(nbunch)
        return ((node, node_degree(node)) for node in nodes)

    def copy(self):
        result = self._copy_type()()
        result.graph.update(dict(self.graph))
        result.add_nodes_from((node, dict(attrs)) for node, attrs in self.nodes(data=True))
        if self.is_multigraph():
            # 4-tuple shape avoids the ``key=key, **attrs`` collision when
            # an edge attribute is literally named "key"
            # (franken_networkx-9x7r0).
            result.add_edges_from(
                (u, v, key, dict(attrs))
                for u, v, key, attrs in self.edges(keys=True, data=True)
            )
        else:
            result.add_edges_from(
                (u, v, dict(attrs)) for u, v, attrs in self.edges(data=True)
            )
        return result

    def __reduce__(self):
        # br-r37-c1-cgv-pkl: same defect class as br-r37-c1-{neb6c, fgv-pkl}.
        # `_DIRECTED_CONVERSION_VIEW_TYPES` and
        # `_UNDIRECTED_CONVERSION_VIEW_TYPES` create synthetic classes
        # named "DiGraph" / "MultiDiGraph" / "Graph" / "MultiGraph"
        # that share __qualname__ and __module__ with the public
        # canonical classes but are distinct class objects. Pickle's
        # qualname-based class lookup finds the canonical class, sees
        # `lookup is not type(self)`, and crashes with
        # PicklingError("not the same object as franken_networkx.X").
        # Snapshot the conversion view as a real (canonical-class)
        # graph copy at pickle time — restoration goes through the
        # canonical class so type identity is preserved across the
        # roundtrip.
        return (_reconstruct_filtered_view_as_copy, (self.copy(),))

    def __deepcopy__(self, memo):
        copied = _deepcopy(self.copy(), memo)
        memo[id(self)] = copied
        return copied

    def _copy_type(self):
        if self.is_directed():
            return MultiDiGraph if self.is_multigraph() else DiGraph
        return MultiGraph if self.is_multigraph() else Graph

    def to_directed_class(self):
        return MultiDiGraph if self.is_multigraph() else DiGraph

    def to_undirected_class(self):
        return MultiGraph if self.is_multigraph() else Graph

class _DirectedGraphConversionView(_ConversionGraphViewBase):
    _directed = True

    def _adj_neighbors(self, node):
        return iter(self._graph[node])

    def _adj_neighbor_value(self, node, neighbor):
        return self._graph[node][neighbor]

    def _pred_neighbors(self, node):
        if self._graph.is_directed():
            return iter(self._graph.pred[node])
        return iter(self._graph[node])

    def _pred_neighbor_value(self, node, neighbor):
        if self._graph.is_directed():
            return self._graph.pred[node][neighbor]
        return self._graph[node][neighbor]

    def has_edge(self, u, v, key=None):
        return self._graph.has_edge(u, v)

    def has_successor(self, u, v):
        # br-r37-c1-ppiei / br-r37-c1-2r06n: the MAPPING decides, as it does for
        # the module-level pair. This needed BOTH halves -- rewriting it alone
        # was a measured no-op, because `_ConversionAdjacencyView` membership
        # asked the wrapped graph's node view. That is fixed now, so this
        # expression finally means what it says.
        succ = self.succ
        return u in succ and v in succ[u]

    def has_predecessor(self, u, v):
        pred = self.pred
        return u in pred and v in pred[u]

    @_cached_property
    def in_degree(self):
        return _CONVERSION_DEGREE_VIEW_TYPES["in", self._multigraph](self)

    @_cached_property
    def out_degree(self):
        return _CONVERSION_DEGREE_VIEW_TYPES["out", self._multigraph](self)

    def _in_degree_compute(self, nbunch=None, weight=None):
        degrees = _undirected_row_degrees(self, nbunch, weight, 1)
        if degrees is not _NOT_A_ROW_DEGREE_VIEW:
            return degrees
        return self._directed_degree(self.pred, nbunch, weight)

    def _out_degree_compute(self, nbunch=None, weight=None):
        degrees = _undirected_row_degrees(self, nbunch, weight, 1)
        if degrees is not _NOT_A_ROW_DEGREE_VIEW:
            return degrees
        return self._directed_degree(self.succ, nbunch, weight)

    # br-r37-c1-fabqo: only on the directed views - networkx's undirected
    # graphs have no reverse at all, and the shared base's raised
    # NetworkXError where networkx raises AttributeError.
    def reverse(self, copy=True):
        reversed_view = _reverse_directed_view_for(self)
        if copy:
            return reversed_view.copy()
        return reversed_view


class _DirectedMultiGraphConversionView(_ConversionGraphViewBase):
    _directed = True
    _multigraph = True
    get_edge_data = _assigned_private_get_edge_data_multi

    def _adj_neighbors(self, node):
        return iter(self._graph[node])

    def _adj_neighbor_value(self, node, neighbor):
        return self._graph[node][neighbor]

    def _pred_neighbors(self, node):
        if self._graph.is_directed():
            return iter(self._graph.pred[node])
        return iter(self._graph[node])

    def _pred_neighbor_value(self, node, neighbor):
        if self._graph.is_directed():
            return self._graph.pred[node][neighbor]
        return self._graph[node][neighbor]

    def has_edge(self, u, v, key=None):
        return self._graph.has_edge(u, v, key)

    def has_successor(self, u, v):
        # br-r37-c1-ppiei / br-r37-c1-2r06n: the MAPPING decides, as it does for
        # the module-level pair. This needed BOTH halves -- rewriting it alone
        # was a measured no-op, because `_ConversionAdjacencyView` membership
        # asked the wrapped graph's node view. That is fixed now, so this
        # expression finally means what it says.
        succ = self.succ
        return u in succ and v in succ[u]

    def has_predecessor(self, u, v):
        pred = self.pred
        return u in pred and v in pred[u]

    @_cached_property
    def in_degree(self):
        return _CONVERSION_DEGREE_VIEW_TYPES["in", self._multigraph](self)

    @_cached_property
    def out_degree(self):
        return _CONVERSION_DEGREE_VIEW_TYPES["out", self._multigraph](self)

    def _in_degree_compute(self, nbunch=None, weight=None):
        degrees = _undirected_row_degrees(self, nbunch, weight, 1)
        if degrees is not _NOT_A_ROW_DEGREE_VIEW:
            return degrees
        return self._directed_degree(self.pred, nbunch, weight)

    def _out_degree_compute(self, nbunch=None, weight=None):
        degrees = _undirected_row_degrees(self, nbunch, weight, 1)
        if degrees is not _NOT_A_ROW_DEGREE_VIEW:
            return degrees
        return self._directed_degree(self.succ, nbunch, weight)

    # br-r37-c1-fabqo: only on the directed views - networkx's undirected
    # graphs have no reverse at all, and the shared base's raised
    # NetworkXError where networkx raises AttributeError.
    def reverse(self, copy=True):
        reversed_view = _reverse_directed_view_for(self)
        if copy:
            return reversed_view.copy()
        return reversed_view


_DIRECTED_CONVERSION_VIEW_TYPES = {
    False: type("DiGraph", (_DirectedGraphConversionView, DiGraph), {}),
    True: type("MultiDiGraph", (_DirectedMultiGraphConversionView, MultiDiGraph), {}),
}


def _generic_directed_graph_view(graph):
    view_type = _DIRECTED_CONVERSION_VIEW_TYPES[graph.is_multigraph()]
    return view_type(graph)


def _union_row(graph, node):
    # br-r37-c1-36v6r: networkx's to_undirected(as_view=True) row is a
    # UnionAtlas, which iterates set(succ.keys()) | set(pred.keys()) - hash
    # order, not succ then pred. A keys view and an iterator both take
    # CPython's generic set-building path, so the same rows build the same
    # table and iterate alike. successors / predecessors walk the native rows
    # without building a row mapping (1.8 ms against 6.3 ms for every row of
    # a gnp(1000, 0.01) digraph).
    return iter(set(graph.successors(node)) | set(graph.predecessors(node)))


def _union_node_degree(graph, node, weight):
    """br-r37-c1-gue3i: node's degree in a to_undirected(as_view=True) view
    of the DiGraph `graph` - networkx's Graph degree over the UnionAtlas,
    len(nbrs) + (node in nbrs), or the sum of its weights in the union's
    order (sum() itself, whose float accumulation the order decides) plus
    the self-loop's - read off the source's rows. Going through the view's
    synthesized row built each neighbour's value in Python: degree[n] was
    0.03x networkx, weighted 0.24x."""
    if weight is None:
        nbrs = set(graph.successors(node)) | set(graph.predecessors(node))
        return len(nbrs) + (node in nbrs)
    succ = dict(graph.succ[node])
    pred = dict(graph.pred[node])
    # UnionAtlas answers from succ first.
    total = sum(
        (succ[nbr] if nbr in succ else pred[nbr]).get(weight, 1)
        for nbr in _union_row(graph, node)
    )
    loop = succ[node] if node in succ else pred.get(node)
    return total + (loop is not None and loop.get(weight, 1))


def _union_multi_rows(graph, data):
    """br-r37-c1-pgpg1: the MultiDiGraph `graph`'s succ and pred rows as plain
    dicts - what networkx's UnionMultiAdjacency reads, G._succ and G._pred -
    in two native crossings. With `data` a pair's value is its {key: attrs}
    dict holding the edges' live attr dicts (the cached native adjacency);
    without it, the list of its keys in key order and no attr dict is made.
    A pred row shares the succ rows' values, as networkx's _pred[v][u] is
    _succ[u][v]. Walking the view's synthesized rows instead built a row
    mapping per node and a _UnionKeyAtlas per pair: list(view.edges(keys=True,
    data=True)) was 0.09x networkx, number_of_edges 0.08x, degree 0.16x."""
    if data:
        succ = graph._native_adjacency_dict()
    else:
        succ = {node: {} for node in graph}
        for u, v, key in graph.edges(keys=True):
            row = succ[u]
            keys = row.get(v)
            if keys is None:
                row[v] = [key]
            else:
                keys.append(key)
    pred = {
        node: {nbr: succ[nbr][node] for nbr in nbrs}
        for node, nbrs in graph._native_predecessor_keys_bulk()
    }
    return succ, pred


_NO_KEYS = {}


def _union_multi_values(out_keys, in_keys):
    """networkx's UnionAtlas(succ[u][v], pred[u][v]).values() for a pair of a
    to_undirected(as_view=True) view of a MultiDiGraph: the keys in
    set(succ keys) | set(pred keys) order, each value from succ first. A
    one-way pair is a UnionAtlas over {} too (br-r37-c1-u7szm), so its keys
    still come in set order, not the key dict's."""
    return [
        out_keys[key] if key in out_keys else in_keys[key]
        for key in set(out_keys.keys()) | set(in_keys.keys())
    ]


def _union_multi_row_degree(out_row, in_row, node, weight):
    """br-r37-c1-gue3i / br-r37-c1-pgpg1: `node`'s degree in a
    to_undirected(as_view=True) view of a MultiDiGraph, from its succ and pred
    rows - networkx's MultiDegreeView over the UnionMultiInner: per neighbour
    the size of the key union, or one sum() over every key dict's values in
    the union's order, plus the self-loop's. Unweighted, a row value may be a
    key dict or a key list. The view's per-neighbour subtotals summed
    differently: 58.900000000000006 where networkx answers 58.9."""
    if weight is None:
        total = 0
        for nbr, out_keys in out_row.items():
            in_keys = in_row.get(nbr)
            total += len(out_keys) if in_keys is None else len(set(out_keys) | set(in_keys))
        for nbr, in_keys in in_row.items():
            if nbr not in out_row:
                total += len(in_keys)
        loop = out_row.get(node)
        return total if loop is None else total + len(loop)
    total = sum(
        attrs.get(weight, 1)
        for nbr in set(out_row.keys()) | set(in_row.keys())
        for attrs in _union_multi_values(out_row.get(nbr, _NO_KEYS), in_row.get(nbr, _NO_KEYS))
    )
    if node in out_row or node in in_row:
        total += sum(
            attrs.get(weight, 1)
            for attrs in _union_multi_values(
                out_row.get(node, _NO_KEYS), in_row.get(node, _NO_KEYS)
            )
        )
    return total


def _union_multi_node_degree(graph, node, weight):
    """_union_multi_row_degree over `node`'s own two rows (plain key dicts,
    one native crossing each), for a single-node read."""
    return _union_multi_row_degree(
        graph._native_successor_row_dict(node),
        graph._native_predecessor_row_dict(node),
        node,
        weight,
    )


def _union_multi_degrees(graph, nodes, weight):
    """(node, degree) for every node of `nodes` in a to_undirected(as_view=True)
    view of the MultiDiGraph `graph`, from one snapshot of its rows taken when
    the iteration starts."""
    succ, pred = _union_multi_rows(graph, weight is not None)
    for node in nodes:
        yield node, _union_multi_row_degree(succ[node], pred[node], node, weight)


def _union_multi_edges(graph, nodes, data, keys):
    """br-r37-c1-pgpg1: networkx's MultiEdgeDataView walk over a
    to_undirected(as_view=True) view of the MultiDiGraph `graph`: each node's
    neighbours in set(succ) | set(pred) order, a neighbour already walked as a
    source skipped, each pair's keys in set(succ keys) | set(pred keys) order
    with the attrs read from succ first (UnionAtlas). `nodes` holds no
    duplicates (networkx's nbunch is a dict)."""
    succ, pred = _union_multi_rows(graph, data)
    empty = _NO_KEYS if data else ()
    seen = set()
    result = []
    append = result.append
    for node in nodes:
        out_row = succ[node]
        in_row = pred[node]
        for nbr in set(out_row.keys()) | set(in_row.keys()):
            if nbr in seen:
                continue
            out_keys = out_row.get(nbr, empty)
            in_keys = in_row.get(nbr, empty)
            if data:
                for key in set(out_keys.keys()) | set(in_keys.keys()):
                    attrs = out_keys[key] if key in out_keys else in_keys[key]
                    append((node, nbr, key, attrs) if keys else (node, nbr, attrs))
            elif keys:
                for key in set(out_keys) | set(in_keys):
                    append((node, nbr, key))
            else:
                result.extend([(node, nbr)] * len(set(out_keys) | set(in_keys)))
        seen.add(node)
    return result


def _is_concrete_multidigraph(graph):
    return type(graph) is MultiDiGraph and not _has_networkx_private_storage(graph)


_UNION_NODE_DEGREE = {DiGraph: _union_node_degree, MultiDiGraph: _union_multi_node_degree}


class _UndirectedGraphConversionView(_ConversionGraphViewBase):
    def _adj_neighbors(self, node):
        if not self._graph.is_directed():
            return iter(self._graph[node])
        return _union_row(self._graph, node)

    def _adj_neighbor_value(self, node, neighbor):
        if not self._graph.is_directed():
            return self._graph[node][neighbor]
        if self._graph.has_edge(node, neighbor):
            return self._graph.succ[node][neighbor]
        return self._graph.pred[node][neighbor]

    def has_edge(self, u, v, key=None):
        if not self._graph.is_directed():
            return self._graph.has_edge(u, v)
        return self._graph.has_edge(u, v) or self._graph.has_edge(v, u)


class _UnionMultiRow(_Mapping):
    """br-r37-c1-pgpg1: a row of a to_undirected(as_view=True) view of a
    concrete MultiDiGraph (networkx's AdjacencyView(UnionMultiInner)). An
    entry is networkx's AtlasView(UnionAtlas(succ, pred)) over the pair's
    live key dicts, {} for a missing side; one native call reads a pair, or
    a whole row's pairs, where the generic row subscripted the source's succ
    and pred rows per pair: 100 rows' items were 0.15x networkx and
    view.adj[u][v] 0.16x. Slotted, it prints as the generic row does."""

    __slots__ = ("_view", "_node")
    _reverse = False
    _source_rows = _ConversionNeighborMap._source_rows
    __repr__ = _ConversionNeighborMap.__repr__
    __str__ = _ConversionNeighborMap.__str__
    copy = _ConversionNeighborMap.copy

    def __init__(self, view, node):
        self._view = view
        self._node = node

    def __iter__(self):
        return _union_row(self._view._graph, self._node)

    def __len__(self):
        return self._view._graph._fnx_union_row_len(self._node)

    def __getitem__(self, neighbor):
        pair = self._view._graph._fnx_union_multi_pair(self._node, neighbor)
        if pair is None:
            raise KeyError(neighbor)
        outgoing, incoming = pair
        return _UnionKeyAtlas(
            _NO_KEYS if outgoing is None else outgoing,
            _NO_KEYS if incoming is None else incoming,
        )

    def items(self):
        return _UnionMultiRowItems(self)

    def values(self):
        return _UnionMultiRowValues(self)


_UnionMultiRow.__name__ = _UnionMultiRow.__qualname__ = "AdjacencyView"


class _UnionMultiRowItems(_ItemsViewABC):
    __slots__ = ()

    def __iter__(self):
        row = self._mapping
        for neighbor, outgoing, incoming in row._view._graph._fnx_union_multi_row(row._node):
            yield neighbor, _UnionKeyAtlas(
                _NO_KEYS if outgoing is None else outgoing,
                _NO_KEYS if incoming is None else incoming,
            )


_UnionMultiRowItems.__name__ = _UnionMultiRowItems.__qualname__ = "ItemsView"


class _UnionMultiRowValues(_ValuesViewABC):
    __slots__ = ()

    def __iter__(self):
        row = self._mapping
        for _, outgoing, incoming in row._view._graph._fnx_union_multi_row(row._node):
            yield _UnionKeyAtlas(
                _NO_KEYS if outgoing is None else outgoing,
                _NO_KEYS if incoming is None else incoming,
            )


_UnionMultiRowValues.__name__ = _UnionMultiRowValues.__qualname__ = "ValuesView"


class _UnionMultiAdjacencyView(_ConversionAdjacencyView):
    """The adjacency of a to_undirected(as_view=True) view of a concrete
    MultiDiGraph without networkx private storage: _UnionMultiRow rows."""

    def __getitem__(self, node):
        view = self._view
        if node not in view._graph:
            # The generic row's errors: the graph's adjacency raises first.
            view._graph.adj[node]
            raise KeyError(node)
        return _UnionMultiRow(view, node)


def _undirected_multi_adjacency_view(view):
    # networkx's generic_graph_view reads the source's _succ / _pred once,
    # when the view is made, so the row kind is chosen then too.
    if _is_concrete_multidigraph(view._graph):
        return _UnionMultiAdjacencyView(view)
    return _ConversionAdjacencyView(view)


class _UndirectedMultiGraphConversionView(_ConversionGraphViewBase):
    _multigraph = True
    _adj_view_type = staticmethod(_undirected_multi_adjacency_view)
    get_edge_data = _assigned_private_get_edge_data_multi

    def _adj_neighbors(self, node):
        if not self._graph.is_directed():
            return iter(self._graph[node])
        return _union_row(self._graph, node)

    def _adj_neighbor_value(self, node, neighbor):
        if not self._graph.is_directed():
            return self._graph[node][neighbor]

        outgoing = self._graph.succ[node].get(neighbor)
        incoming = self._graph.pred[node].get(neighbor)
        if outgoing is None and incoming is None:
            # Filtered predecessor mappings have their own missing-key wording.
            self._graph.pred[node][neighbor]
            raise KeyError(neighbor)
        # br-r37-c1-u7szm: networkx's UnionMultiInner wraps a one-way pair too,
        # with {} for the missing side.
        return _UnionKeyAtlas(
            {} if outgoing is None else outgoing, {} if incoming is None else incoming
        )

    def has_edge(self, u, v, key=None):
        if not self._graph.is_directed():
            return self._graph.has_edge(u, v, key)
        return self._graph.has_edge(u, v, key) or self._graph.has_edge(v, u, key)


_UNDIRECTED_CONVERSION_VIEW_TYPES = {
    False: type("Graph", (_UndirectedGraphConversionView, Graph), {}),
    True: type("MultiGraph", (_UndirectedMultiGraphConversionView, MultiGraph), {}),
}


def _generic_undirected_graph_view(graph):
    view_type = _UNDIRECTED_CONVERSION_VIEW_TYPES[graph.is_multigraph()]
    return view_type(graph)


class _ViewNativeReader:
    """br-r37-c1-4rhw0: a view's inherited ``_native_*`` reader, answered by the
    concrete graph the view shows.

    The three view mixins sit in front of a PyO3 graph class whose storage is
    EMPTY (br-r37-c1-pgfd2, br-r37-c1-q131o, br-r37-c1-y2b8t), so a native
    method the view inherited read a graph with no nodes: non_neighbors(view,
    n) took its node set from ``_native_node_keys`` and returned an empty set.
    A name the concrete class does not have stays missing, so a
    ``getattr(G, "_native_x", None)`` capability probe answers as it would on
    that class.
    """

    __slots__ = ("_name",)

    def __init__(self, name):
        self._name = name

    def __get__(self, view, owner=None):
        if view is None:
            return self
        if not hasattr(_concrete_class_for(view), self._name):
            raise AttributeError(self._name)
        return getattr(view._fnx_native_graph(), self._name)


# The private native methods that WRITE the graph. A view is frozen and its
# concrete graph is a cached copy, so a write must not land there; these stay
# inherited.
_VIEW_NATIVE_WRITERS = frozenset(
    (
        "_native_add_keyed_edges_no_data",
        "_native_add_keyed_edges_with_data",
        "_native_broadcast_edge_attribute",
        "_native_broadcast_node_attribute",
        "_native_fill_weighted_int_edges",
        "_native_set_edge_attribute_scalar",
        "_native_set_edge_attribute_scalar_multi",
        "_native_set_edge_attributes_dict",
        "_native_set_node_attribute_scalar",
        "_native_set_node_attributes_dict",
    )
)


def _install_view_native_readers():
    names = set()
    for cls in (Graph, DiGraph, MultiGraph, MultiDiGraph):
        names.update(name for name in dir(cls) if name.startswith("_native_"))
    for view_base in (_FilteredGraphView, _ReverseDirectedViewBase, _ConversionGraphViewBase):
        for name in sorted(names - _VIEW_NATIVE_WRITERS):
            if name not in view_base.__dict__:
                setattr(view_base, name, _ViewNativeReader(name))


_install_view_native_readers()


def reverse(G, copy=True):
    """Return graph with all edges reversed."""
    if not G.is_directed():
        raise NetworkXError("Cannot reverse an undirected graph.")
    if copy:
        # br-r37-c1-revdbl: ``G.reverse()`` already returns a fully materialized
        # fnx DiGraph (native integer-space transpose). The previous
        # ``_from_nx_graph(result)`` re-converted that fnx graph end-to-end — the
        # "double build" antipattern — for byte-identical output (~5x slower).
        # Return the native result directly.
        return G.reverse()
    return _reverse_directed_view_for(G)


def nodes(G):
    """Return nodes of G (global function form)."""
    return G.nodes()


def _global_nbunch_nodes(G, nbunch):
    if nbunch is None:
        return None
    try:
        if nbunch in G:
            return [nbunch]
    except TypeError:
        pass
    try:
        nodes = []
        for node in nbunch:
            try:
                _HASH_PROBE.get(node)
            except TypeError as exc:
                raise NetworkXError(
                    f"Node {node} in sequence nbunch is not a valid node."
                ) from exc
            if node in G:
                nodes.append(node)
        return nodes
    except TypeError as exc:
        message = exc.args[0] if exc.args else ""
        if "object is not iterable" in message and _networkx_release() >= (3, 5):
            raise NetworkXError(f"Node {nbunch} is not in the graph.") from exc
        raise NetworkXError("nbunch is not a node or a sequence of nodes.") from exc


def _triangle_selection(G, nodes):
    if nodes is None:
        return None, False

    try:
        if nodes in G:
            return [nodes], True
    except TypeError:
        pass

    return _global_nbunch_nodes(G, nodes), False


def _triangles_and_degree_iter_local(G, nodes=None):
    # br-r37-c1-undtriclus: snapshot adjacency once so the inner
    # ``set(G[neighbor])`` calls become plain dict lookups, not PyO3
    # round-trips.  Cuts ~10ms off a 100-node 1k-edge transitivity call.
    # br-r37-c1-triloc: for nbunch / single-node calls, only snapshot the
    # LOCAL universe (the queried nodes + their neighbors) instead of the
    # whole graph — single-node clustering/triangles was O(V+E) (78-408x
    # slower than nx); now O(deg). Whole-graph (nodes=None) keeps the full
    # snapshot. Results are identical: counting triangles through node u
    # only ever touches N(u) and the adjacency of each w in N(u).
    if nodes is None:
        adj_snapshot = {u: set(G[u]) - {u} for u in G}
        node_iter = list(G)
    else:
        node_iter = list(nodes)
        adj_snapshot = {}
        for node in node_iter:
            neighbors = adj_snapshot.get(node)
            if neighbors is None:
                neighbors = set(G[node]) - {node}
                adj_snapshot[node] = neighbors
            for neighbor in neighbors:
                if neighbor not in adj_snapshot:
                    adj_snapshot[neighbor] = set(G[neighbor]) - {neighbor}

    for node in node_iter:
        neighbor_set = adj_snapshot.get(node, set())
        generalized_degree = _Counter(
            len(neighbor_set & adj_snapshot.get(neighbor, set())) for neighbor in neighbor_set
        )
        triangle_count = sum(size * _count for size, _count in generalized_degree.items())
        yield (node, len(neighbor_set), triangle_count, generalized_degree)


def _weighted_triangles_and_degree_iter_local(G, nodes=None, weight="weight"):
    import numpy as _np

    if weight is None or G.number_of_edges() == 0:
        max_weight = 1
    else:
        max_weight = max(
            attrs.get(weight, 1) for _, _, attrs in G.edges(data=True)
        )

    # br-r37-c1-undtriclus: snapshot adjacency + edge weights once.
    # br-r37-c1-0g2tj follow-up: only the LOCAL universe for nbunch calls - the
    # queried nodes and their neighbours, whose rows hold every edge the loops
    # below read (see _directed_weighted_triangles_and_degree_iter_local).
    if nodes is None:
        universe = G
        node_iter = G
    else:
        node_iter = list(nodes)
        universe = dict.fromkeys(node_iter)
        for node in node_iter:
            universe.update(dict.fromkeys(G[node]))
        if 10 * len(universe) >= 9 * len(G):
            # Nearly every row is needed: one bulk pass reads them cheaper
            # than a row-by-row walk does.
            universe = G
    raw_adj_snapshot = {u: set(dict.fromkeys(G[u])) for u in universe}
    # Symmetric weight cache for undirected.
    weight_cache = {}
    if universe is G:
        for u, v, attrs in G.edges(data=True):
            weight_cache[frozenset((u, v))] = attrs.get(weight, 1) / max_weight
    else:
        for u in universe:
            for v, attrs in G[u].items():
                weight_cache[frozenset((u, v))] = attrs.get(weight, 1) / max_weight

    def normalized_weight(u, v):
        cached = weight_cache.get(frozenset((u, v)))
        if cached is not None:
            return cached
        return G[u][v].get(weight, 1) / max_weight

    for node in node_iter:
        neighbor_set = raw_adj_snapshot.get(node, set()) - {node}
        weighted_triangle_sum = 0.0
        seen_neighbors = set()
        for neighbor in neighbor_set:
            seen_neighbors.add(neighbor)
            neighbor_neighbors = raw_adj_snapshot.get(neighbor, set()) - seen_neighbors
            edge_weight = normalized_weight(node, neighbor)
            shared = neighbor_set & neighbor_neighbors
            if shared:
                weighted_triangle_sum += _np.cbrt(
                    [
                        (
                            edge_weight
                            * normalized_weight(neighbor, shared_neighbor)
                            * normalized_weight(shared_neighbor, node)
                        )
                        for shared_neighbor in shared
                    ]
                ).sum()
        yield (node, len(neighbor_set), 2 * float(weighted_triangle_sum))


def _directed_triangles_and_degree_iter_local(G, nodes=None):
    # br-r37-c1-dirclust: previously called ``G.pred[u]`` / ``G.succ[u]``
    # via PyO3 inside the outer per-node loop AND for each visited
    # neighbour — for K_100-like digraphs this was 4 PyO3 round-trips
    # per neighbour, ~21ms total on a 100-node 1k-edge graph
    # (~5× slower than nx).  Snapshot pred/succ as plain dicts once;
    # the entire inner loop becomes pure-Python set ops.
    # br-r37-c1-qnj0n: for nbunch / single-node calls, only the LOCAL universe -
    # the queried nodes and their predecessors and successors, the only rows
    # networkx reads. Snapshotting every node made clustering(G, node) cost
    # 56 ms beside a 32k-node component where networkx takes 7 us.
    if nodes is None:
        universe = G
        node_iter = G
    else:
        node_iter = list(nodes)
        universe = dict.fromkeys(node_iter)
        for node in node_iter:
            universe.update(dict.fromkeys(G.pred[node]))
            universe.update(dict.fromkeys(G.succ[node]))
    pred_snapshot = {u: set(G.pred[u]) - {u} for u in universe}
    succ_snapshot = {u: set(G.succ[u]) - {u} for u in universe}

    for node in node_iter:
        predecessor_set = pred_snapshot.get(node, set())
        successor_set = succ_snapshot.get(node, set())

        directed_triangle_count = 0
        for neighbor in _itertools.chain(predecessor_set, successor_set):
            neighbor_predecessors = pred_snapshot.get(neighbor, set())
            neighbor_successors = succ_snapshot.get(neighbor, set())
            directed_triangle_count += sum(
                1
                for third_node in _itertools.chain(
                    predecessor_set & neighbor_predecessors,
                    predecessor_set & neighbor_successors,
                    successor_set & neighbor_predecessors,
                    successor_set & neighbor_successors,
                )
            )

        total_degree = len(predecessor_set) + len(successor_set)
        reciprocal_degree = len(predecessor_set & successor_set)
        yield (node, total_degree, reciprocal_degree, directed_triangle_count)
