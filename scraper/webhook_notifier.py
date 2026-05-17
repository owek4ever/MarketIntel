from typing import Any

import httpx
import logging

logger = logging.getLogger(__name__)

class WebhookNotifier:
    def __init__(self, timeout_seconds: float = 10.0, auth_header_name: str | None = None, auth_header_value: str | None = None):
        self.timeout = timeout_seconds
        headers = {}
        if auth_header_name and auth_header_value:
            headers[auth_header_name] = auth_header_value
        self.client = httpx.AsyncClient(timeout=self.timeout, headers=headers)

    async def send_payload(self, webhook_url: str, payload: Any) -> None | httpx.Response:
        """
        Sends the job payload to the webhook_url specified in the job metadata.
        Returns True if successful or no webhook_url was provided, False otherwise.
        """

        if not webhook_url:
            return

        try:
            # Send the entire job object as JSON payload, or customize as needed
            response = await self.client.post(webhook_url, json=payload)

            if response.status_code >= 400:
                logger.warning(
                    f"Webhook returned HTTP {response.status_code}: {response.text}"
                )
                return response
            return response

        except httpx.RequestError as e:
            logger.error(f"Failed to send webhook to {webhook_url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending webhook: {e}")

    async def close(self):
        await self.client.aclose()
