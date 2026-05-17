from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProductPayload(BaseModel):
    """The shape of the product data received strictly tailored to your schema representation."""

    id: Optional[int] = None
    url_hash: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    specifications: Optional[str] = None
    description: Optional[str] = None

    # Custom fields can be sent and passed-through
    metadata: Optional[Dict[str, Any]] = None


class Payload(BaseModel):
    """The payload structure sent to the webhook."""

    # product_id: Optional[int] = None
    # url_hash: Optional[str] = None
    embedding: List[float] = Field(
        ..., description="The highly-dimensional generated vector"
    )
    model_used: str
    dimension: int
