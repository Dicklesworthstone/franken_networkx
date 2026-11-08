"""Owned Louvain levels for graph, numeric, and random-source protocols.

The behavior contract is EXISTING_NETWORKX_STRUCTURE.md section 47. Each
level uses ordered sparse rows and integer community positions; public node
labels remain visible to the caller's shuffle method. Python arithmetic is
retained throughout, including its mixed-type errors and summation order.
"""


def _weighted_edges(graph, nodes, weight):
    """Project attributes without relying on filtered-view key projection."""
    if weight is True or weight is False:
        # These are EdgeView's data switches, including the resulting errors
        # when Louvain attempts to use dictionaries or pairs as weighted edges.
        yield from graph.edges(nodes, data=weight, default=1)
        return
    for source, target, data in graph.edges(nodes, data=True):
        yield source, target, data[weight] if weight in data else 1


def _modularity(graph, partition, weight, resolution):
    """Evaluate the partition using the graph's own weighted degree protocol."""
    from networkx.algorithms.community.quality import NotAPartition

    from franken_networkx.community import is_partition

    if not is_partition(graph, partition):
        raise NotAPartition(graph, partition)
    directed = graph.is_directed()
    if directed:
        outgoing = _directional_degrees(graph, "out_degree", weight)
        incoming = _directional_degrees(graph, "in_degree", weight)
        total = sum(outgoing.values())
        normalization = 1 / total**2
    else:
        outgoing = incoming = dict(graph.degree(weight=weight))
        degree_sum = sum(outgoing.values())
        total = degree_sum / 2
        normalization = 1 / degree_sum**2

    def contribution(part):
        members = set(part)
        internal = sum(
            cost for _, target, cost in _weighted_edges(graph, members, weight)
            if target in members
        )
        out_sum = sum(outgoing[node] for node in members)
        in_sum = sum(incoming[node] for node in members) if directed else out_sum
        return internal / total - resolution * out_sum * in_sum * normalization

    return sum(contribution(part) for part in partition)


def _directional_degrees(graph, direction, weight):
    from franken_networkx import DiGraph

    view = getattr(graph, direction)(weight=weight)
    if type(graph) is DiGraph and weight is not None and not isinstance(weight, str):
        # Full DiGraph degree iteration has a string-only native accumulator;
        # indexed reads already retain arbitrary attribute-key semantics.
        return {node: view[node] for node in graph}
    return dict(view)


def _initial_graph(graph, weight):
    """Build the weighted working graph at the first iterator resume."""
    if not graph.is_multigraph():
        working = graph.__class__()
        working.add_nodes_from(graph)
        working.add_weighted_edges_from(_weighted_edges(graph, None, weight))
        return working

    from franken_networkx import DiGraph, Graph

    working = DiGraph() if graph.is_directed() else Graph()
    working.add_nodes_from(graph)
    for source, target, cost in _weighted_edges(graph, None, weight):
        if working.has_edge(source, target):
            working[source][target]["weight"] += cost
        else:
            working.add_edge(source, target, weight=cost)
    return working


def _coarsen(graph, groups):
    """Aggregate communities in group order, retaining edge encounter order."""
    working = graph.__class__()
    positions = {}
    for position, group in enumerate(groups):
        members = set()
        for node in group:
            positions[node] = position
            members.update(graph.nodes[node].get("nodes", {node}))
        working.add_node(position, nodes=members)
    for source, target, data in graph.edges(data=True):
        left, right = positions[source], positions[target]
        previous = working.get_edge_data(left, right, {"weight": 0})["weight"]
        # The new contribution precedes the accumulated value in the addition.
        working.add_edge(left, right, weight=data["weight"] + previous)
    return working


