# Phase 1: SLURM Setup on Machine 1

Set up SLURM on the HPC machine. This will be the backend that Interlink connects to.

**Before starting:** Read [00-CONFIGURATION.md](00-CONFIGURATION.md) to set up IP variables and prerequisites.

## Install SLURM

```bash
# Set machine IP (update as needed)
M1_IP="192.168.2.122"
M1_HOME="/home/rocky"

# Connect to Machine 1
ssh rocky@${M1_IP}

# Enable EPEL and CRB repositories (needed for dependencies)
sudo dnf install -y epel-release
sudo crb enable

# Install build tools and dependencies
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
  munge munge-libs munge-devel

# Create working directory
mkdir -p ${M1_HOME}/slurm-build
cd ${M1_HOME}/slurm-build

# Clone SLURM (correct branch name: slurm-24.05 not slurm-24-05)
git clone --depth 1 --branch slurm-24.05 https://github.com/SchedMD/slurm.git
cd slurm

# Build from source
./configure --prefix=${M1_HOME}/slurm-demo
make -j$(nproc)
make install

# Create slurm user
sudo useradd -r -s /bin/false slurm || true

# Setup directories
sudo mkdir -p /var/spool/slurm /var/spool/slurmd /var/log/slurm
sudo chown slurm:slurm /var/spool/slurm /var/spool/slurmd /var/log/slurm
sudo chmod 755 /var/spool/slurm /var/spool/slurmd /var/log/slurm

# Create minimal slurm.conf
mkdir -p ${M1_HOME}/slurm-demo/etc
cat > ${M1_HOME}/slurm-demo/etc/slurm.conf <<'SLURMEOF'
# Simple single-node SLURM config
ControlMachine=localhost
ControlAddr=127.0.0.1
SlurmctldHost=localhost
AccountingStorageType=accounting_storage/slurmdbd
AccountingStorageHost=localhost
JobCompType=jobcomp/none
NodeName=localhost CPUs=4 RealMemory=8000 State=UNKNOWN
PartitionName=default Nodes=localhost Default=YES MaxNodes=1

# Paths
SlurmdLogFile=/var/log/slurm/slurmd.log
SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdSpoolDir=/var/spool/slurmd

# Network
MungeSocketFile=/var/run/munge/munge.socket
SLURMEOF

# Start munge (required for authentication)
sudo systemctl enable munge
sudo systemctl start munge

# Add SLURM to PATH
export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:$PATH

# Start SLURM daemons (as current user for testing, not root)
nohup ${M1_HOME}/slurm-demo/sbin/slurmctld -f ${M1_HOME}/slurm-demo/etc/slurm.conf > /tmp/slurmctld.log 2>&1 &
sleep 2
nohup ${M1_HOME}/slurm-demo/sbin/slurmd -f ${M1_HOME}/slurm-demo/etc/slurm.conf > /tmp/slurmd.log 2>&1 &
sleep 2

# Verify
${M1_HOME}/slurm-demo/bin/sinfo
${M1_HOME}/slurm-demo/bin/sbatch --version

echo "✓ SLURM installation complete"
```

## Set up SlurmDBD (Accounting Database)

Jobs will fail with `InvalidAccount` errors without this:

```bash
# Create slurmdbd configuration
mkdir -p ${M1_HOME}/slurm-demo/etc
cat > ${M1_HOME}/slurm-demo/etc/slurmdbd.conf <<'DBEOF'
ArchiveEvents=yes
ArchiveJobs=yes
ArchiveSteps=yes
ArchiveSuspend=yes
AuthType=auth/munge
DbDriver=mysql
DbHost=localhost
DbName=slurm_acct_db
DbUser=slurm
DbPort=3306
DebugLevel=4
ProctrackType=proctrack/linux
LogFile=/var/log/slurm/slurmdbd.log
PidFile=/var/run/slurmdbd.pid
SlurmUser=slurm
DBEOF

# Setup MariaDB for SlurmDBD
sudo systemctl enable mariadb
sudo systemctl start mariadb

# Create database (may prompt for root password)
sudo mysql -e "CREATE DATABASE IF NOT EXISTS slurm_acct_db;"
sudo mysql -e "GRANT ALL ON slurm_acct_db.* TO 'slurm'@'localhost' IDENTIFIED BY 'password';"
sudo mysql -e "FLUSH PRIVILEGES;"

# Start SlurmDBD
nohup ${M1_HOME}/slurm-demo/sbin/slurmdbd -f ${M1_HOME}/slurm-demo/etc/slurmdbd.conf > /tmp/slurmdbd.log 2>&1 &
sleep 2

# Add account to SLURM
${M1_HOME}/slurm-demo/bin/sacctmgr add cluster localhost
${M1_HOME}/slurm-demo/bin/sacctmgr add account default Cluster=localhost

echo "✓ SlurmDBD setup complete"
```

## Test SLURM

```bash
# Create test job
cat > /tmp/test.sh <<'EOF'
#!/bin/bash
#SBATCH --job-name=test
#SBATCH --time=00:01:00
#SBATCH --account=default
echo "Hello from SLURM job"
sleep 5
echo "Done"
EOF

chmod +x /tmp/test.sh

# Submit and check (add to PATH first)
export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:$PATH

${M1_HOME}/slurm-demo/bin/sbatch /tmp/test.sh
sleep 2
${M1_HOME}/slurm-demo/bin/squeue
${M1_HOME}/slurm-demo/bin/sacct

echo "✓ SLURM test complete"
```

## Add to PATH Permanently

```bash
# Make SLURM tools available globally
echo "export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:\$PATH" >> ~/.bashrc

# Reload
source ~/.bashrc

# Verify
which sbatch
sinfo
```

---

## Install Apptainer (Required for Container Support)

The Interlink SLURM plugin uses Apptainer (formerly Singularity) to run container workloads submitted from Kubernetes pods. This is **required** for the Interlink bridge to function.

```bash
# Install EPEL repository (if not already installed)
sudo dnf install -y epel-release

# Install Apptainer
sudo dnf install -y apptainer

# Verify installation
apptainer --version
apptainer run docker://busybox echo "Apptainer is working!"
```

**Important Notes:**
- Apptainer must be available on the machine where the SLURM plugin runs
- The plugin is configured with `SingularityPrefix: /usr/bin/apptainer` in the SlurmConfig.yaml
- Without Apptainer, pod execution will fail when Interlink tries to create containers
- Apptainer is compatible with OCI/Docker images, so existing container images will work

---

Next: [Phase 2: k3s Setup](phase2-k3s-setup.md)
