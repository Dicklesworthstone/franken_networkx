

def thresholded_random_geometric_graph(
    n,
    radius,
    theta,
    dim=2,
    pos=None,
    weight=None,
    p=2,
    seed=None,
    *,
    pos_name="pos",
    weight_name="weight",
):
    """Thresholded random geometric graph.

    NX-matching RNG ordering — weights drawn first (from
    ``rng.expovariate(1)`` per node when not supplied), then positions
    (lists of ``rng.random()`` draws when not supplied). Supplied
    ``pos`` / ``weight`` dicts are stored by reference. fnx extensions
    (``weight`` as callable / scalar) are preserved.

    br-r37-c1-trgg-neg: nx raises NetworkXError on negative ``n``;
    fnx previously silently returned an empty graph. Match nx's
    structural-error contract — same fix shape as br-r37-c1-
    {rgg-neg, pjf7g, srgg-neg}.
    """
    _kernel_seed(seed)  # br-r37-c1-cdf1v: nx's decorator resolves the seed first
    if isinstance(n, int) and n < 0:
        raise NetworkXError(f"Negative number of nodes not valid: {n}")
    # br-r37-c1-rgg-dim0: see random_geometric_graph for rationale.
    if isinstance(dim, int) and dim <= 0:
        raise IndexError("Out of bounds on buffer access (axis 0)")
    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: nx's py_random_state
    G = Graph()
    G.add_nodes_from(range(n))
    # br-r37-c1-cdf1v: nx names the graph (G.graph was left empty).
    G.graph["name"] = f"thresholded_random_geometric_graph({n}, {radius}, {theta}, {dim})"

    if weight is None:
        weight = {v: rng.expovariate(1) for v in G}
    elif callable(weight):
        weight = {v: weight() for v in G}
    elif not isinstance(weight, _Mapping):
        weight = {v: weight for v in G}

    if pos is None:
        pos = {v: [rng.random() for _ in range(dim)] for v in G}

    set_node_attributes(G, weight, weight_name)
    set_node_attributes(G, pos, pos_name)

    # br-r37-c1-nt3co: safe-Rust grid candidate generation replaces SciPy here
    # too; threshold filtering still happens in Python in sorted i<j order.
    if n >= 2:
        edge_indexes = _native_geometric_edge_indexes(
            [pos[i] for i in range(n)], radius, p
        )
        if edge_indexes is not None:
            G.add_edges_from(
                (i, j)
                for i, j in edge_indexes
                if weight[i] + weight[j] >= theta
            )
        else:
            _dist = _math.dist if p == 2 else (lambda a, b: _minkowski_distance(a, b, p))
            _edge_batch = []
            for i in range(n):
                for j in range(i + 1, n):
                    d = _dist(pos[i], pos[j])
                    if d <= radius and weight[i] + weight[j] >= theta:
                        _edge_batch.append((i, j))
            G.add_edges_from(_edge_batch)
    return G


def navigable_small_world_graph(n, p=1, q=1, r=2, dim=2, seed=None):
    """Navigable small-world graph (Kleinberg model).

    br-navsw: fnx's prior Python implementation used a bounding-box local
    loop (``range(-p, p+1)``) without Manhattan filtering, overcounting
    local edges. nx's semantics are Manhattan-distance ``d <= p`` + long-
    range draws from a CDF over ``d**-r``. Matches nx exactly now.
    """
    # br-r37-c1-cdf1v: nx's py_random_state, resolved before the p/q/r checks
    # as its decorator does (a bad seed with p < 1 is ValueError).
    rng = _generator_random_state(seed)
    if p < 1:
        raise NetworkXException("p must be >= 1")
    if q < 0:
        raise NetworkXException("q must be >= 0")
    if r < 0:
        raise NetworkXException("r must be >= 0")

    from itertools import product, accumulate
    from bisect import bisect_left

    G = DiGraph()
    nodes = list(product(range(n), repeat=dim))
    for p1 in nodes:
        probs = [0]
        for p2 in nodes:
            if p1 == p2:
                continue
            d = sum(abs(b - a) for a, b in zip(p1, p2))
            if d <= p:
                G.add_edge(p1, p2)
            probs.append(d ** -r)
        cdf = list(accumulate(probs))
        for _ in range(q):
            target = nodes[bisect_left(cdf, rng.uniform(0, cdf[-1]))]
            G.add_edge(p1, target)
    return G


def geometric_edges(G, radius, p=2, *, pos_name="pos"):
    """Return the list of node pairs within ``radius`` Minkowski-p distance.

    Each node in ``G`` must have an attribute named ``pos_name`` (default
    ``"pos"``) holding its coordinates. ``p`` selects the Minkowski metric
    (``1`` Manhattan, ``2`` Euclidean, ``float('inf')`` Chebyshev).
    Matches ``networkx.geometric_edges``: returns a list of edges and does
    not mutate ``G``.
    """
    nodes = list(G.nodes())
    positions = []
    for node in nodes:
        pos = G.nodes[node].get(pos_name)
        if pos is None:
            raise NetworkXError(
                f"Node {node} (and all nodes) must have a '{pos_name}' attribute."
            )
        positions.append(tuple(pos))

    edge_indexes = _native_geometric_edge_indexes(positions, radius, p)
    if edge_indexes is not None:
        return [(nodes[i], nodes[j]) for i, j in edge_indexes]

    edges: list = []
    if p == float("inf"):
        def _within(pu, pv):
            return max(abs(a - b) for a, b in zip(pu, pv)) <= radius
    else:
        radius_p = radius ** p
        def _within(pu, pv):
            return sum(abs(a - b) ** p for a, b in zip(pu, pv)) <= radius_p

    for i in range(len(nodes)):
        pu = positions[i]
        for j in range(i + 1, len(nodes)):
            if _within(pu, positions[j]):
                edges.append((nodes[i], nodes[j]))
    return edges


# Coloring & Planarity (br-y1g)
def _simple_undirected_graph_local(G):
    H = Graph()
    H.add_nodes_from(G.nodes())
    for u, v in G.edges():
        if u != v and not H.has_edge(u, v):
            H.add_edge(u, v)
    return H


def _chromatic_polynomial_signature_local(G):
    nodes = tuple(sorted(_node_order_key_local(node) for node in G.nodes()))
    edges = tuple(
        sorted(
            tuple(
                sorted(
                    (_node_order_key_local(u), _node_order_key_local(v)),
                )
            )
            for u, v in G.edges()
        )
    )
    return (nodes, edges)


def _chromatic_polynomial_simple_local(G, symbol, memo):
    signature = _chromatic_polynomial_signature_local(G)
    if signature in memo:
        return memo[signature]

    if G.number_of_edges() == 0:
        result = symbol ** G.number_of_nodes()
    else:
        edge = next(iter(G.edges()))
        deleted = G.copy()
        deleted.remove_edge(*edge)
        contracted = _simple_undirected_graph_local(
            contracted_edge(G, edge, self_loops=False, copy=True)
        )
        result = _chromatic_polynomial_simple_local(
            deleted, symbol, memo
        ) - _chromatic_polynomial_simple_local(contracted, symbol, memo)

    memo[signature] = result
    return result


