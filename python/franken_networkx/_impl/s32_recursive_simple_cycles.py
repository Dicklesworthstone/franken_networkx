

def recursive_simple_cycles(G):
    """Find all simple cycles using recursive DFS.

    br-r37-c1-spyv7: networkx's Johnson recursion, not simple_cycles. Its
    cycles come grouped by their least node in G's INSERTION order, each
    starting there, in DFS order over G's successor order; simple_cycles
    follows hash order, which for str nodes differs from networkx and
    between processes. Like networkx (mutates_input=True) it removes one
    selfloop per node from G, recording [v] for each. The subgraph per start
    node is a successor dict filtered by rank: the strongly connected
    component of s among the nodes ranked at or after it is what networkx's
    min-over-components picks, and forward-and-backward reachability finds it.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    def _unblock(thisnode):
        if blocked[thisnode]:
            blocked[thisnode] = False
            while B[thisnode]:
                _unblock(B[thisnode].pop())

    def circuit(thisnode, startnode, component):
        closed = False
        path.append(thisnode)
        blocked[thisnode] = True
        for nextnode in component[thisnode]:
            if nextnode == startnode:
                result.append(path[:])
                closed = True
            elif not blocked[nextnode]:
                if circuit(nextnode, startnode, component):
                    closed = True
        if closed:
            _unblock(thisnode)
        else:
            for nextnode in component[thisnode]:
                if thisnode not in B[nextnode]:
                    B[nextnode].append(thisnode)
        path.pop()
        return closed

    def _reach(source, adjacency, rank):
        seen = {source}
        stack = [source]
        while stack:
            for nbr in adjacency[stack.pop()]:
                if nbr not in seen and ordering[nbr] >= rank:
                    seen.add(nbr)
                    stack.append(nbr)
        return seen

    path = []
    blocked = _defaultdict(bool)
    B = _defaultdict(list)
    result = []
    for v in list(G):
        if G.has_edge(v, v):
            result.append([v])
            G.remove_edge(v, v)

    ordering = {node: rank for rank, node in enumerate(G)}
    succ = {u: list(nbrs) for u, nbrs in G.adj.items()}
    pred = {u: [] for u in succ}
    for u, nbrs in succ.items():
        for v in nbrs:
            pred[v].append(u)
    for s, rank in ordering.items():
        comp = _reach(s, succ, rank) & _reach(s, pred, rank)
        if len(comp) > 1:
            component = {u: [v for v in succ[u] if v in comp] for u in comp}
            for node in comp:
                blocked[node] = False
                B[node][:] = []
            circuit(s, s, component)
    return result


# ---------------------------------------------------------------------------
# Utility Extras B (br-i1d)
# ---------------------------------------------------------------------------


def remove_node_attributes(G, *attr_names, nbunch=None):
    """Remove the given attribute names from nodes in *nbunch* (default all).

    Matches networkx's public signature
    ``remove_node_attributes(G, *attr_names, nbunch=None)``.
    """
    if not attr_names:
        # Treat absence as no-op (matches nx silently doing nothing).
        return
    target_nodes = G.nodes() if nbunch is None else [n for n in nbunch if n in G]
    for node in target_nodes:
        attrs = G.nodes[node] if hasattr(G.nodes, "__getitem__") else {}
        if not isinstance(attrs, dict):
            continue
        for name in attr_names:
            if name in attrs:
                del attrs[name]


def remove_edge_attributes(G, *attr_names, ebunch=None):
    """Remove the given attribute names from edges in *ebunch* (default all).

    Matches networkx's public signature
    ``remove_edge_attributes(G, *attr_names, ebunch=None)``.
    """
    if not attr_names:
        return
    if ebunch is None:
        edge_iter = list(G.edges(keys=True) if G.is_multigraph() else G.edges())
    else:
        edge_iter = list(ebunch)
    for edge in edge_iter:
        if G.is_multigraph() and len(edge) == 3:
            u, v, k = edge
            if G.has_edge(u, v, k):
                data = G[u][v][k]
            else:
                continue
        else:
            u, v = edge[0], edge[1]
            if G.has_edge(u, v):
                data = G[u][v]
                if G.is_multigraph():
                    # No key provided on MG — nx strips across all parallel edges.
                    for k in list(data.keys()):
                        d = data[k]
                        if isinstance(d, dict):
                            for name in attr_names:
                                d.pop(name, None)
                    continue
            else:
                continue
        if isinstance(data, dict):
            for name in attr_names:
                data.pop(name, None)


def floyd_warshall_numpy(G, nodelist=None, weight="weight"):
    """Floyd-Warshall via numpy matrix operations."""
    import numpy as np

    # br-r37-c1-fwdense: native in-place SIMD min-plus Floyd-Warshall for the
    # common case (simple Graph/DiGraph, default nodelist). Replaces numpy's
    # broadcast FW (`for k: A = minimum(A, A[:,k:k+1] + A[k:k+1,:])`), which
    # allocates n temporary n*n arrays, with a zero-temp cache-friendly kernel
    # that also builds the matrix natively (no AtlasView walk). Bit-identical
    # output. Gated on exact type so subclasses / SubgraphViews fall back.
    if nodelist is None and type(G) in (Graph, DiGraph) and isinstance(weight, str):
        try:
            from franken_networkx._fnx import floyd_warshall_dense as _fw_dense
        except ImportError:
            _fw_dense = None
        if _fw_dense is not None:
            res = _fw_dense(G, weight)
            if res is not None:
                n, flat = res
                return np.asarray(flat, dtype=float).reshape(n, n)

    if nodelist is not None:
        if not (len(nodelist) == len(G) == len(set(nodelist))):
            raise NetworkXError(
                "nodelist must contain every node in G with no repeats."
                "If you wanted a subgraph of G use G.subgraph(nodelist)"
            )
    else:
        nodelist = list(G.nodes())
    n = len(nodelist)
    # Initialize missing edges as +inf via the nonedge sentinel so that
    # weight-0 and negative-weight edges are handled correctly. The
    # previous `if A[i,j] != 0` gate skipped any edge with weight 0
    # (leaving dist[i,j] = inf) and silently dropped paths through them.
    # multigraph_weight=min, as networkx builds it: parallel edges contribute
    # the lightest one, not their sum (br-r37-c1-545ld).
    A = to_numpy_array(
        G, nodelist=nodelist, weight=weight, nonedge=np.inf, multigraph_weight=min
    )
    dist = np.array(A, dtype=float)
    np.fill_diagonal(dist, 0)
    for k in range(n):
        dist = np.minimum(dist, dist[:, k : k + 1] + dist[k : k + 1, :])
    return dist


def harmonic_diameter(G, sp=None, *, weight=None):
    """Harmonic diameter: n*(n-1) / sum(1/d(u,v)) for all connected pairs."""
    G = _coerce_arg_to_fnx_graph(G)
    order = G.order()
    sum_invd = 0.0
    for n in G:
        if sp is None:
            length = single_source_dijkstra_path_length(G, n, weight=weight)
        else:
            try:
                length = sp[n]
                _ = len(length)
            except TypeError as err:
                raise NetworkXError('Format of "sp" is invalid.') from err

        for d in length.values():
            if d != 0:
                sum_invd += 1.0 / d

    if sum_invd != 0:
        return order * (order - 1) / sum_invd
    if order > 1:
        return _math.inf
    return _math.nan


def _global_parameters_from_graph(G):
    """Private helper: return raw (b, c) arrays from the Rust distance-
    regular solver, or ``None`` when the graph is not distance-regular.
    """
    return _fnx.global_parameters_rust(G)


def global_parameters(b, c):
    """Iterate (c_i, a_i, b_i) global-parameter triples for an
    intersection array (b, c).

    Matches NetworkX's public signature:
    ``global_parameters(b: list, c: list) -> _Iterable[tuple[int, int, int]]``.
    For a distance-regular graph with diameter d, the intersection array
    is ``[b_0, ..., b_{d-1}]`` and ``[c_1, ..., c_d]``; the yielded
    triples are ``(c_i, a_i, b_i)`` where ``a_i = b_0 - b_i - c_i``.
    """
    return ((y, b[0] - x - y, x) for x, y in zip(list(b) + [0], [0] + list(c)))


def intersection_array(G):
    """Return the intersection array of a distance-regular graph.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph').
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    params = _global_parameters_from_graph(G)
    if params is None:
        # br-r37-c1-64xcg: networkx raises three ways - "... regular." when G is
        # not regular or not connected or its diameter outgrows (8 log2 n) / 3,
        # "... regular" (no period) when an intersection number disagrees -
        # whichever its pair loop meets first; its loop, verbatim, decides.
        return _intersection_array_networkx_loop(G)
    b, c = params
    return (b[:-1], c[1:])


