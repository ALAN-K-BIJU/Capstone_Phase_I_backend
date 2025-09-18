# core/redis_client.py
import redis
import os

# Get Redis connection details from environment variables, with defaults for local dev
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

print("Connecting to Redis...")
try:
    # `decode_responses=True` makes the client return strings instead of bytes
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    # Ping the server to check the connection
    redis_client.ping()
    print("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"FATAL: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Please ensure Redis is running.")
    print(f"Error: {e}")
    redis_client = None