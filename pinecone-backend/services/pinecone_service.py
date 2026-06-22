# services/pinecone_service.py - Pinecone operations service
import time
import uuid
from pinecone import Pinecone
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class PineconeService:
    """Service for Pinecone vector database operations"""
    
    def __init__(self):
        self.client = None
        self.index = None
        
    def initialize(self):
        """Initialize Pinecone connection"""
        try:
            self.client = Pinecone(api_key=config.PINECONE_API_KEY)
            self.index = self.client.Index(config.PINECONE_INDEX_NAME)
            logger.info(f"Successfully connected to Pinecone index: {config.PINECONE_INDEX_NAME}")
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {e}")
            raise
    
    def upsert_vector(self, patient_id: str, practitioner_id: str, resource_type: str, 
                     resource_id: str, embedding_vector: list, text_content: str) -> bool:
        """
        Upsert a vector to Pinecone with patient namespace.
        Follows the existing pinecone structure with patientID and text metadata.
        
        Args:
            patient_id: Patient identifier for namespace
            practitioner_id: Practitioner identifier 
            resource_type: FHIR resource type
            resource_id: Resource identifier
            embedding_vector: Vector embedding
            text_content: Original text content
            
        Returns:
            Success status
        """
        try:
            # Use resource_id as vector ID (matching existing structure like "rec-001", "rec-002")
            vector_id = resource_id
            
            # Prepare metadata following the existing structure
            # Some records have 'fhir_record' JSON, others have 'patientID' and 'text'
            # We'll use the simpler patientID + text format for consistency
            metadata = {
                "patientID": patient_id,
                "text": text_content,
                "resourceType": resource_type,
                "practitionerId": practitioner_id,
                "processed_at": time.time()
            }
            
            # Prepare upsert data
            upsert_data = [(vector_id, embedding_vector, metadata)]
            
            # Upsert to Pinecone with patient namespace (format: "patient-101")
            namespace = patient_id if patient_id.startswith('patient-') else f"patient-{patient_id}"
            self.index.upsert(vectors=upsert_data, namespace=namespace)
            
            logger.info(f"Successfully upserted vector for namespace '{namespace}' (ID: {vector_id})")
            return True
            
        except Exception as e:
            logger.error(f"Error upserting vector to Pinecone: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if Pinecone connection is healthy"""
        try:
            # Try to describe the index
            self.index.describe_index_stats()
            return True
        except Exception:
            return False