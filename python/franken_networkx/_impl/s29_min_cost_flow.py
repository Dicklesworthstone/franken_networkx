

def min_cost_flow(G, demand="demand", capacity="capacity", weight="weight"):
    """Find minimum cost flow satisfying node demands.

    Uses the successive shortest paths algorithm with Bellman-Ford.

    Each node may have a ``demand`` attribute:
    - Negative demand = supply (source, has excess flow to send)
    - Positive demand = demand (sink, needs flow)
    - Zero or missing = transshipment node

    Parameters
    ----------
    G : DiGraph
    demand : str, optional
        Node attribute for supply/demand. Default ``'demand'``.
    capacity : str, optional
        Edge attribute for capacity. Default ``'capacity'``.
    weight : str, optional
        Edge attribute for cost per unit flow. Default ``'weight'``.

    Returns
    -------
    dict of dicts
        ``flowDict[u][v]`` is the optimal flow on edge (u, v).

    Raises
    ------
    NetworkXUnfeasible
        If no feasible flow exists.
    """
    # br-r37-c1-3qt4m: nx's @not_implemented_for('undirected')
    # decorator raises NetworkXNotImplemented, not NetworkXError.
    # min_cost_flow_cost and capacity_scaling both call this so the
    # fix propagates to the whole family.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    nodes = list(G.nodes())
    n = len(nodes)
    if n == 0:
        # br-r37-c1-mcfempty: nx's network_simplex raises
        # NetworkXError("graph has no nodes") on empty input via the
        # validation block in _validate_network_simplex_inputs; fnx's
        # SSP path silently returned {}.  Match nx's contract.  The
        # downstream min_cost_flow_cost / max_flow_min_cost both
        # route here so the empty-graph contract propagates.
        raise NetworkXError("graph has no nodes")

    # br-r37-c1-mcf-negcap: the SSP solver below silently treats
    # negative capacities as 0, masking nx's NetworkXUnfeasible
    # contract.  network_simplex (sibling) already validates via
    # _validate_network_simplex_inputs and matches nx exactly; the
    # SSP path was the gap, which propagated through min_cost_flow_
    # cost and max_flow_min_cost (both route here).
    # br-r37-c1-8foqi: read edge attrs via the native bulk reader (same
    # node-major order as ``G.edges(data=True)`` so the first-offending-edge
    # message is unchanged) instead of the per-edge AdjacencyView view.
    _new_edges = getattr(G, "_native_edges_with_data", None)
    _edge_iter = _new_edges() if _new_edges is not None else G.edges(data=True)
    for u, v, edge_attrs in _edge_iter:
        if isinstance(edge_attrs, dict):
            edge_capacity = float(edge_attrs.get(capacity, float("inf")))
            if edge_capacity < 0:
                raise NetworkXUnfeasible(
                    f"edge {(u, v)!r} has negative capacity"
                )

    # Extract demands via one bulk ``nodes(data=True)`` native read (node order
    # preserved) instead of a per-node ``G.nodes[node]`` AdjacencyView lookup.
    node_demand = {}
    for node, attrs in G.nodes(data=True):
        if isinstance(attrs, dict):
            node_demand[node] = float(attrs.get(demand, 0))
        else:
            node_demand[node] = 0.0

    # br-r37-c1-74xas: nx raises NetworkXError("node X has infinite
    # demand") at this stage (not NetworkXUnfeasible). Detect inf
    # demand explicitly so the exception type + message match nx.
    for node, d in node_demand.items():
        if _math.isinf(d):
            raise NetworkXError(f"node {node!r} has infinite demand")

    # Check feasibility: sum of demands must be zero
    # br-r37-c1-74xas: nx's exact wording is "total node demand is not
    # zero" — match it (still NetworkXUnfeasible).
    total_demand = sum(node_demand.values())
    if abs(total_demand) > 1e-10:
        raise NetworkXUnfeasible("total node demand is not zero")

    # br-r37-c1-t6gfk: the successive-shortest-paths solver below relaxes
    # Bellman-Ford over O(n^2) (u, succ) pairs calling G.successors /
    # G.get_edge_data INSIDE the hot loop — 50-96x slower than nx with real
    # demands (n=600: ~3.5s vs ~37ms). Replace it with the network-simplex
    # algorithm run IN-PROCESS on the fnx graph (no fnx->nx conversion): it
    # extracts the graph to flat arrays once, then pivots on arrays. The flow
    # conformance contract is cost-only (test_flow_conformance_matrix asserts
    # equal cost / balanced total flow, NOT an exact flow dict — fnx's SSP
    # already produced different valid optima than nx on some inputs), and the
    # simplex is cost-exact by construction. The validation above already
    # enforced fnx's error contracts (empty graph, negative capacity, infinite
    # / non-zero total demand); the simplex additionally surfaces nx's
    # NetworkXUnbounded for negative-cost infinite-capacity cycles.
    # br-r37-c1-8foqi: for simple DiGraphs, run fnx's in-process port of the
    # network-simplex over a fast pre-extracting shim (``_FastG``) that caches
    # the node/edge data via fnx's native bulk readers — the ported pivots are
    # byte-identical to nx's but the graph I/O no longer pays the per-element
    # AdjacencyView read tax, bringing min_cost_flow from ~2x slower than nx to
    # parity. Multigraphs keep the upstream ``__wrapped__`` path (the shim does
    # not carry edge keys).
    if not G.is_multigraph():
        from ._network_simplex_native import (
            _FastG as _FastNSG,
            network_simplex as _native_network_simplex,
        )

        _fastg = _FastNSG(G)
        _cost, flow = _native_network_simplex(
            _fastg, demand=demand, capacity=capacity, weight=weight
        )
        if _mcf_inputs_all_integral(G, demand, capacity, weight, _fastg=_fastg):
            flow = _coerce_flow_dict_to_int(flow)
        return flow

    flow, _handled = _min_cost_flow_network_simplex_nx(
        G, demand=demand, capacity=capacity, weight=weight
    )
    if _handled:
        if _mcf_inputs_all_integral(G, demand, capacity, weight):
            flow = _coerce_flow_dict_to_int(flow)
        return flow

    # Initialize flow dict  (successive-shortest-paths fallback)
    flow = {u: {} for u in nodes}
    for u, v in G.edges():
        flow.setdefault(u, {})[v] = 0

    # Build residual graph and run successive shortest paths
    # NetworkX convention: negative demand = supply, positive = demand
    sources = [n for n in nodes if node_demand[n] < 0]
    sinks = [n for n in nodes if node_demand[n] > 0]
    remaining_supply = {n: -node_demand[n] for n in sources}
    remaining_demand = {n: node_demand[n] for n in sinks}

    # Successive shortest paths: augment along shortest cost path
    for _ in range(n * n):  # upper bound on iterations
        # Find shortest path from any source with remaining supply
        # to any sink with remaining demand using Bellman-Ford on residual
        best_path = None
        best_cost = float("inf")
        best_source = None
        best_sink = None

        for source in sources:
            if remaining_supply.get(source, 0) <= 1e-10:
                continue

            # BFS/Bellman-Ford on residual graph
            dist = {source: 0.0}
            pred = {source: None}
            # Relaxation
            for _ in range(n):
                updated = False
                for u in nodes:
                    if u not in dist:
                        continue
                    # Forward edges
                    if hasattr(G, "successors"):
                        succs = list(G.successors(u))
                    else:
                        succs = list(G.neighbors(u))
                    for v in succs:
                        data = G.get_edge_data(u, v)
                        if not isinstance(data, dict):
                            continue
                        cap = float(data.get(capacity, float("inf")))
                        current_flow = flow.get(u, {}).get(v, 0)
                        residual_cap = cap - current_flow
                        if residual_cap > 1e-10:
                            edge_cost = float(data.get(weight, 0))
                            new_dist = dist[u] + edge_cost
                            if v not in dist or new_dist < dist[v] - 1e-10:
                                dist[v] = new_dist
                                pred[v] = (u, "forward")
                                updated = True
                    # Backward edges (reverse flow)
                    if hasattr(G, "predecessors"):
                        preds_list = list(G.predecessors(u))
                    else:
                        preds_list = []
                    for v in preds_list:
                        current_flow = flow.get(v, {}).get(u, 0)
                        if current_flow > 1e-10:
                            data = G.get_edge_data(v, u)
                            edge_cost = (
                                -float(data.get(weight, 0))
                                if isinstance(data, dict)
                                else 0.0
                            )
                            new_dist = dist[u] + edge_cost
                            if v not in dist or new_dist < dist[v] - 1e-10:
                                dist[v] = new_dist
                                pred[v] = (u, "backward")
                                updated = True
                if not updated:
                    break

            # Check reachable sinks
            for sink in sinks:
                if sink in dist and remaining_demand.get(sink, 0) > 1e-10:
                    if dist[sink] < best_cost:
                        best_cost = dist[sink]
                        best_path = pred
                        best_source = source
                        best_sink = sink

        if best_path is None:
            break

        # Find bottleneck along the path
        path_nodes = []
        current = best_sink
        while current is not None:
            path_nodes.append(current)
            p = best_path.get(current)
            if p is None:
                break
            current = p[0] if p else None
        path_nodes.reverse()

        bottleneck = min(remaining_supply[best_source], remaining_demand[best_sink])
        # Also check edge capacities along path
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            info = best_path.get(v)
            if info and info[1] == "forward":
                data = G.get_edge_data(u, v)
                cap = (
                    float(data.get(capacity, float("inf")))
                    if isinstance(data, dict)
                    else float("inf")
                )
                residual = cap - flow.get(u, {}).get(v, 0)
                bottleneck = min(bottleneck, residual)
            elif info and info[1] == "backward":
                bottleneck = min(bottleneck, flow.get(v, {}).get(u, 0))

        if bottleneck <= 1e-10:
            break

        # Augment flow along path
        for i in range(len(path_nodes) - 1):
            u, v = path_nodes[i], path_nodes[i + 1]
            info = best_path.get(v)
            if info and info[1] == "forward":
                flow.setdefault(u, {})[v] = flow.get(u, {}).get(v, 0) + bottleneck
            elif info and info[1] == "backward":
                flow.setdefault(v, {})[u] = flow.get(v, {}).get(u, 0) - bottleneck

        remaining_supply[best_source] -= bottleneck
        remaining_demand[best_sink] -= bottleneck

    # Check if all demands are satisfied
    for source in sources:
        if remaining_supply.get(source, 0) > 1e-10:
            raise NetworkXUnfeasible("no flow satisfies all node demands")
    for sink in sinks:
        if remaining_demand.get(sink, 0) > 1e-10:
            raise NetworkXUnfeasible("no flow satisfies all node demands")

    # br-mcfint: preserve int flow values when every input is int
    # (nx contract).
    if _mcf_inputs_all_integral(G, demand, capacity, weight):
        flow = _coerce_flow_dict_to_int(flow)
    return flow


