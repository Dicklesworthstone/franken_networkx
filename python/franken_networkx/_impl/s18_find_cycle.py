

def find_cycle(G, source=None, orientation=None):
    """Find a cycle reachable from a source node.

    br-r37-c1-fcyclnative: run nx's edge_dfs + find_cycle algorithm directly on
    fnx graph views (``_fnx_find_cycle``) for BOTH directed and undirected,
    instead of paying a full fnx->nx conversion for a function that early-exits
    on the first cycle. The old undirected delegation (br-r37-c1-2hrfs) existed
    only because the Rust binding emitted algorithm-canonical orientation; the
    Python port emits edges in nx's DFS-traversal direction via ``_fnx_edge_dfs``
    (whose adjacency order matches nx), so the cycle edge tuples + orientation
    match exactly (verified 0/800 over directed/undirected x multigraph x all
    orientation modes x sources).
    """
    # br-r37-c1-nwkg0: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-7yn51: native fast path for the common case (orientation=None,
    # source=None, simple graph) — a faithful port of nx's edge_dfs+find_cycle
    # that does the whole DFS in Rust instead of per-node fnx EdgeView crossings
    # (~3-4x faster on cycle-dominated graphs; no early-exit regression since the
    # kernel returns the moment a cycle is found). Multigraph / explicit source /
    # non-None orientation keep the verbatim Python port below.
    if source is None and orientation is None and not G.is_multigraph():
        cycle = _raw_find_cycle_simple(G)
        if cycle is None:
            raise NetworkXNoCycle("No cycle found.")
        return cycle
    # br-r37-c1-fcmg: native fast path for the common MultiGraph / MultiDiGraph
    # case. The verbatim Python edge_dfs port (below) pays an fnx EdgeView per
    # visited node (~14x nx); the kernel runs the keyed DFS entirely in Rust and
    # returns (u, v, key) triples with user-facing key objects, early-exiting on
    # the first cycle. Explicit source / non-None orientation keep the Python port.
    if source is None and orientation is None and G.is_multigraph():
        cycle = _raw_find_cycle_multigraph_simple(G)
        if cycle is None:
            raise NetworkXNoCycle("No cycle found.")
        return cycle
    return _fnx_find_cycle(G, source, orientation)


_FC_FORWARD = "forward"
_FC_REVERSE = "reverse"


def _fnx_edge_dfs(G, source=None, orientation=None):
    """Verbatim port of networkx.edge_dfs, run on an fnx graph's views
    (no fnx->nx conversion). See find_cycle (br-r37-c1-57dlh)."""
    nodes = list(G.nbunch_iter(source))
    if not nodes:
        return

    directed = G.is_directed()
    kwds = {"data": False}
    if G.is_multigraph() is True:
        kwds["keys"] = True

    if orientation is None:

        def edges_from(node):
            return iter(G.edges(node, **kwds))

    elif not directed or orientation == "original":

        def edges_from(node):
            for e in G.edges(node, **kwds):
                yield e + (_FC_FORWARD,)

    elif orientation == "reverse":

        def edges_from(node):
            for e in G.in_edges(node, **kwds):
                yield e + (_FC_REVERSE,)

    elif orientation == "ignore":

        def edges_from(node):
            for e in G.edges(node, **kwds):
                yield e + (_FC_FORWARD,)
            for e in G.in_edges(node, **kwds):
                yield e + (_FC_REVERSE,)

    else:
        raise NetworkXError("invalid orientation argument.")

    if directed:

        def edge_id(edge):
            return edge[:-1] if orientation is not None else edge

    else:

        def edge_id(edge):
            return (frozenset(edge[:2]),) + edge[2:]

    check_reverse = directed and orientation in ("reverse", "ignore")

    visited_edges = set()
    visited_nodes = set()
    edges = {}

    for start_node in nodes:
        stack = [start_node]
        while stack:
            current_node = stack[-1]
            if current_node not in visited_nodes:
                edges[current_node] = edges_from(current_node)
                visited_nodes.add(current_node)

            try:
                edge = next(edges[current_node])
            except StopIteration:
                stack.pop()
            else:
                edgeid = edge_id(edge)
                if edgeid not in visited_edges:
                    visited_edges.add(edgeid)
                    if check_reverse and edge[-1] == _FC_REVERSE:
                        stack.append(edge[0])
                    else:
                        stack.append(edge[1])
                    yield edge


def _fnx_find_cycle(G, source=None, orientation=None):
    """Verbatim port of networkx.find_cycle's loop, on fnx views."""
    if not G.is_directed() or orientation in (None, "original"):

        def tailhead(edge):
            return edge[:2]

    elif orientation == "reverse":

        def tailhead(edge):
            return edge[1], edge[0]

    elif orientation == "ignore":

        def tailhead(edge):
            if edge[-1] == _FC_REVERSE:
                return edge[1], edge[0]
            return edge[:2]

    explored = set()
    cycle = []
    final_node = None
    for start_node in G.nbunch_iter(source):
        if start_node in explored:
            continue

        edges = []
        seen = {start_node}
        active_nodes = {start_node}
        previous_head = None

        for edge in _fnx_edge_dfs(G, start_node, orientation):
            tail, head = tailhead(edge)
            if head in explored:
                continue
            if previous_head is not None and tail != previous_head:
                while True:
                    try:
                        popped_edge = edges.pop()
                    except IndexError:
                        edges = []
                        active_nodes = {tail}
                        break
                    else:
                        popped_head = tailhead(popped_edge)[1]
                        active_nodes.remove(popped_head)

                    if edges:
                        last_head = tailhead(edges[-1])[1]
                        if tail == last_head:
                            break
            edges.append(edge)

            if head in active_nodes:
                cycle.extend(edges)
                final_node = head
                break
            else:
                seen.add(head)
                active_nodes.add(head)
                previous_head = head

        if cycle:
            break
        else:
            explored.update(seen)

    if not cycle:
        raise NetworkXNoCycle("No cycle found.")

    for i, edge in enumerate(cycle):
        tail, head = tailhead(edge)
        if tail == final_node:
            break
    return cycle[i:]


def _make_list_of_ints(sequence):
    if not isinstance(sequence, list):
        result = []
        for value in sequence:
            errmsg = f"sequence is not all integers: {value}"
            try:
                int_value = int(value)
            except ValueError:
                raise NetworkXError(errmsg) from None
            if int_value != value:
                raise NetworkXError(errmsg)
            result.append(int_value)
        return result

    for idx, value in enumerate(sequence):
        if isinstance(value, int):
            continue
        errmsg = f"sequence is not all integers: {value}"
        try:
            int_value = int(value)
        except ValueError:
            raise NetworkXError(errmsg) from None
        if int_value != value:
            raise NetworkXError(errmsg)
        sequence[idx] = int_value
    return sequence


def is_graphical(sequence, method="eg"):
    """Returns True if sequence is a valid degree sequence."""
    deg_sequence = _make_list_of_ints(sequence)
    if any(degree < 0 for degree in deg_sequence):
        return False
    if method == "eg":
        return is_valid_degree_sequence_erdos_gallai(deg_sequence)
    if method == "hh":
        return is_valid_degree_sequence_havel_hakimi(deg_sequence)
    # Upstream nx raises the base NetworkXException here (not
    # NetworkXError). Match it exactly — fetch the class lazily so we
    # don't create a parallel hierarchy that breaks
    # ``except nx.NetworkXException``.
    raise _nx_exception_cls()("`method` must be 'eg' or 'hh'")


