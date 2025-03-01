from groq import Groq
import json
import os
import logging

from tools import tool_definitions, available_tools

# Get logger for this module
logger = logging.getLogger("sigint_agent")

groq = Groq()
model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
temperature = 0.5
logger.info(f"Using GROQ model: {model}")

messages = [
    {
        "role": "system",
        "content": open("prompts/main.txt").read()
    }
]
logger.debug("Loaded system prompt")


def run(message: str, stream_handler=None):
    msg_preview = message[:50] + "..." if len(message) > 50 else message
    logger.info(f"Processing message: {msg_preview}")
    messages.append({"role": "user", "content": message})

    logger.debug("Sending request to GROQ API")

    # If stream_handler is provided, use streaming mode
    if stream_handler:
        response_stream = groq.chat.completions.create(
            model=model,
            messages=messages,
            tools=tool_definitions,
            tool_choice="auto",
            max_tokens=4096,
            stream=True,
            temperature=temperature,
        )

        # Process streaming response
        final_response = process_streaming_response(
            response_stream, stream_handler)
        return final_response
    else:
        # Original non-streaming implementation
        response = groq.chat.completions.create(
            model=model,
            messages=messages,
            tools=tool_definitions,
            tool_choice="auto",
            max_tokens=4096,
            temperature=temperature,
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
                temperature=temperature,
            )

            response_message = response.choices[0].message
            messages.append(response_message)
            logger.info("Received final response from GROQ API")

            return response_message.content

        logger.info("Received direct response from GROQ API (no tool calls)")
        return response_message.content


def process_streaming_response(response_stream, stream_handler):
    """Process a streaming response from GROQ API."""
    collected_message = {"content": "", "tool_calls": []}
    current_tool_call = None

    for chunk in response_stream:
        delta = chunk.choices[0].delta

        # Handle content chunks
        if delta.content:
            collected_message["content"] += delta.content
            stream_handler(delta.content)

        # Handle tool call chunks
        if delta.tool_calls:
            for tool_call_delta in delta.tool_calls:
                if tool_call_delta.index is not None:
                    idx = tool_call_delta.index

                    # Extend the tool_calls list if needed
                    while len(collected_message["tool_calls"]) <= idx:
                        collected_message["tool_calls"].append({
                            "id": "",
                            "function": {"name": "", "arguments": ""},
                            "type": "function"
                        })

                    current_tool_call = collected_message["tool_calls"][idx]

                    # Update tool call data
                    if tool_call_delta.id:
                        current_tool_call["id"] = tool_call_delta.id

                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            current_tool_call["function"]["name"] = \
                                tool_call_delta.function.name

                        if tool_call_delta.function.arguments:
                            current_tool_call["function"]["arguments"] += \
                                tool_call_delta.function.arguments

    # Add the collected message to our messages history
    if collected_message["content"] or collected_message["tool_calls"]:
        final_message = {
            "role": "assistant",
            "content": collected_message["content"]
        }
        if collected_message["tool_calls"]:
            final_message["tool_calls"] = collected_message["tool_calls"]
        messages.append(final_message)

    # Process tool calls if any
    if collected_message["tool_calls"]:
        logger.info(
            f"Received tool calls: {len(collected_message['tool_calls'])}")

        for tool_call in collected_message["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            logger.info(f"Executing tool call: {tool_name}")
            tool_function = available_tools[tool_name]
            tool_args = json.loads(tool_call["function"]["arguments"])
            logger.debug(f"Tool arguments: {tool_args}")
            result = tool_function(**tool_args)
            messages.append(
                {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call["id"],
                    "name": tool_name
                }
            )

        # After tool calls, we need a follow-up response
        logger.debug("Sending follow-up request to GROQ API")
        response = groq.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
            stream=True,
            temperature=temperature,
        )

        # Stream the follow-up response
        second_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                second_response += content
                stream_handler(content)

        # Add the final response to messages
        messages.append({"role": "assistant", "content": second_response})
        logger.info("Received final response from GROQ API")

        return second_response

    return collected_message["content"]
