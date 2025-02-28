import threading
import logging
import sys
import os

# Import modules from our application
import database
import gqrx_client as gqrx
import chat_interface

# Configure logging - do this before any other imports that might configure logging
# First, remove all existing handlers to ensure clean configuration
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Configure a file handler
file_handler = logging.FileHandler("sigint_agent.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure the root logger
logging.root.setLevel(logging.INFO)
logging.root.addHandler(file_handler)

# Import from agent after logging is configured
from agent import run as run_agent

logger = logging.getLogger("sigint_app")


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


def main():
    """Main function to run the application."""
    logger.info("Starting SIGINT Agent Application")

    try:
        # Initialize system (database and initial frequency)
        initialize_system()

        # Run the chat interface (main thread)
        chat_interface.run()

    except Exception as e:
        logger.error(f"Fatal error in main application: {e}", exc_info=True)
        print(f"Fatal error: {e}")
    finally:
        logger.info("SIGINT Agent Application shutting down")


if __name__ == "__main__":
    main()
