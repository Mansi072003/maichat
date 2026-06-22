# models/schemas.py
from pydantic import BaseModel, Field, ValidationError, model_validator
from typing import Optional, List, Any, Dict
from datetime import datetime

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    query: str = Field(..., description="User query/question", min_length=1, max_length=2000)
    
    patient_id: Optional[str] = Field(None, description="Patient identifier for context isolation", min_length=1)
    practitioner_id: Optional[str] = Field(None, description="Practitioner identifier for multi-patient access", min_length=1)
    
    session_id: Optional[str] = Field(default="default", description="Session identifier for conversation tracking")

    @model_validator(mode='after')
    def validate_ids(self) -> "ChatRequest":
        """Ensure exactly one of patient_id or practitioner_id is provided"""
        if not self.patient_id and not self.practitioner_id:
            raise ValueError("Either patient_id or practitioner_id must be provided")
        
        if self.patient_id and self.practitioner_id:
            raise ValueError("Cannot provide both patient_id and practitioner_id")
        
        return self

    class Config:
        # Pydantic v2 uses json_schema_extra instead of schema_extra
        json_schema_extra = {
            "examples": [
                {
                    "query": "What medications is the patient currently taking?",
                    "patient_id": "patient-123",
                    "session_id": "session-456"
                },
                {
                    "query": "Show me a summary of all my patients' recent visits",
                    "practitioner_id": "practitioner-456",
                    "session_id": "session-789"
                }
            ]
        }

class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    answer: str = Field(..., description="Generated answer from the RAG pipeline")
    session_id: Optional[str] = Field(default=None, description="Resolved session identifier (created or reused)")
    context_used: List[str] = Field(default=[], description="Snippets of context used in generation")
    sources: List[Dict[str, Any]] = Field(default=[], description="Source documents with metadata")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata about the response")
    # TESTING: Additional field for debugging (remove after testing)
    testing_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed testing information including context, prompts, and responses")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Based on the patient's medical records, they are currently taking Metformin 500mg twice daily for diabetes management.",
                "context_used": [
                    "Patient is prescribed Metformin 500mg BID for T2DM management...",
                    "Latest lab results show HbA1c of 7.2%, patient compliant with medications..."
                ],
                "sources": [
                    {
                        "id": "record-123",
                        "score": 0.89,
                        "patient_id": "patient-123"
                    }
                ],
                "metadata": {
                    "patient_id": "patient-123",
                    "retrieved_documents": 2,
                    "model_used": "gpt-4o"
                }
            }
        }

class HealthCheckResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Overall health status")
    services: Dict[str, bool] = Field(..., description="Health status of individual services")
    timestamp: datetime = Field(default_factory=datetime.now, description="Health check timestamp")

class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    practitioner_id: Optional[str] = Field(None, description="Practitioner identifier")
    session_id: Optional[str] = Field(default="default", description="Session identifier")
    history: List[Dict[str, Any]] = Field(..., description="Chat history messages")
    total_messages: int = Field(..., description="Total number of messages")

class PatientSummaryResponse(BaseModel):
    """Response model for patient summary"""
    patient_id: str = Field(..., description="Patient identifier")
    data_summary: Dict[str, Any] = Field(..., description="Summary of patient data in vector database")
    context_stats: Dict[str, Any] = Field(..., description="Chat context statistics")
    timestamp: datetime = Field(default_factory=datetime.now, description="Summary timestamp")

class PractitionerPatientsResponse(BaseModel):
    """Response model for practitioner's patients"""
    practitioner_id: str = Field(..., description="Practitioner identifier")
    patients: List[str] = Field(..., description="List of patient IDs under this practitioner")
    total_patients: int = Field(..., description="Total number of patients")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

class FHIRDataMessage(BaseModel):
    """Model for FHIR data messages in queue"""
    id: str = Field(..., description="Record identifier")
    patient_id: str = Field(..., description="Patient identifier", alias="patientID")
    note: str = Field(..., description="Clinical note content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="Message timestamp")
    resource_type: Optional[str] = Field(default="DocumentReference", description="FHIR resource type")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "encounter-789",
                "patientID": "patient-123", 
                "note": "Patient presented with chest pain. ECG normal. Prescribed aspirin.",
                "timestamp": "2024-01-15T10:30:00Z",
                "resource_type": "DocumentReference"
            }
        }

class ContextStats(BaseModel):
    """Model for context statistics"""
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    practitioner_id: Optional[str] = Field(None, description="Practitioner identifier")
    session_id: str = Field(default="default", description="Session identifier")
    message_count: int = Field(..., description="Number of messages in short-term context")
    has_long_term_summary: bool = Field(..., description="Whether long-term summary exists")
    max_short_term: int = Field(..., description="Maximum short-term messages before summarization")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")

class SimilarCase(BaseModel):
    """Model for similar patient cases"""
    patient_id: str = Field(..., description="Similar patient identifier")
    text: str = Field(..., description="Similar case text")
    score: float = Field(..., description="Similarity score")
    source_id: str = Field(..., description="Source document identifier")

class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")