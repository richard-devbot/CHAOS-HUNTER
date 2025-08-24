from .llm_agents.review_ce_cycle import CEReviewAgent, Review
from ..chaos_hunter import ChaosCycle
from ..utils.wrappers import LLM


class Reviewer:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.review_agent = CEReviewAgent(llm)

    def review(self, ce_cycle: ChaosCycle) -> Review:
        review = self.review_agent.reveiew(ce_cycle)
        return review