
# ==========================
# Start Kafka broker service
# ==========================

echo "[INFO] Starting Kafka broker service..."
sudo systemctl start kafka

echo "[INFO] Kafka status:"
sudo systemctl status kafka --no-pager