def _intersection_array_networkx_loop(G):
    """networkx's intersection_array body, for the graphs the native solver rejects."""
    from collections import defaultdict
    from itertools import combinations_with_replacement

    if not is_regular(G) or not is_connected(G):
        raise NetworkXError("Graph is not distance regular.")
    path_length = defaultdict(dict)
    bint = {}
    cint = {}
    diam = 0
    max_diameter_for_dr_graphs = (8 * _math.log(len(G), 2)) / 3
    for u, v in combinations_with_replacement(G, 2):
        pl_u = path_length[u]
        if v not in pl_u:
            pl_u.update(single_source_shortest_path_length(G, u))
            for x, distance in pl_u.items():
                path_length[x][u] = distance
        i = path_length[u][v]
        diam = max(diam, i)
        if diam > max_diameter_for_dr_graphs:
            raise NetworkXError("Graph is not distance regular.")
        vnbrs = G[v]
        for n in vnbrs:
            pl_n = path_length[n]
            if u not in pl_n:
                pl_n.update(single_source_shortest_path_length(G, n))
                for x, distance in pl_n.items():
                    path_length[x][n] = distance
        c = sum(1 for n in vnbrs if pl_u[n] == i - 1)
        b = sum(1 for n in vnbrs if pl_u[n] == i + 1)
        if cint.get(i, c) != c or bint.get(i, b) != b:
            raise NetworkXError("Graph is not distance regular")
        bint[i] = b
        cint[i] = c
    return (
        [bint.get(j, 0) for j in range(diam)],
        [cint.get(j + 1, 0) for j in range(diam)],
    )


# ---------------------------------------------------------------------------
# Small Utilities (br-2zl)
# ---------------------------------------------------------------------------


def eulerize(G, *, backend=None, **backend_kwargs):
    """Add minimum edges to make G Eulerian. Returns copy with added edges.

    Finds odd-degree nodes, computes shortest paths between all pairs of them,
    finds minimum weight matching, and duplicates matched-path edges.
    """
    _validate_backend_dispatch_keywords("eulerize", backend, backend_kwargs)
    from itertools import combinations as _combinations

    # br-r37-c1-96xkv: directed guard runs before the empty/connected
    # check so an empty/length<2 directed graph raises the nx-shaped
    # NetworkXNotImplemented (matches @not_implemented_for ordering).
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Cannot Eulerize null graph")
    if not is_connected(G):
        raise NetworkXError("G is not connected")

    odd_nodes = [v for v, d in G.degree() if d % 2 == 1]
    H = MultiGraph(G)
    if not odd_nodes:
        return H

    # br-r37-c1-dogni: networkx's algorithm, verbatim. Unweighted shortest
    # paths between odd-degree nodes (br-r37-c1-53kq4: hop counts only), taken
    # on the multigraph copy; a MAXIMUM weight matching on weights
    # len(G) + 1 - len(path) (the old min_weight_matching on path lengths chose
    # other paths on ties); and each matched path duplicated with
    # add_edges_from(pairwise(path)) - new parallel edges carrying no data (the
    # old loop copied the original edge's attributes onto them).
    upper_bound = len(H) + 1
    paths_graph = Graph()
    for source, target in _combinations(odd_nodes, 2):
        path = shortest_path(H, source=source, target=target)
        paths_graph.add_edge(target, source, weight=upper_bound - len(path), path=path)
    best_matching = Graph(list(max_weight_matching(paths_graph)))
    for u, v in best_matching.edges():
        path = paths_graph[u][v]["path"]
        H.add_edges_from(zip(path, path[1:]))
    return H


def moral_graph(G):
    """Return the moral graph of a DAG (marry co-parents, drop directions).

    For each node, connect all pairs of its predecessors (marry co-parents),
    then return the undirected version.

    br-r37-c1-n7rgh: nx is @not_implemented_for('undirected'); pre-fix
    fnx fell through to G.predecessors() which raises AttributeError
    on undirected. Add the explicit type guard.
    """
    from itertools import combinations as _combinations

    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    # br-r37-c1-f5h1g: networkx's algorithm - H = G.to_undirected(), so a
    # MultiDiGraph gives a MultiGraph (whose add_edges_from ADDS a parallel edge
    # for a co-parent pair already joined) and G.graph is copied, then each
    # node's predecessors are married in G.pred order. One add_edges_from over
    # every node's pairs, in that order, adds what nx's per-node calls add. On
    # a simple H re-adding an existing pair is a data-less update - a no-op
    # that keeps adjacency order - so only the new pairs are passed on.
    H = G.to_undirected()
    pairs = [pair for preds in G.pred.values() for pair in _combinations(preds, 2)]
    if not H.is_multigraph():
        pairs = [(u, v) for u, v in pairs if not H.has_edge(u, v)]
    H.add_edges_from(pairs)

    return H


