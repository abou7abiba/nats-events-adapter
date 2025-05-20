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

# Import from our modules
from .nats_client import NatsClient
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
            nats_client: An instance of NatsClient
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
            success = await self.nats_client.publish(SUBJECT, file_info)
            if success:
                print(f"Event published to {SUBJECT}")
            else:
                print(f"Failed to publish event to {SUBJECT}")
        except Exception as e:
            print(f"Error publishing event: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()


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
    
    nats_client = None
    observer = None
    
    try:
        # Create and connect to NATS
        nats_client = NatsClient(NATS_SERVER, "file-events-publisher")
        connected = await nats_client.connect()
        
        if not connected:
            print("Failed to connect to NATS server. Exiting.")
            return
        
        # Ensure stream exists
        stream_created = await nats_client.ensure_stream(STREAM_NAME, [SUBJECT])
        if not stream_created:
            print("Failed to create stream. Exiting.")
            return
        
        # Set up the watchdog observer
        event_handler = FileEventHandler(nats_client)
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
        if nats_client is not None and nats_client.is_connected():
            print("Closing NATS connection...")
            await nats_client.close()
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