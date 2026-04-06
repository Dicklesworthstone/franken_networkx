"""Drawing functions — delegates to NetworkX/matplotlib after graph conversion."""

from io import StringIO

from franken_networkx.drawing.layout import bipartite_layout
from franken_networkx.drawing.layout import _to_nx


def _delegate_draw(name, G, *args, **kwargs):
    """Dispatch a drawing helper to NetworkX after graph conversion."""
    import networkx as nx

    fn = getattr(nx, name)
    return fn(_to_nx(G), *args, **kwargs)


def draw(G, pos=None, ax=None, **kwargs):
    """Draw the graph G with matplotlib.

    Converts the FrankenNetworkX graph to a NetworkX graph and delegates
    to ``networkx.draw``.
    """
    import networkx as nx

    nx.draw(_to_nx(G), pos=pos, ax=ax, **kwargs)


def draw_networkx(G, *args, **kwargs):
    """Draw the graph using NetworkX's main drawing helper."""
    return _delegate_draw("draw_networkx", G, *args, **kwargs)


def draw_networkx_nodes(G, pos, *args, **kwargs):
    """Draw graph nodes only."""
    return _delegate_draw("draw_networkx_nodes", G, pos, *args, **kwargs)


def draw_networkx_edges(G, pos, *args, **kwargs):
    """Draw graph edges only."""
    return _delegate_draw("draw_networkx_edges", G, pos, *args, **kwargs)


def draw_networkx_labels(G, pos, *args, **kwargs):
    """Draw graph node labels."""
    return _delegate_draw("draw_networkx_labels", G, pos, *args, **kwargs)


def draw_networkx_edge_labels(G, pos, *args, **kwargs):
    """Draw graph edge labels."""
    return _delegate_draw("draw_networkx_edge_labels", G, pos, *args, **kwargs)


def draw_spring(G, **kwargs):
    """Draw with spring layout."""
    import networkx as nx

    nx.draw_spring(_to_nx(G), **kwargs)


def draw_circular(G, **kwargs):
    """Draw with circular layout."""
    import networkx as nx

    nx.draw_circular(_to_nx(G), **kwargs)


def draw_random(G, **kwargs):
    """Draw with random layout."""
    import networkx as nx

    nx.draw_random(_to_nx(G), **kwargs)


def draw_spectral(G, **kwargs):
    """Draw with spectral layout."""
    import networkx as nx

    nx.draw_spectral(_to_nx(G), **kwargs)


def draw_shell(G, **kwargs):
    """Draw with shell layout."""
    import networkx as nx

    nx.draw_shell(_to_nx(G), **kwargs)


def draw_kamada_kawai(G, **kwargs):
    """Draw with Kamada-Kawai layout."""
    import networkx as nx

    nx.draw_kamada_kawai(_to_nx(G), **kwargs)


def draw_planar(G, **kwargs):
    """Draw with planar layout (if graph is planar)."""
    import networkx as nx

    nx.draw_planar(_to_nx(G), **kwargs)


def draw_forceatlas2(G, **kwargs):
    """Draw with the ForceAtlas2 layout."""
    return _delegate_draw("draw_forceatlas2", G, **kwargs)


def to_latex(Gbunch, *args, **kwargs):
    """Render a graph or graph bunch to LaTeX/TikZ via NetworkX."""
    import networkx as nx

    converted = (
        [_to_nx(graph) for graph in Gbunch]
        if isinstance(Gbunch, (list, tuple))
        else _to_nx(Gbunch)
    )
    return nx.to_latex(converted, *args, **kwargs)


def to_latex_raw(G, *args, **kwargs):
    """Render a graph to raw TikZ via NetworkX."""
    return _delegate_draw("to_latex_raw", G, *args, **kwargs)


def write_latex(Gbunch, path, **options):
    """Write LaTeX/TikZ output via NetworkX."""
    import networkx as nx

    converted = (
        [_to_nx(graph) for graph in Gbunch]
        if isinstance(Gbunch, (list, tuple))
        else _to_nx(Gbunch)
    )
    return nx.write_latex(converted, path, **options)


def generate_network_text(graph, *args, **kwargs):
    """Generate a textual graph rendering via NetworkX."""
    return _delegate_draw("generate_network_text", graph, *args, **kwargs)


def write_network_text(graph, path=None, *args, **kwargs):
    """Write a textual graph rendering via NetworkX."""
    return _delegate_draw("write_network_text", graph, path, *args, **kwargs)


def display(G, **kwds):
    """Display a graph in notebooks when possible, otherwise return text output."""
    try:
        from IPython import get_ipython
    except Exception:
        get_ipython = None

    shell = get_ipython() if get_ipython is not None else None
    if shell is not None and shell.__class__.__name__ == "ZMQInteractiveShell":
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots()
            draw(G, ax=ax, **kwds)
            return fig
        except Exception:
            pass

    buffer = StringIO()
    write_network_text(G, path=buffer, **kwds)
    return buffer.getvalue()


def draw_bipartite(G, top_nodes, pos=None, **kwds):
    """Draw a bipartite graph using a bipartite layout when positions are omitted."""
    if pos is None:
        pos = bipartite_layout(G, top_nodes)
    return draw(G, pos=pos, **kwds)
