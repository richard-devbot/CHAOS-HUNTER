# Retry Mechanism for Rate Limit Handling

This document describes the comprehensive retry mechanism implemented to handle rate limits across all LLM models in ChaosHunter.

## Overview

The retry mechanism automatically handles rate limit errors (HTTP 429) and other throttling issues that commonly occur when using LLM APIs. It implements exponential backoff with jitter to ensure robust and efficient retry behavior.

## Features

### 1. **Exponential Backoff with Jitter**
- **Base Delay**: Starts with a configurable base delay (default: 1-2 seconds)
- **Exponential Growth**: Delay increases exponentially with each retry attempt
- **Maximum Delay**: Capped at a maximum delay (default: 60-120 seconds)
- **Jitter**: Random variation in delay to prevent thundering herd problems

### 2. **Multi-Provider Support**
The retry mechanism handles rate limits from all supported LLM providers:

- **Google Gemini**: `ResourceExhausted: 429` errors with retry delay extraction
- **OpenAI**: Rate limit errors with `retry-after` header parsing
- **Anthropic**: Rate limit errors
- **AWS Bedrock**: Throttling errors

### 3. **Comprehensive Method Coverage**
Retry logic is applied to all LLM methods:
- `_generate()` - Synchronous generation
- `_agenerate()` - Asynchronous generation
- `stream()` - Synchronous streaming
- `astream()` - Asynchronous streaming

### 4. **Smart Error Detection**
The mechanism intelligently identifies rate limit errors:
- Parses error messages for specific rate limit indicators
- Extracts retry delay information from error responses
- Distinguishes between rate limits and other errors

## Configuration

### Retry Parameters

```python
@retry_with_exponential_backoff(
    max_retries=5,        # Maximum number of retry attempts
    base_delay=2.0,       # Initial delay in seconds
    max_delay=120.0,      # Maximum delay in seconds
    exponential_base=2.0, # Base for exponential calculation
    jitter=True           # Enable random jitter
)
```

### Default Settings

- **Max Retries**: 5 attempts (6 total calls including initial)
- **Base Delay**: 2 seconds
- **Max Delay**: 120 seconds
- **Exponential Base**: 2.0
- **Jitter**: Enabled

## Implementation Details

### 1. **Retry Decorator**
The `retry_with_exponential_backoff` decorator wraps functions and automatically retries on rate limit errors.

### 2. **LLM Wrapper**
The `create_retry_llm` function creates LLM instances with retry capabilities by wrapping their core methods.

### 3. **Streaming Support**
Special handling for streaming methods since they return generators and require different retry logic.

### 4. **Error Message Parsing**
Automatic extraction of retry delay information from error messages:
- Google Gemini: Extracts `retry_delay` from error details
- OpenAI: Parses `retry-after` headers
- Other providers: Uses exponential backoff with jitter

## Usage Examples

### Basic Usage
```python
from chaos_hunter.utils.llms import load_llm

# All LLMs are automatically created with retry capabilities
llm = load_llm("google/gemini-1.5-pro")
response = llm.invoke("Hello, world!")  # Automatically retries on rate limits
```

### Custom Retry Configuration
```python
from chaos_hunter.utils.llms import retry_with_exponential_backoff

@retry_with_exponential_backoff(max_retries=3, base_delay=1.0)
def my_api_call():
    # Your API call here
    pass
```

## Error Handling

### Rate Limit Detection
The mechanism detects rate limits by checking for:
- `ResourceExhausted` with `429` status (Google Gemini)
- `rate_limit` in error message
- `429` status codes
- `throttling` or `throttled` keywords (AWS Bedrock)

### Non-Retryable Errors
Non-rate-limit errors are immediately raised without retry attempts to avoid unnecessary delays.

## Monitoring and Logging

The retry mechanism provides informative logging:
```
Rate limit hit, retrying in 4.23 seconds (attempt 2/6)
Stream rate limit hit, retrying in 8.45 seconds (attempt 3/6)
```

## Best Practices

1. **Use Default Settings**: The default configuration works well for most use cases
2. **Monitor Logs**: Watch for retry messages to understand rate limit patterns
3. **Adjust Parameters**: Modify retry settings based on your specific API quotas
4. **Handle Failures**: Always implement proper error handling for final failures

## Testing

Run the test script to verify the retry mechanism:
```bash
python test_retry_mechanism.py
```

This will test:
- Retry decorator functionality
- LLM loading with retry capabilities
- Rate limit simulation structure

## Troubleshooting

### Common Issues

1. **Too Many Retries**: Reduce `max_retries` if you're hitting limits too frequently
2. **Long Delays**: Adjust `base_delay` and `max_delay` for your use case
3. **Missing Retries**: Ensure error messages contain rate limit indicators

### Debug Mode
Enable debug logging to see detailed retry information:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Impact

- **Minimal Overhead**: Retry logic adds negligible performance impact
- **Efficient Backoff**: Exponential backoff minimizes unnecessary retries
- **Jitter Prevention**: Random delays prevent synchronized retry storms

The retry mechanism ensures that ChaosHunter can handle rate limits gracefully while maintaining optimal performance and reliability.
