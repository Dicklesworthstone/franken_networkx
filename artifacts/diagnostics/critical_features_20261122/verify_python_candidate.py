"""Bind a Python-only candidate to the explicitly older released native wheel."""

import hashlib
from pathlib import Path

import franken_networkx
import franken_networkx._fnx as native
import networkx

root = Path.cwd()
artifact = Path(__file__).parent / "python-candidate-artifact"
assert Path(franken_networkx.__file__).resolve() == artifact / "franken_networkx/__init__.py"
count = 0
for source in (root / "python").rglob("*.py"):
    relative = source.relative_to(root / "python")
    target = artifact / relative
    assert target.is_file(), relative
    assert source.read_bytes() == target.read_bytes(), relative
    count += 1
native_path = Path(native.__file__).resolve()
native_sha = hashlib.sha256(native_path.read_bytes()).hexdigest()
assert native_sha == "9314ccf170b8a43ca54f2c77822cd26012e5ba6b121cc314386bfbebbf34e386"
print("SCOPED Python candidate on published 0.4.1 native extension; not current-native qualification")
print("python_sources_verified", count)
print("package", franken_networkx.__file__)
print("native", native_path)
print("native_sha256", native_sha)
print("networkx", networkx.__version__)
