# Current Routing Sweep

Commit: `8cdb36e`

Command:

```bash
env PYTHONPATH=python rch exec -- .venv/bin/python tests/artifacts/perf/20260615T-post-graph-attr-routing-boldfalcon/construction_attr_survey.py survey --repeats 11 > tests/artifacts/perf/20260616T-current-routing-coppercliff/survey.json
```

## Ranking

| case | FNX/NX median ratio | FNX median | NX median | digest match |
| --- | ---: | ---: | ---: | --- |
| `graph_attr` | `1.535097x` | `0.011209354s` | `0.007302049s` | `true` |
| `digraph_attr` | `1.278820x` | `0.009280119s` | `0.007256783s` | `true` |
| `multidigraph_attr` | `1.211533x` | `0.019745131s` | `0.016297638s` | `true` |
| `multigraph_attr` | `1.181291x` | `0.019165873s` | `0.016224510s` | `true` |
| `graph_plain` | `0.549003x` | `0.052943992s` | `0.096436630s` | `true` |

`graph_attr` remains owned by BoldFalcon under `br-r37-c1-04z53.9106`.
The remaining construction cases have smaller residuals and recent rejected
micro-lever attempts, so the next CopperCliff pass moved to a separate
profile-evident spectral primitive.