def _equitable_make_C_from_F_local(F):
    C = _defaultdict(list)
    for node, color in F.items():
        C[color].append(node)
    return C


def _equitable_make_N_from_L_C_local(L, C):
    nodes = L.keys()
    colors = C.keys()
    return {
        (node, color): sum(1 for v in L[node] if v in C[color])
        for node in nodes
        for color in colors
    }


def _equitable_make_H_from_C_N_local(C, N):
    return {
        (c1, c2): sum(1 for node in C[c1] if N[(node, c2)] == 0)
        for c1 in C
        for c2 in C
    }


def _equitable_change_color_local(u, X, Y, N, H, F, C, L):
    F[u] = Y

    for color in C:
        if N[(u, color)] == 0:
            H[(X, color)] -= 1
            H[(Y, color)] += 1

    for neighbor in L[u]:
        N[(neighbor, X)] -= 1
        N[(neighbor, Y)] += 1

        if N[(neighbor, X)] == 0:
            H[(F[neighbor], X)] += 1
        if N[(neighbor, Y)] == 1:
            H[(F[neighbor], Y)] -= 1

    C[X].remove(u)
    C[Y].append(u)


def _equitable_move_witnesses_local(src_color, dst_color, N, H, F, C, T_cal, L):
    X = src_color
    while X != dst_color:
        Y = T_cal[X]
        witness = next(node for node in C[X] if N[(node, Y)] == 0)
        _equitable_change_color_local(witness, X, Y, N=N, H=H, F=F, C=C, L=L)
        X = Y


def _equitable_pad_graph_local(G, num_colors):
    node_count = len(G)
    r = num_colors - 1
    block_size = node_count // (r + 1)

    if node_count != block_size * (r + 1):
        padding = (r + 1) - node_count % (r + 1)
        K = relabel_nodes(
            complete_graph(padding),
            {idx: idx + node_count for idx in range(padding)},
            copy=True,
        )
        G.add_edges_from(K.edges())


def _equitable_procedure_P_local(
    V_minus, V_plus, N, H, F, C, L, excluded_colors=None
):
    if excluded_colors is None:
        excluded_colors = set()

    A_cal = set()
    T_cal = {}
    R_cal = []

    reachable = [V_minus]
    marked = set(reachable)
    idx = 0
    while idx < len(reachable):
        current = reachable[idx]
        idx += 1
        A_cal.add(current)
        R_cal.append(current)

        next_layer = []
        for color in C:
            if (
                H[(color, current)] > 0
                and color not in A_cal
                and color not in excluded_colors
                and color not in marked
            ):
                next_layer.append(color)

        for dst in next_layer:
            T_cal[dst] = current

        marked.update(next_layer)
        reachable.extend(next_layer)

    b = len(C) - len(A_cal)

    if V_plus in A_cal:
        _equitable_move_witnesses_local(
            V_plus,
            V_minus,
            N=N,
            H=H,
            F=F,
            C=C,
            T_cal=T_cal,
            L=L,
        )
        return

    A_0 = set()
    A_cal_0 = set()
    terminal_sets = 0
    made_equitable = False

    for W_1 in R_cal[::-1]:
        for node in C[W_1]:
            X = None
            for color in C:
                if N[(node, color)] == 0 and color in A_cal and color != W_1:
                    X = color
            if X is None:
                continue

            for color in C:
                if N[(node, color)] >= 1 and color not in A_cal:
                    X_prime = color
                    witness = node
                    try:
                        solo_neighbor = next(
                            candidate
                            for candidate in L[witness]
                            if F[candidate] == X_prime and N[(candidate, W_1)] == 1
                        )
                    except StopIteration:
                        continue

                    _equitable_change_color_local(
                        witness,
                        W_1,
                        X,
                        N=N,
                        H=H,
                        F=F,
                        C=C,
                        L=L,
                    )
                    _equitable_move_witnesses_local(
                        src_color=X,
                        dst_color=V_minus,
                        N=N,
                        H=H,
                        F=F,
                        C=C,
                        T_cal=T_cal,
                        L=L,
                    )
                    _equitable_change_color_local(
                        solo_neighbor,
                        X_prime,
                        W_1,
                        N=N,
                        H=H,
                        F=F,
                        C=C,
                        L=L,
                    )
                    _equitable_procedure_P_local(
                        V_minus=X_prime,
                        V_plus=V_plus,
                        N=N,
                        H=H,
                        C=C,
                        F=F,
                        L=L,
                        excluded_colors=excluded_colors.union(A_cal),
                    )
                    made_equitable = True
                    break

            if made_equitable:
                break
        else:
            A_cal_0.add(W_1)
            A_0.update(C[W_1])
            terminal_sets += 1

        if terminal_sets == b:
            B_cal_prime = set()
            T_cal_prime = {}
            reachable = [V_plus]
            marked = set(reachable)
            idx = 0
            while idx < len(reachable):
                current = reachable[idx]
                idx += 1
                B_cal_prime.add(current)

                next_layer = [
                    color
                    for color in C
                    if H[(current, color)] > 0
                    and color not in B_cal_prime
                    and color not in marked
                ]
                for dst in next_layer:
                    T_cal_prime[current] = dst
                marked.update(next_layer)
                reachable.extend(next_layer)

            independent_set = set()
            covered = set()
            covering = {}
            B_prime = [node for color in B_cal_prime for node in C[color]]

            for z in C[V_plus] + B_prime:
                if z in covered or F[z] not in B_cal_prime:
                    continue

                independent_set.add(z)
                covered.add(z)
                covered.update(L[z])

                for w in L[z]:
                    if F[w] in A_cal_0 and N[(z, F[w])] == 1:
                        if w not in covering:
                            covering[w] = z
                        else:
                            z_1 = covering[w]
                            Z = F[z_1]
                            W = F[w]

                            _equitable_move_witnesses_local(
                                W,
                                V_minus,
                                N=N,
                                H=H,
                                F=F,
                                C=C,
                                T_cal=T_cal,
                                L=L,
                            )
                            _equitable_move_witnesses_local(
                                V_plus,
                                Z,
                                N=N,
                                H=H,
                                F=F,
                                C=C,
                                T_cal=T_cal_prime,
                                L=L,
                            )
                            _equitable_change_color_local(
                                z_1, Z, W, N=N, H=H, F=F, C=C, L=L
                            )
                            W_plus = next(
                                color
                                for color in C
                                if N[(w, color)] == 0 and color not in A_cal
                            )
                            _equitable_change_color_local(
                                w,
                                W,
                                W_plus,
                                N=N,
                                H=H,
                                F=F,
                                C=C,
                                L=L,
                            )
                            excluded_colors.update(
                                [color for color in C if color != W and color not in B_cal_prime]
                            )
                            _equitable_procedure_P_local(
                                V_minus=W,
                                V_plus=W_plus,
                                N=N,
                                H=H,
                                C=C,
                                F=F,
                                L=L,
                                excluded_colors=excluded_colors,
                            )
                            made_equitable = True
                            break

                if made_equitable:
                    break
            else:
                raise AssertionError(
                    "Must find a shared solo-neighbor witness in equitable coloring."
                )

        if made_equitable:
            break


