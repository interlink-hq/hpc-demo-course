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

---

Next: [Phase 3: Interlink Setup](phase3-interlink-setup.md)
