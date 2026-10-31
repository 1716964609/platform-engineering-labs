# Kratix Platform Engineering Research — Experiment Record

Date: 2026-11-01 JST
Environment: MacBook Air / Docker Desktop / kind
Kubernetes context: kind-kratix-lab
Repository: platform-engineering-labs

## 1. Research Question

Can Kratix reduce the customization and operational complexity
of a platform built using Kubernetes, Helm, Terraform,
GitHub Actions, and Argo CD?

Motivation:
- Discussions at an SRE / Platform Engineering event
  involving gifty and Three Shake.
- Multi-tenant EKS platform architecture.
- Customization boundaries across CI/CD, Helm and Terraform.
- Platform Team versus Application Team responsibilities.
- Standardization versus team-specific requirements.

These are research questions, not confirmed deficiencies
in any particular company's production environment.

## 2. Architecture

Developer
  -> WebService Custom Resource
  -> Kratix Promise
  -> Configure Pipeline
  -> Deployment / Service / HTTPRoute
  -> Work / WorkPlacement
  -> BucketStateStore / Flux CD
  -> Kubernetes Workloads

Current lab uses Flux CD, not Argo CD.
Terraform and Helm are not integrated into this Kratix pipeline.

## 3. Implemented Capabilities

### v0.1 - v0.3

- Custom WebService Platform API
- Deployment generation
- Service generation
- HTTPRoute generation
- Shared Gateway
- Multi-tenant workloads: team-a and team-b

### Security experiments

Previously exercised:
- Kubernetes RBAC tenant isolation
- Hostname admission policy
- NetworkPolicy tenant isolation
- LimitRange defaults
- ResourceQuota admission enforcement

Security policy source files:
- kratix/security/hostname-policy.yaml
- kratix/security/team-a-limits.yaml
- kratix/security/team-a-quota.yaml
- kratix/security/team-a-compute-quota.yaml
- kratix/security/team-b-ingress-policy.yaml

## 4. v0.4 Resource Profile Experiment

Added resourceProfile to the WebService API.

Profiles:

small:
  CPU request: 50m
  CPU limit: 100m
  Memory request: 32Mi
  Memory limit: 64Mi

medium:
  CPU request: 100m
  CPU limit: 250m
  Memory request: 64Mi
  Memory limit: 256Mi

Results:
- Docker image build: PASS
- Local pipeline execution: PASS
- Deployment/Service/HTTPRoute generation: PASS
- Resource profile assertions: PASS
- Backward compatibility without resourceProfile: PASS
- Promise Revision v0.4.0 created: PASS
- Team A configure workflow: Complete
- Team A Deployment rollout: PASS
- Team A Pods: 2/2 Running
- Actual Pod resources match small profile: PASS

Resource Binding versions:
- default/hello-web: v0.3.0
- team-a/team-a-app: latest
- team-b/team-b-app: v0.3.0

Team B Deployment resource configuration remained unchanged.

## 5. Resource Governance Experiment

Namespace: team-a

ResourceQuota: tenant-compute-quota

Resource       Used    Hard
requests.cpu   100m    150m
requests.memory 64Mi   96Mi
limits.cpu     200m    300m
limits.memory  128Mi   300Mi

Test:
  kubectl run compute-test-medium

Result:
  Forbidden: exceeded quota: tenant-compute-quota

Conclusion:
  Namespace compute budgets are enforced during admission.
  The rejection happened before Pod creation.

## 6. Platform Workflow Resource Contention

Observed Kratix Configure Job containers:
- reader (init)
- render (init)
- work-writer (init)
- status-writer

Each had:
- CPU request: 100m
- Memory request: 128Mi
- CPU limit: 200m
- Memory limit: 256Mi

The sequential init containers do not simply add their
requests together.

Available quota after two application Pods:
- CPU requests: 50m
- Memory requests: 32Mi

A server-side dry-run Pod with equivalent compute requests
was rejected by ResourceQuota.

Finding:
  Running platform automation in a tenant namespace can
  cause platform workflows to compete with tenant workloads
  for the same ResourceQuota.

## 7. Work Delivery State

Destination: worker-1
State Store: BucketStateStore/default

Verified:
- hello-web Work: Ready
- team-a-app Work: Ready
- team-b-app Work: Ready
- Corresponding WorkPlacements: Ready

## 8. v0.5 Workflow Isolation — Prepared Only

Intended configuration:

  spec.workflows.config.pipelineNamespace:
    platform-workflows

Platform namespace created successfully.

The v0.5 Promise source passed server-side dry-run.

IMPORTANT:
  v0.5 has NOT been applied to the cluster.
  Pipeline relocation has NOT been validated.
  Existing Works and WorkPlacements must not be
  deleted without assessing delivery consequences.

The v0.5 Promise still uses the tested v0.4 pipeline image.

## 9. Research Limitations

The experiments demonstrate that Kratix can:
- Provide a higher-level Platform API
- Generate common Kubernetes workload resources
- Standardize compute resource profiles
- Integrate with Kubernetes governance controls

They do NOT establish that Kratix reduces total complexity
relative to Helm, Terraform and Argo CD.

Potential costs introduced by Kratix include:
- Promise and Pipeline maintenance
- Additional controllers and workflow execution
- Version and revision lifecycle management
- Debugging across API, pipeline and delivery layers
- Customization complexity migrating into Promise logic

## 10. Next Research

Primary question:
  Does Kratix actually reduce customization complexity,
  or does it move complexity into a different layer?

Next steps:
1. Complete v0.5 workflow namespace isolation.
2. Build a comparable non-Kratix deployment baseline.
3. Compare the same application customization scenarios.
4. Measure required changes, privileges and dependencies.
5. Evaluate developer experience and platform maintenance.
6. Investigate exception handling and escape hatches.

Candidate baseline:
  GitHub Actions + Terraform + Helm + Argo CD + Kubernetes.

Compare against:
  Kratix Promise + Pipeline + equivalent underlying tools.

## 11. Current Status

Verified through v0.4.
v0.5 source prepared but untested in-cluster.
Complexity comparison remains an open research question.