def equivalence_classes(iterable, relation):
    """Partition elements by an equivalence relation.

    br-r37-c1-8hshk: nx returns a ``set`` of frozensets (iterating in
    hash order); the local implementation returned a ``list`` of
    frozensets in input order. Drop-in code expecting the set return
    type or hash-based iteration broke. Match nx exactly.
    """
    elements = list(iterable)
    blocks = []
    for y in elements:
        for block in blocks:
            x = next(iter(block))
            if relation(x, y):
                block.add(y)
                break
        else:
            blocks.append({y})
    return {frozenset(block) for block in blocks}


def _node_order_key_local(node):
    return (type(node).__module__, type(node).__qualname__, repr(node))


def minimum_cycle_basis(G, weight=None, *, backend=None, **backend_kwargs):
    """Find a minimum weight cycle basis without requiring SciPy.

    Python arithmetic preserves exact integer, Fraction, and Decimal weights.
    Optional native and SciPy acceleration is restricted to nonnegative
    integer weights whose lifted path sums are exactly representable in f64.
    """
    _validate_backend_dispatch_keywords("minimum_cycle_basis", backend, backend_kwargs)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    from franken_networkx._minimum_cycle_basis import (
        minimum_cycle_basis as _minimum_cycle_basis_owned,
    )

    return _minimum_cycle_basis_owned(G, weight)


def chordless_cycles(G, length_bound=None, *, backend=None, **backend_kwargs):
    """Find all chordless (induced) cycles."""
    _validate_backend_dispatch_keywords("chordless_cycles", backend, backend_kwargs)
    return _chordless_cycles_via_parity(G, length_bound=length_bound)


class _ChordlessNeighborhoodCache(dict):
    def __init__(self, G):
        self.G = G

    def __missing__(self, v):
        Gv = self[v] = list(self.G[v])
        return Gv


def _chordless_cycle_search(F, B, path, length_bound):
    blocked = _defaultdict(int)
    target = path[0]
    blocked[path[1]] = 1
    for w in path[1:]:
        for v in B[w]:
            blocked[v] += 1

    stack = [iter(F[path[2]])]
    while stack:
        nbrs = stack[-1]
        for w in nbrs:
            if blocked[w] == 1 and (length_bound is None or len(path) < length_bound):
                Fw = F[w]
                if target in Fw:
                    yield path + [w]
                else:
                    Bw = B[w]
                    if target in Bw:
                        continue
                    for v in Bw:
                        blocked[v] += 1
                    path.append(w)
                    stack.append(iter(Fw))
                    break
        else:
            stack.pop()
            for v in B[path.pop()]:
                blocked[v] -= 1


def _chordless_cycles_via_parity(G, *, length_bound=None):
    """In-process chordless cycle enumeration."""
    G = _coerce_arg_to_fnx_graph(G)
    if length_bound is not None:
        if length_bound == 0:
            return
        elif length_bound < 0:
            raise ValueError("length bound must be non-negative")

    directed = G.is_directed()
    multigraph = G.is_multigraph()

    if multigraph:
        yield from ([v] for v, Gv in G.adj.items() if len(Gv.get(v, ())) == 1)
    else:
        yield from ([v] for v, Gv in G.adj.items() if v in Gv)

    if length_bound is not None and length_bound == 1:
        return

    loops = set(nodes_with_selfloops(G))
    edges = ((u, v) for u in G if u not in loops for v in G._adj[u] if v not in loops)
    if directed:
        F = DiGraph(edges)
        B = F.to_undirected(as_view=False)
    else:
        F = Graph(edges)
        B = None

    if multigraph:
        if not directed:
            B = F.copy()
            visited = set()
        for u, Gu in G.adj.items():
            if u in loops:
                continue
            if directed:
                multiplicity = ((v, len(Guv)) for v, Guv in Gu.items())
                for v, m in multiplicity:
                    if m > 1:
                        F.remove_edges_from(((u, v), (v, u)))
            else:
                multiplicity = ((v, len(Guv)) for v, Guv in Gu.items() if v in visited)
                for v, m in multiplicity:
                    if m == 2:
                        yield [u, v]
                    if m > 1:
                        F.remove_edge(u, v)
                visited.add(u)

    if directed:
        for u, Fu in list(F.adj.items()):
            digons = [[u, v] for v in Fu if F.has_edge(v, u)]
            yield from digons
            F.remove_edges_from(digons)
            F.remove_edges_from(e[::-1] for e in digons)

    if length_bound is not None and length_bound == 2:
        return

    if directed:
        separate = strongly_connected_components

        def stems(C, v):
            for u, w in _itertools.product(C.pred[v], C.succ[v]):
                if not G.has_edge(u, w):
                    yield [u, v, w], F.has_edge(w, u)
    else:
        separate = biconnected_components

        def stems(C, v):
            yield from (
                ([u, v, w], F.has_edge(w, u)) for u, w in _itertools.combinations(C[v], 2)
            )

    components = [c for c in separate(F) if len(c) > 2]
    while components:
        c = components.pop()
        v = next(iter(c))
        Fc = F.subgraph(c)
        Fcc = Bcc = None
        for S, is_triangle in stems(Fc, v):
            if is_triangle:
                yield S
            else:
                if Fcc is None:
                    Fcc = _ChordlessNeighborhoodCache(Fc)
                    Bcc = Fcc if B is None else _ChordlessNeighborhoodCache(B.subgraph(c))
                yield from _chordless_cycle_search(Fcc, Bcc, S, length_bound)

        components.extend(c for c in separate(F.subgraph(c - {v})) if len(c) > 2)


def to_undirected(graph):
    """Return a frozen live undirected view of *graph*.

    Parameter renamed from ``G`` to ``graph`` to match networkx's public
    signature ``to_undirected(graph)``.
    """
    return _generic_undirected_graph_view(graph)


def to_directed(graph):
    """Return a frozen live directed view of *graph*.

    Parameter renamed from ``G`` to ``graph`` to match networkx's public
    signature ``to_directed(graph)``.
    """
    return _generic_directed_graph_view(graph)


