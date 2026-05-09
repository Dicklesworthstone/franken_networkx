"""br-r37-c1-256q5: per-function delegation ledger.

For every public name in ``franken_networkx.__all__``, classify the
execution path the wrapper takes by combining:

- **AST classification** (static): does the function body reference
  ``_call_networkx_for_parity`` / ``_call_networkx_submodule_for_parity``?
  Does it reference a ``_raw_<X>`` Rust binding? Is it a direct
  ``_fnx`` re-export? This determines the *shape* of the wrapper.

- **Runtime instrumentation** (dynamic): for a curated list of
  shape-sensitive functions (shortest-path, max-flow, etc.), invoke
  the wrapper on representative argument shapes (unweighted graph,
  weighted graph created with kwargs, weighted graph mutated
  post-creation) and observe whether ``_call_networkx_for_parity`` or
  a ``_raw_<X>`` binding is the one that actually executed.

Combined output:

- ``docs/delegation_ledger.md`` — Markdown summary table.
- ``docs/delegation_ledger.json`` — full per-function data.

The bead motivation: ``docs/coverage.md`` previously claimed
``NX_DELEGATED=0`` despite many runtime fallbacks via shared parity
helpers; this ledger surfaces the actual mix of Rust-native, Python
wrapper, and NetworkX fallback executions.

Usage::

    python3 scripts/delegation_ledger.py
"""

from __future__ import annotations

import argparse
import ast
import functools
import inspect
import json
import sys
import textwrap
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
INIT_PATH = REPO_ROOT / "python" / "franken_networkx" / "__init__.py"

PARITY_HELPER_NAMES = {
    "_call_networkx_for_parity",
    "_call_networkx_submodule_for_parity",
}


# ---------------------------------------------------------------------------
# AST classification
# ---------------------------------------------------------------------------


@dataclass
class StaticInfo:
    name: str
    is_rust_reexport: bool = False
    calls_parity_helper: bool = False
    calls_raw_rust: bool = False
    raw_rust_targets: list[str] = field(default_factory=list)
    body_lines: int = 0


def _gather_static() -> dict[str, StaticInfo]:
    """Walk ``__init__.py``, returning per-public-name static info."""
    source = INIT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    public_assignments: set[str] = set()
    info: dict[str, StaticInfo] = {}

    # Track assignments like ``foo = _fnx.foo`` and ``foo = _fnx_foo`` —
    # these are zero-cost Rust re-exports.
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "_fnx"
            ):
                public_assignments.add(node.targets[0].id)
        elif isinstance(node, ast.ImportFrom):
            if node.module and "_fnx" in node.module:
                for alias in node.names:
                    public_assignments.add(alias.asname or alias.name)

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        si = StaticInfo(
            name=name,
            is_rust_reexport=False,
            body_lines=getattr(node, "end_lineno", node.lineno) - node.lineno,
        )
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                fn_name = sub.func.id
                if fn_name in PARITY_HELPER_NAMES:
                    si.calls_parity_helper = True
                if fn_name.startswith("_raw_"):
                    si.calls_raw_rust = True
                    si.raw_rust_targets.append(fn_name)
        info[name] = si

    for name in public_assignments:
        if name not in info:
            info[name] = StaticInfo(name=name, is_rust_reexport=True)

    return info


def _classify_static(si: StaticInfo) -> str:
    if si.is_rust_reexport:
        return "rust-reexport"
    if si.calls_raw_rust and not si.calls_parity_helper:
        return "rust-native"
    if si.calls_raw_rust and si.calls_parity_helper:
        return "mixed-route"
    if si.calls_parity_helper:
        return "nx-fallback"
    return "py-wrapper"


# ---------------------------------------------------------------------------
# Runtime instrumentation
# ---------------------------------------------------------------------------


@dataclass
class RuntimeProbe:
    name: str
    shape_id: str
    raw_called: list[str] = field(default_factory=list)
    parity_called_with_target: list[str] = field(default_factory=list)
    error: str | None = None
    classification: str = "uninstrumented"


def _make_unweighted_path_5():
    return fnx.path_graph(5), 0, 4


def _make_weighted_path_5_kwargs():
    g = fnx.Graph()
    for i in range(4):
        g.add_edge(i, i + 1, weight=i + 1.5)
    return g, 0, 4


def _make_weighted_path_5_postmut():
    g = fnx.path_graph(5)
    for i, (u, v) in enumerate(g.edges):
        g[u][v]["weight"] = i + 1.5
    return g, 0, 4


