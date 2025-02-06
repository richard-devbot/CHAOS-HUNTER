import re
import os
import yaml
from collections import Counter, defaultdict
from typing import List, Dict, Literal, Tuple

from ..llm_agents.experiment_plan_agent import DEADLINE_MARGIN
from ...utils.functions import (
    write_file,
    copy_file,
    get_timestamp,
    add_timeunit,
    parse_time,
    list_to_bullet_points,
    render_jinja_template
)
from ...utils.schemas import File
from ...utils.constants import (
    META_TEMPLATE_PATH,
    TASK_TEMPLATE_PATH,
    TASK_K6_TEMPLATE_PATH,
    FAULT_TEMPLATE_PATH,
    GROUNDCHILDREN_TEMPLATE_PATH,
    SUSPEND_TEMPLATE_PATH
)


class IndentedDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(IndentedDumper, self).increase_indent(flow, False)

class NameConfilictAvoider:
    def __init__(self):
        self.name_counter = Counter()

    def avoid_name_confilict(self, workflow_name: str) -> str:
        self.name_counter[workflow_name] += 1
        if self.name_counter[workflow_name] == 1:
            return workflow_name
        else:
            return f"{workflow_name}{self.name_counter[workflow_name]}"


class Plan2WorkflowConverter:
    def convert(
        self,
        experiment_plan: dict,
        work_dir: str
    ) -> Tuple[str, File]:
        temp_dir = f"{work_dir}/temp"
        os.makedirs(temp_dir, exist_ok=True)
        # generate jinja templates
        templates = self.generate_templates(experiment_plan, temp_dir)
        # generate meta-template
        workflow_path = f"{work_dir}/workflow.yaml"
        workflow_name, workflow = self.generate_workflow(experiment_plan, temp_dir)
        write_file(fname=workflow_path, content=workflow)
        return (
            workflow_name,
            File(
                path=workflow_path,
                content=workflow,
                work_dir=work_dir,
                fname="workflow.yaml"
            ),
        )

    def generate_workflow(
        self,
        experiement_plan: dict,
        intermediate_dir: str
    ) -> Tuple[str, str]:
        meta_template_path_src=META_TEMPLATE_PATH
        meta_template_path_dst=f"{intermediate_dir}/{os.path.basename(meta_template_path_src)}"
        copy_file(meta_template_path_src, meta_template_path_dst)
        pre_validation_type, pre_validation_deadline, pre_validation_children, pre_validation_grandchildren = self.get_children(experiement_plan, "pre_validation")
        fault_injection_type, fault_validation_deadline, fault_injection_children, fault_injection_grandchildren = self.get_children(experiement_plan, "fault_injection")
        post_validation_type, pospost_validation_deadline, post_validation_children, post_validation_grandchildren = self.get_children(experiement_plan, "post_validation")
        workflow_name = f"chaos-experiment-{get_timestamp().replace('_', '-')}"
        workflow = render_jinja_template(
            meta_template_path_dst,            
            workflow_name=workflow_name,
            # time schedule
            total_time=add_timeunit(pre_validation_deadline + fault_validation_deadline + pospost_validation_deadline + 3*DEADLINE_MARGIN),
            pre_validation_time=add_timeunit(pre_validation_deadline + DEADLINE_MARGIN),
            fault_injection_time=add_timeunit(fault_validation_deadline + DEADLINE_MARGIN),
            post_validation_time=add_timeunit(pospost_validation_deadline + DEADLINE_MARGIN),
            # pre-validation phase
            pre_validation_type=pre_validation_type,
            pre_validation_children=pre_validation_children,
            pre_validation_grandchildren=pre_validation_grandchildren,
            # fault-injection phase
            fault_injection_type=fault_injection_type,
            fault_injection_children=fault_injection_children,
            fault_injection_grandchildren=fault_injection_grandchildren,
            # post-validation phase
            post_validation_type=post_validation_type,
            post_validation_children=post_validation_children, 
            post_validation_grandchildren=post_validation_grandchildren
        )
        return workflow_name, workflow

    def get_children(
        self,
        plan: dict,
        phase_name: Literal["pre_validation", "fault_injection", "post_validation"]
    ) -> Tuple[str, int, str, str]:
        phase = plan[phase_name]
        tasks = phase["unit_tests"] if phase_name != "fault_injection" else phase["unit_tests"] + phase["fault_injection"]    
        para_groups = self.group_by_start_time(tasks)
        overlapped_groups = self.group_by_overlap(para_groups)
        children_workflows = []
        groundchildren_workflows = []
        name_confilict_avoider = NameConfilictAvoider()
        for overlapped_group in overlapped_groups:
            if len(overlapped_group["overlapped_group"]) == 1: # if no overlapped workflow exists in the group
                parallel_group = overlapped_group["overlapped_group"][0]
                if len(parallel_group["para_group"]["tasks"]) == 1: # if a sigle workflow exists in the group
                    children_workflows.append(parallel_group["para_group"]["tasks"][0]["workflow_name"])
                else:
                    parallel_workflows_name = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-parallel-workflows")
                    children_workflows.append(parallel_workflows_name)
                    groundchildren_workflows.append((
                        "Parallel",
                        parallel_workflows_name,
                        add_timeunit(parallel_group["para_group"]["duration"]),
                        [task["workflow_name"] for task in parallel_group["para_group"]["tasks"]]
                    ))
            else:
                workflow_name1 = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-overlapped-workflows")
                children_workflows.append(workflow_name1)
                overlapped_workflow_names = []
                for parallel_group in overlapped_group["overlapped_group"]:
                    if parallel_group["suspend_time"] == 0:
                        if len(parallel_group["para_group"]["tasks"]) == 1:
                            overlapped_workflow_names.append(parallel_group["para_group"]["tasks"][0]["workflow_name"])
                        else:
                            workflow_name2 = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-parallel-workflow")
                            overlapped_workflow_names.append(workflow_name2)
                            groundchildren_workflows.append((
                                "Parallel",
                                workflow_name2,
                                add_timeunit(parallel_group["para_group"]["duration"]),
                                [task["workflow_name"] for task in parallel_group["para_group"]["tasks"]]
                            ))
                    else:
                        if len(parallel_group["para_group"]["tasks"]) == 1:
                            workflow_name3 = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-suspend-workflow")
                            suspend_name1 = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-suspend")
                            overlapped_workflow_names.append(workflow_name3)
                            groundchildren_workflows.append((
                                "Serial",
                                workflow_name3,
                                add_timeunit(parallel_group["suspend_time"] + parallel_group["para_group"]["duration"]),
                                [suspend_name1, parallel_group["para_group"]["tasks"][0]["workflow_name"]]
                            ))
                            groundchildren_workflows.append((
                                "Suspend",
                                suspend_name1,
                                add_timeunit(parallel_group["suspend_time"])
                            ))
                        else:
                            workflow_name3 = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-suspend-workflow")
                            suspend_name1 = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-suspend")
                            parallel_workflows_name = name_confilict_avoider.avoid_name_confilict(f"{phase_name.replace('_', '-')}-parallel-workflows")
                            overlapped_workflow_names.append(workflow_name3)
                            groundchildren_workflows.append((
                                "Serial",
                                workflow_name3,
                                add_timeunit(parallel_group["suspend_time"] + parallel_group["para_group"]["duration"]),
                                [suspend_name1, parallel_workflows_name]
                            ))
                            groundchildren_workflows.append((
                                "Suspend",
                                suspend_name1,
                                add_timeunit(parallel_group["suspend_time"])
                            ))
                            groundchildren_workflows.append((
                                "Parallel",
                                parallel_workflows_name,
                                add_timeunit(parallel_group["para_group"]["duration"]),
                                [task["workflow_name"] for task in parallel_group["para_group"]["tasks"]]
                            ))
                groundchildren_workflows.append((
                    "Parallel",
                    workflow_name1,
                    add_timeunit(overlapped_group["duration"]),
                    overlapped_workflow_names
                ))
        children = list_to_bullet_points(children_workflows)
        groundchildren = self.get_groundchildren_str(groundchildren_workflows)
        # calc overall deadline
        deadlines = []
        for child_workflowname in children_workflows:
            for groundchild_workflow in groundchildren_workflows:
                if groundchild_workflow[1] == child_workflowname:
                    deadlines.append(groundchild_workflow[2])
        deadline = 0
        for child_deadline in deadlines:
            deadline += parse_time(child_deadline)
        return "Serial", deadline, children, groundchildren

    def group_by_start_time(self, items: List[dict]) -> Dict[str, List[dict]]:
        # grouping tasks whose grace period is the same
        groups = defaultdict(list)
        for item in items:
            groups[item["grace_period"]].append(item)
        return dict(groups)

    def group_by_overlap(self, group: Dict[str, List[dict]]) -> List[List[List[dict]]]:
        para_groups = []
        for grace_period, items in group.items():
            start = parse_time(grace_period)
            max_duration = max([parse_time(item["deadline"]) for item in items])
            end = start + max_duration
            para_groups.append({
                "start": start, 
                "end": end, 
                "duration": max_duration, 
                "tasks": items
            })
        sorted_para_groups = sorted(para_groups, key=lambda x: x["start"])
        #----------------------------------
        # groupping overlapped para_groups
        #----------------------------------
        result = []
        current_start = sorted_para_groups[0]["start"]
        current_end = sorted_para_groups[0]["end"]
        overlapped_duration = sorted_para_groups[0]["duration"]
        current_group = [{"suspend_time": current_start, "para_group": sorted_para_groups[0]}]
        for para_group in sorted_para_groups[1:]:
            start_time = para_group["start"]
            if start_time < current_end:
                suspend_time = start_time - current_start
                current_group.append({"suspend_time": suspend_time, "para_group": para_group})
                if current_end < para_group["end"]:
                    overlapped_duration += (para_group["end"] - current_end)
                current_end = max(current_end, para_group["end"])
            else:
                result.append({"duration": overlapped_duration, "overlapped_group": current_group})
                overlapped_duration = para_group["duration"]
                current_group = [{"suspend_time": 0, "para_group": para_group}]
                current_start = para_group["start"]
                current_end = para_group["end"]
        result.append({"duration": overlapped_duration, "overlapped_group": current_group})
        return result

    def get_groundchildren_str(self, groundchildren: List[tuple]) -> str:
        groundchildren_str = []
        for groundchild in groundchildren:
            groundchildren_str.append(self.get_groundchild_str(*groundchild))
        return "\n\n".join(groundchildren_str)

    def get_groundchild_str(
        self,
        template_type: Literal["Prallel", "Serial", "Suspend"],
        workflow_name: str,
        duration: str,
        children_list: List[str] = None
    ) -> str:
        if template_type == "Suspend":
            groundchild = render_jinja_template(
                SUSPEND_TEMPLATE_PATH,
                name=workflow_name,
                deadline=duration
            )
        else:
            groundchild = render_jinja_template(
                GROUNDCHILDREN_TEMPLATE_PATH,
                name=workflow_name,
                template_type=template_type,
                deadline=duration,
                groundchildren=list_to_bullet_points(children_list)    
            )
        return groundchild

    def generate_templates(
        self,
        experiment_plan: dict,
        intermediate_dir: str
    ) -> List[File]:
        templates = []
        # pre-validation phase
        pre_validation = experiment_plan["pre_validation"]
        pre_validation_templates_str = self.generate_unittest_templates_str(pre_validation["unit_tests"])
        write_file(fname=f"{intermediate_dir}/pre_validation_templates.j2", content=pre_validation_templates_str)
        # fault-injection phase
        fault_injection = experiment_plan["fault_injection"]
        fault_injection_unit_test_templates_str = self.generate_unittest_templates_str(fault_injection["unit_tests"])
        fault_injection_fault_templates_str = self.generate_fault_templates_str(fault_injection["fault_injection"])
        final_templates_str = "# unit tests\n" + fault_injection_unit_test_templates_str + "\n\n# fault_injections\n" + fault_injection_fault_templates_str
        write_file(fname=f"{intermediate_dir}/fault_injection_templates.j2", content=final_templates_str)
        # post-validation phase
        post_validation = experiment_plan["post_validation"]
        post_validation_templates_str = self.generate_unittest_templates_str(post_validation["unit_tests"])
        write_file(fname=f"{intermediate_dir}/post_validation_templates.j2", content=post_validation_templates_str)
        return templates
    
    def generate_unittest_templates_str(self, unit_tests: List[Dict[str, str]]) -> str:
        template_list = []
        for unittest in unit_tests:
            if os.path.splitext(unittest["file_path"])[1] == ".py":
                unittest_template = render_jinja_template(
                    TASK_TEMPLATE_PATH,
                    task_name=unittest["workflow_name"],
                    deadline=unittest["deadline"],
                    duration=parse_time(unittest["duration"]),
                    unittest_path=unittest["file_path"]
                )
            else:
                unittest_template = render_jinja_template(
                    TASK_K6_TEMPLATE_PATH,
                    task_name=unittest["workflow_name"],
                    deadline=unittest["deadline"],
                    duration=unittest["duration"],
                    unittest_path=unittest["file_path"]
                )
            template_list.append(unittest_template)
        templates_str = "\n\n".join(template_list)
        return templates_str

    def generate_fault_templates_str(self, fault_injections: List[Dict[str, str]]) -> str:
        template_list = []
        for fault_injection in fault_injections:
            specs_dict = fault_injection["params"]
            specs_str = yaml.dump(specs_dict, Dumper=IndentedDumper, default_flow_style=False)
            fault_template = render_jinja_template(
                FAULT_TEMPLATE_PATH,
                name=fault_injection["workflow_name"],
                FaultName=fault_injection["name"],
                deadline=fault_injection["duration"],
                faultName=self.to_lowercase_prefix_before_chaos(fault_injection["name"]),
                specs=specs_str
            )
            template_list.append(fault_template)
        templates_str = "\n\n".join(template_list)
        return templates_str

    def to_lowercase_prefix_before_chaos(self, fault_name: str) -> str:
        """supports only fault names of Chaos Mesh"""
        if not fault_name:
            assert False, "Fault name must be specified."
        return re.sub(r'(\w+)(Chaos)', lambda m: m.group(1).lower() + m.group(2), fault_name)