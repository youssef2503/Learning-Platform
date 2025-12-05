#!/usr/bin/env bash

# ===========================================
# Create all required topics for the project
# ===========================================

# CHANGE THIS before running:
BOOTSTRAP_SERVER="<BROKER_HOST>:9092"

if [ "$BOOTSTRAP_SERVER" = "<BROKER_HOST>:9092" ]; then
  echo "[ERROR] Please edit BOOTSTRAP_SERVER in this script before running."
  exit 1
fi

KAFKA_BIN="/opt/kafka/bin"

create_topic () {
  local topic_name=$1
  local partitions=$2
  local replication=$3

  echo "[INFO] Creating topic: $topic_name"
  $KAFKA_BIN/kafka-topics.sh \
    --bootstrap-server "$BOOTSTRAP_SERVER" \
    --create \
    --topic "$topic_name" \
    --partitions "$partitions" \
    --replication-factor "$replication" \
    || echo "[WARN] Topic $topic_name may already exist."
}

# Example: partitions=3, replication-factor=2
create_topic "document.uploaded"              
create_topic "document.processed"             
create_topic "notes.generated"               
create_topic "quiz.requested"                 
create_topic "quiz.generated"                  
create_topic "audio.transcription.requested"  
create_topic "audio.transcription.completed"   
create_topic "audio.generation.requested"     
create_topic "audio.generation.completed"     
create_topic "chat.message"                   

echo "[DONE] Topics creation script finished."
