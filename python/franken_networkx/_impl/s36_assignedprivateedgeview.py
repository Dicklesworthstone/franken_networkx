

class _AssignedPrivateEdgeView:
    def __init__(self, graph):
        self._graph = graph

    def _nbunch(self, nbunch):
        if nbunch is None:
            # br-r37-c1-ka7fd: iterate the ADJACENCY, not the node view.
            # networkx's EdgeView walks `_adj`; this walked `list(self._graph)`,
            # which under an assigned `G._node` reports the assigned mapping
            # instead. That made `G.edges()` raise KeyError on a node with no
            # adjacency row, and — once the raise was guarded — return NO edges
            # at all, where nx returns the edges held in `_adj`.
            #
            # Safe to change wholesale because this view exists ONLY for the
            # assigned-private-storage case: ordinary graphs never reach it, so
            # neither edge order nor the hot path moves.
            return list(_assigned_raw_adj(self._graph))
        # br-r37-c1-wzypa: networkx's nbunch handling is ASYMMETRIC, and both
        # halves are reproduced here because the asymmetry is observable:
        #
        #   G.edges('a')                -> [('a','b')]   'a' has an adjacency row
        #   G.edges('private')          -> KeyError      in _node, NOT in _adj
        #   G.edges('ghost')            -> []            in neither: nx iterates
        #                                                the string's characters
        #   G.edges(['a','private'])    -> [('a','b')]   'private' silently SKIPPED
        #
        # A scalar is tested against the NODE view (nx's `nbunch in self` uses
        # `__contains__`, i.e. `_node`) and returned unfiltered, so the later
        # adjacency lookup raises for a node with no row — that is where nx's
        # KeyError comes from. An iterable is filtered against the ADJACENCY
        # (nx's `nbunch_iter` keeps `n for n in nbunch if n in adj`), so the same
        # node inside a list is dropped instead of raising.
        try:
            if nbunch in self._graph:
                return [nbunch]
        except TypeError:
            pass
        adjacency = _assigned_raw_adj(self._graph)
        try:
            iterator = iter(nbunch)
        except TypeError:
            return []
        nodes = []
        for node in iterator:
            try:
                if node in adjacency:
                    nodes.append(node)
            except TypeError:
                raise NetworkXError(
                    f"Node {node} in sequence nbunch is not a valid node."
                ) from None
        return nodes

    def _rows(self, nbunch=None, data=False, keys=False):
        nodes = self._nbunch(nbunch)
        result = []
        graph = self._graph
        adj = _assigned_raw_adj(graph)
        # `is_multigraph()` was being called once per EDGE from inside both
        # branches below; it is a property of the graph, not of the edge.
        multi = graph.is_multigraph()

        if graph.is_directed():
            for source in nodes:
                # br-r37-c1-wzypa: NOT guarded. `_nbunch` now yields only sources
                # that have an adjacency row — except for an explicit SCALAR
                # nbunch, which nx returns unfiltered precisely so this lookup
                # raises KeyError. Swallowing it here would turn nx's raise into
                # an empty result.
                for target, edge_data in adj[source].items():
                    if multi:
                        for key, attrs in edge_data.items():
                            if keys and data:
                                result.append((source, target, key, attrs))
                            elif keys:
                                result.append((source, target, key))
                            elif data:
                                result.append((source, target, attrs))
                            else:
                                result.append((source, target))
                    elif data:
                        result.append((source, target, edge_data))
                    else:
                        result.append((source, target))
            return result

        seen = set()
        for source in nodes:
            # br-r37-c1-wzypa: unguarded, for the reason in the directed branch.
            for target, edge_data in adj[source].items():
                if target in seen:
                    continue
                if multi:
                    for key, attrs in edge_data.items():
                        if keys and data:
                            result.append((source, target, key, attrs))
                        elif keys:
                            result.append((source, target, key))
                        elif data:
                            result.append((source, target, attrs))
                        else:
                            result.append((source, target))
                elif data:
                    result.append((source, target, edge_data))
                else:
                    result.append((source, target))
            seen.add(source)
        return result

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        # br-r37-c1-jqytt: `M.edges(keys=True)` IS the view, not a copy of it.
        # networkx's `MultiEdgeView.__call__` returns `self` for exactly this
        # argument shape, and everything that makes a view a view goes with the
        # bare list this used to hand back: the class name, liveness, and the
        # 2-tuple containment rule (`('a','b') in M.edges(keys=True)` matches
        # ANY key), which a list cannot express at all.
        #
        # THE RECURSION br-r37-c1-p1dbu RECORDS IS DESIGNED OUT rather than
        # fenced off. That bead had to revert a `return self` because the view's
        # `__iter__` reached the call form and came straight back. `__iter__`
        # below now goes to `_rows` directly, so no path from `self` returns to
        # `__call__`, and the short-circuit cannot close a loop.
        # THE RULE IS "ASKED FOR MY OWN TUPLE SHAPE", which is why `keys` is
        # compared against `_is_multi` rather than against True. networkx returns
        # `self` from `EdgeView.__call__` and `OutEdgeView.__call__` on the
        # DEFAULT call — 2-tuples — and from `MultiEdgeView.__call__` only when
        # `keys=True`, because a multigraph view's own tuples are keyed. Asking a
        # multigraph for `keys=False` is asking for a DIFFERENT shape, and nx
        # hands back a MultiEdgeDataView for it. Reading that asymmetry off the
        # four classes at once is what turned this from the bead's one cell into
        # the rule; writing `keys is True` here would have fixed the multigraph
        # half and left both simple classes wrong.
        if nbunch is None and data is False and bool(keys) == self._is_multi:
            return self
        if isinstance(data, str):
            rows = self._rows(nbunch=nbunch, data=True, keys=keys)
            if keys:
                projected = [
                    (u, v, key, attrs.get(data, default))
                    for u, v, key, attrs in rows
                ]
            else:
                projected = [(u, v, attrs.get(data, default)) for u, v, attrs in rows]
            return self._as_data_view(projected)
        if data is None:
            rows = self._rows(nbunch=nbunch, data=False, keys=keys)
            if keys:
                projected = [(u, v, key, default) for u, v, key in rows]
            else:
                projected = [(u, v, default) for u, v in rows]
            return self._as_data_view(projected)
        return self._as_data_view(self._rows(nbunch=nbunch, data=data, keys=keys))

    @property
    def _is_multi(self):
        return self._graph.is_multigraph()

    def _as_data_view(self, rows):
        """Wrap a built edge list in the class networkx names for this call.

        br-r37-c1-jqytt: every `edges(...)` form on this view handed back a bare
        `list`, so `type(G.edges(data=True)).__name__` read `list` against nx's
        `EdgeDataView` on all four classes — 20 cells beyond the `keys=True` one
        this bead was filed for, all the same omission. The ordinary
        (non-private) path has wrapped its results in these same classes since
        br-r37-c1-mgcall; this view was simply never given the treatment.
        """
        multi = self._is_multi
        directed = self._graph.is_directed()
        if multi:
            view_cls = _OutMultiEdgeDataView if directed else _MultiEdgeDataView
        elif directed:
            view_cls = _OutEdgeDataView
        else:
            # THE UNDIRECTED SIMPLE CASE KEEPS ITS BARE LIST, deliberately.
            # nx names it `EdgeDataView`, and fnx's `EdgeDataView` is a LIVE
            # view built from a call thunk — `(edge_view_call, view_self, *,
            # data, default, nbunch_list, graph)` — not a list wrapper, so
            # feeding it a built list is a TypeError rather than a rename. The
            # other three names all have list-based classes already; this one
            # has no twin, and inventing one to close a type-name cell is a
            # bigger change than this bead, wearing a smaller one's clothes.
            # Left as it was, and recorded on the bead rather than fixed.
            return rows
        return _wrap_edge_data_view(rows, view_cls)

    def __iter__(self):
        # br-r37-c1-vbe1o: ITERATING a multigraph edge view is not the same as
        # CALLING it. nx's MultiEdgeView.__iter__ yields KEYED (u, v, k) tuples,
        # while `G.edges(...)` with the default `keys=False` yields (u, v). fnx's
        # ordinary multigraph view already matches nx (3-tuples); only this
        # private-storage view returned 2-tuples, because it delegated to the
        # CALL form.
        #
        # br-r37-c1-jqytt: straight to `_rows`, NOT through `self(...)`. The call
        # form now short-circuits to `self` for the multigraph keyed shape, so
        # routing iteration through it would be the exact infinite recursion
        # br-r37-c1-p1dbu had to revert a `return self` for. Going to the builder
        # keeps the two directions independent, and is one less dispatch besides.
        return iter(self._rows(keys=self._is_multi))

    def __len__(self):
        # Same asymmetry: nx counts parallel edges individually, which the
        # keys=False form collapses.
        #
        # br-r37-c1-ktsxn: COUNT the assigned adjacency instead of building the
        # edge list to measure it. This was the worst row measured on the whole
        # surface: `len(G.edges)` under assigned private storage read `0.012x`
        # against networkx -- 1925.5us against 22.6us, 85x -- because networkx
        # sums row lengths while this materialised every edge as a tuple. And
        # since CPython's `list(obj)` asks for `__len__` to preallocate BEFORE
        # iterating, `list(G.edges)` paid that build TWICE.
        #
        # THE ARITHMETIC IS THE PART WORTH CHECKING, and it was checked rather
        # than reasoned: a self-loop occupies ONE slot in its own adjacency row
        # but counts TWICE in the degree sum networkx halves, so the naive
        # `row_sum // 2` undercounts whenever the self-loop count is ODD. The
        # corrected `(row_sum + loops) // 2` was verified against
        # `networkx.number_of_edges()` across all four classes and eight edge
        # shapes -- none / one / two / THREE self-loops, an isolated self-loop,
        # a self-loop beside a reciprocal pair, the empty graph, and parallel
        # edges -- and matches every one.
        #
        # `self._graph.adj` is the assigned mapping this view exists to serve,
        # and is `_succ` on a directed graph, so the directed count is the row
        # sum with no halving.
        graph = self._graph
        # br-r37-c1-ktsxn: read the RAW assigned mapping, not `graph.adj`. The
        # public accessor hands back an `AdjacencyView` whose `.values()` wraps
        # every row -- measured at 315.7us for 400 rows against ~20us for the
        # underlying dict, which left this row at 0.0336x even after the count
        # replaced the materialisation. `_private_override` is the same reader
        # the rest of the assigned-storage machinery uses; a directed graph
        # stores its successors under the succ key. Falling back to `graph.adj`
        # keeps the answer correct if neither override is present.
        adj = _assigned_raw_adj(graph)
        # ONE pass over items(): the separate self-loop scan had to re-subscript
        # the mapping per node and cost more than the row sum it accompanied
        # (15.5us against 9.9us for 400 rows).
        row_sum = 0
        loops = 0
        if graph.is_multigraph():
            for node, row in adj.items():
                row_sum += sum(len(kd) for kd in row.values())
                loop_row = row.get(node)
                if loop_row is not None:
                    loops += len(loop_row)
        else:
            for node, row in adj.items():
                row_sum += len(row)
                if node in row:
                    loops += 1
        if graph.is_directed():
            return row_sum
        return (row_sum + loops) // 2

    def __contains__(self, edge):
        if self._graph.is_multigraph():
            # This view exists because a NetworkX private mapping was assigned,
            # so adjacency (not the native store) is the authority.  A two-item
            # probe means key zero rather than "any parallel edge".
            N = len(edge)
            if N == 3:
                u, v, key = edge
            elif N == 2:
                u, v = edge
                key = 0
            else:
                raise ValueError("MultiEdge must have length 2 or 3")
            try:
                return key in self._graph.adj[u][v]
            except KeyError:
                return False
        # br-r37-c1-jqytt: networkx uses TWO DIFFERENT SPELLINGS here and the
        # difference is observable, so both are reproduced rather than averaged
        # into one lenient slice:
        #
        #   EdgeView.__contains__      u, v = e[:2]   except (KeyError, ValueError)
        #   OutEdgeView.__contains__   u, v = e       except KeyError
        #
        # So on an UNDIRECTED graph a 3- or 4-tuple silently drops its tail and
        # answers, while on a DIRECTED one it is a ValueError; and a non-iterable
        # raises different TypeErrors from the two ("'int' object is not
        # subscriptable" against "cannot unpack non-iterable int object")
        # because one subscripts and the other unpacks. Measured against live nx
        # across eight probe shapes on both classes — this used to answer False
        # for five of them where nx raises or answers True.
        if self._graph.is_directed():
            # Strict: ValueError and TypeError both propagate, as nx's does.
            u, v = edge
        else:
            # Lenient slice. TypeError propagates (nx does not catch it); a
            # too-short tuple is nx's caught ValueError, i.e. False.
            try:
                u, v = edge[:2]
            except ValueError:
                return False
        return self._graph.has_edge(u, v)

    def _nx_view_name(self):
        # br-r37-c1-4c6s7: this ONE class stands in for four networkx view
        # classes, and the class name is observable — it is interpolated into
        # the slicing error. The ordinary (non-private) fnx path already
        # reports all four nx names correctly; this view was the only outlier.
        multi = self._graph.is_multigraph()
        directed = self._graph.is_directed()
        if multi:
            return "OutMultiEdgeView" if directed else "MultiEdgeView"
        return "OutEdgeView" if directed else "EdgeView"

    def __getitem__(self, edge):
        # br-r37-c1-4c6s7: mirror networkx's reportviews exactly. This used to
        # be ``u, v = edge[:2]`` with an OPTIONAL third element for multigraphs,
        # which is not the incumbent contract in three separate ways:
        #
        #   * nx unpacks STRICTLY — ``u, v = e`` for simple graphs and
        #     ``u, v, k = e`` for multigraphs. A multigraph subscript therefore
        #     REQUIRES a 3-tuple; ``G.edges['a','b']`` is a ValueError, not a
        #     lookup. The old slice-and-length-check accepted both arities on
        #     both graph kinds.
        #   * the unpack happens BEFORE any lookup or hashing, so an arity error
        #     beats an unhashable-endpoint error. We raised TypeError where nx
        #     raises ValueError.
        #   * a slice must raise nx's typed, actionable NetworkXError. Indexing
        #     a slice gave a bare "'slice' object is not subscriptable".
        #
        # Compared with exception ARGS, not just types — several of these read
        # as green on a type-only sweep (br-r37-c1-4c6s7 lists all 11 cases).
        if isinstance(edge, slice):
            raise NetworkXError(
                f"{self._nx_view_name()} does not support slicing, try "
                f"list(G.edges)[{edge.start}:{edge.stop}:{edge.step}]"
            )
        # Read through `.adj`, which under assigned private storage IS the
        # assigned mapping — the same mapping nx's `_adjdict` points at. Going
        # via `get_edge_data` consulted a different store.
        adj = self._graph.adj
        if self._graph.is_multigraph():
            u, v, key = edge
            # nx's OutMultiEdgeView does NOT customise this message, so the raw
            # KeyError carries whichever dict level actually failed.
            return adj[u][v][key]
        u, v = edge
        try:
            return adj[u][v]
        except KeyError:
            # Deliberately an implicit chain, as in nx: it re-raises inside the
            # `except` without `from None`, so __context__ stays set.
            raise KeyError(f"The edge {edge} is not in the graph.")

    def data(self, data=True, default=None, nbunch=None, keys=False):
        return self(nbunch=nbunch, data=data, keys=keys, default=default)

    get = _adjacency_view_get
    keys = _adjacency_view_keys
    items = _adjacency_view_items
    values = _adjacency_view_values

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
        if isinstance(other, (set, frozenset)):
            return set(self) == other
        return NotImplemented

    __hash__ = None