def min_cost_flow_cost(G, demand="demand", capacity="capacity", weight="weight"):
    """Return the cost of the minimum cost flow.

    Parameters
    ----------
    G : DiGraph
    demand, capacity, weight : str, optional

    Returns
    -------
    float
    """
    flow = min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)
    # nx's min_cost_flow_cost is network_simplex(G)[0] (br-r37-c1-6soms).
    return _network_simplex_cost(G, flow, weight)


def max_flow_min_cost(G, s, t, capacity="capacity", weight="weight"):
    """Find a maximum flow of minimum cost from *s* to *t*.

    First finds maximum flow value, then finds the min-cost flow
    achieving that value.

    Parameters
    ----------
    G : DiGraph
    s, t : node
        Source and sink.
    capacity, weight : str, optional

    Returns
    -------
    dict of dicts
        Flow dictionary.

    br-mfmcsign: by nx convention, a negative demand means the node
    *supplies* that much flow. A source thus has ``demand=-maxFlow``
    and a sink has ``demand=+maxFlow``. The previous implementation
    used the reversed signs (``{s: max_val, t: -max_val}``), which
    inverted supply/demand — the solver then tried to push flow from
    t to s and raised NetworkXUnfeasible on every valid input.

    br-r37-c1-b4n6b: H is ``DiGraph(G)``, as in networkx, not a copy of G -
    an undirected G becomes two arcs per edge instead of reaching
    min_cost_flow undirected and raising NetworkXNotImplemented.
    """
    max_val = maximum_flow_value(G, s, t, capacity=capacity)
    H = DiGraph(G)
    H.add_node(s, demand=-max_val)
    H.add_node(t, demand=max_val)
    return min_cost_flow(H, capacity=capacity, weight=weight)


def capacity_scaling(
    G,
    demand="demand",
    capacity="capacity",
    weight="weight",
    heap=_BINARY_HEAP_DEFAULT,
):
    """Find minimum cost flow using capacity scaling.

    This is an alias for ``min_cost_flow`` — the successive shortest
    paths implementation provides the same optimality guarantees.

    Parameters
    ----------
    G : DiGraph
    demand, capacity, weight : str, optional
    heap : class, optional
        Heap class. Default ``networkx.utils.heaps.BinaryHeap`` so the
        introspectable signature matches nx exactly. The fnx
        implementation manages its own heap; the kwarg is accepted
        for API drop-in compatibility.

    Returns
    -------
    tuple
        ``(flowCost, flowDict)`` matching NetworkX's return signature.
    """
    # br-r37-c1-3qt4m: nx's @not_implemented_for('undirected') on
    # capacity_scaling raises NetworkXNotImplemented before the
    # network_simplex empty-graph check.  Match the ordering.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-kpaki: nx's capacity_scaling uses its own path that
    # returns (0, {}) on empty input — it does NOT raise the
    # network_simplex "graph has no nodes" error min_cost_flow now
    # surfaces.  Match nx by short-circuiting before delegating.
    if len(G) == 0:
        return 0, {}
    try:
        flow = min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)
    except NetworkXUnfeasible as exc:
        # br-r37-c1-8lsax: nx's capacity_scaling and network_simplex
        # raise NetworkXUnfeasible with DIFFERENT wording — capacity_
        # scaling uses "No flow satisfying all demands." (cap+period),
        # network_simplex uses "no flow satisfies all node demands".
        # min_cost_flow shares the network_simplex wording; translate
        # at this boundary so caller message-matching code aligns.
        msg = str(exc)
        if msg == "no flow satisfies all node demands":
            raise NetworkXUnfeasible("No flow satisfying all demands.") from None
        raise
    # br-r37-c1-33ctq: nx's capacity_scaling adds flow * weight to the int 0 only
    # where flow moves, so an edge carrying none never makes the cost a float
    # (cost_of_flow scores every edge, and 0 * 1.5 is 0.0).
    if G.is_multigraph():
        cost = sum(
            flow[u][v][key] * data.get(weight, 0)
            for u, v, key, data in G.edges(keys=True, data=True)
            if flow[u][v][key]
        )
    else:
        cost = sum(
            flow[u][v] * data.get(weight, 0)
            for u, v, data in G.edges(data=True)
            if flow[u][v]
        )
    return cost, flow


