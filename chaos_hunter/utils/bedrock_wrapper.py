"""
Custom wrapper for AWS Bedrock models to avoid circular reference issues
"""

from typing import Any, Iterator, List, Optional
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks.manager import CallbackManagerForLLMRun


class BedrockWrapper(BaseChatModel):
    """
    Wrapper for ChatBedrockConverse to avoid circular reference issues during serialization.
    """
    
    def __init__(
        self,
        model_id: str,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        region_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.region_name = region_name
        self._bedrock_model = None
    
    @property
    def bedrock_model(self) -> ChatBedrockConverse:
        """Lazy initialization of the Bedrock model to avoid serialization issues."""
        if self._bedrock_model is None:
            self._bedrock_model = ChatBedrockConverse(
                model_id=self.model_id,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                region_name=self.region_name
            )
        return self._bedrock_model
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response from the Bedrock model."""
        return self.bedrock_model._generate(messages, stop, run_manager, **kwargs)
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response from the Bedrock model asynchronously."""
        return await self.bedrock_model._agenerate(messages, stop, run_manager, **kwargs)
    
    def stream(
        self,
        input: List[BaseMessage],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[BaseMessage]:
        """Stream responses from the Bedrock model."""
        return self.bedrock_model.stream(input, config, **kwargs)
    
    async def astream(
        self,
        input: List[BaseMessage],
        config: Optional[Any] = None,
        **kwargs: Any,
    ) -> Iterator[BaseMessage]:
        """Stream responses from the Bedrock model asynchronously."""
        return await self.bedrock_model.astream(input, config, **kwargs)
    
    @property
    def _llm_type(self) -> str:
        """Return the LLM type."""
        return "bedrock_wrapper"
    
    @property
    def _identifying_params(self) -> dict:
        """Get the identifying parameters."""
        return {
            "model_id": self.model_id,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "region_name": self.region_name,
        }
