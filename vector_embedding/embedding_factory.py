from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging
import json

from config import settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingProvider(ABC):
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generate a vector embedding for a given text."""
        pass

class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str):
        logger.info(f"Loading Local Embedding Model: {model_name}")
        # Note: If no GPU is available, this will fallback to CPU. 
        # sentence-transformers handles this automatically.
        self.model = SentenceTransformer(model_name)
        
    def generate_embedding(self, text: str) -> List[float]:
        # For intfloat/multilingual-e5-base, the convention is to prepend "passage: "
        if "e5" in settings.local_model_name:
            text = f"passage: {text}"
            
        vector = self.model.encode(text, normalize_embeddings=True)
        # Convert NumPy array to standard Python list
        return vector.tolist()

class EmbeddingFactory:
    """Factory to fetch the active embedding provider."""
    _instance: EmbeddingProvider = None

    @classmethod
    def get_provider(cls) -> EmbeddingProvider:
        if cls._instance is not None:
            return cls._instance
            
        if settings.embedding_provider.lower() == "local":
            cls._instance = LocalEmbeddingProvider(settings.local_model_name)
        else:
            raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}.")
            
        return cls._instance

def format_product_text(product: Any) -> str:
    """
    Format the product data into a single descriptive string to be embedded.
    """
    parts = []
    
    if hasattr(product, "title") and product.title:
        #parts.append(f"Titre: {product.title}")
        parts.append(f"Title: {product.title}")
    
    if hasattr(product, "brand") and product.brand:
        #parts.append(f"Marque: {product.brand}")
        parts.append(f"Brand: {product.brand}")
        
    if hasattr(product, "category") and product.category:
        #parts.append(f"Catégorie: {product.category}")
        parts.append(f"Category: {product.category}")
        
    if hasattr(product, "specifications") and product.specifications:
        # Convert specs to a clean readable format (e.g. key1: value1, key2: value2)
        specs = json.loads(product.specifications) if isinstance(product.specifications, str) else product.specifications
        spec_text = ", ".join(f"{k}: {v}" for k, v in specs.items())
        #parts.append(f"Spécifications: {spec_text}")
        parts.append(f"Specifications: {spec_text}")
    
    if hasattr(product, "description") and product.description:
        #parts.append(f"Description: {product.description}")
        parts.append(f"Description: {product.description}")
    
    if hasattr(product, "metadata") and product.metadata:
        metadata = product.metadata if isinstance(product.metadata, dict) else json.loads(product.metadata)
        metadata_text = ", ".join(f"{k}: {v}" for k, v in metadata.items())
        #parts.append(f"Métadonnées: {metadata_text}")
        parts.append(f"Metadata: {metadata_text}")
        
    return " \n".join(parts)
