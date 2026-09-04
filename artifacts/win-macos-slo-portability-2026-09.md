# Windows/macOS SLO Portability Analysis — 2026-09

> Closes reality-check bead `br-r37-c1-rc-win-macos-slo-backlog-uz29h` via its
> second sanctioned outcome: harness analysis attached to the already-published
> acknowledgment (README "No Windows/macOS performance SLO yet", Limits).

## The three-clause gate, clause by clause (scripts/perf_harness.py)

| Clause | Mechanism (file:line) | Linux | macOS | Windows |
|---|---|---|---|---|
| Pre-setup + pre-measurement admission: 5 consecutive clear 1 s samples of **every CPU in the effective cgroup cpuset** | `/sys/fs/cgroup/cpuset.cpus.effective` / `cpuset/cpuset.effective_cpus` (:529-532), `/proc/stat` per-CPU rows (:548-571) | ✅ | ❌ no cgroupfs; per-CPU busy needs Mach `host_processor_info` via ctypes — and reports the **VM**, not the host | ❌ no cgroupfs; `GetSystemTimes` is aggregate-only — per-CPU needs PDH/pywin32 |
| Continuous during-timing accounting of every **non-affinity** CPU, 300 ms windows, 20% / 2-window abort | :609 (taskset-affinity requirement), :631-641 | ✅ | ❌ `sched_setaffinity` does not exist on macOS; "non-affinity CPU" is undefined | ❌ affinity only via psutil/ctypes; aggregate counters again |
| Statistical: A/A nulls + bootstrap median CI (three-clause median gate) | docstring :19-24 | ✅ portable (stdlib `time.monotonic`) | ✅ | ✅ |

## The structural finding

GitHub macOS/Windows runners are **ephemeral shared VMs**. Even a perfect
per-CPU port would observe only the VM's virtual CPUs — the thing clause 4
exists to catch is **physical-host co-tenancy**, which is unobservable from
inside the VM. On this campaign's bare-metal reference box the clause is
meaningful; on shared runners it is definitionally unprovable. This is not a
porting gap; it is an evidence-class boundary. (Fleet precedent: worker
identity alone moved one measured ratio 13.6× with both A/A nulls passing —
precisely why the exclusivity clause refuses to transfer.)

## Verdict

1. **G6 stays Linux-only with the full three-clause gate.** No weakening: the
   statistical clauses must never be silently promoted to a full SLO verdict.
2. **The limitation stands acknowledged** (README Limits). This artifact is
   the attached harness analysis the acknowledgment lacked.
3. **If per-OS rows are ever wanted**: implement a separate statistical-only
   mode (e.g. `FNX_SLO_SHARED=1`: A/A null + bootstrap CI, no exclusivity
   clause) and label its rows **"shared-runner evidence class"** everywhere
   they appear. Such rows must never be merged into the incumbent-gate
   contract tables in `docs/performance.md` or the README loss/win tables —
   they answer "is it plausible", not "is it proven".

## Reproduce the inventory

```bash
grep -n 'cpuset\|/proc/stat\|taskset\|sched_' scripts/perf_harness.py   # Linux-only surface
sed -n '19,37p' scripts/perf_harness.py                                  # gate doctrine
```
