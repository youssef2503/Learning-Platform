
# ==========================
# Start Zookeeper service
# ==========================

echo "[INFO] Starting Zookeeper service..."
sudo systemctl start zookeeper

echo "[INFO] Zookeeper status:"
sudo systemctl status zookeeper --no-pager
 