def _validate_network_simplex_inputs(G, demand, capacity, weight):
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    if len(G) == 0:
        raise NetworkXError("graph has no nodes")

    total_demand = 0.0
    for node in G:
        node_attrs = G.nodes[node] if hasattr(G.nodes, "__getitem__") else {}
        if not isinstance(node_attrs, dict):
            continue
        node_demand = float(node_attrs.get(demand, 0))
        if _math.isinf(node_demand):
            raise NetworkXError(f"node {node!r} has infinite demand")
        total_demand += node_demand

    for u, v, edge_attrs in G.edges(data=True):
        if not isinstance(edge_attrs, dict):
            continue
        edge_weight = float(edge_attrs.get(weight, 0))
        if _math.isinf(edge_weight):
            raise NetworkXError(f"edge {(u, v)!r} has infinite weight")

        edge_capacity = float(edge_attrs.get(capacity, float("inf")))
        if edge_capacity < 0:
            raise NetworkXUnfeasible(f"edge {(u, v)!r} has negative capacity")

    if abs(total_demand) > 1e-10:
        raise NetworkXUnfeasible("total node demand is not zero")


def network_simplex(G, demand="demand", capacity="capacity", weight="weight"):
    """Find minimum cost flow using the network simplex algorithm.

    Returns both the cost and the flow dictionary.

    Parameters
    ----------
    G : DiGraph
    demand, capacity, weight : str, optional

    Returns
    -------
    (cost, flowDict) : tuple
    """
    _validate_network_simplex_inputs(G, demand, capacity, weight)
    flow = min_cost_flow(G, demand=demand, capacity=capacity, weight=weight)
    return (_network_simplex_cost(G, flow, weight), flow)


def _network_simplex_cost(G, flow, weight):
    """networkx's network_simplex cost (br-r37-c1-6soms): sum(w * x) over the
    non-selfloop edges, from the int 0, then w * x for each negative-weight
    selfloop (saturated); a non-negative selfloop carries no flow and adds
    nothing. cost_of_flow scores every edge, and 0 * 1.5 is 0.0."""
    if G.is_multigraph():
        rows = [
            (u, v, flow[u][v][key] if isinstance(flow[u][v], dict) else flow[u][v], data)
            for u, v, key, data in G.edges(keys=True, data=True)
        ]
    else:
        rows = [(u, v, flow[u][v], data) for u, v, data in G.edges(data=True)]
    cost = sum(data.get(weight, 0) * x for u, v, x, data in rows if u != v)
    for u, v, x, data in rows:
        if u == v and data.get(weight, 0) < 0:
            cost += data.get(weight, 0) * x
    return cost


def flow_hierarchy(G, weight=None):
    """Return the flow hierarchy of a directed graph.

    The flow hierarchy is the fraction of edges not in a cycle.

    Parameters
    ----------
    G : DiGraph
    weight : str or None, optional

    Returns
    -------
    float
        Value in [0, 1]. 1 means no edges are in cycles (DAG).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.number_of_edges() == 0:
        raise NetworkXError("flow_hierarchy not applicable to empty graphs")
    if not G.is_directed():
        # br-r37-c1-4elbw: nx raises NetworkXError with the exact text
        # "G must be a digraph in flow_hierarchy". The Rust binding
        # raised "flow_hierarchy requires a DiGraph", which broke
        # drop-in code matching nx's wording.
        raise NetworkXError("G must be a digraph in flow_hierarchy")
    if weight is not None:
        return _flow_hierarchy_weighted_scc_fold(G, weight)
    return _fnx.flow_hierarchy_rust(G)


def _flow_hierarchy_weighted_scc_fold(G, weight):
    # br-flowhier (cc): nx computes the cyclic weight as
    # ``sum(G.subgraph(c).size(weight) for c in strongly_connected_components(G))``,
    # i.e. the total weight of edges whose endpoints lie in the SAME SCC. fnx's
    # ``subgraph(view).size(weight)`` runs the filtered-view degree machinery, and
    # building one such view PER SCC made flow_hierarchy(weighted) ~22x slower than nx
    # (subgraph-in-loop bomb, br-r37-c1-wfoee family). Replace it with a single O(V+E)
    # pass: tag each node with its SCC id once, then sum the weights of intra-SCC edges
    # directly. Same value as the per-SCC subgraph sizes (a self-loop sits in its node's
    # own SCC, counted once, matching subgraph.size); float summation order differs by
    # ~ULP, well within the round(.,9)/approx parity the conformance suite asserts.
    total_weight = G.size(weight=weight)
    scc_id = {}
    for index, component in enumerate(strongly_connected_components(G)):
        for node in component:
            scc_id[node] = index
    cyclic_weight = sum(
        w for u, v, w in G.edges(data=weight, default=1) if scc_id[u] == scc_id[v]
    )
    return 1 - cyclic_weight / total_weight


# ---------------------------------------------------------------------------
# Triad analysis (br-a59)
# ---------------------------------------------------------------------------

# 16 triad types in MAN notation
_TRIAD_TYPES = [
    "003",
    "012",
    "102",
    "021D",
    "021U",
    "021C",
    "111D",
    "111U",
    "030T",
    "030C",
    "201",
    "120D",
    "120U",
    "120C",
    "210",
    "300",
]


_TRICODES = (
    1, 2, 2, 3, 2, 4, 6, 8, 2, 6, 5, 7, 3, 8, 7, 11,
    2, 6, 4, 8, 5, 9, 9, 13, 6, 10, 9, 14, 7, 14, 12, 15,
    2, 5, 6, 7, 6, 9, 10, 14, 4, 9, 9, 12, 8, 13, 14, 15,
    3, 7, 8, 11, 7, 12, 14, 15, 8, 14, 13, 15, 11, 15, 15, 16,
)
_TRICODE_TO_NAME = {i: _TRIAD_TYPES[code - 1] for i, code in enumerate(_TRICODES)}


def _tricode(G, v, u, w):
    combos = ((v, u, 1), (u, v, 2), (v, w, 4), (w, v, 8), (u, w, 16), (w, u, 32))
    return sum(x for u, v, x in combos if v in G[u])


def _triadic_census_nodelist(G, nodelist):
    nodeset = set(G.nbunch_iter(nodelist))
    if nodelist is not None and len(nodelist) != len(nodeset):
        raise ValueError("nodelist includes duplicate nodes or nodes not in G")
    N = len(G)
    Nnot = N - len(nodeset)
    m = {n: i for i, n in enumerate(nodeset)}
    if Nnot:
        not_nodeset = set(G.nodes) - nodeset
        m.update((n, i + N) for i, n in enumerate(not_nodeset))
    nbrs = {n: G.pred[n].keys() | G.succ[n].keys() for n in G}
    dbl_nbrs = {n: G.pred[n].keys() & G.succ[n].keys() for n in G}
    if Nnot:
        sgl_nbrs = {n: G.pred[n].keys() ^ G.succ[n].keys() for n in not_nodeset}
        sgl = sum(1 for n in not_nodeset for nbr in sgl_nbrs[n] if nbr not in nodeset)
        sgl_edges_outside = sgl // 2
        dbl = sum(1 for n in not_nodeset for nbr in dbl_nbrs[n] if nbr not in nodeset)
        dbl_edges_outside = dbl // 2
    census = {name: 0 for name in _TRIAD_TYPES}
    for v in nodeset:
        vnbrs = nbrs[v]
        dbl_vnbrs = dbl_nbrs[v]
        if Nnot:
            sgl_unbrs_bdy = sgl_unbrs_out = dbl_unbrs_bdy = dbl_unbrs_out = 0
        for u in vnbrs:
            if m[u] <= m[v]:
                continue
            unbrs = nbrs[u]
            neighbors = (vnbrs | unbrs) - {u, v}
            for w in neighbors:
                if m[u] < m[w] or (m[v] < m[w] < m[u] and v not in nbrs[w]):
                    code = _tricode(G, v, u, w)
                    census[_TRICODE_TO_NAME[code]] += 1
            if u in dbl_vnbrs:
                census["102"] += N - len(neighbors) - 2
            else:
                census["012"] += N - len(neighbors) - 2
            if Nnot and u not in nodeset:
                sgl_unbrs = sgl_nbrs[u]
                sgl_unbrs_bdy += len(sgl_unbrs & vnbrs - nodeset)
                sgl_unbrs_out += len(sgl_unbrs - vnbrs - nodeset)
                dbl_unbrs = dbl_nbrs[u]
                dbl_unbrs_bdy += len(dbl_unbrs & vnbrs - nodeset)
                dbl_unbrs_out += len(dbl_unbrs - vnbrs - nodeset)
        if Nnot:
            census["012"] += sgl_edges_outside - (sgl_unbrs_out + sgl_unbrs_bdy // 2)
            census["102"] += dbl_edges_outside - (dbl_unbrs_out + dbl_unbrs_bdy // 2)
    total_triangles = (N * (N - 1) * (N - 2)) // 6
    triangles_without_nodeset = (Nnot * (Nnot - 1) * (Nnot - 2)) // 6
    total_census = total_triangles - triangles_without_nodeset
    census["003"] = total_census - sum(census.values())
    return census


def triadic_census(G, nodelist=None):
    """Count the frequency of each of the 16 triad types.

    Parameters
    ----------
    G : DiGraph
    nodelist : optional list of nodes
        Restrict the triad _count to triads containing at least one
        node from ``nodelist`` (nx parity — br-triadnode). When
        ``nodelist`` is None, counts all triads in the graph.

    Returns
    -------
    dict
        ``{triad_type: _count}`` for all 16 types.
    """
    # br-r37-c1-n7rgh: nx is @not_implemented_for('undirected') and
    # raises NetworkXNotImplemented; previously fnx raised
    # NetworkXError which is the parent class but not catchable as
    # NetworkXNotImplemented.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if nodelist is None:
        raw = _fnx.triadic_census_rust(G)
        # br-r37-c1-v9m7b: nx returns the 16 triad types in canonical
        # MAN-notation order (matching the _TRIAD_TYPES constant); the
        # Rust binding yields them in arbitrary internal order. Reorder.
        return {t: raw.get(t, 0) for t in _TRIAD_TYPES}
    return _triadic_census_nodelist(G, nodelist)


def all_triads(G):
    """Generate all triads (3-node subgraphs) of a directed graph.

    Parameters
    ----------
    G : DiGraph

    Yields
    ------
    DiGraph
        Each yielded graph is a 3-node subgraph.

    br-r37-c1-cfcls: coerce to fnx for consistent return type.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    G = _coerce_arg_to_fnx_graph(G)

    nodes = list(G.nodes())
    n = len(nodes)
    if G.is_multigraph():
        # br-r37-c1-sx0id: nx yields G.subgraph(triplet).copy() - for a
        # MultiDiGraph that is a MultiDiGraph with its keyed parallel edges.
        for triplet in _itertools.combinations(nodes, 3):
            yield G.subgraph(triplet).copy()
        return

    # br-ctcg-triaddirect: `G.subgraph([i, j, k]).copy()` per triad routes
    # through fnx's filtered-view + materialize-copy machinery, ~7x slower than
    # networkx (1960ms vs 271ms on gnm(40, 200)). Snapshot G's node/edge/graph
    # attributes once and build each 3-node induced DiGraph directly with
    # add_nodes_from / add_edges_from — same nodes, induced edges, and
    # node/edge/graph attribute copies as the subgraph copy, without the
    # per-triad view overhead. 1960ms -> 171ms (faster than nx).
    graph_attrs = dict(G.graph)
    node_attrs = {node: dict(G.nodes[node]) for node in nodes}
    out_adj = {node: {nbr: dict(data) for nbr, data in G[node].items()} for node in nodes}

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                triple = (nodes[i], nodes[j], nodes[k])
                H = DiGraph()
                H.graph.update(graph_attrs)
                H.add_nodes_from((t, dict(node_attrs[t])) for t in triple)
                # br-r37-c1-sx0id: the subgraph copy nx yields keeps selfloops
                # and lists each node's successors in G's adjacency order.
                H.add_edges_from(
                    [
                        (a, b, dict(data))
                        for a in triple
                        for b, data in out_adj[a].items()
                        if b in triple
                    ]
                )
                yield H


