"""
Monitor Module

This module subscribes to file events from a NATS JetStream server
and logs those events to a file. It listens for messages about file
additions and deletions, and records them in a log file.

Usage:
    python -m src.monitor
"""
import asyncio
import os
import datetime
import json
import sys
import signal
import traceback
import platform

# Import from our modules
from .nats_client import NatsClient
from .config import (
    NATS_SERVER, SUBJECT, STREAM_NAME, CONSUMER_NAME,
    MONITOR_DIR, LOG_FILE, LOG_FORMAT, DATE_FORMAT,
    JS_CONFIG
)

# Flag to track when shutdown is requested
shutdown_requested = False

def log_event(event_data):
    """
    Write the event data to the log file.
    
    Args:
        event_data: Dictionary containing file event information
    """
    # Ensure monitor directory exists
    os.makedirs(MONITOR_DIR, exist_ok=True)
    
    # Format current timestamp
    timestamp = datetime.datetime.now().strftime(DATE_FORMAT)
    
    # Format the log entry
    log_entry = LOG_FORMAT.format(
        timestamp=timestamp,
        operation=event_data['operation'].upper(),
        path=event_data['path'],
        file_size=event_data['file_size']
    )
    
    # Write to log file
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    
    print(f"Logged event: {log_entry.strip()}")


async def process_messages(nats_client):
    """
    Process messages from the NATS JetStream.
    
    This function continuously pulls messages from the JetStream,
    processes them, and acknowledges receipt.
    
    Args:
        nats_client: NatsClient instance
    """
    # Subscribe to the subject with the durable consumer
    subscription = await nats_client.subscribe(SUBJECT, CONSUMER_NAME)
    if subscription is None:
        print(f"Failed to subscribe to {SUBJECT}. Exiting.")
        return
    
    print(f"Monitoring for file events on subject: {SUBJECT}")
    print(f"Logging to: {LOG_FILE}")
    print("Press Ctrl+C to stop the monitor...")
    
    while not shutdown_requested:
        try:
            # Fetch messages (with a timeout)
            messages = await nats_client.fetch_messages(subscription, 1, timeout=1)
            
            for message in messages:
                try:
                    # Parse the message data
                    event_data = json.loads(message.data.decode())
                    
                    # Log the event
                    log_event(event_data)
                    
                    # Acknowledge the message
                    await message.ack()
                    
                except json.JSONDecodeError as e:
                    print(f"Error decoding message: {e}")
                    await message.ack()  # Acknowledge to avoid reprocessing
                except Exception as e:
                    print(f"Error processing message: {e}")
                    print("\nDetailed error information:")
                    traceback.print_exc()
                    await message.ack()  # Acknowledge to avoid reprocessing
        
        except asyncio.CancelledError:
            # Handle task cancellation gracefully
            print("Task cancelled, shutting down...")
            break
        except Exception as e:
            if not shutdown_requested:
                print(f"Unexpected error: {e}")
                print("\nDetailed error information:")
                traceback.print_exc()
                # Sleep to prevent tight loop in case of persistent error
                await asyncio.sleep(1)


def signal_handler(sig, frame):
    """Handle termination signals to allow for graceful shutdown."""
    global shutdown_requested
    shutdown_requested = True
    print("Shutdown requested, cleaning up...")


async def main():
    """
    Main application function.
    
    Sets up NATS JetStream connection and processes messages.
    """
    # Set up signal handlers for graceful shutdown
    # Windows doesn't support add_signal_handler with the asyncio event loop
    if platform.system() != 'Windows':
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
      # Create client instance once outside the loop
    nats_client = NatsClient(NATS_SERVER, "file-events-monitor")
    try:
        while not shutdown_requested:
            try:
                # Connect to NATS if not already connected
                if not nats_client.is_connected():
                    connected = await nats_client.connect()
                    
                    if not connected:
                        print("Failed to connect to NATS server. Waiting to retry...")
                        await asyncio.sleep(2)
                        continue
                
                # Ensure stream exists
                stream_created = await nats_client.ensure_stream(STREAM_NAME, [SUBJECT])
                if not stream_created:
                    print("Failed to create stream. Waiting to retry...")
                    await asyncio.sleep(2)
                    continue
                
                # Ensure consumer exists
                consumer_created = await nats_client.ensure_consumer(STREAM_NAME, CONSUMER_NAME, JS_CONFIG)
                if not consumer_created:
                    print("Failed to create consumer. Waiting to retry...")
                    await asyncio.sleep(2)
                    continue
                
                # Process messages
                await process_messages(nats_client)
                  # If process_messages returns and no shutdown was requested,
                # there may have been a connection issue
                if not shutdown_requested:
                    print("Connection to NATS server lost. Attempting to reconnect...")
                    # Close the connection if it's still active
                    if nats_client.is_connected():
                        await nats_client.close()
                    await asyncio.sleep(2)  # Wait before attempting to reconnect
                
            except Exception as e:
                if not shutdown_requested:
                    print(f"Unexpected error in main loop: {e}")
                    # Close the connection if it's still active
                    if nats_client.is_connected():
                        await nats_client.close()
                    await asyncio.sleep(2)  # Wait before attempting to reconnect    except asyncio.CancelledError:
        print("Main task cancelled")
    finally:
        # Ensure proper cleanup of NATS connection
        if nats_client.is_connected():
            print("Closing NATS connection...")
            await nats_client.close()
        print("Monitor shutdown complete")


if __name__ == "__main__":
    # Ensure the monitor directory exists
    os.makedirs(MONITOR_DIR, exist_ok=True)
    
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