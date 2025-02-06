import asyncio
from typing import Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic

from chaos_eater.utils.llms import TokenCounterCallback


def print_tokens(method: str, token_counter: Dict[str, int]) -> None:
    input_tokens = token_counter['input_tokens']
    output_tokens = token_counter['output_tokens']
    total_tokens = token_counter['total_tokens']
    print(f"{method} test:")
    print(f"  - Input tokens: {input_tokens}")
    print(f"  - Output tokens: {output_tokens}")
    print(f"  - Total tokens: {total_tokens}")
    assert input_tokens > 0
    assert output_tokens > 0
    assert total_tokens > 0

def load_chain(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant."),
        ("user", "{input}")
    ])
    chain = prompt | llm
    return chain

def estimate_tokens(llm, input: str) -> Dict[str, int]:
    chain = load_chain(llm)
    # invoke test
    token_counter = TokenCounterCallback(llm)
    _ = chain.invoke({"input": input}, {"callbacks": [token_counter]})
    print_tokens("invoke", token_counter.counter)
    # stream test
    token_counter = TokenCounterCallback(llm)
    for _ in chain.stream({"input": input}, {"callbacks": [token_counter]}):
        pass
    print_tokens("stream", token_counter.counter)

async def estimate_tokens_async(llm, input: str) -> Dict[str, int]:
    # define chain
    chain = load_chain(llm)
    # ainvoke test
    token_counter = TokenCounterCallback(llm)
    await chain.ainvoke({"input": input}, {"callbacks": [token_counter]})
    print_tokens("ainvoke", token_counter.counter)
    # astream test
    token_counter = TokenCounterCallback(llm)
    async for _ in chain.astream({"input": input}, {"callbacks": [token_counter]}):
        pass
    print_tokens("astream", token_counter.counter)

#-------
# Tests
#-------
def test_gpt_token_count():
    print()
    print("GPT token count:")
    gpt = ChatOpenAI(model="gpt-4o-2024-08-06", temperature=0)
    estimate_tokens(gpt, "Hello!")
    asyncio.run(estimate_tokens_async(gpt, "Hello!"))

def test_gemini_token_count():
    print()
    print("Gemini token count:")
    gemini = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
    estimate_tokens(gemini, "Hello!")
    asyncio.run(estimate_tokens_async(gemini, "Hello!"))

def test_claude_token_count():
    print()
    print("Claude token count:")
    claude = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0)
    estimate_tokens(claude, "Hello!")
    asyncio.run(estimate_tokens_async(claude, "Hello!"))