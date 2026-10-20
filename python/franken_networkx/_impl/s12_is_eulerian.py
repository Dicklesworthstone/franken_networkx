

def is_eulerian(G):
    """Return True iff *G* is Eulerian (connected + all even degrees).

    The exact simple-Graph path is handled in native index space: row lengths
    provide degree parity, an integer self-loop probe contributes the extra
    NetworkX self-loop degree count, then the existing early-exit native
    connectivity check runs only if parity passes.
    """
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if type(G) is Graph:
        return _raw_is_eulerian(G)
    if G.number_of_nodes() <= 1:
        if G.is_directed():
            # For <=1 nodes the helper is the right answer (nx is_eulerian
            # requires is_strongly_connected on directed input; empty/single
            # cases match).
            if G.number_of_nodes() == 0:
                raise NetworkXPointlessConcept(
                    "Connectivity is undefined for the null graph."
                )
            # Single node with only self-loops: check every degree (including
            # self-loop's +2) is even.
            for node in G.nodes():
                if G.in_degree(node) != G.out_degree(node):
                    return False
            return True
        # Undirected
        if G.number_of_nodes() == 0:
            raise NetworkXPointlessConcept(
                "Connectivity is undefined for the null graph."
            )
        for _, deg in G.degree():
            if deg % 2 != 0:
                return False
        return True
    # br-euldense: the UNDIRECTED native _raw_is_eulerian kernel does O(E) work
    # and was 18-30x slower than nx on dense graphs (K301: 1.65ms vs 0.06ms).
    # nx's test is trivial — all degrees even AND connected — so run it directly
    # (O(V) degree view + native connectivity), matching nx's short-circuit order
    # (degrees first). 7-20x self-speedup, byte-exact. The DIRECTED native kernel
    # is already fast (in/out balance + strong-connectivity in Rust), so keep it.
    if G.is_directed():
        return _raw_is_eulerian(G)
    return all(d % 2 == 0 for _n, d in G.degree()) and is_connected(G)


def eulerian_circuit(G, source=None, keys=False):
    """Return edges of an Eulerian circuit in G.

    Parameters
    ----------
    G : graph
        A graph with an Eulerian circuit.
    source : node, optional
        Starting node for circuit.
    keys : bool, optional
        If True, return edge keys for multigraphs. Default is False.

    Yields
    ------
    edge
        Edges in the Eulerian circuit.

    Notes
    -----
    br-r37-c1-lim0x: Eulerian circuits are non-unique, but nx and the
    Rust binding produced different traversal directions (e.g. fnx
    returned (a,b),(b,c),... while nx returned (a,e),(e,d),...).
    Delegate to nx so the produced edge sequence matches nx's
    documented Hierholzer-traversal contract exactly.

    br-r37-c1-eulcirc (cc): the simple undirected case first ran nx's exact
    Hierholzer on a Python adjacency snapshot (``dict.fromkeys`` preserves
    fnx's adjacency order, so the edge SEQUENCE stayed byte-identical to nx,
    verified 48/48) instead of delegating, which removed the fnx->nx
    conversion cost (was 0.63x).

    br-r37-c1-lim0x follow-through (rc-cgse-witness-routes-obp8v): the native
    Hierholzer kernel now advances in nx's ``G.copy()`` adjacency order (edge
    -emission order — both endpoints appended at first emission), so it is
    byte-identical to nx on non-lex insertion-order fixtures across every
    source (plus error parity on non-Eulerian input). Route the simple
    undirected case to it: byte-parity AND a CGSE witness on the public
    route. Multigraph/directed keep delegating (key ordering).
    """
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ct24s: nx asks is_eulerian first - the null graph raises
    # NetworkXPointlessConcept and a non-Eulerian G "G is not Eulerian."
    # whatever the source - and only then meets the source.
    if not is_eulerian(G):
        raise NetworkXError("G is not Eulerian.")
    if source is not None and source not in G:
        raise NetworkXError(f"Node {source} is not in the graph.")
    if not G.is_multigraph() and (G.is_directed() or number_of_selfloops(G) == 0):
        yield from _fnx.eulerian_circuit(G, source)
        return
    if source is None:
        source = next(iter(G))
    if G.is_multigraph():
        yield from _multigraph_eulerian_circuit_inproc(G, source=source, keys=keys)
    else:
        yield from _simplegraph_eulerian_circuit_inproc(G, source=source)


def _simplegraph_eulerian_circuit_inproc(G, source):
    is_directed = G.is_directed()
    if is_directed:
        adj = {u: {} for u in G}
        for u, nbrs in G.adjacency():
            for v in nbrs:
                adj[v][u] = None
    else:
        adj = {u: dict.fromkeys(nbrs) for u, nbrs in G.adjacency()}
    vertex_stack = [source]
    last_vertex = None
    while vertex_stack:
        current_vertex = vertex_stack[-1]
        adj_cur = adj[current_vertex]
        if not adj_cur:
            if last_vertex is not None:
                yield (last_vertex, current_vertex)
            last_vertex = current_vertex
            vertex_stack.pop()
        else:
            next_vertex = next(iter(adj_cur))
            vertex_stack.append(next_vertex)
            del adj_cur[next_vertex]
            if not is_directed and next_vertex != current_vertex:
                del adj[next_vertex][current_vertex]


def _multigraph_eulerian_circuit_inproc(G, source, keys=False):
    is_directed = G.is_directed()
    adj = {u: {} for u in G}
    if is_directed:
        for u, nbrs in G.adjacency():
            for v, keydict in nbrs.items():
                if u not in adj[v]:
                    adj[v][u] = dict.fromkeys(keydict)
                else:
                    adj[v][u].update(dict.fromkeys(keydict))
    else:
        for u, nbrs in G.adjacency():
            adj_u = adj[u]
            for v, keydict in nbrs.items():
                adj_u[v] = dict.fromkeys(keydict)

    vertex_stack = [(source, None)]
    last_vertex = None
    last_key = None
    while vertex_stack:
        current_vertex, current_key = vertex_stack[-1]
        adj_cur = adj[current_vertex]
        if not adj_cur:
            if last_vertex is not None:
                yield (last_vertex, current_vertex, last_key) if keys else (last_vertex, current_vertex)
            last_vertex, last_key = current_vertex, current_key
            vertex_stack.pop()
        else:
            next_vertex = next(iter(adj_cur))
            next_key_dict = adj_cur[next_vertex]
            next_key = next(iter(next_key_dict))
            vertex_stack.append((next_vertex, next_key))
            del next_key_dict[next_key]
            if not next_key_dict:
                del adj_cur[next_vertex]
            if not is_directed and next_vertex != current_vertex:
                rev_key_dict = adj[next_vertex][current_vertex]
                del rev_key_dict[next_key]
                if not rev_key_dict:
                    del adj[next_vertex][current_vertex]