def is_digraphical(in_sequence, out_sequence):
    """Returns True if some directed graph can realize the in/out sequences."""
    try:
        in_deg_sequence = _make_list_of_ints(in_sequence)
        out_deg_sequence = _make_list_of_ints(out_sequence)
    except NetworkXError:
        return False

    max_len = max(len(in_deg_sequence), len(out_deg_sequence))
    if max_len == 0:
        return True

    degree_pairs = []
    for idx in range(max_len):
        in_degree = in_deg_sequence[idx] if idx < len(in_deg_sequence) else 0
        out_degree = out_deg_sequence[idx] if idx < len(out_deg_sequence) else 0
        if in_degree < 0 or out_degree < 0:
            return False
        degree_pairs.append((in_degree, out_degree))
    return _raw_is_digraphical(degree_pairs)


def is_pseudographical(sequence):
    """Returns True if some pseudograph can realize the sequence."""
    try:
        deg_sequence = _make_list_of_ints(sequence)
    except NetworkXError:
        return False
    return sum(deg_sequence) % 2 == 0 and min(deg_sequence) >= 0


def is_multigraphical(sequence):
    """Returns True if some multigraph can realize the sequence."""
    try:
        deg_sequence = _make_list_of_ints(sequence)
    except NetworkXError:
        return False

    degree_sum = 0
    max_degree = 0
    for degree in deg_sequence:
        if degree < 0:
            return False
        degree_sum += degree
        max_degree = max(max_degree, degree)
    if degree_sum % 2 != 0 or degree_sum < 2 * max_degree:
        return False
    return True


def is_tournament(G):
    """Returns True if and only if ``G`` is a tournament."""
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    return (
        all((v in G[u]) ^ (u in G[v]) for u, v in _combinations(G, 2))
        and number_of_selfloops(G) == 0
    )




# hamiltonian_path was top-level in fnx — removed in br-r37-c1-twl53 to
# mirror nx's namespacing (lives at nx.tournament.hamiltonian_path only).
# fnx.tournament.hamiltonian_path still works through the auto-bound
# submodule fallback in __getattr__.










def is_regular(G):
    """Determines whether a graph is regular."""
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")

    # br-r37-c1-regidx: native O(|V|) integer degree-equality check (short-
    # circuit) for simple graphs. Multigraph degree counts parallel-edge
    # multiplicity (which the simple-graph projection collapses), so those stay
    # on the Python degree-view path below.
    if not G.is_multigraph():
        try:
            return _raw_is_regular(G)
        except NetworkXPointlessConcept:
            raise
        except Exception:
            pass

    node = next(iter(G))
    degree_view = G.degree
    if callable(degree_view):
        degree = degree_view(node)
        degree_items = degree_view()
    else:
        degree = degree_view[node]
        degree_items = degree_view

    if not G.is_directed():
        return all(degree == current_degree for _node, current_degree in degree_items)

    in_degree_view = G.in_degree
    if callable(in_degree_view):
        in_degree = in_degree_view(node)
        in_degree_items = in_degree_view()
    else:
        in_degree = in_degree_view[node]
        in_degree_items = in_degree_view

    out_degree_view = G.out_degree
    if callable(out_degree_view):
        out_degree = out_degree_view(node)
        out_degree_items = out_degree_view()
    else:
        out_degree = out_degree_view[node]
        out_degree_items = out_degree_view

    return all(
        in_degree == current_degree for _node, current_degree in in_degree_items
    ) and all(out_degree == current_degree for _node, current_degree in out_degree_items)


def is_weighted(G, edge=None, weight="weight"):
    """Returns True if ``G`` has weighted edges."""
    if edge is not None:
        data = G.get_edge_data(*edge)
        if data is None:
            msg = f"Edge {edge!r} does not exist."
            raise NetworkXError(msg)
        return weight in data

    if G.number_of_edges() == 0:
        return False

    # br-r37-c1-isnegw (sibling of is_negatively_weighted): scan the live edge
    # dicts via the native to_dict_of_dicts kernel instead of the per-edge
    # edges(data=True) materialization — ~2.2x slower than nx on weighted graphs,
    # where ``all`` cannot short-circuit and walks every edge. to_dict_of_dicts is
    # overlay-safe (reads edge_py_attrs). Undirected rows list each edge twice;
    # harmless for ``all``. Multigraph / views keep the edges() scan.
    if type(G) is Graph or type(G) is DiGraph:
        return all(
            weight in d
            for inner in to_dict_of_dicts(G).values()
            for d in inner.values()
        )
    return all(weight in data for _u, _v, data in G.edges(data=True))


def is_negatively_weighted(G, edge=None, weight="weight"):
    """Returns True if ``G`` has negatively weighted edges."""
    if edge is not None:
        data = G.get_edge_data(*edge)
        if data is None:
            msg = f"Edge {edge!r} does not exist."
            raise NetworkXError(msg)
        return weight in data and data[weight] < 0

    # br-r37-c1-isnegw: scan the live edge-attr dicts via the native
    # to_dict_of_dicts kernel ({u: {v: live_edge_dict}}, built in Rust and
    # reflecting Python-overlay attr mutations) instead of the per-edge
    # ``G.edges(data=True)`` materialization (~2.7x faster, flips 0.49x -> 1.3x
    # vs nx). The native edge-weight bindings (graph_has_negative_edge_weight)
    # CANNOT be used here: they read the Rust inner AttrMap and miss attrs set
    # via ``G[u][v][k] = v`` post-creation. Multigraph / views (no native
    # to_dict_of_dicts) keep the edges() scan. (Undirected rows list each edge
    # twice; harmless for ``any`` and still far cheaper than the view walk.)
    if type(G) is Graph or type(G) is DiGraph:
        return any(
            weight in d and d[weight] < 0
            for inner in to_dict_of_dicts(G).values()
            for d in inner.values()
        )
    return any(weight in data and data[weight] < 0 for _u, _v, data in G.edges(data=True))


# Algorithm functions — traversal additional
from franken_networkx._fnx import (
    edge_bfs as _edge_bfs_raw,
    edge_dfs as _edge_dfs_raw,
)

# Algorithm functions — matching additional
from franken_networkx._fnx import (
    max_weight_clique as _raw_max_weight_clique,
)


def is_edge_cover(G, cover):
    """Return True iff every node of *G* is an endpoint of some edge in ``cover``.

    networkx's definition is node coverage only: ``set(G)`` must be a subset
    of the endpoints in ``cover``. The cover's pairs are not required to be
    edges of *G* (``{(0, 0), (1, 1)}`` covers the single edge ``0-1``). The
    former native check also demanded that every pair be an edge, answering
    False there (nro4w.7). Directed graphs are rejected, as networkx's
    ``@not_implemented_for("directed")`` does.
    """
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return set(G) <= set(_itertools.chain.from_iterable(cover))


