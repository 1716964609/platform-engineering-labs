# Gateway API + RBAC — Experiment Results

Date: 2026-10-31
Environment: macOS / Docker Desktop / kind / Traefik

## 1. Gateway status

Observed:
- Gateway Accepted=True
- Gateway Programmed=True
- Gateway generation=1
- Two team routes initially attached

Result: PASS

## 2. Team-specific routing

Team B HTTPRoute changed from b.lab.test
to b2.lab.test without modifying the Gateway.

| Hostname | Observed HTTP |
|---|---|
| a.lab.test | 200 |
| b.lab.test | 404 |
| b2.lab.test | 200 |
| c.lab.test | 404 |

Result: PASS

## 3. Namespace isolation

Team C HTTPRoute was created, but not attached
to the shared Gateway.

Observed:
- Accepted=False
- Reason=NotAllowedByListeners
- ResolvedRefs=True
- HTTP 404

Result: PASS

## 4. Hostname ownership vulnerability demonstration

Before Admission Policy:

Team A declared c.lab.test.
HTTPRoute Accepted=True.
HTTP request returned 200.

This demonstrated the absence of hostname ownership
enforcement in the initial configuration.

The temporary claim-c HTTPRoute was deleted.

## 5. RBAC

Team A ServiceAccount authorization results:

| Operation | Observed |
|---|---|
| Create HTTPRoute in team-a | yes |
| Create HTTPRoute in team-b | no |
| Update Gateway in platform-gateway | no |
| Patch Namespace | no |

Result: PASS

## 6. Admission Policy

Server-side dry-run results:

Allowed:
- Hostname: a.lab.test
- Request accepted

Denied:
- Hostname: c.lab.test
- Error: Team A may only use a.lab.test

Result: PASS

## 7. Interpretation

RBAC restricts who can perform operations.
Admission Policy restricts valid configuration content.
Gateway API controls route attachment and traffic routing.

The three mechanisms address different boundaries.

## 8. Limitations

- Single-node kind cluster
- No real AWS ALB or EKS
- No multi-cluster Argo CD
- No GitOps reconciliation
- No complete production-grade tenant isolation

The observations above were taken from terminal output
recorded during the experiment.