# br-r37-c1-jqytt: ONE behaviour, FOUR names — the same shape `_FilteredEdgeView`
# already uses for the same reason. `_nx_view_name` above computes these strings
# for the slicing error, which means the class knew nx's name for itself all
# along and `type(G.edges).__name__` still read `_AssignedPrivateEdgeView`. A
# name reachable only from an error message is not the observable one; users
# read `type(...)`, and so does anything dispatching on it.
#
# Subclassing rather than assigning `__name__` per instance, because a name is a
# property of the class and an instance-level override does not survive
# `type(view).__name__` — which is the spelling that was wrong.
class _AssignedPrivateGraphEdgeView(_AssignedPrivateEdgeView):
    pass
_AssignedPrivateGraphEdgeView.__name__ = "EdgeView"


class _AssignedPrivateOutEdgeView(_AssignedPrivateEdgeView):
    pass
_AssignedPrivateOutEdgeView.__name__ = "OutEdgeView"


class _AssignedPrivateMultiEdgeView(_AssignedPrivateEdgeView):
    pass
_AssignedPrivateMultiEdgeView.__name__ = "MultiEdgeView"


class _AssignedPrivateOutMultiEdgeView(_AssignedPrivateEdgeView):
    pass
_AssignedPrivateOutMultiEdgeView.__name__ = "OutMultiEdgeView"


