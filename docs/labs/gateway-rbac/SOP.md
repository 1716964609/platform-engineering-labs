# Gateway API + RBAC + Admission Policy — SOP

## Purpose

Validate multi-tenant boundaries in a shared Kubernetes Gateway.

## Prerequisites

- kind cluster: helm-lab
- Kubernetes context: kind-helm-lab
- Traefik Gateway: platform-gateway/shared-edge
- Namespaces: team-a, team-b, team-c
- Nginx Service: web-demo-web in each team namespace
- RBAC and ValidatingAdmissionPolicy installed

## Procedure

### 1. Verify cluster

```bash
kubectl config use-context kind-helm-lab
kubectl get gateway -n platform-gateway
kubectl get httproute -A
kubectl get namespaces --show-labels
```

Expected: Gateway is programmed, Team A/B routes accepted.

### 2. Verify RBAC

```bash
SA="system:serviceaccount:team-a:route-editor-lab"

kubectl auth can-i create httproutes -n team-a --as="$SA"
kubectl auth can-i create httproutes -n team-b --as="$SA"
kubectl auth can-i update gateways -n platform-gateway --as="$SA"
```

Expected: yes, no, no.

### 3. Verify routing

Keep this port-forward active in another terminal:

```bash
kubectl port-forward -n platform-gateway svc/edge-traefik 8080:80
```

Then:

```bash
for host in a.lab.test b.lab.test b2.lab.test c.lab.test; do
  curl -sS -o /dev/null \
    -w "$host: HTTP %{http_code}\n" \
    -H "Host: $host" \
    http://127.0.0.1:8080/
done
```

Expected: 200, 404, 200, 404.

### 4. Verify Admission Policy

Use server-side dry runs for both an allowed hostname
(a.lab.test) and a denied hostname (c.lab.test).

Expected:
- a.lab.test: request accepted
- c.lab.test: rejected by ValidatingAdmissionPolicy

## Notes

This SOP verifies an existing lab installation.
A fully fresh-cluster reproduction also requires the
original Helm Chart, Terraform configuration, Gateway,
RBAC and Admission Policy manifests.

Do not delete Gateway API CRDs during normal cleanup.
