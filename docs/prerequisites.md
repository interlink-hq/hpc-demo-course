# Prerequisites and Environment Setup

This guide covers all prerequisites and basic setup tasks required before installing SLURM, k3s, or Interlink.

## Infrastructure Requirements

### Machine 1 (SLURM Controller and Compute)
- **IP Address**: 192.168.2.170
- **Hostname**: `slurm-machine` (or your choice)
- **OS**: Rocky Linux 9
- **CPU**: 4+ cores
- **RAM**: 8GB minimum
- **Disk**: 20GB minimum
- **Network**: Connectivity to 192.168.2.0/24 subnet

### Machine 2 (k3s Server)
- **IP Address**: 192.168.2.84
- **Hostname**: `k3s-machine` (or your choice)
- **OS**: Rocky Linux 9
- **CPU**: 4+ cores
- **RAM**: 8GB minimum
- **Disk**: 20GB minimum
- **Network**: Connectivity to 192.168.2.0/24 subnet

### Common Requirements
- **User**: `rocky` (default Rocky Linux user)
- **SSH Access**: Both machines must have SSH enabled
- **Network**: Both machines must be able to reach each other on the 192.168.2.0/24 subnet
- **Internet Access**: For downloading packages (or pre-cached packages available)

## Pre-Setup Checklist

### On Both Machines

#### 1. Verify Network Connectivity

```bash
# From Machine 1 (192.168.2.170), verify network
ip addr show
ip route show
ping 192.168.2.1        # Gateway
ping 192.168.2.84       # Machine 2

# From Machine 2 (192.168.2.84), verify network
ip addr show
ip route show
ping 192.168.2.1        # Gateway
ping 192.168.2.170      # Machine 1
```

Expected output:
- IP addresses correctly assigned (170 and 84)
- Gateway reachable
- Both machines can ping each other

#### 2. Set Hostnames

```bash
# On Machine 1 (192.168.2.170)
sudo hostnamectl set-hostname slurm-machine
echo "192.168.2.170 slurm-machine" | sudo tee -a /etc/hosts
echo "192.168.2.84 k3s-machine" | sudo tee -a /etc/hosts

# On Machine 2 (192.168.2.84)
sudo hostnamectl set-hostname k3s-machine
echo "192.168.2.170 slurm-machine" | sudo tee -a /etc/hosts
echo "192.168.2.84 k3s-machine" | sudo tee -a /etc/hosts
```

Verify hostname setup:
```bash
hostname
cat /etc/hostname
cat /etc/hosts
```

#### 3. Update System Packages

```bash
sudo dnf update -y
sudo dnf upgrade -y
```

#### 4. Install Essential Tools

```bash
sudo dnf install -y \
  vim \
  git \
  curl \
  wget \
  htop \
  tmux \
  net-tools \
  dnsmasq \
  bind-utils \
  telnet \
  openssh-clients \
  openssh-server
```

Verify SSH is running:
```bash
sudo systemctl enable sshd
sudo systemctl start sshd
sudo systemctl status sshd
```

#### 5. Configure Firewall

```bash
# Enable firewall if not already enabled
sudo systemctl enable firewalld
sudo systemctl start firewalld

# For this demo, open necessary ports (NOT for production)
# SLURM ports
sudo firewall-cmd --permanent --add-port=6817/tcp
sudo firewall-cmd --permanent --add-port=6818/tcp
sudo firewall-cmd --permanent --add-port=6819/tcp

# SSH
sudo firewall-cmd --permanent --add-service=ssh

# k3s ports
sudo firewall-cmd --permanent --add-port=6443/tcp
sudo firewall-cmd --permanent --add-port=10250/tcp

# Reload firewall
sudo firewall-cmd --reload

# Verify rules
sudo firewall-cmd --list-all
```

#### 6. SSH Key Setup (Optional but Recommended)

