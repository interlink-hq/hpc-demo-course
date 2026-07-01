# Phase 4: Testing Pod Offload to SLURM

Test real pod submission from k3s to SLURM via Interlink bridge.

## Prerequisites

- Phase 1-3 completed: SLURM on Machine 1, k3s on Machine 2, Interlink running
- VirtualKubelet deployed via Helm to k3s
- Both services accessible (Interlink API on port 3000, k3s on port 6443)
- Virtual node "interlink-node" visible in Kubernetes

## Step 1: Verify Setup

Check that all components are running:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Machine 1: Check Interlink API and Plugin
ssh rocky@192.168.2.170 'ps aux | grep -E "[i]nterlink-api|[s]lurm-plugin"'

# Machine 2: Check VirtualKubelet pod
kubectl get pods -n virtual-kubelet -o wide

# Check virtual node
kubectl get nodes
```

Expected output shows:

- Interlink API and SLURM Plugin running on Machine 1
- VirtualKubelet pod in virtual-kubelet namespace on Machine 2
- Virtual node "interlink-node" with status Ready

## Step 2: Monitor Logs Before Testing

Open separate terminals to monitor:

```bash
# Terminal 1: Monitor Interlink API on Machine 1
ssh rocky@192.168.2.170 'tail -f ~/interlink/interlink-api.log'

# Terminal 2: Monitor VirtualKubelet logs
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl logs -n virtual-kubelet -l app=virtual-kubelet -f

# Terminal 3: Monitor k3s pods
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get pods -w
```

## Step 3: Create Test Pod with Proper Scheduling Constraints

Create a pod scheduled to the Interlink virtual node with proper constraints:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create and submit test pod
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-offload
  namespace: default
spec:
  automountServiceAccountToken: false
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
    command: ["/bin/sh", "-c"]
    args: ["echo 'Successfully offloaded to SLURM! Sleeping 5 minutes now!'; sleep 300"]
EOF

echo "✓ Pod created, checking status..."
```

**Why these configurations:**

- `automountServiceAccountToken: false` - Workaround for token mount limitation
- `nodeSelector: virtual-node.interlink/type: virtual-kubelet` - Matches Interlink node label
- `tolerations` with `Equal` and `value: "true"` - Allows pod to tolerate VirtualKubelet taints

## Step 4: Monitor Pod Status

Watch the pod in real-time:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Monitor pod status
kubectl get pod test-offload -o wide --watch

# In another terminal, describe the pod
kubectl describe pod test-offload
```

### Expected Behavior

**Stage 1 - Pod Pending (0-3 seconds):**

```
NAME           READY   STATUS    RESTARTS   AGE   IP       NODE
test-offload   0/1     Pending   0          1s    <none>   <none>
```

**Stage 2 - Pod Running (3-10 seconds):**

```
NAME           READY   STATUS    RESTARTS   AGE   IP          NODE
test-offload   0/1     Running   0          5s    127.0.0.1   interlink-node
```

Note: IP is 127.0.0.1 (local to VirtualKubelet), node is interlink-node (virtual)

## Step 5: Verify SLURM Job Creation

On Machine 1, check that SLURM job was created:

```bash
ssh rocky@192.168.2.170 << 'SLURM_CHECK'
echo "=== Recent SLURM Jobs ==="
squeue -u rocky | head -10

echo ""
echo "=== Job Directories ==="
ls -lart /tmp/.interlink/ | tail -3

SLURM_CHECK
```

## Step 6: Check Pod Logs

Try to retrieve pod logs:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Check logs
kubectl logs test-offload

# If logs fail (TLS issue), check pod output on SLURM side
ssh rocky@192.168.2.170 'find /tmp/.interlink -name "run-*.out" -type f | xargs tail -20'
```

### Expected Output

From pod logs or SLURM job output:

```
Successfully offloaded to SLURM!
```

## Troubleshooting

### Pod stuck in Pending

**Symptoms:** Pod remains Pending after 30 seconds

**Debugging:**

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl describe pod test-offload
```

Check for:

- Missing tolerations → Add all three taints
- Wrong nodeSelector → Use `virtual-node.interlink/type: virtual-kubelet`
- VirtualKubelet not running → Check `kubectl get pods -n virtual-kubelet`

### Pod shows Running but no SLURM job

**Symptoms:** Pod is Running but no job visible in `squeue`

**Debugging:**

1. Check VirtualKubelet logs: `kubectl logs -n virtual-kubelet -l app=virtual-kubelet`
2. Check Interlink API logs: `ssh rocky@192.168.2.170 'tail -50 ~/interlink/interlink-api.log'`
3. Check SLURM plugin logs: `ssh rocky@192.168.2.170 'tail -50 ~/interlink/slurm-plugin.log'`

### Mount errors in pod output

**Symptoms:** Job output shows "WARNING: skipping mount of ... token"

**This is expected** with the current VirtualKubelet version. ServiceAccount tokens cannot be exported to SLURM jobs. Workaround: use `automountServiceAccountToken: false` (already in test pod).

## Success Criteria

✅ Pod status shows Running on interlink-node  
✅ SLURM job created and executed  
✅ Job output shows "Successfully offloaded to SLURM!"  
✅ Pod can be deleted without errors

When all criteria are met, the Interlink bridge is working end-to-end!
