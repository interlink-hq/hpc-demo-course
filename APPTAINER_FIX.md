# Apptainer Installation & Pod Offload Fix

**Date:** June 25, 2026  
**Status:** ✅ RESOLVED - Pod offload fully operational with Apptainer

## Problem
Pod test failures on SLURM machine due to missing container runtime. The user reported:
> "apptainer is not installed in slurm machine. the pod tests are failing for missing singularity. fix it"

## Root Cause
The Interlink SLURM plugin requires a container runtime (Apptainer/Singularity) to execute Kubernetes container workloads on the SLURM backend. Without it, pod execution would fail.

## Solution Implemented

### 1. Apptainer Installation (Machine 1: 192.168.2.170)
```bash
# Install EPEL repository
sudo dnf install -y epel-release

# Install Apptainer
sudo dnf install -y apptainer

# Verify
apptainer --version
# Output: apptainer version 1.5.1-1.el9
```

### 2. SLURM Plugin Configuration
Updated `~/interlink/SlurmConfig.yaml`:
```yaml
SingularityPrefix: /usr/bin/apptainer
ImagePrefix: "docker://"
```

### 3. Component Restart
- Killed existing plugin and API processes
- Restarted SLURM plugin with updated config
- Restarted Interlink API (depends on plugin)

## Verification Results

| Component | Status | Details |
|-----------|--------|---------|
| Apptainer | ✅ | 1.5.1-1.el9 installed |
| SLURM Plugin | ✅ | Running, configured with Apptainer |
| Interlink API | ✅ | Running and communicating with plugin |
| Test Pod | ✅ | test-final-verify: 1/1 Running |
| SLURM Job | ✅ | Job 15361000 created and executed (CD status) |
| Pod Offload | ✅ | Complete end-to-end pipeline operational |

### Test Execution Results
```
Pod: test-final-verify
- Name: test-final-verify
- Namespace: default
- Node: interlink-node (virtual)
- IP: 127.0.0.1
- Phase: Running
- Ready: True
- Status: Successfully offloaded to SLURM

SLURM Job:
- JobID: 15361000
- Partition: default
- User: rocky
- Status: CD (Completed)
- Nodes: 1 (slurm-machine)
```

## Documentation Updates

### Files Modified
1. **phase1-slurm-setup.md**
   - Added "Install Apptainer (Required for Container Support)" section
   - Documented EPEL repository requirement
   - Explained critical importance for pod execution

2. **phase3-interlink-setup.md**
   - Added prerequisite note about Apptainer
   - Updated SlurmConfig.yaml with SingularityPrefix
   - Fixed SidecarURL to use machine IP (not localhost)
   - Added Step 3.5 for SLURM plugin startup

3. **DEPLOYMENT_STATUS.md**
   - Added Apptainer status to Machine 1 components table
   - Documented version and binary location
   - Explained role in pod execution

4. **CRITICAL_FINDINGS.md**
   - Added "Critical Prerequisites" section
   - Highlighted Apptainer as essential component
   - Added as Key Fix #4 with detailed explanation

## Pod Offload Pipeline (Verified Working)
```
1. Pod submitted to k3s ✓
2. Scheduler routes to interlink-node ✓
3. VirtualKubelet intercepts pod ✓
4. REST request to Interlink API (port 3000) ✓
5. API forwards to SLURM plugin (port 4000) ✓
6. Plugin converts pod spec to sbatch script ✓
7. Apptainer executes container via sbatch ✓
8. SLURM job completes ✓
9. Pod status updated to Running/Completed ✓
```

## Key Insights

1. **Apptainer is NOT optional** - It's a hard requirement for pod execution
2. **Container runtime role** - Converts pod containers to SLURM-executable format
3. **Docker compatibility** - Apptainer supports Docker images via OCI format
4. **Configuration critical** - Must set `SingularityPrefix: /usr/bin/apptainer`
5. **SLURM plugin dependency** - Plugin must start before API

## Testing Procedure

To verify pod offload is working:

```bash
# Create a test pod
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-offload
  namespace: default
spec:
  restartPolicy: Never
  nodeSelector:
    kubernetes.io/os: virtual-kubelet
  tolerations:
  - key: virtual-node.interlink/no-schedule
    operator: Equal
    value: "true"
  - key: node.kubernetes.io/not-ready
    operator: Exists
  - key: node.kubernetes.io/network-unavailable
    operator: Exists
  containers:
  - name: busybox
    image: busybox:latest
    command: ["sh", "-c"]
    args: ["echo 'Pod offloaded to SLURM'; sleep 3"]
EOF

# Verify pod status
kubectl get pod test-offload -o wide
# Expected: test-offload 1/1 Running on interlink-node

# Check SLURM queue
squeue -l
# Expected: New job with status R (running) or CD (completed)
```

## Git Commits

### Related Commits
- `f4fa845` - Install Apptainer and configure SLURM plugin for container support
- `50b218c` - Correct gRPC to REST in documentation and document k3s egress policy
- `8639db4` - Update docs: Full Interlink bridge now working end-to-end

## Conclusion

✅ **Pod offload is now fully operational with Apptainer support**
✅ **All documentation updated to reflect working system**
✅ **System tested and verified end-to-end on real hardware**

The Interlink bridge successfully bridges k3s Kubernetes and SLURM, enabling container workloads to be transparently offloaded from Kubernetes pods to HPC job queues.
