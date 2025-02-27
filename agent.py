from groq import Groq
import json
import os

import gqrx_client as gqrx

groq = Groq()
model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

messages = [
    {
        "role": "system",
        "content": open("prompts/main.txt").read()
    }
]

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
    }
]


def set_frequency(frequency: int):
    """
    Set the frequency of the GQRX receiver.
    """
    result = None
    try:
        response = gqrx.send(f"F {frequency}")
        result = json.dumps({"result": response})
    except Exception as e:
        result = json.dumps({"error": str(e)})
    finally:
        gqrx.close()

    return result


def run(message: str):
    messages.append({"role": "user", "content": message})
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
        available_tools = {
            "set_frequency": set_frequency
        }

        messages.append(response_message)

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_function = available_tools[tool_name]
            tool_args = json.loads(tool_call.function.arguments)
            result = tool_function(**tool_args)
            messages.append(
                {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_call.id,
                    "name": tool_name
                }
            )
        
        response = groq.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
        )

        response_message = response.choices[0].message
        messages.append(response_message)

        return response_message.content
    
    return response_message.content

if __name__ == "__main__":
    print(run("Set the frequency to 457.202 MHz."))