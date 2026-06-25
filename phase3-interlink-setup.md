# Phase 3: Deploy Interlink - Binary Implementation

Deploy real Interlink components using pre-built binaries (no Docker needed).

This phase runs on **Machine 2** (k3s cluster) and **Machine 1** (SLURM).

## Overview

We'll deploy:
1. **SLURM Plugin** - Submits jobs to SLURM (binary daemon on Machine 1, port 4000)
2. **Interlink API** - Translates Kubernetes pods to SLURM jobs (binary daemon on Machine 1, port 3000)
3. **VirtualKubelet** - Registers as Kubernetes node (binary daemon on Machine 2)

The flow: `Pod on k3s` → `VirtualKubelet` → `Interlink API (gRPC)` → `SLURM Plugin` → `SLURM Job`

## Step 1: Setup on Machine 2 (k3s)

```bash
ssh rocky@192.168.2.84
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create working directory
mkdir -p ~/interlink
cd ~/interlink

# Download latest Interlink release
curl -L https://github.com/interlink-hq/interlink/releases/download/v0.4.0/interlink-v0.4.0-linux-amd64 -o interlink
chmod +x interlink

# Download VirtualKubelet
curl -L https://github.com/interlink-hq/interlink/releases/download/v0.4.0/virtual-kubelet-v0.4.0-linux-amd64 -o virtual-kubelet
chmod +x virtual-kubelet
```

## Step 2: Create Kubernetes ServiceAccount and RBAC

Still on Machine 2:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

kubectl apply -f - <<'YAML'
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
```

## Step 3: Create VirtualKubelet kubeconfig

On Machine 2:

```bash
cd ~/interlink

# Create token and kubeconfig
VK_TOKEN=$(kubectl create token virtual-kubelet -n default --duration=24h)
K8S_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
K8S_CA_DATA=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

cat > vk-kubeconfig.yaml <<EOF
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
EOF

chmod 600 vk-kubeconfig.yaml
```

## Step 4: Create VirtualKubelet config

On Machine 2:

```bash
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
```

## Step 5: Deploy SLURM Plugin on Machine 1

On **Machine 1** (192.168.2.170):

```bash
ssh rocky@192.168.2.170
mkdir -p ~/interlink
cd ~/interlink

# Download SLURM plugin release
curl -L https://github.com/interlink-hq/interlink-slurm-plugin/releases/download/v0.4.0/interlink-slurm-plugin-v0.4.0-linux-amd64 -o slurm-plugin
chmod +x slurm-plugin

# Create plugin config
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

# Start SLURM plugin in background
nohup ./slurm-plugin > plugin.log 2>&1 &
echo $! > plugin.pid

sleep 2
echo "SLURM plugin started (PID: $(cat plugin.pid))"
```

## Step 6: Deploy Interlink API on Machine 1

Still on Machine 1:

```bash
# Download Interlink API binary
curl -L https://github.com/interlink-hq/interlink/releases/download/v0.4.0/interlink-v0.4.0-linux-amd64 -o interlink
chmod +x interlink

# Create API config
cat > interlink-config.yaml <<'EOF'
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://127.0.0.1"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/tmp/.interlink-api"
EOF

# Start Interlink API in background
nohup ./interlink > api.log 2>&1 &
echo $! > api.pid

sleep 2
echo "Interlink API started (PID: $(cat api.pid))"

# Verify connectivity
curl -X POST http://localhost:3000/pinglink
```

## Step 7: Start VirtualKubelet on Machine 2

Back on **Machine 2**:

```bash
cd ~/interlink

# Start VirtualKubelet
NODENAME=virtual-kubelet \
  KUBELET_PORT=10251 \
  KUBELET_URL=0.0.0.0 \
  POD_IP=$(hostname -I | awk '{print $1}') \
  CONFIGPATH=$(pwd)/vk-config.yaml \
  KUBECONFIG=$(pwd)/vk-kubeconfig.yaml \
  nohup ./virtual-kubelet > vk.log 2>&1 &

VK_PID=$!
echo $VK_PID > vk.pid
echo "VirtualKubelet started (PID: $VK_PID)"

sleep 5
```

## Step 8: Verify Virtual Node Registration

On Machine 2:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Wait for node to register
for i in {1..30}; do
  if kubectl get node virtual-kubelet 2>/dev/null | grep -q Ready; then
    echo "✓ virtual-kubelet node is Ready"
    break
  fi
  echo "Waiting for node... ($i/30)"
  sleep 3
done

# Check node status
kubectl get nodes -o wide
kubectl describe node virtual-kubelet

# Check logs if needed
tail -50 ~/interlink/vk.log
```

---

Next: [Phase 4: Test Pod Offload](phase4-test-offload.md)

