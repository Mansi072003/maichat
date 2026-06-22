# agents/tools/base_tool.py
"""
Base tool infrastructure for MAI agent tools.

Each tool is a callable with:
  - name, description, parameters (OpenAI function-calling schema)
  - async execute() that returns structured data

Agents use tools via the OpenAI function-calling API:
  1. LLM sees available tool schemas
  2. LLM decides which tools to call with what arguments
  3. Tool executes and returns data
  4. LLM uses tool results to compose the final answer
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseTool(ABC):
    """Abstract base for all agent tools."""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Run the tool and return structured data."""
        ...

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Holds a set of tools for an agent and handles execution."""

    def __init__(self, tools: Optional[List[BaseTool]] = None):
        self._tools: Dict[str, BaseTool] = {}
        for tool in (tools or []):
            self.register(tool)

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    @property
    def tool_list(self) -> List[BaseTool]:
        return list(self._tools.values())

    def openai_schemas(self) -> List[Dict[str, Any]]:
        """All tool schemas in the format expected by OpenAI's `tools` param."""
        return [t.to_openai_schema() for t in self._tools.values()]

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name and return its result as a JSON string."""
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            result = await tool.execute(**arguments)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Tool {tool_name} execution error: {e}")
            return json.dumps({"error": str(e)})


async def run_tool_calling_loop(
    client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    registry: ToolRegistry,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    max_iterations: int = 5,
) -> str:
    """
    Run the OpenAI tool-calling loop until the model produces a final text response.

    1. Send messages + tool schemas to LLM
    2. If LLM returns tool_calls → execute them, append results, loop
    3. If LLM returns content (no tool_calls) → return the text
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    tools = registry.openai_schemas()

    for iteration in range(max_iterations):
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" or (choice.message.tool_calls and len(choice.message.tool_calls) > 0):
            messages.append(choice.message)

            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                logger.info(f"Tool call [{iteration+1}]: {fn_name}({fn_args})")
                result_str = await registry.execute(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
        else:
            return choice.message.content.strip() if choice.message.content else ""

    logger.warning("Tool-calling loop hit max iterations; returning last content")
    return messages[-1].get("content", "") if isinstance(messages[-1], dict) else ""
