# Implementing a ReAct Agent with LangGraph (Notebook Style)

This guide maps the patterns from **LangGraph_React - MCP + Tool Selection.ipynb** to the pipeshub-ai codebase.

**Implementation status:** The ReAct agent is **enabled by default** for all agent chat flows. The API (`app/api/routes/agent.py`) uses `modern_agent_graph` (single-node ReAct) for:
- Non-streaming agent chat (`askAI`-style and `/{agent_id}/chat`)
- Streaming agent chat (`stream_response` / `agent-chat-stream`)

To use the legacy multi-node graph (planner → execute → reflect → respond) instead, set the environment variable:
`USE_LEGACY_AGENT_GRAPH=1` (or `true`/`yes`).

## 1. Basic ReAct agent (notebook pattern)

In the notebook, a ReAct agent is created and invoked like this:

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")
tools = [...]  # list of LangChain tools

# Create agent (compiled graph). create_react_agent was moved from langgraph.prebuilt to langchain.agents.
agent = create_agent(llm, tools, system_prompt="Today is November 12th, 2025")

# Invoke with messages
response = await agent.ainvoke({"messages": [HumanMessage(content="What's the weather in SF?")]})
# or with a single string: agent.ainvoke({"messages": "What's the weather?"})
```

**State shape:** The prebuilt ReAct agent uses a state with a `messages` key (message list). Input and output are both `{"messages": [...]}`.

## 2. Where this lives in pipeshub-ai

- **Graph:** `backend/python/app/modules/agents/qna/graph.py`
  - `create_modern_agent_graph()` builds a graph with a single node: the ReAct agent.
  - Flow: `Entry → react_agent_node → END`.

- **Node:** `backend/python/app/modules/agents/qna/nodes.py`
  - `react_agent_node(state, config, writer)`:
    - Loads tools via `get_agent_tools_with_schemas(state)`.
    - Builds a system prompt with `_build_react_system_prompt(state, log)`.
    - Creates the agent (see below), runs it with the current query and streams chunks via `writer`.
    - Handles retrieval citations and tool results, then streams the final answer.

- **Tools:** `backend/python/app/modules/agents/qna/tool_system.py`
  - `get_agent_tools_with_schemas(state)` returns the list of tools (with Pydantic schemas) for the current agent/context.

So the “notebook-style” ReAct loop (LLM → tool calls → tool results → LLM → …) is implemented inside `react_agent_node`, using the same idea as the notebook but wired to your `ChatState`, streaming, and citation logic.

## 3. Using LangGraph’s prebuilt ReAct agent

To align with the notebook and use LangGraph’s prebuilt ReAct agent:

1. **Create the agent with `create_agent`**

   In `react_agent_node`, use (recommended API; `create_react_agent` was moved from `langgraph.prebuilt` to `langchain.agents`):

   ```python
   from langchain.agents import create_agent

   agent = create_agent(
       llm,
       tools,
       system_prompt=system_prompt,
   )
   ```

   For a **dynamic system prompt**, build the string from state before calling `create_agent` (as in `react_agent_node` via `_build_react_system_prompt`), or use a callable if the API supports it.

2. **Run and stream**

   - Input: `{"messages": [SystemMessage(...), HumanMessage(content=query)]}` (or inject system via `state_modifier`).
   - Stream: `async for chunk in agent.astream({"messages": messages}, config=config):`
   - Process `chunk["messages"]` and forward to your `writer` (e.g. `_process_react_chunk`).

3. **State**

   - The prebuilt agent expects and returns state with `messages` only. Your node can still read/write `state["final_results"]`, `state["tool_records"]`, etc., before/after calling the agent; only the dict you pass into `agent.ainvoke` / `agent.astream` needs to have `messages`.

## 4. Turning the ReAct agent into a chat (notebook pattern)

The notebook wraps the agent in a small graph with a user-input node and a loop:

```python
from langgraph.graph import MessagesState, StateGraph, END

class ConvoState(MessagesState):
    end: bool

def get_user_input(state):
    user_msg = input("\n🧑 You: ")
    if user_msg.strip().lower() == "exit":
        return {"end": True}
    return {"messages": [HumanMessage(content=user_msg)]}

def run_agent(state):
    response = agent_executor.invoke({"messages": state["messages"]})
    return {"messages": [AIMessage(content=response["messages"][-1].content)]}

graph_builder = StateGraph(ConvoState)
graph_builder.add_node("get_user_input", get_user_input)
graph_builder.add_node("run_agent", run_agent)
graph_builder.set_entry_point("get_user_input")
graph_builder.add_conditional_edges("get_user_input", lambda s: "end" if s.get("end") else "go", {"end": END, "go": "run_agent"})
graph_builder.add_edge("run_agent", "get_user_input")
graph = graph_builder.compile()
```

In pipeshub-ai, the “chat” loop is already handled by your API and frontend: each request is one turn. You don’t need this exact wrapper unless you are building a standalone CLI/chat loop; your `modern_agent_graph` plus the route that invokes it already provide the same “user message → agent → response” flow per request.

## 5. MCP + tool selection (notebook pattern)

The notebook loads tools from an MCP server and passes them to the same ReAct agent:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        mcp_tools = await load_mcp_tools(session)
        agent = create_react_agent(llm, mcp_tools)
        response = await agent.ainvoke({"messages": "what's the current price of bitcoin times 12?"})
```

To use MCP tools in pipeshub-ai:

1. In a separate async context (or at agent build time), connect to your MCP server and call `load_mcp_tools(session)`.
2. Combine `mcp_tools` with your existing tools (e.g. from `get_agent_tools_with_schemas`) if you want both.
3. Pass the combined list into `create_react_agent(llm, all_tools, ...)` inside `react_agent_node`.

Tool selection (which tool to call and with what arguments) is handled by the ReAct agent itself; you don’t need extra “tool selection” logic unless you want to pre-filter tools (e.g. by user permissions or toolset config), which you already do via `get_agent_tools_with_schemas`.

## 6. Summary

| Notebook concept              | In pipeshub-ai                                      |
|-------------------------------|-----------------------------------------------------|
| `create_agent(llm, tools, system_prompt=...)` | Use in `react_agent_node` (`from langchain.agents import create_agent`) |
| `agent.ainvoke({"messages": ...})` | `agent.astream({"messages": messages}, config)` in the node |
| System prompt                 | `_build_react_system_prompt(state, log)` or `state_modifier` |
| Tools                         | `get_agent_tools_with_schemas(state)` (+ optional MCP tools) |
| Chat loop                     | Handled by API/frontend; one turn per request       |
| MCP tools                     | `load_mcp_tools(session)` and merge with existing tools |

Using `create_react_agent` from `langgraph.prebuilt` in `react_agent_node` gives you the same ReAct + tool-selection behavior as in the notebook, with your existing streaming, citations, and tool results handling preserved.