def _new_empty_graph_for_view_class(cls):
    """br-r37-c1-ndro1: what ``type(view)()`` makes - a fresh, empty,
    unfrozen graph of the view class's concrete class. networkx's view
    classes ARE the graph classes (generic_graph_view builds
    ``G.__class__()`` and freezes it), so relabel_nodes, the
    maximum-branching, spanning-tree and union rebuilds, intersection_all,
    a conversion view's attribute probe and user code build their output
    that way; fnx's view classes need their backing graph and raised
    TypeError. Called from the view mixins' ``__new__`` with no arguments:
    returning a non-instance of ``cls`` skips ``__init__``. Only from the
    ``__new__`` the call resolved to (``cls.__new__ is`` that mixin's): a
    filtered view over a reverse view is one class with both mixins, and the
    first one's ``super().__new__(cls)`` reaches the second with no
    arguments."""
    for base in cls.__mro__:
        if base in _CONCRETE_FNX_GRAPH_TYPES:
            return base()
    raise TypeError(f"{cls.__name__} needs the graph it views")


def _view_bool(view):
    """br-r37-c1-77tw1: a view is true when it has a node, as networkx's
    (whose graphs have no __bool__: ``bool(G)`` is ``len(G) > 0``). The view
    classes inherited the PyO3 graph class's native ``__bool__``, which
    reads the view's EMPTY Rust base - every view was false, so ``if
    view:`` took the empty branch, and networkx's own code handed a view
    did too: read_graphml(view) passed ``ElementTree(file=view)``'s
    ``if file:`` and failed on an empty tree (AttributeError 'NoneType'
    object has no attribute 'findall') where networkx raises TypeError."""
    return len(view) > 0


def _view_repr(view):
    """br-r37-c1-77tw1: fnx's graph repr, ``DiGraph(nodes=2, edges=1)``, with
    the view's counts - the inherited native ``__repr__`` read the view's
    EMPTY Rust base and printed ``nodes=0, edges=0`` for every view."""
    return (
        f"{_concrete_class_for(view).__name__}"
        f"(nodes={len(view)}, edges={view.number_of_edges()})"
    )


