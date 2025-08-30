from typing import List

from .llms import LLMLog


class ChaosHunterCallback:
    def __init__(self):
        pass

    #--------------------
    # preprocess Phase
    #--------------------
    def on_preprocess_start(self):
        pass

    def on_preprocess_end(self, logs: List[LLMLog]):
        pass

    #--------------------
    # hypothesis phase
    #--------------------
    def on_hypothesis_start(self):
        pass

    def on_hypothesis_end(self, logs: List[LLMLog]):
        pass

    #--------------------
    # experiment phase
    #--------------------
    def on_experiment_plan_start(self):
        pass

    def on_experiment_plan_end(self, logs: List[LLMLog]):
        pass

    def on_experiment_start(self):
        pass

    def on_experiment_end(self):
        pass

    def on_experiment_replan_start(self):
        pass

    def on_experiment_replan_end(self, logs: List[LLMLog]):
        pass

    #--------------------
    # analysis phase
    #--------------------
    def on_analysis_start(self):
        pass

    def on_analysis_end(self, logs: List[LLMLog]):
        pass

    #--------------------
    # improvement phase
    #--------------------
    def on_improvement_start(self):
        pass

    def on_improvement_end(self, logs: List[LLMLog]):
        pass

    #---------------------
    # postprocess phase
    #---------------------
    def on_postprocess_start(self):
        pass

    def on_postprocess_end(self, logs: List[LLMLog]):
        pass