CHAOS_ENGINEERING_DESCRIIPTION = """\
Chaos Engineering is an engineering technique aimed at improving the resiliency of distributed systems. It involves artificially injecting specific failures into a distributed system and observing its behavior in response. Based on the observation, the system can be proactively improved to handle those failures.
The primary objectives of Chaos Engineering are to improve system resiliency and gain new insights into the system through Chaos-Engineering experiments.
Systematically, Chaos Engineering cycles through four phases: hypothesis, experiment, analysis, and improvement phases.
  1) Hypothesis: Define steady states (i.e., normal behavior) of the system and injected failures (i.e., faults). Then, make a hypothesis that “the steady states are maintained in the system even when the failures are injected”.
  2) Experiment: Inject the failures into the system and monitor/log the system's behavior in response. 
  3) Analysis: Analyze the logged data and check if the hypothesis is satisfied. If so, one CE cycle is finished here. If not, move to (4)
  4) Improvement: Reconfigure the system to satisfy the hypothesis. The reconfigured system is tested again in (2) and (3), i.e., repeat (2) to (4) until the hypothesis is satisfied."""