def _find_path_start_inproc(G):
    if not has_eulerian_path(G):
        return None
    if is_eulerian(G):
        return next(iter(G))
    if G.is_directed():
        v1, v2 = (v for v in G if G.in_degree(v) != G.out_degree(v))
        if G.out_degree(v1) > G.in_degree(v1):
            return v1
        else:
            return v2
    else:
        return [v for v in G if G.degree(v) % 2 != 0][0]


def eulerian_path(G, source=None, keys=False):
    """Return edges of an Eulerian path in G.

    Parameters
    ----------
    G : graph
        A graph with an Eulerian path. Directed and undirected
        (br-r37-c1-z4i7f).
    source : node, optional
        Starting node for path.
    keys : bool, optional
        If True, return edge keys for multigraphs. Default is False.

    Yields
    ------
    edge
        Edges in the Eulerian path.
    """
    # br-r37-c1-eulpath-src-bad: nx raises NetworkXError("Node {n}
    # is not in the graph.") on missing source; fnx's Rust binding
    # raises NodeNotFound (subclass of NetworkXException, NOT
    # NetworkXError).  Pre-validate at the wrapper to match the
    # sibling eulerian_circuit's exception class.
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-ct24s: nx asks has_eulerian_path first - the null graph raises
    # NetworkXPointlessConcept, and a source missing from a non-Eulerian G
    # raises KeyError there (its degree lookup) - and only a G that has the
    # path meets "Node ... is not in the graph."
    if not has_eulerian_path(G, source):
        raise NetworkXError("Graph has no Eulerian paths.")
    if source is not None and source not in G:
        raise NetworkXError(f"Node {source} is not in the graph.")
    if G.is_directed():
        if source is None or is_eulerian(G) is False:
            source = _find_path_start_inproc(G.reverse())
        if G.is_multigraph():
            yield from _multigraph_eulerian_circuit_inproc(G, source=source, keys=keys)
        else:
            yield from _simplegraph_eulerian_circuit_inproc(G, source=source)
    else:
        G = G.copy()
        if source is None:
            source = _find_path_start_inproc(G)
        if G.is_multigraph():
            circuit = list(_multigraph_eulerian_circuit_inproc(G, source=source, keys=True))
            if keys:
                yield from reversed([(v, u, k) for u, v, k in circuit])
            else:
                yield from reversed([(v, u) for u, v, _k in circuit])
        else:
            circuit = list(_simplegraph_eulerian_circuit_inproc(G, source=source))
            yield from reversed([(v, u) for u, v in circuit])


def has_eulerian_path(G, source=None):
    """Return True if G has an Eulerian path.

    Parameters
    ----------
    G : graph
        A graph (directed or undirected).
    source : node, optional
        Starting node for path.

    Returns
    -------
    bool
        True if G has an Eulerian path.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if is_eulerian(G):
        return True

    if G.is_directed():
        ins = G.in_degree
        outs = G.out_degree
        if source is not None and outs[source] - ins[source] != 1:
            return False

        unbalanced_ins = 0
        unbalanced_outs = 0
        for v in G:
            diff = ins[v] - outs[v]
            if diff == 1:
                unbalanced_ins += 1
            elif diff == -1:
                unbalanced_outs += 1
            elif diff != 0:
                return False

        return (
            unbalanced_ins <= 1 and unbalanced_outs <= 1 and is_weakly_connected(G)
        )
    else:
        if source is not None and G.degree[source] % 2 != 1:
            return False

        return sum(d % 2 == 1 for _v, d in G.degree()) == 2 and is_connected(G)

# Algorithm functions — paths and cycles
from franken_networkx._fnx import (
    all_shortest_paths as _raw_all_shortest_paths,
    all_simple_paths as _rust_all_simple_paths,
    cycle_basis as _raw_cycle_basis,
)

# br-rustlag: minimum_cycle_basis ships behind an in-flight Rust
# rebuild. When the .so doesn't export it yet, fall back to the Python
# helper below so fnx still imports.
try:
    from franken_networkx._fnx import minimum_cycle_basis as _raw_minimum_cycle_basis
except ImportError:
    _raw_minimum_cycle_basis = None


def cycle_basis(G, root=None):
    """Return a cycle basis of the graph.

    Matches upstream NetworkX: raises NetworkXNotImplemented on
    multigraph inputs before the basis computation runs, rather than
    silently returning ``[]``.
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if root is not None:
        if root not in G:
            raise KeyError(root)
        return _raw_cycle_basis(G, root=root)
    return _raw_cycle_basis(G)


def _build_paths_from_predecessors(sources, target, pred):
    """Compute all simple paths to target, given predecessors, terminating at sources."""
    if target not in pred:
        raise NetworkXNoPath(f"Target {target} cannot be reached from given sources")

    seen = {target}
    stack = [[target, 0]]
    top = 0
    while top >= 0:
        node, i = stack[top]
        if node in sources:
            yield [p for p, n in reversed(stack[: top + 1])]
        if len(pred[node]) > i:
            stack[top][1] = i + 1
            next_node = pred[node][i]
            if next_node in seen:
                continue
            seen.add(next_node)
            top += 1
            if top == len(stack):
                stack.append([next_node, 0])
            else:
                stack[top][:] = [next_node, 0]
        else:
            seen.discard(node)
            top -= 1


def _rows_hold_other_key_objects(G):
    """True when some adjacency row keys a neighbour by an object other than
    the node's own (an equal key of another type, 1.0 beside node 1)."""
    probe = getattr(G, "_native_has_adj_py_keys", None) or getattr(
        G, "_native_has_succ_py_keys", None
    )
    return probe is None or probe()


