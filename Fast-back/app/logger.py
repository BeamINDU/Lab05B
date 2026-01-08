import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = TimedRotatingFileHandler(
    filename='/logs/app.log',
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
