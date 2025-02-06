import os
import re
import glob

from chaos_eater.utils.llms import load_llm
from chaos_eater.utils.functions import save_json, load_json
from chaos_eater.chaos_eater import ChaosEaterOutput
from chaos_eater.reviewing.reviwer import Reviewer


def evaluate(
    result_dir: str,
    model_name: str,
    temperature: float = 0.0,
    port: int = 8000,
    seed: int = 42,
    uses_cache: bool = False
) -> None:
    #--------------
    # load results
    #--------------
    # find results
    pattern = os.path.join(result_dir, "result*")
    result_paths = glob.glob(pattern)
    result_paths.sort()
    # add results to test
    results = []
    for path in result_paths:
        results.append(ChaosEaterOutput(**load_json(path)))

    #-------------------------
    # load llm and reviewer
    #-------------------------
    llm = load_llm(
        model_name=model_name, 
        temperature=temperature,
        port=port,
        model_kwargs={"seed": seed}
    )
    reviewer = Reviewer(llm)

    #------------
    # evaluation
    #------------
    if uses_cache:
        model_name_ = model_name.split('/')[-1]
        pattern_ = re.compile(rf'review\d+_{re.escape(model_name_)}\.json')
        offset = 0
        for file_name in os.listdir(result_dir):
            if pattern_.match(file_name):
                offset += 1
    else:
        offset = 0
    for i, result in enumerate(results[offset:]):
        if result.ce_cycle.completes_reconfig:
            review = reviewer.review(result.ce_cycle)
            review_dict = review.dict()
        else:
            review_dict = {}
        save_json(f"{result_dir}/review{i+offset}_{model_name_}.json", review_dict)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--result_dir", default="dataset", type=str, help="The path to the dataset")
    parser.add_argument("--model_name", default="openai/gpt-4o-2024-08-06", type=str, choices=["openai/gpt-4o-2024-08-06", "openai/gpt-4o-2024-05-13", "google/gemini-1.5-pro", "anthropic/claude-3-5-sonnet-20240620", "meta-llama/Meta-Llama-3-70B-Instruct"], help="Model name of an LLM")
    parser.add_argument("--temperature", default=0.0, type=float, help="Temperature of the LLM")
    parser.add_argument("--seed", default=42, type=int, help="Seed number of the LLM")
    parser.add_argument("--port", default=8000, type=int, help="Port number of the vLLM server")
    parser.add_argument("--experiment_time_limit", default=5, type=int, help="The maximum duration of the Chaos-Engineering experiment")
    parser.add_argument("--uses_cache", action="store_true", help="Whether to use the dataset cache")
    args = parser.parse_args()
    evaluate(
        result_dir=args.result_dir,
        model_name=args.model_name,
        temperature=args.temperature,
        port=args.port,
        seed=args.seed,
        uses_cache=args.uses_cache
    )