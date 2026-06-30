# Phase 2: k3s Setup on Machine 2

Install and test k3s Kubernetes on Machine 2 (192.168.2.84).

## Install k3s

```bash
ssh rocky@192.168.2.84

# Install k3s (disable traefik, disable egress policies for Interlink pod logs)
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION=v1.31.4+k3s1 \
  sh -s - \
  --disable=traefik \
  --egress-selector-mode=disabled

# Make kubeconfig readable
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Wait for k3s to be ready
kubectl wait --for=condition=Ready node --all --timeout=150s

# Verify
kubectl get nodes
kubectl get pods -A
```

## Critical Configuration: Egress Policies

The `--egress-selector-mode=disabled` flag is **essential** for Interlink pod logging:

- **Why**: Offloaded pods need to retrieve logs from the SLURM backend via the VirtualKubelet
- **Without it**: k3s enforces egress restrictions that prevent pods from reaching log endpoints
- **Result**: Pods run on SLURM but kubectl logs fails with TLS errors
- **Solution**: Disable egress selector mode in k3s startup (already configured above)

This is configured automatically when you run the installation command above.

## Install Go (needed to build VirtualKubelet)

```bash
# Install Go 1.26+
wget https://go.dev/dl/go1.26.0.linux-amd64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.26.0.linux-amd64.tar.gz

# Add to PATH
echo 'export PATH=/usr/local/go/bin:$PATH' | sudo tee -a /etc/profile.d/go.sh
source /etc/profile.d/go.sh

go version
```

## Install Docker (needed for building Interlink images)

```bash
sudo dnf install -y docker
sudo systemctl start docker
sudo usermod -aG docker rocky

# Test
docker --version
```

---

Next: [Phase 3: Interlink Setup](phase3-interlink-setup.md)
