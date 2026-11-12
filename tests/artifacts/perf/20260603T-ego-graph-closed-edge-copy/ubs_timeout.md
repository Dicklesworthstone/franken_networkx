# UBS Timeout

Command:

```text
timeout 120 ubs --only=python python/franken_networkx/__init__.py
```

Result: timed out with exit code `124` after detecting Python and starting the scan. Earlier full-file UBS invocation also stalled and was terminated after several minutes with no findings emitted.

Interpretation: tooling stall on the large generated Python compatibility file. Commit gating used `py_compile`, focused pytest ego_graph parity tests, golden digest checks, hyperfine/profile evidence, and artifact checksum verification.
