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

The issue is **NOT** that projected volumes aren't supported by Interlink. Rather, it's that VirtualKubelet cannot access the actual projected volume files.

**Why:**
1. Kubernetes (k3s) creates projected volumes on the **host node** at: `/var/lib/kubelet/pods/{pod-uid}/volumes/kubernetes.io~projected/`
2. Inside this directory: `token`, `ca.crt`, `namespace` files
3. VirtualKubelet runs as a **pod** in a container
4. VirtualKubelet's pod needs a **hostPath volume mount** to access `/var/lib/kubelet`
5. **Current Helm deployment doesn't include this mount**
6. Without this mount, VirtualKubelet can't read the token/ca/namespace files
7. It can't send them to Interlink
8. Interlink creates the directory structure but with no files
9. Apptainer tries to bind-mount non-existent files → FATAL error

**The Fix:**
Add a hostPath volume mount to VirtualKubelet pod to access k3s kubelet directories.

**The core pod offload mechanism works (pod runs), but the container lacks Kubernetes credentials because the projected volume files were never sent to the SLURM job.**

## Current Workarounds

### Option 1: Enable Access to kubelet Volumes (FIX - Recommended)

Add a hostPath volume mount to VirtualKubelet pod to access k3s kubelet directories.

**With Helm:**
```bash
helm upgrade --install vk oci://ghcr.io/virtual-kubelet/virtual-kubelet \
  --namespace virtual-kubelet \
  --set nodeName=interlink-node \
  --set provider=interlink \
  --set logs.level=info \
  --set interlink.url=http://192.168.2.170 \
  --set interlink.port=3000 \
  --set volumeMounts[0].name=kubelet-volumes \
  --set volumeMounts[0].mountPath=/var/lib/kubelet \
  --set volumes[0].name=kubelet-volumes \
  --set volumes[0].hostPath.path=/var/lib/kubelet \
  --wait
```

**Or add to values file:**
```yaml
volumeMounts:
- name: kubelet-volumes
  mountPath: /var/lib/kubelet
  readOnly: true

volumes:
- name: kubelet-volumes
  hostPath:
    path: /var/lib/kubelet
    type: Directory
```

**Result:** VirtualKubelet can now read projected volume files from k3s kubelet directory and send them to Interlink. Apptainer will find the files and mount them successfully.

### Option 2: Disable ServiceAccount Mounting (Workaround - if fix not available)

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

### Option 2: Disable ServiceAccount Mounting (Workaround - if fix not available)

If your container doesn't need to access the Kubernetes API:

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

### Option 3: Use Custom ServiceAccount

Create a ServiceAccount without token auto-mounting:

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

To fully resolve this limitation, ensure VirtualKubelet Helm deployment includes the kubelet volume mount:

**Helm Values:**
```yaml
volumeMounts:
- name: kubelet-volumes
  mountPath: /var/lib/kubelet
  readOnly: true

volumes:
- name: kubelet-volumes
  hostPath:
    path: /var/lib/kubelet
    type: Directory
```

**Or via Helm command:**
```bash
--set volumeMounts[0].name=kubelet-volumes \
--set volumeMounts[0].mountPath=/var/lib/kubelet \
--set volumeMounts[0].readOnly=true \
--set volumes[0].name=kubelet-volumes \
--set volumes[0].hostPath.path=/var/lib/kubelet
```

With this change:
1. VirtualKubelet can access projected volumes on the k3s host
2. It reads token, ca.crt, and namespace files
3. It sends them to Interlink API
4. Interlink includes them in sbatch script
5. Apptainer mounts them into container successfully
6. Container can access Kubernetes API

**This is a simple configuration fix, not a code change.**

## References

- VirtualKubelet GitHub: https://github.com/virtual-kubelet/virtual-kubelet
- Interlink GitHub: https://github.com/interlink-hq/interLink
- Kubernetes ServiceAccount Documentation: https://kubernetes.io/docs/concepts/configuration/secret/#service-account-token-secret