def all_shortest_paths(
    G, source, target, weight=None, method="dijkstra", *, backend=None, **backend_kwargs
):
    """Yield every shortest path from ``source`` to ``target``.

    Returns a generator of equal-length minimum-cost paths. ``method`` selects
    the underlying algorithm (``"dijkstra"``, ``"bellman-ford"``, or
    ``"unweighted"``). Mirrors ``networkx.all_shortest_paths``; raises
    ``NetworkXNoPath`` when advanced if no path exists.
    """
    G = _coerce_arg_to_fnx_graph(G)
    # br-r37-c1-6atv8 / br-r37-c1-emxwl: invalid method and missing
    # source raise eagerly, but target-dependent errors happen when
    # the true generator is advanced, matching nx's generator body.
    _validate_backend_dispatch_keywords("all_shortest_paths", backend, backend_kwargs)
    if weight is not None and method not in {"dijkstra", "bellman-ford", "unweighted"}:
        raise ValueError(f"method not supported: {method}")
    # br-r37-c1-jxvsu: missing source raises eagerly with nx wording.
    if source not in G:
        if weight is not None and method != "unweighted":
            raise NodeNotFound(f"Node {source} is not found in the graph")
        raise NodeNotFound(f"Source {source} not in G")

    def _gen():
        # br-r37-c1-omjmu / br-r37-c1-emxwl: nx raises TypeError on
        # unhashable target and NetworkXNoPath on missing target only
        # when the generator is advanced.
        _HASH_PROBE.get(target)
        if target not in G:
            raise NetworkXNoPath(f"Target {target} cannot be reached from given sources")
        # br-r37-c1-qiplw / br-r37-c1-wjz3x: the native ``_raw_all_shortest_paths``
        # kernel (both undirected and directed) now enumerates paths in nx's
        # BFS-predecessor-DAG order (matching _build_paths_from_predecessors), so
        # the unweighted case (weight=None) runs natively instead of paying a
        # full fnx->nx conversion per call. nx forces method='unweighted'
        # whenever weight is None. The binding raises NetworkXNoPath with a
        # different message for an unreachable (but present) target, so re-raise
        # with nx's exact wording.
        if weight is None or method == "unweighted":
            if G.is_multigraph() or _rows_hold_other_key_objects(G):
                # br-r37-c1-7jysw: networkx's own route - predecessor, then the
                # paths out of it - over the index-space predecessor kernel. The
                # native enumerator projects a multigraph to a simple graph first
                # (1.5-6 ms on a 800-node BA graph, 0.12-0.59x networkx), and it
                # emits node objects where networkx's paths carry the row's key
                # (1.0 in a row of a graph whose node is 1).
                built = _raw_predecessor_indexed(G, source, None)
                if built is not None:
                    yield from _build_paths_from_predecessors({source}, target, built[0])
                    return
            try:
                paths = _raw_all_shortest_paths(G, source, target, method="unweighted")
            except NetworkXNoPath:
                raise NetworkXNoPath(
                    f"Target {target} cannot be reached from given sources"
                )
            yield from paths
            return
        if not isinstance(weight, str) or _should_delegate_dijkstra_to_networkx(G, weight) or (
            method == "bellman-ford" and _should_delegate_bellman_ford_to_networkx(weight)
        ):
            if method == "bellman-ford":
                pred, _ = bellman_ford_predecessor_and_distance(G, source, weight=weight)
            else:
                pred, _ = dijkstra_predecessor_and_distance(G, source, weight=weight)
            yield from _build_paths_from_predecessors({source}, target, pred)
            return
        try:
            if isinstance(weight, str):
                # br-r37-c1-4tmgq: the weighted native path reads the Rust store;
                # push post-construction edge attribute writes down first.
                _sync_rust_edge_attrs(G, edge_only=True)
            paths = _raw_all_shortest_paths(G, source, target, weight=weight, method=method)
        except NetworkXNoPath:
            raise NetworkXNoPath(
                f"Target {target} cannot be reached from given sources"
            )
        yield from paths

    return _gen()


def _all_simple_edge_paths_fnx(G, source, target, cutoff):
    if source not in G:
        raise NodeNotFound(f"source node {source} not in graph")
    if target in G:
        targets = {target}
    else:
        try:
            targets = set(target)
        except TypeError as err:
            raise NodeNotFound(f"target node {target} not in graph") from err
    if cutoff is None:
        cutoff = len(G) - 1
    if cutoff < 0 or not targets:
        return

    get_edges = (
        (lambda node: G.edges(node, keys=True))
        if G.is_multigraph()
        else (lambda node: ((node, nbr) for nbr in G.neighbors(node)))
    )

    current_path = {None: None}
    stack = [iter([(None, source)])]
    while stack:
        next_edge = next((e for e in stack[-1] if e[1] not in current_path), None)
        if next_edge is None:
            stack.pop()
            current_path.popitem()
            continue
        _previous_node, next_node, *_ = next_edge
        if next_node in targets:
            yield (list(current_path.values()) + [next_edge])[2:]
        if len(current_path) - 1 < cutoff and (
            targets - current_path.keys() - {next_node}
        ):
            current_path[next_node] = next_edge
            stack.append(iter(get_edges(next_node)))


def _all_simple_paths_fnx(G, source, target, cutoff):
    for edge_path in _all_simple_edge_paths_fnx(G, source, target, cutoff):
        yield [source] + [edge[1] for edge in edge_path]


def all_simple_paths(
    G, source, target, cutoff=None, *, backend=None, **backend_kwargs
):
    """Yield all simple paths from *source* to *target*."""
    _validate_backend_dispatch_keywords("all_simple_paths", backend, backend_kwargs)
    Gc = _coerce_arg_to_fnx_graph(G)
    yield from _all_simple_paths_fnx(Gc, source, target, cutoff)


# Algorithm functions — graph operators
from franken_networkx._fnx import (
    complement as _raw_complement,
)

# Algorithm functions — efficiency
from franken_networkx._fnx import (
    efficiency as _raw_efficiency,
    global_efficiency as _raw_global_efficiency,
    local_efficiency as _raw_local_efficiency,
)


def efficiency(G, u, v):
    """br-isokw: ``G`` matches nx; Rust binding used ``g``.

    br-r37-c1-eff-int0: nx's reference implementation returns
    literal ``int(0)`` on the disconnected case
    (``except NetworkXNoPath: eff = 0``); the Rust raw binding
    returns ``float(0.0)``.  Drop-in callers asserting
    ``isinstance(result, int)`` on disconnected pairs (or
    chaining ``efficiency`` results into other int-only paths)
    saw a type mismatch.  Mirror nx's exact branching so the
    no-path case matches.

    br-r37-c1-eff-msg: also align the bad-source error message
    — nx raises ``NodeNotFound("Source {u} is not in G")`` from
    its underlying single_source_shortest_path call; the Rust
    binding emitted ``Node {u} is not in G``.  Re-raising with
    nx's exact wording keeps regex-matching tests intact.

    br-r37-c1-t2gyx: nx applies @not_implemented_for("directed")
    decorator before the function body — directed input should raise
    NetworkXNotImplemented, not return a centrality value computed
    over the undirected projection. fnx previously silently accepted.
    """
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    try:
        path_length = shortest_path_length(G, u, v)
    except NetworkXNoPath:
        return 0
    except NodeNotFound as exc:
        # Normalise the message to nx's exact wording.  nx
        # raises ``Source {u}`` when the source is missing
        # (single_source_shortest_path's first check) and
        # ``Target {v}`` when only the target is missing
        # (the inner shortest-path machinery).
        if u not in G:
            raise NodeNotFound(f"Source {u} is not in G") from exc
        raise NodeNotFound(f"Target {v} is not in G") from exc
    return 1 / path_length


def global_efficiency(G):
    """br-isokw: ``G`` matches nx.

    br-effdir: nx.global_efficiency is ``@not_implemented_for('directed')``;
    the Rust-native binding silently returns a float for DiGraphs. Reject
    directed input to restore parity. Also return literal int 0 for n<2
    since nx's ``denom = n*(n-1)`` branch initializes ``g_eff = 0`` (int)
    without ever dividing on that path.
    """
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if G.number_of_nodes() < 2:
        return 0
    return _raw_global_efficiency(G)


