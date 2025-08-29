import time
import random
import re
from typing import List, Tuple, Callable, Iterator, Optional, Any
from functools import wraps

import tiktoken
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrockConverse
from .bedrock_wrapper import BedrockWrapper
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables.base import Runnable
from langchain_core.output_parsers import JsonOutputParser
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult

from .wrappers import LLM, LLMBaseModel, BaseModel


def extract_retry_delay(error_str: str) -> Optional[int]:
    """Extract retry delay from error message using multiple patterns."""
    if "retry_delay" in error_str:
        try:
            # Try multiple patterns to extract retry delay
            patterns = [
                r'retry_delay\s*{\s*seconds:\s*(\d+)',
                r'retry_delay.*?seconds:\s*(\d+)',
                r'retry_delay.*?(\d+)\s*seconds',
                r'seconds:\s*(\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, error_str, re.IGNORECASE | re.DOTALL)
                if match:
                    return int(match.group(1))
        except:
            pass
    return None


def retry_with_exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator that implements exponential backoff retry logic for rate-limited API calls.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to avoid thundering herd
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is a rate limit error
                    is_rate_limit = False
                    retry_after = None
                    
                    # Google Gemini rate limit
                    if "ResourceExhausted" in str(e) and "429" in str(e):
                        is_rate_limit = True
                        # Extract retry delay from error message if available
                        retry_after = extract_retry_delay(str(e))
                    
                    # OpenAI rate limit
                    elif "rate_limit" in str(e).lower() or "429" in str(e):
                        is_rate_limit = True
                        # Extract retry-after header if available
                        if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                            retry_after = e.response.headers.get('retry-after')
                            if retry_after:
                                try:
                                    retry_after = int(retry_after)
                                except:
                                    pass
                    
                    # Anthropic rate limit
                    elif "rate_limit" in str(e).lower() or "429" in str(e):
                        is_rate_limit = True
                    
                    # AWS Bedrock rate limit
                    elif "throttling" in str(e).lower() or "throttled" in str(e).lower():
                        is_rate_limit = True
                    
                    # If it's not a rate limit error or we've exhausted retries, raise the exception
                    if not is_rate_limit or attempt == max_retries:
                        raise last_exception
                    
                    # Calculate delay with exponential backoff
                    if retry_after:
                        delay = retry_after
                    else:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to avoid thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    print(f"Rate limit hit, retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def create_retry_llm(llm_class, max_retries: int = 5, **kwargs):
    """
    Create an LLM instance with retry capabilities.
    """
    llm = llm_class(**kwargs)
    
    # Wrap the _generate method with retry logic
    original_generate = llm._generate
    original_agenerate = getattr(llm, '_agenerate', None)
    
    @retry_with_exponential_backoff(max_retries=max_retries, base_delay=2.0, max_delay=120.0)
    def retry_generate(*args, **kwargs):
        return original_generate(*args, **kwargs)
    
    @retry_with_exponential_backoff(max_retries=max_retries, base_delay=2.0, max_delay=120.0)
    def retry_agenerate(*args, **kwargs):
        return original_agenerate(*args, **kwargs)
    
    # Apply retry logic to core methods
    llm._generate = retry_generate
    if original_agenerate:
        llm._agenerate = retry_agenerate
    
    # For streaming methods, we need to be more careful since they might not exist
    # or might be properties that can't be directly assigned
    try:
        # Check if stream method exists and is callable
        if hasattr(llm, 'stream') and callable(getattr(llm, 'stream')):
            original_stream = llm.stream
            
            def retry_stream(*args, **kwargs):
                for attempt in range(max_retries + 1):  # max_retries + 1 initial attempt
                    try:
                        return original_stream(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_retries:  # Last attempt
                            raise e
                        
                        # Check if this is a rate limit error
                        is_rate_limit = False
                        retry_after = None
                        
                        if "ResourceExhausted" in str(e) and "429" in str(e):
                            is_rate_limit = True
                            retry_after = extract_retry_delay(str(e))
                        elif "rate_limit" in str(e).lower() or "429" in str(e):
                            is_rate_limit = True
                        
                        if not is_rate_limit:
                            raise e
                        
                        delay = retry_after if retry_after else min(2.0 * (2.0 ** attempt), 120.0)
                        if random.random() > 0.5:  # Add jitter
                            delay = delay * (0.5 + random.random() * 0.5)
                        
                        print(f"Stream rate limit hit, retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
            
            # Use setattr to avoid Pydantic field validation issues
            setattr(llm, 'stream', retry_stream)
    except Exception as e:
        # If we can't set the stream method, just log it and continue
        print(f"Warning: Could not wrap stream method: {e}")
    
    try:
        # Check if astream method exists and is callable
        if hasattr(llm, 'astream') and callable(getattr(llm, 'astream')):
            original_astream = llm.astream
            
            def retry_astream(*args, **kwargs):
                for attempt in range(max_retries + 1):  # max_retries + 1 initial attempt
                    try:
                        return original_astream(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_retries:  # Last attempt
                            raise e
                        
                        # Check if this is a rate limit error
                        is_rate_limit = False
                        retry_after = None
                        
                        if "ResourceExhausted" in str(e) and "429" in str(e):
                            is_rate_limit = True
                            retry_after = extract_retry_delay(str(e))
                        elif "rate_limit" in str(e).lower() or "429" in str(e):
                            is_rate_limit = True
                        
                        if not is_rate_limit:
                            raise e
                        
                        delay = retry_after if retry_after else min(2.0 * (2.0 ** attempt), 120.0)
                        if random.random() > 0.5:  # Add jitter
                            delay = delay * (0.5 + random.random() * 0.5)
                        
                        print(f"Async stream rate limit hit, retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
            
            # Use setattr to avoid Pydantic field validation issues
            setattr(llm, 'astream', retry_astream)
    except Exception as e:
        # If we can't set the astream method, just log it and continue
        print(f"Warning: Could not wrap astream method: {e}")
    
    return llm


def load_llm(
    model_name: str,
    temperature: float = 0.0,
    port: int = 8000,
    seed: int = 42,
    aws_region: str = None,
    max_retries: int = 5, # Add max_retries parameter
) -> Runnable:
    if model_name.startswith("openai/"):
        return create_retry_llm(
            ChatOpenAI,
            model=model_name.split("openai/", 1)[1],
            temperature=temperature,
            seed=seed,
            request_timeout=30.0
        )
    elif model_name.startswith("google/"):
        # Normalize optional AI Studio style prefix like "google/models/<id>"
        google_model_id = model_name.split("google/", 1)[1]
        if google_model_id.startswith("models/"):
            google_model_id = google_model_id.split("models/", 1)[1]
        return create_retry_llm(
            ChatGoogleGenerativeAI,
            max_retries=max_retries, # Pass max_retries here
            model=google_model_id,
            temperature=temperature,
            timeout=60.0,  # Set timeout for requests
            # max_retries=5,  # This is now handled by create_retry_llm
            max_output_tokens=8192,
            top_p=0.95,
            top_k=40
        )
    elif model_name.startswith("anthropic/"):
        return create_retry_llm(
            ChatAnthropic,
            model=model_name.split("anthropic/", 1)[1],
            temperature=temperature,
            max_tokens=8192
        )
    elif model_name.startswith("bedrock/"):
        # For BedrockWrapper, we need to handle it differently since it's a custom wrapper
        bedrock_wrapper = BedrockWrapper(
            model_id=model_name.split("bedrock/", 1)[1],
            temperature=temperature,
            max_tokens=8192,
            region_name=aws_region
        )
        
        # Wrap the bedrock model's methods with retry logic
        original_generate = bedrock_wrapper._generate
        original_agenerate = getattr(bedrock_wrapper, '_agenerate', None)
        
        @retry_with_exponential_backoff(max_retries=5, base_delay=2.0, max_delay=120.0)
        def retry_generate(*args, **kwargs):
            return original_generate(*args, **kwargs)
        
        @retry_with_exponential_backoff(max_retries=5, base_delay=2.0, max_delay=120.0)
        def retry_agenerate(*args, **kwargs):
            return original_agenerate(*args, **kwargs)
        
        # Apply retry logic to core methods
        bedrock_wrapper._generate = retry_generate
        if original_agenerate:
            bedrock_wrapper._agenerate = retry_agenerate
        
        # For streaming methods, we need to be more careful since they might not exist
        # or might be properties that can't be directly assigned
        try:
            # Check if stream method exists and is callable
            if hasattr(bedrock_wrapper, 'stream') and callable(getattr(bedrock_wrapper, 'stream')):
                original_stream = bedrock_wrapper.stream
                
                def retry_stream(*args, **kwargs):
                    for attempt in range(6):  # 5 retries + 1 initial attempt
                        try:
                            return original_stream(*args, **kwargs)
                        except Exception as e:
                            if attempt == 5:  # Last attempt
                                raise e
                            
                            # Check if this is a rate limit error
                            is_rate_limit = False
                            retry_after = None
                            
                            if "ResourceExhausted" in str(e) and "429" in str(e):
                                is_rate_limit = True
                                if "retry_delay" in str(e):
                                    try:
                                        import re
                                        match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', str(e))
                                        if match:
                                            retry_after = int(match.group(1))
                                    except:
                                        pass
                            elif "rate_limit" in str(e).lower() or "429" in str(e) or "throttling" in str(e).lower():
                                is_rate_limit = True
                            
                            if not is_rate_limit:
                                raise e
                            
                            delay = retry_after if retry_after else min(2.0 * (2.0 ** attempt), 120.0)
                            if random.random() > 0.5:  # Add jitter
                                delay = delay * (0.5 + random.random() * 0.5)
                            
                            print(f"Bedrock stream rate limit hit, retrying in {delay:.2f} seconds (attempt {attempt + 1}/6)")
                            time.sleep(delay)
                
                # Use setattr to avoid Pydantic field validation issues
                setattr(bedrock_wrapper, 'stream', retry_stream)
        except Exception as e:
            # If we can't set the stream method, just log it and continue
            print(f"Warning: Could not wrap Bedrock stream method: {e}")
        
        try:
            # Check if astream method exists and is callable
            if hasattr(bedrock_wrapper, 'astream') and callable(getattr(bedrock_wrapper, 'astream')):
                original_astream = bedrock_wrapper.astream
                
                def retry_astream(*args, **kwargs):
                    for attempt in range(6):  # 5 retries + 1 initial attempt
                        try:
                            return original_astream(*args, **kwargs)
                        except Exception as e:
                            if attempt == 5:  # Last attempt
                                raise e
                            
                            # Check if this is a rate limit error
                            is_rate_limit = False
                            retry_after = None
                            
                            if "ResourceExhausted" in str(e) and "429" in str(e):
                                is_rate_limit = True
                                retry_after = extract_retry_delay(str(e))
                            elif "rate_limit" in str(e).lower() or "429" in str(e) or "throttling" in str(e).lower():
                                is_rate_limit = True
                            
                            if not is_rate_limit:
                                raise e
                            
                            delay = retry_after if retry_after else min(2.0 * (2.0 ** attempt), 120.0)
                            if random.random() > 0.5:  # Add jitter
                                delay = delay * (0.5 + random.random() * 0.5)
                            
                            print(f"Bedrock async stream rate limit hit, retrying in {delay:.2f} seconds (attempt {attempt + 1}/6)")
                            time.sleep(delay)
                
                # Use setattr to avoid Pydantic field validation issues
                setattr(bedrock_wrapper, 'astream', retry_astream)
        except Exception as e:
            # If we can't set the astream method, just log it and continue
            print(f"Warning: Could not wrap Bedrock astream method: {e}")
        
        return bedrock_wrapper
    else:
        # Note: VLLMOpenAI is for base models
        #       ref: https://python.langchain.com/v0.2/docs/integrations/chat/vllm/
        return create_retry_llm(
            ChatOpenAI,
            model=model_name,
            openai_api_key="EMPTY",
            openai_api_base=f"http://localhost:{port}/v1",
            temperature=temperature,
            max_tokens=2048
        )
    

def build_json_agent(
    llm: LLM,
    chat_messages: List[Tuple[str, str]],
    pydantic_object: LLMBaseModel,
    is_async: bool = False,
    enables_prefill: bool = True,
    streaming_func: Callable = None
) -> Runnable:
    if enables_prefill:
        first_key = str(list(pydantic_object.__fields__.keys())[0])
        prefill_str = '```json\n{{\"{key}\":'.replace("{key}", first_key)
        # chat_messages.append(("human", 'The keys and values in the output JSON dictionary must always be enclosed in single double quotes. Triple quotes (""" or ```) must not be used.'))
        chat_messages.append(("ai", prefill_str)) # add json prefill
        # chat_messages.append(("human", "Please continue the output from where it left off."))
        # chat_messages.append(("human", "Please continue the subsequent output from the middle."))
    parser = JsonOutputParser(pydantic_object=pydantic_object)
    prompt = ChatPromptTemplate.from_messages(chat_messages)
    prompt = prompt.partial(format_instructions=parser.get_format_instructions())
    if streaming_func is None:
        if is_async:
            async def extract_json_items_streaming(input_stream):
                async for input in input_stream:
                    if not isinstance(input, dict):
                        continue
                    yield {key: input.get(key) for key in pydantic_object.__fields__.keys()}
        else:
            def extract_json_items_streaming(input_stream):
                for input in input_stream:
                    if not isinstance(input, dict):
                        continue
                    yield {key: input.get(key) for key in pydantic_object.__fields__.keys()}
    else:
        extract_json_items_streaming = streaming_func
    if enables_prefill:
        if is_async:
            async def add_prefill(input):
                buffer = ""
                prefix_added = False
                prefill_len = len(prefill_str) + 5 # margin
                async for chunk in input:
                    content = chunk.content if isinstance(chunk.content, str) else str(chunk.content[0] if isinstance(chunk.content, list) else chunk.content)
                    if not prefix_added:
                        buffer += content
                        buffer_len = len(buffer)
                        if buffer_len >= prefill_len:
                            if "```json" in buffer:
                                yield buffer
                                prefix_added = True
                            else:
                                prefill_str_ = prefill_str.replace("{{", "{")
                                if prefill_str_.replace("```json\n", "") in buffer.replace("\n", ""):
                                    yield "```json\n" + buffer
                                else:
                                    yield prefill_str_ + buffer
                                prefix_added = True
                    else:
                        yield content
        else:
            def add_prefill(input: Iterator[str]) -> Iterator[str]:
                buffer = ""
                prefix_added = False
                prefill_len = len(prefill_str) + 5 # margin
                for chunk in input:
                    content = chunk.content if isinstance(chunk.content, str) else str(chunk.content[0] if isinstance(chunk.content, list) else chunk.content)
                    if not prefix_added:
                        buffer += content
                        buffer_len = len(buffer)
                        if buffer_len >= prefill_len:
                            if "```json" in buffer:
                                yield buffer
                                prefix_added = True
                            else:
                                prefill_str_ = prefill_str.replace("{{", "{")
                                if prefill_str_.replace("```json\n", "") in buffer.replace("\n", ""):
                                    yield "```json\n" + buffer
                                else:
                                    yield prefill_str_ + buffer
                                prefix_added = True
                    else:
                        yield content
        agent = prompt | llm | add_prefill | parser | extract_json_items_streaming
    else:
        agent = prompt | llm | parser | extract_json_items_streaming
    return agent


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int

class LLMLog(BaseModel):
    name: str
    token_usage: TokenUsage
    message_history: List[List[str] | str]

class LoggingCallback(BaseCallbackHandler):
    def __init__(
        self,
        name: str,
        llm: LLM,
        streaming: bool = True
    ) -> None:
        if "model" in list(llm.__fields__.keys()):
            self.model_name = llm.model
            if "gemini" in self.model_name:
                self.model_provider = "google"
            elif "claude" in self.model_name:
                self.model_provider = "anthropic"
            else:
                raise TypeError(f"Invalid model name: {self.model_name}")
        elif "model_name" in list(llm.__fields__.keys()):
            self.model_name = llm.model_name
            if "gpt" in self.model_name:
                self.model_provider = "openai"
            else:
                raise TypeError(f"Invalid model name: {self.model_name}")
        elif "model_id" in list(llm.__fields__.keys()):
            self.model_name = llm.model_id
            if "bedrock" in str(type(llm)) or hasattr(llm, '_llm_type') and llm._llm_type == "bedrock_wrapper":
                self.model_provider = "bedrock"
            else:
                raise TypeError(f"Invalid model name: {self.model_name}")
        else:
            raise TypeError(f"Invalid llm: {llm}")
        self.streaming = streaming
        if self.model_provider == "openai" and self.streaming:
            self.enc = tiktoken.encoding_for_model(self.model_name)
        self.token_usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0
        )
        self.message_history = []
        self.name = name
        self.log = LLMLog(
            name=self.name,
            token_usage=self.token_usage,
            message_history=self.message_history
        )

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.message_history.append(prompts)
        if self.model_provider == "openai" and self.streaming:
            for prompt in prompts:
                self.token_usage.input_tokens += len(self.enc.encode(prompt))

    def on_llm_end(self, response: LLMResult, **kwargs):
        for generations in response.generations:
            for generation in generations:
                if self.model_provider == "openai" and self.streaming:
                    self.token_usage.output_tokens += len(self.enc.encode(generation.text))
                    self.token_usage.total_tokens = self.token_usage.input_tokens + self.token_usage.output_tokens
                else:
                    if self.model_provider == "openai":
                        tokens = generation.message.response_metadata.get("token_usage")
                        self.token_usage.input_tokens += tokens.get("prompt_tokens", -1)
                        self.token_usage.output_tokens += tokens.get("completion_tokens", -1)
                        self.token_usage.total_tokens += tokens.get("total_tokens", -1)
                    elif self.model_provider in ["google", "anthropic", "bedrock"]:
                        tokens = generation.message.usage_metadata
                        self.token_usage.input_tokens += tokens.get("input_tokens", -1)
                        self.token_usage.output_tokens += tokens.get("output_tokens", -1)
                        self.token_usage.total_tokens += tokens.get("total_tokens", -1)
                self.message_history.append(generation.text)
        self.log = LLMLog(
            name=self.name,
            token_usage=self.token_usage,
            message_history=self.message_history
        )

UNIT = 1e+6
PRICING_PER_TOKEN = {
    "openai/gpt-4o-2024-08-06": {
        "input": 2.50 / UNIT,
        "output": 10. / UNIT
    },
    "openai/gpt-4o-2024-05-13": {
        "input": 5.00 / UNIT,
        "output": 15.00 / UNIT
    },
    "openai/gpt-4o-mini-2024-07-18": {
        "input": 0.15 / UNIT,
        "output": 0.6 / UNIT
    },
    "google/gemini-2.5-pro": {
        "input": 5.50 / UNIT,
        "output": 12.50 / UNIT
    },
    "google/gemini-2.5-flash": {
        "input": 4.50 / UNIT,
        "output": 11.50 / UNIT
    },
    # Approximate pricing: align with gemini-2.5-flash unless adjusted later
    "google/gemini-2.0-flash-lite": {
        "input": 4.50 / UNIT,
        "output": 11.50 / UNIT
    },
    "anthropic/claude-3-5-sonnet-20241022": {
        "input": 3.75 / UNIT,
        "output": 15. / UNIT
    },
    "anthropic/claude-3-5-sonnet-20240620": {
        "input": 3.75 / UNIT,
        "output": 15. / UNIT
    },
    # AWS Bedrock models
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v1:0": {
        "input": 3.75 / UNIT,
        "output": 15. / UNIT
    },
    "bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0": {
        "input": 3.75 / UNIT,
        "output": 15. / UNIT
    },
    "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0": {
        "input": 0.25 / UNIT,
        "output": 1.25 / UNIT
    },
    "bedrock/anthropic.claude-3-opus-20240229-v1:0": {
        "input": 15. / UNIT,
        "output": 75. / UNIT
    },
    "bedrock/anthropic.claude-3-sonnet-20240229-v1:0": {
        "input": 3. / UNIT,
        "output": 15. / UNIT
    },
    "bedrock/anthropic.claude-3-haiku-20240307-v1:0": {
        "input": 0.25 / UNIT,
        "output": 1.25 / UNIT
    },
    "bedrock/amazon.titan-text-express-v1": {
        "input": 0.0008 / UNIT,
        "output": 0.0016 / UNIT
    },
    "bedrock/amazon.titan-text-lite-v1": {
        "input": 0.0003 / UNIT,
        "output": 0.0004 / UNIT
    },
    "bedrock/ai21.j2-ultra-v1": {
        "input": 12.5 / UNIT,
        "output": 12.5 / UNIT
    },
    "bedrock/ai21.j2-mid-v1": {
        "input": 2.5 / UNIT,
        "output": 2.5 / UNIT
    },
    "bedrock/cohere.command-r-v1:0": {
        "input": 5. / UNIT,
        "output": 25. / UNIT
    },
    "bedrock/cohere.command-r-plus-v1:0": {
        "input": 15. / UNIT,
        "output": 75. / UNIT
    },
    "bedrock/meta.llama-3-8b-instruct-v1:0": {
        "input": 0.2 / UNIT,
        "output": 0.2 / UNIT
    },
    "bedrock/meta.llama-3-70b-instruct-v1:0": {
        "input": 0.7 / UNIT,
        "output": 0.8 / UNIT
    },
    "bedrock/meta.llama-3-405b-instruct-v1:0": {
        "input": 1.2 / UNIT,
        "output": 1.6 / UNIT
    },
}