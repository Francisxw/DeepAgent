"""
Tool Calling Context Usage Simulation

Simulates how tool definitions and tool calls consume context window
over a multi-turn conversation with multiple tool calls.
"""

import tiktoken
import json
from dataclasses import dataclass
from typing import List, Dict, Any


def count_tokens(text: str) -> int:
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


@dataclass
class Message:
    role: str
    content: str
    tool_calls: List[Dict] = None
    tool_call_id: str = None


def simulate_conversation(
    num_tools: int = 10,
    num_turns: int = 5,
    tools_per_turn: int = 2,
    avg_tool_result_tokens: int = 200,
) -> Dict[str, Any]:
    """
    Simulate a conversation with tool calls.
    
    Returns token usage breakdown.
    """
    # Tool definitions (avg 70 tokens per tool)
    tool_def_tokens = num_tools * 70
    
    # System prompt
    system_tokens = 500
    
    # Track message tokens
    messages_tokens = 0
    tool_calls_made = 0
    
    for turn in range(num_turns):
        # User message
        user_msg = f"Please help me with task {turn + 1}"
        messages_tokens += count_tokens(user_msg) + 4  # +4 for role
        
        # Assistant thinking + tool calls
        assistant_thinking = "Let me search for information..."
        messages_tokens += count_tokens(assistant_thinking) + 4
        
        # Tool calls (each turn)
        for tc in range(tools_per_turn):
            tool_calls_made += 1
            # Tool call request overhead
            messages_tokens += 30  # tool_call structure
            # Tool result
            messages_tokens += avg_tool_result_tokens
        
        # Final assistant response
        final_response = f"Based on my research, here is the answer for task {turn + 1}..."
        messages_tokens += count_tokens(final_response) + 4
    
    total = tool_def_tokens + system_tokens + messages_tokens
    
    return {
        "tool_definitions": tool_def_tokens,
        "system_prompt": system_tokens,
        "messages": messages_tokens,
        "tool_calls_made": tool_calls_made,
        "total": total,
    }


def main():
    print("=" * 70)
    print("Tool Calling Context Usage Simulation")
    print("=" * 70)
    print()
    
    # Scenario 1: Simple task, few tools
    print("Scenario 1: Simple Task")
    print("-" * 50)
    result = simulate_conversation(
        num_tools=5,
        num_turns=2,
        tools_per_turn=1,
        avg_tool_result_tokens=100,
    )
    print(f"Tool definitions: {result['tool_definitions']} tokens")
    print(f"Tool calls made: {result['tool_calls_made']}")
    print(f"Messages: {result['messages']} tokens")
    print(f"Total: {result['total']} tokens")
    print()
    
    # Scenario 2: Complex task, many tools
    print("Scenario 2: Complex Task")
    print("-" * 50)
    result = simulate_conversation(
        num_tools=20,
        num_turns=5,
        tools_per_turn=3,
        avg_tool_result_tokens=300,
    )
    print(f"Tool definitions: {result['tool_definitions']} tokens")
    print(f"Tool calls made: {result['tool_calls_made']}")
    print(f"Messages: {result['messages']} tokens")
    print(f"Total: {result['total']} tokens")
    print()
    
    # Scenario 3: Long conversation
    print("Scenario 3: Long Conversation")
    print("-" * 50)
    result = simulate_conversation(
        num_tools=10,
        num_turns=10,
        tools_per_turn=2,
        avg_tool_result_tokens=200,
    )
    print(f"Tool definitions: {result['tool_definitions']} tokens")
    print(f"Tool calls made: {result['tool_calls_made']}")
    print(f"Messages: {result['messages']} tokens")
    print(f"Total: {result['total']} tokens")
    print()
    
    # Context exhaustion scenarios
    print("4. Context Exhaustion Analysis")
    print("-" * 50)
    print()
    
    model_limits = {
        "Qwen-Max (32K)": 32000,
        "DeepSeek (64K)": 64000,
        "GPT-4o (128K)": 128000,
        "Claude Sonnet (200K)": 200000,
    }
    
    print("Max conversation turns before context exhaustion:")
    print("(assuming 10 tools, 2 tool calls/turn, 200 token results)")
    print()
    
    for model, limit in model_limits.items():
        # Calculate max turns
        tool_def = 10 * 70  # 700 tokens
        system = 500
        tokens_per_turn = 4 + 20 + 2 * (30 + 200) + 30  # ~514 tokens/turn
        
        max_turns = (limit - tool_def - system - 4000) // tokens_per_turn  # leave 4K buffer
        
        print(f"  {model}: ~{max_turns} turns")
    
    print()
    
    # Tool result size impact
    print("5. Tool Result Size Impact")
    print("-" * 50)
    print()
    
    result_sizes = [
        ("Small (100 tokens)", 100),
        ("Medium (300 tokens)", 300),
        ("Large (1000 tokens)", 1000),
        ("Very Large (5000 tokens)", 5000),
    ]
    
    print("Impact on 10-turn conversation with 2 tool calls per turn:")
    print()
    
    for label, size in result_sizes:
        result = simulate_conversation(
            num_tools=10,
            num_turns=10,
            tools_per_turn=2,
            avg_tool_result_tokens=size,
        )
        print(f"  {label}:")
        print(f"    Total: {result['total']:,} tokens")
        print(f"    Tool results portion: {10 * 2 * size:,} tokens")
        print()
    
    # Recommendations
    print("6. Context Optimization Strategies")
    print("-" * 50)
    print("""
Strategy 1: Tool Result Truncation
-----------------------------------
  - Limit tool output to essential information
  - Use pagination for large datasets
  - Return summaries instead of full content
  
  Example: Instead of returning full search results:
    Bad: 5000 tokens of raw HTML
    Good: 300 tokens of extracted titles + snippets

Strategy 2: Dynamic Tool Loading
--------------------------------
  - Use a router agent to select relevant tools
  - Only bind needed tools for each subtask
  
  Flow: User query -> Router -> Select tools -> Worker agent

Strategy 3: Context Pruning
---------------------------
  - Summarize old turns
  - Remove irrelevant tool results
  - Keep only essential context

Strategy 4: Subagent Delegation
-------------------------------
  - Delegate complex tasks to specialized subagents
  - Each subagent has its own fresh context
  - Return only final results to main agent

Strategy 5: Streaming/Chunking
-----------------------------
  - Process large data in chunks
  - Don't load all data into context at once
  - Use external storage (Redis, DB) for intermediate results
""")


if __name__ == "__main__":
    main()
