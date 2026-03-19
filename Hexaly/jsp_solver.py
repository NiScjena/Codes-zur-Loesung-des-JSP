from __future__ import annotations

from typing import Optional, Dict, List, Tuple
import random

import hexaly.optimizer


def _read_all_ints(path: str) -> List[int]:
    """Liest alle ints der Datei"""
    ints: List[int] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            for tok in s.replace(",", " ").split():
                try:
                    ints.append(int(tok))
                except ValueError:
                    pass
    return ints


def read_abz_ft_la_pairs(path: str) -> Tuple[int, int, List[List[int]], List[List[int]], int]:
    """
    Erwartet ABZ/FT/LA-Paare:
    - erste zwei ints: nb_jobs nb_machines
    - danach nb_jobs * nb_machines Paare (machine_id, processing_time)
    """
    data = _read_all_ints(path)
    if len(data) < 2:
        raise ValueError("zu wenig Daten")

    nb_jobs, nb_machines = data[0], data[1]
    need = 2 + nb_jobs * (2 * nb_machines)
    if len(data) < need:
        raise ValueError(f"zu wenig Integers. Erwartet >= {need}, gefunden {len(data)}.")

    idx = 2
    jobs_ops: List[List[Tuple[int, int]]] = []
    all_m: List[int] = []

    for _j in range(nb_jobs):
        ops: List[Tuple[int, int]] = []
        for _o in range(nb_machines):
            m = data[idx]
            p = data[idx + 1]
            idx += 2
            if p <= 0:
                raise ValueError("processing time muss > 0 sein")
            ops.append((m, p))
            all_m.append(m)
        jobs_ops.append(ops)

    mn, mx = min(all_m), max(all_m)
    if mn == 1 and mx == nb_machines:
        jobs_ops = [[(m - 1, p) for (m, p) in job] for job in jobs_ops]

    machine_order: List[List[int]] = []
    processing_time: List[List[int]] = [[0] * nb_machines for _ in range(nb_jobs)]

    for j, ops in enumerate(jobs_ops):
        order = []
        for (m, p) in ops:
            if not (0 <= m < nb_machines):
                raise ValueError(f"machine id {m} außerhalb 0..{nb_machines-1}")
            order.append(m)
            processing_time[j][m] = int(p)
        machine_order.append(order)

    max_end = sum(sum(processing_time[j]) for j in range(nb_jobs))
    return nb_jobs, nb_machines, processing_time, machine_order, max_end