On your local machine, generate SSH keys if you don't have them:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Copy your public key to both machines:
```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub rocky@192.168.2.170
ssh-copy-id -i ~/.ssh/id_ed25519.pub rocky@192.168.2.84
```

Then verify passwordless login:
```bash
ssh rocky@192.168.2.170 hostname
ssh rocky@192.168.2.84 hostname
```

#### 7. Disable SELinux (For Simplicity)

⚠️ **Note**: This is only for demonstration. In production, configure SELinux properly.

```bash
# Check current status
sudo getenforce

# Set to permissive mode
sudo setenforce 0
sudo sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config

# Verify (takes effect after reboot)
sudo getenforce
```

#### 8. Configure Time Synchronization

Important for cluster operations:
```bash
# Check current status
timedatectl status

# If NTP is not synchronized:
sudo systemctl enable chronyd
sudo systemctl start chronyd
timedatectl set-ntp true
```

#### 9. Verify Time Sync Between Machines

```bash
# On both machines:
date

# They should show approximately the same time (within a few seconds)
```

#### 10. Create Standard Directories

```bash
# Create directories for configurations and logs
sudo mkdir -p /etc/slurm /var/log/slurm /var/spool/slurmd
sudo mkdir -p /opt/interlink

# Give appropriate permissions
sudo chown -R root:root /etc/slurm
sudo chown -R root:root /var/log/slurm
```

## Machine-Specific Prerequisites

### Machine 1 (SLURM) Only

#### Install Development Tools

```bash
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y \
  munge \
  munge-devel \
  munge-libs \
  readline-devel \
  mariadb-devel \
  hwloc-devel
```

#### Verify Available Resources

```bash
# Check CPU count
nproc

# Check available memory
free -h

# Check disk space
df -h /

# Output should show:
# - Multiple CPUs (4+)
# - Multiple GB of RAM
# - Plenty of disk space
```

### Machine 2 (k3s) Only

#### Install Container Runtime Requirements

```bash
sudo dnf install -y \
  container-selinux \
  selinux-policy-base \
  selinux-policy-devel \
  apparmor \
  apparmor-devel
```

## Verification Checklist

Before proceeding to the next sections, verify the following on **both machines**:

- [ ] Network connectivity works (can ping between machines)
- [ ] Hostnames are set correctly
- [ ] SSH is enabled and running
- [ ] Essential tools are installed (git, curl, wget)
- [ ] Firewall is configured with necessary ports open
- [ ] Time is synchronized across machines
- [ ] SELinux is in permissive mode (or configured)
- [ ] Directories are created at `/etc/slurm`, `/var/log/slurm`, `/opt/interlink`
- [ ] For Machine 1: Development tools and SLURM dependencies installed
- [ ] For Machine 2: Container runtime requirements installed

## Troubleshooting Prerequisites

### Cannot SSH Between Machines
```bash
# Check if SSH service is running
sudo systemctl status sshd

# Check if firewall is blocking (temporarily disable for testing)
sudo systemctl stop firewalld

# Test SSH
ssh rocky@192.168.2.170  # from Machine 2
ssh rocky@192.168.2.84   # from Machine 1
```

### Hostname Not Resolving
```bash
# Check /etc/hosts has both entries
cat /etc/hosts

# Verify DNS is working
nslookup slurm-machine
nslookup k3s-machine
```

### Firewall Issues
```bash
# List all open ports
sudo firewall-cmd --list-ports

# If a required port is missing, add it
sudo firewall-cmd --permanent --add-port=<PORT>/tcp
sudo firewall-cmd --reload
```

## Next Steps

Once you've verified everything above:

- **Machine 1 users** → Go to [Machine 1 - SLURM Setup](machine1-slurm.md)
- **Machine 2 users** → Go to [Machine 2 - k3s Setup](machine2-k3s.md)
- **Both setup paths** eventually lead to [Interlink Setup](interlink-setup.md)

---

**Completed prerequisites?** Continue to the setup for your assigned machine! ➡️
