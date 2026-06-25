# Phase 3: Interlink Setup - Full Implementation

Deploy real Interlink binaries to bridge SLURM (Machine 1) and k3s (Machine 2).

## Architecture

```
Machine 1 (192.168.2.170)              Machine 2 (192.168.2.84)
─────────────────────────              ──────────────────────
Interlink API (port 3000)              VirtualKubelet Binary
└─ REST/HTTP endpoint                  └─ Connects to Interlink API
SLURM (local)                          k3s Kubernetes
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

### Machine 2 (k3s + VirtualKubelet)

```bash
ssh rocky@192.168.2.84 << 'M2SETUP'
VER="0.6.1-patch1"
BASE="https://github.com/interlink-hq/interLink/releases/download/$VER"

mkdir -p ~/interlink
cd ~/interlink

# Download VirtualKubelet binary
curl -sL "$BASE/virtual-kubelet_Linux_x86_64" -o virtual-kubelet && chmod +x virtual-kubelet

# Download SSH tunnel binary
curl -sL "$BASE/ssh-tunnel_Linux_x86_64" -o ssh-tunnel && chmod +x ssh-tunnel

echo "✓ Binaries downloaded"
ls -lh virtual-kubelet ssh-tunnel
M2SETUP
```

## Step 2: Configure Interlink API (Machine 1)

Create configuration file:

```bash
ssh rocky@192.168.2.170 << 'CONFIG'
cd ~/interlink

cat > interlink-config.yaml <<'EOF'
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://127.0.0.1"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/tmp/.interlink-api"
EOF

cat > plugin-config.yaml <<'EOF'
InterlinkURL: "http://127.0.0.1"
InterlinkPort: "3000"
SidecarURL: "http://0.0.0.0"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/tmp/.interlink/"
ExportPodData: true
SbatchPath: "/opt/slurm/bin/sbatch"
ScancelPath: "/opt/slurm/bin/scancel"
SqueuePath: "/opt/slurm/bin/squeue"
CommandPrefix: ""
SingularityPrefix: ""
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

## Step 4: Configure VirtualKubelet (Machine 2)

### Set up RBAC

```bash
ssh rocky@192.168.2.84 << 'RBAC'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

/usr/local/bin/k3s kubectl apply -f - <<'YAML'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: virtual-kubelet
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: virtual-kubelet
rules:
- apiGroups: ["coordination.k8s.io"]
  resources: ["leases"]
  verbs: ["update", "create", "get", "list", "watch", "patch"]
- apiGroups: [""]
  resources: ["configmaps", "secrets", "services", "serviceaccounts", "namespaces"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["delete", "get", "list", "watch", "patch"]
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["create", "get"]
- apiGroups: [""]
  resources: ["nodes/status"]
  verbs: ["update", "patch"]
- apiGroups: [""]
  resources: ["pods/status"]
  verbs: ["update", "patch"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: virtual-kubelet
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: virtual-kubelet
subjects:
- kind: ServiceAccount
  name: virtual-kubelet
  namespace: default
YAML

echo "✓ RBAC configured"
RBAC
```

### Create kubeconfig for VirtualKubelet

```bash
ssh rocky@192.168.2.84 << 'KUBECONFIG'
cd ~/interlink

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Get k3s connection details
VK_TOKEN=$(/usr/local/bin/k3s kubectl create token virtual-kubelet -n default --duration=87600h 2>/dev/null | head -c 100)
K8S_SERVER=$(/usr/local/bin/k3s kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
K8S_CA_DATA=$(/usr/local/bin/k3s kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

cat > vk-kubeconfig.yaml <<KUBECFG
apiVersion: v1
kind: Config
clusters:
- name: default-cluster
  cluster:
    server: ${K8S_SERVER}
    certificate-authority-data: ${K8S_CA_DATA}
contexts:
- name: default-context
  context:
    cluster: default-cluster
    user: virtual-kubelet
    namespace: default
current-context: default-context
users:
- name: virtual-kubelet
  user:
    token: ${VK_TOKEN}
KUBECFG

chmod 600 vk-kubeconfig.yaml
echo "✓ kubeconfig created"
cat vk-kubeconfig.yaml | head -5
KUBECONFIG
```

