"""Stage only the newly built engineering wheel and bind its Python sources."""

import hashlib
from pathlib import Path
import zipfile

base = Path(__file__).parent
wheels = list((base / "final-native-wheels").glob("*.whl"))
assert len(wheels) == 1, wheels
wheel = wheels[0]
artifact = base / "final-native-artifact"
assert not artifact.exists(), "a previous artifact must not be silently reused"
artifact.mkdir()
with zipfile.ZipFile(wheel) as archive:
    for member in archive.infolist():
        relative = Path(member.filename)
        assert not relative.is_absolute() and ".." not in relative.parts
    archive.extractall(artifact)
root = Path.cwd()
count = 0
for source in (root / "python").rglob("*"):
    if not source.is_file() or source.suffix not in {".py", ".pyi"}:
        continue
    relative = source.relative_to(root / "python")
    target = artifact / relative
    assert target.is_file(), relative
    assert source.read_bytes() == target.read_bytes(), relative
    count += 1
extensions = list((artifact / "franken_networkx").glob("_fnx*.so"))
assert len(extensions) == 1, extensions
native_sha = hashlib.sha256(extensions[0].read_bytes()).hexdigest()
assert native_sha != "9314ccf170b8a43ca54f2c77822cd26012e5ba6b121cc314386bfbebbf34e386"
print("Fresh development-profile engineering wheel; no performance or release qualification")
print("wheel", wheel)
print("wheel_sha256", hashlib.sha256(wheel.read_bytes()).hexdigest())
print("python_sources_verified", count)
print("native", extensions[0])
print("native_sha256", native_sha)
