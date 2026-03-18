# Kubernetes — Best Practices

<!-- CAPABILITY REFERENCE
Best practices card for Kubernetes.
To combine with capabilities/infrastructure/docker.md and a role (e.g. roles/engineering/platform-engineer.md).
-->

> **Reference version:** Kubernetes 1.30+ | **Last updated:** 2026-02
> **Official docs:** [kubernetes.io/docs](https://kubernetes.io/docs/)

---

## 🏛️ Fundamental principles

### 1. Declarative — everything is YAML (or Helm, Kustomize)

```yaml
# ✅ Declarative — desired state versioned
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app: myapp
    component: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
      component: api
  template:
    metadata:
      labels:
        app: myapp
        component: api
    spec:
      containers:
        - name: api
          image: myapp/api:1.2.3  # explicit tag
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

**Rule:** Never `kubectl run` or `kubectl create` in production. Everything goes through versioned manifests.

### 2. Resource requests & limits — mandatory

```yaml
# ✅ Always specify requests AND limits
resources:
  requests:
    cpu: 100m       # What the pod normally needs
    memory: 128Mi
  limits:
    cpu: 500m       # Maximum allowed (throttled beyond)
    memory: 512Mi   # OOMKilled beyond this
```

| Without resources | Risk |
|---|---|
| No requests | The scheduler cannot place the pod correctly |
| No limits | A pod can consume the entire node |

### 3. Probes — liveness, readiness, startup

```yaml
# ✅ All 3 probes
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5

startupProbe:
  httpGet:
    path: /health/started
    port: 8080
  failureThreshold: 30
  periodSeconds: 10
```

| Probe | Role | If failing |
|---|---|---|
| Startup | Has the app finished starting? | Waits |
| Readiness | Can the app receive traffic? | Removed from Service |
| Liveness | Is the app alive? | Restarts the pod |

### 4. Namespaces for isolation

```yaml
# ✅ One namespace per environment or domain
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    env: production
```

```
namespaces/
├── production
├── staging
├── monitoring
└── ingress
```

### 5. Labels and annotations — systematic

```yaml
metadata:
  labels:
    app.kubernetes.io/name: myapp
    app.kubernetes.io/version: "1.2.3"
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: myplatform
    app.kubernetes.io/managed-by: helm
  annotations:
    description: "Main backend API"
    owner: "team-backend"
```

---

## 📐 Recommended patterns

### HPA — Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### PodDisruptionBudget

```yaml
# ✅ Guarantee availability during updates
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 1   # or maxUnavailable: 1
  selector:
    matchLabels:
      app: myapp
      component: api
```

### NetworkPolicy

```yaml
# ✅ Zero-trust: deny all by default, explicit whitelist
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-netpol
spec:
  podSelector:
    matchLabels:
      app: myapp
      component: api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              component: ingress
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              component: database
      ports:
        - port: 3306
```

### Secrets — never in plaintext

```yaml
# ✅ ExternalSecrets or Sealed Secrets
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: api-secrets
spec:
  secretStoreRef:
    name: vault
    kind: ClusterSecretStore
  target:
    name: api-secrets
  data:
    - secretKey: DB_PASSWORD
      remoteRef:
        key: myapp/database
        property: password
```

---

## 🚫 Anti-patterns

```yaml
# ❌ Latest image
image: myapp:latest

# ❌ No resources
containers:
  - name: api
    image: myapp:1.0
    # resources: ???  → will consume the entire node

# ❌ No probes
# → K8s does not know if the app is alive or ready

# ❌ kubectl apply on a non-versioned local file
# → No traceability, no rollback

# ❌ Secrets in base64 in committed YAML manifests
# base64 is NOT encryption

# ❌ hostPath volumes in production
volumes:
  - name: data
    hostPath:
      path: /data  # node coupling
```

---

## ✅ Quick checklist

```
- [ ] Versioned manifests (Git) — no imperative kubectl in production
- [ ] Explicit image tags (never latest)
- [ ] Resources requests + limits on every container
- [ ] All 3 probes (startup, readiness, liveness)
- [ ] Standard kubernetes.io labels
- [ ] Namespaces for isolation
- [ ] NetworkPolicies (deny all + whitelist)
- [ ] Encrypted secrets (External Secrets, Sealed Secrets, Vault)
- [ ] PodDisruptionBudget for high availability
- [ ] HPA for auto-scaling
- [ ] RBAC: principle of least privilege
- [ ] Pod Security Standards (restricted)
```
