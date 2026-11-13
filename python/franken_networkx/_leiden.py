"""Owned modularity Leiden implementation.

The three phases follow Traag, Waltman and van Eck (2019), Appendix A,
algorithm A.2. Public levels expose successful refined contractions, not the
possibly disconnected coarse partition produced by local moving.
"""

import math
from collections import deque
from dataclasses import dataclass

from networkx.exception import NetworkXError


_REFINEMENT_TEMPERATURE = 0.01
_MAX_REFINEMENT_ATTEMPTS = 64


@dataclass
class _Level:
    adjacency: list
    loops: list
    degrees: list
    members: list
    total_weight: float


def _checked_sum(values):
    try:
        result = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise NetworkXError("Leiden accumulated weight is not finite") from exc
    if not math.isfinite(result):
        raise NetworkXError("Leiden accumulated weight is not finite")
    return result


def _number(value, *, resolution=False):
    message = (
        "resolution must be a finite positive number"
        if resolution else "Leiden edge weights must be finite nonnegative numbers"
    )
    if isinstance(value, (str, bytes, complex)):
        raise NetworkXError(message)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise NetworkXError(message) from exc
    if not math.isfinite(result) or (result <= 0 if resolution else result < 0):
        raise NetworkXError(message)
    return result


def _snapshot(graph, weight):
    labels = list(graph)
    indices = {node: index for index, node in enumerate(labels)}
    edge_weights = {}
    for u, v, data in graph.edges(data=True):
        value = _number(1 if weight is None else data.get(weight, 1))
        left, right = indices[u], indices[v]
        pair = (left, right) if left <= right else (right, left)
        edge_weights.setdefault(pair, []).append(value)

    adjacency = [{} for _ in labels]
    loops = [0.0] * len(labels)
    combined = {pair: _checked_sum(values) for pair, values in edge_weights.items()}
    total_weight = _checked_sum(combined.values())
    if not math.isfinite(2 * total_weight):
        raise NetworkXError("Leiden accumulated degree is not finite")
    for (left, right), value in combined.items():
        if left == right:
            loops[left] = value
        elif value > 0:
            adjacency[left][right] = value
            adjacency[right][left] = value
    degrees = [
        _checked_sum([*row.values(), loops[node], loops[node]])
        for node, row in enumerate(adjacency)
    ]
    return labels, _Level(
        adjacency, loops, degrees, [{node} for node in range(len(labels))], total_weight
    )


def _delta(level, between_weight, left_degree, right_degree, resolution):
    # Divide before multiplying degrees so a representable score does not
    # overflow merely because two large degree sums were multiplied first.
    penalty = (left_degree / (2 * level.total_weight)) * right_degree * resolution
    result = between_weight - penalty
    if not math.isfinite(result):
        raise NetworkXError("Leiden modularity arithmetic is not finite")
    return result


def _membership(blocks, size):
    membership = [0] * size
    for index, block in enumerate(blocks):
        for node in block:
            membership[node] = index
    return membership


def _degree_sum(level, nodes):
    return _checked_sum(level.degrees[node] for node in nodes)


def _fast_local_move(level, initial_membership, resolution, rng):
    groups = {}
    for node, group in enumerate(initial_membership):
        groups.setdefault(group, set()).add(node)
    membership = list(initial_membership)
    masses = {group: _degree_sum(level, nodes) for group, nodes in groups.items()}
    next_group = max(groups, default=-1) + 1
    order = list(range(len(level.adjacency)))
    rng.shuffle(order)
    queue = deque(order)
    queued = set(order)

    while queue:
        node = queue.popleft()
        queued.remove(node)
        old_group = membership[node]
        by_group = {}
        for neighbor, value in level.adjacency[node].items():
            by_group.setdefault(membership[neighbor], []).append(value)
        incident = {group: _checked_sum(values) for group, values in by_group.items()}
        remainder = groups[old_group] - {node}
        removal = _delta(
            level, incident.get(old_group, 0.0), level.degrees[node],
            _degree_sum(level, remainder), resolution,
        )

        best_group = old_group
        best_gain = 0.0
        # A fresh singleton is a real destination, including on an aggregate
        # graph whose inherited coarse communities contain several nodes.
        if -removal > best_gain:
            best_group, best_gain = None, -removal
        for group in sorted(incident):
            if group == old_group:
                continue
            gain = _delta(
                level, incident[group], level.degrees[node], masses[group], resolution
            ) - removal
            if not math.isfinite(gain):
                raise NetworkXError("Leiden modularity arithmetic is not finite")
            if gain > best_gain:
                best_group, best_gain = group, gain
        if best_group == old_group:
            continue

        groups[old_group].remove(node)
        if groups[old_group]:
            masses[old_group] = _degree_sum(level, groups[old_group])
        else:
            del groups[old_group]
            del masses[old_group]
        if best_group is None:
            best_group = next_group
            next_group += 1
            groups[best_group] = set()
        groups[best_group].add(node)
        masses[best_group] = _degree_sum(level, groups[best_group])
        membership[node] = best_group
        for neighbor in level.adjacency[node]:
            if membership[neighbor] != best_group and neighbor not in queued:
                queued.add(neighbor)
                queue.append(neighbor)

    return sorted(groups.values(), key=min)


