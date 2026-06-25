# Testing Procedures: End-to-End Interlink Validation

This guide provides comprehensive testing procedures to verify your Interlink setup is working correctly.

## Overview

After completing all setup steps, you should perform the following tests in order:

1. **Component Health Tests** - Verify each component is running
2. **Network Connectivity Tests** - Verify machines can communicate
3. **SLURM Functionality Tests** - Verify SLURM jobs work
4. **Kubernetes Functionality Tests** - Verify k3s pods work
5. **Interlink Integration Tests** - Verify end-to-end flow
6. **Performance Tests** (optional) - Test under load

## Pre-Testing Checklist

Before starting tests, ensure:

- [ ] Machine 1 (192.168.2.170) - SLURM is running
- [ ] Machine 2 (192.168.2.84) - k3s is running
- [ ] Network connectivity between machines verified
- [ ] Interlink components deployed (if applicable)

## Test 1: Component Health Checks

### 1.1 Check SLURM Services on Machine 1

```bash
# SSH to Machine 1
ssh rocky@192.168.2.170

# Check slurmctld (controller)
sudo systemctl status slurmctld

# Check slurmd (compute daemon)
sudo systemctl status slurmd

# Check munge (authentication)
sudo systemctl status mungd

# If all show "active (running)", proceed to next test
```

### 1.2 Check k3s Services on Machine 2

```bash
# SSH to Machine 2
ssh rocky@192.168.2.84

# Check k3s service
sudo systemctl status k3s

# Check kubectl access
kubectl get nodes

# Check system pods
kubectl get pods -A

# Expected output shows multiple system pods in kube-system namespace
```

### 1.3 Check Interlink Components

```bash
# On Machine 1 - Check Interlink Server
ssh rocky@192.168.2.170
sudo systemctl status interlink-server

# On Machine 2 - Check VirtualKubelet
ssh rocky@192.168.2.84
kubectl get pods -n interlink
kubectl logs -n interlink -l app=virtualkubelet | head -20
```

**RESULT**: All services should show "active (running)" or similar running status.

## Test 2: Network Connectivity Tests

### 2.1 Basic Ping Tests

```bash
# From Machine 1 to Machine 2
ssh rocky@192.168.2.170
ping -c 5 192.168.2.84
ping -c 5 k3s-machine

# From Machine 2 to Machine 1
ssh rocky@192.168.2.84
ping -c 5 192.168.2.170
ping -c 5 slurm-machine
```

**EXPECTED**: All pings should succeed with 0% packet loss.

### 2.2 Port Connectivity Tests

```bash
# From Machine 2, test SLURM ports on Machine 1
ssh rocky@192.168.2.84

# Test slurmctld port
nc -zv 192.168.2.170 6817
echo "Result: Port 6817 (slurmctld)"

# Test slurmd port
nc -zv 192.168.2.170 6818
echo "Result: Port 6818 (slurmd)"

# Test Interlink Server port
nc -zv 192.168.2.170 3000
echo "Result: Port 3000 (Interlink)"

# From Machine 1, test k3s port on Machine 2
ssh rocky@192.168.2.170
nc -zv 192.168.2.84 6443
echo "Result: Port 6443 (k3s API)"
```

**EXPECTED**: All connections should show "succeeded".

### 2.3 SSH Access Test

```bash
# From Machine 1 to Machine 2
ssh rocky@192.168.2.170
ssh rocky@192.168.2.84 hostname

# From Machine 2 to Machine 1
ssh rocky@192.168.2.84
ssh rocky@192.168.2.170 hostname
```

**EXPECTED**: Commands should execute successfully and return the hostname.

## Test 3: SLURM Functionality Tests

### 3.1 Cluster Status

```bash
ssh rocky@192.168.2.170

# Check cluster info
sinfo

# Expected output:
# PARTITION  AVAIL  TIMELIMIT  NODES  STATE NODELIST
# default*      up   infinite      1   idle slurm-machine

# Get detailed cluster info
scontrol show config | head -20

# Check node status
scontrol show node slurm-machine
```

### 3.2 Submit and Run Job

```bash
ssh rocky@192.168.2.170

# Create test job script
cat > /tmp/test-job.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=test-slurm
#SBATCH --output=/tmp/slurm-test-%j.out
#SBATCH --error=/tmp/slurm-test-%j.err
#SBATCH --time=00:05:00
#SBATCH --ntasks=1

echo "=== SLURM Job Test ==="
echo "Hostname: $(hostname)"
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "CPU cores: $SLURM_CPUS_ON_NODE"
sleep 3
echo "Job completed successfully!"
EOF

chmod +x /tmp/test-job.sh

# Submit the job
JOB_ID=$(sbatch /tmp/test-job.sh | awk '{print $NF}')
echo "Submitted job ID: $JOB_ID"

# Monitor job
sleep 2
squeue

# Wait for completion
sleep 10
squeue

# Check output
cat /tmp/slurm-test-${JOB_ID}.out
cat /tmp/slurm-test-${JOB_ID}.err

# Get job accounting info
sacct -j $JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed
```

