from __future__ import annotations

import operator
from typing import Optional
from typing_extensions import Annotated, TypedDict


class AgentMetric(TypedDict, total=False):


    agent: str                
    model: str               
    run_name: str             
    call_index: int          

    input_tokens: int
    output_tokens: int
    total_tokens: int
    wall_time_s: float      

    success: bool
    error: str


class InputState(TypedDict):


    task_id: str
    task: str


class WorkState(TypedDict, total=False):


    plans: list[str]
    architectures: list[str]
    codes: list[str]
    reviews: list[str]
    test_cases: list[str]
    final_code: Optional[str]
    iteration: int

    reviewer_iteration: int

    tester_iteration: int

    max_reviewer_iterations: int  
    max_tester_iterations: int    

    need_revision: bool
    programmer_mode: str       


class MonitorState(TypedDict, total=False):

    metrics: Annotated[list[AgentMetric], operator.add]


class OutputState(TypedDict, total=False):

    final_code: str
    metrics: list[AgentMetric]
    success: bool
    error: str


class CodeGenState(InputState, WorkState, MonitorState, total=False):

    success: bool
    error: str
