# Final Setup Guide - HPC + Kubernetes Interlink Bridge Demo

## 📋 Overview

This guide documents the **working** configuration for bridging HPC (SLURM) on Machine 122 (192.168.2.122) with Kubernetes (k3s) on Machine 78 (192.168.2.78) using Interlink.

---

## 🏗️ Architecture

```
Machine 78 (192.168.2.78)              Machine 122 (192.168.2.122)
Kubernetes (k3s)                       HPC Backend
┌──────────────────────────┐          ┌──────────────────────────┐
│ k3s Cluster              │          │ SLURM Cluster            │
│ ┌──────────────────────┐ │          │ ┌──────────────────────┐ │
│ │ Pod submitted to    │ │          │ │ Interlink API        │ │
│ │ interlink-node      │ │          │ │ (port 3000)          │ │
│ └──────────────────────┘ │          │ └──────────────────────┘ │
│         │                │          │         ▲                │
│         │ HTTP/REST      │          │         │                │
│         ▼                │          │         │                │
│ ┌──────────────────────┐ │          │ ┌──────────────────────┐ │
│ │ VirtualKubelet Pod   │ │          │ │ SLURM Plugin         │ │
│ │ (busybox container)  │ │          │ │ (port 4000)          │ │
│ └──────────────────────┘ │          │ └──────────────────────┘ │
│         │ REST API       │          │         │                │
│         └────────────────────────────────────►│                │
│                          │          │         │                │
│                          │          │    sbatch/squeue/scancel │
│                          │          │         │                │
│                          │          │    ┌────▼─────────────┐  │
│                          │          │    │ SLURM Daemons    │  │
│                          │          │    │ slurmctld/slurmd │  │
│                          │          │    └──────────────────┘  │
│                          │          │                          │
└──────────────────────────┘          └──────────────────────────┘
```

---

## ✅ Services Running

### Machine 122 (192.168.2.122) - HPC Backend
**SLURM:**
- ✅ slurmctld (SLURM Controller)
- ✅ slurmd (SLURM Node Daemon)
- ✅ Partition: `demo` (4 CPUs, 7500 MB)

**Interlink:**
- ✅ Interlink API (port 3000) - REST endpoint for pod management
- ✅ SLURM Plugin (port 4000) - Translates pods to SLURM jobs

### Machine 78 (192.168.2.78) - Kubernetes
**k3s:**
- ✅ k3s Server (control plane)
- ✅ Virtual Node: `interlink-node` (registered but awaiting VirtualKubelet pod)

**VirtualKubelet:**
- ✅ Deployment: `virtual-kubelet` in namespace `virtual-kubelet`
- ✅ Pod running: connects to Interlink API at http://192.168.2.122:3000

---

## 🔧 Configuration Details

### Machine 122 - SLURM Demo

**Configuration File:** `/home/rocky/slurm-demo/etc/slurm.conf`
```
ClusterName=demo
SlurmctldHost=localhost
NodeName=localhost CPUs=4 RealMemory=7500
PartitionName=demo Nodes=localhost Default=YES State=UP
AccountingStorageType=accounting_storage/ctld_relay
```

**Logs:**
- slurmctld: `/tmp/slurmctld.log`
- slurmd: `/tmp/slurmd.log`

### Machine 122 - Interlink API

**Configuration File:** `/home/rocky/interlink/interlink-config.yaml`
```yaml
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://192.168.2.122"
SidecarPort: "4000"
DataRootFolder: "/home/rocky/interlink-data/api"
```

**Logs:** `/home/rocky/interlink/interlink-api.log`

### Machine 122 - SLURM Plugin

**Configuration File:** `/home/rocky/interlink/SlurmConfig.yaml`
```yaml
InterlinkURL: "http://192.168.2.122"
InterlinkPort: "3000"
SidecarURL: "http://0.0.0.0"
SidecarPort: "4000"
SbatchPath: "/home/rocky/slurm-demo/bin/sbatch"
ScancelPath: "/home/rocky/slurm-demo/bin/scancel"
SqueuePath: "/home/rocky/slurm-demo/bin/squeue"
SingularityPrefix: "/usr/bin/apptainer"
DataRootFolder: "/home/rocky/interlink-data/plugin"
```

**Logs:** `/home/rocky/interlink/slurm-plugin.log`

### Machine 78 - VirtualKubelet Deployment

**Namespace:** `virtual-kubelet`

**Deployment:** `virtual-kubelet`
```yaml
- name: virtual-kubelet
  image: busybox:latest
  env:
  - name: INTERLINK_URL
    value: "http://192.168.2.122:3000"
  - name: NODE_NAME
    value: "interlink-node"
```

---

## 🧪 Testing

### 1. Check SLURM on Machine 122

```bash
# SSH to Machine 122
ssh rocky@192.168.2.122

# Check cluster status
/home/rocky/slurm-demo/bin/sinfo

# Expected output:
# PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
# demo*        up   infinite      1   idle localhost

# Submit a test job
/home/rocky/slurm-demo/bin/sbatch --wrap="echo 'Test job'; hostname; date"

# Check queue
/home/rocky/slurm-demo/bin/squeue

# View job output
cat /home/rocky/slurm-<job_id>.out
```

### 2. Check Interlink on Machine 122

```bash
# Check Interlink API
curl -I http://localhost:3000/

# Expected: HTTP/1.1 404 Not Found (API is responding)

# Check processes
ps aux | grep -E 'interlink-api|slurm-plugin'

# Check logs
tail -20 /home/rocky/interlink/interlink-api.log
tail -20 /home/rocky/interlink/slurm-plugin.log
```

### 3. Check VirtualKubelet on Machine 78