def local_efficiency(G):
    """br-isokw: ``G`` matches nx.

    br-effdir: nx.local_efficiency is ``@not_implemented_for('directed')``;
    fnx silently returned a float for DiGraphs. Reject directed input.

    br-r37-c1-pb97z: nx raises ZeroDivisionError on the null graph
    (mean of an empty per-node efficiency dict). The Rust impl silently
    returned 0.0; surface the same exception so drop-in code that
    catches ZeroDivisionError on empty inputs keeps working.

    br-r37-c1-vbjbk: snapshot adjacency lists and CPython set order once and
    evaluate induced-subgraph BFS with NetworkX's FilterAtlas branch condition
    (``2 * len(induced) < len(atlas)``) and builtin ``sum()``, matching
    ``nx.local_efficiency`` bit-for-bit (``==``) at ~7x speedup.
    """
    # br-r37-c1-rg8jh: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    n_total = len(G)
    if n_total == 0:
        raise ZeroDivisionError("division by zero")
    nodes = list(G)
    adj_lists = {u: list(G[u]) for u in nodes}
    adj_sets = {u: set(iter(adj_lists[u])) for u in nodes}

    def _ego_eff(v):
        induced = adj_sets[v]
        m = len(induced)
        if m < 2:
            return 0
        denom = m * (m - 1)
        sources = (
            list(induced)
            if 2 * m < n_total
            else [n for n in nodes if n in induced]
        )
        g_eff = 0
        for src in sources:
            seen = {src}
            nextlevel = [src]
            level = 0
            while nextlevel:
                level += 1
                inv_level = 1.0 / level
                thislevel = nextlevel
                nextlevel = []
                for cur in thislevel:
                    adj_cur = adj_lists[cur]
                    if 2 * m < len(adj_cur):
                        cur_set = adj_sets[cur]
                        nbrs = (w for w in induced if w in cur_set)
                    else:
                        nbrs = (w for w in adj_cur if w in induced)
                    for w in nbrs:
                        if w not in seen:
                            seen.add(w)
                            nextlevel.append(w)
                            g_eff += inv_level
                    if len(seen) == m:
                        nextlevel = []
                        break
        return g_eff / denom

    return sum(_ego_eff(v) for v in nodes) / n_total

# Algorithm functions — broadcasting
from franken_networkx._fnx import (
    tree_broadcast_center as _raw_tree_broadcast_center,
    tree_broadcast_time as _raw_tree_broadcast_time,
)


def tree_broadcast_center(G):
    """Return the broadcast center of a tree.

    br-r37-c1-2dwen: nx is decorated with
    ``@not_implemented_for('directed')`` outer and
    ``@not_implemented_for('multigraph')`` inner. nx raises
    'multigraph' first for MultiDiGraph (inner decorator fires
    first) — mirror that ordering.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    return _raw_tree_broadcast_center(G)


def tree_broadcast_time(G, node=None):
    """Return the minimum broadcast time of a (node in a) tree.

    br-r37-c1-2dwen: same multigraph/directed type-guard ordering
    as tree_broadcast_center.

    br-r37-c1-g3fye: raise NodeNotFound with nx's bare-value message
    when ``node`` isn't in G — the Rust binding's NodeNotFound message
    leaks its typed-node representation (``"node str:1:z not in G"``)
    instead of ``"node z not in G"``.
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")
    if node is None:
        return _raw_tree_broadcast_time(G)
    if node not in G:
        raise NodeNotFound(f"node {node} not in G")
    return _raw_tree_broadcast_time(G, node)

# Algorithm functions — traversal (BFS) — wrapped for sort_neighbors support
from franken_networkx._fnx import (
    bfs_edges as _bfs_edges_raw,
    bfs_layers as _bfs_layers_raw,
    bfs_predecessors as _bfs_predecessors_raw,
    bfs_successors as _bfs_successors_raw,
    bfs_tree as _bfs_tree_raw,
    descendants_at_distance as _raw_descendants_at_distance,
)


def bfs_layers(G, sources):
    """Yield BFS layers starting from ``sources``.

    br-r37-c1-omjmu: nx raises ``TypeError`` when any of the given
    sources is unhashable (the inner loop builds a dict keyed on
    sources).  fnx's Rust binding silently treats unhashable
    sources as non-members and yields nothing — eagerly hash-check
    each source so the contract matches nx exactly.
    """
    # nx accepts a single source OR an iterable.  Mirror its
    # ``if sources in G`` test which silently returns False on
    # unhashable: when the bare ``sources`` is hashable and a node,
    # treat as single-source; otherwise iterate.
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    try:
        single_node = sources in G
    except TypeError:
        single_node = False
    if single_node:
        _HASH_PROBE.get(sources)
        sources_list = [sources]
    else:
        # br-r37-c1-bfsl-typeerr: nx raises TypeError when sources
        # is non-iterable AND not in G — its ``set(sources)`` call
        # propagates ``TypeError: 'int' object is not iterable``.
        # fnx previously caught the TypeError here and routed to the
        # Rust raw binding (which then raised NodeNotFound) — too
        # helpful, masked nx's documented contract.  Let the natural
        # TypeError surface.
        sources_list = list(sources)
        for s in sources_list:
            _HASH_PROBE.get(s)
        sources = tuple(sources_list)
    # br-r37-c1-jxvsu: nx raises ``NetworkXError("The node X is not
    # in the graph.")`` when any source is missing; fnx's Rust
    # binding silently yielded nothing for missing sources.
    for s in sources_list:
        if s not in G:
            raise NetworkXError(f"The node {s} is not in the graph.")
    # br-r37-c1-bfsl-gen: ``yield from`` so the wrapper is a true
    # generator function (matches nx's ``isinstance(result,
    # types.GeneratorType)`` contract).  The Rust raw binding
    # returns a ``list_iterator`` (eagerly materialised); without
    # the wrapping yield-from, drop-in callers using
    # ``inspect.isgenerator`` saw a False where nx returned True.
    # br-cc-descmg: on a MULTIGRAPH the raw kernel re-walks the parallel-edge
    # adjacency (0.03x / ~35x slower than nx). A node's BFS layer is exactly its
    # unweighted single_source_shortest_path_length distance, and that kernel is a
    # fnx WIN and yields the dict in BFS-discovery order — so for a SINGLE source
    # group it by distance (layer index ascending, discovery order within a layer,
    # byte-identical to nx.bfs_layers). Multi-source keeps the raw kernel.
    if single_node and G.is_multigraph():
        _spl = single_source_shortest_path_length(G, sources_list[0])
        _layers = {}
        for _node, _dist in _spl.items():
            _layers.setdefault(_dist, []).append(_node)
        for _d in sorted(_layers):
            yield _layers[_d]
        return
    if not single_node and sources in G:
        visited = set(sources_list)
        current_layer = list(visited)
        while current_layer:
            yield current_layer
            next_layer = []
            for node in current_layer:
                for child in G[node]:
                    if child not in visited:
                        visited.add(child)
                        next_layer.append(child)
            current_layer = next_layer
        return
    yield from _bfs_layers_raw(G, sources)


