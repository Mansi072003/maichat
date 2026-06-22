# services/generation_service.py
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class GenerationService:
    """Service for generating responses using OpenAI's GPT models"""
    
    def __init__(self):
        self.client = None
        self.model_name = config.LLM_MODEL_NAME
        
    async def initialize(self):
        """Initialize OpenAI client"""
        try:
            logger.info("Initializing OpenAI client")
            if config.OPENAI_BASE_URL:
                self.client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
                logger.info(f"OpenAI client initialized with custom base URL: {config.OPENAI_BASE_URL}")
            else:
                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            logger.info(f"OpenAI client initialized with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    
    async def generate_answer(
        self,
        query: str,
        retrieved_context: List[Dict[str, Any]],
        short_term_context: List[Dict[str, str]],
        long_term_context: str,
        patient_id: str
    ) -> Dict[str, Any]:
        """
        Generate answer using retrieved context and conversation history.
        
        Args:
            query: User query
            retrieved_context: Context retrieved from Pinecone
            short_term_context: Recent chat history
            long_term_context: Summarized long-term context
            patient_id: Patient identifier
            
        Returns:
            Generated response with metadata
        """
        if not self.client:
            raise ValueError("Generation service not initialized. Call initialize() first.")
        
        try:
            logger.info(f"Generating answer for patient {patient_id}")
            
            # Build the prompt
            prompt = self._build_prompt(
                query=query,
                retrieved_context=retrieved_context,
                short_term_context=short_term_context,
                long_term_context=long_term_context,
                patient_id=patient_id
            )
            
            # Generate response
            response = self.client.chat.completions.create(
                model=self.model_name,  # gpt-4o is the newest model
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=config.GENERATION_TEMPERATURE,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content.strip()
            
            logger.info("Answer generated successfully")
            
            return {
                "answer": answer,
                "model_used": self.model_name,
                "context_sources": len(retrieved_context),
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                # TESTING: Additional fields for debugging (remove after testing)
                "prompt": prompt,
                "raw_response": answer
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                "answer": f"I apologize, but I encountered an error while processing your query: {str(e)}",
                "error": str(e)
            }
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the medical assistant"""
        return """You are an advanced medical AI assistant with access to patient medical records and conversation history. Your role is to:

1. Provide accurate, helpful medical information based solely on the provided patient records
2. Maintain context from previous conversations with this patient
3. Never fabricate or assume medical information not present in the records
4. Clearly state when information is not available in the provided records
5. Suggest consulting healthcare providers for medical decisions
6. Be empathetic and professional in your responses
7. Respect patient privacy and confidentiality

Guidelines:
- Base your responses on the provided medical records and context
- If asked about information not in the records, clearly state this limitation
- Use medical terminology appropriately but explain complex terms
- Consider the conversation history to provide contextually relevant responses
- Always recommend consulting healthcare providers for medical advice or decisions"""
    
    def _build_prompt(
        self,
        query: str,
        retrieved_context: List[Dict[str, Any]],
        short_term_context: List[Dict[str, str]],
        long_term_context: str,
        patient_id: str
    ) -> str:
        """Build the complete prompt for the LLM"""
        
        prompt_parts = []
        
        # Add patient context
        prompt_parts.append(f"Patient ID: {patient_id}")
        prompt_parts.append("")
        
        # Add long-term context if available
        if long_term_context and long_term_context.strip():
            prompt_parts.append("=== CONVERSATION SUMMARY (Long-term Context) ===")
            prompt_parts.append(long_term_context.strip())
            prompt_parts.append("")
        
        # Add short-term context (recent messages)
        if short_term_context:
            prompt_parts.append("=== RECENT CONVERSATION (Short-term Context) ===")
            for msg in short_term_context[-5:]:  # Last 5 messages for context
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.capitalize()}: {content}")
            prompt_parts.append("")
        
        # Add retrieved medical records
        if retrieved_context:
            prompt_parts.append("=== RELEVANT MEDICAL RECORDS ===")
            for i, context in enumerate(retrieved_context, 1):
                text = context.get("text", "")
                score = context.get("score", 0)
                prompt_parts.append(f"Record {i} (Relevance: {score:.2f}):")
                prompt_parts.append(text.strip())
                prompt_parts.append("")
        else:
            prompt_parts.append("=== MEDICAL RECORDS ===")
            prompt_parts.append("No relevant medical records found for this query.")
            prompt_parts.append("")
        
        # Add current query
        prompt_parts.append("=== CURRENT QUESTION ===")
        prompt_parts.append(query)
        prompt_parts.append("")
        
        prompt_parts.append("Please provide a helpful response based on the available information:")
        
        return "\n".join(prompt_parts)
    
    async def summarize_conversation(
        self,
        messages: List[Dict[str, str]],
        existing_summary: str = ""
    ) -> str:
        """
        Summarize a conversation for long-term context storage.
        
        Args:
            messages: List of message dictionaries
            existing_summary: Existing summary to build upon
            
        Returns:
            Condensed summary of the conversation
        """
        if not self.client:
            raise ValueError("Generation service not initialized. Call initialize() first.")
        
        try:
            logger.info("Summarizing conversation for long-term context")
            
            # Build conversation text
            conversation_text = []
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                conversation_text.append(f"{role.capitalize()}: {content}")
            
            # Create summarization prompt
            prompt_parts = []
            
            if existing_summary:
                prompt_parts.append("Previous Summary:")
                prompt_parts.append(existing_summary)
                prompt_parts.append("")
            
            prompt_parts.append("New Conversation to Summarize:")
            prompt_parts.extend(conversation_text)
            prompt_parts.append("")
            prompt_parts.append(
                "Please provide a concise summary of the key medical topics, "
                "patient concerns, and important information discussed. "
                "If there's a previous summary, integrate the new information appropriately."
            )
            
            prompt = "\n".join(prompt_parts)
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a medical conversation summarizer. Create concise, "
                        "accurate summaries of medical conversations that preserve key information."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=config.SUMMARIZATION_TEMPERATURE,
                max_tokens=500
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("Conversation summarized successfully")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing conversation: {e}")
            # Return existing summary if summarization fails
            return existing_summary or "Summary generation failed."
    
    async def health_check(self) -> bool:
        """Check if the generation service is healthy"""
        try:
            if not self.client:
                return False
            
            # Test with a simple generation
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
            
            return response.choices[0].message.content is not None
            
        except Exception as e:
            logger.error(f"Generation service health check failed: {e}")
            return False
