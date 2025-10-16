import logging
import sys


def setup_logger(verbosity: int = 0) -> logging.Logger:
    level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO

    logger = logging.getLogger("prop_recommender")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Ensure propagation is disabled to avoid duplicate logs
    logger.propagate = False
    return logger

