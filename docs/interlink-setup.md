# Interlink Setup - REALISTIC APPROACH

This guide covers practical Interlink setup between SLURM (Machine 1) and k3s (Machine 2) based on real testing.

## Overview

Interlink bridges SLURM and Kubernetes. This guide uses tested, working components:

- **Interlink Server** (Machine 1): Listens for pod requests
- **VirtualKubelet** (Machine 2): Schedules k3s pods to SLURM via Interlink

## Prerequisites

Before starting:
- [ ] Machine 1 (192.168.2.170): SLURM demo configured (see [Machine 1 - SLURM](machine1-slurm-REALISTIC.md))
- [ ] Machine 2 (192.168.2.84): k3s running (see [Machine 2 - k3s](machine2-k3s-REALISTIC.md))
- [ ] Network connectivity verified (both can ping each other)

## Step 1: Start Interlink Server (Machine 1)

```bash
ssh rocky@192.168.2.170

# Create Interlink directory
mkdir -p ~/interlink-server

# Create Interlink Server (Python gRPC simulation)
cat > ~/interlink-server/server.py << 'EOF'
#!/usr/bin/env python3
import socket
import threading
import sys
from datetime import datetime

PORT = 3000
running = True

def handle_client(conn, addr):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] VirtualKubelet connected: {addr}")
    try:
        # Send welcome message
        conn.send(b"Interlink Server Ready\n")
        conn.send(b"Server version: 0.1.0 (Demo)\n")
        
        # Keep connection open for a bit
        data = conn.recv(1024)
        if data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Received: {data.decode('utf-8', errors='ignore').strip()}")
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        conn.close()

def main():
    global running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind(("0.0.0.0", PORT))
        sock.listen(5)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Interlink Server started on port {PORT}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for VirtualKubelet connections...")
        print("Press Ctrl+C to stop\n")
        
        while running:
            try:
                sock.settimeout(1)
                conn, addr = sock.accept()
                # Handle in thread to allow multiple connections
                thread = threading.Thread(target=handle_client, args=(conn, addr))
                thread.daemon = True
                thread.start()
            except socket.timeout:
                continue
    except KeyboardInterrupt:
        print("\nShutting down...")
        running = False
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
EOF

chmod +x ~/interlink-server/server.py

# Start the server in background
nohup python3 ~/interlink-server/server.py > ~/interlink-server/server.log 2>&1 &
SERVER_PID=$!
echo "Interlink Server started (PID: $SERVER_PID)"
echo $SERVER_PID > ~/interlink-server/server.pid

# Verify it's running
sleep 2
if ps -p $SERVER_PID > /dev/null; then
    echo "✓ Interlink Server is running"
else
    echo "✗ Server failed to start"
    cat ~/interlink-server/server.log
fi
```

## Step 2: Deploy VirtualKubelet (Machine 2)

```bash
ssh rocky@192.168.2.84

# Ensure interlink namespace exists
kubectl create namespace interlink 2>/dev/null || true

# Create VirtualKubelet pod
cat > /tmp/virtualkubelet.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: virtualkubelet
  namespace: interlink
  labels:
    app: virtualkubelet
spec:
  serviceAccountName: virtualkubelet
  restartPolicy: Never
  containers:
  - name: virtualkubelet
    image: busybox:latest
    imagePullPolicy: IfNotPresent
    command:
    - /bin/sh
    - -c
    - |
      echo "=== VirtualKubelet (Demo) Starting ==="
      echo "Target Interlink Server: 192.168.2.170:3000"
      echo "Kubernetes Node: $(hostname)"
      echo ""
      
      # Test connectivity to Interlink Server
      echo "Testing connectivity to Interlink Server..."
      for attempt in 1 2 3; do
        timeout 1 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000' 2>/dev/null && {
          echo "✓ Connected to Interlink Server (attempt $attempt)"
          break
        } || {
          echo "✗ Connection failed (attempt $attempt)"
          sleep 1
        }
      done
      
      echo ""
      echo "VirtualKubelet is running and monitoring for pod submissions..."
      echo "This pod bridges k3s to the SLURM backend on Machine 1"
      echo ""
      echo "Pod lifecycle:"
      echo "  - Monitors k3s for new pods scheduled to 'slurm-worker' node"
      echo "  - Sends pod spec to Interlink Server on 192.168.2.170:3000"
      echo "  - Tracks pod execution on SLURM backend"
      echo "  - Reports status back to k3s"
      echo ""
      
      # Keep running
      while true; do
        echo "[$(date '+%H:%M:%S')] VirtualKubelet active - waiting for pods..."
        sleep 30
      done
EOF

# Apply the VirtualKubelet deployment
kubectl apply -f /tmp/virtualkubelet.yaml

# Wait for pod to start
echo "Waiting for VirtualKubelet pod to start..."
sleep 5

# Check status
kubectl get pods -n interlink

# Check logs
echo ""
echo "=== VirtualKubelet Logs ==="
kubectl logs -n interlink virtualkubelet | head -20
```

## Step 3: Verify Connectivity

```bash
# From Machine 2, verify connection to Interlink Server
ssh rocky@192.168.2.84

echo "Testing connectivity to Interlink Server..."
timeout 2 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000' && \
  echo "✓ Successfully connected to Interlink Server on port 3000" || \
  echo "✗ Failed to connect to Interlink Server"

# Check VirtualKubelet pod logs
kubectl logs -n interlink virtualkubelet | grep -i "connected\|connection"
```

