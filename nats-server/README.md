# NATS Server with JetStream

This directory contains configuration for running NATS server with JetStream enabled in Docker, along with utilities for working with NATS JetStream events.

## Contents

- `docker-compose.yml` - Docker Compose configuration for NATS server with JetStream enabled
- `.env` - Environment variables for Docker Compose
- `inspect_events.bat` - Utility script for monitoring and inspecting JetStream events
- `data/` - Persistence directory for NATS JetStream data

## Getting Started

### Start the NATS Server

To start the NATS server with JetStream enabled:

```bash
docker-compose up -d
```

This will start the NATS server in detached mode with the following ports exposed:
- 4222: Client connections
- 8222: HTTP monitoring
- 6222: Clustering

The server is configured to use JetStream with data persistence in the `./data` directory.

## Using the Event Inspector Utility

The `inspect_events.bat` script provides several commands to help you inspect and monitor NATS JetStream events related to file operations from the file events system.

### Command Syntax

The inspector script now supports customizable parameters:

```bash
inspect_events.bat [command] [options]
```

Where:
- `[command]` is one of: `stream`, `messages`, `consumer`, `watch`, `connections`, `monitor`, or `help`
- `[options]` are optional parameters to customize the command

### Available Options

The script supports the following options:

- `--stream=NAME` - Specify the stream name (default: FILES)
- `--server=URL` - Specify the NATS server URL (default: localhost:4222)
- `--consumer=NAME` - Specify the consumer name (default: file-monitor)
- `--subject=NAME` - Specify the subject name (default: file.events)

### Available Commands

#### Get Help

```bash
inspect_events.bat help
```

This displays the help message with available commands, options, and examples.

#### Stream Information

```bash
inspect_events.bat stream
# Or with custom stream and server
inspect_events.bat stream --stream=MY_STREAM --server=localhost:4222
```

This command shows information about the specified stream, including:
- Stream configuration
- Statistics (message counts, byte counts)
- Storage information
- Subject filters

Example output:
```
=== Stream Information ===
Stream: FILES
Server: localhost:4222

Information for Stream FILES

Configuration:

                     Name: FILES
                Subjects: file.events
                 Cluster: n/a
                  Server: NBFCCNP9I62D2THMKXHP3QJXS4V7LE7JBCHXAPZDYLJJQZPFRR7JVMKN
                    Msgs: 12
                     Bytes: 2.8 KiB
                   First: 2025-05-12T16:20:20Z
                    Last: 2025-05-12T16:45:33Z
```

#### View Stream Messages

```bash
inspect_events.bat messages
# Or with a custom stream
inspect_events.bat messages --stream=MY_STREAM
```

This command displays all the messages currently stored in the specified stream. This is useful for viewing the history of file events.

Example output:
```
=== Stream Messages ===
Stream: FILES
Server: localhost:4222

[1] Received at: 2025-05-12T16:28:45Z

{"path":"C:\\Users\\abou7\\DevLab\\workspaces\\dxw-space\\nats-events-adapter\\test\\storage\\test.txt","operation":"added","file_size":12.0,"timestamp":1746912525.0}
```

#### Consumer Information

```bash
inspect_events.bat consumer
# Or with custom consumer and stream
inspect_events.bat consumer --consumer=my-consumer --stream=MY_STREAM
```

This command shows information about the specified consumer, including:
- Consumer configuration
- Delivery statistics
- Acknowledgment information

Example output:
```
=== Consumer Information ===
Stream: FILES
Consumer: file-monitor
Server: localhost:4222

Information for Consumer FILES > file-monitor

Configuration:

        Durable Name: file-monitor
           Pull Mode: true
      Deliver Policy: new
```

#### Watch for New Messages

```bash
inspect_events.bat watch
# Or with custom subject and stream
inspect_events.bat watch --subject=custom.events --stream=MY_STREAM
```

This command watches for new messages in real-time on the specified subject, displaying them as they are published to the stream. This is especially useful for monitoring file events as they happen.

Press Ctrl+C to stop watching.

Example output:
```
=== Watching for New Messages ===
Subject: file.events
Stream: FILES
Server: localhost:4222
Press Ctrl+C to stop watching

16:47:23 Subscribing on file.events with acknowledgement
[#1] Received JetStream message: stream=FILES consumer=ephemeral_1684340843 subject=file.events
{"path":"C:\\Users\\abou7\\DevLab\\workspaces\\dxw-space\\nats-events-adapter\\test\\storage\\document.txt","operation":"added","file_size":0.0,"timestamp":1746913643.0}
```

#### View Active Connections

```bash
inspect_events.bat connections
```

This command displays all active connections to the NATS server, including both publishers and subscribers. It's useful for monitoring which clients are currently connected to your NATS server.

Example output:
```
=== Active NATS Connections ===
Server: localhost:4222

This will show all active connections including publishers and subscribers

ID: 7
    Server: nats-server
    IP: 172.18.0.1:52066
    Client ID: file-events-publisher
    Client Type: NATS
    Client Version: 
    RTT: 0s
    Uptime: 1m3s
    Last Activity: 2025-05-13T01:30:25.775251958Z
    Subscriptions: 0
    Subscriptions Pending: 0
    Messages Out: 5
    Messages In: 0
    Bytes Out: 645
    Bytes In: 0
    Slow Consumer: false
```

#### Open HTTP Monitoring Interface

```bash
inspect_events.bat monitor
```

This command opens the NATS HTTP monitoring interface in your default web browser. The interface provides a comprehensive dashboard for monitoring all aspects of your NATS server, including:

- Server information and statistics
- Connection details
- Stream metrics
- Consumer status
- Subscription information

The monitoring interface is accessible at http://localhost:8222/ and includes several useful endpoints:

- `/connz` - Information about current connections
- `/jsz` - JetStream statistics and information
- `/streamz` - Information about all streams
- `/subsz` - Information about subscriptions

This provides a user-friendly way to monitor your NATS server's health and activity.

## Troubleshooting

If you encounter issues with the NATS server or JetStream:

1. Check that the NATS server container is running:
   ```bash
   docker ps | findstr nats-server
   ```

2. Examine the NATS server logs:
   ```bash
   docker logs nats-server
   ```

3. Ensure the data directory has proper permissions for persistence.

4. If the `inspect_events.bat` commands are not working, verify your docker-compose.yml file includes `container_name: nats-server` to ensure the container name matches what the script expects.

5. If the monitoring interface isn't accessible, ensure that port 8222 is properly exposed in your docker-compose.yml file and not blocked by any firewall.

## Related Resources

- [NATS Documentation](https://docs.nats.io/)
- [JetStream Documentation](https://docs.nats.io/nats-concepts/jetstream)
- [NATS Monitoring Documentation](https://docs.nats.io/running-a-nats-service/configuration/monitoring)
- [File Events Adapter](../nats-events-adapter/README.md) - The companion application that uses this NATS server