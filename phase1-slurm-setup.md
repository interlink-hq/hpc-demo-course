# Phase 1: SLURM Setup on Machine 1

Set up SLURM on the HPC machine (192.168.2.170). This will be the backend that Interlink connects to.

## Install SLURM

```bash
# Connect to Machine 1
ssh rocky@192.168.2.170

# Install required packages
sudo dnf install -y \
  gcc g++ \
  make \
  libmunge-dev \
  munge \
  munge-libs \
  mysql-server \
  mariadb-devel \
  readline-devel \
  pam-devel \
  openssl-devel \
  pmix-devel \
  numactl-devel \
  git \
  curl

# Clone SLURM (use a stable tag)
cd /tmp
git clone --depth 1 --branch slurm-24-05 https://github.com/SchedMD/slurm.git
cd slurm

# Build from source
./configure --prefix=/opt/slurm
make -j$(nproc)
sudo make install

# Create slurm user
sudo useradd -r -s /bin/false slurm || true

# Setup directories
sudo mkdir -p /var/spool/slurm /var/spool/slurmd
sudo chown slurm:slurm /var/spool/slurm /var/spool/slurmd
sudo chmod 755 /var/spool/slurm /var/spool/slurmd

# Create minimal slurm.conf
sudo tee /etc/slurm/slurm.conf > /dev/null <<'EOF'
# Simple single-node SLURM config
ControlMachine=machine1
ControlAddr=192.168.2.170
AccountingStorageHost=localhost
AccountingStorageType=accounting_storage/none
JobCompType=jobcomp/none
NodeName=machine1 CPUs=4 RealMemory=8000 State=UNKNOWN
PartitionName=default Nodes=machine1 Default=YES

# Paths
SlurmdLogFile=/var/log/slurm/slurmd.log
SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdSpoolDir=/var/spool/slurmd

# Network
MungeSocketFile=/var/run/munge/munge.socket
EOF

# Start services
sudo systemctl restart munge
sudo /opt/slurm/sbin/slurmctld -c
sudo /opt/slurm/sbin/slurmd -c

# Verify
/opt/slurm/bin/sinfo
/opt/slurm/bin/sbatch --version
```

## Test SLURM

```bash
# Create test job
cat > /tmp/test.sh <<'EOF'
#!/bin/bash
#SBATCH --job-name=test
#SBATCH --time=1:00
echo "Hello from SLURM job"
sleep 10
EOF

# Submit and check
/opt/slurm/bin/sbatch /tmp/test.sh
/opt/slurm/bin/squeue
/opt/slurm/bin/sacct
```

## Add to PATH

```bash
# Make SLURM tools available globally
echo 'export PATH=/opt/slurm/bin:/opt/slurm/sbin:$PATH' | sudo tee -a /etc/profile.d/slurm.sh

# Reload
source /etc/profile.d/slurm.sh

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
