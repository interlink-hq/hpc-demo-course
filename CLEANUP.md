# Cleanup & Reset

Complete teardown procedures for testing and resetting the environment.

## Quick Cleanup

```bash
# Set your machines
M1_IP="192.168.2.122"
M2_IP="192.168.2.78"

# Stop all services
ssh rocky@${M1_IP} << 'M1STOP'
pkill -f interlink-api || true
pkill -f slurm-plugin || true
pkill -f slurmctld || true
pkill -f slurmd || true
pkill -f slurmdbd || true
sleep 2
echo "✓ All services stopped on Machine 1"
M1STOP

ssh rocky@${M2_IP} << 'M2STOP'
pkill -f virtual-kubelet || true
pkill -f k3s || true
sleep 2
echo "✓ All services stopped on Machine 2"
M2STOP
```

## Full Reset (Machine 1 - SLURM/Interlink)

```bash
ssh rocky@${M1_IP} << 'M1RESET'

# Stop services
pkill -f interlink-api || true
pkill -f slurm-plugin || true
pkill -f slurmctld || true
pkill -f slurmd || true
pkill -f slurmdbd || true
sleep 2

# Remove temporary data
rm -rf ~/.interlink*
rm -rf ~/interlink/*.log
rm -rf /var/spool/slurm*
rm -rf /var/log/slurm/*

# Stop database
sudo systemctl stop mariadb 2>/dev/null || true

# Verify cleanup
echo "=== Cleanup Complete ==="
echo "Remaining processes:"
ps aux | grep -E '[s]lurm|[i]nterlink|[m]ariadb' | grep -v grep || echo "None"
echo ""
echo "Remaining directories:"
du -sh ~/* 2>/dev/null | grep -E 'slurm|interlink' || echo "None"

M1RESET
```

## Full Reset (Machine 2 - k3s/VirtualKubelet)

```bash
ssh rocky@${M2_IP} << 'M2RESET'

# Stop k3s
pkill -f virtual-kubelet || true
pkill -f k3s || true
sleep 2

# Uninstall k3s (if desired)
sudo /usr/local/bin/k3s-uninstall.sh 2>/dev/null || true
sudo /usr/local/bin/k3s-agent-uninstall.sh 2>/dev/null || true

# Remove temporary data
rm -rf ~/.kube
rm -rf /var/lib/rancher/k3s 2>/dev/null || true
rm -rf /var/log/pods 2>/dev/null || true
rm -rf /etc/rancher 2>/dev/null || true

# Verify cleanup
echo "=== Cleanup Complete ==="
echo "Remaining processes:"
ps aux | grep -E '[k]3s|[v]irtual' | grep -v grep || echo "None"
echo ""
echo "Remaining directories:"
du -sh ~/* 2>/dev/null | grep -E 'kube|rancher' || echo "None"

M2RESET
```

## Selective Cleanup (Keep Infrastructure, Reset Workloads)

Use this if you want to keep SLURM and k3s but reset the Interlink integration.

```bash
# Stop only Interlink services
ssh rocky@${M1_IP} << 'M1INT'
pkill -f interlink-api || true
pkill -f slurm-plugin || true
rm -rf ~/.interlink*
echo "✓ Interlink services stopped and cleaned"
M1INT

# Reset k3s workloads
ssh rocky@${M2_IP} << 'M2WORKLOAD'
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl delete namespace virtual-kubelet 2>/dev/null || true
kubectl delete pod --all 2>/dev/null || true
echo "✓ Kubernetes workloads cleaned"
M2WORKLOAD
```

## Database Reset (If MariaDB has issues)

```bash
ssh rocky@${M1_IP} << 'DBRESET'

# Stop SlurmDBD first
pkill -f slurmdbd || true
sleep 2

# Stop database
sudo systemctl stop mariadb || true
sudo systemctl start mariadb

# Reset database
sudo mysql <<'EOF'
DROP DATABASE IF EXISTS slurm_acct_db;
CREATE DATABASE slurm_acct_db;
GRANT ALL ON slurm_acct_db.* TO 'slurm'@'localhost' IDENTIFIED BY 'password';
FLUSH PRIVILEGES;
EOF

echo "✓ Database reset complete"

DBRESET
```

## Verify Clean State

```bash
echo "=== Machine 1 Status ==="
ssh rocky@${M1_IP} 'ps aux | wc -l'
ssh rocky@${M1_IP} 'du -sh ~'

echo ""
echo "=== Machine 2 Status ==="
ssh rocky@${M2_IP} 'ps aux | wc -l'
ssh rocky@${M2_IP} 'du -sh ~'

echo ""
echo "=== Network Connectivity ==="
ssh rocky@${M1_IP} "ping -c 1 ${M2_IP}" 2>&1 | tail -1
ssh rocky@${M2_IP} "ping -c 1 ${M1_IP}" 2>&1 | tail -1
```

## Troubleshooting Cleanup

### Processes Won't Stop
```bash
# Get process info
ssh rocky@${M1_IP} 'ps aux | grep -i slurm'

# Kill by PID if needed
ssh rocky@${M1_IP} 'kill -9 <PID>'
```

### Disk Space Issues
```bash
# Find large directories
ssh rocky@${M1_IP} 'du -sh ~/* | sort -h | tail -10'

# Check systemd journal
ssh rocky@${M1_IP} 'sudo journalctl --disk-usage'
```

### Cannot Remove Directories
```bash
# Check permissions
ssh rocky@${M1_IP} 'ls -la /var/spool/ | grep slurm'

# Fix permissions
ssh rocky@${M1_IP} 'sudo chown -R rocky:rocky ~/slurm-demo ~/interlink ~/.interlink*'

# Then remove
ssh rocky@${M1_IP} 'rm -rf ~/slurm-demo ~/interlink ~/.interlink*'
```

---

**After cleanup**, you can restart from Phase 1 of [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).
