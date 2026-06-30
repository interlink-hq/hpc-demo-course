# Configuration & Machine Setup

This document defines the configuration variables and prerequisites for the entire Interlink deployment.

## Network Configuration

Update these variables for your environment:

```bash
# Machine 1 (SLURM + Interlink)
M1_IP="192.168.2.122"
M1_USER="rocky"
M1_HOME="/home/rocky"

# Machine 2 (k3s + VirtualKubelet)
M2_IP="192.168.2.78"
M2_USER="rocky"
M2_HOME="/home/rocky"

# Network settings
NETWORK="192.168.2.0/24"
DNS_SERVERS="8.8.8.8,8.8.4.4"
```

## Machine Prerequisites

### Machine 1 (SLURM + Interlink)

**OS:** Rocky Linux 9.x or compatible
**Specs:** Min 2 CPU, 4GB RAM, 20GB disk

**Required Packages:**
```bash
# Enable repositories
sudo dnf install -y epel-release
sudo crb enable

# Build tools and dependencies
sudo dnf install -y \
  gcc gcc-c++ \
  make \
  pkgconfig \
  git curl wget \
  readline-devel pam-devel openssl-devel \
  libseccomp-devel hwloc-devel \
  numactl-devel hwloc-devel \
  dbus-devel \
  mariadb mariadb-devel \
  munge munge-libs \
  munge-devel

# Container runtime
sudo dnf install -y apptainer

# Verify installations
sinfo --version 2>/dev/null || echo "SLURM not yet installed (build from source)"
apptainer --version
```

### Machine 2 (k3s + VirtualKubelet)

**OS:** Rocky Linux 9.x or compatible
**Specs:** Min 2 CPU, 4GB RAM, 20GB disk
**Network:** Must reach Machine 1 on port 3000 (Interlink API)

**Required Tools:**
```bash
# k3s (lightweight Kubernetes)
# Will be installed via: curl -sfL https://get.k3s.io | sh -

# Helm 3.x
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify Helm
helm version
```

## Port Requirements

Ensure these ports are open between machines:

| Service | Port | Machine | Required For |
|---------|------|---------|--------------|
| Interlink API | 3000 | M1 | VirtualKubelet communication |
| SLURM Plugin | 4000 | M1 | API ↔ Plugin communication |
| k3s API | 6443 | M2 | kubectl access |
| kubelets | 10250 | M2 | Internal communication |

## SSH Setup

Ensure passwordless SSH between machines (optional but recommended):

```bash
# On each machine, generate key if not exists
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 || true

# Copy M1 public key to M2's authorized_keys
cat ~/.ssh/id_ed25519.pub | ssh rocky@M2_IP "cat >> ~/.ssh/authorized_keys"

# Verify connection works
ssh rocky@M2_IP "echo 'SSH works'"
```

## Directory Structure

All deployments use this directory structure:

```bash
# Machine 1
~/interlink/                         # Interlink binaries and configs
  ├── interlink-api                  # API binary
  ├── slurm-plugin                   # SLURM plugin binary
  ├── interlink-config.yaml          # API configuration
  ├── SlurmConfig.yaml               # Plugin configuration
  ├── interlink-api.log              # API logs
  └── slurm-plugin.log               # Plugin logs

# Machine 2
~/virtual-kubelet/                   # VirtualKubelet setup (if using binary)
  ├── vk                             # VirtualKubelet binary
  ├── vk.log                         # VirtualKubelet logs
  └── kubeconfig                     # Kubernetes config

# SLURM (Machine 1)
~/slurm-demo/                        # SLURM installation
  ├── bin/                           # SLURM binaries (sinfo, sbatch, etc.)
  ├── spool/                         # Job spool directory
  └── log/                           # SLURM logs
```

## Environment Variables

Source these for convenient testing:

```bash
# Machine 1
export M1_IP="192.168.2.122"
export SLURM_BIN="$HOME/slurm-demo/bin"
export INTERLINK_HOME="$HOME/interlink"
export PATH="$SLURM_BIN:$PATH"

# Machine 2
export M2_IP="192.168.2.78"
export M1_IP="192.168.2.122"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

## Verification Checklist

Before proceeding, verify:

- [ ] Both machines can ping each other
- [ ] Both machines have internet access (for downloads)
- [ ] Machine 1 has `gcc`, `git`, `curl` installed
- [ ] Machine 2 has internet access for k3s and Helm downloads
- [ ] Enough disk space on both machines (at least 5GB free)
- [ ] Firewall rules allow required ports (or is disabled for testing)
- [ ] SSH key-based authentication works (if setup)

---

Next: [Phase 1: SLURM Setup](phase1-slurm-setup.md)
