"""
Configuration module for the NATS Events Adapter.

This module contains all configuration parameters for the application,
making it easier to modify settings in one place.
"""
import os

# NATS Server configuration
NATS_SERVER = "nats://localhost:4222"  # URL of the NATS server
SUBJECT = "file.events"  # Subject name for file events
STREAM_NAME = "FILES"  # JetStream stream name
CONSUMER_NAME = "file-monitor"  # JetStream consumer name

# File paths configuration
# Get the base directory (src parent directory)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STORAGE_DIR = os.path.join(BASE_DIR, 'test', 'storage')  # Path to storage directory
MONITOR_DIR = os.path.join(BASE_DIR, 'test', 'monitor')  # Path to monitor directory
LOG_FILE = os.path.join(MONITOR_DIR, 'storage_monitor.log')  # Path to log file

# JetStream configuration
JS_CONFIG = {
    "ack_policy": "explicit",  # Explicit acknowledgment required
    "deliver_policy": "new"    # Only deliver new messages
}

# Logging configuration
LOG_FORMAT = "[{timestamp}] File {operation}: {path}, Size: {file_size:.2f} KB\n"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"