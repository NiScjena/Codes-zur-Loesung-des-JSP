#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Job-Shop-Scheduling mit Gurobi.

Dieses Modul enthält Funktionen zum:
- Einlesen von JSPLIB-ähnlichen Instanzen
- Erzeugen zufälliger Setupzeiten
- Lösen des JSSP als MIP mit Gurobi
- Visualisieren der Lösung als Gantt-Chart

Autor: Niklas Schmitt
Datum: 20.03.2026
"""

from __future__ import annotations

import os
import random
from typing import Dict, List, Optional, Tuple

import gurobipy as gp
from gurobipy import GRB


def plot_gantt(
    schedule: Dict[int, List[Tuple[float, float, int, int]]],
    title: str = "JSSP Gurobi Gantt Chart",
    save_path: str = "gantt.png",
):
    """
    Erstellt ein Gantt-Diagramm für einen gegebenen Schedule.

    Args:
        schedule: Dictionary mit Maschinen-ID als Schlüssel und einer Liste von
            Tupeln (Startzeit, Endzeit, Job-ID, Operations-ID) als Wert.
        title: Titel des Diagramms.
        save_path: Pfad zum Speichern der Grafik.
    """
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt

    machines = sorted(schedule.keys())
    if not machines:
        print("Leere Gantt Chart")
        return

    # Alle Jobs sammeln, um konsistente Farben zuzuweisen
    all_jobs = sorted({j for m in schedule for (_, _, j, _) in schedule[m]})
    cmap = plt.get_cmap("tab20")
    job_color = {j: cmap(j % 20) for j in all_jobs}

    fig, ax = plt.subplots(figsize=(16, 8))

    # Balken je Maschine und Operation einzeichnen
    for m in machines:
        y = m
        for (st, et, j, o) in schedule[m]:
            ax.add_patch(
                patches.Rectangle(
                    (st, y - 0.4),
                    et - st,
                    0.8,
                    edgecolor="black",
                    facecolor=job_color[j],
                )
            )
            ax.text(
                st + (et - st) / 2,
                y,
                f"J{j + 1}-O{o + 1}",
                ha="center",
                va="center",
                fontsize=16,
            )

    max_t = (
        max(et for m in schedule for (_, et, _, _) in schedule[m])
        if schedule
        else 0
    )

    ax.set_xlim(0, max_t * 1.05 + 1)
    ax.set_ylim(-0.5, max(machines) + 0.5)
    ax.set_yticks(machines)
    ax.set_yticklabels([f"M{m + 1}" for m in machines], fontsize=16)
    ax.set_xlabel("Zeit", fontsize=18)
    ax.set_ylabel("Maschine", fontsize=18)
    ax.set_title(title, fontsize=18)
    ax.tick_params(axis="x", labelsize=16)

    plt.tight_layout()
    fig.savefig(save_path, dpi=200)
    print(f"Gantt gespeichert als: {save_path}")
    plt.show()


def read_jsplib_txt(path: str) -> Tuple[List[List[Tuple[int, int]]], int, int]:
    """
    Liest eine JSSP-Instanz aus einer Textdatei im JSPLIB-ähnlichen Format.

    Erwartetes Format:
        Erste Zeile: n_jobs n_machines
        Danach pro Job eine Zeile mit je 2 * n_machines Werten:
            machine_1 proc_time_1 machine_2 proc_time_2 ...

    Args:
        path: Pfad zur Eingabedatei.

    Returns:
        Tuple aus:
            - jobs: Liste aller Jobs mit Operationen als (Maschine, Bearbeitungszeit)
            - n_jobs: Anzahl der Jobs
            - n_machines: Anzahl der Maschinen
    """
    lines: List[str] = []

    # Datei einlesen, leere Zeilen und Kommentare überspringen
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(s)

    if not lines:
        raise ValueError("Datei enthält keine Datenzeilen")

    # Header auslesen
    header = list(map(int, lines[0].split()))
    if len(header) < 2:
        raise ValueError("Header muss n_jobs und n_machines enthalten")

    n_jobs, n_machines = header[0], header[1]

    if n_jobs <= 0 or n_machines <= 0:
        raise ValueError("n_jobs und n_machines müssen > 0 sein.")

    if len(lines) < 1 + n_jobs:
        raise ValueError(
            f"Erwarte {n_jobs} Jobzeilen nach Header, aber Datei hat nur "
            f"{len(lines) - 1}"
        )

    jobs: List[List[Tuple[int, int]]] = []
    all_m: List[int] = []

    # Jobdaten einlesen
    for j in range(n_jobs):
        parts = list(map(int, lines[1 + j].split()))
        if len(parts) != 2 * n_machines:
            raise ValueError(
                f"Job {j + 1}: {len(parts)} Werte, erwartet {2 * n_machines}."
            )

        ops: List[Tuple[int, int]] = []
        for o in range(n_machines):
            m = parts[2 * o]
            p = parts[2 * o + 1]

            if p <= 0:
                raise ValueError(
                    f"Job {j + 1}, Op {o + 1}: ptime muss > 0 sein"
                )

            ops.append((m, p))
            all_m.append(m)

        jobs.append(ops)

    # Prüfen, ob Maschinen 0-basiert oder 1-basiert indexiert sind
    mn, mx = min(all_m), max(all_m)
    if mn == 1 and mx == n_machines:
        jobs = [[(m - 1, p) for (m, p) in job] for job in jobs]
    elif mn == 0 and mx == n_machines - 1:
        pass
    else:
        raise ValueError(
            f"Maschinen-IDs passen nicht zum Header: min={mn}, max={mx}, "
            f"erwartet 0..{n_machines - 1} oder 1..{n_machines}."
        )

    return jobs, n_jobs, n_machines


def generate_setup_times(
    n_jobs: int,
    n_machines: int,
    jobs: List[List[Tuple[int, int]]],
    max_setup: Optional[int] = None,
    seed: Optional[int] = None,
    diagonal_zero: bool = True,
) -> List[List[List[int]]]:
    """
    Erzeugt zufällige Setupzeiten zwischen Jobwechseln auf jeder Maschine.

    setup[m][j_prev][j_next] liegt in [0, max_setup]

    Standard für max_setup (None):
        maximale Bearbeitungszeit einer Operation in der Instanz

    Args:
        n_jobs: Anzahl der Jobs.
        n_machines: Anzahl der Maschinen.
        jobs: Jobdefinitionen mit Operationen.
        max_setup: Obergrenze der Setupzeiten.
        seed: Zufallsseed für Reproduzierbarkeit.
        diagonal_zero: Falls True, werden setup[m][j][j] = 0 gesetzt.

    Returns:
        Dreidimensionale Liste der Setupzeiten.
    """
    if seed is not None:
        random.seed(seed)

    # Standardwert für max_setup bestimmen
    if max_setup is None:
        max_setup = 0
        for j in range(n_jobs):
            for o in range(len(jobs[j])):
                max_setup = max(max_setup, int(jobs[j][o][1]))

    # Setupzeiten zufällig generieren
    setup = [
        [
            [random.randint(0, max_setup) for _ in range(n_jobs)]
            for _ in range(n_jobs)
        ]
        for _ in range(n_machines)
    ]

    # Setup von Job zu sich selbst optional auf 0 setzen
    if diagonal_zero:
        for m in range(n_machines):
            for j in range(n_jobs):
                setup[m][j][j] = 0

    return setup


def solve_jssp_gurobi(
    jobs: List[List[Tuple[int, int]]],
    time_limit: float = 60.0,
    verbose: bool = True,
    with_setup: bool = False,
    setup_seed: Optional[int] = None,
    max_setup: Optional[int] = None,
) -> Optional[Tuple[float, Dict[int, List[Tuple[float, float, int, int]]]]]:
    """
    Löst ein Job-Shop-Scheduling-Problem mittels Gurobi-MIP-Modell.

    Args:
        jobs: Liste von Jobs mit Operationen als (Maschine, Bearbeitungszeit).
        time_limit: Maximale Laufzeit des Solvers in Sekunden.
        verbose: Aktiviert Solver-Ausgaben.
        with_setup: Berücksichtigt Setupzeiten zwischen Jobs.
        setup_seed: Seed für zufällige Setupzeiten.
        max_setup: Maximale Setupzeit.

    Returns:
        Tuple aus Makespan und Schedule je Maschine oder None, falls keine
        Lösung gefunden wurde.
    """
    n_jobs = len(jobs)
    n_ops = len(jobs[0])
    n_machines = 1 + max(m for job in jobs for (m, _) in job)

    # Horizont als grobe obere Schranke
    horizon = sum(pt for job in jobs for (_, pt) in job)
    setup = None

    if with_setup:
        setup = generate_setup_times(
            n_jobs=n_jobs,
            n_machines=n_machines,
            jobs=jobs,
            max_setup=max_setup,
            seed=setup_seed,
        )
        max_s = max(
            setup[m][a][b]
            for m in range(n_machines)
            for a in range(n_jobs)
            for b in range(n_jobs)
        )
        horizon = int(horizon + n_machines * (n_jobs - 1) * max_s)

    M = float(horizon + 1.0)

    # Modell initialisieren
    model = gp.Model("JSSP_MIP")
    model.Params.OutputFlag = 1 if verbose else 0
    model.Params.TimeLimit = float(time_limit)
    model.Params.MIPFocus = 1
    model.Params.Heuristics = 0.2

    # Startzeitvariablen für jede Operation
    S = {
        (j, o): model.addVar(lb=0.0, name=f"S_{j}_{o}")
        for j in range(n_jobs)
        for o in range(n_ops)
    }

    # Makespan-Variable
    Cmax = model.addVar(lb=0.0, name="Cmax")

    # Technologische Reihenfolge innerhalb eines Jobs
    for j in range(n_jobs):
        for o in range(n_ops - 1):
            pt = jobs[j][o][1]
            model.addConstr(
                S[(j, o + 1)] >= S[(j, o)] + pt,
                name=f"prec_{j}_{o}",
            )

    # Operationen pro Maschine sammeln
    ops_on_m: Dict[int, List[Tuple[int, int]]] = {
        m: [] for m in range(n_machines)
    }
    for j in range(n_jobs):
        for o in range(n_ops):
            m = jobs[j][o][0]
            ops_on_m[m].append((j, o))

    # Disjunktive Nebenbedingungen: keine Überlappung auf derselben Maschine
    for m, ops in ops_on_m.items():
        for a in range(len(ops)):
            j1, o1 = ops[a]
            p1 = jobs[j1][o1][1]

            for b in range(a + 1, len(ops)):
                j2, o2 = ops[b]
                p2 = jobs[j2][o2][1]

                y = model.addVar(
                    vtype=GRB.BINARY,
                    name=f"Y_{m}_{j1}_{o1}_{j2}_{o2}",
                )

                if setup is None:
                    s12 = 0
                    s21 = 0
                else:
                    s12 = setup[m][j1][j2]
                    s21 = setup[m][j2][j1]

                model.addConstr(
                    S[(j2, o2)] >= S[(j1, o1)] + p1 + s12 - M * (1 - y),
                    name=f"noov1_{m}_{j1}_{o1}_{j2}_{o2}",
                )
                model.addConstr(
                    S[(j1, o1)] >= S[(j2, o2)] + p2 + s21 - M * y,
                    name=f"noov2_{m}_{j1}_{o1}_{j2}_{o2}",
                )

    # Makespan an letzte Operation jedes Jobs koppeln
    for j in range(n_jobs):
        last = n_ops - 1
        model.addConstr(
            Cmax >= S[(j, last)] + jobs[j][last][1],
            name=f"cmax_{j}",
        )

    model.setObjective(Cmax, GRB.MINIMIZE)
    model.optimize()

    # Nur OPTIMAL oder TIME_LIMIT mit gefundener Lösung akzeptieren
    if model.Status not in (GRB.OPTIMAL, GRB.TIME_LIMIT):
        return None

    if model.SolCount == 0:
        if verbose:
            try:
                print(
                    f"Keine zulässige Lösung im TimeLimit, "
                    f"Bound {model.ObjBound:.4f}"
                )
            except Exception:
                print("Keine zulässige Lösung im TimeLimit")
        return None

    # Schedule aus der gefundenen Lösung extrahieren
    schedule: Dict[int, List[Tuple[float, float, int, int]]] = {
        m: [] for m in range(n_machines)
    }

    for j in range(n_jobs):
        for o in range(n_ops):
            st = float(S[(j, o)].X)
            m_id, pt = jobs[j][o]
            schedule[m_id].append((st, st + float(pt), j, o))

    for m_id in schedule:
        schedule[m_id].sort(key=lambda x: x[0])

    return float(Cmax.X), schedule


def solve_from_jsplib(
    path: str,
    time_limit: float = 60.0,
    visualize: bool = False,
    verbose: bool = True,
    with_setup: bool = False,
    setup_seed: Optional[int] = None,
    max_setup: Optional[int] = None,
):
    """
    Liest eine Instanz aus Datei ein und löst sie mit dem Gurobi-Solver.

    Args:
        path: Pfad zur Instanzdatei.
        time_limit: Maximale Solverlaufzeit.
        visualize: Falls True, wird ein Gantt-Chart erzeugt.
        verbose: Falls True, werden Informationen ausgegeben.
        with_setup: Falls True, werden Setupzeiten berücksichtigt.
        setup_seed: Seed für Setupzeitengenerierung.
        max_setup: Maximale Setupzeit.

    Returns:
        Tuple aus Makespan und Schedule oder None, falls keine Lösung gefunden
        wurde.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Datei nicht gefunden {path}")

    jobs, n_jobs, n_machines = read_jsplib_txt(path)

    if verbose:
        print(f"Instanz: {n_jobs} Jobs, {n_machines} Maschinen (Header)")
        print(f"Datei: {os.path.abspath(path)}")
        if with_setup:
            ms = "max(proc_time)" if max_setup is None else str(max_setup)
            print(f"Setup: aktiv, max_setup={ms}, seed={setup_seed}")

    res = solve_jssp_gurobi(
        jobs,
        time_limit=time_limit,
        verbose=verbose,
        with_setup=with_setup,
        setup_seed=setup_seed,
        max_setup=max_setup,
    )

    if res is None:
        if verbose:
            print("Keine Lösung gefunden")
        return None

    Cmax, schedule = res

    if verbose:
        print(f"\nMakespan: {Cmax:.2f}\n")

    if visualize:
        plot_gantt(
            schedule,
            title=f"JSSP Gurobi (Makespan={Cmax:.2f})",
            save_path="gantt.png",
        )

    return Cmax, schedule