# Shape-sensitive wrappers we want to profile. Each entry is
# (wrapper-name, list of (shape-id, builder, args, kwargs)).
RUNTIME_SPECS: list[tuple[str, list[tuple[str, Callable, tuple, dict]]]] = [
    (
        "single_source_dijkstra_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source",), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source",), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source",), {}),
        ],
    ),
    (
        "single_source_bellman_ford_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source",), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source",), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source",), {}),
        ],
    ),
    (
        "astar_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source", "target"), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source", "target"), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source", "target"), {}),
        ],
    ),
    (
        "shortest_path_length",
        [
            ("path-5-unweighted", _make_unweighted_path_5, ("source", "target"), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, ("source", "target"), {"weight": "weight"}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, ("source", "target"), {"weight": "weight"}),
        ],
    ),
    (
        "floyd_warshall",
        [
            ("path-5-unweighted", _make_unweighted_path_5, (), {}),
            ("path-5-weighted-kwargs", _make_weighted_path_5_kwargs, (), {}),
            ("path-5-weighted-postmut", _make_weighted_path_5_postmut, (), {}),
        ],
    ),
]


class _Tracer:
    """Wraps `_call_networkx_for_parity` and every `_raw_<X>` to record
    invocations during a single `_observe_call` window."""

    def __init__(self):
        self.parity_targets: list[str] = []
        self.raw_targets: list[str] = []
        self._patched: list[tuple[Any, str, Any]] = []

    def install(self):
        original_parity = fnx._call_networkx_for_parity

        def _parity_wrap(name, *args, **kwargs):
            self.parity_targets.append(name)
            return original_parity(name, *args, **kwargs)

        fnx._call_networkx_for_parity = _parity_wrap
        self._patched.append((fnx, "_call_networkx_for_parity", original_parity))

        for attr in dir(fnx):
            if not attr.startswith("_raw_"):
                continue
            target = getattr(fnx, attr)
            if not callable(target):
                continue
            self._patch_raw(attr, target)

    def _patch_raw(self, attr: str, target: Callable):
        @functools.wraps(target)
        def _wrap(*args, **kwargs):
            self.raw_targets.append(attr)
            return target(*args, **kwargs)

        # Some _raw_* are PyO3 builtins which don't accept @wraps.
        # Catch the AttributeError and fall back to a plain wrapper.
        try:
            wrapped = _wrap
            wrapped.__wrapped__ = target
        except (AttributeError, TypeError):
            def wrapped(*args, **kwargs):
                self.raw_targets.append(attr)
                return target(*args, **kwargs)

        setattr(fnx, attr, wrapped)
        self._patched.append((fnx, attr, target))

    def restore(self):
        for obj, name, original in self._patched:
            setattr(obj, name, original)
        self._patched.clear()


