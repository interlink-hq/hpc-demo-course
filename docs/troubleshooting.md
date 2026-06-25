# Troubleshooting Guide

This guide provides solutions to common issues you may encounter during setup or operation.

## Quick Diagnosis

Before diving into specific sections, run this diagnostic:

```bash
#!/bin/bash
echo "=== Quick Diagnosis ==="

echo "1. Machine 1 (SLURM):"
ssh rocky@192.168.2.170 '
  echo "  SLURM Controller: $(sudo systemctl is-active slurmctld)"
  echo "  SLURM Compute: $(sudo systemctl is-active slurmd)"
  echo "  Munge: $(sudo systemctl is-active mungd)"
  echo "  Nodes: $(sinfo | grep -c idle) idle"
'

echo ""
echo "2. Machine 2 (k3s):"
ssh rocky@192.168.2.84 '
  echo "  k3s: $(sudo systemctl is-active k3s)"
  echo "  Nodes: $(kubectl get nodes --no-headers | wc -l) total"
  echo "  Pods: $(kubectl get pods -A --no-headers | wc -l) total"
'

echo ""
echo "3. Network:"
ping -c 1 192.168.2.170 > /dev/null && echo "  Machine 1: Reachable" || echo "  Machine 1: UNREACHABLE"
ping -c 1 192.168.2.84 > /dev/null && echo "  Machine 2: Reachable" || echo "  Machine 2: UNREACHABLE"
```

---

## SLURM Issues

### Problem: Node Shows "down" State

**Symptoms**: `sinfo` shows node in "down" or "unknown" state

**Diagnosis**:
```bash
ssh rocky@192.168.2.170

# Check node state
sinfo

# Get detailed info
scontrol show node slurm-machine

# Check slurmd logs
tail -50 /var/log/slurm/slurmd.log

# Check if slurmd is running
sudo systemctl status slurmd
```

**Solutions**:

1. **Restart slurmd**:
   ```bash
   ssh rocky@192.168.2.170
   sudo systemctl restart slurmd
   sleep 5
   sinfo
   ```

2. **Check for permission issues**:
   ```bash
   # Verify ownership
   ls -la /var/spool/slurmd
   ls -la /var/log/slurm/
   
   # Should be owned by slurm:slurm
   sudo chown -R slurm:slurm /var/spool/slurmd
   sudo chown -R slurm:slurm /var/log/slurm/
   ```

3. **Check disk space**:
   ```bash
   df -h /
   # If < 1GB free, clean up
   ```

4. **Validate configuration**:
   ```bash
   sudo slurmctld -Cc
   # Should show "Configuration is valid"
   ```

### Problem: Cannot Connect to slurmctld

**Symptoms**: Commands like `sinfo` fail with "Unable to contact slurm controller"

**Diagnosis**:
```bash
ssh rocky@192.168.2.170

# Check if controller is running
sudo systemctl status slurmctld

# Check listening ports
sudo ss -tlnp | grep 6817

# Check if port is accessible
scontrol ping
```

**Solutions**:

1. **Restart controller**:
   ```bash
   sudo systemctl restart slurmctld
   sleep 5
   sinfo
   ```

2. **Check configuration**:
   ```bash
   # Verify slurm.conf exists
   cat /etc/slurm/slurm.conf | head -20
   
   # Check for syntax errors
   sudo slurmctld -Cc
   ```

3. **Check network**:
   ```bash
   # From another machine
   ssh rocky@192.168.2.84
   nc -zv 192.168.2.170 6817
   telnet 192.168.2.170 6817
   ```

4. **Check firewall**:
   ```bash
   sudo firewall-cmd --list-ports | grep 6817
   # If not listed
   sudo firewall-cmd --permanent --add-port=6817/tcp
   sudo firewall-cmd --reload
   ```

### Problem: Munge Authentication Fails

**Symptoms**: Jobs fail to run, "Munge error" in logs

**Diagnosis**:
```bash
ssh rocky@192.168.2.170

# Check munge service
sudo systemctl status mungd

# Test munge locally
munge -n | unmunge

# Check munge key
ls -la /etc/munge/munge.key
```

**Solutions**:

1. **Restart munge**:
   ```bash
   sudo systemctl restart mungd
   sleep 2
   munge -n | unmunge
   ```

2. **Regenerate munge key** (if corrupted):
   ```bash
   sudo /usr/sbin/mungekey --verbose --force
   sudo systemctl restart mungd
   ```

3. **Fix permissions**:
   ```bash
   sudo chmod 600 /etc/munge/munge.key
   sudo chown munge:munge /etc/munge/munge.key
   ```

### Problem: Jobs Stuck in PENDING State

**Symptoms**: `squeue` shows job in PENDING, never runs

