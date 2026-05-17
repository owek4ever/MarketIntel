import asyncio
import logging
from redis.asyncio import Redis

from config import Config
from store import ProxyStore
from n8n_sync import sync_loop, fetch_and_sync_proxies
from server import handle_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing Proxy Manager...")

    # Connect to Redis
    redis_client = Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        password=Config.REDIS_PASSWORD,
        decode_responses=False # Keep raw bytes for fast transmission, decode when necessary
    )
    
    # Verify Redis connection
    await redis_client.ping() # type: ignore
    logger.info("Connected to Redis successfully.")

    store = ProxyStore(redis_client, Config.HOURLY_LIMIT_PER_PROXY_DOMAIN, Config.DAILY_LIMIT_PER_PROXY_DOMAIN)

    # Do an initial sync before accepting traffic to have proxies available immediately
    await fetch_and_sync_proxies(store)

    # Launch n8n sync daemon in the background
    _sync_task = asyncio.create_task(sync_loop(store))

    # Define proxy server factory binding the store instance
    async def handle_client_wrapper(reader, writer):
        await handle_client(reader, writer, store)

    # Start the TCP proxy server
    server = await asyncio.start_server(
        handle_client_wrapper, 
        host=Config.PROXY_HOST, 
        port=Config.PROXY_PORT
    )

    addrs = ', '.join(str(sockets.getsockname()) for sockets in server.sockets)
    logger.info(f"Proxy Server serving on {addrs}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Proxy Manager shutting down.")
