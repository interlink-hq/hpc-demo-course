# Machine 2: k3s Setup - REALISTIC APPROACH

This guide covers practical k3s setup on Machine 2 (192.168.2.84) based on real-world testing.

## Overview

k3s is a lightweight Kubernetes that works well on these machines. This guide focuses on what actually works.

## Prerequisites

Ensure you have completed [Prerequisites and Environment Setup](prerequisites.md).

Key assumptions:
- Machine 2 IP: 192.168.2.84
- Machine 2 Hostname: k3s-machine
- User: rocky
- OS: Rocky Linux 9

## Step 1: Verify System Setup

```bash
ssh rocky@192.168.2.84

# Verify hostname
hostname
# Expected: k3s-machine

# Verify network
ping -c 2 192.168.2.170
# Expected: 0% packet loss

# Check internet access
ping -c 1 8.8.8.8
# Expected: Success (needed for k3s download)
```

## Step 2: Install k3s

k3s provides an automated installation script:

```bash
ssh rocky@192.168.2.84

# Download and run k3s installer
curl -sfL https://get.k3s.io | sh -

# Wait for installation to complete (1-2 minutes)
echo "Waiting for k3s to start..."
sleep 30

# Verify k3s service is running
sudo systemctl status k3s

# Expected: k3s service should be active (running)
```

## Step 3: Set Up kubectl Access

**Important**: k3s stores kubeconfig with restricted permissions. Follow this carefully:

```bash
ssh rocky@192.168.2.84

# Option A: Use k3s kubectl (no config needed)
sudo /usr/local/bin/k3s kubectl get nodes

# Expected output shows your machine as Ready

# Option B: Copy kubeconfig for easier access
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

# Set environment variable
export KUBECONFIG=~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc

# Verify it works
kubectl get nodes
# Expected: Shows your k3s-machine node in Ready state
```

## Step 4: Verify Kubernetes Installation

```bash
ssh rocky@192.168.2.84

# Check cluster info
kubectl cluster-info

# Expected: Outputs Kubernetes API server and CoreDNS addresses

# Check all nodes
kubectl get nodes -o wide

# Expected: One node (your machine) in Ready state with k3s version

# Check system namespaces and pods
kubectl get ns

# Expected: Shows default, kube-system, kube-node-lease, kube-public

# Check system pods
kubectl get pods -A

# Expected: Shows coredns, local-path-provisioner, metrics-server, and traefik pods
```

## Step 5: Verify Networking

```bash
ssh rocky@192.168.2.84

# Deploy a test pod
kubectl run test-pod --image=busybox --restart=Never -- sleep 300

# Wait for pod to start
sleep 5

# Check pod status
kubectl get pods

# Expected: test-pod should be Running

# Test pod networking
kubectl exec test-pod -- nslookup kubernetes.default

# Expected: Should resolve successfully

# Check pod IP
POD_IP=$(kubectl get pod test-pod -o jsonpath='{.status.podIP}')
echo "Pod IP: $POD_IP"

# Clean up
kubectl delete pod test-pod
```

## Step 6: Create Namespace for Interlink

```bash
ssh rocky@192.168.2.84

# Create interlink namespace
kubectl create namespace interlink

# Create ServiceAccount for VirtualKubelet
kubectl create serviceaccount virtualkubelet -n interlink

# Give it admin permissions (for demo - not for production)
kubectl create clusterrolebinding virtualkubelet \
  --clusterrole=cluster-admin \
  --serviceaccount=interlink:virtualkubelet

# Verify
kubectl get sa -n interlink
# Expected: Shows virtualkubelet service account
```

## Step 7: Deploy VirtualKubelet (Interlink Client)