def _max_weight_clique_native(G, weight):
    """br-cc-mwc-native: nx's exact MaxWeightClique branch-and-bound run in
    pure Python over a PRECOMPUTED native adjacency (``to_dict_of_lists`` ->
    {node: set(neighbours)}). The algorithm is copied verbatim from nx
    (networkx/algorithms/clique.py MaxWeightClique) with the ONLY change being
    ``self.G.has_edge(v, w)`` -> ``w in adj[v]`` (O(1) set membership, no PyO3)
    and ``self.G.degree(v)`` -> a single native bulk ``dict(G.degree())``. This
    skips the whole ``_fnx_to_nx`` conversion, which alone (0.34ms @ n=60)
    exceeded nx's entire runtime (0.29ms) and made the delegated path 0.48x.
    Byte-identical result (same node order, same expand/branch order, same
    validation) to nx.
    """
    adj = {v: set(nbrs) for v, nbrs in to_dict_of_lists(G).items()}
    if weight is None:
        node_weights = {v: 1 for v in G.nodes()}
    else:
        node_weights = {}
        for v in G.nodes():
            nd = G.nodes[v]
            if weight not in nd:
                raise KeyError(
                    f"Node {v!r} does not have the requested weight field."
                )
            wv = nd[weight]
            if not isinstance(wv, int):
                raise ValueError(
                    f"The {weight!r} field of node {v!r} is not an integer."
                )
            node_weights[v] = wv

    incumbent_nodes = []
    incumbent_weight = 0

    def greedily_find_independent_set(P):
        independent_set = []
        P = P[:]
        while P:
            v = P[0]
            independent_set.append(v)
            av = adj[v]
            P = [w for w in P if v != w and w not in av]
        return independent_set

    def find_branching_nodes(P, target):
        residual_wt = {v: node_weights[v] for v in P}
        total_wt = 0
        P = P[:]
        while P:
            independent_set = greedily_find_independent_set(P)
            min_wt_in_class = min(residual_wt[v] for v in independent_set)
            total_wt += min_wt_in_class
            if total_wt > target:
                break
            for v in independent_set:
                residual_wt[v] -= min_wt_in_class
            P = [v for v in P if residual_wt[v] != 0]
        return P

    def expand(C, C_weight, P):
        nonlocal incumbent_nodes, incumbent_weight
        if C_weight > incumbent_weight:
            incumbent_nodes = C[:]
            incumbent_weight = C_weight
        branching_nodes = find_branching_nodes(P, incumbent_weight - C_weight)
        while branching_nodes:
            v = branching_nodes.pop()
            P.remove(v)
            av = adj[v]
            expand(
                C + [v],
                C_weight + node_weights[v],
                [w for w in P if w in av],
            )

    degrees = dict(G.degree())
    nodes = sorted(G.nodes(), key=lambda v: degrees[v], reverse=True)
    nodes = [v for v in nodes if node_weights[v] > 0]
    expand([], 0, nodes)
    return incumbent_nodes, incumbent_weight


