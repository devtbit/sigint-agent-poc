from groq import Groq
import json
import os
import logging

from database import save_session
import gqrx_client as gqrx

# Get logger for this module
logger = logging.getLogger("sigint_agent")

groq = Groq()
model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
logger.info(f"Using GROQ model: {model}")

messages = [
    {
        "role": "system",
        "content": open("prompts/main.txt").read()
    }
]
logger.debug("Loaded system prompt")

tools = [
    {
        "type": "function",
        "function": {
            "name": "set_frequency",
            "description": "Set the frequency of the GQRX receiver.",
            "parameters": {
                "type": "object",
                "properties": {
                    "frequency": {
                        "type": "integer",
                        "description": "The frequency to set the GQRX receiver to in Hz."
                    }
                },
                "required": ["frequency"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_frequency",
            "description": "Get the current frequency from the GQRX receiver.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]
logger.debug("Initialized available tools")


def set_frequency(frequency: int):
    """
    Set the frequency of the GQRX receiver.
    """
    logger.info(f"Setting GQRX frequency to {frequency} Hz")
    result = None
    try:
        response = gqrx.send(f"F {frequency}")
        result = json.dumps({"result": response})
        logger.info(f"Successfully set frequency to {frequency} Hz. Response: {response}")
        save_session(frequency)
        logger.debug(f"Saved frequency {frequency} to session database")
    except Exception as e:
        logger.error(f"Error setting frequency: {e}", exc_info=True)
        result = json.dumps({"error": str(e)})
    finally:
        gqrx.close()

    return result


def get_current_frequency():
    """Get the current frequency from the GQRX receiver."""
    logger.info("Getting current GQRX frequency")
    result = None
    try:
        response = gqrx.send("f")
        logger.info(f"Current frequency: {response} Hz")
        result = json.dumps({"result": response})
    except Exception as e:
        logger.error(f"Error getting frequency: {e}", exc_info=True)
        result = json.dumps({"error": str(e)})
    finally:
        gqrx.close()
    return result


def run(message: str):
    logger.info(f"Processing message: {message[:50]}..." if len(message) > 50 else f"Processing message: {message}")
    messages.append({"role": "user", "content": message})
    
    logger.debug("Sending request to GROQ API")
    response = groq.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        max_tokens=4096,
    )
    
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    if tool_calls:
        logger.info(f"Received tool calls: {len(tool_calls)}")
        available_tools = {
            "set_frequency": set_frequency,
            "get_current_frequency": get_current_frequency
        }

        messages.append(response_message)

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            logger.info(f"Executing tool call: {tool_name}")
            tool_function = available_tools[tool_name]
            tool_args = json.loads(tool_call.function.arguments)
            logger.debug(f"Tool arguments: {tool_args}")
            result = tool_function(**tool_args)
            messages.append(
                {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call.id,
                    "name": tool_name
                }
            )
        
        logger.debug("Sending follow-up request to GROQ API")
        response = groq.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
        )

        response_message = response.choices[0].message
        messages.append(response_message)
        logger.info("Received final response from GROQ API")

        return response_message.content
    
    logger.info("Received direct response from GROQ API (no tool calls)")
    return response_message.content