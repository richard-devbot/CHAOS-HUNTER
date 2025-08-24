from typing import List, Optional, Literal

from .selectors import Selectors
from ....utils.wrappers import LLMBaseModel, LLMField


# ref: https://chaos-mesh.org/docs/simulate-network-chaos-on-kubernetes/ (ver. 2.6.2)
class Selector(LLMBaseModel):
    mode: Literal["one", "all", "fixed", "fixed-percent", "random-max-percent"] = LLMField(
        example="one",
        description="Specifies the mode of the experiment. The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods)"
    )
    selector: Selectors = LLMField(
        example=None,
        description="Specifies the target Pod."
    )

class Reorder(LLMBaseModel):
    reorder: Optional[str] = LLMField(
        default="0", 
        example="0.5",
        description="Indicates the probability to reorder"
    )
    correlation: Optional[str] = LLMField(
        default="0", 
        example="50",
        description="Indicates the correlation between this time's length of delay time and the previous time's length of delay time. Range of value: [0, 100]",
    )
    gap: Optional[int] = LLMField(
        default=0, 
        example=5,
        description="Indicates the gap before and after packet reordering",
    )

class Deplay(LLMBaseModel):
    latency: Optional[str] = LLMField(
        default=None,
        example="2ms",
        description="Indicates the network latency"
    )
    correlation: Optional[str] = LLMField(
        default=None, 
        example="50",
        description="Indicates the correlation between the current latency and the previous one. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )
    jitter: Optional[str] = LLMField(
        default=None,
        example="1ms",
        description="Indicates the range of the network latency"
    )
    reorder: Optional[Reorder] = LLMField(
        default=None,
        description="Indicates the status of network packet reordering"
    )

class Loss(LLMBaseModel):
    loss: Optional[str] = LLMField(
        default="0",
        example="50",
        description="Indicates the probability of packet loss. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )
    correlation: Optional[str] = LLMField(
        default="0",
        example="50",
        description="Indicates the correlation between the probability of current packet loss and the previous time's packet loss. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )

class Duplicate(LLMBaseModel):
    duplicate: Optional[str] = LLMField(
        default="0",
        example="50",
        description="Indicates the probability of packet duplicating. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )
    correlation: Optional[str] = LLMField(
        default="0",
        example="50",
        description="Indicates the correlation between the probability of current packet duplicating and the previous time's packet duplicating. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )

class Corrupt(LLMBaseModel):
    corrupt: Optional[str] = LLMField(
        default="0",
        example="50",
        description="Indicates the probability of packet corruption. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )
    correlation: Optional[str] = LLMField(
        default="0",
        example="50",
        description="Indicates the correlation between the probability of current packet corruption and the previous time's packet corruption. Range of value: [0, 100]. Specify only the number. NEVER include any units."
    )

class Rate(LLMBaseModel):
    rate: str = LLMField(
        default=None,
        example="1mbps",
        description="Indicates the rate of bandwidth limit. Allows bit, kbit, mbit, gbit, tbit, bps, kbps, mbps, gbps, tbps unit. bps means bytes per second"
    )

class Bandwidth(LLMBaseModel):
    rate: str = LLMField(
        default=None,
        example="1mbps",
        description="Indicates the rate of bandwidth limit. Allows bit, kbit, mbit, gbit, tbit, bps, kbps, mbps, gbps, tbps unit. bps means bytes per second"
    )
    limit: int = LLMField(
        default=None,
        example=1,
        description="Indicates the number of bytes waiting in queue"
    )
    buffer: int = LLMField(
        default=None,
        example=1,
        description="Indicates the maximum number of bytes that can be sent instantaneously"
    )
    peakrate: Optional[int] = LLMField(
        default=None,
        example=1,
        description="Indicates the maximum consumption of bucket (usually not set)"
    )
    minburst: Optional[int] = LLMField(
        default=None,
        example=1,
        description="Indicates the size of peakrate bucket (usually not set)"
    )

class NetworkChaos(LLMBaseModel):
    action: Literal["netem", "delay", "loss", "duplicate", "corrupt", "partition", "bandwidth"] = LLMField(
        example="Partition",
        description="Indicates the specific fault type. Available types include: netem, delay (network delay), loss (packet loss), duplicate (packet duplicating), corrupt (packet corrupt), partition (network partition), and bandwidth (network bandwidth limit). After you specify action field, specify action-related fields for other necessary field configuration."
    )
    direction: Optional[Literal["from", "to", "both"]] = LLMField(
        default="to",
        example="both",
        description="Indicates the direction of target packets. Available vaules include from (the packets from target), to (the packets to target), and both (the packets from or to target). This parameter makes Chaos only take effect for a specific direction of packets."
    )
    target: Optional[Selector] = LLMField(
        default=None,
        description="Used in combination with direction, making Chaos only effective for some packets. 'from' and 'both' direction cannot be used when targets is empty in netem action."
    )
    mode: Literal["one", "all", "fixed", "fixed-percent", "random-max-percent"] = LLMField(
        example="one",
        description="Specifies the mode of the experiment. The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods)"
    )
    value: Optional[str] = LLMField(
        default=None,
        example="1",
        description="Provides parameters for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods."
    )
    selector: Selectors = LLMField(
        description="Specifies the target Pod."
    )
    externalTargets: Optional[List[str]] = LLMField(
        default=None,
        example=["1.1.1.1", "www.google.com"],
        description="Indicates the network targets except for Kubernetes, which can be IPv4 addresses or domains. This parameter only works with direction: to."
    )
    device: Optional[str] = LLMField(
        default=None,
        example="eth0",
        description="Specifies the affected network interface"
    )
    delay: Optional[Deplay] = LLMField(
        description="When setting action to delay means simulating network delay fault, you also need to configure this parameters."
    )
    loss: Optional[Loss] = LLMField( # TODO
        description="When setting action to loss means simulating packet loss fault, you can also configure this parameters."
    )
    duplicated: Optional[Duplicate] = LLMField( # TODO
        description="When setting action to duplicate, meaning simulating package duplication, you can also set this parameters."
    )
    corrupt: Optional[Corrupt] = LLMField( # TODO
        description="When setting action to corrupt means simulating package corruption fault, you can also configure the following parameters."
    )
    rate: Optional[Rate] = LLMField(
        description="When setting action to rate means simulating bandwidth rate fault, you also need to configure this parameters. This action is similar to bandwidth/rate below, however, the key distinction is that this action can combine with other netem actions listed above. However, if you require more control over the bandwidth simulation such as limiting the buffer size, select the bandwidth action."
    )
    bandwidth: Optional[Bandwidth] = LLMField(
        description="When setting 'action' to 'bandwidth' means simulating bandwidth limit fault, you also need to configure this parameters. This action is mutually exclusive with any netem action defined above. If you need to inject bandwidth rate along with other network failures such as corruption, use the rate action instead."
    )