def max_weight_clique(G, weight="weight"):
    """Find a maximum-weight clique.

    br-mwclqnone: nx accepts ``weight=None`` (every node has weight 1, so the
    result is a max-cardinality clique with total len(clique)).

    br-cc-mwc-native: the Rust ``max_weight_clique`` binding solves max-
    CARDINALITY (ignores node weights) and returns the clique size as the
    weight, so it is wrong for the weighted case. Run nx's exact branch-and-
    bound NATIVELY over a precomputed native adjacency instead — byte-exact
    with nx and 1.3-1.6x (was 0.48x through the ``_fnx_to_nx`` delegation, whose
    conversion alone exceeded nx's whole runtime). Directed raises as nx does;
    multigraphs keep the nx delegation (rare; native adjacency-set path is for
    simple graphs).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return _max_weight_clique_native(G, weight)

# Algorithm functions — DAG additional
from franken_networkx._fnx import (
    is_aperiodic as _raw_is_aperiodic,
    antichains as _raw_antichains,
    immediate_dominators as _raw_immediate_dominators,
    dominance_frontiers as _raw_dominance_frontiers,
)


def immediate_dominators(G, start):
    """Immediate dominators of every node reachable from ``start``.

    Matches upstream ``nx.immediate_dominators`` contract: the returned
    dict does **not** include ``start`` itself (franken_networkx-y87ra).
    """
    # br-r37-c1-1y7h1: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ct24s: nx's @not_implemented_for("undirected") runs first.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    # br-r37-c1-mz7g4: nx pre-validates ``start in G`` (silently
    # returns False on unhashable, then raises NetworkXError);
    # without this guard fnx silently computes whatever the Rust impl
    # returns. Match nx's exact contract.
    if start not in G:
        raise NetworkXError("start is not in G")
    try:
        idom = _raw_immediate_dominators(G, start)
    except NetworkXNotImplemented as exc:
        # br-r37-c1-yf4tf: align Rust binding's custom message with
        # nx's standard '@not_implemented_for' format.
        if "not defined for undirected" in str(exc):
            raise NetworkXNotImplemented(
                "not implemented for undirected type"
            ) from exc
        raise
    # Rust binding returns a dict that includes {start: start}; drop the
    # self-dominator entry to match nx's documented shape.
    idom.pop(start, None)
    # br-gauntlet-idom-order: nx builds the idom dict by iterating nodes in
    # reverse-postorder (``order = dfs_postorder_nodes(G, start); order.pop();
    # order.reverse()``) and inserts each key on first assignment, so the dict
    # iteration order is that reverse-postorder (excluding ``start``). The native
    # kernel returns correct *values* but in a different key order, which breaks
    # the iteration-order parity contract. Reorder to nx's exact sequence.
    try:
        order = list(dfs_postorder_nodes(G, start))
        if order:
            order.pop()  # drop ``start`` (last in postorder)
        order.reverse()
        reordered = {u: idom[u] for u in order if u in idom}
        # keep any stragglers (defensive: should be empty) in original order
        for k, v in idom.items():
            if k not in reordered:
                reordered[k] = v
        idom = reordered
    except Exception:
        pass
    return idom


def dominance_frontiers(G, start):
    """Dominance frontiers for every node reachable from ``start``.

    br-r37-c1-mz7g4: nx pre-validates ``start in G`` (silently returns
    False on unhashable, then raises NetworkXError); without this
    guard fnx silently computes. Match nx's exact contract.
    """
    # br-r37-c1-1y7h1: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ct24s: nx's @not_implemented_for("undirected") runs first.
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")
    if start not in G:
        raise NetworkXError("start is not in G")
    # br-r37-c1-domfront: the native _raw_dominance_frontiers kernel only walked
    # >=2-predecessor join points and missed nx's start-node special case — nx
    # processes ``start`` with idom[start]=None so predecessors of start (back
    # edges) walk all the way to the root, adding ``start`` to their frontiers.
    # e.g. on 0->1,0->2,1->3,2->3,3->0 nx yields df[3]={0}, df[0]={0}; the kernel
    # gave empty sets. Reimplement nx's exact algorithm on immediate_dominators
    # (verified key-order- and value-identical to nx); idom key order drives the
    # result dict key order.
    idom = dict(immediate_dominators(G, start))
    idom[start] = None
    df = {u: set() for u in idom}
    for u in idom:
        if u == start or len(G.pred[u]) >= 2:
            for v in G.pred[u]:
                if v in idom:
                    while v != idom[u]:
                        df[v].add(u)
                        v = idom[v]
    return df


def antichains(G, topo_order=None):
    """Generate all antichains in a DAG.

    Parameters
    ----------
    G : DiGraph
        A directed acyclic graph.
    topo_order : iterable, optional
        A topological order of the nodes. If None, computed automatically.

    Yields
    ------
    set
        An antichain (set of nodes with no path between any pair).
    """
    if not G.is_directed():
        raise NetworkXNotImplemented("not implemented for undirected type")

    def _gen():
        nonlocal topo_order
        if topo_order is None:
            topo_order = list(topological_sort(G))

        TC = transitive_closure_dag(G, topo_order)
        antichains_stacks = [([], list(reversed(topo_order)))]

        while antichains_stacks:
            (antichain, stack) = antichains_stacks.pop()
            yield antichain
            while stack:
                x = stack.pop()
                new_antichain = antichain + [x]
                new_stack = [t for t in stack if not ((t in TC[x]) or (x in TC[t]))]
                antichains_stacks.append((new_antichain, new_stack))

    return _gen()

# Algorithm functions — additional shortest path
from franken_networkx._fnx import (
    dijkstra_path_length as _raw_dijkstra_path_length,
    multidigraph_dijkstra_path_target as _raw_multidigraph_dijkstra_path_target,
    multidigraph_dijkstra_path_length_target as _raw_multidigraph_dijkstra_path_length_target,
    multidigraph_single_source_dijkstra as _raw_mdg_ss_dijkstra,
    multidigraph_single_source_dijkstra_path_length as _raw_mdg_ss_dijkstra_path_length,
    bellman_ford_path_length as _raw_bellman_ford_path_length,
    single_source_dijkstra as _raw_single_source_dijkstra,
    single_source_dijkstra_path as _raw_single_source_dijkstra_path,
    single_source_dijkstra_path_length as _raw_single_source_dijkstra_path_length,
    single_target_dijkstra_path_length as _raw_single_target_dijkstra_path_length,
    dijkstra_predecessor_and_distance as _raw_dijkstra_predecessor_and_distance,
    single_source_bellman_ford as _raw_single_source_bellman_ford,
    single_source_bellman_ford_path as _raw_single_source_bellman_ford_path,
    single_source_bellman_ford_path_length as _raw_single_source_bellman_ford_path_length,
    single_target_shortest_path as _raw_single_target_shortest_path,
    single_target_shortest_path_length as _raw_single_target_shortest_path_length,
    all_pairs_dijkstra_path as _raw_all_pairs_dijkstra_path,
    all_pairs_dijkstra_path_length as _raw_all_pairs_dijkstra_path_length,
    johnson_path_directed as _raw_johnson_path_directed,
    all_pairs_bellman_ford_path as _raw_all_pairs_bellman_ford_path,
    all_pairs_bellman_ford_path_length as _raw_all_pairs_bellman_ford_path_length,
    floyd_warshall as _raw_floyd_warshall,
    floyd_warshall_predecessor_and_distance as _raw_floyd_warshall_predecessor_and_distance,
    bidirectional_shortest_path as _raw_bidirectional_shortest_path,
    negative_edge_cycle as _raw_negative_edge_cycle,
    predecessor as _raw_predecessor,
    predecessor_indexed as _raw_predecessor_indexed,
    path_weight,
)


def _reraise_no_path_with_display_keys(source, target):
    """br-r37-c1-t27ad: re-raise NetworkXNoPath with networkx's wording.

    The native binding formats the CANONICAL node key into the message --
    ``No path between str:1:a and str:1:z.`` -- where networkx uses the node as
    the caller passed it. crates/fnx-python/src/algorithms.rs converts back with
    ``py_node_key`` on the SUCCESS path and not on the error path.

    The leak is STRING-key specific (int and tuple keys already round-trip), so
    it hits the most common node type while looking clean in most fixtures.

    Fixed here rather than in Rust because the shim already holds the caller's
    own ``source`` and ``target``, and this is the established idiom for a
    leaked native message in this file -- br-r37-c1-qmu8x does the same for
    ``Source 'x' is not in G``. Re-raising unconditionally is safe: for these
    functions the ONLY NetworkXNoPath condition is this one, and networkx's
    message for it is exactly the string built below.
    """
    raise NetworkXNoPath(f"No path between {source} and {target}.") from None


def bidirectional_shortest_path(G, source, target):
    """Return the shortest path between source and target via two-way BFS.

    br-r37-c1-k4wsy: the Rust binding now runs nx's exact bidirectional
    walk for BOTH orientations with discovery-object parity. The old
    directed delegation (br-r37-c1-t2gyx) was actually WRONG:
    ``_fnx_to_nx``'s succ-major walk reorders pred rows, poisoning nx's
    reverse-frontier tie-break (br-r37-c1-w7nn3) — and it paid the
    conversion tax on every call.
    """
    private_rows = _point_query_uses_private_rows(G)
    if not private_rows:
        G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-qmu8x: validate membership up front with nx's exact wording.
    # The native binding otherwise leaks a repr-quoted "Source 'x' is not in G"
    # whereas nx emits the unquoted "Source x is not in G" (source first).
    if source not in G:
        raise NodeNotFound(f"Source {source} is not in G")
    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")
    if private_rows:
        # The caller's live mappings, not the hidden native topology, own
        # these rows. Forward-only BFS is insufficient: NetworkX expands
        # the smaller frontier and uses predecessor order for reverse ties.
        if target == source:
            return [source]
        forward_adj = G._succ if G.is_directed() else G._adj
        reverse_adj = G._pred if G.is_directed() else G._adj
        pred, succ = {source: None}, {target: None}
        forward, reverse = [source], [target]

        def build_path(meeting):
            path = []
            node = meeting
            while node is not None:
                path.append(node)
                node = pred[node]
            path.reverse()
            node = succ[path[-1]]
            while node is not None:
                path.append(node)
                node = succ[node]
            return path

        while forward and reverse:
            if len(forward) <= len(reverse):
                current, forward = forward, []
                for node in current:
                    for neighbor in forward_adj[node]:
                        if neighbor not in pred:
                            forward.append(neighbor)
                            pred[neighbor] = node
                        if neighbor in succ:
                            return build_path(neighbor)
            else:
                current, reverse = reverse, []
                for node in current:
                    for neighbor in reverse_adj[node]:
                        if neighbor not in succ:
                            succ[neighbor] = node
                            reverse.append(neighbor)
                        if neighbor in pred:
                            return build_path(neighbor)
        _reraise_no_path_with_display_keys(source, target)
    try:
        return _raw_bidirectional_shortest_path(G, source, target)
    except NetworkXNoPath:
        _reraise_no_path_with_display_keys(source, target)


def is_aperiodic(G):
    """Returns True if ``G`` is aperiodic."""
    if not G.is_directed():
        raise NetworkXError("is_aperiodic not defined for undirected graphs")
    if len(G) == 0:
        raise NetworkXPointlessConcept("Graph has no nodes.")
    if not is_strongly_connected(G):
        raise NetworkXError("Graph is not strongly connected.")

    source = next(iter(G))
    levels = {source: 0}
    this_level = [source]
    gcd_cycle = 0
    level = 1
    while this_level:
        next_level = []
        for u in this_level:
            for v in G[u]:
                if v in levels:
                    gcd_cycle = _math.gcd(gcd_cycle, levels[u] - levels[v] + 1)
                else:
                    next_level.append(v)
                    levels[v] = level
        this_level = next_level
        level += 1
    return gcd_cycle == 1


def single_target_shortest_path_length(G, target, cutoff=None):
    """Reverse BFS lengths to ``target`` from every other node.

    Returns a dict ``{source: distance}`` of hop counts. ``cutoff`` truncates
    the search depth. Mirrors ``networkx.single_target_shortest_path_length``.
    """
    if target not in G:
        raise NodeNotFound(f"Target {target} is not in G")
    root = _reverse_view_root(G)
    if root is not None and (
        cutoff is None or isinstance(cutoff, int) and 0 <= cutoff <= _sys.maxsize
    ):
        # Predecessors of a reverse view are successors of its root.
        lengths = {target: 0}
        for parent, node in _bfs_edges_raw(root, target, depth_limit=cutoff):
            lengths[node] = lengths[parent] + 1
        return lengths
    # br-r37-c1-sptlen: for undirected graphs the distance from every node TO
    # target equals the distance FROM target (symmetric), so route to the native
    # single_source kernel (~2.5x faster than networkx) instead of the per-node
    # Python reverse-BFS (~6x slower). Hop counts are integers and the dict is
    # built in BFS-from-target order in both, so the result is byte-identical
    # (value + key order). Directed graphs need reverse adjacency -> Python path.
    if not G.is_directed():
        return single_source_shortest_path_length(G, target, cutoff=cutoff)
    if _has_networkx_private_storage(G):
        # A directed target walk follows authoritative predecessor rows, not
        # the native graph's potentially hidden edges or successor rows.
        adj = G._pred
        count = len(adj)
        seen = {target}
        lengths = {target: 0}
        frontier = [target]
        level = 0
        limit = float("inf") if cutoff is None else cutoff
        while frontier and limit > level:
            level += 1
            current, frontier = frontier, []
            for node in current:
                for neighbor in adj[node]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        frontier.append(neighbor)
                        lengths[neighbor] = level
                if len(seen) == count:
                    return lengths
        return lengths
    # br-r37-c1-a0nl0: directed reverse BFS is now native as well. The raw
    # binding emits discovery-order pairs, preserving the Python loop's
    # predecessor tie-breaking while avoiding per-node predecessor wrappers.
    return _raw_single_target_shortest_path_length(G, target, cutoff=cutoff)


def single_target_shortest_path(G, target, cutoff=None):
    """Reverse BFS paths to ``target`` from every other node.

    Returns a dict ``{source: path-list}`` where each path ends at ``target``.
    Mirrors ``networkx.single_target_shortest_path``.
    """
    if target not in G:
        raise NodeNotFound(f"Target {target} not in G")
    root = _reverse_view_root(G)
    if root is None and _has_networkx_private_storage(G):
        # Preserve the original target object at the end of each path, and
        # use predecessor rows only for directed graphs, exactly as NetworkX.
        adj = G._pred if G.is_directed() else G._adj
        count = len(adj)
        paths = {target: [target]}
        frontier = [target]
        level = 0
        limit = float("inf") if cutoff is None else cutoff
        while frontier and limit > level:
            current, frontier = frontier, []
            for node in current:
                for neighbor in adj[node]:
                    if neighbor not in paths:
                        paths[neighbor] = [neighbor] + paths[node]
                        frontier.append(neighbor)
                if len(paths) == count:
                    return paths
            level += 1
        return paths
    # br-r37-c1-stsp: the native binding now emits {node: path} keyed in
    # BFS-discovery-from-target order (reverse BFS over integer adjacency:
    # neighbors for undirected, predecessors for directed), matching nx's
    # dict-insertion order. This replaces the per-node pure-Python reverse
    # BFS (~4-5x slower than nx, scaling with |V|+|E|).
    if cutoff is not None and cutoff < 0:
        cutoff = 0
    if root is not None and (
        cutoff is None or isinstance(cutoff, int) and 0 <= cutoff <= _sys.maxsize
    ):
        paths = {target: [target]}
        for parent, node in _bfs_edges_raw(root, target, depth_limit=cutoff):
            paths[node] = [node] + paths[parent]
        return paths
    return _raw_single_target_shortest_path(G, target, cutoff)


def _ordered_predecessor_nodes_and_levels(G, source, predecessor_map):
    ordered_nodes = [source]
    seen_levels = {source: 0}
    nextlevel = [source]
    level = 0

    while nextlevel and len(ordered_nodes) < len(predecessor_map):
        level += 1
        thislevel = nextlevel
        nextlevel = []
        for node in thislevel:
            for neighbor in G[node]:
                if neighbor in predecessor_map and neighbor not in seen_levels:
                    seen_levels[neighbor] = level
                    nextlevel.append(neighbor)
                    ordered_nodes.append(neighbor)

    return ordered_nodes, seen_levels


def predecessor(G, source, target=None, cutoff=None, return_seen=None):
    """BFS-predecessor map for shortest paths from ``source``.

    Returns a dict ``{node: [predecessors]}`` where each list holds every
    BFS-predecessor of ``node`` on a shortest path from ``source``. If
    ``return_seen=True``, also returns the per-node BFS depth dict. Mirrors
    ``networkx.predecessor``.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    # br-r37-c1-7jysw: networkx's level BFS in index space, emitted in its
    # discovery order with its key objects (a cutoff other than none or a
    # positive int keeps the routes below).
    native_cutoff = _normalize_predecessor_cutoff(cutoff)
    if native_cutoff is None or (type(native_cutoff) is int and 0 < native_cutoff < 2**63):
        built = _raw_predecessor_indexed(G, source, native_cutoff)
        if built is not None:
            pred, seen = built
            if target is not None:
                if return_seen:
                    if target not in pred:
                        return ([], -1)
                    return (pred[target], seen[target])
                if target not in pred:
                    return []
                return pred[target]
            if return_seen:
                return (pred, seen)
            return pred
    if G.is_directed():
        level = 0
        nextlevel = [source]
        seen = {source: level}
        pred = {source: []}
        while nextlevel:
            level = level + 1
            thislevel = nextlevel
            nextlevel = []
            for v in thislevel:
                for w in G[v]:
                    if w not in seen:
                        pred[w] = [v]
                        seen[w] = level
                        nextlevel.append(w)
                    elif seen[w] == level:
                        pred[w].append(v)
            if cutoff and cutoff <= level:
                break
        if target is not None:
            if return_seen:
                if target not in pred:
                    return ([], -1)
                return (pred[target], seen[target])
            if target not in pred:
                return []
            return pred[target]
        if return_seen:
            return (pred, seen)
        return pred
    # br-r37-c1-pred-cutfloat: nx's predecessor uses
    # ``if cutoff and cutoff <= level: break`` (truthy-aware).
    # For NaN / +inf, comparison returns False so the search runs
    # to completion — both treated as unbounded.  For -inf and
    # negative finite, comparison is True at level 0 → breaks
    # immediately (returns just source).  Finite floats round up
    # via ceil (last level admitted is ceil(cutoff)).  The Rust
    # binding requires int and raises TypeError/OverflowError on
    # the floats — normalise here.
    cutoff = _normalize_predecessor_cutoff(cutoff)
    predecessor_map = _raw_predecessor(G, source, cutoff=cutoff)
    ordered_nodes, seen_levels = _ordered_predecessor_nodes_and_levels(
        G, source, predecessor_map
    )
    if target is not None:
        if return_seen:
            if target not in predecessor_map:
                return ([], -1)
            return (predecessor_map[target], seen_levels[target])
        return predecessor_map.get(target, [])
    ordered_predecessor_map = {node: predecessor_map[node] for node in ordered_nodes}
    if return_seen:
        ordered_seen_levels = {node: seen_levels[node] for node in ordered_nodes}
        return ordered_predecessor_map, ordered_seen_levels
    return ordered_predecessor_map


