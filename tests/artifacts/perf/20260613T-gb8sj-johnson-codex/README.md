# br-r37-c1-gb8sj Johnson Baseline

This directory records the profile-backed proof bundle for the native Johnson
shortest-path optimization campaign.

Contract gate:
- exact `fnx.johnson(G, weight)` equality with NetworkX 3.6.1;
- exact outer and inner dictionary order;
- exact path lists;
- deterministic SHA-256 over the ordered JSON representation.

The first pass is baseline/profile only. Production code changes are kept to one
lever after this bundle identifies a scoreable target.
