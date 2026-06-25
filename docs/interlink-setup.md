# Interlink Setup: Bridging SLURM and Kubernetes

This guide covers the installation and configuration of Interlink to bridge the SLURM cluster on Machine 1 with the k3s Kubernetes cluster on Machine 2.

## Overview

Interlink acts as a bridge between Kubernetes and traditional HPC workload managers. It consists of:

1. **Interlink Server** - Runs on Machine 1 (SLURM side)
   - Listens for requests from the VirtualKubelet
   - Translates pod specs to SLURM jobs
   - Manages job lifecycle

2. **VirtualKubelet** - Runs on Machine 2 (k3s side)
   - Appears as a node to Kubernetes
   - Schedules pods to Interlink Server
   - Reports pod status back to Kubernetes

3. **Network Communication** - Between the two machines
   - gRPC protocol (secure, efficient)
   - TLS certificates for security

## Prerequisites

Before starting this section, ensure you have:

- ✅ Machine 1 (192.168.2.170) with SLURM running (see [Machine 1 - SLURM Setup](machine1-slurm.md))
- ✅ Machine 2 (192.168.2.84) with k3s running (see [Machine 2 - k3s Setup](machine2-k3s.md))
- ✅ Network connectivity verified between machines
- ✅ SSH access to both machines as user `rocky`

## Architecture Diagram

```
┌─────────────────────────────────┐
│  Machine 2: k3s (192.168.2.84)  │
│  ┌──────────────────────────────┤
│  │  Kubernetes Cluster          │
│  │  ┌────────────────────────┐   │
│  │  │  kube-apiserver        │   │
│  │  │  scheduler             │   │
│  │  └────────────────────────┘   │
│  │                              │
│  │  ┌────────────────────────┐   │
│  │  │  VirtualKubelet        │◄──┼─── gRPC
│  │  │  (Interlink Client)    │   │
│  │  └────────────────────────┘   │
│  └──────────────────────────────┤
└─────────────────────────────────┘
            ▲
            │ gRPC
            │
┌───────────▼──────────────────────┐
│  Machine 1: SLURM (192.168.2.170)│
│  ┌──────────────────────────────┤
│  │  ┌────────────────────────┐   │
│  │  │  Interlink Server      │   │
│  │  │  (Job Translator)      │   │
│  │  └────────────────────────┘   │
│  │                              │
│  │  ┌────────────────────────┐   │
│  │  │  slurmctld             │   │
│  │  │  slurmd (compute)      │   │
│  │  └────────────────────────┘   │
│  └──────────────────────────────┤
└────────────────────────────────────┘
```

## Step 1: Install Interlink on Machine 1 (SLURM Side)

### 1.1 Prerequisites on Machine 1

```bash
# SSH to Machine 1
ssh rocky@192.168.2.170

# Install Go (if not already installed)
# Interlink is written in Go
cd ~
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz

# Add Go to PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Verify
go version
```

### 1.2 Clone Interlink Repository

```bash
# Clone Interlink
cd ~
git clone https://github.com/interlink-project/interlink.git
cd interlink

# Check available versions/branches
git tag | head -20

# Checkout a stable version (example)
git checkout v0.5.0  # Or latest stable
```

### 1.3 Build Interlink Server

```bash
# Navigate to server directory
cd ~/interlink

# Build the Interlink server
make build

# Or build specific component
go build -o interlink-server ./cmd/interlink-server

# Verify build
./interlink-server --version
```

### 1.4 Create Interlink Configuration on Machine 1

```bash
# Create config directory
mkdir -p ~/.interlink/config

# Create Interlink server configuration
cat > ~/.interlink/config/interlink-server.yaml << 'EOF'
# Interlink Server Configuration
# Running on SLURM Machine (192.168.2.170)

# Listen address for VirtualKubelet connections
listenPort: 3000
listenAddress: 0.0.0.0

# TLS Configuration (optional but recommended)
tls:
  enabled: true
  certPath: /home/rocky/.interlink/certs/server.crt
  keyPath: /home/rocky/.interlink/certs/server.key

# SLURM Configuration
slurm:
  # Path to SLURM commands
  sbatchPath: /usr/bin/sbatch
  scancelPath: /usr/bin/scancel
  scontrolPath: /usr/sbin/scontrol
  squeuePath: /usr/bin/squeue
  
  # Default SLURM partition for pods
  defaultPartition: default
  
  # Time to live for pod jobs (in minutes)
  ttl: 1440  # 24 hours
  
  # Container image to use for pod jobs
  containerImage: docker.io/library/busybox:latest

# Logging
logging:
  level: info
  format: json

EOF

# Copy if needed
mkdir -p /opt/interlink/config
sudo cp ~/.interlink/config/interlink-server.yaml /opt/interlink/config/
```

