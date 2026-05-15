import logging
from logging.config import dictConfig
from typing import Any

from app.config import Settings


RESERVED_LOG_FIELDS = ("trace_id", "task_id", "message_id", "delivery_status", "error_code")


def configure_logging(settings: Settings) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": settings.log_level,
            },
        }
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_context(**kwargs: Any) -> dict[str, Any]:
    return {field: kwargs.get(field) for field in RESERVED_LOG_FIELDS if kwargs.get(field) is not None}
