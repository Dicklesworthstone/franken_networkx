#!/usr/bin/env python3
"""Generate docs/coverage.md from the live franken_networkx export surface.

The matrix is derived from ``franken_networkx.__all__`` so it reflects the
declared public API instead of a best-effort AST census of ``__init__.py``.

Classification rules:
  RUST_NATIVE   — public callables implemented in ``franken_networkx._fnx``
  PY_WRAPPER    — public Python callables without runtime NetworkX use
  NX_DELEGATED  — public Python callables that import or call NetworkX
  CLASS         — public classes, exceptions, and iterator types
  CONSTANT      — public non-callable values such as ``config`` or ``__version__``
"""

from __future__ import annotations

import argparse
import ast
import difflib
import inspect
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs/coverage.md"
CATEGORY_ORDER = ("RUST_NATIVE", "PY_WRAPPER", "NX_DELEGATED", "CLASS", "CONSTANT")
RUNTIME_ROUTE_ORDER = (
    "RUST_NATIVE",
    "PY_WRAPPER",
    "NETWORKX_HELPER",
    "DIRECT_NETWORKX",
    "CLASS",
    "CONSTANT",
)
NETWORKX_NAMES = {"networkx", "nx", "_nx"}
PARITY_HELPER_NAMES = {
    "_call_networkx_for_parity",
    "_call_networkx_submodule_for_parity",
}
PERFORMANCE_ROUTE_PROBES = (
    {
        "metric_id": "shortest_path",
        "export": "shortest_path",
        "shape": "unweighted source-target grid graph",
        "expected_route": "RUST_NATIVE",
        "evidence": "artifacts/perf/slo_thresholds.json",
    },
    {
        "metric_id": "shortest_path_weighted_delegated",
        "export": "shortest_path",
        "shape": "path graph with non-unit `weight` edge attributes",
        "expected_route": "NETWORKX_HELPER",
        "evidence": "artifacts/perf/slo_thresholds.json",
    },
)


def load_public_exports():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "python"))
    import franken_networkx as fnx  # pylint: disable=import-outside-toplevel

    duplicates = []
    seen = set()
    ordered_names = []
    for name in fnx.__all__:
        if name in seen:
            duplicates.append(name)
            continue
        seen.add(name)
        ordered_names.append(name)
    exports = []
    missing = []
    for name in ordered_names:
        try:
            exports.append((name, getattr(fnx, name)))
        except AttributeError:
            missing.append(name)
    if missing:
        joined = ", ".join(sorted(missing))
        raise RuntimeError(f"Names declared in __all__ but missing at runtime: {joined}")
    return exports, sorted(set(duplicates))


def _literal_string(node) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return "<dynamic>"


def inspect_runtime_use(obj) -> dict:
    """Return source-level runtime-routing evidence for a public callable."""
    try:
        source = inspect.getsource(obj)
    except (OSError, TypeError):
        return {"direct_networkx": False, "helper_calls": []}

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return {"direct_networkx": False, "helper_calls": []}

    aliases = set()
    direct_networkx = False
    helper_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "networkx":
                    aliases.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "networkx":
                aliases.add("networkx")
                for alias in node.names:
                    aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in PARITY_HELPER_NAMES:
                target_arg_index = (
                    1 if node.func.id == "_call_networkx_submodule_for_parity" else 0
                )
                helper_calls.append(
                    {
                        "helper": node.func.id,
                        "target": _literal_string(node.args[target_arg_index])
                        if len(node.args) > target_arg_index
                        else "<dynamic>",
                    }
                )
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id in (NETWORKX_NAMES | aliases):
                direct_networkx = True
        elif isinstance(node, ast.Name):
            if node.id in aliases:
                direct_networkx = True
    return {"direct_networkx": direct_networkx, "helper_calls": helper_calls}


def uses_networkx_runtime(obj) -> bool:
    """Return True when the function source directly imports or references NetworkX."""
    return bool(inspect_runtime_use(obj)["direct_networkx"])