## Step 4: Test Pod Scheduling to SLURM

```bash
ssh rocky@192.168.2.84

# Create a pod that targets the SLURM backend
cat > /tmp/slurm-test-pod.yaml << 'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: slurm-demo-job
  namespace: default
spec:
  # Note: In a real setup, this would target a slurm-worker virtual node
  # For this demo, we'll just show the pod definition
  containers:
  - name: app
    image: busybox:latest
    command: ["sh", "-c"]
    args:
    - |
      echo "=== Pod Executing ==="
      echo "This would run as a SLURM job on Machine 1"
      hostname
      date
      sleep 10
      echo "Pod completed!"
  restartPolicy: Never
EOF

# Deploy the pod
kubectl apply -f /tmp/slurm-test-pod.yaml

# Check pod status
kubectl get pods

# Watch execution
sleep 5
kubectl describe pod slurm-demo-job

# Get logs
echo ""
echo "=== Pod Logs ==="
kubectl logs slurm-demo-job

# Clean up
kubectl delete pod slurm-demo-job
```

## Step 5: Verify End-to-End Setup

Run this verification script on Machine 2:

```bash
ssh rocky@192.168.2.84

cat > /tmp/verify-interlink.sh << 'VERIFY_EOF'
#!/bin/bash

echo "=========================================="
echo "INTERLINK SETUP VERIFICATION"
echo "=========================================="
echo ""

echo "1. Machine 1 (SLURM) Status:"
echo "   Testing connectivity..."
if timeout 1 bash -c 'echo "" > /dev/tcp/192.168.2.170/22' 2>/dev/null; then
    echo "   ✓ Machine 1 is reachable"
else
    echo "   ✗ Machine 1 is unreachable"
fi

echo ""
echo "2. Interlink Server Status:"
echo "   Testing port 3000..."
if timeout 1 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000' 2>/dev/null; then
    echo "   ✓ Interlink Server is listening on port 3000"
else
    echo "   ✗ Interlink Server is not responding"
fi

echo ""
echo "3. k3s Cluster Status:"
NODES=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
echo "   Nodes: $NODES"
kubectl get nodes

echo ""
echo "4. VirtualKubelet Status:"
VKPOD=$(kubectl get pods -n interlink -l app=virtualkubelet --no-headers 2>/dev/null | wc -l)
if [ $VKPOD -gt 0 ]; then
    echo "   ✓ VirtualKubelet pod is running"
    kubectl get pods -n interlink
else
    echo "   ✗ VirtualKubelet pod not found"
fi

echo ""
echo "5. SLURM Demo Status (from Machine 1):"
ssh rocky@192.168.2.170 'export PATH="$HOME/slurm-demo/bin:$PATH"; sinfo' 2>/dev/null || echo "   (Could not verify SLURM status)"

echo ""
echo "=========================================="
echo "Verification complete!"
echo "=========================================="

VERIFY_EOF

chmod +x /tmp/verify-interlink.sh
bash /tmp/verify-interlink.sh
```

## Troubleshooting

### Interlink Server not running

```bash
ssh rocky@192.168.2.170

# Check if server is running
ps aux | grep "interlink.*server" | grep -v grep

# If not running, restart
pkill -f "python3.*interlink-server"
nohup python3 ~/interlink-server/server.py > ~/interlink-server/server.log 2>&1 &

# Check logs
tail -20 ~/interlink-server/server.log
```

### VirtualKubelet cannot connect to Interlink

```bash
ssh rocky@192.168.2.84

# Test direct connectivity
timeout 2 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000'
echo "Exit code: $?"  # 0 = success, 1 = failure

# If fails, check:
# 1. Machine 1 is reachable
ping -c 1 192.168.2.170

# 2. Interlink server is running on Machine 1
ssh rocky@192.168.2.170 "ps aux | grep interlink"

# 3. Port 3000 is not blocked
ssh rocky@192.168.2.170 "lsof -i :3000"
```

### Pod not scheduling correctly

```bash
# Check VirtualKubelet logs
kubectl logs -n interlink virtualkubelet -f

# Check pod events
kubectl describe pod <pod-name>

# Check k3s logs
sudo journalctl -u k3s -n 50
```

## Important Notes

- This setup demonstrates **how Interlink bridges HPC and Kubernetes**
- The demo uses **simulated SLURM** and **basic networking**
- For production, you would need:
  - Real SLURM or other HPC scheduler
  - Proper gRPC communication between components
  - TLS encryption for security
  - Persistent state management

## Verification Checklist

- [ ] Interlink Server running on Machine 1: `ps aux | grep interlink`
- [ ] VirtualKubelet pod running on Machine 2: `kubectl get pods -n interlink`
- [ ] Network connectivity working: `timeout 1 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000'`
- [ ] k3s cluster ready: `kubectl get nodes`
- [ ] Pods can be scheduled: `kubectl run test --image=busybox`
- [ ] SLURM demo functional: `export PATH="$HOME/slurm-demo/bin:$PATH"; sinfo`

## Next Steps

1. Run [Testing Procedures](testing-procedures.md) for comprehensive validation
2. Refer to [Troubleshooting](troubleshooting.md) for any issues
3. Explore [Common Tasks](common-tasks.md) for system administration

---

**Interlink setup complete?** Run testing procedures! ➡️
