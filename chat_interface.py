import logging
import sys
import select
import termios
import tty
import time

# Import agent module
from agent import run as run_agent

logger = logging.getLogger("chat_interface")

def run():
    """Run the chat-like interface in the terminal."""
    logger.info("Starting chat interface")
    print("\n==== SIGINT Agent Chat Interface ====")
    print("Type '.exit' or '.quit' to end the session")
    print("======================================\n")

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
            print(f"\nAgent: {response}")

    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Exiting application...")
    except Exception as e:
        logger.error(f"Error in chat interface: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings) 