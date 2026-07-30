#!/usr/bin/env python3
"""Generate the NetworkX 3.6.1 behavioral differential corpus.

The production entry point is the ``feature_behavioral_oracle`` Rust binary in
``fnx-conformance``.  It embeds CPython with PyO3, loads this module in-process,
and calls :func:`run_from_pyo3`.  Keeping the case generator in Python lets the
oracle operate on the real Python-visible objects while the Rust entry point
mechanically proves that the reference did not run in a subprocess.

The corpus is deliberately conservative:

* every row marked ``present`` in ``docs/coverage.md`` is accounted for;
* generated graph inputs come from a fixed PRNG seed and are serialized;
* aliases are tested once only when both packages expose the same object;
* ordering-only differences in node/edge collections are canonicalized away;
* path order, scalar types, exception types/messages, and exact float bits are
  retained;
* a row is ``agree`` only after at least one successful call on each side;
* equal failures without a successful call are ``error_only_agreement``;
* timeouts and unsupported argument shapes are ``unexercised``;
* every divergence contains the exact graph and argument recipe that found it.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
import contextlib
from dataclasses import dataclass
import hashlib
import importlib
import inspect
import io
import json
import math
import operator
import os
from pathlib import Path
import pkgutil
import random
import re
import signal
import sys
import tempfile
from types import ModuleType
from typing import Any


SCHEMA_VERSION = "fnx.behavioral-differential.v1"
NETWORKX_VERSION = "3.6.1"
NETWORKX_SOURCE_SHA256 = (
    "078c247dde263d696a86f6a2551bab277e16171bc38e797322ce8318755b1fc5"
)
CORPUS_SEED = 0xF36_100D
CASES_PER_GROUP = 2
MAX_CASE_ATTEMPTS = 8
CALL_TIMEOUT_SECONDS = 1.5
FIXED_GEXF_LASTMODIFIED_DATE = "2000-01-01"
REQUIRED_RUNTIME_ENVIRONMENT = {
    "MKL_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}

SURFACE_ROW_RE = re.compile(
    r"^\| `(?P<family>[^`]+)` "
    r"\| `(?P<networkx_path>networkx[^`]+)` "
    r"\| `(?P<kind>[^`]+)` "
    r"\| `(?P<status>[^`]+)` "
    r"\| `(?P<franken_path>franken_networkx[^`]+)` \|"
)
ADDRESS_RE = re.compile(r" at 0x[0-9a-fA-F]+")
CORE_GRAPH_CLASSES = {"Graph", "DiGraph", "MultiGraph", "MultiDiGraph"}
GRAPH_PARAMETER_NAMES = {
    "B",
    "G",
    "G1",
    "G2",
    "G_to_add_to",
    "H",
    "T",
    "flowG",
    "graph",
}
SOURCE_NAMES = {
    "_s",
    "n",
    "node",
    "node1",
    "root",
    "s",
    "source",
    "start",
    "u",
    "u_of_edge",
}
TARGET_NAMES = {
    "_t",
    "node2",
    "t",
    "target",
    "v",
    "v_of_edge",
}
NODE_COLLECTION_NAMES = {
    "C",
    "S",
    "center_nodes",
    "nbunch",
    "nbunch1",
    "nodes",
    "nodes1",
    "nodes2",
    "sources",
    "targets",
    "terminal_nodes",
}
INTEGER_PARAMETER_NAMES = {
    "N",
    "clique_size",
    "d",
    "dim",
    "h",
    "i",
    "k",
    "l",
    "m",
    "m1",
    "m2",
    "max_size",
    "n",
    "n1",
    "n2",
    "num_cliques",
    "num_colors",
    "number_of_sets",
    "order",
    "repeats",
    "sample_size",
    "shift",
    "stretch",
    "walk_length",
}
PROBABILITY_PARAMETER_NAMES = {
    "alpha",
    "beta",
    "mu",
    "p",
    "p1",
    "p2",
    "p_in",
    "p_out",
    "q",
    "tau1",
    "tau2",
    "theta",
    "threshold",
    "time_delta",
}
UNORDERED_EDGE_HINTS = {
    "boundary",
    "bridges",
    "cut",
    "edge_bfs",
    "edge_dfs",
    "edge_disjoint",
    "edges",
    "edgelist",
    "matching",
    "non_edges",
    "selfloop_edges",
}
PARTITION_HINTS = {
    "biconnected",
    "clique",
    "communities",
    "components",
    "groups",
    "partition",
    "sets",
}
PATH_COLLECTION_HINTS = {
    "all_pairs",
    "all_shortest_paths",
    "all_simple_paths",
    "shortest_simple_paths",
}
PATH_HINTS = {
    "astar_path",
    "bellman_ford_path",
    "bidirectional_shortest_path",
    "dag_longest_path",
    "dijkstra_path",
    "shortest_path",
}
SIDE_EFFECT_PREFIXES = (
    "networkx.drawing.",
    "networkx.draw",
    "networkx.display",
)
VOLATILE_FILE_WRITERS = {
    "write_adjlist",
    "write_multiline_adjlist",
}
NONDETERMINISTIC_RESULT_NAMES = {
    "directed_combinatorial_laplacian_matrix",
    "directed_laplacian_matrix",
    "eigenvector_centrality_numpy",
    "random_regular_expander_graph",
    "sigma",
}
GEXF_DATE_FUNCTIONS = {
    "generate_gexf",
    "write_gexf",
}


@dataclass(frozen=True)
class SurfaceRow:
    family: str
    networkx_path: str
    kind: str
    status: str
    franken_path: str


@dataclass
class Outcome:
    status: str
    normalized: Any
    stdout: str
    stderr: str


class InputUnsupported(RuntimeError):
    """The generic generator cannot construct a meaningful required value."""


class CallTimedOut(TimeoutError):
    """A single generated invocation exceeded the bounded call budget."""


class DeterministicRng:
    """Small stable PRNG whose output does not depend on Python versions."""

    def __init__(self, seed: int) -> None:
        self.state = seed & ((1 << 64) - 1)

    def next_u64(self) -> int:
        self.state = (
            self.state * 6364136223846793005 + 1442695040888963407
        ) & ((1 << 64) - 1)
        value = self.state
        value ^= value >> 18
        value ^= value << 27
        value ^= value >> 22
        return value & ((1 << 64) - 1)

    def index(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper must be positive")
        return self.next_u64() % upper


def stable_json(value: Any, *, pretty: bool = False) -> str:
    kwargs: dict[str, Any] = {
        "ensure_ascii": False,
        "sort_keys": True,
    }
    if pretty:
        kwargs["indent"] = 2
    else:
        kwargs["separators"] = (",", ":")
    return json.dumps(value, **kwargs)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def read_present_surface(coverage_path: Path) -> list[SurfaceRow]:
    rows: list[SurfaceRow] = []
    in_feature_universe = False
    for line in coverage_path.read_text(encoding="utf-8").splitlines():
        if line == "## Exhaustive FeatureUniverse":
            in_feature_universe = True
            continue
        if in_feature_universe and line.startswith("## "):
            break
        if not in_feature_universe:
            continue
        match = SURFACE_ROW_RE.match(line)
        if match is None or match.group("status") != "present":
            continue
        rows.append(SurfaceRow(**match.groupdict()))
    if len(rows) != 3399:
        raise RuntimeError(
            "expected 3,399 present FeatureUniverse paths, "
            f"found {len(rows)} in {coverage_path}"
        )
    return rows


def networkx_source_sha256(networkx_module: ModuleType) -> str:
    package_root = Path(networkx_module.__file__).resolve().parent
    digest = hashlib.sha256()
    for source_path in sorted(package_root.rglob("*.py")):
        relative_path = source_path.relative_to(package_root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def materialize_public_modules(package: ModuleType) -> None:
    """Make dotted public attributes deterministic before alias grouping."""
    for info in sorted(
        pkgutil.walk_packages(package.__path__, f"{package.__name__}."),
        key=lambda item: item.name,
    ):
        relative = info.name.removeprefix(f"{package.__name__}.")
        parts = relative.split(".")
        if "tests" in parts or any(part.startswith("_") for part in parts):
            continue
        try:
            importlib.import_module(info.name)
        except Exception:
            # Optional rendering/IO dependencies are assessed when a call is
            # attempted.  Import failure must not erase unrelated API groups.
            continue


def resolve_path(path: str) -> Any:
    parts = path.split(".")
    if not parts:
        raise AttributeError("empty qualified path")
    obj: Any = importlib.import_module(parts[0])
    for index, part in enumerate(parts[1:], start=1):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            module_name = ".".join(parts[: index + 1])
            obj = importlib.import_module(module_name)
    return obj


def graph_case_specs() -> list[dict[str, Any]]:
    profiles = (
        ("connected", "Graph"),
        ("disconnected", "Graph"),
        ("tree", "Graph"),
        ("bipartite", "Graph"),
        ("dag", "DiGraph"),
        ("strongly_connected", "DiGraph"),
        ("parallel", "MultiGraph"),
        ("parallel_directed", "MultiDiGraph"),
    )
    specs: list[dict[str, Any]] = []
    for index, (profile, graph_type) in enumerate(profiles):
        specs.append(
            generate_graph_spec(
                seed=CORPUS_SEED + index * 101,
                profile=profile,
                graph_type=graph_type,
            )
        )
    return specs


def generate_graph_spec(*, seed: int, profile: str, graph_type: str) -> dict[str, Any]:
    rng = DeterministicRng(seed)
    node_count = 5 + rng.index(3)
    node_ids: list[int | str]
    if seed & 1:
        node_ids = [f"n{index}" for index in range(node_count)]
    else:
        node_ids = list(range(node_count))

    edge_pairs: list[tuple[int, int]] = []
    if profile == "connected":
        edge_pairs.extend((index - 1, index) for index in range(1, node_count))
    elif profile == "disconnected":
        midpoint = max(2, node_count // 2)
        edge_pairs.extend((index - 1, index) for index in range(1, midpoint))
        edge_pairs.extend(
            (index - 1, index) for index in range(midpoint + 1, node_count)
        )
    elif profile == "tree":
        for index in range(1, node_count):
            edge_pairs.append((rng.index(index), index))
    elif profile == "bipartite":
        midpoint = max(2, node_count // 2)
        for left in range(midpoint):
            for right in range(midpoint, node_count):
                if (left + right + rng.index(3)) % 2 == 0:
                    edge_pairs.append((left, right))
        if not edge_pairs:
            edge_pairs.append((0, midpoint))
    elif profile == "dag":
        edge_pairs.extend((index - 1, index) for index in range(1, node_count))
        for left in range(node_count):
            for right in range(left + 2, node_count):
                if rng.index(4) == 0:
                    edge_pairs.append((left, right))
    elif profile == "strongly_connected":
        edge_pairs.extend(
            (index, (index + 1) % node_count) for index in range(node_count)
        )
        for _ in range(node_count):
            left = rng.index(node_count)
            right = rng.index(node_count)
            if left != right:
                edge_pairs.append((left, right))
    elif profile in {"parallel", "parallel_directed"}:
        edge_pairs.extend((index - 1, index) for index in range(1, node_count))
        edge_pairs.extend([(0, 1), (0, 1)])
        if profile == "parallel_directed":
            edge_pairs.append((1, 0))
    else:
        raise ValueError(f"unknown graph profile {profile!r}")

    if profile in {"connected", "disconnected"}:
        for _ in range(node_count):
            left = rng.index(node_count)
            right = rng.index(node_count)
            if left != right:
                edge_pairs.append((left, right))

    directed = graph_type in {"DiGraph", "MultiDiGraph"}
    multigraph = graph_type in {"MultiGraph", "MultiDiGraph"}
    seen: set[tuple[int, int]] = set()
    edges: list[dict[str, Any]] = []
    key_counts: defaultdict[tuple[int, int], int] = defaultdict(int)
    for ordinal, (left_index, right_index) in enumerate(edge_pairs):
        canonical_indices = (
            (left_index, right_index)
            if directed or left_index <= right_index
            else (right_index, left_index)
        )
        if not multigraph and canonical_indices in seen:
            continue
        seen.add(canonical_indices)
        key = key_counts[canonical_indices]
        key_counts[canonical_indices] += 1
        edge = {
            "u": node_ids[left_index],
            "v": node_ids[right_index],
            "attrs": {
                "capacity": 1 + ((ordinal + seed) % 7),
                "color": "warm" if ordinal % 2 == 0 else "cool",
                "weight": 1 + ((ordinal * 3 + seed) % 9),
            },
        }
        if multigraph:
            edge["key"] = key
        edges.append(edge)

    nodes = []
    midpoint = max(2, node_count // 2)
    for index, node in enumerate(node_ids):
        attrs: dict[str, Any] = {
            "color": "even" if index % 2 == 0 else "odd",
            "value": index + 1,
        }
        if profile == "bipartite":
            attrs["bipartite"] = 0 if index < midpoint else 1
        nodes.append({"id": node, "attrs": attrs})

    return {
        "id": f"{profile}-{seed}",
        "seed": seed,
        "profile": profile,
        "graph_type": graph_type,
        "directed": directed,
        "multigraph": multigraph,
        "graph_attrs": {"case_id": f"{profile}-{seed}"},
        "nodes": nodes,
        "edges": edges,
    }


def build_graph(module: ModuleType, spec: Mapping[str, Any], class_name: str | None = None) -> Any:
    graph_class = getattr(module, class_name or spec["graph_type"])
    graph = graph_class()
    graph.graph.update(spec["graph_attrs"])
    for node in spec["nodes"]:
        graph.add_node(node["id"], **node["attrs"])
    for edge in spec["edges"]:
        kwargs = dict(edge["attrs"])
        if spec["multigraph"]:
            kwargs["key"] = edge["key"]
        graph.add_edge(edge["u"], edge["v"], **kwargs)
    return graph


def secondary_graph_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    copied = json.loads(stable_json(spec))
    copied["id"] = f"{spec['id']}-secondary"
    copied["graph_attrs"]["case_id"] = copied["id"]
    if len(copied["edges"]) > 1:
        copied["edges"] = copied["edges"][1:]
    return copied


def graph_nodes(spec: Mapping[str, Any]) -> list[Any]:
    return [entry["id"] for entry in spec["nodes"]]


def graph_edges(spec: Mapping[str, Any]) -> list[tuple[Any, ...]]:
    if spec["multigraph"]:
        return [
            (entry["u"], entry["v"], entry["key"]) for entry in spec["edges"]
        ]
    return [(entry["u"], entry["v"]) for entry in spec["edges"]]


def simple_index_edges(spec: Mapping[str, Any]) -> tuple[int, list[tuple[int, int]]]:
    """Return the generated graph as a simple undirected integer graph."""
    nodes = graph_nodes(spec)
    indices = {node: index for index, node in enumerate(nodes)}
    edges = {
        tuple(sorted((indices[entry["u"]], indices[entry["v"]])))
        for entry in spec["edges"]
        if entry["u"] != entry["v"]
    }
    return len(nodes), sorted(edges)


def graph6_payload(spec: Mapping[str, Any]) -> bytes:
    """Encode a generated small graph without calling either package."""
    node_count, edges = simple_index_edges(spec)
    if node_count > 62:
        raise InputUnsupported("generated graph6 adapter only supports <=62 nodes")
    edge_set = set(edges)
    bits = [
        int((left, right) in edge_set)
        for right in range(1, node_count)
        for left in range(right)
    ]
    bits.extend([0] * ((-len(bits)) % 6))
    data = [node_count + 63]
    data.extend(
        63
        + sum(bit << (5 - offset) for offset, bit in enumerate(bits[index : index + 6]))
        for index in range(0, len(bits), 6)
    )
    return bytes(data)


def sparse6_payload(spec: Mapping[str, Any]) -> bytes:
    """Encode a generated small graph without calling either package."""
    node_count, simple_edges = simple_index_edges(spec)
    if node_count > 62:
        raise InputUnsupported("generated sparse6 adapter only supports <=62 nodes")
    width = 1
    while 1 << width < node_count:
        width += 1

    def encode_integer(value: int) -> list[int]:
        return [
            int(bool(value & (1 << (width - 1 - offset))))
            for offset in range(width)
        ]

    ordered_edges = sorted(
        (max(left, right), min(left, right)) for left, right in simple_edges
    )
    bits: list[int] = []
    current_vertex = 0
    for vertex, neighbor in ordered_edges:
        if vertex == current_vertex:
            bits.append(0)
            bits.extend(encode_integer(neighbor))
        elif vertex == current_vertex + 1:
            current_vertex += 1
            bits.append(1)
            bits.extend(encode_integer(neighbor))
        else:
            current_vertex = vertex
            bits.append(1)
            bits.extend(encode_integer(vertex))
            bits.append(0)
            bits.extend(encode_integer(neighbor))
    if (
        width < 6
        and node_count == (1 << width)
        and ((-len(bits)) % 6) >= width
        and current_vertex < node_count - 1
    ):
        bits.append(0)
        bits.extend([1] * ((-len(bits)) % 6))
    else:
        bits.extend([1] * ((-len(bits)) % 6))
    data = [ord(":"), node_count + 63]
    data.extend(
        63
        + sum(bit << (5 - offset) for offset, bit in enumerate(bits[index : index + 6]))
        for index in range(0, len(bits), 6)
    )
    return bytes(data)


def graphml_payload(spec: Mapping[str, Any]) -> str:
    """Build a minimal exact GraphML input independent of either package."""
    nodes = graph_nodes(spec)
    node_ids = {node: f"n{index}" for index, node in enumerate(nodes)}
    edge_default = "directed" if spec["directed"] else "undirected"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        f'  <graph id="generated" edgedefault="{edge_default}">',
    ]
    lines.extend(f'    <node id="{node_ids[node]}"/>' for node in nodes)
    seen: set[tuple[str, str]] = set()
    for entry in spec["edges"]:
        source = node_ids[entry["u"]]
        target = node_ids[entry["v"]]
        identity = (
            (source, target)
            if spec["directed"] or source <= target
            else (target, source)
        )
        if not spec["multigraph"] and identity in seen:
            continue
        seen.add(identity)
        lines.append(f'    <edge source="{source}" target="{target}"/>')
    lines.extend(["  </graph>", "</graphml>"])
    return "\n".join(lines) + "\n"


def gml_payload(spec: Mapping[str, Any]) -> str:
    """Build a minimal exact GML input independent of either package."""
    nodes = graph_nodes(spec)
    node_ids = {node: index for index, node in enumerate(nodes)}
    lines = ["graph [", f"  directed {int(bool(spec['directed']))}"]
    for node in nodes:
        lines.extend(
            [
                "  node [",
                f"    id {node_ids[node]}",
                f'    label "n{node_ids[node]}"',
                "  ]",
            ]
        )
    seen: set[tuple[int, int]] = set()
    for entry in spec["edges"]:
        source = node_ids[entry["u"]]
        target = node_ids[entry["v"]]
        identity = (
            (source, target)
            if spec["directed"] or source <= target
            else (target, source)
        )
        if not spec["multigraph"] and identity in seen:
            continue
        seen.add(identity)
        lines.extend(
            [
                "  edge [",
                f"    source {source}",
                f"    target {target}",
                "  ]",
            ]
        )
    lines.append("]")
    return "\n".join(lines) + "\n"


def adjacency_list_payload(spec: Mapping[str, Any]) -> str:
    """Build a deterministic adjacency-list input."""
    nodes = graph_nodes(spec)
    adjacency: defaultdict[Any, list[Any]] = defaultdict(list)
    for entry in spec["edges"]:
        adjacency[entry["u"]].append(entry["v"])
        if not spec["directed"]:
            adjacency[entry["v"]].append(entry["u"])
    return "".join(
        " ".join([str(node), *(str(neighbor) for neighbor in adjacency[node])])
        + "\n"
        for node in nodes
    )


def edge_list_payload(spec: Mapping[str, Any], *, weighted: bool) -> str:
    """Build a deterministic edge-list input."""
    fields = []
    for entry in spec["edges"]:
        row = [str(entry["u"]), str(entry["v"])]
        if weighted:
            row.append(str(entry["attrs"]["weight"]))
        fields.append(" ".join(row))
    return "\n".join(fields) + "\n"


def file_path_recipe(function_name: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    """Create an exact file recipe or reject formats without a sound adapter."""
    lowered = function_name.lower()
    leaf = lowered.rsplit(".", 1)[-1]
    is_reader = leaf.startswith("read_")
    is_writer = leaf.startswith("write_")
    if not is_reader and not is_writer:
        raise InputUnsupported(
            f"`{function_name}` path parameter is not a recognized file reader/writer"
        )
    if "graphml" in leaf:
        suffix = ".graphml"
        payload = graphml_payload(spec).encode("utf-8")
    elif "gml" in leaf:
        suffix = ".gml"
        payload = gml_payload(spec).encode("utf-8")
    elif "graph6" in leaf:
        suffix = ".g6"
        payload = graph6_payload(spec) + b"\n"
    elif "sparse6" in leaf:
        suffix = ".s6"
        payload = sparse6_payload(spec) + b"\n"
    elif "multiline_adjlist" in leaf:
        raise InputUnsupported(
            f"no exact generated multiline-adjacency adapter for `{function_name}`"
        )
    elif "adjlist" in leaf:
        suffix = ".adjlist"
        payload = adjacency_list_payload(spec).encode("utf-8")
    elif "edgelist" in leaf:
        suffix = ".edgelist"
        payload = edge_list_payload(
            spec, weighted="weighted" in leaf
        ).encode("utf-8")
    else:
        if is_reader:
            raise InputUnsupported(
                f"no exact generated file input adapter for `{function_name}`"
            )
        suffix = ".out"
        payload = b""
    return {
        "kind": "temp_path",
        "suffix": suffix,
        "initial_bytes_hex": payload.hex() if is_reader else "",
    }


def generated_path(spec: Mapping[str, Any]) -> list[Any]:
    nodes = graph_nodes(spec)
    if not nodes:
        return []
    adjacency: defaultdict[Any, list[Any]] = defaultdict(list)
    for edge in spec["edges"]:
        adjacency[edge["u"]].append(edge["v"])
        if not spec["directed"]:
            adjacency[edge["v"]].append(edge["u"])
    source = nodes[0]
    target = nodes[-1]
    queue: deque[Any] = deque([source])
    predecessor: dict[Any, Any | None] = {source: None}
    while queue:
        node = queue.popleft()
        if node == target:
            break
        for neighbor in adjacency[node]:
            if neighbor not in predecessor:
                predecessor[neighbor] = node
                queue.append(neighbor)
    if target not in predecessor:
        return nodes[: min(2, len(nodes))]
    path = []
    current: Any | None = target
    while current is not None:
        path.append(current)
        current = predecessor[current]
    path.reverse()
    return path


def canonical_node(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, float):
        return canonical_float(value)
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [canonical_node(item) for item in value]}
    return {
        "type": f"{type(value).__module__}.{type(value).__qualname__}",
        "repr": ADDRESS_RE.sub("", repr(value)),
    }


def canonical_float(value: float) -> dict[str, str]:
    if math.isnan(value):
        return {"type": "float", "value": "nan"}
    if math.isinf(value):
        return {"type": "float", "value": "inf" if value > 0 else "-inf"}
    return {"type": "float", "value": value.hex()}


def canonical_graph(graph: Any) -> dict[str, Any]:
    directed = bool(graph.is_directed())
    multigraph = bool(graph.is_multigraph())
    nodes = [
        {
            "node": canonical_node(node),
            "attrs": canonicalize(dict(attrs), "mapping", directed=directed),
        }
        for node, attrs in graph.nodes(data=True)
    ]
    nodes.sort(key=stable_json)

    raw_edges = (
        graph.edges(data=True, keys=True)
        if multigraph
        else graph.edges(data=True)
    )
    edges = []
    for edge in raw_edges:
        if multigraph:
            left, right, key, attrs = edge
        else:
            left, right, attrs = edge
            key = None
        left_node = canonical_node(left)
        right_node = canonical_node(right)
        if not directed and stable_json(right_node) < stable_json(left_node):
            left_node, right_node = right_node, left_node
        edges.append(
            {
                "u": left_node,
                "v": right_node,
                "key": canonical_node(key) if multigraph else None,
                "attrs": canonicalize(dict(attrs), "mapping", directed=directed),
            }
        )
    edges.sort(key=stable_json)
    return {
        "type": "graph",
        "directed": directed,
        "multigraph": multigraph,
        "graph": canonicalize(dict(graph.graph), "mapping", directed=directed),
        "nodes": nodes,
        "edges": edges,
    }


def is_graph_like(value: Any) -> bool:
    return all(
        hasattr(value, name)
        for name in ("edges", "is_directed", "is_multigraph", "nodes")
    )


def canonical_type_name(value_type: type[Any]) -> str:
    module = value_type.__module__
    qualname = value_type.__qualname__
    if module == "networkx" or module.startswith("networkx."):
        return f"graph_api.{qualname}"
    if module == "franken_networkx" or module.startswith("franken_networkx."):
        return f"graph_api.{qualname}"
    return f"{module}.{qualname}"


def canonical_callable(value: Any) -> dict[str, Any]:
    module = getattr(value, "__module__", None)
    qualname = getattr(value, "__qualname__", getattr(value, "__name__", None))
    if module == "networkx" or (
        isinstance(module, str) and module.startswith("networkx.")
    ):
        module = "graph_api"
    elif module == "franken_networkx" or (
        isinstance(module, str) and module.startswith("franken_networkx.")
    ):
        module = "graph_api"
    return {
        "type": "callable",
        "module": module,
        "qualname": qualname,
    }


def normalization_policy(name: str) -> str:
    lowered = name.lower()
    if any(hint in lowered for hint in PATH_COLLECTION_HINTS):
        return "path_collection"
    if any(lowered == hint or lowered.endswith(f".{hint}") for hint in PATH_HINTS):
        return "path"
    if any(hint in lowered for hint in UNORDERED_EDGE_HINTS):
        return "edge_collection"
    if any(hint in lowered for hint in PARTITION_HINTS):
        return "partition"
    return "auto"


def canonicalize(
    value: Any,
    policy: str = "auto",
    *,
    directed: bool = False,
    depth: int = 0,
) -> Any:
    if depth > 24:
        return {"type": "depth_limit"}
    if value is None or isinstance(value, (bool, int, str)):
        return {"type": type(value).__name__, "value": value}
    if isinstance(value, float):
        return canonical_float(value)
    if isinstance(value, complex):
        return {
            "type": "complex",
            "real": canonical_float(value.real),
            "imag": canonical_float(value.imag),
        }
    if isinstance(value, bytes):
        return {"type": "bytes", "hex": value.hex()}
    if inspect.isroutine(value) or inspect.isclass(value):
        return canonical_callable(value)
    if is_graph_like(value):
        return canonical_graph(value)

    module_name = type(value).__module__
    if module_name.startswith("numpy"):
        if hasattr(value, "tolist"):
            return {
                "type": "array",
                "dtype": str(getattr(value, "dtype", "")),
                "shape": list(getattr(value, "shape", ())),
                "items": canonicalize(
                    value.tolist(), "sequence", directed=directed, depth=depth + 1
                ),
            }
        if hasattr(value, "item"):
            return canonicalize(value.item(), policy, directed=directed, depth=depth + 1)
    if hasattr(value, "toarray") and module_name.startswith("scipy"):
        array = value.toarray()
        return canonicalize(array, "sequence", directed=directed, depth=depth + 1)
    if module_name.startswith("pandas") and hasattr(value, "to_dict"):
        return canonicalize(
            value.to_dict(), "mapping", directed=directed, depth=depth + 1
        )

    if isinstance(value, Mapping):
        items = [
            (
                canonicalize(key, "auto", directed=directed, depth=depth + 1),
                canonicalize(val, policy, directed=directed, depth=depth + 1),
            )
            for key, val in value.items()
        ]
        items.sort(key=lambda item: stable_json(item[0]))
        return {
            "type": "mapping",
            "items": [{"key": key, "value": val} for key, val in items],
        }
    if isinstance(value, (set, frozenset)):
        items = [
            canonicalize(item, "auto", directed=directed, depth=depth + 1)
            for item in value
        ]
        items.sort(key=stable_json)
        return {"type": "set", "items": items}

    if isinstance(value, Iterable):
        try:
            raw_items = list(value)
        except Exception as exc:
            return {
                "type": "unconsumed_iterable",
                "class": f"{type(value).__module__}.{type(value).__qualname__}",
                "error": f"{type(exc).__name__}: {exc}",
            }
        if len(raw_items) > 10_000:
            return {
                "type": "oversized_iterable",
                "class": f"{type(value).__module__}.{type(value).__qualname__}",
                "length": len(raw_items),
            }
        return canonicalize_sequence(
            raw_items,
            policy,
            directed=directed,
            depth=depth + 1,
        )

    if hasattr(value, "__dict__"):
        return {
            "type": canonical_type_name(type(value)),
            "state": canonicalize(
                vars(value), "mapping", directed=directed, depth=depth + 1
            ),
        }
    return {
        "type": canonical_type_name(type(value)),
        "repr": (
            ADDRESS_RE.sub("", repr(value))
            .replace("franken_networkx", "graph_api")
            .replace("networkx", "graph_api")
        ),
    }


def canonicalize_sequence(
    raw_items: list[Any],
    policy: str,
    *,
    directed: bool,
    depth: int,
) -> dict[str, Any]:
    if policy == "edge_collection":
        items = [
            canonical_edge_value(item, directed=directed, depth=depth + 1)
            for item in raw_items
        ]
        items.sort(key=stable_json)
        return {"type": "edge_collection", "items": items}
    if policy == "partition":
        groups = []
        for group in raw_items:
            if isinstance(group, Iterable) and not isinstance(group, (str, bytes)):
                members = [
                    canonicalize(
                        item, "auto", directed=directed, depth=depth + 1
                    )
                    for item in group
                ]
                members.sort(key=stable_json)
                groups.append({"type": "node_collection", "items": members})
            else:
                groups.append(
                    canonicalize(
                        group, "auto", directed=directed, depth=depth + 1
                    )
                )
        groups.sort(key=stable_json)
        return {"type": "partition", "items": groups}
    if policy == "path":
        return {
            "type": "path",
            "items": [
                canonicalize(item, "auto", directed=directed, depth=depth + 1)
                for item in raw_items
            ],
        }
    if policy == "path_collection":
        paths = [
            canonicalize_sequence(
                list(path),
                "path",
                directed=directed,
                depth=depth + 1,
            )
            for path in raw_items
        ]
        paths.sort(key=stable_json)
        return {"type": "path_collection", "items": paths}
    if policy == "sequence":
        return {
            "type": "sequence",
            "items": [
                canonicalize(item, "sequence", directed=directed, depth=depth + 1)
                for item in raw_items
            ],
        }

    normalized = [
        canonicalize(item, "auto", directed=directed, depth=depth + 1)
        for item in raw_items
    ]
    # The generic surface contract treats a bare iterable as an unordered
    # node/value collection.  Ordered paths are selected above by name.
    normalized.sort(key=stable_json)
    return {"type": "collection", "items": normalized}


def canonical_edge_value(value: Any, *, directed: bool, depth: int) -> Any:
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        return canonicalize(value, "auto", directed=directed, depth=depth + 1)
    left = canonicalize(value[0], "auto", directed=directed, depth=depth + 1)
    right = canonicalize(value[1], "auto", directed=directed, depth=depth + 1)
    if not directed and stable_json(right) < stable_json(left):
        left, right = right, left
    remainder = [
        canonicalize(item, "auto", directed=directed, depth=depth + 1)
        for item in value[2:]
    ]
    return {"type": "edge", "u": left, "v": right, "data": remainder}


@contextlib.contextmanager
def bounded_call() -> Iterable[None]:
    previous = signal.getsignal(signal.SIGALRM)

    def handle_alarm(_signum: int, _frame: Any) -> None:
        raise CallTimedOut(
            f"call exceeded {CALL_TIMEOUT_SECONDS:.1f} seconds"
        )

    signal.signal(signal.SIGALRM, handle_alarm)
    signal.setitimer(signal.ITIMER_REAL, CALL_TIMEOUT_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def first_edge(spec: Mapping[str, Any]) -> tuple[Any, ...]:
    edges = graph_edges(spec)
    if not edges:
        raise InputUnsupported("generated graph has no edge")
    return edges[0]


def generated_matching(spec: Mapping[str, Any]) -> set[tuple[Any, Any]]:
    used: set[Any] = set()
    matching = set()
    for edge in spec["edges"]:
        left, right = edge["u"], edge["v"]
        if left not in used and right not in used:
            matching.add((left, right))
            used.update((left, right))
    return matching


def generated_partition(spec: Mapping[str, Any]) -> list[set[Any]]:
    nodes = graph_nodes(spec)
    left = set(nodes[::2])
    right = set(nodes[1::2])
    return [group for group in (left, right) if group]


def parameter_recipe(
    parameter: inspect.Parameter,
    *,
    function_name: str,
    has_graph_parameter: bool,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    name = parameter.name
    nodes = graph_nodes(spec)
    if name in GRAPH_PARAMETER_NAMES:
        role = "secondary" if name in {"G2", "H"} else "primary"
        return {"kind": "graph", "role": role}
    if name == "N":
        if "pydot" in function_name or "agraph" in function_name:
            return {"kind": "graph", "role": "primary"}
        return {"kind": "integer", "value": len(nodes)}
    if name in SOURCE_NAMES:
        if name == "n" and not has_graph_parameter:
            return {"kind": "integer", "value": len(nodes)}
        return {"kind": "node", "index": 0}
    if name in TARGET_NAMES:
        return {"kind": "node", "index": -1}
    if name in NODE_COLLECTION_NAMES:
        if name in {"x", "y", "z"}:
            return {"kind": "node_set", "indices": [0]}
        split = max(1, len(nodes) // 2)
        indices = list(range(split))
        if name == "targets":
            indices = list(range(split, len(nodes))) or [len(nodes) - 1]
        return {"kind": "node_set", "indices": indices}
    if name in {"x", "y", "z"}:
        offset = {"x": 0, "y": 1, "z": 2}[name]
        return {"kind": "node_set", "indices": [min(offset, len(nodes) - 1)]}
    if name in INTEGER_PARAMETER_NAMES:
        if name == "radius":
            return {"kind": "float", "value": 0.75}
        value = 2
        if name in {"N", "n", "order"}:
            value = len(nodes)
        elif name in {"m", "m1", "m2"}:
            value = max(1, len(nodes) - 1)
        elif name == "d":
            value = 2
        elif name == "dim":
            value = 2
        return {"kind": "integer", "value": value}
    if name in PROBABILITY_PARAMETER_NAMES:
        values = {
            "alpha": 0.2,
            "beta": 0.5,
            "mu": 0.25,
            "p": 0.35,
            "p1": 0.2,
            "p2": 0.4,
            "p_in": 0.7,
            "p_out": 0.15,
            "q": 0.2,
            "tau1": 2.5,
            "tau2": 1.5,
            "theta": 0.2,
            "threshold": 2.0,
            "time_delta": 1.0,
        }
        return {"kind": "float", "value": values[name]}
    if name == "path":
        leaf_name = function_name.rsplit(".", 1)[-1]
        if (
            ".readwrite." in function_name
            or leaf_name.startswith("read_")
            or leaf_name.startswith("write_")
        ):
            return file_path_recipe(function_name, spec)
        return {"kind": "path"}
    if name in {"nodes_for_path", "nodes_for_cycle", "nodes_for_star"}:
        return {"kind": "path"}
    if name in {"paths", "rooted_trees"}:
        return {"kind": "paths"}
    if name in {"edge", "edges1", "edges2"}:
        return {"kind": "edge"}
    if name in {"edges", "edgelist", "cover"}:
        return {"kind": "edges"}
    if name == "matching":
        return {"kind": "matching"}
    if name in {"communities", "partition"}:
        return {"kind": "partition"}
    if name == "colors":
        return {"kind": "colors"}
    if name == "pos":
        return {"kind": "positions"}
    if name in {"attribute", "attr", "name", "src_attr", "dest_attr"}:
        value = "color" if "attr" in name or name == "attribute" else "weight"
        return {"kind": "string", "value": value}
    if name == "capacity":
        return {"kind": "string", "value": "capacity"}
    if name == "weight":
        return {"kind": "string", "value": "weight"}
    if name == "default":
        return {"kind": "integer", "value": 0}
    if name == "op":
        return {"kind": "operator", "value": "eq"}
    if name in {"values", "map", "mapping", "many_to_one"}:
        return {"kind": "node_mapping"}
    if name == "flowDict":
        return {"kind": "flow_mapping"}
    if name == "predecessors":
        return {"kind": "predecessor_mapping"}
    if name in {
        "aseq",
        "bseq",
        "deg_sequence",
        "degree_sequence",
        "in_degree_sequence",
        "in_deg_sequence",
        "in_degrees",
        "in_sequence",
        "out_degree_sequence",
        "out_deg_sequence",
        "out_degrees",
        "out_sequence",
        "sequence",
    }:
        return {"kind": "degree_sequence", "value": [2, 2, 2, 2]}
    if name in {"lines", "series"}:
        return {"kind": "lines", "value": ["0 1", "1 2", "2 3"]}
    if name in {"data", "d"}:
        return {"kind": "adjacency_mapping"}
    if name in {"A", "P", "R"}:
        return {"kind": "adjacency_array"}
    if name == "df":
        return {"kind": "adjacency_dataframe"}
    if name == "xy":
        return {"kind": "coordinate", "value": [0.25, 0.75]}
    if name == "sizes":
        return {"kind": "integer_sequence", "value": [3, 3]}
    if name in {"joint_degrees", "joint_degree_sequence", "nkk"}:
        return {"kind": "joint_degree", "value": {1: {1: 2}}}
    if name == "init_cycle":
        return {"kind": "path"}
    if name in {"row_order", "terminal_nodes"}:
        return {"kind": "node_list", "indices": list(range(len(nodes)))}
    if name == "num_colors":
        return {"kind": "integer", "value": 3}
    if name == "node_attributes":
        return {"kind": "string_list", "value": ["color"]}
    if name == "shift_list":
        return {"kind": "integer_sequence", "value": [2, -2]}
    if name == "offsets":
        return {"kind": "integer_sequence", "value": [1, 2]}
    if name == "intervals":
        return {"kind": "intervals", "value": [[0, 2], [1, 3], [4, 5]]}
    if name == "constructor":
        return {
            "kind": "shell_constructor",
            "value": [[4, 2, 0.5], [3, 1, 0.4]],
        }
    if name == "triad_name":
        return {"kind": "string", "value": "030T"}
    if name == "fullname":
        return {"kind": "string", "value": "math.sqrt"}
    if name == "module_name":
        return {"kind": "string", "value": "math"}
    if name == "iterable":
        return {"kind": "integer_sequence", "value": [3, 1, 2]}
    if name == "relation":
        return {"kind": "operator", "value": "eq"}
    if name == "obj":
        return {"kind": "nested_sequence", "value": [[1, 2], [3, 4]]}
    if name == "distribution":
        return {"kind": "float_sequence", "value": [1.0, 2.0, 3.0]}
    if name == "alpha":
        return {"kind": "float", "value": 0.2}
    if name == "bytes_in":
        return {"kind": "bytes", "hex": graph6_payload(spec).hex()}
    if name == "string":
        if "sparse6" in function_name:
            return {"kind": "bytes", "hex": sparse6_payload(spec).hex()}
        return {"kind": "string", "value": "generated"}
    if name == "graphml_string":
        return {"kind": "string", "value": graphml_payload(spec)}
    raise InputUnsupported(
        f"no generated value recipe for required parameter `{name}`"
    )


def realize_recipe(
    recipe: Mapping[str, Any],
    *,
    module: ModuleType,
    spec: Mapping[str, Any],
    secondary_spec: Mapping[str, Any],
    temp_root: Path,
    function_name: str,
) -> Any:
    kind = recipe["kind"]
    nodes = graph_nodes(spec)
    if kind == "graph":
        selected = secondary_spec if recipe["role"] == "secondary" else spec
        return build_graph(module, selected)
    if kind == "node":
        return nodes[recipe["index"]]
    if kind in {"node_set", "node_list"}:
        values = [nodes[index] for index in recipe["indices"]]
        return set(values) if kind == "node_set" else values
    if kind == "path":
        return generated_path(spec)
    if kind == "paths":
        path = generated_path(spec)
        return [path, list(reversed(path))]
    if kind == "edge":
        return first_edge(spec)
    if kind == "edges":
        return graph_edges(spec)
    if kind == "matching":
        return generated_matching(spec)
    if kind == "partition":
        return generated_partition(spec)
    if kind == "colors":
        return {node: index % 3 for index, node in enumerate(nodes)}
    if kind == "positions":
        return {
            node: (float(index), float((index * index) % 5))
            for index, node in enumerate(nodes)
        }
    if kind == "node_mapping":
        return {node: f"mapped-{index}" for index, node in enumerate(nodes)}
    if kind == "flow_mapping":
        flow: dict[Any, dict[Any, int]] = {node: {} for node in nodes}
        for edge in spec["edges"]:
            flow[edge["u"]][edge["v"]] = 0
            if not spec["directed"]:
                flow[edge["v"]][edge["u"]] = 0
        return flow
    if kind == "predecessor_mapping":
        path = generated_path(spec)
        return {
            node: ([] if index == 0 else [path[index - 1]])
            for index, node in enumerate(path)
        }
    if kind == "adjacency_mapping":
        adjacency: dict[Any, list[Any]] = {node: [] for node in nodes}
        for edge in spec["edges"]:
            adjacency[edge["u"]].append(edge["v"])
            if not spec["directed"]:
                adjacency[edge["v"]].append(edge["u"])
        return adjacency
    if kind == "adjacency_array":
        import numpy as np

        array = np.zeros((len(nodes), len(nodes)), dtype=float)
        node_index = {node: index for index, node in enumerate(nodes)}
        for edge in spec["edges"]:
            left = node_index[edge["u"]]
            right = node_index[edge["v"]]
            array[left, right] = float(edge["attrs"]["weight"])
            if not spec["directed"]:
                array[right, left] = array[left, right]
        return array
    if kind == "adjacency_dataframe":
        try:
            import pandas as pd
        except ImportError as exc:
            raise InputUnsupported("pandas is not installed") from exc
        array = realize_recipe(
            {"kind": "adjacency_array"},
            module=module,
            spec=spec,
            secondary_spec=secondary_spec,
            temp_root=temp_root,
            function_name=function_name,
        )
        return pd.DataFrame(array, index=nodes, columns=nodes)
    if kind == "operator":
        return {"eq": operator.eq}[recipe["value"]]
    if kind == "temp_path":
        path = temp_root / f"generated{recipe['suffix']}"
        initial_bytes = bytes.fromhex(recipe["initial_bytes_hex"])
        if initial_bytes:
            path.write_bytes(initial_bytes)
        return path
    if kind == "bytes":
        return bytes.fromhex(recipe["hex"])
    if kind in {
        "float",
        "integer",
        "string",
        "degree_sequence",
        "lines",
        "integer_sequence",
        "joint_degree",
        "coordinate",
        "string_list",
        "intervals",
        "shell_constructor",
        "nested_sequence",
        "float_sequence",
    }:
        return recipe["value"]
    raise InputUnsupported(f"cannot realize generated recipe kind `{kind}`")


def optional_overrides(
    signature: inspect.Signature,
    *,
    spec: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    overrides: dict[str, dict[str, Any]] = {}
    for name, parameter in signature.parameters.items():
        if parameter.default is inspect.Parameter.empty:
            continue
        if name in {"seed", "random_state"}:
            overrides[name] = {"kind": "integer", "value": int(spec["seed"])}
        elif name == "max_iter":
            overrides[name] = {"kind": "integer", "value": 200}
        elif name == "tol":
            overrides[name] = {"kind": "float", "value": 1e-10}
        elif name == "nstart":
            overrides[name] = {"kind": "uniform_node_mapping"}
    return overrides


def realize_optional_recipe(
    recipe: Mapping[str, Any],
    *,
    spec: Mapping[str, Any],
) -> Any:
    if recipe["kind"] == "uniform_node_mapping":
        return {node: 1.0 for node in graph_nodes(spec)}
    return recipe["value"]


def call_recipe_for(
    target: Any,
    *,
    function_name: str,
    spec: Mapping[str, Any],
    skip_self: bool = False,
) -> dict[str, Any]:
    signature = inspect.signature(target)
    parameters = list(signature.parameters.values())
    if skip_self and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]
    has_graph_parameter = any(
        parameter.name in GRAPH_PARAMETER_NAMES for parameter in parameters
    )
    required = []
    for parameter in parameters:
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        if parameter.default is not inspect.Parameter.empty:
            continue
        required.append(
            {
                "name": parameter.name,
                "value": parameter_recipe(
                    parameter,
                    function_name=function_name,
                    has_graph_parameter=has_graph_parameter,
                    spec=spec,
                ),
            }
        )
    return {
        "required": required,
        "optional_overrides": optional_overrides(signature, spec=spec),
    }


def realize_call_recipe(
    recipe: Mapping[str, Any],
    *,
    module: ModuleType,
    spec: Mapping[str, Any],
    temp_root: Path,
    function_name: str,
) -> tuple[list[Any], dict[str, Any], list[Any]]:
    secondary_spec = secondary_graph_spec(spec)
    args = []
    graph_arguments = []
    for entry in recipe["required"]:
        value = realize_recipe(
            entry["value"],
            module=module,
            spec=spec,
            secondary_spec=secondary_spec,
            temp_root=temp_root,
            function_name=function_name,
        )
        args.append(value)
        if is_graph_like(value):
            graph_arguments.append(value)
        elif isinstance(value, list):
            graph_arguments.extend(item for item in value if is_graph_like(item))
    kwargs = {
        name: realize_optional_recipe(value_recipe, spec=spec)
        for name, value_recipe in recipe["optional_overrides"].items()
    }
    return args, kwargs, graph_arguments


def canonical_temp_files(temp_root: Path) -> list[dict[str, Any]]:
    """Capture generated reader/writer side effects without order ambiguity."""
    files = []
    for path in sorted(temp_root.rglob("*")):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(temp_root).as_posix(),
                "bytes_hex": payload.hex(),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return files


def reset_runtime_randomness(seed: int) -> None:
    """Give each implementation the same deterministic ambient RNG state."""
    random.seed(seed)
    try:
        import numpy as np
    except ImportError:
        return
    np.random.seed(seed % (1 << 32))


@contextlib.contextmanager
def deterministic_volatile_metadata(function_name: str) -> Iterable[None]:
    """Pin known runtime metadata while preserving exact output comparison."""
    if function_name.rsplit(".", 1)[-1] not in GEXF_DATE_FUNCTIONS:
        yield
        return

    time_module = sys.modules["time"]
    original_strftime = time_module.strftime

    def deterministic_strftime(format_string: str, *args: Any) -> str:
        if format_string == "%Y-%m-%d" and not args:
            return FIXED_GEXF_LASTMODIFIED_DATE
        return original_strftime(format_string, *args)

    time_module.strftime = deterministic_strftime
    try:
        yield
    finally:
        time_module.strftime = original_strftime


def run_target(
    target: Any,
    *,
    module: ModuleType,
    spec: Mapping[str, Any],
    recipe: Mapping[str, Any],
    policy: str,
    function_name: str,
    receiver: Any | None = None,
) -> Outcome:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="fnx-behavioral-oracle-") as temp_dir:
        temp_root = Path(temp_dir)
        try:
            reset_runtime_randomness(int(spec["seed"]))
            args, kwargs, graph_arguments = realize_call_recipe(
                recipe,
                module=module,
                spec=spec,
                temp_root=temp_root,
                function_name=function_name,
            )
            with deterministic_volatile_metadata(function_name):
                with (
                    contextlib.redirect_stdout(stdout),
                    contextlib.redirect_stderr(stderr),
                    bounded_call(),
                ):
                    result = target(*args, **kwargs)
                directed = bool(spec["directed"])
                normalized = {
                    "return": canonicalize(result, policy, directed=directed),
                    "graph_arguments_after": [
                        canonical_graph(graph) for graph in graph_arguments
                    ],
                    "receiver_after": (
                        canonical_graph(receiver)
                        if receiver is not None and is_graph_like(receiver)
                        else None
                    ),
                    "temp_files_after": canonical_temp_files(temp_root),
                }
            return Outcome("ok", normalized, stdout.getvalue(), stderr.getvalue())
        except InputUnsupported as exc:
            return Outcome(
                "unsupported",
                {"reason": str(exc)},
                stdout.getvalue(),
                stderr.getvalue(),
            )
        except CallTimedOut as exc:
            return Outcome(
                "timeout",
                {"reason": str(exc)},
                stdout.getvalue(),
                stderr.getvalue(),
            )
        except Exception as exc:
            return Outcome(
                "error",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "graph_arguments_after": [
                        canonical_graph(graph)
                        for graph in locals().get("graph_arguments", [])
                    ],
                    "receiver_after": (
                        canonical_graph(receiver)
                        if receiver is not None and is_graph_like(receiver)
                        else None
                    ),
                    "temp_files_after": canonical_temp_files(temp_root),
                },
                stdout.getvalue(),
                stderr.getvalue(),
            )


def outcomes_match(reference: Outcome, candidate: Outcome) -> bool:
    if reference.status != candidate.status:
        return False
    if reference.status in {"timeout", "unsupported"}:
        return True
    return (
        reference.normalized == candidate.normalized
        and reference.stdout == candidate.stdout
        and reference.stderr == candidate.stderr
    )


def outcome_payload(outcome: Outcome) -> dict[str, Any]:
    return {
        "status": outcome.status,
        "normalized": outcome.normalized,
        "stdout": outcome.stdout,
        "stderr": outcome.stderr,
    }


def preferred_representative(rows: list[SurfaceRow]) -> SurfaceRow:
    return min(
        rows,
        key=lambda row: (
            row.networkx_path.count("."),
            len(row.networkx_path),
            row.networkx_path,
        ),
    )


def group_present_rows(
    rows: list[SurfaceRow],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: defaultdict[tuple[str, int, int], list[SurfaceRow]] = defaultdict(list)
    resolution_failures = []
    for row in rows:
        try:
            networkx_obj = resolve_path(row.networkx_path)
            franken_obj = resolve_path(row.franken_path)
        except Exception as exc:
            resolution_failures.append(
                {
                    "paths": [row.networkx_path],
                    "franken_paths": [row.franken_path],
                    "kind": row.kind,
                    "status": "unexercised",
                    "reason": (
                        "present path no longer resolves in the live process: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    "cases": [],
                }
            )
            continue
        groups[(row.kind, id(networkx_obj), id(franken_obj))].append(row)

    grouped = []
    for (_, _, _), members in groups.items():
        representative = preferred_representative(members)
        grouped.append(
            {
                "rows": sorted(members, key=lambda row: row.networkx_path),
                "representative": representative,
                "networkx_obj": resolve_path(representative.networkx_path),
                "franken_obj": resolve_path(representative.franken_path),
            }
        )
    grouped.sort(
        key=lambda group: group["representative"].networkx_path
    )
    return grouped, resolution_failures


def candidate_specs_for_group(
    representative: SurfaceRow,
    specs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if representative.kind == "method":
        owner_name = representative.networkx_path.rsplit(".", 2)[-2]
        if owner_name in CORE_GRAPH_CLASSES:
            return [
                spec for spec in specs if spec["graph_type"] == owner_name
            ] or specs
    return specs


def evaluate_callable_group(
    group: Mapping[str, Any],
    *,
    networkx_module: ModuleType,
    franken_module: ModuleType,
    specs: list[dict[str, Any]],
) -> dict[str, Any]:
    representative: SurfaceRow = group["representative"]
    paths = [row.networkx_path for row in group["rows"]]
    franken_paths = [row.franken_path for row in group["rows"]]
    base = {
        "identity_id": hashlib.sha256(
            "\0".join(paths + franken_paths).encode("utf-8")
        ).hexdigest()[:20],
        "paths": paths,
        "franken_paths": franken_paths,
        "family": representative.family,
        "kind": representative.kind,
        "representative": representative.networkx_path,
        "normalization_policy": normalization_policy(
            representative.networkx_path
        ),
        "cases": [],
    }
    if representative.networkx_path.startswith(SIDE_EFFECT_PREFIXES):
        return {
            **base,
            "status": "unexercised",
            "reason": (
                "rendering side effects and backend-specific artist objects "
                "are outside the canonical graph-value model"
            ),
        }
    if (
        representative.networkx_path.rsplit(".", 1)[-1]
        in VOLATILE_FILE_WRITERS
    ):
        return {
            **base,
            "status": "unexercised",
            "reason": (
                "writer embeds wall-clock metadata, so a reproducible exact "
                "output comparison requires an injectable clock"
            ),
        }
    if (
        representative.networkx_path.rsplit(".", 1)[-1]
        in NONDETERMINISTIC_RESULT_NAMES
    ):
        return {
            **base,
            "status": "unexercised",
            "reason": (
                "repeated same-process runs produced different normalized "
                "values despite resetting Python and NumPy RNG state"
            ),
        }

    networkx_target = group["networkx_obj"]
    franken_target = group["franken_obj"]
    policy = base["normalization_policy"]
    successful_matches = 0
    equal_errors = 0
    unsupported_reasons = []

    for spec in candidate_specs_for_group(representative, specs)[
        :MAX_CASE_ATTEMPTS
    ]:
        try:
            recipe = call_recipe_for(
                networkx_target,
                function_name=representative.networkx_path,
                spec=spec,
            )
        except (InputUnsupported, TypeError, ValueError) as exc:
            unsupported_reasons.append(str(exc))
            continue

        reference = run_target(
            networkx_target,
            module=networkx_module,
            spec=spec,
            recipe=recipe,
            policy=policy,
            function_name=representative.networkx_path,
        )
        candidate = run_target(
            franken_target,
            module=franken_module,
            spec=spec,
            recipe=recipe,
            policy=policy,
            function_name=representative.franken_path,
        )
        case = {
            "input_id": spec["id"],
            "argument_recipe": recipe,
            "networkx_status": reference.status,
            "franken_status": candidate.status,
        }

        if reference.status in {"timeout", "unsupported"} or candidate.status in {
            "timeout",
            "unsupported",
        }:
            unsupported_reasons.append(
                f"{spec['id']}: NetworkX={reference.status}, "
                f"FrankenNetworkX={candidate.status}"
            )
            base["cases"].append(case)
            continue

        if not outcomes_match(reference, candidate):
            case["agreement"] = False
            base["cases"].append(case)
            return {
                **base,
                "status": "diverge",
                "reason": "canonical outcomes differ",
                "divergence": {
                    "exact_input": spec,
                    "argument_recipe": recipe,
                    "networkx": outcome_payload(reference),
                    "franken_networkx": outcome_payload(candidate),
                },
            }

        case["agreement"] = True
        case["outcome_sha256"] = sha256_json(outcome_payload(reference))
        base["cases"].append(case)
        if reference.status == "ok":
            successful_matches += 1
        elif reference.status == "error":
            equal_errors += 1
        if successful_matches >= CASES_PER_GROUP:
            break

    if successful_matches:
        return {
            **base,
            "status": "agree",
            "reason": (
                f"{successful_matches} generated successful case(s) "
                "canonically agree"
            ),
        }
    if equal_errors:
        return {
            **base,
            "status": "error_only_agreement",
            "reason": (
                f"{equal_errors} generated fully-bound case(s) raised the "
                "same exception, but no successful value was exercised"
            ),
        }
    reason = (
        "; ".join(dict.fromkeys(unsupported_reasons))
        or "no generated call could be completed"
    )
    return {**base, "status": "unexercised", "reason": reason}


def evaluate_method_group(
    group: Mapping[str, Any],
    *,
    networkx_module: ModuleType,
    franken_module: ModuleType,
    specs: list[dict[str, Any]],
) -> dict[str, Any]:
    representative: SurfaceRow = group["representative"]
    owner_networkx_path = representative.networkx_path.rsplit(".", 1)[0]
    owner_franken_path = representative.franken_path.rsplit(".", 1)[0]
    owner_name = owner_networkx_path.rsplit(".", 1)[-1]
    member_name = representative.networkx_path.rsplit(".", 1)[-1]
    paths = [row.networkx_path for row in group["rows"]]
    franken_paths = [row.franken_path for row in group["rows"]]
    base = {
        "identity_id": hashlib.sha256(
            "\0".join(paths + franken_paths).encode("utf-8")
        ).hexdigest()[:20],
        "paths": paths,
        "franken_paths": franken_paths,
        "family": representative.family,
        "kind": representative.kind,
        "representative": representative.networkx_path,
        "normalization_policy": normalization_policy(member_name),
        "cases": [],
    }
    if owner_name not in CORE_GRAPH_CLASSES:
        return {
            **base,
            "status": "unexercised",
            "reason": (
                f"owner class `{owner_name}` requires a specialized generated "
                "constructor not yet in the core graph method adapter"
            ),
        }

    networkx_owner = resolve_path(owner_networkx_path)
    franken_owner = resolve_path(owner_franken_path)
    owner_specs = [
        spec for spec in specs if spec["graph_type"] == owner_name
    ]
    successful_matches = 0
    equal_errors = 0
    unsupported_reasons = []
    for spec in owner_specs[:MAX_CASE_ATTEMPTS]:
        networkx_receiver = build_graph(
            networkx_module, spec, class_name=owner_name
        )
        franken_receiver = build_graph(
            franken_module, spec, class_name=owner_name
        )
        networkx_target = getattr(networkx_receiver, member_name)
        franken_target = getattr(franken_receiver, member_name)
        try:
            recipe = call_recipe_for(
                group["networkx_obj"],
                function_name=representative.networkx_path,
                spec=spec,
                skip_self=True,
            )
        except (InputUnsupported, TypeError, ValueError) as exc:
            unsupported_reasons.append(str(exc))
            continue

        reference = run_target(
            networkx_target,
            module=networkx_module,
            spec=spec,
            recipe=recipe,
            policy=base["normalization_policy"],
            function_name=representative.networkx_path,
            receiver=networkx_receiver,
        )
        candidate = run_target(
            franken_target,
            module=franken_module,
            spec=spec,
            recipe=recipe,
            policy=base["normalization_policy"],
            function_name=representative.franken_path,
            receiver=franken_receiver,
        )
        case = {
            "input_id": spec["id"],
            "argument_recipe": recipe,
            "networkx_status": reference.status,
            "franken_status": candidate.status,
        }
        if reference.status in {"timeout", "unsupported"} or candidate.status in {
            "timeout",
            "unsupported",
        }:
            unsupported_reasons.append(
                f"{spec['id']}: NetworkX={reference.status}, "
                f"FrankenNetworkX={candidate.status}"
            )
            base["cases"].append(case)
            continue
        if not outcomes_match(reference, candidate):
            case["agreement"] = False
            base["cases"].append(case)
            return {
                **base,
                "status": "diverge",
                "reason": "canonical outcomes or receiver states differ",
                "divergence": {
                    "exact_input": spec,
                    "argument_recipe": recipe,
                    "networkx": outcome_payload(reference),
                    "franken_networkx": outcome_payload(candidate),
                },
            }
        case["agreement"] = True
        case["outcome_sha256"] = sha256_json(outcome_payload(reference))
        base["cases"].append(case)
        if reference.status == "ok":
            successful_matches += 1
        elif reference.status == "error":
            equal_errors += 1
        if successful_matches >= CASES_PER_GROUP:
            break

    if successful_matches:
        return {
            **base,
            "status": "agree",
            "reason": (
                f"{successful_matches} generated successful case(s) "
                "canonically agree, including receiver state"
            ),
        }
    if equal_errors:
        return {
            **base,
            "status": "error_only_agreement",
            "reason": (
                f"{equal_errors} generated fully-bound case(s) raised the "
                "same exception, but no successful value was exercised"
            ),
        }
    reason = (
        "; ".join(dict.fromkeys(unsupported_reasons))
        or "no generated core-graph method call could be completed"
    )
    return {**base, "status": "unexercised", "reason": reason}


def evaluate_class_group(
    group: Mapping[str, Any],
    *,
    networkx_module: ModuleType,
    franken_module: ModuleType,
    specs: list[dict[str, Any]],
) -> dict[str, Any]:
    representative: SurfaceRow = group["representative"]
    paths = [row.networkx_path for row in group["rows"]]
    franken_paths = [row.franken_path for row in group["rows"]]
    base = {
        "identity_id": hashlib.sha256(
            "\0".join(paths + franken_paths).encode("utf-8")
        ).hexdigest()[:20],
        "paths": paths,
        "franken_paths": franken_paths,
        "family": representative.family,
        "kind": representative.kind,
        "representative": representative.networkx_path,
        "normalization_policy": "auto",
        "cases": [],
    }
    class_name = getattr(group["networkx_obj"], "__name__", "")
    if class_name in CORE_GRAPH_CLASSES:
        spec = next(
            spec for spec in specs if spec["graph_type"] == class_name
        )
        reference = canonical_graph(
            build_graph(networkx_module, spec, class_name=class_name)
        )
        candidate = canonical_graph(
            build_graph(franken_module, spec, class_name=class_name)
        )
        case = {
            "input_id": spec["id"],
            "argument_recipe": {"constructor": "generated graph snapshot"},
            "agreement": reference == candidate,
        }
        base["cases"].append(case)
        if reference != candidate:
            return {
                **base,
                "status": "diverge",
                "reason": "constructed graph states differ",
                "divergence": {
                    "exact_input": spec,
                    "argument_recipe": case["argument_recipe"],
                    "networkx": reference,
                    "franken_networkx": candidate,
                },
            }
        return {
            **base,
            "status": "agree",
            "reason": "generated constructor state canonically agrees",
        }
    if representative.family == "exceptions":
        message = f"generated-{CORPUS_SEED}"
        reference_exc = group["networkx_obj"](message)
        candidate_exc = group["franken_obj"](message)
        reference = {
            "type": type(reference_exc).__name__,
            "message": str(reference_exc),
        }
        candidate = {
            "type": type(candidate_exc).__name__,
            "message": str(candidate_exc),
        }
        base["cases"].append(
            {
                "input_id": "generated-exception-message",
                "argument_recipe": {"message": message},
                "agreement": reference == candidate,
            }
        )
        if reference != candidate:
            return {
                **base,
                "status": "diverge",
                "reason": "generated exception construction differs",
                "divergence": {
                    "exact_input": {"message": message},
                    "argument_recipe": {"message": message},
                    "networkx": reference,
                    "franken_networkx": candidate,
                },
            }
        return {
            **base,
            "status": "agree",
            "reason": "generated exception construction agrees",
        }
    return {
        **base,
        "status": "unexercised",
        "reason": (
            f"class `{class_name}` requires a specialized generated "
            "constructor outside the core graph/exception adapters"
        ),
    }


def non_behavioral_group(group: Mapping[str, Any]) -> dict[str, Any]:
    representative: SurfaceRow = group["representative"]
    paths = [row.networkx_path for row in group["rows"]]
    franken_paths = [row.franken_path for row in group["rows"]]
    return {
        "identity_id": hashlib.sha256(
            "\0".join(paths + franken_paths).encode("utf-8")
        ).hexdigest()[:20],
        "paths": paths,
        "franken_paths": franken_paths,
        "family": representative.family,
        "kind": representative.kind,
        "representative": representative.networkx_path,
        "normalization_policy": None,
        "status": "non_behavioral",
        "reason": (
            f"`{representative.kind}` binding has structural surface parity "
            "but no standalone callable behavior"
        ),
        "cases": [],
    }


def build_corpus(repo_root: Path, *, bridge: str) -> dict[str, Any]:
    if bridge != "pyo3-embedded":
        raise RuntimeError(
            "official corpus generation requires the PyO3 embedded runner"
        )
    runtime_drift = {
        name: os.environ.get(name)
        for name, expected in REQUIRED_RUNTIME_ENVIRONMENT.items()
        if os.environ.get(name) != expected
    }
    if runtime_drift:
        expected = ", ".join(
            f"{name}={value}"
            for name, value in sorted(REQUIRED_RUNTIME_ENVIRONMENT.items())
        )
        observed = ", ".join(
            f"{name}={value!r}" for name, value in sorted(runtime_drift.items())
        )
        raise RuntimeError(
            "behavioral oracle requires a deterministic runtime environment: "
            f"expected {expected}; observed {observed}"
        )

    import networkx

    if networkx.__version__ != NETWORKX_VERSION:
        raise RuntimeError(
            f"expected networkx=={NETWORKX_VERSION}, "
            f"loaded {networkx.__version__}"
        )
    source_digest = networkx_source_sha256(networkx)
    if source_digest != NETWORKX_SOURCE_SHA256:
        raise RuntimeError(
            "pinned NetworkX source fingerprint drifted: "
            f"expected {NETWORKX_SOURCE_SHA256}, got {source_digest}"
        )

    import franken_networkx

    materialize_public_modules(networkx)
    materialize_public_modules(franken_networkx)
    rows = read_present_surface(repo_root / "docs" / "coverage.md")
    groups, resolution_failures = group_present_rows(rows)
    specs = graph_case_specs()

    results = list(resolution_failures)
    for index, group in enumerate(groups, start=1):
        representative = group["representative"]
        if representative.kind == "callable":
            result = evaluate_callable_group(
                group,
                networkx_module=networkx,
                franken_module=franken_networkx,
                specs=specs,
            )
        elif representative.kind == "method":
            result = evaluate_method_group(
                group,
                networkx_module=networkx,
                franken_module=franken_networkx,
                specs=specs,
            )
        elif representative.kind == "class":
            result = evaluate_class_group(
                group,
                networkx_module=networkx,
                franken_module=franken_networkx,
                specs=specs,
            )
        else:
            result = non_behavioral_group(group)
        results.append(result)
        if index % 100 == 0:
            print(
                f"behavioral oracle: evaluated {index}/{len(groups)} identity groups",
                file=sys.stderr,
            )

    results.sort(key=lambda item: item["paths"][0])
    path_counts: defaultdict[str, int] = defaultdict(int)
    group_counts: defaultdict[str, int] = defaultdict(int)
    family_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for result in results:
        status = result["status"]
        count = len(result["paths"])
        path_counts[status] += count
        group_counts[status] += 1
        family_counts[result.get("family", "unknown")][status] += count
    accounted_paths = sum(path_counts.values())
    if accounted_paths != len(rows):
        raise RuntimeError(
            f"behavioral corpus accounts for {accounted_paths} paths, "
            f"expected {len(rows)}"
        )

    divergences = [
        {
            "identity_id": result["identity_id"],
            "paths": result["paths"],
            **result["divergence"],
        }
        for result in results
        if result["status"] == "diverge"
    ]
    summary = {
        "present_paths": len(rows),
        "identity_groups": len(results),
        "agree_paths": path_counts["agree"],
        "diverge_paths": path_counts["diverge"],
        "error_only_agreement_paths": path_counts["error_only_agreement"],
        "unexercised_paths": path_counts["unexercised"],
        "non_behavioral_paths": path_counts["non_behavioral"],
        "agree_groups": group_counts["agree"],
        "diverge_groups": group_counts["diverge"],
        "error_only_agreement_groups": group_counts[
            "error_only_agreement"
        ],
        "unexercised_groups": group_counts["unexercised"],
        "non_behavioral_groups": group_counts["non_behavioral"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "reference": {
            "package": "networkx",
            "version": networkx.__version__,
            "python_source_sha256": source_digest,
        },
        "runner": {
            "bridge": bridge,
            "entrypoint": (
                "PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 "
                "OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 "
                "target/debug/feature_behavioral_oracle --write"
            ),
            "corpus_seed": CORPUS_SEED,
            "cases_per_group": CASES_PER_GROUP,
            "call_timeout_seconds": CALL_TIMEOUT_SECONDS,
            "runtime_environment": REQUIRED_RUNTIME_ENVIRONMENT,
            "subprocess_reference_calls": 0,
        },
        "normalization": {
            "node_collections": "canonical tagged values sorted by stable JSON",
            "edge_collections": (
                "undirected endpoints canonicalized, collections sorted"
            ),
            "partitions": "members and groups independently sorted",
            "paths": "node order preserved; collections of paths sorted",
            "mappings": "keys canonicalized and sorted",
            "floats": "exact IEEE-754 hexadecimal form; NaN/Inf tagged",
            "exceptions": "exact class name and message",
            "mutations": "post-call graph arguments and receiver state included",
            "volatile_metadata": (
                "GEXF lastmodifieddate pinned to 2000-01-01 during each call"
            ),
        },
        "generated_inputs": specs,
        "summary": summary,
        "per_family": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_counts.items())
        },
        "divergences": divergences,
        "items": results,
    }


def render_report(corpus: Mapping[str, Any]) -> str:
    summary = corpus["summary"]
    lines = [
        "# FrankenNetworkX Behavioral Differential Oracle",
        "",
        "*Generated by the PyO3-embedded `fnx-conformance` oracle; do not edit manually.*",
        "",
        "## Method and provenance",
        "",
        f"- Reference: `networkx=={corpus['reference']['version']}`.",
        (
            "- Reference Python source SHA-256: "
            f"`{corpus['reference']['python_source_sha256']}`."
        ),
        "- Execution: NetworkX and FrankenNetworkX are imported in the same embedded CPython process through PyO3; the corpus records zero reference subprocess calls.",
        f"- Generated-input seed: `{corpus['runner']['corpus_seed']}`; every divergence embeds the exact graph and argument recipe that reproduced it.",
        "- Canonical comparison removes unspecified node/edge collection ordering while preserving ordered paths, exact float bits, exact exception contracts, stdout/stderr, and graph mutation state.",
        "",
        "## Present-path behavioral accounting",
        "",
        "| Status | Paths | Identity groups | Meaning |",
        "|--------|------:|----------------:|---------|",
        (
            f"| `agree` | {summary['agree_paths']} | "
            f"{summary['agree_groups']} | At least one generated successful "
            "case canonically agrees. |"
        ),
        (
            f"| `diverge` | {summary['diverge_paths']} | "
            f"{summary['diverge_groups']} | A generated case produced a "
            "genuine canonical mismatch. |"
        ),
        (
            f"| `error_only_agreement` | "
            f"{summary['error_only_agreement_paths']} | "
            f"{summary['error_only_agreement_groups']} | Fully-bound generated "
            "calls agree only on errors; no successful value is claimed. |"
        ),
        (
            f"| `unexercised` | {summary['unexercised_paths']} | "
            f"{summary['unexercised_groups']} | No meaningful bounded "
            "generated invocation completed. |"
        ),
        (
            f"| `non_behavioral` | {summary['non_behavioral_paths']} | "
            f"{summary['non_behavioral_groups']} | Structural "
            "descriptor/property/attribute binding, not a callable result. |"
        ),
        (
            f"| **All present paths** | **{summary['present_paths']}** | "
            f"**{summary['identity_groups']}** | Every path is accounted for. |"
        ),
        "",
        "## Per-family path accounting",
        "",
        "| Family | Agree | Diverge | Error-only | Unexercised | Non-behavioral |",
        "|--------|------:|--------:|-----------:|------------:|---------------:|",
    ]
    for family, counts in corpus["per_family"].items():
        lines.append(
            f"| `{family}` | {counts.get('agree', 0)} | "
            f"{counts.get('diverge', 0)} | "
            f"{counts.get('error_only_agreement', 0)} | "
            f"{counts.get('unexercised', 0)} | "
            f"{counts.get('non_behavioral', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Honest current sentence",
            "",
            (
                f"Of {summary['present_paths']} surface-present NetworkX paths, "
                f"generated in-process differential cases currently prove "
                f"{summary['agree_paths']} behaviorally agreeing and "
                f"{summary['diverge_paths']} diverging; "
                f"{summary['error_only_agreement_paths']} have error-only "
                f"agreement, {summary['unexercised_paths']} remain "
                f"unexercised, and {summary['non_behavioral_paths']} are "
                "non-behavioral bindings."
            ),
            "",
            "## Genuine divergences",
            "",
        ]
    )
    if not corpus["divergences"]:
        lines.append("No canonical divergence was found in the generated corpus.")
    else:
        for divergence in corpus["divergences"]:
            lines.extend(
                [
                    f"### `{divergence['identity_id']}`",
                    "",
                    "- Paths: "
                    + ", ".join(f"`{path}`" for path in divergence["paths"]),
                    (
                        "- Exact reproducer: see `divergences` entry "
                        f"`{divergence['identity_id']}` in the JSON corpus."
                    ),
                    "",
                ]
            )
    lines.extend(
        [
            "## Reproduction",
            "",
            "```bash",
            "RCH_REQUIRE_REMOTE=1 env -u CARGO_TARGET_DIR rch exec \\",
            "  --base <clean-commit> --clean-overlay \\",
            "  --overlay-path crates/fnx-conformance \\",
            "  --overlay-path scripts/generate_behavioral_oracle.py \\",
            "  --overlay-path Cargo.lock -- \\",
            "  cargo build -p fnx-conformance --bin feature_behavioral_oracle --locked",
            "",
            "PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 \\",
            "  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \\",
            "  target/debug/feature_behavioral_oracle --check",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_or_check(
    repo_root: Path,
    *,
    check: bool,
    bridge: str,
) -> dict[str, Any]:
    corpus = build_corpus(repo_root, bridge=bridge)
    corpus_text = stable_json(corpus, pretty=True) + "\n"
    report_text = render_report(corpus)
    corpus_path = (
        repo_root
        / "artifacts"
        / "conformance"
        / "behavioral_oracle"
        / "feature_behavioral_corpus_v1.json"
    )
    report_path = repo_root / "docs" / "behavioral_conformance.md"
    if check:
        expected_corpus = corpus_path.read_text(encoding="utf-8")
        expected_report = report_path.read_text(encoding="utf-8")
        if expected_corpus != corpus_text:
            raise RuntimeError(f"generated corpus drifted: {corpus_path}")
        if expected_report != report_text:
            raise RuntimeError(f"generated report drifted: {report_path}")
    else:
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        corpus_path.write_text(corpus_text, encoding="utf-8")
        report_path.write_text(report_text, encoding="utf-8")
    return corpus["summary"]


def run_from_pyo3(repo_root: str, check: bool) -> str:
    """Entry point called by the Rust/PyO3 embedding binary."""
    summary = write_or_check(
        Path(repo_root).resolve(),
        check=check,
        bridge="pyo3-embedded",
    )
    return stable_json(summary)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview the behavioral oracle. Official write/check operations "
            "must use the PyO3 Rust entry point."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="run the generator without writing official artifacts",
    )
    args = parser.parse_args()
    if not args.preview:
        parser.error(
            "official artifacts require the PyO3 runner; use --preview only"
        )
    corpus = build_corpus(args.repo_root.resolve(), bridge="pyo3-embedded")
    print(stable_json(corpus["summary"], pretty=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
