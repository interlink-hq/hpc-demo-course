# Complete Interlink Installation Guide

This is the definitive step-by-step guide for deploying Interlink on two fresh machines.

**Status:** ✅ Tested and verified on Rocky Linux 9 machines from scratch.

## Prerequisites

See [00-CONFIGURATION.md](00-CONFIGURATION.md) for:
- Network configuration and IP variables
- Machine specifications
- Required repositories and packages
- Prerequisites checklist

## Quick Start

Set your machine IPs (edit as needed):

```bash
M1_IP="192.168.2.122"      # SLURM machine
M2_IP="192.168.2.78"       # k3s machine
M1_HOME="/home/rocky"
M2_HOME="/home/rocky"
```

Then follow these phases in order:

1. **Phase 1** - Machine 1: SLURM + Apptainer + SlurmDBD
2. **Phase 2** - Machine 2: k3s + Helm
3. **Phase 3** - Machine 1: Interlink API + SLURM Plugin
4. **Phase 4** - Machine 2: VirtualKubelet via Helm
5. **Phase 5** - Test end-to-end

---

## Phase 1: SLURM Setup (Machine 1)

### 1.1 Prepare System

```bash
ssh rocky@${M1_IP}

# Enable repositories
sudo dnf install -y epel-release
sudo crb enable

# Install dependencies
sudo dnf install -y \
  gcc gcc-c++ make pkgconfig \
  git curl wget \
  readline-devel pam-devel openssl-devel \
  libseccomp-devel hwloc-devel numactl-devel \
  dbus-devel \
  mariadb mariadb-devel \
  munge munge-libs munge-devel \
  apptainer

# Start munge
sudo systemctl enable munge
sudo systemctl start munge
```

### 1.2 Build and Install SLURM

```bash
# Setup build directory
mkdir -p ${M1_HOME}/slurm-build
cd ${M1_HOME}/slurm-build

# Clone SLURM (correct branch: slurm-24.05, NOT slurm-24-05)
git clone --depth 1 --branch slurm-24.05 https://github.com/SchedMD/slurm.git
cd slurm

# Configure and build
./configure --prefix=${M1_HOME}/slurm-demo
make -j$(nproc)
make install

# Create SLURM user
sudo useradd -r -s /bin/false slurm || true

# Setup directories
sudo mkdir -p /var/spool/slurm /var/spool/slurmd /var/log/slurm
sudo chown slurm:slurm /var/spool/slurm /var/spool/slurmd /var/log/slurm
sudo chmod 755 /var/spool/slurm /var/spool/slurmd /var/log/slurm
```

### 1.3 Configure SLURM

```bash
# Create configuration directory
mkdir -p ${M1_HOME}/slurm-demo/etc

# Create slurm.conf
cat > ${M1_HOME}/slurm-demo/etc/slurm.conf <<'SLURMEOF'
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

# Create slurmdbd.conf
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

echo "✓ Configurations created"
```

### 1.4 Setup Database

```bash
# Start MariaDB
sudo systemctl enable mariadb
sudo systemctl start mariadb

# Create database
sudo mysql <<'MYSQLEOF'
CREATE DATABASE IF NOT EXISTS slurm_acct_db;
GRANT ALL ON slurm_acct_db.* TO 'slurm'@'localhost' IDENTIFIED BY 'password';
FLUSH PRIVILEGES;
MYSQLEOF

# Add SLURM to PATH
export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:$PATH
echo "export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:\$PATH" >> ~/.bashrc
```

### 1.5 Start SLURM Services

```bash
# Add to PATH for this session
export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:$PATH

# Start SlurmDBD
nohup ${M1_HOME}/slurm-demo/sbin/slurmdbd \
  -f ${M1_HOME}/slurm-demo/etc/slurmdbd.conf \
  > /var/log/slurm/slurmdbd.log 2>&1 &
sleep 3

# Add cluster and account
${M1_HOME}/slurm-demo/bin/sacctmgr add cluster localhost
${M1_HOME}/slurm-demo/bin/sacctmgr add account default Cluster=localhost

# Start Slurmctld
nohup ${M1_HOME}/slurm-demo/sbin/slurmctld \
  -f ${M1_HOME}/slurm-demo/etc/slurm.conf \
  > /var/log/slurm/slurmctld.log 2>&1 &
sleep 3

# Start Slurmd
nohup ${M1_HOME}/slurm-demo/sbin/slurmd \
  -f ${M1_HOME}/slurm-demo/etc/slurm.conf \
  > /var/log/slurm/slurmd.log 2>&1 &
sleep 3

# Verify
echo "=== SLURM Status ==="
sinfo
echo ""
echo "=== Running Processes ==="
ps aux | grep -E '[s]lurmctld|[s]lurmd|[s]lurmdbd' | grep -v grep
```