def dijkstra_path_length(G, source, target, weight="weight"):
    """Return the shortest weighted path length from ``source`` to ``target``.

    Mirrors ``networkx.dijkstra_path_length``. Raises ``NetworkXNoPath``
    if no path exists.
    """
    if _point_query_uses_private_rows(G):
        return _dijkstra_path_length_inproc(G, source, target, weight=weight)
    G = _coerce_arg_to_fnx_graph(G)
    # br-cc-mgdijkstra: multigraph -> simple min-weight graph + fast simple kernel.
    if G.is_multigraph() and isinstance(weight, str):
        if G.is_directed():
            if source not in G:
                raise NodeNotFound(f"Node {source} not found in graph")
            _HASH_PROBE.get(target)
            if target not in G:
                raise NetworkXNoPath(f"Node {target} not reachable from {source}")
            # br-r37-c1-04z53.9172: this fast path ran BEFORE the delegation
            # predicate below, so a MultiDiGraph reached the f64 kernel however
            # the classifier voted. That is why the 2**60 / 2**70 / Fraction
            # rows kept diverging on MultiDiGraph after the classifier itself
            # was corrected. The kernel's own "return None to delegate" rule
            # carries no exactness dimension, so the predicate has to be asked.
            if _should_delegate_dijkstra_to_networkx(G, weight):
                return _dijkstra_path_length_inproc(G, source, target, weight=weight)
            try:
                _direct = _raw_multidigraph_dijkstra_path_length_target(
                    G, source, target, weight=weight
                )
            except NetworkXNoPath as exc:
                # br-r37-c1-rmzr6: the MultiDiGraph branch reached the raw
                # kernel without the re-raise the general path below already
                # does, so it surfaced the kernel's own wording -- and with the
                # canonical key in it: "No path between str:1:a and str:1:z."
                # networkx uses a DIFFERENT template for dijkstra_path_length
                # than for shortest_path, and Graph / DiGraph / MultiGraph all
                # already emit it here; MultiDiGraph was the one class out.
                raise NetworkXNoPath(
                    f"Node {target} not reachable from {source}"
                ) from exc
            if _direct is not None:
                return _direct
            return _dijkstra_path_length_inproc(G, source, target, weight=weight)
        _simple, _delegate = _multigraph_collapse_min_weight(G, weight)
        if _delegate:
            return _dijkstra_path_length_inproc(G, source, target, weight=weight)
        return dijkstra_path_length(_simple, source, target, weight=weight)
    route = _dijkstra_weight_route(G, weight)
    if route == "networkx":
        return _dijkstra_path_length_inproc(G, source, target, weight=weight)
    if source not in G:
        raise NodeNotFound(f"Node {source} not found in graph")
    # br-r37-c1-omjmu: nx's _dijkstra raises TypeError on unhashable
    # target during the inner loop. Without this hash-check fnx would
    # silently fall through to ``target not in G`` (silent-False) and
    # raise NetworkXNoPath instead.
    _HASH_PROBE.get(target)
    if target not in G:
        if route == "rows":
            # networkx walks the whole component (reading its weights) first.
            return _rerun_with_weight_scan(dijkstra_path_length, G, source, target, weight)
        raise NetworkXNoPath(f"Node {target} not reachable from {source}")
    # br-r37-c1-04z53.9102: call the target-only native length kernel directly.
    # It preserves nx's int-vs-float result type at the PyO3 boundary, so the
    # wrapper no longer needs to construct the path and re-sum edge attrs here.
    try:
        return _raw_dijkstra_path_length(
            G, source, target, weight=weight, check_rows=route == "rows"
        )
    except NetworkXNoPath as exc:
        raise NetworkXNoPath(f"Node {target} not reachable from {source}") from exc
    except _WeightRowsUnverified:
        pass
    return _rerun_with_weight_scan(dijkstra_path_length, G, source, target, weight)


