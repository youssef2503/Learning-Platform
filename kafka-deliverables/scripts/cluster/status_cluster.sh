
# ==============================
# Check Zookeeper & Kafka status
# ==============================

echo "===== ZOOKEEPER STATUS ====="
sudo systemctl status zookeeper --no-pager || echo "[ERROR] Zookeeper not running!"

echo ""
echo "===== KAFKA STATUS ====="
sudo systemctl status kafka --no-pager || echo "[ERROR] Kafka not running!"