class _Level:
    """One local-improvement phase over indexed nodes and sparse neighbors."""

    def __init__(self, graph, total, resolution):
        self.nodes = list(graph)
        self.positions = {node: position for position, node in enumerate(self.nodes)}
        self.community = list(range(len(self.nodes)))
        self.directed = graph.is_directed()
        self.total = total
        self.resolution = resolution
        if self.directed:
            incoming = dict(graph.in_degree(weight="weight"))
            outgoing = dict(graph.out_degree(weight="weight"))
            self.in_degree = [incoming[node] for node in self.nodes]
            self.out_degree = [outgoing[node] for node in self.nodes]
            self.in_total = self.in_degree.copy()
            self.out_total = self.out_degree.copy()
        else:
            degree = dict(graph.degree(weight="weight"))
            self.out_degree = [degree[node] for node in self.nodes]
            self.out_total = self.out_degree.copy()

        self.neighbors = []
        for node in self.nodes:
            row = {}
            if self.directed:
                for neighbors in (graph[node], graph.pred[node]):
                    for neighbor, data in neighbors.items():
                        if neighbor != node:
                            position = self.positions[neighbor]
                            row.setdefault(position, 0.0)
                            row[position] += data["weight"]
            else:
                row = {
                    self.positions[neighbor]: data["weight"]
                    for neighbor, data in graph[node].items() if neighbor != node
                }
            self.neighbors.append(row)

    def _move(self, node):
        weights = {}
        for neighbor, cost in self.neighbors[node].items():
            group = self.community[neighbor]
            weights.setdefault(group, 0.0)
            weights[group] += cost
        previous = self.community[node]
        weights.setdefault(previous, 0.0)
        outgoing = self.out_degree[node]
        self.out_total[previous] -= outgoing
        total, resolution = self.total, self.resolution
        if self.directed:
            incoming = self.in_degree[node]
            self.in_total[previous] -= incoming
            removal = (
                -weights[previous] / total
                + resolution * (
                    outgoing * self.in_total[previous]
                    + incoming * self.out_total[previous]
                ) / total**2
            )
        else:
            removal = (
                -weights[previous] / total
                + resolution * (self.out_total[previous] * outgoing) / (2 * total**2)
            )

        best, best_gain = previous, 0
        for candidate, cost in weights.items():
            if self.directed:
                gain = removal + cost / total - resolution * (
                    outgoing * self.in_total[candidate]
                    + incoming * self.out_total[candidate]
                ) / total**2
            else:
                gain = removal + cost / total - resolution * (
                    self.out_total[candidate] * outgoing
                ) / (2 * total**2)
            if gain > best_gain:
                best, best_gain = candidate, gain
        self.out_total[best] += outgoing
        if self.directed:
            self.in_total[best] += incoming
        self.community[node] = best
        return previous, best

    def moves(self, rng):
        order = self.nodes.copy()
        rng.shuffle(order)
        while True:
            moved = False
            for label in order:
                node = self.positions[label]
                previous, current = self._move(node)
                if previous != current:
                    moved = True
                    yield node, previous, current
            if not moved:
                return


def partitions(graph, weight, resolution, threshold, rng, sets_factory):
    """Yield independent partitions, suspending before the next level's work."""
    from itertools import chain

    sets = sets_factory(list(graph.nodes()))
    if not any(graph.adj.values()):
        yield sets.partition
        return
    previous_modularity = _modularity(graph, sets.partition, weight, resolution)
    working = _initial_graph(graph, weight)
    total = working.size(weight="weight")
    first = True
    while True:
        level = _Level(working, total, resolution)
        moves = level.moves(rng)
        first_move = next(moves, None)
        if not first and first_move is None:
            return
        first = False
        # Subclass node factories can give even the first level explicit
        # memberships; its constructor can also change working-node order.
        moves = () if first_move is None else chain((first_move,), moves)
        yield sets.level(
            moves, nodes=level.nodes,
            membership=lambda node: working.nodes[node].get("nodes", {node}),
        )
        current_modularity = _modularity(working, sets.inner, "weight", resolution)
        if current_modularity - previous_modularity <= threshold:
            return
        previous_modularity = current_modularity
        working = _coarsen(working, sets.inner)