def bellman_ford_path_length(G, source, target, weight="weight"):
    """Return the shortest weighted path length from ``source`` to ``target`` via Bellman-Ford.

    Handles negative edge weights. Mirrors ``networkx.bellman_ford_path_length``.
    Raises ``NetworkXUnbounded`` on negative cycles reachable from ``source``,
    ``NetworkXNoPath`` if ``target`` is unreachable.
    """
    if _point_query_uses_private_rows(G):
        return _bellman_ford_path_length_inproc(G, source, target, weight=weight)
    # br-r37-c1-bfpathnative: the native single-pair Bellman-Ford kernel returns
    # nx-identical paths (the old br-r37-c1-9axrp "incorrect paths/lengths" note
    # is stale — see bellman_ford_path), so compute the path natively and sum it
    # preserving nx's int-vs-float length type instead of paying the fnx->nx
    # conversion. The wrapper owns nx's error contract (same as bellman_ford_path,
    # but the no-path message and the source==target value differ for the *length*
    # variant): NodeNotFound("Source ... not in G"); NetworkXNoPath("node ... not
    # reachable from ...") for unreachable OR missing target; NetworkXUnbounded
    # ("Negative cycle detected."); source == target -> 0 (before relaxation, so
    # no negative-cycle detection in that case). Callable/non-str/NaN/inf/
    # non-numeric weight delegate (negatives are valid for Bellman-Ford).
    G = _coerce_arg_to_fnx_graph(G)
    _HASH_PROBE.get(source)
    _HASH_PROBE.get(target)
    # br-cc-mgdijkstra: multigraph Bellman-Ford LENGTH -> collapse parallels to the
    # simple min-weight graph (nx uses min weight per pair; length is order-
    # independent) + fast simple kernel. The fused validate+collapse replaces the
    # slow native multigraph kernel AND the two O(|E|) Python gate scans, keeping
    # negatives (valid for Bellman-Ford) and delegating only NaN/inf/nonnumeric.
    if G.is_multigraph() and isinstance(weight, str):
        _simple, _delegate = _multigraph_collapse_min_weight_bellman(G, weight)
        if _delegate:
            return _bellman_ford_path_length_inproc(
                G, source, target, weight=weight
            )
        return bellman_ford_path_length(_simple, source, target, weight=weight)
    route = _bellman_ford_weight_route(G, weight)
    if route == "networkx":
        return _bellman_ford_path_length_inproc(
            G, source, target, weight=weight
        )
    if source not in G:
        raise NodeNotFound(f"Source {source} not in G")
    if source == target:
        return 0
    # br-r37-c1-svsam: the kernel reports the length with networkx's type
    # (int when every edge on the path is int / bool / unweighted). Re-summing
    # the path through G[u][v] exposed each edge dict on it, and an exposed
    # dict makes the next weighted call resync and rescan all E weights - so a
    # repeated query on an UNCHANGED graph paid O(E) every time. The gate above
    # already routes inexact types and int sums past 2**53 to networkx, so the
    # f64 distance of an all-int path is exact.
    if target not in G:
        # networkx walks the source's component (reading its weights) before
        # it finds the target missing, so a negative cycle there wins.
        if route == "rows":
            return _rerun_with_weight_scan(bellman_ford_path_length, G, source, target, weight)
        single_source_bellman_ford_path_length(G, source, weight=weight)
        raise NetworkXNoPath(f"node {target} not reachable from {source}")
    try:
        length, all_int = _raw_bellman_ford_path_length(
            G, source, target, weight=weight, check_rows=route == "rows"
        )
    except NetworkXUnbounded:
        raise NetworkXUnbounded("Negative cycle detected.")
    except (NetworkXNoPath, NodeNotFound):
        raise NetworkXNoPath(f"node {target} not reachable from {source}")
    except _WeightRowsUnverified:
        length = None
    if length is None:
        return _rerun_with_weight_scan(bellman_ford_path_length, G, source, target, weight)
    return int(length) if all_int else length


