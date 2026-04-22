"""Drawing layout helpers."""

import numpy as np
import warnings


def _to_nx(G):
    """Convert an fnx graph to an nx graph for delegation to NetworkX functions.

    This creates a proper nx.Graph (or nx.DiGraph) that can be passed to
    NetworkX functions that require isinstance checks.
    """
    from franken_networkx.backend import _fnx_to_nx

    return _fnx_to_nx(G)


def _process_params(G, center, dim):
    nodes = list(G)
    if center is None:
        center = np.zeros(dim)
    else:
        center = np.asarray(center)

    if len(center) != dim:
        raise ValueError("length of center coordinates must match dimension of layout")

    return nodes, center


def _store_positions(G, pos, store_pos_as):
    if store_pos_as is None or not hasattr(G, "nodes"):
        return

    has_node = getattr(G, "has_node", None)
    for node, coords in pos.items():
        if has_node is not None and not has_node(node):
            continue
        try:
            G.nodes[node][store_pos_as] = coords
        except (KeyError, TypeError):
            continue


def _layout_neighbors(G, node):
    try:
        for neighbor in G[node]:
            yield neighbor
    except (KeyError, TypeError):
        return

    is_directed = getattr(G, "is_directed", lambda: False)
    predecessors = getattr(G, "predecessors", None)
    if is_directed() and predecessors is not None:
        for neighbor in predecessors(node):
            yield neighbor


def _layout_degree(G, node):
    degree = getattr(G, "degree")
    try:
        return degree(node)
    except TypeError:
        return degree[node]


def _bipartite_sets_for_layout(G, nodes):
    import franken_networkx as fnx

    if not nodes:
        return set(), set()

    start = nodes[0]
    color = {start: True}
    stack = [start]
    while stack:
        node = stack.pop()
        for neighbor in _layout_neighbors(G, node):
            if neighbor not in color:
                color[neighbor] = not color[node]
                stack.append(neighbor)
            elif color[neighbor] == color[node]:
                raise fnx.NetworkXError("Graph is not bipartite.")

    if len(color) != len(nodes):
        raise fnx.AmbiguousSolution(
            "Disconnected graph: Ambiguous solution for bipartite sets."
        )

    top = {node for node, is_top in color.items() if is_top}
    bottom = {node for node, is_top in color.items() if not is_top}
    return top, bottom


def _create_random_state(seed):
    if seed is None or seed is np.random:
        return np.random.mtrand._rand
    if isinstance(seed, np.random.RandomState):
        return seed
    if isinstance(seed, int):
        return np.random.RandomState(seed)
    if isinstance(seed, np.random.Generator):
        return seed
    msg = (
        f"{seed} cannot be used to create a numpy.random.RandomState or\n"
        "numpy.random.Generator instance"
    )
    raise ValueError(msg)


def rescale_layout(pos, scale=1):
    """Return scaled positions with largest coordinate magnitude equal to scale."""
    pos -= pos.mean(axis=0)
    lim = np.abs(pos).max()
    if lim > 0:
        pos *= scale / lim
    return pos


def arf_layout(
    G,
    pos=None,
    scaling=1,
    a=1.1,
    etol=1e-6,
    dt=1e-3,
    max_iter=1000,
    *,
    seed=None,
    store_pos_as=None,
):
    """Position nodes using the attractive-repulsive force layout."""
    if a <= 1:
        raise ValueError("The parameter a should be larger than 1")

    nodes = list(G)
    pos_tmp = random_layout(G, seed=seed)
    if pos is None:
        pos = pos_tmp
    else:
        pos = dict(pos)
        for node in nodes:
            if node not in pos:
                pos[node] = pos_tmp[node].copy()

    node_count = len(nodes)
    if node_count == 0:
        return pos

    springs = np.ones((node_count, node_count)) - np.eye(node_count)
    node_order = {node: index for index, node in enumerate(nodes)}
    for left, right in G.edges():
        if left != right:
            left_index, right_index = (node_order[node] for node in (left, right))
            springs[left_index, right_index] = a

    pos_arr = np.asarray(list(pos.values()))
    rho = scaling * np.sqrt(node_count)

    error = etol + 1
    iteration = 0
    while error > etol:
        diff = pos_arr[:, np.newaxis] - pos_arr[np.newaxis]
        distance = np.linalg.norm(diff, axis=-1)[..., np.newaxis]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            change = springs[..., np.newaxis] * diff - rho / distance * diff
        change = np.nansum(change, axis=0)
        pos_arr += change * dt

        error = np.linalg.norm(change, axis=-1).sum()
        if iteration > max_iter:
            break
        iteration += 1

    pos = dict(zip(nodes, pos_arr))
    _store_positions(G, pos, store_pos_as)
    return pos


