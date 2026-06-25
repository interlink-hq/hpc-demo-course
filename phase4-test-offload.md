# Phase 4: Testing Pod Offload to SLURM

Test real pod submission from k3s to SLURM via Interlink bridge.

## Prerequisites

- Phase 1-3 completed: SLURM on Machine 1, k3s on Machine 2, Interlink API and VirtualKubelet running
- Both services accessible (Interlink API on port 3000, k3s on port 6443)
- Kubernetes nodes visible from Machine 2

## Step 1: Verify Setup

Check that both components are running:

```bash
# Machine 1: Interlink API
ssh rocky@192.168.2.170 'ps aux | grep interlink-api | grep -v grep'

# Output should show:
# rocky 56644 ... ./interlink-api

# Machine 2: VirtualKubelet  
ssh rocky@192.168.2.84 'ps aux | grep virtual-kubelet | grep -v grep'

# Output should show:
# rocky 46737 ... ./virtual-kubelet -configpath=./vk-config.yaml -nodename=interlink-node
```

### Check Kubernetes nodes

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
/usr/local/bin/k3s kubectl get nodes -o wide
```

Expected output (note: `interlink-node` may show as `NotReady` during initialization):

```
NAME                    STATUS     ROLES           VERSION
interlink-node          NotReady    agent           test
corso-hpc-2.cloudcnaf   Ready       control-plane   v1.31.4+k3s1
```

## Step 2: Monitor Logs Before Testing

Open separate terminals to monitor components:

```bash
# Terminal 1: Monitor Interlink API on Machine 1
ssh rocky@192.168.2.170 'tail -f ~/interlink/interlink-api.log'

# Terminal 2: Monitor VirtualKubelet on Machine 2
ssh rocky@192.168.2.84 'tail -f ~/interlink/vk.log'

# Terminal 3: Monitor k3s on Machine 2
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
/usr/local/bin/k3s kubectl get pods -w
```

## Step 3: Create Test Pod Scheduled to Interlink Node

Create a simple pod that will run on the virtual kubelet node:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create and submit test pod
/usr/local/bin/k3s kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-offload-pod
  namespace: default
spec:
  nodeName: interlink-node
  restartPolicy: Never
  containers:
  - name: test-container
    image: busybox:latest
    command:
    - /bin/sh
    - -c
    - echo "Hello from SLURM job submitted via Interlink"; sleep 10
EOF

echo "✓ Pod created, watching status..."
```

## Step 4: Monitor Pod Status

Watch the pod status in real-time:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Monitor pod status
/usr/local/bin/k3s kubectl get pod test-offload-pod -o wide --watch

# In another terminal, describe the pod for detailed info
/usr/local/bin/k3s kubectl describe pod test-offload-pod
```

### Expected Behavior

**Initial state (0-5 seconds):**
```
NAME                  READY   STATUS    RESTARTS   AGE
test-offload-pod      0/1     Pending   0          2s
```

**During execution (5-15 seconds):**
```
NAME                  READY   STATUS    RESTARTS   AGE
test-offload-pod      0/1     Running   0          8s
```

**After completion (15-20 seconds):**
```
NAME                  READY   STATUS      RESTARTS   AGE
test-offload-pod      0/1     Completed   0          18s
```

## Step 5: Check Pod Logs

Retrieve logs from the completed pod:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

/usr/local/bin/k3s kubectl logs test-offload-pod

# Expected output:
# Hello from SLURM job submitted via Interlink
```

## Step 6: Verify Job in SLURM

On Machine 1, check if the job was submitted to SLURM:

```bash
ssh rocky@192.168.2.170 << 'SLURMCHECK'
echo "=== SLURM Queue Status ==="
/opt/slurm/bin/squeue

echo ""
echo "=== Recent Jobs ==="
/opt/slurm/bin/squeue --all

echo ""
echo "=== Job Info (if job ID available) ==="
# Get most recent job ID
JID=$(/opt/slurm/bin/squeue --all -h -o "%i" | head -1)
if [ ! -z "$JID" ]; then
  /opt/slurm/bin/scontrol show job $JID
else
  echo "No recent jobs in queue"
fi

SLURMCHECK
```

## Step 7: Test Pod Deletion

Clean up the test pod:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

