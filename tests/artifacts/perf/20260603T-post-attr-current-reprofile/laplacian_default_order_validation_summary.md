# Validation Summary

## Commands

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_to_scipy_sparse_default_native_parity.py tests/python/test_parity_comprehensive.py -q -k 'laplacian_matrix'`
- `timeout 180s ubs python/franken_networkx/__init__.py`

## Results

- `py_compile`: passed.
- Focused pytest: passed.
- UBS: exit `124`; the monolithic wrapper scan timed out after startup and emitted no findings before the timeout.

## Behavior

Focused parity covers default laplacian, explicit nodelist with self-loop/isolate, present weight attr fallback, unweighted/weighted dtype parity, and directed unweighted fallback.
