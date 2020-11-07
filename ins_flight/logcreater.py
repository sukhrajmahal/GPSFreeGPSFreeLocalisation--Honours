import logging
import io
import os

class LogCreater:

    @staticmethod
    def setup_logger(name, level=logging.DEBUG):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        return logger 