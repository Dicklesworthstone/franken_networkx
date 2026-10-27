

def _dag_longest_path_length_multigraph(G, weight, default_weight):
    topo_order = topological_sort(G)
    _prd = getattr(G, "_native_predecessor_row_dict", None)
    multi_pred = {}
    if _prd is not None:
        for _v in G:
            _pw = {}
            for _u, _keydict in _prd(_v).items():
                _pw[_u] = max(
                    (
                        attrs.get(weight, default_weight)
                        if isinstance(attrs, dict)
                        else default_weight
                        for attrs in _keydict.values()
                    ),
                    default=default_weight,
                )
            multi_pred[_v] = _pw
    else:
        for _v, _preds in G.pred.items():
            _pw = {}
            for _u, _keydict in _preds.items():
                _pw[_u] = max(
                    (
                        attrs.get(weight, default_weight)
                        if isinstance(attrs, dict)
                        else default_weight
                        for attrs in _keydict.values()
                    ),
                    default=default_weight,
                )
            multi_pred[_v] = _pw

    dist = {}
    for v in topo_order:
        us = [(dist[u][0] + _w, u) for u, _w in multi_pred[v].items()]
        maxu = max(us, key=lambda x: x[0]) if us else (0, v)
        dist[v] = maxu if maxu[0] >= 0 else (0, v)
    return max((length for length, _ in dist.values()), default=0)


