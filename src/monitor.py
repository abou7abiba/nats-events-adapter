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
import nats
from nats.js.api import ConsumerConfig
from nats.errors import TimeoutError, ConnectionClosedError, NoServersError

# Import configuration
from .config import (
    NATS_SERVER, SUBJECT, STREAM_NAME, CONSUMER_NAME,
    MONITOR_DIR, LOG_FILE, LOG_FORMAT, DATE_FORMAT,
    JS_CONFIG
)

# Flag to track when shutdown is requested
shutdown_requested = False

async def setup_jetstream():
    """
    Connect to NATS server and set up JetStream consumer.
    
    Returns:
        tuple: (NATS connection, JetStream context)
    """
    # Connect to NATS server with retry
    print(f"Connecting to NATS server at {NATS_SERVER}")
    
    # Connection options with improved timeout and reconnect settings
    options = {
        "servers": [NATS_SERVER],
        "connect_timeout": 10,  # Increase timeout to 10 seconds
        "reconnect_time_wait": 2,  # Wait 2 seconds before reconnection attempts
        "max_reconnect_attempts": 5,  # Try to reconnect 5 times
        "name": "file-events-monitor"  # Identify this client for monitoring
    }
    
    retry_attempts = 0
    max_retries = 3
    retry_delay = 2  # seconds
    
    while retry_attempts < max_retries:
        try:
            nc = await nats.connect(**options)
            print("Successfully connected to NATS server")
            js = nc.jetstream()
            
            # Ensure stream exists
            try:
                await js.stream_info(STREAM_NAME)
                print(f"Stream '{STREAM_NAME}' exists")
            except nats.errors.Error:
                # Create the stream if it doesn't exist
                await js.add_stream(name=STREAM_NAME, subjects=[SUBJECT])
                print(f"Created stream '{STREAM_NAME}' with subject {SUBJECT}")
            
            # Create a durable consumer if it doesn't exist
            consumer_config = ConsumerConfig(
                durable_name=CONSUMER_NAME,
                ack_policy=JS_CONFIG["ack_policy"],
                deliver_policy=JS_CONFIG["deliver_policy"]
            )
            
            try:
                await js.consumer_info(STREAM_NAME, CONSUMER_NAME)
                print(f"Consumer '{CONSUMER_NAME}' exists")
            except nats.errors.Error:
                await js.add_consumer(STREAM_NAME, consumer_config)
                print(f"Created consumer '{CONSUMER_NAME}'")
            
            return nc, js
            
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
            sys.exit(1)


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


async def process_messages(js):
    """
    Process messages from the NATS JetStream.
    
    This function continuously pulls messages from the JetStream,
    processes them, and acknowledges receipt.
    
    Args:
        js: JetStream context
    """
    # Subscribe to the subject with the durable consumer
    subscription = await js.pull_subscribe(SUBJECT, CONSUMER_NAME)
    
    print(f"Monitoring for file events on subject: {SUBJECT}")
    print(f"Logging to: {LOG_FILE}")
    print("Press Ctrl+C to stop the monitor...")
    
    while not shutdown_requested:
        try:
            # Fetch messages (with a timeout)
            messages = await subscription.fetch(1, timeout=1)
            
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
        
        except nats.errors.TimeoutError:
            # This is normal when no messages are available
            # Just wait a bit and try again
            if not shutdown_requested:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            # Handle task cancellation gracefully
            print("Task cancelled, shutting down...")
            break
        except nats.errors.ConnectionClosedError as e:
            if not shutdown_requested:
                print(f"Connection closed: {e}. Attempting to reconnect...")
                # Break from the loop, which will trigger reconnection in main()
                return
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
    
    nc = None
    try:
        while not shutdown_requested:
            try:
                # Setup JetStream
                nc, js = await setup_jetstream()
                
                # Process messages
                await process_messages(js)
                
                # If process_messages returns and no shutdown was requested,
                # there may have been a connection issue
                if not shutdown_requested:
                    print("Connection to NATS server lost. Attempting to reconnect...")
                    await asyncio.sleep(2)  # Wait before attempting to reconnect
                
            except Exception as e:
                if not shutdown_requested:
                    print(f"Unexpected error in main loop: {e}")
                    await asyncio.sleep(2)  # Wait before attempting to reconnect
    except asyncio.CancelledError:
        print("Main task cancelled")
    finally:
        # Ensure proper cleanup of NATS connection
        if nc is not None and nc.is_connected:
            print("Closing NATS connection...")
            await nc.close()
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