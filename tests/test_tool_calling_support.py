"""
Tool Calling Support Detection Script

This script helps you detect whether a model supports tool calling (function calling).
"""

from langchain_core.tools import tool
import asyncio


# Define test tools
@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: sunny, 25C"


@tool
def calculate(expression: str) -> float:
    """Calculate a mathematical expression."""
    return eval(expression)


async def check_tool_calling_support(model, model_name: str, test_invoke: bool = False) -> dict:
    """
    Check if a model supports tool calling.
    
    Args:
        model: The LangChain chat model instance
        model_name: A friendly name for the model
        test_invoke: Whether to actually invoke the model (costs API calls)
    
    Returns:
        dict with support status and details
    """
    result = {
        "model": model_name,
        "has_bind_tools": False,
        "can_bind_tools": False,
        "bind_error": None,
        "invoke_test": None,
        "supports_tool_calling": False,
        "confidence": "unknown",
    }
    
    # Step 1: Check if bind_tools method exists
    result["has_bind_tools"] = hasattr(model, "bind_tools")
    if not result["has_bind_tools"]:
        result["confidence"] = "high - no bind_tools method"
        return result
    
    # Step 2: Try to bind tools (doesn't make API call)
    try:
        model_with_tools = model.bind_tools([get_weather, calculate])
        result["can_bind_tools"] = True
    except Exception as e:
        result["bind_error"] = str(e)[:200]
        result["confidence"] = "high - bind_tools raised error"
        return result
    
    # Step 3: Optionally test with actual invoke
    if test_invoke:
        try:
            # Send a prompt that should trigger tool usage
            response = await model_with_tools.ainvoke(
                "What's the weather in Beijing? Also calculate 123 * 456"
            )
            
            # Check for tool_calls
            tool_calls = getattr(response, "tool_calls", [])
            
            result["invoke_test"] = {
                "has_tool_calls": len(tool_calls) > 0,
                "tool_calls_count": len(tool_calls),
                "tool_calls": [
                    {"name": tc["name"], "args": tc["args"]} 
                    for tc in tool_calls
                ] if tool_calls else [],
                "has_content": bool(response.content) if hasattr(response, "content") else False,
            }
            
            result["supports_tool_calling"] = len(tool_calls) > 0
            result["confidence"] = "high - tested with invoke"
            
        except Exception as e:
            result["invoke_test"] = {"error": str(e)[:200]}
            result["confidence"] = "medium - invoke failed but bind worked"
    else:
        # Without invoke, we assume support if bind works
        result["supports_tool_calling"] = True
        result["confidence"] = "medium - bind_tools works, not tested with invoke"
    
    return result


async def main():
    """Test various models for tool calling support."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 60)
    print("Tool Calling Support Detection")
    print("=" * 60)
    print()
    
    # Test models
    models_to_test = []
    
    # 1. OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        models_to_test.append(("OpenAI GPT-4o-mini", ChatOpenAI(model="gpt-4o-mini")))
    
    # 2. Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        models_to_test.append(("Anthropic Claude", ChatAnthropic(model="claude-sonnet-4-5")))
    
    # 3. Google Gemini
    if os.environ.get("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        models_to_test.append(("Google Gemini", ChatGoogleGenerativeAI(model="gemini-2.0-flash")))
    
    # 4. OpenAI-compatible (Qwen/DeepSeek/Moonshot)
    # Example for Qwen
    if os.environ.get("DASHSCOPE_API_KEY"):
        from langchain_openai import ChatOpenAI
        models_to_test.append((
            "Qwen (OpenAI-compatible)", 
            ChatOpenAI(
                model="qwen-max",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.environ["DASHSCOPE_API_KEY"]
            )
        ))
    
    # 5. Ollama (local)
    try:
        from langchain_ollama import ChatOllama
        models_to_test.append(("Ollama Llama3.1", ChatOllama(model="llama3.1")))
    except ImportError:
        print("Note: langchain_ollama not installed, skipping Ollama test")
    
    if not models_to_test:
        print("No models to test. Please set API keys in environment.")
        print()
        print("Required environment variables:")
        print("  - OPENAI_API_KEY for OpenAI")
        print("  - ANTHROPIC_API_KEY for Claude")
        print("  - GOOGLE_API_KEY for Gemini")
        print("  - DASHSCOPE_API_KEY for Qwen")
        return
    
    # Test each model
    for model_name, model in models_to_test:
        print(f"Testing: {model_name}")
        print("-" * 40)
        
        # Quick check without invoke (free)
        result = await check_tool_calling_support(model, model_name, test_invoke=False)
        
        print(f"  has_bind_tools: {result['has_bind_tools']}")
        print(f"  can_bind_tools: {result['can_bind_tools']}")
        print(f"  supports_tool_calling: {result['supports_tool_calling']}")
        print(f"  confidence: {result['confidence']}")
        
        if result["bind_error"]:
            print(f"  error: {result['bind_error']}")
        
        print()
    
    print("=" * 60)
    print("Interpretation Guide")
    print("=" * 60)
    print("""
confidence levels:
  - high:     Definitely supports tool calling (tested)
  - medium:   Likely supports (bind_tools works, not tested with API call)
  - unknown:  Cannot determine

For models with 'medium' confidence, you can run with test_invoke=True
to actually test with an API call (costs money).

Common issues:
  - bind_tools works but invoke fails: Model doesn't support tool calling
  - tool_calls is empty: Model chose not to use tools (normal behavior)
  - Error about 'tools' parameter: Provider API doesn't support it
""")


if __name__ == "__main__":
    asyncio.run(main())
