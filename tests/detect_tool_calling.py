"""
Tool Calling Support Detection - Complete Guide
================================================

This script demonstrates different methods to detect if a model supports tool calling.
"""

import asyncio
from typing import Optional
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel


# ============================================================
# Method 1: Check bind_tools Method (Quick Check)
# ============================================================

def has_bind_tools(model: BaseChatModel) -> bool:
    """
    Quick check: Does the model have bind_tools method?
    
    Note: All BaseChatModel subclasses have this method, but having it
    doesn't guarantee the underlying API supports tool calling.
    """
    return hasattr(model, "bind_tools")


# ============================================================
# Method 2: Try Binding Tools (API-Free Check)
# ============================================================

def can_bind_tools(model: BaseChatModel) -> tuple[bool, Optional[str]]:
    """
    Try to bind tools to the model.
    
    This doesn't make an API call, just checks if the binding works.
    Some models may succeed here but fail on actual invocation.
    """
    @tool
    def test_tool(x: str) -> str:
        """A test tool."""
        return x
    
    try:
        model.bind_tools([test_tool])
        return True, None
    except Exception as e:
        return False, str(e)


# ============================================================
# Method 3: Actual Invocation Test (Most Reliable)
# ============================================================

async def test_with_invoke(model: BaseChatModel) -> dict:
    """
    Actually invoke the model with tools.
    
    This is the most reliable method but costs API calls.
    """
    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: sunny"
    
    result = {
        "can_bind": False,
        "invoke_success": False,
        "has_tool_calls": False,
        "tool_calls": [],
        "error": None,
    }
    
    try:
        model_with_tools = model.bind_tools([get_weather])
        result["can_bind"] = True
        
        response = await model_with_tools.ainvoke(
            "What's the weather in Tokyo?"
        )
        result["invoke_success"] = True
        
        tool_calls = getattr(response, "tool_calls", [])
        result["has_tool_calls"] = len(tool_calls) > 0
        result["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"]}
            for tc in tool_calls
        ]
        
    except Exception as e:
        result["error"] = str(e)[:200]
    
    return result


# ============================================================
# Method 4: Known Model Lists
# ============================================================

# Models known to support tool calling
KNOWN_TOOL_CALLING_MODELS = {
    # OpenAI
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "o1", "o1-mini", "o3-mini",
    
    # Anthropic
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "claude-3.5-sonnet", "claude-3.5-haiku",
    "claude-sonnet-4", "claude-sonnet-4-5",
    
    # Google
    "gemini-1.5-pro", "gemini-1.5-flash",
    "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash",
    
    # DeepSeek
    "deepseek-chat", "deepseek-reasoner",
    
    # Mistral
    "mistral-large", "mistral-medium", "mistral-small",
    "codestral",
    
    # Groq
    "llama-3.1-70b", "llama-3.1-8b",
    "mixtral-8x7b",
    
    # Qwen (via OpenAI-compatible API)
    "qwen-max", "qwen-plus", "qwen-turbo",
    "qwen2.5-72b", "qwen2.5-32b",
    
    # Moonshot (via OpenAI-compatible API)
    "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k",
}

# Models known NOT to support tool calling
KNOWN_NON_TOOL_MODELS = {
    # Older models
    "gpt-3.5-turbo-instruct",
    "text-davinci-003",
    
    # Some local models (depends on version)
    "llama-2-7b", "llama-2-13b", "llama-2-70b",
    "mistral-7b",  # base model
    
    # Embedding models
    "text-embedding-ada-002", "text-embedding-3-small",
}

# Models with partial/limited support
PARTIAL_SUPPORT_MODELS = {
    "ollama": "Depends on the specific model. Llama 3.1+ supports it.",
    "local": "Varies by model. Check model documentation.",
}


def is_known_tool_model(model_name: str) -> Optional[bool]:
    """
    Check if model is in known lists.
    
    Returns:
        True: Known to support
        False: Known NOT to support  
        None: Unknown/not in lists
    """
    model_lower = model_name.lower()
    
    for known in KNOWN_TOOL_CALLING_MODELS:
        if known in model_lower:
            return True
    
    for known in KNOWN_NON_TOOL_MODELS:
        if known in model_lower:
            return False
    
    return None


# ============================================================
# Combined Detection Function
# ============================================================