def classify_export(obj) -> str:
    if inspect.isclass(obj):
        return "CLASS"
    if not (inspect.isbuiltin(obj) or inspect.isfunction(obj)):
        return "CONSTANT"

    module_name = getattr(obj, "__module__", "") or ""
    if module_name == "franken_networkx._fnx":
        return "RUST_NATIVE"
    if inspect.isfunction(obj) and uses_networkx_runtime(obj):
        return "NX_DELEGATED"
    return "PY_WRAPPER"


def analyze_export(name, obj) -> dict:
    category = classify_export(obj)
    module_name = getattr(obj, "__module__", type(obj).__module__)
    if inspect.isfunction(obj):
        runtime_use = inspect_runtime_use(obj)
    else:
        runtime_use = {
            "direct_networkx": False,
            "helper_calls": [],
        }

    if category == "RUST_NATIVE":
        runtime_route = "RUST_NATIVE"
    elif category in {"CLASS", "CONSTANT"}:
        runtime_route = category
    elif runtime_use["helper_calls"]:
        runtime_route = "NETWORKX_HELPER"
    elif runtime_use["direct_networkx"]:
        runtime_route = "DIRECT_NETWORKX"
    else:
        runtime_route = "PY_WRAPPER"

    return {
        "name": name,
        "category": category,
        "runtime_route": runtime_route,
        "module": module_name,
        "helper_calls": runtime_use["helper_calls"],
        "direct_networkx": runtime_use["direct_networkx"],
    }


