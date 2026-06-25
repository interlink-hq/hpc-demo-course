# Phase 4: Test End-to-End Pod Offload

Verify that pods submitted to the virtual-kubelet node are offloaded to SLURM jobs.

## Prerequisites

- Phase 1: SLURM running on Machine 1
- Phase 2: k3s running on Machine 2
- Phase 3: VirtualKubelet, Interlink API, SLURM Plugin all deployed

## Test 1: Verify Virtual Node Registration

On Machine 2:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Check that virtual-kubelet node is registered and Ready
kubectl get nodes
kubectl describe node virtual-kubelet

# Should show:
# Name: virtual-kubelet
# Status: Ready
```

## Test 2: Submit Simple Pod to Virtual Node

On Machine 2:

```bash
# Create test pod
cat > test-pod.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: slurm-test-hello
  namespace: default
spec:
  nodeName: virtual-kubelet
  containers:
  - name: hello
    image: busybox:latest
    command: ["sh", "-c", "echo 'Hello from SLURM'; sleep 5; echo 'Done'"]
  restartPolicy: Never
EOF

# Submit the pod
kubectl apply -f test-pod.yaml

# Watch the pod status
kubectl get pod slurm-test-hello -w

# Should show:
# NAME                READY   STATUS      RESTARTS   AGE
# slurm-test-hello    0/1     Completed   0          30s
```

## Test 3: Check Job on SLURM (Machine 1)

On Machine 1:

```bash
# Check SLURM job was created
squeue

# Should show a job like:
# JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
# 1     default       slurm... rocky  CD      5s      1 machine1

# Check job output
sacct -l

# See the job's output
cat /tmp/.interlink/*/output.log 2>/dev/null || echo "No output yet"
```

## Test 4: Pod Logs and Status

On Machine 2:

```bash
# Get pod logs
kubectl logs slurm-test-hello

# Should show: "Hello from SLURM" and "Done"

# Detailed pod status
kubectl describe pod slurm-test-hello

# Check VirtualKubelet logs for details
tail -50 ~/interlink-setup/interlink/vk.log
```

## Test 5: Multiple Pods

Submit multiple pods to test:

```bash
for i in {1..3}; do
  cat > pod-$i.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: slurm-job-$i
  namespace: default
spec:
  nodeName: virtual-kubelet
  containers:
  - name: job
    image: busybox:latest
    command: ["sh", "-c", "echo 'Job $i running'; sleep 10"]
  restartPolicy: Never
EOF

  kubectl apply -f pod-$i.yaml
done

# Monitor all pods
kubectl get pods -w

# Check all SLURM jobs on Machine 1
ssh rocky@192.168.2.170 'squeue'
```

## Troubleshooting

### Pods stuck in Pending

```bash
# Check VirtualKubelet logs
tail -100 ~/interlink-setup/interlink/vk.log

# Check Interlink API logs (on Machine 1)
docker logs interlink-api --tail=100

# Check SLURM plugin logs (on Machine 1)
docker logs interlink-plugin --tail=100
```

### Check Interlink API Connectivity

On Machine 2:

```bash
# Test if API is reachable
curl -v http://192.168.2.170:3000/pinglink

# Should get: {"status": "ok"}
```

### Verify SLURM on Machine 1

```bash
ssh rocky@192.168.2.170

# Check SLURM is running
systemctl status slurmd
systemctl status slurmctld

# Manual test job
echo '#!/bin/bash
echo Test
sleep 5' | sbatch

squeue
```

## Success Criteria

When everything works:

1. ✅ Virtual-kubelet node shows as Ready in k3s
2. ✅ Submitting pod to virtual-kubelet creates it instantly (not Pending)
3. ✅ Pod completes on SLURM (shows as Completed in k3s)
4. ✅ SLURM job appears in `squeue` on Machine 1
5. ✅ Pod logs from SLURM job output are retrievable with `kubectl logs`

This is **real pod offload to HPC** 🎉

---

## Next Steps

- Monitor production workloads
- Add resource limits and job specifications
- Implement pod persistence across node failures
- Add monitoring and logging infrastructure