def triad_type(G):
    """Return the triad type of a 3-node directed graph.

    Parameters
    ----------
    G : DiGraph
        Must have exactly 3 nodes.

    Returns
    -------
    str
        One of the 16 MAN triad type codes.

    br-r37-c1-n7rgh: nx is @not_implemented_for('undirected'); add
    the type guard before the 3-node check so undirected inputs
    raise NetworkXNotImplemented (matching nx) instead of the
    Rust binding's NetworkXError.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if not is_triad(G):
        # br-r37-c1-39gx2: nx raises ``NetworkXAlgorithmError`` (not
        # NetworkXError) with a specific 'G is not a triad (order-3
        # DiGraph)' message — distinct exception class lets users
        # catch algorithmic invariants separately from generic errors.
        raise NetworkXAlgorithmError("G is not a triad (order-3 DiGraph)")
    if G.is_multigraph():
        return _triad_type_by_edge_count(G)
    nodes = list(G.nodes())
    return _fnx.triad_type_rust(G, nodes[0], nodes[1], nodes[2])


def _triad_type_by_edge_count(G):
    """networkx's triad_type, verbatim (br-r37-c1-sx0id): it classifies by
    len(G.edges()), which on a MultiDiGraph counts parallel edges - so a
    doubled arc reads as a mutual pair ('102') and more than six arcs give
    None. The native kernel reads the simple adjacency and cannot say that."""
    edges = list(G.edges())
    num_edges = len(edges)
    if num_edges == 0:
        return "003"
    if num_edges == 1:
        return "012"
    if num_edges == 2:
        e1, e2 = edges
        if set(e1) == set(e2):
            return "102"
        if e1[0] == e2[0]:
            return "021D"
        if e1[1] == e2[1]:
            return "021U"
        if e1[1] == e2[0] or e2[1] == e1[0]:
            return "021C"
    elif num_edges == 3:
        for e1, e2, e3 in _itertools.permutations(edges, 3):
            if set(e1) == set(e2):
                if e3[0] in e1:
                    return "111U"
                return "111D"
            if set(e1).symmetric_difference(set(e2)) == set(e3):
                if {e1[0], e2[0], e3[0]} == {e1[0], e2[0], e3[0]} == set(G.nodes()):
                    return "030C"
                return "030T"
    elif num_edges == 4:
        for e1, e2, e3, e4 in _itertools.permutations(edges, 4):
            if set(e1) == set(e2):
                if set(e3) == set(e4):
                    return "201"
                if {e3[0]} == {e4[0]} == set(e3).intersection(set(e4)):
                    return "120D"
                if {e3[1]} == {e4[1]} == set(e3).intersection(set(e4)):
                    return "120U"
                if e3[1] == e4[0]:
                    return "120C"
    elif num_edges == 5:
        return "210"
    elif num_edges == 6:
        return "300"
    return None


def is_triad(G):
    """Return True if *G* is a valid triad (3-node directed graph)."""
    return (
        G.is_directed()
        and G.number_of_nodes() == 3
        and not any((node, node) in G.edges() for node in G.nodes())
    )


def triads_by_type(G):
    """Group all triads of *G* by their type.

    Returns
    -------
    collections.defaultdict
        ``{triad_type: [list of triad subgraphs]}`` — a defaultdict(list)
        so ``result[unknown_type]`` yields ``[]`` matching nx's contract.

    br-triadsempty: nx.triads_by_type only includes keys for types
    that actually appear in the graph. fnx pre-populated all 16 triad
    types with empty lists, so iterating items / checking membership
    would diverge (fnx yields 16 entries; nx yields only non-empty
    counts). Drop empty buckets to match nx's sparse output.

    br-r37-c1-3gqao: return defaultdict(list) (matching nx's container
    type) so callers indexing unknown triad types get [] not KeyError.
    """
    from collections import defaultdict as _defaultdict

    # br-r37-c1-sx0id: nx's loop - keys in first-occurrence order, and a triad
    # that is not a triad (a selfloop) raises from triad_type.
    out = _defaultdict(list)
    for triad in all_triads(G):
        out[triad_type(triad)].append(triad)
    return out


# ---------------------------------------------------------------------------
# Edge swapping & rewiring (br-eo5)
# ---------------------------------------------------------------------------


def _swap_degree_cdf(degrees):
    """networkx 3.6.1 ``utils.cumulative_distribution``, exactly (the swaps'
    RNG draws are only nx-identical if the CDF is bit-identical)."""
    cdf = [0.0]
    cumulative = 0.0
    for element in degrees:
        cumulative += element
        cdf.append(cumulative)
    return [element / cumulative for element in cdf]


def _swap_draw(n, cdf, rng):
    """networkx 3.6.1 ``utils.discrete_sequence(n, cdistribution=cdf, seed=rng)``:
    all ``n`` uniforms are drawn before any is mapped through the CDF."""
    uniforms = [rng.random() for _ in range(n)]
    return [_bisect.bisect_left(cdf, s) - 1 for s in uniforms]


def _edge_swap_networkx_exact(G, nswap, max_tries, seed, *, directed):
    """``networkx`` 3.6.1 ``double_edge_swap`` / ``directed_edge_swap``, step for step.

    br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.4: fnx used a different
    algorithm (uniform edge pick) documented as an "intentional divergence" but
    never owned in the upstream-divergence ledger, so the same seed produced a
    different graph than networkx (12 failures in networkx's own
    test_swap.py under NETWORKX_TEST_BACKEND). This is nx's algorithm with
    nx's RNG consumption: degree-weighted source choice via
    ``discrete_sequence`` over the degree CDF (degrees taken once, in node
    order), ``seed.choice`` over the CURRENT neighbour order, nx's skip rules
    (which do not count as tries in the undirected case) and nx's operation
    order. Neighbour lists are read from an insertion-ordered mirror that
    models nx's dict adjacency exactly, so an attempt never crosses into Rust;
    only accepted swaps touch ``G``, in nx's order, so ``G`` also ends with
    nx's adjacency order.
    """
    rng = _create_py_random_state(seed)
    keys, degrees = zip(*G.degree())
    cdf = _swap_degree_cdf(degrees)

    if directed:
        succ = {node: dict.fromkeys(G.succ[node]) for node in keys}
        tries = 0
        swapcount = 0
        while swapcount < nswap:
            start = keys[_swap_draw(1, cdf, rng)[0]]
            tries += 1
            if tries > max_tries:
                raise NetworkXAlgorithmError(
                    f"Maximum number of swap attempts ({tries}) exceeded "
                    f"before desired swaps achieved ({nswap})."
                )
            if not succ[start]:
                continue
            second = rng.choice(list(succ[start]))
            if start == second:
                continue
            if not succ[second]:
                continue
            third = rng.choice(list(succ[second]))
            if second == third:
                continue
            if not succ[third]:
                continue
            fourth = rng.choice(list(succ[third]))
            if third == fourth:
                continue
            if (
                third not in succ[start]
                and fourth not in succ[second]
                and second not in succ[third]
            ):
                for a, b in ((start, third), (third, second), (second, fourth)):
                    G.add_edge(a, b)
                    succ[a][b] = None
                for a, b in ((start, second), (second, third), (third, fourth)):
                    G.remove_edge(a, b)
                    del succ[a][b]
                swapcount += 1
        return G

    adj = {node: dict.fromkeys(G[node]) for node in keys}

    def _mirror_add(a, b):
        adj[a][b] = None
        adj[b][a] = None

    def _mirror_remove(a, b):
        del adj[a][b]
        if a != b:
            del adj[b][a]

    n = 0
    swapcount = 0
    while swapcount < nswap:
        ui, xi = _swap_draw(2, cdf, rng)
        if ui == xi:
            continue
        u = keys[ui]
        x = keys[xi]
        v = rng.choice(list(adj[u]))
        y = rng.choice(list(adj[x]))
        if v == y:
            continue
        if (x not in adj[u]) and (y not in adj[v]):
            G.add_edge(u, x)
            _mirror_add(u, x)
            G.add_edge(v, y)
            _mirror_add(v, y)
            G.remove_edge(u, v)
            _mirror_remove(u, v)
            G.remove_edge(x, y)
            _mirror_remove(x, y)
            swapcount += 1
        if n >= max_tries:
            raise NetworkXAlgorithmError(
                f"Maximum number of swap attempts ({n}) exceeded "
                f"before desired swaps achieved ({nswap})."
            )
        n += 1
    return G


def double_edge_swap(G, nswap=1, max_tries=100, seed=None):
    """Swap two edges while preserving the degree sequence.

    For each swap attempt, select edges (u,v) and (x,y) and replace
    with (u,x) and (v,y) if no self-loops or parallel edges result.

    Parameters
    ----------
    G : Graph
        Modified in place.
    nswap : int, optional
        Number of swaps to perform.
    max_tries : int, optional
        Maximum attempts per swap.
    seed : int or None, optional

    Returns
    -------
    G : Graph
        The modified graph.
    """
    # br-r37-c1-des-validate: nx raises on five precondition / runtime
    # cases; previously fnx silently returned G unchanged for all
    # five, which masked invalid input AND hid the
    # max_tries-exhausted state from callers (a real algorithm
    # signal — the graph topology refused the requested degree-
    # preserving rearrangement).
    # br-r37-c1-cdf1v: nx's @py_random_state resolves the seed before these.
    seed = _create_py_random_state(seed)
    if G.is_directed():
        raise NetworkXError(
            "double_edge_swap() not defined for directed graphs. "
            "Use directed_edge_swap instead."
        )
    if nswap > max_tries:
        raise NetworkXError("Number of swaps > number of tries allowed.")
    if len(G) < 4:
        raise NetworkXError("Graph has fewer than four nodes.")
    if G.number_of_edges() < 2:
        raise NetworkXError("Graph has fewer than 2 edges")

    # br-r37-c1-frbgb: via the nx dispatcher ``seed`` may already be a
    # ``random.Random``; ``create_py_random_state`` accepts every form nx does.
    return _edge_swap_networkx_exact(G, nswap, max_tries, seed, directed=False)


def directed_edge_swap(G, *, nswap=1, max_tries=100, seed=None):
    """Swap three-edge directed paths while preserving in/out degree sequences.

    As in networkx: pick a start node weighted by degree and walk a random
    path ``u→v→x→y``; if ``u→x``, ``x→v`` and ``v→y`` are all absent, replace
    the path's three edges with them.

    Parameters
    ----------
    G : DiGraph
        Modified in place.
    nswap : int, optional
    max_tries : int, optional
    seed : int or None, optional

    Returns
    -------
    G : DiGraph
    """
    # br-r37-c1-cdf1v: nx's @py_random_state resolves the seed first - before
    # @not_implemented_for, as its flattened argmap runs them - so a bad seed
    # raises ValueError on any graph.
    seed = _create_py_random_state(seed)
    # br-r37-c1-n7rgh: nx is @not_implemented_for('undirected') and
    # raises NetworkXNotImplemented (catchable via that subclass).
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # nx's preconditions, in nx's order.
    if nswap > max_tries:
        raise NetworkXError("Number of swaps > number of tries allowed.")
    if len(G) < 4:
        raise NetworkXError("DiGraph has fewer than four nodes.")
    if G.number_of_edges() < 3:
        raise NetworkXError("DiGraph has fewer than 3 edges")
    return _edge_swap_networkx_exact(G, nswap, max_tries, seed, directed=True)


# ---------------------------------------------------------------------------
# Graph predicates (br-5wd)
# ---------------------------------------------------------------------------


def is_valid_degree_sequence_erdos_gallai(deg_sequence):
    """Check if an integer sequence is a valid degree sequence (Erdos-Gallai).

    br-isokw: parameter name ``deg_sequence`` matches nx exactly so
    ``is_valid_degree_sequence_erdos_gallai(deg_sequence=[...])``
    kwarg-style drop-in calls work.

    The Erdos-Gallai theorem: a non-increasing sequence d_1 >= ... >= d_n
    is graphical iff sum(d_i) is even and for each k:
    sum(d_i, i=1..k) <= k*(k-1) + sum(min(d_i, k), i=k+1..n).
    """
    sequence = _make_list_of_ints(deg_sequence)
    seq = sorted(sequence, reverse=True)
    n = len(seq)
    if n == 0:
        return True
    if sum(seq) % 2 != 0:
        return False
    # br-egallai-linear: the old check was O(n^2) -- it recomputed
    # sum(seq[:k]) and sum(min(d, k) for d in seq[k:]) for EVERY k. Use prefix
    # sums plus a binary search for the (sorted-descending) crossover where the
    # degrees drop below k, so each Erdos-Gallai inequality is O(log n):
    #   sum(min(d, k) for d in seq[k:]) = (p - k) * k + sum(seq[p:])
    # with p = max(k, #{d : d >= k}). 27x on a 400-degree sequence (matches nx);
    # the boolean result is bit-identical to the previous code (verified across
    # thousands of graphical / non-graphical / edge-case sequences).
    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i + 1] = prefix[i] + seq[i]
    total = prefix[n]
    # br-r37-c1-egsweep (cc): ``m`` = count of degrees >= k, tracked with a single
    # descending pointer (seq is non-increasing, so the elements >= k are the prefix
    # seq[0..m-1]) — O(n) total instead of a per-k ``bisect`` (O(n log n)). AND break
    # at the Durfee corner: by Tripathi-Vijay the Erdos-Gallai inequalities only need
    # checking for k up to s = max{k : d_k >= k} (the h-index); once m < k every
    # remaining k holds automatically. For low-max-degree sequences s << n, so this
    # checks ~s rows not n — the default eg method was ~0.64x of nx (it looped all n).
    m = n
    for k in range(1, n + 1):
        while m > 0 and seq[m - 1] < k:
            m -= 1
        if m < k:
            break
        sum_min = (m - k) * k + (total - prefix[m])
        rhs = k * (k - 1) + sum_min
        if prefix[k] > rhs:
            return False
    return True


def is_valid_degree_sequence_havel_hakimi(deg_sequence):
    """Check if an integer sequence is a valid degree sequence (Havel-Hakimi).

    br-isokw: parameter name ``deg_sequence`` matches nx.

    Repeatedly removes the largest element d, subtracts 1 from the next
    d largest elements. If any become negative, not graphical.
    """
    # br-hhbucket: the old check re-sorted the whole list on EVERY reduction
    # step -- O(n^2 log n). Use the standard bucket method (nx's algorithm):
    # keep a count array num_degs[d] and reduce stubs in O(sum of degrees)
    # without re-sorting, plus the Zverovich-Zverovich early-accept. The
    # boolean result is bit-identical (verified over 5000+ sequences vs both
    # the old code and nx). N=1000: 1.66ms -> 0.14ms (12x; also faster than nx).
    deg = _make_list_of_ints(deg_sequence)
    p = len(deg)
    num_degs = [0] * p
    dmax, dmin, dsum, n = 0, p, 0, 0
    for d in deg:
        if d < 0 or d >= p:
            return False
        if d > 0:
            if d > dmax:
                dmax = d
            if d < dmin:
                dmin = d
            dsum += d
            n += 1
            num_degs[d] += 1
    if dsum % 2 or dsum > n * (n - 1):
        return False
    # Accept if no positive degrees or the ZZ condition holds.
    if n == 0 or 4 * dmin * n >= (dmax + dmin + 1) * (dmax + dmin + 1):
        return True
    modstubs = [0] * (dmax + 1)
    while n > 0:
        while num_degs[dmax] == 0:
            dmax -= 1
        if dmax > n - 1:
            return False
        num_degs[dmax] -= 1
        n -= 1
        mslen = 0
        k = dmax
        for _ in range(dmax):
            while num_degs[k] == 0:
                k -= 1
            num_degs[k] -= 1
            n -= 1
            if k > 1:
                modstubs[mslen] = k - 1
                mslen += 1
        for i in range(mslen):
            stub = modstubs[i]
            num_degs[stub] += 1
            n += 1
    return True


def is_valid_joint_degree(joint_degrees):
    """Check if a joint degree dictionary is realizable."""
    degree_count = {}
    for degree in joint_degrees:
        if degree > 0:
            degree_size = sum(joint_degrees[degree].values()) / degree
            if not degree_size.is_integer():
                return False
            degree_count[degree] = degree_size

    for degree_left in joint_degrees:
        for degree_right in joint_degrees[degree_left]:
            edge_count = joint_degrees[degree_left][degree_right]
            if not float(edge_count).is_integer():
                return False

            if (
                degree_left != degree_right
                and edge_count > degree_count[degree_left] * degree_count[degree_right]
            ):
                return False
            if degree_left == degree_right:
                if edge_count > degree_count[degree_left] * (
                    degree_count[degree_left] - 1
                ):
                    return False
                if edge_count % 2 != 0:
                    return False
    return True


def is_strongly_regular(G):
    """Check if *G* is strongly regular.

    A graph is strongly regular srg(v,k,λ,μ) if it is k-regular and
    every pair of adjacent vertices has exactly λ common neighbors,
    and every pair of non-adjacent vertices has exactly μ common neighbors.

    br-srgdiam: nx.is_strongly_regular uses ``is_distance_regular(G)
    and diameter(G) == 2`` — the diameter-2 requirement excludes
    complete graphs (K_n has diameter 1) and C_3 (=K_3). The Rust
    _fnx.is_strongly_regular_rust implementation missed this
    requirement and classified every K_n (n>=3) as strongly regular,
    plus C_3 as True where nx returns False. Also enforce nx's
    directed/multigraph rejection explicitly.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return is_distance_regular(G) and diameter(G) == 2