**EXPECTED**: Job should complete successfully with exit code 0 and output should show the test messages.

### 3.3 Multiple Job Test

```bash
ssh rocky@192.168.2.170

# Submit 3 jobs
for i in {1..3}; do
  sbatch /tmp/test-job.sh
done

# Monitor all jobs
squeue

# Wait for completion
sleep 15

# Show all jobs (including completed)
squeue --all

# Get summary
sacct --format=JobID,JobName,State,ExitCode,Start,End
```

**EXPECTED**: All 3 jobs should complete successfully.

## Test 4: Kubernetes Functionality Tests

### 4.1 Cluster and Node Status

```bash
ssh rocky@192.168.2.84

# Check cluster info
kubectl cluster-info

# Check nodes
kubectl get nodes -o wide

# Expected: Shows k3s-machine as Ready

# Check system pods
kubectl get pods -A

# Expected: Shows core system pods running
```

### 4.2 Deploy Test Application

```bash
ssh rocky@192.168.2.84

# Deploy nginx
kubectl create deployment nginx-test --image=nginx

# Wait for deployment
sleep 10

# Check deployment
kubectl get deployment nginx-test
kubectl get pods -l app=nginx-test

# Expected: Pod should be running

# Expose as service
kubectl expose deployment nginx-test --port=80 --type=NodePort

# Get NodePort
NODE_PORT=$(kubectl get svc nginx-test -o jsonpath='{.spec.ports[0].nodePort}')
echo "Service on port: $NODE_PORT"

# Test service
curl http://localhost:$NODE_PORT

# Expected: Should get nginx welcome page

# Clean up
kubectl delete svc nginx-test
kubectl delete deployment nginx-test
```

### 4.3 Pod Networking Test

```bash
ssh rocky@192.168.2.84

# Deploy two test pods
kubectl run test-pod-1 --image=busybox --restart=Never -- sleep 3600
kubectl run test-pod-2 --image=busybox --restart=Never -- sleep 3600

# Wait for pods
sleep 10

# Get pod IPs
POD1_IP=$(kubectl get pod test-pod-1 -o jsonpath='{.status.podIP}')
POD2_IP=$(kubectl get pod test-pod-2 -o jsonpath='{.status.podIP}')

echo "Pod 1: $POD1_IP"
echo "Pod 2: $POD2_IP"

# Test connectivity between pods
kubectl exec test-pod-1 -- ping -c 3 $POD2_IP

# Expected: All pings should succeed

# Test DNS
kubectl exec test-pod-1 -- nslookup kubernetes.default

# Expected: Should resolve to cluster IP

# Clean up
kubectl delete pod test-pod-1 test-pod-2
```

## Test 5: Interlink Integration Tests

### 5.1 VirtualKubelet Node Visibility

```bash
ssh rocky@192.168.2.84

# Check if SLURM worker node appears
kubectl get nodes

# Expected output should include:
# k3s-machine    Ready     control-plane,master   Xd   vX.X.X
# slurm-worker   Ready     agent                  Xm   vX.X.X

# Get details on virtual node
kubectl describe node slurm-worker

# Expected: Should show capacities and conditions
```

### 5.2 Pod Scheduling on SLURM Worker

```bash
ssh rocky@192.168.2.84

# Create test pod targeting SLURM worker
cat > /tmp/slurm-pod.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: interlink-test-pod
  namespace: default
spec:
  nodeSelector:
    kubernetes.io/hostname: slurm-worker
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sh", "-c"]
    args: 
    - |
      echo "=== Pod Test Via Interlink ==="
      echo "Hostname: $(hostname)"
      echo "Date: $(date)"
      echo "Working directory: $(pwd)"
      sleep 5
      echo "Pod completed!"
  restartPolicy: Never
EOF

# Submit pod
kubectl apply -f /tmp/slurm-pod.yaml

# Monitor pod
sleep 3
kubectl get pods

# Get pod details
kubectl describe pod interlink-test-pod

# Expected: Pod should be created and scheduled

# Check logs
sleep 10
kubectl logs interlink-test-pod

# Expected: Should show the echo output
```

### 5.3 Verify Job Appears in SLURM

```bash
ssh rocky@192.168.2.170

# List jobs while pod is running (on Machine 2 side)
squeue

# Expected: Should show job submitted from Interlink

# Get job details
LAST_JOB=$(squeue -o "%i" | tail -1)
scontrol show job $LAST_JOB

# Expected: Job details should show the pod-related job
```

### 5.4 End-to-End Pod Lifecycle

```bash
ssh rocky@192.168.2.84

# Create pod with specific requirements
cat > /tmp/lifecycle-test.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: lifecycle-test
spec:
  nodeSelector:
    kubernetes.io/hostname: slurm-worker
  containers:
  - name: app
    image: busybox
    command: ["sh", "-c"]
    args:
    - |
      for i in {1..5}; do
        echo "Iteration $i at $(date)"
        sleep 1
      done
      echo "All iterations complete!"
  restartPolicy: Never
EOF

# Submit pod
kubectl apply -f /tmp/lifecycle-test.yaml

# Monitor state changes
echo "Initial state:"
kubectl get pods

echo "Waiting 3 seconds..."
sleep 3

echo "Running state:"
kubectl get pods

echo "Waiting for completion..."
sleep 10

echo "Final state:"
kubectl get pods

# Get completion details
kubectl get pod lifecycle-test -o jsonpath='{.status.phase}'
kubectl describe pod lifecycle-test | grep -A 5 "Status:"

# Expected: Pod should go through: Pending -> Running -> Succeeded

# Clean up
kubectl delete pod lifecycle-test
```

