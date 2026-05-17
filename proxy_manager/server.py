import asyncio
import logging
import urllib.parse
from store import ProxyStore
from config import Config

logger = logging.getLogger(__name__)

async def stream_copy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Pipes bytes continuously from reader to writer."""
    try:
        while True:
            data = await reader.read(8192)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception as e:
        # Expected EOF or Connection Reset
        logger.debug(f"Stream copy closed: {e}")
    finally:
        try:
            if not writer.is_closing():
                writer.close()
        except Exception:
            pass

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, store: ProxyStore):
    """Handles an incoming proxy connection from the Playwright worker."""
    peername = writer.get_extra_info('peername')
    logger.debug(f"Accepted connection from {peername}")

    try:
        # Read the first line of the HTTP payload to determine destination
        first_line_bytes = await reader.readline()
        if not first_line_bytes:
            writer.close()
            return
            
        first_line = first_line_bytes.decode('utf-8', errors='ignore').strip()
        parts = first_line.split()
        if len(parts) >= 2:
            method = parts[0].upper()
            url_target = parts[1]
        else:
            writer.close()
            return

        # Determine target host and domain
        if method == "CONNECT":
            # Form: CONNECT target.com:443 HTTP/1.1
            host_port = url_target
            domain = host_port.split(':')[0]
        else:
            # Form: GET http://target.com/path HTTP/1.1
            parsed_url = urllib.parse.urlparse(url_target)
            domain = parsed_url.hostname or url_target
            
        # Optional: strip port if appended in domain
        if ':' in domain:
            domain = domain.split(':')[0]

        # Check for blocked domains
        for blocked in Config.BLOCKED_DOMAINS:
            if blocked in domain:
                logger.info(f"🚫 [BLOCKED] Dropping request to tracker/blocked domain: '{domain}'")
                writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                await writer.drain()
                writer.close()
                return
        
        # Get a proxy from store
        proxy = await store.get_best_proxy(domain)
        if not proxy:
            # No proxy available, reject connection gracefully
            logger.warning(f"No proxy available for domain {domain}")
            writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Log routing decision prominently
        logger.info(f"🚀 [PROXY ASSIGNED] Client '{peername}' -> Domain '{domain}' -> Using Proxy '{proxy}' (Method: {method})")
        
        # Parse proxy credentials and host
        proxy_auth = None
        if "@" in proxy:
            creds, proxy_host_port = proxy.split("@", 1)
            proxy_host, proxy_port = proxy_host_port.split(":")
            import base64
            auth_b64 = base64.b64encode(creds.encode('utf-8')).decode('utf-8')
            proxy_auth = f"Proxy-Authorization: Basic {auth_b64}\r\n".encode('utf-8')
        else:
            proxy_host, proxy_port = proxy.split(":")
            
        # Connect to the upstream proxy
        try:
            remote_reader, remote_writer = await asyncio.open_connection(proxy_host, int(proxy_port))
        except Exception as e:
            logger.error(f"❌ [PROXY FAILED] Could not connect to upstream proxy {proxy}: {e}")
            await store.report_failure(proxy)
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await writer.drain()
            writer.close()
            return

        # Record proxy usage bounds
        await store.record_usage(proxy, domain)

        # Forward the initially read first line
        remote_writer.write(first_line_bytes)
        if proxy_auth:
            remote_writer.write(proxy_auth)
        await remote_writer.drain()

        logger.debug(f"🔄 Connected to upstream {proxy_host}:{proxy_port}. Pumping data...")
        # Wire up bi-directional stream pumping
        task_client_to_remote = asyncio.create_task(stream_copy(reader, remote_writer))
        task_remote_to_client = asyncio.create_task(stream_copy(remote_reader, writer))

        # Wait until either side closes
        await asyncio.gather(task_client_to_remote, task_remote_to_client, return_exceptions=True)
        logger.info(f"🛑 [CONNECTION CLOSED] Domain '{domain}' via Proxy '{proxy}'")
            
    except Exception as e:
        logger.error(f"Error handling connection: {e}")
    finally:
        try:
            if not writer.is_closing():
                writer.close()
        except Exception:
            pass
