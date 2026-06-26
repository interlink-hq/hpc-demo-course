# Deployment Methods Explained

## What This Document Covers

This course repository demonstrates the Interlink bridge with binary deployment for all components. You may see references to earlier exploration with Helm - this document clarifies why binary deployment is the chosen approach.

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

**Why standalone binaries?**
- Simple: No Docker, no container orchestration needed
- Direct: Direct file system and SLURM access
- Transparent: Easy to debug and monitor
- Lightweight: Minimal resource overhead

### Machine 2: k3s + VirtualKubelet

#### VirtualKubelet
- **Deployment**: Standalone binary process
- **Command**: `./vk -nodename=interlink-node -configpath=vk-config.yaml`
- **Config file**: `vk-config.yaml`
- **RBAC**: ServiceAccount `virtual-kubelet` with necessary ClusterRole bindings
- **What it does**:
  - Watches Kubernetes API for pods scheduled to "interlink-node"
  - Sends pod specifications to Interlink API (REST/HTTP)
  - Receives pod status updates from Interlink API
  - Updates pod status in Kubernetes

**Why NOT Kubernetes Deployment?**
- VirtualKubelet needs direct kubeconfig access
- Running as Kubernetes Pod creates circular dependency
- Binary process is simpler and more transparent

## Earlier Exploration: Helm Deployment

### Why Helm Was Attempted

Helm provides:
- Templated Kubernetes manifests
- Easy installation/uninstallation
- Standard packaging for Kubernetes applications
- Potential multi-cluster deployment

### Why Helm Was Not Used

For VirtualKubelet specifically:

1. **Circular Dependency**: VirtualKubelet must communicate with Kubernetes to manage pods. Running it as a Kubernetes Pod creates complexity.

2. **TLS Certificate Issues**: VirtualKubelet's pod log retrieval requires HTTPS with proper certificates. Helm deployment requires:
   - Certificate generation (CSR - CertificateSigningRequest)
   - RBAC permissions for certificate signing
   - Complex certificate mounting into Pod
   - Persistent certificate storage

3. **Same Functionality**: Both Helm and binary deployments use the same underlying VirtualKubelet binary. Helm adds packaging complexity without functional improvement.

4. **Training Focus**: This course teaches the fundamentals of pod offloading, not Kubernetes package management. Binary deployment is simpler and more transparent for learning.

**Commits related to Helm exploration:**
- `fad4557`: Deploy VirtualKubelet via official Helm chart (explored)
- `0f8f8d3`: Remove Helm deployment (incomplete - log retrieval TLS issue)

### If You Want to Use Helm

If you prefer Helm deployment:
1. Use the official VirtualKubelet Helm chart from https://github.com/virtual-kubelet/virtual-kubelet
2. Configure RBAC and service account properly
3. Generate TLS certificates for pod log retrieval
4. Mount certificates into the Pod
5. Ensure pod can access kubeconfig

The core Interlink pipeline (pod → API → plugin → SLURM) works identically whether VirtualKubelet runs as binary or Helm-deployed Pod.

## Current Implementation (Recommended)

```
Machine 2 (k3s)              Machine 1 (SLURM)
─────────────────            ────────────────
VirtualKubelet               Interlink API
  (binary)                     (binary)
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

For this training course:

- [ ] Binary VirtualKubelet on Machine 2
- [ ] Binary Interlink API on Machine 1
- [ ] Binary SLURM Plugin on Machine 1
- [ ] Proper RBAC for VirtualKubelet service account
- [ ] Configuration files (YAML) for all three components
- [ ] Network connectivity between machines
- [ ] Apptainer installed on Machine 1

## Summary

This course uses **binary deployment for all components** because:

✅ Simpler architecture (fewer moving parts)  
✅ More transparent (easier to debug)  
✅ Fully functional (identical to complex deployments)  
✅ Better for learning (focus on Interlink concepts, not Kubernetes packaging)  
✅ Production-ready (proven and tested on real hardware)  

For production deployments with multiple instances, you could explore:
- Helm for packaging
- Docker/Podman for container isolation  
- Systemd/supervisord for process management
- Kubernetes Operators for lifecycle management

But for this training course and proof-of-concept work, binary deployment is **recommended and sufficient**.

---

**Next**: Start with [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for step-by-step deployment.