**Diagnosis**:
```bash
ssh rocky@192.168.2.170

# Check job status
squeue

# Get detailed info
JOBID=<job-id>
scontrol show job $JOBID

# Look for "Reason:" field - this explains why
```

**Solutions**:

1. **Check node availability**:
   ```bash
   sinfo
   # If no "idle" nodes, jobs will wait
   ```

2. **Check job requirements**:
   ```bash
   scontrol show job $JOBID | grep -E "CPUs|Memory|Partition"
   
   # Verify node can meet requirements
   scontrol show node slurm-machine | grep -E "CPUs|RealMemory"
   ```

3. **Update job if requirements too high**:
   ```bash
   # Cancel current job
   scancel $JOBID
   
   # Resubmit with lower requirements
   sbatch --ntasks=1 --cpus-per-task=1 --mem=512 test-job.sh
   ```

4. **Check partition assignment**:
   ```bash
   scontrol show job $JOBID | grep Partition
   sinfo -p default
   ```

### Problem: Job Completes But Output Not Available

**Symptoms**: Job shows COMPLETED but output files missing or empty

**Solutions**:

1. **Check output paths**:
   ```bash
   # Verify SLURM output file locations
   cat /etc/slurm/slurm.conf | grep -i "state\|spool"
   
   # Check if files exist
   ls -la /var/spool/slurm*
   ```

2. **Ensure proper permissions**:
   ```bash
   # Job output should be accessible to user
   ls -la /var/spool/slurm/job_*
   ```

3. **Check logs directly**:
   ```bash
   # View job accounting
   sacct -j $JOBID --format=JobID,JobName,State,ExitCode
   
   # View controller logs
   tail /var/log/slurm/slurmctld.log
   ```

---

## Kubernetes (k3s) Issues

### Problem: Nodes Not Ready

**Symptoms**: `kubectl get nodes` shows NotReady

**Diagnosis**:
```bash
ssh rocky@192.168.2.84

# Check node status
kubectl get nodes

# Get details
kubectl describe node k3s-machine

# Check system pods
kubectl get pods -A

# Check kubelet logs
journalctl -u k3s -n 50
```

**Solutions**:

1. **Restart k3s**:
   ```bash
   sudo systemctl restart k3s
   sleep 10
   kubectl get nodes
   ```

2. **Check for resource issues**:
   ```bash
   # Check disk space
   df -h /
   
   # Check memory
   free -h
   
   # Check for memory pressure
   kubectl describe node k3s-machine | grep -E "Allocatable|Pressure"
   ```

3. **Check CNI plugin**:
   ```bash
   # Check if flannel is deployed
   kubectl get ds -A -o wide | grep -i flann
   
   # Check flannel pods
   kubectl get pods -n kube-system -l app=flannel
   ```

4. **Check containerd**:
   ```bash
   # Check container status
   systemctl status containerd
   
   # Restart if needed
   sudo systemctl restart containerd
   ```

### Problem: Pods Stuck in Pending

**Symptoms**: `kubectl get pods` shows Pending indefinitely

**Diagnosis**:
```bash
# Get pod details
kubectl describe pod <pod-name>

# Check events for the pod
kubectl get events

# Check node capacity
kubectl describe nodes
```

**Solutions**:

1. **Check node selectors**:
   ```bash
   # If pod has nodeSelector, verify node has matching labels
   kubectl get nodes --show-labels
   
   # Add missing labels if needed
   kubectl label node k3s-machine workload=general
   ```

2. **Check resource requests**:
   ```bash
   # Get pod request/limits
   kubectl get pod <pod-name> -o yaml | grep -A 5 resources
   
   # Check node capacity
   kubectl describe node k3s-machine | grep -E "Allocatable|Requested"
   ```

3. **Check PVC status** (if using storage):
   ```bash
   kubectl get pvc -A
   kubectl describe pvc <pvc-name>
   ```

### Problem: CrashLoopBackOff

**Symptoms**: Pod crashes and k3s keeps restarting it

**Diagnosis**:
```bash
# Check pod logs
kubectl logs <pod-name>
kubectl logs <pod-name> --previous

# Get pod details
kubectl describe pod <pod-name>

# Check events
kubectl get events
```

**Solutions**:

1. **Review application logs**:
   ```bash
   kubectl logs <pod-name> | tail -50
   ```

2. **Check image availability**:
   ```bash
   # If pull fails
   kubectl describe pod <pod-name> | grep -i image
   
   # Test if image exists
   podman pull <image-name>
   ```

3. **Check resource limits**:
   ```bash
   # Pod might be OOMKilled
   kubectl describe pod <pod-name> | grep -i "oom\|killed"
   
   # Increase memory in pod spec
   ```

### Problem: Services Not Accessible

**Symptoms**: Cannot reach service IP or NodePort

