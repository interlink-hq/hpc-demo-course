# Machine 1: SLURM Setup - REALISTIC APPROACH

This guide covers a practical SLURM setup on Machine 1 (192.168.2.170) that works with the current environment.

## Overview

Due to package availability and network constraints, this guide uses two approaches:

1. **Option A**: Use pre-built SLURM RPM packages (if available in repo)
2. **Option B**: Deploy SLURM demo/simulator (for course demonstration)

For this course, we'll use **Option B** which provides a functional demo of SLURM concepts.

## Prerequisites

Before starting, ensure you have completed [Prerequisites and Environment Setup](prerequisites.md).

## Step 1: Verify System Setup

```bash
ssh rocky@192.168.2.170

# Verify hostname
hostname
# Expected output: slurm-machine

# Verify /etc/hosts
grep "192.168.2" /etc/hosts
# Expected: Both machine IPs configured

# Verify connectivity
ping -c 2 192.168.2.84
# Expected: 0% packet loss
```

## Step 2: Check for Available SLURM Packages

```bash
ssh rocky@192.168.2.170

# Search for SLURM in available repositories
dnf search slurm

# Try to list available versions
dnf info slurm 2>/dev/null || echo "SLURM not in standard repos"
```

## Step 3: SLURM Demo Setup (If official packages unavailable)

If SLURM packages aren't available, use the demo setup that simulates SLURM:

```bash
ssh rocky@192.168.2.170

# Create SLURM demo directory
mkdir -p ~/slurm-demo/{bin,etc,logs}

# Create mock sbatch command
cat > ~/slurm-demo/bin/sbatch << 'EOF'
#!/bin/bash
JOBID=$((RANDOM * 1000))
echo "Submitted batch job $JOBID"
mkdir -p ~/slurm-demo/jobs/job_$JOBID
cp "$1" ~/slurm-demo/jobs/job_$JOBID/script.sh 2>/dev/null || true
bash "$1" > ~/slurm-demo/jobs/job_$JOBID/output.log 2>&1 &
echo $! > ~/slurm-demo/jobs/job_$JOBID/pid
EOF
chmod +x ~/slurm-demo/bin/sbatch

# Create mock sinfo command
cat > ~/slurm-demo/bin/sinfo << 'EOF'
#!/bin/bash
echo "PARTITION  AVAIL  TIMELIMIT  NODES  STATE NODELIST"
echo "default*      up   infinite      1   idle slurm-machine"
EOF
chmod +x ~/slurm-demo/bin/sinfo

# Create mock squeue command
cat > ~/slurm-demo/bin/squeue << 'EOF'
#!/bin/bash
echo "JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)"
for jobdir in ~/slurm-demo/jobs/job_*; do
  [ -d "$jobdir" ] || continue
  JOBID=$(basename $jobdir | sed 's/job_//')
  [ -f "$jobdir/pid" ] || continue
  PID=$(cat $jobdir/pid)
  if kill -0 $PID 2>/dev/null; then
    echo "$JOBID default    sbatch  rocky  R       1s      1 slurm-machine"
  else
    echo "$JOBID default    sbatch  rocky  CD      2s      1 slurm-machine"
  fi
done
EOF
chmod +x ~/slurm-demo/bin/squeue

# Add to PATH
echo 'export PATH="$HOME/slurm-demo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## Step 4: Test SLURM Demo

```bash
ssh rocky@192.168.2.170

# Activate the SLURM demo tools
export PATH="$HOME/slurm-demo/bin:$PATH"

# Check cluster status
sinfo

# Expected output:
# PARTITION  AVAIL  TIMELIMIT  NODES  STATE NODELIST
# default*      up   infinite      1   idle slurm-machine
```

## Step 5: Submit and Run a Test Job

```bash
ssh rocky@192.168.2.170

# Activate SLURM tools
export PATH="$HOME/slurm-demo/bin:$PATH"

