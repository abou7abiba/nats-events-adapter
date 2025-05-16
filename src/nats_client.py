"""
NATS Client Module

This module provides a wrapper for NATS client operations, encapsulating
the JetStream functionality and providing a simple interface for publishing
and subscribing to events.
"""
import asyncio
import nats
import json
import traceback
from typing import List, Dict, Any, Optional, Union
from nats.js.api import ConsumerConfig
from nats.errors import TimeoutError, ConnectionClosedError, NoServersError

class NatsClient:
    """
    A client for interacting with NATS server and JetStream.
    
    This class abstracts away the details of connecting to NATS, setting up
    streams and consumers, and handling messages. It provides a simplified
    interface for publishing and subscribing to messages.
    """
    
    def __init__(self, server_url: str, client_name: str = "nats-client"):
        """
        Initialize a new NATS client.
        
        Args:
            server_url: URL of the NATS server (e.g., "nats://localhost:4222")
            client_name: Name to identify this client for monitoring
        """
        self.server_url = server_url
        self.client_name = client_name
        self.nc = None  # NATS connection
        self.js = None  # JetStream context
        
        # Connection options with good defaults
        self.options = {
            "servers": [self.server_url],
            "connect_timeout": 10,  # 10 seconds
            "reconnect_time_wait": 2,  # 2 seconds between reconnection attempts
            "max_reconnect_attempts": 5,  # Try to reconnect 5 times
            "name": self.client_name
        }
    
    async def connect(self, max_retries: int = 3, retry_delay: int = 2) -> bool:
        """
        Connect to the NATS server with retry logic.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds (doubles each retry)
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if self.is_connected():
            return True
            
        retry_attempts = 0
        current_delay = retry_delay
        
        while retry_attempts < max_retries:
            try:
                self.nc = await nats.connect(**self.options)
                print(f"Successfully connected to NATS server at {self.server_url}")
                self.js = self.nc.jetstream()
                return True
                
            except (TimeoutError, ConnectionClosedError, NoServersError) as e:
                retry_attempts += 1
                if retry_attempts < max_retries:
                    print(f"Failed to connect: {e}. Retrying in {current_delay} seconds... (Attempt {retry_attempts}/{max_retries})")
                    await asyncio.sleep(current_delay)
                    # Exponential backoff
                    current_delay *= 2
                else:
                    print(f"Failed to connect after {max_retries} attempts: {e}")
                    print("Please make sure the NATS server is running and accessible.")
                    print(f"Server URL: {self.server_url}")
                    return False
            except Exception as e:
                print(f"Unexpected error connecting to NATS: {e}")
                print("\nDetailed error information:")
                traceback.print_exc()
                return False
        
        return False
    
    async def ensure_stream(self, stream_name: str, subjects: List[str]) -> bool:
        """
        Create a stream if it doesn't exist.
        
        Args:
            stream_name: Name of the stream to create
            subjects: List of subjects for the stream
            
        Returns:
            bool: True if the stream exists or was created, False otherwise
        """
        if not self.is_connected():
            print("Cannot create stream: not connected to NATS")
            return False
            
        try:
            # Check if stream exists
            try:
                await self.js.stream_info(stream_name)
                print(f"Stream '{stream_name}' exists")
                return True
            except nats.errors.Error:
                # Create stream if it doesn't exist
                await self.js.add_stream(name=stream_name, subjects=subjects)
                print(f"Created stream '{stream_name}' with subjects {subjects}")
                return True
        except Exception as e:
            print(f"Error ensuring stream: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()
            return False
    
    async def ensure_consumer(self, stream_name: str, consumer_name: str, 
                             config: Dict[str, Any]) -> bool:
        """
        Create a consumer if it doesn't exist.
        
        Args:
            stream_name: Name of the stream
            consumer_name: Name of the consumer to create
            config: Consumer configuration options
            
        Returns:
            bool: True if the consumer exists or was created, False otherwise
        """
        if not self.is_connected():
            print("Cannot create consumer: not connected to NATS")
            return False
            
        try:
            # Create a consumer config
            consumer_config = ConsumerConfig(
                durable_name=consumer_name,
                ack_policy=config.get("ack_policy", "explicit"),
                deliver_policy=config.get("deliver_policy", "new")
            )
            
            # Check if consumer exists
            try:
                await self.js.consumer_info(stream_name, consumer_name)
                print(f"Consumer '{consumer_name}' exists")
                return True
            except nats.errors.Error:
                # Create consumer if it doesn't exist
                await self.js.add_consumer(stream_name, consumer_config)
                print(f"Created consumer '{consumer_name}'")
                return True
        except Exception as e:
            print(f"Error ensuring consumer: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()
            return False
    
    async def publish(self, subject: str, data: Union[Dict, str, bytes]) -> bool:
        """
        Publish a message to the specified subject.
        
        Args:
            subject: Subject to publish to
            data: Data to publish (can be a dictionary, string, or bytes)
            
        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.is_connected():
            print("Cannot publish: not connected to NATS")
            return False
            
        try:
            # Convert data to bytes if it's not already
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            elif isinstance(data, str):
                data = data.encode()
            
            await self.nc.publish(subject, data)
            return True
        except Exception as e:
            print(f"Error publishing to {subject}: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()
            return False
    
    async def subscribe(self, subject: str, consumer_name: str) -> Optional[Any]:
        """
        Subscribe to a subject with the specified consumer.
        
        Args:
            subject: Subject to subscribe to
            consumer_name: Name of the consumer
            
        Returns:
            Optional[Any]: Subscription object if successful, None otherwise
        """
        if not self.is_connected():
            print("Cannot subscribe: not connected to NATS")
            return None
            
        try:
            subscription = await self.js.pull_subscribe(subject, consumer_name)
            return subscription
        except Exception as e:
            print(f"Error subscribing to {subject}: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()
            return None
    
    async def fetch_messages(self, subscription, batch_size: int = 1, timeout: float = 1.0) -> List:
        """
        Fetch messages from a subscription.
        
        Args:
            subscription: The subscription to fetch messages from
            batch_size: Number of messages to fetch
            timeout: Time to wait for messages in seconds
            
        Returns:
            List: List of messages, empty list if none or error
        """
        if not self.is_connected():
            print("Cannot fetch messages: not connected to NATS")
            return []
            
        try:
            return await subscription.fetch(batch_size, timeout=timeout)
        except nats.errors.TimeoutError:
            # Normal when no messages are available
            return []
        except Exception as e:
            print(f"Error fetching messages: {e}")
            print("\nDetailed error information:")
            traceback.print_exc()
            return []
    
    async def close(self) -> None:
        """
        Close the connection to the NATS server.
        """
        if self.is_connected():
            try:
                await self.nc.close()
                print("NATS connection closed")
                self.nc = None
                self.js = None
            except Exception as e:
                print(f"Error closing NATS connection: {e}")
    
    def is_connected(self) -> bool:
        """
        Check if the client is connected to the NATS server.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.nc is not None and self.nc.is_connected