def equitable_color(G, num_colors):
    """Equitable graph coloring: each color class differs by at most 1."""
    native_adjacency = (
        Graph._native_adjacency_keys
        if type(G) is Graph and type(num_colors) is int
        else None
    )
    if callable(native_adjacency):
        # br-r37-c1-l8m9v: the algorithm immediately relabels to dense ints,
        # ignores attributes, and later sorts every node and neighbor. Capture
        # that dense topology in one native crossing instead of constructing a
        # second Graph and then crossing PyO3 once per adjacency row.
        adjacency_rows = native_adjacency(G)
        original_nodes = [node for node, _neighbors in adjacency_rows]
        nodes_to_int = {node: idx for idx, node in enumerate(original_nodes)}
        int_to_nodes = {idx: node for idx, node in enumerate(original_nodes)}
        working_adjacency = [[] for _node in original_nodes]
        for node, neighbors in adjacency_rows:
            working_adjacency[nodes_to_int[node]] = sorted(
                nodes_to_int[neighbor] for neighbor in neighbors
            )
        max_degree = max(
            (
                len(neighbors) + (node in neighbors)
                for node, neighbors in enumerate(working_adjacency)
            ),
            default=0,
        )
        working_graph = None
    else:
        nodes_to_int = {node: idx for idx, node in enumerate(G.nodes)}
        int_to_nodes = {idx: node for node, idx in nodes_to_int.items()}
        working_graph = relabel_nodes(G, nodes_to_int, copy=True)
        working_adjacency = None
        if len(working_graph.nodes) > 0:
            max_degree = max(
                working_graph.degree[node] for node in working_graph.nodes
            )
        else:
            max_degree = 0

    if max_degree >= num_colors:
        raise NetworkXAlgorithmError(
            f"Graph has maximum degree {max_degree}, needs "
            f"{max_degree + 1} (> {num_colors}) colors for guaranteed coloring."
        )

    if working_adjacency is None:
        _equitable_pad_graph_local(working_graph, num_colors)
        working_nodes = working_graph.nodes
        edge_rows = (
            (node, sorted(working_graph.neighbors(node)))
            for node in sorted(working_nodes)
        )
    else:
        node_count = len(working_adjacency)
        block_size = node_count // num_colors
        if node_count != block_size * num_colors:
            padding = num_colors - node_count % num_colors
            # Preserve the current/NetworkX K1 quirk: add_edges_from(K1.edges())
            # adds no node. Kp for p >= 2 contributes the complete clique.
            if padding >= 2:
                first_padding_node = node_count
                padding_stop = node_count + padding
                working_adjacency.extend(
                    [
                        [
                            neighbor
                            for neighbor in range(first_padding_node, padding_stop)
                            if neighbor != node
                        ]
                        for node in range(first_padding_node, padding_stop)
                    ]
                )
        working_nodes = range(len(working_adjacency))
        edge_rows = enumerate(working_adjacency)

    neighborhoods = {node: [] for node in working_nodes}
    coloring = {node: idx % num_colors for idx, node in enumerate(working_nodes)}
    color_classes = _equitable_make_C_from_F_local(coloring)
    color_neighbor_counts = {
        (node, color): 0
        for node in neighborhoods
        for color in color_classes
    }
    witness_graph = _equitable_make_H_from_C_N_local(
        color_classes, color_neighbor_counts
    )

    seen_edges = set()
    for u, neighbors in edge_rows:
        for v in neighbors:
            if (v, u) in seen_edges:
                continue

            seen_edges.add((u, v))
            neighborhoods[u].append(v)
            neighborhoods[v].append(u)
            color_neighbor_counts[(u, coloring[v])] += 1
            color_neighbor_counts[(v, coloring[u])] += 1

            if coloring[u] != coloring[v]:
                if color_neighbor_counts[(u, coloring[v])] == 1:
                    witness_graph[(coloring[u], coloring[v])] -= 1
                if color_neighbor_counts[(v, coloring[u])] == 1:
                    witness_graph[(coloring[v], coloring[u])] -= 1

        if color_neighbor_counts[(u, coloring[u])] != 0:
            new_color = next(
                color for color in color_classes if color_neighbor_counts[(u, color)] == 0
            )
            old_color = coloring[u]
            _equitable_change_color_local(
                u,
                old_color,
                new_color,
                N=color_neighbor_counts,
                H=witness_graph,
                F=coloring,
                C=color_classes,
                L=neighborhoods,
            )
            _equitable_procedure_P_local(
                V_minus=old_color,
                V_plus=new_color,
                N=color_neighbor_counts,
                H=witness_graph,
                F=coloring,
                C=color_classes,
                L=neighborhoods,
            )

    return {int_to_nodes[node]: coloring[node] for node in int_to_nodes}


def chromatic_polynomial(G):
    """Return the chromatic polynomial of an undirected graph."""
    if G.is_directed():
        raise NetworkXNotImplemented("not implemented for directed type")

    import sympy

    if number_of_selfloops(G) > 0:  # br-r37-c1-5i5gb: native O(|V|) check, not O(|E|) EdgeView pass
        return sympy.Integer(0)

    x = sympy.Symbol("x")
    simplified_graph = _simple_undirected_graph_local(G)
    polynomial = _chromatic_polynomial_simple_local(simplified_graph, x, memo={})
    return sympy.simplify(polynomial)


def _embedding_connected_components(embedding):
    nodes = list(embedding.nodes())
    unseen = set(nodes)
    components = []
    while unseen:
        start = next(iter(unseen))
        unseen.remove(start)
        component = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbor in embedding.neighbors_cw_order(node):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def _embedding_set_position(parent, tree, remaining_nodes, delta_x, y_coordinate, pos):
    child = tree[parent]
    if child is not None:
        pos[child] = (pos[parent][0] + delta_x[child], y_coordinate[child])
        remaining_nodes.append(child)


def _embedding_make_bi_connected(embedding, starting_node, outgoing_node, edges_counted):
    if (starting_node, outgoing_node) in edges_counted:
        return []
    edges_counted.add((starting_node, outgoing_node))

    v1 = starting_node
    v2 = outgoing_node
    face_list = [starting_node]
    face_set = set(face_list)
    _, v3 = embedding.next_face_half_edge(v1, v2)

    while v2 != starting_node or v3 != outgoing_node:
        if v1 == v2:
            raise NetworkXError("Invalid half-edge")
        if v2 in face_set:
            embedding.add_half_edge(v1, v3, ccw=v2)
            embedding.add_half_edge(v3, v1, cw=v2)
            edges_counted.add((v2, v3))
            edges_counted.add((v3, v1))
            v2 = v1
        else:
            face_set.add(v2)
            face_list.append(v2)

        v1 = v2
        v2, v3 = embedding.next_face_half_edge(v2, v3)
        edges_counted.add((v1, v2))

    return face_list


