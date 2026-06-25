# Machine 1: SLURM Installation and Configuration

This guide covers the installation and configuration of SLURM on Machine 1 (192.168.2.170).

## Overview

SLURM (Simple Linux Utility for Resource Management) is an open-source workload manager used for HPC clusters. In this demo setup, Machine 1 will run:
- **SLURM Controller** (slurmctld) - Manages the cluster
- **SLURM Compute Node** (slurmd) - Executes jobs locally
- **SLURM Database** (optional but recommended) - Stores accounting data

## Prerequisites

Before starting, ensure you have completed [Prerequisites and Environment Setup](prerequisites.md).

Key assumptions:
- Machine 1 IP: 192.168.2.170
- Machine 1 Hostname: slurm-machine
- User: rocky
- OS: Rocky Linux 9

## Step 1: Install SLURM Dependencies

All commands in this section should be run on **Machine 1 (192.168.2.170)**.

```bash
# SSH to Machine 1
ssh rocky@192.168.2.170

# Update package list
sudo dnf update -y

# Install build tools and dependencies
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y \
  munge \
  munge-devel \
  munge-libs \
  readline-devel \
  mariadb-devel \
  hwloc-devel \
  openssl-devel \
  perl-devel \
  contribs
```

## Step 2: Create SLURM User Account

SLURM runs under the `slurm` user for security:

```bash
# Create slurm user
sudo useradd -r -s /bin/bash slurm

# Create necessary directories
sudo mkdir -p /var/spool/slurm
sudo mkdir -p /var/log/slurm
sudo mkdir -p /etc/slurm

# Set ownership
sudo chown -R slurm:slurm /var/spool/slurm
sudo chown -R slurm:slurm /var/log/slurm

# Verify
id slurm
```

## Step 3: Configure Munge for Authentication

SLURM uses Munge for cluster-wide authentication:

```bash
# Create Munge key directory
sudo mkdir -p /etc/munge
cd /etc/munge

# Generate a munge key
sudo /usr/sbin/mungekey --verbose

# Set permissions
sudo chmod 600 /etc/munge/munge.key
sudo chown munge:munge /etc/munge/munge.key

# Start and enable Munge service
sudo systemctl enable mungd
sudo systemctl start mungd

# Verify Munge is working
sudo systemctl status mungd
```

## Step 4: Download and Compile SLURM

```bash
# Create build directory
mkdir -p ~/slurm-build
cd ~/slurm-build

# Download SLURM source (latest stable version)
# You can find the latest version at https://www.schedmd.com/downloads.html
wget https://www.schedmd.com/downloads/latest/slurm-latest.tar.bz2

# Or use a specific version
wget https://www.schedmd.com/downloads/tar/slurm-23.11.7.tar.bz2

# Extract
tar -xjf slurm-23.11.7.tar.bz2
cd slurm-23.11.7

# Configure (typical configuration for single machine)
./configure --prefix=/usr \
  --sysconfdir=/etc/slurm \
  --localstatedir=/var \
  --with-munge=/usr \
  --with-mysql_config=/usr/bin/mysql_config

# Compile (this may take a few minutes)
make -j $(nproc)

# Install
sudo make install
```

## Step 5: Create SLURM Configuration File

Create `/etc/slurm/slurm.conf`:

```bash
# Create the config directory if not exists
sudo mkdir -p /etc/slurm

# Create slurm.conf
cat > /tmp/slurm.conf << 'EOF'
# SLURM Configuration File
# Generated for HPC Course Demo
# Machine: 192.168.2.170 (slurm-machine)

ClusterName=hpc-cluster
ControlMachine=slurm-machine
ControlAddr=192.168.2.170
SlurmctldPort=6817
SlurmdPort=6818
AuthType=auth/munge
AuthAltTypes=auth/jwt
StateSaveLocation=/var/spool/slurm
SlurmdSpoolDir=/var/spool/slurmd
SwitchType=switch/none
MpiDefault=none
ProctrackType=proctrack/cgroup
ProctrackType=proctrack/linux
TaskPlugin=task/cgroup
InactiveLimit=0
KillWaitTime=30
MinJobAge=300
SlurmctldTimeout=120
SlurmdTimeout=300
Waittime=0
SchedulerType=sched/backfill
SelectType=select/cons_tres
SelectTypeParameters=CR_Core
FastSchedule=1
DefMemPerCPU=1024

# Job accounting
JobAcctGatherType=jobacct_gather/linux
JobAcctGatherFrequency=30

# Default job parameters
MaxArraySize=1000
MaxJobCount=5000
MaxStepCount=40000

# Create default partition
PartitionName=default Nodes=slurm-machine Default=YES MaxTime=3600
NodeName=slurm-machine CPUs=4 RealMemory=7500 State=unknown
EOF

# Copy to /etc/slurm/
sudo cp /tmp/slurm.conf /etc/slurm/slurm.conf

# Set permissions
sudo chown slurm:slurm /etc/slurm/slurm.conf
sudo chmod 644 /etc/slurm/slurm.conf

# Verify configuration
sudo slurmctld -Cc  # Validates the config file
```

### Configuration Explanation

Key parameters in slurm.conf:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| ClusterName | hpc-cluster | Name of the SLURM cluster |
| ControlMachine | slurm-machine | Hostname of the controller (must resolve) |
| ControlAddr | 192.168.2.170 | IP address of the controller |
| SlurmctldPort | 6817 | Port for controller (default) |
| SlurmdPort | 6818 | Port for compute nodes (default) |
| AuthType | auth/munge | Authentication method |
| ProctrackType | proctrack/cgroup | Process tracking method |
| SelectType | select/cons_tres | Job allocation strategy |
| PartitionName | default | Queue/partition name |
| Nodes | slurm-machine | Which nodes are in this partition |
| CPUs | 4 | Number of CPUs on this node |
| RealMemory | 7500 | Available memory in MB |

