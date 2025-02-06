from typing import List, Tuple, Callable, Iterator

import tiktoken
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain_core.runnables.base import Runnable
from langchain_core.output_parsers import JsonOutputParser
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult

from .wrappers import LLM, LLMBaseModel, BaseModel


def load_llm(
    model_name: str,
    temperature: float = 0.0,
    port: int = 8000,
    seed: int = 42,
) -> Runnable:
    if model_name.startswith("openai/"):
        return ChatOpenAI(
            model=model_name.split("openai/", 1)[1],
            temperature=temperature,
            seed=seed,
            request_timeout=30.0,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
    elif model_name.startswith("google/"):
        return ChatGoogleGenerativeAI(
            model=model_name.split("google/", 1)[1],
            temperature=temperature,
            model_kwargs={"generation_config": {"response_mime_type": "application/json"}}
        )
    elif model_name.startswith("anthropic/"):
        return ChatAnthropic(
            model=model_name.split("anthropic/", 1)[1],
            temperature=temperature,
            max_tokens=8192
            # model_kwargs=model_kwargs
        )
    else:
        # Note: VLLMOpenAI is for base models
        #       ref: https://python.langchain.com/v0.2/docs/integrations/chat/vllm/
        return ChatOpenAI(
            model=model_name,
            openai_api_key="EMPTY",
            openai_api_base=f"http://localhost:{port}/v1",
            temperature=temperature,
            max_tokens=2048,
            model_kwargs={"seed": seed}
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
                    if not prefix_added:
                        buffer += chunk.content
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
                        yield chunk.content
        else:
            def add_prefill(input: Iterator[str]) -> Iterator[str]:
                buffer = ""
                prefix_added = False
                prefill_len = len(prefill_str) + 5 # margin
                for chunk in input:
                    if not prefix_added:
                        buffer += chunk.content
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
                        yield chunk.content
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
                    elif self.model_provider in ["google", "anthropic"]:
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
    "google/gemini-1.5-pro-latest": {
        "input": 3.50 / UNIT,
        "output": 10.50 / UNIT
    },
    "google/gemini-1.5-pro": {
        "input": 3.50 / UNIT,
        "output": 10.50 / UNIT
    },
    "anthropic/claude-3-5-sonnet-20241022": {
        "input": 3.75 / UNIT,
        "output": 15. / UNIT
    },
    "anthropic/claude-3-5-sonnet-20240620": {
        "input": 3.75 / UNIT,
        "output": 15. / UNIT
    },
}