def _embedding_triangulate_face(embedding, v1, v2):
    _, v3 = embedding.next_face_half_edge(v1, v2)
    _, v4 = embedding.next_face_half_edge(v2, v3)
    if v1 in (v2, v3):
        return
    while v1 != v4:
        if embedding.has_edge(v1, v3):
            v1, v2, v3 = v2, v3, v4
        else:
            embedding.add_half_edge(v1, v3, ccw=v2)
            embedding.add_half_edge(v3, v1, cw=v2)
            v1, v2, v3 = v1, v3, v4
        _, v4 = embedding.next_face_half_edge(v2, v3)


def _embedding_triangulate(embedding, fully_triangulate=True):
    nodes = list(embedding.nodes())
    if len(nodes) <= 1:
        return embedding, nodes

    embedding = embedding.copy()
    component_nodes = [next(iter(component)) for component in _embedding_connected_components(embedding)]
    for index in range(len(component_nodes) - 1):
        embedding.connect_components(component_nodes[index], component_nodes[index + 1])

    outer_face = []
    face_list = []
    edges_visited = set()
    for v in embedding.nodes():
        for w in embedding.neighbors_cw_order(v):
            new_face = _embedding_make_bi_connected(embedding, v, w, edges_visited)
            if new_face:
                face_list.append(new_face)
                if len(new_face) > len(outer_face):
                    outer_face = new_face

    for face in face_list:
        if face is not outer_face or fully_triangulate:
            _embedding_triangulate_face(embedding, face[0], face[1])

    if fully_triangulate:
        v1 = outer_face[0]
        v2 = outer_face[1]
        v3 = embedding[v2][v1]["ccw"]
        outer_face = [v1, v2, v3]

    return embedding, outer_face


def _embedding_canonical_ordering(embedding, outer_face):
    v1 = outer_face[0]
    v2 = outer_face[1]
    chords = _defaultdict(int)
    marked_nodes = set()
    ready_to_pick = set(outer_face)

    outer_face_ccw_nbr = {}
    prev_nbr = v2
    for index in range(2, len(outer_face)):
        outer_face_ccw_nbr[prev_nbr] = outer_face[index]
        prev_nbr = outer_face[index]
    outer_face_ccw_nbr[prev_nbr] = v1

    outer_face_cw_nbr = {}
    prev_nbr = v1
    for index in range(len(outer_face) - 1, 0, -1):
        outer_face_cw_nbr[prev_nbr] = outer_face[index]
        prev_nbr = outer_face[index]

    def is_outer_face_nbr(x, y):
        if x not in outer_face_ccw_nbr:
            return outer_face_cw_nbr[x] == y
        if x not in outer_face_cw_nbr:
            return outer_face_ccw_nbr[x] == y
        return outer_face_ccw_nbr[x] == y or outer_face_cw_nbr[x] == y

    def is_on_outer_face(x):
        return x not in marked_nodes and (x in outer_face_ccw_nbr or x == v1)

    for v in outer_face:
        for neighbor in embedding.neighbors_cw_order(v):
            if is_on_outer_face(neighbor) and not is_outer_face_nbr(v, neighbor):
                chords[v] += 1
                ready_to_pick.discard(v)

    canonical_ordering = [None] * len(list(embedding.nodes()))
    canonical_ordering[0] = (v1, [])
    canonical_ordering[1] = (v2, [])
    ready_to_pick.discard(v1)
    ready_to_pick.discard(v2)

    for k in range(len(list(embedding.nodes())) - 1, 1, -1):
        v = ready_to_pick.pop()
        marked_nodes.add(v)

        wp = None
        wq = None
        neighbor_iterator = iter(embedding.neighbors_cw_order(v))
        while True:
            neighbor = next(neighbor_iterator)
            if neighbor in marked_nodes:
                continue
            if is_on_outer_face(neighbor):
                if neighbor == v1:
                    wp = v1
                elif neighbor == v2:
                    wq = v2
                elif outer_face_cw_nbr[neighbor] == v:
                    wp = neighbor
                else:
                    wq = neighbor
            if wp is not None and wq is not None:
                break

        wp_wq = [wp]
        neighbor = wp
        while neighbor != wq:
            next_neighbor = embedding[v][neighbor]["ccw"]
            wp_wq.append(next_neighbor)
            outer_face_cw_nbr[neighbor] = next_neighbor
            outer_face_ccw_nbr[next_neighbor] = neighbor
            neighbor = next_neighbor

        if len(wp_wq) == 2:
            chords[wp] -= 1
            if chords[wp] == 0:
                ready_to_pick.add(wp)
            chords[wq] -= 1
            if chords[wq] == 0:
                ready_to_pick.add(wq)
        else:
            new_face_nodes = set(wp_wq[1:-1])
            for w in new_face_nodes:
                ready_to_pick.add(w)
                for neighbor in embedding.neighbors_cw_order(w):
                    if is_on_outer_face(neighbor) and not is_outer_face_nbr(w, neighbor):
                        chords[w] += 1
                        ready_to_pick.discard(w)
                        if neighbor not in new_face_nodes:
                            chords[neighbor] += 1
                            ready_to_pick.discard(neighbor)
        canonical_ordering[k] = (v, wp_wq)

    return canonical_ordering


