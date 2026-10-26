"""FrankenNetworkX flow submodule.

Re-exports the upstream ``networkx.algorithms.flow`` surface so
existing ``franken_networkx.flow.*`` call sites keep working, but
overrides specific functions with fnx-native implementations that return
fnx graph types instead of NetworkX graphs.

Current native overrides:
- high-level max-flow/min-cut/min-cost helpers route to fnx top-level natives
- ``gomory_hu_tree`` — returns fnx.Graph
"""

from __future__ import annotations

import inspect as _inspect
from collections import deque as _deque
from itertools import islice as _islice, pairwise as _pairwise
from operator import itemgetter as _itemgetter

from networkx.algorithms.flow import *  # noqa: F401,F403
import networkx.algorithms.flow as _nx_flow

import franken_networkx as _fnx

__all__ = list(
    getattr(_nx_flow, "__all__", ())
    or [name for name in dir(_nx_flow) if not name.startswith("_")]
)


class CurrentEdge:
    """Mechanism for iterating over out-edges incident to a node in a circular
    manner. StopIteration exception is raised when wraparound occurs.
    """

    __slots__ = ("_edges", "_it", "_curr")

    def __init__(self, edges):
        self._edges = edges
        if self._edges:
            self._rewind()

    def get(self):
        return self._curr

    def move_to_next(self):
        try:
            self._curr = next(self._it)
        except StopIteration:
            self._rewind()
            raise

    def _rewind(self):
        self._it = iter(self._edges.items())
        self._curr = next(self._it)

    def __eq__(self, other):
        return (getattr(self, "_curr", None), self._edges) == (
            getattr(other, "_curr", None),
            other._edges,
        )


class Level:
    """Active and inactive nodes in a level."""

    __slots__ = ("active", "inactive")

    def __init__(self):
        self.active = set()
        self.inactive = set()


class GlobalRelabelThreshold:
    """Measurement of work before the global relabeling heuristic should be
    applied.
    """

    def __init__(self, n, m, freq):
        self._threshold = (n + m) / freq if freq else float("inf")
        self._work = 0

    def add_work(self, work):
        self._work += work

    def is_reached(self):
        return self._work >= self._threshold

    def clear_work(self):
        self._work = 0


def build_residual_network(G, capacity, *, backend=None, **backend_kwargs):
    _fnx._validate_backend_dispatch_keywords(
        "build_residual_network", backend, backend_kwargs
    )
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise _fnx.NetworkXError("MultiGraph and MultiDiGraph not supported (yet).")

    R = _fnx.DiGraph()
    R.add_nodes_from(G)

    inf = float("inf")
    edge_list = [
        (u, v, attr)
        for u, v, attr in G.edges(data=True)
        if u != v and attr.get(capacity, inf) > 0
    ]

    inf = (
        3
        * sum(
            attr[capacity]
            for u, v, attr in edge_list
            if capacity in attr and attr[capacity] != inf
        )
        or 1
    )
    if G.is_directed():
        for u, v, attr in edge_list:
            r = min(attr.get(capacity, inf), inf)
            if not R.has_edge(u, v):
                R.add_edge(u, v, capacity=r)
                R.add_edge(v, u, capacity=0)
            else:
                R[u][v]["capacity"] = r
    else:
        for u, v, attr in edge_list:
            r = min(attr.get(capacity, inf), inf)
            R.add_edge(u, v, capacity=r)
            R.add_edge(v, u, capacity=r)

    R.graph["inf"] = inf
    return R


def detect_unboundedness(R, s, t, *, backend=None, **backend_kwargs):
    _fnx._validate_backend_dispatch_keywords(
        "detect_unboundedness", backend, backend_kwargs
    )
    q = _deque([s])
    seen = {s}
    inf = R.graph["inf"]
    while q:
        u = q.popleft()
        for v, attr in R[u].items():
            if attr["capacity"] == inf and v not in seen:
                if v == t:
                    raise _fnx.NetworkXUnbounded(
                        "Infinite capacity path, flow unbounded above."
                    )
                seen.add(v)
                q.append(v)


