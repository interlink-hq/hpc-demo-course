# HPC Course: Interlink Setup Between SLURM and Kubernetes

This repository contains comprehensive step-by-step instructions for setting up **Interlink** across two physical machines: one running a SLURM HPC cluster and another running a single-node Kubernetes (k3s) server.

## Quick Reference

| Component | Machine | IP Address | OS |
|-----------|---------|------------|-----|
| **SLURM HPC** | Machine 1 | 192.168.2.170 | Rocky Linux |
| **k3s Kubernetes** | Machine 2 | 192.168.2.84 | Rocky Linux |
| **User Credentials** | Both | N/A | Username: `rocky` |

## What is Interlink?

Interlink is a cloud-native HPC project that acts as a bridge between:
- **VirtualKubelet** running on Kubernetes (k3s) 
- **Traditional HPC workload managers** like SLURM

This allows Kubernetes pods to be transparently scheduled on HPC resources, combining containerization with HPC capabilities.

## Course Structure

This repository is organized as follows:

```
├── README.md (you are here)
├── docs/
│   ├── prerequisites.md          # System requirements and network setup
│   ├── machine1-slurm.md         # SLURM installation and configuration
│   ├── machine2-k3s.md           # k3s installation and configuration  
│   ├── interlink-setup.md        # Interlink installation and configuration
│   ├── testing-procedures.md     # End-to-end testing guide
│   ├── troubleshooting.md        # Common issues and solutions
│   └── common-tasks.md           # General Linux tasks (SSH, firewall, etc.)
└── configs/
    ├── slurm-examples/           # Example SLURM configurations
    ├── k3s-examples/             # Example k3s configurations
    └── interlink-examples/       # Example Interlink configurations
```

## Learning Objectives

By completing this course, you will:

1. **Understand HPC concepts** - Learn how SLURM manages compute resources
2. **Master Kubernetes basics** - Deploy and manage k3s on a single machine
3. **Bridge HPC and containers** - Set up Interlink to unify both environments
4. **Troubleshoot distributed systems** - Debug networking and service issues across machines
5. **Write production documentation** - Document infrastructure setup procedures

## Getting Started

### Prerequisites
- Two Rocky Linux 9 VMs with:
  - 4+ CPU cores each
  - 8GB+ RAM each
  - 20GB+ disk space each
  - Network connectivity between them on 192.168.2.0/24 subnet
  - SSH access as user `rocky`

### Setup Timeline

Follow the guides in this order:

1. **[Prerequisites](docs/prerequisites.md)** - 15 minutes
   - Verify network connectivity
   - Install basic tools and dependencies

2. **[Machine 1 - SLURM Setup](docs/machine1-slurm.md)** - 30-45 minutes
   - Install SLURM controller and compute nodes
   - Configure partitions and resources

3. **[Machine 2 - k3s Setup](docs/machine2-k3s.md)** - 20-30 minutes
   - Install single-node k3s cluster
   - Verify Kubernetes functionality

4. **[Interlink Setup](docs/interlink-setup.md)** - 30-45 minutes
   - Install Interlink components on both machines
   - Configure VirtualKubelet and SLURM connector

5. **[Testing & Validation](docs/testing-procedures.md)** - 15-20 minutes
   - Run end-to-end tests
   - Submit jobs from k3s to SLURM

6. **[Troubleshooting](docs/troubleshooting.md)** - As needed
   - Common issues and solutions
   - Debug networking and service problems

## Common Tasks Reference

For general Linux tasks (SSH setup, firewall configuration, etc.), see [common-tasks.md](docs/common-tasks.md).

## Key Concepts to Understand

### SLURM
- **Workload Manager**: Allocates and schedules compute jobs
- **Multi-machine capable**: Can span multiple compute nodes
- **Job queuing**: Uses slurm.conf for configuration

### Kubernetes (k3s)
- **Container orchestrator**: Deploys and manages containerized workloads
- **Lightweight**: k3s is ideal for single-node demonstration
- **Extensible**: VirtualKubelet allows custom backends

### Interlink
- **VirtualKubelet-based**: Acts as a Kubelet to k3s
- **SLURM connector**: Translates pods to SLURM jobs
- **Transparent scheduling**: Seamless integration between two systems

## Important Notes

⚠️ **This is a demonstration setup**, not production-ready. For production use:
- Add proper security (TLS, authentication, authorization)
- Implement persistent storage solutions
- Set up monitoring and logging
- Plan for high availability

## Testing Your Setup

Once complete, you should be able to:

1. SSH to both machines and run basic system commands
2. Submit SLURM jobs on Machine 1 and verify they execute
3. Deploy k3s pods on Machine 2 and verify they run
4. Submit a Kubernetes pod that transparently runs as a SLURM job
5. View pod status in both k3s and SLURM simultaneously

## Troubleshooting

If you encounter issues:

1. Check [troubleshooting.md](docs/troubleshooting.md) for common solutions
2. Verify network connectivity between machines: `ssh rocky@192.168.2.170`
3. Check service status: `systemctl status slurmd` (SLURM) or `systemctl status k3s` (k3s)
4. Review logs: `/var/log/slurm/` or `journalctl -xe`

## Support

For issues with:
- **SLURM**: See [Machine 1 - SLURM Setup](docs/machine1-slurm.md) or [troubleshooting.md](docs/troubleshooting.md)
- **k3s**: See [Machine 2 - k3s Setup](docs/machine2-k3s.md)
- **Interlink**: See [Interlink Setup](docs/interlink-setup.md)

## License

These course materials are provided for educational purposes.

## Questions?

Refer to the detailed documentation in the `docs/` directory for comprehensive setup instructions and troubleshooting guides.

---

**Ready to begin?** Start with [Prerequisites](docs/prerequisites.md)! ➡️
