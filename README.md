# smart-firewall

Behavior-aware access gateway on a Raspberry Pi. Port-knocking hides SSH, and an anomaly-detection model scores each connection to allow, challenge or block it.

Project docs live in the team's Obsidian vault (Firewall project, `00-Overview/Overview.md`).

## Layout (planned)

- `sfw/`: shared code (features, scoring)
- `pipeline/`: log parsing, data generation, training
- `gateway/`: knockd, nftables, hook
- `dashboard/`: Flask page
- `deploy/`: Pi deployment
- `tests/`
- `data/`: local only, not in git
