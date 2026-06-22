# services/embedding_service.py - Clinical BERT embedding service
import torch
from transformers import AutoTokenizer, AutoModel
from utils.logger import get_logger
import config

logger = get_logger(__name__)

class EmbeddingService:
    """Service for generating embeddings using Clinical BERT"""
    
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def initialize(self):
        """Initialize the Clinical BERT model"""
        try:
            logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL_NAME}")
            # Suppress the resume_download deprecation warning
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")
            
            self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL_NAME)
            self.model = AutoModel.from_pretrained(config.EMBEDDING_MODEL_NAME)
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Successfully loaded embedding model on {self.device}")
        except Exception as e:
            logger.error(f"Error loading Clinical BERT model: {e}")
            raise
    
    def generate_embedding(self, text: str) -> list:
        """
        Generate embedding for text using Clinical BERT.
        
        Args:
            text: Input text to embed
            
        Returns:
            768-dimensional embedding as list
        """
        try:
            # Tokenize input text
            encoded_input = self.tokenizer(
                text, 
                padding=True, 
                truncation=True, 
                max_length=512, 
                return_tensors='pt'
            )
            
            # Move to device
            encoded_input = {k: v.to(self.device) for k, v in encoded_input.items()}
            
            # Generate embedding
            with torch.no_grad():
                output = self.model(**encoded_input)
            
            # Extract [CLS] token embedding
            embedding = output.last_hidden_state[:, 0, :].squeeze()
            
            # Handle batch dimension
            if embedding.dim() > 1:
                embedding = embedding[0]
            
            # Convert to list
            embedding_list = embedding.cpu().numpy().tolist()
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check if embedding service is healthy"""
        try:
            # Try to generate a simple embedding
            test_embedding = self.generate_embedding("health check test")
            return len(test_embedding) == 768  # Clinical BERT embedding dimension
        except Exception:
            return False