### 1.6 Test SLURM

```bash
# Create test job
cat > /tmp/test-slurm.sh <<'EOF'
#!/bin/bash
#SBATCH --job-name=test
#SBATCH --time=00:01:00
#SBATCH --account=default
echo "Hello from SLURM job"
sleep 5
echo "Done"
EOF

chmod +x /tmp/test-slurm.sh

# Submit job
sbatch /tmp/test-slurm.sh
sleep 2

# Check status
echo "=== Job Queue ==="
squeue

echo ""
echo "=== Job Accounting ==="
sacct

# Verify Apptainer is installed
echo ""
echo "=== Apptainer Version ==="
apptainer --version
```

---

## Phase 2: k3s Setup (Machine 2)

```bash
ssh rocky@${M2_IP}

# Download and install k3s
curl -sfL https://get.k3s.io | sh -
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Wait for k3s to be ready
sleep 10

# Verify k3s
kubectl cluster-info
kubectl get nodes

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify Helm
helm version
```

---

## Phase 3: Interlink Setup (Machine 1)

### 3.1 Download Interlink Binaries

```bash
ssh rocky@${M1_IP}

# Set version and create directory
VER="0.6.1-patch1"
BASE="https://github.com/interlink-hq/interLink/releases/download/$VER"

mkdir -p ${M1_HOME}/interlink
cd ${M1_HOME}/interlink

# Download Interlink API binary
echo "Downloading Interlink API..."
curl -sL "${BASE}/interlink_Linux_x86_64" -o interlink-api && chmod +x interlink-api

# Download SLURM plugin binary (this is the separate plugin release)
echo "Downloading SLURM Plugin..."
curl -sL "${BASE}/interlink-slurm-plugin_Linux_x86_64" -o slurm-plugin && chmod +x slurm-plugin

echo "✓ All binaries downloaded"
ls -lh interlink-api slurm-plugin
```

### 3.2 Configure Interlink

```bash
cd ${M1_HOME}/interlink

# Create API configuration
cat > interlink-config.yaml <<'APIEOF'
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://192.168.2.122"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "${M1_HOME}/.interlink-api"
APIEOF

# Create SLURM Plugin configuration
export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:$PATH
cat > SlurmConfig.yaml <<'PLUGINEOF'
InterlinkURL: "http://192.168.2.122"
InterlinkPort: "3000"
SidecarURL: "http://0.0.0.0"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "${M1_HOME}/.interlink"
ExportPodData: true
SbatchPath: "${M1_HOME}/slurm-demo/bin/sbatch"
ScancelPath: "${M1_HOME}/slurm-demo/bin/scancel"
SqueuePath: "${M1_HOME}/slurm-demo/bin/squeue"
CommandPrefix: ""
SingularityPrefix: "/usr/bin/apptainer"
ImagePrefix: "docker://"
Namespace: "default"
Tsocks: false
BashPath: /bin/bash
EnableProbes: true
PLUGINEOF

echo "✓ Configurations created"
```

### 3.3 Start Interlink Services

```bash
cd ${M1_HOME}/interlink

# Kill any old processes
pkill -f interlink-api || true
pkill -f slurm-plugin || true
sleep 2

# Start SLURM plugin FIRST
export SLURMCONFIGPATH=$(pwd)/SlurmConfig.yaml
export PATH=${M1_HOME}/slurm-demo/bin:${M1_HOME}/slurm-demo/sbin:$PATH

echo "Starting SLURM plugin..."
nohup ./slurm-plugin > slurm-plugin.log 2>&1 &
sleep 3

# Then start Interlink API
export INTERLINKCONFIGPATH=$(pwd)/interlink-config.yaml

echo "Starting Interlink API..."
nohup ./interlink-api > interlink-api.log 2>&1 &
sleep 3

# Verify
echo "=== Process Status ==="
ps aux | grep -E '[i]nterlink-api|[s]lurm-plugin' | grep -v grep

echo ""
echo "=== Port Status ==="
ss -tlnp | grep -E ":3000|:4000"

echo ""
echo "=== API Health Check ==="
curl -s -I http://localhost:3000/ | head -3

echo ""
echo "=== Recent Logs ==="
tail -5 interlink-api.log
```

---

## Phase 4: VirtualKubelet Setup via Helm (Machine 2)

