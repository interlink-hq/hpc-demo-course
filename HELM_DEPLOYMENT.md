# VirtualKubelet Helm Chart Deployment

This document describes deploying VirtualKubelet to k3s using the official Helm chart approach. This is the **recommended method** for production deployments.

## Overview

Instead of manually running VirtualKubelet binaries, we use Helm to manage the deployment. This provides:
- Declarative configuration management
- Automatic pod lifecycle management
- Easy upgrades and rollbacks
- Integration with k3s package management

## Prerequisites

1. **Helm 3.x** installed on Machine 2 (k3s)
2. **VirtualKubelet binary** pre-downloaded to Machine 2 at `/home/rocky/vk`
3. **Interlink API** running on Machine 1 (port 3000)
4. **SLURM Plugin** running on Machine 1 (port 4000)
5. **k3s with Apptainer support** on both machines

## Quick Deploy

The Helm chart is provided in the repository at `virtual-kubelet-chart/`:

```bash
ssh rocky@192.168.2.84 << 'HELM'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Install or upgrade VirtualKubelet
helm upgrade --install virtual-kubelet /path/to/virtual-kubelet-chart \
  --namespace default
HELM
```

## Chart Structure

```
virtual-kubelet-chart/
├── Chart.yaml                 # Chart metadata
├── values.yaml                # Default configuration values
└── templates/
    ├── deployment.yaml        # VirtualKubelet Deployment
    ├── serviceaccount.yaml    # ServiceAccount for RBAC
    ├── rbac.yaml              # ClusterRole and ClusterRoleBinding
    └── configmap.yaml         # VirtualKubelet configuration
```

## Configuration

The chart is configured via `values.yaml`:

```yaml
nodeName: interlink-node
interlink:
  url: "http://192.168.2.170"
  port: "3000"
vk:
  image:
    repository: alpine
    tag: "3.18"
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi
serviceAccount:
  create: true
  name: virtual-kubelet
namespace: default
```

### Configuration Options

- **nodeName**: Name of the virtual Kubernetes node (must be "interlink-node")
- **interlink.url**: URL where Interlink API is running (Machine 1)
- **interlink.port**: Port for Interlink API (default: 3000)
- **vk.image**: Container image for running the deployment
- **vk.resources**: CPU/memory requests and limits for the pod

## Customization

To customize the deployment, modify `values.yaml` before installing:

```bash
helm upgrade --install virtual-kubelet ./virtual-kubelet-chart \
  --set interlink.url="http://192.168.2.170" \
  --set interlink.port="3000" \
  --namespace default
```

## Deployment Details

### What the Chart Does

1. **Creates ServiceAccount** with necessary RBAC permissions
2. **Creates ClusterRole** for VirtualKubelet operations on pods and nodes
3. **Creates ClusterRoleBinding** to bind the role to the service account
4. **Deploys VirtualKubelet pod** with:
   - Volume mounts for k3s kubeconfig and host binaries
   - Host network enabled (required for Interlink communication)
   - Proper tolerations for the virtual node
   - Node selector for control-plane (runs on k3s master)
   - Liveness probe to monitor pod health

### RBAC Permissions

The chart grants VirtualKubelet the following permissions:

```
Leases (coordination.k8s.io)      - create, update, get, list, watch, patch
Pods (core)                        - delete, get, list, watch, patch
Pod Status (core)                  - update, patch
Nodes (core)                       - create, get
Node Status (core)                 - update, patch
Events (core)                      - create, patch
ConfigMaps, Secrets (core)        - get, list, watch
```

## Verification

### Check Helm Release

```bash
ssh rocky@192.168.2.84 << 'VERIFY'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# List releases
helm list -n default

# Check release status
helm status virtual-kubelet -n default
VERIFY
```

### Check VirtualKubelet Pod

```bash
ssh rocky@192.168.2.84 << 'VERIFY'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Get pod status
kubectl get pods -n default -l app=virtual-kubelet-vk

# View logs
kubectl logs -n default -l app=virtual-kubelet-vk --tail=50

# Describe pod
kubectl describe pod -n default -l app=virtual-kubelet-vk
VERIFY
```

### Check Virtual Node Registration

```bash
ssh rocky@192.168.2.84 << 'VERIFY'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# List nodes
kubectl get nodes

# Describe virtual node
kubectl describe node interlink-node
VERIFY
```

Expected output shows the virtual node with:
- Status: NotReady (expected for virtual nodes)
- Taints: virtual-node.interlink/no-schedule, node.kubernetes.io/not-ready, etc.
- Labels: virtual-node.interlink/type=virtual-kubelet

## Testing Pod Offload

Once the chart is deployed, test pod offloading:

```bash
ssh rocky@192.168.2.84 << 'TEST'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create test pod
cat > /tmp/test-pod-helm.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-helm-offload
spec:
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
    effect: NoSchedule
  containers:
  - name: app
    image: busybox:latest
    command: ["echo", "Test from Helm-deployed VirtualKubelet"]
EOF

kubectl apply -f /tmp/test-pod-helm.yaml

# Monitor pod
kubectl get pods test-helm-offload -w

# Check job on SLURM
TEST
```

### Verify SLURM Job

```bash
ssh rocky@192.168.2.170 'squeue' | grep -i test
```

## Upgrade and Rollback

### Upgrade VirtualKubelet Version

To upgrade to a new version:

```bash
helm upgrade virtual-kubelet ./virtual-kubelet-chart \
  --namespace default
```

### Rollback to Previous Version

```bash
helm rollback virtual-kubelet \
  --namespace default
```

### View Release History

```bash
helm history virtual-kubelet -n default
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod virtual-kubelet-vk-* -n default

# Check logs
kubectl logs -n default -l app=virtual-kubelet-vk

# Common issues:
# - VirtualKubelet binary not found at /home/rocky/vk
# - Cannot access k3s kubeconfig at /etc/rancher/k3s/k3s.yaml
# - Interlink API not reachable at 192.168.2.170:3000
```

### VirtualKubelet Binary Not Found

Ensure the binary exists on the host:

```bash
ssh rocky@192.168.2.84 'ls -lh /home/rocky/vk'
```

If missing, download it:

```bash
ssh rocky@192.168.2.84 << 'DL'
VER="0.6.1-patch1"
curl -sL "https://github.com/interlink-hq/interLink/releases/download/$VER/virtual-kubelet_Linux_x86_64" \
  -o /home/rocky/vk && chmod +x /home/rocky/vk
DL
```

### Pods Not Offloading

Check that:
1. VirtualKubelet pod is running: `kubectl get pods -l app=virtual-kubelet-vk`
2. Virtual node is registered: `kubectl get nodes`
3. Interlink API is reachable: `ssh rocky@192.168.2.84 'curl http://192.168.2.170:3000/'`
4. SLURM plugin is running on Machine 1: `ssh rocky@192.168.2.170 'ps aux | grep slurm-plugin'`
5. Pod has correct tolerations and nodeSelector (see Testing section above)

## Uninstall

To remove the VirtualKubelet deployment:

```bash
helm uninstall virtual-kubelet -n default
```

This will remove:
- VirtualKubelet Deployment
- ServiceAccount
- ClusterRole and ClusterRoleBinding
- ConfigMap

Note: The virtual node may persist briefly after uninstall. It will be cleaned up automatically.

## Next Steps

For more information:
- See `phase4-test-offload.md` for comprehensive testing procedures
- See `CRITICAL_FINDINGS.md` for technical deep-dive on known issues
- See `README.md` for overall architecture overview
