"""br-r37-c1-zcbtx: API-ergonomics signature delta report.

For every name re-exported through ``franken_networkx.__all__`` that
also exists at the top of ``networkx.*``, compare the two signatures
(``inspect.signature``) and classify any difference as one of:

- **identical**: parameter names, defaults, kinds match exactly.
- **kwarg-superset**: fnx has additional keyword params beyond nx
  (typically ``backend``/``backend_kwargs`` — neutral / friendly).
- **missing-keyword**: fnx is missing a keyword param that nx has
  (potential drop-in friction — users passing the kwarg break).
- **default-drift**: same name, different default value.
- **kind-drift**: same name, different kind (positional-only vs
  keyword-only, etc.).
- **positional-mismatch**: positional argument names or counts diverge.
- **builtin-no-signature**: one or both is a builtin without an
  introspectable signature (PyO3 binding) — manual review.

The report is written to ``docs/api_ergonomics_audit.md`` with a
side-by-side table per category, plus a top-N priority list of
high-traffic missing-keyword cases (read/write/conversion family).

Usage::

    python3 scripts/api_ergonomics_audit.py
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import franken_networkx as fnx
import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

# High-traffic IO / conversion / parsing families — when one of these has
# a missing-keyword finding, surface it on the priority list.
HIGH_TRAFFIC_PREFIXES = (
    "read_",
    "write_",
    "from_",
    "to_",
    "parse_",
    "generate_",
)


@dataclass
class ParamSpec:
    name: str
    kind: str
    default: Any | None
    has_default: bool

    @classmethod
    def from_param(cls, p: inspect.Parameter) -> "ParamSpec":
        return cls(
            name=p.name,
            kind=p.kind.name,
            default=None if p.default is inspect.Parameter.empty else _stringify(p.default),
            has_default=p.default is not inspect.Parameter.empty,
        )


def _stringify(value: Any) -> Any:
    """Return a comparable, JSON-safe form of a default value.

    Types and callables compare by ``__name__`` rather than ``repr``
    so that fnx's own ``Graph`` class default does not flag a drift
    against nx's ``Graph`` (and similarly for module-level helpers
    like ``no_filter`` that differ only by which module imported them).
    """
    if isinstance(value, (int, float, str, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_stringify(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _stringify(v) for k, v in value.items()}
    if isinstance(value, type):
        return f"<class:{value.__name__}>"
    if callable(value):
        return f"<callable:{getattr(value, '__name__', repr(value))}>"
    return repr(value)


@dataclass
class FuncDelta:
    name: str
    fnx_signature: str | None = None
    nx_signature: str | None = None
    classification: str = "unclassified"
    deltas: list[str] = field(default_factory=list)
    fnx_params: list[ParamSpec] = field(default_factory=list)
    nx_params: list[ParamSpec] = field(default_factory=list)


def _try_signature(fn) -> inspect.Signature | None:
    try:
        return inspect.signature(fn)
    except (TypeError, ValueError):
        return None


def _classify(
    fnx_sig: inspect.Signature,
    nx_sig: inspect.Signature,
    fnx_params: list[ParamSpec],
    nx_params: list[ParamSpec],
) -> tuple[str, list[str]]:
    fnx_by_name = {p.name: p for p in fnx_params}
    nx_by_name = {p.name: p for p in nx_params}

    # Positional comparison (skip VAR_POSITIONAL / VAR_KEYWORD which we
    # treat as wildcards).
    def _positional(params):
        return [
            p
            for p in params
            if p.kind in ("POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD")
        ]

    fnx_pos = _positional(fnx_params)
    nx_pos = _positional(nx_params)

    deltas: list[str] = []
    has_positional_mismatch = False
    has_default_drift = False
    has_kind_drift = False

    if [p.name for p in fnx_pos] != [p.name for p in nx_pos]:
        # Allow leading exact match when fnx has fewer positional (treated as
        # missing-keyword if the extras are keyword-only on nx side).
        common = min(len(fnx_pos), len(nx_pos))
        for fp, np in zip(fnx_pos[:common], nx_pos[:common]):
            if fp.name != np.name:
                has_positional_mismatch = True
                deltas.append(
                    f"positional name mismatch at index {fnx_pos.index(fp)}: "
                    f"fnx={fp.name!r} nx={np.name!r}"
                )
                break
        if not has_positional_mismatch and len(fnx_pos) != len(nx_pos):
            has_positional_mismatch = True
            deltas.append(
                f"positional arity differs: fnx={len(fnx_pos)} ({[p.name for p in fnx_pos]}) "
                f"vs nx={len(nx_pos)} ({[p.name for p in nx_pos]})"
            )

    fnx_names = set(fnx_by_name)
    nx_names = set(nx_by_name)

    extra_in_fnx = sorted(fnx_names - nx_names)
    missing_in_fnx = sorted(nx_names - fnx_names)

    for name in missing_in_fnx:
        np = nx_by_name[name]
        deltas.append(
            f"missing in fnx: {name} (nx kind={np.kind}, default={np.default if np.has_default else 'NO_DEFAULT'})"
        )

    for name in extra_in_fnx:
        fp = fnx_by_name[name]
        deltas.append(
            f"extra in fnx: {name} (kind={fp.kind}, default={fp.default if fp.has_default else 'NO_DEFAULT'})"
        )

    for name in fnx_names & nx_names:
        fp = fnx_by_name[name]
        np = nx_by_name[name]
        if fp.has_default != np.has_default or fp.default != np.default:
            has_default_drift = True
            deltas.append(
                f"default drift on {name}: "
                f"fnx default={fp.default if fp.has_default else 'NO_DEFAULT'} "
                f"vs nx default={np.default if np.has_default else 'NO_DEFAULT'}"
            )
        if fp.kind != np.kind:
            has_kind_drift = True
            deltas.append(f"kind drift on {name}: fnx={fp.kind} nx={np.kind}")

    if not deltas:
        return "identical", []

    if has_positional_mismatch:
        return "positional-mismatch", deltas

    if missing_in_fnx and not extra_in_fnx and not has_default_drift and not has_kind_drift:
        return "missing-keyword", deltas
    if extra_in_fnx and not missing_in_fnx and not has_default_drift and not has_kind_drift:
        return "kwarg-superset", deltas
    if has_default_drift and not missing_in_fnx and not extra_in_fnx and not has_kind_drift:
        return "default-drift", deltas
    if has_kind_drift and not has_default_drift and not missing_in_fnx and not extra_in_fnx:
        return "kind-drift", deltas

    return "mixed", deltas


def run_audit() -> list[FuncDelta]:
    deltas: list[FuncDelta] = []
    for name in sorted(getattr(fnx, "__all__", [])):
        fnx_obj = getattr(fnx, name, None)
        nx_obj = getattr(nx, name, None)
        if fnx_obj is None or nx_obj is None:
            continue
        if not callable(fnx_obj) or not callable(nx_obj):
            continue
        # Skip classes — they have a different ergonomics surface (we
        # care about top-level function APIs, not __init__).
        if inspect.isclass(fnx_obj) or inspect.isclass(nx_obj):
            continue

        fnx_sig = _try_signature(fnx_obj)
        nx_sig = _try_signature(nx_obj)

        delta = FuncDelta(name=name)

        if fnx_sig is None or nx_sig is None:
            delta.classification = "builtin-no-signature"
            delta.fnx_signature = str(fnx_sig) if fnx_sig else "<no-introspectable-signature>"
            delta.nx_signature = str(nx_sig) if nx_sig else "<no-introspectable-signature>"
            deltas.append(delta)
            continue

        delta.fnx_signature = str(fnx_sig)
        delta.nx_signature = str(nx_sig)
        delta.fnx_params = [ParamSpec.from_param(p) for p in fnx_sig.parameters.values()]
        delta.nx_params = [ParamSpec.from_param(p) for p in nx_sig.parameters.values()]

        delta.classification, delta.deltas = _classify(
            fnx_sig, nx_sig, delta.fnx_params, delta.nx_params
        )
        deltas.append(delta)

    return deltas


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_markdown(deltas: list[FuncDelta], path: Path) -> None:
    by_class: dict[str, list[FuncDelta]] = {}
    for d in deltas:
        by_class.setdefault(d.classification, []).append(d)

    legend = {
        "identical": "fnx and nx signatures match exactly",
        "kwarg-superset": "fnx has extra keyword parameters beyond nx (usually `backend`/`backend_kwargs` — neutral)",
        "missing-keyword": "fnx is missing a keyword parameter that nx has (drop-in users may break)",
        "default-drift": "same parameter name on both sides, different default value",
        "kind-drift": "same parameter name, different kind (positional-only vs keyword-only)",
        "positional-mismatch": "positional argument names or arity diverge",
        "mixed": "multiple delta categories combine",
        "builtin-no-signature": "one or both lacks an introspectable signature; manual review",
    }

    lines = [
        "# API Ergonomics — Signature Delta Audit",
        "",
        "*Auto-generated by `scripts/api_ergonomics_audit.py` (br-r37-c1-zcbtx).*",
        "",
        f"Functions audited: **{len(deltas)}** (subset of `franken_networkx.__all__` "
        "where the same name resolves on the top-level `networkx` namespace).",
        "",
        "## Summary",
        "",
        "| classification | count | meaning |",
        "|----------------|-------|---------|",
    ]
    for cls in sorted(by_class):
        lines.append(f"| `{cls}` | {len(by_class[cls])} | {legend.get(cls, '')} |")
    lines.append("")

    # Priority list: high-traffic IO/conversion missing-keyword cases.
    priority: list[FuncDelta] = []
    for d in by_class.get("missing-keyword", []):
        if any(d.name.startswith(p) for p in HIGH_TRAFFIC_PREFIXES):
            priority.append(d)
    if priority:
        lines.append("## High-priority missing-keyword findings (IO / conversion family)")
        lines.append("")
        lines.append("These public APIs handle the most user-visible drop-in flows; "
                     "missing kwargs here are most likely to break adoption.")
        lines.append("")
        for d in priority:
            lines.append(f"- **`{d.name}`**")
            for delta in d.deltas:
                lines.append(f"  - {delta}")
        lines.append("")

    for cls in sorted(by_class):
        lines.append(f"## {cls} ({len(by_class[cls])})")
        lines.append("")
        if cls == "identical":
            # Just list the names — table-of-deltas would be empty.
            names = sorted(d.name for d in by_class[cls])
            lines.append(", ".join(f"`{n}`" for n in names))
            lines.append("")
            continue

        for d in sorted(by_class[cls], key=lambda x: x.name):
            lines.append(f"### `{d.name}`")
            lines.append("")
            lines.append(f"- fnx: `{d.fnx_signature}`")
            lines.append(f"- nx:  `{d.nx_signature}`")
            if d.deltas:
                lines.append("")
                for delta in d.deltas:
                    lines.append(f"  - {delta}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(deltas: list[FuncDelta], path: Path) -> None:
    out = []
    for d in deltas:
        out.append(
            {
                "name": d.name,
                "classification": d.classification,
                "fnx_signature": d.fnx_signature,
                "nx_signature": d.nx_signature,
                "deltas": d.deltas,
                "fnx_params": [
                    {
                        "name": p.name,
                        "kind": p.kind,
                        "default": p.default,
                        "has_default": p.has_default,
                    }
                    for p in d.fnx_params
                ],
                "nx_params": [
                    {
                        "name": p.name,
                        "kind": p.kind,
                        "default": p.default,
                        "has_default": p.has_default,
                    }
                    for p in d.nx_params
                ],
            }
        )
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DOCS_DIR,
        help="directory to write markdown and json reports",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress the per-class summary on stdout",
    )
    args = parser.parse_args(argv)

    deltas = run_audit()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(deltas, out_dir / "api_ergonomics_audit.md")
    write_json(deltas, out_dir / "api_ergonomics_audit.json")

    if not args.quiet:
        by_class: dict[str, int] = {}
        for d in deltas:
            by_class[d.classification] = by_class.get(d.classification, 0) + 1
        print(f"Audited {len(deltas)} functions.")
        for cls, count in sorted(by_class.items()):
            print(f"  {cls:30s} {count:>4}")
        print(f"\nWrote {out_dir / 'api_ergonomics_audit.md'}")
        print(f"Wrote {out_dir / 'api_ergonomics_audit.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