def build_flow_dict(G, R, *, backend=None, **backend_kwargs):
    _fnx._validate_backend_dispatch_keywords(
        "build_flow_dict", backend, backend_kwargs
    )
    flow_dict = {}
    for u in G:
        flow_dict[u] = {v: 0 for v in G[u]}
        flow_dict[u].update(
            (v, attr["flow"]) for v, attr in R[u].items() if attr["flow"] > 0
        )
    return flow_dict


def _edmonds_karp_core(R, s, t, cutoff):
    R_nodes = R.nodes
    R_pred = R.pred
    R_succ = R.succ
    inf = R.graph["inf"]

    def augment(path):
        flow = inf
        it = iter(path)
        u = next(it)
        for v in it:
            attr = R_succ[u][v]
            flow = min(flow, attr["capacity"] - attr["flow"])
            u = v
        if flow * 2 > inf:
            raise _fnx.NetworkXUnbounded(
                "Infinite capacity path, flow unbounded above."
            )
        it = iter(path)
        u = next(it)
        for v in it:
            R_succ[u][v]["flow"] += flow
            R_succ[v][u]["flow"] -= flow
            u = v
        return flow

    def bidirectional_bfs():
        pred = {s: None}
        q_s = [s]
        succ = {t: None}
        q_t = [t]
        while True:
            q = []
            if len(q_s) <= len(q_t):
                for u in q_s:
                    for v, attr in R_succ[u].items():
                        if v not in pred and attr["flow"] < attr["capacity"]:
                            pred[v] = u
                            if v in succ:
                                return v, pred, succ
                            q.append(v)
                if not q:
                    return None, None, None
                q_s = q
            else:
                for u in q_t:
                    for v, attr in R_pred[u].items():
                        if v not in succ and attr["flow"] < attr["capacity"]:
                            succ[v] = u
                            if v in pred:
                                return v, pred, succ
                            q.append(v)
                if not q:
                    return None, None, None
                q_t = q

    flow_value = 0
    while flow_value < cutoff:
        v, pred, succ = bidirectional_bfs()
        if pred is None:
            break
        path = [v]
        u = v
        while u != s:
            u = pred[u]
            path.append(u)
        path.reverse()
        u = v
        while u != t:
            u = succ[u]
            path.append(u)
        flow_value += augment(path)
    return flow_value


def _edmonds_karp_impl(G, s, t, capacity, residual, cutoff):
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if s not in G:
        raise _fnx.NetworkXError(f"node {str(s)} not in graph")
    if t not in G:
        raise _fnx.NetworkXError(f"node {str(t)} not in graph")
    if s == t:
        raise _fnx.NetworkXError("source and sink are the same node")

    if residual is None:
        R = build_residual_network(G, capacity)
    else:
        R = residual

    for u in R:
        for e in R[u].values():
            e["flow"] = 0

    if cutoff is None:
        cutoff = float("inf")
    R.graph["flow_value"] = _edmonds_karp_core(R, s, t, cutoff)
    return R


def edmonds_karp(
    G,
    s,
    t,
    capacity="capacity",
    residual=None,
    value_only=False,
    cutoff=None,
    *,
    backend=None,
    **backend_kwargs,
):
    _fnx._validate_backend_dispatch_keywords("edmonds_karp", backend, backend_kwargs)
    R = _edmonds_karp_impl(G, s, t, capacity, residual, cutoff)
    R.graph["algorithm"] = "edmonds_karp"
    return R


