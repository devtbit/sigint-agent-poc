import threading
import logging
import sys
import os
import atexit
import time
import datetime

# Import modules from our application
import database
import gqrx_client as gqrx
import chat_interface
import stream_groq_whisper

# Configure logging - do this before any other imports that might configure logging
# First, remove all existing handlers to ensure clean configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Create logs directory if it doesn't exist
logs_dir = "logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Generate timestamp for the log file
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = os.path.join(logs_dir, f"{timestamp}_sigint_agent.log")

# Configure a file handler
file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure the root logger
logging.root.setLevel(logging.INFO)
logging.root.addHandler(file_handler)

# Import from agent after logging is configured
from agent import run as run_agent

logger = logging.getLogger("sigint_app")
logger.info(f"Logging to: {log_filename}")


def initialize_system():
    """Initialize the system by setting up the database and getting the current frequency."""
    logger.info("Initializing system")

    # Initialize database
    database.initialize_db()
    logger.info("Database initialized")

    # Get current frequency from GQRX and create a session
    frequency = None
    try:
        logger.info("Getting current frequency from GQRX")
        frequency = gqrx.send("f")
        gqrx.close()
    except Exception as e:
        logger.error(f"Error getting current frequency: {e}")
        gqrx.close()

    if frequency:
        database.save_session(frequency)
        logger.info(f"Initialized session with frequency: {frequency}")
    else:
        logger.warning("Failed to get frequency, session initialized without frequency")


def cleanup():
    """Cleanup function to be called when the application exits."""
    logger.info("Cleaning up before exit")
    try:
        # First, reset terminal settings to ensure they're restored properly
        chat_interface.reset_terminal()

        # Then stop the audio stream processing
        stream_groq_whisper.stop_audio_stream()

        # Add a small sleep to ensure cleanup messages are displayed
        time.sleep(0.1)

        # Print a final message to confirm cleanup is complete
        print("\nTerminal settings restored. Application exited cleanly.")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


def main():
    """Main function to run the application."""
    logger.info("Starting SIGINT Agent Application")

    try:
        # Initialize system (database and initial frequency)
        initialize_system()

        # Register cleanup function to be called on exit
        atexit.register(cleanup)

        # Set up signal handlers for more reliable cleanup
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda signum, frame: sys.exit(0))

        # Start the audio stream processing in a background thread
        logger.info("Starting audio stream processing")
        audio_thread = stream_groq_whisper.run_audio_stream()
        logger.info("Audio stream processing started")

        # Run the chat interface (main thread)
        logger.info("Starting chat interface")
        chat_interface.run()

    except Exception as e:
        logger.error(f"Fatal error in main application: {e}", exc_info=True)
        print(f"Fatal error: {e}")
    finally:
        logger.info("SIGINT Agent Application shutting down")
        # Ensure cleanup is called (in case atexit doesn't trigger)
        cleanup()


if __name__ == "__main__":
    main()
