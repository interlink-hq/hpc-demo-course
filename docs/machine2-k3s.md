# Machine 2: k3s Installation and Configuration

This guide covers the installation and configuration of k3s on Machine 2 (192.168.2.84).

## Overview

k3s is a lightweight, fully compliant Kubernetes distribution. For this demo, Machine 2 will run:
- **k3s Server** (single-node cluster) - Acts as both control plane and worker
- **Container Runtime** - containerd (included with k3s)
- **CNI Plugin** - Flannel or Cilium for networking

## Prerequisites

Before starting, ensure you have completed [Prerequisites and Environment Setup](prerequisites.md).

Key assumptions:
- Machine 2 IP: 192.168.2.84
- Machine 2 Hostname: k3s-machine
- User: rocky
- OS: Rocky Linux 9

## Step 1: Prepare the System

All commands in this section should be run on **Machine 2 (192.168.2.84)**.

```bash
# SSH to Machine 2
ssh rocky@192.168.2.84

# Update system
sudo dnf update -y
sudo dnf upgrade -y

# Install required packages
sudo dnf install -y \
  curl \
  wget \
  git \
  net-tools \
  bind-utils \
  open-iscsi \
  nfs-utils \
  container-selinux
```

## Step 2: Disable Firewall (for demonstration)

⚠️ **This is for demo purposes only. In production, configure firewall properly.**

```bash
# Temporarily stop firewalld
sudo systemctl stop firewalld

# Disable it from starting on boot (for demo)
sudo systemctl disable firewalld

# Or, if you want to keep firewall running, add necessary ports:
# sudo firewall-cmd --permanent --add-port=6443/tcp      # k3s API
# sudo firewall-cmd --permanent --add-port=10250/tcp     # Kubelet
# sudo firewall-cmd --permanent --add-port=8472/udp      # Flannel
# sudo firewall-cmd --reload
```

## Step 3: Install k3s

The easiest way to install k3s is using the installation script:

```bash
# Download and run the k3s install script
curl -sfL https://get.k3s.io | sh -

# The script will:
# - Download k3s binary
# - Create systemd service
# - Start the k3s service
# - Copy kubeconfig to ~/.kube/config

# Wait for k3s to fully start (30-60 seconds)
sleep 30

# Check if k3s service is running
sudo systemctl status k3s

# Verify k3s is ready
sudo k3s kubectl get nodes
```

## Step 4: Configure kubeconfig Access

```bash
# Copy kubeconfig to user home directory
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown rocky:rocky ~/.kube/config
chmod 600 ~/.kube/config

# Verify kubectl works
kubectl get nodes

# You should see something like:
# NAME           STATUS   ROLES                  AGE   VERSION
# k3s-machine    Ready    control-plane,master   2m    v1.XX.X

# Get more details
kubectl get nodes -o wide
```

## Step 5: Verify k3s Installation

```bash
# Check cluster info
kubectl cluster-info

# Check all namespaces
kubectl get ns

# Check system pods
kubectl get pods -A

# Check services
kubectl get svc -A

# Expected output should show:
# - kube-system namespace with core services
# - k3s service controller
# - coredns pod
# - local-path-provisioner
```

## Step 6: Verify Networking

```bash
# Check node IP
kubectl get nodes -o wide

# Check flannel pods (default CNI)
kubectl get pods -n kube-system -l app=flannel

# Test pod networking by deploying a test pod
kubectl run test-pod --image=busybox --restart=Never -- sleep 3600

# Wait for pod to be ready
sleep 10

# Verify pod is running
kubectl get pods

# Test pod connectivity
kubectl exec test-pod -- nslookup kubernetes.default

# Clean up test pod
kubectl delete pod test-pod
```

## Step 7: Configure k3s for Interlink

Create the k3s configuration directory:

```bash
# Create config directory
sudo mkdir -p /etc/rancher/k3s

# Create server configuration (if needed for customization)
# This is optional - k3s works with defaults
sudo bash -c 'cat > /etc/rancher/k3s/config.yaml << EOF
# k3s configuration for Interlink demo
# Most defaults are fine, but you can customize here:
# 
# Example overrides:
# data-dir: /var/lib/rancher/k3s
# write-kubeconfig-mode: "0644"
# flannel-backend: vxlan

EOF'
```

## Step 8: Create RBAC Configuration for Interlink

Interlink will need certain permissions. Create a ServiceAccount for it:

```bash
# Create ServiceAccount for Interlink
kubectl create serviceaccount interlink-admin -n kube-system

# Create ClusterRoleBinding for admin access
kubectl create clusterrolebinding interlink-admin \
  --clusterrole=cluster-admin \
  --serviceaccount=kube-system:interlink-admin

# Verify
kubectl get serviceaccount -n kube-system | grep interlink
```

## Step 9: Configure Firewall for k3s

If you kept firewall enabled:

```bash
# Add k3s required ports
sudo firewall-cmd --permanent --add-port=6443/tcp      # k3s API server
sudo firewall-cmd --permanent --add-port=10250/tcp     # Kubelet
sudo firewall-cmd --permanent --add-port=10255/tcp     # Kubelet read-only
sudo firewall-cmd --permanent --add-port=8472/udp      # Flannel VXLAN
sudo firewall-cmd --permanent --add-port=30000-32767/tcp  # NodePort range

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

## Step 10: Test k3s Functionality

### Deploy a Test Application

```bash
# Create a simple nginx deployment
kubectl create deployment nginx-test --image=nginx