**Diagnosis**:
```bash
# Check service
kubectl get svc

# Get details
kubectl describe svc <service-name>

# Check endpoints
kubectl get endpoints <service-name>

# Test connectivity to pod directly
kubectl exec <pod-name> -- curl localhost:8080
```

**Solutions**:

1. **Verify endpoints**:
   ```bash
   # If endpoints are empty, pods might not be running
   kubectl get endpoints
   kubectl get pods
   ```

2. **Check network policies**:
   ```bash
   # List network policies
   kubectl get networkpolicies -A
   
   # If policies exist, they might be blocking traffic
   ```

3. **Test with port-forward**:
   ```bash
   # Bypass network policies
   kubectl port-forward <pod-name> 8080:8080
   # Then test from localhost
   curl localhost:8080
   ```

### Problem: Cannot Access kubeconfig

**Symptoms**: kubectl commands fail with authentication errors

**Solutions**:

1. **Set KUBECONFIG**:
   ```bash
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   kubectl get nodes
   ```

2. **Copy kubeconfig to user**:
   ```bash
   sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
   sudo chown $USER:$USER ~/.kube/config
   chmod 600 ~/.kube/config
   ```

3. **Fix permissions**:
   ```bash
   ls -la ~/.kube/config
   # Should be 600 permissions owned by your user
   ```

---

## Interlink Issues

### Problem: VirtualKubelet Pod Not Running

**Symptoms**: `kubectl get pods -n interlink` shows Error or CrashLoopBackOff

**Diagnosis**:
```bash
ssh rocky@192.168.2.84

# Check pod status
kubectl get pods -n interlink

# Get logs
kubectl logs -n interlink <pod-name>

# Get detailed info
kubectl describe pod -n interlink <pod-name>
```

**Solutions**:

1. **Check configuration**:
   ```bash
   # Verify ConfigMap exists
   kubectl get configmap -n interlink
   
   # Check contents
   kubectl get configmap interlink-config -n interlink -o yaml
   ```

2. **Check certificates**:
   ```bash
   # Verify Secret exists
   kubectl get secret -n interlink
   
   # Check cert dates
   openssl x509 -in ~/.interlink/certs/server.crt -text -noout | grep -E "Not|CN="
   ```

3. **Redeploy VirtualKubelet**:
   ```bash
   # Delete and recreate
   kubectl delete deployment -n interlink virtualkubelet
   
   # Wait for removal
   sleep 10
   
   # Recreate
   kubectl apply -f /tmp/virtualkubelet-deployment.yaml
   ```

### Problem: Interlink Server Not Listening

**Symptoms**: Cannot connect to Interlink server on port 3000

**Diagnosis**:
```bash
ssh rocky@192.168.2.170

# Check service status
sudo systemctl status interlink-server

# Check if port is open
sudo ss -tlnp | grep 3000

# Check logs
journalctl -u interlink-server -n 50
```

**Solutions**:

1. **Start service**:
   ```bash
   sudo systemctl start interlink-server
   sleep 5
   sudo systemctl status interlink-server
   ```

2. **Check configuration file**:
   ```bash
   # Verify config exists
   cat ~/.interlink/config/interlink-server.yaml
   
   # Check for YAML syntax errors
   ```

3. **Rebuild if needed**:
   ```bash
   cd ~/interlink
   make clean
   make build
   sudo systemctl restart interlink-server
   ```

### Problem: Pods Not Appearing as SLURM Jobs

**Symptoms**: Pod created in k3s but no job appears in SLURM

**Diagnosis**:
```bash
# Check VirtualKubelet logs
ssh rocky@192.168.2.84
kubectl logs -n interlink -l app=virtualkubelet -f

# Check Interlink Server logs
ssh rocky@192.168.2.170
journalctl -u interlink-server -f

# Try creating pod with debug
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: debug-pod
spec:
  nodeSelector:
    kubernetes.io/hostname: slurm-worker
  containers:
  - name: test
    image: busybox
    command: ["sleep", "300"]
EOF
```

**Solutions**:

1. **Verify network connectivity**:
   ```bash
   # From Machine 2, test Interlink Server
   ssh rocky@192.168.2.84
   nc -zv 192.168.2.170 3000
   ```

2. **Check virtual node is ready**:
   ```bash
   kubectl get nodes slurm-worker
   kubectl describe node slurm-worker
   
   # Should show Ready status
   ```

3. **Check Interlink Server configuration**:
   ```bash
   ssh rocky@192.168.2.170
   cat ~/.interlink/config/interlink-server.yaml
   
   # Verify SLURM paths are correct
   which sbatch
   which scontrol
   ```

