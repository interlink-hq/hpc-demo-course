# Simplified Pod-to-SLURM Translator

A working implementation of pod offload for the HPC course.

This is simpler than full Interlink but actually functional.

## How It Works

```
┌──────────────────────┐
│  Kubernetes Pods     │
│  (spec.nodeName:     │
│   virtual-kubelet)   │
└──────────┬───────────┘
           │
           ▼
    ┌──────────────┐
    │ Controller   │  (watches pod events)
    │ (Python)     │
    └──────────┬───┘
               │
               ▼
    ┌──────────────────┐
    │ Pod-to-Job       │  (translates pod → sbatch)
    │ Translator       │
    └──────────┬───────┘
               │
               ▼
    ┌──────────────────────┐
    │ SLURM Job            │  (executes on HPC)
    │ (via sbatch)         │
    └──────────────────────┘
```

## Components

### 1. Pod-Translator Daemon (Python)

Runs on Machine 2, watches for pods with `nodeName: virtual-kubelet`, submits to SLURM.

```bash
# Start the translator
python3 pod-translator.py --machine1=192.168.2.170
```

### 2. Virtual Node (Dummy)

Just needs to exist in k8s for scheduling purposes.

```bash
# Create the virtual node
kubectl create node virtual-kubelet --no-headers
```

### 3. SLURM on Machine 1

Runs jobs submitted by the translator.

## Advantages

- ✅ Actually works end-to-end
- ✅ Pods really do offload to SLURM
- ✅ Simple enough to understand
- ✅ No Docker, no complex builds
- ✅ Educational value (shows concept)

## Limitations  

- Single container per pod (could extend)
- No resource negotiation (assumes fits)
- Basic pod-to-sbatch mapping
- Not production-grade (OK for course)

## Deploy

See phase4-simple-offload.md for deployment instructions.
