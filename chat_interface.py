import logging
import sys
import select
import termios
import tty
import time

# Import agent module
from agent import run as run_agent

logger = logging.getLogger("chat_interface")

# Store old_settings as a global variable so it can be accessed for cleanup
old_settings = None


def reset_terminal():
    """Reset terminal settings to their original state.
    This function is meant to be called during application cleanup."""
    global old_settings

    if old_settings:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            logger.info("Terminal settings have been restored")
            # Write a newline to ensure cursor position is reset
            sys.stdout.write('\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error resetting terminal: {e}")


def run():
    """Run the chat-like interface in the terminal."""
    global old_settings

    logger.info("Starting chat interface")

    sigint_ascii = """
============================================================
 .d8888b.  8888888 .d8888b.  8888888 888b    888 88888888888
d88P  Y88b   888  d88P  Y88b   888   8888b   888     888
Y88b.        888  888    888   888   88888b  888     888
 "Y888b.     888  888          888   888Y88b 888     888
    "Y88b.   888  888  88888   888   888 Y88b888     888
      "888   888  888    888   888   888  Y88888     888
Y88b  d88P   888  Y88b  d88P   888   888   Y8888     888
 "Y8888P"  8888888 "Y8888P"  8888888 888    Y888     888

       d8888  .d8888b.  8888888888 888b    888 88888888888
      d88888 d88P  Y88b 888        8888b   888     888
     d88P888 888    888 888        88888b  888     888
    d88P 888 888        8888888    888Y88b 888     888
   d88P  888 888  88888 888        888 Y88b888     888
  d88P   888 888    888 888        888  Y88888     888
 d8888888888 Y88b  d88P 888        888   Y8888     888
d88P     888  "Y8888P"  8888888888 888    Y888     888
============================================================
                                                      v0.1.0
"""
    print(sigint_ascii)
    print("Type '.exit' or '.quit' to end the session")
    print("============================================================\n")

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
                time.sleep(0.01)

            # Restore terminal settings for normal processing
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            # Check for exit command
            if user_input.lower() in ['.exit', '.quit']:
                print("Exiting application...")
                break

            # Process the user's message using the agent
            response = run_agent(user_input)
            print(f"\nOperator: {response}")

    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Exiting application...")
    except Exception as e:
        logger.error(f"Error in chat interface: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")
    finally:
        # Restore terminal settings
        reset_terminal()
