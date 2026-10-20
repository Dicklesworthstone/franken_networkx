

# br-r37-c1-mdvname: ``type(MDG.degree).__name__`` should return
# nx's canonical ``DiMultiDegreeView`` (not the fnx-internal class
# name).  _Set ``__name__`` on the class so introspection matches.
MultiDiGraphDegreeView.__name__ = "DiMultiDegreeView"


class _DirectedDegreeView:
    def __init__(self, graph, adjacency_attr, *, nodes=None, weight=None):
        self._graph = graph
        self._adjacency_attr = adjacency_attr
        self._nodes = nodes
        self._weight = weight
        # br-r37-c1-pejo5: node revision at nbunch-resolution time.
        self._fnx_nodes_seq = getattr(graph, "nodes_seq", None)
        # br-r37-c1-5noxi: decide the scalar-lookup route ONCE, here, instead
        # of re-deriving it on every subscript. _node_degree answered
        # `G.in_degree[n]` by re-running an isinstance pair and two string
        # comparisons before it could call the native counter — two Python
        # frames and ~0.45us of dispatch around a 0.18us native call, on an op
        # networkx completes in 0.154us total. None of those questions can
        # change for the life of the view: the weight is fixed at construction,
        # the direction is fixed, and a graph does not change class.
        # br-r37-c1-2r06n: a graph carrying networkx private storage must not use
        # the native counters at all -- they read the Rust store, which does not
        # know about an assigned `_succ`/`_pred`/`_node`. `out_degree('ZZ')` for a
        # node carried only by an assigned `_succ` answered 0 from the native
        # counter, which then failed the membership probe in __getitem__ and
        # raised KeyError where nx returns 1.
        #
        # Resolved ONCE here rather than per lookup, which is only sound because
        # `_set_private_override` drops the cached degree views when it installs
        # storage -- verified that the view is otherwise reused across the
        # assignment, so an __init__-time answer would go stale. Ordinary graphs
        # pay one dict membership test per VIEW, not per degree lookup.
        ov = vars(graph)
        self._fnx_private_storage = (
            _PRIVATE_NODE_OVERRIDE in ov
            or _PRIVATE_ADJ_OVERRIDE in ov
            or _PRIVATE_SUCC_OVERRIDE in ov
            or _PRIVATE_PRED_OVERRIDE in ov
            or _SHARED_STORAGE_SOURCE in ov
        )
        # br-r37-c1-2r06n: the container `__call__` asks about a single argument,
        # resolved here so the hot path keeps ONE attribute load. Writing the
        # choice inline as a conditional cost a measured 3.2 percent on
        # `G.out_degree(n)` (0.9690 [0.9577, 0.9793], with the __iter__ negative
        # control flat) -- one extra attribute load and a branch on a ~416 ns
        # call. Precomputed, the lookup is exactly what it was before the fix.
        self._fnx_member_of = graph.succ if self._fnx_private_storage else graph
        self._fast_degree = None
        if (
            weight is None
            and not self._fnx_private_storage
            and not isinstance(graph, (_FilteredGraphView, _ReverseDirectedViewBase))
        ):
            if adjacency_attr == "succ":
                self._fast_degree = getattr(graph, "_native_out_degree", None)
            elif adjacency_attr == "pred":
                self._fast_degree = getattr(graph, "_native_in_degree", None)

    @property
    def _adjacency(self):
        return getattr(self._graph, self._adjacency_attr)

    def _iter_nodes(self):
        if self._nodes is None:
            # br-r37-c1-2r06n: nx's `_nodes` is `self._succ`, NOT the node view,
            # and that holds for the IN-degree view as much as the out-degree
            # one. Under an assigned `_succ` the two differ, and iterating the
            # node view silently dropped a node the mapping carries.
            # `_fnx_member_of` is the graph itself on an ordinary graph, so that
            # case keeps the original path exactly.
            if self._fnx_private_storage:
                return iter(self._fnx_member_of)
            return iter(self._graph)
        return iter(self._nodes)

    def _node_degree(self, node, weight):
        # br-r37-c1-5670z / kjaqc: unweighted directed fast path (simple AND
        # multi). The generic path below walks the per-node succ/pred AtlasView
        # in pure Python -- len() for simple (O(degree)), sum(len(keydict) ...)
        # for multi (O(degree)). The native out_degree/in_degree gives the
        # identical count (distinct-successor count for simple, edge-multiplicity
        # sum for multi). Both PyDiGraph and PyMultiDiGraph expose the methods.
        if (
            weight is None
            # br-r37-c1-2r06n: assigned private storage is invisible to the Rust
            # store the native counters read, exactly as a filtered view's empty
            # base is.
            and not self._fnx_private_storage
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            # br-r37-c1-vfytj/revrow: the native _native_*_degree paths read
            # the graph's Rust base, which is EMPTY for a filtered/subgraph
            # view AND a reverse view (_ReverseDirectedViewBase)
            # (super().__new__ empty base) — so they returned 0 / {} for
            # subgraph in_degree/out_degree. On a filtered view fall through
            # to the generic self._adjacency[node] path, which reads the
            # FILTER-AWARE succ/pred adjacency views.
            if self._adjacency_attr == "succ":
                return self._graph._native_out_degree(node)
            if self._adjacency_attr == "pred":
                return self._graph._native_in_degree(node)
        # br-r37-c1-wdeg2: weighted in/out degree on a SIMPLE DiGraph summed over
        # ``self._adjacency[node]`` (a succ/pred AtlasView) — materializing that
        # view PER NODE made full-graph weighted in_degree ~14x nx. Sum over the
        # native per-row dict instead (identical pred/succ order, so sum()'s
        # float compensation is byte-identical) — ~14x self-speedup. Filtered/
        # reverse views (empty Rust base) + multigraph (key-nested row dicts)
        # keep the generic AtlasView path below.
        if (
            weight is not None
            and type(self._graph) is DiGraph
            # br-r37-c1-2r06n: same reason as the unweighted counters above.
            and not self._fnx_private_storage
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            if self._adjacency_attr == "succ":
                _row = self._graph._native_adjacency_row_dict(node)
                return sum(attrs.get(weight, 1) for attrs in _row.values())
            if self._adjacency_attr == "pred":
                _row = self._graph._native_predecessor_row_dict(node)
                return sum(attrs.get(weight, 1) for attrs in _row.values())
        if (
            weight is not None
            and isinstance(weight, str)
            and type(self._graph) is MultiDiGraph
            and not self._fnx_private_storage
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            if self._adjacency_attr == "succ":
                _nat = self._graph._native_weighted_out_degree_subset
            elif self._adjacency_attr == "pred":
                _nat = self._graph._native_weighted_in_degree_subset
            else:
                _nat = None
            if _nat is not None:
                try:
                    _pairs = _nat([node], weight)
                except TypeError:
                    _pairs = None
                if _pairs:
                    return _pairs[0][1]

        adjacency = self._adjacency[node]
        if self._graph.is_multigraph():
            if weight is None:
                return sum(len(keydict) for keydict in adjacency.values())
            # br-r37-c1-outdegsum: ONE flat sum() over the flattened edges, which
            # is what networkx writes:
            #
            #     sum(dd.get(weight, 1)
            #         for key_dict in nbrs.values() for dd in key_dict.values())
            #
            # This was a nested `total += ...` running fold, and that is a PARITY
            # BUG, not a style difference. CPython's builtins.sum is
            # Neumaier-compensated; a naive left-to-right fold is not. On
            # out-edge weights [1e16, 1.0, -1e16] networkx returns 1.0 and the
            # fold returned 0.0 -- the compensation term is exactly the value.
            #
            # Measured on MultiDiGraph, four cells wrong: in_degree(n, weight)
            # and out_degree(n, weight), both for distinct neighbours and for
            # parallel edges on one neighbour. The TOTAL degree view was already
            # correct because it goes through a different function, which is why
            # this survived: `degree(n, weight)` agreed with networkx while its
            # own in/out siblings did not.
            return sum(
                attrs.get(weight, 1)
                for keydict in adjacency.values()
                for attrs in keydict.values()
            )

        if weight is None:
            return len(adjacency)
        return sum(attrs.get(weight, 1) for attrs in adjacency.values())

    def __len__(self):
        if self._nodes is None:
            # br-r37-c1-2r06n: nx is `len(self._nodes)`, i.e. `len(self._succ)`.
            # With `_node` assigned that is SMALLER than the node view, and with
            # `_succ` assigned it is larger — this answered the node count both
            # times.
            if self._fnx_private_storage:
                return len(self._fnx_member_of)
            return len(self._graph)
        return len(self._nodes)

    def __iter__(self):
        # br-r37-c1-pejo5
        _degree_view_frozen_nodes_check(self)
        # br-r37-c1-2r06n: EVERY native bulk path below reads the Rust store,
        # which cannot see an assigned `_succ`/`_pred`/`_node` — the same reason
        # the per-node counters are turned off in __init__. One early exit to the
        # generic loop rather than a flag on each of the four guards: that loop
        # yields `(node, self[node])`, and both halves of it are already
        # private-aware.
        #
        # This is also what makes iteration agree with nx on the case where nx
        # RAISES: with `_succ` assigned, `dict(G.in_degree)` iterates the succ
        # keys and then looks each up in `_pred`, so a node carried only by
        # `_succ` raises KeyError rather than being silently skipped.
        if self._fnx_private_storage:
            for node in self._iter_nodes():
                yield (node, self[node])
            return
        # br-r37-c1-degidx: unweighted full-graph iteration uses a single
        # native bulk call (one Rust loop) instead of N per-node
        # _native_*_degree PyO3 round-trips (each hashing the node key).
        if (
            self._nodes is None
            and self._weight is None
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            # br-r37-c1-degcounts (cc): for a simple DiGraph, zip the cached node
            # list (``list(G)`` hits the node_iter_mirror, ~0.09ms @ 20k nodes)
            # with a counts-only native call (NO per-node py_node_key PyObject
            # rebuild) instead of ``_native_*_degree_pairs``, which rebuilt a
            # node object per entry — the entire in_degree/out_degree gap (pairs
            # 1.5ms vs nx 1.25ms = 0.62x; zip+counts ~0.8ms = ~1.4x). list(G)
            # order == nodes_ordered() order == pairs order (verified), so this
            # is byte-identical. Multi types / non-DiGraph keep the pairs path.
            if type(self._graph) is DiGraph:
                if self._adjacency_attr == "succ":
                    counts = getattr(self._graph, "_native_out_degree_counts", None)
                    cache_key = "out"
                elif self._adjacency_attr == "pred":
                    counts = getattr(self._graph, "_native_in_degree_counts", None)
                    cache_key = "in"
                else:
                    counts = None
                    cache_key = None
                if counts is not None:
                    # The PyO3 count arrays are index-ordered and the native
                    # node/edge generations are bumped for every structural
                    # change.  Keep the converted Python arrays on the graph
                    # so repeat directional-degree reads do not rebuild one
                    # Vec per call; a generation mismatch replaces the whole
                    # direction-specific entry before it can be observed.
                    #
                    # This is deliberately unavailable to private-storage
                    # graphs above: their caller-owned dicts can mutate
                    # in-place without touching native generations.
                    state = (self._graph.nodes_seq, self._graph.edges_seq)
                    cache = vars(self._graph).get("_fnx_directional_degree_counts")
                    entry = None if cache is None else cache.get(cache_key)
                    if entry is None or entry[0] != state:
                        values = counts()
                        if cache is None:
                            cache = {}
                            vars(self._graph)["_fnx_directional_degree_counts"] = cache
                        cache[cache_key] = (state, values)
                    else:
                        values = entry[1]
                    yield from zip(self._graph, values)
                    return
            # br-r37-c1-vfytj/revrow: native bulk pairs read the (empty) Rust
            # base of a filtered/reverse view — skip for those view classes.
            if self._adjacency_attr == "succ":
                pairs = getattr(self._graph, "_native_out_degree_pairs", None)
            elif self._adjacency_attr == "pred":
                pairs = getattr(self._graph, "_native_in_degree_pairs", None)
            else:
                pairs = None
            if pairs is not None:
                yield from _degree_view_guarded_pairs(self, pairs())
                return
        # br-r37-c1-8njy5: exact MultiDiGraph weighted in/out degree can use
        # Rust's native multiedge walk; views and nbunch stay on Python paths.
        if (
            self._nodes is None
            and isinstance(self._weight, str)
            and type(self._graph) is MultiDiGraph
            and self._adjacency_attr in ("succ", "pred")
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            if self._adjacency_attr == "succ":
                weighted_pairs = getattr(self._graph, "_native_weighted_out_degree", None)
            else:
                weighted_pairs = getattr(self._graph, "_native_weighted_in_degree", None)
            if weighted_pairs is not None:
                yield from _degree_view_guarded_pairs(self, weighted_pairs(self._weight))
                return
        # br-r37-c1-wdeg2: weighted full-graph iteration on a SIMPLE DiGraph
        # sums over the native per-row dict directly, skipping the per-node
        # ``self[node]`` __getitem__/_node_degree dispatch (byte-identical, the
        # same path _node_degree takes for single nodes).
        if (
            self._nodes is None
            and self._weight is not None
            and type(self._graph) is DiGraph
            and self._adjacency_attr in ("succ", "pred")
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            _w = self._weight
            # br-cc-diwdegvals: zip cached node list with a VALUES-only directional
            # native accumulator (int-store fast path, else exact) — no per-node
            # row-dict materialization / py_node_key rebuild / store-dirtying. Same
            # win as the total-degree path (0.7x -> ~3x). Falls back to the row-dict
            # sum if the native method is absent.
            _vname = (
                "_native_weighted_out_degree_values"
                if self._adjacency_attr == "succ"
                else "_native_weighted_in_degree_values"
            )
            _values = getattr(self._graph, _vname, None)
            if _values is not None:
                yield from zip(self._graph, _values(_w))
                return
            _row = (
                self._graph._native_adjacency_row_dict
                if self._adjacency_attr == "succ"
                else self._graph._native_predecessor_row_dict
            )
            for node in self._graph:
                yield (node, sum(a.get(_w, 1) for a in _row(node).values()))
            return
        # br-r37-c1-degnbdirw (cc): weighted in/out degree over a node SUBSET routes
        # to the native directional weighted-subset kernel (already present for both
        # DiGraph and MultiDiGraph from 752b2b98c) instead of the per-node
        # _node_degree AtlasView loop — MDG in/out_degree(nbunch, weight) was ~0.05x.
        # Filtered/reverse views (empty Rust base) keep the generic path.
        if (
            self._nodes is not None
            and isinstance(self._weight, str)
            and self._adjacency_attr in ("succ", "pred")
            and not isinstance(
                self._graph, (_FilteredGraphView, _ReverseDirectedViewBase)
            )
        ):
            if self._adjacency_attr == "succ":
                native = getattr(self._graph, "_native_weighted_out_degree_subset", None)
            else:
                native = getattr(self._graph, "_native_weighted_in_degree_subset", None)
            if native is not None:
                yield from native(self._nodes, self._weight)
                return
        for node in self._iter_nodes():
            yield (node, self[node])

    def __getitem__(self, node):
        # br-r37-c1-5noxi: the pre-resolved native counter, when this view has
        # one. Identical answer to _node_degree's first branch — same method,
        # same argument — with the branch itself hoisted to __init__.
        fast = self._fast_degree
        degree = fast(node) if fast is not None else self._node_degree(node, self._weight)
        # br-r37-c1-i89jx: nx's DiDegreeView.__getitem__ reads ``self._succ[n]``
        # / ``self._pred[n]``, so indexing a node that is not in the graph
        # raises KeyError. The unweighted native fast path in _node_degree
        # (``_native_out_degree`` / ``_native_in_degree``) answers 0 for an
        # absent node instead, and 0 is a perfectly plausible degree — so the
        # caller got a real-looking number and kept computing where networkx
        # would have raised. Every other path here already agrees with nx:
        # weighted, subgraph-filtered and reverse views all raise, because they
        # go through the adjacency lookup rather than the native counter.
        #
        # The membership probe is charged ONLY when the answer is 0, so a node
        # with any edges pays nothing, and it lives in __getitem__ rather than
        # in _node_degree so that ITERATION — which visits only nodes already
        # known to be present, including isolated ones — is untouched.
        if degree == 0 and not self._fnx_private_storage:
            # ``hash`` first: nx reaches this through a dict lookup, so an
            # UNHASHABLE index raises TypeError there, not KeyError. fnx's
            # ``in`` swallows that TypeError and answers False, which would
            # turn nx's TypeError into a KeyError — so the hashability check
            # cannot be folded into the membership probe.
            _HASH_PROBE.get(node)
            if node not in self._graph:
                raise KeyError(node)
        # br-r37-c1-2r06n: the probe is SKIPPED under private storage rather
        # than re-pointed at the assigned mapping. With storage assigned the
        # native counters are already off, so `_node_degree` reached
        # `self._adjacency[node]` and that subscript raised nx's KeyError by
        # itself; probing `node not in self._graph` on top of it would re-ask the
        # NODE view, which is the wrong authority and the whole bug.
        return degree

    def __bool__(self):
        return bool(len(self))

    def __call__(self, nbunch=None, weight=None):
        if weight is None:
            weight = self._weight
        if nbunch is None and weight == self._weight:
            return self
        if nbunch is None:
            return type(self)(self._graph, self._adjacency_attr, weight=weight)
        try:
            # br-r37-c1-2r06n: nx's DiDegreeView sets `_nodes = self._succ` and
            # asks `nbunch in self._nodes`, so the SUCC MAPPING decides whether a
            # single argument is a node -- for the in-degree view too, which is
            # why nx's in_degree and out_degree disagree under an assigned
            # `_succ`. That asymmetry is nx's and is matched here rather than
            # smoothed. `nbunch in self._graph` asked the node view instead and
            # got it wrong in both directions: it returned a VIEW for a node
            # carried only by `_succ` (nx returns an int) and an INT for a node
            # carried only by `_node` (nx returns a view).
            if nbunch in self._fnx_member_of:
                # br-r37-c1-degcallfast: answer from the counter the constructor
                # already bound, instead of re-entering `_node_degree` and
                # re-deciding what `__init__` decided once. That frame re-runs a
                # weight test, a private-storage test and two isinstance checks
                # before reaching the same native call.
                #
                # Measured on DiGraph, V=1200: out_degree(n) 0.3381us -> 0.1117us,
                # i.e. 0.5499x -> 1.6642x against networkx; MultiDiGraph 1.3154x
                # -> 4.0518x. The subscript form `view[n]` already cost only
                # 0.1134us, so the CALL form was paying ~0.21us of pure dispatch
                # that the subscript did not.
                #
                # THE MEMBERSHIP TEST ABOVE IS LOAD-BEARING AND IS KEPT. A first
                # attempt dropped it and called the counter directly inside a
                # try/except, which measured 2.6084x - and was WRONG.
                # `_native_out_degree` does not raise for a non-node: it returns
                # 0 for an absent int, a str, a list, a dict and None. networkx
                # raises NetworkXError for the absent int and returns an empty
                # VIEW for the rest, so the try/except form silently answered 0
                # in five distinct shapes. It only looked right because the
                # benchmark asked for a node that was present.
                #
                # `weight is None` is the EFFECTIVE weight after the resolution
                # at the top of this function, and `_fast_degree` is bound only
                # for an unweighted view over a concrete graph with no assigned
                # private storage, so anything else still takes `_node_degree`.
                if weight is None:
                    fast = self._fast_degree
                    if fast is not None:
                        return fast(nbunch)
                return self._node_degree(nbunch, weight)
        except TypeError:
            pass
        # br-r37-c1-degnbnative (cc): unweighted in_degree/out_degree(nbunch) — one
        # native pass (filter + directional degree) replaces nbunch_iter membership
        # + per-node native-degree calls. Reuse _FilteredDegreeView with `self` as
        # the raw view so view[node] still answers in/out degree for any node;
        # iteration serves the precomputed pairs. Errors map to NetworkXError.
        #
        # br-r37-c1-vbe1o: NOT under assigned private storage. This native subset
        # kernel reads the Rust store, so for a node carried only by an assigned
        # mapping it returns no pair and the call yields an EMPTY view — where
        # networkx builds a view over that node and then raises KeyError from the
        # degree lookup. The other native paths in this class already carry this
        # gate; this one was missed.
        if weight is None and not self._fnx_private_storage:
            if self._adjacency_attr == "succ":
                native = getattr(self._graph, "_native_out_degree_pairs_subset", None)
            elif self._adjacency_attr == "pred":
                native = getattr(self._graph, "_native_in_degree_pairs_subset", None)
            else:
                native = None
            if native is not None:
                try:
                    pairs = native(nbunch)
                except TypeError as exc:
                    # br-r37-c1-degnbnative (cc): a single non-iterable bad node
                    # (e.g. degree(99), used by is_isolate) reaches the native call
                    # and fails try_iter; nx degree(n) raises "Node n is not in the
                    # graph." Map that case; unhashable-element messages pass through.
                    if "is not iterable" in str(exc):
                        raise NetworkXError(f"Node {nbunch} is not in the graph.")
                    raise NetworkXError(str(exc))
                return _filtered_degree_view(self, None, pairs=pairs, owner=self, graph=self._graph)
        nodes = list(self._graph.nbunch_iter(nbunch))
        return type(self)(self._graph, self._adjacency_attr, nodes=nodes, weight=weight)

    def __eq__(self, other):
        # br-r37-c1-dv-eq: see _WeightAwareDegreeView.__eq__.
        # _DirectedDegreeView is the in_degree/out_degree view for
        # DiGraph and MultiDiGraph; nx.InDegreeView/OutDegreeView
        # compare via dict equality of (node, degree).
        if isinstance(other, _DirectedDegreeView):
            return (
                self._adjacency_attr == other._adjacency_attr
                and dict(self) == dict(other)
            )
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def __hash__(self):
        return id(self._graph) ^ hash(self._adjacency_attr)

    def __repr__(self):
        # br-r37-c1-degviewname: nx's InDegreeView / OutDegreeView /
        # InMultiDegreeView / OutMultiDegreeView all repr as
        # ``<ClassName>({node: degree, ...})``. fnx previously used
        # the default object.__repr__ (``<franken_networkx.
        # _DirectedDegreeView object at 0x...>``) — opaque and
        # diverging from nx's documented format.  Use
        # ``type(self).__name__`` so the four subclasses below pick
        # up the right canonical name.
        return f"{type(self).__name__}({dict(self)!r})"

    def __str__(self):
        # br-r37-c1-dvvme: networkx's str is the list (see MultiGraphDegreeView).
        return str(list(self))


# br-r37-c1-degviewname: instantiate concrete subclasses per direction
# × multi so ``type(view).__name__`` matches nx's
# ``InDegreeView`` / ``OutDegreeView`` / ``InMultiDegreeView`` /
# ``OutMultiDegreeView``.
class _InDegreeView(_DirectedDegreeView):
    pass
_InDegreeView.__name__ = "InDegreeView"


class _OutDegreeView(_DirectedDegreeView):
    pass
_OutDegreeView.__name__ = "OutDegreeView"


class _InMultiDegreeView(_DirectedDegreeView):
    pass
_InMultiDegreeView.__name__ = "InMultiDegreeView"


class _OutMultiDegreeView(_DirectedDegreeView):
    pass
_OutMultiDegreeView.__name__ = "OutMultiDegreeView"


Graph.nbunch_iter = _graph_nbunch_iter
DiGraph.nbunch_iter = _graph_nbunch_iter
MultiGraph.nbunch_iter = _graph_nbunch_iter
MultiDiGraph.nbunch_iter = _graph_nbunch_iter


def _add_weighted_edges_from_with_attr(cls):
    def add_weighted_edges_from(self, ebunch_to_add, weight="weight", **attr):
        """Accept extra **attr that apply to every inserted edge (matches nx).

        Upstream NetworkX's add_weighted_edges_from(ebunch_to_add,
        weight=..., **attr) applies ``attr`` to every edge in addition
        to the weight. The fnx Rust method only takes string weight
        names and validates endpoints up front, but nx streams through
        ``add_edges_from`` one edge at a time. Keep the Python wrapper
        on the streaming path so earlier valid edges remain inserted if
        a later edge or generator step raises. Parameter name matches nx
        (br-r37-c1-wcdm3).

        br-r37-c1-g438p: hash-validate endpoints up front so unhashable
        types (list, set, dict) raise nx-shaped TypeError instead of
        being silently absorbed by the Rust binding (which keys nodes
        by Python id when the value isn't hashable).
        """
        # br-r37-c1-wedgesbatch (cc): for a string weight name, delegate to
        # add_edges_from EXACTLY as nx does -- hits fnx's native attributed batch
        # instead of a per-edge add_edge PyO3 loop (0.135x -> ~1.1x, beats nx). Error
        # contract + partial-insert semantics are add_edges_from's, identical to nx's
        # add_weighted_edges_from (the same delegation). The weighted wiener stale-store
        # bug this previously exposed is now fixed (7b61292a3); broad batch-vs-store
        # check (wiener/size/degree/dijkstra/pagerank/betweenness/closeness/adj_matrix/
        # degree_pearson) all match. Non-str weight keys keep the per-edge path below.
        if isinstance(weight, str):
            # br-r37-c1-awefgen: hand `add_edges_from` a LIST when the input is
            # already re-iterable. The native batch kernel is gated on
            # `isinstance(ebunch_to_add, (list, tuple))`, so streaming a
            # generator into it silently disqualifies every edge from the fast
            # path. Measured on 1600 edges, the SAME edges either way:
            #
            #   MultiDiGraph  add_edges_from(LIST) 1530.0us   (GEN) 4299.0us  2.81x
            #   MultiGraph                          985.1us         4041.2us  4.10x
            #   Graph                               506.5us          735.3us  1.45x
            #
            # and fnx's own add_weighted_edges_from measured 4257.6us on
            # MultiDiGraph - the generator number, not the list one.
            #
            # THE STREAMING PATH IS KEPT where it is load-bearing. networkx
            # streams through add_edges_from one edge at a time, so edges before
            # a bad element ARE inserted and then the error raises
            # (br-r37-c1-wcdm3). Materialising up front would insert nothing.
            # So: only re-iterable inputs are materialised, and if building the
            # list raises, the same source is streamed again - which reproduces
            # networkx exactly, inserting the good prefix before raising at the
            # same element. A generator is never re-iterable and is never
            # materialised.
            if type(ebunch_to_add) in (list, tuple):
                try:
                    materialized = [
                        (u, v, {weight: w}) for u, v, w in ebunch_to_add
                    ]
                except Exception:  # noqa: BLE001 - fall back to nx's streaming
                    self.add_edges_from(
                        ((u, v, {weight: w}) for u, v, w in ebunch_to_add), **attr
                    )
                    return
                self.add_edges_from(materialized, **attr)
                return
            self.add_edges_from(
                ((u, v, {weight: w}) for u, v, w in ebunch_to_add), **attr
            )
            return
        for edge in ebunch_to_add:
            u, v, w = edge
            # br-r37-c1-77ux3 (sibling): nx delegates to
            # ``add_edges_from((u, v, {weight: w}) for ...)``, which creates
            # node ``u`` BEFORE it examines ``v`` — so an edge whose ``v`` is
            # None/unhashable still leaves ``u`` on the graph before raising.
            # Validating both endpoints up front (the old behaviour) dropped
            # that partial node.
            if u is None:
                raise ValueError("None cannot be a node")
            _HASH_PROBE.get(u)
            if v is None:
                self.add_node(u)
                raise ValueError("None cannot be a node")
            try:
                _HASH_PROBE.get(v)
            except TypeError:
                self.add_node(u)
                raise
            edge_attrs = dict(attr)
            edge_attrs[weight] = w
            if self.is_multigraph():
                if isinstance(weight, str):
                    self.add_edge(u, v, **edge_attrs)
                else:
                    key = self.add_edge(u, v)
                    self.edges[u, v, key].update(edge_attrs)
                    _sync_rust_edge_attrs(self)
            else:
                if isinstance(weight, str):
                    self.add_edge(u, v, **edge_attrs)
                else:
                    self.add_edge(u, v)
                    self.edges[u, v].update(edge_attrs)
                    _sync_rust_edge_attrs(self)

    return add_weighted_edges_from


Graph.add_weighted_edges_from = _add_weighted_edges_from_with_attr(Graph)
DiGraph.add_weighted_edges_from = _add_weighted_edges_from_with_attr(DiGraph)
MultiGraph.add_weighted_edges_from = _add_weighted_edges_from_with_attr(MultiGraph)
MultiDiGraph.add_weighted_edges_from = _add_weighted_edges_from_with_attr(MultiDiGraph)


# br-r37-c1-8xp4a: the native reverse copy of each directed class, as it was
# before the public wrapper below - what _materialize_view builds a reverse
# view's concrete graph from (it shares attribute values, as view.copy() does).
_NATIVE_REVERSE = {}


def _directed_reverse_with_copy_kwarg(cls):
    raw = cls.reverse
    _NATIVE_REVERSE[cls] = raw

    def reverse(self, copy=True):
        """Return the reverse of a directed graph.

        copy=True (default) materialises a fresh directed graph whose
        edges are flipped. copy=False returns a frozen live reverse_view
        (matches upstream nx).

        br-r37-c1-0c6wz: the raw Rust reverse path now preserves nx's
        node and edge iteration contract, so copy=True can stay on the
        native O(V+E) path instead of rebuilding through Python add_edge.
        """
        if copy:
            # br-r37-c1-fabqo: a graph VIEW's own Rust storage is empty, so the
            # raw reverse of a filtered view was an empty graph; reverse the
            # concrete graph the view shows. br-r37-c1-uwvq4: deep - networkx
            # deep-copies the graph dict and every node's and edge's attrs.
            return raw(self if type(self) is cls else _coerce_arg_to_fnx_graph(self), deep=True)
        # Live reversed view — matches nx.DiGraph.reverse(copy=False).
        return reverse_view(self)

    return reverse


DiGraph.reverse = _directed_reverse_with_copy_kwarg(DiGraph)
MultiDiGraph.reverse = _directed_reverse_with_copy_kwarg(MultiDiGraph)


class _WeightAwareDegreeView:
    """Python wrapper that adds weight-kwarg support to the Rust
    DegreeView on Graph / DiGraph.

    Unweighted calls delegate to the raw Rust DegreeView. Weighted
    calls compute the degree by summing edge attributes, matching
    upstream NetworkX's semantics.
    """

    def __init__(self, graph, raw_view, *, direction=None):
        self._graph = graph
        self._raw = raw_view
        self._direction = direction  # None | "in" | "out"

    def _as_degree_view(self, weight, values=None, *, pairs=None):
        """br-r37-c1-z4iod: return a VIEW, not a one-shot iterator.

        The weighted whole-graph paths below each returned a raw
        ``iter(zip(...))`` / generator. networkx returns a DegreeView, and the
        difference is not cosmetic — a generator is exhausted by its first
        consumer, so

            deg = G.degree(weight='weight')
            total = sum(d for _, d in deg)
            top   = max(deg, key=lambda kv: kv[1])   # empty under fnx

        gave a correct first answer and an empty second pass, with the failure
        surfacing far from its cause. ``len()`` also raised
        TypeError("object of type 'zip' has no len()"). MultiGraph and
        MultiDiGraph already returned proper views from the same accessor, so
        they were the in-tree control.

        Pairs are materialised into a list because that is what makes the
        result re-iterable and sized; the VALUES were already materialised by
        the native accumulators, so this adds one list of tuples and keeps
        every fast path above intact. ``view[node]`` still answers the WEIGHTED
        degree, via the parent, for any node — not just the ones iterated.
        """
        if values is not None:
            # Lazy: the view re-zips these against the graph's node order on
            # every iteration, so nothing is materialised here.
            return _filtered_degree_view(
                self, None, weight=weight, owner=self, values=values, graph=self._graph,
                whole_graph=True,
            )
        # The remaining producers are one-shot generators (dirty store /
        # non-scalar weight fallbacks), so those DO have to be materialised to
        # become re-iterable. They are the cold paths.
        return _filtered_degree_view(
            self, None, weight=weight, pairs=list(pairs), owner=self, graph=self._graph,
            whole_graph=True,
        )

    def __iter__(self):
        # NetworkX binds its adjacency iterator at the consumer's first
        # ``next()``, not when ``iter(G.degree)`` is called.  The raw PyO3 view
        # snapshots at ``iter(raw)``; defer that call inside a true generator.
        # Native bulk pair creation remains intact; unlike an outer chain,
        # this frame releases the view when the inner walk raises.
        yield from _degree_view_guarded_pairs(self, iter(self._raw))

    def __len__(self):
        return len(self._raw)

    def __getitem__(self, node):
        # br-r37-c1-dv-subscript: nx's DegreeView raises ``KeyError``
        # on a missing node and ``TypeError`` on an unhashable node
        # (the underlying ``self._succ[node]`` dict lookup).  fnx's
        # Rust raw DegreeView translated both to ``NodeNotFound``,
        # masking caller bugs and breaking ``except KeyError:``
        # callers (NodeNotFound is a subclass of NetworkXException,
        # NOT a sibling/subclass of KeyError).  Hash-check + map
        # NodeNotFound→KeyError for nx-shaped contract.
        _HASH_PROBE.get(node)
        try:
            return self._raw[node]
        except NodeNotFound as exc:
            raise KeyError(node) from exc

    def __repr__(self):
        # br-r37-c1-mdvname: previously delegated to ``repr(self._raw)``
        # which always produces ``DegreeView(...)`` (the underlying
        # Rust raw view's repr). After splitting into ``_GraphDegreeView``
        # (DegreeView) and ``_DiGraphDegreeView`` (DiDegreeView)
        # subclasses, format using ``type(self).__name__`` so DiGraph's
        # repr correctly shows ``DiDegreeView({...})``.
        return f"{type(self).__name__}({dict(self)!r})"

    def __reduce__(self):
        # br-r37-c1-dv-pkl: pickle the raw Rust DegreeView (Graph) /
        # DiDegreeView (DiGraph) crashes with TypeError("cannot pickle
        # ... object") because PyO3 types lack default pickle support.
        # Snapshot to a list of (node, degree) 2-tuples — matches the
        # iteration shape of both fnx's and nx's DegreeView (which
        # restores as DegreeView with the same sequence). Live-tracking
        # is lost by design (matches nx — the underlying graph
        # reference can't survive pickling).
        return (list, (list(self),))

    # br-r37-c1-vcopy: nx's DegreeView/DiDegreeView preserve type
    # through copy.copy / copy._deepcopy.  The __reduce__ snapshot
    # path made copy return a plain list — define __copy__ /
    # __deepcopy__ returning self so type(c) is preserved.
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        # br-r37-c1-vcopydc: _deepcopy must be a SNAPSHOT independent
        # of subsequent G mutations (matches nx).  Deep-copy the
        # underlying graph and return its .degree view — preserves
        # type (DegreeView/DiDegreeView via the cycle-190 subclasses)
        # AND snapshot semantics.
        new_graph = _deepcopy(self._graph, memo)
        return new_graph.degree

    def __eq__(self, other):
        # br-r37-c1-dv-eq: nx's DegreeView/DiDegreeView compare
        # equal when their (node, degree) sequences match. The
        # _WeightAwareDegreeView wrapper used default object.__eq__
        # (identity) — `G.degree == G.degree` returned False since
        # each access returns a fresh wrapper instance. Compare via
        # dict-of-(node→degree) so attribute-driven differences are
        # detected (matches nx — same shape as comparing degree
        # sequences).
        if isinstance(other, _WeightAwareDegreeView):
            return dict(self) == dict(other)
        if isinstance(other, (MultiGraphDegreeView, MultiDiGraphDegreeView)):
            return dict(self) == dict(other)
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def __hash__(self):
        return id(self._graph) ^ hash(self._direction or "")

    def _weighted_value(self, node, weight):
        # br-r37-c1-yo1nt: match nx's DegreeView/DiDegreeView *exact*
        # summation — a flat ``sum()`` per neighbor-dict group, with the
        # groups added together (directed total = sum(succ) + sum(pred)),
        # NOT one continuous fold. CPython ``sum`` is Neumaier-compensated for
        # floats and the association matters, so a running ``total +=`` drifts
        # ~1 ULP from nx. See _native_weighted_degree (the all-node fast path).
        # br-r37-c1-degscalar: simple-class twin of the multigraph routing in
        # _weighted_multidegree_value. Same lever, same kernel, same exactness
        # gate; see that function for the full account.
        #
        # GATED ON _direction IS NONE. The native kernel answers TOTAL degree
        # (successors plus predecessors on a directed graph), so an in_degree or
        # out_degree view must NOT come here - it would silently return the
        # wrong number rather than a slow one.
        #
        # Per call at V=2000, node 0 with 4 edges: Graph 2.39us -> 1.01us,
        # DiGraph 2.99us -> 1.05us, against networkx at 0.86us / 1.01us. Both
        # remain BELOW parity; this narrows the gap, it does not close it.
        if self._direction is None and isinstance(weight, str):
            native = getattr(self._graph, "_native_weighted_degree_subset", None)
            if native is not None:
                try:
                    pairs = native([node], weight)
                except TypeError:
                    pairs = None
                if pairs:
                    return pairs[0][1]

        def _grp(neighbors):
            return sum(
                edge_attrs[weight]
                if isinstance(edge_attrs, dict) and weight in edge_attrs
                else 1
                for edge_attrs in dict(neighbors).values()
            )

        if self._direction == "in":
            return _grp(self._graph.pred[node])
        if self._direction == "out":
            return _grp(self._graph.succ[node])
        if self._graph.is_directed():
            # Total degree on a directed graph is in + out weight sum.
            return _grp(self._graph.succ[node]) + _grp(self._graph.pred[node])
        adj = self._graph.adj[node]
        total = _grp(adj)
        # nx counts a self-loop's weight twice for undirected total degree
        # (DegreeView.__getitem__ adds ``nbrs[n].get(weight, 1)`` again when
        # ``n in nbrs``).
        if node in adj:
            edge_attrs = adj[node]
            if isinstance(edge_attrs, dict) and weight in edge_attrs:
                total += edge_attrs[weight]
            else:
                total += 1
        return total

    def __call__(self, nbunch=None, weight=None):
        if weight is None:
            # br-degnbn: nx's G.degree(nbunch) silently skips nodes not
            # in G via nbunch_iter; the Rust raw path raised NodeNotFound
            # on any missing node. Honour the nx contract: single-node
            # lookups preserve KeyError-style errors, iterable nbunches
            # filter to in-graph nodes only.
            # br-r37-c1-ey6ob: hoist the EXACT-`str` lookup above the sequence
            # test entirely. The sequence branch below is guarded by
            # `not isinstance(nbunch, (str, bytes))`, so for an exact `str` it
            # can never be taken — which means every `G.degree("n")` call was
            # paying a two-tuple `isinstance` to learn something the `type(...)
            # is str` test one block later already decides. Provably equivalent:
            # exact `str` reached the identical `self._raw[nbunch]` body before,
            # and a `str` SUBCLASS still fails `type(...) is str` and falls
            # through to the unchanged sequence test.
            #
            # Worth doing because the wrapper, not the lookup, is the cost.
            # Measured on ELF ecfc2d30: the native `self._raw[n]` is 93.0ns while
            # the whole `G.degree(n)` call is 252.5ns, so 159.5ns is Python
            # wrapper — against networkx's own 76.6ns of wrapper over its 109.6ns
            # subscript. `G.degree(n)` is the worst row on this surface at
            # 0.7226x.
            #
            # EXACT `str` only, and that is required rather than cosmetic: the
            # native lookup resolves a key by its CHARACTERS and never calls
            # `__hash__`, so an unhashable `str` subclass would come back with a
            # NUMBER where networkx returns an empty view.
            if type(nbunch) is str:
                try:
                    return self._raw[nbunch]
                except (NodeNotFound, KeyError):
                    # Absent: fall through to the str-iteration contract below,
                    # where networkx's nbunch_iter walks the CHARACTERS.
                    filtered = [n for n in nbunch if n in self._graph]
                    return _filtered_degree_view(
                        self._raw, filtered, owner=self, graph=self._graph
                    )
            # br-r37-c1-ktsxn: the EXACT-`int` twin of the hoist above, for the
            # reason `br-r37-c1-dlqkq` gives for `str`: without it an int
            # argument pays TWO node resolutions on the common path --
            # `nbunch in self._graph` in the `else` arm at the end of this
            # method, then `self._raw[nbunch]` again -- plus, on the way there, a
            # two-tuple `isinstance`, a four-tuple `isinstance`, and a
            # `hasattr(nbunch, "__iter__")` that BUILDS AND SWALLOWS an
            # AttributeError because an int is not iterable.
            #
            # The in-tree control is the multigraph pair: `MultiGraph.degree(n)`
            # and `MultiDiGraph.degree(n)` measured 2.6950x and 2.9415x AGAINST
            # networkx on int keys while `Graph` and `DiGraph` measured 0.4492x
            # and 0.4655x -- the simple classes were the slow ones, and nearly 2x
            # slower in absolute terms (456 / 431 ns per call against 239 / 275)
            # than their more complicated siblings.
            #
            # PROVABLY EQUIVALENT: on a HIT this returns exactly what the `else`
            # arm at the end of the method returns for the same argument; on a
            # MISS it falls through to that unchanged contract. `type(...) is int`
            # excludes `bool` (an int SUBCLASS) and every other subclass, so the
            # unhashable-subclass hazard that forces the exact-type gate on the
            # `str` twin cannot arise here either.
            if type(nbunch) is int:
                try:
                    return self._raw[nbunch]
                except (NodeNotFound, KeyError):
                    pass
            # br-r37-c1-5n6mn: the exact-`str` test now runs BEFORE this one.
            # A `str` is never None, so the order cannot change either answer,
            # and it takes one comparison off every `G.degree("n")` — the hot
            # shape — at the cost of one on the argument-less `G.degree()`,
            # which builds a view and is not called in a loop.
            #
            # Worth doing because the wrapper IS the whole gap. Measured on ELF
            # 2c3e0c53: the subscripts are at parity (networkx 0.1191us, fnx
            # 0.1192us, ratio 0.9990) while the wrappers are not — networkx
            # 0.0896us against fnx 0.1489us. Paired A/B of the two orderings:
            # 0.1515us -> 0.1450us, 1.0408x CI [1.0396, 1.0479].
            if nbunch is None:
                return self._raw
            # br-r37-c1-dlqkq: `str` is excluded from the sequence branch either
            # way, so test that FIRST and short-circuit. The previous spelling
            # (`A or hasattr(...) and not isinstance(...)`) evaluated a 4-tuple
            # isinstance AND a hasattr — which builds and swallows an
            # AttributeError on miss — before rejecting every string key, the
            # most common single-node argument there is. Same truth table:
            # list/tuple/set/frozenset still take the branch, str/bytes still do
            # not, and a non-iterable non-str still falls through.
            if not isinstance(nbunch, (str, bytes)) and (
                isinstance(nbunch, (list, tuple, set, frozenset))
                or hasattr(nbunch, "__iter__")
            ):
                if type(nbunch) not in _NEVER_HASHABLE_TYPES:
                    try:
                        _HASH_PROBE.get(nbunch)
                        if nbunch in self._graph:
                            return self._raw[nbunch]
                    except TypeError:
                        pass
                # br-r37-c1-tk51o: nx.Graph.nbunch_iter raises
                # NetworkXError("Node X in sequence nbunch is not a
                # valid node.") on any unhashable element. Pre-fix fnx
                # silently filtered them out via ``n in self._graph``
                # short-circuit (returns False for unhashables).
                # br-r37-c1-degnbnative (cc): one native pass (hash-check +
                # canonical membership filter + degree) replaces the Python
                # filter loop + per-node raw[n] lookup. The kernel re-raises an
                # unhashable element as TypeError carrying the exact message, so
                # the wrapper below maps it back to NetworkXError. Iteration of
                # the result serves the precomputed pairs; view[node] still falls
                # to the raw view for any node.
                native = getattr(self._graph, "_native_degree_pairs_subset", None)
                if native is not None:
                    try:
                        pairs = native(nbunch)
                    except TypeError as exc:
                        raise NetworkXError(str(exc))
                    return _filtered_degree_view(self._raw, None, pairs=pairs, owner=self, graph=self._graph)
                filtered = []
                for n in nbunch:
                    try:
                        _HASH_PROBE.get(n)
                    except TypeError:
                        raise NetworkXError(
                            f"Node {n} in sequence nbunch is not a valid node."
                        )
                    if n in self._graph:
                        filtered.append(n)
                # br-degnbnview: nx.Graph.degree(nbunch) returns a
                # DegreeView-like object that iterates as (node, deg)
                # tuples AND supports ``view[node]`` key lookup for any
                # node in the original graph. The Rust raw view's
                # __call__(list) returned a plain list of tuples — so
                # callers like bipartite.degrees (which does
                # ``B.degree(top, weight)`` and then ``deg[node]``) broke
                # with "list index out of range" / TypeError. Wrap the
                # filtered result in a small proxy that preserves both
                # behaviours without touching the Rust binding.
                return _filtered_degree_view(self._raw, filtered, owner=self, graph=self._graph)
            # br-r37-c1-1x6aq: nx's DegreeView.__call__ answers with an int
            # ONLY when the node is present:
            #
            #     if nbunch in self._nodes: return <int degree>
            #     return self.__class__(self._graph, nbunch, weight)
            #
            # and that second line runs ``nbunch_iter``, which ITERATES a
            # str/bytes argument's elements. So `G.degree('nope')` on a graph
            # with no 'n'/'o'/'p'/'e' node is an EMPTY VIEW in networkx, not an
            # error — fnx raised NetworkXError here, so ordinary defensive code
            # (`if G.degree(n):`) crashed under fnx where it runs under nx.
            # A non-iterable argument (99) still raises, because nbunch_iter
            # raises on it; that case already matched and is preserved.
            # br-r37-c1-dlqkq: for an EXACT `str`, ask for the DEGREE first and
            # treat its failure as absence. The same contract, but one node
            # resolution instead of two: the membership test canonicalized the
            # key and probed the IndexMap, and then `self._raw[nbunch]` did both
            # again on every successful lookup. Present nodes are the
            # overwhelmingly common case, and paying twice for them made
            # `G.degree(n)` the worst row on the read surface at 0.5073x.
            #
            # EXACT `str` only, and that is not a micro-optimization — it is
            # required. The native lookup resolves a key by its CHARACTERS and
            # never calls `__hash__`, so an unhashable `str` subclass would come
            # back with a NUMBER where networkx returns an empty view (the
            # membership test rejects it via the br-r37-c1-lvlu7 hashability
            # contract). Anything that is not exactly `str` keeps the membership
            # test, which already has that right.
            if type(nbunch) is str:
                try:
                    return self._raw[nbunch]
                except (NodeNotFound, KeyError):
                    pass
            else:
                try:
                    present = nbunch in self._graph
                except TypeError:
                    present = False
                if present:
                    return self._raw[nbunch]
            if isinstance(nbunch, (str, bytes)):
                # Iterating bytes yields ints, which is also what nbunch_iter
                # sees, so the element filter is correct for both types.
                filtered = [n for n in nbunch if n in self._graph]
                return _filtered_degree_view(self._raw, filtered, owner=self, graph=self._graph)
            raise NetworkXError(f"Node {nbunch} is not in the graph.")
        # Weighted path
        if nbunch is None:
            # br-r37-c1-yo1nt: total weighted degree over all nodes routes to
            # the native bulk accumulator (nx-exact flat sum() order + numeric
            # type), avoiding the per-node dict(G.adj[node]) AtlasView walk.
            # Only the total view (no direction) — in/out keep _weighted_value.
            if self._direction is None and isinstance(weight, str):
                # br-r37-c1-wdeg2: for an UNDIRECTED simple Graph, sum weights
                # over the native to_dict_of_dicts snapshot (whose inner dicts
                # ARE the live edge attr dicts) instead of the native
                # _native_weighted_degree kernel, which built a PyList + called
                # Python ``sum`` PER NODE (~1.5x nx). nx counts a self-loop's
                # weight twice, so add it again. Same neighbour order -> byte
                # AND numeric-type identical (int vs float preserved); reaches
                # nx parity. DiGraph total degree (in+out) and multigraph keep
                # the native kernel (to_dict_of_dicts there is successors-only).
                if type(self._graph) is Graph:
                    # br-cc-undegvals: INT weights zip the cached node list with a
                    # VALUES-only native store accumulator (no py_node_key rebuild, no
                    # whole-graph to_dict_of_dicts materialization) — the same win the
                    # DiGraph degree(weight) path carries (0.80x -> ~3x). Returns None
                    # for a dirty store / non-int weight, which keeps FLOAT and mutated
                    # graphs on the byte-identical to_dict_of_dicts sum below.
                    _iv = getattr(
                        self._graph, "_native_weighted_degree_int_values", None
                    )
                    if _iv is not None:
                        _vals = _iv(weight)
                        if _vals is not None:
                            return self._as_degree_view(weight, _vals)
                    # br-r37-c1-wdegfval (bt): FLOAT weights get the same values-only
                    # store accumulator (Neumaier-compensated in Rust, bit-identical to
                    # builtins.sum), skipping the whole to_dict_of_dicts snapshot below.
                    # Returns None on a dirty store / non-float / missing weight, which
                    # keeps int/mixed/mutated graphs on the byte-identical gen path.
                    _fv = getattr(
                        self._graph, "_native_weighted_degree_float_values", None
                    )
                    if _fv is not None:
                        _vals = _fv(weight)
                        if _vals is not None:
                            return self._as_degree_view(weight, _vals)
                    # br-r37-c1-weightupdate-9rts1: a MIXED int/float graph
                    # satisfies neither pure accumulator above, so it fell to the
                    # exact gen below on EVERY weighted read (0.83x nx, where a
                    # single-type graph is 4.9x). The mixed accumulator sums an
                    # exact integer prefix per node and promotes to a compensated
                    # float on that node's first float value, exactly as CPython's
                    # sum() does, so the RESULT TYPE stays per-node nx-identical
                    # (int where nx gives int). Returns None on a dirty store, a
                    # non-numeric weight, i64 overflow, or an integer past 2**53,
                    # which keeps those on the byte-identical gen path.
                    _mv = getattr(
                        self._graph, "_native_weighted_degree_mixed_values", None
                    )
                    if _mv is not None:
                        _vals = _mv(weight)
                        if _vals is not None:
                            return self._as_degree_view(weight, _vals)
                    dod = to_dict_of_dicts(self._graph)

                    def _weighted_degree_gen():
                        for node, nbrs in dod.items():
                            total = sum(d.get(weight, 1) for d in nbrs.values())
                            selfloop = nbrs.get(node)
                            if selfloop is not None:
                                total = total + selfloop.get(weight, 1)
                            yield (node, total)

                    return self._as_degree_view(weight, pairs=_weighted_degree_gen())
                # br-cc-diwdegvals: simple DiGraph total weighted degree zips the
                # cached node list (list(G) via node_iter_mirror, ~0.003ms) with a
                # VALUES-only native accumulator (int-store fast path, else exact
                # PyList+sum). This replaces the per-node succ_row/pred_row dict
                # materialization + Python sum() (which ALSO marked the store dirty
                # on a read) — 0.71ms -> 0.15ms (0.76x -> ~3.7x vs nx). nx adds the
                # two group sums separately (a self-loop is counted in both succ and
                # pred), which the values accumulator reproduces (successors_indices
                # and predecessors_indices both include the self-loop), and list(G)
                # order == nodes_ordered() order (verified), so byte-identical.
                if type(self._graph) is DiGraph:
                    values = getattr(
                        self._graph, "_native_weighted_degree_values", None
                    )
                    if values is not None:
                        return self._as_degree_view(weight, values(weight))
                native = getattr(self._graph, "_native_weighted_degree", None)
                if native is not None:
                    return self._as_degree_view(weight, pairs=native(weight))
            return self._as_degree_view(
                weight,
                pairs=((n, self._weighted_value(n, weight)) for n in self._graph),
            )
        if nbunch in self._graph:
            return self._weighted_value(nbunch, weight)
        # br-r37-c1-degnbw (cc): iterable nbunch + str weight -> native weighted
        # subset pass (was a lazy _FilteredDegreeView whose per-node iteration ran
        # the Python _weighted_value AtlasView loop, ~0.12x). pairs are served on
        # iteration; view[node] still computes weighted via the parent. Native skips
        # not-in-graph nodes (== nbunch_iter) and raises NetworkXError on an
        # unhashable element (== nx + the unweighted path). Falls through when no
        # native (conversion views) or a non-str weight.
        if isinstance(weight, str) and (
            isinstance(nbunch, (list, tuple, set, frozenset))
            or (hasattr(nbunch, "__iter__") and not isinstance(nbunch, (str, bytes)))
        ):
            native = getattr(self._graph, "_native_weighted_degree_subset", None)
            if native is not None:
                try:
                    pairs = native(nbunch, weight)
                except TypeError as exc:
                    raise NetworkXError(str(exc))
                return _filtered_degree_view(self, None, weight=weight, pairs=pairs, owner=self, graph=self._graph)
        # br-degexc: a single hashable nbunch that isn't in the graph
        # must raise NetworkXError, matching NX. Falling through to
        # ``[n for n in nbunch ...]`` would TypeError on non-iterables
        # (e.g. ints) instead.
        try:
            filtered = [n for n in nbunch if n in self._graph]
        except TypeError:
            raise NetworkXError(f"Node {nbunch} is not in the graph.")
        return _filtered_degree_view(self, filtered, weight=weight, owner=self, graph=self._graph)


def _degree_view_guarded_pairs(view, pairs):
    """Preserve a live node-dict guard around native degree snapshots.

    A full NetworkX degree walk is a generator over the adjacency keys. The
    native pair iterators have no mutation guard; itertools.chain cannot make
    their snapshot live or spend them after an exception. A real dict iterator
    supplies CPython's exact size/key checks, including after the final pair,
    and the generator below closes after the first error. Restricted nbunches
    iterate a frozen list instead, so they must not inherit the whole-graph
    guard. Private storage and graph views keep their existing live walks.
    """
    graph = view._graph
    if (
        (getattr(view, "_nodes", None) is not None and not getattr(view, "_whole_graph", False))
        or type(graph) not in (Graph, DiGraph, MultiGraph, MultiDiGraph)
        or _has_networkx_private_storage(graph)
    ):
        return pairs

    def walk():
        nodes = graph._fnx_native_node_iter()
        for _node, pair in zip(nodes, pairs):
            yield pair

    return walk()


def _degree_view_frozen_nodes_check(view):
    """br-r37-c1-pejo5: an nbunch degree view raises once a frozen node is gone.

    networkx resolves the nbunch once and then indexes the adjacency for every
    resolved node on each iteration, so removing one of them turns a later read
    into ``KeyError``. fnx's proxies walked their frozen list and skipped
    whatever was missing, answering with the survivors — right for a node the
    caller NAMED that never existed (it is dropped at resolution and never
    reaches this list), wrong for one that was resolved IN and has since been
    removed.

    Gated on ``nodes_seq``: only a node-set change can invalidate a frozen
    node, so edge churn — the common case — costs one integer compare rather
    than a walk of the nbunch. This mirrors _raise_if_frozen_nbunch_node_removed
    on the edge side (br-r37-c1-2pia7); the two contracts are the same one, on
    neighbouring accessors.
    """
    nodes = view._nodes
    if nodes is None:
        return
    if getattr(view, "_whole_graph", False):
        # An UNRESTRICTED view derives a node list for its own bookkeeping; it
        # was never an nbunch, so nothing in it is "frozen" and a removed node
        # simply drops out (br-r37-c1-vfc2t), it does not raise.
        return
    graph = view._graph
    stamp = getattr(view, "_fnx_nodes_seq", None)
    if stamp is not None:
        current = getattr(graph, "nodes_seq", None)
        if current is not None and current == stamp:
            return
    for node in nodes:
        if node not in graph:
            raise KeyError(node)


class _FilteredDegreeView:
    """Proxy over a DegreeView that restricts iteration to a fixed node
    list while still answering ``view[node]`` lookups via the raw view.

    br-degnbnview: see _WeightAwareDegreeView.__call__ for context.
    Mirrors nx's DegreeView contract so bipartite.degrees and callers
    that mix iteration with key-indexing work transparently.

    br-r37-c1-wu9dv: ``__name__`` set to 'DegreeView' so introspection
    (``type(view).__name__``) matches nx exactly.
    """

    __slots__ = (
        "_raw",
        "_nodes",
        "_weight",
        "_parent",
        "_pairs",
        "_values",
        "_vgraph",
        "_token",
        "_whole_graph",
        "_fnx_nodes_seq",
        "_graph",
    )

    def __init__(
        self, raw, nodes, weight=None, pairs=None, values=None, graph=None, whole_graph=False
    ):
        # br-r37-c1-z4iod: `values` is the lazy mode — a per-node value list
        # straight from a native accumulator, zipped against the graph's node
        # order on each iteration. `pairs` stays the eager mode for the paths
        # that can only produce a one-shot generator.
        self._values = values
        self._vgraph = graph
        # br-r37-c1-vfc2t: an UNRESTRICTED view spans whatever the graph holds
        # now; an nbunch-restricted one keeps its resolved node set frozen, which
        # is networkx's own semantics (br-r37-c1-2pia7).
        self._whole_graph = whole_graph
        # br-r37-c1-pejo5: _graph/_fnx_nodes_seq give the shared frozen-node
        # check the same two attributes the other degree proxies expose.
        self._graph = graph
        # br-r37-c1-degtok: read once, reuse for the token below.
        _seq = getattr(graph, "nodes_seq", None)
        self._fnx_nodes_seq = _seq
        if values is not None:
            self._raw = raw
            self._pairs = None
            self._nodes = None
            self._weight = weight
            self._parent = raw if isinstance(raw, _WeightAwareDegreeView) else None
            self._token = (
            _edge_list_freshness_token(graph, _seq)
            if graph is not None
            else self._freshness()
        )
            return
        self._raw = raw
        # br-r37-c1-degnbnative (cc): when `pairs` (precomputed (node, degree) from
        # the native subset kernel) is supplied, iteration serves it directly and
        # _nodes is derived for __contains__/__len__; __getitem__ still falls to the
        # raw view so view[node] works for any node, not just the subset.
        self._pairs = pairs
        self._nodes = [p[0] for p in pairs] if pairs is not None else list(nodes)
        self._weight = weight
        # When wrapping a _WeightAwareDegreeView for weighted lookup we
        # need the parent to compute weighted values; otherwise raw is
        # the Rust DegreeView for unweighted access.
        self._parent = raw if isinstance(raw, _WeightAwareDegreeView) else None
        self._token = (
            _edge_list_freshness_token(graph, _seq)
            if graph is not None
            else self._freshness()
        )

    # br-r37-c1-vfc2t: networkx's degree views are LIVE. Both snapshot modes
    # here (`pairs` from the native subset kernel, `values` from the native
    # weighted accumulator) were computed at construction and never refreshed,
    # so a view bound before a mutation reported pre-mutation degrees — and a
    # degree is a number, so a stale one is indistinguishable from a correct
    # one.
    #
    # No rebuild thunk is needed, because the third mode is ALREADY live: it
    # walks `_nodes` and calls `_value(n)`, which reads through to the graph.
    # So a stale snapshot just steps aside and lets that path answer. The node
    # SET stays frozen either way, which is what networkx does with an nbunch
    # (see br-r37-c1-2pia7); only the degrees go live.
    def _freshness(self):
        graph = self._graph_ref()
        return None if graph is None else _edge_list_freshness_token(graph)

    def _graph_ref(self):
        if self._vgraph is not None:
            return self._vgraph
        parent = self._parent
        return getattr(parent, "_graph", None) if parent is not None else None

    def _snapshot_is_current(self):
        token = self._token
        if token is None:
            # No token could be computed at construction (foreign graph), so
            # there is nothing to compare against — keep the old behaviour
            # rather than guess.
            return True
        return self._freshness() == token

    def _live_nodes(self):
        """The nodes to report when a snapshot has gone stale.

        Restricted views keep their frozen node list; an unrestricted weighted
        view (the `values` mode, which has no `_nodes`) spans whatever the
        graph holds now, exactly as networkx's does.
        """
        if self._nodes is not None and not self._whole_graph:
            return self._nodes
        graph = self._graph_ref()
        return list(graph) if graph is not None else []

    def _value(self, node):
        if self._weight is not None and self._parent is not None:
            return self._parent._weighted_value(node, self._weight)
        return self._raw[node]

    def __iter__(self):
        # Fresh/stale selection must happen at the first ``next()``.  Returning
        # the selected native iterator directly makes `iter(view)` itself choose
        # a stale snapshot if a caller mutates the graph before consuming it.
        yield from _degree_view_guarded_pairs(self, self._iter_now())

    def _iter_now(self):
        _degree_view_frozen_nodes_check(self)
        # br-r37-c1-degnbhash: the staleness check is INLINE. It used to be
        # `_snapshot_is_current()` -> `_freshness()` -> `_graph_ref()`, three
        # Python frames on every iteration to compare two integers, and a frame
        # was measured at roughly 49ns on this surface (br-r37-c1-degframe). The
        # method stays for `__len__` and any other caller; only this hot site
        # is unrolled, and the logic is copied, not changed.
        # br-r37-c1-z4iod: a plain function returning an iterator, NOT a
        # generator function — the values mode below has to hand back a fresh
        # zip, and a `return` inside a generator would silently end iteration
        # instead of returning it.
        token = self._token
        if token is not None:
            graph = self._vgraph
            if graph is None:
                parent = self._parent
                graph = getattr(parent, "_graph", None) if parent is not None else None
            # A None graph makes `_freshness()` return None, which never equals
            # a non-None token, so it counts as STALE -- unreachable in practice
            # (the token was computed from the same graph at construction) but
            # copied faithfully rather than reasoned away.
            current = None if graph is None else _edge_list_freshness_token(graph)
            if current != token:
                return ((n, self._value(n)) for n in self._live_nodes())
        if self._values is not None:
            # Fresh zip per call: re-iterable like nx's view, and still lazy,
            # so the weighted whole-graph paths keep their native accumulator
            # win instead of materialising a list of tuples up front.
            return iter(zip(self._vgraph, self._values))
        if self._pairs is not None:
            return iter(self._pairs)
        return ((n, self._value(n)) for n in self._nodes)

    def __len__(self):
        # br-r37-c1-vfc2t: len() has to agree with iteration, so it consults
        # the same freshness check. A stale snapshot falls back to the live
        # node set, which for an unrestricted view is the graph's CURRENT
        # nodes and for a restricted one is its frozen nbunch.
        #
        # br-r37-c1-degtok: which is exactly why a RESTRICTED view can skip the
        # check. `_live_nodes()` returns `self._nodes` VERBATIM when the view is
        # restricted, so both branches below already answer `len(self._nodes)`
        # -- the check cannot change the result, and it costs a
        # private-storage probe plus two PyO3 getter crossings. `list(view)`
        # calls `__len__` before `__iter__`, so this was paid on every single
        # materialisation.
        nodes = self._nodes
        if nodes is not None and not self._whole_graph:
            return len(nodes)
        if not self._snapshot_is_current():
            return len(self._live_nodes())
        if self._values is not None:
            return len(self._values)
        return len(self._nodes)

    # br-r37-c1-p1uro: NO __contains__ ON PURPOSE. networkx's degree views do
    # not define one, so `in` falls back to __iter__ — which yields
    # ``(node, degree)`` pairs. On a networkx degree view ``node in view`` is
    # therefore False and ``(node, degree) in view`` is True. This proxy used
    # to define __contains__ over NODES, which inverted BOTH answers (3 of the
    # 4 graph classes; MultiDiGraph escaped because its restricted path does
    # not build this proxy). Two swapped booleans give a caller the wrong
    # branch either way round rather than an error, so the fix is to define
    # nothing and inherit networkx's semantics from iteration. __getitem__ is
    # a separate dunder and still answers by NODE, as it does in networkx.

    def __getitem__(self, node):
        return self._value(node)

    def __call__(self, nbunch=None, weight=None):
        # Rare: chained degree calls. Fall through to the raw underlying
        # graph-level view so nested nbunch semantics still work.
        if isinstance(self._raw, _WeightAwareDegreeView):
            return self._raw(nbunch=nbunch, weight=weight)
        if callable(self._raw):
            return self._raw(nbunch) if nbunch is not None else self._raw
        raise TypeError("DegreeView not callable in this context")

    def __repr__(self):
        # br-r37-c1-wu9dv: nx exposes this as DegreeView({n: deg, ...}) —
        # drop-in code prints the full dict-style repr. Match it.
        # br-r37-c1-1x6aq: the NAME is per-variant, not always "DegreeView" —
        # see _filtered_degree_view.
        return f"{type(self).__name__}({dict(self)!r})"

    def __str__(self):
        # br-r37-c1-wu9dv: nx DegreeView.__str__ returns str(list(self)).
        return str(list(self))


# br-r37-c1-wu9dv: rename so ``type(view).__name__`` matches nx exactly.
_FilteredDegreeView.__name__ = "DegreeView"
_FilteredDegreeView.__qualname__ = "DegreeView"


# br-r37-c1-1x6aq: an nbunch-restricted degree view must report the SAME class
# as the view it restricts. nx has eight of them — DegreeView, DiDegreeView,
# MultiDegreeView, DiMultiDegreeView and the four In/Out variants — and fnx
# returned the single hardcoded "DegreeView" for all of them, so
# ``type(DG.degree(['a'])).__name__`` said DegreeView where nx says
# DiDegreeView (6 of the 8 were wrong).
#
# The unrestricted views already carry the right names, so the name is taken
# from the owning view rather than re-derived from the graph type — one source
# of truth, and a new view variant inherits correct behaviour for free. The
# name must live on the CLASS (``type(v).__name__`` cannot be shadowed per
# instance), hence one cached subclass per name.
_FILTERED_DEGREE_VIEW_CLASSES = {}


# br-r37-c1-degnbhash: EXACT types whose instances can never be hashable, so
# `hash(x)` on one is a guaranteed raise. Exact-type membership is required
# rather than isinstance: a `list` SUBCLASS may legitimately define `__hash__`,
# and must keep taking the real hash path. Measured on a 4-node list nbunch:
# `try hash(list) / except TypeError` costs 228.2ns, against 31.0ns for the type
# test that replaces it -- 8.7% of the whole `G.degree(nbunch)` call, spent
# building and catching an exception whose outcome was known from the type.
_NEVER_HASHABLE_TYPES = frozenset({list, set, dict, bytearray})

# br-r37-c1-degderive: exact container types an nbunch is almost always one
# of. Exact-type membership, so a subclass keeps the general path.
_PLAIN_NBUNCH_CONTAINERS = frozenset({list, tuple, set, frozenset})

# br-r37-c1-degchain: bound once; the per-element walk then happens in C.
_chain_from_iterable = _itertools.chain.from_iterable


def _filtered_degree_view(
    raw, nodes, weight=None, pairs=None, owner=None, values=None, graph=None,
    whole_graph=False,
):
    name = type(owner).__name__ if owner is not None else "DegreeView"
    cls = _FILTERED_DEGREE_VIEW_CLASSES.get(name)
    if cls is None:
        cls = type(name, (_FilteredDegreeView,), {"__slots__": ()})
        cls.__qualname__ = name
        _FILTERED_DEGREE_VIEW_CLASSES[name] = cls
    return cls(
        raw, nodes, weight=weight, pairs=pairs, values=values, graph=graph,
        whole_graph=whole_graph,
    )


# br-r37-c1-viewnames: align ``type(view).__name__`` with nx so
# introspecting code (test fixtures, debug repr, drop-in libraries
# that branch on the view class name) sees the same identifiers
# under fnx as under nx.  Only ``__name__`` is renamed; ``__qualname__``
# stays at the original private name so pickle's class-lookup path
# (``module.qualname``) still finds the class — the existing
# ``__reduce__`` snapshot path on these views matches nx's pickle
# semantic so the qualname mismatch is harmless.
_DiGraphEdgeView.__name__ = "OutEdgeView"
_MultiGraphEdgeView.__name__ = "MultiEdgeView"
_MultiDiGraphEdgeView.__name__ = "OutMultiEdgeView"

# Rust-bound NodeView variants — nx exposes a single ``NodeView`` class
# regardless of graph type.
try:
    _fnx.DiNodeView.__name__ = "NodeView"
except (AttributeError, TypeError):
    pass
try:
    _fnx.MultiGraphNodeView.__name__ = "NodeView"
except (AttributeError, TypeError):
    pass
try:
    _fnx.MultiDiGraphNodeView.__name__ = "NodeView"
except (AttributeError, TypeError):
    pass


# br-r37-c1-mdvname: ``type(G.degree).__name__`` should return
# nx's canonical ``DegreeView`` (Graph) or ``DiDegreeView``
# (DiGraph). Define two trivial subclasses with the right
# ``__name__`` so introspection matches nx.  ``_WeightAwareDegreeView
# .__repr__`` already returned ``repr(self._raw)`` with the right
# text — these subclasses inherit that behaviour.
class _GraphDegreeView(_WeightAwareDegreeView):
    pass
_GraphDegreeView.__name__ = "DegreeView"


class _DiGraphDegreeView(_WeightAwareDegreeView):
    pass
_DiGraphDegreeView.__name__ = "DiDegreeView"


# Capture the raw Rust descriptors before overriding so our wrapper can
# delegate to them.
_GRAPH_RAW_DEGREE = Graph.degree
_DIGRAPH_RAW_DEGREE = DiGraph.degree


def _graph_degree(self):
    return _GraphDegreeView(self, _GRAPH_RAW_DEGREE.__get__(self, type(self)))