def negative_edge_cycle(G, weight="weight", heuristic=True):
    """Return ``True`` if ``G`` contains a negative-weight cycle."""
    G = _coerce_arg_to_fnx_graph(G)
    return _negative_edge_cycle_inprocess(G, weight)


def _negative_edge_cycle_inprocess(G, weight):
    from collections import deque as _deque

    if G.number_of_edges() == 0:
        return False

    if callable(weight):
        wt = weight
    elif G.is_multigraph():
        wt = lambda u, v, d: min(attr.get(weight, 1) for attr in d.values())
    else:
        wt = lambda u, v, d: d.get(weight, 1)

    if not G.is_directed():
        # nx's weight function takes G[u][v] - the keydict {key: attrs} on a
        # multigraph, which the min-over-keys wt above expects. Walking
        # edges(data=True) handed it one parallel edge's attr dict instead, and
        # an undirected MultiGraph raised AttributeError ('float' has no 'get').
        for u, nbrs in G.adj.items():
            for v, d in nbrs.items():
                if wt(u, v, d) < 0:
                    return True
        return False

    # Directed
    for u in G:
        if G.has_edge(u, u):
            if G.is_multigraph():
                if any(attr.get(weight, 1) < 0 for attr in G[u][u].values()):
                    return True
            else:
                if wt(u, u, G[u][u]) < 0:
                    return True

    g_succ = {u: {v: wt(u, v, G[u][v]) for v in G[u]} for u in G}
    nodes = list(g_succ)
    newnode = -1
    while newnode in g_succ:
        newnode -= 1
    g_succ[newnode] = dict.fromkeys(nodes, 1)

    n = len(g_succ)
    inf = float("inf")
    dist = {newnode: 0}
    pred = {newnode: []}
    count = {}
    q = _deque([newnode])
    in_q = {newnode}
    while q:
        u = q.popleft()
        in_q.remove(u)
        if all(pred_u not in in_q for pred_u in pred[u]):
            dist_u = dist[u]
            for v, w in g_succ[u].items():
                dist_v = dist_u + w
                if dist_v < dist.get(v, inf):
                    if v not in in_q:
                        q.append(v)
                        in_q.add(v)
                        count_v = count.get(v, 0) + 1
                        if count_v == n:
                            return True
                        count[v] = count_v
                    dist[v] = dist_v
                    pred[v] = [u]
                elif dist.get(v) is not None and dist_v == dist.get(v):
                    pred[v].append(u)
    return False


def _single_source_dijkstra_cutoff_view(source, dists, paths, cutoff):
    # br-r37-c1-djk-cutnan: nx Dijkstra's cutoff check is
    # ``if d > cutoff: continue`` (skip nodes with d > cutoff).
    # For cutoff=NaN, ``d > NaN`` is always False so the check
    # NEVER skips → unbounded result.  fnx used the inverse form
    # ``if distance <= cutoff`` which is ALSO always False for
    # NaN → filters out everything.  Symmetric inversion turned
    # nx's "NaN means unbounded" into fnx's "NaN means empty".
    # Fix: treat NaN (and +inf — same outcome) as ``None``
    # before the filter loop.
    if cutoff is None:
        return dists, paths
    if isinstance(cutoff, float) and (_math.isnan(cutoff) or cutoff == _math.inf):
        return dists, paths

    filtered_dists = {}
    filtered_paths = {}
    if source in dists:
        filtered_dists[source] = dists[source]
        filtered_paths[source] = paths[source]

    for node, distance in dists.items():
        if node == source:
            continue
        if distance <= cutoff:
            filtered_dists[node] = distance
            filtered_paths[node] = paths[node]
    return filtered_dists, filtered_paths


def _sp_edge_weights_all_int(G, weight):
    """Return True iff ``weight`` is a str attr and every edge carries
    an integer value at that attr (including missing → default 1).

    br-ssintfloat: used by single_source_dijkstra / bellman_ford to
    coerce float distances back to int when nx would have preserved
    integer types (nx's weighted shortest-path preserves int when
    every input is int).
    """
    if not isinstance(weight, str):
        return False
    # br-gauntlet-perf1: native O(E) Int-variant scan for simple Graph/DiGraph,
    # avoiding the slow Python EdgeView materialization (this was the dominant
    # residual cost in weighted single_source_dijkstra after the non-numeric
    # gate went native). The caller (single_source_dijkstra) has already synced
    # Python edge attrs into ``inner``. Multigraphs keep the Python scan.
    if (
        _native_edge_weights_all_int is not None
        and not G.is_multigraph()
        and hasattr(G, "_fnx_sync_attrs_to_inner")
    ):
        try:
            native = _native_edge_weights_all_int(G, weight)
        except Exception:
            native = None
        if native is not None:
            return bool(native)
    import numbers as _numbers
    for _, _, attrs in G.edges(data=True):
        if not isinstance(attrs, dict):
            continue
        w = attrs.get(weight, 1)
        if not isinstance(w, _numbers.Integral) or isinstance(w, bool):
            return False
    return True


def _sp_edge_weights_all_float(G, weight):
    """Return True iff ``weight`` is a str attr and EVERY edge carries an
    explicit non-bool ``float`` value at that attr.

    br-apdfloat (cc): when this holds, no shortest-path distance can ever be an
    integer (nx keeps a distance int only when the WHOLE path sums ints; a single
    float taints it, and there are no ints here — a missing attr would default to
    int 1, which is why we require every edge to carry an explicit float). So
    ``_sp_propagate_int_types`` is a guaranteed no-op for every target EXCEPT the
    source seed (nx seeds ``dist[source] = 0`` as int), and the cheap length-only
    kernel suffices — skipping the O(sum-of-path-lengths) per-source path walk
    (per-edge ``G[u][v]`` PyO3 lookups) that dominated weighted all_pairs/closeness
    on float-weighted graphs. Requires at least one edge so an empty graph falls
    through to the unchanged path.
    """
    if not isinstance(weight, str):
        return False
    saw_edge = False
    for _, _, attrs in G.edges(data=True):
        if not isinstance(attrs, dict) or weight not in attrs:
            return False
        w = attrs[weight]
        if isinstance(w, bool) or not isinstance(w, float):
            return False
        saw_edge = True
    return saw_edge


