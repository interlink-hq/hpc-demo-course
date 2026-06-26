# ServiceAccount Token Mount Limitation

## Problem Description

When pods are offloaded to SLURM via Interlink, Kubernetes automatically mounts the ServiceAccount token, CA certificate, and namespace file into the container at `/var/run/secrets/kubernetes.io/serviceaccount/`. 

However, VirtualKubelet + Interlink does not currently export these projected volumes to the SLURM execution environment. The result is that Apptainer attempts to bind-mount files that don't exist, causing warnings and mount failures.

## Symptoms

```
WARNING: skipping mount of /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/ca.crt: 
  stat /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/ca.crt: no such file or directory

WARNING: skipping mount of /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/namespace:
  stat /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/namespace: no such file or directory

WARNING: skipping mount of /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/token:
  stat /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/token: no such file or directory

FATAL: container creation failed: mount hook function failure: 
  mount source /tmp/.interlink/.../projectedVolumeMaps/kube-api-access-{name}/token doesn't exist
```

## Root Cause

1. VirtualKubelet receives pod spec with projected volumes from Kubernetes
2. VirtualKubelet attempts to export volume contents to the Interlink API
3. **Gap**: Projected volumes (ServiceAccount tokens) are not properly serialized/exported
4. Interlink API has no token files to pass to SLURM plugin
5. SLURM plugin generates sbatch scripts that try to mount non-existent files
6. Apptainer fails to bind-mount missing files at container startup

The core pod offload mechanism works (pod runs), but the container lacks Kubernetes credentials.

## Current Workarounds

### Option 1: Disable ServiceAccount Mounting (Recommended)

If your container doesn't need to access the Kubernetes API:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: test-busybox
  namespace: default
spec:
  serviceAccountName: default
  automountServiceAccountToken: false  # ← Add this
  
  nodeSelector:
    virtual-node.interlink/type: virtual-kubelet
  
  tolerations:
  - key: virtual-node.interlink/no-schedule
    operator: Equal
    value: "true"
    effect: NoSchedule
  - key: node.kubernetes.io/not-ready
    operator: Equal
    value: "true"
    effect: NoExecute
  - key: node.kubernetes.io/network-unavailable
    operator: Equal
    value: "true"
    effect: NoExecute
  
  containers:
  - name: busybox
    image: busybox:latest
    command: ["/bin/sh"]
    args: ["-c", "echo 'Hello from SLURM'; sleep 30"]
```

### Option 2: Use Custom ServiceAccount

Create a ServiceAccount without token auto-mounting:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: offload-sa
automountServiceAccountToken: false
---
apiVersion: v1
kind: Pod
metadata:
  name: test-busybox
  namespace: default
spec:
  serviceAccountName: offload-sa  # ← Use custom SA
  
  nodeSelector:
    virtual-node.interlink/type: virtual-kubelet
  # ... rest of spec
```

### Option 3: Alternative Credentials

For workloads that need API access, consider:

1. **Docker/Container Registries**: Use image pull secrets instead
2. **API Access**: Mount credentials via ConfigMaps or Secrets (still won't work - same limitation)
3. **Job Credentials**: Inject via environment variables or files at job submission time

## Expected Behavior When Fixed

Once VirtualKubelet properly exports projected volumes:

```bash
$ kubectl exec test-busybox -- ls /var/run/secrets/kubernetes.io/serviceaccount/
ca.crt
namespace
token

$ kubectl exec test-busybox -- cat /var/run/secrets/kubernetes.io/serviceaccount/token
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

$ kubectl exec test-busybox -- curl --cacert /var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
  -H "Authorization: Bearer $(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \
  https://kubernetes.default.svc.cluster.local/api/v1/pods
# Would successfully access Kubernetes API
```

## Impact Assessment

**What WORKS (not affected by this limitation):**
- ✓ Pod offload to SLURM
- ✓ Container image execution via Apptainer
- ✓ Pod status and lifecycle tracking
- ✓ Environment variables
- ✓ ConfigMap mounts
- ✓ Secret mounts (volumes other than projected)
- ✓ Log retrieval
- ✓ Multi-container pods
- ✓ Init containers

**What DOESN'T WORK (due to this limitation):**
- ✗ In-container access to Kubernetes API
- ✗ In-container access to service account token
- ✗ In-container kubectl commands that need authentication
- ✗ Applications that authenticate with Kubernetes API at startup

## Recommended Usage Pattern

For this training course and typical HPC workloads:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hpc-workload
spec:
  # Disable automatic token mounting
  automountServiceAccountToken: false
  
  # Required for offloading to SLURM
  nodeSelector:
    virtual-node.interlink/type: virtual-kubelet
  tolerations:
  - key: virtual-node.interlink/no-schedule
    operator: Equal
    value: "true"
    effect: NoSchedule
  - key: node.kubernetes.io/not-ready
    operator: Equal
    value: "true"
    effect: NoExecute
  - key: node.kubernetes.io/network-unavailable
    operator: Equal
    value: "true"
    effect: NoExecute
  
  containers:
  - name: compute-task
    image: hpc-image:latest
    # Most HPC workloads don't need Kubernetes API access
    # They focus on computation and data processing
```

## Path Forward

To fully resolve this limitation:

1. **VirtualKubelet Enhancement**: Implement projected volume export in VirtualKubelet's pod descriptor
2. **Interlink API Enhancement**: Accept and serialize projected volume contents
3. **SLURM Plugin Enhancement**: Include token files in sbatch job scripts
4. **Apptainer Integration**: Verify mount succeeds with provided files

This would be a worthwhile enhancement but requires changes across the Interlink stack and is beyond the scope of this training course setup.

## References

- VirtualKubelet GitHub: https://github.com/virtual-kubelet/virtual-kubelet
- Interlink GitHub: https://github.com/interlink-hq/interLink
- Kubernetes ServiceAccount Documentation: https://kubernetes.io/docs/concepts/configuration/secret/#service-account-token-secret
