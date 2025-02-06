from enum import Enum
from chaos_eater.ce_tools.ce_tool_base import CEToolBase
from chaos_eater.ce_tools.chaosmesh.chaosmesh import ChaosMesh

class CEToolType(Enum):
    chaosmesh = "chaosmesh"
    # chaosmonkey = "chaos_monkey"

class CETool:
    FACTORY_MAP = {
        CEToolType.chaosmesh: ChaosMesh,
        # CETools.chaosmonkey: ChaosMonkeyDoc,
    }

    @classmethod
    def init(cls, ce_tool: str) -> CEToolBase:
        if ce_tool in cls.FACTORY_MAP:
            return cls.FACTORY_MAP[ce_tool]()
        raise TypeError("Invalid chaos tool!")