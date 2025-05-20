@echo off
:: ===================================================================
:: NATS JetStream Inspector
:: ===================================================================
:: This script provides utilities to inspect and monitor NATS JetStream
:: events for the file events system.
::
:: Usage:
::   inspect_events.bat [command] [options]
::
:: Commands:
::   stream   - Show information about a stream
::   messages - Display messages in a stream
::   consumer - Show information about a consumer
::   watch    - Watch for new messages in real-time
::   connections - List all active connections (publishers & subscribers)
::   monitor - Open the HTTP monitoring interface in the default browser
::   help     - Display this help message
::
:: Options:
::   --stream=NAME  - Stream name (default: FILES)
::   --server=URL   - NATS server URL (default: nats:4222 for Docker, localhost:4222 for local)
::   --consumer=NAME - Consumer name (default: file-monitor)
::   --subject=NAME - Subject name (default: file.events)
::
:: Examples:
::   inspect_events.bat stream
::   inspect_events.bat messages --stream=ORDERS
::   inspect_events.bat watch --subject=order.events
::   inspect_events.bat consumer --consumer=my-consumer
:: ===================================================================

:: Default Configuration
set NATS_BOX_CONTAINER=nats-box
set DEFAULT_NATS_SERVER_DOCKER=nats:4222
set DEFAULT_NATS_SERVER_LOCAL=localhost:4222
set DEFAULT_STREAM_NAME=FILES
set DEFAULT_SUBJECT=file.events
set DEFAULT_CONSUMER=file-monitor

:: Check if NATS CLI is installed locally
where nats >nul 2>&1
if %ERRORLEVEL% == 0 (
    set USE_LOCAL_CLI=true
    set DEFAULT_NATS_SERVER=%DEFAULT_NATS_SERVER_LOCAL%
    echo Using local NATS CLI installation
) else (
    set USE_LOCAL_CLI=false
    set DEFAULT_NATS_SERVER=%DEFAULT_NATS_SERVER_DOCKER%
    echo NATS CLI not found locally, using Docker container
)

:: Initialize with defaults
set NATS_SERVER=%DEFAULT_NATS_SERVER%
set STREAM_NAME=%DEFAULT_STREAM_NAME%
set SUBJECT=%DEFAULT_SUBJECT%
set CONSUMER=%DEFAULT_CONSUMER%

:: Parse command
set COMMAND=%1
if "%COMMAND%"=="" goto :help
if /i "%COMMAND%"=="help" goto :help

:: Parse options (arguments after the command)
shift
:parse_args
if "%1"=="" goto :execute_command

set ARG=%1

set PREFIX=%ARG:~0,9%
if "%PREFIX%"=="--stream" (
    shift
    call set STREAM_NAME=%%1
    shift
    goto :parse_args
)

set PREFIX=%ARG:~0,9%
if "%PREFIX%"=="--server" (
    shift
    ::set NATS_SERVER=%ARG:~9%
    call set NATS_SERVER=%%1
    shift
    goto :parse_args
)

set PREFIX=%ARG:~0,11%
if "%PREFIX%"=="--consumer" (
    shift
    call set CONSUMER=%%1
    shift
    goto :parse_args
)

set PREFIX=%ARG:~0,10%
if "%PREFIX%"=="--subject" (
    shift
    call set SUBJECT=%%1
    shift
    goto :parse_args
)

:: Unknown option - ignore and continue
shift
goto :parse_args

:execute_command
:: Execute the requested command
if /i "%COMMAND%"=="stream" goto :stream
if /i "%COMMAND%"=="messages" goto :messages
if /i "%COMMAND%"=="consumer" goto :consumer
if /i "%COMMAND%"=="watch" goto :watch
if /i "%COMMAND%"=="connections" goto :connections
if /i "%COMMAND%"=="monitor" goto :monitor
goto :help

