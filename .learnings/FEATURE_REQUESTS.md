# Titan Feature Requests

(Manual log. Capture requested capability + why + suggested implementation.)

---

## [FEAT-20260202-001] security-hardening-gates

**Logged**: 2026-02-03T02:10:00Z
**Priority**: medium
**Status**: pending
**Area**: infra

### Requested Capability
Incorporate host/system hardening ideas (firewall default-deny, SSH key-only, Tailscale-only access, command allowlists, sandbox mode) into Titan's promotion gates and deployment checklist.

### User Context
User shared an X post describing a secure setup workflow and wants to incorporate security-first practices into Titan as it progresses toward live trading.

### Complexity Estimate
medium

### Suggested Implementation
- Add `docs/SECURITY_BASELINE.md` describing recommended host hardening for Titan deployments.
- Add `titan promote` checks that verify:
  - No public-facing ports for trading control plane (unless explicitly configured)
  - Exec/tool allowlists enforced
  - Live trading requires explicit enable flag + 2-person/explicit approval option
- For future remote deployments, support Tailscale-only connectivity + SSH key-only.

### Metadata
- Frequency: first_time
- Related Features: titan promote, risk governor, deployment

---