class _ReverseDirectedViewBase:
    adjlist_inner_dict_factory = dict
    adjlist_outer_dict_factory = dict

    def __bool__(self):
        return _view_bool(self)

    def __repr__(self):
        return _view_repr(self)
    edge_attr_dict_factory = dict
    graph_attr_dict_factory = dict
    node_attr_dict_factory = dict
    node_dict_factory = dict

    def __new__(cls, graph=None, *args, **kwargs):
        # br-r37-c1-q131o: empty Rust base — the reverse-view classes mix this
        # in with the PyO3 DiGraph/MultiDiGraph base, whose __new__ copies the
        # whole parent graph into the view's storage (O(|V|+|E|)). Dead weight:
        # every query is answered through self._graph with succ/pred swapped.
        # Same fix as _FilteredGraphView / _ConversionGraphViewBase.
        if (
            graph is None
            and not args
            and not kwargs
            and cls.__new__ is _ReverseDirectedViewBase.__new__
        ):
            return _new_empty_graph_for_view_class(cls)
        return super().__new__(cls)

    def __init__(self, graph):
        _store = self.__dict__
        # A failed graph.graph lookup can leave a parent/view cycle before
        # the first setattr. Register before any such edge is installed.
        self._fnx_register_gc_dict(_store)
        # Fresh canonical views have no caches or user-owned state to reset.
        # Subclasses, nested views and reinitialization keep the full funnel.
        fast_init = (
            not _store
            and type(graph) in (DiGraph, MultiDiGraph)
            and type(self) in (_ReverseDirectedView, _ReverseMultiDirectedView)
            and (
                type(self).__setattr__ is _digraph_setattr_with_cached_public_adjacency
                or type(self).__setattr__ is _multidigraph_setattr_with_cached_public_adjacency
            )
        )
        _store["_graph"] = graph
        # br-r37-c1-u9a13: share the parent's graph dict, as networkx's
        # reverse view does (R.graph is G.graph). ``self.graph = graph.graph``
        # went through the graph-attrs descriptor, which copies into the
        # view's own dict - a write on either side was lost on the other.
        # Same bypass as the filtered view (br-r37-c1-fgv-graph-id).
        _store[_GRAPH_ATTR_OVERRIDE] = graph.graph
        if fast_init:
            _store["frozen"] = True
        else:
            self.frozen = True
        # br-r37-c1-revadjname: pick canonical AdjacencyView /
        # MultiAdjacencyView per multi-ness so type(R.adj).__name__
        # matches nx.
        adj_cls = (
            _ReverseMultiAdjacencyView if graph.is_multigraph()
            else _ReverseGraphAdjacencyView
        )
        # All three views are built BEFORE any assignment, because the batch
        # funnel runs nothing between the writes.  ``adj`` and ``succ`` expose
        # the same live mapping but networkx constructs DISTINCT wrappers for
        # them on a reverse view; keeping one object under both names makes the
        # otherwise-visible ``R.adj is R.succ`` identity test diverge.
        succ_view = adj_cls(self)
        pred_view = adj_cls(self, reverse=True)
        adj_view = adj_cls(self)
        if fast_init:
            _store[_PRIVATE_SUCC_OVERRIDE] = succ_view
            self._fnx_set_private_dir_override()
            _store[_PRIVATE_PRED_OVERRIDE] = pred_view
            self._fnx_set_private_dir_override()
            _store[_PRIVATE_ADJ_OVERRIDE] = adj_view
            self._fnx_set_private_adj_override()
            _install_private_method_shadows(self, _store)
        else:
            _set_private_overrides(
                self,
                (
                    (_PRIVATE_SUCC_OVERRIDE, succ_view),
                    (_PRIVATE_PRED_OVERRIDE, pred_view),
                    (_PRIVATE_ADJ_OVERRIDE, adj_view),
                ),
            )

    def _fnx_native_graph(self):
        # br-r37-c1-4rhw0: the reversed graph, for native kernels (see
        # _FilteredGraphView._fnx_native_graph) - this view's Rust storage is
        # empty (br-r37-c1-q131o).
        return _materialize_view(self)

    def __iter__(self):
        return iter(self._graph)

    def __len__(self):
        return len(self._graph)

    def __contains__(self, node):
        return node in self._graph

    def __getitem__(self, node):
        # Match NetworkX: view[node] returns the reversed adjacency
        # mapping (i.e. self.succ[node] under the swapped-direction
        # semantics already baked into _ReverseAdjacencyView).
        return self.adj[node]

    def is_directed(self):
        return True

    def is_multigraph(self):
        return self._graph.is_multigraph()

    def to_directed_class(self):
        return MultiDiGraph if self.is_multigraph() else DiGraph

    def to_undirected_class(self):
        return MultiGraph if self.is_multigraph() else Graph

    def to_directed(self, as_view=False):
        """Convert reversed adjacency to a deep copy or a frozen live view."""
        graph_class = MultiDiGraph if self.is_multigraph() else DiGraph
        # The canonical routines already preserve attribute-key fidelity,
        # per-dictionary deepcopy semantics, and the as_view contract. Their
        # exact-type native paths cannot read this view's empty Rust storage.
        return graph_class.to_directed(self, as_view=as_view)

    def to_undirected(self, reciprocal=False, as_view=False):
        """Convert reversed adjacency, preserving reciprocal and view options."""
        graph_class = MultiDiGraph if self.is_multigraph() else DiGraph
        return graph_class.to_undirected(self, reciprocal=reciprocal, as_view=as_view)

    def reverse(self, copy=True):
        """Return the underlying (un-reversed) directed graph.

        The reverse of a reverse-view is the original orientation.
        copy=True deep-copies graph, node, and edge attribute dictionaries.
        copy=False returns the live underlying graph (no wrapper).
        """
        if copy:
            graph_class = MultiDiGraph if self.is_multigraph() else DiGraph
            # Snapshot the current view before the native deep reverse. The
            # kernel materialization cache does not track node-attribute edits.
            return graph_class.reverse(self.copy(), copy=True)
        return self._graph

    @property
    def nodes(self):
        """Expose the underlying graph's NodeView.

        reverse_view doesn't change node identity or attributes, only
        edge direction — so the NodeView is shared with the original
        graph. Matches upstream's callable NodeView surface (e.g.
        view.nodes.data(), view.nodes(data=True)).
        """
        return self._graph.nodes

    def nbunch_iter(self, nbunch=None):
        return self._graph.nbunch_iter(nbunch)

    def _nbunch(self, nbunch):
        if nbunch is None:
            return list(self._graph.nodes())
        if nbunch in self._graph:
            return [nbunch]
        try:
            return [node for node in nbunch if node in self._graph]
        except TypeError:
            return []

    def _edges(self, nbunch=None, data=False, keys=False, default=None):
        nodes = self._nbunch(nbunch)
        result = []
        # cc-revedgespred: iterate the parent's native per-node predecessor row
        # (`_fast_pred_row` -> a PLAIN dict in one native call) instead of
        # `self._graph.pred[source]`, which returns a MultiAdjacencyView/AtlasView
        # that re-materialises `_native_predecessor_row` ~3x per edge (MDG
        # reverse.edges(keys,data) ran 0.17x nx). `_fast_pred_row` is O(deg) and
        # already falls back to `graph.pred[node]` for a nested-view parent, so it
        # is byte-identical (same row keys/order, same keydicts, same attrs).
        if self._graph.is_multigraph():
            for source in nodes:
                for target, keyed_attrs in _fast_pred_row(self._graph, source).items():
                    for key, attrs in keyed_attrs.items():
                        if isinstance(data, str):
                            result.append(
                                (source, target, key, attrs.get(data, default))
                                if keys
                                else (source, target, attrs.get(data, default))
                            )
                        elif data is None and keys:
                            result.append((source, target, key, default))
                        elif data is None:
                            result.append((source, target, default))
                        elif data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
        else:
            for source in nodes:
                for target, attrs in _fast_pred_row(self._graph, source).items():
                    if isinstance(data, str):
                        result.append((source, target, attrs.get(data, default)))
                    elif data is None:
                        result.append((source, target, default))
                    elif data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
        return result

    @_cached_property
    def edges(self):
        # br-r37-c1-revadjname: pick canonical OutEdgeView /
        # OutMultiEdgeView per multi-ness.
        if self._graph.is_multigraph():
            return _ReverseOutMultiEdgeView(self)
        return _ReverseOutEdgeView(self)

    def _out_edges_compute(self, nbunch=None, data=False, keys=False, default=None):
        nodes = self._nbunch(nbunch)
        result = []
        adjacency = self.succ
        if self._graph.is_multigraph():
            for source in nodes:
                for target, keyed_attrs in adjacency[source].items():
                    for key, attrs in keyed_attrs.items():
                        if isinstance(data, str):
                            result.append(
                                (source, target, key, attrs.get(data, default))
                                if keys
                                else (source, target, attrs.get(data, default))
                            )
                        elif data is None and keys:
                            result.append((source, target, key, default))
                        elif data is None:
                            result.append((source, target, default))
                        elif data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
        else:
            for source in nodes:
                for target, attrs in adjacency[source].items():
                    if isinstance(data, str):
                        result.append((source, target, attrs.get(data, default)))
                    elif data is None:
                        result.append((source, target, default))
                    elif data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
        return result

    def _in_edges_compute(self, nbunch=None, data=False, keys=False, default=None):
        nodes = self._nbunch(nbunch)
        result = []
        adjacency = self.pred
        if self._graph.is_multigraph():
            for target in nodes:
                for source, keyed_attrs in adjacency[target].items():
                    for key, attrs in keyed_attrs.items():
                        if isinstance(data, str):
                            result.append(
                                (source, target, key, attrs.get(data, default))
                                if keys
                                else (source, target, attrs.get(data, default))
                            )
                        elif data is None and keys:
                            result.append((source, target, key, default))
                        elif data is None:
                            result.append((source, target, default))
                        elif data and keys:
                            result.append((source, target, key, attrs))
                        elif data:
                            result.append((source, target, attrs))
                        elif keys:
                            result.append((source, target, key))
                        else:
                            result.append((source, target))
        else:
            for target in nodes:
                for source, attrs in adjacency[target].items():
                    if isinstance(data, str):
                        result.append((source, target, attrs.get(data, default)))
                    elif data is None:
                        result.append((source, target, default))
                    elif data:
                        result.append((source, target, attrs))
                    else:
                        result.append((source, target))
        return result

    # br-r37-c1-revview: nx exposes these on a reverse view as
    # @property returning a view object that supports __iter__,
    # __getitem__, __call__, __len__ etc.  fnx had them as plain
    # methods, so ``R.in_edges`` returned a bound method (not a
    # view) — ``list(R.in_edges)`` and ``R.degree[node]`` raised
    # TypeError.  Wrap each via a small Proxy class with the
    # canonical nx ``__name__``.
    @property
    def out_edges(self):
        if self._graph.is_multigraph():
            return _RevOutMultiEdgeViewProxy(self)
        return _RevOutEdgeViewProxy(self)

    @property
    def in_edges(self):
        if self._graph.is_multigraph():
            return _RevInMultiEdgeViewProxy(self)
        return _RevInEdgeViewProxy(self)

    def _degree_compute(self, nbunch=None, weight=None):
        def edge_weight(attrs):
            return attrs.get(weight, 1)

        def node_degree(node):
            if self._graph.is_multigraph():
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

            if weight is None:
                return len(self.succ[node]) + len(self.pred[node])

            total = 0
            for attrs in self.succ[node].values():
                total += edge_weight(attrs)
            for attrs in self.pred[node].values():
                total += edge_weight(attrs)
            return total

        if nbunch is None:
            return ((node, node_degree(node)) for node in self._graph)

        try:
            if nbunch in self._graph:
                return node_degree(nbunch)
        except TypeError:
            pass

        nodes = self._nbunch(nbunch)
        return ((node, node_degree(node)) for node in nodes)

    @property
    def degree(self):
        # br-r37-c1-r3gjb: a node's TOTAL degree is invariant under edge
        # reversal (in + out is the same edge set), so route straight to the
        # parent's native degree view — same nodes, same totals, same view
        # class (DiDegreeView / DiMultiDegreeView) — instead of recomputing
        # through the per-neighbour _degree_compute / _ReverseNeighborMap walk
        # (reverse().degree() was 54x nx). in_degree / out_degree keep the
        # swapped reverse path: their view class NAME must read In/Out, which
        # the parent's swapped views would not provide.
        #
        # br-r37-c1-nvm5i: the shortcut is only sound while self and the parent
        # have the SAME NODE SET. `reverse(...).subgraph(...)` keeps this class
        # in its MRO while filtering the nodes, so the parent's view answered
        # for nodes the subgraph does not contain — `G.degree` reported all four
        # nodes of the parent, at the parent's degrees, for a two-node subgraph
        # whose own `nodes()` and `edges()` were correct.
        #
        # `isinstance(self, _FilteredGraphView)` is the exact discriminator: it
        # is True only when SELF does the filtering. A reverse view OVER an
        # already-filtered graph (`subgraph(...).reverse()`) is False and keeps
        # the shortcut, which is right — there the parent's node set is already
        # the filtered one.
        if isinstance(self, _FilteredGraphView):
            return super().degree
        return self._graph.degree

    def subgraph(self, nodes):
        return _generic_filtered_graph_view(
            self,
            filter_node=_subgraph_filter_from_nbunch(self, nodes),
        )

    def edge_subgraph(self, edges):
        return edge_subgraph(self, edges)

    def copy(self, as_view=False):
        if as_view:
            return _generic_filtered_graph_view(self)

        copy_factory = getattr(self._graph, "_copy_type", None)
        result_type = copy_factory() if callable(copy_factory) else self._graph.__class__
        result = result_type()
        result.graph.update(dict(self.graph))
        result.add_nodes_from((node, dict(attrs)) for node, attrs in self.nodes(data=True))
        if self._graph.is_multigraph():
            # Use 4-tuple (u, v, key, attrs_dict) so an edge attribute literally
            # named "key" doesn't collide with add_edge's positional ``key=``
            # parameter (see franken_networkx-9x7r0).
            result.add_edges_from(
                (u, v, key, dict(attrs))
                for u, v, key, attrs in self.edges(keys=True, data=True)
            )
        else:
            result.add_edges_from(
                (u, v, dict(attrs)) for u, v, attrs in self.edges(data=True)
            )
        return result

    def number_of_nodes(self):
        return len(self._graph)

    def order(self):
        return self.number_of_nodes()

    def adjacency(self):
        return ((node, _ReverseNeighborMap(self, node)) for node in self._graph)

    def __copy__(self):
        return _graph_view_shallowcopy(self)

    def __deepcopy__(self, memo):
        copy_factory = getattr(self._graph, "_copy_type", None)
        graph_class = copy_factory() if callable(copy_factory) else self._graph.__class__
        return _graph_deepcopy(self, memo, snapshot_class=graph_class)

    def number_of_edges(self, u=None, v=None):
        if u is None:
            return self._graph.number_of_edges()
        # br-r37-c1-fabqo: networkx's (u, v) count on the REVERSED adjacency -
        # the override took no arguments. A simple graph asks `v in _adj[u]`,
        # so a missing u raises KeyError; a multigraph counts the keys and
        # answers 0 for any missing endpoint.
        if self._graph.is_multigraph():
            try:
                return len(self.adj[u][v])
            except KeyError:
                return 0
        return 1 if v in self.adj[u] else 0

    def size(self, weight=None):
        if weight is None:
            return self.number_of_edges()
        return sum(degree for _, degree in self.degree(weight=weight)) / 2

    def has_node(self, node):
        return node in self._graph

    def has_edge(self, u, v, key=None):
        if self._graph.is_multigraph():
            return self._graph.has_edge(v, u, key)
        return self._graph.has_edge(v, u)

    def get_edge_data(self, u, v, *args, **kwargs):
        if self._graph.is_multigraph():
            key = kwargs.pop("key", None)
            default = kwargs.pop("default", None)
            if kwargs:
                unexpected = next(iter(kwargs))
                raise TypeError(f"get_edge_data() got an unexpected keyword argument '{unexpected}'")
            if len(args) > 2:
                raise TypeError(
                    f"get_edge_data() takes from 3 to 5 positional arguments but {len(args) + 3} were given"
                )
            if len(args) >= 1:
                key = args[0]
            if len(args) == 2:
                default = args[1]
            try:
                keys = self._adj[u][v]
                return keys if key is None else keys[key]
            except KeyError:
                return default

        if "key" in kwargs:
            raise TypeError("get_edge_data() got an unexpected keyword argument 'key'")
        default = kwargs.pop("default", None)
        if kwargs:
            unexpected = next(iter(kwargs))
            raise TypeError(f"get_edge_data() got an unexpected keyword argument '{unexpected}'")
        if len(args) > 1:
            raise TypeError(
                f"get_edge_data() takes from 3 to 4 positional arguments but {len(args) + 3} were given"
            )
        if args:
            default = args[0]
        # A filtered view can inherit this method from its reversed parent.
        # Its logical adjacency already has the right orientation and filters;
        # reversing parent endpoints again reads a different (or hidden) edge.
        try:
            return self._adj[u][v]
        except KeyError:
            return default

    def neighbors(self, node):
        return self._graph.predecessors(node)

    def successors(self, node):
        return self._graph.predecessors(node)

    def predecessors(self, node):
        return self._graph.successors(node)

    def __getattr__(self, name):
        if name in _FILTERED_VIEW_MUTATORS:
            return _frozen
        # br-r37-c1-ndro1: networkx's reverse view is a DiGraph, whose missing
        # attribute reads "'DiGraph' object has no attribute 'items'" (what
        # from_dict_of_dicts & co. handed a view raise); a bare
        # AttributeError(name) said 'items'.
        raise AttributeError(
            f"'{_concrete_class_for(self).__name__}' object has no attribute '{name}'"
        )

    def __reduce__(self):
        copy_factory = getattr(self._graph, "_copy_type", None)
        graph_class = copy_factory() if callable(copy_factory) else self._graph.__class__
        return _graph_pickle_view_reduce(self, graph_class)

    # br-r37-c1-rvfrz: same MRO mutability hole as br-r37-c1-6qm6r —
    # _ReverseDirectedView inherits from (_ReverseDirectedViewBase,
    # DiGraph) and _ReverseMultiDirectedView from (_ReverseDirectedViewBase,
    # MultiDiGraph). The canonical class's mutators (add_node,
    # add_edge, ...) are reachable via MRO BEFORE __getattr__ ever
    # gets consulted, so mutating a reversed view became a silent
    # no-op (Graph.add_node targets unset Rust state on the synthetic
    # instance) instead of raising NetworkXError("Frozen graph can't
    # be modified") as nx does. Shadow each of the 12 nx-defined
    # mutators here so they're found in MRO before the inherited
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


