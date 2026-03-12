# reMarkable Device Sync Setup

This guide documents the automatic daily sync setup between a reMarkable Paper Pro and the aspirant-cell server.

## Architecture

```
reMarkable Paper Pro (192.168.1.x, DHCP)
    │
    │  rsync over SSH (Dropbear dbclient)
    │  Port 41922 → aspirant@home.the-aspirant.com
    │
    ▼
aspirant-cell (home.the-aspirant.com)
    /data/aspirant/remarkable/
    ├── xochitl/      ← mirror of device notebooks
    └── to-device/    ← staging area for files to send to device
```

**Sync direction:** The reMarkable initiates all connections (push model). The server never connects to the device. This avoids issues with the device's DHCP-assigned IP changing.

**Schedule:** Daily at midnight UTC via systemd timer.

## Device Environment

- **OS:** Custom Linux (imx8mm-ferrari), root filesystem is **read-only**
- **Writable paths:** `/home` (encrypted), `/etc/systemd/system` (bind-mounted from `/home`), `/data`
- **SSH client:** Dropbear (`dbclient`), **not** OpenSSH — uses Dropbear key format
- **SSH server:** Dropbear (accepts connections with password from Settings)
- **Shell:** BusyBox ash + bash available
- **No `ssh-keygen`** — keys must be generated with `dropbearkey` or copied from elsewhere
- **BusyBox `head`** doesn't support `-N` flag, use `head -n N` instead
- **rsync:** Available at `/usr/bin/rsync` (v3.2.7)
- **wget:** Available (no curl)
- **Notebook data:** `/home/root/.local/share/remarkable/xochitl/`

## Files on the reMarkable

| Path | Purpose |
|------|---------|
| `/home/root/.ssh/aspirant_sync_dropbear` | Dropbear-format SSH private key for server auth |
| `/home/root/.ssh/authorized_keys` | Keys allowed to SSH into the device |
| `/home/root/sync-to-server.sh` | Sync script |
| `/home/root/sync.log` | Sync log file |
| `/etc/systemd/system/aspirant-sync.service` | systemd oneshot service |
| `/etc/systemd/system/aspirant-sync.timer` | systemd daily timer |

## Files on the Server

| Path | Purpose |
|------|---------|
| `/home/aspirant/.ssh/authorized_keys` | Contains the device's public key with `command=` restriction |
| `/home/aspirant/remarkable-sync-validate.sh` | Validates incoming rsync commands, restricts to `/data/aspirant/remarkable/` |
| `/data/aspirant/remarkable/xochitl/` | Mirror of device notebooks |
| `/data/aspirant/remarkable/to-device/` | Staging area — files here get pulled to device and deleted |
| `/data/aspirant/remarkable/sync-access.log` | Access log from the validation script |

## Server-Side Security

The device's SSH key is restricted in `authorized_keys` with:

```
command="/home/aspirant/remarkable-sync-validate.sh",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA... remarkable-sync
```

This means the key can **only**:
- Run rsync to/from `xochitl/` or `to-device/` under `/data/aspirant/remarkable/`
- No shell access, no port forwarding, no agent forwarding, no PTY

The validation script (`remarkable-sync-validate.sh`) additionally checks that:
- The SSH command starts with `rsync --server`
- The target path is `xochitl/` or `to-device/` (no path traversal)
- All access is logged to `sync-access.log`

## Setup From Scratch

### Prerequisites

- reMarkable Paper Pro with wifi and SSH enabled
- aspirant-cell server running with remarkable service
- SSH access to both devices

### Step 1: Find the reMarkable's password

On the device: **Settings > General > Help > About > Copyrights and licenses** — scroll to find the root SSH password. Note: this password **changes on every reboot**.

### Step 2: Connect to the reMarkable

From a machine on the same network:
```bash
# Find the device (it may not respond to ping)
# Scan for SSH on the local subnet:
for ip in 192.168.1.{1..254}; do
  (timeout 1 bash -c "echo -n '' > /dev/tcp/$ip/22" 2>/dev/null && echo "SSH open: $ip") &
done; wait

# Connect with sshpass (install if needed: apt install sshpass)
sshpass -p 'DEVICE_PASSWORD' ssh -o StrictHostKeyChecking=no root@DEVICE_IP
```

### Step 3: Generate SSH key on the device

The reMarkable uses Dropbear, not OpenSSH. Keys must be in Dropbear format:

```bash
# On the reMarkable:
dropbearkey -t ed25519 -f /home/root/.ssh/aspirant_sync_dropbear
# Note the "Public key portion is:" line — you need this for the server
```

### Step 4: Configure the server

On the aspirant-cell server:

