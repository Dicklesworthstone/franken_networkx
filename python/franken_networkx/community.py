"""FrankenNetworkX community submodule.

Re-exports the upstream ``networkx.algorithms.community`` surface so
existing ``franken_networkx.community.*`` call sites keep working, but
overrides specific functions with fnx-native implementations as the
native port lands.

br-r37-c1-rq36c: previously ``franken_networkx.community`` was a
direct alias for ``networkx.algorithms.community``, so calls like
``fnx.community.label_propagation_communities(G)`` ran nx's pure-Python
implementation against an fnx Graph (paying dispatch overhead on top
of the algorithm's own runtime). This module fronts the same surface
but routes the algorithms with fnx fast paths through them.
"""

from __future__ import annotations

import math as _math
import random as _random

import networkx.algorithms.community as _nx_community
from networkx.algorithms.community import *  # noqa: F401,F403

import franken_networkx as _fnx
from franken_networkx._fnx import (
    louvain_partitions_start as _native_louvain_partitions_start,
    networkx_greedy_modularity_merges as _native_greedy_modularity_merges,
)


_LOUVAIN_RANDOM_CLASS = _random.Random
_LOUVAIN_RANDOM_PROTOCOL = {
    name: getattr(_LOUVAIN_RANDOM_CLASS, name)
    for name in (
        "shuffle", "_randbelow", "getrandbits", "random", "getstate", "setstate",
        "seed", "__init__", "__new__", "__getattribute__",
    )
}

_LABEL_PROPAGATION_RANDOM_CLASS = _random.Random
_LABEL_PROPAGATION_RANDOM_PROTOCOL = {
    name: getattr(_LABEL_PROPAGATION_RANDOM_CLASS, name)
    for name in (
        "shuffle", "choice", "_randbelow", "getrandbits", "random",
        "__getattribute__",
    )
}


def _louvain_native_rng_allowed(seed):
    """A state handoff cannot replace custom shuffle or random-state hooks."""
    if _random.Random is not _LOUVAIN_RANDOM_CLASS or any(
        getattr(_LOUVAIN_RANDOM_CLASS, name) is not method
        for name, method in _LOUVAIN_RANDOM_PROTOCOL.items()
    ):
        return False
    if type(seed) is int:
        return True
    return type(seed) is _LOUVAIN_RANDOM_CLASS and not any(
        name in vars(seed) for name in _LOUVAIN_RANDOM_PROTOCOL
    )


def _louvain_random_sources(seed):
    kernel_seed = _fnx._kernel_seed(seed)
    # Large integers are already normalized by _kernel_seed. Reusing that
    # instance avoids invoking overridden Random construction/seed hooks twice.
    rng = (
        kernel_seed if type(kernel_seed) is _random.Random
        else _fnx._generator_random_state(seed)
    )
    return rng, kernel_seed


def modularity(G, communities, weight="weight", resolution=1, *, backend=None, **backend_kwargs):
    """Return the modularity of a partition of ``G``.

    br-r37-c1-modsubmod: this module's ``from
    networkx.algorithms.community import *`` re-exported nx's pure-Python
    ``modularity``, so ``fnx.community.modularity(fnx_graph)`` ran nx's
    algorithm against the fnx Graph's adjacency views (~30x nx on a
    1200-node graph). Route to the registered native backend impl
    (``_modularity_backend_impl`` -> Rust ``_raw_modularity``), which is
    byte-for-byte equal to nx (weighted / resolution / directed / the
    NotAPartition + zero-edge ZeroDivisionError contracts) and ~30x faster.
    """
    _fnx._validate_backend_dispatch_keywords("modularity", backend, backend_kwargs)
    return _fnx._modularity_backend_impl(
        G, communities, weight=weight, resolution=resolution
    )


class _CommunityBinaryHeap:
    def __init__(self):
        from itertools import count as _count

        self._dict = {}
        self._heap = []
        self._count = _count()

    def __bool__(self):
        return bool(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def get(self, key, default=None):
        return self._dict.get(key, default)

    def pop(self):
        from heapq import heappop as _heappop

        d = self._dict
        if not d:
            raise _fnx.NetworkXError("heap is empty")
        heap = self._heap
        while True:
            value, _, key = _heappop(heap)
            if key in d and value == d[key]:
                break
        del d[key]
        return key, value

    def insert(self, key, value, allow_increase=False):
        from heapq import heappush as _heappush

        d = self._dict
        if key in d:
            old_value = d[key]
            if value < old_value or (allow_increase and value > old_value):
                d[key] = value
                _heappush(self._heap, (value, next(self._count), key))
                return value < old_value
            return False
        d[key] = value
        _heappush(self._heap, (value, next(self._count), key))
        return True


def _kernighan_lin_sweep(edge_info, side):
    heap0, heap1 = cost_heaps = _CommunityBinaryHeap(), _CommunityBinaryHeap()
    for u, nbrs in edge_info.items():
        cost_u = sum(wt if side[v] else -wt for v, wt in nbrs.items())
        if side[u]:
            heap1.insert(u, cost_u)
        else:
            heap0.insert(u, -cost_u)

    def _update_heap_values(node):
        side_node = side[node]
        for nbr, wt in edge_info[node].items():
            side_nbr = side[nbr]
            if side_nbr == side_node:
                wt = -wt
            heap_nbr = cost_heaps[side_nbr]
            if nbr in heap_nbr:
                cost_nbr = heap_nbr.get(nbr) + 2 * wt
                heap_nbr.insert(nbr, cost_nbr, allow_increase=True)

    i = 0
    totcost = 0
    while heap0 and heap1:
        u, cost_u = heap0.pop()
        _update_heap_values(u)
        v, cost_v = heap1.pop()
        _update_heap_values(v)
        totcost += cost_u + cost_v
        i += 1
        yield totcost, i, (u, v)


def _community_groups(many_to_one):
    from collections import defaultdict as _defaultdict

    one_to_many = _defaultdict(set)
    for v, k in many_to_one.items():
        one_to_many[k].add(v)
    return dict(one_to_many)


def kernighan_lin_bisection(
    G, partition=None, max_iter=10, weight="weight", seed=None, *, backend=None, **backend_kwargs
):
    """Partition ``G`` into two blocks via the Kernighan-Lin algorithm."""
    _fnx._validate_backend_dispatch_keywords(
        "kernighan_lin_bisection", backend, backend_kwargs
    )
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")

    nodes = list(G)
    if partition is None:
        rng = _fnx._generator_random_state(seed)
        rng.shuffle(nodes)
        mid = len(nodes) // 2
        A, B = nodes[:mid], nodes[mid:]
    else:
        try:
            A, B = partition
        except (TypeError, ValueError) as err:
            raise _fnx.NetworkXError("partition must be two sets") from err
        if not is_partition(G, [A, B]):
            raise _fnx.NetworkXError("partition invalid")

    side = {node: (node in A) for node in nodes}

    if type(G) is _fnx.Graph and not callable(weight):
        dod = _fnx.to_dict_of_dicts(G)
        edge_info = {
            u: {v: wt for v, d in nbrs.items() if (wt := d.get(weight, 1)) is not None}
            for u, nbrs in dod.items()
        }
    else:
        if callable(weight):
            sum_weight = weight
        elif G.is_multigraph():
            sum_weight = lambda u, v, d: sum(dd.get(weight, 1) for dd in d.values())
        else:
            sum_weight = lambda u, v, d: d.get(weight, 1)
        edge_info = {
            u: {
                v: wt
                for v, d in G.adj[u].items()
                if (wt := sum_weight(u, v, d)) is not None
            }
            for u in nodes
        }

    for _ in range(max_iter):
        costs = list(_kernighan_lin_sweep(edge_info, side))
        min_cost, min_i, _ = min(costs)
        if min_cost >= 0:
            break
        for _cost, _idx, (u, v) in costs[:min_i]:
            side[u] = 1
            side[v] = 0

    part1 = {u for u, s in side.items() if s == 0}
    part2 = {u for u, s in side.items() if s == 1}
    return part1, part2


def label_propagation_communities(G, *, backend=None, **backend_kwargs):
    """Community sets via the semi-synchronous label-propagation method.

    br-r37-c1-0upl7: the previous override (br-r37-c1-lpstruct) still built a
    structural ``nx.Graph`` and ran nx's pure-Python algorithm on it (~1.8x
    nx). Fully de-delegate for the simple ``Graph``: the algorithm only reads
    a graph colouring (native ``greedy_color``, already byte-exact with nx)
    plus per-node neighbour-label frequencies, so run it in index space over a
    one-time key-only adjacency snapshot with a reusable mark-array.

    Byte-identical to nx: colour classes are processed in nx's exact order
    (``greedy_color`` dict-iteration order, mirroring ``_color_network``);
    within a colour class the update order is irrelevant (a proper colouring
    makes each class an independent set, so updates don't see each other);
    labels are the same 0..n-1 ints; the Prec-Max tie-break (``max`` of the
    most-frequent label set) and the final node-order grouping all match.

    Directed graphs raise (nx is ``@not_implemented_for('directed')``);
    multigraph / view / non-fnx graphs delegate to nx.
    """
    _fnx._validate_backend_dispatch_keywords(
        "label_propagation_communities", backend, backend_kwargs
    )
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")

    from collections import defaultdict

    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}
    adj = [None] * n
    _nak = getattr(G, "_native_adjacency_keys", None)
    if type(G) is _fnx.Graph and _nak is not None:
        for node, nbrs in _nak():
            adj[idx[node]] = [idx[v] for v in nbrs]
    else:
        for u in node_list:
            adj[idx[u]] = [idx[v] for v in G[u]]

    # Colour classes in nx's exact order (greedy_color dict order).
    colors = _fnx.coloring.greedy_color(G)
    color_buckets = {}
    color_order = []
    for node, color in colors.items():
        bucket = color_buckets.get(color)
        if bucket is None:
            bucket = []
            color_buckets[color] = bucket
            color_order.append(color)
        bucket.append(idx[node])

    labels = list(range(n))
    freq = [0] * n

    def _most_frequent(node):
        # Returns the list of max-frequency neighbour labels (order-immaterial:
        # callers use only membership, length and max).
        touched = []
        for v in adj[node]:
            lab = labels[v]
            if freq[lab] == 0:
                touched.append(lab)
            freq[lab] += 1
        max_freq = freq[touched[0]]
        for lab in touched:
            if freq[lab] > max_freq:
                max_freq = freq[lab]
        best = [lab for lab in touched if freq[lab] == max_freq]
        for lab in touched:
            freq[lab] = 0
        return best

    def _complete():
        for v in range(n):
            if not adj[v]:
                continue
            if labels[v] not in _most_frequent(v):
                return False
        return True

    while not _complete():
        for color in color_order:
            for node in color_buckets[color]:
                if not adj[node]:
                    continue
                best = _most_frequent(node)
                if len(best) == 1:
                    labels[node] = best[0]
                elif len(best) > 1 and labels[node] not in best:
                    labels[node] = max(best)  # Prec-Max tie-break

    clusters = defaultdict(set)
    for i in range(n):
        clusters[labels[i]].add(node_list[i])
    return clusters.values()