def _assigned_private_edge_view(graph):
    """The `_AssignedPrivateEdgeView` subclass networkx would name for `graph`.

    br-r37-c1-jqytt. Chosen from the graph's own `is_multigraph()` /
    `is_directed()` rather than from `type(graph)`, so a subclass of any of the
    four still lands on the right name.
    """
    if graph.is_multigraph():
        cls = (
            _AssignedPrivateOutMultiEdgeView
            if graph.is_directed()
            else _AssignedPrivateMultiEdgeView
        )
    else:
        cls = (
            _AssignedPrivateOutEdgeView
            if graph.is_directed()
            else _AssignedPrivateGraphEdgeView
        )
    return cls(graph)


class _AssignedPrivateDegreeView:
    def __init__(self, graph, *, nodes=None, weight=None):
        self._graph = graph
        self._nodes = nodes
        self._weight = weight
        # br-r37-c1-degsnap: snapshot the IMMUTABLE half of fast-path
        # eligibility. A graph instance never changes class, directedness or
        # multi-ness, and this view's `weight` is fixed at construction -- so
        # re-deriving `type(graph) not in (...)`, `is_directed()` and
        # `is_multigraph()` on EVERY scalar call was pure repetition. Only the
        # OVERRIDE PRESENCE can change during the view's life, and that is still
        # read live from `graph.__dict__` on every call.
        #
        # A `_FilteredGraphView` (or any non-concrete parent) fails the type test
        # and gets `_fast_map = None`, so it pays these stores once and skips the
        # two predicate reads it used to make per call.
        # br-r37-c1-degwt: the snapshot is deliberately WEIGHT-INDEPENDENT. It
        # used to bail when `weight` was set, which left the weighted walk with
        # no fast path at all -- and that walk was the worst measured row on the
        # surface at `0.0904x`. Each consumer states its own weight rule.
        # br-r37-c1-degbind: BIND THE MAPPING, don't re-read it per call. This
        # is a PARITY fix first and a perf lever second. networkx's
        # `DegreeView.__init__` does `self._succ = G._succ`, so a view the
        # caller HOLDS stays bound to the mapping it was built from; fnx re-read
        # the override on every call, so a held view tracked a REASSIGNED
        # `G._adj` where networkx keeps reporting the old one. Measured
        # divergence, before this change:
        #
        #   held view, then `G._adj = {...}`
        #     nx  -> [(0,1),(1,2),(2,1),(3,0)]   the mapping it was built with
        #     fnx -> [(0,3),(1,1),(2,1),(3,1)]   the new one
        #
        # Binding matches networkx on BOTH sides: in-place mutation of the same
        # mapping is still seen (it is the same object, exactly as nx's
        # `self._succ` is), and a REASSIGNMENT is not -- while a freshly read
        # `G.degree` still gets the new mapping, because the assignment funnel
        # drops the memoised view (br-r37-c1-degprop).
        if type(graph) in (
            Graph,
            DiGraph,
            MultiGraph,
            MultiDiGraph,
        ):
            directed = graph.is_directed()
            self._fast_directed = directed
            self._fast_multi = graph.is_multigraph()
            storage = graph.__dict__
            missing = _PRIVATE_MISSING
            fast_map = storage.get(
                _PRIVATE_SUCC_OVERRIDE if directed else _PRIVATE_ADJ_OVERRIDE,
                missing,
            )
            fast_pred = (
                storage.get(_PRIVATE_PRED_OVERRIDE, missing) if directed else None
            )
            if fast_map is missing or fast_pred is missing:
                self._fast_map = None
                self._fast_pred = None
            else:
                self._fast_map = fast_map
                self._fast_pred = fast_pred
        else:
            self._fast_directed = False
            self._fast_multi = False
            self._fast_map = None
            self._fast_pred = None

    def _derive(self, nodes=None, weight=None):
        """A sibling view over the SAME graph, reusing this one's snapshot.

        br-r37-c1-degderive: `__call__` builds a fresh view on every
        `G.degree(nbunch)` / `G.degree(weight=...)`, and `__init__` re-derives a
        snapshot -- the class test, `is_directed()`, `is_multigraph()`, and two
        instance-dict lookups for the override mappings -- that THIS view
        already holds for that very graph. Measured: 392.9ns for the full
        `__init__` against 148.1ns for copying, so 244.8ns a call, about 10% of
        the whole `list(G.degree(nbunch))` row.

        Copying is exact, not approximate. Every snapshot field is a property of
        the GRAPH, not of the view: its class, its directedness, its
        multi-ness, and -- since br-r37-c1-degwt made the snapshot
        weight-independent -- the mappings, which is why a different `weight`
        may reuse them. And since br-r37-c1-degbind a view is deliberately BOUND
        to the mappings it was built with, so handing the child the parent's
        mappings is the same contract networkx has: a child made from a stale
        parent is stale in exactly the way its parent is, while a freshly read
        `G.degree` rebuilds because the assignment funnel drops the memoised
        view.
        """
        sibling = object.__new__(type(self))
        sibling._graph = self._graph
        sibling._nodes = nodes
        sibling._weight = weight
        sibling._fast_directed = self._fast_directed
        sibling._fast_multi = self._fast_multi
        sibling._fast_map = self._fast_map
        sibling._fast_pred = self._fast_pred
        return sibling

    def _nodes_authority(self):
        """nx's ``_nodes`` for a DegreeView: ``self._succ``.

        br-r37-c1-vbe1o: on an undirected graph ``_succ`` IS ``_adj``, and on a
        directed one it is the successor side — for the TOTAL-degree view too,
        which is why nx's ``G.degree`` raises KeyError for a node an assigned
        ``_succ`` carries but ``_pred`` does not. Either way the authority is a
        MAPPING, never the node view: ``iter(self._graph)`` dropped a node the
        assigned adjacency carried and admitted one only an assigned ``_node``
        carried.

        This whole class exists only for graphs carrying private storage, so no
        ordinary graph reaches this and there is nothing to measure.
        """
        graph = self._graph
        return graph.succ if graph.is_directed() else graph.adj

    def _iter_nodes(self):
        if self._nodes is None:
            return iter(self._nodes_authority())
        return iter(self._nodes)

    def _edge_weight(self, attrs):
        if self._weight is None:
            return 1
        return attrs.get(self._weight, 1)

    def _filtered_set_count(self, node, *, reverse=False):
        # br-r37-c1-r3gjb: unweighted degree on a node-set subgraph with the
        # DEFAULT edge filter is a set intersection over the native parent
        # row — the visible neighbours of a (visible) node are exactly
        # parent_row & keep, every edge being visible. Count them in C instead
        # of the per-neighbour _node_visible / _edge_visible Python loop.
        # Simple graphs count neighbours; multigraphs sum parallel-edge
        # multiplicity (len of each keydict). Undirected total degree counts
        # a self-loop's edges twice. Returns None -> slow path for weighted /
        # non-default edge filter / non-set node filter / non-visible node.
        view = self._graph
        if (
            self._weight is not None
            or not getattr(view, "_filter_edge_is_default", False)
            or not isinstance(view, _FilteredGraphView)
        ):
            return None
        # br-r37-c1-kum9v: the fast path reads native parent rows
        # (_fast_pred_row / parent[node]); a NESTED subgraph's parent is
        # another _FilteredGraphView whose Rust base is EMPTY, so the inherited
        # _native_predecessor_row_dict raises KeyError. Only fast-path when the
        # parent is a CONCRETE graph; nested views fall to the slow filtered
        # walk (correct — that path was not actually fast for a view parent).
        parent = view._graph
        if type(parent) not in (Graph, DiGraph, MultiGraph, MultiDiGraph):
            return None
        keep = getattr(getattr(view, "_filter_node", None), "nodes", None)
        if keep is None or node not in keep:
            return None
        if reverse:
            row = _fast_pred_row(parent, node)
        else:
            row = parent[node]
        try:
            visible = keep.intersection(row)
        except TypeError:
            return None
        multi = view.is_multigraph()
        if multi:
            total = sum(len(row[nbr]) for nbr in visible)
        else:
            total = len(visible)
        # undirected total degree double-counts a (visible) self-loop
        if not reverse and not view.is_directed() and node in row:
            total += len(row[node]) if multi else 1
        return total

    def _filtered_set_weight(self, node, *, reverse=False):
        """br-r37-c1-subwdeg: the WEIGHTED twin of `_filtered_set_count`.

        Weighted degree on a node-set subgraph was the worst row on the whole
        read surface: `subgraph.degree(n, weight=)` measured 0.0853x on
        MultiGraph and 0.0911x on MultiDiGraph, ~11.7x slower than networkx, on
        a node whose degree is THREE. The unweighted twin sits at 0.9970x on the
        same fixture, which is what localises the cost: `_filtered_set_count`
        bails whenever a weight is set, so the weighted call fell to the generic
        walk over `self._graph.adj[node]`, and on a filtered MULTIgraph view
        `.values()` builds a filtered keydict per neighbour. Measured on that
        node: `dict(adj[0])` alone is 32.5us against networkx's 5.3us.

        ORDER IS LOAD-BEARING HERE IN A WAY IT IS NOT IN THE COUNTING TWIN.
        `_filtered_set_count` may use `keep.intersection(row)` and let the SET
        decide iteration order, because a count is order-invariant. A weighted
        sum is not: CPython's builtins.sum is Neumaier-compensated and the
        association decides the answer (br-r37-c1-outdegsum landed 133 cells
        that got this wrong). So this walks `row` in PARENT ADJACENCY ORDER and
        filters, which is the order the filtered adjacency view yields and
        therefore the order networkx sums in.

        Same gates as the counting twin: default edge filter only (so every
        edge of a visible pair is visible), a CONCRETE parent only, and a
        node-set filter. Anything else returns None and keeps the generic walk.
        """
        view = self._graph
        weight = self._weight
        if (
            weight is None
            or not getattr(view, "_filter_edge_is_default", False)
            or not isinstance(view, _FilteredGraphView)
        ):
            return None
        parent = view._graph
        if type(parent) not in (Graph, DiGraph, MultiGraph, MultiDiGraph):
            return None
        keep = getattr(getattr(view, "_filter_node", None), "nodes", None)
        if keep is None:
            return None
        try:
            if node not in keep:
                return None
        except TypeError:
            return None
        row = _fast_pred_row(parent, node) if reverse else parent[node]
        multi = view.is_multigraph()
        try:
            if multi:
                total = sum(
                    attrs.get(weight, 1)
                    for nbr in row
                    if nbr in keep
                    for attrs in row[nbr].values()
                )
            else:
                total = sum(
                    row[nbr].get(weight, 1) for nbr in row if nbr in keep
                )
        except TypeError:
            return None
        # undirected total degree double-counts a (visible) self-loop, exactly
        # as networkx adds `nbrs[n]` again after its flat sum.
        if not reverse and not view.is_directed() and node in row:
            if multi:
                total += sum(attrs.get(weight, 1) for attrs in row[node].values())
            else:
                total += row[node].get(weight, 1)
        return total

    def _visible_edge_count(self, node, nbr, row):
        """br-r37-c1-p6dhq: how many edges (node, nbr) are visible, WITHOUT
        materialising their attribute dicts.

        Unweighted degree only ever needs a COUNT -- `_edge_weight` returns a
        constant 1 when `self._weight is None` -- but the walk reached that count
        by iterating `row.items()`, which builds the filtered keydict VALUE for
        every neighbour. On a multigraph that is a `_multi_edge_keydict` plus an
        inner view per neighbour, and it was the dominant cost of the worst row
        on the surface: 3735us to answer `degree()` for THREE nodes.

        `_native_edge_key_set` gives the parallel-edge keys directly, the same
        accessor br-r37-c1-k3vnp used for row iteration, gated the same way -- a
        CONCRETE multigraph parent only, because a reverse/filtered view
        delegates it WITHOUT reorienting and answers the empty set for both
        orientations.
        """
        view = self._graph
        if not view.is_multigraph():
            return 1
        key_set = self._fnx_parent_key_set
        if key_set is None:
            return len(row[nbr])
        return sum(
            1 for key in key_set(node, nbr) if view._edge_visible(node, nbr, key)
        )

    @property
    def _fnx_parent_key_set(self):
        view = self._graph
        # The degree view's graph is NOT always a filtered view -- a concrete
        # graph has no `_edge_visible`, and on one `getattr(view, "_graph")`
        # still returns something, so the isinstance check is what makes this
        # safe rather than the parent-type check alone. Caught by
        # test_upstream_networkx_view_helpers_accept_fnx_graphs.
        if not isinstance(view, _FilteredGraphView):
            return None
        parent = getattr(view, "_graph", None)
        if type(parent) not in (MultiGraph, MultiDiGraph):
            return None
        return getattr(parent, "_native_edge_key_set", None)

    def _out_degree(self, node):
        fast = self._filtered_set_count(node)
        if fast is not None:
            return fast
        # br-r37-c1-subwdeg: the weighted twin of the probe above.
        fast = self._filtered_set_weight(node)
        if fast is not None:
            return fast
        # br-r37-c1-p6dhq: unweighted degree is a COUNT; do not build the values.
        if self._weight is None:
            view = self._graph
            row = view.adj[node]
            undirected = not view.is_directed()
            # br-r37-c1-degnbr: `_visible_edge_count` was reached through a
            # Python method call PER NEIGHBOUR, and each call re-asked
            # `is_multigraph()` -- 8 calls per node on a 4-degree simple graph,
            # to compute a constant. For a simple graph it IS a constant 1, so
            # the whole walk is the row length plus the self-loop bump, which is
            # exactly what networkx's DegreeView yields. Same answer, no loop.
            if not view.is_multigraph():
                total = len(row)
                if undirected and node in row:
                    total += 1
                return total
            key_set = self._fnx_parent_key_set
            if key_set is None:
                # The concrete-multigraph twin, inlined. `row[nbr]` is kept in
                # place of `row.items()` deliberately: on a FILTERED multigraph
                # view items() builds the filtered keydict VALUE per neighbour,
                # which is the cost br-r37-c1-p6dhq removed.
                total = 0
                for nbr in row:
                    count = len(row[nbr])
                    total += count
                    if undirected and nbr == node:
                        total += count
                return total
            total = 0
            for nbr in row:
                count = self._visible_edge_count(node, nbr, row)
                total += count
                if undirected and nbr == node:
                    total += count
            return total
        # br-r37-c1-outdegsum: ONE flat sum() over all neighbours, THEN the
        # self-loop term added once - which is both what networkx computes and,
        # separately, the association it computes it in:
        #
        #     deg = sum(dd.get(weight, 1) for dd in nbrs.values())
        #     if n in nbrs: deg += nbrs[n].get(weight, 1)
        #
        # This was a nested `total += ...` running fold with the self-loop
        # addition INTERLEAVED inside the loop. Two separate parity bugs in one
        # expression: CPython's builtins.sum is Neumaier-compensated and a naive
        # fold is not, and folding the self-loop mid-sequence changes the
        # association even when compensation is not in play. On weights
        # [1e16, 1.0, -1e16] networkx returns 1.0 and the fold returned 0.0.
        adj = self._graph.adj[node]
        multi = self._graph.is_multigraph()
        if multi:
            total = sum(
                self._edge_weight(attrs)
                for edge_data in adj.values()
                for attrs in edge_data.values()
            )
        else:
            total = sum(self._edge_weight(edge_data) for edge_data in adj.values())
        if not self._graph.is_directed() and node in adj:
            edge_data = adj[node]
            if multi:
                total += sum(self._edge_weight(attrs) for attrs in edge_data.values())
            else:
                total += self._edge_weight(edge_data)
        return total

    def _in_degree(self, node):
        if not self._graph.is_directed():
            return 0
        fast = self._filtered_set_count(node, reverse=True)
        if fast is not None:
            return fast
        # br-r37-c1-subwdeg: the weighted twin of the probe above.
        fast = self._filtered_set_weight(node, reverse=True)
        if fast is not None:
            return fast
        # br-r37-c1-p6dhq: the predecessor twin. The stored arc runs
        # nbr -> node here, so the key-set endpoints are swapped, exactly as
        # `_edge_visible` swaps them.
        if self._weight is None:
            view = self._graph
            row = view.pred[node]
            key_set = self._fnx_parent_key_set
            total = 0
            for nbr in row:
                if not view.is_multigraph():
                    total += 1
                elif key_set is None:
                    total += len(row[nbr])
                else:
                    total += sum(
                        1
                        for key in key_set(nbr, node)
                        if view._edge_visible(nbr, node, key)
                    )
            return total
        # br-r37-c1-outdegsum: the predecessor twin of the flat sum() above.
        # networkx's in-degree has no self-loop doubling, so this is one sum and
        # nothing else.
        pred = self._graph.pred[node]
        if self._graph.is_multigraph():
            return sum(
                self._edge_weight(attrs)
                for edge_data in pred.values()
                for attrs in edge_data.values()
            )
        return sum(self._edge_weight(edge_data) for edge_data in pred.values())

    def _degree(self, node):
        return self._out_degree(node) + self._in_degree(node)

    def __iter__(self):
        """br-r37-c1-degchain: WHOLE-GRAPH iteration hands the pairs to a
        C-level iterator; an nbunch view keeps the generator.

        A "yield from <list>" resumes this Python frame once PER ELEMENT.
        Measured on plain lists: 4 elements 232.1ns, 64 elements 1259.1ns, 400
        elements 7220.5ns -- against 1745.2ns for handing back iter(list) at
        400. So a whole-graph walk was paying roughly 14ns a node purely to
        pass values through this frame.

        Returning iter(fast) directly is NOT what happens here, and that is
        deliberate: it would run the body at iter() time instead of at the
        first next(), and a probe shows fnx currently MATCHES networkx on an
        assigned-storage graph when a caller holds an iterator across a
        mutation made BEFORE the first next(). Trading a correct behaviour for
        speed is not this change's call to make.

        itertools.chain.from_iterable over a one-shot generator keeps both: the
        generator body -- and therefore the whole snapshot -- still runs at the
        first next(), verified directly, while the per-element walk happens in
        C. Measured 2662.5ns at 400 elements against 7220.5ns.

        It is applied ONLY when self._nodes is None. Chain has setup cost, so
        at 4 elements it is SLOWER (347.3ns against 232.1ns) -- and
        self._nodes is not None is exactly the nbunch case, known here without
        computing anything, so the small case keeps the generator. This method
        is now a plain function that does no work before returning, so both
        branches stay exactly as lazy as they were.
        """
        if self._nodes is None:
            return _chain_from_iterable(self._pairs_once())
        return self._pairs_generator()

    def _pairs_once(self):
        """Yield the whole pair list as ONE item, for chain.from_iterable."""
        yield self._pairs_source()

    def _pairs_generator(self):
        yield from self._pairs_source()

    def _pairs_source(self):
        fast = self._fast_private_degree_pairs()
        if fast is None:
            fast = self._fast_private_weighted_pairs()
        if fast is None:
            fast = self._fast_filtered_degree_pairs()
        if fast is not None:
            return fast
        return [(node, self._degree(node)) for node in self._iter_nodes()]

    def _fast_private_weighted_pairs(self):
        """br-r37-c1-degwt: WEIGHTED degree straight off the RAW mappings.

        Every fast path this campaign added gates on `weight is None`, so the
        weighted walk was the one route still going through `graph.adj` -- the
        wrapping cost `br-r37-c1-ktsxn` removed everywhere else. Profiling 20
        iterations over 400 nodes / 1600 edges counted, for 8,000 node-visits
        and 64,000 edges: **80,040** `AdjacencyView` constructions (ten per
        node), 72,000 `_keydict` + 72,000 `_atlas` + 72,000 generator frames of
        wrapper machinery, and PER EDGE one `_edge_weight` call plus an
        `is_multigraph()` and an `is_directed()` read -- 64,000 and 72,042 of
        them. networkx does `nbrs = self._succ[n]` and one `sum()`.

        THE SUMMATION SHAPE IS COPIED FROM networkx DELIBERATELY, not
        rearranged. `_weighted_value` already records why: CPython's `sum` is
        Neumaier-compensated for floats, so the ASSOCIATION decides the last
        bits. Each class below reproduces its own view's exact expression --
        including nx's `(n in nbrs and nbrs[n].get(weight, 1))`, whose value is
        `False` rather than `0` when the node has no self-loop, and the
        multigraph form's separate `deg +=` for the self-loop group.
        """
        if self._weight is None or self._fast_map is None:
            return None
        nodes = self._nodes
        weight = self._weight
        multi = self._fast_multi
        if self._fast_directed:
            succ = self._fast_map
            pred = self._fast_pred
            items = succ.items() if nodes is None else [(n, succ[n]) for n in nodes]
            if multi:
                return [
                    (
                        node,
                        sum(
                            d.get(weight, 1)
                            for key_dict in succs.values()
                            for d in key_dict.values()
                        )
                        + sum(
                            d.get(weight, 1)
                            for key_dict in pred[node].values()
                            for d in key_dict.values()
                        ),
                    )
                    for node, succs in items
                ]
            return [
                (
                    node,
                    sum(dd.get(weight, 1) for dd in succs.values())
                    + sum(dd.get(weight, 1) for dd in pred[node].values()),
                )
                for node, succs in items
            ]
        adj = self._fast_map
        items = adj.items() if nodes is None else [(n, adj[n]) for n in nodes]
        if multi:
            pairs = []
            for node, nbrs in items:
                deg = sum(
                    d.get(weight, 1)
                    for key_dict in nbrs.values()
                    for d in key_dict.values()
                )
                if node in nbrs:
                    deg += sum(d.get(weight, 1) for d in nbrs[node].values())
                pairs.append((node, deg))
            return pairs
        return [
            (
                node,
                sum(dd.get(weight, 1) for dd in nbrs.values())
                + (node in nbrs and nbrs[node].get(weight, 1)),
            )
            for node, nbrs in items
        ]

    def _fast_private_degree_pairs(self):
        """br-r37-c1-degnbr: bulk UNWEIGHTED degree straight off the RAW
        assigned mappings, for a CONCRETE graph carrying private storage.

        The per-node route spent almost all of its time getting the row rather
        than counting it. `_nodes_authority()` and `_out_degree` both go through
        `graph.adj` / `graph.succ`, and those accessors return a view that wraps
        a fresh row object per subscript: for 400 nodes the `.adj` property cost
        `225.69us` and the subscripts another `194.07us`, against `957.13us` for
        the whole row. Counting off the raw dicts answers the same 400 pairs in
        `34.02us` where networkx takes `32.00us`.

        Deliberately NARROW. A `_FilteredGraphView` is excluded because its
        answer needs the `_node_visible`/`_edge_visible` machinery, and that
        case already has its own bulk path below; a weighted view is excluded
        because it must read attribute dicts; an nbunch is excluded because the
        node set is then the caller's, not the mapping's.

        The DIRECTED branch iterates the SUCCESSOR keys and subscripts the
        predecessor mapping WITHOUT a guard, on purpose: that is where networkx
        raises KeyError for a node an assigned `_succ` carries but `_pred` does
        not, and `br-r37-c1-vbe1o` is the bead recording that fnx used to return
        a plausible number there instead.
        """
        # br-r37-c1-degsnap: the same snapshot the scalar twin reads, so the
        # eligibility rule lives in ONE place. `_fast_map is None` already
        # covers a weighted view and a non-concrete parent.
        # br-r37-c1-degnb: an nbunch view is served HERE now. This used to bail
        # on `self._nodes is not None`, which sent `G.degree(nbunch)` down the
        # fully-wrapped per-node route -- a FOUR-node nbunch built SIXTEEN
        # `AdjacencyView`s per call. networkx's own nbunch view does exactly
        # what the restricted branch below does: its `_nodes` is
        # `list(G.nbunch_iter(nbunch))` and `__iter__` subscripts `_succ[n]` for
        # each one, in that order.
        if self._weight is not None or self._fast_map is None:
            return None
        nodes = self._nodes
        multi = self._fast_multi
        if self._fast_directed:
            succ = self._fast_map
            pred = self._fast_pred
            items = succ.items() if nodes is None else [(n, succ[n]) for n in nodes]
            if multi:
                return [
                    (
                        node,
                        sum(len(kd) for kd in row.values())
                        + sum(len(kd) for kd in pred[node].values()),
                    )
                    for node, row in items
                ]
            return [(node, len(row) + len(pred[node])) for node, row in items]
        adj = self._fast_map
        items = adj.items() if nodes is None else [(n, adj[n]) for n in nodes]
        if multi:
            # An undirected self-loop contributes its parallel-edge count TWICE.
            return [
                (
                    node,
                    sum(len(kd) for kd in row.values())
                    + (len(row[node]) if node in row else 0),
                )
                for node, row in items
            ]
        return [(node, len(row) + (node in row)) for node, row in items]

    def _fast_filtered_degree_pairs(self):
        # cc-rvdegfast: bulk fast path for UNWEIGHTED total degree over an
        # UNDIRECTED simple _FilteredGraphView whose filter shape makes the
        # per-node `_filtered_set_count` bail — a closure filter_node (no `.nodes`
        # set) and/or a non-default filter_edge (e.g. restricted_view). Those walk
        # the filtered `self.adj` per node, paying the per-edge
        # `_node_visible`/`_edge_visible` machinery (~0.04x nx). Compute the visible
        # node set ONCE per iteration (live-safe: recomputed each call, never
        # cached, so a mutated parent stays reflected), then count each visible
        # node's filter_edge-passing visible neighbours off the native parent row,
        # double-counting a self-loop exactly as nx's total degree does. Weighted /
        # directed / multigraph / nbunch / the node-set+default-edge case (already
        # fast via `_filtered_set_count`) keep the per-node path.
        if self._nodes is not None:
            return None
        view = self._graph
        if not isinstance(view, _FilteredGraphView) or type(view._graph) not in (
            Graph,
            DiGraph,
            MultiGraph,
            MultiDiGraph,
        ):
            return None
        weight = self._weight
        edge_default = getattr(view, "_filter_edge_is_default", False)
        keep_is_set = getattr(getattr(view, "_filter_node", None), "nodes", None) is not None
        if weight is None and edge_default and keep_is_set:
            return None  # per-node _filtered_set_count already handles this fast
        parent = view._graph
        # cc-rvdegwt: weighted degree is a float SUM; CPython's builtin `sum` is
        # Neumaier-compensated (3.12+), so a naive `+=` accumulator would diverge by
        # ULPs. Directed weighted total = sum(out) + sum(in) with nx's specific
        # per-direction order — deferred to the slow path (weighted DIRECTED returns
        # None below). Undirected weighted collects the per-edge values in adjacency
        # order and reduces with the builtin `sum`, matching nx bit-for-bit.
        if weight is not None and parent.is_directed():
            return None
        filter_edge = view._filter_edge
        multi = view.is_multigraph()
        order = list(iter(view))  # visible nodes in view order (== _iter_nodes)
        visible = set(order)

        def _pair_count(u, v, keydict):
            # contribution of the u--v edge(s) to u's degree: a simple graph
            # contributes 1 (if the edge passes filter_edge); a multigraph sums the
            # parallel keys that pass filter_edge(u, v, key). Degree is a SUM so key
            # order is irrelevant (no reorder concern, unlike the edges view).
            if multi:
                if edge_default:
                    return len(keydict)
                return sum(1 for key in keydict if filter_edge(u, v, key))
            if edge_default or filter_edge(u, v):
                return 1
            return 0

        if parent.is_directed():
            # Directed total degree = out + in. Credit each visible edge's count to
            # the source (out) and the target (in); a self-loop (u, u) is both a
            # successor and predecessor of u so it lands twice, matching nx. Simple
            # DiGraph: one pass off the hoisted successor snapshot (its per-node
            # `_fast_succ_row` is an O(V) whole-graph rebuild). MultiDiGraph:
            # per-source `_fast_succ_row` is O(deg) (per-row native dict), so use it.
            deg = {n: 0 for n in order}
            if multi:
                for u in order:
                    row = _fast_succ_row(parent, u)
                    for v in row:
                        if v in visible:
                            c = _pair_count(u, v, row[v])
                            deg[u] += c
                            deg[v] += c
            else:
                na_keys = getattr(parent, "_native_adjacency_keys", None)
                if na_keys is None:
                    return None
                succ = dict(na_keys())
                for u in order:
                    for v in succ[u]:
                        if v in visible and (edge_default or filter_edge(u, v)):
                            deg[u] += 1
                            deg[v] += 1
            return list(deg.items())
        pairs = []
        if weight is None:
            for node in order:
                row = _fast_adj_row(parent, node)
                total = 0
                for nbr in row:
                    if nbr not in visible:
                        continue
                    c = _pair_count(node, nbr, row[nbr] if multi else None)
                    total += c
                    if nbr == node:  # undirected degree double-counts a self-loop
                        total += c
                pairs.append((node, total))
            return pairs
        # Weighted undirected: nx computes
        #   deg = sum(dd.get(w,1) for dd in nbrs.values())
        #   if n in nbrs: deg += (self-loop weight, once more)
        # over the FILTERED adjacency (visible + filter_edge-passing), neighbour-
        # major / key-minor order. Collect the values in that order and reduce with
        # the builtin `sum` so the Neumaier compensation matches nx bit-for-bit; add
        # the self-loop's weight a second time (undirected double-count) exactly as
        # nx's trailing `+=` does.
        for node in order:
            row = _fast_adj_row(parent, node)
            vals = []
            selfloop_extra = 0
            for nbr in row:
                if nbr not in visible:
                    continue
                if multi:
                    passing = [
                        attrs.get(weight, 1)
                        for key, attrs in row[nbr].items()
                        if edge_default or filter_edge(node, nbr, key)
                    ]
                    vals.extend(passing)
                    if nbr == node:
                        selfloop_extra = sum(passing)
                else:
                    if edge_default or filter_edge(node, nbr):
                        val = row[nbr].get(weight, 1)
                        vals.append(val)
                        if nbr == node:
                            selfloop_extra = val
            total = sum(vals) + selfloop_extra
            pairs.append((node, total))
        return pairs

    def __len__(self):
        if self._nodes is None:
            # br-r37-c1-vbe1o: nx is len(self._nodes), i.e. len(self._succ).
            return len(self._nodes_authority())
        return len(self._nodes)

    def __getitem__(self, node):
        """br-r37-c1-degframe: the fast path is INLINE here, not delegated.

        This used to call a helper, so a subscript cost TWO Python frames where
        networkx's costs one. Measured over 256 calls on 400 nodes / 1600
        edges: nx `dv[i]` `102.9ns`, fnx `155.9ns`, and the SAME computation
        hand-inlined with no call at all `57.3ns` -- so the whole deficit and
        more besides was frame overhead, at roughly `49ns` a frame. The
        arithmetic was never the problem.

        The body is not duplicated to achieve that: `__call__`'s scalar path
        runs its own membership test -- which it needs anyway to decide whether
        the argument IS a node -- and then delegates HERE, so this remains the
        one place a degree is computed.

        The row subscripts stay unguarded: that is where networkx raises
        KeyError for a missing node and TypeError for an unhashable one, and on
        a directed graph `pred[node]` is where it raises for a node an assigned
        `_succ` carries but `_pred` does not (br-r37-c1-vbe1o).
        """
        succ = self._fast_map
        if succ is not None and self._weight is None:
            if self._fast_directed:
                row = succ[node]
                prow = self._fast_pred[node]
                if self._fast_multi:
                    return sum(len(kd) for kd in row.values()) + sum(
                        len(kd) for kd in prow.values()
                    )
                return len(row) + len(prow)
            row = succ[node]
            if self._fast_multi:
                # An undirected self-loop contributes its parallel-edge count TWICE.
                return sum(len(kd) for kd in row.values()) + (
                    len(row[node]) if node in row else 0
                )
            return len(row) + (node in row)
        # br-r37-c1-dvvme: networkx indexes a dict here, so an unhashable node
        # is its dict-key TypeError ("cannot use 'list' as a dict key"); the
        # slow path's set membership worded it as a set element.
        _HASH_PROBE.get(node)
        return self._degree(node)

    def __call__(self, nbunch=None, weight=None):
        if weight is None:
            weight = self._weight
        if nbunch is None and weight == self._weight:
            return self
        if nbunch is None:
            return self._derive(weight=weight)
        # br-r37-c1-degscalar: answer a scalar node WITHOUT building anything.
        # The route below asks `_nodes_authority()` (an AdjacencyView) for
        # membership and then constructs a whole second degree view just to
        # subscript it once. Both are skipped when the raw mapping can answer;
        # if it cannot, the original route runs unchanged.
        if weight is None and self._weight is None:
            adj = self._fast_map
            if adj is not None:
                # br-r37-c1-degframe: the membership test this path needs anyway
                # doubles as the eligibility check, and __getitem__ does the
                # arithmetic. A miss is NOT an error here -- it falls through to
                # the nbunch rules below -- which is why the test comes first
                # rather than letting the subscript raise. On a directed graph
                # only the SUCCESSOR mapping is probed, so a ragged `_pred`
                # still raises from __getitem__, as networkx does.
                try:
                    present = nbunch in adj
                except TypeError:
                    present = False
                if present:
                    return self[nbunch]
        # br-r37-c1-vbe1o: the MAPPING decides whether a single argument is a
        # node, exactly as in nx's `nbunch in self._nodes`. Asking the node view
        # returned a whole DegreeView where nx returns an int — a RETURN-TYPE
        # divergence, so a caller doing arithmetic on it got a TypeError rather
        # than a wrong number.
        # br-r37-c1-degnb: filter against the RAW mapping when one is available.
        # `_nodes_authority()` returns `graph.succ` / `graph.adj`, so the
        # membership test below was building an `AdjacencyView` and probing it
        # per node. The raw dict answers the identical question.
        authority = self._fast_map
        if authority is None:
            authority = self._nodes_authority()
        try:
            if nbunch in authority:
                return self._derive(weight=weight)[nbunch]
        except TypeError:
            pass
        # br-r37-c1-vbe1o: nx builds this list as `list(G.nbunch_iter(nbunch))`,
        # and nbunch_iter has TWO rules, not one:
        #
        #   * a SINGLE node -- `nbunch in self`, the node view -- yields [nbunch];
        #   * anything else is filtered by `n in self._adj`, the ADJACENCY.
        #
        # Both are reproduced here rather than delegating to fnx's own
        # `nbunch_iter`, which filters the second case on the node view instead
        # of the adjacency. Delegating imported that divergence: `G.degree(['ZZ'])`
        # started raising KeyError where nx returns {}. Fixing nbunch_iter itself
        # is the better repair and is tracked separately -- it is a hot path, and
        # this class is not.
        #
        # The single-node rule is what the plain `for node in nbunch` was missing:
        # it split a STRING argument into characters, so `G.degree('ZZ')` gave an
        # empty view where nx gives a view over ['ZZ'] that raises on lookup.
        # br-r37-c1-degderive: settle the common containers by exact type first.
        # The pair below costs 61.1ns + 52.1ns; the frozenset test costs 48.9ns
        # and answers for list/tuple/set/frozenset, which is what an nbunch
        # almost always is. Anything else -- a str, an int, a generator, a
        # range, a subclass -- falls through to the original test unchanged.
        if type(nbunch) in _PLAIN_NBUNCH_CONTAINERS:
            nodes = [node for node in nbunch if node in authority]
        elif isinstance(nbunch, (str, bytes)):
            nodes = [nbunch] if nbunch in self._graph else []
        elif not hasattr(nbunch, "__iter__"):
            # br-r37-c1-dvvme: networkx builds the view's node list eagerly,
            # list(G.nbunch_iter(nbunch)), so a single node the graph lacks
            # raises NetworkXError('Node 9 is not in the graph.') at the call;
            # an empty view came back instead.
            nodes = [nbunch] if nbunch in self._graph else list(self._graph.nbunch_iter(nbunch))
        else:
            nodes = [node for node in nbunch if node in authority]
        return self._derive(nodes=nodes, weight=weight)

    def __repr__(self):
        # br-r37-c1-snvrepr: nx's subgraph DegreeView /
        # DiDegreeView / MultiDegreeView / DiMultiDegreeView repr
        # as ``<ClassName>({node: degree, ...})``. fnx had no
        # __repr__ here, falling through to default
        # ``<...object at 0x...>``. Use ``type(self).__name__`` so
        # the subclasses below pick up the right canonical name.
        return f"{type(self).__name__}({dict(self)!r})"

    def __str__(self):
        # br-r37-c1-dvvme: networkx's DegreeView prints the list; with no
        # __str__ here str() fell back to the repr.
        return str(list(self))


