"""Layout algorithms delegated to NetworkX after graph conversion."""


def _to_nx(G):
    """Convert a FrankenNetworkX graph to a NetworkX graph for drawing."""
    import networkx as nx

    if G.is_directed():
        H = nx.DiGraph()
    else:
        H = nx.Graph()
    for n, attrs in G.nodes(data=True):
        H.add_node(n, **attrs)
    for u, v, d in G.edges(data=True):
        H.add_edge(u, v, **d)
    return H


def _delegate_layout(name, G, *args, **kwargs):
    """Dispatch a graph layout call to NetworkX after graph conversion."""
    import networkx as nx

    fn = getattr(nx, name)
    return fn(_to_nx(G), *args, **kwargs)


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
    return nx.spring_layout(_to_nx(G), **kwargs)


def circular_layout(G, **kwargs):
    """Position nodes on a circle."""
    import networkx as nx
    return nx.circular_layout(_to_nx(G), **kwargs)


def random_layout(G, **kwargs):
    """Position nodes uniformly at random."""
    import networkx as nx
    return nx.random_layout(_to_nx(G), **kwargs)


def shell_layout(G, **kwargs):
    """Position nodes in concentric circles."""
    import networkx as nx
    return nx.shell_layout(_to_nx(G), **kwargs)


def spectral_layout(G, **kwargs):
    """Position nodes using eigenvectors of the graph Laplacian."""
    import networkx as nx
    return nx.spectral_layout(_to_nx(G), **kwargs)


def kamada_kawai_layout(G, **kwargs):
    """Position nodes using Kamada-Kawai path-length cost function."""
    import networkx as nx
    return nx.kamada_kawai_layout(_to_nx(G), **kwargs)


def planar_layout(G, **kwargs):
    """Position nodes without edge crossings (if graph is planar)."""
    import networkx as nx
    return nx.planar_layout(_to_nx(G), **kwargs)


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
    """Rescale a position dict using NetworkX's layout helper."""
    import networkx as nx

    return nx.rescale_layout_dict(pos, scale=scale)


def spiral_layout(G, *args, **kwargs):
    """Position nodes along a spiral."""
    return _delegate_layout("spiral_layout", G, *args, **kwargs)
