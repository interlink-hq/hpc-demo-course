# HPC + Kubernetes Course: SLURM ↔ k3s Interlink Bridge

**Objective:** Learn how to bridge HPC (SLURM) and Kubernetes (k3s) using Interlink.

This repository contains step-by-step instructions to deploy a complete Interlink setup bridging two systems:

1. **Machine 1 (SLURM):** 192.168.2.170 - HPC job scheduler
2. **Machine 2 (k3s):** 192.168.2.84 - Kubernetes cluster

Kubernetes pods scheduled to the virtual node will be automatically offloaded to SLURM jobs.

## Quick Start

**Start here:** Read **[COMPLETE_GUIDE.md](COMPLETE_GUIDE.md)** for the tested, end-to-end deployment procedure.

This is the definitive reference that has been validated on real hardware.

### Documentation Structure

**Primary Resources:**
1. **[COMPLETE_GUIDE.md](COMPLETE_GUIDE.md)** - Start here, end-to-end tested deployment (uses Helm for VirtualKubelet)
2. **[VOLUME_MOUNT_LIMITATION.md](VOLUME_MOUNT_LIMITATION.md)** - Known limitation with ServiceAccount tokens and workarounds ⚠️
3. **[DEPLOYMENT_METHODS.md](DEPLOYMENT_METHODS.md)** - Explains why Helm is required for VirtualKubelet and deployment architecture

**Understanding the Architecture:**
1. **[FINAL_SUMMARY.md](FINAL_SUMMARY.md)** - Complete project overview with verification evidence
2. **[CRITICAL_FINDINGS.md](CRITICAL_FINDINGS.md)** - Technical deep-dive on all issues resolved

**Legacy Documentation (background information):**
1. **[Phase 1: SLURM Setup](phase1-slurm-setup.md)** - Initial SLURM deployment
2. **[Phase 2: k3s Setup](phase2-k3s-setup.md)** - Initial k3s deployment  
3. **[Phase 3: Interlink Setup](phase3-interlink-setup.md)** - Detailed Interlink binary configuration
4. **[Phase 4: Test Pod Offload](phase4-test-offload.md)** - Testing procedures

**Troubleshooting & Reference:**
- **[CRITICAL_FINDINGS.md](CRITICAL_FINDINGS.md)** - Technical deep-dive on issues and solutions
- **[APPTAINER_FIX.md](APPTAINER_FIX.md)** - Apptainer installation and integration

**Recommended:** Follow COMPLETE_GUIDE.md for your first deployment.

## Architecture Overview

```
k3s (Machine 2)                          Interlink Bridge                 SLURM (Machine 1)
───────────────────                      ────────────────                 ──────────────────
Pod submitted                                                              
   │                                                                       
   ▼                                                                       
Virtual Node "interlink-node"                                             
   │ (watches for pods)                                                   
   │                                                                       
   ├─► VirtualKubelet Binary (192.168.2.84)                              
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
   │                                              │ sbatch/squeue/scancel
   │                                              │                       
   │                                              ▼                       
   │                                        SLURM Daemon                  
   │                                              │                       
   │ ◄──────────────────────────────────────────┘ (status updates)      
   │                                                                       
Pod status updated (Running/Completed)                                    
```

## What Gets Deployed

| Component | Machine | Type | Port | Role |
|-----------|---------|------|------|------|
| VirtualKubelet | 2 | Helm deployment (Kubernetes Pod) | - | Watches k8s pods, submits to Interlink |
| Interlink API | 1 | Binary (standalone process) | 3000 | Translates pods to SLURM jobs |
| SLURM Plugin | 1 | Binary (standalone process) | 4000 | Submits jobs to SLURM via sbatch |
| SLURM | 1 | Service/Daemon | - | Schedules and executes jobs |
| k3s | 2 | Service/Daemon | 6443 | Kubernetes control plane |

**Note on VirtualKubelet:** Deployed via the official Helm chart from virtual-kubelet.github.io. This is the standard deployment method for VirtualKubelet in Kubernetes environments.

## Network Requirements

- **Connectivity:** Machine 2 must reach Machine 1 on port 3000
- **SSH Keys:** Key-based SSH between machines (for remote commands)
- **Subnet:** 192.168.2.0/24 (adjust if different)

Test connectivity before starting:
```bash
ping 192.168.2.170          # From Machine 2
ping 192.168.2.84           # From Machine 1
curl http://192.168.2.170:3000/  # From Machine 2 (after Phase 3)
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

After deploying VirtualKubelet via Helm, test with:

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
Pod shows as Running on interlink-node virtual node
Output: "Hello from SLURM!" followed by sleep
SLURM job visible on Machine 1
```

See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for detailed step-by-step testing procedures and [Phase 4](phase4-test-offload.md) for additional testing approaches.

## Troubleshooting Quick Reference

### Pod stuck in Pending
1. Verify `interlink-node` exists: `kubectl get nodes`
2. Check VirtualKubelet running: `ssh rocky@192.168.2.84 'ps aux | grep virtual-kubelet'`
3. Check logs: `ssh rocky@192.168.2.84 'tail -50 ~/interlink/vk.log'`

### Interlink API not responding
1. Check if running: `ssh rocky@192.168.2.170 'ps aux | grep interlink-api'`
2. Check port: `ssh rocky@192.168.2.170 'netstat -tlnp | grep 3000'`
3. Check logs: `ssh rocky@192.168.2.170 'tail -50 ~/interlink/interlink-api.log'`

### Network issues between machines
```bash
ssh rocky@192.168.2.170 'ping 192.168.2.84'
ssh rocky@192.168.2.84 'curl -v http://192.168.2.170:3000/' 2>&1 | head -20
```

## Learning Objectives

By completing this course, you'll understand:

✓ How HPC systems (SLURM) differ from container orchestration (Kubernetes)  
✓ How to implement a translation layer (Interlink) between systems  
✓ How pod abstractions map to job abstractions  
✓ How to debug cross-system workflows  
✓ How to monitor and verify Kubernetes workloads on HPC infrastructure  
✓ Real-world patterns for hybrid HPC+cloud deployments  

## File Structure

```
hpc-course/
├── README.md                        # This file
├── phase1-slurm-setup.md           # SLURM cluster deployment
├── phase2-k3s-setup.md             # k3s deployment
├── phase3-interlink-setup.md       # Interlink bridge (binary-based)
├── phase4-test-offload.md          # Testing and validation
└── configs/                        # Configuration examples
```

## References

- **Interlink:** https://github.com/interlink-hq/interlink
- **SLURM:** https://slurm.schedmd.com/
- **k3s:** https://docs.k3s.io/
- **Kubernetes:** https://kubernetes.io/docs/

---

**Ready to start?** Begin with [Phase 1: SLURM Setup](phase1-slurm-setup.md)
