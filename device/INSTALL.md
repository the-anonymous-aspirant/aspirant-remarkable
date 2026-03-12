# reMarkable Device Sync Setup

This guide sets up automatic daily sync from your reMarkable Paper Pro to the aspirant-online server.

## Prerequisites

- reMarkable Paper Pro with SSH access enabled
- aspirant-online server running with the remarkable service
- SSH key from the remarkable service added to the reMarkable (see main setup)
- Server accessible from the reMarkable's network

## Step 1: Copy Files to Device

Connect to the reMarkable via SSH and copy the sync script:

```bash
# From your computer (replace SERVER_IP with your server's IP)
scp remarkable/device/sync-to-server.sh root@10.11.99.1:/home/root/sync-to-server.sh
scp remarkable/device/remarkable-sync.service root@10.11.99.1:/etc/systemd/system/
scp remarkable/device/remarkable-sync.timer root@10.11.99.1:/etc/systemd/system/
```

## Step 2: Configure Server Address

SSH into the reMarkable and edit the service file:

```bash
ssh root@10.11.99.1

# Edit the service to set your server's address
vi /etc/systemd/system/remarkable-sync.service

# Update these lines:
# Environment=SYNC_SERVER_HOST=your-server-ip-or-hostname
# Environment=SYNC_SERVER_PORT=8085
# Environment=SYNC_SERVER_DATA_PATH=/data/remarkable
```

## Step 3: Generate SSH Key on Device

The reMarkable needs an SSH key to authenticate with your server:

```bash
# On the reMarkable
ssh-keygen -t ed25519 -f /home/root/.ssh/id_ed25519 -N ""

# Copy the public key to your server
cat /home/root/.ssh/id_ed25519.pub
# Add this key to ~/.ssh/authorized_keys on the server
```

## Step 4: Test Connectivity

Test that the reMarkable can reach the server:

```bash
# Test SSH
ssh -i /home/root/.ssh/id_ed25519 root@your-server-ip "echo ok"

# Test sync script manually
chmod +x /home/root/sync-to-server.sh
/home/root/sync-to-server.sh
```

## Step 5: Enable Timer

```bash
# Reload systemd
systemctl daemon-reload

# Enable and start the timer
systemctl enable remarkable-sync.timer
systemctl start remarkable-sync.timer

# Verify
systemctl status remarkable-sync.timer
systemctl list-timers | grep remarkable
```

## Step 6: Verify

```bash
# Check timer status
systemctl status remarkable-sync.timer

# Check last run
systemctl status remarkable-sync.service

# View logs
journalctl -u remarkable-sync.service -n 50

# Manual trigger
systemctl start remarkable-sync.service
```

## Troubleshooting

**Timer not firing:** Check `systemctl list-timers` and verify the timer is active. The `Persistent=true` flag means missed runs (e.g., device was off at midnight) will execute on next wake.

**SSH connection fails:** Verify the SSH key is correct and the server is reachable. Try `ssh -v -i /home/root/.ssh/id_ed25519 root@server-ip` for verbose output.

**rsync fails:** Ensure rsync is available on both the device and server. The reMarkable includes rsync by default.

**xochitl doesn't see new files:** The `SIGUSR1` signal should trigger file discovery. If not, restart xochitl manually: `systemctl restart xochitl`.

**Battery path not found:** The battery sysfs path varies by device revision. Check `ls /sys/class/power_supply/` to find the correct path and update the script if needed.
