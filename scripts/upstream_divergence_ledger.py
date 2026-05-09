"""br-r37-c1-hchj7: unified upstream-divergence ledger.

Walks the codebase plus the artifacts produced by sibling audits
(`raw_vs_public_audit`, `api_ergonomics_audit`, `delegation_ledger`)
and aggregates every observable nx-divergence point into a single
ledger with five rows per public function:

- **native-parity**: Rust-native execution, results match nx.
- **wrapper-patched**: Python wrapper post-processes raw output to
  match nx (sort, type-coerce, ordering normalization).
- **intentionally-delegated**: AST-visible parity helper or direct
  NetworkX route — e.g. weighted Floyd-Warshall.
- **raw-known-gap**: lower-level raw kernel has a documented parity
  gap; public wrapper hides via fallback.
- **owner-acknowledged-limitation**: divergence is intentional /
  documented as out-of-scope; wrapper does not pretend parity.

Sources combined:

1. Static AST scan of ``python/franken_networkx/__init__.py`` (which
   already classifies wrappers as rust-native, mixed-route,
   nx-fallback, etc. — feeds into the ledger from
   ``delegation_ledger.json``).
2. Markers in source code: ``"KNOWN GAP"`` comments in Rust crates,
   ``br-r37-c1-*`` bug-tag references with surrounding context.
3. Findings from ``raw_vs_public_audit.json`` (per-fixture mismatch
   classifications).
4. Recent closed beads from ``.beads/issues.jsonl`` matching
   public function names — surfaces past divergence work.

Output:

- ``docs/upstream_divergence_ledger.md`` — Markdown summary.
- ``docs/upstream_divergence_ledger.json`` — full ledger.

Usage::

    python3 scripts/upstream_divergence_ledger.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

CATEGORIES = (
    "native-parity",
    "wrapper-patched",
    "intentionally-delegated",
    "raw-known-gap",
    "owner-acknowledged-limitation",
)

CATEGORY_LEGEND = {
    "native-parity": (
        "Rust-native execution; output matches NetworkX byte-for-byte"
    ),
    "wrapper-patched": (
        "Python wrapper post-processes raw output (sort, type-coerce, etc.) "
        "so the user-visible result matches NetworkX"
    ),
    "intentionally-delegated": (
        "Wrapper routes to NetworkX (via _call_networkx_for_parity) for some "
        "or all input shapes; not a Rust-native path"
    ),
    "raw-known-gap": (
        "Lower-level _raw_<X> kernel has a documented gap; public wrapper "
        "hides the divergence via fallback"
    ),
    "owner-acknowledged-limitation": (
        "Divergence is intentional / out-of-scope; documented in source"
    ),
}


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@dataclass
class LedgerEntry:
    name: str
    category: str
    source: str
    note: str = ""
    evidence: str = ""


def _load_delegation_ledger() -> tuple[dict[str, str], list[dict]]:
    path = DOCS_DIR / "delegation_ledger.json"
    if not path.exists():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    static_class = {entry["name"]: entry["classification"] for entry in payload.get("static", [])}
    runtime = payload.get("runtime", [])
    return static_class, runtime


def _load_raw_vs_public_audit() -> list[dict]:
    path = DOCS_DIR / "raw_vs_public_audit.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


KNOWN_GAP_RE = re.compile(
    r"//\s*KNOWN GAP[^\n]*\(([^)]+)\)[^\n]*",
    re.IGNORECASE,
)


def _scan_rust_known_gaps() -> list[tuple[str, str, str]]:
    """Yield (function_name, source_path, note) for ``KNOWN GAP`` markers
    in Rust crate source. Function name is best-effort: looks at the
    enclosing ``pub fn ...`` above the marker."""
    findings: list[tuple[str, str, str]] = []
    for crate_src in (REPO_ROOT / "crates").glob("*/src/*.rs"):
        try:
            text = crate_src.read_text(encoding="utf-8")
        except OSError:
            continue
        if "KNOWN GAP" not in text:
            continue
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            if "KNOWN GAP" not in line:
                continue
            # Find enclosing function.
            fn_name = "<unknown>"
            for prev_idx in range(idx, -1, -1):
                m = re.match(r"\s*pub fn\s+(\w+)", lines[prev_idx])
                if m:
                    fn_name = m.group(1)
                    break
            findings.append(
                (
                    fn_name,
                    str(crate_src.relative_to(REPO_ROOT)),
                    line.strip(),
                )
            )
    return findings


def _scan_python_intentional_delegation() -> list[tuple[str, str]]:
    """Find functions in __init__.py that contain only an
    `_call_networkx_for_parity` body (full delegation)."""
    init_path = REPO_ROOT / "python" / "franken_networkx" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    # Quick heuristic: walk function defs and look for direct return/yield-from
    # of _call_networkx_for_parity at the top level (not buried in a branch).
    fn_re = re.compile(
        r"^def\s+([a-zA-Z_]\w*)\s*\([^)]*\):\s*$",
        re.MULTILINE,
    )
    findings = []
    matches = list(fn_re.finditer(text))
    for i, m in enumerate(matches):
        name = m.group(1)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        # If the body contains ``_call_networkx_for_parity`` AND no
        # ``_raw_`` AND has only a return / yield-from statement, treat
        # as full delegation. Use simple scan (not AST) for speed.
        if (
            "_call_networkx_for_parity" in body
            and "_raw_" not in body
            and "_fnx." not in body
        ):
            # Tighter: look for "return _call_networkx" near top.
            if re.search(r"return\s+_call_networkx_for_parity", body):
                findings.append((name, "return-only delegation"))
    return findings


def _load_recent_closed_beads(limit_per_function: int = 1) -> dict[str, list[str]]:
    path = REPO_ROOT / ".beads" / "issues.jsonl"
    if not path.exists():
        return {}
    by_function: dict[str, list[str]] = defaultdict(list)
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") != "closed":
                continue
            title = rec.get("title", "")
            # Heuristic: extract a function-shaped token from title.
            for match in re.finditer(r"\b([a-z_][a-z0-9_]{2,})\b", title.lower()):
                token = match.group(1)
                if len(by_function[token]) < limit_per_function:
                    by_function[token].append(rec.get("id", "?") + ": " + title[:80])
    except OSError:
        pass
    return by_function


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def build_ledger() -> tuple[list[LedgerEntry], dict[str, dict]]:
    entries: list[LedgerEntry] = []
    summary: dict[str, dict] = {}

    static_class, runtime = _load_delegation_ledger()
    rvp = _load_raw_vs_public_audit()
    closed_beads = _load_recent_closed_beads()

    # 1. Native-parity: rust-native + rust-reexport with no contradictory
    #    audit finding.
    rvp_by_name = {row["name"]: row for row in rvp}
    for name, cls in sorted(static_class.items()):
        if cls in ("rust-reexport", "rust-native"):
            audit = rvp_by_name.get(name)
            if audit and audit["classification"] in (
                "wrapper-broken",
                "wrapper-misalign",
                "error-divergence",
            ):
                # Audit found a problem — categorize there instead.
                continue
            entries.append(
                LedgerEntry(
                    name=name,
                    category="native-parity",
                    source="static-classification",
                    note=f"static={cls}; raw-vs-public={(audit or {}).get('classification', 'unaudited')}",
                )
            )
        elif cls == "mixed-route":
            entries.append(
                LedgerEntry(
                    name=name,
                    category="intentionally-delegated",
                    source="static-classification",
                    note=f"mixed-route: wrapper has both _raw_<X> and parity-helper paths",
                )
            )
        elif cls == "nx-fallback":
            entries.append(
                LedgerEntry(
                    name=name,
                    category="intentionally-delegated",
                    source="static-classification",
                    note="wrapper calls _call_networkx_for_parity exclusively",
                )
            )

    # 2. Wrapper-patched: from raw-vs-public audit, "wrapper-corrected".
    for row in rvp:
        if row["classification"] == "wrapper-corrected":
            entries.append(
                LedgerEntry(
                    name=row["name"],
                    category="wrapper-patched",
                    source="raw-vs-public-audit",
                    note="raw output is post-processed by wrapper to match nx",
                    evidence="docs/raw_vs_public_audit.md",
                )
            )

    # 3. Raw-known-gap: from "KNOWN GAP" markers in Rust crates.
    for fn_name, src, comment in _scan_rust_known_gaps():
        entries.append(
            LedgerEntry(
                name=fn_name,
                category="raw-known-gap",
                source=f"rust-source-comment ({src})",
                note=comment[:200],
                evidence=src,
            )
        )

    # 4. Owner-acknowledged-limitation: bead-tagged annotations of the
    #    form "raw-known-gap" but routed through wrapper. These are
    #    known and expected to remain until an upstream port lands.
    #    The Rust scan catches the source side; here we cross-reference
    #    closed beads that mention the function name + "known gap".
    for fn_name, src, comment in _scan_rust_known_gaps():
        bead_hits = closed_beads.get(fn_name, [])
        for hit in bead_hits:
            entries.append(
                LedgerEntry(
                    name=fn_name,
                    category="owner-acknowledged-limitation",
                    source="closed-bead",
                    note=hit[:200],
                )
            )

    # Build summary keyed by function name.
    for entry in entries:
        bucket = summary.setdefault(
            entry.name,
            {cat: [] for cat in CATEGORIES},
        )
        bucket[entry.category].append({
            "source": entry.source,
            "note": entry.note,
            "evidence": entry.evidence,
        })

    return entries, summary


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def write_markdown(entries: list[LedgerEntry], summary: dict[str, dict], path: Path) -> None:
    counts = Counter(e.category for e in entries)
    lines = [
        "# FrankenNetworkX Upstream Divergence Ledger",
        "",
        "*Auto-generated by `scripts/upstream_divergence_ledger.py` (br-r37-c1-hchj7).*",
        "",
        "Combines static AST analysis (`docs/delegation_ledger.json`), per-fixture "
        "audit findings (`docs/raw_vs_public_audit.json`), Rust source `KNOWN GAP` "
        "markers, and closed bead history into a single per-function divergence "
        "table.",
        "",
        "## Summary",
        "",
        "| category | count | meaning |",
        "|----------|-------|---------|",
    ]
    for cat in CATEGORIES:
        lines.append(f"| `{cat}` | {counts.get(cat, 0)} | {CATEGORY_LEGEND[cat]} |")
    lines.append("")

    # Per-category tables.
    by_cat: dict[str, list[LedgerEntry]] = defaultdict(list)
    for e in entries:
        by_cat[e.category].append(e)

    for cat in CATEGORIES:
        lines.append(f"## {cat} ({len(by_cat[cat])})")
        lines.append("")
        if not by_cat[cat]:
            lines.append("_No entries._")
            lines.append("")
            continue
        if cat == "native-parity" and len(by_cat[cat]) > 50:
            # Compact list for the dominant bucket.
            names = sorted({e.name for e in by_cat[cat]})
            lines.append(", ".join(f"`{n}`" for n in names))
            lines.append("")
            continue

        lines.append("| function | source | note |")
        lines.append("|----------|--------|------|")
        for e in sorted(by_cat[cat], key=lambda x: (x.name, x.source)):
            note = e.note.replace("|", "\\|")
            lines.append(f"| `{e.name}` | {e.source} | {note} |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json(entries: list[LedgerEntry], summary: dict[str, dict], path: Path) -> None:
    payload = {
        "entries": [
            {
                "name": e.name,
                "category": e.category,
                "source": e.source,
                "note": e.note,
                "evidence": e.evidence,
            }
            for e in entries
        ],
        "summary": summary,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    entries, summary = build_ledger()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_markdown(entries, summary, out_dir / "upstream_divergence_ledger.md")
    write_json(entries, summary, out_dir / "upstream_divergence_ledger.json")

    if not args.quiet:
        counts = Counter(e.category for e in entries)
        print(f"Ledger entries: {len(entries)} across {len(summary)} unique functions")
        for cat in CATEGORIES:
            print(f"  {cat:35s} {counts.get(cat, 0):>5}")
        print(f"\nWrote {out_dir / 'upstream_divergence_ledger.md'}")
        print(f"Wrote {out_dir / 'upstream_divergence_ledger.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