4. **Restart components**:
   ```bash
   # On Machine 2
   ssh rocky@192.168.2.84
   kubectl delete pod -n interlink virtualkubelet-*
   
   # Wait for restart
   sleep 10
   
   # On Machine 1
   ssh rocky@192.168.2.170
   sudo systemctl restart interlink-server
   ```

---

## Network Issues

### Problem: Cannot Ping Between Machines

**Symptoms**: `ping 192.168.2.170` fails from Machine 2 or vice versa

**Diagnosis**:
```bash
# Check IP configuration
ssh rocky@192.168.2.170 ip addr show
ssh rocky@192.168.2.84 ip addr show

# Check routing
ssh rocky@192.168.2.170 ip route show
ssh rocky@192.168.2.84 ip route show

# Check if firewall is blocking
ssh rocky@192.168.2.170 sudo firewall-cmd --list-all
ssh rocky@192.168.2.84 sudo firewall-cmd --list-all
```

**Solutions**:

1. **Verify network configuration**:
   ```bash
   # Check DHCP if dynamic
   dhclient -v
   
   # Set static IP if needed
   sudo nmcli device modify eth0 ipv4.addresses 192.168.2.170/24
   sudo nmcli device modify eth0 ipv4.gateway 192.168.2.1
   sudo nmcli connection reload
   ```

2. **Disable firewall temporarily for testing**:
   ```bash
   sudo systemctl stop firewalld
   ping 192.168.2.170
   # If works, reconfigure firewall rules
   sudo systemctl start firewalld
   ```

3. **Check physical network**:
   ```bash
   # Verify cables/connectivity
   ethtool eth0 | grep "Link"
   # Should show "Link detected: yes"
   ```

### Problem: Port Not Accessible

**Symptoms**: `nc -zv 192.168.2.170 6817` fails

**Diagnosis**:
```bash
# Check if port is listening
ssh rocky@192.168.2.170 sudo ss -tlnp | grep 6817

# Check firewall
sudo firewall-cmd --list-ports

# Check from remote machine
ssh rocky@192.168.2.84 nc -zv 192.168.2.170 6817
```

**Solutions**:

1. **Open firewall port**:
   ```bash
   ssh rocky@192.168.2.170
   sudo firewall-cmd --permanent --add-port=6817/tcp
   sudo firewall-cmd --reload
   ```

2. **Verify service is running**:
   ```bash
   # Port must be in LISTEN state
   sudo ss -tlnp | grep <port>
   ```

3. **Check for IP binding restrictions**:
   ```bash
   # If only bound to localhost, won't be accessible remotely
   netstat -tlnp | grep :<port>
   ```

---

## General Troubleshooting

### How to Check Logs

```bash
# System journal
journalctl -xe -n 50

# Specific service
journalctl -u slurmctld -n 50
journalctl -u k3s -n 50

# Real-time follow
journalctl -f

# SLURM specific logs
tail /var/log/slurm/*.log

# Kubernetes logs
kubectl logs -A
```

### How to Collect Debug Information

```bash
# Run diagnostic script
#!/bin/bash
echo "=== SYSTEM INFO ===" > diag.txt
date >> diag.txt
hostname >> diag.txt
uname -a >> diag.txt

echo "=== NETWORK ===" >> diag.txt
ip addr show >> diag.txt
ip route show >> diag.txt

echo "=== SLURM ===" >> diag.txt
sinfo >> diag.txt
squeue >> diag.txt

echo "=== KUBERNETES ===" >> diag.txt
kubectl get nodes >> diag.txt
kubectl get pods -A >> diag.txt

echo "=== SERVICES ===" >> diag.txt
systemctl status slurmctld >> diag.txt
systemctl status slurmd >> diag.txt
systemctl status k3s >> diag.txt

# Compress for sharing
tar czf diag-$(date +%Y%m%d-%H%M%S).tar.gz diag.txt
```

### How to Reset and Start Fresh

```bash
# SLURM reset
ssh rocky@192.168.2.170
sudo systemctl stop slurmctld slurmd
sudo rm -rf /var/spool/slurm/*
sudo systemctl start slurmctld slurmd

# k3s reset
ssh rocky@192.168.2.84
sudo systemctl stop k3s
sudo /usr/local/bin/k3s-uninstall.sh
curl -sfL https://get.k3s.io | sh -
```

---

## Getting Help

If issues persist:

1. Check the relevant setup guide for your component
2. Review this troubleshooting guide's Quick Diagnosis
3. Check service logs with `journalctl`
4. Verify network connectivity with ping/nc
5. Try restarting the affected service

For Interlink specific issues, check the official Interlink documentation:
- https://github.com/interlink-hq/interlink

For SLURM issues:
- https://slurm.schedmd.com/

For Kubernetes (k3s):
- https://docs.k3s.io/

---

**Issue resolved?** Return to testing procedures or main README. ➡️