### 1.5 Create TLS Certificates (if using TLS)

```bash
# Create certificates directory
mkdir -p ~/.interlink/certs

# Generate private key
openssl genrsa -out ~/.interlink/certs/server.key 2048

# Create certificate signing request
openssl req -new -key ~/.interlink/certs/server.key \
  -subj "/C=IT/ST=Milan/L=Milan/O=HPC/CN=slurm-machine" \
  -out ~/.interlink/certs/server.csr

# Create self-signed certificate (valid for 365 days)
openssl x509 -req -days 365 -in ~/.interlink/certs/server.csr \
  -signkey ~/.interlink/certs/server.key \
  -out ~/.interlink/certs/server.crt

# Verify certificate
openssl x509 -in ~/.interlink/certs/server.crt -text -noout

# Also generate client certificate for VirtualKubelet
openssl genrsa -out ~/.interlink/certs/client.key 2048

openssl req -new -key ~/.interlink/certs/client.key \
  -subj "/C=IT/ST=Milan/L=Milan/O=HPC/CN=virtualkubelet" \
  -out ~/.interlink/certs/client.csr

openssl x509 -req -days 365 -in ~/.interlink/certs/client.csr \
  -signkey ~/.interlink/certs/server.key \
  -out ~/.interlink/certs/client.crt

# Set permissions
chmod 600 ~/.interlink/certs/*
```

### 1.6 Create Systemd Service for Interlink Server

```bash
# Create service file
sudo bash -c 'cat > /etc/systemd/system/interlink-server.service << EOF
[Unit]
Description=Interlink Server (SLURM Bridge)
After=network.target slurmctld.service

[Service]
Type=simple
User=rocky
WorkingDirectory=/home/rocky/interlink
ExecStart=/home/rocky/interlink/interlink-server --config /home/rocky/.interlink/config/interlink-server.yaml
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=interlink-server

[Install]
WantedBy=multi-user.target
EOF'

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable interlink-server
sudo systemctl start interlink-server

# Verify it's running
sudo systemctl status interlink-server

# Check logs
journalctl -u interlink-server -n 20 -f
```

## Step 2: Install VirtualKubelet on Machine 2 (k3s Side)

### 2.1 Prerequisites on Machine 2

```bash
# SSH to Machine 2
ssh rocky@192.168.2.84

# Install Go (if not already installed)
cd ~
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz

# Add Go to PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Verify
go version

# Set up kubeconfig
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

### 2.2 Build VirtualKubelet

```bash
# Clone or download VirtualKubelet
cd ~
git clone https://github.com/interlink-project/interlink.git
cd interlink

# Build VirtualKubelet component
go build -o interlink-vk ./cmd/interlink-vk

# Verify
./interlink-vk --version
```

### 2.3 Create VirtualKubelet Configuration on Machine 2

```bash
# Create config directory
mkdir -p ~/.interlink/config

# Create VirtualKubelet configuration
cat > ~/.interlink/config/virtualkubelet.yaml << 'EOF'
# VirtualKubelet Configuration
# Running on k3s Machine (192.168.2.84)

# Node configuration
nodeName: slurm-worker
nodeNamespace: kube-system

# Interlink Server endpoint
interlink:
  # Address of Interlink Server on Machine 1
  serverAddress: 192.168.2.170:3000
  
  # TLS configuration (if enabled on server)
  tls:
    enabled: true
    certPath: /home/rocky/.interlink/certs/client.crt
    keyPath: /home/rocky/.interlink/certs/client.key
    caPath: /home/rocky/.interlink/certs/server.crt

# Kubelet configuration
kubelet:
  # Port for kubelet
  port: 10250
  
  # Operational system type
  operatingSystem: linux

# Pod configuration
pod:
  # Default namespace for scheduled pods
  namespace: default
  
  # Pod overhead (resource used by infrastructure)
  overhead:
    cpu: 10m
    memory: 64Mi

