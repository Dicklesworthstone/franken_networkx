"""FrankenNetworkX coloring submodule.

Mirrors ``networkx.algorithms.coloring`` but routes every function that
networkx re-exports at top level to FrankenNetworkX's optimized top-level
implementation.

br-r37-c1-colroute: previously ``franken_networkx.algorithms.coloring`` was
aliased directly to networkx's module. Calls like
``fnx.algorithms.coloring.greedy_color`` ran nx's pure-Python implementation
over fnx graph views (~1.8x slower than native fnx.greedy_color). Binding every
name networkx aliases to top level to the ``franken_networkx`` top-level
implementation ensures drop-in performance and semantic parity
(fnx.algorithms.coloring.X is fnx.X, exactly as nx.algorithms.coloring.X is nx.X).
"""

from __future__ import annotations

from collections import defaultdict as _defaultdict, deque as _deque
import importlib as _importlib
import itertools as _itertools
import sys as _sys
import types as _types

import networkx as _nx
import networkx.algorithms.coloring as _nxcl
from networkx.algorithms.coloring import *  # noqa: F401,F403

import franken_networkx as _fnx

__all__ = getattr(
    _nxcl, "__all__", [n for n in dir(_nxcl) if not n.startswith("_")]
)


def strategy_largest_first(G, colors):
    """Return a list of the nodes of ``G`` in decreasing order by degree."""
    return sorted(G, key=G.degree, reverse=True)


def strategy_random_sequential(G, colors, seed=None):
    """Return a random permutation of the nodes of ``G`` as a list."""
    rng = _fnx._generator_random_state(seed)
    nodes = list(G)
    rng.shuffle(nodes)
    return nodes


def strategy_smallest_last(G, colors):
    """Return a deque of the nodes of ``G``, "smallest" last."""
    H = G.copy()
    result = _deque()
    degrees = _defaultdict(set)
    lbound = float("inf")
    for node, d in H.degree():
        degrees[d].add(node)
        lbound = min(lbound, d)

    def find_min_degree():
        return next(d for d in _itertools.count(lbound) if d in degrees)

    for _ in G:
        min_degree = find_min_degree()
        u = degrees[min_degree].pop()
        if not degrees[min_degree]:
            del degrees[min_degree]
        result.appendleft(u)

        for v in H[u]:
            degree = H.degree(v)
            degrees[degree].remove(v)
            if not degrees[degree]:
                del degrees[degree]
            degrees[degree - 1].add(v)

        H.remove_node(u)
        lbound = min_degree - 1

    return result


def _maximal_independent_set(G):
    result = set()
    remaining = set(G)
    while remaining:
        G = G.subgraph(remaining)
        v = min(remaining, key=G.degree)
        result.add(v)
        remaining -= set(G[v]) | {v}
    return result


def strategy_independent_set(G, colors):
    """Yield nodes using a greedy independent set removal strategy."""
    remaining_nodes = set(G)
    while len(remaining_nodes) > 0:
        nodes = _maximal_independent_set(G.subgraph(remaining_nodes))
        remaining_nodes -= nodes
        yield from nodes


def strategy_connected_sequential_bfs(G, colors):
    """Yield nodes in breadth-first connected sequential order."""
    return strategy_connected_sequential(G, colors, "bfs")


def strategy_connected_sequential_dfs(G, colors):
    """Yield nodes in depth-first connected sequential order."""
    return strategy_connected_sequential(G, colors, "dfs")


def strategy_connected_sequential(G, colors, traversal="bfs"):
    """Yield nodes in breadth-first or depth-first connected sequential order."""
    if traversal == "bfs":
        traverse = _fnx.bfs_edges
    elif traversal == "dfs":
        traverse = _fnx.dfs_edges
    else:
        raise _fnx.NetworkXError(
            "Please specify one of the strings 'bfs' or"
            " 'dfs' for connected sequential ordering"
        )
    for component in _fnx.connected_components(G):
        source = next(iter(component))
        yield source
        for _, end in traverse(G.subgraph(component), source):
            yield end


def strategy_saturation_largest_first(G, colors):
    """Iterate over all the nodes of ``G`` in saturation order (DSATUR)."""
    distinct_colors = {v: set() for v in G}

    for node, color in colors.items():
        for neighbor in G[node]:
            distinct_colors[neighbor].add(color)

    if len(colors) >= 2:
        for node, color in colors.items():
            if color in distinct_colors[node]:
                raise _fnx.NetworkXError("Neighboring nodes must have different colors")

    if not colors:
        node = max(G, key=G.degree)
        yield node
        for v in G[node]:
            distinct_colors[v].add(0)

    while len(G) != len(colors):
        for node, color in colors.items():
            for neighbor in G[node]:
                distinct_colors[neighbor].add(color)

        saturation = {v: len(c) for v, c in distinct_colors.items() if v not in colors}
        node = max(saturation, key=lambda v: (saturation[v], G.degree(v)))
        yield node