def _dinitz_impl(G, s, t, capacity, residual, cutoff):
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if s not in G:
        raise _fnx.NetworkXError(f"node {str(s)} not in graph")
    if t not in G:
        raise _fnx.NetworkXError(f"node {str(t)} not in graph")
    if s == t:
        raise _fnx.NetworkXError("source and sink are the same node")

    if residual is None:
        R = build_residual_network(G, capacity)
    else:
        R = residual

    for u in R:
        for e in R[u].values():
            e["flow"] = 0

    INF = R.graph["inf"]
    if cutoff is None:
        cutoff = INF

    R_succ = R.succ
    R_pred = R.pred

    def breath_first_search():
        parents = {}
        vertex_dist = {s: 0}
        queue = _deque([(s, 0)])
        while queue:
            if t in parents:
                break
            u, dist = queue.popleft()
            for v, attr in R_succ[u].items():
                if attr["capacity"] - attr["flow"] > 0:
                    if v in parents:
                        if vertex_dist[v] == dist + 1:
                            parents[v].append(u)
                    else:
                        parents[v] = _deque([u])
                        vertex_dist[v] = dist + 1
                        queue.append((v, dist + 1))
        return parents

    def depth_first_search(parents):
        total_flow = 0
        u = t
        path = [u]
        while True:
            if len(parents[u]) > 0:
                v = parents[u][0]
                path.append(v)
            else:
                path.pop()
                if len(path) == 0:
                    break
                v = path[-1]
                parents[v].popleft()
            if v == s:
                flow = INF
                for u, v in _pairwise(path):
                    flow = min(flow, R_pred[u][v]["capacity"] - R_pred[u][v]["flow"])
                for u, v in _pairwise(reversed(path)):
                    R_pred[v][u]["flow"] += flow
                    R_pred[u][v]["flow"] -= flow
                    if R_pred[v][u]["capacity"] - R_pred[v][u]["flow"] == 0:
                        parents[v].popleft()
                        while path[-1] != v:
                            path.pop()
                total_flow += flow
                v = path[-1]
            u = v
        return total_flow

    flow_value = 0
    while flow_value < cutoff:
        parents = breath_first_search()
        if t not in parents:
            break
        this_flow = depth_first_search(parents)
        if this_flow * 2 > INF:
            raise _fnx.NetworkXUnbounded(
                "Infinite capacity path, flow unbounded above."
            )
        flow_value += this_flow

    R.graph["flow_value"] = flow_value
    return R


def dinitz(
    G,
    s,
    t,
    capacity="capacity",
    residual=None,
    value_only=False,
    cutoff=None,
    *,
    backend=None,
    **backend_kwargs,
):
    _fnx._validate_backend_dispatch_keywords("dinitz", backend, backend_kwargs)
    R = _dinitz_impl(G, s, t, capacity, residual, cutoff)
    R.graph["algorithm"] = "dinitz"
    return R


