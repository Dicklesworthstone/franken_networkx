"""Drawing functions — delegates to NetworkX/matplotlib."""

import bz2
import gzip
from io import StringIO
from pathlib import Path

from franken_networkx.drawing.layout import (
    _to_nx,
    bipartite_layout,
    circular_layout,
    kamada_kawai_layout,
    planar_layout,
    random_layout,
    shell_layout,
    spectral_layout,
    spring_layout,
)

_DOC_WRAPPER_TIKZ = (
    "\\documentclass{{report}}\n"
    "\\usepackage{{tikz}}\n"
    "\\usepackage{{subcaption}}\n\n"
    "\\begin{{document}}\n"
    "{content}\n"
    "\\end{{document}}"
)
_FIG_WRAPPER = "\\begin{{figure}}\n{content}{caption}{label}\n\\end{{figure}}"
_SUBFIG_WRAPPER = (
    "  \\begin{{subfigure}}{{{size}\\textwidth}}\n"
    "{content}{caption}{label}\n"
    "  \\end{{subfigure}}"
)


def _is_graph_like(obj):
    return hasattr(obj, "is_directed") and hasattr(obj, "is_multigraph")


def _as_nx_graph(G):
    if not _is_graph_like(G):
        return G
    try:
        return _to_nx(G)
    except AttributeError:
        return G


def _as_nx_graph_bunch(Gbunch):
    if _is_graph_like(Gbunch):
        return _as_nx_graph(Gbunch)
    try:
        return [_as_nx_graph(G) for G in Gbunch]
    except TypeError:
        return Gbunch


def _delegate_draw(name, G, *args, **kwargs):
    """Dispatch a drawing helper to NetworkX."""
    import networkx as nx

    fn = getattr(nx, name)
    G = _as_nx_graph(G)
    return fn(G, *args, **kwargs)


def draw(G, pos=None, ax=None, **kwargs):
    """Draw the graph G with matplotlib.

    Delegates to ``networkx.draw``.
    """
    return _delegate_draw("draw", G, pos=pos, ax=ax, **kwargs)


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
    return draw(G, pos=spring_layout(G), **kwargs)


def draw_circular(G, **kwargs):
    """Draw with circular layout."""
    return draw(G, pos=circular_layout(G), **kwargs)


def draw_random(G, **kwargs):
    """Draw with random layout."""
    return draw(G, pos=random_layout(G), **kwargs)


def draw_spectral(G, **kwargs):
    """Draw with spectral layout."""
    return draw(G, pos=spectral_layout(G), **kwargs)


def draw_shell(G, nlist=None, **kwargs):
    """Draw with shell layout."""
    return draw(G, pos=shell_layout(G, nlist=nlist), **kwargs)


def draw_kamada_kawai(G, **kwargs):
    """Draw with Kamada-Kawai layout."""
    return draw(G, pos=kamada_kawai_layout(G), **kwargs)


def draw_planar(G, **kwargs):
    """Draw with planar layout (if graph is planar)."""
    return draw(G, pos=planar_layout(G), **kwargs)


def draw_forceatlas2(G, **kwargs):
    """Draw with the ForceAtlas2 layout."""
    return _delegate_draw("draw_forceatlas2", G, **kwargs)


def to_latex(
    Gbunch,
    pos="pos",
    tikz_options="",
    default_node_options="",
    node_options="node_options",
    node_label="node_label",
    default_edge_options="",
    edge_options="edge_options",
    edge_label="edge_label",
    edge_label_options="edge_label_options",
    caption="",
    latex_label="",
    sub_captions=None,
    sub_labels=None,
    n_rows=1,
    as_document=True,
    document_wrapper=_DOC_WRAPPER_TIKZ,
    figure_wrapper=_FIG_WRAPPER,
    subfigure_wrapper=_SUBFIG_WRAPPER,
):
    """Render a graph or graph bunch to LaTeX/TikZ."""
    if _is_graph_like(Gbunch) or hasattr(Gbunch, "adj"):
        raw = to_latex_raw(
            Gbunch,
            pos,
            tikz_options,
            default_node_options,
            node_options,
            node_label,
            default_edge_options,
            edge_options,
            edge_label,
            edge_label_options,
        )
    else:
        from franken_networkx import NetworkXError

        size = 1 / n_rows
        graph_count = len(Gbunch)
        if isinstance(pos, (str, dict)):
            pos = [pos] * graph_count
        if sub_captions is None:
            sub_captions = [""] * graph_count
        if sub_labels is None:
            sub_labels = [""] * graph_count
        if not (
            len(Gbunch) == len(pos) == len(sub_captions) == len(sub_labels)
        ):
            raise NetworkXError(
                "length of Gbunch, sub_captions and sub_figures must agree"
            )

        raw = ""
        for graph, graph_pos, subcap, sublbl in zip(
            Gbunch, pos, sub_captions, sub_labels
        ):
            subraw = to_latex_raw(
                graph,
                graph_pos,
                tikz_options,
                default_node_options,
                node_options,
                node_label,
                default_edge_options,
                edge_options,
                edge_label,
                edge_label_options,
            )
            cap = f"    \\caption{{{subcap}}}" if subcap else ""
            lbl = f"\\label{{{sublbl}}}" if sublbl else ""
            raw += subfigure_wrapper.format(
                size=size, content=subraw, caption=cap, label=lbl
            )
            raw += "\n"

    raw = raw[:-1]
    cap = f"\n  \\caption{{{caption}}}" if caption else ""
    lbl = f"\\label{{{latex_label}}}" if latex_label else ""
    figure = figure_wrapper.format(content=raw, caption=cap, label=lbl)
    if as_document:
        return document_wrapper.format(content=figure)
    return figure


def to_latex_raw(G, *args, **kwargs):
    """Render a graph to raw TikZ via NetworkX."""
    return _delegate_draw("to_latex_raw", G, *args, **kwargs)


def write_latex(Gbunch, path, **options):
    """Write LaTeX/TikZ output."""
    data = to_latex(Gbunch, **options)
    if hasattr(path, "write"):
        try:
            path.write(data)
        except TypeError:
            path.write(data.encode("utf-8"))
        return None

    output_path = Path(path)
    if output_path.suffix == ".gz":
        with gzip.open(output_path, "wt", encoding="utf-8") as fh:
            fh.write(data)
    elif output_path.suffix == ".bz2":
        with bz2.open(output_path, "wt", encoding="utf-8") as fh:
            fh.write(data)
    else:
        output_path.write_text(data, encoding="utf-8")
    return None


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
