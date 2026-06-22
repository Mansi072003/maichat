# main.py - Main entry point for FHIR data consumer
import time
import redis.exceptions
from utils.logger import get_logger
from processors import FHIRProcessor
import config

logger = get_logger(__name__)

def main():
    """Main entry point"""
    try:
        # Validate configuration
        config.validate_config()
        
        # Create and initialize processor
        processor = FHIRProcessor()
        processor.initialize()
        
        # Main consumer loop
        queue_name = 'fhir_data'
        logger.info(f"Starting FHIR data consumer on queue: '{queue_name}'")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Get message from Redis
                logger.debug("Waiting for messages...")
                message_data = processor.redis_service.get_message(queue_name, timeout=30)
                logger.debug("No messages received in 30 seconds, continuing...",message_data)
                if message_data is None:
                    logger.debug("No messages received in 30 seconds, continuing...")
                    continue
                
                # Process the message
                success = processor.process_message(message_data)
                
                if success:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Too many consecutive errors ({consecutive_errors}), sleeping...")
                        time.sleep(30)
                        consecutive_errors = 0
                
            except redis.exceptions.TimeoutError:
                # Timeout is normal when no messages in queue
                logger.debug("Redis timeout (no messages), continuing...")
                continue
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Redis connection error in consumer loop: {e}")
                
                # Try to reconnect Redis
                try:
                    processor.redis_service.reconnect()
                    logger.info("Successfully reconnected to Redis")
                    consecutive_errors = 0
                except Exception:
                    logger.error("Failed to reconnect to Redis")
                    consecutive_errors += 1
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, exiting...")
                    break
                
                time.sleep(10)
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")
                consecutive_errors += 1
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, exiting...")
                    break
                
                time.sleep(10)
            
            # Brief pause to prevent tight loops
            time.sleep(0.1)
        
        logger.info("FHIR data consumer stopped")
        
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())