:help
echo.
echo NATS JetStream Inspector
echo =======================
echo.
echo This script provides utilities to inspect and monitor NATS JetStream
echo events for the file events system.
echo.
echo Commands:
echo   stream      - Show information about a stream
echo   messages    - Display messages in a stream
echo   consumer    - Show information about a consumer
echo   watch       - Watch for new messages in real-time
echo   connections - List all active connections (publishers & subscribers)
echo   monitor     - Open the HTTP monitoring interface in the default browser
echo   help        - Display this help message
echo.
echo Options:
echo   --stream=NAME   - Stream name (default: %DEFAULT_STREAM_NAME%)
echo   --server=URL    - NATS server URL (default: %DEFAULT_NATS_SERVER%)
echo   --consumer=NAME - Consumer name (default: %DEFAULT_CONSUMER%)
echo   --subject=NAME  - Subject name (default: %DEFAULT_SUBJECT%)
echo.
echo Using: %USE_LOCAL_CLI% CLI installation
echo.
echo Examples:
echo   inspect_events.bat stream
echo   inspect_events.bat messages --stream=ORDERS
echo   inspect_events.bat watch --subject=order.events
echo   inspect_events.bat consumer --consumer=my-consumer
goto :eof

:stream
echo.
echo === Stream Information ===
echo Stream: %STREAM_NAME%
echo Server: %NATS_SERVER%
echo.
if %USE_LOCAL_CLI%==true (
    :: Use local NATS CLI
    nats stream info %STREAM_NAME% --server=%NATS_SERVER%
) else (
    :: Use the nats-box container
    echo DEBUG: docker exec %NATS_BOX_CONTAINER% nats stream info %STREAM_NAME% --server=%NATS_SERVER%
    docker exec %NATS_BOX_CONTAINER% nats stream info %STREAM_NAME% --server=%NATS_SERVER%
)
goto :eof

:messages
echo.
echo === Stream Messages ===
echo Stream: %STREAM_NAME%
echo Server: %NATS_SERVER%
echo.
if %USE_LOCAL_CLI%==true (
    :: Use local NATS CLI with raw option to avoid paging issues
    nats stream view %STREAM_NAME% --server=%NATS_SERVER% --raw
) else (
    :: Use the nats-box container with raw option
    docker exec %NATS_BOX_CONTAINER% nats stream view %STREAM_NAME% --server=%NATS_SERVER% --raw
)
goto :eof

:consumer
echo.
echo === Consumer Information ===
echo Stream: %STREAM_NAME%
echo Consumer: %CONSUMER%
echo Server: %NATS_SERVER%
echo.
if %USE_LOCAL_CLI%==true (
    :: Use local NATS CLI
    nats consumer info %STREAM_NAME% %CONSUMER% --server=%NATS_SERVER%
) else (
    :: Use the nats-box container
    docker exec %NATS_BOX_CONTAINER% nats consumer info %STREAM_NAME% %CONSUMER% --server=%NATS_SERVER%
)
goto :eof

:connections
echo.
echo === Active NATS Connections ===
echo Server: %NATS_SERVER%
echo.
echo This will show all active connections including publishers and subscribers
echo.
if %USE_LOCAL_CLI%==true (
    :: Use local NATS CLI with system account
    nats server report connections --server=%NATS_SERVER%
) else (
    :: Use the nats-box container with system account
    docker exec %NATS_BOX_CONTAINER% nats server report connections --server=%NATS_SERVER%
)
goto :eof

:monitor
echo.
echo === Opening NATS HTTP Monitoring Interface ===
echo.
echo Launching web browser with NATS monitoring dashboard...
start http://localhost:8222/
goto :eof

:watch
echo.
echo === Watching for New Messages ===
echo Subject: %SUBJECT%
echo Stream: %STREAM_NAME%
echo Server: %NATS_SERVER%
echo Press Ctrl+C to stop watching
echo.
if %USE_LOCAL_CLI%==true (
    :: Use local NATS CLI
    nats sub --stream=%STREAM_NAME% %SUBJECT% --server=%NATS_SERVER%
) else (
    :: Use the nats-box container with interactive mode
    docker exec -it %NATS_BOX_CONTAINER% nats sub --stream=%STREAM_NAME% %SUBJECT% --server=%NATS_SERVER%
)
goto :eof