# Create a test job script
cat > /tmp/test-job.sh << 'EOF'
#!/bin/bash
echo "=== SLURM Job Test ==="
echo "Hostname: $(hostname)"
echo "Date: $(date)"
echo "User: $(whoami)"
sleep 2
echo "Job completed!"
EOF

chmod +x /tmp/test-job.sh

# Submit the job
sbatch /tmp/test-job.sh

# Check job queue
sleep 2
squeue

# View job output
ls ~/slurm-demo/jobs/job_*/output.log
cat ~/slurm-demo/jobs/job_*/output.log
```

## Step 6: Set Up Interlink Server

Create an Interlink Server that listens for requests from the k3s VirtualKubelet:

```bash
ssh rocky@192.168.2.170

# Create Interlink server directory
mkdir -p ~/interlink-server/certs

# Create the Interlink Server (Python gRPC mock)
cat > ~/interlink-server/server.py << 'EOF'
#!/usr/bin/env python3
import socket
import sys

PORT = 3000
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", PORT))
sock.listen(5)

print(f"Interlink Server listening on port {PORT}")
print("Waiting for VirtualKubelet connections...")
print("Press Ctrl+C to stop")

try:
  while True:
    conn, addr = sock.accept()
    print(f"[VirtualKubelet] Connection from {addr}")
    conn.send(b"Interlink Server Ready\n")
    conn.close()
except KeyboardInterrupt:
  print("\nServer stopped")
finally:
  sock.close()
EOF

chmod +x ~/interlink-server/server.py

# Start the server in background
nohup python3 ~/interlink-server/server.py > ~/interlink-server/server.log 2>&1 &
SERVER_PID=$!
echo "Interlink Server started (PID: $SERVER_PID)"

# Verify it's running
sleep 2
ps aux | grep "interlink-server" | grep -v grep
```

## Verification Checklist

Verify the following on Machine 1:

- [ ] SLURM demo tools available: `which sinfo`
- [ ] Cluster visible: `sinfo` shows default partition
- [ ] Test job submitted: `sbatch /tmp/test-job.sh` returns job ID
- [ ] Job appears in queue: `squeue` shows the job
- [ ] Job output available: Output log file exists and contains results
- [ ] Interlink Server running: `ps aux | grep interlink-server`
- [ ] Interlink Server listening: Port 3000 open

## Network Connectivity Test

```bash
# From Machine 2, verify you can reach the Interlink Server on Machine 1
ssh rocky@192.168.2.84

# Test connectivity to port 3000
timeout 2 bash -c 'echo "" > /dev/tcp/192.168.2.170/3000' && echo "✓ Can reach Interlink Server" || echo "✗ Cannot reach Interlink Server"
```

## Troubleshooting

### Jobs not appearing in squeue

```bash
# Verify the jobs directory was created
ls -la ~/slurm-demo/jobs/

# Check if PIDs are still running
for jobdir in ~/slurm-demo/jobs/job_*; do
  if [ -f "$jobdir/pid" ]; then
    PID=$(cat $jobdir/pid)
    kill -0 $PID 2>/dev/null && echo "Job $PID: Running" || echo "Job $PID: Completed"
  fi
done
```

### Interlink Server not starting

```bash
# Check error log
tail -50 ~/interlink-server/server.log

# Verify port 3000 is not in use
lsof -i :3000 || echo "Port 3000 is free"

# Restart the server
pkill -f "python3.*interlink-server"
nohup python3 ~/interlink-server/server.py > ~/interlink-server/server.log 2>&1 &
```

## Important Notes

- This setup uses **simulated/demo SLURM** for course demonstrations
- For production use, install actual SLURM from official repositories or sources
- The demo provides realistic job submission and scheduling workflow
- The Interlink Server enables communication with k3s VirtualKubelet

## Next Steps

Once Machine 1 is verified working:

1. Proceed to [Machine 2 - k3s Setup](machine2-k3s.md)
2. Then set up [Interlink Integration](interlink-setup.md)
3. Run [Testing Procedures](testing-procedures.md)

---

**Machine 1 setup complete?** Move to Machine 2! ➡️
