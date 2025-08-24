#!/usr/bin/env python3
"""
Test script to verify the circular reference fix for Bedrock models
"""

import os
import sys
from chaos_hunter.utils.llms import load_llm
from chaos_hunter.utils.bedrock_wrapper import BedrockWrapper

def test_bedrock_wrapper_serialization():
    """Test that the BedrockWrapper can be serialized without circular reference issues."""
    print("Testing BedrockWrapper serialization...")
    
    try:
        # Create a BedrockWrapper instance
        wrapper = BedrockWrapper(
            model_id="anthropic.claude-3-5-sonnet-20241022-v1:0",
            temperature=0.0,
            max_tokens=8192,
            region_name="us-east-1"
        )
        
        # Test serialization
        import json
        from langchain_core.load.dump import dumpd
        
        # This should not raise a circular reference error
        serialized = dumpd(wrapper)
        print("✅ BedrockWrapper serialization successful")
        print(f"   Serialized keys: {list(serialized.keys())}")
        
        return True
    except Exception as e:
        print(f"❌ BedrockWrapper serialization failed: {e}")
        return False

def test_load_llm_bedrock():
    """Test loading a Bedrock model through the load_llm function."""
    print("\nTesting load_llm with Bedrock model...")
    
    try:
        # Set AWS credentials if available
        if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
            llm = load_llm(
                model_name="bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0",
                temperature=0.0,
                aws_region="us-east-1"
            )
            
            print(f"✅ Successfully loaded Bedrock model")
            print(f"   Type: {type(llm)}")
            print(f"   LLM Type: {getattr(llm, '_llm_type', 'N/A')}")
            
            # Test serialization
            from langchain_core.load.dump import dumpd
            serialized = dumpd(llm)
            print("✅ Model serialization successful")
            
            return True
        else:
            print("⚠️  AWS credentials not found, skipping actual model loading")
            print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to test with real API calls")
            return True
    except Exception as e:
        print(f"❌ Failed to load Bedrock model: {e}")
        return False

def test_streaming_compatibility():
    """Test that the wrapper is compatible with streaming operations."""
    print("\nTesting streaming compatibility...")
    
    try:
        wrapper = BedrockWrapper(
            model_id="anthropic.claude-3-5-sonnet-20241022-v1:0",
            temperature=0.0,
            max_tokens=8192,
            region_name="us-east-1"
        )
        
        # Test that the wrapper has the required methods
        required_methods = ['stream', 'astream', '_generate', '_agenerate']
        for method in required_methods:
            if hasattr(wrapper, method):
                print(f"✅ Method {method} available")
            else:
                print(f"❌ Method {method} missing")
                return False
        
        print("✅ All required streaming methods available")
        return True
    except Exception as e:
        print(f"❌ Streaming compatibility test failed: {e}")
        return False

if __name__ == "__main__":
    print("Circular Reference Fix Test")
    print("=" * 50)
    
    # Test 1: BedrockWrapper serialization
    test1_passed = test_bedrock_wrapper_serialization()
    
    # Test 2: Load LLM with Bedrock
    test2_passed = test_load_llm_bedrock()
    
    # Test 3: Streaming compatibility
    test3_passed = test_streaming_compatibility()
    
    print("\n" + "=" * 50)
    if all([test1_passed, test2_passed, test3_passed]):
        print("✅ All tests passed! Circular reference issue should be fixed.")
    else:
        print("❌ Some tests failed. Please check the implementation.")
    
    print("\nTo test with real AWS credentials:")
    print("export AWS_ACCESS_KEY_ID='your-key'")
    print("export AWS_SECRET_ACCESS_KEY='your-secret'")
    print("python test_circular_reference_fix.py")
