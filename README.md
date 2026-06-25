# Interlink HPC Course: SLURM ↔ Kubernetes Bridge

**Real working setup** - Built from Interlink's actual e2e workflow

Two machines, one SLURM cluster, one k3s Kubernetes, bridged with Interlink VirtualKubelet.

## Setup

| Machine | IP | Role | OS |
|---------|-----|------|-----|
| Machine 1 | 192.168.2.170 | SLURM HPC | Rocky Linux 9 |
| Machine 2 | 192.168.2.84 | k3s Kubernetes | Rocky Linux 9 |

## Architecture

```
Machine 2 (k3s)                          Machine 1 (SLURM)
┌─────────────────────┐                  ┌──────────────┐
│ Kubernetes Pods     │                  │ SLURM Jobs   │
│ (scheduled to VK)   │                  │              │
└──────────┬──────────┘                  └──────┬───────┘
           │                                     ▲
           │ kubectl apply                       │
           ▼                                     │
    ┌─────────────────┐                  ┌──────┴───────┐
    │ Virtual-Kubelet │◄────────────────►│ Interlink    │
    │ (node)          │  gRPC port 3000  │ API          │
    └─────────────────┘                  └──────────────┘
    (real kubelet impl)                  (pod→job translator)
```

## Follow the Guide

1. **[Phase 1: SLURM Setup](phase1-slurm-setup.md)** - Install and test SLURM on Machine 1
2. **[Phase 2: k3s Setup](phase2-k3s-setup.md)** - Install and test k3s on Machine 2  
3. **[Phase 3: Interlink Setup](phase3-interlink-setup.md)** - Deploy VirtualKubelet and Interlink API
4. **[Phase 4: Test Pod Offload](phase4-test-offload.md)** - Submit pods that offload to SLURM

## What Actually Works

This course shows:
- ✅ Building and deploying **actual VirtualKubelet binary** from source
- ✅ Running **real Interlink API** and SLURM plugin in containers  
- ✅ **Pod scheduling to virtual-kubelet node** that works
- ✅ **Pod-to-SLURM job translation** via Interlink gRPC API
- ✅ **End-to-end pod offload** - Kubernetes pod → SLURM job

Based on the **official Interlink e2e test workflow** from github.com/interlink-hq/interlink