def combinatorial_embedding_to_pos(embedding, fully_triangulate=False):
    """Convert combinatorial embedding to positions."""
    nodes = list(embedding.nodes())
    if len(nodes) < 4:
        default_positions = [(0, 0), (2, 0), (1, 1)]
        return {node: default_positions[index] for index, node in enumerate(nodes)}

    embedding, outer_face = _embedding_triangulate(embedding, fully_triangulate)

    left_t_child = {}
    right_t_child = {}
    delta_x = {}
    y_coordinate = {}

    node_list = _embedding_canonical_ordering(embedding, outer_face)

    v1, v2, v3 = node_list[0][0], node_list[1][0], node_list[2][0]

    delta_x[v1] = 0
    y_coordinate[v1] = 0
    right_t_child[v1] = v3
    left_t_child[v1] = None

    delta_x[v2] = 1
    y_coordinate[v2] = 0
    right_t_child[v2] = None
    left_t_child[v2] = None

    delta_x[v3] = 1
    y_coordinate[v3] = 1
    right_t_child[v3] = v2
    left_t_child[v3] = None

    for k in range(3, len(node_list)):
        vk, contour_neighbors = node_list[k]
        wp = contour_neighbors[0]
        wp1 = contour_neighbors[1]
        wq = contour_neighbors[-1]
        wq1 = contour_neighbors[-2]
        adds_multiple_triangles = len(contour_neighbors) > 2

        delta_x[wp1] += 1
        delta_x[wq] += 1

        delta_x_wp_wq = sum(delta_x[node] for node in contour_neighbors[1:])
        delta_x[vk] = (-y_coordinate[wp] + delta_x_wp_wq + y_coordinate[wq]) // 2
        y_coordinate[vk] = (y_coordinate[wp] + delta_x_wp_wq + y_coordinate[wq]) // 2
        delta_x[wq] = delta_x_wp_wq - delta_x[vk]
        if adds_multiple_triangles:
            delta_x[wp1] -= delta_x[vk]

        right_t_child[wp] = vk
        right_t_child[vk] = wq
        if adds_multiple_triangles:
            left_t_child[vk] = wp1
            right_t_child[wq1] = None
        else:
            left_t_child[vk] = None

    pos = {v1: (0, y_coordinate[v1])}
    remaining_nodes = [v1]
    while remaining_nodes:
        parent_node = remaining_nodes.pop()
        _embedding_set_position(
            parent_node,
            left_t_child,
            remaining_nodes,
            delta_x,
            y_coordinate,
            pos,
        )
        _embedding_set_position(
            parent_node,
            right_t_child,
            remaining_nodes,
            delta_x,
            y_coordinate,
            pos,
        )
    return pos


def _vf2pp_node_label_value_local(G, node, node_label, default_label):
    return G.nodes[node].get(node_label, default_label)


def _vf2pp_mapping_matches_labels_local(
    G1,
    G2,
    mapping,
    *,
    node_label,
    default_label,
):
    return all(
        _vf2pp_node_label_value_local(G1, left, node_label, default_label)
        == _vf2pp_node_label_value_local(G2, right, node_label, default_label)
        for left, right in mapping.items()
    )


def _vf2pp_labeled_mappings_local(G1, G2, *, node_label, default_label):
    if G1.number_of_nodes() == 0 or G2.number_of_nodes() == 0:
        return []
    if G1.is_directed() != G2.is_directed():
        return []
    if G1.is_multigraph() != G2.is_multigraph():
        return []

    return [
        mapping
        for mapping in _vf2pp_all_isomorphisms_rust(G1, G2)
        if _vf2pp_mapping_matches_labels_local(
            G1,
            G2,
            mapping,
            node_label=node_label,
            default_label=default_label,
        )
    ]


# Isomorphism VF2++ (br-req)
def _isomorphic_mapping_matches_callbacks(G1, G2, mapping, node_match, edge_match):
    """Filter a structural isomorphism mapping through NetworkX-style callbacks."""
    if node_match is not None:
        for node, mapped in mapping.items():
            if not node_match(G1.nodes[node], G2.nodes[mapped]):
                return False

    if edge_match is not None:
        # networkx's matchers call edge_match once per mapped node pair with
        # the two adjacency values G1[u][v] and G2[mu][mv]: the datadicts, or
        # for multigraphs the keydicts ({key: datadict}) that
        # categorical_multiedge_match and friends expect. Pairing individual
        # multigraph datadicts (nro4w.7) handed those helpers bare attribute
        # values: AttributeError: 'int' object has no attribute 'get'.
        directed = G1.is_directed()
        seen = set()
        for u, v in G1.edges():
            pair = (u, v) if directed else frozenset((u, v))
            if pair in seen:
                continue
            seen.add(pair)
            if not edge_match(G1[u][v], G2[mapping[u]][mapping[v]]):
                return False

    if G1.is_multigraph() or G2.is_multigraph():
        # The candidate mappings come from the simple-graph structure; the
        # matchers also demand equal edge multiplicity on every mapped pair
        # (number_of_edges), which also decides a multigraph / simple pair.
        for u, v in G1.edges():
            if G1.number_of_edges(u, v) != G2.number_of_edges(mapping[u], mapping[v]):
                return False
    return True


def could_be_isomorphic(G1, G2, *, properties="dtc"):
    """Return False if graphs are definitely not isomorphic."""
    # br-r37-c1-jwdzp: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    if G1.order() != G2.order():
        return False

    properties_to_check = set(properties)
    G1_props = []
    G2_props = []

    def _properties_consistent():
        g1_table = [tuple(prop[node] for prop in G1_props) for node in G1]
        g2_table = [tuple(prop[node] for prop in G2_props) for node in G2]
        return sorted(g1_table) == sorted(g2_table)

    if "d" in properties_to_check:
        # br-r37-c1-cbiso (cc): materialise the degree map ONCE (native batch ~11us) rather
        # than indexing the DegreeView per node in the table build (PyO3 per-node ~49us);
        # identical values, and most non-isomorphic pairs exit right here on the degree
        # check, so this is the dominant cost.
        G1_props.append(dict(G1.degree()))
        G2_props.append(dict(G2.degree()))
        if not _properties_consistent():
            return False

    if "t" in properties_to_check:
        G1_props.append(triangles(G1))
        G2_props.append(triangles(G2))
        if not _properties_consistent():
            return False

    if "c" in properties_to_check:
        G1_props.append(_Counter(_itertools.chain.from_iterable(find_cliques(G1))))
        G2_props.append(_Counter(_itertools.chain.from_iterable(find_cliques(G2))))
        if not _properties_consistent():
            return False

    return True


def _matcher_factory(nx_matcher_cls):
    class _Matcher(nx_matcher_cls):
        def __init__(self, G1, G2, node_match=None, edge_match=None):
            # Match nx's full constructor signature (br-r37-c1-matchersig).
            # Earlier this factory only accepted (G1, G2), shadowing the
            # node_match/edge_match callbacks nx exposes — drop-in code
            # passing them got TypeError.
            G1_nx = _networkx_graph_for_parity(G1)
            G2_nx = _networkx_graph_for_parity(G2)
            super().__init__(
                G1_nx,
                G2_nx,
                node_match=node_match,
                edge_match=edge_match,
            )

    _Matcher.__name__ = nx_matcher_cls.__name__
    _Matcher.__qualname__ = nx_matcher_cls.__name__
    _Matcher.__doc__ = nx_matcher_cls.__doc__
    return _Matcher


def _build_vf2_matcher_classes():
    import networkx.algorithms.isomorphism as _nxi

    return (
        _matcher_factory(_nxi.GraphMatcher),
        _matcher_factory(_nxi.DiGraphMatcher),
        _matcher_factory(_nxi.MultiGraphMatcher),
        _matcher_factory(_nxi.MultiDiGraphMatcher),
    )


GraphMatcher, DiGraphMatcher, MultiGraphMatcher, MultiDiGraphMatcher = (
    _build_vf2_matcher_classes()
)