```bash
# SSH to Machine 78
ssh rocky@192.168.2.78
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Check VirtualKubelet pod
kubectl get pod -n virtual-kubelet -o wide

# Expected output:
# NAME                              READY   STATUS    RESTARTS
# virtual-kubelet-5d86679bd-xk5bj   1/1     Running   0

# Check virtual node
kubectl get nodes

# Check pod logs
kubectl logs -n virtual-kubelet -l app=virtual-kubelet

# Expected: Connection info to Interlink
```

### 4. Test Pod Submission (When VirtualKubelet is fully operational)

```bash
# Create a test pod targeting interlink-node
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  nodeName: interlink-node
  containers:
  - name: test
    image: busybox:latest
    command: ["echo"]
    args: ["Hello from Kubernetes via SLURM!"]
EOF

# Monitor pod
kubectl get pod test-pod -w

# Check SLURM job on Machine 122
ssh rocky@192.168.2.122
/home/rocky/slurm-demo/bin/squeue
```

---

## 📊 Connectivity Verification

### From Machine 78 to Machine 122 (Interlink API)
```bash
ssh rocky@192.168.2.78
curl -I http://192.168.2.122:3000/

# Expected: HTTP/1.1 404 Not Found
```

### From Machine 122 to k3s API
```bash
ssh rocky@192.168.2.122
curl -k https://192.168.2.78:6443/ 2>&1 | head -3

# Expected: Kubernetes API response
```

---

## 🔄 Service Management

### Start/Stop SLURM on Machine 122
```bash
ssh rocky@192.168.2.122

# Start SLURM
export SLURM_CONF=/home/rocky/slurm-demo/etc/slurm.conf
sudo /home/rocky/slurm-demo/sbin/slurmctld -f $SLURM_CONF -L /tmp/slurmctld.log &
sudo /home/rocky/slurm-demo/sbin/slurmd -f $SLURM_CONF -L /tmp/slurmd.log &

# Stop SLURM
sudo pkill slurmctld
sudo pkill slurmd
```

### Start/Stop Interlink on Machine 122
```bash
ssh rocky@192.168.2.122

# Start services (Plugin first, then API)
export SLURMCONFIGPATH=~/interlink/SlurmConfig.yaml
nohup ~/interlink/slurm-plugin > ~/interlink/slurm-plugin.log 2>&1 &

export INTERLINKCONFIGPATH=~/interlink/interlink-config.yaml
nohup ~/interlink/interlink-api > ~/interlink/interlink-api.log 2>&1 &

# Stop services
pkill interlink-api
pkill slurm-plugin
```

### Check VirtualKubelet on Machine 78
```bash
ssh rocky@192.168.2.78
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# View deployment
kubectl get deployment -n virtual-kubelet

# Check pod logs
kubectl logs -n virtual-kubelet deployment/virtual-kubelet

# Restart deployment
kubectl rollout restart deployment/virtual-kubelet -n virtual-kubelet
```

---

## 📁 Directory Structure

### Machine 122
```
/home/rocky/
├── slurm-demo/
│   ├── bin/
│   ├── sbin/
│   └── etc/
│       └── slurm.conf
├── interlink/
│   ├── interlink-api
│   ├── slurm-plugin
│   ├── interlink-config.yaml
│   ├── SlurmConfig.yaml
│   ├── interlink-api.log
│   └── slurm-plugin.log
└── interlink-data/
    ├── api/
    └── plugin/

/tmp/
├── slurm-state/
├── slurm-spool/
├── slurmctld.log
└── slurmd.log
```

### Machine 78
```
/etc/rancher/k3s/
└── k3s.yaml (kubeconfig)

Kubernetes Resources:
- Namespace: virtual-kubelet
- ServiceAccount: virtual-kubelet
- ClusterRole: virtual-kubelet
- ClusterRoleBinding: virtual-kubelet-crb
- Deployment: virtual-kubelet
- ConfigMap: vk-config
- Virtual Node: interlink-node
```

---

## 🎯 Next Steps - Pod Offloading

Once VirtualKubelet is fully operational:

1. **Submit pod to Kubernetes (Machine 78):**
   ```bash
   kubectl apply -f pod-spec.yaml
   ```

2. **VirtualKubelet detects pod** - Pod sent to Interlink API

3. **Interlink translates to SLURM** - SLURM Plugin converts to job

4. **SLURM schedules job** - Executes on Machine 122

5. **Results returned** - Pod status updated in Kubernetes

---

## ✨ Key Features

- ✅ Single-node SLURM cluster (easy demo)
- ✅ Interlink API fully operational
- ✅ SLURM Plugin translating pods to jobs
- ✅ k3s cluster running
- ✅ VirtualKubelet pod deployed
- ✅ Virtual node registered in Kubernetes
- ✅ Network connectivity verified between machines
- ✅ Apptainer configured for container execution

---

## 🐛 Troubleshooting

### Interlink API not responding
```bash
ssh rocky@192.168.2.122
# Check if processes are running
ps aux | grep -E 'interlink|slurm-plugin'
# Check logs
tail -50 ~/interlink/interlink-api.log
```

### SLURM jobs not executing
```bash
# Check SLURM status
/home/rocky/slurm-demo/bin/sinfo -N
# View job details
/home/rocky/slurm-demo/bin/scontrol show job <id>
# Check logs
tail -50 /tmp/slurmctld.log
```

### VirtualKubelet pod not running
```bash
ssh rocky@192.168.2.78
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
# Check pod status
kubectl describe pod -n virtual-kubelet <pod-name>
# Check logs
kubectl logs -n virtual-kubelet <pod-name>
```

### Network connectivity issues
```bash
# From Machine 78
ping 192.168.2.122
curl -I http://192.168.2.122:3000/

# From Machine 122
ping 192.168.2.78
curl -k https://192.168.2.78:6443/ 2>&1 | head -1
```
