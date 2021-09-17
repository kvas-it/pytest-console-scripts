import logging

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def run():
    LOGGER.debug("DEBUG")
    LOGGER.info("INFO")
    LOGGER.warning("WARNING")
