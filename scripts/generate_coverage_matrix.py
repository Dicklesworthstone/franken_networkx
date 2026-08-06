#!/usr/bin/env python3
"""Generate docs/coverage.md from NetworkX 3.6.1 and FrankenNetworkX.

The FeatureUniverse is extracted in an isolated Python process from the pinned
``networkx==3.6.1`` package.  For the package root and every importable,
non-test module, the extractor uses ``__all__`` when present and otherwise
uses Python's public wildcard rule (module globals whose names do not begin
with ``_``).  The package ``__version__`` metadata item is included
explicitly.  Each qualified path is then compared with the corresponding
``franken_networkx`` path.

FeatureUniverse statuses:
  present   — binding kind and inspectable signature match
  partial   — binding exists, but its kind, signature, or value is incomplete
  missing   — corresponding FrankenNetworkX module or attribute is absent
  n/a       — comparison is not meaningful (currently package version identity)
  excluded  — namespace/test/support module; every row records the reason

The legacy implementation-route appendix is still derived from
``franken_networkx.__all__`` so it reflects the package's own declared root
exports rather than a best-effort AST census of ``__init__.py``.

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
import importlib
import inspect
import json
import re
import subprocess  # nosec B404 - fixed interpreter and repo-owned extractor
import sys
import textwrap
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs/coverage.md"
PINNED_NETWORKX_VERSION = "3.6.1"
FEATURE_EXTRACTION_TIMEOUT_SECONDS = 60
FEATURE_STATUS_ORDER = ("present", "partial", "missing", "n/a", "excluded")
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
DIVERGENCE_CATEGORY_ORDER = (
    "native-parity",
    "wrapper-patched",
    "intentionally-delegated",
    "raw-known-gap",
    "owner-acknowledged-limitation",
)
DIVERGENCE_CATEGORY_RULES = {
    "native-parity": "public Rust-native export; no Python fallback route detected",
    "wrapper-patched": "public wrapper records a compatibility repair over a lower-level gap",
    "intentionally-delegated": "AST-visible parity helper or direct NetworkX route",
    "raw-known-gap": "lower-level raw/native implementation has a documented parity gap",
    "owner-acknowledged-limitation": "documented limitation is intentionally owned until native repair",
}
DIVERGENCE_ANNOTATIONS = (
    {
        "category": "wrapper-patched",
        "export": "is_planar",
        "route": "PY_WRAPPER",
        "source": "bead:br-isplanarbroken",
        "evidence": "python/franken_networkx/__init__.py:br-isplanarbroken",
        "note": "public wrapper routes through check_planarity so K3,3/Petersen match NetworkX",
    },
    {
        "category": "raw-known-gap",
        "export": "_raw_is_planar",
        "route": "RUST_NATIVE",
        "source": "code:KNOWN GAP",
        "evidence": "crates/fnx-algorithms/src/lib.rs:KNOWN GAP",
        "note": "raw kernel still uses necessary edge-count bounds, not a complete LR planarity test",
    },
    {
        "category": "owner-acknowledged-limitation",
        "export": "_raw_is_planar",
        "route": "RUST_NATIVE",
        "source": "code:KNOWN GAP",
        "evidence": "crates/fnx-algorithms/src/lib.rs:KNOWN GAP",
        "note": "callers are directed to the public wrapper until Boyer-Myrvold/Hopcroft-Tarjan lands",
    },
)

_NETWORKX_SURFACE_EXTRACTOR = r"""
import hashlib
import importlib
import inspect
import json
import pkgutil
import re
import sys
from pathlib import Path

# br-r37-c1-9hnq3: this child runs under -I (isolated), which is what keeps
# FrankenNetworkX from patching the surface we are measuring — but -I also drops
# the USER site-packages, which is where networkx itself is installed, so
# ``import networkx`` raised ModuleNotFoundError and took 7 tests down with it.
# The parent passes the pinned networkx tree's location as argv[1]; add exactly
# that one directory and nothing else, so isolation still holds everywhere else.
sys.path.insert(0, sys.argv[1])

import networkx

EXPECTED_VERSION = "3.6.1"
if networkx.__version__ != EXPECTED_VERSION:
    raise RuntimeError(
        f"FeatureUniverse requires networkx=={EXPECTED_VERSION}; "
        f"loaded {networkx.__version__}"
    )

package_root = Path(networkx.__file__).resolve().parent
source_digest = hashlib.sha256()
for source_path in sorted(package_root.rglob("*.py")):
    relative_path = source_path.relative_to(package_root).as_posix()
    source_digest.update(relative_path.encode("utf-8"))
    source_digest.update(b"\0")
    source_digest.update(source_path.read_bytes())
    source_digest.update(b"\0")

