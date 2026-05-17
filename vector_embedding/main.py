import logging
import asyncio
import httpx
from fastapi import FastAPI, HTTPException

from config import settings
from models import ProductPayload, Payload
from embedding_factory import EmbeddingFactory, format_product_text

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Generates embeddings for product details and POSTs them to Webhooks.",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing application and loading models...")
    # Trigger model download/load on boot so first request doesn't hang
    EmbeddingFactory.get_provider()
    logger.info("Model loaded successfully.")


async def send_to_webhook(payload: Payload):
    """Asynchronously pushes the vector payload to the configured webhook."""

    # We serialize it to dict
    data = payload.model_dump()

    headers = {}
    if settings.webhook_auth_enabled:
        headers[settings.webhook_auth_header_name] = settings.webhook_auth_header_value

    try:
        async with httpx.AsyncClient(
            timeout=settings.webhook_timeout_seconds,
            headers=headers
        ) as client:
            response = await client.post(settings.webhook_url, json=data)
            response.raise_for_status()
            logger.info(
                f"Webhook dispatched successfully for product. url_hash: {payload.url_hash}, status code: {response.status_code}"
            )
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"Webhook returned error status: {exc.response.status_code} - {exc.response.text}"
        )
    except httpx.RequestError as exc:
        logger.error(f"Failed to communicate with Webhook: {exc}")
    except Exception as exc:
        logger.error(f"Unexpected error in webhook dispatch: {exc}")


@app.post("/api/v1/products/embed")
async def generate_and_dispatch_embedding(product: ProductPayload):
    """
    Receives product data, generates embeddings, and fires off a background task to POST to webhook.
    """
    logger.info(
        f"Received embedding request for url_hash: {product.url_hash} | title: {product.title}"
    )

    # 1. Format text
    text_to_embed = format_product_text(product)

    if not text_to_embed.strip():
        raise HTTPException(
            status_code=400,
            detail="Not enough valid product data provided to create embeddings.",
        )

    try:
        # 2. Get provider and compute vector
        provider = EmbeddingFactory.get_provider()
        vector = provider.generate_embedding(text_to_embed)

        # 3. Create Webhook payload
        webhook_payload = Payload(
            product_id=product.id,
            url_hash=product.url_hash,
            embedding=vector,
            model_used=settings.local_model_name
            if settings.embedding_provider == "local"
            else settings.embedding_provider,
            dimension=len(vector),
        )

        # 4. Enqueue to background task
        # background_tasks.add_task(send_to_webhook, webhook_payload)

        return {
            "status": "done",
            # "message": "Embedding generated and queued for webhook dispatch.",
            "embedding": webhook_payload,
        }

    except Exception as e:
        logger.error(f"Error during embedding generation: {e}")
        raise HTTPException(
            status_code=500, detail="Internal Server Error during model execution."
        )


@app.get("/health")
def health_check():
    return {"status": "ok"}
