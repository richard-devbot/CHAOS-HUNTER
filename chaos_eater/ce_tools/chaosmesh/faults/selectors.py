from typing import List, Dict, Literal, Optional
from langchain_core.pydantic_v1 import BaseModel, Field, root_validator


# ref: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#resources-that-support-set-based-requirements
class SetBasedRequirements(BaseModel):
    key: str = Field(description="Label key")
    operator: Literal["In", "NotIn", "Exists", "DoesNotExist"] = Field(description="Select an operator.")
    values: List[str] = Field(description="Label values. The values set must be non-empty in the case of In and NotIn.")

# ref: https://chaos-mesh.org/docs/define-chaos-experiment-scope/
class Selectors(BaseModel):
    # namespace selectors
    namespaces: Optional[List[str]] = Field(
        default=None,
        description="Specifies the namespace of the experiment's target Pod. If this selector is None, Chaos Mesh will set it to the namespace of the current Chaos experiment."
    )
    # label selectors
    labelSelectors: Optional[Dict[str, str]] = Field(
        default=None,
        description="Specifies the label-key/value pairs that the experiment's target Pod must have. If multiple labels are specified, the experiment target must have all the labels specified by this selector."
    )
    # expression selectors: https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/#resources-that-support-set-based-requirements
    expressionSelectors: Optional[List[SetBasedRequirements]] = Field(
        default=None,
        example=[{"key": "tier", "operator": "In", "values": ["cache"]}, {"key": "environment", "operator": "NotIn", "values": ["dev"]}],
        description="Specifies a set of expressions that define the label's rules to specifiy the experiment's target Pod."
    )
    # annotation selectors
    annotationSelectors: Optional[Dict[str, str]] = Field(
        default=None,
        description="Specifies the annotation-key/value pairs that the experiment's target Pod must have. If multiple annotations are specified, the experiment target must have all annotations specified by this selector."
    )
    # field selectors
    fieldSelectors: Optional[Dict[str, str]] = Field(
        default=None,
        example={"metadata.name": "my-pod", "metadata.namespace": "dafault"},
        description="Specifies the field-key/value pairs of the experiment's target Pod. If multiple fields are specified, the experiment target must have all fields set by this selector."
    )
    # pod selectors
    podPhaseSelectors: Optional[List[Literal["Pending", "Running", "Succeeded", "Failed", "Unknown"]]] = Field(
        default=None,
        description="Specifies the phase of the experiment's target Pod. If this selector is None, the target Pod's phase is not limited."
    )
    # node selectors
    nodeSelectors: Optional[Dict[str, str]] = Field(
        default=None,
        description="Specifies the node-label-key/value pairs to which the experiment's target Pod belongs."
    )
    # node list selectors
    nodes: Optional[List[str]] = Field(
        default=None,
        description="Specifies the node to which the experiment's target Pod belongs. The target Pod can only belong to one node in the configured node list. If multiple node labels are specified, the node to which the experiment's target Pod belongs must have all labels specified by this selector."
    )
    # pod list selector
    pods: Optional[Dict[str, List[str]]] = Field(
        default=None,
        example={"default": ["pod-0", "pod-2"]},
        description="Specifies the namespaces and list of the experiment's target Pods. If you have specified this selector, Chaos Mesh ignores other configured selectors."
    )
    # @root_validator(pre=True)
    # def check_at_least_one_field(cls, values):
    #     if not any(values.get(field) for field in ['field1', 'field2', 'field3']):
    #         raise ValueError('At least one of field1, field2, or field3 must be provided')
    #     return values