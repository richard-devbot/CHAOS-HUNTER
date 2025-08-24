#!/usr/bin/env python3
"""
Test script for AWS Bedrock integration with ChaosHunter
"""

import os
import sys
from chaos_hunter.utils.llms import load_llm

def test_bedrock_models():
    """Test loading Bedrock models"""
    
    # Test model names
    test_models = [
        "bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0",
        "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        "bedrock/amazon.titan-text-express-v1",
        "bedrock/ai21.j2-mid-v1",
        "bedrock/cohere.command-r-v1:0",
        "bedrock/meta.llama-3-8b-instruct-v1:0",
    ]
    
    print("Testing Bedrock model loading...")
    
    for model_name in test_models:
        try:
            print(f"Testing {model_name}...")
            llm = load_llm(
                model_name=model_name,
                temperature=0.0,
                aws_region="us-east-1"
            )
            print(f"✓ Successfully loaded {model_name}")
            print(f"  Type: {type(llm)}")
            print(f"  Model ID: {getattr(llm, 'model_id', 'N/A')}")
            print()
        except Exception as e:
            print(f"✗ Failed to load {model_name}: {e}")
            print()

def test_pricing():
    """Test pricing information for Bedrock models"""
    from chaos_hunter.utils.llms import PRICING_PER_TOKEN
    
    print("Testing Bedrock pricing...")
    
    bedrock_models = [k for k in PRICING_PER_TOKEN.keys() if k.startswith("bedrock/")]
    
    for model in bedrock_models:
        pricing = PRICING_PER_TOKEN[model]
        print(f"{model}:")
        print(f"  Input: ${pricing['input'] * 1e6:.4f} per 1M tokens")
        print(f"  Output: ${pricing['output'] * 1e6:.4f} per 1M tokens")
        print()

if __name__ == "__main__":
    print("ChaosHunter AWS Bedrock Integration Test")
    print("=" * 50)
    
    # Check if AWS credentials are set
    if not (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')):
        print("⚠️  AWS credentials not found in environment variables")
        print("   Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to test with real API calls")
        print()
    
    test_pricing()
    
    if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
        test_bedrock_models()
    else:
        print("Skipping model loading tests (no AWS credentials)")
    
    print("Test completed!")