def is_at_free(G, *, backend=None, **backend_kwargs):
    """Check if *G* is asteroidal-triple-free (AT-free).

    An asteroidal triple is three nodes where between each pair there
    exists a path avoiding the neighborhood of the third.

    br-r37-c1-tqimg: nx is @not_implemented_for('directed',
    'multigraph').
    """
    _validate_backend_dispatch_keywords(
        "is_at_free",
        backend,
        backend_kwargs,
    )
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return _fnx.is_at_free_rust(G)


def is_d_separator(G, x, y, z):
    """Check if node set *z* d-separates *x* from *y* in a DAG (Rust)."""
    from franken_networkx._fnx import is_d_separator_rust as _rust_dsep

    # NetworkX's not_implemented_for decorator rejects undirected inputs
    # before it validates the node sets.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    # br-r37-c1-dsepscalar: nx accepts scalar nodes for x/y/z
    # (``is_d_separator(G, 0, 2, 1)``) and normalizes via
    # ``{x} if x in G else x``.  fnx's bare ``set(x)`` raised
    # ``TypeError: 'int' object is not iterable`` on scalar args.
    # nx also wraps the whole normalize+disjoint block in a
    # try/except TypeError that raises NodeNotFound — mirror that
    # so unhashable / non-iterable inputs get the right exception
    # type.  Follow nx's exact ordering so passing a list like
    # ``[1]`` for z surfaces NodeNotFound via the ``set & list``
    # TypeError (matches nx's strictness).
    try:
        x = {x} if x in G else x
        y = {y} if y in G else y
        z = {z} if z in G else z
        intersection = x & y or x & z or y & z
        if intersection:
            raise NetworkXError(
                f"The sets are not disjoint, with intersection {intersection}"
            )
        set_v = x | y | z
        if set_v - set(G.nodes):
            raise NodeNotFound(
                f"The node(s) {set_v - set(G.nodes)} are not found in G"
            )
    except TypeError:
        raise NodeNotFound(
            "One of x, y, or z is not a node or a set of nodes in G"
        )
    # br-r37-c1-iea1p: the native Bayes-ball kernel accepts cyclic digraphs,
    # but NetworkX rejects them after node-set validation.
    if not is_directed_acyclic_graph(G):
        raise NetworkXError("graph should be directed acyclic")
    return _rust_dsep(G, list(x), list(y), list(z))


