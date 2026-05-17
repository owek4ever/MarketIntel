import os

class Config:
    # Redis Configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
    
    # Limitations
    HOURLY_LIMIT_PER_PROXY_DOMAIN = int(os.getenv("HOURLY_LIMIT", "50"))
    DAILY_LIMIT_PER_PROXY_DOMAIN = int(os.getenv("DAILY_LIMIT", "500"))
    
    # n8n Sync
    N8N_PROXY_URL = os.getenv("N8N_PROXY_URL", "http://localhost:5678/webhook/proxies")
    N8N_PROXY_AUTH_HEADER_NAME = os.getenv("N8N_PROXY_AUTH_HEADER_NAME", "x-api-key")
    N8N_PROXY_AUTH_HEADER_VALUE = os.getenv("N8N_PROXY_AUTH_HEADER_VALUE", "21ZCKkMVXoH1lhW7w2lg66iYja8EtRFW5qEZRoMIa55OmiBokLQgdNde4MpscjoS")
    SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_DAYS", "1")) * 60 * 60 * 24
    
    # Proxy Server settings
    PROXY_HOST = os.getenv("PROXY_HOST", "0.0.0.0")
    PROXY_PORT = int(os.getenv("PROXY_PORT", "8888"))

    # Blocked Domains (Traffic to these will be instantly dropped)
    BLOCKED_DOMAINS = [
        "google-analytics.com",
        "googletagmanager.com",
        "fonts.gstatic.com",
        "facebook.net",
        "facebook.com"
    ]