## Step 6: Configure cgroup Plugin

Create `/etc/slurm/cgroup.conf`:

```bash
cat > /tmp/cgroup.conf << 'EOF'
CgroupMountpoint=/cgroup
CgroupAutomount=yes
ConstrainCores=no
ConstrainRAMSpace=no
EOF

sudo cp /tmp/cgroup.conf /etc/slurm/cgroup.conf
sudo chown slurm:slurm /etc/slurm/cgroup.conf
sudo chmod 644 /etc/slurm/cgroup.conf
```

## Step 7: Create Compute Node Configuration

Create directories for compute node state:

```bash
# Create slurmd spool directory
sudo mkdir -p /var/spool/slurmd
sudo chown slurm:slurm /var/spool/slurmd
sudo chmod 755 /var/spool/slurmd

# Create log directory for compute node
sudo touch /var/log/slurm/slurmd.log
sudo chown slurm:slurm /var/log/slurm/slurmd.log
```

## Step 8: Start SLURM Services

```bash
# Create systemd service files if not already present
# slurmctld service
sudo bash -c 'cat > /etc/systemd/system/slurmctld.service << EOF
[Unit]
Description=SLURM controller daemon
After=network.target munge.service
Wants=slurmctld.service

[Service]
Type=forking
ExecStart=/usr/sbin/slurmctld
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF'

# slurmd service
sudo bash -c 'cat > /etc/systemd/system/slurmd.service << EOF
[Unit]
Description=SLURM compute node daemon
After=network.target munge.service slurmctld.service
Wants=slurmd.service

[Service]
Type=forking
ExecStart=/usr/sbin/slurmd -D
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=process
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF'

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable slurmctld
sudo systemctl start slurmctld

# Wait a moment for controller to start
sleep 3

sudo systemctl enable slurmd
sudo systemctl start slurmd

# Verify services are running
sudo systemctl status slurmctld
sudo systemctl status slurmd
```

## Step 9: Test SLURM Installation

```bash
# Check cluster status
sinfo

# Expected output: Shows the default partition with 1 node

# Check node status in detail
scontrol show node slurm-machine

# List jobs (should be empty initially)
squeue

# Check controller status
scontrol ping
```

If you see the node listed in `sinfo` with state `idle`, SLURM is working correctly.

## Step 10: Submit a Test Job

```bash
# Create a simple test job script
cat > /tmp/test-job.sh << 'EOF'
#!/bin/bash
#SBATCH --job-name=test
#SBATCH --output=/tmp/test-job-%j.out
#SBATCH --error=/tmp/test-job-%j.err
#SBATCH --time=00:01:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

echo "Hello from SLURM!"
hostname
date
sleep 5
echo "Job completed!"
EOF

# Make it executable
chmod +x /tmp/test-job.sh

# Submit the job
sbatch /tmp/test-job.sh

# Check job status
squeue

# Wait for completion and check output
sleep 10
cat /tmp/test-job-*.out
cat /tmp/test-job-*.err
```

Expected output should show the job executed and printed "Hello from SLURM!" with the hostname and date.

## Step 11: Configure Firewall for SLURM

```bash
# Add SLURM ports to firewall
sudo firewall-cmd --permanent --add-port=6817/tcp  # slurmctld
sudo firewall-cmd --permanent --add-port=6818/tcp  # slurmd
sudo firewall-cmd --permanent --add-port=6819/tcp  # slurmd

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

## Verification Checklist

Verify the following before proceeding to Interlink setup:

- [ ] Munge service is running: `sudo systemctl status mungd`
- [ ] SLURM controller running: `sudo systemctl status slurmctld`
- [ ] SLURM compute daemon running: `sudo systemctl status slurmd`
- [ ] Cluster visible: `sinfo` shows default partition
- [ ] Node is idle: `sinfo` shows state as `idle`
- [ ] Test job completed: Test job script executed successfully
- [ ] Firewall ports open: `sudo firewall-cmd --list-ports` includes 6817-6819

## Troubleshooting SLURM Issues

### Nodes show "down" state

```bash
# Check slurmd logs
tail -f /var/log/slurm/slurmd.log

# Restart slurmd
sudo systemctl restart slurmd

# Check again
sinfo
```

### Cannot connect to slurmctld

```bash
# Check if controller is running
sudo systemctl status slurmctld

# Check logs
tail -f /var/log/slurm/slurmctld.log

# Verify port is open
sudo ss -tlnp | grep slurm

# Test connectivity
scontrol ping
```

### Munge authentication fails

```bash
# Check munge service
sudo systemctl status mungd

# Restart munge
sudo systemctl restart mungd

# Verify key exists
ls -la /etc/munge/munge.key

# Test munge authentication
munge -n | unmunge

# If not working, regenerate key
sudo /usr/sbin/mungekey --verbose
```

### Jobs don't run (stuck in pending)

```bash
# Check job details
scontrol show job <job-id>

# Common reasons:
# 1. Node not idle - check sinfo
# 2. Job has conflicting requirements - check sbatch command
# 3. Invalid partition - verify partition name in sbatch

# Try with explicit debug:
srun -vvv hostname
```

## Next Steps

Once SLURM is verified working:

1. If you haven't set up Machine 2 yet, go to [Machine 2 - k3s Setup](machine2-k3s.md)
2. After both machines are ready, proceed to [Interlink Setup](interlink-setup.md)

---

**SLURM setup complete?** Move to the next phase! ➡️
