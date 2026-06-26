# Deployment Methods Explained

## What This Document Covers

This course repository demonstrates the Interlink bridge with:
- **Machine 1**: Binary deployment for Interlink API and SLURM Plugin
- **Machine 2**: **Helm deployment for VirtualKubelet** (required standard approach)

## Components and How They're Deployed

### Machine 1: SLURM + Interlink Bridge

#### 1. Interlink API
- **Deployment**: Standalone binary
- **Command**: `./interlink-api`
- **Port**: 3000
- **Config file**: `interlink-config.yaml`
- **What it does**: 
  - Listens for pod specifications from VirtualKubelet
  - Converts Kubernetes pods to SLURM job concepts
  - Forwards requests to SLURM plugin
  - Returns pod status updates

#### 2. SLURM Plugin (Sidecar)
- **Deployment**: Standalone binary
- **Command**: `./slurm-plugin`
- **Port**: 4000
- **Config file**: `SlurmConfig.yaml`
- **What it does**:
  - Receives job requests from Interlink API
  - Generates sbatch job scripts
  - Submits jobs to SLURM via sbatch
  - Monitors job status via squeue
  - Returns status to Interlink API

**Why standalone binaries for Interlink?**
- Simple: No Docker, no container orchestration needed
- Direct: Direct file system and SLURM access
- Transparent: Easy to debug and monitor
- Lightweight: Minimal resource overhead

### Machine 2: k3s + VirtualKubelet

#### VirtualKubelet (Helm Deployment - REQUIRED)
- **Deployment**: Official Helm chart from virtual-kubelet.github.io
- **Namespace**: `virtual-kubelet`
- **Helm command**: `helm install vk virtual-kubelet/virtual-kubelet --namespace virtual-kubelet`
- **Type**: Kubernetes Deployment → Pod
- **RBAC**: ServiceAccount with ClusterRole for pod management
- **What it does**:
  - Watches Kubernetes API for pods scheduled to "interlink-node"
  - Sends pod specifications to Interlink API (REST/HTTP)
  - Receives pod status updates from Interlink API
  - Updates pod status in Kubernetes

**Why Helm for VirtualKubelet?**
- **Standard approach**: Recommended by VirtualKubelet community
- **Kubernetes-native**: Should run as a Pod within Kubernetes
- **Lifecycle management**: Helm handles pod creation, updates, and scaling
- **RBAC integration**: Properly configured ServiceAccounts and permissions
- **Production-ready**: Tested and supported deployment method
- **Best practices**: Follows Kubernetes community standards

## Earlier Exploration: Binary Approach

### Why Binary Was Initially Attempted

Earlier versions of this course attempted to run VirtualKubelet as a standalone binary process (see git history commits). This approach seemed attractive because:
- Avoided Kubernetes complexity
- Reduced "layers" of abstraction
- Appeared simpler for training

### Why Binary Approach Was Changed to Helm

After careful consideration, the course was updated to use the **required Helm deployment** because:

1. **Production Standard**: VirtualKubelet **must** run as a Kubernetes Pod via Helm, not as external process
2. **Kubernetes Integration**: Helm-deployed VirtualKubelet properly integrates with k3s cluster
3. **RBAC Security**: Helm chart handles proper RBAC configuration with least privilege
4. **Community Best Practice**: VirtualKubelet project officially recommends Helm deployment
5. **Feature Support**: Helm deployment supports all VirtualKubelet features including:
   - Pod lifecycle management
   - Status synchronization
   - TLS certificate generation
   - Proper service account handling

## Current Implementation (Required)

```
Machine 2 (k3s)              Machine 1 (SLURM)
─────────────────            ────────────────
VirtualKubelet Pod           Interlink API
  (Helm deployed)              (binary)
    (in k3s)                   
    │                            │
    ├─ REST/HTTP ───────────────┤
    │                            │
    │                        SLURM Plugin
    │                          (binary)
    │                            │
    │                    ┌───────┴────────┐
    │                    │                │
    │              SLURM Commands    Job Execution
    │                 sbatch              Apptainer
    │               squeue              (container)
    │               scancel
    │
    └── updates pod status
```

## Deployment Checklist

For this training course (Helm-based):

- [ ] Helm installed on Machine 2
- [ ] Virtual Kubelet Helm repository added
- [ ] Helm chart deployed to virtual-kubelet namespace
- [ ] RBAC configured for VirtualKubelet service account
- [ ] Binary Interlink API on Machine 1
- [ ] Binary SLURM Plugin on Machine 1
- [ ] Network connectivity between machines
- [ ] Apptainer installed on Machine 1

## Summary

This course uses:

✅ **Helm deployment for VirtualKubelet** (standard, required, production-ready)  
✅ **Binary deployment for Interlink components** (simpler for cross-machine communication)  
✅ **Kubernetes-native approach** (follows best practices and community standards)  

For more details on the actual deployment steps, see [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md).

---

**Next**: Start with [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for step-by-step Helm deployment.
