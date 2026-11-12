"""Capacity-scaling minimum-cost flow over an indexed residual network.

The public behavior is specified in EXISTING_NETWORKX_STRUCTURE.md, section
23.2. Residual arcs are paired array entries, so cancellation is an XOR and
the hot loops never construct graph objects or repeatedly cross native views.
Neighbor and parallel-arc order are retained for equal-cost path selection.
"""

from math import log

from networkx.exception import NetworkXNotImplemented, NetworkXUnbounded, NetworkXUnfeasible


_UNBOUNDED = (
    "Negative cost cycle of infinite capacity found. "
    "Min cost flow may be unbounded below."
)


def _selfloop_data(graph):
    multi = graph.is_multigraph()
    for node, row in graph._adj.items():
        if node in row:
            if multi:
                yield from row[node].values()
            else:
                yield row[node]


class _Residual:
    __slots__ = (
        "nodes", "index", "excess", "potential", "adj", "capacity",
        "weight", "flow", "key", "infinity",
    )

    def __init__(self, graph, demand, capacity, weight):
        if not graph.is_directed():
            raise NetworkXNotImplemented("not implemented for undirected type")
        if sum(graph.nodes[node].get(demand, 0) for node in graph) != 0:
            raise NetworkXUnfeasible("Sum of the demands should be 0.")
        # Demand providers run on two live node traversals. Snapshotting the
        # labels first hides mutations and changes the iteration error boundary.
        node_excess = [(node, -graph.nodes[node].get(demand, 0)) for node in graph]
        self.nodes = [node for node, _ in node_excess]
        self.index = {node: index for index, node in enumerate(self.nodes)}
        self.excess = [excess for _, excess in node_excess]
        self.potential = [0] * len(self.nodes)
        self.adj = [{} for _ in self.nodes]
        self.capacity, self.weight, self.flow, self.key = [], [], [], []

        infinity = float("inf")
        for data in _selfloop_data(graph):
            if data.get(weight, 0) < 0 and data.get(capacity, infinity) == infinity:
                raise NetworkXUnbounded(_UNBOUNDED)
        if graph.is_multigraph():
            edges = graph.edges(keys=True, data=True)
        else:
            edges = ((u, v, 0, data) for u, v, data in graph.edges(data=True))
        edges = [
            (u, v, key, data)
            for u, v, key, data in edges
            if u != v and data.get(capacity, infinity) > 0
        ]
        self.infinity = max(
            sum(abs(value) for value in self.excess),
            2 * sum(
                data[capacity] for _, _, _, data in edges
                if capacity in data and data[capacity] != infinity
            ),
        ) or 1
        for u, v, key, data in edges:
            source, target = self.index[u], self.index[v]
            arc = len(self.flow)
            self.adj[source].setdefault(target, []).append(arc)
            self.adj[target].setdefault(source, []).append(arc + 1)
            # Capacity reads/comparisons may update the live cost provider.
            bound = min(data.get(capacity, self.infinity), self.infinity)
            value = data.get(weight, 0)
            self.capacity.extend((bound, 0))
            self.weight.extend((value, -value))
            self.flow.extend((0, 0))
            self.key.extend((key, key))
        self._check_unbounded()

    def _check_unbounded(self):
        """Prove negative cycles inside infinite-capacity SCCs only.

        Acyclic infinite-capacity chains need no weight relaxation. Restricting
        the proof to SCCs also keeps disconnected nodes out of its iteration
        bound. The shared queue-based Bellman-Ford primitive retains the
        predecessor-cycle checks needed before floating-point distances
        overflow. Flow arithmetic retains the caller's numeric types.
        """
        edges = []
        infinity = float("inf")
        neighbors = [[] for _ in self.nodes]
        reverse = [[] for _ in self.nodes]
        for source, row in enumerate(self.adj):
            for target, arcs in row.items():
                best = infinity
                for arc in arcs:
                    if self.capacity[arc] == self.infinity:
                        best = min(best, self.weight[arc])
                if best != infinity:
                    edges.append((source, target, best))
                    neighbors[source].append(target)
                    reverse[target].append(source)
        if not any(value < 0 for _, _, value in edges):
            return

        # Iterative Kosaraju avoids recursion limits on long supply networks.
        visited, finish = set(), []
        for root in range(len(self.nodes)):
            if root in visited:
                continue
            visited.add(root)
            stack = [(root, iter(neighbors[root]))]
            while stack:
                node, successors = stack[-1]
                child = next(successors, None)
                if child is None:
                    finish.append(node)
                    stack.pop()
                elif child not in visited:
                    visited.add(child)
                    stack.append((child, iter(neighbors[child])))
        component = [-1] * len(self.nodes)
        groups = []
        for root in reversed(finish):
            if component[root] != -1:
                continue
            group = []
            component[root] = len(groups)
            pending = [root]
            while pending:
                node = pending.pop()
                group.append(node)
                for predecessor in reverse[node]:
                    if component[predecessor] == -1:
                        component[predecessor] = len(groups)
                        pending.append(predecessor)
            groups.append(group)
        group_edges = [[] for _ in groups]
        for source, target, value in edges:
            if component[source] == component[target]:
                group_edges[component[source]].append((source, target, value))
        for nodes, arcs in zip(groups, group_edges):
            if not any(value < 0 for _, _, value in arcs):
                continue
            if any(value == -infinity for _, _, value in arcs):
                raise NetworkXUnbounded(_UNBOUNDED)
            if _negative_cycle(nodes, arcs):
                raise NetworkXUnbounded(_UNBOUNDED)

    def _augment(self, source, target, arc, amount):
        self.flow[arc] += amount
        self.flow[arc ^ 1] -= amount
        self.excess[source] -= amount
        self.excess[target] += amount

    def _saturate(self, delta):
        capacity, flow, weight = self.capacity, self.flow, self.weight
        potential = self.potential
        for source, row in enumerate(self.adj):
            source_potential = potential[source]
            for target, arcs in row.items():
                for arc in arcs:
                    if weight[arc] - source_potential + potential[target] < 0:
                        amount = capacity[arc] - flow[arc]
                        if amount >= delta:
                            self._augment(source, target, arc, amount)

    def _shortest_augmenting_path(self, source, deficits, delta, heap):
        capacity, flow, weight = self.capacity, self.flow, self.weight
        potential, nodes, index = self.potential, self.nodes, self.index
        queue = heap()
        insert = queue.insert
        getattr(queue, "get")  # Resolve the public heap protocol before insertion.
        insert(nodes[source], 0)
        settled, previous = {}, {}
        infinity = float("inf")
        while queue:
            label, distance = queue.pop()
            node = index[label]
            settled[node] = distance
            if label in deficits:
                return node, previous, settled
            node_potential = potential[node]
            for neighbor, arcs in self.adj[node].items():
                if neighbor in settled:
                    continue
                best_weight, best_arc = infinity, None
                for arc in arcs:
                    if capacity[arc] - flow[arc] >= delta and weight[arc] < best_weight:
                        best_weight, best_arc = weight[arc], arc
                if best_arc is None:
                    continue
                candidate = distance + best_weight - node_potential + potential[neighbor]
                if insert(nodes[neighbor], candidate):
                    previous[neighbor] = (node, best_arc)
        return None, previous, settled

    def solve(self, heap):
        delta = 2 ** int(log(max(self.capacity), 2))
        nodes, excess, potential = self.nodes, self.excess, self.potential
        while delta >= 1:
            self._saturate(delta)
            supplies, deficits = set(), set()
            for index, node in enumerate(nodes):
                if excess[index] >= delta:
                    supplies.add(node)
                elif excess[index] <= -delta:
                    deficits.add(node)
            while supplies and deficits:
                source_label = next(iter(supplies))
                source = self.index[source_label]
                target, previous, settled = self._shortest_augmenting_path(
                    source, deficits, delta, heap
                )
                if target is None:
                    supplies.remove(source_label)
                    continue
                node = target
                while node != source:
                    predecessor, arc = previous[node]
                    self.flow[arc] += delta
                    self.flow[arc ^ 1] -= delta
                    node = predecessor
                excess[source] -= delta
                excess[target] += delta
                if excess[source] < delta:
                    supplies.remove(source_label)
                if excess[target] > -delta:
                    deficits.remove(nodes[target])
                target_distance = settled[target]
                for node, distance in settled.items():
                    potential[node] -= distance - target_distance
            delta //= 2
        if any(value != 0 for value in excess):
            raise NetworkXUnfeasible("No flow satisfying all demands.")

    def flow_dict(self, graph, capacity, weight):
        """Read the original graph's output shape, retaining every zero arc."""
        result = {}
        infinity = float("inf")
        multi = graph.is_multigraph()
        for node in graph:
            row = result[node] = {}
            for neighbor, data in graph[node].items():
                if multi:
                    row[neighbor] = {
                        key: attrs[capacity]
                        if node == neighbor and attrs.get(capacity, infinity) > 0
                        and attrs.get(weight, 0) < 0 else 0
                        for key, attrs in data.items()
                    }
                else:
                    row[neighbor] = (
                        data[capacity]
                        if node == neighbor and data.get(capacity, infinity) > 0
                        and data.get(weight, 0) < 0 else 0
                    )
            for target, arcs in self.adj[self.index[node]].items():
                neighbor = self.nodes[target]
                for arc in arcs:
                    if self.flow[arc] > 0:
                        if multi:
                            if neighbor in row:
                                row[neighbor][self.key[arc]] = self.flow[arc]
                        else:
                            row[neighbor] = self.flow[arc]
        return result


class _CycleRows(dict):
    """Only the adjacency protocol needed by the owned Bellman-Ford core."""

    @property
    def _adj(self):
        return self


def _negative_cycle(nodes, arcs):
    from . import _inner_bellman_ford_inproc

    rows = _CycleRows((node, {}) for node in nodes)
    for source, target, value in arcs:
        rows[source][target] = value
    return _inner_bellman_ford_inproc(
        rows, nodes, lambda _u, _v, value: value,
        {node: [] for node in nodes}, dist={node: 0 for node in nodes},
    ) is not None


def capacity_scaling(graph, demand, capacity, weight, heap):
    """Run successive shortest augmentations at decreasing capacity scales."""
    residual = _Residual(graph, demand, capacity, weight)
    infinity = float("inf")
    cost = sum(
        0 if data.get(capacity, infinity) <= 0 or data.get(weight, 0) >= 0
        else data[capacity] * data[weight]
        for data in _selfloop_data(graph)
    )
    if residual.capacity:
        residual.solve(heap)
        for row in residual.adj:
            for arcs in row.values():
                for arc in arcs:
                    if residual.flow[arc] > 0:
                        cost += residual.flow[arc] * residual.weight[arc]
    return cost, residual.flow_dict(graph, capacity, weight)
