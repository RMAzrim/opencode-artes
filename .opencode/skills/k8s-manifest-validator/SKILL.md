---
name: K8s Manifest Validator
description: Validate and lint Kubernetes manifest files (YAML/JSON) against required fields, resource constraints, and best practices, with an optional kubectl dry-run schema check.
metadata:
  source: skills/k8s-manifest-validator/k8s-manifest-validator.md
---

# K8s Manifest Validator

## Prerequisites & Dependencies

- Python 3.10+ (for YAML/JSON parsing)
- `kubectl` for Kubernetes cluster interaction (optional, for validation)
- `jq` for JSON parsing (optional)

## Execution Steps

1. **Parse the Kubernetes manifest**: Read the YAML or JSON file containing the Kubernetes resource definition.

2. **Validate required fields**: Check for essential fields like `apiVersion`, `kind`, `metadata.name`, and appropriate `spec` structure based on the resource type.

3. **Check resource constraints**: Validate CPU/memory requests and limits, replica counts, and service account settings.

4. **Generate validation report**: Output a structured report listing:
   - Valid fields and structures
   - Missing or invalid fields
   - Warnings for deprecated or recommended settings
   - Suggested fixes for common issues

5. **Optional kubectl dry-run**: If `kubectl` is available, run `kubectl apply --dry-run=client` to validate the manifest against the cluster's schema.

6. **Example output**: A validation report indicating the manifest is valid, or listing issues like missing `selector`, incorrect `apiVersion`, or improper `metadata` formatting.

```bash
kubectl apply --dry-run=client -f manifest.yaml
```