STRATEGIES = {
    "largest_first": strategy_largest_first,
    "random_sequential": strategy_random_sequential,
    "smallest_last": strategy_smallest_last,
    "independent_set": strategy_independent_set,
    "connected_sequential_bfs": strategy_connected_sequential_bfs,
    "connected_sequential_dfs": strategy_connected_sequential_dfs,
    "connected_sequential": strategy_connected_sequential,
    "saturation_largest_first": strategy_saturation_largest_first,
    "DSATUR": strategy_saturation_largest_first,
}


def _greedy_coloring_with_interchange(G, nodes):
    """Color an ordered graph, freeing colors with two-color component swaps.

    The ordering is already selected, but may be a lazy strategy iterator.
    Capture the graph before advancing that iterator: interchange operates on
    this topology even when a custom strategy subsequently mutates ``G``.
    Every edge contributes an incidence at both endpoints, including directed
    and parallel edges, matching the interchange contract rather than the
    successor-only rule of ordinary greedy coloring.

    The state here is an adjacency snapshot and one color per node. A search
    computes the complete union of two-color components touching the proposed
    color's neighbors. The union, and therefore the interchange choice, does
    not depend on traversal order or linked per-color adjacency structures.
    """
    len(G)  # Preserve the post-strategy graph validation boundary.
    colors = dict.fromkeys(G, -1)
    adjacency = {node: [] for node in colors}
    for u, v in G.edges():
        adjacency[u].append(v)
        adjacency[v].append(u)

    highest_color = 0
    for node in nodes:
        row = adjacency[node]
        occupied = {colors[neighbor] for neighbor in row}
        color = next(c for c in _itertools.count() if c not in occupied)

        if color > highest_color:
            # Reuse a color only after ordinary greedy coloring would enlarge
            # the palette. The first admissible pair in this order wins.
            swapped = False
            for lower in range(highest_color):
                roots = [neighbor for neighbor in row if colors[neighbor] == lower]
                for upper in range(lower + 1, highest_color + 1):
                    component = set(roots)
                    pending = list(roots)
                    for current in pending:
                        opposite = upper if colors[current] == lower else lower
                        for neighbor in adjacency[current]:
                            if colors[neighbor] == opposite and neighbor not in component:
                                component.add(neighbor)
                                pending.append(neighbor)

                    if any(
                        neighbor in component and colors[neighbor] == upper
                        for neighbor in row
                    ):
                        continue

                    for member in component:
                        colors[member] = upper if colors[member] == lower else lower
                    color = lower
                    swapped = True
                    break
                if swapped:
                    break

        colors[node] = color
        highest_color = max(highest_color, color)

    # Initial insertion order is intentional, even if the strategy orders the
    # nodes differently or leaves some nodes uncolored (represented by -1).
    return colors


_FNX_STRATEGY_OVERRIDES = {
    "strategy_largest_first": strategy_largest_first,
    "strategy_random_sequential": strategy_random_sequential,
    "strategy_smallest_last": strategy_smallest_last,
    "strategy_independent_set": strategy_independent_set,
    "strategy_connected_sequential_bfs": strategy_connected_sequential_bfs,
    "strategy_connected_sequential_dfs": strategy_connected_sequential_dfs,
    "strategy_connected_sequential": strategy_connected_sequential,
    "strategy_saturation_largest_first": strategy_saturation_largest_first,
    "STRATEGIES": STRATEGIES,
}


def _route_module_to_fnx(mod, nx_source):
    """Rebind top-level-aliased nx names in `mod` to fnx's optimized implementations."""
    routed = []
    for name in dir(nx_source):
        if name.startswith("_"):
            continue
        nval = getattr(nx_source, name)
        if not callable(nval):
            continue
        if getattr(_nx, name, None) is not nval:
            continue
        fval = getattr(_fnx, name, None)
        if fval is not None and fval is not nval:
            if isinstance(mod, dict):
                mod[name] = fval
            else:
                setattr(mod, name, fval)
            routed.append(name)
    return routed


def _route_to_fnx_toplevel():
    """Rebind top-level-aliased nx names to fnx's optimized implementations."""
    routed = _route_module_to_fnx(globals(), _nxcl)
    _install_child_modules()
    return routed


def _install_child_modules():
    """Proxy child modules (greedy_coloring, equitable_coloring) so their
    functions also route to fnx top-level implementations."""
    for child_name in ("greedy_coloring", "equitable_coloring"):
        try:
            nx_child = _importlib.import_module(f"networkx.algorithms.coloring.{child_name}")
        except Exception:
            continue

        alias_cl = f"{__name__}.{child_name}"
        alias_alg = f"franken_networkx.algorithms.coloring.{child_name}"

        proxy = _types.ModuleType(alias_cl, nx_child.__doc__)
        proxy.__dict__.update(nx_child.__dict__)
        proxy.__name__ = alias_cl
        proxy.__package__ = __name__

        _route_module_to_fnx(proxy, nx_child)
        if child_name == "greedy_coloring":
            for _sname, _sval in _FNX_STRATEGY_OVERRIDES.items():
                setattr(proxy, _sname, _sval)

        globals()[child_name] = proxy
        _sys.modules[alias_cl] = proxy
        _sys.modules[alias_alg] = proxy


_routed_names = _route_to_fnx_toplevel()
_install_child_modules()
