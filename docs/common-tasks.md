# Common Tasks Reference

This document provides quick references for common Linux tasks you may need during the setup process.

## SSH and Remote Access

### Connect to a Machine

```bash
# Using password (if SSH keys not set up)
ssh rocky@192.168.2.170

# Using SSH key
ssh -i ~/.ssh/id_ed25519 rocky@192.168.2.170

# Set default for simpler connections
ssh rocky@slurm-machine
```

### Copy Files Between Machines

```bash
# Copy FROM remote TO local
scp -r rocky@192.168.2.170:/path/on/remote /local/path

# Copy FROM local TO remote
scp -r /local/path rocky@192.168.2.170:/path/on/remote

# Example: Copy SLURM config from Machine 1 to local
scp rocky@slurm-machine:/etc/slurm/slurm.conf ~/
```

### Edit Remote Files

```bash
# Using nano
ssh rocky@192.168.2.170 'nano /etc/slurm/slurm.conf'

# Using vim
ssh rocky@192.168.2.170 'vim /etc/slurm/slurm.conf'

# Or mount the directory locally (if rsync installed)
sshfs rocky@192.168.2.170:/etc /mnt/remote-etc
```

## Firewall Management

### Check Firewall Status

```bash
# Check if firewalld is running
sudo systemctl status firewalld

# List all open ports
sudo firewall-cmd --list-all

# List only ports
sudo firewall-cmd --list-ports
```

### Open/Close Ports

```bash
# Open a port temporarily (until reboot)
sudo firewall-cmd --add-port=6443/tcp

# Open a port permanently
sudo firewall-cmd --permanent --add-port=6443/tcp

# After permanent changes, reload firewall
sudo firewall-cmd --reload

# Close a port
sudo firewall-cmd --remove-port=6443/tcp
sudo firewall-cmd --permanent --remove-port=6443/tcp
```

### Add Services to Firewall

```bash
# Add a service (permanently)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh

# Reload to apply
sudo firewall-cmd --reload
```

### Temporarily Disable Firewall (for debugging)

```bash
# Stop firewall temporarily
sudo systemctl stop firewalld

# Disable permanently (NOT recommended)
sudo systemctl disable firewalld
```

## User and Permissions

### Add User to Sudo Group

```bash
# Add user to wheel group (which has sudo access)
sudo usermod -aG wheel username

# Verify the user can sudo
sudo -u username sudo whoami
```

### Change File Permissions

```bash
# Make file executable
chmod +x filename

# Change ownership
sudo chown user:group filename

# Change permissions recursively
sudo chmod -R 755 /directory
sudo chown -R user:group /directory
```

### Become Another User

```bash
# Switch to root
sudo su -

# Switch to another user
sudo su - username
```

## System Information

### Check System Resources

```bash
# CPU information
lscpu
nproc

# Memory information
free -h
cat /proc/meminfo

# Disk information
df -h
du -sh /directory

# System uptime
uptime

# Network interfaces
ip addr show
ip route show
```

### Check System Logs

```bash
# View recent system logs
journalctl -n 50

# Follow log in real-time
journalctl -f

# View logs for specific service
journalctl -u sshd -n 50

# View errors
journalctl -p err -n 50
```

## Network Testing

### Ping and Connectivity

```bash
# Ping a host
ping -c 5 192.168.2.84

# Check DNS resolution
nslookup k3s-machine
dig k3s-machine

# Trace route
traceroute 192.168.2.170
```

### Port Connectivity

```bash
# Check if a port is open
telnet 192.168.2.170 6817

# Using netcat (if available)
nc -zv 192.168.2.170 6817

# Check listening ports
sudo netstat -tlnp
ss -tlnp

# Specific service
ss -tlnp | grep sshd
```

### Network Interface Configuration

```bash
# Show all interfaces
ip addr show
ifconfig

# Show IP routes
ip route show

# Test DNS
cat /etc/resolv.conf
```

## Service Management

### Start/Stop/Restart Services

```bash
# Check service status
sudo systemctl status sshd

# Start a service
sudo systemctl start sshd

# Stop a service
sudo systemctl stop sshd

# Restart a service
sudo systemctl restart sshd

# Enable service to auto-start on boot
sudo systemctl enable sshd

# Disable auto-start
sudo systemctl disable sshd
```

### View Service Logs