# br-r37-c1-revview: small proxy classes that wrap a reverse-view
# method so the result behaves like a view object (callable +
# iterable + indexable + sized) AND has the canonical nx
# ``__name__`` for type introspection.
class _RevEdgeMethodViewBase:
    """Base proxy: wraps an edge-computing method on the reverse
    view. ``self()`` (no args) → list of edges. _Iterable / sized.
    Calling with kwargs forwards to the underlying compute method.
    """

    __slots__ = ("_owner",)
    # br-r37-c1-ex1s6: the reverse view's rows membership reads - its succ
    # (the graph's pred) for out_edges, its pred (the graph's succ) for
    # in_edges; see _nx_edge_view_contains.
    _fnx_edge_kind = "out"

    def __init__(self, owner):
        self._owner = owner

    def _compute(self, *args, **kwargs):
        raise NotImplementedError

    def __call__(self, nbunch=None, data=False, keys=False, default=None):
        # br-r37-c1-ex1s6: networkx's In/OutEdgeView.__call__ - the view
        # itself for a plain call (a multigraph's only with keys=True), else
        # a live In/OutEdgeDataView (a list before: no liveness, no name,
        # membership by scan).
        return _view_edges_call(self, self._owner, nbunch, data, keys, default)

    def _list(self, nbunch=None, data=False, keys=False, default=None):
        return self._compute(nbunch=nbunch, data=data, keys=keys, default=default)

    def __iter__(self):
        # Multi*Graph reverse views default to keys=True for __iter__
        # but keys=False for __call__ — match the nx asymmetry.
        if self._owner._graph.is_multigraph():
            return iter(self._compute(keys=True))
        return iter(self._compute())

    def __len__(self):
        return len(self._compute())

    def __contains__(self, item):
        # br-r37-c1-ex1s6: one row lookup, networkx's rules; this built a set
        # of every edge per probe and answered False for a malformed one.
        graph = self._owner._graph
        kind = self._fnx_edge_kind
        rows = graph.succ if kind == "in" else graph.pred
        return _nx_edge_view_contains(rows, item, kind, graph.is_multigraph())

    def __getitem__(self, edge):
        if isinstance(edge, slice):
            raise NetworkXError(
                f"{type(self).__name__} does not support slicing, try "
                f"list(G.edges)[{edge.start}:{edge.stop}:{edge.step}]"
            )
        view = self._owner
        multi = view.is_multigraph()
        if multi:
            u, v, key = edge
        else:
            u, v = edge
        # Read the owner's rows so a filtered reverse view keeps its orientation
        # and predicates. Reversing its parent again would read the wrong edge.
        attrs = view.pred[v][u] if self._fnx_edge_kind == "in" else view.succ[u][v]
        return attrs[key] if multi else attrs

    get = _adjacency_view_get

    def keys(self):
        return _KeysViewABC(self)

    def items(self):
        return _ItemsViewABC(self)

    def values(self):
        return _ValuesViewABC(self)

    def __repr__(self):
        return f"{type(self).__name__}({list(self)!r})"

    def data(self, data=True, default=None, nbunch=None, keys=False):
        # br-r37-c1-revview-data: nx's reverse-view edges have a
        # ``.data()`` method that returns an EdgeDataView. Match.
        return self(nbunch=nbunch, data=data, keys=keys, default=default)

    # br-r37-c1-revvcopy: see _RevDegreeViewBase above — same fix
    # for in_edges / out_edges proxies.
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        # br-r37-c1-vcopydc (cycle 200 dual): nx's _deepcopy is a
        # SNAPSHOT independent of subsequent G mutations.  Deep-
        # copy the underlying directed graph, build its reverse,
        # and return the matching view based on the cycle-188-style
        # subclass name.
        new_graph = _deepcopy(self._owner._graph, memo)
        new_reverse = new_graph.reverse(copy=False)
        cls_name = type(self).__name__
        if cls_name in ("InEdgeView", "InMultiEdgeView"):
            return new_reverse.in_edges
        return new_reverse.out_edges