# br-r37-c1-snvrepr: 4 trivial subclasses with canonical nx
# ``__name__`` so subgraph .degree dispatch (above) picks the
# right per-class name.
class _AssignedDegreeView(_AssignedPrivateDegreeView):
    pass
_AssignedDegreeView.__name__ = "DegreeView"


class _AssignedDiDegreeView(_AssignedPrivateDegreeView):
    pass
_AssignedDiDegreeView.__name__ = "DiDegreeView"


class _AssignedMultiDegreeView(_AssignedPrivateDegreeView):
    pass
_AssignedMultiDegreeView.__name__ = "MultiDegreeView"


class _AssignedDiMultiDegreeView(_AssignedPrivateDegreeView):
    pass
_AssignedDiMultiDegreeView.__name__ = "DiMultiDegreeView"


# br-r37-c1-l7ww9: there is deliberately no `_private_aware_iter` here either.
# The native `__iter__` iterates the assigned `_node` mapping itself when one is
# installed, behind the same bool as `__len__` and `__contains__`.


# br-r37-c1-l7ww9: there is deliberately no `_private_aware_len` here. The
# native `__len__` consults the assigned `_node` mapping itself, behind the same
# `private_node_override` bool `__contains__` already uses, so an ordinary graph
# pays one bool test instead of two Python frames (the wrapper, plus the
# `_private_override` helper it called). `len(G)` is the cheapest operation the
# library has, and networkx's own `__len__` is itself a Python method returning
# `len(self._node)` — losing that race 2x was the wrapper, not the store.


