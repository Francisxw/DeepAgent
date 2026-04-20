"""
Quick script to check model capabilities from LangChain's registry.
"""

from langchain_core.language_models import ModelProfileRegistry, ModelProfile


def check_model_capabilities(model_id: str) -> dict:
    """Check if a model supports tool calling via registry."""
    registry = ModelProfileRegistry()
    
    try:
        profile = registry.get_model_profile(model_id)
        if profile is None:
            return {"model": model_id, "status": "not_in_registry"}
        
        result = {
            "model": model_id,
            "status": "found",
            "tool_calling": getattr(profile, "tool_calling", None),
            "structured_output": getattr(profile, "structured_output", None),
            "openai_compatible": getattr(profile, "openai_compatible", None),
        }
        
        # List all attributes
        attrs = {}
        for attr in dir(profile):
            if not attr.startswith("_"):
                value = getattr(profile, attr, None)
                if value is not None and not callable(value):
                    attrs[attr] = value
        result["all_attributes"] = attrs
        
        return result
        
    except Exception as e:
        return {"model": model_id, "status": "error", "error": str(e)}


if __name__ == "__main__":
    print("=" * 60)
    print("Model Capabilities Check (via LangChain Registry)")
    print("=" * 60)
    print()
    
    models = [
        "gpt-4o",
        "gpt-4o-mini", 
        "claude-sonnet-4-5",
        "claude-3-5-sonnet",
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "qwen-max",
        "deepseek-chat",
        "llama3.1",
    ]
    
    for model_id in models:
        result = check_model_capabilities(model_id)
        print(f"Model: {model_id}")
        print(f"  Status: {result.get('status')}")
        
        if result.get("status") == "found":
            print(f"  Tool Calling: {result.get('tool_calling')}")
            print(f"  Structured Output: {result.get('structured_output')}")
        elif result.get("status") == "error":
            print(f"  Error: {result.get('error')}")
        
        print()
