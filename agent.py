from groq import Groq
import json
import os
import logging

from database import save_session, get_last_transcripts, get_transcripts
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
                        "description": "The frequency to set the GQRX receiver"
                                       " to in Hz."
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_10_minutes",
            "description": "Get the last 10 minutes of transcripts for "
                           "a given frequency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "frequency": {
                        "type": "integer",
                        "description": "The frequency to get transcripts for."
                    }
                },
                "required": ["frequency"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_frequency_summary",
            "description": "Get a summary of the intercepted communications "
                           "for a given frequency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "frequency": {
                        "type": "integer",
                        "description": "The frequency to get a summary for."
                    }
                },
                "required": ["frequency"]
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
        logger.info(
            f"Successfully set frequency to {frequency} Hz."
            f" Response: {response}"
        )
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


def get_last_10_minutes(frequency: int):
    """Get the last 10 minutes of transcripts for a given frequency."""
    logger.info(
        "Getting last 10 minutes of transcripts for frequency: "
        f"{frequency} Hz")
    result = None
    try:
        transcripts = get_last_transcripts(frequency, 10)
        logger.info(f"Found {len(transcripts)} transcripts")
        result = json.dumps({
            "result": [
                {
                    "timestamp": transcript.timestamp.isoformat(),
                    "text": transcript.text
                }
                for transcript in transcripts
            ]
        })
    except Exception as e:
        logger.error(
            "Error getting last 10 minutes of transcripts: "
            f"{e}", exc_info=True)
        result = json.dumps({"error": str(e)})
    return result


def get_frequency_summary(frequency: int):
    """
    Get a summary of the intercepted communications
    for a given frequency.
    """
    logger.info(f"Getting summary for frequency: {frequency} Hz")
    result = None
    try:
        transcripts = get_transcripts(frequency, 250)
        logger.info(f"Found {len(transcripts)} transcripts for summarization")
        summary = summarize_transcripts(transcripts)
        logger.info(f"Summary: {summary}")
        if summary:
            result = json.dumps({"result": summary})
        else:
            result = json.dumps({"error": "No summary found"})
    except Exception as e:
        logger.error(f"Error getting summary: {e}", exc_info=True)
        result = json.dumps({"error": str(e)})
    return result


def summarize_transcripts(transcripts: list):
    """Summarize the intercepted communications."""
    logger.info("Summarizing transcripts")
    summary = None
    try:
        # Load the summarization prompt
        with open("prompts/summarization.txt", "r") as f:
            summarization_prompt = f.read()

        # Create a list of transcripts for the prompt
        transcripts_list = [
            f"[{i+1}] {t.text}"
            for i, t in enumerate(transcripts)
        ]
        transcripts_str = "\n".join(transcripts_list)

        # Create the prompt
        prompt = summarization_prompt.format(transcripts=transcripts_str)

        # Send the prompt to GROQ
        response = groq.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt}],
            max_tokens=4096,
        )

        # Get the summary from the response
        summary = response.choices[0].message.content
        logger.info(f"Summary: {summary}")
    except Exception as e:
        logger.error(f"Error summarizing transcripts: {e}", exc_info=True)
    return summary


def run(message: str):
    msg_preview = message[:50] + "..." if len(message) > 50 else message
    logger.info(f"Processing message: {msg_preview}")
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
    messages.append(response_message)

    tool_calls = response_message.tool_calls
    if tool_calls:
        logger.info(f"Received tool calls: {len(tool_calls)}")
        available_tools = {
            "set_frequency": set_frequency,
            "get_current_frequency": get_current_frequency,
            "get_last_10_minutes": get_last_10_minutes,
            "get_frequency_summary": get_frequency_summary
        }

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