def _private_aware_contains(raw_contains):
    # br-r37-c1-mi31t: ``n in G`` is the only node-membership spelling that
    # cannot escape this probe. ``has_node`` is bound straight to the raw native
    # slot and a graph that gains NetworkX private storage gets a per-INSTANCE
    # method shadow instead; a dunder is looked up on the TYPE, so every graph
    # pays this wrapper on every call. Measured 2026-08-04, 1200-node graph, 512
    # present string keys: nx 63.4 ns, fnx ``n in G`` 236.8 ns, fnx
    # ``G.has_node(n)`` 98.5 ns — the native lookup is identical code in both, so
    # the whole 138.3 ns gap was this probe. It is also 91% of the published
    # preferential_attachment loss, because both nx's ``_apply_prediction`` and
    # our ``_link_prediction_validate_ebunch`` membership-test each endpoint.
    #
    # So the probe is written as cheaply as Python allows: the key and the
    # sentinel are closure cells rather than module globals, ``self.__dict__``
    # replaces the ``vars()`` builtin call, and the ``_private_override`` helper
    # is inlined so an ordinary graph pays no extra interpreter frame.
    missing = _PRIVATE_MISSING
    override_key = _PRIVATE_NODE_OVERRIDE

    def __contains__(self, node):
        node_mapping = self.__dict__.get(override_key, missing)
        if node_mapping is not missing:
            try:
                return node in node_mapping
            except TypeError:
                return False
        return raw_contains(self, node)

    return __contains__


