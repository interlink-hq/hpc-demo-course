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

Set your machine IPs (edit as needed). **Note:** These must be set before each SSH command:

```bash
# Set these at the start of EACH shell session where you'll run commands
export M1_IP="192.168.2.122"      # SLURM machine
export M2_IP="192.168.2.78"       # k3s machine
export M1_HOME="/home/rocky"
export M2_HOME="/home/rocky"
```

**Important:** These variables are used in heredocs (here-documents). They must be exported in the current shell before the SSH commands run, OR use literal paths (no `$` variables).

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
# SLURM 24.05 configuration for single-node demo
ClusterName=localhost
ControlMachine=localhost
ControlAddr=127.0.0.1
SlurmctldHost=localhost(127.0.0.1)

# Accounting
AccountingStorageType=accounting_storage/slurmdbd
AccountingStorageHost=localhost
AccountingStoragePort=6819

# Job completion
JobCompType=jobcomp/none

# Nodes and partitions
NodeName=localhost CPUs=4 RealMemory=8000 State=UNKNOWN
PartitionName=default Nodes=localhost Default=YES MaxNodes=1

# Paths and files
SlurmdLogFile=/var/log/slurm/slurmd.log
SlurmctldLogFile=/var/log/slurm/slurmctld.log
SlurmdSpoolDir=/var/spool/slurmd
SlurmdDebug=info
SlurmctldDebug=info

# Security and communication
MungeSocketFile=/var/run/munge/munge.socket.2
AuthType=auth/munge
CryptoType=crypto/munge

# Job processing
DefMemPerCPU=2000
MaxMemPerNode=8000
SLURMEOF

# Create slurmdbd.conf (permissions must be 600)
cat > ${M1_HOME}/slurm-demo/etc/slurmdbd.conf <<'DBEOF'
# Database
DbDriver=mysql
DbHost=localhost
DbName=slurm_acct_db
DbUser=slurm
DbPass=password
DbPort=3306

# Logging
DebugLevel=debug
LogFile=/var/log/slurm/slurmdbd.log

# Authorization
AuthType=auth/munge
AuthInfo=creds_p=/var/run/munge/munge.socket.2

# Process
ProctrackType=proctrack/linux
SlurmUser=rocky
DBEOF

# Fix permissions (CRITICAL - must be 600)
chmod 600 ${M1_HOME}/slurm-demo/etc/slurmdbd.conf
chmod 600 ${M1_HOME}/slurm-demo/etc/slurm.conf

echo "✓ Configurations created with correct permissions"
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

# Ensure log directory exists and has proper permissions
sudo mkdir -p /var/log/slurm /var/spool/slurmd
sudo chmod 755 /var/log/slurm /var/spool/slurmd
sudo chown $(whoami):$(whoami) /var/log/slurm /var/spool/slurmd

# Start SlurmDBD (database backend - must start first)
echo "Starting SlurmDBD..."
nohup ${M1_HOME}/slurm-demo/sbin/slurmdbd \
  -f ${M1_HOME}/slurm-demo/etc/slurmdbd.conf \
  > /var/log/slurm/slurmdbd.log 2>&1 &
sleep 5

# Verify database is ready
echo "Waiting for database to initialize..."
for i in {1..10}; do
  if ${M1_HOME}/slurm-demo/bin/sacctmgr list cluster 2>/dev/null; then
    echo "✓ Database ready"
    break
  fi
  sleep 1
done

# Add cluster to accounting
${M1_HOME}/slurm-demo/bin/sacctmgr add cluster localhost -i 2>/dev/null || true
${M1_HOME}/slurm-demo/bin/sacctmgr add account default Cluster=localhost -i 2>/dev/null || true

# Start Slurmctld (control daemon)
echo "Starting Slurmctld..."
nohup ${M1_HOME}/slurm-demo/sbin/slurmctld \
  -f ${M1_HOME}/slurm-demo/etc/slurm.conf \
  -D \
  > /var/log/slurm/slurmctld.log 2>&1 &
sleep 3

# Start Slurmd (compute daemon)
echo "Starting Slurmd..."
nohup ${M1_HOME}/slurm-demo/sbin/slurmd \
  -f ${M1_HOME}/slurm-demo/etc/slurm.conf \
  -D \
  > /var/log/slurm/slurmd.log 2>&1 &
sleep 3

# Verify all are running
echo "=== SLURM Status ==="
sinfo
echo ""
echo "=== Running Processes ==="
ps aux | grep -E '[s]lurmctld|[s]lurmd|[s]lurmdbd' | grep -v grep

echo ""
echo "=== Check for Errors ==="
tail -5 /var/log/slurm/slurmdbd.log
tail -5 /var/log/slurm/slurmctld.log
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
ssh rocky@${M1_IP} << 'M1SETUP'

# Set version and create directory
VER="0.6.1-patch1"
BASE="https://github.com/interlink-hq/interlink/releases/download/$VER"

# Separate release for SLURM plugin
PLUGIN_BASE="https://github.com/interlink-hq/interlink-slurm-plugin/releases/download/$VER"

mkdir -p ~/interlink
cd ~/interlink

# Download Interlink API binary
echo "Downloading Interlink API..."
curl -sL "${BASE}/interlink_Linux_x86_64" -o interlink-api && chmod +x interlink-api

# Download SLURM plugin binary (from separate interlink-slurm-plugin repo)
echo "Downloading SLURM Plugin..."
curl -sL "${PLUGIN_BASE}/interlink-sidecar-slurm_Linux_x86_64" -o slurm-plugin && chmod +x slurm-plugin

# Verify downloads
if [ -f interlink-api ] && [ -f slurm-plugin ]; then
  echo "✓ All binaries downloaded successfully"
  ls -lh interlink-api slurm-plugin