def _shortest_augmenting_path_impl(
    G, s, t, capacity, residual, two_phase, cutoff
):
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if s not in G:
        raise _fnx.NetworkXError(f"node {str(s)} not in graph")
    if t not in G:
        raise _fnx.NetworkXError(f"node {str(t)} not in graph")
    if s == t:
        raise _fnx.NetworkXError("source and sink are the same node")

    if residual is None:
        R = build_residual_network(G, capacity)
    else:
        R = residual

    R_nodes = R.nodes
    R_pred = R.pred
    R_succ = R.succ

    for u in R:
        for e in R_succ[u].values():
            e["flow"] = 0

    heights = {t: 0}
    q = _deque([(t, 0)])
    while q:
        u, height = q.popleft()
        height += 1
        for v, attr in R_pred[u].items():
            if v not in heights and attr["flow"] < attr["capacity"]:
                heights[v] = height
                q.append((v, height))

    if s not in heights:
        R.graph["flow_value"] = 0
        return R

    n = len(G)
    m = R.size() / 2

    for u in R:
        R_nodes[u]["height"] = heights[u] if u in heights else n
        R_nodes[u]["curr_edge"] = CurrentEdge(R_succ[u])

    counts = [0] * (2 * n - 1)
    for u in R:
        counts[R_nodes[u]["height"]] += 1

    inf = R.graph["inf"]

    def augment(path):
        flow = inf
        it = iter(path)
        u = next(it)
        for v in it:
            attr = R_succ[u][v]
            flow = min(flow, attr["capacity"] - attr["flow"])
            u = v
        if flow * 2 > inf:
            raise _fnx.NetworkXUnbounded(
                "Infinite capacity path, flow unbounded above."
            )
        it = iter(path)
        u = next(it)
        for v in it:
            R_succ[u][v]["flow"] += flow
            R_succ[v][u]["flow"] -= flow
            u = v
        return flow

    def relabel(u):
        height = n - 1
        for v, attr in R_succ[u].items():
            if attr["flow"] < attr["capacity"]:
                height = min(height, R_nodes[v]["height"])
        return height + 1

    if cutoff is None:
        cutoff = float("inf")

    flow_value = 0
    path = [s]
    u = s
    d = n if not two_phase else int(min(m**0.5, 2 * n ** (2.0 / 3)))
    done = R_nodes[s]["height"] >= d
    while not done:
        height = R_nodes[u]["height"]
        curr_edge = R_nodes[u]["curr_edge"]
        while True:
            v, attr = curr_edge.get()
            if height == R_nodes[v]["height"] + 1 and attr["flow"] < attr["capacity"]:
                path.append(v)
                u = v
                break
            try:
                curr_edge.move_to_next()
            except StopIteration:
                counts[height] -= 1
                if counts[height] == 0:
                    R.graph["flow_value"] = flow_value
                    return R
                height = relabel(u)
                if u == s and height >= d:
                    if not two_phase:
                        R.graph["flow_value"] = flow_value
                        return R
                    else:
                        done = True
                        break
                counts[height] += 1
                R_nodes[u]["height"] = height
                if u != s:
                    path.pop()
                    u = path[-1]
                    break
        if u == t:
            flow_value += augment(path)
            if flow_value >= cutoff:
                R.graph["flow_value"] = flow_value
                return R
            path = [s]
            u = s

    flow_value += _edmonds_karp_core(R, s, t, cutoff - flow_value)
    R.graph["flow_value"] = flow_value
    return R


def shortest_augmenting_path(
    G,
    s,
    t,
    capacity="capacity",
    residual=None,
    value_only=False,
    two_phase=False,
    cutoff=None,
    *,
    backend=None,
    **backend_kwargs,
):
    _fnx._validate_backend_dispatch_keywords(
        "shortest_augmenting_path", backend, backend_kwargs
    )
    R = _shortest_augmenting_path_impl(
        G, s, t, capacity, residual, two_phase, cutoff
    )
    R.graph["algorithm"] = "shortest_augmenting_path"
    return R