def is_minimal_d_separator(G, x, y, z, *, included=None, restricted=None):
    """Check if *z* is a minimal d-separator of *x* and *y*.

    Matches networkx's keyword-only ``included`` and ``restricted``
    constraints from PEP 3102 / nx's API:

    - ``included``: subset of *z* that must remain in any minimal
      d-separator (not removable when shrinking).
    - ``restricted``: superset that *z* and any reduction must stay
      within.

    When either constraint is given fnx delegates to networkx for
    correctness; the standalone path keeps the simple O(|z|) reducer.
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # NetworkX checks the DAG contract before validating any node set or
    # included/restricted constraint.
    if not is_directed_acyclic_graph(G):
        raise NetworkXError("graph should be directed acyclic")

    if included is not None or restricted is not None:
        # br-cc-dsepinproc: the included/restricted form delegated via the full
        # O(V+E) fnx->nx conversion (~0.18x). Run nx's EXACT criteria algorithm
        # (van der Zander & Liskiewicz 2020) in-process on a local ancestral
        # snapshot, reusing the same Bayes-Ball _reachable_dsep as
        # find_minimal_d_separator. Returns a deterministic BOOL, byte-identical
        # to nx (0/425 adversarial incl. valid/perturbed/empty z + included +
        # restricted; error contracts match). Plain DiGraph only; others delegate.
        try:
            x = {x} if x in G else x
            y = {y} if y in G else y
            z = {z} if z in G else z
            inc = set() if included is None else ({included} if included in G else included)
            rest = set(G) if restricted is None else ({restricted} if restricted in G else restricted)
            nodes = set(G)
            missing = (x | y | inc | rest) - nodes
            if missing:
                raise NodeNotFound(f"The node(s) {missing} are not found in G")
        except TypeError:
            raise NodeNotFound(
                "One of x, y, z, included or restricted is not a node or set of nodes in G"
            )
        if not inc <= z:
            raise NetworkXError(
                f"Included nodes {inc} must be in proposed separating set z {x}"
            )
        if not z <= rest:
            raise NetworkXError(
                f"Separating set {z} must be contained in restricted set {rest}"
            )
        intersection = x & y or x & z or y & z
        if intersection:
            raise NetworkXError(
                f"The sets are not disjoint, with intersection {intersection}"
            )
        nodeset = x | y | inc
        anc = set(nodeset)
        for node in nodeset:
            anc |= ancestors(G, node)
        succ = {}
        for node, nbrs in G.adjacency():
            succ[node] = [v for v in nbrs if v in anc] if node in anc else []
        pred = {node: [] for node in anc}
        for u in anc:
            for v in succ.get(u, ()):
                pred[v].append(u)
        x_closure = _reachable_dsep(succ, pred, x, anc, z)
        if x_closure & y:
            return False
        if not (z <= anc):
            return False
        y_closure = _reachable_dsep(succ, pred, y, anc, z)
        if not ((z - inc) <= (x_closure & y_closure)):
            return False
        return True
    if not is_d_separator(G, x, y, z):
        return False
    # br-r37-c1-dsepscalar: normalize z the same way is_d_separator
    # does so the standalone reducer accepts scalar args.
    z = {z} if z in G else z
    z = set(z)
    for node in list(z):
        reduced = z - {node}
        if is_d_separator(G, x, y, reduced):
            return False
    return True


# ---------------------------------------------------------------------------
# Graph products (br-69m)
# ---------------------------------------------------------------------------


def corona_product(G, H):
    """Return the corona product of *G* and *H*.

    For each node v in G, add a copy of H and connect v to all nodes
    in that copy.

    Parameters
    ----------
    G, H : Graph

    Returns
    -------
    Graph
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    _validate_product_graph_types(G, H, allow_multigraph=True)
    G, H = _product_factors(G, H)

    # br-r37-c1-prodrooted: native fast path (simple, self-loop-free).
    # corona's result mixes G's original nodes with (g, h) tuples; the native
    # kernel builds that node table + the edge set in Rust (canonicalising each
    # product tuple once) instead of the per-edge Python construction. Same edge
    # set (parity tests canonicalise edges); H-multigraph / EDGE-attrs / self-loops
    # fall back to the Python build below.
    # br-r37-c1-prodnodeattr (cc): corona DROPS node attrs (both nx and the Python
    # fallback yield empty node dicts), so NODE attrs never affect the output — only
    # H's per-copy EDGE attrs need the Python path. Gate on EDGE attrs alone so a
    # node-attributed (edge-attr-free) corona goes native (byte-identical to nx,
    # which also drops the node attrs) instead of the ~5x-slower Python build.
    if (
        not H.is_directed()
        and not H.is_multigraph()
        and not _graph_has_any_edge_attrs(G)
        and not _graph_has_any_edge_attrs(H)
        and not number_of_selfloops(G)
        and not number_of_selfloops(H)
    ):
        _fast = _fnx.corona_product_fast(G, H)
        if _fast is not None:
            return _fast

    # br-r37-c1-prodedgeattr (cc): EDGE-attributed corona. Only H's edge attrs reach
    # the output (copied onto each G-node's H-block); G's edge attrs + all node attrs
    # are dropped. When both factors are simple Graphs and H's edge attrs are SCALAR
    # (pristine H edge mirror), the native kernel clones H's store attrs onto the
    # H-copy edges -> beats nx instead of the O(V_G*E_H) Python batch. None -> batch.
    if (
        type(G) is Graph
        and type(H) is Graph
        and not number_of_selfloops(G)
        and not number_of_selfloops(H)
    ):
        _corona_edge_native = getattr(_fnx, "corona_product_edge_attrs_fast", None)
        if _corona_edge_native is not None:
            _r = _corona_edge_native(G, H)
            if _r is not None:
                return _r

    P = _product_graph_class(G, H)()
    P.add_nodes_from(G.nodes())

    # br-r37-c1-prodbatch (cc): the native path above handles the no-attr case; the
    # attributed case bails here and paid a per-edge/node add_edge/add_node dispatch
    # over the O(V_G) G-edges + O(V_G*V_H) star edges + O(V_G*E_H) H-copy edges.
    # Batch each layer (per-G-node for the H-copy so the star-then-H-copy insertion
    # order is preserved) through add_edges_from/add_nodes_from — byte-identical
    # (verified node+edge order across simple/multigraph-H, attrs, self-loops).
    if G.is_multigraph():  # unreachable (rejected above); kept for parity
        P.add_edges_from((u, v, key, {}) for u, v, key in G.edges(keys=True))
    else:
        P.add_edges_from(G.edges())

    for g in G.nodes():
        P.add_nodes_from((g, h) for h in H.nodes())
        P.add_edges_from([(g, (g, h)) for h in H.nodes()])
        # H's edges (simple and multigraph alike) copy into g's H-block; a
        # multigraph P assigns fresh integer keys, matching nx's
        # add_edges_from(H.edges.data()).
        P.add_edges_from([((g, u), (g, v), dict(attrs)) for u, v, attrs in H.edges(data=True)])

    return P


