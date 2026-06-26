# Phase 3: Interlink Setup - Full Implementation

Deploy real Interlink binaries to bridge SLURM (Machine 1) and k3s (Machine 2).

## Architecture

```
Machine 1 (192.168.2.170)              Machine 2 (192.168.2.84)
─────────────────────────              ──────────────────────
Interlink API (port 3000)              VirtualKubelet Pod
└─ REST/HTTP endpoint                  └─ Deployed via Helm chart
SLURM (local)                          k3s Kubernetes (Helm)
└─ sbatch, squeue, scancel             └─ Watches for pods on "interlink-node"
```

## Step 1: Download Interlink Binaries

Use pre-built binaries from [Interlink releases](https://github.com/interlink-hq/interLink/releases).

### Machine 1 (SLURM + Interlink API)

```bash
ssh rocky@192.168.2.170 << 'M1SETUP'
VER="0.6.1-patch1"
BASE="https://github.com/interlink-hq/interLink/releases/download/$VER"

mkdir -p ~/interlink
cd ~/interlink

# Download Interlink API binary
curl -sL "$BASE/interlink_Linux_x86_64" -o interlink-api && chmod +x interlink-api

# Download SSH tunnel binary (optional, for remote connections)
curl -sL "$BASE/ssh-tunnel_Linux_x86_64" -o ssh-tunnel && chmod +x ssh-tunnel

echo "✓ Binaries downloaded"
ls -lh interlink-api ssh-tunnel
M1SETUP
```

### Machine 2 (k3s + Helm)

**Note:** VirtualKubelet is deployed via Helm, NOT as a binary. Install Helm instead:

```bash
ssh rocky@192.168.2.84 << 'M2SETUP'
echo "=== Checking/Installing Helm ==="
which helm || (
  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
  helm version
)

echo "✓ Helm ready"
M2SETUP
```

## Step 2: Configure Interlink (Machine 1)

**IMPORTANT:** Before starting, ensure Apptainer is installed on Machine 1 (see Phase 1: Install Apptainer).

Create configuration files:

```bash
ssh rocky@192.168.2.170 << 'CONFIG'
cd ~/interlink

# Interlink API configuration
cat > interlink-config.yaml <<'EOF'
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://192.168.2.170"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/tmp/.interlink-api"
EOF

# SLURM Plugin configuration (note SingularityPrefix pointing to Apptainer)
cat > SlurmConfig.yaml <<'EOF'
InterlinkURL: "http://192.168.2.170"
InterlinkPort: "3000"
SidecarURL: "http://0.0.0.0"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/tmp/.interlink/"
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
EOF

echo "✓ Configs created"
ls -la *.yaml
CONFIG
```

**Configuration Details:**

- **SidecarURL**: Must be the machine IP (192.168.2.170), not localhost, to avoid SSRF detection
- **SingularityPrefix**: Points to `/usr/bin/apptainer` (installed via `sudo dnf install apptainer`)
- **SbatchPath/ScanelPath/SqueuePath**: Point to actual SLURM binary locations
- The SLURM plugin uses Apptainer to execute container workloads from Kubernetes pods

## Step 3: Start Interlink API (Machine 1)

```bash
ssh rocky@192.168.2.170 << 'START_API'
cd ~/interlink

# Kill any previous instances
pkill -f interlink-api || true
sleep 2

# Start Interlink API in background
export INTERLINKCONFIGPATH=$(pwd)/interlink-config.yaml
nohup ./interlink-api > interlink-api.log 2>&1 &

sleep 3

echo "=== Interlink API Status ==="
ps aux | grep -E '[i]nterlink-api'
echo ""
echo "=== API Logs ==="
tail -10 interlink-api.log

START_API
```

**Verify API is running:**
```bash
ssh rocky@192.168.2.170 "curl -s -I http://localhost:3000/ | head -3"
```

Expected output:
```
HTTP/1.1 404 Not Found
Content-Type: text/plain; charset=utf-8
...
```

## Step 3.5: Start SLURM Plugin (Machine 1)

**Important:** The SLURM plugin must be started BEFORE the API. Start it like this:

```bash
ssh rocky@192.168.2.170 << 'START_PLUGIN'
cd ~/interlink

# Kill any previous instances
pkill -f slurm-plugin || true
sleep 2

# Start SLURM plugin in background
export SLURMCONFIGPATH=$(pwd)/SlurmConfig.yaml
nohup ./slurm-plugin > slurm-plugin.log 2>&1 &

sleep 3

echo "=== SLURM Plugin Status ==="
ps aux | grep -E '[s]lurm-plugin'
echo ""
echo "=== Plugin Logs ==="
tail -10 slurm-plugin.log

START_PLUGIN
```

**Verify both are running:**
```bash
ssh rocky@192.168.2.170 "ps aux | grep -E '[i]nterlink-api|[s]lurm-plugin' | grep -v grep"
```

Expected output:
```
rocky    77429  0.3  0.4 1810088 33728 ?  Sl  15:31   0:00 ./slurm-plugin
rocky    77436  1.3  0.4 1303460 38648 ?  Sl  15:31   0:00 ./interlink-api
```

## Step 4: Deploy VirtualKubelet via Helm (Machine 2)

**VirtualKubelet is deployed via the official Helm chart from OCI GitHub registry. Interlink configuration is passed via Helm values.**

### Step 4.1: Deploy VirtualKubelet via Helm with Interlink Configuration

```bash
ssh rocky@192.168.2.84 << 'HELM_DEPLOY'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Creating virtual-kubelet namespace ==="
kubectl create namespace virtual-kubelet || true

echo ""
echo "=== Deploying VirtualKubelet via Helm from OCI registry ==="
helm upgrade --install vk oci://ghcr.io/virtual-kubelet/virtual-kubelet \
  --namespace virtual-kubelet \
  --set nodeName=interlink-node \
  --set provider=interlink \
  --set logs.level=info \
  --set interlink.url=http://192.168.2.170 \
  --set interlink.port=3000 \
  --wait

echo "✓ VirtualKubelet deployed via Helm with Interlink configuration"

echo ""
echo "=== Verification ==="
kubectl get pods -n virtual-kubelet -o wide
kubectl get nodes | grep interlink-node

HELM_DEPLOY
```

Expected output:
```
NAME                                    READY   STATUS    RESTARTS   AGE
vk-virtual-kubelet-XXXXXXXXXX-XXXXX    1/1     Running   0          10s
```

## Step 5: Verify VirtualKubelet Helm Deployment (Machine 2)

```bash
ssh rocky@192.168.2.84 << 'VERIFY_VK'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

echo "=== Checking VirtualKubelet Deployment ==="
kubectl get deployment -n virtual-kubelet

echo ""
echo "=== Checking VirtualKubelet Pod ==="
kubectl get pods -n virtual-kubelet -o wide

echo ""
echo "=== VirtualKubelet Logs (check Interlink connection) ==="
kubectl logs -n virtual-kubelet -l app=virtual-kubelet --tail=30 | grep -i interlink

echo ""
echo "=== Checking Virtual Node Registration ==="
kubectl get nodes

echo ""
echo "=== Helm Values (Interlink configuration) ==="
helm get values vk -n virtual-kubelet

echo ""
echo "✓ VirtualKubelet Helm deployment complete with Interlink configuration"
VERIFY_VK
```

Expected output:
```
NAME                    STATUS   ROLES           VERSION
interlink-node          Ready    agent           test
corso-hpc-2.cloudcnaf   Ready    control-plane   v1.31.4+k3s1
```

**Note:** The Helm chart automatically creates all necessary RBAC resources (ServiceAccount, ClusterRole, ClusterRoleBinding) in the virtual-kubelet namespace. Interlink configuration is passed via Helm values.

## Step 6: Verify Connectivity

### Check Interlink API logs

```bash
ssh rocky@192.168.2.170 'tail -20 ~/interlink/interlink-api.log | grep -E "error|warn|listening"'
```

### Check VirtualKubelet logs

```bash
ssh rocky@192.168.2.84 'tail -20 ~/interlink/vk.log | grep -E "error|warn|Pod\|Interlink"'
```

## Summary of Deployed Components

| Component | Machine | Port | Deployment Method | Config |
|-----------|---------|------|-------------------|--------|
| Interlink API | 1 | 3000 | Binary (~/interlink/interlink-api) | interlink-config.yaml |
| SLURM Plugin | 1 | 4000 | Binary (~/interlink/slurm-plugin) | SlurmConfig.yaml |
| VirtualKubelet | 2 | - | Helm Chart (virtual-kubelet/virtual-kubelet) | Helm values |
| k3s | 2 | 6443 | k3s cluster | /etc/rancher/k3s/k3s.yaml |
| SLURM | 1 | - | /opt/slurm/bin/* | - |

## Common Commands

```bash
# Machine 1: Check Interlink API
ssh rocky@192.168.2.170 'ps aux | grep interlink-api'
ssh rocky@192.168.2.170 'tail -f ~/interlink/interlink-api.log'

# Machine 1: Check SLURM Plugin
ssh rocky@192.168.2.170 'ps aux | grep slurm-plugin'
ssh rocky@192.168.2.170 'tail -f ~/interlink/slurm-plugin.log'

# Machine 2: Check VirtualKubelet (via Helm)
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get pods -n virtual-kubelet -o wide
kubectl logs -n virtual-kubelet -l app=virtual-kubelet -f

# Machine 2: List nodes
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes -o wide

# Machine 2: Check Helm deployment
helm list -n virtual-kubelet
helm status vk -n virtual-kubelet
```

## Troubleshooting

### Interlink API won't start

- Check if port 3000 is already in use: `netstat -tlnp | grep 3000`
- Verify config file path: `echo $INTERLINKCONFIGPATH`
- Check API logs: `tail -50 ~/interlink/interlink-api.log`

### SLURM Plugin fails to start

- Ensure it starts BEFORE the API: `ps aux | grep -E '[s]lurm-plugin|[i]nterlink-api'`
- Check plugin logs: `tail -50 ~/interlink/slurm-plugin.log`
- Verify Apptainer is installed: `apptainer --version`

### VirtualKubelet Helm pod not running

- Check Helm deployment: `kubectl get deployment -n virtual-kubelet`
- Check pod status: `kubectl get pods -n virtual-kubelet`
- Check pod logs: `kubectl logs -n virtual-kubelet -l app=virtual-kubelet --tail=50`
- Verify Helm values: `helm values vk -n virtual-kubelet`

### Virtual node not showing as Ready

- Verify VirtualKubelet pod is running: `kubectl get pods -n virtual-kubelet`
- Check connectivity to Interlink API: `curl http://192.168.2.170:3000/`
- Review VirtualKubelet logs: `kubectl logs -n virtual-kubelet -l app=virtual-kubelet`
- Check ConfigMap: `kubectl get configmap vk-config -n virtual-kubelet`

### Pod not scheduling to interlink-node

- Confirm node exists: `kubectl get nodes`
- Check node status: `kubectl describe node interlink-node`
- Verify RBAC: `kubectl get clusterrole,clusterrolebinding | grep virtual-kubelet`
- Review VirtualKubelet logs for pod watch events: `kubectl logs -n virtual-kubelet -l app=virtual-kubelet | grep -i pod`

### Helm deployment fails

- Check Helm chart availability: `helm search repo virtual-kubelet`
- Verify namespace exists: `kubectl get ns virtual-kubelet`
- Check Helm release status: `helm status vk -n virtual-kubelet`
- View Helm install output: `helm get values vk -n virtual-kubelet`

---

Next: [Phase 4: Test Pod Offload](phase4-test-offload.md)