def read_taillard_instance(path: str) -> Tuple[int, int, List[List[int]], List[List[int]], int]:
    """
    Taillard/JSP-lib Format (dein Code: lines[1] usw.)
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines() if ln.strip()]

    first_line = lines[1].split()
    nb_jobs = int(first_line[0])
    nb_machines = int(first_line[1])

    pt_start = 3
    pt_end = pt_start + nb_jobs

    processing_times_in_processing_order = [
        [int(lines[i].split()[j]) for j in range(nb_machines)]
        for i in range(pt_start, pt_end)
    ]

    mo_start = 4 + nb_jobs
    mo_end = mo_start + nb_jobs

    machine_order = [
        [int(lines[i].split()[j]) - 1 for j in range(nb_machines)]
        for i in range(mo_start, mo_end)
    ]

    processing_time = [
        [processing_times_in_processing_order[j][machine_order[j].index(m)] for m in range(nb_machines)]
        for j in range(nb_jobs)
    ]

    max_end = sum(sum(processing_time[j]) for j in range(nb_jobs))
    return nb_jobs, nb_machines, processing_time, machine_order, max_end


def read_instance_auto(path: str) -> Tuple[int, int, List[List[int]], List[List[int]], int]:
    try:
        return read_abz_ft_la_pairs(path)
    except Exception:
        pass
    return read_taillard_instance(path)


def generate_setup_times(
    nb_jobs: int,
    nb_machines: int,
    processing_time: List[List[int]],
    max_setup: Optional[int] = None,
    seed: Optional[int] = None,
    diagonal_zero: bool = True,
) -> List[List[List[int]]]:
    """
    Erzeugt sequenzabhängige Setupzeiten pro Maschine:
      setup_time[m][j_prev][j_next] in [0, max_setup]

    max_setup:
      - None => max(processing_time[j][m]) über alle j,m
    """
    if seed is not None:
        random.seed(seed)

    if max_setup is None:
        max_setup = 0
        for j in range(nb_jobs):
            for m in range(nb_machines):
                max_setup = max(max_setup, int(processing_time[j][m]))

    setup_time = [
        [[random.randint(0, max_setup) for _jn in range(nb_jobs)] for _jp in range(nb_jobs)]
        for _m in range(nb_machines)
    ]

    if diagonal_zero:
        for m in range(nb_machines):
            for j in range(nb_jobs):
                setup_time[m][j][j] = 0

    return setup_time


def solve_hexaly_code2_model(
    nb_jobs: int,
    nb_machines: int,
    processing_time: List[List[int]],
    machine_order: List[List[int]],
    max_end: int,
    time_limit: Optional[int] = None,
    threads: Optional[int] = None,
    setup_time: Optional[List[List[List[int]]]] = None,
) -> Tuple[float, Dict[int, List[Tuple[float, float, int, int]]]]:
    """
    JSSP mit Hexaly:
    - tasks[j][m] Intervalle
    - Job-Reihenfolge via machine_order
    - Maschinen: list(nb_jobs) mit Sequenz-Constraints
    - optional sequenzabhängige Setupzeiten zwischen Jobs auf Maschine m
    """

    #setup zeiten maximum
    if setup_time is not None:
        max_setup = max(
            setup_time[m][j1][j2]
            for m in range(nb_machines)
            for j1 in range(nb_jobs)
            for j2 in range(nb_jobs)
        )
        max_end = int(max_end + nb_machines * (nb_jobs - 1) * max_setup)

    with hexaly.optimizer.HexalyOptimizer() as optimizer:
        if threads and int(threads) > 0:
            optimizer.param.nb_threads = int(threads)

        model = optimizer.model
        tasks = [[model.interval(0, max_end) for m in range(nb_machines)] for j in range(nb_jobs)]
        for j in range(nb_jobs):
            for m in range(nb_machines):
                model.constraint(model.length(tasks[j][m]) == int(processing_time[j][m]))

        task_array = model.array(tasks)
        for j in range(nb_jobs):
            for k in range(nb_machines - 1):
                m1 = machine_order[j][k]
                m2 = machine_order[j][k + 1]
                model.constraint(model.start(model.at(task_array, j, m2)) >= model.end(model.at(task_array, j, m1)))
        jobs_order = [model.list(nb_jobs) for _ in range(nb_machines)]
        setup_arr = model.array(setup_time) if setup_time is not None else None

        for m in range(nb_machines):
            seq = jobs_order[m]
            model.constraint(model.eq(model.count(seq), nb_jobs))

            if setup_arr is None:
                seq_lambda = model.lambda_function(
                    lambda i: model.start(model.at(task_array, seq[i + 1], m))
                    >= model.end(model.at(task_array, seq[i], m))
                )
            else:
                seq_lambda = model.lambda_function(
                    lambda i: model.start(model.at(task_array, seq[i + 1], m))
                    >= model.end(model.at(task_array, seq[i], m))
                    + model.at(setup_arr, m, seq[i], seq[i + 1])
                )

            model.constraint(model.and_(model.range(0, nb_jobs - 1), seq_lambda))

        # Gesamtzeit
        makespan_expr = model.max([
            model.end(tasks[j][machine_order[j][nb_machines - 1]])
            for j in range(nb_jobs)
        ])
        model.minimize(makespan_expr)

        model.close()

        if time_limit and int(time_limit) > 0:
            optimizer.param.time_limit = int(time_limit)

        optimizer.solve()

        cmax = float(makespan_expr.value)

        schedule: Dict[int, List[Tuple[float, float, int, int]]] = {m: [] for m in range(nb_machines)}
        for j in range(nb_jobs):
            for m in range(nb_machines):
                iv = tasks[j][m].value
                schedule[m].append((float(iv.start()), float(iv.end()), j, m))

        for m in schedule:
            schedule[m].sort(key=lambda x: x[0])

        return cmax, schedule

#erstellung des Gantcharts
def plot_gantt(
    schedule: Dict[int, List[Tuple[float, float, int, int]]],
    title: str = "JSSP Gantt",
    save_path: Optional[str] = None,
) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    machines = sorted(schedule)
    if not machines:
        return

    jobs = sorted({j for mach in schedule for (_, _, j, _) in schedule[mach]})
    cmap = plt.get_cmap("tab20")
    color = {j: cmap(j % 20) for j in jobs}

    fig, ax = plt.subplots(figsize=(16, 8))
    for mach in machines:
        y = mach
        for st, et, j, m in schedule[mach]:
            ax.add_patch(
                patches.Rectangle(
                    (st, y - 0.4),
                    et - st,
                    0.8,
                    edgecolor="black",
                    facecolor=color[j],
                )
            )
            ax.text(st + (et - st) / 2, y, f"J{j+1}-O{m+1}", ha="center", va="center", fontsize=16)

    max_t = max(et for mach in schedule for (_, et, _, _) in schedule[mach]) if schedule else 0
    ax.set_xlim(0, max_t * 1.05 + 1)
    ax.set_ylim(-0.5, max(machines) + 0.5)
    ax.set_yticks(machines)
    ax.set_yticklabels([f"M{m+1}" for m in machines],fontsize=16)
    ax.set_xlabel("Zeit", fontsize=18)
    ax.set_ylabel("Maschine", fontsize=18)
    ax.tick_params(axis="x", labelsize=16)
    ax.set_title(title,fontsize=18)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=200)
    plt.show()


def solve_from_jsplib(
    path: str,
    time_limit: Optional[int] = None,
    visualize: bool = False,
    verbose: bool = False,
    threads: Optional[int] = None,
    with_setup: bool = False,
    setup_seed: Optional[int] = None,
    max_setup: Optional[int] = None,
) -> Tuple[float, Dict[int, List[Tuple[float, float, int, int]]]]:
    nb_jobs, nb_machines, processing_time, machine_order, max_end = read_instance_auto(path)

    setup_time = None
    if with_setup:
        setup_time = generate_setup_times(
            nb_jobs=nb_jobs,
            nb_machines=nb_machines,
            processing_time=processing_time,
            max_setup=max_setup,   
            seed=setup_seed,
        )

    cmax, schedule = solve_hexaly_code2_model(
        nb_jobs=nb_jobs,
        nb_machines=nb_machines,
        processing_time=processing_time,
        machine_order=machine_order,
        max_end=max_end,
        time_limit=time_limit,
        threads=threads,
        setup_time=setup_time,
    )

    print(f"\nMakespan: {cmax:.2f}\n")

    if verbose:
        for mach, ops in schedule.items():
            print(f"Maschine M{mach}:")
            for st, et, j, m in ops:
                print(f"  Job {j+1} auf M{m}: {st:.2f} -> {et:.2f}")

    if visualize:
        plot_gantt(schedule, title=f"JSSP Hexaly (Makespan={cmax:.2f})", save_path="gantt.png")

    return cmax, schedule