def _preflow_push_impl(
    G, s, t, capacity, residual, global_relabel_freq, value_only
):
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if s not in G:
        raise _fnx.NetworkXError(f"node {str(s)} not in graph")
    if t not in G:
        raise _fnx.NetworkXError(f"node {str(t)} not in graph")
    if s == t:
        raise _fnx.NetworkXError("source and sink are the same node")

    if global_relabel_freq is None:
        global_relabel_freq = 0
    if global_relabel_freq < 0:
        raise _fnx.NetworkXError("global_relabel_freq must be nonnegative.")

    if residual is None:
        R = build_residual_network(G, capacity)
    else:
        R = residual

    detect_unboundedness(R, s, t)

    R_nodes = R.nodes
    R_pred = R.pred
    R_succ = R.succ

    for u in R:
        R_nodes[u]["excess"] = 0
        for e in R_succ[u].values():
            e["flow"] = 0

    def reverse_bfs(src):
        heights = {src: 0}
        q = _deque([(src, 0)])
        while q:
            u, height = q.popleft()
            height += 1
            for v, attr in R_pred[u].items():
                if v not in heights and attr["flow"] < attr["capacity"]:
                    heights[v] = height
                    q.append((v, height))
        return heights

    heights = reverse_bfs(t)

    if s not in heights:
        R.graph["flow_value"] = 0
        return R

    n = len(R)
    max_height = max(heights[u] for u in heights if u != s)
    heights[s] = n

    grt = GlobalRelabelThreshold(n, R.size(), global_relabel_freq)

    for u in R:
        R_nodes[u]["height"] = heights[u] if u in heights else n + 1
        R_nodes[u]["curr_edge"] = CurrentEdge(R_succ[u])

    def push(u, v, flow):
        R_succ[u][v]["flow"] += flow
        R_succ[v][u]["flow"] -= flow
        R_nodes[u]["excess"] -= flow
        R_nodes[v]["excess"] += flow

    for u, attr in R_succ[s].items():
        flow = attr["capacity"]
        if flow > 0:
            push(s, u, flow)

    levels = [Level() for _ in range(2 * n)]
    for u in R:
        if u != s and u != t:
            level = levels[R_nodes[u]["height"]]
            if R_nodes[u]["excess"] > 0:
                level.active.add(u)
            else:
                level.inactive.add(u)

    def activate(v):
        if v != s and v != t:
            level = levels[R_nodes[v]["height"]]
            if v in level.inactive:
                level.inactive.remove(v)
                level.active.add(v)

    def relabel(u):
        grt.add_work(len(R_succ[u]))
        return (
            min(
                R_nodes[v]["height"]
                for v, attr in R_succ[u].items()
                if attr["flow"] < attr["capacity"]
            )
            + 1
        )

    def discharge(u, is_phase1):
        height = R_nodes[u]["height"]
        curr_edge = R_nodes[u]["curr_edge"]
        next_height = height
        levels[height].active.remove(u)
        while True:
            v, attr = curr_edge.get()
            if height == R_nodes[v]["height"] + 1 and attr["flow"] < attr["capacity"]:
                flow = min(R_nodes[u]["excess"], attr["capacity"] - attr["flow"])
                push(u, v, flow)
                activate(v)
                if R_nodes[u]["excess"] == 0:
                    levels[height].inactive.add(u)
                    break
            try:
                curr_edge.move_to_next()
            except StopIteration:
                height = relabel(u)
                if is_phase1 and height >= n - 1:
                    levels[height].active.add(u)
                    break
                next_height = height
        R_nodes[u]["height"] = height
        return next_height

    def gap_heuristic(height):
        for level in _islice(levels, height + 1, max_height + 1):
            for u in level.active:
                R_nodes[u]["height"] = n + 1
            for u in level.inactive:
                R_nodes[u]["height"] = n + 1
            levels[n + 1].active.update(level.active)
            level.active.clear()
            levels[n + 1].inactive.update(level.inactive)
            level.inactive.clear()

    def global_relabel(from_sink):
        src = t if from_sink else s
        heights = reverse_bfs(src)
        if not from_sink:
            del heights[t]
        max_height = max(heights.values())
        if from_sink:
            for u in R:
                if u not in heights and R_nodes[u]["height"] < n:
                    heights[u] = n + 1
        else:
            for u in heights:
                heights[u] += n
            max_height += n
        del heights[src]
        for u, new_height in heights.items():
            old_height = R_nodes[u]["height"]
            if new_height != old_height:
                if u in levels[old_height].active:
                    levels[old_height].active.remove(u)
                    levels[new_height].active.add(u)
                else:
                    levels[old_height].inactive.remove(u)
                    levels[new_height].inactive.add(u)
                R_nodes[u]["height"] = new_height
        return max_height

    height = max_height
    while height > 0:
        while True:
            level = levels[height]
            if not level.active:
                height -= 1
                break
            old_height = height
            old_level = level
            u = next(iter(level.active))
            height = discharge(u, True)
            if grt.is_reached():
                height = global_relabel(True)
                max_height = height
                grt.clear_work()
            elif not old_level.active and not old_level.inactive:
                gap_heuristic(old_height)
                height = old_height - 1
                max_height = height
            else:
                max_height = max(max_height, height)

    if value_only:
        R.graph["flow_value"] = R_nodes[t]["excess"]
        return R

    height = global_relabel(False)
    grt.clear_work()

    while height > n:
        while True:
            level = levels[height]
            if not level.active:
                height -= 1
                break
            u = next(iter(level.active))
            height = discharge(u, False)
            if grt.is_reached():
                height = global_relabel(False)
                grt.clear_work()

    R.graph["flow_value"] = R_nodes[t]["excess"]
    return R