def render_markdown(exports, duplicates) -> str:
    categorized = defaultdict(list)
    runtime_routes = defaultdict(list)
    module_counts = Counter()
    analyses = [analyze_export(name, obj) for name, obj in exports]

    for analysis in analyses:
        categorized[analysis["category"]].append(analysis["name"])
        runtime_routes[analysis["runtime_route"]].append(analysis)
        module_counts[analysis["module"]] += 1

    total = len(exports)
    helper_call_count = sum(len(row["helper_calls"]) for row in analyses)
    lines = [
        "# FrankenNetworkX Coverage Matrix",
        "",
        "*Auto-generated by `scripts/generate_coverage_matrix.py` from `franken_networkx.__all__` — do not edit manually.*",
        "",
        "## Summary",
        "",
        "| Category | Count | % | Rule |",
        "|----------|-------|---|------|",
        f"| RUST_NATIVE | {len(categorized['RUST_NATIVE'])} | {len(categorized['RUST_NATIVE'])*100//max(total,1)}% | native extension exports from `franken_networkx._fnx` |",
        f"| PY_WRAPPER | {len(categorized['PY_WRAPPER'])} | {len(categorized['PY_WRAPPER'])*100//max(total,1)}% | Python-defined exports with no runtime NetworkX dependency detected |",
        f"| NX_DELEGATED | {len(categorized['NX_DELEGATED'])} | {len(categorized['NX_DELEGATED'])*100//max(total,1)}% | Python-defined exports that import or call NetworkX at runtime |",
        f"| CLASS | {len(categorized['CLASS'])} | {len(categorized['CLASS'])*100//max(total,1)}% | public classes, exceptions, iterators |",
        f"| CONSTANT | {len(categorized['CONSTANT'])} | {len(categorized['CONSTANT'])*100//max(total,1)}% | public non-callable values |",
        f"| **Total public exports** | **{total}** | | unique names from `franken_networkx.__all__` |",
        "",
        "All declared public exports are classified. `--check` fails if this generated report drifts from the live module surface.",
        "",
        "## Runtime Route Ledger",
        "",
        "This ledger separates the broad public-export category from source-visible runtime routing. A public Python wrapper can stay `PY_WRAPPER` while still containing argument-shape branches that call NetworkX through parity helpers.",
        "",
        "| Runtime route | Exports | Helper call sites | Rule |",
        "|---------------|---------|-------------------|------|",
    ]
    route_rules = {
        "RUST_NATIVE": "native extension export from `franken_networkx._fnx`",
        "PY_WRAPPER": "Python-defined export with no visible NetworkX route",
        "NETWORKX_HELPER": "Python-defined export with `_call_networkx_*_for_parity(...)` branches",
        "DIRECT_NETWORKX": "Python-defined export that directly imports or calls NetworkX",
        "CLASS": "public classes, exceptions, iterators",
        "CONSTANT": "public non-callable values",
    }
    for route in RUNTIME_ROUTE_ORDER:
        helper_sites = (
            sum(len(row["helper_calls"]) for row in runtime_routes[route])
            if route == "NETWORKX_HELPER"
            else 0
        )
        lines.append(
            f"| {route} | {len(runtime_routes[route])} | {helper_sites} | {route_rules[route]} |"
        )
    lines.extend(
        [
            "",
            f"`NETWORKX_HELPER` currently covers {len(runtime_routes['NETWORKX_HELPER'])} public export(s) and {helper_call_count} parity-helper call site(s).",
            "",
            "## Performance Route Probes",
            "",
            "| Metric / probe | Public function | Representative argument shape | Expected route | Gate evidence |",
            "|----------------|-----------------|-------------------------------|----------------|---------------|",
        ]
    )
    for probe in PERFORMANCE_ROUTE_PROBES:
        lines.append(
            "| `{metric_id}` | `{export}` | {shape} | {expected_route} | `{evidence}` |".format(
                **probe
            )
        )
    lines.extend(
        [
            "",
            "## NetworkX Helper Delegations",
            "",
            "| Export | Helper call sites | NetworkX target(s) |",
            "|--------|-------------------|--------------------|",
        ]
    )
    for analysis in sorted(
        runtime_routes["NETWORKX_HELPER"],
        key=lambda row: row["name"],
    ):
        targets = sorted({call["target"] for call in analysis["helper_calls"]})
        rendered_targets = ", ".join(f"`{target}`" for target in targets)
        lines.append(
            f"| `{analysis['name']}` | {len(analysis['helper_calls'])} | {rendered_targets} |"
        )
    lines.append("")

    if duplicates:
        lines.extend(
            [
                "## Duplicate `__all__` Entries",
                "",
                f"The live module currently declares {len(duplicates)} duplicate name(s) in `__all__`. The matrix deduplicates them before counting the public surface.",
                "",
            ]
        )
        for name in duplicates:
            lines.append(f"- `{name}`")
        lines.append("")

    lines.extend(
        [
        "## Module Breakdown",
        "",
        "| Module | Count |",
        "|--------|-------|",
        ]
    )
    for module_name, count in sorted(module_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{module_name}` | {count} |")

    for category in CATEGORY_ORDER:
        names = sorted(categorized[category])
        lines.extend(["", f"## {category} exports ({len(names)})", ""])
        for name in names:
            lines.append(f"- `{name}`")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if docs/coverage.md is stale",
    )
    args = parser.parse_args()

    try:
        exports, duplicates = load_public_exports()
    except Exception as exc:  # pragma: no cover - exercised in CI on failure
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    rendered = render_markdown(exports, duplicates)
    existing = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""

    if args.check:
        if existing != rendered:
            diff = "".join(
                difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    rendered.splitlines(keepends=True),
                    fromfile=str(OUT_PATH),
                    tofile=f"{OUT_PATH} (regenerated)",
                )
            )
            print(diff or f"{OUT_PATH} is stale", file=sys.stderr)
            return 1
        print(f"{OUT_PATH} is up to date")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rendered, encoding="utf-8")

    counts = Counter(classify_export(obj) for _, obj in exports)
    print(f"Generated {OUT_PATH} with {len(exports)} unique exports classified")
    if duplicates:
        print(f"  duplicate __all__ entries skipped: {len(duplicates)}")
    for category in CATEGORY_ORDER:
        print(f"  {category}: {counts[category]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
