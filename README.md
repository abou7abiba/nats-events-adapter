# NATS Events Adapter

A system that monitors file changes in a storage directory and logs them using NATS JetStream for message passing.

## Project Structure

```
nats-server/
├── .env                 # Environment variables for NATS server
├── docker-compose.yml   # Docker configuration for NATS
└── data/                # Persistence directory for NATS JetStream

nats-events-adapter/
├── src/
│   ├── config.py        # Centralized configuration settings
│   ├── file_listener.py # Component that detects file changes
│   └── monitor.py       # Component that logs file events
├── test/
│   ├── monitor/
│   │   └── storage_monitor.log # Log file (created automatically)
│   └── storage/         # Test directory to monitor for file changes
├── environment.yml      # Conda environment configuration
├── activate_env.bat     # Script to activate the conda environment
└── requirements.txt     # Python dependencies
```

## Setup Instructions

### 1. Set Up Python Environment

This project uses a dedicated conda environment with Python 3.12.

#### Option 1: Using the environment.yml file (recommended)

```bash
# Create the conda environment from the environment.yml file
conda env create -f environment.yml

# Activate the environment
conda activate new-pine
```

#### Option 2: Using the activation script

```bash
# Simply run the activation script
activate_env.bat
```

This will activate the conda environment and provide information about available commands.

### 2. Start the NATS Server with JetStream

```bash
cd nats-server
docker-compose up -d
```

This will start the NATS server with JetStream enabled, using a volume mount defined in the `.env` file.

### 3. Start the Monitor Component

With the conda environment activated, open a terminal and run:

```bash
python -m src.monitor
```

### 4. Start the File Listener Component

With the conda environment activated, open another terminal and run:

```bash
python -m src.file_listener
```

## Testing the System

1. Add a file to the test storage directory:
   ```bash
   echo "test content" > test/storage/test.txt
   ```

2. Delete a file from the test storage directory:
   ```bash
   rm test/storage/test.txt
   ```

3. Check the logs:
   ```bash
   cat test/monitor/storage_monitor.log
   ```

## Changing Configuration

You can customize the behavior of the system by modifying the configuration settings in `src/config.py`. The following settings can be adjusted:

### NATS Server Configuration
```python
# NATS Server connection settings
NATS_SERVER = "nats://localhost:4222"  # Change this if your NATS server is on a different host/port
```

### Stream and Subject Configuration
```python
# JetStream configuration
STREAM_NAME = "FILES"      # Name of the JetStream stream
SUBJECT = "file.events"    # Subject name for file events
CONSUMER_NAME = "file-monitor"  # Durable consumer name for the monitor
```

### Directory Settings
```python
# File paths
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "storage")  # Directory to monitor
MONITOR_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test", "monitor")  # Directory for logs
LOG_FILE = os.path.join(MONITOR_DIR, "storage_monitor.log")  # Log file path
```

After changing configuration, restart both the file listener and monitor components for the changes to take effect.

## Recent Updates

### Windows Compatibility
- Fixed signal handling on Windows platforms
- Added platform detection to ensure proper shutdown behavior
- Improved error handling and recovery

### Enhanced Resilience
- Added reconnection logic for NATS server connection interruptions
- Improved error handling with detailed error reporting
- Implemented graceful shutdown mechanism

## How It Works

1. The file listener monitors the `test/storage` directory for file additions and deletions.
2. When a file change is detected, it publishes an event to NATS with the file path, operation, and size.
3. The monitor component subscribes to these events and logs them to `test/monitor/storage_monitor.log`.
4. NATS JetStream provides persistence for the events, ensuring they are delivered even if the monitor is temporarily offline.

## Troubleshooting

### Common Issues

1. **NATS Connection Failure**
   - Ensure Docker is running and the NATS server container is up
   - Check the NATS server logs: `docker logs nats-server_nats_1`
   - Verify the NATS server URL in `config.py` matches your setup

2. **File Events Not Being Detected**
   - Confirm the correct directory is being monitored (check the STORAGE_DIR in config.py)
   - Ensure file operations are being performed in the monitored directory

3. **Windows-Specific Issues**
   - If experiencing issues with Ctrl+C not working properly, ensure you're using the latest version with Windows compatibility fixes