def modular_product(G, H):
    """Return the modular product of *G* and *H*.

    Two nodes (u1,v1) and (u2,v2) are adjacent iff:
    - u1-u2 is edge in G AND v1-v2 is edge in H, OR
    - u1-u2 is NOT edge in G AND v1-v2 is NOT edge in H (and u1≠u2, v1≠v2).
    """
    if G.is_directed() or H.is_directed():
        raise NetworkXNotImplemented("Modular product not implemented for directed graphs")
    if G.is_multigraph() or H.is_multigraph():
        raise NetworkXNotImplemented("Modular product not implemented for multigraphs")
    # br-r37-c1-prodmodular: native fast path for the simple, self-loop-free case.
    # nx iterates all O((VW)^2) product-node pairs with a per-pair has_edge() + two
    # per-edge add_edge() (tuple-key construction tax); the native kernel precomputes
    # adjacency bitmatrices and assembles the same edge set in Rust. Same edge set
    # (the product parity tests compare canonicalised edges); EDGE-attrs / self-loops
    # fall back to the Python build below.
    # br-r37-c1-prodnodeattr (cc): modular's edge set is adjacency-only; on an
    # EDGE-attr-free product every edge's _paired_edge_attrs({}, {}) is empty, so
    # only NODE attrs decorate the output. Gate on EDGE attrs and paint paired node
    # attrs onto the native result -> node-attributed modular goes from the O(N^2)
    # Python has_edge loop (8.2s / 0.24x at 50x45) to the native bitmatrix build +
    # one node paint (0.5s / 3.66x vs nx).
    # br-cc-prod-edgeattr: EDGE attrs no longer force the O((V_G*V_H)^2) Python
    # has_edge loop. modular's edge set is adjacency-only, and its edge ATTRS are
    # non-empty ONLY on the "both-edge" product edges ((u1,u2)∈G AND (v1,v2)∈H,
    # paired) — a SMALL O(E_G*E_H) subset — while the huge "neither-edge" majority
    # stays attr-free (empty _paired_edge_attrs({},{})). So build the whole
    # structure natively (the kernel is adjacency-only, ignores edge attrs) and
    # DECORATE only that small both-edge subset with one set_edge_attributes.
    # UNLIKE tensor/strong (whose whole dense edge set needs decoration -> partial
    # <1x), here decoration << structure, so it BEATS nx: 0.24x -> 3.1-3.4x.
    if not number_of_selfloops(G) and not number_of_selfloops(H):
        _fast = _fnx.modular_product_fast(G, H)
        if _fast is not None:
            if _graph_has_any_node_attrs(G) or _graph_has_any_node_attrs(H):
                _fast.add_nodes_from(
                    ((g, h), _product_node_attrs(dict(g_attrs), dict(h_attrs)))
                    for g, g_attrs in G.nodes(data=True)
                    for h, h_attrs in H.nodes(data=True)
                )
            if _graph_has_any_edge_attrs(G) or _graph_has_any_edge_attrs(H):
                _g_edges = list(G.edges(data=True))
                _h_edges = list(H.edges(data=True))
                _em = {}
                for _u1, _u2, _ga in _g_edges:
                    for _v1, _v2, _ha in _h_edges:
                        _pa = _paired_edge_attrs(_ga, _ha)
                        _em[((_u1, _v1), (_u2, _v2))] = _pa
                        _em[((_u1, _v2), (_u2, _v1))] = _pa
                set_edge_attributes(_fast, _em)
            return _fast
    P = Graph()

    for g, g_attrs in G.nodes(data=True):
        for h, h_attrs in H.nodes(data=True):
            P.add_node((g, h), **_product_node_attrs(dict(g_attrs), dict(h_attrs)))

    # br-r37-c1-1076l: networkx's algorithm - every edge of G against every
    # edge of H (a selfloop is an edge like any other, so (1,1) in G with (0,1)
    # in H joins (1,0) and (1,1); the old pair loop only visited distinct node
    # pairs), then the same over both complements, which have no selfloops.
    for pair_g, pair_h in ((G, H), (complement(G), complement(H))):
        h_edges = list(pair_h.edges(data=True))
        for u, v, c in pair_g.edges(data=True):
            for x, y, d in h_edges:
                attrs = _paired_edge_attrs(c, d)
                P.add_edge((u, x), (v, y), **attrs)
                P.add_edge((v, x), (u, y), **attrs)

    return P