def louvain_communities(
    G,
    weight="weight",
    resolution=1,
    threshold=1e-07,
    max_level=None,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Find communities via native or owned Python Louvain levels.

    Ordinary graph/numeric/random inputs retain the native kernel. The owned
    level engine preserves custom random hooks, Python numeric arithmetic,
    graph views and subclasses, without NetworkX algorithm delegation.
    """
    _fnx._validate_backend_dispatch_keywords(
        "louvain_communities", backend, backend_kwargs
    )
    from collections import deque
    from itertools import islice

    from franken_networkx._louvain import partitions

    # Resolve the seed before graph traversal and level-limit validation.
    rng, kernel_seed = _louvain_random_sources(seed)
    levels = partitions(G, weight, resolution, threshold, rng, _LouvainLevelSets)
    if max_level is not None:
        if max_level <= 0:
            raise ValueError("max_level argument must be a positive integer or None")
        # Use the actual iterator adapter for integer/index and range errors;
        # it validates now but does not inspect the graph or draw randomness.
        levels = islice(levels, max_level)
    native = _louvain_native_arguments(G, weight, resolution, threshold, kernel_seed)
    if native is not None and (
        max_level is None or (type(max_level) is int and max_level > 0)
    ):
        run = _fnx._raw_louvain_communities(G, weight, *native, max_level, kernel_seed)
        if run is not None:
            nodes, native_levels = run
            sets = _LouvainLevelSets(nodes)
            for moves in native_levels:
                partition = sets.level(moves)
            return partition
    return deque(levels, maxlen=1).pop()


def _louvain_native_arguments(G, weight, resolution, threshold, kernel_seed):
    """Return native parameters only when graph and RNG protocols are plain."""
    if not _louvain_native_rng_allowed(kernel_seed) or type(G) not in (
        _fnx.Graph,
        _fnx.DiGraph,
        _fnx.MultiGraph,
        _fnx.MultiDiGraph,
    ):
        return None
    if _fnx._has_networkx_private_storage(G):
        return None
    resolution = _as_exact_float(resolution)
    threshold = _as_exact_float(threshold)
    if (
        type(weight) is not str
        or resolution is None
        or threshold is None
        or not _math.isfinite(resolution)
        or not _math.isfinite(threshold)
    ):
        return None
    return float(resolution), float(threshold)


def louvain_partitions(
    G,
    weight="weight",
    resolution=1,
    threshold=0.0000001,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Yield the partition at each level of the Louvain algorithm.

    br-r37-c1-81vo1: networkx's generator ran on the fnx graph through its
    views (0.77x networkx). The levels now come from the native kernel behind
    ``louvain_communities``, one generator resume at a time, as networkx's do:
    the seed is resolved when the generator is created, ``G`` is read at the
    first resume, and each resume draws from the seed's generator only what
    networkx's would - so a caller drawing between levels sees networkx's
    stream. Where the kernel declines, the owned level engine reads the
    caller's graph directly and preserves custom numeric and random protocols.
    """
    _fnx._validate_backend_dispatch_keywords(
        "louvain_partitions", backend, backend_kwargs
    )
    rng, kernel_seed = _louvain_random_sources(seed)
    return _louvain_partition_levels(G, weight, resolution, threshold, rng, kernel_seed)


def _louvain_partition_levels(G, weight, resolution, threshold, rng, kernel_seed):
    # networkx's generator body: nothing runs before the first resume.
    native = _louvain_native_arguments(G, weight, resolution, threshold, kernel_seed)
    stepper = (
        None if native is None else _native_louvain_partitions_start(G, weight, *native)
    )
    if stepper is None:
        from franken_networkx._louvain import partitions

        yield from partitions(
            G, weight, resolution, threshold, rng, _LouvainLevelSets
        )
        return
    sets = _LouvainLevelSets(stepper.node_keys())
    while (moves := stepper.step(kernel_seed)) is not None:
        yield sets.level(moves)


class _LouvainLevelSets:
    """networkx's ``louvain_partitions`` bookkeeping, replaying the native
    kernel's moves (br-r37-c1-ygt3z).

    networkx moves a node by ``partition[a].difference_update(com)`` /
    ``partition[b].update(com)`` - ``com`` the node's set of original nodes -
    on sets it keeps across levels, and yields copies of them; between levels
    ``_gen_graph`` builds each new node's ``com`` by updating a fresh set from
    each member of an ``inner_partition`` set. Wherever hashes collide, a
    set's iteration order follows that history, so the kernel returns the
    moves it made - networkx's, in networkx's order - and they are replayed
    here on real sets. ``level`` takes one level's ``(node, from, to)`` level
    positions and returns what networkx yields for it.
    """

    __slots__ = ("partition", "nodes", "coms", "inner")

    def __init__(self, nodes):
        self.partition = [{u} for u in nodes]
        self.nodes = nodes
        self.coms = None  # the first level's nodes are the graph's own
        self.inner = None

    def level(self, moves, *, nodes=None, membership=None):
        if nodes is not None:
            # The owned engine has a real level graph. Its constructor and
            # node-attribute factories may define order and memberships.
            self.nodes, self.coms = nodes, None
        elif self.inner is not None:
            # _gen_graph of the level before: node i stands for inner[i].
            coms = self.coms
            self.coms = new_coms = []
            for part in self.inner:
                members = set()
                for node in part:
                    members.update({node} if coms is None else coms[node])
                new_coms.append(members)
            self.nodes = range(len(new_coms))
        partition, nodes, coms = self.partition, self.nodes, self.coms
        inner = [{u} for u in nodes]
        for u, a, b in moves:
            node = nodes[u]
            com = (
                membership(node) if membership is not None
                else ({node} if coms is None else coms[u])
            )
            partition[a].difference_update(com)
            inner[a].remove(node)
            partition[b].update(com)
            inner[b].add(node)
        self.partition = partition = list(filter(len, partition))
        self.inner = list(filter(len, inner))
        return [s.copy() for s in partition]


def _as_exact_float(value):
    """``value`` when a float of it is what networkx's arithmetic uses, else ``None``."""
    if type(value) is float or (type(value) is int and -(2**53) <= value <= 2**53):
        return value
    return None


class _ModularityHeapEntry:
    """A merge priority whose tie-break uses the caller's node objects."""

    __slots__ = ("priority", "edge")

    def __init__(self, priority, edge):
        self.priority = priority
        self.edge = edge

    def __lt__(self, other):
        if self.priority == other.priority:
            try:
                return self.edge < other.edge
            except TypeError as exc:
                raise TypeError(
                    "Consider using a tuple, with a priority value that can be compared."
                ) from exc
        return self.priority < other.priority


class _ModularityQueue:
    """An indexed heap with one live entry per adjacent community pair.

    Lazy stale entries change comparisons for NaN priorities and custom node
    labels. Replacing entries in place keeps those inputs on the same sparse
    merge schedule as ordinary numbers, with bounded queue storage.
    """

    def __init__(self, entries=()):
        from heapq import heapify

        self.heap = list(entries)
        heapify(self.heap)
        self.positions = {item.edge: i for i, item in enumerate(self.heap)}

    def __len__(self):
        return len(self.heap)

    def _rise(self, position, floor=0):
        item = self.heap[position]
        while position > floor:
            parent = (position - 1) // 2
            if not item < self.heap[parent]:
                break
            self.heap[position] = self.heap[parent]
            self.positions[self.heap[position].edge] = position
            position = parent
        self.heap[position] = item
        self.positions[item.edge] = position

    def _repair(self, position):
        item = self.heap[position]
        child = 2 * position + 1
        while child < len(self.heap):
            right = child + 1
            if right < len(self.heap) and not self.heap[child] < self.heap[right]:
                child = right
            self.heap[position] = self.heap[child]
            self.positions[self.heap[position].edge] = position
            position = child
            child = 2 * position + 1
        self.heap[position] = item
        self._rise(position)

    def push(self, item):
        if item.edge in self.positions:
            return
        self.heap.append(item)
        self._rise(len(self.heap) - 1)

    def pop(self):
        item = self.heap[0]
        self.remove(item.edge)
        return item

    def remove(self, edge):
        position = self.positions.pop(edge)
        last = self.heap.pop()
        if position < len(self.heap):
            self.heap[position] = last
            self._repair(position)

    def replace(self, edge, item):
        position = self.positions.pop(edge)
        self.heap[position] = item
        self._repair(position)


def _greedy_modularity_communities_owned(G, weight, resolution, cutoff, best_n):
    """Sparse CNM merges in the caller's Python numeric and node domains.

    The state is a symmetric gain table, a heap for each row, and a heap of
    row minima. A merge absorbs its first community into its second, updates
    only adjacent gains, and retains the original frozenset construction
    order. No graph conversion or upstream algorithm is required.
    """
    if not G.size():
        return [{node} for node in G]
    if cutoff < 1 or cutoff > G.number_of_nodes():
        raise ValueError(f"cutoff must be between 1 and {len(G)}. Got {cutoff}.")
    if best_n is not None:
        if best_n < 1 or best_n > G.number_of_nodes():
            raise ValueError(f"best_n must be between 1 and {len(G)}. Got {best_n}.")
        if best_n < cutoff:
            raise ValueError(f"Must have best_n >= cutoff. Got {best_n} < {cutoff}")
        if best_n == 1:
            return [set(G)]
    else:
        best_n = G.number_of_nodes()

    directed = G.is_directed()
    # Start the solver through the graph's public node-count protocol before
    # weighted reads, including on a graph subclass with observable providers.
    G.number_of_nodes()
    reciprocal = 1 / G.size(weight)
    if directed:
        def directional_degrees(name):
            view = getattr(G, name)(weight=weight)
            if type(G) is _fnx.DiGraph and weight is not None and not isinstance(weight, str):
                # Full native degree iteration accepts only string selectors;
                # indexed reads retain arbitrary dictionary-key semantics.
                for node in G:
                    yield node, view[node]
            else:
                yield from view

        outgoing = {
            node: degree * reciprocal for node, degree in directional_degrees("out_degree")
        }
        incoming = {
            node: degree * reciprocal for node, degree in directional_degrees("in_degree")
        }
    else:
        outgoing = incoming = {
            node: degree * reciprocal * 0.5 for node, degree in G.degree(weight=weight)
        }

    from collections import defaultdict

    gains = defaultdict(lambda: defaultdict(float))
    for left, right, value in G.edges(data=weight, default=1):
        if left != right:
            gains[left][right] += value
            gains[right][left] += value
    for left, row in gains.items():
        for right, value in row.items():
            row[right] = reciprocal * value - resolution * (
                outgoing[left] * incoming[right] + incoming[left] * outgoing[right]
            )

    rows = {
        node: _ModularityQueue(
            _ModularityHeapEntry(-gain, (node, neighbor))
            for neighbor, gain in gains[node].items()
        )
        for node in G
    }
    frontier = _ModularityQueue(rows[node].heap[0] for node in G if rows[node])
    communities = {node: frozenset([node]) for node in G}

    def remove_pair(row_node, neighbor):
        row = rows[row_node]
        old = row.heap[0]
        row.remove((row_node, neighbor))
        if old.edge == (row_node, neighbor):
            frontier.remove(old.edge)
            if row:
                frontier.push(row.heap[0])

    def set_pair(row_node, neighbor, gain, existed):
        row = rows[row_node]
        previous = row.heap[0] if row else None
        entry = _ModularityHeapEntry(-gain, (row_node, neighbor))
        if existed:
            row.replace(entry.edge, entry)
        else:
            row.push(entry)
        current = row.heap[0]
        if previous is None:
            frontier.push(current)
        elif previous.edge != current.edge or previous.priority != current.priority:
            frontier.replace(previous.edge, current)

    while len(communities) > cutoff:
        if len(frontier) <= 1:
            result = sorted(communities.values(), key=len, reverse=True)
            while len(result) > best_n:
                first, second, *remaining = result
                result = [first ^ second, *remaining]
            return result
        selected = frontier.pop()
        left, right = selected.edge
        if -selected.priority < 0 and len(communities) <= best_n:
            break

        rows[left].pop()
        if rows[left]:
            frontier.push(rows[left].heap[0])
        remove_pair(right, left)
        communities[right] = frozenset(communities[left] | communities[right])
        del communities[left]

        left_neighbors = set(gains[left])
        right_neighbors = set(gains[right])
        for neighbor in (left_neighbors | right_neighbors) - {left, right}:
            if neighbor in left_neighbors and neighbor in right_neighbors:
                value = gains[right][neighbor] + gains[left][neighbor]
            elif neighbor in right_neighbors:
                value = gains[right][neighbor] - resolution * (
                    outgoing[left] * incoming[neighbor] + outgoing[neighbor] * incoming[left]
                )
            else:
                value = gains[left][neighbor] - resolution * (
                    outgoing[right] * incoming[neighbor] + outgoing[neighbor] * incoming[right]
                )
            gains[right][neighbor] = gains[neighbor][right] = value
            set_pair(right, neighbor, value, neighbor in right_neighbors)
            set_pair(neighbor, right, value, neighbor in right_neighbors)

        for neighbor in list(gains[left]):
            del gains[neighbor][left]
            if neighbor != right:
                remove_pair(neighbor, left)
                remove_pair(left, neighbor)
        del gains[left]
        outgoing[right] += outgoing[left]
        outgoing[left] = 0
        if directed:
            incoming[right] += incoming[left]
            incoming[left] = 0

    return sorted(communities.values(), key=len, reverse=True)


def _greedy_modularity_communities_native(G, weight, resolution, cutoff, best_n):
    """networkx's greedy_modularity_communities, the merge loop native.

    br-r37-c1-epic-native-algorithms-1g0lj.3: networkx 3.6's body with its
    ``_greedy_modularity_communities_generator`` replaced by
    ``networkx_greedy_modularity_merges``. The generator's setup (``m``, ``q0``,
    the ``a``/``b`` degree dicts, the edge weights) is computed here from ``G``'s
    own API exactly as networkx computes it; node labels are ranked so the
    native heaps break equal gains as networkx's ``_HeapElement`` compares
    ``(u, v)`` label tuples; and the merges are replayed into networkx's
    ``communities`` dict, so even the frozensets are built the same way.

    ``None`` where that cannot hold: node labels not all ``int`` or all ``str``
    (other labels may not compare, or compare in ways ranks cannot carry),
    weights, resolution, cutoff or best_n that are not plain ints within 2**53
    or floats, or a NaN gain.
    """
    if not G.size():
        return [{n} for n in G]
    if cutoff < 1 or cutoff > G.number_of_nodes():
        raise ValueError(f"cutoff must be between 1 and {len(G)}. Got {cutoff}.")
    if best_n is not None:
        if best_n < 1 or best_n > G.number_of_nodes():
            raise ValueError(f"best_n must be between 1 and {len(G)}. Got {best_n}.")
        if best_n < cutoff:
            raise ValueError(f"Must have best_n >= cutoff. Got {best_n} < {cutoff}")
        if best_n == 1:
            return [set(G)]
    else:
        best_n = G.number_of_nodes()
    if any(_as_exact_float(value) is None for value in (resolution, cutoff, best_n)):
        return None

    nodes = list(G)
    label_type = type(nodes[0])
    if label_type not in (int, str) or any(type(node) is not label_type for node in nodes):
        return None
    order = sorted(nodes)
    rank = {node: position for position, node in enumerate(order)}
    sources, targets, weights = [], [], []
    for u, v, wt in G.edges(data=weight, default=1):
        if _as_exact_float(wt) is None:
            return None
        sources.append(rank[u])
        targets.append(rank[v])
        weights.append(float(wt))

    directed = G.is_directed()
    m = G.size(weight)
    q0 = 1 / m
    if directed:
        a = {node: deg_out * q0 for node, deg_out in G.out_degree(weight=weight)}
        b = {node: deg_in * q0 for node, deg_in in G.in_degree(weight=weight)}
    else:
        a = b = {node: deg * q0 * 0.5 for node, deg in G.degree(weight=weight)}
    a_ranked = [0.0] * len(order)
    for node, value in a.items():
        a_ranked[rank[node]] = value
    b_ranked = None
    if directed:
        b_ranked = [0.0] * len(order)
        for node, value in b.items():
            b_ranked[rank[node]] = value
    try:
        merges, exhausted = _native_greedy_modularity_merges(
            sources,
            targets,
            weights,
            a_ranked,
            b_ranked,
            q0,
            float(resolution),
            float(cutoff),
            float(best_n),
        )
    except ValueError:
        return None

    communities = {n: frozenset([n]) for n in nodes}
    for u, v in merges:
        u = order[u]
        v = order[v]
        communities[v] = frozenset(communities[u] | communities[v])
        del communities[u]
    communities = communities.values()
    if exhausted:
        communities = sorted(communities, key=len, reverse=True)
        while len(communities) > best_n:
            comm1, comm2, *rest = communities
            communities = [comm1 ^ comm2]
            communities.extend(rest)
        return communities
    return sorted(communities, key=len, reverse=True)


def _cnm_plain_networkx_storage(G):
    """Inspect dictionaries without executing customized weight providers."""
    storage = G.__dict__
    if type(storage.get("_node")) is not dict:
        return False
    if any(type(node) not in (int, str) for node in storage["_node"]):
        return False
    roots = [storage.get("_adj")]
    if "_pred" in storage:
        roots.append(storage["_pred"])
    multi = G.is_multigraph()
    for root in roots:
        if type(root) is not dict:
            return False
        for row in root.values():
            if type(row) is not dict:
                return False
            for data in row.values():
                if type(data) is not dict:
                    return False
                for attrs in data.values() if multi else (data,):
                    if type(attrs) is not dict or any(
                        type(key) not in (str, int, float, bool, bytes, type(None))
                        for key in attrs
                    ):
                        return False
    return True


def greedy_modularity_communities(
    G,
    weight=None,
    resolution=1,
    cutoff=1,
    best_n=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Find communities using Clauset-Newman-Moore greedy modularity.

    Ordinary primitive labels and numeric weights use the native merge
    kernel. The owned sparse merge engine handles other labels, numeric
    protocols, and graph views without converting or delegating the graph.
    """
    _fnx._validate_backend_dispatch_keywords(
        "greedy_modularity_communities", backend, backend_kwargs
    )
    import networkx as nx

    # Native admission inspects parameters and edge values. Graph subclasses
    # and assigned storage can make those inspections observable; run their
    # protocols once, directly through the owned engine.
    if (
        type(G) in (
            _fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph,
            nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph,
        )
        and not _fnx._has_networkx_private_storage(G)
        and "_graph" not in G.__dict__
        and not any(
            name in G.__dict__
            for name in ("size", "number_of_nodes", "is_directed", "is_multigraph")
        )
        and G.edge_attr_dict_factory is dict
        and (weight is None or type(weight) is str)
        and _as_exact_float(resolution) is not None
        and _as_exact_float(cutoff) is not None
        and (best_n is None or _as_exact_float(best_n) is not None)
        and (
            type(G) in (_fnx.Graph, _fnx.DiGraph, _fnx.MultiGraph, _fnx.MultiDiGraph)
            or _cnm_plain_networkx_storage(G)
        )
    ):
        result = _greedy_modularity_communities_native(
            G, weight, resolution, cutoff, best_n
        )
        if result is not None:
            return result
    return _greedy_modularity_communities_owned(
        G, weight, resolution, cutoff, best_n
    )


def _label_propagation_snapshot_allowed(G, rng):
    """Only snapshot graphs and random sources without observable overrides."""
    return (
        type(G) is _fnx.Graph
        and not _fnx._has_networkx_private_storage(G)
        and G.edge_attr_dict_factory is dict
        and type(rng) is _LABEL_PROPAGATION_RANDOM_CLASS
        and _random.Random is _LABEL_PROPAGATION_RANDOM_CLASS
        and all(
            getattr(_LABEL_PROPAGATION_RANDOM_CLASS, name) is method
            for name, method in _LABEL_PROPAGATION_RANDOM_PROTOCOL.items()
        )
        and not any(name in vars(rng) for name in _LABEL_PROPAGATION_RANDOM_PROTOCOL)
    )


def asyn_lpa_communities(G, weight=None, seed=None, *, backend=None, **backend_kwargs):
    """Communities via asynchronous label propagation.

    br-r37-c1-h4bad: the ``from networkx.algorithms.community import *``
    re-export ran nx's pure-Python LPA directly against the fnx Graph,
    rebuilding an adjacency view (``G[node]``) for every node on every
    round (~2.6x nx on a 400-node graph). nx's ``seed`` is already a real
    CPython ``random.Random`` (via ``py_random_state``), so the algorithm
    stays in Python and is byte-exact; the fix is two-fold:

    1. Snapshot the fnx adjacency ONCE via a single native crossing
       (``fnx_to_nx_adjacency``) instead of an ``O(rounds*V)`` view rebuild.
    2. Run the whole label-propagation loop in INDEX space (node -> 0..n-1):
       labels, the shuffle permutation, and the neighbour lists are all
       plain ints, so the hot inner loop never touches a Python node object
       or a dict-of-objects. This is byte-exact because Fisher-Yates
       ``shuffle`` draws depend only on ``len`` (not element values), nx's
       labels are themselves the same 0..n-1 ints, and the final
       ``groups`` mapping is rebuilt in node order.

    asyn_lpa supports directed graphs (unlike ``label_propagation_communities``).
    An ordinary simple undirected ``Graph`` uses the index snapshot, built
    when iteration starts. Other graphs and custom random sources retain
    live Python traversal so graph views, private mappings, and callbacks
    preserve their observable behavior.
    """
    _fnx._validate_backend_dispatch_keywords(
        "asyn_lpa_communities", backend, backend_kwargs
    )
    # NetworkX validates the seed at call time but reads the graph only when
    # iteration starts. Even native-route admission must wait: private stores
    # and edge weights can be replaced while the iterator is still suspended.
    rng = _fnx._create_py_random_state(seed)

    def _gen():
        yield from _asyn_lpa_communities(G, weight, rng)

    return _gen()


def _asyn_lpa_live(G, weight, rng):
    """Traverse caller rows when graph, numeric or random hooks are observable."""
    from collections import Counter as _Counter, defaultdict

    labels = {node: i for i, node in enumerate(G)}
    cont = True
    while cont:
        cont = False
        nodes = list(G)
        rng.shuffle(nodes)
        for node in nodes:
            if not G[node]:
                continue
            if weight is None:
                label_freq = _Counter(map(labels.get, G[node]))
            else:
                label_freq = defaultdict(float)
                for _, v, wt in G.edges(node, data=weight, default=1):
                    label_freq[labels[v]] += wt
            max_freq = max(label_freq.values())
            best_labels = [
                label for label, freq in label_freq.items() if freq == max_freq
            ]
            if labels[node] not in best_labels:
                labels[node] = rng.choice(best_labels)
                cont = True
    yield from _community_groups(labels).values()


def _asyn_lpa_communities(G, weight, rng):
    if (
        not _label_propagation_snapshot_allowed(G, rng)
        or (weight is not None and type(weight) is not str)
    ):
        # Custom selectors retain the public edge-view protocol, including
        # the special meanings of literal data=True and data=False.
        return _asyn_lpa_live(G, weight, rng)

    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}

    if weight is None:
        # Unweighted (the default): key-only native rows — ``_native_adjacency_keys``
        # is ~4x cheaper than the attr-bearing crossing (no per-edge attr dict
        # materialised). Build the index adjacency keyed by node index so row
        # order is irrelevant.
        _nak = getattr(G, "_native_adjacency_keys", None)
        adj = [None] * n
        if _nak is not None:
            for node, nbrs in _nak():
                adj[idx[node]] = [idx[v] for v in nbrs]
        else:  # defensive: native helper unavailable
            for u in node_list:
                adj[idx[u]] = [idx[v] for v in G._adj[u]]
    else:
        from franken_networkx.backend import (
            _native_fnx_to_nx_adjacency as _bulk_adjacency,
        )

        if _bulk_adjacency is not None:
            bulk = _bulk_adjacency(G)
            canon_to_idx = {canon: i for i, (canon, _nbrs) in enumerate(bulk)}
            adj = [
                [(canon_to_idx[nbr], attrs.get(weight, 1)) for nbr, attrs in nbrs]
                for _canon, nbrs in bulk
            ]
        else:  # defensive: native helper unavailable
            adj = [
                [(idx[v], dd.get(weight, 1)) for v, dd in G._adj[u].items()]
                for u in node_list
            ]
        if any(type(value) not in (int, float, bool) for row in adj for _, value in row):
            # A numeric callback can mutate weights that a later node reads.
            # Do not turn that live traversal into a value snapshot or coerce
            # types such as Decimal, Fraction and NumPy scalars to float64.
            return _asyn_lpa_live(G, weight, rng)

    unweighted = weight is None

    def _gen():
        labels = list(range(n))
        order = list(range(n))
        # Reusable arrays keyed by label (labels live in 0..n-1): avoid
        # nx's per-node Counter/defaultdict (hashing + an ABC instancecheck
        # per node per round — ~half the runtime in cProfile). ``freq`` is
        # zeroed only at the touched entries, so reuse is O(degree) not O(n).
        # ``touched`` preserves first-seen label order, matching Counter /
        # defaultdict insertion order exactly, so the best-label tie set and
        # thus every ``seed.choice`` draw is byte-identical to nx.
        zero = 0 if unweighted else 0.0
        freq = [zero] * n
        visited = [0] * n if not unweighted else None
        visit = 0
        cont = True
        while cont:
            cont = False
            perm = order[:]
            rng.shuffle(perm)
            for node in perm:
                nbrs = adj[node]
                if not nbrs:
                    continue
                touched = []
                if unweighted:
                    for v in nbrs:
                        lab = labels[v]
                        if freq[lab] == 0:
                            touched.append(lab)
                        freq[lab] += 1
                else:
                    visit += 1
                    for v, wt in nbrs:
                        lab = labels[v]
                        # Zero is a valid sum, including after cancellation.
                        # Re-adding an already seen label biases choice() by
                        # duplicating that label in the tied candidates.
                        if visited[lab] != visit:
                            visited[lab] = visit
                            touched.append(lab)
                        freq[lab] += wt
                max_freq = freq[touched[0]]
                for lab in touched:
                    if freq[lab] > max_freq:
                        max_freq = freq[lab]
                cur = labels[node]
                best_labels = [lab for lab in touched if freq[lab] == max_freq]
                for lab in touched:
                    freq[lab] = zero
                if cur not in best_labels:
                    labels[node] = rng.choice(best_labels)
                    cont = True
        # Rebuild node-keyed labels in node order so _community_groups() yields the
        # exact communities (sets of node objects) nx would.
        label_by_node = {node_list[i]: labels[i] for i in range(n)}
        yield from _community_groups(label_by_node).values()

    return _gen()


def fast_label_propagation_communities(
    G, *, weight=None, seed=None, backend=None, **backend_kwargs
):
    """Communities via fast label propagation (Traag & Šubelj 2023)."""
    _fnx._validate_backend_dispatch_keywords(
        "fast_label_propagation_communities", backend, backend_kwargs
    )
    rng = _fnx._create_py_random_state(seed)

    def _gen():
        yield from _fast_label_propagation_communities(G, weight, rng)

    return _gen()


def _fast_label_propagation_communities(G, weight, rng):
    from collections import deque

    if (
        not _label_propagation_snapshot_allowed(G, rng)
        or weight is not None
        or getattr(G, "_native_adjacency_keys", None) is None
    ):
        from collections import Counter as _Counter, defaultdict

        rng_fb = rng

        def _fast_label_count(comms, node):
            if weight is None:
                if not G.is_multigraph():
                    return _Counter(map(comms.get, _fnx.all_neighbors(G, node)))
                label_freqs = defaultdict(int)
                for nbr in G[node]:
                    label_freqs[comms[nbr]] += len(G[node][nbr])
                if G.is_directed():
                    for nbr in G.pred[node]:
                        label_freqs[comms[nbr]] += len(G.pred[node][nbr])
                return label_freqs
            label_freqs = defaultdict(float)
            for _, nbr, w in G.edges(node, data=weight, default=1):
                label_freqs[comms[nbr]] += w
            if G.is_directed():
                for nbr, _, w in G.in_edges(node, data=weight, default=1):
                    label_freqs[comms[nbr]] += w
            return label_freqs

        def _fallback_gen():
            nodes_queue = deque(G)
            rng_fb.shuffle(nodes_queue)
            nodes_set = set(G)
            comms = {node: i for i, node in enumerate(G)}
            while nodes_queue:
                node = nodes_queue.popleft()
                nodes_set.remove(node)
                if G.degree(node) > 0:
                    label_freqs = _fast_label_count(comms, node)
                    max_freq = max(label_freqs.values())
                    comm = rng_fb.choice(
                        [c for c in label_freqs if label_freqs[c] == max_freq]
                    )
                    if comms[node] != comm:
                        comms[node] = comm
                        for nbr in _fnx.all_neighbors(G, node):
                            if comms[nbr] != comm and nbr not in nodes_set:
                                nodes_queue.append(nbr)
                                nodes_set.add(nbr)
            yield from _community_groups(comms).values()

        return _fallback_gen()

    node_list = list(G)
    n = len(node_list)
    idx = {u: i for i, u in enumerate(node_list)}
    adj = [None] * n
    for node, nbrs in G._native_adjacency_keys():
        adj[idx[node]] = [idx[v] for v in nbrs]

    def _gen():
        comms = list(range(n))
        perm = list(range(n))
        rng.shuffle(perm)  # O(n); identical permutation to nx's deque shuffle
        queue = deque(perm)
        in_queue = [True] * n  # bool array mirrors nx's nodes_set membership
        freq = [0] * n
        while queue:
            node = queue.popleft()
            in_queue[node] = False
            nbrs = adj[node]
            if not nbrs:
                continue
            touched = []
            for v in nbrs:
                lab = comms[v]
                if freq[lab] == 0:
                    touched.append(lab)
                freq[lab] += 1
            max_freq = freq[touched[0]]
            for lab in touched:
                if freq[lab] > max_freq:
                    max_freq = freq[lab]
            best_labels = [lab for lab in touched if freq[lab] == max_freq]
            for lab in touched:
                freq[lab] = 0
            comm = rng.choice(best_labels)
            if comms[node] != comm:
                comms[node] = comm
                for v in nbrs:
                    if comms[v] != comm and not in_queue[v]:
                        queue.append(v)
                        in_queue[v] = True
        label_by_node = {node_list[i]: comms[i] for i in range(n)}
        yield from _community_groups(label_by_node).values()

    return _gen()


def k_clique_communities(G, k, cliques=None, *, backend=None, **backend_kwargs):
    """Find k-clique communities via the clique-percolation method."""
    _fnx._validate_backend_dispatch_keywords(
        "k_clique_communities", backend, backend_kwargs
    )

    from collections import defaultdict
    from itertools import count

    def _gen():
        if k < 2:
            raise _fnx.NetworkXError(f"k={k}, k must be greater than 1.")
        nonlocal cliques
        if cliques is None:
            # find_cliques performs graph conversion here, when iteration
            # starts. Converting at call time snapshots views and NetworkX
            # inputs before the caller's pending graph edits can take effect.
            unique = [frozenset(c) for c in _fnx.find_cliques(G) if len(c) >= k]
        else:
            unique = list(dict.fromkeys(frozenset(c) for c in cliques if len(c) >= k))
        if not unique:
            return
        # Counts are integral, so the ordinary float threshold has the same
        # effect as its ceiling. Keep the original comparison above first:
        # inf and NaN select no cliques and must not reach ceil(). Exact type
        # admission avoids invoking custom numeric conversion callbacks.
        native_k = _math.ceil(k) if type(k) is float else k
        node_id = defaultdict(count().__next__).__getitem__
        clique_nodes = [[node_id(u) for u in c] for c in unique]
        clique_hashes = [hash(c) for c in unique]
        for comp in _fnx._fnx.k_clique_percolation_components(clique_nodes, clique_hashes, native_k):
            yield frozenset.union(*(unique[i] for i in comp))

    return _gen()


def _without_most_central_edges(G, most_valuable_edge):
    original_num_components = _fnx.number_connected_components(G)
    num_new_components = original_num_components
    while num_new_components <= original_num_components:
        edge = most_valuable_edge(G)
        G.remove_edge(*edge)
        new_components = tuple(_fnx.connected_components(G))
        num_new_components = len(new_components)
    return new_components


def girvan_newman(G, most_valuable_edge=None, *, backend=None, **backend_kwargs):
    """Finds communities in a graph using the Girvan–Newman method."""
    _fnx._validate_backend_dispatch_keywords("girvan_newman", backend, backend_kwargs)
    def _gen():
        nonlocal most_valuable_edge
        if G.number_of_edges() == 0:
            yield tuple(_fnx.connected_components(G))
            return
        if most_valuable_edge is None:

            def most_valuable_edge(g):
                betweenness = _fnx.edge_betweenness_centrality(g)
                return max(betweenness, key=betweenness.get)

        # Copy the live caller graph at the first resume. Pre-converting a
        # NetworkX graph or view both freezes its state too early and loses
        # its copy hooks and the working-graph type a custom callback sees.
        g = G.copy().to_undirected()
        g.remove_edges_from(list(_fnx.selfloop_edges(g)))
        while g.number_of_edges() > 0:
            yield _without_most_central_edges(g, most_valuable_edge)

    return _gen()


def asyn_fluidc(G, k, max_iter=100, seed=None, *, backend=None, **backend_kwargs):
    """Returns communities in `G` as detected by Fluid Communities algorithm."""
    _fnx._validate_backend_dispatch_keywords("asyn_fluidc", backend, backend_kwargs)
    from collections import Counter

    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    rng = _fnx._generator_random_state(seed)
    if not isinstance(k, int):
        raise _fnx.NetworkXError("k must be an integer.")
    if not k > 0:
        raise _fnx.NetworkXError("k must be greater than 0.")
    if not _fnx.is_connected(G):
        raise _fnx.NetworkXError("Fluid Communities require connected Graphs.")
    if len(G) < k:
        raise _fnx.NetworkXError("k cannot be bigger than the number of nodes.")
    if max_iter <= 0:
        raise ValueError(f"{max_iter=} must be greater than 0")

    max_density = 1.0
    vertices = list(G)
    rng.shuffle(vertices)
    communities = {n: i for i, n in enumerate(vertices[:k])}
    density = {}
    com_to_numvertices = {}
    for vertex in communities:
        com_to_numvertices[communities[vertex]] = 1
        density[communities[vertex]] = max_density

    iter_count = 0
    cont = True
    while cont and iter_count < max_iter:
        cont = False
        iter_count += 1
        vertices = list(G)
        rng.shuffle(vertices)
        for vertex in vertices:
            com_counter = Counter()
            try:
                com_counter.update({communities[vertex]: density[communities[vertex]]})
            except KeyError:
                pass
            for v in G[vertex]:
                try:
                    com_counter.update({communities[v]: density[communities[v]]})
                except KeyError:
                    continue
            new_com = -1
            if len(com_counter.keys()) > 0:
                max_freq = max(com_counter.values())
                best_communities = [
                    com
                    for com, freq in com_counter.items()
                    if (max_freq - freq) < 0.0001
                ]
                try:
                    if communities[vertex] in best_communities:
                        new_com = communities[vertex]
                except KeyError:
                    pass
                if new_com == -1:
                    cont = True
                    new_com = rng.choice(best_communities)
                    try:
                        com_to_numvertices[communities[vertex]] -= 1
                        density[communities[vertex]] = (
                            max_density / com_to_numvertices[communities[vertex]]
                        )
                    except KeyError:
                        pass
                    communities[vertex] = new_com
                    com_to_numvertices[communities[vertex]] += 1
                    density[communities[vertex]] = (
                        max_density / com_to_numvertices[communities[vertex]]
                    )
    return iter(_community_groups(communities).values())


def edge_betweenness_partition(
    G, number_of_sets, *, weight=None, backend=None, **backend_kwargs
):
    """Partition created by iteratively removing the highest edge betweenness edge."""
    _fnx._validate_backend_dispatch_keywords(
        "edge_betweenness_partition", backend, backend_kwargs
    )
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if number_of_sets <= 0:
        raise _fnx.NetworkXError("number_of_sets must be >0")
    if number_of_sets == 1:
        return [set(G)]
    if number_of_sets == len(G):
        return [{n} for n in G]
    if number_of_sets > len(G):
        raise _fnx.NetworkXError("number_of_sets must be <= len(G)")

    H = G.copy()
    partition = list(_fnx.connected_components(H))
    while len(partition) < number_of_sets:
        ranking = _fnx.edge_betweenness_centrality(H, weight=weight)
        edge = max(ranking, key=ranking.get)
        H.remove_edge(*edge)
        partition = list(_fnx.connected_components(H))
    return partition


def edge_current_flow_betweenness_partition(
    G, number_of_sets, *, weight=None, backend=None, **backend_kwargs
):
    """Partition created by removing the highest edge current flow betweenness edge."""
    _fnx._validate_backend_dispatch_keywords(
        "edge_current_flow_betweenness_partition", backend, backend_kwargs
    )
    import functools as _functools

    G = _fnx._coerce_arg_to_fnx_graph(G)
    if number_of_sets <= 0:
        raise _fnx.NetworkXError("number_of_sets must be >0")
    elif number_of_sets == 1:
        return [set(G)]
    elif number_of_sets == len(G):
        return [{n} for n in G]
    elif number_of_sets > len(G):
        raise _fnx.NetworkXError("number_of_sets must be <= len(G)")

    rank = _functools.partial(
        _fnx.edge_current_flow_betweenness_centrality,
        normalized=False,
        weight=weight,
    )
    H = G.copy()
    partition = list(_fnx.connected_components(H))
    if len(partition) > 1:
        Hcc_subgraphs = [H.subgraph(cc).copy() for cc in partition]
    else:
        Hcc_subgraphs = [H]

    ranking = {}
    for Hcc in Hcc_subgraphs:
        ranking.update(rank(Hcc))

    while len(partition) < number_of_sets:
        edge = max(ranking, key=ranking.get)
        for cc, Hcc in zip(partition, Hcc_subgraphs):
            if edge[0] in cc:
                Hcc.remove_edge(*edge)
                del ranking[edge]
                splitcc_list = list(_fnx.connected_components(Hcc))
                if len(splitcc_list) > 1:
                    cc_new = min(splitcc_list, key=len)
                    Hcc_new = Hcc.subgraph(cc_new).copy()
                    newranks = rank(Hcc_new)
                    for e, r in newranks.items():
                        ranking[e if e in ranking else e[::-1]] = r
                    partition.append(cc_new)
                    Hcc_subgraphs.append(Hcc_new)
                    Hcc.remove_nodes_from(cc_new)
                    cc.difference_update(cc_new)
                newranks = rank(Hcc)
                for e, r in newranks.items():
                    ranking[e if e in ranking else e[::-1]] = r
                break
    return partition


def _calculate_local_modularity_for_candidate(G, v, C, B, T, I):
    C_tmp = C | {v}
    B_tmp = B.copy()
    T_tmp = T.copy()
    I_tmp = I.copy()
    removed_B_nodes = set()

    for nbr in G[v]:
        if nbr not in C_tmp:
            B_tmp.add(v)
            T_tmp.add(frozenset([v, nbr]))
        if nbr in B:
            nbr_still_in_B = any(nbr_nbr not in C_tmp for nbr_nbr in G[nbr])
            if not nbr_still_in_B:
                B_tmp.remove(nbr)
                removed_B_nodes.add(nbr)
        if nbr in C_tmp:
            I_tmp.add(frozenset([v, nbr]))

    for removed_node in removed_B_nodes:
        for removed_node_nbr in G[removed_node]:
            if removed_node_nbr not in B_tmp:
                T_tmp.discard(frozenset([removed_node_nbr, removed_node]))
                I_tmp.discard(frozenset([removed_node_nbr, removed_node]))

    R_tmp = len(I_tmp) / len(T_tmp) if len(T_tmp) > 0 else 1
    return R_tmp, B_tmp, T_tmp, I_tmp


def _clauset_greedy_source_expansion(G, *, source, cutoff=None):
    if cutoff is None:
        cutoff = float("inf")
    C = {source}
    B = {source}
    U = set(G[source].keys()) - C
    T = {frozenset([node, nbr]) for node in B for nbr in G.neighbors(node)}
    I = {edge for edge in T if all(node in C for node in edge)}

    R_value = 0
    while len(C) < cutoff:
        if not U:
            break
        max_R = 0
        best_node = None
        best_node_B = best_node_T = best_node_I = set()

        for v in U:
            R_tmp, B_tmp, T_tmp, I_tmp = _calculate_local_modularity_for_candidate(
                G, v, C, B, T, I
            )
            if R_tmp > max_R:
                max_R = R_tmp
                best_node = v
                best_node_B = B_tmp
                best_node_T = T_tmp
                best_node_I = I_tmp

        C = C | {best_node}
        U.update(set(G[best_node].keys()) - C)
        U.remove(best_node)
        B = best_node_B
        T = best_node_T
        I = best_node_I
        if max_R < R_value:
            break
        R_value = max_R

    return C


def greedy_source_expansion(G, *, source, cutoff=None, method="clauset"):
    """Find the local community around a source node."""
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if method != "clauset":
        raise ValueError(f"{method} is not a valid choice for an algorithm.")
    return _clauset_greedy_source_expansion(G, source=source, cutoff=cutoff)


def lukes_partitioning(
    G, max_size, node_weight=None, edge_weight=None, *, backend=None, **backend_kwargs
):
    """Optimal partitioning of a weighted tree using the Lukes algorithm."""
    _fnx._validate_backend_dispatch_keywords(
        "lukes_partitioning", backend, backend_kwargs
    )
    from copy import deepcopy
    from functools import lru_cache
    from random import choice

    G = _fnx._coerce_arg_to_fnx_graph(G)
    if not _fnx.is_tree(G):
        raise _fnx.NotATree("lukes_partitioning works only on trees")
    if G.is_directed():
        root = [n for n, d in G.in_degree() if d == 0]
        assert len(root) == 1
        root = root[0]
        t_G = deepcopy(G)
    else:
        root = choice(list(G.nodes))
        t_G = _fnx.dfs_tree(G, root)

    if edge_weight is None or node_weight is None:
        safe_G = deepcopy(G)
        if edge_weight is None:
            _fnx.set_edge_attributes(safe_G, 1.0, "weight")
            edge_weight = "weight"
        if node_weight is None:
            _fnx.set_node_attributes(safe_G, 1, "weight")
            node_weight = "weight"
    else:
        safe_G = G

    all_n_attr = _fnx.get_node_attributes(safe_G, node_weight).values()
    for x in all_n_attr:
        if not isinstance(x, int):
            raise TypeError(
                "lukes_partitioning needs integer "
                f"values for node_weight ({node_weight})"
            )

    def _leaves(gr):
        for x in gr.nodes:
            if not _fnx.descendants(gr, x):
                yield x

    def _a_parent_of_leaves_only(gr):
        tleaves = set(_leaves(gr))
        for n in set(gr.nodes) - tleaves:
            if all(x in tleaves for x in _fnx.descendants(gr, n)):
                return n

    @lru_cache(2048)
    def _value_of_cluster(cluster):
        valid_edges = [e for e in safe_G.edges if e[0] in cluster and e[1] in cluster]
        return sum(safe_G.edges[e][edge_weight] for e in valid_edges)

    def _value_of_partition(partition):
        return sum(_value_of_cluster(frozenset(c)) for c in partition)

    @lru_cache(2048)
    def _weight_of_cluster(cluster):
        return sum(safe_G.nodes[n][node_weight] for n in cluster)

    def _pivot(partition, node):
        ccx = [c for c in partition if node in c]
        assert len(ccx) == 1
        return ccx[0]

    def _concatenate_or_merge(partition_1, partition_2, x, i, ref_weight):
        ccx = _pivot(partition_1, x)
        cci = _pivot(partition_2, i)
        merged_xi = ccx.union(cci)
        if _weight_of_cluster(frozenset(merged_xi)) <= ref_weight:
            cp1 = [c for c in partition_1 if c != ccx]
            cp2 = [c for c in partition_2 if c != cci]
            option_2 = [merged_xi] + cp1 + cp2
            return option_2, _value_of_partition(option_2)
        option_1 = partition_1 + partition_2
        return option_1, _value_of_partition(option_1)

    leaves = set(_leaves(t_G))
    for lv in leaves:
        t_G.nodes[lv]["partitions"] = {}
        slot = safe_G.nodes[lv][node_weight]
        t_G.nodes[lv]["partitions"][slot] = [{lv}]
        t_G.nodes[lv]["partitions"][0] = [{lv}]

    for inner in [x for x in t_G.nodes if x not in leaves]:
        t_G.nodes[inner]["partitions"] = {}
        slot = safe_G.nodes[inner][node_weight]
        t_G.nodes[inner]["partitions"][slot] = [{inner}]

    while True:
        x_node = _a_parent_of_leaves_only(t_G)
        weight_of_x = safe_G.nodes[x_node][node_weight]
        best_value = 0
        best_partition = None
        bp_buffer = {}
        x_descendants = _fnx.descendants(t_G, x_node)
        for i_node in x_descendants:
            for j in range(weight_of_x, max_size + 1):
                for p1 in range(weight_of_x, j + 1):
                    a, b = p1, j - p1
                    if (
                        a not in t_G.nodes[x_node]["partitions"]
                        or b not in t_G.nodes[i_node]["partitions"]
                    ):
                        continue
                    part1 = t_G.nodes[x_node]["partitions"][a]
                    part2 = t_G.nodes[i_node]["partitions"][b]
                    part, value = _concatenate_or_merge(part1, part2, x_node, i_node, j)
                    if j not in bp_buffer or bp_buffer[j][1] < value:
                        bp_buffer[j] = part, value
                    if best_value <= value:
                        best_value = value
                        best_partition = part
            for w, (best_part_for_vl, _vl) in bp_buffer.items():
                t_G.nodes[x_node]["partitions"][w] = best_part_for_vl
            bp_buffer.clear()

        t_G.nodes[x_node]["partitions"][0] = best_partition
        t_G.remove_nodes_from(x_descendants)
        if x_node == root:
            return t_G.nodes[root]["partitions"][0]


def naive_greedy_modularity_communities(
    G, resolution=1, weight=None, *, backend=None, **backend_kwargs
):
    """Find communities in G using greedy modularity maximization."""
    _fnx._validate_backend_dispatch_keywords(
        "naive_greedy_modularity_communities", backend, backend_kwargs
    )
    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    communities = [frozenset([u]) for u in G.nodes()]
    merges = []
    old_modularity = None
    new_modularity = modularity(G, communities, resolution=resolution, weight=weight)
    while old_modularity is None or new_modularity > old_modularity:
        old_modularity = new_modularity
        trial_communities = list(communities)
        to_merge = None
        for i, u in enumerate(communities):
            for j, v in enumerate(communities):
                if j <= i or len(u) == 0 or len(v) == 0:
                    continue
                trial_communities[j] = u | v
                trial_communities[i] = frozenset([])
                trial_modularity = modularity(
                    G, trial_communities, resolution=resolution, weight=weight
                )
                if trial_modularity >= new_modularity:
                    if trial_modularity > new_modularity:
                        new_modularity = trial_modularity
                        to_merge = (i, j, new_modularity - old_modularity)
                    elif to_merge and min(i, j) < min(to_merge[0], to_merge[1]):
                        new_modularity = trial_modularity
                        to_merge = (i, j, new_modularity - old_modularity)
                trial_communities[i] = u
                trial_communities[j] = v
        if to_merge is not None:
            merges.append(to_merge)
            i, j, _dq = to_merge
            u, v = communities[i], communities[j]
            communities[j] = u | v
            communities[i] = frozenset([])
    return sorted((c for c in communities if len(c) > 0), key=len, reverse=True)


def spectral_modularity_bipartition(G):
    """Return a bipartition of the nodes based on the modularity matrix spectrum."""
    import numpy as np

    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    B = _fnx.modularity_matrix(G)
    eigenvalues, eigenvectors = np.linalg.eig(B)
    index = np.argsort(eigenvalues)[-1]
    v2 = zip(np.real(eigenvectors[:, index]), G)
    left, right = set(), set()
    for u, n in v2:
        if u < 0:
            left.add(n)
        else:
            right.add(n)
    return left, right


def greedy_node_swap_bipartition(G, *, init_split=None, max_iter=10):
    """Split the nodes into two communities based on greedy modularity maximization."""
    from copy import deepcopy
    import random as _random

    G = _fnx._coerce_arg_to_fnx_graph(G)
    if G.is_multigraph():
        raise _fnx.NetworkXNotImplemented("not implemented for multigraph type")
    if init_split is None:
        m1 = len(G) // 2
        some_nodes = set(_random.sample(list(G), m1))
        other_nodes = {n for n in G if n not in some_nodes}
        best_split_so_far = (some_nodes, other_nodes)
    else:
        if not is_partition(G, init_split):
            raise _fnx.NetworkXError("init_split is not a partition of G")
        if len(init_split) != 2:
            raise _fnx.NetworkXError("init_split must be a bipartition")
        best_split_so_far = deepcopy(init_split)

    best_mod = modularity(G, best_split_so_far)
    max_split, max_mod = best_split_so_far, best_mod
    its = 0
    m = G.number_of_edges()
    G_degree = dict(G.degree)

    while max_mod >= best_mod and its < max_iter:
        best_split_so_far = max_split
        best_mod = max_mod
        next_split = deepcopy(max_split)
        next_mod = max_mod
        nodes = set(G)
        while nodes:
            max_swap = -1
            max_node = None
            max_node_comm = None
            non_max_node_comm = None
            left, right = next_split
            leftd = sum(G_degree[n] for n in left)
            rightd = sum(G_degree[n] for n in right)
            for n in nodes:
                if n in left:
                    in_comm, out_comm = left, right
                    in_deg, out_deg = leftd, rightd
                else:
                    in_comm, out_comm = right, left
                    in_deg, out_deg = rightd, leftd

                nbrs = set(G[n].keys())
                d_eii = -len(nbrs & in_comm) / m
                d_ejj = len(nbrs & out_comm) / m
                deg = G_degree[n]
                d_sum_ai = (deg / (2 * m**2)) * (in_deg - out_deg - deg)
                swap_change = d_eii + d_ejj + d_sum_ai

                if swap_change > max_swap:
                    max_swap = swap_change
                    max_node = n
                    max_node_comm = in_comm
                    non_max_node_comm = out_comm
            max_node_comm.remove(max_node)
            non_max_node_comm.add(max_node)
            next_mod += max_swap
            if next_mod > max_mod:
                max_split, max_mod = deepcopy(next_split), next_mod
            nodes.remove(max_node)
        its += 1
    return best_split_so_far


def leiden_communities(
    G,
    weight="weight",
    resolution=1,
    max_level=None,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Find a best partition of `G` using Leiden Community Detection (backend required)."""
    _fnx._validate_backend_dispatch_keywords(
        "leiden_communities", backend, backend_kwargs
    )
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    _fnx._generator_random_state(seed)
    raise NotImplementedError(
        "'leiden_communities' is not implemented by networkx. "
        "Please try a different backend."
    )


def leiden_partitions(
    G,
    weight="weight",
    resolution=1,
    seed=None,
    *,
    backend=None,
    **backend_kwargs,
):
    """Yield partitions for each level of Leiden Community Detection (backend required)."""
    _fnx._validate_backend_dispatch_keywords(
        "leiden_partitions", backend, backend_kwargs
    )
    if G.is_directed():
        raise _fnx.NetworkXNotImplemented("not implemented for directed type")
    _fnx._generator_random_state(seed)
    raise NotImplementedError(
        "'leiden_partitions' is not implemented by networkx. "
        "Please try a different backend."
    )


_UPSTREAM_PUBLIC = getattr(
    _nx_community,
    "__all__",
    tuple(name for name in dir(_nx_community) if not name.startswith("_")),
)
__all__ = sorted(
    set(_UPSTREAM_PUBLIC)
    | {
        "label_propagation_communities",
        "louvain_communities",
        "asyn_lpa_communities",
        "fast_label_propagation_communities",
        "greedy_modularity_communities",
        "k_clique_communities",
    }
)


def __getattr__(name):  # pragma: no cover — defensive passthrough
    try:
        return getattr(_nx_community, name)
    except AttributeError as exc:
        raise AttributeError(
            f"module 'franken_networkx.community' has no attribute {name!r}"
        ) from exc


def is_partition(G, communities, *, backend=None, **backend_kwargs):
    """Return True iff ``communities`` is a partition of the nodes of ``G``.

    br-r37-c1-commpart: re-exported from networkx as ``@nx._dispatchable``, so
    ``fnx.community.is_partition(fnx_graph, ...)`` round-tripped the WHOLE graph
    through ``_fnx_to_nx`` (full O(V+E) conversion) for an O(V) membership check
    — ~52x slower than nx. networkx's exact predicate run in-process (uses only
    ``len(G)`` and ``n in G``, no nx helpers) — byte-identical.
    """
    _fnx._validate_backend_dispatch_keywords("is_partition", backend, backend_kwargs)
    if not isinstance(communities, list):
        communities = list(communities)
    # Snapshot the node set ONCE so per-element membership is a pure-Python set
    # lookup rather than a PyO3 ``n in G`` crossing for every node in every block.
    gnodes = set(G)
    nodes = {n for c in communities for n in c if n in gnodes}
    return len(gnodes) == len(nodes) == sum(len(c) for c in communities)


def partition_quality(G, partition, *, backend=None, **backend_kwargs):
    """Return ``(coverage, performance)`` of ``partition`` of ``G``.

    br-r37-c1-commpart: same ``@nx._dispatchable`` conversion tax as
    :func:`is_partition` (~14x slower). networkx's exact O(C^2 + L) algorithm run
    in-process — byte-identical, including the exact ``NetworkXError`` message
    networkx's ``@require_partition`` raises on an invalid partition and the
    multigraph ``performance == -1.0`` contract.
    """
    _fnx._validate_backend_dispatch_keywords(
        "partition_quality", backend, backend_kwargs
    )
    from itertools import combinations as _combinations

    if not is_partition(G, partition):
        raise _fnx.NetworkXError(
            "`partition` is not a valid partition of the nodes of G"
        )

    node_community = {}
    for i, community in enumerate(partition):
        for node in community:
            node_community[node] = i

    if not G.is_multigraph():
        possible_inter_community_edges = sum(
            len(p1) * len(p2) for p1, p2 in _combinations(partition, 2)
        )
        if G.is_directed():
            possible_inter_community_edges *= 2
    else:
        possible_inter_community_edges = 0

    n = len(G)
    total_pairs = n * (n - 1)
    if not G.is_directed():
        total_pairs //= 2

    intra_community_edges = 0
    inter_community_non_edges = possible_inter_community_edges
    for e in G.edges():
        if node_community[e[0]] == node_community[e[1]]:
            intra_community_edges += 1
        else:
            inter_community_non_edges -= 1

    coverage = intra_community_edges / len(G.edges)
    if G.is_multigraph():
        performance = -1.0
    else:
        performance = (intra_community_edges + inter_community_non_edges) / total_pairs
    return coverage, performance


def __dir__():
    return sorted(set(__all__) | set(name for name in globals() if not name.startswith("_")))