def preflow_push(
    G,
    s,
    t,
    capacity="capacity",
    residual=None,
    global_relabel_freq=1,
    value_only=False,
    *,
    backend=None,
    **backend_kwargs,
):
    _fnx._validate_backend_dispatch_keywords("preflow_push", backend, backend_kwargs)
    R = _preflow_push_impl(
        G, s, t, capacity, residual, global_relabel_freq, value_only
    )
    R.graph["algorithm"] = "preflow_push"
    return R


def _boykov_kolmogorov_impl(G, s, t, capacity, residual, cutoff):
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if s not in G:
        raise _fnx.NetworkXError(f"node {str(s)} not in graph")
    if t not in G:
        raise _fnx.NetworkXError(f"node {str(t)} not in graph")
    if s == t:
        raise _fnx.NetworkXError("source and sink are the same node")

    if residual is None:
        R = build_residual_network(G, capacity)
    else:
        R = residual

    for u in R:
        for e in R[u].values():
            e["flow"] = 0

    INF = R.graph["inf"]
    if cutoff is None:
        cutoff = INF

    R_succ = R.succ
    R_pred = R.pred

    def grow():
        while active:
            u = active[0]
            if u in source_tree:
                this_tree = source_tree
                other_tree = target_tree
                neighbors = R_succ
            else:
                this_tree = target_tree
                other_tree = source_tree
                neighbors = R_pred
            for v, attr in neighbors[u].items():
                if attr["capacity"] - attr["flow"] > 0:
                    if v not in this_tree:
                        if v in other_tree:
                            return (u, v) if this_tree is source_tree else (v, u)
                        this_tree[v] = u
                        dist[v] = dist[u] + 1
                        timestamp[v] = timestamp[u]
                        active.append(v)
                    elif v in this_tree and _is_closer(u, v):
                        this_tree[v] = u
                        dist[v] = dist[u] + 1
                        timestamp[v] = timestamp[u]
            active.popleft()
        return None, None

    def augment(u, v):
        attr = R_succ[u][v]
        flow = min(INF, attr["capacity"] - attr["flow"])
        path = [u]
        w = u
        while w != s:
            n = w
            w = source_tree[n]
            attr = R_pred[n][w]
            flow = min(flow, attr["capacity"] - attr["flow"])
            path.append(w)
        path.reverse()
        path.append(v)
        w = v
        while w != t:
            n = w
            w = target_tree[n]
            attr = R_succ[n][w]
            flow = min(flow, attr["capacity"] - attr["flow"])
            path.append(w)
        it = iter(path)
        u = next(it)
        these_orphans = []
        for v in it:
            R_succ[u][v]["flow"] += flow
            R_succ[v][u]["flow"] -= flow
            if R_succ[u][v]["flow"] == R_succ[u][v]["capacity"]:
                if v in source_tree:
                    source_tree[v] = None
                    these_orphans.append(v)
                if u in target_tree:
                    target_tree[u] = None
                    these_orphans.append(u)
            u = v
        orphans.extend(sorted(these_orphans, key=dist.get))
        return flow

    def adopt():
        while orphans:
            u = orphans.popleft()
            if u in source_tree:
                tree = source_tree
                neighbors = R_pred
            else:
                tree = target_tree
                neighbors = R_succ
            nbrs = (
                (n, attr, dist[n])
                for n, attr in neighbors[u].items()
                if n in tree
            )
            for v, attr, d in sorted(nbrs, key=_itemgetter(2)):
                if attr["capacity"] - attr["flow"] > 0:
                    if _has_valid_root(v, tree):
                        tree[u] = v
                        dist[u] = dist[v] + 1
                        timestamp[u] = time
                        break
            else:
                nbrs = (
                    (n, attr, dist[n])
                    for n, attr in neighbors[u].items()
                    if n in tree
                )
                for v, attr, d in sorted(nbrs, key=_itemgetter(2)):
                    if attr["capacity"] - attr["flow"] > 0:
                        if v not in active:
                            active.append(v)
                    if tree[v] == u:
                        tree[v] = None
                        orphans.appendleft(v)
                if u in active:
                    active.remove(u)
                del tree[u]

    def _has_valid_root(n, tree):
        path = []
        v = n
        while v is not None:
            path.append(v)
            if v in (s, t):
                base_dist = 0
                break
            elif timestamp[v] == time:
                base_dist = dist[v]
                break
            v = tree[v]
        else:
            return False
        length = len(path)
        for i, u in enumerate(path, 1):
            dist[u] = base_dist + length - i
            timestamp[u] = time
        return True

    def _is_closer(u, v):
        return timestamp[v] <= timestamp[u] and dist[v] > dist[u] + 1

    source_tree = {s: None}
    target_tree = {t: None}
    active = _deque([s, t])
    orphans = _deque()
    flow_value = 0
    time = 1
    timestamp = {s: time, t: time}
    dist = {s: 0, t: 0}
    while flow_value < cutoff:
        u, v = grow()
        if u is None:
            break
        time += 1
        flow_value += augment(u, v)
        adopt()

    if flow_value * 2 > INF:
        raise _fnx.NetworkXUnbounded("Infinite capacity path, flow unbounded above.")

    R.graph["trees"] = (source_tree, target_tree)
    R.graph["flow_value"] = flow_value
    return R