class _RevOutEdgeViewProxy(_RevEdgeMethodViewBase):
    def _compute(self, *args, **kwargs):
        return self._owner._out_edges_compute(*args, **kwargs)
_RevOutEdgeViewProxy.__name__ = "OutEdgeView"


class _RevInEdgeViewProxy(_RevEdgeMethodViewBase):
    _fnx_edge_kind = "in"

    def _compute(self, *args, **kwargs):
        return self._owner._in_edges_compute(*args, **kwargs)
_RevInEdgeViewProxy.__name__ = "InEdgeView"


class _RevOutMultiEdgeViewProxy(_RevEdgeMethodViewBase):
    def _compute(self, *args, **kwargs):
        return self._owner._out_edges_compute(*args, **kwargs)
_RevOutMultiEdgeViewProxy.__name__ = "OutMultiEdgeView"


class _RevInMultiEdgeViewProxy(_RevEdgeMethodViewBase):
    _fnx_edge_kind = "in"

    def _compute(self, *args, **kwargs):
        return self._owner._in_edges_compute(*args, **kwargs)
_RevInMultiEdgeViewProxy.__name__ = "InMultiEdgeView"


class _RevDegreeViewBase:
    """Proxy for a reverse-view degree. Supports ``view[node]`` →
    int, ``list(view)`` → [(node, deg), ...], and ``view(weight=)``
    forwarding to the underlying compute method."""

    __slots__ = ("_owner",)

    def __init__(self, owner):
        self._owner = owner

    def __call__(self, nbunch=None, weight=None):
        return self._owner._degree_compute(nbunch=nbunch, weight=weight)

    def __iter__(self):
        return iter(self._owner._degree_compute())

    def __getitem__(self, node):
        return self._owner._degree_compute(node)

    def __len__(self):
        return len(self._owner._graph)

    def __repr__(self):
        return f"{type(self).__name__}({dict(self)!r})"

    def __str__(self):
        # br-r37-c1-dvvme: networkx's DegreeView prints the list, not its repr.
        return str(list(self))

    # br-r37-c1-revvcopy: copy._deepcopy(R.degree) recursed into the
    # parent graph and tripped _graph_deepcopy's no-arg ``cls()``
    # (reverse view requires a graph arg).  __copy__ returns self
    # (live wrapper, matching nx).  __deepcopy__ snapshots via
    # deep-copy of underlying graph + reverse + .degree (cycle 200
    # dual; matches nx's snapshot semantic for _deepcopy).
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        new_graph = _deepcopy(self._owner._graph, memo)
        new_reverse = new_graph.reverse(copy=False)
        return new_reverse.degree


