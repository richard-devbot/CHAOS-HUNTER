#!/usr/bin/env python3
"""
Test script for enhanced AWS Bedrock integration with ChaosHunter
"""

import os
import sys
from chaos_hunter.utils.llms import load_llm
from chaos_hunter.utils.bedrock_utils import (
    get_available_bedrock_models,
    validate_bedrock_credentials,
    get_bedrock_model_info,
    get_model_display_name,
    PREDEFINED_BEDROCK_MODELS
)

def test_credentials_validation():
    """Test AWS credentials validation"""
    print("Testing AWS credentials validation...")
    
    if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
        print("⚠️  AWS credentials not found in environment variables")
        print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to test with real API calls")
        return False
    
    try:
        is_valid = validate_bedrock_credentials()
        if is_valid:
            print("✅ AWS credentials are valid")
            return True
        else:
            print("❌ AWS credentials are invalid")
            return False
    except Exception as e:
        print(f"❌ Error validating credentials: {e}")
        return False

def test_model_discovery():
    """Test dynamic model discovery"""
    print("\nTesting dynamic model discovery...")
    
    if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
        print("⚠️  Skipping model discovery test (no AWS credentials)")
        return
    
    try:
        models = get_available_bedrock_models()
        if models:
            print(f"✅ Found {len(models)} available Bedrock models:")
            for i, model in enumerate(models[:5], 1):  # Show first 5
                print(f"   {i}. {model['model_id']} ({model['provider']})")
            if len(models) > 5:
                print(f"   ... and {len(models) - 5} more")
        else:
            print("⚠️  No Bedrock models found (check permissions)")
    except Exception as e:
        print(f"❌ Error discovering models: {e}")

def test_model_info():
    """Test getting model information"""
    print("\nTesting model information retrieval...")
    
    if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
        print("⚠️  Skipping model info test (no AWS credentials)")
        return
    
    # Test with a common model
    test_model = "anthropic.claude-3-5-sonnet-20241022-v1:0"
    try:
        info = get_bedrock_model_info(test_model)
        if info:
            print(f"✅ Model info for {test_model}:")
            print(f"   Name: {info.get('model_name', 'N/A')}")
            print(f"   Provider: {info.get('provider', 'N/A')}")
            print(f"   Status: {info.get('lifecycle_status', 'N/A')}")
        else:
            print(f"⚠️  Could not get info for {test_model}")
    except Exception as e:
        print(f"❌ Error getting model info: {e}")

def test_display_names():
    """Test model display name generation"""
    print("\nTesting display name generation...")
    
    test_models = [
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0",
        "bedrock/amazon.titan-text-express-v1",
        "bedrock/ai21.j2-ultra-v1",
        "bedrock/cohere.command-r-v1:0",
        "bedrock/meta.llama-3-8b-instruct-v1:0"
    ]
    
    for model in test_models:
        display_name = get_model_display_name(model)
        print(f"   {model} → {display_name}")

def test_session_token_support():
    """Test session token support"""
    print("\nTesting session token support...")
    
    # Check if session token is set
    session_token = os.getenv('AWS_SESSION_TOKEN')
    if session_token:
        print(f"✅ AWS Session Token is set (length: {len(session_token)})")
        print("   Testing with session token...")
        try:
            is_valid = validate_bedrock_credentials()
            if is_valid:
                print("✅ Credentials with session token are valid")
            else:
                print("❌ Credentials with session token are invalid")
        except Exception as e:
            print(f"❌ Error with session token: {e}")
    else:
        print("ℹ️  No AWS Session Token found (this is normal for permanent credentials)")

def test_custom_model_loading():
    """Test loading custom Bedrock models"""
    print("\nTesting custom model loading...")
    
    test_models = [
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0",
        "bedrock/amazon.titan-text-express-v1",
        "bedrock/ai21.j2-mid-v1"
    ]
    
    for model_name in test_models:
        try:
            print(f"Testing {model_name}...")
            llm = load_llm(
                model_name=model_name,
                temperature=0.0,
                aws_region="us-east-1"
            )
            print(f"✅ Successfully loaded {model_name}")
            print(f"   Type: {type(llm)}")
            print(f"   Model ID: {getattr(llm, 'model_id', 'N/A')}")
        except Exception as e:
            print(f"❌ Failed to load {model_name}: {e}")
        print()

def test_predefined_models():
    """Test predefined model list"""
    print("\nTesting predefined model list...")
    print(f"✅ Found {len(PREDEFINED_BEDROCK_MODELS)} predefined Bedrock models")
    
    # Group by provider
    providers = {}
    for model in PREDEFINED_BEDROCK_MODELS:
        if model.startswith("bedrock/"):
            model_id = model[9:]  # Remove "bedrock/" prefix
            provider = model_id.split('.')[0]
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model_id)
    
    for provider, models in providers.items():
        print(f"   {provider.title()}: {len(models)} models")

if __name__ == "__main__":
    print("ChaosHunter Enhanced AWS Bedrock Integration Test")
    print("=" * 60)
    
    # Test session token support
    test_session_token_support()
    
    # Test credentials validation
    credentials_valid = test_credentials_validation()
    
    # Test model discovery
    test_model_discovery()
    
    # Test model info retrieval
    test_model_info()
    
    # Test display name generation
    test_display_names()
    
    # Test predefined models
    test_predefined_models()
    
    # Test custom model loading (only if credentials are valid)
    if credentials_valid:
        test_custom_model_loading()
    else:
        print("\n⚠️  Skipping custom model loading tests (invalid credentials)")
    
    print("\n" + "=" * 60)
    print("Enhanced Bedrock integration test completed!")
