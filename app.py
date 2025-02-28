import threading
import logging
import sys
import os

# Import modules from our application
import database
import gqrx_client as gqrx

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

# Now import modules that might also configure logging
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


def run_chat_interface():
    """Run the chat-like interface in the terminal."""
    logger.info("Starting chat interface")
    print("\n==== SIGINT Agent Chat Interface ====")
    print("Type '.exit' or '.quit' to end the session")
    print("======================================\n")

    # Use a different approach to get input that won't be affected by ffmpeg
    import select
    import termios
    import tty

    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        while True:
            # Print prompt
            sys.stdout.write("\nYou: ")
            sys.stdout.flush()

            # Collect input
            user_input = ""

            # Set terminal to raw mode to read characters one by one
            tty.setraw(sys.stdin.fileno())

            while True:
                # Check if there's input ready to be read
                if select.select([sys.stdin], [], [], 0)[0]:
                    char = sys.stdin.read(1)

                    # Handle special keys
                    if ord(char) == 3:  # Ctrl+C
                        raise KeyboardInterrupt

                    # Handle Enter key
                    if char == '\r' or char == '\n':
                        sys.stdout.write('\n')
                        sys.stdout.flush()
                        break

                    # Handle backspace
                    if ord(char) == 127:
                        if user_input:
                            user_input = user_input[:-1]
                            sys.stdout.write('\b \b')  # Erase character
                            sys.stdout.flush()
                    else:
                        user_input += char
                        sys.stdout.write(char)
                        sys.stdout.flush()

                # Yield to other threads, prevents CPU hogging
                import time
                time.sleep(0.01)

            # Restore terminal settings for normal processing
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            # Check for exit command
            if user_input.lower() in ['.exit', '.quit']:
                print("Exiting application...")
                break

            # Process the user's message using the agent
            response = run_agent(user_input)
            print(f"\nAgent: {response}")

    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Exiting application...")
    except Exception as e:
        logger.error(f"Error in chat interface: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def main():
    """Main function to run the application."""
    logger.info("Starting SIGINT Agent Application")

    try:
        # Initialize system (database and initial frequency)
        initialize_system()

        # Run the chat interface (main thread)
        run_chat_interface()

    except Exception as e:
        logger.error(f"Fatal error in main application: {e}", exc_info=True)
        print(f"Fatal error: {e}")
    finally:
        logger.info("SIGINT Agent Application shutting down")


if __name__ == "__main__":
    main()
