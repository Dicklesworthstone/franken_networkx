"""Drawing layout helpers."""

import numpy as np


def _to_nx(G):
    """Convert an fnx graph to an nx graph for delegation to NetworkX functions.

    This creates a proper nx.Graph (or nx.DiGraph) that can be passed to
    NetworkX functions that require isinstance checks.
    """
    from franken_networkx.backend import _fnx_to_nx

    return _fnx_to_nx(G)


def _delegate_layout(name, G, *args, **kwargs):
    """Dispatch a graph layout call to NetworkX."""
    import networkx as nx

    fn = getattr(nx, name)
    try:
        graph = _to_nx(G)
    except AttributeError:
        graph = G
    return fn(graph, *args, **kwargs)


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


def arf_layout(G, *args, **kwargs):
    """Position nodes using the attractive-repulsive force layout."""
    return _delegate_layout("arf_layout", G, *args, **kwargs)


def bfs_layout(G, start, *args, **kwargs):
    """Position nodes by breadth-first-search layers."""
    return _delegate_layout("bfs_layout", G, start, *args, **kwargs)


def bipartite_layout(G, *args, **kwargs):
    """Position bipartite nodes in two aligned layers."""
    return _delegate_layout("bipartite_layout", G, *args, **kwargs)


def spring_layout(G, **kwargs):
    """Position nodes using Fruchterman-Reingold force-directed algorithm."""
    import networkx as nx

    return nx.spring_layout(G, **kwargs)


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


def spectral_layout(G, **kwargs):
    """Position nodes using eigenvectors of the graph Laplacian."""
    import networkx as nx

    return nx.spectral_layout(G, **kwargs)


def kamada_kawai_layout(G, **kwargs):
    """Position nodes using Kamada-Kawai path-length cost function."""
    import networkx as nx

    return nx.kamada_kawai_layout(G, **kwargs)


def planar_layout(G, **kwargs):
    """Position nodes without edge crossings (if graph is planar)."""
    import networkx as nx

    return nx.planar_layout(G, **kwargs)


def forceatlas2_layout(G, *args, **kwargs):
    """Position nodes using the ForceAtlas2 layout algorithm."""
    return _delegate_layout("forceatlas2_layout", G, *args, **kwargs)


def fruchterman_reingold_layout(G, *args, **kwargs):
    """Position nodes with the explicit Fruchterman-Reingold layout entry point."""
    return _delegate_layout("fruchterman_reingold_layout", G, *args, **kwargs)


def multipartite_layout(G, *args, **kwargs):
    """Position multipartite nodes in aligned layers."""
    return _delegate_layout("multipartite_layout", G, *args, **kwargs)


def rescale_layout_dict(pos, scale=1):
    """Return a dictionary of scaled positions keyed by node."""
    if not pos:
        return {}
    pos_v = np.array(list(pos.values()))
    pos_v = rescale_layout(pos_v, scale=scale)
    return dict(zip(pos, pos_v))


def spiral_layout(G, *args, **kwargs):
    """Position nodes along a spiral."""
    return _delegate_layout("spiral_layout", G, *args, **kwargs)
