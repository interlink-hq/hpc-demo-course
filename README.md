# HPC + Kubernetes Course: SLURM ↔ k3s Interlink Bridge

**Objective:** Learn how to bridge HPC (SLURM) and Kubernetes (k3s) using Interlink.

This repository contains step-by-step instructions to deploy a complete Interlink setup bridging two systems:

1. **Machine 1 (SLURM):** $M1_IP - HPC job scheduler
2. **Machine 2 (k3s):** $M2_IP - Kubernetes cluster

Kubernetes pods scheduled to the virtual node will be automatically offloaded to SLURM jobs.

## Getting Started (5 minutes)

### 1. **Prerequisites**
Read [00-CONFIGURATION.md](00-CONFIGURATION.md) - check your machine specs and network setup

### 2. **Deployment**
Follow [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) step-by-step - this is the complete, tested deployment procedure

### 3. **Cleanup**
See [CLEANUP.md](CLEANUP.md) for reset and troubleshooting procedures

## Documentation Structure

```
hpc-course/
├── README.md                              # This file (start here)
├── INSTALLATION_GUIDE.md                  # ⭐ Primary deployment guide (follow this!)
├── 00-CONFIGURATION.md                    # Prerequisites and setup checklist
├── CLEANUP.md                             # Reset and troubleshooting
│
├── docs/PHASES/                           # Phase-by-phase learning path
│   ├── phase1-slurm-setup.md             # Detailed SLURM installation
│   ├── phase2-k3s-setup.md               # Detailed k3s installation
│   ├── phase3-interlink-setup.md         # Detailed Interlink setup
│   ├── phase4-test-offload.md            # Detailed testing procedures
│   └── COMPLETE_GUIDE.md                  # High-level system overview
│
└── docs/REFERENCES/                       # Advanced reference materials
    ├── VOLUME_MOUNT_LIMITATION.md         # ServiceAccount token configuration
    ├── CRITICAL_FINDINGS.md               # All issues resolved
    ├── DEPLOYMENT_METHODS.md              # Why Helm is required
    ├── DEPLOYMENT_STATUS.md               # System validation results
    ├── FINAL_SUMMARY.md                   # Complete system overview
    ├── APPTAINER_FIX.md                   # Apptainer integration history
    └── README.md                          # Navigation guide for references
```

## Quick Navigation

**I'm ready to deploy:** Start with [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)

**I want to understand the architecture first:** Read [docs/PHASES/COMPLETE_GUIDE.md](docs/PHASES/COMPLETE_GUIDE.md)

**I want detailed phase-by-phase instructions:** See [docs/PHASES/](docs/PHASES/) directory

**I'm troubleshooting an issue:** Check [CLEANUP.md](CLEANUP.md) and [docs/REFERENCES/](docs/REFERENCES/)

## Architecture Overview

```
k3s (Machine 2)                 Interlink Bridge              SLURM (Machine 1)
───────────────────             ────────────────              ──────────────────
Pod submitted                                                
   │                                                          
   ▼                                                          
Virtual Node "interlink-node"                                
   │ (watches for pods)                                      
   │                                                          
   ├─► VirtualKubelet Pod (Helm)                            
   │       │                                                 
   │       │ REST/HTTP                                     
   │       │                                                 
   │       └──────────────────────────────► Interlink API (port 3000)
   │                                              │           
   │                                              │ REST/HTTP 
   │                                              │           
   │                                              ▼           
   │                                        SLURM Plugin      
   │                                              │           
   │                                              │ sbatch/squeue
   │                                              │           
   │                                              ▼           
   │                                        SLURM Daemon      
   │                                              │           
   │ ◄──────────────────────────────────────────┘ (status)  
   │                                                          
Pod completes on SLURM backend                               
```

## What Gets Deployed

| Component | Machine | Type | Port | Role |
|-----------|---------|------|------|------|
| VirtualKubelet | 2 | Helm Pod | - | Watches k8s pods, translates to Interlink |
| Interlink API | 1 | Binary | 3000 | Translates pods to SLURM jobs |
| SLURM Plugin | 1 | Binary | 4000 | Submits jobs to SLURM |
| SLURM | 1 | Service | - | Schedules and executes jobs |
| k3s | 2 | Service | 6443 | Kubernetes control plane |