def _private_aware_nodes(raw_nodes):
    def nodes(self):
        cache = vars(self)
        owner = _shared_unsplit_owner(self, cache)
        if owner is not None:
            view = cache.get("_fnx_view_nodes")
            if view is None:
                view = raw_nodes.__get__(owner, type(owner))
                cache["_fnx_view_nodes"] = view
            return view
        if _PRIVATE_NODE_OVERRIDE in cache or _SHARED_STORAGE_SOURCE in cache:
            view = cache.get("_fnx_view_nodes_assigned")
            if view is None:
                view = _AssignedPrivateNodeView(self)
                cache["_fnx_view_nodes_assigned"] = view
            return view
        # br-r37-c1-b3cnf: cache the raw NodeView wrapper so
        # ``g.nodes is g.nodes`` matches nx's @cached_property identity.
        view = cache.get("_fnx_view_nodes")
        if view is None:
            view = raw_nodes.__get__(self, type(self))
            cache["_fnx_view_nodes"] = view
        return view

    # br-r37-c1-wbwkb: nx's cached_property mechanism — see _CachedViewDescriptor.
    return _CachedViewDescriptor(nodes, "nodes", "_fnx_view_nodes_assigned")


def _private_aware_edges(raw_edges):
    def edges(self):
        # br-r37-c1-b3cnf follow-up: cache wrapper for both branches
        # (private storage / regular). Both should return the same
        # instance on repeat access per nx's @cached_property contract.
        cache = vars(self)
        owner = _shared_unsplit_owner(self, cache)
        if owner is not None:
            view = cache.get("_fnx_view_edges")
            if view is None:
                view = raw_edges.__get__(owner, type(owner))
                cache["_fnx_view_edges"] = view
            try:
                _EDGE_VIEW_GRAPH_OWNER[id(view)] = owner
            except TypeError:
                pass
            return view
        if _has_networkx_private_storage(self):
            view = cache.get("_fnx_view_edges_assigned")
            if view is None:
                # br-r37-c1-jqytt: the subclass carrying nx's name for this
                # graph kind, not the shared base.
                view = _assigned_private_edge_view(self)
                cache["_fnx_view_edges_assigned"] = view
            return view
        # br-r37-c1-b3cnf: cache the raw EdgeView wrapper so
        # ``g.edges is g.edges`` matches nx's @cached_property identity.
        view = cache.get("_fnx_view_edges")
        if view is None:
            view = raw_edges.__get__(self, type(self))
            cache["_fnx_view_edges"] = view
        # br-r37-c1-dc14n: register the graph in the per-process
        # weakref map so EdgeDataView (created lazily when the user
        # calls view(nbunch=...)) can recover the owning graph and
        # iterate adj in nx-matching order. Keyed by id(view); the
        # entry is overwritten each access.
        try:
            _EDGE_VIEW_GRAPH_OWNER[id(view)] = self
        except TypeError:
            # If the view is unhashable for some reason, fall through —
            # EdgeDataView will skip the adj-walk and return raw output.
            pass
        return view

    # br-r37-c1-wbwkb: nx's cached_property mechanism — see _CachedViewDescriptor.
    # The ``_EDGE_VIEW_GRAPH_OWNER`` registration above now runs once per view
    # instead of once per access; the entry is keyed by ``id(view)`` and holds a
    # weak ref to the graph, and a memoised view lives exactly as long as the
    # graph it is stored on, so the mapping is unchanged.
    return _CachedViewDescriptor(edges, "edges", "_fnx_view_edges_assigned")