def is_isomorphic(G1, G2, node_match=None, edge_match=None):
    """Test graph isomorphism, preserving NetworkX callback semantics."""
    # br-r37-c1-jwdzp: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    # nro4w.7: networkx picks GraphMatcher / DiGraphMatcher and raises for a
    # mixed pair before any matching, callbacks or not (fnx returned False
    # without callbacks). A multigraph / simple-graph pair is NOT rejected:
    # the matcher compares edge multiplicities, so MultiGraph(P4) ~ P4.
    if G1.is_directed() != G2.is_directed():
        raise NetworkXError("Graphs G1 and G2 are not of the same type.")
    if node_match is None and edge_match is None:
        # br-r37-c1-isoprecheck (cc): cheap sound pre-reject before the VF2++
        # rust kernel. faster_could_be_isomorphic is a degree-histogram
        # necessary condition (valid for undirected/directed/multi, ~0.013ms);
        # the rust kernel otherwise pays full VF2 setup (~0.2ms) before
        # rejecting a non-isomorphic pair. Byte-identical result (sound
        # necessary condition; 0 fails / 75 und+dir+sparse pairs). NOT
        # could_be_isomorphic — that raises "not implemented for directed type".
        if not faster_could_be_isomorphic(G1, G2):
            return False
        return _is_isomorphic_rust(G1, G2)

    return any(
        _isomorphic_mapping_matches_callbacks(
            G1,
            G2,
            mapping,
            node_match,
            edge_match,
        )
        for mapping in _vf2pp_all_isomorphisms_rust(G1, G2)
    )


def vf2pp_is_isomorphic(G1, G2, node_label=None, default_label=None):
    """Test isomorphism using VF2++."""
    # br-r37-c1-9rd4z: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    # br-r37-c1-vf2pp-empty: nx's vf2pp treats empty graphs as a
    # degenerate case and returns False / None / [] for the
    # is/get/all forms respectively.  The Rust binding instead
    # treated empty/empty as trivially isomorphic (True / {} / [{}]).
    # Match nx's contract by short-circuiting at the wrapper.
    if G1.number_of_nodes() == 0 or G2.number_of_nodes() == 0:
        return False
    # Fast path: when no label matching needed, use Rust is_isomorphic
    if node_label is None:
        # br-r37-c1-isoprecheck (cc): cheap sound degree-histogram pre-reject
        # before the VF2++ rust kernel (see is_isomorphic). Sound necessary
        # condition for all graph types; byte-identical result.
        if not faster_could_be_isomorphic(G1, G2):
            return False
        return _is_isomorphic_rust(G1, G2)

    return bool(
        _vf2pp_labeled_mappings_local(
            G1,
            G2,
            node_label=node_label,
            default_label=default_label,
        )
    )


def vf2pp_isomorphism(G1, G2, node_label=None, default_label=None):
    """Find one isomorphism mapping using VF2++."""
    # br-r37-c1-9rd4z: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    # br-r37-c1-vf2pp-empty: empty-graph short-circuit (see
    # vf2pp_is_isomorphic).
    if G1.number_of_nodes() == 0 or G2.number_of_nodes() == 0:
        return None
    if node_label is None:
        return _vf2pp_isomorphism_rust(G1, G2)

    mappings = _vf2pp_labeled_mappings_local(
        G1,
        G2,
        node_label=node_label,
        default_label=default_label,
    )
    return mappings[0] if mappings else None


def vf2pp_all_isomorphisms(G1, G2, node_label=None, default_label=None):
    """Generate all isomorphism mappings using VF2++."""
    # br-r37-c1-9rd4z: accept nx-typed inputs.
    G1 = _coerce_arg_to_fnx_graph(G1)
    G2 = _coerce_arg_to_fnx_graph(G2)
    # br-r37-c1-vf2pp-empty: empty-graph short-circuit (see
    # vf2pp_is_isomorphic).
    if G1.number_of_nodes() == 0 or G2.number_of_nodes() == 0:
        return
    if node_label is None:
        yield from _vf2pp_all_isomorphisms_rust(G1, G2)
        return

    yield from _vf2pp_labeled_mappings_local(
        G1,
        G2,
        node_label=node_label,
        default_label=default_label,
    )


def tree_isomorphism(t1, t2, *, backend=None, **backend_kwargs):
    """Return an isomorphism mapping between two trees t1 and t2.

    br-r37-c1-l6zub: parity with nx.isomorphism.tree_isomorphism.
    Delegates to NetworkX (O(n log n) algorithm from Aho-Hopcroft-Ullman).
    """
    _validate_backend_dispatch_keywords(
        "tree_isomorphism",
        backend,
        backend_kwargs,
    )
    import networkx as nx
    # br-r37-c1-treeisocheck (cc): nx's tree_isomorphism itself runs is_tree +
    # faster_could_be_isomorphic (degree-sequence reject) BEFORE the AHU, but the
    # delegate paid a 2x whole-graph fnx->nx conversion first — even for the
    # common case of non-isomorphic trees nx rejects in O(n) (39/39 random
    # distinct trees differ in degree sequence). Do those cheap checks in-process
    # so non-iso short-circuits without converting. Byte-identical: same
    # NotATree contract, [] for non-iso (0 fails / 64 pairs + edge cases vs nx),
    # and the isomorphic-mapping path is unchanged (still the delegate). 0.13x ->
    # 9.61x on the non-iso path.
    if not is_tree(t1):
        raise NetworkXError("t1 is not a tree")
    if not is_tree(t2):
        raise NetworkXError("t2 is not a tree")
    if not faster_could_be_isomorphic(t1, t2):
        return []
    return nx.algorithms.isomorphism.tree_isomorphism(
        _networkx_graph_for_parity(t1),
        _networkx_graph_for_parity(t2),
        backend="networkx",
    )


def rooted_tree_isomorphism(t1, root1, t2, root2, *, backend=None, **backend_kwargs):
    """Return an isomorphism mapping between rooted trees.

    br-r37-c1-07kwm: parity with nx.isomorphism.rooted_tree_isomorphism.
    Delegates to NetworkX (O(n log n) algorithm from Aho-Hopcroft-Ullman).
    """
    _validate_backend_dispatch_keywords(
        "rooted_tree_isomorphism",
        backend,
        backend_kwargs,
    )
    import networkx as nx
    # br-r37-c1-treeisocheck (cc): cheap in-process pre-reject before the 2x
    # fnx->nx conversion + AHU (sibling of tree_isomorphism). A rooted iso is an
    # unrooted iso that maps root->root, so faster_could_be_isomorphic (degree
    # sequence) is a sound necessary condition; non-iso (different degree seq)
    # short-circuits without converting. Byte-identical: NotATree contract + []
    # for non-iso (0 fails vs nx incl varied roots/edge cases); iso-mapping path
    # unchanged. 0.50x -> 66.62x on the non-iso path.
    if not is_tree(t1):
        raise NetworkXError("t1 is not a tree")
    if not is_tree(t2):
        raise NetworkXError("t2 is not a tree")
    if not faster_could_be_isomorphic(t1, t2):
        return []
    return nx.algorithms.isomorphism.rooted_tree_isomorphism(
        _networkx_graph_for_parity(t1),
        root1,
        _networkx_graph_for_parity(t2),
        root2,
        backend="networkx",
    )