module_infos = sorted(
    pkgutil.walk_packages(networkx.__path__, f"{networkx.__name__}."),
    key=lambda info: info.name,
)
included_module_names = [networkx.__name__]
excluded_modules = {}
for info in module_infos:
    relative_name = info.name.removeprefix(f"{networkx.__name__}.")
    parts = relative_name.split(".")
    if "tests" in parts:
        excluded_modules[info.name] = (
            "test-only module; not part of NetworkX's installed user API contract"
        )
    elif parts[-1] == "conftest":
        excluded_modules[info.name] = (
            "pytest support module; not part of NetworkX's user API contract"
        )
    elif any(part.startswith("_") for part in parts):
        excluded_modules[info.name] = (
            "private module path; a dotted component begins with `_`"
        )
    else:
        included_module_names.append(info.name)

modules = {networkx.__name__: networkx}
import_failures = []
for module_name in included_module_names[1:]:
    try:
        modules[module_name] = importlib.import_module(module_name)
    except Exception as exc:
        import_failures.append(
            {
                "module": module_name,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
if import_failures:
    raise RuntimeError(
        "Unable to import the complete pinned NetworkX public module set: "
        + json.dumps(import_failures, sort_keys=True)
    )


def object_kind(obj):
    if inspect.ismodule(obj):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if callable(obj):
        return "callable"
    return "constant"


def signature_text(obj):
    try:
        return re.sub(
            r" at 0x[0-9a-fA-F]+",
            "",
            str(inspect.signature(obj)),
        )
    except (TypeError, ValueError):
        return None


def stable_repr(obj):
    return re.sub(r" at 0x[0-9a-fA-F]+", "", repr(obj))


def type_name(obj):
    obj_type = type(obj)
    return f"{obj_type.__module__}.{obj_type.__qualname__}"


def member_kind(static_obj, resolved_obj):
    if isinstance(static_obj, property):
        return "property"
    if callable(resolved_obj):
        return "method"
    if hasattr(static_obj, "__get__"):
        return "descriptor"
    return "attribute"


rows = {}
namespace_reason = (
    "namespace container; its declared callable, class, and value members "
    "are enumerated as separate qualified FeatureUniverse rows"
)

rows[networkx.__name__] = {
    "path": networkx.__name__,
    "source_module": networkx.__name__,
    "name": networkx.__name__,
    "kind": "module",
    "object_module": networkx.__name__,
    "signature": None,
    "type_name": "builtins.module",
    "value_repr": None,
    "declared_by": "package root",
    "exclusion_reason": namespace_reason,
}
for info in module_infos:
    reason = excluded_modules.get(info.name, namespace_reason)
    rows[info.name] = {
        "path": info.name,
        "source_module": info.name.rpartition(".")[0],
        "name": info.name.rpartition(".")[2],
        "kind": "module",
        "object_module": info.name,
        "signature": None,
        "type_name": "builtins.module",
        "value_repr": None,
        "declared_by": "installed module inventory",
        "exclusion_reason": reason,
    }

for module_name in included_module_names:
    module = modules[module_name]
    if hasattr(module, "__all__"):
        declared_names = list(module.__all__)
        declared_by = f"{module_name}.__all__"
    else:
        declared_names = [
            name for name in vars(module) if not name.startswith("_")
        ]
        declared_by = f"{module_name} public module namespace"
    if module_name == networkx.__name__ and "__version__" not in declared_names:
        declared_names.append("__version__")

    for name in dict.fromkeys(declared_names):
        path = f"{module_name}.{name}"
        try:
            obj = getattr(module, name)
        except Exception as exc:
            rows[path] = {
                "path": path,
                "source_module": module_name,
                "name": name,
                "kind": "unresolved",
                "object_module": None,
                "signature": None,
                "type_name": None,
                "value_repr": None,
                "declared_by": declared_by,
                "reference_error": f"{type(exc).__name__}: {exc}",
                "exclusion_reason": None,
            }
            continue

        kind = object_kind(obj)
        exclusion_reason = (
            excluded_modules.get(path, namespace_reason)
            if kind == "module"
            else None
        )
        rows[path] = {
            "path": path,
            "source_module": module_name,
            "name": name,
            "kind": kind,
            "object_module": (
                obj.__name__
                if kind == "module"
                else getattr(obj, "__module__", type(obj).__module__)
            ),
            "signature": (
                signature_text(obj) if kind in {"callable", "class"} else None
            ),
            "type_name": type_name(obj),
            "value_repr": stable_repr(obj) if kind == "constant" else None,
            "declared_by": (
                "networkx package metadata"
                if path == "networkx.__version__"
                else declared_by
            ),
            "exclusion_reason": exclusion_reason,
        }

class_rows = [
    dict(row)
    for row in rows.values()
    if row["kind"] == "class" and not row.get("exclusion_reason")
]
for class_row in class_rows:
    owner = getattr(
        modules[class_row["source_module"]],
        class_row["name"],
    )
    for member_name in sorted(name for name in dir(owner) if not name.startswith("_")):
        declaring_class = next(
            (
                base
                for base in owner.__mro__
                if member_name in vars(base)
            ),
            None,
        )
        if declaring_class is None or not declaring_class.__module__.startswith(
            "networkx"
        ):
            continue
        static_member = inspect.getattr_static(owner, member_name)
        resolved_member = getattr(owner, member_name)
        kind = member_kind(static_member, resolved_member)
        path = f"{class_row['path']}.{member_name}"
        rows[path] = {
            "path": path,
            "source_module": class_row["source_module"],
            "name": member_name,
            "kind": kind,
            "object_module": declaring_class.__module__,
            "signature": (
                signature_text(resolved_member) if kind == "method" else None
            ),
            "type_name": type_name(static_member),
            "value_repr": (
                stable_repr(resolved_member) if kind == "attribute" else None
            ),
            "declared_by": (
                f"{declaring_class.__module__}."
                f"{declaring_class.__qualname__} class MRO"
            ),
            "exclusion_reason": None,
            "owner_source_module": class_row["source_module"],
            "owner_name": class_row["name"],
            "member_name": member_name,
        }

payload = {
    "networkx_version": networkx.__version__,
    "networkx_python_source_sha256": source_digest.hexdigest(),
    "discovered_module_count": len(module_infos),
    "included_module_count": len(included_module_names),
    "excluded_module_count": len(excluded_modules),
    "rows": [rows[path] for path in sorted(rows)],
}
print(json.dumps(payload, sort_keys=True))
"""


@lru_cache(maxsize=1)
def load_feature_universe_reference() -> dict:
    """Extract the pinned NetworkX surface without FrankenNetworkX patching it."""
    # br-r37-c1-9hnq3: locate the pinned networkx tree in THIS process (where it
    # is importable) and hand the child its parent directory. The child runs
    # isolated, so it cannot find networkx on its own.
    import networkx as _networkx_for_location

    networkx_site = str(
        Path(_networkx_for_location.__file__).resolve().parent.parent
    )
    try:
        completed = subprocess.run(  # nosec B603 - argv is fixed and shell is disabled
            [sys.executable, "-I", "-c", _NETWORKX_SURFACE_EXTRACTOR, networkx_site],
            check=False,
            capture_output=True,
            text=True,
            timeout=FEATURE_EXTRACTION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "NetworkX FeatureUniverse extraction timed out after "
            f"{FEATURE_EXTRACTION_TIMEOUT_SECONDS}s"
        ) from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"NetworkX FeatureUniverse extraction failed: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "NetworkX FeatureUniverse extractor returned invalid JSON"
        ) from exc
    if payload.get("networkx_version") != PINNED_NETWORKX_VERSION:
        raise RuntimeError(
            "FeatureUniverse version mismatch: expected "
            f"{PINNED_NETWORKX_VERSION}, got {payload.get('networkx_version')}"
        )
    return payload


def _surface_object_kind(obj) -> str:
    if inspect.ismodule(obj):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if callable(obj):
        return "callable"
    return "constant"


def _surface_signature(obj) -> str | None:
    try:
        return re.sub(
            r" at 0x[0-9a-fA-F]+",
            "",
            str(inspect.signature(obj)),
        )
    except (TypeError, ValueError):
        return None


def _surface_stable_repr(obj) -> str:
    return re.sub(r" at 0x[0-9a-fA-F]+", "", repr(obj))


def _surface_member_kind(static_obj, resolved_obj) -> str:
    if isinstance(static_obj, property):
        return "property"
    if callable(resolved_obj):
        return "method"
    if hasattr(static_obj, "__get__"):
        return "descriptor"
    return "attribute"


_ALGORITHM_FAMILIES = {
    "approximation",
    "assortativity",
    "bipartite",
    "centrality",
    "coloring",
    "community",
    "components",
    "connectivity",
    "flow",
    "isomorphism",
    "link_analysis",
    "minors",
    "operators",
    "shortest_paths",
    "traversal",
    "tree",
}


def feature_family(reference_row: dict) -> str:
    """Return a stable, review-sized family for a qualified surface path."""
    path = reference_row["path"]
    if path == "networkx.__version__":
        return "package metadata"
    if path == "networkx.config":
        return "configuration"

    module_name = reference_row.get("object_module")
    if not module_name or not module_name.startswith("networkx"):
        module_name = reference_row["source_module"]
    parts = module_name.split(".")
    if len(parts) == 1:
        return "package root"
    top_level = parts[1]
    if top_level == "algorithms":
        if len(parts) > 2 and parts[2] in _ALGORITHM_FAMILIES:
            return f"algorithms.{parts[2]}"
        return "algorithms.other"
    if top_level in {"convert", "convert_matrix", "relabel"}:
        return "conversion"
    if top_level == "exception":
        return "exceptions"
    if top_level == "lazy_imports":
        return "runtime"
    if top_level in {
        "classes",
        "drawing",
        "generators",
        "linalg",
        "readwrite",
        "utils",
    }:
        return top_level
    return "package root"


def classify_feature_universe(reference: dict | None = None) -> list[dict]:
    """Compare every pinned NetworkX path with its FrankenNetworkX peer."""
    if reference is None:
        reference = load_feature_universe_reference()

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "python"))
    import franken_networkx as fnx  # pylint: disable=import-outside-toplevel

    _materialize_callable_module_shims(fnx)
    module_cache = {"networkx": fnx}

    def load_franken_module(networkx_module_name):
        franken_module_name = networkx_module_name.replace(
            "networkx", "franken_networkx", 1
        )
        if franken_module_name not in module_cache:
            try:
                module_cache[franken_module_name] = importlib.import_module(
                    franken_module_name
                )
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
                module_cache[franken_module_name] = exc
        return franken_module_name, module_cache[franken_module_name]

    rows = []
    for reference_row in reference["rows"]:
        row = dict(reference_row)
        row["family"] = feature_family(reference_row)
        row["franken_path"] = reference_row["path"].replace(
            "networkx", "franken_networkx", 1
        )

        exclusion_reason = reference_row.get("exclusion_reason")
        if exclusion_reason:
            row["status"] = "excluded"
            row["detail"] = exclusion_reason
            row["franken_kind"] = None
            row["franken_signature"] = None
            rows.append(row)
            continue

        if reference_row["path"] == "networkx.__version__":
            row["status"] = "n/a"
            row["detail"] = (
                "package identity metadata intentionally reports the "
                "FrankenNetworkX release, not NetworkX's release"
            )
            row["franken_kind"] = "constant"
            row["franken_signature"] = None
            rows.append(row)
            continue

        if reference_row["kind"] == "unresolved":
            row["status"] = "n/a"
            row["detail"] = (
                "the pinned NetworkX declaration itself does not resolve: "
                f"{reference_row.get('reference_error', 'unknown error')}"
            )
            row["franken_kind"] = None
            row["franken_signature"] = None
            rows.append(row)
            continue

        if reference_row.get("owner_source_module"):
            owner_module_name, owner_module = load_franken_module(
                reference_row["owner_source_module"]
            )
            if isinstance(owner_module, Exception):
                row["status"] = "missing"
                row["detail"] = (
                    f"owner module `{owner_module_name}` is not importable: "
                    f"{type(owner_module).__name__}: {owner_module}"
                )
                row["franken_kind"] = None
                row["franken_signature"] = None
                rows.append(row)
                continue
            try:
                owner = getattr(owner_module, reference_row["owner_name"])
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
                row["status"] = "missing"
                row["detail"] = (
                    f"owner class `{reference_row['owner_name']}` is absent "
                    f"from `{owner_module_name}`: {type(exc).__name__}: {exc}"
                )
                row["franken_kind"] = None
                row["franken_signature"] = None
                rows.append(row)
                continue
            member_name = reference_row["member_name"]
            try:
                static_member = inspect.getattr_static(owner, member_name)
                resolved_member = getattr(owner, member_name)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
                row["status"] = "missing"
                row["detail"] = (
                    f"class member `{member_name}` is absent from "
                    f"`{row['franken_path'].rsplit('.', 1)[0]}`: "
                    f"{type(exc).__name__}: {exc}"
                )
                row["franken_kind"] = None
                row["franken_signature"] = None
                rows.append(row)
                continue

            franken_kind = _surface_member_kind(
                static_member, resolved_member
            )
            franken_call_shape = (
                _surface_signature(resolved_member)
                if reference_row["kind"] == "method"
                else None
            )
            row["franken_kind"] = franken_kind
            row["franken_signature"] = franken_call_shape
            if franken_kind != reference_row["kind"]:
                row["status"] = "partial"
                row["detail"] = (
                    f"class-member kind differs: NetworkX exposes "
                    f"`{reference_row['kind']}`, FrankenNetworkX exposes "
                    f"`{franken_kind}`"
                )
            elif reference_row["kind"] == "method":
                reference_call_shape = reference_row.get("signature")
                if (
                    reference_call_shape is not None
                    and franken_call_shape != reference_call_shape
                ):
                    row["status"] = "partial"
                    if franken_call_shape is None:
                        row["detail"] = (
                            "inspectable method signature is missing: "
                            f"NetworkX exposes `{reference_call_shape}`, "
                            "FrankenNetworkX exposes no signature"
                        )
                    else:
                        row["detail"] = (
                            "method signature differs: NetworkX "
                            f"`{reference_call_shape}`; FrankenNetworkX "
                            f"`{franken_call_shape}`"
                        )
                else:
                    row["status"] = "present"
                    row["detail"] = (
                        "class-member kind and signature match"
                        if reference_call_shape is not None
                        else "class-member kind matches; NetworkX exposes no inspectable signature"
                    )
            elif reference_row["kind"] == "attribute":
                franken_type = type(resolved_member)
                franken_type_name = (
                    f"{franken_type.__module__}.{franken_type.__qualname__}"
                )
                franken_value_repr = _surface_stable_repr(resolved_member)
                if (
                    franken_type_name == reference_row["type_name"]
                    and franken_value_repr == reference_row["value_repr"]
                ):
                    row["status"] = "present"
                    row["detail"] = "class attribute value and type match"
                else:
                    row["status"] = "partial"
                    row["detail"] = (
                        "class attribute differs: NetworkX "
                        f"`{reference_row['type_name']}="
                        f"{reference_row['value_repr']}`; FrankenNetworkX "
                        f"`{franken_type_name}={franken_value_repr}`"
                    )
            else:
                row["status"] = "present"
                row["detail"] = "class-member binding kind matches"
            rows.append(row)
            continue

        source_module = reference_row["source_module"]
        franken_module_name, franken_module = load_franken_module(
            source_module
        )
        if isinstance(franken_module, Exception):
            row["status"] = "missing"
            row["detail"] = (
                f"module `{franken_module_name}` is not importable: "
                f"{type(franken_module).__name__}: {franken_module}"
            )
            row["franken_kind"] = None
            row["franken_signature"] = None
            rows.append(row)
            continue

        try:
            franken_obj = getattr(franken_module, reference_row["name"])
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
            row["status"] = "missing"
            row["detail"] = (
                f"attribute `{reference_row['name']}` is absent from "
                f"`{franken_module_name}`: {type(exc).__name__}: {exc}"
            )
            row["franken_kind"] = None
            row["franken_signature"] = None
            rows.append(row)
            continue

        franken_kind = _surface_object_kind(franken_obj)
        franken_call_shape = (
            _surface_signature(franken_obj)
            if reference_row["kind"] in {"callable", "class"}
            else None
        )
        row["franken_kind"] = franken_kind
        row["franken_signature"] = franken_call_shape

        if franken_kind != reference_row["kind"]:
            row["status"] = "partial"
            if reference_row["kind"] == "callable" and callable(franken_obj):
                row["detail"] = (
                    "function-object surface is missing: NetworkX exposes a "
                    f"callable, while FrankenNetworkX exposes a callable "
                    f"`{franken_kind}` proxy"
                )
            else:
                row["detail"] = (
                    f"binding kind differs: NetworkX exposes "
                    f"`{reference_row['kind']}`, FrankenNetworkX exposes "
                    f"`{franken_kind}`"
                )
            rows.append(row)
            continue

        if reference_row["kind"] in {"callable", "class"}:
            reference_call_shape = reference_row.get("signature")
            if (
                reference_call_shape is not None
                and franken_call_shape != reference_call_shape
            ):
                row["status"] = "partial"
                if franken_call_shape is None:
                    row["detail"] = (
                        "inspectable signature is missing: NetworkX exposes "
                        f"`{reference_call_shape}`, FrankenNetworkX exposes no "
                        "signature"
                    )
                else:
                    row["detail"] = (
                        f"signature differs: NetworkX `{reference_call_shape}`; "
                        f"FrankenNetworkX `{franken_call_shape}`"
                    )
            else:
                row["status"] = "present"
                row["detail"] = (
                    "binding kind and signature match"
                    if reference_call_shape is not None
                    else "binding kind matches; NetworkX exposes no inspectable signature"
                )
            rows.append(row)
            continue

        franken_type = type(franken_obj)
        franken_type_name = (
            f"{franken_type.__module__}.{franken_type.__qualname__}"
        )
        franken_value_repr = _surface_stable_repr(franken_obj)
        if (
            franken_type_name == reference_row["type_name"]
            and franken_value_repr == reference_row["value_repr"]
        ):
            row["status"] = "present"
            row["detail"] = "value and type match"
        else:
            row["status"] = "partial"
            row["detail"] = (
                "value surface differs: NetworkX "
                f"`{reference_row['type_name']}={reference_row['value_repr']}`; "
                "FrankenNetworkX "
                f"`{franken_type_name}={franken_value_repr}`"
            )
        rows.append(row)

    valid_statuses = set(FEATURE_STATUS_ORDER)
    if len({row["path"] for row in rows}) != len(rows):
        raise RuntimeError("FeatureUniverse contains duplicate qualified paths")
    for row in rows:
        if row["status"] not in valid_statuses:
            raise RuntimeError(
                f"Unclassified FeatureUniverse row: {row['path']}"
            )
        if row["status"] in {"partial", "excluded"} and not row["detail"]:
            raise RuntimeError(
                f"{row['status']} FeatureUniverse row lacks a reason: "
                f"{row['path']}"
            )
    return rows


def _markdown_cell(value) -> str:
    if value is None:
        return "—"
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", "<br>")
    )


def render_feature_universe(reference: dict, rows: list[dict]) -> list[str]:
    """Render provenance, per-family coverage, and the exhaustive matrix."""
    family_counts = defaultdict(Counter)
    total_counts = Counter()
    for row in rows:
        family_counts[row["family"]][row["status"]] += 1
        total_counts[row["status"]] += 1

    applicable = (
        total_counts["present"]
        + total_counts["partial"]
        + total_counts["missing"]
    )
    strict_fraction = total_counts["present"] / max(applicable, 1)
    strict_percent = f"{strict_fraction * 100:.1f}%"
    lines = [
        "# FrankenNetworkX Surface-Parity Matrix",
        "",
        "*Auto-generated by `scripts/generate_coverage_matrix.py`; do not edit manually.*",
        "",
        "## FeatureUniverse provenance and method",
        "",
        f"- Reference package: pinned `networkx=={reference['networkx_version']}` from `uv.lock`.",
        f"- Reference source fingerprint: SHA-256 `{reference['networkx_python_source_sha256']}` over every installed NetworkX `.py` path and byte stream.",
        f"- Module census: {reference['discovered_module_count']} installed submodules discovered; {reference['included_module_count']} root/public modules imported and enumerated; {reference['excluded_module_count']} test or pytest-support modules retained as explicit excluded rows.",
        "- Enumeration runs in an isolated `python -I` process that imports NetworkX but never FrankenNetworkX. For each included module it reads `__all__` when present; otherwise it applies Python's wildcard rule and reads names in the live module namespace that do not begin with `_`. `networkx.__version__` is added as package metadata. Public class members declared by a NetworkX class in the class MRO are then added from `dir()` plus `inspect.getattr_static()`.",
        "- Each unique qualified path is then resolved against the corresponding `franken_networkx` module. Module-valued namespace containers are excluded because their callable/class/value members are counted separately; every such row retains that reason.",
        "",
        "`present` means import/binding-kind/signature parity only. It does not mean native Rust ownership, performance parity, or exhaustive behavioral conformance. `partial` is never included in the strict-present numerator.",
        "",
        "## Per-family strict surface coverage",
        "",
        "| Family | Present | Partial | Missing | N/A | Excluded | Applicable | Strict present |",
        "|--------|--------:|--------:|--------:|----:|---------:|-----------:|---------------:|",
    ]
    for family in sorted(family_counts):
        counts = family_counts[family]
        family_applicable = (
            counts["present"] + counts["partial"] + counts["missing"]
        )
        family_percent = (
            f"{counts['present'] * 100 / family_applicable:.1f}%"
            if family_applicable
            else "—"
        )
        lines.append(
            f"| `{family}` | {counts['present']} | {counts['partial']} | "
            f"{counts['missing']} | {counts['n/a']} | {counts['excluded']} | "
            f"{family_applicable} | {family_percent} |"
        )
    lines.extend(
        [
            (
                f"| **All families** | **{total_counts['present']}** | "
                f"**{total_counts['partial']}** | "
                f"**{total_counts['missing']}** | "
                f"**{total_counts['n/a']}** | "
                f"**{total_counts['excluded']}** | "
                f"**{applicable}** | **{strict_percent}** |"
            ),
            "",
            (
                "At the declared import-and-signature surface measured here, "
                f"a real user can port **{total_counts['present']} of "
                f"{applicable} applicable NetworkX feature paths today "
                f"({strict_percent})**; the {total_counts['partial']} partial "
                f"and {total_counts['missing']} missing paths are not counted "
                "as portable, and this is not a behavioral-conformance score."
            ),
            "",
            "## Exhaustive FeatureUniverse",
            "",
            "| Family | NetworkX path | Kind | Status | FrankenNetworkX path | Evidence / exact gap / exclusion reason |",
            "|--------|---------------|------|--------|----------------------|-----------------------------------------|",
        ]
    )
    for row in sorted(rows, key=lambda item: (item["family"], item["path"])):
        lines.append(
            "| `{family}` | `{path}` | `{kind}` | `{status}` | "
            "`{franken_path}` | {detail} |".format(
                family=_markdown_cell(row["family"]),
                path=_markdown_cell(row["path"]),
                kind=_markdown_cell(row["kind"]),
                status=_markdown_cell(row["status"]),
                franken_path=_markdown_cell(row["franken_path"]),
                detail=_markdown_cell(row["detail"]),
            )
        )
    lines.append("")
    return lines


def _materialize_callable_module_shims(fnx):
    """Force every ``franken_networkx`` subpackage to import.

    br-r37-c1-oul4c: several exports (``bridges``, ``reciprocity``,
    ``isomorphism`` ...) start life as a plain function and are
    *replaced* by a callable-module shim the first time the matching
    ``franken_networkx.<name>`` subpackage is imported.  Whether that
    has happened depends on global import order, which made both the
    category and runtime-route classification — and therefore the
    rendered doc — non-deterministic.  Eagerly importing every
    subpackage pins the introspected state to the fully-materialized
    form, so the ledger is reproducible regardless of caller.
    """
    import importlib  # pylint: disable=import-outside-toplevel
    import pkgutil  # pylint: disable=import-outside-toplevel

    for info in pkgutil.walk_packages(fnx.__path__, f"{fnx.__name__}."):
        if ".tests" in info.name or info.name.endswith(".tests"):
            continue
        try:
            importlib.import_module(info.name)
        except Exception:  # pylint: disable=broad-except
            # optional/​heavy backends (matplotlib, pydot ...) may be
            # absent — skip; their exports are introspected as-is.
            continue


def load_public_exports():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "python"))
    import franken_networkx as fnx  # pylint: disable=import-outside-toplevel

    _materialize_callable_module_shims(fnx)

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
    # br-r37-c1-oul4c: classify on `callable()` rather than
    # isbuiltin/isfunction.  Exports like `bridges` / `reciprocity` are
    # served by a callable-module shim (`_CallableBridgesModule`) that
    # *replaces* the plain function the first time the matching
    # `franken_networkx.<name>` submodule is imported.  A plain function
    # is `isfunction`, the shim is not — so the old gate made the
    # classification (and the rendered doc) depend on submodule import
    # order, leaving test_generated_coverage_matrix_document_is_current
    # permanently stale.  `callable()` is true for both forms, so the
    # classification is now deterministic.
    if not callable(obj):
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


def _load_external_divergence_rows() -> list[dict]:
    """br-r37-c1-943zy: pick up rows generated by
    ``scripts/upstream_divergence_ledger.py`` (raw-vs-public audit
    findings, Rust ``KNOWN GAP`` markers, closed-bead history) so the
    coverage doc stays consistent with the unified ledger.
    """
    path = ROOT / "docs" / "upstream_divergence_ledger.json"
    if not path.exists():
        return []
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    rows: list[dict] = []
    for entry in payload.get("entries", []):
        category = entry.get("category")
        if category not in DIVERGENCE_CATEGORY_RULES:
            continue
        # Skip the bulk native-parity / intentionally-delegated rows
        # — the AST pass below already produces those at higher
        # fidelity. Surface only the categories the AST pass cannot
        # discover on its own (KNOWN GAP markers, closed-bead history,
        # raw-vs-public wrapper-patched findings).
        if category in {"native-parity", "intentionally-delegated"}:
            continue
        rows.append(
            {
                "category": category,
                "export": entry.get("name", ""),
                "route": "PY_WRAPPER",
                "source": entry.get("source", "external-ledger"),
                "evidence": entry.get("evidence")
                or "docs/upstream_divergence_ledger.md",
                "note": entry.get("note", ""),
            }
        )
    return rows


def build_upstream_divergence_ledger(analyses) -> list[dict]:
    """Build review-facing upstream divergence rows from AST plus annotations."""
    ledger = []
    for analysis in analyses:
        if analysis["category"] == "RUST_NATIVE":
            ledger.append(
                {
                    "category": "native-parity",
                    "export": analysis["name"],
                    "route": analysis["runtime_route"],
                    "source": "ast:public-export",
                    "evidence": analysis["module"],
                    "note": "native extension export counted as parity-owned unless annotated otherwise",
                }
            )
        elif analysis["runtime_route"] in {"NETWORKX_HELPER", "DIRECT_NETWORKX"}:
            targets = sorted({call["target"] for call in analysis["helper_calls"]})
            evidence = ", ".join(targets) if targets else "direct networkx reference"
            ledger.append(
                {
                    "category": "intentionally-delegated",
                    "export": analysis["name"],
                    "route": analysis["runtime_route"],
                    "source": "ast:runtime-route",
                    "evidence": evidence,
                    "note": "public wrapper keeps NetworkX behavior for this argument surface",
                }
            )

    ledger.extend(dict(row) for row in DIVERGENCE_ANNOTATIONS)
    # br-r37-c1-943zy: pick up external ledger rows (audit findings,
    # KNOWN GAP markers, closed-bead history) deduped against the
    # hand-curated DIVERGENCE_ANNOTATIONS by (category, export, source).
    seen = {(row["category"], row["export"], row["source"]) for row in ledger}
    for row in _load_external_divergence_rows():
        key = (row["category"], row["export"], row["source"])
        if key in seen:
            continue
        seen.add(key)
        ledger.append(row)

    return sorted(
        ledger,
        key=lambda row: (
            DIVERGENCE_CATEGORY_ORDER.index(row["category"]),
            row["export"],
            row["source"],
        ),
    )


def render_markdown(exports, duplicates) -> str:
    reference = load_feature_universe_reference()
    feature_rows = classify_feature_universe(reference)
    categorized = defaultdict(list)
    runtime_routes = defaultdict(list)
    module_counts = Counter()
    analyses = [analyze_export(name, obj) for name, obj in exports]
    divergence_ledger = build_upstream_divergence_ledger(analyses)
    divergence_counts = Counter(row["category"] for row in divergence_ledger)

    for analysis in analyses:
        categorized[analysis["category"]].append(analysis["name"])
        runtime_routes[analysis["runtime_route"]].append(analysis)
        module_counts[analysis["module"]] += 1

    total = len(exports)
    helper_call_count = sum(len(row["helper_calls"]) for row in analyses)
    lines = render_feature_universe(reference, feature_rows)
    lines.extend(
        [
        "## FrankenNetworkX root-export implementation appendix",
        "",
        "The FeatureUniverse above measures NetworkX-qualified import and signature surface. This appendix separately classifies the implementation routes of names declared by `franken_networkx.__all__`; its 763-row denominator must not be used as NetworkX surface coverage.",
        "",
        "### FrankenNetworkX export summary",
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
    )
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
            "## Upstream Divergence Ledger",
            "",
            "This ledger makes divergence ownership explicit. Rows come from AST-visible public-export/runtime-route analysis plus bead/test/code annotations for known lower-level gaps.",
            "",
            "| Divergence state | Rows | Rule |",
            "|------------------|------|------|",
        ]
    )
    for category in DIVERGENCE_CATEGORY_ORDER:
        lines.append(
            f"| {category} | {divergence_counts[category]} | {DIVERGENCE_CATEGORY_RULES[category]} |"
        )
    lines.extend(
        [
            "",
            "## Upstream Divergence Annotations",
            "",
            "| State | Export / surface | Route | Source | Evidence | Note |",
            "|-------|------------------|-------|--------|----------|------|",
        ]
    )
    # br-r37-c1-943zy: render every non-bulk divergence row (the
    # AST-derived native-parity / intentionally-delegated rows are
    # summarized in the count table above; here we surface the rows
    # that need review attention — wrapper-patched, raw-known-gap,
    # owner-acknowledged-limitation).
    annotation_rows = [
        row
        for row in divergence_ledger
        if row["category"]
        in {"wrapper-patched", "raw-known-gap", "owner-acknowledged-limitation"}
    ]
    for row in annotation_rows:
        lines.append(
            "| {category} | `{export}` | {route} | {source} | `{evidence}` | {note} |".format(
                **row
            )
        )
    lines.extend(
        [
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

    feature_counts = Counter(
        row["status"]
        for row in classify_feature_universe(
            load_feature_universe_reference()
        )
    )
    applicable = (
        feature_counts["present"]
        + feature_counts["partial"]
        + feature_counts["missing"]
    )
    counts = Counter(classify_export(obj) for _, obj in exports)
    print(
        f"Generated {OUT_PATH} with "
        f"{sum(feature_counts.values())} FeatureUniverse rows classified"
    )
    for status in FEATURE_STATUS_ORDER:
        print(f"  {status}: {feature_counts[status]}")
    print(
        "  strict present: "
        f"{feature_counts['present']}/{applicable} "
        f"({feature_counts['present'] * 100 / max(applicable, 1):.1f}%)"
    )
    print(f"FrankenNetworkX root-export appendix: {len(exports)} unique names")
    if duplicates:
        print(f"  duplicate __all__ entries skipped: {len(duplicates)}")
    for category in CATEGORY_ORDER:
        print(f"  {category}: {counts[category]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