# id(EdgeView) -> owning Graph. br-r37-c1-cxglk: WeakValueDictionary
# so the entry auto-prunes when the Graph is garbage-collected,
# preventing both (a) unbounded memory growth (every G.edges access
# previously appended-or-overwrote a permanent entry) and (b) silent
# id-collision correctness bugs where a recycled id() returned a
# stale Graph from a long-dead EdgeView. Used by
# EdgeDataView._materialize_via_adj_walk (br-r37-c1-dc14n).
_EDGE_VIEW_GRAPH_OWNER: "_weakref.WeakValueDictionary[int, object]" = (
    _weakref.WeakValueDictionary()
)


def _private_aware_degree(raw_degree):
    def degree(self):
        cache = vars(self)
        owner = _shared_unsplit_owner(self, cache)
        if owner is not None:
            view = cache.get("_fnx_view_degree")
            if view is None:
                view = raw_degree.__get__(owner, type(owner))
                cache["_fnx_view_degree"] = view
            return view
        if _has_networkx_private_storage(self):
            # br-r37-c1-degprop: cache the ASSIGNED view too. `nodes` and
            # `edges` already cache theirs (`_fnx_view_nodes_assigned`,
            # `_fnx_view_edges_assigned`) under the br-r37-c1-b3cnf
            # cached_property contract; `degree` got the cache on its ORDINARY
            # branch only, so a graph with private storage rebuilt a whole
            # degree view on EVERY `G.degree` access. Measured 256 accesses at
            # `97.04us` against networkx's `4.42us` -- `0.0456x` for the bare
            # accessor, and 41% of the scalar `G.degree(n)` row.
            #
            # Safe to cache: the assigned views resolve NOTHING in `__init__`
            # (they hold only the graph and read the override live on each
            # call), which is what makes them unlike the native-counter views
            # br-r37-c1-2r06n had to drop. The drop is added there anyway, so a
            # reassignment always rebuilds.
            view = cache.get("_fnx_view_degree_assigned")
            if view is not None:
                return view
            # br-r37-c1-snvrepr: dispatch to canonical-named subclass
            # so ``type(view).__name__`` matches nx's per-graph-class
            # form (DegreeView/DiDegreeView/MultiDegreeView/
            # DiMultiDegreeView).
            directed = self.is_directed()
            multi = self.is_multigraph()
            if multi and directed:
                cls = _AssignedDiMultiDegreeView
            elif multi:
                cls = _AssignedMultiDegreeView
            elif directed:
                cls = _AssignedDiDegreeView
            else:
                cls = _AssignedDegreeView
            view = cls(self)
            cache["_fnx_view_degree_assigned"] = view
            return view
        # br-r37-c1-b3cnf follow-up: cache the DegreeView wrapper so
        # ``g.degree is g.degree`` matches nx's @cached_property.
        view = cache.get("_fnx_view_degree")
        if view is None:
            view = raw_degree.__get__(self, type(self))
            cache["_fnx_view_degree"] = view
        return view

    # br-r37-c1-wbwkb: nx's cached_property mechanism — see _CachedViewDescriptor.
    return _CachedViewDescriptor(degree, "degree", "_fnx_view_degree_assigned")


