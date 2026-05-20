import logging
from pathlib import Path

from backend.config import PROJECT_ROOT

LOG_FILE = PROJECT_ROOT / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("mace-chatbot")


def sanitize_error_message(message: str) -> str:
    lowered = message.lower()
    if any(term in lowered for term in ("api_key", "groq", "secret", "password", "token")):
        return "An internal error occurred. Please try again later."
    return message
