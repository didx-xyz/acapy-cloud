import sys

from loguru import logger

# Remove default handler
logger.remove()

# Define custom formatter
formatter = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level> - "
    "Context: "
    "{extra[wallet_id]} "
    "{extra[topic]} "
    "{extra[body]}"
)
logger.configure(
    extra={"wallet_id": "", "topic": "", "body": ""}
)  # Default values for extra args

# Log to stderr
logger.add(sys.stderr, level="DEBUG", format=formatter)

# Log to a file
logger.add(
    "./logs/app_{time}.log",
    rotation="00:00",  # new file is created at midnight
    retention="7 days",  # keep logs for up to 7 days
    enqueue=True,  # asynchronous
    level="DEBUG",
    format=formatter,
)

# Configure email notifications
# logger.add("smtp+ssl://username:password@host:port", level="CRITICAL")


# Export this logger
def get_logger(name: str):
    return logger.bind(name=name)
