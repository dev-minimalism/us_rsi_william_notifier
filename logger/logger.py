import logging
from logging.handlers import RotatingFileHandler

# 로그 설정
log_handler = RotatingFileHandler("./log/rsi_william_usa.log", maxBytes=10**6, backupCount=5)

logging.basicConfig(
    handlers=[log_handler],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()