def dag_longest_path_length(G, weight="weight", default_weight=1):
    """Return the length of the longest path in a DAG.

    Parameters
    ----------
    G : DiGraph
        A directed acyclic graph (DAG).
    weight : str, optional
        Edge attribute name to use for weights. Default is 'weight'.
    default_weight : int, optional
        Default weight for edges without the weight attribute. Default is 1.

    Returns
    -------
    int
        The length of the longest path.

    br-daglongundir: nx is @not_implemented_for('undirected') and
    raises NetworkXNotImplemented('not implemented for undirected type').
    Gate on G.is_directed() so the exception class matches.

    br-r37-c1-jwa0g: the length is computed from the (pure-Python,
    weight-correct) ``dag_longest_path`` result by summing edge weights
    via Python ``G[u][v]`` access — exactly nx's algorithm.  The Rust
    ``_fnx.dag_longest_path_length`` fast path was dropped: its
    ``edge_attrs()`` reader is blind to weights stored by
    ``add_weighted_edges_from`` or post-creation ``G[u][v][w]=...``
    mutation (Rust attr-sync gap, br-r37-c1-7s20o), so it silently
    returned the hop count for such graphs.  Summing from an integer
    ``0`` also makes int/float return-type preservation natural —
    sum-of-ints stays int — matching nx without any restoration logic.
    The cyclic-graph error contract is inherited from
    ``dag_longest_path`` -> ``topological_sort`` (NetworkXUnfeasible,
    "Graph contains a cycle or graph changed during iteration").
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if G.is_multigraph():
        return _dag_longest_path_length_multigraph(
            G, weight=weight, default_weight=default_weight
        )
    path = dag_longest_path(
        G, weight=weight, default_weight=default_weight
    )
    path_length = 0
    if G.is_multigraph():
        for u, v in zip(path, path[1:]):
            keydict = G[u][v]
            heaviest = max(
                keydict,
                key=lambda k: keydict[k].get(weight, default_weight),
            )
            path_length += keydict[heaviest].get(weight, default_weight)
    else:
        for u, v in zip(path, path[1:]):
            path_length += G[u][v].get(weight, default_weight)
    return path_length

# Algorithm functions — graph isomorphism
from franken_networkx._fnx import (
    fast_could_be_isomorphic as _raw_fast_could_be_isomorphic,
    graph_edit_distance_common_rust as _graph_edit_distance_common_rust,
    faster_could_be_isomorphic as _raw_faster_could_be_isomorphic,
    is_isomorphic as _is_isomorphic_rust,
    vf2pp_all_isomorphisms_rust as _vf2pp_all_isomorphisms_rust,
    vf2pp_isomorphism_rust as _vf2pp_isomorphism_rust,
)
from networkx.algorithms import isomorphism as _nx_isomorphism

# br-r37-c1-iso-removed: nine isomorphism matcher constructors
# (categorical/numerical/generic × node/edge/multiedge) live only at
# ``nx.algorithms.isomorphism.X`` in nx; nx top-level access raises
# AttributeError.  fnx exposed them as top-level convenience aliases
# that masked the contract — drop-in callers writing
# ``nx.categorical_node_match(...)`` got a working function on fnx
# while nx raises.  Available exclusively at
# ``fnx.algorithms.isomorphism.X`` (which delegates to nx).  Module
# ``__getattr__`` traps top-level access.


# br-r37-c1-qliut: GraphMatcher / DiGraphMatcher / MultiGraphMatcher /
# MultiDiGraphMatcher were defined as explicit subclasses here, but the
# factory at module-level (see _build_vf2_matcher_classes below) overwrites
# all four assignments. The earlier explicit defs were dead code.


class ISMAGS(_nx_isomorphism.ISMAGS):
    """ISMAGS matcher accepting FrankenNetworkX graph objects."""

    def __init__(self, graph, subgraph, node_match=None, edge_match=None, cache=None):
        super().__init__(
            _networkx_graph_for_parity(graph),
            _networkx_graph_for_parity(subgraph),
            node_match=node_match,
            edge_match=edge_match,
            cache=cache,
        )


class TimeRespectingGraphMatcher(_nx_isomorphism.TimeRespectingGraphMatcher):
    """Temporal graph matcher accepting FrankenNetworkX graph objects."""

    def __init__(self, G1, G2, temporal_attribute_name, delta):
        super().__init__(
            _networkx_graph_for_parity(G1),
            _networkx_graph_for_parity(G2),
            temporal_attribute_name,
            delta,
        )


class TimeRespectingDiGraphMatcher(_nx_isomorphism.TimeRespectingDiGraphMatcher):
    """Temporal directed-graph matcher accepting FrankenNetworkX graph objects."""

    def __init__(self, G1, G2, temporal_attribute_name, delta):
        super().__init__(
            _networkx_graph_for_parity(G1),
            _networkx_graph_for_parity(G2),
            temporal_attribute_name,
            delta,
        )


def fast_could_be_isomorphic(G1, G2):
    """br-isokw: ``G1, G2`` match nx; Rust binding used ``g1, g2``."""
    # br-r37-c1-jwdzp: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    return _raw_fast_could_be_isomorphic(G1, G2)


def faster_could_be_isomorphic(G1, G2):
    """br-isokw: ``G1, G2`` match nx."""
    # br-r37-c1-jwdzp: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    return _raw_faster_could_be_isomorphic(G1, G2)

# Planarity
from franken_networkx._fnx import is_planar as _raw_is_planar
from franken_networkx._fnx import is_chordal as _raw_is_chordal


def is_chordal(G):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``.

    br-chordaltype: nx.is_chordal is @not_implemented_for('directed',
    'multigraph') and raises NetworkXNotImplemented; the Rust binding
    accepted MultiGraph input and returned False. Gate on type
    upfront so the contract matches.

    br-r37-c1-i8qr5: nx's _is_complete_graph internal helper raises
    NetworkXError('Self loop found in _is_complete_graph()') when
    is_chordal reaches a candidate complete subgraph that contains a
    self-loop (e.g. K4 + self-loop). The Rust _raw_is_chordal silently
    returns True for the same input. Delegate any self-loop input to
    nx so the exact raise pattern is preserved (nx only raises for
    the specific algorithm-reaches-_is_complete_graph case, not for
    every self-loop graph — the delegation reproduces that exact
    selectivity).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if number_of_selfloops(G) > 0:  # br-r37-c1-5i5gb: native O(|V|) check, not O(|E|) EdgeView pass
        if len(G) <= 3:
            return True
        unnumbered = set(G)
        s = next(iter(G))
        unnumbered.remove(s)
        numbered = {s}
        while unnumbered:
            v = max(unnumbered, key=lambda n: len(G._adj[n].keys() & numbered))
            unnumbered.remove(v)
            numbered.add(v)
            clique_wanna_be = set(G[v]) & numbered
            sg = G.subgraph(clique_wanna_be)
            if number_of_selfloops(sg) > 0:
                raise NetworkXError("Self loop found in _is_complete_graph()")
            n = len(sg)
            if n >= 2:
                e = sg.number_of_edges()
                max_edges = (n * (n - 1)) // 2
                if e != max_edges:
                    return False
        return True
    return _raw_is_chordal(G)


def _loopless_simple_undirected_edges(G):
    if G.is_directed() or G.is_multigraph():
        return None

    edges = list(G.edges())
    for u, v in edges:
        if u == v:
            return None
    return edges


def _is_triangle_free_with_edges(G, edges):
    adjacency = {node: set() for node in G.nodes()}
    for u, v in edges:
        adjacency.setdefault(u, set()).add(v)
        adjacency.setdefault(v, set()).add(u)

    for u, v in edges:
        u_neighbors = adjacency[u]
        v_neighbors = adjacency[v]
        if len(u_neighbors) <= len(v_neighbors):
            if any(node in v_neighbors for node in u_neighbors):
                return False
        elif any(node in u_neighbors for node in v_neighbors):
            return False
    return True


def is_planar(G, *, backend=None, **backend_kwargs):
    """Return True if ``G`` is planar.

    Matches upstream ``nx.is_planar(G, *, backend=None, **backend_kwargs)``
    signature so keyword calls like ``is_planar(G=g)`` work
    (franken_networkx-sl3mn); the raw Rust binding used ``g`` as the
    parameter name which broke kwarg parity.

    br-isplanarbroken: the Rust ``_raw_is_planar`` incorrectly
    classified K3,3 and the Petersen graph as planar (both are
    canonical non-planar graphs). Critically, fnx's own
    ``check_planarity`` already returned the correct answer for the
    same inputs, so the two functions contradicted each other. Route
    through ``check_planarity`` so is_planar and check_planarity
    always agree (both match nx's reference LR-planarity
    implementation).
    """
    _validate_backend_dispatch_keywords("is_planar", backend, backend_kwargs)
    # br-r37-c1-gttlp: cheap necessary-condition short-circuits before
    # the nx-graph round-trip + full LR embedding that check_planarity
    # builds. Same Kuratowski-style bounds proven correct in the Rust
    # crate via br-r37-c1-xdjpt; lifted to the Python wrapper here so
    # the speedup is independent of binary state.
    n = G.number_of_nodes()
    m = G.number_of_edges()
    simple_edges = _loopless_simple_undirected_edges(G)
    if simple_edges is not None:
        if n <= 4:
            # Every loop-free simple graph with ≤ 4 nodes is planar.
            return True
        if m > 3 * n - 6:
            # Euler bound: planar simple graphs with ≥ 3 nodes have
            # |E| ≤ 3|V|-6.
            return False
        # Girth-4 tightened bound: triangle-free planar simple graphs
        # have |E| ≤ 2|V|-4. The adjacency-set triangle scan is
        # O(sum(deg(u), deg(v))) over edges and replaces the heavier
        # nx-graph copy + full LR embedding when triggered.
        if m > 2 * n - 4 and _is_triangle_free_with_edges(G, simple_edges):
            return False
    # br-r37-c1-native-is-planar-boolean-zuxh1: exact native Left-Right
    # planarity kernel (de Fraysseix–Rosenstiehl / Brandes), boolean only.
    # Replaces the O(n^2) fnx->nx conversion + nx's pure-Python LR embedding
    # that check_planarity pays. Planarity is a graph invariant, so the
    # boolean is order-independent and matches check_planarity(G)[0] exactly.
    try:
        return _fnx.is_planar_lr(G)
    except Exception:
        is_p, _ = check_planarity(G)
        return is_p

# Barycenter
from franken_networkx._fnx import barycenter as _raw_barycenter
from franken_networkx._fnx import find_cycle_simple as _raw_find_cycle_simple
from franken_networkx._fnx import (
    find_cycle_multigraph_simple as _raw_find_cycle_multigraph_simple,
)


def barycenter(G, weight=None, attr=None, sp=None, *, backend=None, **backend_kwargs):
    """Return the barycenter of the graph or its node set.

    br-barymissing: nx.barycenter accepts ``weight`` (edge-attr name
    for weighted shortest paths), ``attr`` (store node-barycentricity
    as a node attribute), and ``sp`` (precomputed shortest-path dict).
    fnx's Rust binding only accepted (G). Delegate to nx when any
    non-default kwarg is supplied; fast-path kept for the plain
    (G,) form.

    br-baryattr: when ``attr`` is supplied, NX mutates the input graph
    in place by writing the barycentricity score to ``G.nodes[v][attr]``.
    The delegation goes through ``_networkx_graph_for_parity`` which
    builds a fresh nx Graph copy, so NX wrote the attribute on that
    copy — not on the user's fnx graph. Pull the attr back from the
    nx copy onto the original fnx graph so the side effect is visible
    where the user expects it.
    """
    _validate_backend_dispatch_keywords("barycenter", backend, backend_kwargs)
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if len(G) == 0:
        # Match nx's split empty-graph behavior: undirected graph
        # classes raise, while directed graph classes return [].
        if G.is_directed():
            return []
        raise NetworkXPointlessConcept("G has no nodes.")
    if weight is None and attr is None and sp is None:
        # br-r37-c1-pooue: the Rust _raw_barycenter does not check
        # reachability before computing, so it silently returns a
        # result on a non-strongly-connected DiGraph (e.g.,
        # DiGraph([(0,1),(1,2),(2,3)]) → [1, 2]). nx raises
        # NetworkXNoPath in that case. Route directed inputs through
        # the Python path below when the graph is not strongly
        # connected so the parity error surfaces correctly.
        if G.is_directed():
            if not is_strongly_connected(G):
                raise NetworkXNoPath(
                    f"Input graph {G} is disconnected, so every induced subgraph "
                    "has infinite barycentricity."
                )
            # br-r37-c1-ecqmz: _raw_barycenter has the directed-collapse
            # defect (gr.undirected() before computing) — returns wrong
            # barycenter on directed cycle5+chord (gives [0, 2] instead
            # of nx's [0]). Compute natively via shortest_path_length
            # which IS directed-aware.
            smallest = float("inf")
            result: list = []
            for v, dists in shortest_path_length(G):
                bc = sum(dists.values())
                if bc < smallest:
                    smallest = bc
                    result = [v]
                elif bc == smallest:
                    result.append(v)
            return result
        return _raw_barycenter(G)
    if sp is None:
        if weight is not None:
            sp_iter = shortest_path_length(G, weight=weight)
        else:
            sp_iter = shortest_path_length(G)
    else:
        if weight is not None:
            raise ValueError("Cannot use both sp, weight arguments together")
        sp_iter = sp.items()
    smallest = float("inf")
    barycenter_vertices: list = []
    n = len(G)
    for v, dists in sp_iter:
        if len(dists) < n:
            raise NetworkXNoPath(
                f"Input graph {G} is disconnected, so every induced subgraph "
                "has infinite barycentricity."
            )
        barycentricity = sum(dists.values())
        if attr is not None:
            G.nodes[v][attr] = barycentricity
        if barycentricity < smallest:
            smallest = barycentricity
            barycenter_vertices = [v]
        elif barycentricity == smallest:
            barycenter_vertices.append(v)
    return barycenter_vertices

# Algorithm functions — A* shortest path
from franken_networkx._fnx import (
    astar_path as _raw_astar_path,
    astar_path_length as _raw_astar_path_length,
    shortest_simple_paths as _raw_shortest_simple_paths,
)


def _translate_astar_no_path(exc, source, target):
    """br-astarnop: the Rust astar_path binding surfaces
    ``ValueError('No path between <s> and <t>.')`` on disconnected
    inputs. nx raises ``NetworkXNoPath('Node <t> not reachable from
    <s>')``. Normalize to nx's exact class + wording so drop-in
    ``except nx.NetworkXNoPath`` keeps working.
    """
    if isinstance(exc, ValueError) and "No path" in str(exc):
        return NetworkXNoPath(f"Node {target} not reachable from {source}")
    return None


def _astar_path_inproc(G, source, target, heuristic=None, weight="weight", *, cutoff=None):
    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")

    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")

    if heuristic is None:
        def heuristic(u, v):
            return 0

    weight_fn = _weight_function(G, weight)
    G_succ = G._adj

    c = _itertools.count()
    queue = [(0, next(c), source, 0, None)]
    enqueued = {}
    explored = {}

    while queue:
        _, __, curnode, dist, parent = _heappop(queue)

        if curnode == target:
            path = [curnode]
            node = parent
            while node is not None:
                path.append(node)
                node = explored[node]
            path.reverse()
            return path

        if curnode in explored:
            if explored[curnode] is None:
                continue
            qcost, h = enqueued[curnode]
            if qcost < dist:
                continue

        explored[curnode] = parent

        for neighbor, w in G_succ[curnode].items():
            cost = weight_fn(curnode, neighbor, w)
            if cost is None:
                continue
            ncost = dist + cost
            if neighbor in enqueued:
                qcost, h = enqueued[neighbor]
                if qcost <= ncost:
                    continue
            else:
                h = heuristic(neighbor, target)

            if cutoff and ncost + h > cutoff:
                continue

            enqueued[neighbor] = ncost, h
            _heappush(queue, (ncost + h, next(c), neighbor, ncost, curnode))

    raise NetworkXNoPath(f"Node {target} not reachable from {source}")


def _astar_path_length_inproc(
    G, source, target, heuristic=None, weight="weight", *, cutoff=None
):
    if source not in G or target not in G:
        msg = f"Either source {source} or target {target} is not in G"
        raise NodeNotFound(msg)

    weight_fn = _weight_function(G, weight)
    path = _astar_path_inproc(
        G, source, target, heuristic=heuristic, weight=weight, cutoff=cutoff
    )
    return sum(weight_fn(u, v, G[u][v]) for u, v in zip(path[:-1], path[1:]))


def astar_path(G, source, target, heuristic=None, weight="weight", *, cutoff=None):
    """Return the shortest path from ``source`` to ``target`` via A* search.

    ``heuristic(u, v)`` should be admissible (never overestimate). If omitted,
    A* degenerates to Dijkstra. Mirrors ``networkx.astar_path``; raises
    ``NetworkXNoPath`` if no path exists.
    """
    # br-r37-c1-phy2p: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-yx0sh: validate source/target membership up front with nx's
    # exact wording. The native _raw_astar_path otherwise leaks a repr-quoted
    # message ("Source 'x' is not in G") while nx emits the unquoted
    # "Source x is not in G" (source checked first, then target). The wrapper
    # below only translates the ValueError no-path case, not NodeNotFound.
    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")
    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")
    # br-r37-c1-bzio2: the Rust _raw_astar_path honours edge weights via
    # edge_weight_or_default (verified parity vs nx on weighted graphs);
    # the previous unconditional ``_graph_has_nonunit_weight`` gate was
    # overly defensive and forced a ~50 ms Python edge scan per call on
    # BA5000. Now we only delegate for the cases the Rust impl genuinely
    # can't handle: callable/non-string ``weight``, ``cutoff``, or any
    # edge with a finite negative weight (A* requires non-negative
    # weights to remain optimal). The negative-weight scan reuses the
    # native O(|E|) helper landed in br-r37-c1-644fx.
    # br-r37-c1-astar-strw: also delegate when edge values at
    # ``weight`` key are non-numeric (str / list / dict) — Rust
    # silently treats them as 1.0; nx propagates a TypeError on the
    # natural ``+`` accumulation.  Same defect family as
    # br-r37-c1-vi0zo on dijkstra/bellman_ford.
    # br-r37-c1-kp1va: the Rust _raw_astar_path kernel is now generic over
    # GraphView and the PyO3 binding dispatches DiGraph/MultiDiGraph to their
    # directed projection (GraphView::neighbors_iter yields successors), so
    # directed A* runs natively and respects edge direction — the prior
    # ``G.is_directed()`` delegation (br-r37-c1-astdir) is removed.
    if _should_delegate_astar_to_networkx(weight, cutoff):
        return _astar_path_inproc(
            G,
            source,
            target,
            heuristic=heuristic,
            weight=weight,
            cutoff=cutoff,
        )
    # br-cc-mgdijkstra-dir: DIRECTED multigraph A* PATH -> collapse to the simple
    # min-weight DiGraph + recurse. Directed edges(keys,data) preserves out-adjacency
    # order so the collapsed A* explores identically -> byte-identical path.
    if G.is_directed() and G.is_multigraph() and isinstance(weight, str):
        _simple, _delegate = _multigraph_collapse_min_weight(G, weight)
        if _delegate:
            return _astar_path_inproc(
                G,
                source,
                target,
                heuristic=heuristic,
                weight=weight,
                cutoff=cutoff,
            )
        return astar_path(
            _simple, source, target, heuristic=heuristic, weight=weight, cutoff=cutoff
        )
    # br-r37-c1-0x9pd: A* reads edge weights from inner.AttrMap, so
    # post-creation Python mutations (G[u][v]['weight']=v) need to be
    # synced first — same architectural fix as br-r37-c1-sjf4t for
    # dijkstra/bellman-ford/floyd-warshall.
    # br-r37-c1-astgate: sync ONCE, and only run the O(|E|) weight scans when
    # the graph carries the weight attribute (see astar_path_length).
    # br-r37-c1-syncedgeonly: A* reads only EDGE weights, never node attrs, so
    # use the edge-only sync. The full sync's unconditional O(N) node-attr
    # rebuild (no node-dirty guard) was ~38% of a single-pair astar_path call
    # (cProfile: _fnx_sync_attrs_to_inner 0.088s of 0.231s); the edge-only
    # variant is edges_dirty-guarded and a no-op on an unmutated graph.
    # br-r37-c1-ixp5q: reuse dijkstra's cached, single-pass, sync-free
    # weight-validity gate (has_negative/nonfinite/nonnumeric over edge_py_attrs,
    # memoized by the revision token in vars(G)) instead of three separate
    # uncached O(|E|) scans. cProfile of weighted single-pair astar showed those
    # scans were ~1.78ms of pure overhead while the native kernel (~1.05ms) is
    # already at nx parity (~1.10ms) -> astar was 2.6x slower than nx; the cached
    # gate makes repeat calls on a graph free -> parity. (nan-weighted edges now
    # delegate to nx, matching dijkstra — strictly more correct than the old
    # silent native run on an unordered-comparison weight.)
    route = _dijkstra_weight_route(G, weight)
    if route == "networkx":
        return _astar_path_inproc(
            G,
            source,
            target,
            heuristic=heuristic,
            weight=weight,
            cutoff=cutoff,
        )
    # Kernel reads edge weights from inner core; push post-creation Python
    # mutations (edges_dirty-guarded, no-op on an unmutated graph).
    _sync_rust_edge_attrs(G, edge_only=True)
    try:
        return _raw_astar_path(
            G,
            source,
            target,
            heuristic=heuristic,
            weight=weight,
            check_rows=route == "rows",
        )
    except _WeightRowsUnverified:
        pass
    except ValueError as exc:
        translated = _translate_astar_no_path(exc, source, target)
        if translated is not None:
            raise translated from exc
        raise
    return _rerun_with_weight_scan(
        astar_path, G, source, target, heuristic=heuristic, weight=weight, cutoff=cutoff
    )


def astar_path_length(
    G, source, target, heuristic=None, weight="weight", *, cutoff=None
):
    """Return the shortest path length from ``source`` to ``target`` via A* search.

    ``heuristic(u, v)`` should be admissible. Mirrors ``networkx.astar_path_length``;
    raises ``NetworkXNoPath`` if no path exists.
    """
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-bzio2: same gate update as astar_path.
    # br-r37-c1-astar-strw: non-numeric weight delegation (sibling).
    # br-r37-c1-kp1va: directed A* now runs natively (see astar_path).
    if _should_delegate_astar_to_networkx(weight, cutoff):
        return _astar_path_length_inproc(
            G,
            source,
            target,
            heuristic=heuristic,
            weight=weight,
            cutoff=cutoff,
        )
    # br-cc-mgdijkstra: multigraph A* length -> collapse parallels to the simple
    # min-weight graph (nx uses min weight per pair) + fast simple A* kernel. A*
    # LENGTH is order-independent (unlike the path), so this is byte-exact. The
    # helper's validation delegates non-numeric / negative / +inf, matching A*'s
    # own weight-validity scans.
    if G.is_multigraph() and isinstance(weight, str):
        _simple, _delegate = _multigraph_collapse_min_weight(G, weight)
        if _delegate:
            return _astar_path_length_inproc(
                G,
                source,
                target,
                heuristic=heuristic,
                weight=weight,
                cutoff=cutoff,
            )
        return astar_path_length(
            _simple, source, target, heuristic=heuristic, weight=weight, cutoff=cutoff
        )
    # br-r37-c1-astgate: sync inner ONCE, then only run the O(|E|) negative/
    # inf/nonnumeric weight scans when the graph actually carries the weight
    # attribute. Each scan previously re-synced (4x redundant sync) and ran
    # unconditionally even on unweighted graphs -- ~2.4ms of pure overhead on a
    # single-pair A* whose native search is ~0.05ms (45x slower than nx -> 7.4x).
    # br-r37-c1-0x9pd: see astar_path.
    # br-r37-c1-syncedgeonly: edge-only sync (reads edge weights, not node attrs).
    # br-r37-c1-ixp5q: cached single-pass weight-validity gate (see
    # astar_path) replacing three uncached O(|E|) scans -> parity on repeat calls.
    if _should_delegate_dijkstra_to_networkx(G, weight):
        return _astar_path_length_inproc(
            G,
            source,
            target,
            heuristic=heuristic,
            weight=weight,
            cutoff=cutoff,
        )
    _sync_rust_edge_attrs(G, edge_only=True)
    # br-r37-c1-tm1tq: nx pre-checks ``source not in G or target not in G``
    # and raises a single combined-message NodeNotFound rather than
    # the per-side message that ``astar_path``'s translator returns
    # ('Target ... is not in G').  Mirror nx's exact wording so users
    # who match on the message string are not broken.
    if source not in G or target not in G:
        msg = f"Either source {source} or target {target} is not in G"
        raise NodeNotFound(msg)
    try:
        result, extra = _raw_astar_path_length(
            G, source, target, heuristic=heuristic, weight=weight
        )
    except ValueError as exc:
        translated = _translate_astar_no_path(exc, source, target)
        if translated is not None:
            raise translated from exc
        raise
    # br-r37-c1-astarlen-int / yo37g: nx returns int when every chosen-path edge weight is
    # int (sum-of-ints stays int); the Rust binding accumulates in f64. The length binding
    # avoids the old SECOND A* search (the 0.50x cost): for SIMPLE graphs it returns the
    # all-int flag computed in Rust (``extra`` is a bool); for multigraphs it returns the
    # chosen path so we int-check via G.get_edge_data here. ``isinstance(v, int)`` counts
    # bool as int (bool is an int subclass; nx accumulates True + True as 2).
    if isinstance(extra, bool):
        if extra and isinstance(result, float) and result.is_integer():
            return int(result)
        return result
    if isinstance(weight, str) and isinstance(result, float) and result.is_integer():
        all_int = True
        for u, v in zip(extra, extra[1:]):
            attrs = G.get_edge_data(u, v, default={}) or {}
            value = attrs.get(weight, 1)
            if not isinstance(value, int):
                all_int = False
                break
        if all_int:
            return int(result)
    return result


import heapq as _heapq
import itertools as _itertools


class _ShortestSimplePathBuffer:
    __slots__ = ("paths", "sortedpaths", "counter")

    def __init__(self):
        self.paths = set()
        self.sortedpaths = []
        self.counter = _itertools.count()

    def __len__(self):
        return len(self.sortedpaths)

    def push(self, cost, path):
        hashable_path = tuple(path)
        if hashable_path not in self.paths:
            _heapq.heappush(self.sortedpaths, (cost, next(self.counter), path))
            self.paths.add(hashable_path)

    def pop(self):
        (_cost, _num, path) = _heapq.heappop(self.sortedpaths)
        self.paths.remove(tuple(path))
        return path


def _ssp_bidirectional_pred_succ(G, source, target, ignore_nodes=None, ignore_edges=None):
    if ignore_nodes and (source in ignore_nodes or target in ignore_nodes):
        raise NetworkXNoPath(f"No path between {source} and {target}.")
    if target == source:
        return ({target: None}, {source: None}, source)

    if G.is_directed():
        Gpred = G.predecessors
        Gsucc = G.successors
    else:
        Gpred = G.neighbors
        Gsucc = G.neighbors

    if ignore_nodes:
        def filter_iter(nodes):
            def iterate(v):
                for w in nodes(v):
                    if w not in ignore_nodes:
                        yield w
            return iterate

        Gpred = filter_iter(Gpred)
        Gsucc = filter_iter(Gsucc)

    if ignore_edges:
        if G.is_directed():
            def filter_pred_iter(pred_iter):
                def iterate(v):
                    for w in pred_iter(v):
                        if (w, v) not in ignore_edges:
                            yield w
                return iterate

            def filter_succ_iter(succ_iter):
                def iterate(v):
                    for w in succ_iter(v):
                        if (v, w) not in ignore_edges:
                            yield w
                return iterate

            Gpred = filter_pred_iter(Gpred)
            Gsucc = filter_succ_iter(Gsucc)
        else:
            def filter_iter(nodes):
                def iterate(v):
                    for w in nodes(v):
                        if (v, w) not in ignore_edges and (w, v) not in ignore_edges:
                            yield w
                return iterate

            Gpred = filter_iter(Gpred)
            Gsucc = filter_iter(Gsucc)

    pred = {source: None}
    succ = {target: None}
    forward_fringe = [source]
    reverse_fringe = [target]

    while forward_fringe and reverse_fringe:
        if len(forward_fringe) <= len(reverse_fringe):
            this_level = forward_fringe
            forward_fringe = []
            for v in this_level:
                for w in Gsucc(v):
                    if w not in pred:
                        forward_fringe.append(w)
                        pred[w] = v
                    if w in succ:
                        return pred, succ, w
        else:
            this_level = reverse_fringe
            reverse_fringe = []
            for v in this_level:
                for w in Gpred(v):
                    if w not in succ:
                        succ[w] = v
                        reverse_fringe.append(w)
                    if w in pred:
                        return pred, succ, w

    raise NetworkXNoPath(f"No path between {source} and {target}.")


def _ssp_bidirectional_shortest_path(
    G, source, target, ignore_nodes=None, ignore_edges=None, weight=None
):
    pred, succ, w = _ssp_bidirectional_pred_succ(
        G, source, target, ignore_nodes, ignore_edges
    )
    path = []
    while w is not None:
        path.append(w)
        w = succ[w]
    w = pred[path[0]]
    while w is not None:
        path.insert(0, w)
        w = pred[w]
    return len(path), path


def _ssp_bidirectional_dijkstra(
    G, source, target, weight="weight", ignore_nodes=None, ignore_edges=None
):
    if ignore_nodes and (source in ignore_nodes or target in ignore_nodes):
        raise NetworkXNoPath(f"No path between {source} and {target}.")
    if source == target:
        if source not in G:
            raise NodeNotFound(f"Node {source} not in graph")
        return (0, [source])

    if G.is_directed():
        Gpred = G.predecessors
        Gsucc = G.successors
    else:
        Gpred = G.neighbors
        Gsucc = G.neighbors

    if ignore_nodes:
        def filter_iter(nodes):
            def iterate(v):
                for w in nodes(v):
                    if w not in ignore_nodes:
                        yield w
            return iterate

        Gpred = filter_iter(Gpred)
        Gsucc = filter_iter(Gsucc)

    if ignore_edges:
        if G.is_directed():
            def filter_pred_iter(pred_iter):
                def iterate(v):
                    for w in pred_iter(v):
                        if (w, v) not in ignore_edges:
                            yield w
                return iterate

            def filter_succ_iter(succ_iter):
                def iterate(v):
                    for w in succ_iter(v):
                        if (v, w) not in ignore_edges:
                            yield w
                return iterate

            Gpred = filter_pred_iter(Gpred)
            Gsucc = filter_succ_iter(Gsucc)
        else:
            def filter_iter(nodes):
                def iterate(v):
                    for w in nodes(v):
                        if (v, w) not in ignore_edges and (w, v) not in ignore_edges:
                            yield w
                return iterate

            Gpred = filter_iter(Gpred)
            Gsucc = filter_iter(Gsucc)

    wt = _weight_function(G, weight)
    dists = [{}, {}]
    paths = [{source: [source]}, {target: [target]}]
    fringe = [[], []]
    seen = [{source: 0}, {target: 0}]
    c = _itertools.count()
    _heapq.heappush(fringe[0], (0, next(c), source))
    _heapq.heappush(fringe[1], (0, next(c), target))
    neighs = [Gsucc, Gpred]
    finaldist = None
    finalpath = []
    dir_idx = 1
    while fringe[0] and fringe[1]:
        dir_idx = 1 - dir_idx
        (dist, _, v) = _heapq.heappop(fringe[dir_idx])
        if v in dists[dir_idx]:
            continue
        dists[dir_idx][v] = dist
        if v in dists[1 - dir_idx]:
            return (finaldist, finalpath)

        for w in neighs[dir_idx](v):
            if dir_idx == 0:
                minweight = wt(v, w, G.get_edge_data(v, w))
            else:
                minweight = wt(w, v, G.get_edge_data(w, v))
            if minweight is None:
                continue
            vwLength = dists[dir_idx][v] + minweight

            if w in dists[dir_idx]:
                if vwLength < dists[dir_idx][w]:
                    raise ValueError("Contradictory paths found: negative weights?")
            elif w not in seen[dir_idx] or vwLength < seen[dir_idx][w]:
                seen[dir_idx][w] = vwLength
                _heapq.heappush(fringe[dir_idx], (vwLength, next(c), w))
                paths[dir_idx][w] = paths[dir_idx][v] + [w]
                if w in seen[0] and w in seen[1]:
                    totaldist = seen[0][w] + seen[1][w]
                    if finalpath == [] or finaldist > totaldist:
                        finaldist = totaldist
                        revpath = paths[1][w][:]
                        revpath.reverse()
                        finalpath = paths[0][w] + revpath[1:]
    raise NetworkXNoPath(f"No path between {source} and {target}.")


def _shortest_simple_paths_fallback_generator(G, source, target, weight):
    if source not in G:
        raise NodeNotFound(f"source node {source} not in graph")
    if target not in G:
        raise NodeNotFound(f"target node {target} not in graph")

    if weight is None:
        length_func = len
        shortest_path_func = _ssp_bidirectional_shortest_path
    else:
        wt = _weight_function(G, weight)

        def length_func(path):
            return sum(
                wt(u, v, G.get_edge_data(u, v)) for (u, v) in zip(path, path[1:])
            )

        shortest_path_func = _ssp_bidirectional_dijkstra

    listA = []
    listB = _ShortestSimplePathBuffer()
    prev_path = None
    while True:
        if not prev_path:
            length, path = shortest_path_func(G, source, target, weight=weight)
            listB.push(length, path)
        else:
            ignore_nodes = set()
            ignore_edges = set()
            for i in range(1, len(prev_path)):
                root = prev_path[:i]
                root_length = length_func(root)
                for path in listA:
                    if path[:i] == root:
                        ignore_edges.add((path[i - 1], path[i]))
                try:
                    length, spur = shortest_path_func(
                        G,
                        root[-1],
                        target,
                        ignore_nodes=ignore_nodes,
                        ignore_edges=ignore_edges,
                        weight=weight,
                    )
                    path = root[:-1] + spur
                    listB.push(root_length + length, path)
                except NetworkXNoPath:
                    pass
                ignore_nodes.add(root[-1])

        if listB:
            path = listB.pop()
            yield path
            listA.append(path)
            prev_path = path
        else:
            break


def shortest_simple_paths(G, source, target, weight=None):
    """Yield simple paths from source to target in increasing length order.

    Returns a true generator for simple fnx graphs, matching nx's lazy contract
    while avoiding the old full fnx->nx conversion fallback.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")

    return _shortest_simple_paths_fallback_generator(G, source, target, weight)

# Algorithm functions — approximation
from franken_networkx._fnx import (
    clique_removal as _raw_clique_removal,
    maximal_independent_set as _raw_maximal_independent_set,
    large_clique_size as _raw_large_clique_size,
    max_clique as _raw_max_clique,
    maximum_independent_set as _raw_maximum_independent_set,
    min_weighted_vertex_cover as _raw_min_weighted_vertex_cover,
)












def maximal_independent_set(G, nodes=None, seed=None, *, backend=None, **backend_kwargs):
    """Return a maximal independent set of nodes in G.

    br-r37-c1-366al: the native ``_raw_maximal_independent_set`` kernel
    operates on canonical *string* node keys, so its
    ``seed.choice(list(available))`` over a string-hashed set picks a
    different index than nx's choice over the original Python node
    objects — yielding a valid but DIFFERENT maximal independent set for
    many seed/graph combinations (a parity break that the small
    path-graph tests never caught).  nx's algorithm
    (``networkx/algorithms/mis.py``) is short and its only
    parity-critical state is ordinary CPython ``set``/``list`` objects of
    the node values, so run it verbatim in-process on the fnx graph's
    real Python node objects.  This is byte-exact with nx for every
    hashable node type and folds in nx's ``@not_implemented_for(
    'directed')`` guard, ``@py_random_state`` seed handling, the
    self-loop ``NetworkXUnfeasible`` path, and nx's set-repr error
    wording with no extra reformatting.
    """
    G = _coerce_arg_to_fnx_graph(G)
    _validate_backend_dispatch_keywords(
        "maximal_independent_set", backend, backend_kwargs
    )

    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    # Match nx's @py_random_state(2): None/`random` -> the global instance,
    # int -> random.Random(int), random.Random -> itself, anything else
    # (e.g. a float / NaN) -> ValueError.
    seed = _create_py_random_state(seed)

    # Touch adjacency lazily (only the seed nodes plus each chosen node), the
    # same access pattern as nx — a full G.adjacency() snapshot is ~2x slower
    # here because it materialises every node's neighbours, most of which the
    # algorithm never reads. ``G[v]`` is the adjacency view (== nx's
    # ``G.adj[v]``); the node objects are the graph's real Python keys so every
    # CPython set built from them iterates exactly as nx's does.
    node_list = list(G)
    node_set = set(node_list)

    if not nodes:
        nodes = {seed.choice(node_list)}
    else:
        nodes = set(nodes)
    if not nodes.issubset(node_set):
        raise NetworkXUnfeasible(f"{nodes} is not a subset of the nodes of G")
    # br-cc-mis-neighbors: nx's algorithm reads adjacency as ``G[v]`` (a live
    # AtlasView). On fnx that routes through the pure-Python row-keydict layer
    # (a fresh view object + keydict rebuild per access — the 0.58x gap, since
    # the algorithm is otherwise byte-for-byte nx for seed parity). The
    # algorithm only needs the neighbour KEYS and uses them exclusively in
    # order-independent set ops, so read them via the native ``G.neighbors``
    # (one PyO3 call, cached node objects, self-loops included) — byte-exact
    # with nx, skips the keydict machinery.
    neighbors = set.union(*[set(G.neighbors(v)) for v in nodes])
    if set.intersection(neighbors, nodes):
        raise NetworkXUnfeasible(f"{nodes} is not an independent set of G")
    indep_nodes = list(nodes)
    available_nodes = node_set.difference(neighbors.union(nodes))
    while available_nodes:
        node = seed.choice(list(available_nodes))
        indep_nodes.append(node)
        # Materialise the neighbour keys to a LIST before difference_update:
        # feeding the raw ``neighbors`` iterator perturbs the set's internal
        # layout vs nx's ``list(G[node]) + [node]``, which (via list()
        # ordering of the shrinking available set) changes a later
        # seed.choice pick and breaks byte-exactness.
        available_nodes.difference_update(list(G.neighbors(node)) + [node])
    return indep_nodes


_maximal_independent_set_impl = maximal_independent_set


def spanner(G, stretch, weight=None, seed=None):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``.

    br-r37-c1-spnr-validate: nx raises NetworkXNotImplemented on
    multigraph and ValueError("math domain error") on empty graph
    (from internal ``log(0)``).  fnx's Rust binding silently
    produced a regular Graph for both cases.  Pre-validate to
    match nx's contracts.

    Validation order matches nx:
      1. stretch < 1 → ValueError("stretch must be at least 1")
         (delegated to Rust binding for valid graphs)
      2. multigraph → NetworkXNotImplemented
      3. empty graph + valid stretch → ValueError("math domain
         error") from log(0) leak
    """
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-spnr-order: nx applies @not_implemented_for("directed")
    # and @not_implemented_for("multigraph") decorators BEFORE the
    # function body's stretch validation. Wrong-type input therefore
    # raises NetworkXNotImplemented regardless of stretch value.
    # The previous comment ("nx checks stretch FIRST") was incorrect
    # — verified against nx source.
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if not isinstance(stretch, (int, float)) or stretch < 1:
        raise ValueError("stretch must be at least 1")
    if G.number_of_nodes() == 0:
        raise ValueError("math domain error")
    return _spanner_inproc(G, stretch, weight, _create_py_random_state(seed))


def _spanner_inproc(G, stretch, weight, seed):
    """networkx's Baswana-Sen spanner, step for step, over plain dicts.

    nro4w.7: the native kernel (br-r37-c1-va1lb) built a valid spanner but
    not networkx's: its random draws and tie-breaks differ, so the same seed
    gave different edges. This follows networkx's sparsifiers.py exactly:

    - the residual graph is networkx's ``G.copy()`` (adjacency order of the
      copy, not of G) held as a dict of dicts, so its node and neighbour
      iteration is networkx's;
    - edge weights are networkx's unique tie-breakers, ``(id(u), id(v))`` or
      ``(w, id(u), id(v))`` with (u, v) oriented as ``G.edges()`` yields it;
    - one ``seed.random()`` per center of ``set(clustering.values())``, and
      the size-limit retry, in networkx's order;
    - the spanner's edges are added in the order networkx adds them.

    Ties break on ``id``, so the result equals networkx's whenever both see
    the same node objects (always for small ints); that is networkx's own
    reproducibility contract.
    """
    import math

    k = (stretch + 1) // 2
    nodes = list(G)
    # The tie-breakers are ids, so they must be ids of objects that stay alive
    # for the whole call: fnx may hand out a fresh int object per iteration,
    # whose id could be reused and collide. One snapshot's objects serve.
    canonical = {node: node for node in nodes}
    radj = {node: {} for node in nodes}
    for u, nbrs in G.adj.items():
        for v in nbrs:
            radj[u][v] = None
            radj[v][u] = None
    if weight:
        for u, v, data in G.edges(data=True):
            radj[u][v] = radj[v][u] = (data[weight], id(canonical[u]), id(canonical[v]))
    else:
        for u, v in G.edges():
            radj[u][v] = radj[v][u] = (id(canonical[u]), id(canonical[v]))

    added = []

    def add_to_spanner(u, v):
        added.append((u, v, radj[u][v][0]) if weight else (u, v))

    def lightest_edge_dicts(clustering, node):
        neighbor_of = {}
        weight_of = {}
        for neighbor, edge_weight in radj[node].items():
            center = clustering[neighbor]
            if center not in weight_of or edge_weight < weight_of[center]:
                neighbor_of[center] = neighbor
                weight_of[center] = edge_weight
        return neighbor_of, weight_of

    def remove_edge(u, v):
        del radj[u][v]
        if u != v:
            del radj[v][u]

    clustering = {v: v for v in nodes}
    sample_prob = math.pow(len(nodes), -1 / k)
    size_limit = 2 * math.pow(len(nodes), 1 + 1 / k)
    i = 0
    while i < k - 1:
        sampled_centers = set()
        for center in set(clustering.values()):
            if seed.random() < sample_prob:
                sampled_centers.add(center)
        edges_to_add = set()
        edges_to_remove = set()
        new_clustering = {}
        for v in radj:
            if clustering[v] in sampled_centers:
                continue
            neighbor_of, weight_of = lightest_edge_dicts(clustering, v)
            neighboring_sampled_centers = set(weight_of.keys()) & sampled_centers
            if not neighboring_sampled_centers:
                for neighbor in neighbor_of.values():
                    edges_to_add.add((v, neighbor))
                for neighbor in radj[v]:
                    edges_to_remove.add((v, neighbor))
            else:
                closest_center = min(neighboring_sampled_centers, key=weight_of.get)
                closest_center_weight = weight_of[closest_center]
                edges_to_add.add((v, neighbor_of[closest_center]))
                new_clustering[v] = closest_center
                for center, edge_weight in weight_of.items():
                    if edge_weight < closest_center_weight:
                        edges_to_add.add((v, neighbor_of[center]))
                for neighbor in radj[v]:
                    nbr_cluster = clustering[neighbor]
                    if (
                        nbr_cluster == closest_center
                        or weight_of[nbr_cluster] < closest_center_weight
                    ):
                        edges_to_remove.add((v, neighbor))
        if len(edges_to_add) > size_limit:
            continue
        i = i + 1
        for u, v in edges_to_add:
            add_to_spanner(u, v)
        for u, v in edges_to_remove:
            if u in radj and v in radj[u]:
                remove_edge(u, v)
        for node, center in clustering.items():
            if center in sampled_centers:
                new_clustering[node] = center
        clustering = new_clustering
        for u in radj:
            for v in list(radj[u]):
                if clustering[u] == clustering[v]:
                    remove_edge(u, v)
        for v in list(radj):
            if v not in clustering:
                for nbr in list(radj[v]):
                    remove_edge(v, nbr)
                del radj[v]
    for v in radj:
        neighbor_of, _ = lightest_edge_dicts(clustering, v)
        for neighbor in neighbor_of.values():
            add_to_spanner(v, neighbor)

    H = Graph()
    H.add_nodes_from(nodes)
    if weight:
        H.add_edges_from((u, v, {weight: value}) for u, v, value in added)
    else:
        H.add_edges_from(added)
    return H


# Algorithm functions — tree recognition
from franken_networkx._fnx import (
    is_arborescence as _raw_is_arborescence,
    is_branching as _raw_is_branching,
)


def is_arborescence(G):
    """Return True if ``G`` is an arborescence.

    br-r37-c1-rg8jh: Python wrapper around the bare Rust binding so
    nx-typed inputs are coerced at the boundary.
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_arborescence(G)


def is_branching(G):
    """Return True if ``G`` is a branching (forest of in-arborescences).

    br-r37-c1-rg8jh: see is_arborescence.
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_is_branching(G)

# Algorithm functions — isolates
from franken_networkx._fnx import (
    is_isolate as _raw_is_isolate,
    isolates as _raw_isolates,
    number_of_isolates as _raw_number_of_isolates,
)


def number_of_isolates(G):
    """Return the number of isolated nodes (degree-0).

    br-r37-c1-0555d: nx-coerce wrapper.
    """
    G = _coerce_arg_to_fnx_graph(G)
    return _raw_number_of_isolates(G)


def isolates(G):
    """Yield isolated nodes (degree-0) of ``G``.

    Lazy generator matching nx's iterator contract (br-r37-c1-lby4x).
    The Rust binding returns a materialized list; wrapping with
    ``yield from`` makes the returned object a true ``generator`` so
    ``isinstance(result, types.GeneratorType)`` matches and short-circuit
    callers like ``next(isolates(huge_graph))`` don't pay for the full
    materialisation.
    """
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    yield from _raw_isolates(G)


def is_isolate(G, n):
    """Return True iff ``n`` is an isolate (degree-0 node) of *G*.

    Second parameter renamed from the Rust binding's ``node`` to match
    networkx's public signature ``is_isolate(G, n)``.
    """
    # br-r37-c1-isol-exc: nx implements ``is_isolate`` as
    # ``G.degree(n) == 0`` so a missing node bubbles up
    # ``NetworkXError("Node {n} is not in the graph.")`` from the
    # degree view.  fnx's Rust binding raised ``NodeNotFound``
    # (sibling-of NetworkXError, NOT a subclass), breaking
    # ``except NetworkXError:`` callers that follow nx's contract.
    # Mirror nx's one-liner so the typed-error contract aligns.
    return G.degree(n) == 0

# Algorithm functions — boundary
from franken_networkx._fnx import (
    cut_size as _raw_cut_size,
    edge_boundary as _raw_edge_boundary,
    node_boundary_rows as _raw_node_boundary_rows,
    normalized_cut_size as _raw_normalized_cut_size,
)


def _coerce_nbunch(nbunch):
    """br-nbunchseq: Rust bindings expect Sequence input for nbunch.
    nx accepts any iterable (set, dict.keys(), generator, etc.). Coerce
    to list so drop-in code with ``cut_size(G, S={0,1})`` works.
    """
    if nbunch is None:
        return None
    if isinstance(nbunch, (list, tuple)):
        return nbunch
    return list(nbunch)


def cut_size(G, S, T=None, weight=None):
    """br-boundkw: ``G, S, T`` match nx; Rust binding used ``g, nbunch1, nbunch2``.

    br-r37-c1-f47su: nx returns int when the result is integer (always
    for unweighted, and when all relevant weights are int). The Rust
    binding always returns float. Coerce to int when input weights
    permit so isinstance(cut_size(G, S), int) checks match nx.
    """
    # br-r37-c1-eog89: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    if not G.is_multigraph() and (
        weight is None or not _graph_has_nonunit_weight(G, weight)
    ):
        S_nb = _coerce_nbunch(S)
        T_nb = _coerce_nbunch(T)
        raw = _raw_cut_size(G, S_nb, T_nb, weight=weight)
        if weight is None or _sp_edge_weights_all_int(G, weight):
            if isinstance(raw, float) and raw.is_integer():
                return int(raw)
        if raw != 0:
            return raw
        # br-r37-c1-rjgh0: a zero cut takes the path below. nx sums the crossing
        # edges from the int 0 - an empty cut is 0 - where the kernel's f64 sum
        # of nothing is -0.0.

    if T is None:
        T_eff = set(G) - set(S)
    else:
        T_eff = T
    edges = edge_boundary(G, S, T_eff, data=weight, default=1)
    if G.is_directed():
        edges = _itertools.chain(
            edges, edge_boundary(G, T_eff, S, data=weight, default=1)
        )
    if weight is None:
        return sum(1 for _ in edges)
    raw = sum(w for u, v, w in edges)
    if _sp_edge_weights_all_int(G, weight):
        if isinstance(raw, float) and raw.is_integer():
            return int(raw)
    return raw


def normalized_cut_size(G, S, T=None, weight=None):
    """br-boundkw: ``G, S, T`` match nx."""
    # br-r37-c1-eog89: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    if T is None:
        T = set(G) - set(S)
    num_cut_edges = cut_size(G, S, T=T, weight=weight)
    volume_S = volume(G, S, weight=weight)
    volume_T = volume(G, T, weight=weight)
    return num_cut_edges * ((1 / volume_S) + (1 / volume_T))


def node_boundary(G, nbunch1, nbunch2=None, *, backend=None, **backend_kwargs):
    """br-boundkw: ``G`` matches nx; Rust binding used ``g``.

    br-ndbndset: nx.node_boundary returns a set; the Rust binding
    returned a list. Callers doing set ops (``{...} == nb``,
    ``nb.issubset(...)``, ``nb & other``) silently broke. Coerce to
    set.
    """
    _validate_backend_dispatch_keywords("node_boundary", backend, backend_kwargs)
    # br-r37-c1-e861i: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-n4j4k: networkx's own set operations, whose result iterates in
    # an order they decide wherever hashes collide - nset1 grown in nbunch1
    # order, the rows chained in nset1's order into a grown set, then the set
    # difference (and &= set(nbunch2)) - over the native rows, chained in one
    # call where the graph has index rows.
    nset1 = {n for n in nbunch1 if n in G}
    rows = None
    if _raw_neighbors_dispatch(G) is not None:
        rows = _raw_node_boundary_rows(G, nset1)
    if rows is None:
        rows = _itertools.chain.from_iterable(G[v] for v in nset1)
    bdy = set(rows) - nset1
    if nbunch2 is not None:
        bdy &= set(nbunch2)
    return bdy


def edge_boundary(
    G, nbunch1, nbunch2=None, data=False, keys=False, default=None, *, backend=None, **backend_kwargs
):
    """Yield edges with at least one endpoint in ``nbunch1``.

    br-edgebounddata: nx.edge_boundary supports ``data``, ``keys``, and
    ``default`` kwargs to annotate each emitted edge with attribute
    data — fnx previously only accepted (nbunch1, nbunch2). Delegate
    to nx when any of the data/keys/default switches are non-default
    so the emitted tuples match exactly.

    _Generator function so the returned object is a true generator
    matching nx's contract (br-r37-c1-ohxpp).
    """
    _validate_backend_dispatch_keywords("edge_boundary", backend, backend_kwargs)
    # br-r37-c1-e861i: materialize SubgraphView first (view family).
    G = _coerce_arg_to_fnx_graph(G)
    nset1 = {n for n in nbunch1 if n in G}
    if not G.is_multigraph() and type(G) in (Graph, DiGraph):
        if data is False and nbunch2 is None:
            # br-r37-c1-ebneigh: the data=False boundary only needs the neighbor, but
            # `G.edges(nset1)` materializes the EdgeView (builds (u,v) tuples) — ~8x more
            # expensive than `G.neighbors` (see br-aspneigh). Emit (u,v) from G.neighbors:
            # an edge is in the boundary iff exactly one endpoint is in nset1, i.e. for
            # u in nset1 the neighbor v with v not in nset1 (the XOR below specializes to
            # that since u is always in nset1). SAME nset1-set x adjacency order, so
            # byte-identical to nx (verified 2000/2000 incl self-loops/directed/strings).
            # Build eagerly (cheaper than per-item generator yield) then yield from.
            # 0.78x -> ~1.7x. (nbunch2-given + data=True keep the EdgeView path below.)
            yield from [
                (u, v) for u in nset1 for v in G.neighbors(u) if v not in nset1
            ]
            return
        if data is False and nbunch2 is not None:
            # NetworkX first turns nbunch1 into a set, so list(nset1) preserves
            # that observable row order while avoiding the Python EdgeView pass.
            yield from _raw_edge_boundary(G, list(nset1), _coerce_nbunch(nbunch2))
            return
        edges = G.edges(nset1, data=data, default=default)
        if nbunch2 is None:
            for edge in edges:
                if (edge[0] in nset1) ^ (edge[1] in nset1):
                    yield edge
            return
        nset2 = set(nbunch2)
        for edge in edges:
            if (edge[0] in nset1 and edge[1] in nset2) or (
                edge[1] in nset1 and edge[0] in nset2
            ):
                yield edge
        return

    if G.is_multigraph():
        edges = G.edges(nset1, data=data, keys=keys, default=default)
    else:
        edges = G.edges(nset1, data=data, default=default)
    if nbunch2 is None:
        for edge in edges:
            if (edge[0] in nset1) ^ (edge[1] in nset1):
                yield edge
        return
    nset2 = set(nbunch2)
    for edge in edges:
        if (edge[0] in nset1 and edge[1] in nset2) or (
            edge[1] in nset1 and edge[0] in nset2
        ):
            yield edge


def volume(G, S, weight=None):
    """Return the volume of a set of nodes."""
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        return sum(d for v, d in G.out_degree(S, weight=weight))
    return sum(d for v, d in G.degree(S, weight=weight))


def edge_expansion(G, S, T=None, weight=None):
    """Return the edge expansion between two node sets."""
    if T is None and weight is None and hasattr(S, "__len__") and len(S) > 0:
        G = _coerce_arg_to_fnx_graph(G)
        s_nodes = list(S)
        try:
            unique_s = set(s_nodes)
        except TypeError:
            unique_s = None
        if (
            unique_s is not None
            and len(unique_s) == len(s_nodes)
            and not G.is_multigraph()
            and not G.is_directed()
            and len(s_nodes) < G.number_of_nodes()
            and all(node in G for node in s_nodes)
        ):
            return _raw_edge_expansion(G, s_nodes)
    if T is None:
        T = list(set(G) - set(S))
    num_cut_edges = cut_size(G, S, T=T, weight=weight)
    denominator = min(len(S), len(T))
    if denominator == 0:
        raise ZeroDivisionError("division by zero")
    return num_cut_edges / denominator


def mixing_expansion(G, S, T=None, weight=None):
    """Return the mixing expansion between two node sets."""
    num_cut_edges = cut_size(G, S, T=T, weight=weight)
    num_total_edges = G.number_of_edges()
    return num_cut_edges / (2 * num_total_edges)


def node_expansion(G, S):
    """Return the node expansion of a set."""
    if hasattr(S, "__len__") and len(S) > 0:
        G = _coerce_arg_to_fnx_graph(G)
        s_nodes = list(S)
        if not G.is_multigraph() and not G.is_directed():
            return _raw_node_expansion(G, s_nodes)
    neighborhood = set(_itertools.chain.from_iterable(G.neighbors(v) for v in S))
    return len(neighborhood) / len(S)


def boundary_expansion(G, S):
    """Return the boundary expansion of a set."""
    return len(node_boundary(G, S)) / len(S)


def conductance(G, S, T=None, weight=None):
    """Return the conductance between two node sets."""
    if T is None:
        T = list(set(G) - set(S))
    num_cut_edges = cut_size(G, S, T, weight=weight)
    volume_s = volume(G, S, weight=weight)
    volume_t = volume(G, T, weight=weight)
    denominator = min(volume_s, volume_t)
    if denominator == 0:
        raise ZeroDivisionError("division by zero")
    return num_cut_edges / denominator
