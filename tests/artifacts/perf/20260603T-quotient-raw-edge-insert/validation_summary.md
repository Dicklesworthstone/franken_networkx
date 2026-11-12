# Validation summary: quotient raw trusted edge insertion

Bead: `br-r37-c1-04z53.43`

Result: rejected; no source change kept.

Commands run:

- `rch exec -- .venv/bin/python .../bench_quotient_graph.py bench --samples 10 --engines fnx nx`
  - baseline and candidate completed.
- `rch exec -- .venv/bin/python .../bench_quotient_graph.py profile --skip-digest ...`
  - baseline and candidate completed.
- `rch exec -- hyperfine --warmup 2 --runs 15 ... --skip-digest`
  - baseline and candidate completed.
- `rch exec -- .venv/bin/python .../bench_quotient_graph.py bench --samples 3 --engines fnx nx`
  - restored source proof completed.
- `rch exec -- .venv/bin/python -m py_compile .../bench_quotient_graph.py .../validate_quotient_raw_edge_insert.py`
  - passed.
- `rch exec -- .venv/bin/python .../validate_quotient_raw_edge_insert.py`
  - passed after narrowing the helper to the default weighted-key path.
- `timeout 120s ubs .../bench_quotient_graph.py .../validate_quotient_raw_edge_insert.py`
  - passed.
- `git diff HEAD -- python/franken_networkx/__init__.py`
  - empty after rejection restore.

Known blocker: none for this rejected candidate. Broader workspace status still
contains unrelated peer changes and generated artifacts outside this bead.
