# Validation Summary

## Build And Syntax

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`: passed.

## Behavior

- `RCH_ENV_ALLOWLIST=PYTHONPATH rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_review_mode_regression_lock.py -q -k "attr_matrix"`: 1 passed, 430 deselected.
- `parity_probe.json`: passed direct equality against NetworkX for undirected default, undirected weight, named edge attribute, callable edge attribute, normalized output, directed weight, and default-order return.

## UBS

- `timeout 180s ubs python/franken_networkx/__init__.py`: exit 124. The monolithic wrapper scan timed out after startup and emitted no findings before the timeout.