# Expose it as a service
kubectl expose deployment nginx-test --port=80 --target-port=80 --type=NodePort

# Get the NodePort
NODE_PORT=$(kubectl get svc nginx-test -o jsonpath='{.spec.ports[0].nodePort}')
echo "Service exposed on port: $NODE_PORT"

# Test the service
curl http://localhost:$NODE_PORT

# Clean up
kubectl delete deployment nginx-test
kubectl delete svc nginx-test
```

### Test Pod Scheduling

```bash
# Deploy a test pod
cat > /tmp/test-pod.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: test-scheduler
spec:
  containers:
  - name: alpine
    image: alpine
    command: ["sleep", "3600"]
EOF

kubectl apply -f /tmp/test-pod.yaml

# Wait for pod to run
sleep 5

# Verify pod is scheduled
kubectl get pods

# Get pod details
kubectl describe pod test-scheduler

# Execute command in pod
kubectl exec test-scheduler -- hostname

# Clean up
kubectl delete -f /tmp/test-pod.yaml
```

## Step 11: Verify Cluster Networking

Test connectivity between pods and to the outside:

```bash
# Deploy two test pods
kubectl run test-pod-1 --image=busybox --restart=Never -- sleep 3600
kubectl run test-pod-2 --image=busybox --restart=Never -- sleep 3600

# Wait for pods to be ready
sleep 10

# Test networking between pods
POD1_IP=$(kubectl get pod test-pod-1 -o jsonpath='{.status.podIP}')
POD2_IP=$(kubectl get pod test-pod-2 -o jsonpath='{.status.podIP}')

echo "Pod 1 IP: $POD1_IP"
echo "Pod 2 IP: $POD2_IP"

# Ping from pod1 to pod2
kubectl exec test-pod-1 -- ping -c 3 $POD2_IP

# Test DNS from pod
kubectl exec test-pod-1 -- nslookup kubernetes.default

# Test external connectivity
kubectl exec test-pod-1 -- ping -c 3 8.8.8.8

# Clean up
kubectl delete pod test-pod-1 test-pod-2
```

## Step 12: Enable kubectl Autocompletion (Optional)

```bash
# Install bash completion
kubectl completion bash | sudo tee /etc/bash_completion.d/kubectl > /dev/null

# Apply immediately
source <(kubectl completion bash)

# Or add to bashrc for future sessions
echo "source <(kubectl completion bash)" >> ~/.bashrc
source ~/.bashrc
```

## Step 13: Create Test Namespace

Create a namespace for testing Interlink:

```bash
# Create namespace
kubectl create namespace interlink-test

# Verify
kubectl get namespaces

# Set as default (optional)
kubectl config set-context --current --namespace=interlink-test

# Verify context
kubectl config current-context
kubectl config get-contexts
```

## Verification Checklist

Verify the following before proceeding to Interlink setup:

- [ ] k3s service running: `sudo systemctl status k3s`
- [ ] kubectl works: `kubectl get nodes`
- [ ] Nodes are ready: `kubectl get nodes` shows STATUS=Ready
- [ ] System pods running: `kubectl get pods -A` shows kube-system pods
- [ ] Networking works: Pod-to-pod communication working
- [ ] Test deployment successful: nginx deployment ran and was accessible
- [ ] ServiceAccount created: `kubectl get sa -n kube-system | grep interlink`

## Useful kubectl Commands

For reference during setup and testing:

```bash
# Cluster information
kubectl cluster-info
kubectl version

# Node management
kubectl get nodes
kubectl describe node k3s-machine
kubectl top nodes

# Pod management
kubectl get pods -A
kubectl get pods -n kube-system
kubectl describe pod <pod-name>

# Service management
kubectl get svc -A
kubectl get endpoints

# Debugging
kubectl logs <pod-name>
kubectl logs <pod-name> -n <namespace>
kubectl exec <pod-name> -- <command>
kubectl port-forward <pod-name> 8080:8080

# Resource management
kubectl get resources
kubectl explain <resource>
```

## Troubleshooting k3s Issues

### k3s service not running

```bash
# Check service status
sudo systemctl status k3s

# View logs
sudo journalctl -u k3s -n 50

# Restart service
sudo systemctl restart k3s
```

### Nodes not ready

```bash
# Get node status
kubectl get nodes

# Describe node for details
kubectl describe node k3s-machine

# Check kubelet logs
sudo journalctl -u k3s -f

# Common causes:
# - Not enough memory
# - CNI plugin not ready
# - Disk pressure
```

### Pods stuck in pending

```bash
# Check pod events
kubectl describe pod <pod-name>

# Check resource availability
kubectl top nodes
kubectl top pods

# Check for taints/tolerations
kubectl describe node k3s-machine | grep Taints

# Check storage class
kubectl get storageclass
```

### Network connectivity issues

```bash
# Check CNI plugin
kubectl get daemonset -n kube-system

# Check network policies
kubectl get networkpolicies -A

# Test pod networking
kubectl run debug-pod --image=nicolaka/netshoot -it -- bash

# Check iptables (from node)
sudo iptables -L -n
```

## Next Steps

Once k3s is verified working:

1. If you haven't set up Machine 1 yet, go to [Machine 1 - SLURM Setup](machine1-slurm.md)
2. After both machines are ready, proceed to [Interlink Setup](interlink-setup.md)

---

**k3s setup complete?** Move to the next phase! ➡️
