"""Drawing functions — delegates to NetworkX/matplotlib."""

import bz2
from collections import defaultdict
import gzip
from io import StringIO
from os import PathLike
from pathlib import Path
import sys
from typing import Any, NamedTuple

from franken_networkx.drawing.layout import (
    _to_nx,
    bipartite_layout,
    circular_layout,
    forceatlas2_layout,
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


class _NetworkTextAsciiBaseGlyphs:
    empty = "+"
    newtree_last = "+-- "
    newtree_mid = "+-- "
    endof_forest = "    "
    within_forest = ":   "
    within_tree = "|   "


class _NetworkTextAsciiDirectedGlyphs(_NetworkTextAsciiBaseGlyphs):
    last = "L-> "
    mid = "|-> "
    backedge = "<-"
    vertical_edge = "!"


class _NetworkTextAsciiUndirectedGlyphs(_NetworkTextAsciiBaseGlyphs):
    last = "L-- "
    mid = "|-- "
    backedge = "-"
    vertical_edge = "|"


class _NetworkTextUtfBaseGlyphs:
    empty = "╙"
    newtree_last = "╙── "
    newtree_mid = "╟── "
    endof_forest = "    "
    within_forest = "╎   "
    within_tree = "│   "


class _NetworkTextUtfDirectedGlyphs(_NetworkTextUtfBaseGlyphs):
    last = "└─╼ "
    mid = "├─╼ "
    backedge = "╾"
    vertical_edge = "╽"


class _NetworkTextUtfUndirectedGlyphs(_NetworkTextUtfBaseGlyphs):
    last = "└── "
    mid = "├── "
    backedge = "─"
    vertical_edge = "│"


class _NetworkTextFrame(NamedTuple):
    parent: Any
    node: Any
    indents: list[str]
    this_islast: bool
    this_vertical: bool


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
    return draw(G, pos=forceatlas2_layout(G), **kwargs)


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


def to_latex_raw(
    G,
    pos="pos",
    tikz_options="",
    default_node_options="",
    node_options="node_options",
    node_label="label",
    default_edge_options="",
    edge_options="edge_options",
    edge_label="label",
    edge_label_options="edge_label_options",
):
    """Render a graph to raw TikZ."""
    import franken_networkx as fnx

    if G.is_multigraph():
        raise fnx.NetworkXNotImplemented("not implemented for multigraph type")

    i4 = "\n    "
    i8 = "\n        "

    if not isinstance(pos, dict):
        pos = fnx.get_node_attributes(G, pos)
    if not pos:
        pos = {node: f"({round(360.0 * i / len(G), 3)}:2)" for i, node in enumerate(G)}

    for node in G:
        if node not in pos:
            raise fnx.NetworkXError(f"node {node} has no specified pos {pos}")
        posnode = pos[node]
        if not isinstance(posnode, str):
            try:
                posx, posy = posnode
                pos[node] = f"({round(posx, 3)}, {round(posy, 3)})"
            except (TypeError, ValueError):
                msg = f"position pos[{node}] is not 2-tuple or a string: {posnode}"
                raise fnx.NetworkXError(msg) from None

    if not isinstance(node_options, dict):
        node_options = fnx.get_node_attributes(G, node_options)
    if not isinstance(node_label, dict):
        node_label = fnx.get_node_attributes(G, node_label)
    if not isinstance(edge_options, dict):
        edge_options = fnx.get_edge_attributes(G, edge_options)
    if not isinstance(edge_label, dict):
        edge_label = fnx.get_edge_attributes(G, edge_label)
    if not isinstance(edge_label_options, dict):
        edge_label_options = fnx.get_edge_attributes(G, edge_label_options)

    topts = "" if tikz_options == "" else f"[{tikz_options.strip('[]')}]"
    defn = "" if default_node_options == "" else f"[{default_node_options.strip('[]')}]"
    directed = G.is_directed()
    linestyle = "->" if directed else "-"
    if default_edge_options == "":
        defe = f"[{linestyle}]"
    elif "-" in default_edge_options:
        defe = default_edge_options
    else:
        defe = f"[{linestyle},{default_edge_options.strip('[]')}]"

    result = "  \\begin{tikzpicture}" + topts
    result += i4 + "  \\draw" + defn
    for node in G:
        nopts = f"[{node_options[node].strip('[]')}]" if node in node_options else ""
        ntext = f"{{{node_label[node]}}}" if node in node_label else f"{{{node}}}"
        result += i8 + f"{pos[node]} node{nopts} ({node}){ntext}"
    result += ";\n"

    result += "      \\begin{scope}" + defe
    seen = set()
    for u in G:
        for v in G[u]:
            if not directed and v in seen:
                continue
            edge = (u, v)
            e_opts = f"{edge_options[edge]}".strip("[]") if edge in edge_options else ""
            if u == v and "loop" not in e_opts:
                e_opts = "loop," + e_opts
            e_opts = f"[{e_opts}]" if e_opts != "" else ""

            els = edge_label_options[edge] if edge in edge_label_options else ""
            els = f"[{els.strip('[]')}]"
            e_label = f" node{els} {{{edge_label[edge]}}}" if edge in edge_label else ""
            result += i8 + f"\\draw{e_opts} ({u}) to{e_label} ({v});"
        if not directed:
            seen.add(u)

    result += "\n      \\end{scope}\n    \\end{tikzpicture}\n"
    return result


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


def _network_text_node_data(graph, node):
    return graph.nodes[node]


def _network_text_edge_pairs(graph):
    edges = graph.edges
    if graph.is_multigraph():
        try:
            edge_iter = edges(keys=True)
        except TypeError:
            edge_iter = edges
    else:
        try:
            edge_iter = edges()
        except TypeError:
            edge_iter = edges

    for edge in edge_iter:
        yield edge[0], edge[1]


def _network_text_adjacency_maps(graph):
    successors = {node: [] for node in graph.nodes}
    predecessors = {node: [] for node in graph.nodes}
    is_directed = graph.is_directed()

    for source, target in _network_text_edge_pairs(graph):
        successors.setdefault(source, [])
        successors.setdefault(target, [])
        predecessors.setdefault(source, [])
        predecessors.setdefault(target, [])

        if target not in successors[source]:
            successors[source].append(target)
        if is_directed:
            if source not in predecessors[target]:
                predecessors[target].append(source)
        else:
            if source != target and source not in successors[target]:
                successors[target].append(source)

    if not is_directed:
        predecessors = successors
    return successors, predecessors


def _network_text_successors(graph, node, successors=None):
    if successors is not None:
        return list(successors[node])
    if graph.is_directed():
        succ = getattr(graph, "succ", None)
        if succ is not None:
            return list(succ[node])
        return list(graph.successors(node))
    return list(graph.adj[node])


def _network_text_predecessors(graph, node, predecessors=None):
    if predecessors is not None:
        return list(predecessors[node])
    if graph.is_directed():
        pred = getattr(graph, "pred", None)
        if pred is not None:
            return list(pred[node])
        return list(graph.predecessors(node))
    return list(graph.adj[node])


def _network_text_degree(graph, node):
    return graph.degree[node]


def _network_text_in_degree(graph, node):
    in_degree = getattr(graph, "in_degree", None)
    if in_degree is not None:
        return in_degree[node]
    return _network_text_degree(graph, node)


def _network_text_connected_components(graph, successors):
    seen = set()
    components = []
    for root in graph.nodes:
        if root in seen:
            continue
        component = []
        stack = [root]
        seen.add(root)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbor in reversed(_network_text_successors(graph, node, successors)):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def _network_text_strongly_connected_components(graph, successors):
    index = 0
    stack = []
    on_stack = set()
    indices = {}
    lowlinks = {}
    components = []

    def visit(node):
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for successor in _network_text_successors(graph, node, successors):
            if successor not in indices:
                visit(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[successor])

        if lowlinks[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(component)

    for node in graph.nodes:
        if node not in indices:
            visit(node)
    return components


def _network_text_find_sources(graph, successors):
    """Return a deterministic source set that reaches every graph node."""
    node_order = {node: index for index, node in enumerate(graph.nodes)}
    if graph.is_directed():
        components = _network_text_strongly_connected_components(graph, successors)
        component_of = {}
        for component_index, component in enumerate(components):
            for node in component:
                component_of[node] = component_index

        has_incoming = [False] * len(components)
        for node in graph.nodes:
            node_component = component_of[node]
            for successor in _network_text_successors(graph, node, successors):
                successor_component = component_of[successor]
                if successor_component != node_component:
                    has_incoming[successor_component] = True

        sources = []
        for component_index, component in enumerate(components):
            if not has_incoming[component_index]:
                sources.append(
                    min(
                        component,
                        key=lambda n: (_network_text_in_degree(graph, n), node_order[n]),
                    )
                )
        return sources

    sources = [
        min(set(component), key=lambda n: _network_text_degree(graph, n))
        for component in _network_text_connected_components(graph, successors)
    ]
    return sorted(sources, key=lambda n: _network_text_degree(graph, n))


def _network_text_glyphs(graph, ascii_only):
    if graph.is_directed():
        return (
            _NetworkTextAsciiDirectedGlyphs
            if ascii_only
            else _NetworkTextUtfDirectedGlyphs
        )
    return (
        _NetworkTextAsciiUndirectedGlyphs
        if ascii_only
        else _NetworkTextUtfUndirectedGlyphs
    )


def generate_network_text(
    graph,
    with_labels=True,
    sources=None,
    max_depth=None,
    ascii_only=False,
    vertical_chains=False,
):
    """Generate lines in the NetworkX network-text graph format."""
    glyphs = _network_text_glyphs(graph, ascii_only)
    is_directed = graph.is_directed()
    successors, predecessors = _network_text_adjacency_maps(graph)

    if isinstance(with_labels, str):
        label_attr = with_labels
    elif with_labels:
        label_attr = "label"
    else:
        label_attr = None

    if max_depth == 0:
        yield glyphs.empty + " ..."
    elif len(graph.nodes) == 0:
        yield glyphs.empty
    else:
        if sources is None:
            sources = _network_text_find_sources(graph, successors)
        else:
            sources = list(sources)

        last_idx = len(sources) - 1
        stack = [
            _NetworkTextFrame(None, node, [], idx == last_idx, False)
            for idx, node in enumerate(sources)
        ][::-1]

        num_skipped_children = defaultdict(lambda: 0)
        seen_nodes = set()
        while stack:
            parent, node, indents, this_islast, this_vertical = stack.pop()

            if node is not Ellipsis:
                skip = node in seen_nodes
                if skip:
                    num_skipped_children[parent] += 1

                if (
                    this_islast
                    and num_skipped_children[parent]
                    and parent is not None
                ):
                    stack.append(_NetworkTextFrame(node, Ellipsis, indents, True, False))
                    stack.append(
                        _NetworkTextFrame(parent, node, indents, False, this_vertical)
                    )
                    continue

                if skip:
                    continue
                seen_nodes.add(node)

            if not indents:
                if this_islast:
                    this_vertical = False
                    this_prefix = indents + [glyphs.newtree_last]
                    next_prefix = indents + [glyphs.endof_forest]
                else:
                    this_prefix = indents + [glyphs.newtree_mid]
                    next_prefix = indents + [glyphs.within_forest]
            elif this_vertical:
                this_prefix = indents
                next_prefix = indents
            elif this_islast:
                this_prefix = indents + [glyphs.last]
                next_prefix = indents + [glyphs.endof_forest]
            else:
                this_prefix = indents + [glyphs.mid]
                next_prefix = indents + [glyphs.within_tree]

            if node is Ellipsis:
                label = " ..."
                suffix = ""
                children = []
            else:
                node_data = _network_text_node_data(graph, node)
                if label_attr is not None:
                    label = str(node_data.get(label_attr, node))
                else:
                    label = str(node)

                collapse = node_data.get("collapse", False)

                if is_directed:
                    children = _network_text_successors(graph, node, successors)
                    handled_parents = {parent}
                else:
                    children = [
                        child
                        for child in _network_text_successors(graph, node, successors)
                        if child not in seen_nodes
                    ]
                    handled_parents = {*children, parent}

                if max_depth is not None and len(indents) == max_depth - 1:
                    if children:
                        children = [Ellipsis]
                    handled_parents = {parent}

                if collapse:
                    if children:
                        children = [Ellipsis]
                    handled_parents = {parent}

                other_parents = [
                    p
                    for p in _network_text_predecessors(graph, node, predecessors)
                    if p not in handled_parents
                ]
                if other_parents:
                    if label_attr is not None:
                        other_parent_labels = ", ".join(
                            str(_network_text_node_data(graph, p).get(label_attr, p))
                            for p in other_parents
                        )
                    else:
                        other_parent_labels = ", ".join(str(p) for p in other_parents)
                    suffix = " ".join(["", glyphs.backedge, other_parent_labels])
                else:
                    suffix = ""

            if this_vertical:
                yield "".join(this_prefix + [glyphs.vertical_edge])

            yield "".join(this_prefix + [label, suffix])

            if vertical_chains:
                if is_directed:
                    num_children = len(set(children))
                else:
                    num_children = len(set(children) - {parent})
                next_is_vertical = num_children == 1
            else:
                next_is_vertical = False

            for idx, child in enumerate(children[::-1]):
                stack.append(
                    _NetworkTextFrame(
                        node,
                        child,
                        next_prefix,
                        idx == 0,
                        next_is_vertical,
                    )
                )


def write_network_text(
    graph,
    path=None,
    with_labels=True,
    sources=None,
    max_depth=None,
    ascii_only=False,
    end="\n",
    vertical_chains=False,
):
    """Write a graph in the NetworkX network-text graph format."""
    if path is None:
        write = sys.stdout.write
    elif hasattr(path, "write"):
        write = path.write
    elif callable(path):
        write = path
    elif isinstance(path, (str, bytes, PathLike)):
        output_path = Path(path.decode() if isinstance(path, bytes) else path)
        data = "".join(
            line + end
            for line in generate_network_text(
                graph,
                with_labels=with_labels,
                sources=sources,
                max_depth=max_depth,
                ascii_only=ascii_only,
                vertical_chains=vertical_chains,
            )
        )
        output_path.write_text(data, encoding="utf-8")
        return None
    else:
        raise TypeError(type(path))

    for line in generate_network_text(
        graph,
        with_labels=with_labels,
        sources=sources,
        max_depth=max_depth,
        ascii_only=ascii_only,
        vertical_chains=vertical_chains,
    ):
        write(line + end)
    return None


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
