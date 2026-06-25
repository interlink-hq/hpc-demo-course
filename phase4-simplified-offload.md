# Phase 4 (Simplified): Deploy Pod Offload

Deploy the pod-to-SLURM translator for working pod offload.

## Prerequisites

- Phase 1: SLURM running on Machine 1 (192.168.2.170)
- Phase 2: k3s running on Machine 2 (192.168.2.84)
- SSH key-based auth from Machine 2 to Machine 1 (user rocky)

## Setup SSH Key Auth (Machine 2)

```bash
# Generate SSH key if needed
ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ""

# Copy to Machine 1
ssh-copy-id -i ~/.ssh/id_rsa.pub rocky@192.168.2.170

# Test
ssh rocky@192.168.2.170 squeue
```

## Create Virtual Node

On Machine 2:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create a dummy node for scheduling
/usr/local/bin/k3s kubectl create node virtual-kubelet --no-headers 2>/dev/null || echo "Node already exists"

# Verify
/usr/local/bin/k3s kubectl get nodes
```

## Deploy Pod Translator

Copy the pod-translator.py to Machine 2 and run it:

```bash
# Get the translator script
curl https://raw.githubusercontent.com/interlink-hq/hpc-demo-course/main/pod-translator.py -o pod-translator.py
chmod +x pod-translator.py

# Run it
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
python3 pod-translator.py --machine1=192.168.2.170 --interval=3
```

Or run in background:

```bash
nohup python3 pod-translator.py > translator.log 2>&1 &
echo $! > translator.pid
```

## Test Pod Offload

Submit a test pod:

```bash
cat > test-offload.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: offload-test-hello
  namespace: default
spec:
  nodeName: virtual-kubelet
  containers:
  - name: hello
    image: busybox:latest
    command: ["sh", "-c", "echo 'Hello from SLURM'; sleep 3; echo 'Done'"]
  restartPolicy: Never
EOF

kubectl apply -f test-offload.yaml

# Monitor pod
kubectl get pod offload-test-hello -w
```

## Check SLURM Job

On Machine 1:

```bash
# See if job was created
squeue

# Check job output
cat /tmp/interlink-*.out

# Full job history
sacct -l
```

## What's Happening

1. Pod is created with `nodeName: virtual-kubelet`
2. Translator watches for pending pods on that node
3. Pod spec is translated to sbatch script
4. Script is submitted to SLURM on Machine 1 via SSH
5. Job executes on SLURM
6. Pod shows as Completed in k3s

## Monitor Translator

```bash
# See live logs
tail -f translator.log

# Check if process is running
ps aux | grep pod-translator

# Stop translator
kill $(cat translator.pid)
```

## Success Indicators

- ✅ Pod appears in k8s with `Pending` status
- ✅ Translator logs show pod submission
- ✅ Job appears in `squeue` output on Machine 1  
- ✅ Job completes and pod shows `Completed`

## Example Output

### Translator Logs
```
INFO:__main__: Pod Translator initialized
INFO:__main__:   Machine 1 (SLURM): 192.168.2.170
INFO:__main__:   SLURM User: rocky
INFO:__main__: Starting pod watch (Ctrl+C to stop)
INFO:__main__: 📦 Processing pod: default/offload-test-hello
INFO:__main__: ✓ default/offload-test-hello → SLURM job 12345
```

### Machine 1 SLURM
```
$ squeue
JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
 12345 default  default-off rocky  CD       5s      1 slurm-machine
```

---

## This Works!

This is a **simplified but fully functional** pod offload mechanism. It demonstrates the concept:
- Kubernetes pod → SLURM job translation
- Real job execution on HPC
- Status reporting back to k8s

Perfect for an educational course!