def descendants_at_distance(G, source, distance):
    """Return all nodes at given ``distance`` from ``source`` in ``G``.

    Returns a mutable ``set`` matching nx's contract (br-r37-c1-ohxpp).
    The Rust binding returned an immutable ``frozenset``, breaking
    drop-in code that calls ``.add()`` / ``.remove()`` on the result.

    br-r37-c1-c4agn: nx raises NetworkXError (not NodeNotFound) on
    missing/unhashable source. The Rust binding raised NodeNotFound.
    Translate the missing-node error to NetworkXError to match nx,
    and hash-check up front so unhashable inputs also raise
    NetworkXError (matching nx's pre-hash validation).
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    try:
        _HASH_PROBE.get(source)
    except TypeError as exc:
        raise NetworkXError(
            f"The node {source} is not in the graph."
        ) from exc
    # br-r37-c1-dad-distance / br-r37-c1-miu30: nx iterates BFS layers
    # ``for i, layer in enumerate(bfs_layers(...))`` and returns
    # ``set(layer)`` only when the *integer* layer index ``i == distance``.
    # So the result is non-empty ONLY when ``distance`` equals some
    # non-negative integer: ``2.0`` matches (``2 == 2.0``) and returns
    # layer 2, but ``0.5``/``1.9``/``-1``/non-numeric never equal any ``i``
    # and yield ``set()``. The previous code did ``int(distance)`` which
    # TRUNCATED ``0.5 -> 0`` / ``1.9 -> 1`` and wrongly returned that layer.
    # The Rust binding instead raised OverflowError/TypeError. Match nx's
    # silently-empty-result contract — but still raise NetworkXError if the
    # source isn't in the graph (preserved below).
    try:
        distance_int = int(distance)
    except (TypeError, ValueError):
        distance_int = -1  # sentinel: nx-shaped degenerate-empty result
    if source not in G:
        raise NetworkXError(f"The node {source} is not in the graph.")
    # ``distance != distance_int`` rejects non-integer numerics (0.5, 1.9,
    # -0.5); ``distance_int < 0`` rejects exact negatives and the non-numeric
    # sentinel. Both degenerate to nx's empty ``set()``.
    if distance_int < 0 or distance != distance_int:
        return set()
    # A shortest-path BFS layer cannot reach distance |V|. Bound the native
    # usize conversion too, preserving Python's empty result for huge ints.
    if distance_int >= len(G):
        return set()
    # br-r37-c1-n4j4k: networkx returns set(layer) of the layer LIST, in the
    # order its loop discovers the nodes, and the set's iteration order follows
    # that wherever hashes collide. The native kernel walks the index rows
    # marking only what it reaches (a local query costs its reach, where the
    # kernel this replaced paid an O(V+E) setup - br-r37-c1-dadlocal) and
    # returns the layer in discovery order, as each parent's row shows it.
    if _raw_neighbors_dispatch(G) is not None:
        return set(_raw_descendants_at_distance(G, source, distance_int))
    # A multigraph: networkx's layer BFS over the rows. dict.fromkeys over the
    # frontier's rows keeps each neighbour's first occurrence - the discovery
    # order - at C level (br-r37-c1-dadchain expanded frontiers the same way).
    layer = [source]
    visited = {source}
    _chain = _itertools.chain.from_iterable
    _nbrs = G.neighbors
    for _ in range(distance_int):
        layer = [w for w in dict.fromkeys(_chain(_nbrs(u) for u in layer)) if w not in visited]
        if not layer:
            return set()
        visited.update(layer)
    return set(layer)

# Algorithm functions — traversal (DFS) — wrapped for sort_neighbors support
from franken_networkx._fnx import (
    dfs_edges as _dfs_edges_raw,
    dfs_postorder_nodes as _dfs_postorder_nodes_raw,
    dfs_predecessors as _dfs_predecessors_raw,
    dfs_preorder_nodes as _dfs_preorder_nodes_raw,
    dfs_successors as _dfs_successors_raw,
    dfs_tree as _dfs_tree_raw,
)


def _py_bfs_edges(G, source, depth_limit=None, sort_neighbors=None, reverse=False):
    """networkx's ``bfs_edges``: ``generic_bfs_edges`` over the successors (the
    predecessors when reversing a digraph), each row passed through
    ``sort_neighbors`` as networkx passes it - the row ITERATOR, when the node
    is discovered. ``depth_limit`` is networkx's raw value (NaN, inf, floats
    and negatives compare as networkx compares them)."""
    successors = G.predecessors if reverse and G.is_directed() else G.neighbors
    if sort_neighbors is None:
        return generic_bfs_edges(G, source, successors, depth_limit)
    return generic_bfs_edges(
        G, source, lambda node: iter(sort_neighbors(successors(node))), depth_limit
    )


def _py_dfs_labeled_edges(G, source=None, depth_limit=None, sort_neighbors=None):
    """Python-level DFS labeled edges with sort_neighbors support."""
    nodes = G if source is None else [source]
    if depth_limit is None:
        depth_limit = len(G)

    get_children = (
        G.neighbors
        if sort_neighbors is None
        else lambda n: iter(sort_neighbors(G.neighbors(n)))
    )

    visited = set()
    for start in nodes:
        if start in visited:
            continue
        yield start, start, "forward"
        visited.add(start)
        stack = [(start, get_children(start))]
        depth_now = 1
        while stack:
            parent, children = stack[-1]
            for child in children:
                if child in visited:
                    yield parent, child, "nontree"
                else:
                    yield parent, child, "forward"
                    visited.add(child)
                    if depth_now < depth_limit:
                        stack.append((child, iter(get_children(child))))
                        depth_now += 1
                        break
                    else:
                        yield parent, child, "reverse-depth_limit"
            else:
                stack.pop()
                depth_now -= 1
                if stack:
                    yield stack[-1][0], parent, "reverse"
        yield start, start, "reverse"


def _py_dfs_edges(G, source=None, depth_limit=None, sort_neighbors=None):
    """Python-level DFS with sort_neighbors support."""
    for u, v, label in _py_dfs_labeled_edges(
        G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
    ):
        if label == "forward" and u != v:
            yield (u, v)


def _traversal_missing_source_error(G, source):
    # br-r37-c1-i7asy: nx raises NetworkXError("The node {n} is not in the
    # {graph|digraph}.") for a missing traversal source. The native bfs/dfs
    # bindings instead leak a repr-quoted "The node 'n' is not in the graph."
    # (always 'graph', even for digraphs). Reformat with nx's exact wording,
    # honouring the directed/undirected graph-kind distinction.
    graph_kind = "digraph" if G.is_directed() else "graph"
    return NetworkXError(f"The node {source} is not in the {graph_kind}.")


def bfs_edges(G, source, reverse=False, depth_limit=None, sort_neighbors=None):
    """Yield edges in BFS order from source.

    Private-root graphs and views stream their current rows with the raw
    depth limit and lazy source validation. The native-root route below
    retains its binding-specific argument normalization.

    _Generator function so the returned object is a true generator
    matching nx's contract (br-r37-c1-682kr).

    br-r37-c1-c4agn: hash-check on source eagerly so unhashable
    inputs raise TypeError on call (matching nx's argmap), not
    NetworkXError after iteration starts.

    br-r37-c1-bfs-depth: nx's BFS implementation walks `range
    (depth_limit)` (or while-loop) which trivially yields nothing
    on negative depth — returning empty. The Rust binding declared
    `depth_limit` as unsigned int and raised OverflowError on
    negative values. Match nx by short-circuiting to empty on
    negative depth_limit.
    """
    if _point_query_uses_private_rows(G):
        return _py_bfs_edges(G, source, depth_limit, sort_neighbors, reverse=reverse)
    # br-r37-c1-8xp4a: a reverse view's successors are its root's predecessors.
    root = _reverse_view_root(G)
    if root is not None:
        return bfs_edges(
            root,
            source,
            reverse=not reverse,
            depth_limit=depth_limit,
            sort_neighbors=sort_neighbors,
        )
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    _HASH_PROBE.get(source)
    # br-r37-c1-mub4s: a sort_neighbors walk is networkx's own loop, fed the
    # raw depth_limit.
    if sort_neighbors is not None:
        return _py_bfs_edges(G, source, depth_limit, sort_neighbors, reverse=reverse)
    # br-r37-c1-bfs-cutfloat: nx accepts any numeric ``depth_limit``
    # (NaN / +inf / negative / float).  fnx's Rust binding's PyO3
    # signature requires a non-negative int and raises TypeError /
    # OverflowError on the floats.  Same family as br-r37-c1-asp-nan
    # (all_simple_paths cutoff).  Normalise to None / int / -1 (for
    # short-circuit-empty) before delegating.
    normalized_depth = _normalize_bfs_depth_limit(depth_limit)
    if normalized_depth is _DEPTH_EMPTY:
        # NaN, -inf or a negative depth yields nothing - after networkx has
        # read the source's row, so an absent source still raises.
        return _py_bfs_edges(G, source, depth_limit, reverse=reverse)

    def _gen():
        try:
            yield from _bfs_edges_raw(G, source, reverse=reverse, depth_limit=normalized_depth)
        except NodeNotFound as exc:
            raise _traversal_missing_source_error(G, source) from exc

    return _gen()


_DEPTH_EMPTY = object()  # sentinel for "no traversal" (NaN/-inf/neg)


def _normalize_bfs_depth_limit(depth_limit):
    """Map ``depth_limit`` to a value the Rust BFS binding accepts.

    nx accepts any numeric (or None) and treats NaN / negative as
    "no traversal" empty, +inf as unbounded.  The Rust binding
    only accepts ``None`` or non-negative int.

    Returns:
      * None — unbounded (matches nx None or +inf)
      * non-negative int — bounded (matches nx finite cutoff
        rounded up via ceil)
      * ``_DEPTH_EMPTY`` sentinel — empty iteration (matches nx
        on NaN / -inf / negative int)
    """
    if depth_limit is None:
        return None
    # Numeric — coerce
    try:
        if isinstance(depth_limit, float):
            if _math.isnan(depth_limit):
                return _DEPTH_EMPTY
            if _math.isinf(depth_limit):
                return None if depth_limit > 0 else _DEPTH_EMPTY
            depth_limit = _math.ceil(depth_limit)
        depth_int = int(depth_limit)
    except (TypeError, ValueError):
        return depth_limit  # let downstream surface the error
    if depth_int < 0:
        return _DEPTH_EMPTY
    return depth_int


def _coerce_index_arg(value, arg_name):
    """Coerce an integer-typed argument the way nx does, with nx-shaped errors.

    Several PyO3-bound power-iteration entry points (e.g. ``pagerank``,
    ``eigenvector_centrality``) receive ``max_iter`` in Rust as an
    unsigned int and reject floats with ``TypeError: argument
    'max_iter': 'float' object cannot be interpreted as an integer``.
    nx's pure-Python implementations call ``range(max_iter)`` (which
    invokes ``__index__``) and raise the same TypeError but *without*
    the ``argument 'max_iter':`` prefix.  Drop-in callers that
    regex-match nx's exact wording fail on fnx.

    Use ``_operator.index`` to reproduce nx's TypeError wording exactly
    while still accepting bool/int/numpy-int values.
    """
    if value is None:
        return value
    try:
        return _operator.index(value)
    except TypeError:
        # _operator.index already raises with the nx-shaped message;
        # let it surface unchanged (no PyO3 prefix).
        raise


def _normalize_predecessor_cutoff(cutoff):
    """Normalize ``cutoff`` for predecessor / dijkstra-style functions.

    nx's predecessor loop is roughly::

        while nextlevel:
            level += 1
            ...process this level...
            if cutoff and cutoff <= level: break

    The check is *truthy-aware* — distinct from the BFS-shape
    semantic in ``_normalize_bfs_depth_limit``.  And ``level``
    increments BEFORE the break check, so a positive cutoff N
    admits exactly level N before stopping.  _Mapping:

      * None / 0 / NaN / +inf → None (unbounded — falsy or
        comparison never breaks)
      * -inf / negative finite → 1 (truthy + always <= level → break
        after level 1, matching nx empirical behaviour:
        ``predecessor(P5, 0, cutoff=-1) == {0:[], 1:[0]}``)
      * finite float → ceil
      * positive int → unchanged

    The Rust binding requires int and raises TypeError /
    OverflowError on the floats — this helper converts to one
    of the accepted forms while preserving nx's behaviour.
    """
    if cutoff is None:
        return None
    try:
        if isinstance(cutoff, float):
            if _math.isnan(cutoff):
                return None  # NaN comparisons False → unbounded
            if _math.isinf(cutoff):
                return None if cutoff > 0 else 1
            cutoff = _math.ceil(cutoff)
        cutoff_int = int(cutoff)
    except (TypeError, ValueError):
        return cutoff
    # nx's ``if cutoff and ...`` makes 0 falsy → unbounded
    if cutoff_int == 0:
        return None
    if cutoff_int < 0:
        return 1
    return cutoff_int


def dfs_edges(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """Yield edges in DFS order from source.

    Private-root graphs and views stream the existing Python DFS loop,
    preserving the caller's raw depth limit and lazy source validation.

    _Generator function so the returned object is a true generator
    matching nx's contract (br-r37-c1-682kr).

    br-r37-c1-c4agn: hash-check on source eagerly (when supplied).

    br-r37-c1-dfs-cutfloat: nx accepts any numeric ``depth_limit``
    (NaN / +inf / finite floats); the Rust binding requires
    non-negative int.  Reuse ``_normalize_bfs_depth_limit`` from
    br-r37-c1-bfs-cutfloat to map the non-int cases to nx-shaped
    behaviour (NaN/-inf/neg → empty, +inf → unbounded, finite
    float → ceil).
    """
    if _point_query_uses_private_rows(G):
        return _py_dfs_edges(G, source, depth_limit, sort_neighbors)
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if source is not None:
        _HASH_PROBE.get(source)
    depth_limit = _normalize_bfs_depth_limit(depth_limit)
    if depth_limit is _DEPTH_EMPTY:
        # nx returns the source's first edge (empty if source has
        # no neighbours), which fnx's existing dfs_edges Rust path
        # also yields when depth_limit is 0 — so route NaN/-inf/neg
        # to depth_limit=0 to preserve the "edge to first neighbor
        # only" emission empirically observed via nx.
        depth_limit = 0

    def _gen():
        try:
            if sort_neighbors is not None:
                yield from _py_dfs_edges(G, source, depth_limit, sort_neighbors)
                return
            yield from _dfs_edges_raw(G, source=source, depth_limit=depth_limit)
        except NodeNotFound as exc:
            raise _traversal_missing_source_error(G, source) from exc

    return _gen()


_EDGE_TRAVERSAL_FORWARD = "forward"
_EDGE_TRAVERSAL_REVERSE = "reverse"


def edge_bfs(G, source=None, orientation=None):
    """Iterate edges in breadth-first-search order, matching NetworkX."""
    nbunch_nodes = _global_nbunch_nodes(G, source)
    nodes = list(G) if nbunch_nodes is None else nbunch_nodes
    if not nodes:
        return

    directed = G.is_directed()
    if orientation is None:
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G[node].items():
                    for key in keydict:
                        yield (node, nbr, key)

        else:

            def edges_from(node):
                for nbr in G[node]:
                    yield (node, nbr)

    elif not directed or orientation == "original":
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G[node].items():
                    for key in keydict:
                        yield (node, nbr, key, _EDGE_TRAVERSAL_FORWARD)

        else:

            def edges_from(node):
                for nbr in G[node]:
                    yield (node, nbr, _EDGE_TRAVERSAL_FORWARD)

    elif orientation == "reverse":
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G._native_predecessor_row_dict(node).items():
                    for key in keydict:
                        yield (nbr, node, key, _EDGE_TRAVERSAL_REVERSE)

        else:

            def edges_from(node):
                for nbr in G._native_predecessor_row_dict(node):
                    yield (nbr, node, _EDGE_TRAVERSAL_REVERSE)

    elif orientation == "ignore":
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G[node].items():
                    for key in keydict:
                        yield (node, nbr, key, _EDGE_TRAVERSAL_FORWARD)
                for nbr, keydict in G._native_predecessor_row_dict(node).items():
                    for key in keydict:
                        yield (nbr, node, key, _EDGE_TRAVERSAL_REVERSE)

        else:

            def edges_from(node):
                for nbr in G[node]:
                    yield (node, nbr, _EDGE_TRAVERSAL_FORWARD)
                for nbr in G._native_predecessor_row_dict(node):
                    yield (nbr, node, _EDGE_TRAVERSAL_REVERSE)

    else:
        raise NetworkXError("invalid orientation argument.")

    if directed:

        def edge_id(edge):
            return edge[:-1] if orientation is not None else edge

    else:

        def edge_id(edge):
            return (frozenset(edge[:2]),) + edge[2:]

    check_reverse = directed and orientation in ("reverse", "ignore")
    visited_nodes = set(nodes)
    visited_edges = set()
    queue = _deque((node, edges_from(node)) for node in nodes)

    while queue:
        _parent, children_edges = queue.popleft()
        for edge in children_edges:
            child = edge[0] if check_reverse and edge[-1] == _EDGE_TRAVERSAL_REVERSE else edge[1]
            if child not in visited_nodes:
                visited_nodes.add(child)
                queue.append((child, edges_from(child)))
            current_edge_id = edge_id(edge)
            if current_edge_id not in visited_edges:
                visited_edges.add(current_edge_id)
                yield edge


def edge_dfs(G, source=None, orientation=None):
    """Iterate edges in depth-first-search order, matching NetworkX."""
    nbunch_nodes = _global_nbunch_nodes(G, source)
    nodes = list(G) if nbunch_nodes is None else nbunch_nodes
    if not nodes:
        return

    directed = G.is_directed()
    if orientation is None:
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G[node].items():
                    for key in keydict:
                        yield (node, nbr, key)

        else:

            def edges_from(node):
                for nbr in G[node]:
                    yield (node, nbr)

    elif not directed or orientation == "original":
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G[node].items():
                    for key in keydict:
                        yield (node, nbr, key, _EDGE_TRAVERSAL_FORWARD)

        else:

            def edges_from(node):
                for nbr in G[node]:
                    yield (node, nbr, _EDGE_TRAVERSAL_FORWARD)

    elif orientation == "reverse":
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G._native_predecessor_row_dict(node).items():
                    for key in keydict:
                        yield (nbr, node, key, _EDGE_TRAVERSAL_REVERSE)

        else:

            def edges_from(node):
                for nbr in G._native_predecessor_row_dict(node):
                    yield (nbr, node, _EDGE_TRAVERSAL_REVERSE)

    elif orientation == "ignore":
        if G.is_multigraph():

            def edges_from(node):
                for nbr, keydict in G[node].items():
                    for key in keydict:
                        yield (node, nbr, key, _EDGE_TRAVERSAL_FORWARD)
                for nbr, keydict in G._native_predecessor_row_dict(node).items():
                    for key in keydict:
                        yield (nbr, node, key, _EDGE_TRAVERSAL_REVERSE)

        else:

            def edges_from(node):
                for nbr in G[node]:
                    yield (node, nbr, _EDGE_TRAVERSAL_FORWARD)
                for nbr in G._native_predecessor_row_dict(node):
                    yield (nbr, node, _EDGE_TRAVERSAL_REVERSE)

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
                current_edge_id = edge_id(edge)
                if current_edge_id not in visited_edges:
                    visited_edges.add(current_edge_id)
                    stack.append(
                        edge[0]
                        if check_reverse and edge[-1] == _EDGE_TRAVERSAL_REVERSE
                        else edge[1]
                    )
                    yield edge


def bfs_predecessors(G, source, depth_limit=None, sort_neighbors=None):
    """Return (node, predecessor) pairs from BFS."""
    # br-r37-c1-eghxq: bfs_edges accepts nx-typed inputs, and takes a reverse
    # view to its root without a copy (br-r37-c1-8xp4a).
    return (
        (child, parent)
        for parent, child in bfs_edges(
            G,
            source,
            depth_limit=depth_limit,
            sort_neighbors=sort_neighbors,
        )
    )


def bfs_successors(G, source, depth_limit=None, sort_neighbors=None):
    """Iterate (node, [successors]) pairs in BFS discovery order.

    Matches NetworkX's generator-of-pairs contract, with the source
    appearing first and subsequent parent nodes appearing in the order
    they were discovered by the BFS. Honours the ``sort_neighbors``
    callable when provided.
    """
    # br-r37-c1-8xp4a: a reverse view's successors are its root's predecessors.
    root = _reverse_view_root(G)
    if _point_query_uses_private_rows(G):
        edge_source = _py_bfs_edges(G, source, depth_limit, sort_neighbors)
    elif root is not None:
        edge_source = bfs_edges(
            root,
            source,
            reverse=True,
            depth_limit=depth_limit,
            sort_neighbors=sort_neighbors,
        )
    elif sort_neighbors is not None:
        # br-r37-c1-eghxq: accept nx-typed inputs.
        G = _coerce_arg_to_fnx_graph(G)
        edge_source = _py_bfs_edges(G, source, depth_limit, sort_neighbors)
    else:
        G = _coerce_arg_to_fnx_graph(G)
        # Build edge stream from bfs_edges which already emits in BFS
        # discovery order (matching upstream on both graph and digraph
        # inputs with the same neighbour-iteration order).
        edge_source = bfs_edges(G, source, depth_limit=depth_limit)

    current_parent = None
    current_children = None
    for parent, child in edge_source:
        if parent != current_parent:
            if current_parent is not None:
                yield current_parent, current_children
            current_parent = parent
            current_children = [child]
        else:
            current_children.append(child)
    if current_parent is not None:
        yield current_parent, current_children
    else:
        yield source, []


def bfs_tree(G, source, reverse=False, depth_limit=None, sort_neighbors=None):
    """Return BFS tree rooted at source."""
    if _point_query_uses_private_rows(G):
        T = DiGraph()
        T.add_node(source)
        T.add_edges_from(_py_bfs_edges(G, source, depth_limit, sort_neighbors, reverse=reverse))
        return T
    # br-r37-c1-8xp4a: a reverse view's successors are its root's predecessors.
    root = _reverse_view_root(G)
    if root is not None:
        return bfs_tree(
            root,
            source,
            reverse=not reverse,
            depth_limit=depth_limit,
            sort_neighbors=sort_neighbors,
        )
    G = _coerce_arg_to_fnx_graph(G)
    if sort_neighbors is None:
        try:
            return _bfs_tree_raw(G, source, reverse, depth_limit, None)
        except Exception:
            pass
    if source not in G:
        # nx reaches G.neighbors / G.predecessors, which name the graph kind:
        # "digraph" for a directed G (this said "graph" for every G).
        raise _traversal_missing_source_error(G, source)
    T = DiGraph()
    T.add_node(source)
    T.add_edges_from(
        bfs_edges(
            G,
            source,
            reverse=reverse,
            depth_limit=depth_limit,
            sort_neighbors=sort_neighbors,
        )
    )
    return T


def dfs_predecessors(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """Return (node, predecessor) dict from DFS.

    br-r37-c1-20swv: the Rust _dfs_predecessors_raw returned the dict
    with keys in Rust-internal order rather than nx's DFS-discovery
    order (e.g. fnx {'d':'c','e':'d','b':'a','c':'b'} vs nx
    {'b':'a','c':'b','d':'c','e':'d'}). Build the dict by walking
    dfs_edges so iteration order matches nx exactly. Values
    (parent for each node) were already correct.
    """
    # br-r37-c1-eghxq: accept nx-typed inputs.
    if not _point_query_uses_private_rows(G):
        G = _coerce_arg_to_fnx_graph(G)
    try:
        preds = {}
        for u, v in dfs_edges(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors):
            preds[v] = u
        return preds
    except NodeNotFound as exc:
        raise _traversal_missing_source_error(G, source) from exc


def dfs_successors(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """Return (node, [successors]) dict from DFS.

    The native-root unsorted path uses the native canonical DFS edge stream,
    which preserves NetworkX's DFS-discovery dict order without rebuilding a
    Python ``defaultdict`` from the public ``dfs_edges`` generator.
    """
    if _point_query_uses_private_rows(G):
        successors = {}
        for parent, child in _py_dfs_edges(G, source, depth_limit, sort_neighbors):
            successors.setdefault(parent, []).append(child)
        return successors
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if source is not None:
        _HASH_PROBE.get(source)
    depth_limit = _normalize_bfs_depth_limit(depth_limit)
    if depth_limit is _DEPTH_EMPTY:
        depth_limit = 0
    try:
        if sort_neighbors is None:
            return _dfs_successors_raw(G, source=source, depth_limit=depth_limit)
        from collections import defaultdict as _defaultdict
        succs = _defaultdict(list)
        for u, v in dfs_edges(G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors):
            succs[u].append(v)
        return dict(succs)
    except NodeNotFound as exc:
        raise _traversal_missing_source_error(G, source) from exc


def dfs_preorder_nodes(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """Yield nodes in DFS preorder from source.

    Native-root inputs retain the eager hash check (br-r37-c1-mz7g4).
    Private-root inputs stream labeled events with lazy source validation.
    """
    if _point_query_uses_private_rows(G):
        return (
            node for _, node, label in _py_dfs_labeled_edges(G, source, depth_limit, sort_neighbors)
            if label == "forward"
        )
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if source is not None:
        _HASH_PROBE.get(source)

    def _gen():
        try:
            if sort_neighbors is not None:
                for _, v, label in _py_dfs_labeled_edges(
                    G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
                ):
                    if label == "forward":
                        yield v
                return
            nodes = _dfs_preorder_nodes_raw(G, source=source, depth_limit=depth_limit)
        except NodeNotFound as exc:
            raise _traversal_missing_source_error(G, source) from exc
        yield from nodes

    return _gen()


def dfs_postorder_nodes(G, source=None, depth_limit=None, *, sort_neighbors=None):
    """Yield nodes in DFS postorder from source.

    Native-root inputs retain the eager hash check (br-r37-c1-mz7g4).
    Private-root inputs stream labeled events with lazy source validation.
    """
    if _point_query_uses_private_rows(G):
        return (
            node for _, node, label in _py_dfs_labeled_edges(G, source, depth_limit, sort_neighbors)
            if label == "reverse"
        )
    # br-r37-c1-eghxq: accept nx-typed inputs.
    G = _coerce_arg_to_fnx_graph(G)
    if source is not None:
        _HASH_PROBE.get(source)

    def _gen():
        try:
            if sort_neighbors is not None:
                for _, v, label in _py_dfs_labeled_edges(
                    G, source=source, depth_limit=depth_limit, sort_neighbors=sort_neighbors
                ):
                    if label == "reverse":
                        yield v
                return
            nodes = _dfs_postorder_nodes_raw(G, source=source, depth_limit=depth_limit)
        except NodeNotFound as exc:
            raise _traversal_missing_source_error(G, source) from exc
        yield from nodes

    return _gen()
