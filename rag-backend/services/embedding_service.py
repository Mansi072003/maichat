# services/embedding_service.py
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from typing import List, Union
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class EmbeddingService:
    """Service for generating embeddings using Clinical BERT"""
    
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.model_name = config.EMBEDDING_MODEL_NAME
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    async def initialize(self):
        """Initialize the embedding model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Embedding model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a 768-dimensional embedding for given text using Clinical BERT.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding
        """
        if not self.model or not self.tokenizer:
            raise ValueError("Embedding model not initialized. Call initialize() first.")
        
        try:
            # Tokenize input text
            encoded_input = self.tokenizer(
                text,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors='pt'
            )
            
            # Move inputs to device
            encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}
            
            # Generate embedding
            with torch.no_grad():
                output = self.model(**encoded_input)
            
            # Extract [CLS] token embedding (sentence representation)
            embedding = output.last_hidden_state[:, 0, :].squeeze()
            
            # Convert to numpy and then to list
            if embedding.dim() > 1:
                embedding = embedding[0]  # Handle batch dimension
                
            embedding_list = embedding.cpu().numpy().tolist()
            
            logger.debug(f"Generated embedding of dimension {len(embedding_list)}")
            return embedding_list
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding lists
        """
        if not self.model or not self.tokenizer:
            raise ValueError("Embedding model not initialized. Call initialize() first.")
        
        try:
            embeddings = []
            
            # Process in batches to manage memory
            batch_size = 8
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Tokenize batch
                encoded_inputs = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors='pt'
                )
                
                # Move to device
                encoded_inputs = {k: v.to(self.device) for k, v in encoded_inputs.items()}
                
                # Generate embeddings
                with torch.no_grad():
                    outputs = self.model(**encoded_inputs)
                
                # Extract [CLS] token embeddings
                batch_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                
                # Convert to list of lists
                for embedding in batch_embeddings:
                    embeddings.append(embedding.tolist())
            
            logger.info(f"Generated {len(embeddings)} embeddings in batch")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise
    
    def get_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Cosine similarity score
        """
        try:
            emb1 = np.array(embedding1)
            emb2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(emb1, emb2)
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    async def health_check(self) -> bool:
        """Check if the embedding service is healthy"""
        try:
            if not self.model or not self.tokenizer:
                return False
            
            # Test with a simple embedding
            test_embedding = self.generate_embedding("Health check test")
            return len(test_embedding) > 0
            
        except Exception as e:
            logger.error(f"Embedding service health check failed: {e}")
            return False