```bash
# Create the validation script
cat > /home/aspirant/remarkable-sync-validate.sh << 'EOF'
#!/bin/bash
ALLOWED_BASE="/data/aspirant/remarkable"
LOG="${ALLOWED_BASE}/sync-access.log"
if [ -z "$SSH_ORIGINAL_COMMAND" ]; then
    echo "Interactive shell not allowed" >&2
    exit 1
fi
case "$SSH_ORIGINAL_COMMAND" in
    rsync\ --server*)
        DEST=$(echo "$SSH_ORIGINAL_COMMAND" | rev | cut -d' ' -f1 | rev)
        case "$DEST" in
            xochitl/*|to-device/*|xochitl/|to-device/|.)
                echo "$(date -Iseconds) ALLOWED: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
                cd "$ALLOWED_BASE" && exec $SSH_ORIGINAL_COMMAND
                ;;
            *)
                echo "$(date -Iseconds) DENIED path: $DEST cmd: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
                echo "Access denied: invalid path" >&2
                exit 1
                ;;
        esac
        ;;
    *)
        echo "$(date -Iseconds) DENIED non-rsync: $SSH_ORIGINAL_COMMAND" >> "$LOG" 2>/dev/null
        echo "Only rsync is allowed" >&2
        exit 1
        ;;
esac
EOF
chmod +x /home/aspirant/remarkable-sync-validate.sh

# Add the device's public key to authorized_keys (replace PUBKEY with the actual key)
echo 'command="/home/aspirant/remarkable-sync-validate.sh",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding PUBKEY' >> /home/aspirant/.ssh/authorized_keys

# Create data directories
mkdir -p /data/aspirant/remarkable/xochitl /data/aspirant/remarkable/to-device
chown -R aspirant:aspirant /data/aspirant/remarkable
```

### Step 5: Deploy sync script to the device

SCP the script from this repo or write it directly:

```bash
sshpass -p 'DEVICE_PASSWORD' scp device/sync-to-server.sh root@DEVICE_IP:/home/root/sync-to-server.sh
sshpass -p 'DEVICE_PASSWORD' ssh root@DEVICE_IP 'chmod +x /home/root/sync-to-server.sh'
```

The script (`sync-to-server.sh`) does:
1. `rsync -az` push: device xochitl → server `xochitl/`
2. `rsync -az --remove-source-files` pull: server `to-device/` → device xochitl
3. `killall -USR1 xochitl` if new files were pulled (triggers discovery)
4. `wget` POST device info (IP, battery) to remarkable service API

**Key config in the script:**
```
SERVER_HOST="home.the-aspirant.com"
SERVER_PORT="41922"
SSH_KEY="/home/root/.ssh/aspirant_sync_dropbear"
```

### Step 6: Create systemd units on the device

```bash
sshpass -p 'DEVICE_PASSWORD' ssh root@DEVICE_IP

# Service (oneshot)
cat > /etc/systemd/system/aspirant-sync.service << 'EOF'
[Unit]
Description=Sync reMarkable notebooks to aspirant-cell
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/home/root/sync-to-server.sh
TimeoutStartSec=600
EOF

# Timer (daily at midnight, persistent across reboots)
cat > /etc/systemd/system/aspirant-sync.timer << 'EOF'
[Unit]
Description=Daily sync of reMarkable notebooks

[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable aspirant-sync.timer
systemctl start aspirant-sync.timer
```

### Step 7: Test

```bash
# Manual run
systemctl start aspirant-sync.service
systemctl status aspirant-sync.service
cat /home/root/sync.log

# Check timer
systemctl status aspirant-sync.timer
```

## Gotchas

### Password changes on reboot
The reMarkable root password regenerates on every reboot. The sync script uses key-based auth and is unaffected, but if you need to SSH in manually you'll need the new password from Settings.

### Dropbear key format
OpenSSH keys (`ssh-keygen`) **do not work** with Dropbear's `dbclient`. The reMarkable uses Dropbear for both SSH client and server. Keys must be generated with `dropbearkey`. The public key output is in standard OpenSSH format and works in `authorized_keys` on the server.

### Read-only root filesystem
The root filesystem (`/`) is mounted read-only. Only `/home`, `/data`, and bind-mounted paths like `/etc/systemd/system` are writable. Scripts and keys go in `/home/root/`.

### Device discovery
The reMarkable does not respond to ICMP ping. To find it on the network, scan for port 22:
```bash
for ip in 192.168.1.{1..254}; do
  (timeout 1 bash -c "echo -n '' > /dev/tcp/$ip/22" 2>/dev/null && echo "SSH: $ip") &
done; wait
```

### BusyBox limitations
The reMarkable uses BusyBox for many utils. `head -N` doesn't work (use `head -n N`). `curl` is not available (use `wget`). `ssh-keygen` is not available (use `dropbearkey`).

### SSH port
The aspirant-cell SSH daemon listens on port **41922**, not the default 22.

### xochitl signal
`killall -USR1 xochitl` makes the xochitl process discover new files without a full restart. If this doesn't work, `systemctl restart xochitl` is the fallback (but interrupts the user).

### Battery path
The battery sysfs path is `/sys/class/power_supply/max77818_battery/capacity`. This may vary by device revision. Check `ls /sys/class/power_supply/` if battery reports "unknown".

## Maintenance

### View sync logs
```bash
# On the device:
cat /home/root/sync.log

# On the server (access log):
cat /data/aspirant/remarkable/sync-access.log
```

### Trigger manual sync
```bash
# From the device:
systemctl start aspirant-sync.service

# Or from the server (via the web UI):
# Click "Sync Now" on /admin/remarkable
# Note: this requires the server to reach the device, which only works on LAN
```

### Change sync schedule
Edit the timer on the device:
```bash
vi /etc/systemd/system/aspirant-sync.timer
# Change OnCalendar= to desired schedule
systemctl daemon-reload
systemctl restart aspirant-sync.timer
```