## Test 6: Batch Job Test

### 6.1 Multiple Pods via Interlink

```bash
ssh rocky@192.168.2.84

# Create batch job manifest
cat > /tmp/batch-test.yaml << 'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: interlink-batch-job
spec:
  parallelism: 3
  completions: 3
  template:
    spec:
      nodeSelector:
        kubernetes.io/hostname: slurm-worker
      containers:
      - name: worker
        image: busybox:latest
        command: ["sh", "-c"]
        args:
        - |
          echo "Job starting at $(date)"
          hostname
          sleep 10
          echo "Job completed at $(date)"
      restartPolicy: Never
EOF

# Submit batch job
kubectl apply -f /tmp/batch-test.yaml

# Monitor job progress
for i in {1..5}; do
  echo "=== Iteration $i ==="
  kubectl get job interlink-batch-job
  kubectl get pods -l job-name=interlink-batch-job
  sleep 5
done

# Get job completion status
kubectl get job interlink-batch-job

# Clean up
kubectl delete job interlink-batch-job
```

**EXPECTED**: All pods should be scheduled on SLURM worker and complete successfully.

## Test 7: Resource Testing

### 7.1 CPU Utilization

```bash
ssh rocky@192.168.2.84

# Create CPU-intensive pod
cat > /tmp/cpu-test.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: cpu-test
spec:
  nodeSelector:
    kubernetes.io/hostname: slurm-worker
  containers:
  - name: cpu-worker
    image: busybox
    command: ["/bin/sh", "-c"]
    args:
    - |
      # CPU intensive task
      for i in {1..3}; do
        echo "CPU task iteration $i"
        # Prime number calculation
        for n in {1..1000}; do
          echo $n | bc > /dev/null
        done
      done
      echo "CPU test complete"
  restartPolicy: Never
EOF

kubectl apply -f /tmp/cpu-test.yaml

# Monitor on both sides
echo "=== Kubernetes side ==="
sleep 5
kubectl get pods
kubectl describe pod cpu-test | grep -E "State:|Phase:"

echo ""
echo "=== SLURM side ==="
ssh rocky@192.168.2.170 squeue

# Clean up
kubectl delete pod cpu-test
```

## Test 8: Error Handling

### 8.1 Pod with Exit Code

```bash
ssh rocky@192.168.2.84

# Create pod that exits with error
cat > /tmp/error-test.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: error-test
spec:
  nodeSelector:
    kubernetes.io/hostname: slurm-worker
  containers:
  - name: failing-app
    image: busybox
    command: ["/bin/sh", "-c"]
    args:
    - |
      echo "This pod will fail"
      exit 1
  restartPolicy: Never
EOF

kubectl apply -f /tmp/error-test.yaml

# Monitor
sleep 10

# Get status
kubectl get pod error-test
kubectl describe pod error-test

# Check exit code
kubectl get pod error-test -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}'

# Expected: Exit code should be 1

# Clean up
kubectl delete pod error-test
```

## Test Summary

Run this final verification:

```bash
echo "=== FINAL TEST SUMMARY ==="

# Test 1: Component Health
echo "1. Component Health:"
ssh rocky@192.168.2.170 'sudo systemctl is-active slurmctld slurmd mungd'
ssh rocky@192.168.2.84 'sudo systemctl is-active k3s'

# Test 2: Network
echo "2. Network Connectivity:"
ping -c 1 192.168.2.170 && echo "  Machine 1: OK"
ping -c 1 192.168.2.84 && echo "  Machine 2: OK"

# Test 3: SLURM
echo "3. SLURM Status:"
ssh rocky@192.168.2.170 'sinfo'

# Test 4: Kubernetes
echo "4. Kubernetes Nodes:"
ssh rocky@192.168.2.84 'kubectl get nodes'

# Test 5: Interlink
echo "5. Virtual Node:"
ssh rocky@192.168.2.84 'kubectl get nodes | grep slurm-worker'

echo ""
echo "=== ALL TESTS COMPLETE ==="
```

## Troubleshooting Failed Tests

If any test fails, refer to:

1. **SLURM issues** → See [Troubleshooting - SLURM Section](troubleshooting.md#slurm-issues)
2. **Kubernetes issues** → See [Troubleshooting - Kubernetes Section](troubleshooting.md#kubernetes-issues)
3. **Interlink issues** → See [Troubleshooting - Interlink Section](troubleshooting.md#interlink-issues)
4. **Network issues** → See [Troubleshooting - Network Section](troubleshooting.md#network-issues)

---

**All tests passing?** Proceed to production or refer to troubleshooting! ➡️