def bfs_layout(
    G,
    start,
    *,
    align="vertical",
    scale=1,
    center=None,
    store_pos_as=None,
):
    """Position nodes by breadth-first-search layers."""
    import franken_networkx as fnx

    nodes, center = _process_params(G, center, 2)
    layers = dict(enumerate(fnx.bfs_layers(G, start)))

    if len(nodes) != sum(len(layer_nodes) for layer_nodes in layers.values()):
        raise fnx.NetworkXError(
            "bfs_layout didn't include all nodes. Perhaps use input graph:\n"
            "        G.subgraph(nx.node_connected_component(G, start))"
        )

    return multipartite_layout(
        G,
        subset_key=layers,
        align=align,
        scale=scale,
        center=center,
        store_pos_as=store_pos_as,
    )


def bipartite_layout(
    G,
    nodes=None,
    align="vertical",
    scale=1,
    center=None,
    aspect_ratio=4 / 3,
    store_pos_as=None,
):
    """Position bipartite nodes in two aligned layers."""
    if align not in ("vertical", "horizontal"):
        raise ValueError("align must be either vertical or horizontal.")

    graph_nodes, center = _process_params(G, center, 2)
    if len(graph_nodes) == 0:
        return {}

    height = 1
    width = aspect_ratio * height
    offset = (width / 2, height / 2)

    if nodes is None:
        top, bottom = _bipartite_sets_for_layout(G, graph_nodes)
        layout_nodes = list(G)
    else:
        top = set(nodes)
        bottom = set(G) - top
        layout_nodes = list(top) + list(bottom)

    left_xs = np.repeat(0, len(top))
    right_xs = np.repeat(width, len(bottom))
    left_ys = np.linspace(0, height, len(top))
    right_ys = np.linspace(0, height, len(bottom))

    top_pos = np.column_stack([left_xs, left_ys]) - offset
    bottom_pos = np.column_stack([right_xs, right_ys]) - offset

    pos_arr = np.concatenate([top_pos, bottom_pos])
    pos_arr = rescale_layout(pos_arr, scale=scale) + center
    if align == "horizontal":
        pos_arr = pos_arr[:, ::-1]
    pos = dict(zip(layout_nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def spring_layout(
    G,
    k=None,
    pos=None,
    fixed=None,
    iterations=50,
    threshold=1e-4,
    weight="weight",
    scale=1,
    center=None,
    dim=2,
    seed=None,
    store_pos_as=None,
    *,
    method="auto",
    gravity=1.0,
):
    """Position nodes using the Fruchterman-Reingold force-directed algorithm."""
    import franken_networkx as fnx

    if method not in ("auto", "force", "energy"):
        raise ValueError("the method must be either auto, force, or energy.")
    if method == "auto":
        method = "force" if len(G) < 500 else "energy"

    nodes, center = _process_params(G, center, dim)
    rng = _create_random_state(seed)

    if fixed is not None:
        if pos is None:
            raise ValueError("nodes are fixed without positions given")
        for node in fixed:
            if node not in pos:
                raise ValueError("nodes are fixed without positions given")
        node_to_index = {node: index for index, node in enumerate(nodes)}
        fixed = np.asarray(
            [node_to_index[node] for node in fixed if node in node_to_index],
            dtype=int,
        )

    if pos is not None:
        dom_size = max(coord for pos_tup in pos.values() for coord in pos_tup)
        if dom_size == 0:
            dom_size = 1
        pos_arr = rng.rand(len(nodes), dim) * dom_size + center
        for index, node in enumerate(nodes):
            if node in pos:
                pos_arr[index] = np.asarray(pos[node])
    else:
        pos_arr = None
        dom_size = 1

    if len(nodes) == 0:
        return {}
    if len(nodes) == 1:
        pos = {nodes[0]: center}
        _store_positions(G, pos, store_pos_as)
        return pos

    if len(nodes) >= 500 or method == "energy":
        adjacency = fnx.to_scipy_sparse_array(G, weight=weight, dtype="f")
        if k is None and fixed is not None:
            nnodes, _ = adjacency.shape
            k = dom_size / np.sqrt(nnodes)
        pos_arr = _sparse_fruchterman_reingold(
            adjacency,
            k,
            pos_arr,
            fixed,
            iterations,
            threshold,
            dim,
            rng,
            method,
            gravity,
        )
    else:
        adjacency = fnx.to_numpy_array(G, weight=weight)
        if k is None and fixed is not None:
            nnodes, _ = adjacency.shape
            k = dom_size / np.sqrt(nnodes)
        pos_arr = _fruchterman_reingold(
            adjacency,
            k,
            pos_arr,
            fixed,
            iterations,
            threshold,
            dim,
            rng,
        )

    if fixed is None and scale is not None:
        pos_arr = rescale_layout(pos_arr, scale=scale) + center
    pos = dict(zip(nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def _fruchterman_reingold(
    adjacency,
    k=None,
    pos=None,
    fixed=None,
    iterations=50,
    threshold=1e-4,
    dim=2,
    seed=None,
):
    """Return dense Fruchterman-Reingold coordinates from an adjacency matrix."""
    import franken_networkx as fnx

    try:
        nnodes, _ = adjacency.shape
    except AttributeError as err:
        msg = "fruchterman_reingold() takes an adjacency matrix as input"
        raise fnx.NetworkXError(msg) from err

    if pos is None:
        pos = np.asarray(seed.rand(nnodes, dim), dtype=adjacency.dtype)
    else:
        pos = pos.astype(adjacency.dtype)

    if k is None:
        k = np.sqrt(1.0 / nnodes)

    temperature = (
        max(max(pos.T[0]) - min(pos.T[0]), max(pos.T[1]) - min(pos.T[1])) * 0.1
    )
    cooling_step = temperature / (iterations + 1)

    for _iteration in range(iterations):
        delta = pos[:, np.newaxis, :] - pos[np.newaxis, :, :]
        distance = np.linalg.norm(delta, axis=-1)
        np.clip(distance, 0.01, None, out=distance)
        displacement = np.einsum(
            "ijk,ij->ik",
            delta,
            (k * k / distance**2 - adjacency * distance / k),
        )
        length = np.linalg.norm(displacement, axis=-1)
        length = np.clip(length, a_min=0.01, a_max=None)
        delta_pos = np.einsum("ij,i->ij", displacement, temperature / length)
        if fixed is not None:
            delta_pos[fixed] = 0.0
        pos += delta_pos
        temperature -= cooling_step
        if (np.linalg.norm(delta_pos) / nnodes) < threshold:
            break

    return pos


def _sparse_fruchterman_reingold(
    adjacency,
    k=None,
    pos=None,
    fixed=None,
    iterations=50,
    threshold=1e-4,
    dim=2,
    seed=None,
    method="energy",
    gravity=1.0,
):
    """Return sparse Fruchterman-Reingold coordinates from an adjacency matrix."""
    import scipy as sp
    import franken_networkx as fnx

    try:
        nnodes, _ = adjacency.shape
    except AttributeError as err:
        msg = "fruchterman_reingold() takes an adjacency matrix as input"
        raise fnx.NetworkXError(msg) from err

    if pos is None:
        pos = np.asarray(seed.rand(nnodes, dim), dtype=adjacency.dtype)
    else:
        pos = pos.astype(adjacency.dtype)

    if fixed is None:
        fixed = []

    if k is None:
        k = np.sqrt(1.0 / nnodes)

    if method == "energy":
        return _energy_fruchterman_reingold(
            adjacency,
            nnodes,
            k,
            pos,
            fixed,
            iterations,
            threshold,
            dim,
            gravity,
        )

    try:
        adjacency = adjacency.tolil()
    except AttributeError:
        adjacency = sp.sparse.coo_array(adjacency).tolil()

    temperature = (
        max(max(pos.T[0]) - min(pos.T[0]), max(pos.T[1]) - min(pos.T[1])) * 0.1
    )
    cooling_step = temperature / (iterations + 1)
    displacement = np.zeros((dim, nnodes))

    for _iteration in range(iterations):
        displacement *= 0
        for index in range(adjacency.shape[0]):
            if index in fixed:
                continue
            delta = (pos[index] - pos).T
            distance = np.sqrt((delta**2).sum(axis=0))
            distance = np.clip(distance, a_min=0.01, a_max=None)
            row = adjacency.getrowview(index).toarray()
            displacement[:, index] += (
                delta * (k * k / distance**2 - row * distance / k)
            ).sum(axis=1)
        length = np.sqrt((displacement**2).sum(axis=0))
        length = np.clip(length, a_min=0.01, a_max=None)
        delta_pos = (displacement * temperature / length).T
        pos += delta_pos
        temperature -= cooling_step
        if (np.linalg.norm(delta_pos) / nnodes) < threshold:
            break

    return pos


def _energy_fruchterman_reingold(
    adjacency,
    nnodes,
    k,
    pos,
    fixed,
    iterations,
    threshold,
    dim,
    gravity,
):
    """Return energy-optimized Fruchterman-Reingold coordinates."""
    import scipy as sp

    if gravity <= 0:
        raise ValueError("the gravity must be positive.")

    if iterations == 0:
        return pos.copy()

    try:
        adjacency = adjacency.tocsr()
    except AttributeError:
        adjacency = sp.sparse.csr_array(adjacency)

    adjacency = np.abs(adjacency)
    adjacency = (adjacency + adjacency.T) / 2

    n_components, labels = sp.sparse.csgraph.connected_components(
        adjacency,
        directed=False,
    )
    bincount = np.bincount(labels)
    batch_size = 500

    def cost_fr(x):
        current_pos = x.reshape((nnodes, dim))
        grad = np.zeros((nnodes, dim))
        cost = 0.0
        for left in range(0, nnodes, batch_size):
            right = min(left + batch_size, nnodes)
            delta = current_pos[left:right, np.newaxis, :] - current_pos[
                np.newaxis, :, :
            ]
            distance_squared = np.sum(delta * delta, axis=2)
            distance_squared = np.maximum(distance_squared, 1e-10)
            distance = np.sqrt(distance_squared)
            adjacency_distance = adjacency[left:right] * distance
            grad[left:right] = 2 * np.einsum(
                "ij,ijk->ik",
                adjacency_distance / k - k**2 / distance_squared,
                delta,
            )
            cost += np.sum(adjacency_distance * distance_squared) / (3 * k)
            cost -= k**2 * np.sum(np.log(distance))
        centers = np.zeros((n_components, dim))
        np.add.at(centers, labels, current_pos)
        delta0 = centers / bincount[:, np.newaxis] - 0.5
        grad += gravity * delta0[labels]
        cost += gravity * 0.5 * np.sum(
            bincount * np.linalg.norm(delta0, axis=1) ** 2
        )
        grad[fixed] = 0.0
        return cost, grad.ravel()

    options = {"maxiter": iterations, "gtol": threshold}
    return sp.optimize.minimize(
        cost_fr,
        pos.ravel(),
        method="L-BFGS-B",
        jac=True,
        options=options,
    ).x.reshape((nnodes, dim))


def circular_layout(G, scale=1, center=None, dim=2, store_pos_as=None):
    """Position nodes on a circle."""
    if dim < 2:
        raise ValueError("cannot handle dimensions < 2")

    nodes, center = _process_params(G, center, dim)
    paddims = max(0, dim - 2)

    if len(nodes) == 0:
        pos = {}
    elif len(nodes) == 1:
        pos = {nodes[0]: center}
    else:
        theta = np.linspace(0, 1, len(nodes) + 1)[:-1] * 2 * np.pi
        theta = theta.astype(np.float32)
        pos_arr = np.column_stack(
            [np.cos(theta), np.sin(theta), np.zeros((len(nodes), paddims))]
        )
        pos_arr = rescale_layout(pos_arr, scale=scale) + center
        pos = dict(zip(nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def random_layout(G, center=None, dim=2, seed=None, store_pos_as=None):
    """Position nodes uniformly at random."""
    nodes, center = _process_params(G, center, dim)
    rng = _create_random_state(seed)
    pos_arr = rng.rand(len(nodes), dim) + center
    pos_arr = pos_arr.astype(np.float32)
    pos = dict(zip(nodes, pos_arr))
    _store_positions(G, pos, store_pos_as)
    return pos


def shell_layout(G, nlist=None, rotate=None, scale=1, center=None, dim=2, store_pos_as=None):
    """Position nodes in concentric circles."""
    if dim != 2:
        raise ValueError("can only handle 2 dimensions")

    nodes, center = _process_params(G, center, dim)

    if len(nodes) == 0:
        return {}
    if len(nodes) == 1:
        pos = {nodes[0]: center}
        _store_positions(G, pos, store_pos_as)
        return pos

    if nlist is None:
        nlist = [nodes]

    radius_bump = scale / len(nlist)
    radius = 0.0 if len(nlist[0]) == 1 else radius_bump

    if rotate is None:
        rotate = np.pi / len(nlist)
    first_theta = rotate
    pos = {}
    for shell_nodes in nlist:
        theta = (
            np.linspace(0, 2 * np.pi, len(shell_nodes), endpoint=False, dtype=np.float32)
            + first_theta
        )
        shell_pos = radius * np.column_stack([np.cos(theta), np.sin(theta)]) + center
        pos.update(zip(shell_nodes, shell_pos))
        radius += radius_bump
        first_theta += rotate

    _store_positions(G, pos, store_pos_as)
    return pos


def spectral_layout(G, weight="weight", scale=1, center=None, dim=2, store_pos_as=None):
    """Position nodes using eigenvectors of the graph Laplacian."""
    import franken_networkx as fnx

    nodes, center = _process_params(G, center, dim)

    if len(nodes) <= 2:
        if len(nodes) == 0:
            pos_arr = np.array([])
        elif len(nodes) == 1:
            pos_arr = np.array([center])
        else:
            pos_arr = np.array([np.zeros(dim), np.array(center) * 2.0])
        return dict(zip(nodes, pos_arr))

    try:
        if len(nodes) < 500:
            raise ValueError
        adjacency = fnx.to_scipy_sparse_array(G, weight=weight, dtype="d")
        if G.is_directed():
            adjacency = adjacency + adjacency.T
        pos_arr = _sparse_spectral(adjacency, dim)
    except (ImportError, ValueError):
        adjacency = fnx.to_numpy_array(G, weight=weight)
        if G.is_directed():
            adjacency += adjacency.T
        pos_arr = _spectral(adjacency, dim)

    pos_arr = rescale_layout(pos_arr, scale=scale) + center
    pos = dict(zip(nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def _spectral(adjacency, dim=2):
    """Return dense spectral coordinates from an adjacency matrix."""
    import franken_networkx as fnx

    try:
        nnodes, _ = adjacency.shape
    except AttributeError as err:
        msg = "spectral() takes an adjacency matrix as input"
        raise fnx.NetworkXError(msg) from err

    degree = np.identity(nnodes, dtype=adjacency.dtype) * np.sum(adjacency, axis=1)
    laplacian = degree - adjacency

    eigenvalues, eigenvectors = np.linalg.eig(laplacian)
    index = np.argsort(eigenvalues)[1 : dim + 1]
    return np.real(eigenvectors[:, index])


def _sparse_spectral(adjacency, dim=2):
    """Return sparse spectral coordinates from an adjacency matrix."""
    import scipy as sp
    import franken_networkx as fnx

    try:
        nnodes, _ = adjacency.shape
    except AttributeError as err:
        msg = "sparse_spectral() takes an adjacency matrix as input"
        raise fnx.NetworkXError(msg) from err

    degree = sp.sparse.dia_array(
        (adjacency.sum(axis=1), 0),
        shape=(nnodes, nnodes),
    ).tocsr()
    laplacian = degree - adjacency

    k = dim + 1
    ncv = max(2 * k + 1, int(np.sqrt(nnodes)))
    eigenvalues, eigenvectors = sp.sparse.linalg.eigsh(laplacian, k, which="SM", ncv=ncv)
    index = np.argsort(eigenvalues)[1:k]
    return np.real(eigenvectors[:, index])


def kamada_kawai_layout(
    G,
    dist=None,
    pos=None,
    weight="weight",
    scale=1,
    center=None,
    dim=2,
    store_pos_as=None,
):
    """Position nodes using the Kamada-Kawai path-length cost function."""
    import franken_networkx as fnx

    nodes, center = _process_params(G, center, dim)
    if len(nodes) == 0:
        return {}

    if dist is None:
        dist = dict(fnx.shortest_path_length(G, weight=weight))

    dist_mtx = 1e6 * np.ones((len(nodes), len(nodes)))
    for row, row_node in enumerate(nodes):
        if row_node not in dist:
            continue
        row_dist = dist[row_node]
        for col, col_node in enumerate(nodes):
            if col_node not in row_dist:
                continue
            dist_mtx[row][col] = row_dist[col_node]

    if pos is None:
        if dim >= 3:
            pos = random_layout(G, dim=dim)
        elif dim == 2:
            pos = circular_layout(G, dim=dim)
        else:
            pos = dict(zip(nodes, np.linspace(0, 1, len(nodes))))

    pos_arr = np.array([pos[node] for node in nodes])
    pos_arr = _kamada_kawai_solve(dist_mtx, pos_arr, dim)
    pos_arr = rescale_layout(pos_arr, scale=scale) + center
    pos = dict(zip(nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def _kamada_kawai_solve(dist_mtx, pos_arr, dim):
    """Anneal node locations from a matrix of preferred distances."""
    import scipy as sp

    mean_weight = 1e-3
    cost_args = (
        1 / (dist_mtx + np.eye(dist_mtx.shape[0]) * 1e-3),
        mean_weight,
        dim,
    )
    opt_result = sp.optimize.minimize(
        _kamada_kawai_costfn,
        pos_arr.ravel(),
        method="L-BFGS-B",
        args=cost_args,
        jac=True,
    )
    return opt_result.x.reshape((-1, dim))


def _kamada_kawai_costfn(pos_vec, invdist, meanweight, dim):
    """Return Kamada-Kawai cost and gradient for the optimizer."""
    node_count = invdist.shape[0]
    pos_arr = pos_vec.reshape((node_count, dim))

    delta = pos_arr[:, np.newaxis, :] - pos_arr[np.newaxis, :, :]
    nodesep = np.linalg.norm(delta, axis=-1)
    direction = np.einsum(
        "ijk,ij->ijk",
        delta,
        1 / (nodesep + np.eye(node_count) * 1e-3),
    )

    offset = nodesep * invdist - 1.0
    offset[np.diag_indices(node_count)] = 0

    cost = 0.5 * np.sum(offset**2)
    grad = np.einsum("ij,ij,ijk->ik", invdist, offset, direction) - np.einsum(
        "ij,ij,ijk->jk",
        invdist,
        offset,
        direction,
    )

    sum_pos = np.sum(pos_arr, axis=0)
    cost += 0.5 * meanweight * np.sum(sum_pos**2)
    grad += meanweight * sum_pos

    return cost, grad.ravel()


def planar_layout(G, scale=1, center=None, dim=2, store_pos_as=None):
    """Position nodes without edge crossings (if graph is planar)."""
    import franken_networkx as fnx

    if dim != 2:
        raise ValueError("can only handle 2 dimensions")

    nodes, center = _process_params(G, center, dim)
    if len(nodes) == 0:
        return {}

    if isinstance(G, fnx.PlanarEmbedding):
        embedding = G
    else:
        is_planar, embedding = fnx.check_planarity(G)
        if not is_planar:
            raise fnx.NetworkXException("G is not planar.")

    embedding_pos = fnx.combinatorial_embedding_to_pos(embedding)
    node_list = list(embedding)
    pos_arr = np.vstack([embedding_pos[node] for node in node_list])
    pos_arr = pos_arr.astype(np.float64)
    pos_arr = rescale_layout(pos_arr, scale=scale) + center
    pos = dict(zip(node_list, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def forceatlas2_layout(
    G,
    pos=None,
    *,
    max_iter=100,
    jitter_tolerance=1.0,
    scaling_ratio=2.0,
    gravity=1.0,
    distributed_action=False,
    strong_gravity=False,
    node_mass=None,
    node_size=None,
    weight=None,
    linlog=False,
    seed=None,
    dim=2,
    store_pos_as=None,
    backend=None,
    **backend_kwargs,
):
    """Position nodes using the ForceAtlas2 layout algorithm."""
    if backend is not None and backend != "networkx":
        # Match upstream NetworkX: a non-default backend triggers the dispatch
        # path which raises ImportError when that backend isn't installed.
        raise ImportError(
            f"'{backend}' backend is not installed."
        )
    del backend_kwargs  # The default in-tree implementation ignores backend kwargs.
    import franken_networkx as fnx

    nodes = list(G)
    if len(nodes) == 0:
        return {}

    rng = _create_random_state(seed)
    if pos is None:
        pos = random_layout(G, dim=dim, seed=rng)
        pos_arr = np.array(list(pos.values()))
    elif len(pos) == 0:
        pos = random_layout(G, dim=dim, seed=rng)
        pos_arr = np.array(list(pos.values()))
    elif len(pos) == len(nodes):
        pos_arr = np.array([pos[node] for node in nodes])
    else:
        pos_init = np.array(list(pos.values()))
        max_pos = pos_init.max(axis=0)
        min_pos = pos_init.min(axis=0)
        dim = max_pos.size
        pos_arr = min_pos + rng.rand(len(nodes), dim) * (max_pos - min_pos)
        for index, node in enumerate(nodes):
            if node in pos:
                pos_arr[index] = pos[node].copy()

    mass = np.zeros(len(nodes))
    size = np.zeros(len(nodes))

    adjust_sizes = False
    if node_size is None:
        node_size = {}
    else:
        adjust_sizes = True

    if node_mass is None:
        node_mass = {}

    for index, node in enumerate(nodes):
        mass[index] = node_mass.get(node, _layout_degree(G, node) + 1)
        size[index] = node_size.get(node, 1)

    node_count = len(nodes)
    adjacency = fnx.to_numpy_array(G, weight=weight)

    speed = 1
    speed_efficiency = 1
    swing = 1
    traction = 1
    for _iteration in range(max_iter):
        diff = pos_arr[:, None] - pos_arr[None]
        distance = np.linalg.norm(diff, axis=-1)

        if linlog:
            attraction = -np.log(1 + distance) / distance
            np.fill_diagonal(attraction, 0)
            attraction = np.einsum("ij, ij -> ij", attraction, adjacency)
            attraction = np.einsum("ijk, ij -> ik", diff, attraction)
        else:
            attraction = -np.einsum("ijk, ij -> ik", diff, adjacency)

        if distributed_action:
            attraction /= mass[:, None]

        tmp = mass[:, None] @ mass[None]
        if adjust_sizes:
            distance += -size[:, None] - size[None]

        distance_squared = distance**2
        np.fill_diagonal(tmp, 0)
        np.fill_diagonal(distance_squared, 1)
        factor = (tmp / distance_squared) * scaling_ratio
        repulsion = np.einsum("ijk, ij -> ik", diff, factor)

        pos_centered = pos_arr - np.mean(pos_arr, axis=0)
        if strong_gravity:
            gravities = -gravity * mass[:, None] * pos_centered
        else:
            with np.errstate(divide="ignore", invalid="ignore"):
                unit_vec = pos_centered / np.linalg.norm(pos_centered, axis=-1)[
                    :, None
                ]
            unit_vec = np.nan_to_num(unit_vec, nan=0)
            gravities = -gravity * mass[:, None] * unit_vec

        update = attraction + repulsion + gravities

        swing += (mass * np.linalg.norm(pos_arr - update, axis=-1)).sum()
        traction += (0.5 * mass * np.linalg.norm(pos_arr + update, axis=-1)).sum()

        speed, speed_efficiency = _forceatlas2_estimate_factor(
            node_count,
            swing,
            traction,
            speed,
            speed_efficiency,
            jitter_tolerance,
        )

        if adjust_sizes:
            displacement_norm = np.linalg.norm(update, axis=-1)
            swinging = mass * displacement_norm
            factor = 0.1 * speed / (1 + np.sqrt(speed * swinging))
            factor = (
                np.minimum(factor * displacement_norm, 10.0 * np.ones(displacement_norm.shape))
                / displacement_norm
            )
        else:
            swinging = mass * np.linalg.norm(update, axis=-1)
            factor = speed / (1 + np.sqrt(speed * swinging))

        factored_update = update * factor[:, None]
        pos_arr += factored_update
        if abs(factored_update).sum() < 1e-10:
            break

    pos = dict(zip(nodes, pos_arr))
    _store_positions(G, pos, store_pos_as)
    return pos


def _forceatlas2_estimate_factor(
    node_count,
    swing,
    traction,
    speed,
    speed_efficiency,
    jitter_tolerance,
):
    """Return the updated ForceAtlas2 speed and speed efficiency."""
    opt_jitter = 0.05 * np.sqrt(node_count)
    min_jitter = np.sqrt(opt_jitter)
    max_jitter = 10
    min_speed_efficiency = 0.05

    other = min(max_jitter, opt_jitter * traction / node_count**2)
    jitter = jitter_tolerance * max(min_jitter, other)

    if swing / traction > 2.0:
        if speed_efficiency > min_speed_efficiency:
            speed_efficiency *= 0.5
        jitter = max(jitter, jitter_tolerance)
    if swing == 0:
        target_speed = np.inf
    else:
        target_speed = jitter * speed_efficiency * traction / swing

    if swing > jitter * traction:
        if speed_efficiency > min_speed_efficiency:
            speed_efficiency *= 0.7
    elif speed < 1000:
        speed_efficiency *= 1.3

    max_rise = 0.5
    speed = speed + min(target_speed - speed, max_rise * speed)
    return speed, speed_efficiency


def fruchterman_reingold_layout(
    G,
    k=None,
    pos=None,
    fixed=None,
    iterations=50,
    threshold=1e-4,
    weight="weight",
    scale=1,
    center=None,
    dim=2,
    seed=None,
    store_pos_as=None,
    *,
    method="auto",
    gravity=1.0,
):
    """Position nodes with the explicit Fruchterman-Reingold layout entry point."""
    return spring_layout(
        G,
        k=k,
        pos=pos,
        fixed=fixed,
        iterations=iterations,
        threshold=threshold,
        weight=weight,
        scale=scale,
        center=center,
        dim=dim,
        seed=seed,
        store_pos_as=store_pos_as,
        method=method,
        gravity=gravity,
    )


def multipartite_layout(
    G,
    subset_key="subset",
    align="vertical",
    scale=1,
    center=None,
    store_pos_as=None,
):
    """Position multipartite nodes in aligned layers."""
    import franken_networkx as fnx

    if align not in ("vertical", "horizontal"):
        raise ValueError("align must be either vertical or horizontal.")

    graph_nodes, center = _process_params(G, center, 2)
    if len(graph_nodes) == 0:
        return {}

    try:
        if len(graph_nodes) != sum(len(nodes) for nodes in subset_key.values()):
            raise fnx.NetworkXError(
                "all nodes must be in one subset of `subset_key` dict"
            )
    except AttributeError:
        node_to_subset = {}
        for node, data in G.nodes(data=True):
            if subset_key in data:
                node_to_subset[node] = data[subset_key]
        if len(node_to_subset) != len(graph_nodes):
            raise fnx.NetworkXError(
                f"all nodes need a subset_key attribute: {subset_key}"
            )

        grouped = {}
        for node, subset in node_to_subset.items():
            grouped.setdefault(subset, set()).add(node)
        subset_key = grouped

    try:
        layers = dict(sorted(subset_key.items()))
    except TypeError:
        layers = subset_key

    pos_arr = None
    layout_nodes = []
    width = len(layers)
    for index, layer in enumerate(layers.values()):
        height = len(layer)
        xs = np.repeat(index, height)
        ys = np.arange(0, height, dtype=float)
        offset = ((width - 1) / 2, (height - 1) / 2)
        layer_pos = np.column_stack([xs, ys]) - offset
        if pos_arr is None:
            pos_arr = layer_pos
        else:
            pos_arr = np.concatenate([pos_arr, layer_pos])
        layout_nodes.extend(layer)

    pos_arr = rescale_layout(pos_arr, scale=scale) + center
    if align == "horizontal":
        pos_arr = pos_arr[:, ::-1]
    pos = dict(zip(layout_nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos


def rescale_layout_dict(pos, scale=1):
    """Return a dictionary of scaled positions keyed by node."""
    if not pos:
        return {}
    pos_v = np.array(list(pos.values()))
    pos_v = rescale_layout(pos_v, scale=scale)
    return dict(zip(pos, pos_v))


def spiral_layout(
    G,
    scale=1,
    center=None,
    dim=2,
    resolution=0.35,
    equidistant=False,
    store_pos_as=None,
):
    """Position nodes along a spiral."""
    if dim != 2:
        raise ValueError("can only handle 2 dimensions")

    nodes, center = _process_params(G, center, dim)

    if len(nodes) == 0:
        return {}
    if len(nodes) == 1:
        pos = {nodes[0]: center}
        _store_positions(G, pos, store_pos_as)
        return pos

    if equidistant:
        chord = 1
        step = 0.5
        theta = resolution
        theta += chord / (step * theta)
        pos_arr = []
        for _ in range(len(nodes)):
            radius = step * theta
            theta += chord / radius
            pos_arr.append([np.cos(theta) * radius, np.sin(theta) * radius])
    else:
        dist = np.arange(len(nodes), dtype=float)
        angle = resolution * dist
        pos_arr = np.transpose(dist * np.array([np.cos(angle), np.sin(angle)]))

    pos_arr = rescale_layout(np.array(pos_arr), scale=scale) + center
    pos = dict(zip(nodes, pos_arr))

    _store_positions(G, pos, store_pos_as)
    return pos