def _choose_refinement(candidates, rng):
    if len(candidates) == 1:
        return candidates[0][0]
    # D is measured in edge-weight units (m times modularity gain), with a
    # fixed internal temperature. Subtracting the largest D avoids exp overflow.
    candidates.sort(key=lambda item: (-item[1], item[0]))
    maximum = candidates[0][1]
    probabilities = [
        math.exp((gain - maximum) / _REFINEMENT_TEMPERATURE)
        for _, gain in candidates
    ]
    remaining = rng.random() * math.fsum(probabilities)
    for (group, _), probability in zip(candidates, probabilities):
        if remaining < probability:
            return group
        remaining -= probability
    return candidates[-1][0]


def _refine(level, coarse, resolution, rng):
    blocks = {node: {node} for node in range(len(level.adjacency))}
    membership = list(range(len(level.adjacency)))
    for community in coarse:
        eligible = []
        for node in sorted(community):
            rest = community - {node}
            between = _checked_sum(
                value for neighbor, value in level.adjacency[node].items()
                if neighbor in rest
            )
            if _delta(
                level, between, level.degrees[node], _degree_sum(level, rest), resolution
            ) >= 0:
                eligible.append(node)
        rng.shuffle(eligible)

        for node in eligible:
            own = membership[node]
            if len(blocks[own]) != 1:
                continue
            neighbors = {
                membership[neighbor] for neighbor in level.adjacency[node]
                if neighbor in community and membership[neighbor] != own
            }
            candidates = [(own, 0.0)]
            for group in sorted(neighbors):
                block = blocks[group]
                rest = community - block
                cross = _checked_sum(
                    value for member in block
                    for neighbor, value in level.adjacency[member].items()
                    if neighbor in rest
                )
                block_degree = _degree_sum(level, block)
                if _delta(
                    level, cross, block_degree, _degree_sum(level, rest), resolution
                ) < 0:
                    continue
                between = _checked_sum(
                    value for neighbor, value in level.adjacency[node].items()
                    if neighbor in block
                )
                gain = _delta(
                    level, between, level.degrees[node], block_degree, resolution
                )
                if gain >= 0:
                    candidates.append((group, gain))
            selected = _choose_refinement(candidates, rng)
            if selected != own:
                blocks[selected].add(node)
                membership[node] = selected
                del blocks[own]
    return sorted(blocks.values(), key=min)


def _aggregate(level, refined, coarse):
    owner = _membership(refined, len(level.adjacency))
    coarse_owner = _membership(coarse, len(level.adjacency))
    loop_weights = [[level.loops[node] for node in block] for block in refined]
    edges = {}
    for node, row in enumerate(level.adjacency):
        for neighbor, value in row.items():
            if neighbor <= node:
                continue
            left, right = owner[node], owner[neighbor]
            if left == right:
                loop_weights[left].append(value)
            else:
                pair = (left, right) if left < right else (right, left)
                edges.setdefault(pair, []).append(value)
    adjacency = [{} for _ in refined]
    for (left, right), values in edges.items():
        value = _checked_sum(values)
        adjacency[left][right] = value
        adjacency[right][left] = value
    members = [
        set().union(*(level.members[node] for node in block)) for block in refined
    ]
    result = _Level(
        adjacency,
        [_checked_sum(values) for values in loop_weights],
        [_degree_sum(level, block) for block in refined],
        members,
        level.total_weight,
    )
    # Preserve the coarse partition on the refined quotient. Resetting these
    # labels to singletons would discard the split-and-reconsider Leiden step.
    initial_membership = [coarse_owner[min(block)] for block in refined]
    return result, initial_membership


def leiden_partitions(graph, weight, resolution, rng):
    """Iterate independent original-node sets after each refined contraction."""
    resolution = _number(resolution, resolution=True)
    labels, level = _snapshot(graph, weight)
    if level.total_weight == 0:
        yield [{node} for node in labels]
        return

    membership = list(range(len(labels)))
    yielded = False
    stalled_attempts = 0
    while True:
        coarse = _fast_local_move(level, membership, resolution, rng)
        if len(coarse) == len(level.adjacency):
            if not yielded:
                yield [{labels[node] for node in block} for block in level.members]
            return
        refined = _refine(level, coarse, resolution, rng)
        if len(refined) == len(level.adjacency):
            # Staying has nonzero probability during refinement. A failed
            # contraction is not evidence that the coarse partition converged.
            stalled_attempts += 1
            if stalled_attempts >= _MAX_REFINEMENT_ATTEMPTS:
                raise NetworkXError(
                    "Leiden refinement made no progress after 64 attempts"
                )
            membership = _membership(coarse, len(level.adjacency))
            continue
        level, membership = _aggregate(level, refined, coarse)
        stalled_attempts = 0
        yielded = True
        yield [{labels[node] for node in block} for block in level.members]