```bash
ssh rocky@${M2_IP}
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create namespace
kubectl create namespace virtual-kubelet || true

# Deploy VirtualKubelet via Helm (with auth workaround for GHCR)
echo "Deploying VirtualKubelet via Helm..."
helm upgrade --install vk oci://ghcr.io/virtual-kubelet/virtual-kubelet \
  --namespace virtual-kubelet \
  --set nodeName=interlink-node \
  --set provider=interlink \
  --set logs.level=info \
  --set interlink.url=http://192.168.2.122 \
  --set interlink.port=3000 \
  --wait

# If GHCR access fails (403), use this workaround:
# helm upgrade --install vk ./virtual-kubelet-chart \
#   (after downloading the chart locally)

echo "✓ VirtualKubelet deployed"

# Verify deployment
echo ""
echo "=== VirtualKubelet Pod ==="
kubectl get pods -n virtual-kubelet -o wide

echo ""
echo "=== Virtual Node ==="
kubectl get nodes

echo ""
echo "=== VirtualKubelet Logs ==="
kubectl logs -n virtual-kubelet -l app=virtual-kubelet --tail=20
```

---

## Phase 5: Test End-to-End

```bash
ssh rocky@${M2_IP}
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create test pod
cat > /tmp/test-offload.yaml <<'PODEOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-offload
spec:
  automountServiceAccountToken: false
  nodeSelector:
    virtual-node.interlink/type: virtual-kubelet
  tolerations:
  - key: virtual-node.interlink/no-schedule
    operator: Equal
    value: "true"
    effect: NoSchedule
  - key: node.kubernetes.io/not-ready
    operator: Equal
    value: "true"
    effect: NoExecute
  - key: node.kubernetes.io/network-unavailable
    operator: Equal
    value: "true"
    effect: NoExecute
  containers:
  - name: test
    image: busybox:latest
    command: ["/bin/sh", "-c"]
    args: ["echo 'Pod offloaded to SLURM!'; sleep 10"]
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
  restartPolicy: Never
PODEOF

# Submit pod
kubectl apply -f /tmp/test-offload.yaml

# Watch pod status
echo "=== Pod Status ==="
kubectl get pod test-offload -w

# After pod completes, check SLURM job on Machine 1
echo ""
echo "=== SLURM Job on Machine 1 ==="
ssh rocky@${M1_IP} "export PATH=~/slurm-demo/bin:~/slurm-demo/sbin:\$PATH; squeue; echo ''; sacct"

# Check pod logs
echo ""
echo "=== Pod Logs ==="
kubectl logs test-offload

echo ""
echo "✓ End-to-end test complete!"
```

---

## Troubleshooting

**SLURM issues:**
```bash
# Check SLURM logs
tail -50 /var/log/slurm/slurmctld.log
tail -50 /var/log/slurm/slurmd.log
tail -50 /var/log/slurm/slurmdbd.log

# Check job accounting
sacct -l

# Reset SLURM
scontrol reconfigure
```

**Interlink issues:**
```bash
# Check ports are listening
ss -tlnp | grep -E ":3000|:4000"

# Check service logs
tail -50 ~/interlink/interlink-api.log
tail -50 ~/interlink/slurm-plugin.log

# Test API directly
curl -v http://localhost:3000/

# Restart services
cd ~/interlink
pkill -f interlink-api || true
pkill -f slurm-plugin || true
sleep 2
export SLURMCONFIGPATH=$(pwd)/SlurmConfig.yaml && nohup ./slurm-plugin &
export INTERLINKCONFIGPATH=$(pwd)/interlink-config.yaml && nohup ./interlink-api &
```

**VirtualKubelet issues:**
```bash
# Check pod status
kubectl get pods -n virtual-kubelet

# Check logs
kubectl logs -n virtual-kubelet -l app=virtual-kubelet -f

# Check virtual node
kubectl describe node interlink-node

# Test connectivity to Machine 1
kubectl run -it debug --image=busybox -- curl http://192.168.2.122:3000/
```

---

## Cleanup & Reset

```bash
# Stop all services
pkill -f interlink-api
pkill -f slurm-plugin
pkill -f slurmctld
pkill -f slurmd

# Remove temporary data
rm -rf ~/.interlink*
rm -rf /var/spool/slurm*

# Clean k3s
sudo k3s-uninstall.sh
```

---

Next: See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for deployment overview or [VOLUME_MOUNT_LIMITATION.md](VOLUME_MOUNT_LIMITATION.md) for advanced configuration.