async def detect_tool_calling_support(
    model: BaseChatModel,
    model_name: str,
    test_invoke: bool = False
) -> dict:
    """
    Comprehensive tool calling support detection.
    
    Args:
        model: The LangChain chat model instance
        model_name: Model identifier string
        test_invoke: Whether to test with actual API call
    
    Returns:
        dict with detection results
    """
    result = {
        "model": model_name,
        "detection_methods": {},
        "supports_tool_calling": False,
        "confidence": "unknown",
        "recommendation": "",
    }
    
    # Method 1: bind_tools check
    result["detection_methods"]["has_bind_tools"] = has_bind_tools(model)
    
    # Method 2: Try binding
    can_bind, bind_error = can_bind_tools(model)
    result["detection_methods"]["can_bind_tools"] = can_bind
    if bind_error:
        result["detection_methods"]["bind_error"] = bind_error
    
    # Method 3: Known model check
    known_support = is_known_tool_model(model_name)
    result["detection_methods"]["known_model"] = known_support
    
    # Method 4: Actual test (optional)
    if test_invoke:
        invoke_result = await test_with_invoke(model)
        result["detection_methods"]["invoke_test"] = invoke_result
        
        if invoke_result["invoke_success"] and invoke_result["has_tool_calls"]:
            result["supports_tool_calling"] = True
            result["confidence"] = "high"
        elif invoke_result["invoke_success"] and not invoke_result["has_tool_calls"]:
            # Model responded but didn't use tools - might still support it
            result["supports_tool_calling"] = True
            result["confidence"] = "medium"
        else:
            result["supports_tool_calling"] = False
            result["confidence"] = "high"
    else:
        # Infer from other methods
        if not can_bind:
            result["supports_tool_calling"] = False
            result["confidence"] = "high"
        elif known_support is True:
            result["supports_tool_calling"] = True
            result["confidence"] = "medium"
        elif known_support is False:
            result["supports_tool_calling"] = False
            result["confidence"] = "medium"
        else:
            result["supports_tool_calling"] = True  # Assume yes if bind works
            result["confidence"] = "low"
    
    # Generate recommendation
    if result["confidence"] == "low":
        result["recommendation"] = "Run with test_invoke=True for reliable detection"
    elif result["confidence"] == "medium":
        result["recommendation"] = "Model likely supports tool calling based on bind_tools"
    else:
        result["recommendation"] = "Detection complete"
    
    return result


# ============================================================
# Demo
# ============================================================

async def demo():
    """Demonstrate the detection methods."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 70)
    print("Tool Calling Support Detection Demo")
    print("=" * 70)
    print()
    
    # Show known models
    print("Known Tool Calling Models:")
    print("-" * 40)
    for model in sorted(KNOWN_TOOL_CALLING_MODELS)[:15]:
        print(f"  [OK] {model}")
    print(f"  ... and {len(KNOWN_TOOL_CALLING_MODELS) - 15} more")
    print()
    
    # Quick test with available models
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        
        print("Testing OpenAI GPT-4o-mini:")
        print("-" * 40)
        model = ChatOpenAI(model="gpt-4o-mini")
        result = await detect_tool_calling_support(
            model, "gpt-4o-mini", test_invoke=False
        )
        print(f"  Supports Tool Calling: {result['supports_tool_calling']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Recommendation: {result['recommendation']}")
        print()
    
    # Test with OpenAI-compatible model (Qwen)
    if os.environ.get("OPENAI_BASE_URL") or os.environ.get("DASHSCOPE_API_KEY"):
        from langchain_openai import ChatOpenAI
        
        api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        
        print("Testing Qwen (OpenAI-compatible):")
        print("-" * 40)
        model = ChatOpenAI(
            model="qwen-max",
            api_key=api_key,
            base_url=base_url
        )
        result = await detect_tool_calling_support(
            model, "qwen-max", test_invoke=False
        )
        print(f"  Supports Tool Calling: {result['supports_tool_calling']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Recommendation: {result['recommendation']}")
        print()
    
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
Detection Methods (in order of reliability):

1. test_invoke=True  - Most reliable, costs API calls
   - Actually sends request with tools
   - Checks if model returns tool_calls

2. Known model list  - Reliable for common models
   - Check against KNOWN_TOOL_CALLING_MODELS
   - May not cover all models

3. bind_tools check  - Quick but not definitive
   - bind_tools may succeed even if API doesn't support
   - Use as preliminary check only

4. Error handling    - Runtime detection
   - Catch exceptions when model returns unexpected format
   - Implement fallback in production code
""")


if __name__ == "__main__":
    asyncio.run(demo())
