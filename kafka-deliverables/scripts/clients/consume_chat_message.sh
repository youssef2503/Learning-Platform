#!/usr/bin/env bash

# ===========================================
# Simple console consumer for chat.message
# ===========================================

BOOTSTRAP_SERVER="<BROKER_HOST>:9092"
TOPIC_NAME="chat.message"
KAFKA_BIN="/opt/kafka/bin"

if [ "$BOOTSTRAP_SERVER" = "<BROKER_HOST>:9092" ]; then
  echo "[ERROR] Please edit BOOTSTRAP_SERVER in this script before running."
  exit 1
fi

echo "[INFO] Consuming messages from topic: $TOPIC_NAME"
echo "[INFO] Bootstrap server: $BOOTSTRAP_SERVER"
echo "------------------------------------------------------------"

$KAFKA_BIN/kafka-console-consumer.sh \
  --bootstrap-server "$BOOTSTRAP_SERVER" \
  --topic "$TOPIC_NAME" \
  --from-beginning
 