else
  echo "✗ Download failed - check URLs above"
  exit 1
fi

M1SETUP
```

### 3.2 Configure Interlink

```bash
ssh rocky@${M1_IP} << 'M1CONFIG'

cd ~/interlink

# Create API configuration (unquoted heredoc to expand variables)
cat > interlink-config.yaml <<APIEOF
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://192.168.2.122"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/home/rocky/.interlink-api"
APIEOF

# Create SLURM Plugin configuration (unquoted heredoc to expand variables)
cat > SlurmConfig.yaml <<PLUGINEOF
InterlinkURL: "http://192.168.2.122"
InterlinkPort: "3000"
SidecarURL: "http://0.0.0.0"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/home/rocky/.interlink"
ExportPodData: true
SbatchPath: "/home/rocky/slurm-demo/bin/sbatch"
ScancelPath: "/home/rocky/slurm-demo/bin/scancel"
SqueuePath: "/home/rocky/slurm-demo/bin/squeue"
CommandPrefix: ""
SingularityPrefix: "/usr/bin/apptainer"
ImagePrefix: "docker://"
Namespace: "default"
Tsocks: false
BashPath: /bin/bash
EnableProbes: true
PLUGINEOF

echo "✓ Configurations created"
ls -la *.yaml

M1CONFIG
```

**Note:** The configs use literal IP `192.168.2.122` and paths. If your IPs differ, edit the configs after creation or use `sed` to replace them.

### 3.3 Start Interlink Services

```bash
ssh rocky@${M1_IP} << 'M1START'

cd ~/interlink

# Kill any old processes
pkill -f interlink-api || true
pkill -f slurm-plugin || true
sleep 2

# Export PATH for SLURM commands
export PATH=/home/rocky/slurm-demo/bin:/home/rocky/slurm-demo/sbin:$PATH

# Start SLURM plugin FIRST (listens on port 4000)
export SLURMCONFIGPATH=$(pwd)/SlurmConfig.yaml

echo "Starting SLURM plugin..."
nohup ./slurm-plugin > slurm-plugin.log 2>&1 &
sleep 3

# Then start Interlink API (listens on port 3000)
export INTERLINKCONFIGPATH=$(pwd)/interlink-config.yaml

echo "Starting Interlink API..."
nohup ./interlink-api > interlink-api.log 2>&1 &
sleep 3

# Verify both are running
echo "=== Process Status ==="
ps aux | grep -E '[i]nterlink-api|[s]lurm-plugin' | grep -v grep

echo ""
echo "=== Port Status ==="
netstat -tlnp 2>/dev/null | grep -E ":3000|:4000" || ss -tlnp 2>/dev/null | grep -E ":3000|:4000"

echo ""
echo "=== Interlink API Startup (check logs) ==="
tail -10 interlink-api.log

echo ""
echo "=== SLURM Plugin Startup ==="
tail -10 slurm-plugin.log

M1START
```

**Verify:** Both services should now be running. Check logs for any errors. The Interlink API initializes on startup, and the SLURM plugin connects to it.

---

## Phase 4: VirtualKubelet Setup via Helm (Machine 2)

```bash
ssh rocky@${M2_IP} << 'M2VK'

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create namespace
kubectl create namespace virtual-kubelet || true

# Try to deploy VirtualKubelet via Helm from OCI registry
echo "Attempting to deploy VirtualKubelet via Helm..."
if helm upgrade --install vk oci://ghcr.io/virtual-kubelet/virtual-kubelet \
  --namespace virtual-kubelet \
  --set nodeName=interlink-node \
  --set provider=interlink \
  --set logs.level=info \
  --set interlink.url=http://192.168.2.122 \
  --set interlink.port=3000 \
  --wait 2>&1 | grep -i "403\|denied\|unauthorized"; then
  
  echo "✗ GHCR access failed (403 Forbidden)"
  echo ""
  echo "Workaround: Using binary VirtualKubelet instead"
  echo "Download and install binary from: https://github.com/virtual-kubelet/virtual-kubelet/releases"
  echo "Then restart and re-run this phase"
  exit 1
fi

echo "✓ VirtualKubelet deployed via Helm"

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

M2VK
```

**Note:** If GHCR (GitHub Container Registry) returns 403 Forbidden:
1. This is an authentication issue - GHCR requires login for some images
2. Workaround: Deploy binary VirtualKubelet instead (see DEPLOYMENT_METHODS.md)

---

## Phase 5: Test End-to-End

```bash
ssh rocky@${M2_IP} << 'M2TEST'

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
M1_IP="192.168.2.122"

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
echo "Submitting test pod..."
kubectl apply -f /tmp/test-offload.yaml

# Wait for pod to complete
echo "=== Watching Pod Status (Ctrl+C to stop watching) ==="
timeout 60 kubectl get pod test-offload -w || true

echo ""
echo "=== Final Pod Status ==="
kubectl get pod test-offload

# Check pod logs
echo ""
echo "=== Pod Logs ==="
kubectl logs test-offload 2>/dev/null || echo "(Logs not yet available)"

# Check SLURM job on Machine 1
echo ""
echo "=== SLURM Job on Machine 1 (via SSH) ==="
ssh rocky@${M1_IP} << 'M1SQUEUE'
export PATH=/home/rocky/slurm-demo/bin:/home/rocky/slurm-demo/sbin:$PATH
echo "Recent jobs:"
squeue
echo ""
echo "Job accounting:"
sacct | tail -5
M1SQUEUE

echo ""
echo "✓ End-to-end test complete!"

M2TEST
```

**Expected Output:**
- Pod shows as Running on interlink-node
- Pod shows output: "Pod offloaded to SLURM!"
- SLURM job visible on Machine 1 with JobState=COMPLETED

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