/usr/local/bin/k3s kubectl delete pod test-offload-pod

echo "✓ Pod deleted"

# Verify deletion
/usr/local/bin/k3s kubectl get pods
```

## Step 8: Analyze Logs

### Interlink API Logs (Machine 1)

```bash
ssh rocky@192.168.2.170 << 'APILOGS'
echo "=== Interlink API Logs ==="
tail -50 ~/interlink/interlink-api.log | grep -E "error|pod|offload|submitted|status"

APILOGS
```

Look for messages like:
- Pod received from VirtualKubelet
- Job submitted to SLURM
- Job status updates

### VirtualKubelet Logs (Machine 2)

```bash
ssh rocky@192.168.2.84 << 'VKLOGS'
echo "=== VirtualKubelet Logs ==="
tail -100 ~/interlink/vk.log | grep -E "error|Pod\|offload\|Interlink\|gRPC"

VKLOGS
```

Look for messages like:
- Pod watch events
- Interlink API connection status
- Pod lifecycle events (Create, Run, Delete)

## Troubleshooting

### Pod stays in Pending state

1. **Check node status:**
   ```bash
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   /usr/local/bin/k3s kubectl describe node interlink-node
   ```

2. **Check VirtualKubelet connectivity:**
   ```bash
   ssh rocky@192.168.2.84 'tail -50 ~/interlink/vk.log | grep -i "error\|fail\|connect"'
   ```

3. **Check Interlink API:**
   ```bash
   ssh rocky@192.168.2.170 'curl -s http://localhost:3000/ | head -20'
   ```

### Pod shows Running but never completes

1. **Check if image pull is failing:**
   ```bash
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   /usr/local/bin/k3s kubectl describe pod test-offload-pod
   ```

2. **Verify SLURM job is actually running:**
   ```bash
   ssh rocky@192.168.2.170 '/opt/slurm/bin/squeue'
   ```

### Network connectivity issues

1. **Test IP connectivity between machines:**
   ```bash
   ssh rocky@192.168.2.170 'ping -c 3 192.168.2.84'
   ssh rocky@192.168.2.84 'ping -c 3 192.168.2.170'
   ```

2. **Test port accessibility:**
   ```bash
   ssh rocky@192.168.2.84 'curl -v http://192.168.2.170:3000/ 2>&1 | head -20'
   ```

## Success Criteria

✓ Pod is submitted to k3s  
✓ VirtualKubelet receives pod creation event  
✓ Pod is translated to SLURM job  
✓ Job appears in SLURM queue  
✓ Job completes successfully  
✓ Pod status reflects job completion  
✓ Pod logs are accessible in k3s  

## Advanced Testing

### Test with custom container image

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

/usr/local/bin/k3s kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-python-pod
  namespace: default
spec:
  nodeName: interlink-node
  restartPolicy: Never
  containers:
  - name: python-container
    image: python:3.9-slim
    command:
    - python
    - -c
    - |
      print("Running Python in SLURM job")
      import socket
      print(f"Hostname: {socket.gethostname()}")
      print("✓ Pod successfully offloaded to SLURM")
EOF
```

### Test with resource requests

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

/usr/local/bin/k3s kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-resources-pod
  namespace: default
spec:
  nodeName: interlink-node
  restartPolicy: Never
  containers:
  - name: test-container
    image: busybox:latest
    command: ["echo", "Testing resource requests"]
    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "500m"
EOF
```

### Test multiple pods in parallel

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

for i in {1..3}; do
  /usr/local/bin/k3s kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: parallel-pod-$i
  namespace: default
spec:
  nodeName: interlink-node
  restartPolicy: Never
  containers:
  - name: worker
    image: busybox:latest
    command: ["echo", "Pod $i running in SLURM"]
EOF
  echo "✓ Pod $i submitted"
done

# Monitor all pods
/usr/local/bin/k3s kubectl get pods -l run=parallel-pod -w
```

---

**Summary:**

This phase validates that the Interlink bridge is working correctly by:
1. Submitting a pod to the virtual kubelet node
2. Observing the pod being offloaded to SLURM
3. Verifying the pod executes and completes
4. Confirming logs are accessible in Kubernetes

If pods are successfully offloaded and complete, the Interlink SLURM↔Kubernetes bridge is operational.