_ISOMORPHISM_MODULE_EXPORTS = (
    # br-r37-c1-qliut: deduped — the 4 matcher names below appeared
    # twice in this tuple. Kept the first occurrence only.
    "GraphMatcher",
    "DiGraphMatcher",
    "MultiGraphMatcher",
    "MultiDiGraphMatcher",
    "ISMAGS",
    "TimeRespectingGraphMatcher",
    "TimeRespectingDiGraphMatcher",
    "is_isomorphic",
    "could_be_isomorphic",
    "fast_could_be_isomorphic",
    "faster_could_be_isomorphic",
    "vf2pp_is_isomorphic",
    "vf2pp_isomorphism",
    "vf2pp_all_isomorphisms",
    "tree_isomorphism",
    "rooted_tree_isomorphism",
)


_ISOMORPHISM_MATCHER_HELPERS = (
    "categorical_node_match",
    "categorical_edge_match",
    "categorical_multiedge_match",
    "generic_node_match",
    "generic_edge_match",
    "generic_multiedge_match",
    "numerical_node_match",
    "numerical_edge_match",
    "numerical_multiedge_match",
)


def _build_isomorphism_module():
    from itertools import permutations as _iso_permutations

    def _iso_copyfunc(f, name=None):
        return _types.FunctionType(
            f.__code__, f.__globals__, name or f.__name__, f.__defaults__, f.__closure__
        )

    def _iso_allclose(x, y, rtol=1.0000000000000001e-05, atol=1e-08):
        return all(
            _math.isclose(xi, yi, rel_tol=rtol, abs_tol=atol) for xi, yi in zip(x, y)
        )

    def categorical_node_match(attr, default):
        if isinstance(attr, str):

            def match(data1, data2):
                return data1.get(attr, default) == data2.get(attr, default)

        else:
            attrs = list(zip(attr, default))

            def match(data1, data2):
                return all(data1.get(attr, d) == data2.get(attr, d) for attr, d in attrs)

        return match

    categorical_edge_match = _iso_copyfunc(
        categorical_node_match, "categorical_edge_match"
    )

    def categorical_multiedge_match(attr, default):
        if isinstance(attr, str):

            def match(datasets1, datasets2):
                values1 = {data.get(attr, default) for data in datasets1.values()}
                values2 = {data.get(attr, default) for data in datasets2.values()}
                return values1 == values2

        else:
            attrs = list(zip(attr, default))

            def match(datasets1, datasets2):
                values1 = set()
                for data1 in datasets1.values():
                    x = tuple(data1.get(attr, d) for attr, d in attrs)
                    values1.add(x)
                values2 = set()
                for data2 in datasets2.values():
                    x = tuple(data2.get(attr, d) for attr, d in attrs)
                    values2.add(x)
                return values1 == values2

        return match

    def numerical_node_match(attr, default, rtol=1.0000000000000001e-05, atol=1e-08):
        if isinstance(attr, str):

            def match(data1, data2):
                return _math.isclose(
                    data1.get(attr, default),
                    data2.get(attr, default),
                    rel_tol=rtol,
                    abs_tol=atol,
                )

        else:
            attrs = list(zip(attr, default))

            def match(data1, data2):
                values1 = [data1.get(attr, d) for attr, d in attrs]
                values2 = [data2.get(attr, d) for attr, d in attrs]
                return _iso_allclose(values1, values2, rtol=rtol, atol=atol)

        return match

    numerical_edge_match = _iso_copyfunc(numerical_node_match, "numerical_edge_match")

    def numerical_multiedge_match(
        attr, default, rtol=1.0000000000000001e-05, atol=1e-08
    ):
        if isinstance(attr, str):

            def match(datasets1, datasets2):
                values1 = sorted(data.get(attr, default) for data in datasets1.values())
                values2 = sorted(data.get(attr, default) for data in datasets2.values())
                return _iso_allclose(values1, values2, rtol=rtol, atol=atol)

        else:
            attrs = list(zip(attr, default))

            def match(datasets1, datasets2):
                values1 = []
                for data1 in datasets1.values():
                    x = tuple(data1.get(attr, d) for attr, d in attrs)
                    values1.append(x)
                values2 = []
                for data2 in datasets2.values():
                    x = tuple(data2.get(attr, d) for attr, d in attrs)
                    values2.append(x)
                values1.sort()
                values2.sort()
                for xi, yi in zip(values1, values2):
                    if not _iso_allclose(xi, yi, rtol=rtol, atol=atol):
                        return False
                else:
                    return True

        return match

    def generic_node_match(attr, default, op):
        if isinstance(attr, str):

            def match(data1, data2):
                return op(data1.get(attr, default), data2.get(attr, default))

        else:
            attrs = list(zip(attr, default, op))

            def match(data1, data2):
                for attr, d, operator in attrs:
                    if not operator(data1.get(attr, d), data2.get(attr, d)):
                        return False
                else:
                    return True

        return match

    generic_edge_match = _iso_copyfunc(generic_node_match, "generic_edge_match")

    def generic_multiedge_match(attr, default, op):
        if isinstance(attr, str):
            attr = [attr]
            default = [default]
            op = [op]
        attrs = list(zip(attr, default))

        def match(datasets1, datasets2):
            values1 = []
            for data1 in datasets1.values():
                x = tuple(data1.get(attr, d) for attr, d in attrs)
                values1.append(x)
            values2 = []
            for data2 in datasets2.values():
                x = tuple(data2.get(attr, d) for attr, d in attrs)
                values2.append(x)
            for vals2 in _iso_permutations(values2):
                for xi, yi in zip(values1, vals2):
                    if not all(map(lambda x, y, z: z(x, y), xi, yi, op)):
                        break
                else:
                    return True
            else:
                return False

        return match

    matchers = {
        "categorical_node_match": categorical_node_match,
        "categorical_edge_match": categorical_edge_match,
        "categorical_multiedge_match": categorical_multiedge_match,
        "generic_node_match": generic_node_match,
        "generic_edge_match": generic_edge_match,
        "generic_multiedge_match": generic_multiedge_match,
        "numerical_node_match": numerical_node_match,
        "numerical_edge_match": numerical_edge_match,
        "numerical_multiedge_match": numerical_multiedge_match,
    }

    module = _types.ModuleType(f"{__name__}.isomorphism")
    module.__doc__ = "FrankenNetworkX graph isomorphism API."
    module.__package__ = __name__
    all_exports = list(_ISOMORPHISM_MODULE_EXPORTS) + list(_ISOMORPHISM_MATCHER_HELPERS)
    module.__all__ = all_exports
    for export_name in _ISOMORPHISM_MODULE_EXPORTS:
        setattr(module, export_name, globals()[export_name])
    for helper_name, helper_fn in matchers.items():
        setattr(module, helper_name, helper_fn)
    return module