def rooted_product(G, H, root):
    """Return the rooted product of *G* and *H* at *root*.

    Replace each node v in G with a copy of H, connecting v's copy of
    *root* to the neighbors of v.
    """
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if root not in H:
        raise NodeNotFound("root must be a vertex in H")

    # br-r37-c1-prodrooted: native fast path (simple, no-attr, self-loop-free).
    # The rooted product carries no attrs; the Python build pays the per-edge
    # tuple-key construction tax. The native kernel canonicalises each product
    # tuple once and assembles the edge set in Rust. Same edge set (parity tests
    # canonicalise edges); other shapes fall back to the Python build below.
    # br-r37-c1-prodnodeattr (cc): the rooted product carries NO attrs at all — both
    # nx and the Python fallback drop every node AND edge attr. So the native kernel
    # (which builds the attr-free structure) is correct for ANY attributed input;
    # only directed/multigraph-H/self-loop shapes need the Python path. Dropping the
    # `_graph_has_any_attrs` gate routes attributed rooted products through the fast
    # native build (byte-identical to nx's attr-free output).
    if (
        not G.is_directed()
        and not H.is_directed()
        and not H.is_multigraph()
        and not number_of_selfloops(G)
        and not number_of_selfloops(H)
    ):
        _fast = _fnx.rooted_product_fast(G, H, root)
        if _fast is not None:
            return _fast

    # br-r37-c1-prodbatch (cc): the native path handles no-attr; the rooted product
    # carries no edge attrs but the native path bails on ANY attr, so an attributed
    # G/H lands here. Batch the O(V_G*V_H) node build + O(V_G*E_H + E_G) edge layers
    # through add_nodes_from/add_edges_from (one native call each) — byte-identical
    # node/edge order to the per-item loop.
    P = Graph()
    P.add_nodes_from((g, h) for g in G.nodes() for h in H.nodes())
    P.add_edges_from(((g, u), (g, v)) for g in G.nodes() for u, v in H.edges())
    P.add_edges_from(((u, root), (v, root)) for u, v in G.edges())

    return P
