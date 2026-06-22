# services/retrieval_service.py
import json
from typing import List, Dict, Any, Optional
from pinecone import Pinecone
from services.embedding_service import EmbeddingService
from services.mongodb_service import MongoDBService
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class RetrievalService:
    """Service for retrieving relevant documents from Pinecone"""
    
    def __init__(self, embedding_service: EmbeddingService, mongodb_service: MongoDBService):
        self.embedding_service = embedding_service
        self.mongodb_service = mongodb_service
        self.pinecone_client = None
        self.index = None
        self.index_name = config.PINECONE_INDEX_NAME
        
    async def initialize(self):
        """Initialize Pinecone client and index"""
        try:
            logger.info("Initializing Pinecone client")
            self.pinecone_client = Pinecone(api_key=config.PINECONE_API_KEY)
            self.index = self.pinecone_client.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise
    
    async def retrieve_context(
        self,
        query: str,
        patient_id: str = None,
        practitioner_id: str = None,
        top_k: int = None,
        similarity_threshold: float = None
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: User query
            patient_id: Patient ID for single patient namespace
            practitioner_id: Practitioner ID for multi-patient retrieval
            top_k: Number of results to retrieve
            similarity_threshold: Minimum similarity threshold
            
        Returns:
            Dictionary with retrieved contexts and metadata
        """
        if not self.index:
            raise ValueError("Retrieval service not initialized. Call initialize() first.")
        
        top_k = top_k or config.TOP_K_RETRIEVAL
        similarity_threshold = similarity_threshold or config.SIMILARITY_THRESHOLD
        
        try:
            if practitioner_id:
                # Handle practitioner query - retrieve from multiple patient namespaces
                return await self._retrieve_for_practitioner(
                    query, practitioner_id, top_k, similarity_threshold
                )
            elif patient_id:
                # Handle patient query - retrieve from single namespace
                return await self._retrieve_for_patient(
                    query, patient_id, top_k, similarity_threshold
                )
            else:
                return {
                    "contexts": [],
                    "sources": [],
                    "error": "No patient ID or practitioner ID provided for retrieval"
                }
                
        except Exception as e:
            logger.error(f"Error during context retrieval: {e}")
            return {
                "contexts": [],
                "sources": [],
                "error": f"Retrieval error: {str(e)}"
            }

    async def retrieve_for_session(self, query: str, session_id: str, top_k: int = None, similarity_threshold: float = None) -> Dict[str, Any]:
        """Session-aware retrieval that looks up the session -> patient and calls patient retrieval"""
        try:
            session = await self.mongodb_service.get_session(session_id)
            if not session:
                return {"contexts": [], "sources": [], "error": f"Session {session_id} not found"}
            patient_id = session.get("patient_id")
            return await self.retrieve_context(query=query, patient_id=patient_id, top_k=top_k, similarity_threshold=similarity_threshold)
        except Exception as e:
            logger.error(f"Error in retrieve_for_session: {e}")
            return {"contexts": [], "sources": [], "error": str(e)}

    async def _retrieve_for_patient(
        self,
        query: str,
        patient_id: str,
        top_k: int,
        similarity_threshold: float
    ) -> Dict[str, Any]:
        """Retrieve context for a single patient"""
        logger.info(f"Retrieving context for patient {patient_id}, query: {query[:50]}...")
        
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query)
        
        # Query Pinecone with patient namespace
        namespace = patient_id if patient_id.startswith('patient-') else f"patient-{patient_id}"
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=namespace
        )
        
        if not results.get("matches"):
            logger.info(f"No matches found for patient {patient_id}")
            return {
                "contexts": [],
                "sources": [],
                "message": "No relevant medical records found for this patient"
            }
        
        # Process results
        contexts, sources = self._process_pinecone_results(results, similarity_threshold)
        
        logger.info(f"Retrieved {len(contexts)} relevant contexts for patient {patient_id}")
        
        return {
            "contexts": contexts,
            "sources": sources,
            "total_matches": len(results["matches"]),
            "filtered_matches": len(contexts)
        }
    
    async def _retrieve_for_practitioner(
        self,
        query: str,
        practitioner_id: str,
        top_k: int,
        similarity_threshold: float
    ) -> Dict[str, Any]:
        """Retrieve context for all patients under a practitioner"""
        logger.info(f"Retrieving context for practitioner {practitioner_id}, query: {query[:50]}...")
        
        # Get practitioner's patient list from MongoDB
        patient_list = await self.mongodb_service.get_practitioner_patients(practitioner_id)
        
        if not patient_list:
            logger.warning(f"No patients found for practitioner {practitioner_id}")
            return {
                "contexts": [],
                "sources": [],
                "message": f"No patients found for practitioner {practitioner_id}"
            }
        
        logger.info(f"Found {len(patient_list)} patients for practitioner {practitioner_id}")
        
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query)
        
        all_contexts = []
        all_sources = []
        total_matches = 0
        
        # Query each patient's namespace
        for patient_id in patient_list:
            try:
                namespace = patient_id if patient_id.startswith('patient-') else f"patient-{patient_id}"
                
                # Query this patient's namespace
                results = self.index.query(
                    vector=query_embedding,
                    top_k=top_k // len(patient_list) + 1,  # Distribute top_k across patients
                    include_metadata=True,
                    namespace=namespace
                )
                
                if results.get("matches"):
                    total_matches += len(results["matches"])
                    
                    # Process results for this patient
                    contexts, sources = self._process_pinecone_results(results, similarity_threshold)
                    
                    # Add patient context info
                    for context in contexts:
                        context["patient_id"] = patient_id
                    
                    for source in sources:
                        source["patient_id"] = patient_id
                    
                    all_contexts.extend(contexts)
                    all_sources.extend(sources)
                    
            except Exception as e:
                logger.error(f"Error querying patient {patient_id} namespace: {e}")
                continue
        
        # Sort all contexts by relevance score
        all_contexts.sort(key=lambda x: x.get("score", 0), reverse=True)
        all_sources.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Limit to top_k results
        all_contexts = all_contexts[:top_k]
        all_sources = all_sources[:top_k]
        
        logger.info(f"Retrieved {len(all_contexts)} relevant contexts across {len(patient_list)} patients")
        
        return {
            "contexts": all_contexts,
            "sources": all_sources,
            "total_matches": total_matches,
            "filtered_matches": len(all_contexts),
            "patients_queried": len(patient_list),
            "practitioner_id": practitioner_id
        }
    
    def _process_pinecone_results(
        self,
        results: Dict[str, Any],
        similarity_threshold: float
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Process Pinecone query results into contexts and sources"""
        contexts = []
        sources = []
        
        for match in results["matches"]:
            # Check similarity threshold
            if match.get("score", 0) < similarity_threshold:
                continue
            
            metadata = match.get("metadata", {})
            
            # Extract context based on data structure
            context_text = self._extract_context_text(metadata)
            
            if context_text:
                contexts.append({
                    "text": context_text,
                    "score": match.get("score", 0),
                    "source_id": match.get("id", "unknown")
                })
                
                sources.append({
                    "id": match.get("id", "unknown"),
                    "score": match.get("score", 0),
                    "patient_id": metadata.get("patientID", "unknown")
                })
        
        return contexts, sources
    
    def _extract_context_text(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Extract readable text content from metadata.
        
        Args:
            metadata: Metadata from Pinecone match
            
        Returns:
            Extracted text or None
        """
        try:
            # Check if there's a direct text field
            if "text" in metadata:
                return metadata["text"]
            
            # Check if there's a FHIR record to parse
            if "fhir_record" in metadata:
                fhir_record_str = metadata["fhir_record"]
                if isinstance(fhir_record_str, str):
                    fhir_record = json.loads(fhir_record_str)
                else:
                    fhir_record = fhir_record_str
                
                # Extract text from FHIR record
                text_content = fhir_record.get("text", {})
                if isinstance(text_content, dict):
                    return text_content.get("div", "")
                return str(text_content)
            
            # Check for note field
            if "note" in metadata:
                return metadata["note"]
            
            # Fallback to serialized metadata
            return json.dumps(metadata, indent=2)
            
        except Exception as e:
            logger.error(f"Error extracting context text: {e}")
            return None
    
    async def search_similar_patients(
        self,
        query: str,
        exclude_patient_id: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for similar cases across all patients (for research purposes).
        
        Args:
            query: Search query
            exclude_patient_id: Patient ID to exclude from results
            top_k: Number of results to return
            
        Returns:
            List of similar cases from other patients
        """
        try:
            logger.info("Searching for similar cases across patients")
            
            query_embedding = self.embedding_service.generate_embedding(query)
            
            # Search across all namespaces (no namespace specified)
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k * 3,  # Get more to filter out excluded patient
                include_metadata=True
            )
            
            similar_cases = []
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})
                patient_id = metadata.get("patientID")
                
                # Skip excluded patient
                if patient_id == exclude_patient_id:
                    continue
                
                context_text = self._extract_context_text(metadata)
                if context_text:
                    similar_cases.append({
                        "patient_id": patient_id,
                        "text": context_text,
                        "score": match.get("score", 0),
                        "source_id": match.get("id", "unknown")
                    })
                
                if len(similar_cases) >= top_k:
                    break
            
            return similar_cases
            
        except Exception as e:
            logger.error(f"Error searching similar patients: {e}")
            return []
    
    async def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """
        Get a summary of available data for a patient.
        
        Args:
            patient_id: Patient ID
            
        Returns:
            Summary information about patient's data
        """
        try:
            # Query for patient's data without specific query
            namespace = patient_id if patient_id.startswith('patient-') else f"patient-{patient_id}"
            results = self.index.query(
                vector=[0.0] * 768,  # Dummy vector
                top_k=100,
                include_metadata=True,
                namespace=namespace
            )
            
            total_records = len(results.get("matches", []))
            
            # Analyze types of records
            record_types = {}
            for match in results.get("matches", []):
                metadata = match.get("metadata", {})
                # This would depend on how records are structured
                record_type = metadata.get("type", "unknown")
                record_types[record_type] = record_types.get(record_type, 0) + 1
            
            return {
                "patient_id": patient_id,
                "total_records": total_records,
                "record_types": record_types,
                "has_data": total_records > 0
            }
            
        except Exception as e:
            logger.error(f"Error getting patient summary: {e}")
            return {
                "patient_id": patient_id,
                "total_records": 0,
                "record_types": {},
                "has_data": False,
                "error": str(e)
            }
    
    async def health_check(self) -> bool:
        """Check if the retrieval service is healthy"""
        try:
            if not self.index:
                return False
            
            # Test with a simple query
            test_results = self.index.describe_index_stats()
            return test_results is not None
            
        except Exception as e:
            logger.error(f"Retrieval service health check failed: {e}")
            return False