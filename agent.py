from groq import Groq
import json
import os
import logging

from tools import tool_definitions, available_tools

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


def run(message: str):
    msg_preview = message[:50] + "..." if len(message) > 50 else message
    logger.info(f"Processing message: {msg_preview}")
    messages.append({"role": "user", "content": message})

    logger.debug("Sending request to GROQ API")
    response = groq.chat.completions.create(
        model=model,
        messages=messages,
        tools=tool_definitions,
        tool_choice="auto",
        max_tokens=4096,
    )

    response_message = response.choices[0].message
    messages.append(response_message)

    tool_calls = response_message.tool_calls
    if tool_calls:
        logger.info(f"Received tool calls: {len(tool_calls)}")

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
