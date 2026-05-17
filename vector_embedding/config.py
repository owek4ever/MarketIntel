from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    app_name: str = "Vector Embedding Service"
    debug: bool = False
    
    # Embedding Configuration
    embedding_provider: str = "local" # 'local' or 'openai' (ready for future use)
    
    # Use an excellent multilingual model that supports French/English with 768 dimensions.
    # Alternatives: 
    #   intfloat/multilingual-e5-base
    #   dangvantuan/sentence-camembert-large (French only)
    # local_model_name: str = "intfloat/multilingual-e5-base" 
    # local_model_name: str = "sentence-transformers/LaBSE"
    local_model_name: str = "sentence-transformers/xlm-r-100langs-bert-base-nli-stsb-mean-tokens"
    
    openai_api_key: Optional[str] = None
    hf_token: Optional[str] = None
    
    # Webhook target
    webhook_url: str = "http://localhost:5678/webhook/embeddings-result"
    webhook_timeout_seconds: float = 10.0
    webhook_auth_enabled: bool = False
    webhook_auth_header_name: str = "x-api-key"
    webhook_auth_header_value: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Set HF_TOKEN in environment so Hugging Face libraries pick it up automatically
import os
if settings.hf_token:
    os.environ["HF_TOKEN"] = settings.hf_token