def _sp_weight_type_survives_the_f64_kernel(weight_value):
    """True when a weight VALUE's TYPE comes back out of the native kernel.

    br-r37-c1-3dtn4: networkx never coerces a distance - its type follows the
    Python sum along the path, so ``Fraction`` weights give a ``Fraction``
    distance and numpy scalars give numpy scalars. The native kernel works in
    f64, and the only type it can restore afterwards is ``int``. Anything else
    numeric - Fraction, Decimal, numpy float64/int64 - arrives back as a plain
    float, silently, with the rounding that implies for exact rational work.

    ``bool`` survives because it is restored as ``int``, which is what nx's own
    arithmetic produces (``True + 2`` is ``3``), so it is deliberately NOT
    treated as exotic here.
    """
    return type(weight_value) in (int, float, bool)


def _sp_weights_need_networkx_for_type_parity(G, weight):
    """True when some edge weight's TYPE cannot survive the native kernel.

    br-r37-c1-3dtn4: the callers of this are the routes that reach an f64 kernel
    WITHOUT passing a type-aware gate. Delegating is the only sound repair: once
    the kernel has returned a float, the original ``Fraction`` is gone and no
    amount of post-processing recovers it.

    The native scan answers this for free where it is available - its
    ``has_nonfinite``/``has_nonnumeric`` slots already fold in the exactness
    channel that flags exotic numerics - and it is the same scan
    ``_should_delegate_dijkstra_to_networkx`` consults, so the two cannot drift
    apart. ``has_negative`` is deliberately NOT consulted: Bellman-Ford handles
    negative weights natively and must keep doing so.
    """
    if not isinstance(weight, str):
        return False
    # br-r37-c1-qnj0n: through the shared cache - this scan ran uncached on
    # every weighted Bellman-Ford call.
    scan = _cached_native_weight_scan(G, weight)
    if scan is not None:
        _has_negative, has_nonfinite, has_nonnumeric = scan
        return bool(has_nonfinite or has_nonnumeric)
    if G.is_multigraph():
        rows = (attrs for _u, _v, _k, attrs in G.edges(keys=True, data=True))
    else:
        rows = (attrs for _u, _v, attrs in G.edges(data=True))
    for attrs in rows:
        if isinstance(attrs, dict) and weight in attrs:
            if not _sp_weight_type_survives_the_f64_kernel(attrs[weight]):
                return True
    return False


def _sp_propagate_int_types(G, weight, dists, paths):
    """br-r37-c1-srczero generalized: nx never coerces — each distance's
    TYPE follows the Python sum along the chosen shortest path
    (int+int=int, any float taints). With all-int graphs the blanket
    coercion fast path applies; this handles MIXED graphs by re-deriving
    int-ness along each returned path (the fnx kernel reproduces nx's
    traversal exactly, so the path IS nx's path). Source (path of one
    node, no edges) becomes int 0 — subsumes the literal-int-0 seed."""
    import numbers as _numbers

    multi = G.is_multigraph()
    out = {}
    for node, d in dists.items():
        p = paths.get(node)
        if p is None or d != int(d):
            out[node] = d
            continue
        all_int = True
        for u, v in zip(p, p[1:]):
            if multi:
                cands = [dd.get(weight, 1) for dd in G[u][v].values()]
                w = min(cands)
            else:
                w = G[u][v].get(weight, 1)
            # br-r37-c1-3dtn4: bool is NOT excluded. networkx does no such test -
            # it just adds, and `True + 2` is the int `3` - so a graph mixing
            # True with ints keeps int distances there and lost them here. bool
            # IS Integral for arithmetic, and this helper's whole job is to
            # follow the arithmetic nx performed.
            if not isinstance(w, _numbers.Integral):
                all_int = False
                break
        out[node] = int(d) if all_int else d
    return out


def _sp_coerce_dist_to_int(dists):
    """Coerce integer-valued floats in a distance dict back to int."""
    return {k: (int(v) if isinstance(v, float) and v.is_integer() else v)
            for k, v in dists.items()}


def _reorder_by_distance(dists, *, G=None, source=None, adj=None):
    """Return the keys of ``dists`` sorted by ascending distance, with
    BFS-from-source-adj-iteration order as the tiebreak (matches nx's
    Dijkstra/BF processing order). When G or source is None the tiebreak
    falls back to dict-insertion order (br-r37-c1-62jy2).

    br-r37-c1-reorderfastpath: skip the BFS visit-order build whenever
    the distances are already unique — most weighted-Dijkstra outputs
    have no ties, so the BFS scan (~1ms per source) is pure overhead
    on the all_pairs hot path.  The optional ``adj`` parameter lets
    callers pre-snapshot ``G.adj`` once and reuse it across many
    per-source reorder calls, dropping the PyO3 round-trip cost.
    """
    if G is None or source is None or source not in dists:
        # Stable sort by value preserves insertion order on ties.
        return sorted(dists.keys(), key=lambda k: dists[k])
    # Fast path: if every distance is unique, ``sorted`` by value
    # alone is already deterministic and matches nx's nx-also-sorted
    # output.  ``len(set(dists.values())) == len(dists)`` is O(N).
    values = list(dists.values())
    if len(set(values)) == len(values):
        return sorted(dists.keys(), key=lambda k: dists[k])
    # Slow path: build BFS index for proper tie-break.
    if adj is None:
        bfs_index = {n: i for i, n in enumerate(_bfs_visit_order(G, source))}
    else:
        bfs_index = {n: i for i, n in enumerate(_bfs_visit_order_from_adj(adj, source))}
    return sorted(
        dists.keys(),
        key=lambda k: (dists[k], bfs_index.get(k, float("inf"))),
    )


def _snapshot_edge_weights(G, weight_attr, default=1.0):
    """Build a frozenset-keyed ``{frozenset((u, v)): weight}`` dict so
    callers can look up the weight of an edge in O(1) without paying
    a PyO3 round-trip per lookup.  Used by APSP wrappers that need to
    derive distances from a returned path (br-r37-c1-bfdistderive).
    Returns ``None`` for non-string ``weight_attr`` — callers should
    fall back to whatever existing path they had.
    """
    if not isinstance(weight_attr, str):
        return None
    out = {}
    for u, v, attrs in G.edges(data=True):
        if isinstance(attrs, dict):
            w = attrs.get(weight_attr, default)
        else:
            w = default
        out[frozenset((u, v))] = w
    return out


def _path_lengths_from_paths(paths_by_target, edge_weights):
    """Given ``paths_by_target = {target: [src, ..., target]}`` and a
    ``{frozenset((u, v)): weight}`` lookup dict, return
    ``{target: total_weight}``.  Self-targets (path == [src]) get 0.
    """
    if edge_weights is None:
        return {}
    out = {}
    for target, path in paths_by_target.items():
        total = 0.0
        for i in range(len(path) - 1):
            total += edge_weights.get(frozenset((path[i], path[i + 1])), 1.0)
        out[target] = total
    return out


def _bfs_visit_order_from_adj(adj, source):
    """Same shape as :func:`_bfs_visit_order` but walks a pre-snapshotted
    ``adj`` dict (``{node: list_of_neighbours}``) — avoids PyO3 round-trip
    per visit when the caller is doing many BFS sweeps on the same graph
    (e.g. ``all_pairs_dijkstra`` reorder).
    """
    if source not in adj:
        yield source
        return
    seen = {source}
    yield source
    frontier = [source]
    while frontier:
        next_frontier = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    yield v
                    next_frontier.append(v)
        frontier = next_frontier
