# Phase 3: Deploy Interlink - Real Implementation

Deploy real Interlink components based on the official e2e workflow.

This phase runs on **Machine 2** (k3s cluster) and connects to **Machine 1** (SLURM).

## Overview

We'll deploy:
1. **Interlink API** - Translates Kubernetes pods to SLURM jobs (Docker container on Machine 1)
2. **SLURM Plugin** - Submits jobs to SLURM (Docker container on Machine 1)
3. **VirtualKubelet** - Registers as Kubernetes node (runs on Machine 2)

The flow: `Pod on k3s` → `VirtualKubelet` → `Interlink API` → `SLURM Plugin` → `SLURM Job`

## Setup on Machine 2

```bash
ssh rocky@192.168.2.84
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Create working directory
mkdir -p ~/interlink-setup
cd ~/interlink-setup

# Clone Interlink source
git clone https://github.com/interlink-hq/interlink.git
cd interlink

# Initialize submodules (includes SLURM plugin)
git submodule update --init plugins/slurm
```

## Build Docker Images

Still on Machine 2:

```bash
# Build Interlink API image
docker build -f docker/Dockerfile.interlink \
  -t interlink:latest .

# Build SLURM plugin image
docker build -f plugins/slurm/docker/Dockerfile \
  -t interlink-slurm-plugin:latest plugins/slurm
```

## Create Docker Network (connects to Machine 1)

```bash
# Create network for container communication
docker network create interlink-net
```

## Deploy SLURM Plugin Container on Machine 1

On **Machine 1** (192.168.2.170):

```bash
ssh rocky@192.168.2.170

# Copy plugin config to Machine 1
cat > /tmp/plugin-config.yaml <<'EOF'
InterlinkURL: "http://interlink-api:3000"
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

# Install Docker on Machine 1 if needed
sudo dnf install -y docker
sudo systemctl start docker

# Start SLURM plugin container
docker run -d \
  --name interlink-plugin \
  --network interlink-net \
  -p 4000:4000 \
  --privileged \
  -v /tmp/plugin-config.yaml:/etc/interlink/InterLinkConfig.yaml:ro \
  -e SLURMCONFIGPATH=/etc/interlink/InterLinkConfig.yaml \
  -e SHARED_FS=true \
  interlink-slurm-plugin:latest

docker logs interlink-plugin
```

## Deploy Interlink API Container

Still on **Machine 1**:

```bash
# Create API config
cat > /tmp/interlink-config.yaml <<'EOF'
InterlinkAddress: "http://0.0.0.0"
InterlinkPort: "3000"
SidecarURL: "http://interlink-plugin:4000"
SidecarPort: "4000"
VerboseLogging: true
ErrorsOnlyLogging: false
DataRootFolder: "/tmp/.interlink-api"
EOF

# Start Interlink API container
docker run -d \
  --name interlink-api \
  --network interlink-net \
  -p 3000:3000 \
  -v /tmp/interlink-config.yaml:/etc/interlink/InterLinkConfig.yaml:ro \
  -e INTERLINKCONFIGPATH=/etc/interlink/InterLinkConfig.yaml \
  interlink:latest

# Verify it's running
docker logs interlink-api
curl -X POST http://localhost:3000/pinglink
```

## Setup VirtualKubelet on Machine 2

Back on **Machine 2**:

```bash
cd ~/interlink-setup/interlink

# Create service account and RBAC
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
YAML

# Build VirtualKubelet binary
CGO_ENABLED=0 go build -o vk ./cmd/virtual-kubelet

# Create kubeconfig for VirtualKubelet
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

# Create VirtualKubelet config
cat > vk-config.yaml <<EOF
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

# Start VirtualKubelet
NODENAME=virtual-kubelet \
  KUBELET_PORT=10251 \
  KUBELET_URL=0.0.0.0 \
  POD_IP=$(hostname -I | awk '{print $1}') \
  CONFIGPATH=vk-config.yaml \
  KUBECONFIG=vk-kubeconfig.yaml \
  nohup ./vk > vk.log 2>&1 &

# Verify it registered
sleep 10
kubectl get nodes
kubectl get node virtual-kubelet -o wide
```

---

Next: [Phase 4: Test Pod Offload](phase4-test-offload.md)
