# Kubernetes — Best Practices

<!-- STACK REFERENCE
Fiche de best practices pour Kubernetes.
À combiner avec stacks/infrastructure/docker.md et un rôle (ex: roles/platform-engineer.md).
-->

> **Version de référence :** Kubernetes 1.30+ | **Dernière mise à jour :** 2026-02
> **Docs officielles :** [kubernetes.io/docs](https://kubernetes.io/docs/)

---

## 🏛️ Principes fondamentaux

### 1. Déclaratif — tout est YAML (ou Helm, Kustomize)

```yaml
# ✅ Déclaratif — état désiré versionné
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
          image: myapp/api:1.2.3  # tag explicite
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
```

**Règle :** Jamais de `kubectl run` ou `kubectl create` en production. Tout passe par des manifestes versionnés.

### 2. Resource requests & limits — obligatoires

```yaml
# ✅ Toujours spécifier requests ET limits
resources:
  requests:
    cpu: 100m       # Ce que le pod a besoin normalement
    memory: 128Mi
  limits:
    cpu: 500m       # Maximum autorisé (throttling au-delà)
    memory: 512Mi   # OOMKilled au-delà
```

| Sans resources | Risque |
|---|---|
| Pas de requests | Le scheduler ne peut pas placer le pod correctement |
| Pas de limits | Un pod peut consommer TOUT le node |

### 3. Probes — liveness, readiness, startup

```yaml
# ✅ Les 3 probes
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

| Probe | Rôle | Si KO |
|---|---|---|
| Startup | L'app a-t-elle fini de démarrer ? | Attend |
| Readiness | L'app peut-elle recevoir du trafic ? | Retire du Service |
| Liveness | L'app est-elle vivante ? | Restart le pod |

### 4. Namespaces pour l'isolation

```yaml
# ✅ Un namespace par environnement ou par domaine
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

### 5. Labels et annotations — systématiques

```yaml
metadata:
  labels:
    app.kubernetes.io/name: myapp
    app.kubernetes.io/version: "1.2.3"
    app.kubernetes.io/component: api
    app.kubernetes.io/part-of: myplatform
    app.kubernetes.io/managed-by: helm
  annotations:
    description: "API backend principale"
    owner: "team-backend"
```

---

## 📐 Patterns recommandés

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
# ✅ Garantir la disponibilité pendant les mises à jour
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 1   # ou maxUnavailable: 1
  selector:
    matchLabels:
      app: myapp
      component: api
```

### NetworkPolicy

```yaml
# ✅ Zero-trust : deny all par défaut, whitelist explicite
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

### Secrets — jamais en clair

```yaml
# ✅ ExternalSecrets ou Sealed Secrets
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
# ❌ Image latest
image: myapp:latest

# ❌ Pas de resources
containers:
  - name: api
    image: myapp:1.0
    # resources: ???  → va consommer tout le node

# ❌ Pas de probes
# → K8s ne sait pas si l'app est vivante ou prête

# ❌ kubectl apply sur un fichier local non versionné
# → Pas de traçabilité, pas de rollback

# ❌ Secrets en base64 dans les manifestes YAML commités
# base64 n'est PAS du chiffrement

# ❌ hostPath volumes en production
volumes:
  - name: data
    hostPath:
      path: /data  # couplage au node
```

---

## ✅ Checklist rapide

```
- [ ] Manifestes versionnés (Git) — pas de kubectl impératif en prod
- [ ] Tags d'image explicites (jamais latest)
- [ ] Resources requests + limits sur chaque container
- [ ] Les 3 probes (startup, readiness, liveness)
- [ ] Labels kubernetes.io standards
- [ ] Namespaces pour l'isolation
- [ ] NetworkPolicies (deny all + whitelist)
- [ ] Secrets chiffrés (External Secrets, Sealed Secrets, Vault)
- [ ] PodDisruptionBudget pour la haute disponibilité
- [ ] HPA pour le scaling auto
- [ ] RBAC : principe du moindre privilège
- [ ] Pod Security Standards (restricted)
```
