# services/redis_service.py - Redis connection and operations service
import redis
import json
import time
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class RedisService:
    """Service for Redis connection and queue operations"""
    
    def __init__(self):
        self.client = None
        
    def initialize(self):
        """Initialize Redis connection"""
        try:
            self.client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD,
                db=config.REDIS_DB,
                socket_connect_timeout=10,
                socket_timeout=30,  # Increased from 10 to 30 seconds
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True
            )
            self.client.ping()
            logger.info("Successfully connected to Redis")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def get_message(self, queue_name: str, timeout: int = 30):
        """
        Get a message from Redis queue (blocking).
        
        Args:
            queue_name: Name of the queue
            timeout: Timeout in seconds
            
        Returns:
            Message data or None if timeout
        """
        try:
            result = self.client.brpop(queue_name, timeout=timeout)
            if result is None:
                return None
                
            _, message_json = result
            return json.loads(message_json)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            return None
        except redis.exceptions.TimeoutError as e:
            logger.debug(f"Redis timeout waiting for message (this is normal): {e}")
            return None
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Redis connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading from Redis: {e}")
            raise
    
    def reconnect(self):
        """Attempt to reconnect to Redis"""
        try:
            self.initialize()
        except Exception as e:
            logger.error(f"Failed to reconnect to Redis: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            self.client.ping()
            return True
        except Exception:
            return False