## Network Requirements

- **Connectivity:** Machine 2 must reach Machine 1 on port 3000
- **SSH Keys:** Key-based SSH between machines (for remote commands)
- **Subnet:** 192.168.2.0/24 (adjust if different)

Test connectivity before starting:
```bash
ping $M1_IP          # From Machine 2
ping $M2_IP           # From Machine 1
curl http://$M1_IP:3000/  # From Machine 2 (after Phase 3)
```

## Expected Workflow

1. Submit pod to k3s pointing to `interlink-node`
2. Pod status changes to Running
3. VirtualKubelet detects pod, sends spec to Interlink API
4. Interlink translates to SLURM job and submits via sbatch
5. Job appears in SLURM queue (`squeue`)
6. Pod status reflects job execution
7. Job completes, pod marked as Completed
8. Logs available via `kubectl logs`

## Key Concepts

### VirtualKubelet
- Kubernetes node implementation that schedules pods to external systems
- Watches k3s API for pods on "interlink-node"
- Translates pod specs and submits to Interlink

### Interlink API  
- Bridge service translating Kubernetes concepts to HPC concepts
- Pod spec → SLURM job script
- Pod status → SLURM job status
- Uses REST/HTTP for communication between components

### SLURM Plugin
- Submits jobs to SLURM via sbatch
- Monitors job status via squeue
- Reports back to Interlink API

## Testing Your Setup

After completing deployment (Phase 5 in INSTALLATION_GUIDE.md), test with:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Submit test pod with proper constraints
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: hello-slurm
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
  - name: app
    image: busybox:latest
    command: ["/bin/sh", "-c"]
    args: ["echo 'Hello from SLURM!'; sleep 5"]
  restartPolicy: Never
EOF

# Watch pod status
kubectl get pod hello-slurm -w

# Check logs
kubectl logs hello-slurm
```

Expected output:
```
Pod shows as Running on interlink-node
Output: "Hello from SLURM!" followed by sleep
SLURM job visible on Machine 1
```

## Troubleshooting Quick Reference

### Pod stuck in Pending
1. Verify `interlink-node` exists: `kubectl get nodes`
2. Check VirtualKubelet running: `ssh rocky@$M2_IP 'kubectl get pods -n virtual-kubelet'`
3. Check logs: `ssh rocky@$M2_IP 'kubectl logs -n virtual-kubelet -l app=virtual-kubelet'`

### Interlink API not responding
1. Check if running: `ssh rocky@$M1_IP 'ps aux | grep interlink-api'`
2. Check port: `ssh rocky@$M1_IP 'netstat -tlnp | grep 3000'`
3. Check logs: `ssh rocky@$M1_IP 'tail -50 ~/interlink/interlink-api.log'`

### Network issues between machines
```bash
ssh rocky@$M1_IP 'ping $M2_IP'
ssh rocky@$M2_IP 'curl -v http://$M1_IP:3000/' 2>&1 | head -20
```

See [CLEANUP.md](CLEANUP.md) for more troubleshooting options.

## Learning Objectives

By completing this course, you'll understand:

✓ How HPC systems (SLURM) differ from container orchestration (Kubernetes)  
✓ How to implement a translation layer (Interlink) between systems  
✓ How pod abstractions map to job abstractions  
✓ How to debug cross-system workflows  
✓ How to monitor and verify Kubernetes workloads on HPC infrastructure  
✓ Real-world patterns for hybrid HPC+cloud deployments  

## References

- **Interlink:** https://github.com/interlink-hq/interlink
- **SLURM:** https://slurm.schedmd.com/
- **k3s:** https://docs.k3s.io/
- **Kubernetes:** https://kubernetes.io/docs/
- **Virtual Kubelet:** https://github.com/virtual-kubelet/virtual-kubelet

---

**Ready to start?** Begin with [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