# Resource configuration
resources:
  # CPU capacity
  cpuCapacity: 10
  # Memory capacity (in MB)
  memoryCapacity: 10240
  # GPU capacity (if available)
  gpuCapacity: 0

# Logging
logging:
  level: info
  format: json

EOF

# Copy for privileged access
mkdir -p /opt/interlink/config
sudo cp ~/.interlink/config/virtualkubelet.yaml /opt/interlink/config/
```

### 2.4 Copy Client Certificates to Machine 2

If using TLS, copy the certificates from Machine 1:

```bash
# From Machine 2
# Create certs directory
mkdir -p ~/.interlink/certs

# Copy certificates from Machine 1
scp rocky@192.168.2.170:~/.interlink/certs/client.crt ~/.interlink/certs/
scp rocky@192.168.2.170:~/.interlink/certs/client.key ~/.interlink/certs/
scp rocky@192.168.2.170:~/.interlink/certs/server.crt ~/.interlink/certs/

# Set permissions
chmod 600 ~/.interlink/certs/*

# Verify
ls -la ~/.interlink/certs/
```

### 2.5 Create Kubernetes Deployment for VirtualKubelet

Create a Kubernetes deployment to run VirtualKubelet:

```bash
# Create namespace for Interlink
kubectl create namespace interlink

# Create ServiceAccount
kubectl create serviceaccount virtualkubelet -n interlink

# Create ClusterRoleBinding
kubectl create clusterrolebinding virtualkubelet \
  --clusterrole=cluster-admin \
  --serviceaccount=interlink:virtualkubelet

# Create ConfigMap with configuration
kubectl create configmap interlink-config \
  --from-file=/home/rocky/.interlink/config/virtualkubelet.yaml \
  -n interlink

# Create Secret with TLS certificates (if using TLS)
kubectl create secret generic interlink-certs \
  --from-file=/home/rocky/.interlink/certs/ \
  -n interlink
```

### 2.6 Deploy VirtualKubelet as a Pod

```bash
# Create VirtualKubelet deployment manifest
cat > /tmp/virtualkubelet-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: virtualkubelet
  namespace: interlink
  labels:
    app: virtualkubelet
spec:
  replicas: 1
  selector:
    matchLabels:
      app: virtualkubelet
  template:
    metadata:
      labels:
        app: virtualkubelet
    spec:
      serviceAccountName: virtualkubelet
      containers:
      - name: virtualkubelet
        image: busybox  # Placeholder; use actual VirtualKubelet image
        imagePullPolicy: IfNotPresent
        command:
          - /bin/sh
          - -c
          - |
            # Start VirtualKubelet
            /home/rocky/interlink/interlink-vk \
              --kubeconfig=/etc/kubernetes/kubelet.conf \
              --config=/etc/interlink/virtualkubelet.yaml
        volumeMounts:
        - name: kubeconfig
          mountPath: /etc/kubernetes
        - name: config
          mountPath: /etc/interlink
        - name: certs
          mountPath: /etc/interlink/certs
      volumes:
      - name: kubeconfig
        hostPath:
          path: /etc/rancher/k3s
          type: Directory
      - name: config
        configMap:
          name: interlink-config
      - name: certs
        secret:
          secretName: interlink-certs
EOF

# Apply the deployment
kubectl apply -f /tmp/virtualkubelet-deployment.yaml

# Wait for pod to start
sleep 10

# Check deployment status
kubectl get deployment -n interlink
kubectl get pods -n interlink

# Check logs
kubectl logs -n interlink -l app=virtualkubelet -f
```

## Step 3: Configure Network Communication

### 3.1 Verify Network Connectivity

Test connectivity between machines:

```bash
# From Machine 2 (k3s), test connection to Machine 1 (SLURM)
ssh rocky@192.168.2.84

# Test port 3000 (Interlink Server default)
telnet 192.168.2.170 3000

# Or use netcat
nc -zv 192.168.2.170 3000

# From Machine 1, test reverse
ssh rocky@192.168.2.170
nc -zv 192.168.2.84 6443  # k3s API
```

### 3.2 Check Firewall Rules

```bash
# On Machine 1 (SLURM)
sudo firewall-cmd --list-ports

# Add Interlink Server port if needed
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --reload

# On Machine 2 (k3s)
sudo firewall-cmd --list-ports

# Add Kubelet port if needed
sudo firewall-cmd --permanent --add-port=10250/tcp
sudo firewall-cmd --reload
```

## Step 4: Testing Interlink Setup

### 4.1 Verify Components Are Running

```bash
# On Machine 1, check Interlink Server
ssh rocky@192.168.2.170
sudo systemctl status interlink-server
journalctl -u interlink-server -n 10

# On Machine 2, check VirtualKubelet pod
ssh rocky@192.168.2.84
kubectl get pods -n interlink
kubectl logs -n interlink -l app=virtualkubelet
```

### 4.2 Verify VirtualKubelet as Kubernetes Node

```bash
# On Machine 2, check if SLURM node appears in Kubernetes
kubectl get nodes

# You should see:
# - k3s-machine (your actual k3s node)
# - slurm-worker (virtual node created by VirtualKubelet)

# Get details on the virtual node
kubectl describe node slurm-worker
```

### 4.3 Submit a Test Pod to SLURM via Kubernetes

```bash
# Create a test pod manifest
cat > /tmp/interlink-test-pod.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: slurm-test-pod
  namespace: default
spec:
  nodeSelector:
    kubernetes.io/hostname: slurm-worker
  containers:
  - name: test-container
    image: busybox:latest
    command: ["sh", "-c"]
    args: ["echo 'Running on SLURM!'; hostname; date; sleep 30"]
  restartPolicy: Never
EOF

# Submit the pod
kubectl apply -f /tmp/interlink-test-pod.yaml

# Check pod status
sleep 5
kubectl get pods

# Get pod details
kubectl describe pod slurm-test-pod

# Check logs
kubectl logs slurm-test-pod
```

### 4.4 Verify Job in SLURM

```bash
# From Machine 1, check if job appears in SLURM
ssh rocky@192.168.2.170

# List jobs
squeue

# Get job details
scontrol show job <job-id>

# Check job output
sacct -j <job-id> --format=JobID,JobName,State,ExitCode
```

## Verification Checklist

Verify the following:

- [ ] Interlink Server running on Machine 1: `sudo systemctl status interlink-server`
- [ ] VirtualKubelet pod running on Machine 2: `kubectl get pods -n interlink`
- [ ] VirtualKubelet node visible: `kubectl get nodes` shows `slurm-worker`
- [ ] Network connectivity: `telnet 192.168.2.170 3000` works
- [ ] Test pod created successfully: `kubectl get pods` shows pod
- [ ] Test pod appears as SLURM job: `squeue` shows job
- [ ] Pod completion tracked in k3s: `kubectl get pods` shows completion status

## Troubleshooting Interlink Issues

### Interlink Server won't start

```bash
# Check logs
journalctl -u interlink-server -n 50

# Common issues:
# - Port 3000 already in use: sudo ss -tlnp | grep 3000
# - SLURM not running: sudo systemctl status slurmctld
# - Configuration file issues: Check YAML syntax

# Restart
sudo systemctl restart interlink-server
```

### VirtualKubelet pod not running

```bash
# Check pod status
kubectl describe pod -n interlink virtualkubelet-*

# Check logs
kubectl logs -n interlink virtualkubelet-*

# Common issues:
# - Invalid config: Check ConfigMap
# - Missing certificates: Check Secret
# - Kubeconfig not mounted properly: Check volumeMounts

# Redeploy
kubectl delete deployment -n interlink virtualkubelet
kubectl apply -f /tmp/virtualkubelet-deployment.yaml
```

### Pods not appearing as SLURM jobs

```bash
# Check Interlink logs on Machine 1
journalctl -u interlink-server -f

# Check VirtualKubelet logs on Machine 2
kubectl logs -n interlink -l app=virtualkubelet -f

# Verify network connectivity
ping -c 5 192.168.2.170

# Check Interlink Server listening
sudo ss -tlnp | grep 3000
```

## Next Steps

Once Interlink is working:

1. Go to [Testing Procedures](testing-procedures.md) for comprehensive end-to-end tests
2. Use [Troubleshooting Guide](troubleshooting.md) for any issues
3. Review [Common Tasks](common-tasks.md) for reference

---

**Interlink configured?** Test it thoroughly! ➡️
