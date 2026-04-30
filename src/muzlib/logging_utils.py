"""Logging configuration utility for the Muzlib application."""

import os
import logging

# Ensure the logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure basic logging
logging.basicConfig(
    level=logging.DEBUG,  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
    filename='logs/muzlib.log',   # Log to file, omit for console logging
    filemode='w'          # Overwrite ('w') or append ('a') to log file
)