def _private_aware_has_node(raw_has_node):
    def has_node(self, n):
        # Parameter named ``n`` to match networkx (br-r37-c1-classmethsig).
        # Drop-in callers writing ``G.has_node(n=x)`` would have hit
        # TypeError under fnx's earlier ``node`` name.
        storage = self.__dict__
        if _PRIVATE_NODE_OVERRIDE in storage or _SHARED_STORAGE_SOURCE in storage:
            return n in self
        return raw_has_node(self, n)

    return has_node


def _private_aware_has_edge_simple(raw_has_edge):
    """has_edge wrapper for non-multigraph types — nx signature is (u, v).

    br-r37-c1-vbe1o: DEAD — this factory is defined and never called. The live
    private-storage path is the instance shadow `_assigned_private_has_edge_simple`
    near the top of the private-storage section. Editing THIS one is a silent
    no-op; it cost me a cycle before a sweep showed the divergence count
    unchanged. Kept only so the name resolves for anything that greps for it;
    it should be deleted once someone confirms no external caller binds it.
    """
    def has_edge(self, u, v):
        # br-r37-c1-hashed-he: nx's has_edge propagates ``TypeError:
        # unhashable type: 'X'`` on unhashable u or v (the underlying
        # ``self._adj[u]`` dict lookup raises).  fnx's Rust binding
        # silently caught the error and returned False, masking
        # caller bugs.  Hash-check eagerly to restore nx's contract.
        _HASH_PROBE.get(u)
        _HASH_PROBE.get(v)
        if not _has_networkx_private_storage(self):
            return raw_has_edge(self, u, v)
        if u not in self:
            return False
        try:
            neighbors = self.adj[u]
        except KeyError:
            return False
        return v in neighbors

    return has_edge


def _private_aware_has_edge_multi(raw_has_edge):
    """has_edge wrapper for multigraph types — nx signature is (u, v, key=None)."""
    def has_edge(self, u, v, key=None):
        # br-r37-c1-hashed-he: same as the simple variant — nx
        # raises TypeError on unhashable u/v; fnx silently
        # returned False.  Hash-check first.
        _HASH_PROBE.get(u)
        _HASH_PROBE.get(v)
        # br-r37-c1-mhe-keyhash: extend the hash-check to the
        # multigraph ``key`` arg.  nx propagates ``TypeError:
        # unhashable type: '<X>'`` from the inner ``key in
        # neighbors[v]`` dict lookup; fnx's Rust binding caught
        # the error and silently returned False, masking caller
        # bugs (sister of br-r37-c1-cl78j add_edge fix that
        # closed the corresponding mutation-side variant).
        if key is not None:
            _HASH_PROBE.get(key)
        if not _has_networkx_private_storage(self):
            if key is None:
                return raw_has_edge(self, u, v)
            return raw_has_edge(self, u, v, key)
        if u not in self:
            return False
        try:
            neighbors = self.adj[u]
        except KeyError:
            return False
        if v not in neighbors:
            return False
        if key is not None:
            return key in neighbors[v]
        return True

    return has_edge
