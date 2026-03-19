# jsp_solver.py
from __future__ import annotations

import collections
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from ortools.sat.python import cp_model


TaskKey = Tuple[int, int]  


@dataclass(frozen=True)
class TaskVars:
    start: cp_model.IntVar
    end: cp_model.IntVar
    interval: cp_model.IntervalVar
    machine: int
    duration: int


def _build_random_setup_times(
    jobs_count: int,
    machines_count: int,
    max_setup: int,
    seed: int = 42,
) -> List[List[List[int]]]:
    """
    setup_times[machine][job_from][job_to] in [0, max_setup]
    setup_times[m][j][j] = 0
    """
    rng = random.Random(seed)

    setup = [
        [[0 for _ in range(jobs_count)] for _ in range(jobs_count)]
        for _ in range(machines_count)
    ]

    for m in range(machines_count):
        for j_from in range(jobs_count):
            for j_to in range(jobs_count):
                if j_from == j_to:
                    setup[m][j_from][j_to] = 0
                else:
                    setup[m][j_from][j_to] = rng.randint(0, max_setup)

    return setup


def solve_jobshop(
    jobs_data: List[List[Tuple[int, int]]],
    *,
    use_setup_times: bool = False,
    setup_times: Optional[List[List[List[int]]]] = None,
    setup_seed: int = 42,
    time_limit: Optional[int] = None,
    threads: Optional[int] = None,
    verbose: bool = False,
) -> Dict:
    """
    jobs_data: list[job] where job = list[(machine, duration)]
    If use_setup_times=True and setup_times is None:
      -> generate random setup times in [0, max_duration_in_instance]
    """

    jobs_count = len(jobs_data)
    machines_count = 1 + max(task[0] for job in jobs_data for task in job)
    horizon = sum(task[1] for job in jobs_data for task in job)
    max_duration_in_instance = max(task[1] for job in jobs_data for task in job)

    if use_setup_times and setup_times is None:
        setup_times = _build_random_setup_times(
            jobs_count,
            machines_count,
            max_setup=max_duration_in_instance,
            seed=setup_seed,
        )

    model = cp_model.CpModel()

    all_tasks: Dict[TaskKey, TaskVars] = {}
    machine_to_tasks = collections.defaultdict(list)
    #Variablenerstellung
    for job_id, job in enumerate(jobs_data):
        for task_id, (machine, duration) in enumerate(job):
            start = model.new_int_var(0, horizon, f"s_{job_id}_{task_id}")
            end = model.new_int_var(0, horizon, f"e_{job_id}_{task_id}")
            interval = model.new_interval_var(start, duration, end, f"i_{job_id}_{task_id}")

            all_tasks[(job_id, task_id)] = TaskVars(
                start=start,
                end=end,
                interval=interval,
                machine=machine,
                duration=duration,
            )
            machine_to_tasks[machine].append((job_id, task_id))

    #falls keine setup zeiten genutzt werden sollen
    if not use_setup_times:
        for machine, tasks in machine_to_tasks.items():
            model.add_no_overlap([all_tasks[t].interval for t in tasks])
    else:
        assert setup_times is not None

        for machine, tasks in machine_to_tasks.items():
            for i in range(len(tasks)):
                for j in range(i + 1, len(tasks)):
                    a = tasks[i]
                    b = tasks[j]
                    a_job, _ = a
                    b_job, _ = b

                    a_before_b = model.new_bool_var(f"m{machine}_a{a}_before_b{b}")
                    model.add(
                        all_tasks[a].end + setup_times[machine][a_job][b_job]
                        <= all_tasks[b].start
                    ).only_enforce_if(a_before_b)
                    model.add(
                        all_tasks[b].end + setup_times[machine][b_job][a_job]
                        <= all_tasks[a].start
                    ).only_enforce_if(a_before_b.Not())


    for job_id, job in enumerate(jobs_data):
        for t in range(len(job) - 1):
            model.add(all_tasks[(job_id, t + 1)].start >= all_tasks[(job_id, t)].end)
#Gesamtzeit
    makespan = model.new_int_var(0, horizon, "makespan")
    model.add_max_equality(
        makespan,
        [all_tasks[(j, len(job) - 1)].end for j, job in enumerate(jobs_data)],
    )
    model.minimize(makespan)

    # Lösen
    solver = cp_model.CpSolver()
    if time_limit:
        solver.parameters.max_time_in_seconds = float(time_limit)
    if threads:
        solver.parameters.num_search_workers = int(threads)
    if verbose:
        solver.parameters.log_search_progress = True

    status = solver.solve(model)

    result = {
        "status": status,
        "objective": solver.objective_value if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "horizon": horizon,
        "jobs_count": jobs_count,
        "machines_count": machines_count,
        "max_duration_in_instance": max_duration_in_instance,
        "use_setup_times": use_setup_times,
        "setup_seed": setup_seed if use_setup_times and setup_times is None else None,
        "tasks": [
            {
                "job": j,
                "task": t,
                "machine": tv.machine,
                "start": solver.value(tv.start),
                "end": solver.value(tv.end),
            }
            for (j, t), tv in all_tasks.items()
        ],
    }

    return result
