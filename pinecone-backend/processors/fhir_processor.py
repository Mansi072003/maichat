# processors/fhir_processor.py - FHIR data processing logic
import uuid
from utils.logger import get_logger
from services import RedisService, PineconeService, EmbeddingService

logger = get_logger(__name__)

class FHIRProcessor:
    """Processor for FHIR medical data"""
    
    def __init__(self):
        self.redis_service = RedisService()
        self.pinecone_service = PineconeService()
        self.embedding_service = EmbeddingService()
    
    def initialize(self):
        """Initialize all services"""
        try:
            self.redis_service.initialize()
            self.pinecone_service.initialize()
            self.embedding_service.initialize()
            logger.info("FHIR processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FHIR processor: {e}")
            raise
    
    def process_message(self, message_data: dict) -> bool:
        """
        Process a single FHIR message in the new format.
        Expected format: {patientId, practitionerId, resourceType, resourceId, text}
        
        Args:
            message_data: FHIR message dictionary
            
        Returns:
            Success status
        """
        try:
            # Extract and validate data from new format
            patient_id = message_data.get("patientId")
            practitioner_id = message_data.get("practitionerId") 
            resource_type = message_data.get("resourceType")
            resource_id = message_data.get("resourceId")
            text_content = message_data.get("text")
            
            # Validate required fields
            if not patient_id:
                logger.warning("Missing patientId in message")
                return False
            
            if not text_content:
                logger.warning("Missing text content in message")
                return False
            
            if not resource_id:
                resource_id = f"unknown-{uuid.uuid4()}"
            
            logger.info(f"Processing record for patient: {patient_id}, resourceType: {resource_type}")
            
            # Generate embedding
            embedding_vector = self.embedding_service.generate_embedding(text_content)
            
            # Store in Pinecone with new structure
            success = self.pinecone_service.upsert_vector(
                patient_id=patient_id,
                practitioner_id=practitioner_id,
                resource_type=resource_type,
                resource_id=resource_id,
                embedding_vector=embedding_vector,
                text_content=text_content
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing FHIR message: {e}")
            return False
    
    def health_check(self) -> dict:
        """Check health of all services"""
        return {
            "redis": self.redis_service.health_check(),
            "pinecone": self.pinecone_service.health_check(),
            "embedding": self.embedding_service.health_check()
        }