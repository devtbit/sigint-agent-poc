from langchain_groq import ChatGroq
from langchain.tools import tool

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent


# LangGraph Memory
memory = MemorySaver()


@tool
def gqrx_sweep(min_range: int,
               max_range: int) -> [float]:
    """
    Performs a sweep scan of the range frequency to find most
    active stations. Returns a list of the frequencies found
    in MHz.
    """
    return [
        459.190,
        457.615,
        457.277,
    ]


def load_text_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    return content


def init_graph():
    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile")
    main_prompt = load_text_file("prompts/main.txt")

    tools = [gqrx_sweep]

    return create_react_agent(llm,
                              tools,
                              checkpointer=memory,
                              state_modifier=main_prompt)


user_id = "sigint1"

graph = init_graph()

input_message_use_case_1 = "Find any frequency where human conversation is happening in the ranges: 456MHz - 460MHz"  # noqa

# TODO: requires plan-execute agent architecture
# input_message_use_case_2 = "Find frequencies where anyone is discussing or talking about a library in the ranges: 456000.000kHz - 460000.000kHz"  # noqa

response = graph.invoke(
    {"messages": [("user", input_message_use_case_1)]},
    config={"configurable": {"thread_id": user_id}})

print(response, flush=True)