class _RevDiDegreeViewProxy(_RevDegreeViewBase):
    pass
_RevDiDegreeViewProxy.__name__ = "DiDegreeView"


class _RevDiMultiDegreeViewProxy(_RevDegreeViewBase):
    pass
_RevDiMultiDegreeViewProxy.__name__ = "DiMultiDegreeView"


class _ReverseDirectedView(_ReverseDirectedViewBase, DiGraph):
    pass


class _ReverseMultiDirectedView(_ReverseDirectedViewBase, MultiDiGraph):
    pass


def _reverse_directed_view_for(graph):
    view_type = (
        _ReverseMultiDirectedView if graph.is_multigraph() else _ReverseDirectedView
    )
    return view_type(graph)


class _ReverseNeighborMap(_Mapping):
    def __init__(self, view, node, *, reverse=False):
        self._view = view
        self._node = node
        self._reverse = reverse
        # Capture the parent's live per-node view, not a plain dictionary of
        # its current neighbors. In particular, _fast_*_row builds a snapshot
        # of MultiDiGraph neighbor keys even though its edge dictionaries live
        # on. The public row is already local to this node and tracks edge
        # churn. Capturing it now also preserves a held row when its node is
        # removed or the parent is cleared, rather than attaching to a new row
        # if the same node is added again.
        rows = view._graph.succ if reverse else view._graph.pred
        self._fnx_row = rows[node]

    def _raw_neighbors(self):
        return self._fnx_row

    def __iter__(self):
        return iter(self._raw_neighbors())

    def __len__(self):
        return len(self._raw_neighbors())

    def __getitem__(self, neighbor):
        row = self._raw_neighbors()
        owner = getattr(row, "_fnx_multi_edge_owner", None)
        if type(owner) is MultiDiGraph and not _has_networkx_private_storage(owner):
            if neighbor not in row:
                raise KeyError(neighbor)
            # The native keydict returned here detaches when the final parallel
            # edge disappears. A public AtlasView cell re-resolves the pair and
            # would attach a held keydict to replacement edges. On clear/node
            # removal the parent's existing row-detach hook clears this owner;
            # the fallback then reads that row's preserved attributes instead.
            u, v = (self._node, neighbor) if self._reverse else (neighbor, self._node)
            return owner.get_edge_data(u, v)
        return row[neighbor]

    def items(self):
        return _ItemsViewABC(self)

    def keys(self):
        return _KeysViewABC(self)

    def values(self):
        return _ValuesViewABC(self)


class _ReverseAdjacencyView(_Mapping):
    def __init__(self, view, *, reverse=False):
        self._view = view
        self._reverse = reverse

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getitem__(self, node):
        # br-r37-c1-sc825: nx reaches a dict lookup here, so an UNHASHABLE
        # index raises TypeError, not KeyError. The membership test below
        # answers False for an unhashable argument instead of propagating, so
        # without this the view reported "no such node" for something that is
        # not a valid node at all. Every sibling view already opens this way —
        # see br-r37-c1-i9whv, which established the contract.
        _HASH_PROBE.get(node)
        if node not in self._view._graph:
            # br-r37-c1-k4nsd: an UNFILTERED reverse view reaches a plain dict
            # in nx, so it raises the bare key — the "Key n not found" wording
            # belongs to FilterAtlas, i.e. only when something underneath is
            # actually filtered.
            raise _missing_node_key_error(self._view._graph, node)
        return _ReverseNeighborMap(self._view, node, reverse=self._reverse)

    def __repr__(self):
        # br-r37-c1-revadjname: nx's reverse-view succ/pred/adj repr
        # as ``AdjacencyView({...})`` / ``MultiAdjacencyView({...})``.
        # fnx had no __repr__ here, falling through to default
        # ``<...object at 0x...>``. Use ``type(self).__name__`` so
        # the two subclasses below pick up the right canonical name.
        # Recursively unwrap inner mapping values (per-key dicts on
        # MultiGraph wrap as AtlasView) so the repr matches nx's
        # plain-dict format.
        from collections.abc import Mapping as _Mapping
        def _unwrap(v):
            if isinstance(v, _Mapping):
                return {k2: _unwrap(v2) for k2, v2 in v.items()}
            return v
        return f"{type(self).__name__}({_unwrap(self)!r})"

    # br-r37-c1-revvcopy: __copy__ returns self (live wrapper —
    # matches nx).  __deepcopy__ snapshots via deep-copy of the
    # underlying directed graph + reverse + .succ/.pred based on
    # the ``self._reverse`` direction flag (cycle 200 dual).
    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        new_graph = _deepcopy(self._view._graph, memo)
        new_reverse = new_graph.reverse(copy=False)
        # self._reverse=True means we're the .pred view (reversed
        # from .succ); False means we're the .succ view.  Reverse
        # view's .succ is the original graph's predecessors and
        # vice versa.
        if self._reverse:
            return new_reverse.pred
        return new_reverse.succ


# br-r37-c1-revadjname: 2 trivial subclasses with canonical nx
# ``__name__`` so ``type(R.adj).__name__`` matches nx for reverse
# views.  The factory in _ReverseDirectedViewBase.__init__
# dispatches based on ``graph.is_multigraph()``.
class _ReverseGraphAdjacencyView(_ReverseAdjacencyView):
    pass
_ReverseGraphAdjacencyView.__name__ = "AdjacencyView"


class _ReverseMultiAdjacencyView(_ReverseAdjacencyView):
    pass
_ReverseMultiAdjacencyView.__name__ = "MultiAdjacencyView"
