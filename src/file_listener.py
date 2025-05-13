"""
File Listener Module

This module monitors a directory for file system events (additions and deletions)
and publishes those events to a NATS JetStream server.

Usage:
    python -m src.file_listener
"""
import asyncio
import os
import time
import json
import sys
import signal
import traceback
import platform
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import nats
from nats.errors import TimeoutError, ConnectionClosedError, NoServersError

# Import configuration
from .config import (
    NATS_SERVER, SUBJECT, STREAM_NAME, 
    STORAGE_DIR
)

# Flag to track when shutdown is requested
shutdown_requested = False

class FileEventHandler(FileSystemEventHandler):
    """
    Handler for file system events that publishes events to NATS.
    
    This class extends FileSystemEventHandler to detect when files are
    added or deleted in the monitored directory, then publishes these
    events to a NATS JetStream subject.
    """
    
    def __init__(self, nats_client):
        """
        Initialize the event handler with a NATS client.
        
        Args:
            nats_client: An active NATS client connection
        """
        self.nats_client = nats_client
        super().__init__()
        
    def on_created(self, event):
        """
        Handle file creation events.
        
        Args:
            event: The file system event object
        """
        # Only process file events, not directory events
        if not event.is_directory:
            self._process_file_event(event.src_path, "added")
            
    def on_deleted(self, event):
        """
        Handle file deletion events.
        
        Args:
            event: The file system event object
        """
        # Only process file events, not directory events
        if not event.is_directory:
            self._process_file_event(event.src_path, "deleted")
            
    def _process_file_event(self, file_path, operation):
        """
        Process a file event and prepare it for publishing.
        
        Args:
            file_path: Path to the affected file
            operation: String indicating the operation ('added' or 'deleted')
        """
        # Calculate file size if the file exists (for 'added' operations)
        file_size = 0
        if operation == "added" and os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / 1024  # Size in KB
        
        # Create event data structure    
        file_info = {
            "path": file_path,
            "operation": operation,
            "file_size": file_size,
            "timestamp": time.time()
        }
        
        print(f"File {operation}: {file_path}")
        
        # Skip publishing if shutdown is in progress
        if not shutdown_requested:
            # Use asyncio.run to run the async publish method from sync code
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._send_event(file_info))
                loop.close()
            except RuntimeError as e:
                # This can happen during shutdown if the event loop is already closed
                print(f"Event loop error: {e}")
                print("Skipping event publishing")
            except Exception as e:
                print(f"Error publishing event: {e}")
                print("\nDetailed error information:")
                traceback.print_exc()
        
    async def _send_event(self, file_info):
        """
        Send an event to the NATS server.
        
        Args:
            file_info: Dictionary containing file event information
        """
        try:
            # Publish the event as JSON data
            await self.nats_client.publish(SUBJECT, json.dumps(file_info).encode())
            print(f"Event published to {SUBJECT}")
        except Exception as e:
            print(f"Error publishing event: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()


async def run_nats_client():
    """
    Connect to NATS server and set up JetStream.
    
    Returns:
        An active NATS client connection
    """
    # Connect to NATS server with retry
    print(f"Connecting to NATS server at {NATS_SERVER}")
    
    # Connection options with improved timeout and reconnect settings
    options = {
        "servers": [NATS_SERVER],
        "connect_timeout": 10,  # Increase timeout to 10 seconds
        "reconnect_time_wait": 2,  # Wait 2 seconds before reconnection attempts
        "max_reconnect_attempts": 5,  # Try to reconnect 5 times
        "name": "file-events-publisher"  # Identify this client for monitoring
    }
    
    retry_attempts = 0
    max_retries = 3
    retry_delay = 2  # seconds
    
    while retry_attempts < max_retries:
        try:
            nc = await nats.connect(**options)
            print("Successfully connected to NATS server")
            
            # Access JetStream context
            js = nc.jetstream()
            
            # Create a stream if it doesn't exist
            try:
                # Attempt to create the stream
                await js.add_stream(name=STREAM_NAME, subjects=[SUBJECT])
                print(f"Created stream '{STREAM_NAME}' with subject {SUBJECT}")
            except nats.errors.Error as e:
                # Stream might already exist, which is OK
                print(f"Stream setup info: {e}")
            
            return nc
            
        except (TimeoutError, ConnectionClosedError, NoServersError) as e:
            retry_attempts += 1
            if retry_attempts < max_retries:
                print(f"Failed to connect: {e}. Retrying in {retry_delay} seconds... (Attempt {retry_attempts}/{max_retries})")
                await asyncio.sleep(retry_delay)
                # Increase the delay for next retry (exponential backoff)
                retry_delay *= 2
            else:
                print(f"Failed to connect after {max_retries} attempts: {e}")
                print("Please make sure the NATS server is running and accessible.")
                print(f"Server URL: {NATS_SERVER}")
                # Exit with error
                sys.exit(1)
        except Exception as e:
            print(f"Unexpected error connecting to NATS: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()
            sys.exit(1)


def signal_handler(sig, frame):
    """Handle termination signals to allow for graceful shutdown."""
    global shutdown_requested
    shutdown_requested = True
    print("Shutdown requested, cleaning up...")


async def main():
    """
    Main application function.
    
    Sets up NATS connection and file system observer.
    """
    # Set up signal handlers for graceful shutdown
    # Windows doesn't support add_signal_handler with the asyncio event loop
    if platform.system() != 'Windows':
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    
    print(f"Starting file listener for directory: {STORAGE_DIR}")
    
    nc = None
    observer = None
    
    try:
        # Connect to NATS
        nc = await run_nats_client()
        
        # Set up the watchdog observer
        event_handler = FileEventHandler(nc)
        observer = Observer()
        observer.schedule(event_handler, STORAGE_DIR, recursive=True)
        observer.start()
        
        print("File listener is running. Press Ctrl+C to stop.")
        
        # Keep the program running until shutdown is requested
        while not shutdown_requested:
            await asyncio.sleep(1)
    
    except asyncio.CancelledError:
        print("Main task cancelled")
    except Exception as e:
        print(f"Error in main loop: {e}")
        print("\nDetailed error information:")
        traceback.print_exc()
    finally:
        # Graceful shutdown
        print("Shutting down file listener...")
        
        # Stop and join the observer
        if observer is not None:
            observer.stop()
            observer.join()
            print("Observer stopped")
        
        # Close NATS connection
        if nc is not None and nc.is_connected:
            print("Closing NATS connection...")
            await nc.close()
            print("NATS connection closed")
        
        print("Shutdown complete")


if __name__ == "__main__":
    # Create storage directory if it doesn't exist
    os.makedirs(STORAGE_DIR, exist_ok=True)
    
    # Register signal handlers for the main thread
    # This is the Windows-compatible way to handle signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Run the main async function
        asyncio.run(main())
    except KeyboardInterrupt:
        # This handles the case when KeyboardInterrupt is raised outside of our tasks
        print("Shutdown by keyboard interrupt")
    except Exception as e:
        # Print the full exception traceback for better debugging
        print(f"Shutdown due to error: {e}")
        print("\nDetailed error information:")
        traceback.print_exc()
        sys.exit(1)