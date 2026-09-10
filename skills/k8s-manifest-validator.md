---
id: k8s-manifest-validator
file_path: skills/k8s-manifest-validator.md
name: K8s Manifest Validator
category: devops
tags: [kubernetes, manifests, validation, kubeconform, ingress]
author: opencode-core
version: 1.0.0
description: Create and validate Kubernetes manifests (Deployment, Service, Ingress).
---

# K8s Manifest Validator

## Prerequisites & Dependencies
- `kubectl` 1.27+ and `kubeconform` (or `kubeval`) installed for offline schema validation
- Optional: dev cluster access (`KUBECONFIG` set) for server-side dry-run and apply
- Target cluster's ingress controller class documented (e.g., `nginx`, `traefik`)

## Execution Steps
1. Author the Deployment with explicit `apiVersion`/`kind`, stable selector labels, resource requests/limits, and `readinessProbe`/`livenessProbe`.
2. Author the Service selecting on identical labels and the Ingress with TLS plus path rules matching the controller class.
3. Validate syntax and schema offline: `kubeconform -strict -summary -kubernetes-version 1.30.0 manifests/`.
4. Validate against the live API: `kubectl apply --dry-run=server -f manifests/`.
5. Apply to a dev namespace and confirm rollout status, endpoints, and Ingress routing returns the expected responses.
6. Before promoting to staging/production, diff manifests against cluster state with `kubectl diff`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: api, labels: { app: api } }
spec:
  replicas: 2
  selector: { matchLabels: { app: api } }
  template:
    metadata: { labels: { app: api } }
    spec:
      containers:
        - name: api
          image: registry.example.com/api:1.4.2
          ports: [{ containerPort: 3000 }]
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { memory: 256Mi }
          readinessProbe: { httpGet: { path: /healthz, port: 3000 } }
---
apiVersion: v1
kind: Service
metadata: { name: api }
spec:
  selector: { app: api }
  ports: [{ port: 80, targetPort: 3000 }]
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata: { name: api, annotations: { cert-manager.io/cluster-issuer: letsencrypt } }
spec:
  ingressClassName: nginx
  tls: [{ hosts: [api.example.com], secretName: api-tls }]
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: api, port: { number: 80 } } }
```

```bash
kubeconform -strict -summary -kubernetes-version 1.30.0 manifests/
kubectl apply --dry-run=server -f manifests/
kubectl rollout status deploy/api -n dev
```
