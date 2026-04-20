"""Tool Token Usage Analysis"""

import tiktoken
import json


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model("gpt-4o")
    except:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def analyze_tool(tool_def: dict) -> dict:
    """Analyze a single tool definition."""
    tool_json = json.dumps(tool_def)
    return {
        "name": tool_def.get("name", "unknown"),
        "json_size": len(tool_json),
        "tokens": count_tokens(tool_json),
    }


# ============================================================
# Sample Tools with Different Complexity
# ============================================================

SIMPLE_TOOL = {
    "name": "get_weather",
    "description": "Get weather for a city",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"}
        },
        "required": ["city"]
    }
}

MEDIUM_TOOL = {
    "name": "internet_search",
    "description": "Search the internet for information, news, and data",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query string"},
            "max_results": {"type": "integer", "description": "Maximum results", "default": 5}
        },
        "required": ["query"]
    }
}

COMPLEX_TOOL = {
    "name": "execute_sql_query",
    "description": "Execute SQL query on MySQL database. Only read-only SELECT queries are allowed.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The SQL query to execute (SELECT only)"
            },
            "database": {
                "type": "string",
                "description": "Target database name"
            },
            "timeout": {
                "type": "integer",
                "description": "Query timeout in seconds",
                "default": 30
            },
            "format": {
                "type": "string",
                "enum": ["json", "csv", "table"],
                "description": "Output format for results"
            }
        },
        "required": ["query"]
    }
}

# DeepAgent style tool (from your project)
DEEPAGENT_TOOLS = [
    # MySQL tools
    {
        "name": "list_sql_tables",
        "description": "List all available tables in the MySQL database"
    },
    {
        "name": "get_table_data",
        "description": "Read first 100 rows from a MySQL table, returns CSV format",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Table name to read"}
            },
            "required": ["table_name"]
        }
    },
    {
        "name": "execute_sql_query",
        "description": "Execute custom SQL query on MySQL (SELECT/SHOW/DESCRIBE only)",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query"}
            },
            "required": ["query"]
        }
    },
    # Search tools
    {
        "name": "internet_search",
        "description": "Search the internet using Baidu API",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    # File tools
    {
        "name": "read_file_content",
        "description": "Read content from uploaded files (MD/DOCX/PDF/XLSX)",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path"}
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "generate_markdown",
        "description": "Generate markdown report and save to file",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Markdown content"},
                "filename": {"type": "string", "description": "Output filename"}
            },
            "required": ["content", "filename"]
        }
    },
    {
        "name": "convert_md_to_pdf",
        "description": "Convert markdown file to PDF",
        "parameters": {
            "type": "object",
            "properties": {
                "md_path": {"type": "string", "description": "Markdown file path"}
            },
            "required": ["md_path"]
        }
    },
    # RAG tools
    {
        "name": "search_knowledge_base",
        "description": "Search local knowledge base using vector similarity",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_file_to_kb",
        "description": "Add a file to the knowledge base",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File to add"}
            },
            "required": ["file_path"]
        }
    },
]


def main():
    print("=" * 70)
    print("Tool Token Usage Analysis")
    print("=" * 70)
    print()
    
    # Single tool analysis
    print("1. Single Tool Token Usage by Complexity")
    print("-" * 50)
    
    tools_by_complexity = [
        ("Simple", SIMPLE_TOOL),
        ("Medium", MEDIUM_TOOL),
        ("Complex", COMPLEX_TOOL),
    ]
    
    for label, tool in tools_by_complexity:
        result = analyze_tool(tool)
        print(f"{label}: {result['name']}")
        print(f"  JSON size: {result['json_size']} chars")
        print(f"  Tokens: {result['tokens']}")
        print()
    
    # Multi-tool accumulation
    print("2. Multi-Tool Accumulation")
    print("-" * 50)
    
    tool_counts = [1, 3, 5, 10, 20]
    for count in tool_counts:
        # Duplicate tools to simulate
        tools = DEEPAGENT_TOOLS[:count] if count <= len(DEEPAGENT_TOOLS) else DEEPAGENT_TOOLS * (count // len(DEEPAGENT_TOOLS) + 1)
        tools = tools[:count]
        
        total_json = json.dumps(tools)
        total_tokens = count_tokens(total_json)
        
        print(f"{count} tools: ~{total_tokens} tokens")
    
    print()
    
    # Your project's actual tools
    print("3. Your Project's Tool Configuration")
    print("-" * 50)
    
    total_json = json.dumps(DEEPAGENT_TOOLS)
    total_tokens = count_tokens(total_json)
    
    print(f"Total tools: {len(DEEPAGENT_TOOLS)}")
    print(f"Total tool definitions: ~{total_tokens} tokens")
    print()
    
    for tool in DEEPAGENT_TOOLS:
        result = analyze_tool(tool)
        print(f"  {result['name']}: {result['tokens']} tokens")
    
    print()
    
    # Tool call overhead
    print("4. Tool Call/Result Overhead")
    print("-" * 50)
    
    # Simulate a tool call
    tool_call_request = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "internet_search",
                "arguments": '{"query": "AI news 2024", "max_results": 5}'
            }
        }]
    }
    
    # Simulate a tool result (short)
    tool_result_short = {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "Found 5 results: 1. OpenAI announces GPT-5..."
    }
    
    # Simulate a tool result (long)
    tool_result_long = {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "Found 5 results:\n\n1. OpenAI announces GPT-5 with improved reasoning...\n\n2. Google releases Gemini 2.5 with new features...\n\n3. Anthropic Claude improves tool calling accuracy...\n\n4. DeepSeek V4 offers competitive performance...\n\n5. Mistral launches new model for code generation..."
    }
    
    print(f"Tool call request: {count_tokens(json.dumps(tool_call_request))} tokens")
    print(f"Tool result (short): {count_tokens(json.dumps(tool_result_short))} tokens")
    print(f"Tool result (long): {count_tokens(json.dumps(tool_result_long))} tokens")
    print()
    
    # Context window impact
    print("5. Context Window Impact")
    print("-" * 50)
    
    model_contexts = {
        "GPT-4o": 128000,
        "GPT-4o-mini": 128000,
        "Claude Sonnet 4": 200000,
        "Gemini 2.5 Pro": 1000000,
        "Qwen-Max": 32000,
        "DeepSeek V4": 64000,
    }
    
    print(f"Your tools overhead: {total_tokens} tokens")
    print()
    print("Percentage of context window used by tools:")
    
    for model, ctx in model_contexts.items():
        pct = (total_tokens / ctx) * 100
        print(f"  {model}: {pct:.2f}% ({ctx:,} total)")
    
    print()
    
    # Recommendations
    print("6. Optimization Recommendations")
    print("-" * 50)
    print("""
1. Keep descriptions concise
   - Bad: "This tool searches the internet for information..."
   - Good: "Search the internet"

2. Use default values to reduce required parameters
   
3. For many tools, consider tool routing:
   - Use a "router" agent to select relevant tools
   - Only bind the selected tools to the worker agent

4. Truncate tool results:
   - Don't return full HTML/pages
   - Return summarized/extracted content

5. Monitor actual usage:
   - Log token counts per request
   - Identify tools that consume the most context
""")


if __name__ == "__main__":
    main()