isomorphism = _build_isomorphism_module()
_sys.modules[f"{__name__}.isomorphism"] = isomorphism


# Tree/Forest Utilities (br-xkr)
def _junction_tree_nx(G):
    from itertools import combinations

    clique_graph = Graph()
    if G.is_directed():
        G = moral_graph(G)
    chordal_graph, _ = complete_to_chordal_graph(G)
    cliques = [
        tuple(sorted(i))
        for i in _chordal_graph_cliques_inprocess(chordal_graph)
    ]
    clique_graph.add_nodes_from(cliques, type="clique")
    for edge in combinations(cliques, 2):
        set_edge_0 = set(edge[0])
        set_edge_1 = set(edge[1])
        if not set_edge_0.isdisjoint(set_edge_1):
            sepset = tuple(sorted(set_edge_0.intersection(set_edge_1)))
            clique_graph.add_edge(
                edge[0], edge[1], weight=len(sepset), sepset=sepset
            )
    jt = maximum_spanning_tree(clique_graph)
    for edge in list(jt.edges(data=True)):
        jt.add_node(edge[2]["sepset"], type="sepset")
        jt.add_edge(edge[0], edge[2]["sepset"])
        jt.add_edge(edge[1], edge[2]["sepset"])
        jt.remove_edge(edge[0], edge[1])
    return jt


def junction_tree(G):
    """Junction tree of a graph.

    br-r37-c1-7hq76: nx.junction_tree uses the sorted-tuple cliques
    themselves as node identifiers and inserts intermediate sepset
    nodes between connected cliques (so the tree is bipartite over
    cliques and sepsets). It also moralizes directed inputs and
    triangulates non-chordal graphs via complete_to_chordal_graph.

    br-r37-c1-jtchord: run nx's exact algorithm IN-PROCESS instead of the
    full ``_call_networkx_for_parity`` conversion-then-nx path. The cost is
    dominated by ``complete_to_chordal_graph`` (nx ~6.5s at n=500) +
    ``chordal_graph_cliques`` (nx ~2.2s); fnx's native
    ``complete_to_chordal_graph`` is byte-identical to nx (same fill edges)
    but ~2.1x faster. The chordal graph is then handed to nx's exact
    ``chordal_graph_cliques`` + maximum-spanning-tree over the clique graph,
    so the resulting junction tree is byte-identical (node/edge/type) to nx
    — verified 320/320 incl. directed — at ~1.6x. The clique ORDER is taken
    from nx's ``chordal_graph_cliques`` on the converted chordal graph (fnx's
    native clique enumeration yields the same SET but a different order, which
    would change the maximum-spanning-tree tie-breaks).
    """
    G = _coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise NetworkXNotImplemented("not implemented for multigraph type")
    return _junction_tree_nx(G)


def join_trees(rooted_trees, *, label_attribute=None, first_label=0):
    """Join a list of rooted trees under a new root.

    Matches networkx's public signature exactly:
    ``join_trees(rooted_trees, *, label_attribute=None, first_label=0)``.

    Parameters
    ----------
    rooted_trees : list of (tree, root) pairs
        Each pair is a NetworkX-compatible tree and the node within
        that tree to use as its root. Nodes are relabelled to integers
        starting at ``first_label + 1``.
    label_attribute : str, optional
        When set, original node labels are stored under this attribute
        on the returned tree.
    first_label : int, optional (default=0)
        Label assigned to the new synthetic root node.
    """
    from itertools import accumulate
    from functools import partial

    if not rooted_trees:
        return empty_graph(1)

    trees, roots = zip(*rooted_trees)

    # Result has the same class as the first tree (matches nx).
    R = type(trees[0])()

    lengths = (len(tree) for tree in trees[:-1])
    first_labels = list(accumulate(lengths, initial=first_label + 1))

    new_roots = []
    for tree, root, first_node in zip(trees, roots, first_labels):
        new_root = first_node + list(tree.nodes()).index(root)
        new_roots.append(new_root)

    relabel = partial(
        convert_node_labels_to_integers, label_attribute=label_attribute
    )
    new_trees = [
        relabel(tree, first_label=fl)
        for tree, fl in zip(trees, first_labels)
    ]

    for tree in new_trees:
        R.update(tree)

    R.add_node(first_label)
    R.add_edges_from((first_label, root) for root in new_roots)

    return R


def random_unlabeled_tree(n, *, number_of_trees=None, seed=None):
    """Uniform random unlabeled tree (Wilf's algorithm, as networkx).

    ``number_of_trees`` matches networkx's public signature. When set,
    returns a list of independently-sampled trees of size *n*.

    br-r37-c1-rut-zero: nx raises ``NetworkXPointlessConcept("the
    null graph is not a tree")`` for n=0; fnx silently returned an
    empty Graph via the random_tree fallback.  Mirror nx's contract.
    """
    # br-r37-c1-cdf1v: networkx's sampler on networkx's RNG handling, the
    # seed resolved first as its decorator does.
    rng = _generator_random_state(seed)
    if n == 0:
        raise NetworkXPointlessConcept("the null graph is not a tree")
    cache_trees = [0, 1]
    cache_forests = [1]
    if number_of_trees is None:
        return _generator_tree_from_edges(
            *_random_unlabeled_tree(n, cache_trees, cache_forests, rng)
        )
    return [
        _generator_tree_from_edges(*_random_unlabeled_tree(n, cache_trees, cache_forests, rng))
        for _ in range(number_of_trees)
    ]


def random_unlabeled_rooted_tree(n, *, number_of_trees=None, seed=None):
    """Return one or more random unlabeled rooted trees."""
    rng = _generator_random_state(seed)  # br-r37-c1-cdf1v: resolved first, as nx's decorator
    if n == 0:
        raise NetworkXPointlessConcept("the null graph is not a tree")
    cache_trees = [0, 1]

    def build_tree():
        edges, nodes = _random_unlabeled_rooted_tree_exact(n, cache_trees, rng)
        return _generator_tree_from_edges(edges, nodes, root=0)

    if number_of_trees is None:
        return build_tree()
    return [build_tree() for _ in range(number_of_trees)]


def random_unlabeled_rooted_forest(n, *, q=None, number_of_forests=None, seed=None):
    """Return one or more random unlabeled rooted forests."""
    rng = _generator_random_state(seed)
    q = n if q is None else q
    if q == 0 and n != 0:
        raise ValueError("q must be a positive integer if n is positive.")

    cache_trees = [0, 1]
    cache_forests = [1]

    def build_forest():
        edges, nodes, roots = _random_unlabeled_rooted_forest_exact(
            n,
            q,
            cache_trees,
            cache_forests,
            rng,
        )
        return _generator_tree_from_edges(edges, nodes, roots=set(roots))

    if number_of_forests is None:
        return build_forest()
    return [build_forest() for _ in range(number_of_forests)]
