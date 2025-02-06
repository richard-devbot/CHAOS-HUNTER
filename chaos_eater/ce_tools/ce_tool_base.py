from typing import List
from abc import ABC, abstractmethod

class CEToolBase(ABC):
    @abstractmethod
    def get_docs(self, chaos_vars: List[str]) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_chaos_var_candidates(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_workflow_format_name(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_workflow_file_suffix(self) -> str:
        raise NotImplementedError
    
    @abstractmethod
    def get_workflow_validation_condition(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def extract_workflow(self, input_stream) -> str:
        raise NotImplementedError
    
    