def _run_runtime_probes() -> list[RuntimeProbe]:
    probes: list[RuntimeProbe] = []
    for fname, shapes in RUNTIME_SPECS:
        wrapper = getattr(fnx, fname, None)
        if wrapper is None:
            continue
        for shape_id, builder, arg_keys, kwargs in shapes:
            try:
                graph, *extras = builder()
            except Exception as exc:
                probes.append(
                    RuntimeProbe(
                        name=fname,
                        shape_id=shape_id,
                        error=f"build: {type(exc).__name__}: {exc}",
                    )
                )
                continue

            arg_map = {"source": extras[0] if extras else None,
                       "target": extras[1] if len(extras) > 1 else None}
            try:
                args = [arg_map[key] for key in arg_keys]
            except KeyError:
                args = []

            tracer = _Tracer()
            tracer.install()
            try:
                wrapper(graph, *args, **kwargs)
                err = None
            except Exception as exc:
                err = f"call: {type(exc).__name__}: {exc}"
            finally:
                tracer.restore()

            probe = RuntimeProbe(
                name=fname,
                shape_id=shape_id,
                raw_called=list(tracer.raw_targets),
                parity_called_with_target=list(tracer.parity_targets),
                error=err,
            )
            if err is not None:
                probe.classification = "error"
            elif probe.parity_called_with_target and probe.raw_called:
                probe.classification = "mixed (nx-fallback after raw try)"
            elif probe.parity_called_with_target:
                probe.classification = "nx-fallback"
            elif probe.raw_called:
                probe.classification = "rust-native"
            else:
                probe.classification = "py-wrapper-only"
            probes.append(probe)
    return probes


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_markdown(
    static: dict[str, StaticInfo],
    runtime: list[RuntimeProbe],
    path: Path,
) -> None:
    counts = Counter(_classify_static(si) for si in static.values())
    public = sorted(getattr(fnx, "__all__", []))

    lines = [
        "# FrankenNetworkX Delegation Ledger",
        "",
        "*Auto-generated by `scripts/delegation_ledger.py` (br-r37-c1-256q5).*",
        "",
        "## Static AST classification",
        "",
        "Counts derived from `python/franken_networkx/__init__.py` AST. "
        "Categories:",
        "",
        "- `rust-reexport`: assigned directly from `_fnx.<name>` — zero Python overhead.",
        "- `rust-native`: wrapper calls a `_raw_<X>` binding without any parity-helper fallback.",
        "- `mixed-route`: wrapper has both a `_raw_<X>` path and a parity-helper path (gates by input shape).",
        "- `nx-fallback`: wrapper calls `_call_networkx_for_parity` and never reaches a `_raw_<X>` binding.",
        "- `py-wrapper`: pure-Python wrapper; no parity helper, no raw binding (e.g. orchestrators or trivial helpers).",
        "",
        "| classification | count |",
        "|----------------|-------|",
    ]
    for cls, n in sorted(counts.items()):
        lines.append(f"| `{cls}` | {n} |")
    lines.append("")

    lines.append("## Runtime probe results")
    lines.append("")
    lines.append(
        "Per-(function, shape) instrumentation. Wraps `_call_networkx_for_parity` "
        "and every `_raw_<X>` to record which path actually executed, eliminating "
        "the static-AST blind spot called out in the cvrij/256q5 modes-of-reasoning "
        "reports."
    )
    lines.append("")
    lines.append(
        "| function | shape | classification | raw bindings used | nx fallbacks |"
    )
    lines.append("|----------|-------|----------------|-------------------|--------------|")
    for probe in runtime:
        raw_str = ", ".join(f"`{x}`" for x in probe.raw_called) or "—"
        nx_str = ", ".join(f"`{x}`" for x in probe.parity_called_with_target) or "—"
        lines.append(
            f"| `{probe.name}` | `{probe.shape_id}` | `{probe.classification}` | "
            f"{raw_str} | {nx_str} |"
        )
    lines.append("")

    # Per-function static breakdown table
    lines.append("## Per-function static classification")
    lines.append("")
    lines.append("| name | classification | calls_parity_helper | raw_targets |")
    lines.append("|------|----------------|--------------------|-------------|")
    for name in public:
        si = static.get(name)
        if si is None:
            cls = "untracked"
            parity = ""
            raw = ""
        else:
            cls = _classify_static(si)
            parity = "yes" if si.calls_parity_helper else "no"
            raw = ", ".join(f"`{t}`" for t in sorted(set(si.raw_rust_targets))) or "—"
        lines.append(f"| `{name}` | `{cls}` | {parity} | {raw} |")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(
    static: dict[str, StaticInfo],
    runtime: list[RuntimeProbe],
    path: Path,
) -> None:
    out = {
        "static": [
            {
                "name": si.name,
                "classification": _classify_static(si),
                "is_rust_reexport": si.is_rust_reexport,
                "calls_parity_helper": si.calls_parity_helper,
                "calls_raw_rust": si.calls_raw_rust,
                "raw_rust_targets": sorted(set(si.raw_rust_targets)),
                "body_lines": si.body_lines,
            }
            for name, si in sorted(static.items())
        ],
        "runtime": [
            {
                "name": probe.name,
                "shape": probe.shape_id,
                "classification": probe.classification,
                "raw_called": probe.raw_called,
                "parity_called_with_target": probe.parity_called_with_target,
                "error": probe.error,
            }
            for probe in runtime
        ],
    }
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=DOCS_DIR, help="output directory"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress stdout summary"
    )
    args = parser.parse_args(argv)

    static = _gather_static()
    runtime = _run_runtime_probes()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(static, runtime, out_dir / "delegation_ledger.md")
    write_json(static, runtime, out_dir / "delegation_ledger.json")

    if not args.quiet:
        counts = Counter(_classify_static(si) for si in static.values())
        print(f"Static: {sum(counts.values())} top-level wrappers in __init__.py")
        for cls, n in sorted(counts.items()):
            print(f"  {cls:20s} {n:>5}")
        rt_counts = Counter(p.classification for p in runtime)
        print(f"\nRuntime: {len(runtime)} (function, shape) probes")
        for cls, n in sorted(rt_counts.items()):
            print(f"  {cls:35s} {n:>4}")
        print(f"\nWrote {out_dir / 'delegation_ledger.md'}")
        print(f"Wrote {out_dir / 'delegation_ledger.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
