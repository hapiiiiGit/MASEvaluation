from .solo_programmer import build_solo_programmer_graph
from .planner_programmer import build_planner_programmer_graph
from .programmer_reviewer import build_programmer_reviewer_graph
from .programmer_tester import build_programmer_tester_graph
from .plan_programmer_reviewer import build_plan_programmer_reviewer_graph
from .plan_programmer_tester import build_plan_programmer_tester_graph
from .planner_architect_programmer import build_planner_architect_programmer_graph
from .planner_architect_programmer_reviewer import build_planner_architect_programmer_reviewer_graph
from .planner_architect_programmer_reviewer_tester import build_planner_architect_programmer_reviewer_tester_graph

GRAPH_REGISTRY = {
    "solo_programmer": build_solo_programmer_graph,
    "planner_programmer": build_planner_programmer_graph,
    "programmer_reviewer": build_programmer_reviewer_graph,
    "programmer_tester": build_programmer_tester_graph,
    "plan_programmer_reviewer": build_plan_programmer_reviewer_graph,
    "plan_programmer_tester": build_plan_programmer_tester_graph,
    "planner_architect_programmer": build_planner_architect_programmer_graph,
    "planner_architect_programmer_reviewer": build_planner_architect_programmer_reviewer_graph,
    "planner_architect_programmer_reviewer_tester": build_planner_architect_programmer_reviewer_tester_graph,
}