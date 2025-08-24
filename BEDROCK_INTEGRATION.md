# AWS Bedrock Integration for ChaosHunter

This document describes the AWS Bedrock integration added to ChaosHunter, allowing users to leverage AWS Bedrock models for chaos engineering experiments.

## Overview

AWS Bedrock is a fully managed service that offers a choice of high-performing foundation models from leading AI companies like Anthropic, Amazon, AI21 Labs, Cohere, Meta, and Stability AI via a single API. The integration allows ChaosHunter to use these models for all LLM operations.

## Supported Models

The following Bedrock models are now available in ChaosHunter:

### Anthropic Models
- `bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0` - Latest Claude 3.5 Sonnet
- `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0` - Claude 3.5 Sonnet (June 2024)
- `bedrock/anthropic.claude-3-5-haiku-20241022-v1:0` - Claude 3.5 Haiku
- `bedrock/anthropic.claude-3-opus-20240229-v1:0` - Claude 3 Opus
- `bedrock/anthropic.claude-3-sonnet-20240229-v1:0` - Claude 3 Sonnet
- `bedrock/anthropic.claude-3-haiku-20240307-v1:0` - Claude 3 Haiku

### Amazon Models
- `bedrock/amazon.titan-text-express-v1` - Titan Text Express
- `bedrock/amazon.titan-text-lite-v1` - Titan Text Lite

### AI21 Labs Models
- `bedrock/ai21.j2-ultra-v1` - Jurassic-2 Ultra
- `bedrock/ai21.j2-mid-v1` - Jurassic-2 Mid

### Cohere Models
- `bedrock/cohere.command-r-v1:0` - Command R
- `bedrock/cohere.command-r-plus-v1:0` - Command R Plus

### Meta Models
- `bedrock/meta.llama-3-8b-instruct-v1:0` - Llama 3 8B Instruct
- `bedrock/meta.llama-3-70b-instruct-v1:0` - Llama 3 70B Instruct
- `bedrock/meta.llama-3-405b-instruct-v1:0` - Llama 3 405B Instruct

## Setup Instructions

### 1. AWS Account Setup

1. Create an AWS account if you don't have one
2. Enable AWS Bedrock service in your AWS console
3. Request access to the models you want to use (some models require approval)
4. Create an IAM user with appropriate Bedrock permissions

### 2. AWS Credentials

You'll need to provide AWS credentials in the ChaosHunter interface:

- **AWS Access Key ID**: Your AWS access key
- **AWS Secret Access Key**: Your AWS secret key
- **AWS Session Token** (optional): Your AWS session token (required for temporary credentials)
- **AWS Region**: The AWS region where Bedrock is available (e.g., `us-east-1`, `us-west-2`)

**Note**: If you're using temporary credentials (e.g., from AWS STS, IAM roles, or AWS SSO), you'll need to provide the session token as well.

### 3. Model Access

Ensure you have access to the Bedrock models you want to use. You can check and request access in the AWS Bedrock console.

## Usage in ChaosHunter

### 1. Model Selection

In the ChaosHunter Streamlit interface:

1. Go to the sidebar settings
2. Enter your AWS credentials first:
   - AWS Access Key ID
   - AWS Secret Access Key
   - AWS Session Token (if using temporary credentials)
   - AWS Region (defaults to `us-east-1`)
3. The system will automatically fetch and display available Bedrock models
4. Select a Bedrock model from the "Model" dropdown
5. Optionally, you can add custom Bedrock models using the "Custom Model ID" field

**Dynamic Model Discovery**: Once you enter valid AWS credentials, ChaosHunter will automatically fetch and display all Bedrock models available to your account. If credentials are not provided or invalid, it will fall back to a predefined list of common Bedrock models.

### 2. Configuration

The Bedrock models support the same configuration options as other models:

- **Temperature**: Controls randomness (0.0 = deterministic, 1.0 = very random)
- **Max Tokens**: Maximum number of tokens in the response
- **Seed**: For reproducible results (where supported)

### 3. Pricing

Pricing is automatically calculated based on token usage. Bedrock models have different pricing tiers:

- **Claude models**: $3.75-$15.00 per 1M input tokens, $1.25-$75.00 per 1M output tokens
- **Titan models**: $0.0003-$0.0008 per 1M input tokens, $0.0004-$0.0016 per 1M output tokens
- **AI21 models**: $2.50-$12.50 per 1M tokens (input/output)
- **Cohere models**: $5.00-$15.00 per 1M input tokens, $25.00-$75.00 per 1M output tokens
- **Meta models**: $0.20-$1.20 per 1M input tokens, $0.20-$1.60 per 1M output tokens

## Technical Implementation

### Dependencies

The integration requires the `langchain-aws` package:

```bash
pip install langchain-aws
```

### Code Changes

The integration includes the following key changes:

1. **`chaos_hunter/utils/llms.py`**:
   - Added `ChatBedrockConverse` import
   - Updated `load_llm()` function to handle Bedrock models
   - Added Bedrock pricing information
   - Updated `LoggingCallback` to handle Bedrock token usage

2. **`ChaosHunter_demo.py`**:
   - Added Bedrock models to the model selection dropdown
   - Added AWS credentials input fields
   - Updated initialization logic to handle AWS credentials
   - Added AWS region change detection

### Model Loading

Bedrock models are loaded using the `ChatBedrockConverse` class from `langchain-aws`:

```python
from langchain_aws import ChatBedrockConverse

llm = ChatBedrockConverse(
    model_id="anthropic.claude-3-5-sonnet-20241022-v1:0",
    temperature=0.0,
    max_tokens=8192,
    region_name="us-east-1"
)
```

## Testing

You can test the Bedrock integration using the provided test script:

```bash
python test_bedrock_integration.py
```

This script will:
1. Test model loading for various Bedrock models
2. Display pricing information
3. Verify the integration works correctly

## Troubleshooting

### Common Issues

1. **"Access Denied" errors**: Ensure you have access to the specific Bedrock model
2. **"Invalid credentials"**: Check your AWS Access Key ID and Secret Access Key
3. **"Region not available"**: Ensure the model is available in your selected AWS region
4. **"Model not found"**: Verify the model ID is correct and you have access to it

### Debugging

1. Check AWS credentials are properly set in environment variables
2. Verify model access in AWS Bedrock console
3. Check AWS region availability for specific models
4. Review CloudWatch logs for detailed error information

## Security Considerations

- AWS credentials are stored in Streamlit session state (in-memory only)
- Credentials are not persisted between sessions
- Consider using AWS IAM roles for production deployments
- Follow AWS security best practices for credential management

## Future Enhancements

Potential future improvements:

1. Support for Bedrock custom models
2. Integration with AWS Bedrock Model Invocation Logging
3. Support for Bedrock Guardrails
4. Enhanced error handling and retry logic
5. Support for Bedrock Model Evaluation

## Support

For issues with the Bedrock integration:

1. Check the AWS Bedrock documentation
2. Verify your AWS account setup and permissions
3. Review the ChaosHunter logs for detailed error messages
4. Test with the provided test script to isolate issues