```bash
# Real-time logs for a service
journalctl -u sshd -f

# Recent 50 lines
journalctl -u sshd -n 50

# Since last boot
journalctl -u sshd -b

# For specific time range
journalctl -u sshd --since "2024-01-01" --until "2024-01-02"
```

## Package Management

### Install/Update/Remove Packages

```bash
# Update package list
sudo dnf update

# Install a package
sudo dnf install package-name

# Install multiple packages
sudo dnf install package1 package2 package3

# Remove a package
sudo dnf remove package-name

# Search for a package
sudo dnf search package-name

# Show package info
sudo dnf info package-name
```

### Install Groups

```bash
# List available groups
sudo dnf grouplist

# Install a group
sudo dnf groupinstall "Development Tools"

# Remove a group
sudo dnf groupremove "Development Tools"
```

## File Operations

### View File Content

```bash
# View entire file
cat /etc/hostname

# View first N lines
head -20 /var/log/messages

# View last N lines
tail -20 /var/log/messages

# Follow file as it updates
tail -f /var/log/syslog

# Search within file
grep "error" /var/log/messages

# Count lines
wc -l /var/log/messages
```

### Edit Files

```bash
# Using nano (simpler editor)
nano /etc/hostname

# Using vim (advanced editor)
vim /etc/hostname

# Quick edit with sed
sed -i 's/oldtext/newtext/g' /path/to/file

# Append to file
echo "new line" >> /path/to/file

# Prepend to file
sed -i '1i\new line' /path/to/file
```

## Environment Variables

### View Environment Variables

```bash
# Show all variables
env

# Show specific variable
echo $PATH
echo $HOME

# Show all shell variables
set
```

### Set Environment Variables

```bash
# Temporary (only for current session)
export VARIABLE_NAME="value"

# Permanent (add to ~/.bashrc or ~/.bash_profile)
echo 'export VARIABLE_NAME="value"' >> ~/.bashrc
source ~/.bashrc
```

## Process Management

### View Running Processes

```bash
# Simple list
ps aux

# Tree view
ps auxf

# Real-time monitoring
top

# Enhanced monitoring
htop

# Search for process
ps aux | grep slurmctld
```

### Kill Processes

```bash
# Find process ID
ps aux | grep process-name

# Kill by PID
kill 1234

# Force kill
kill -9 1234

# Kill all processes matching name
pkill process-name

# Kill all matching with signal
pkill -9 process-name
```

## Disk and Storage

### Check Disk Usage

```bash
# Filesystem overview
df -h

# Directory size
du -sh /directory

# Top-level directories
du -sh /*

# Find large files
find / -size +1G -type f
```

### Create and Format Partitions (if needed)

```bash
# List partitions
sudo fdisk -l

# Partition a disk (interactive)
sudo fdisk /dev/sdb

# Format a partition
sudo mkfs.ext4 /dev/sdb1

# Mount a partition
sudo mount /dev/sdb1 /mnt/point

# Unmount
sudo umount /mnt/point
```

## Useful One-Liners

### Check Service Running and Restart if Down

```bash
sudo systemctl is-active sshd || sudo systemctl start sshd
```

### Monitor Log Changes in Real-Time

```bash
tail -f /var/log/messages | grep ERROR
```

### Check if Port is Open on Machine

```bash
ss -tlnp | grep :6817
```

### Find All Config Files Modified Today

```bash
find /etc -type f -mtime 0
```

### Compress and Archive Directory

```bash
tar -czf backup.tar.gz /directory
```

### Extract Archive

```bash
tar -xzf backup.tar.gz
```

## Troubleshooting Commands

### General Troubleshooting Workflow

```bash
# 1. Check system resources
free -h && df -h && uptime

# 2. Check network connectivity
ping 192.168.2.84 && ss -tlnp

# 3. Check service status
sudo systemctl status service-name

# 4. View logs
journalctl -u service-name -n 50

# 5. Check for errors
dmesg | tail -20
```

### Emergency Mode

```bash
# If system won't boot normally, get emergency shell:
# At boot, append to kernel parameters: systemd.unit=emergency.target
# Then repair filesystem
sudo fsck /dev/sda1
```

---

For more detailed information on any command, use the `man` command:
```bash
man command-name
```

For quick help on a command:
```bash
command-name --help
```

---

**Back to main guide?** Go to [README](../README.md)