### Create VirtualKubelet config

```bash
ssh rocky@192.168.2.84 << 'VKCONFIG'
cd ~/interlink

cat > vk-config.yaml <<'EOF'
InterlinkURL: "http://192.168.2.170"
InterlinkPort: "3000"
VerboseLogging: true
ErrorsOnlyLogging: false
ServiceAccount: "virtual-kubelet"
Namespace: default
Resources:
  CPU: "100"
  Memory: "128Gi"
  Pods: "100"
HTTP:
  Insecure: true
KubeletHTTP:
  Insecure: true
EOF

echo "✓ VK config created"
cat vk-config.yaml
VKCONFIG
```

## Step 5: Start VirtualKubelet (Machine 2)

```bash
ssh rocky@192.168.2.84 << 'START_VK'
cd ~/interlink

# Kill any previous instance
pkill -f virtual-kubelet || true
sleep 2

# Start VirtualKubelet in background
nohup ./virtual-kubelet \
  -configpath=./vk-config.yaml \
  -nodename=interlink-node \
  > vk.log 2>&1 &

sleep 3

echo "=== VirtualKubelet Status ==="
ps aux | grep -E '[v]irtual-kubelet'
echo ""
echo "=== VK Logs ==="
tail -15 vk.log

START_VK
```

### Verify VirtualKubelet registered

```bash
ssh rocky@192.168.2.84 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml; /usr/local/bin/k3s kubectl get nodes -o wide'
```

Expected output:
```
NAME                    STATUS   ROLES           VERSION
interlink-node          NotReady agent           test
corso-hpc-2.cloudcnaf   Ready    control-plane   v1.31.4+k3s1
```

The `interlink-node` will show `NotReady` initially while connecting to the API. It should transition to `Ready` once connectivity is established.

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

| Component | Machine | Port | Binary | Config |
|-----------|---------|------|--------|--------|
| Interlink API | 1 | 3000 | ~/interlink/interlink-api | interlink-config.yaml |
| VirtualKubelet | 2 | - | ~/interlink/virtual-kubelet | vk-config.yaml |
| k3s | 2 | 6443 | /usr/local/bin/k3s | /etc/rancher/k3s/k3s.yaml |
| SLURM | 1 | - | /opt/slurm/bin/* | - |

## Common Commands

```bash
# Machine 1: Check Interlink API
ssh rocky@192.168.2.170 'ps aux | grep interlink-api'
ssh rocky@192.168.2.170 'tail -f ~/interlink/interlink-api.log'

# Machine 2: Check VirtualKubelet
ssh rocky@192.168.2.84 'ps aux | grep virtual-kubelet'
ssh rocky@192.168.2.84 'tail -f ~/interlink/vk.log'

# Machine 2: List nodes
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
/usr/local/bin/k3s kubectl get nodes -o wide

# Machine 2: Check VirtualKubelet logs
ssh rocky@192.168.2.84 'grep -E "error|Pod|Interlink" ~/interlink/vk.log | tail -20'
```

## Troubleshooting

### Interlink API won't start

- Check if port 3000 is already in use: `netstat -tlnp | grep 3000`
- Verify config file path: `echo $INTERLINKCONFIGPATH`
- Check API logs: `tail -50 interlink-api.log`

### VirtualKubelet not showing as Ready

- Verify it's running: `ps aux | grep virtual-kubelet`
- Check connectivity to Interlink API: `curl http://192.168.2.170:3000/`
- Review logs: `tail -50 vk.log`

### Pod not scheduling to interlink-node

- Confirm node exists: `/usr/local/bin/k3s kubectl get nodes`
- Check RBAC: `/usr/local/bin/k3s kubectl get clusterrole,clusterrolebinding`
- Verify kubeconfig token is valid
- Review VirtualKubelet logs for pod watch events

---

Next: [Phase 4: Test Pod Offload](phase4-test-offload.md)

