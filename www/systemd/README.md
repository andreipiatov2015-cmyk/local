# Autostart after reboot

1. Install unit:
   ```bash
   sudo cp /var/www/systemd/restart_astra.service /etc/systemd/system/restart_astra.service
   sudo systemctl daemon-reload
   ```
2. Enable autostart:
   ```bash
   sudo systemctl enable --now restart_astra.service
   ```
3. Check status/logs:
   ```bash
   systemctl status restart_astra.service
   journalctl -u restart_astra.service -b
   ```
