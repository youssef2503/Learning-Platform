

# ===========================================
# Describe all project topics
# ===========================================

BOOTSTRAP_SERVER="<BROKER_HOST>:9092"

if [ "$BOOTSTRAP_SERVER" = "<BROKER_HOST>:9092" ]; then
  echo "[ERROR] Please edit BOOTSTRAP_SERVER in this script before running."
  exit 1
fi

KAFKA_BIN="/opt/kafka/bin"

TOPICS=(
  "document.uploaded"
  "document.processed"
  "notes.generated"
  "quiz.requested"
  "quiz.generated"
  "audio.transcription.requested"
  "audio.transcription.completed"
  "audio.generation.requested"
  "audio.generation.completed"
  "chat.message"
)

for t in "${TOPICS[@]}"; do
  echo "=============================="
  echo "Topic: $t"
  $KAFKA_BIN/kafka-topics.sh \
    --bootstrap-server "$BOOTSTRAP_SERVER" \
    --describe \
    --topic "$t"
done