def boykov_kolmogorov(
    G,
    s,
    t,
    capacity="capacity",
    residual=None,
    value_only=False,
    cutoff=None,
    *,
    backend=None,
    **backend_kwargs,
):
    _fnx._validate_backend_dispatch_keywords(
        "boykov_kolmogorov", backend, backend_kwargs
    )
    R = _boykov_kolmogorov_impl(G, s, t, capacity, residual, cutoff)
    R.graph["algorithm"] = "boykov_kolmogorov"
    return R


for _fn_name in (
    "build_residual_network",
    "detect_unboundedness",
    "build_flow_dict",
    "edmonds_karp",
    "dinitz",
    "shortest_augmenting_path",
    "preflow_push",
    "boykov_kolmogorov",
):
    if hasattr(_nx_flow, _fn_name):
        globals()[_fn_name].__doc__ = getattr(_nx_flow, _fn_name).__doc__


# br-r37-c1-ojs7g: ``from networkx.algorithms.flow import *`` above left the
# high-level flow helpers bound to NetworkX implementations even though fnx has
# native top-level versions with local parity/perf fixes. Route the root flow
# namespace through fnx; deeper child modules such as
# ``franken_networkx.algorithms.flow.maxflow`` remain NetworkX aliases.
_FNX_NATIVE_FLOW_NAMES = (
    "capacity_scaling", "cost_of_flow", "gomory_hu_tree", "max_flow_min_cost",
    "maximum_flow", "maximum_flow_value", "min_cost_flow", "min_cost_flow_cost",
    "minimum_cut", "minimum_cut_value", "network_simplex",
)


def _make_fnx_flow_router(name):
    def routed(*args, **kwargs):
        return getattr(_fnx, name)(*args, **kwargs)

    upstream = getattr(_nx_flow, name)
    routed.__name__ = name
    routed.__qualname__ = name
    routed.__doc__ = upstream.__doc__
    routed.__signature__ = _inspect.signature(upstream)
    return routed


for _name in _FNX_NATIVE_FLOW_NAMES:
    globals()[_name] = _make_fnx_flow_router(_name)

