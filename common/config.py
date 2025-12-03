import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_kafka_servers():
    """
    Fetches Kafka servers from environment variables.
    If not found, defaults to localhost (for local testing).
    """
    servers_str = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    
    if servers_str:
        # Convert the string from .env to a list
        # Example: "10.0.30.1:9092,10.0.30.2:9092" -> ["10.0.30.1:9092", "10.0.30.2:9092"]
        return servers_str.split(",")
    
    # Default value if nothing is set in .env
    return ["localhost:9092"]

KAFKA_BOOTSTRAP_SERVERS = get_kafka_servers()