```bash
ssh rocky@192.168.2.84

# Create VirtualKubelet deployment manifest
cat > /tmp/virtualkubelet.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: virtualkubelet
  namespace: interlink
spec:
  serviceAccountName: virtualkubelet
  containers:
  - name: virtualkubelet
    image: busybox:latest
    imagePullPolicy: IfNotPresent
    command:
    - /bin/sh
    - -c
    - |
      echo "VirtualKubelet starting..."
      echo "Connecting to Interlink Server at 192.168.2.170:3000"
      timeout 2 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000' && \
        echo "✓ Connected to Interlink Server" || \
        echo "✗ Cannot reach Interlink Server"
      
      echo "Running VirtualKubelet..."
      echo "This pod simulates the VirtualKubelet that bridges k3s to SLURM"
      sleep 3600
  restartPolicy: Never
EOF

# Deploy
kubectl apply -f /tmp/virtualkubelet.yaml

# Wait for pod to start
sleep 5

# Check status
kubectl get pods -n interlink

# Expected: virtualkubelet pod should be Running

# Check logs
kubectl logs -n interlink virtualkubelet

# Expected: Should see connection status to Interlink Server
```

## Step 8: Verify Complete Setup

```bash
ssh rocky@192.168.2.84

# Check everything is in place
echo "=== k3s Status ==="
sudo systemctl is-active k3s && echo "✓ k3s running" || echo "✗ k3s not running"

echo ""
echo "=== Kubernetes Nodes ==="
kubectl get nodes

echo ""
echo "=== VirtualKubelet Status ==="
kubectl get pods -n interlink

echo ""
echo "=== System Pods ==="
kubectl get pods -n kube-system | head -5

echo ""
echo "Setup verification complete!"
```

## Troubleshooting

### kubectl command not found

```bash
# Use the full path
sudo /usr/local/bin/k3s kubectl get nodes

# Or set up an alias
echo 'alias kubectl="/usr/local/bin/k3s kubectl"' >> ~/.bashrc
source ~/.bashrc
```

### Cannot copy kubeconfig

```bash
# Alternative: Use sudo for kubectl
sudo /usr/local/bin/k3s kubectl get nodes

# Or run with sudo -E to preserve environment
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
sudo -E /usr/local/bin/k3s kubectl get nodes
```

### k3s service not starting

```bash
# Check status
sudo systemctl status k3s

# Check logs
sudo journalctl -u k3s -n 50

# Restart
sudo systemctl restart k3s

# Wait and check again
sleep 10
sudo systemctl status k3s
```

### VirtualKubelet pod not connecting to Interlink

```bash
# Check if Interlink Server is running on Machine 1
ssh rocky@192.168.2.170 "ps aux | grep interlink"

# Test connectivity from Machine 2
timeout 2 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000' && \
  echo "✓ Can reach Interlink" || \
  echo "✗ Cannot reach Interlink"

# Check pod logs for errors
kubectl logs -n interlink virtualkubelet -f
```

## Verification Checklist

Verify on Machine 2:

- [ ] k3s service running: `sudo systemctl is-active k3s`
- [ ] kubectl works: `kubectl get nodes` shows Ready
- [ ] System pods running: `kubectl get pods -n kube-system` shows pods
- [ ] Interlink namespace created: `kubectl get ns | grep interlink`
- [ ] VirtualKubelet deployed: `kubectl get pods -n interlink`
- [ ] Can reach Machine 1: `ping 192.168.2.170`
- [ ] Can reach Interlink Server: `timeout 2 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000'`

## Important Notes

- The VirtualKubelet pod shown here is a **demo/simulation**
- For full Interlink integration, see [Interlink Setup](interlink-setup.md)
- k3s stores its config in `/etc/rancher/k3s/k3s.yaml` with restricted permissions
- The kubeconfig can be copied for user access but needs proper permissions

## Next Steps

Once Machine 2 is verified working:

1. Ensure Machine 1 is set up with SLURM demo
2. Proceed to [Interlink Setup](interlink-setup.md)
3. Run [Testing Procedures](testing-procedures.md)

---

**Machine 2 setup complete?** Set up Interlink! ➡️
