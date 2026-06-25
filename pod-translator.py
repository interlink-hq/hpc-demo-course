#!/usr/bin/env python3
"""
Pod-to-SLURM Translator

Watches Kubernetes for pods scheduled to virtual-kubelet node.
When found, translates pod spec to sbatch job and submits to SLURM.

Usage:
  KUBECONFIG=/etc/rancher/k3s/k3s.yaml python3 pod-translator.py \
    --machine1=192.168.2.170 \
    --slurm-user=rocky
"""

import os
import sys
import json
import subprocess
import time
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


class PodTranslator:
    def __init__(self, machine1_ip, slurm_user="rocky", kubeconfig=None):
        self.machine1 = machine1_ip
        self.slurm_user = slurm_user
        self.kubeconfig = kubeconfig or os.getenv('KUBECONFIG')
        self.tracked_pods = set()  # Track which pods we've already processed
        
        if not self.kubeconfig:
            self.kubeconfig = str(Path.home() / '.kube' / 'config')
        
        log.info(f"Pod Translator initialized")
        log.info(f"  Machine 1 (SLURM): {self.machine1}")
        log.info(f"  SLURM User: {self.slurm_user}")
        log.info(f"  kubeconfig: {self.kubeconfig}")
    
    def kubectl(self, *args):
        """Run kubectl command"""
        cmd = ['/usr/local/bin/k3s', 'kubectl'] + list(args)
        env = os.environ.copy()
        env['KUBECONFIG'] = self.kubeconfig
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                env=env
            )
            return result.stdout, result.returncode
        except subprocess.TimeoutExpired:
            log.error(f"kubectl command timed out: {' '.join(cmd)}")
            return "", 1
        except Exception as e:
            log.error(f"kubectl error: {e}")
            return "", 1
    
    def get_pods(self):
        """Get all pods as JSON"""
        output, code = self.kubectl('get', 'pods', '-A', '-o', 'json')
        if code == 0:
            return json.loads(output)
        return {'items': []}
    
    def pod_to_sbatch(self, pod_name, namespace, container):
        """Convert pod spec to sbatch job script"""
        image = container.get('image', 'busybox')
        cmd = container.get('command', [])
        args = container.get('args', [])
        
        # Build command
        full_cmd = cmd + args if cmd else []
        if not full_cmd:
            full_cmd = ['echo', f'Pod {namespace}/{pod_name} executed']
        
        command_str = ' '.join(full_cmd)
        
        # Create sbatch script
        job_name = f"{namespace}-{pod_name}"[:15]
        script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --time=00:30:00
#SBATCH --output=/tmp/interlink-%j.out
#SBATCH --error=/tmp/interlink-%j.err

echo "=== Pod {namespace}/{pod_name} ==="
echo "Container: {container.get('name', 'main')}"
echo "Image: {image}"
echo ""

{command_str}

echo ""
echo "Pod execution completed"
"""
        return script, job_name
    
    def submit_to_slurm(self, script, pod_id):
        """Submit sbatch script to SLURM on Machine 1"""
        try:
            # Use SSH to submit the job
            cmd = f'ssh -o ConnectTimeout=5 {self.slurm_user}@{self.machine1} sbatch'
            result = subprocess.run(
                cmd,
                shell=True,
                input=script,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and 'Submitted' in result.stdout:
                # Extract job ID
                try:
                    job_id = result.stdout.split()[-1]
                    log.info(f"✓ {pod_id} → SLURM job {job_id}")
                    return job_id
                except:
                    log.info(f"✓ {pod_id} submitted to SLURM")
                    return True
            else:
                log.error(f"✗ SLURM submission failed for {pod_id}")
                log.error(f"  Error: {result.stderr}")
                return None
        
        except subprocess.TimeoutExpired:
            log.error(f"SSH timeout submitting {pod_id}")
            return None
        except Exception as e:
            log.error(f"Error submitting {pod_id}: {e}")
            return None
    
    def process_pod(self, pod):
        """Process a single pod"""
        metadata = pod.get('metadata', {})
        spec = pod.get('spec', {})
        status = pod.get('status', {})
        
        pod_name = metadata.get('name', '')
        namespace = metadata.get('namespace', '')
        pod_id = f"{namespace}/{pod_name}"
        node_name = spec.get('nodeName', '')
        containers = spec.get('containers', [])
        phase = status.get('phase', '')
        
        # Only process pods scheduled to virtual-kubelet that haven't been processed
        if (node_name == 'virtual-kubelet' and 
            containers and 
            pod_id not in self.tracked_pods and
            phase in ['Pending', 'Unknown']):
            
            log.info(f"📦 Processing pod: {pod_id}")
            
            # Take first container
            container = containers[0]
            script, job_name = self.pod_to_sbatch(pod_name, namespace, container)
            
            job_id = self.submit_to_slurm(script, pod_id)
            if job_id:
                self.tracked_pods.add(pod_id)
                return True
        
        return False
    
    def watch_pods(self, interval=5):
        """Watch for pods and offload them"""
        log.info("Starting pod watch (Ctrl+C to stop)")
        log.info(f"Checking every {interval} seconds...")
        
        try:
            while True:
                pods_data = self.get_pods()
                
                for pod in pods_data.get('items', []):
                    self.process_pod(pod)
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            log.info("Shutting down...")
            sys.exit(0)
        except Exception as e:
            log.error(f"Watch loop error: {e}")
            time.sleep(interval)
            self.watch_pods(interval)


def main():
    parser = argparse.ArgumentParser(
        description='Pod-to-SLURM translator'
    )
    parser.add_argument(
        '--machine1',
        default=os.getenv('MACHINE1', '192.168.2.170'),
        help='Machine 1 IP (SLURM host)'
    )
    parser.add_argument(
        '--slurm-user',
        default='rocky',
        help='SLURM user account'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Watch interval (seconds)'
    )
    
    args = parser.parse_args()
    
    translator = PodTranslator(
        machine1_ip=args.machine1,
        slurm_user=args.slurm_user
    )
    
    translator.watch_pods(interval=args.interval)


if __name__ == '__main__':
    main()
