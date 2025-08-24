"""
AWS Bedrock utilities for ChaosHunter
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Dict, Optional
import streamlit as st


def get_available_bedrock_models(region: str = "us-east-1") -> List[Dict[str, str]]:
    """
    Fetch available Bedrock models for the current AWS credentials.
    
    Args:
        region: AWS region to query
        
    Returns:
        List of dictionaries containing model information
    """
    try:
        bedrock = boto3.client('bedrock', region_name=region)
        response = bedrock.list_foundation_models()
        
        models = []
        for model in response.get('modelSummaries', []):
            models.append({
                'model_id': model['modelId'],
                'model_name': model['modelName'],
                'provider': model['providerName'],
                'input_modalities': model.get('inputModalities', []),
                'output_modalities': model.get('outputModalities', []),
                'customizations_supported': model.get('customizationsSupported', []),
                'inference_types_supported': model.get('inferenceTypesSupported', [])
            })
        
        return models
    except NoCredentialsError:
        st.error("AWS credentials not found. Please check your AWS Access Key ID and Secret Access Key.")
        return []
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            st.error("Access denied. Please check your AWS permissions for Bedrock.")
        elif error_code == 'UnauthorizedOperation':
            st.error("Unauthorized operation. Please check your AWS permissions.")
        else:
            st.error(f"AWS error: {e}")
        return []
    except Exception as e:
        st.error(f"Error fetching Bedrock models: {e}")
        return []


def validate_bedrock_credentials(region: str = "us-east-1") -> bool:
    """
    Validate AWS credentials for Bedrock access.
    
    Args:
        region: AWS region to test
        
    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        bedrock = boto3.client('bedrock', region_name=region)
        # Try to list models to validate credentials
        bedrock.list_foundation_models(MaxResults=1)
        return True
    except Exception:
        return False


def get_bedrock_model_info(model_id: str, region: str = "us-east-1") -> Optional[Dict]:
    """
    Get detailed information about a specific Bedrock model.
    
    Args:
        model_id: The Bedrock model ID
        region: AWS region
        
    Returns:
        Dictionary with model information or None if not found
    """
    try:
        bedrock = boto3.client('bedrock', region_name=region)
        response = bedrock.get_foundation_model(modelIdentifier=model_id)
        
        model = response.get('modelDetails', {})
        return {
            'model_id': model.get('modelId'),
            'model_name': model.get('modelName'),
            'provider': model.get('providerName'),
            'input_modalities': model.get('inputModalities', []),
            'output_modalities': model.get('outputModalities', []),
            'customizations_supported': model.get('customizationsSupported', []),
            'inference_types_supported': model.get('inferenceTypesSupported', []),
            'model_arn': model.get('modelArn'),
            'lifecycle_status': model.get('lifecycleStatus')
        }
    except Exception:
        return None


# Predefined Bedrock models for fallback
PREDEFINED_BEDROCK_MODELS = [
    # Anthropic Models
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0",
    "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0",
    "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
    "bedrock/anthropic.claude-3-opus-20240229-v1:0",
    "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
    "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    
    # Amazon Models
    "bedrock/amazon.titan-text-express-v1",
    "bedrock/amazon.titan-text-lite-v1",
    
    # AI21 Labs Models
    "bedrock/ai21.j2-ultra-v1",
    "bedrock/ai21.j2-mid-v1",
    
    # Cohere Models
    "bedrock/cohere.command-r-v1:0",
    "bedrock/cohere.command-r-plus-v1:0",
    
    # Meta Models
    "bedrock/meta.llama-3-8b-instruct-v1:0",
    "bedrock/meta.llama-3-70b-instruct-v1:0",
    "bedrock/meta.llama-3-405b-instruct-v1:0",
]


def get_model_display_name(model_id: str) -> str:
    """
    Get a user-friendly display name for a Bedrock model.
    
    Args:
        model_id: The Bedrock model ID
        
    Returns:
        User-friendly display name
    """
    # Remove the "bedrock/" prefix for display
    if model_id.startswith("bedrock/"):
        model_id = model_id[9:]  # Remove "bedrock/" prefix
    
    # Create a more readable name
    parts = model_id.split('.')
    if len(parts) >= 2:
        provider = parts[0].title()
        model_name = parts[1].replace('-', ' ').title()
        return f"{provider} {model_name}"
    
    return model_id.replace('-', ' ').title()
