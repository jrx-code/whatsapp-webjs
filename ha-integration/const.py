"""Constants for the WhatsApp Notifier (wapi) integration."""

DOMAIN = "wapi"

CONF_API_URL = "api_url"
CONF_API_KEY = "api_key"
CONF_SESSION = "session"
CONF_CONTACTS = "contacts"

DEFAULT_PORT = 3001
DEFAULT_TIMEOUT = 30

# Auto-discovery targets (tried in order)
DISCOVERY_URLS = [
    "http://wwebjs-web-api:3001",
    "http://localhost:3001",
]

ATTR_MEDIA_URL = "media_url"
