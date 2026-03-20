#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ausführungsskript für den JSP-OR-Tools-Solver.

Dieses Modul enthält:
- die Kommandozeilensteuerung des Programms,
- eine optionale Dateiauswahl per Tkinter,
- das Einlesen von SWV-Instanzdateien,
- die Übergabe von Laufzeit-, Thread- und Setup-Parametern,
- den Aufruf von ``solve_jobshop()``,
- sowie die optionale Visualisierung des berechneten Schedules
  als Gantt-Diagramm.

Autor: Niklas Schmitt
Datum: 20.03.2026
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from jsp_solver import solve_jobshop


def pick_file_gui(initial_dir: str | None = None) -> str | None:
    """Öffnet einen Datei-Dialog zur Auswahl einer Instanzdatei."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    path = filedialog.askopenfilename(
        title="Instanz auswählen",
        initialdir=initial_dir or os.getcwd(),
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
    )
    root.destroy()
    return path or None


def time_limit_arg(raw: str) -> int | None:
    """Wandelt das Zeitlimit aus der CLI in int oder None um."""
    s = raw.strip().lower()
    if s in {"", "none", "null", "nolimit", "unlimited"}:
        return None

    t = int(s)
    return t if t > 0 else None


def read_swv_instance(path: str):
    """Liest eine SWV-Instanzdatei ein und gibt jobs_data zurück."""
    tokens = []

    # Datei zeilenweise lesen, Kommentare und Leerzeilen ignorieren
    for line in Path(path).read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        for x in line.split():
            tokens.append(int(x))

    # Erste zwei Werte: Anzahl Jobs und Maschinen
    jobs, machines = tokens[0], tokens[1]
    idx = 2

    jobs_data = []

    # Für jeden Job werden Maschinen-/Zeit-Paare eingelesen
    for _ in range(jobs):
        job = []
        for _ in range(machines):
            m = tokens[idx]
            t = tokens[idx + 1]
            idx += 2
            job.append((m, t))
        jobs_data.append(job)

    return jobs_data


def plot_gantt(result: dict, title: str = "Job Shop Schedule (Gantt)") -> None:
    """Erzeugt ein Gantt-Diagramm für das berechnete Job-Shop-Schedule."""
    import matplotlib.pyplot as plt

    if result.get("objective") is None:
        print("Keine Lösung zum Plotten vorhanden.")
        return

    tasks = result["tasks"]
    machines = sorted({t["machine"] for t in tasks})
    jobs = sorted({t["job"] for t in tasks})

    # Farbzuordnung pro Job
    cmap = plt.get_cmap("tab20")
    job_to_color = {job: cmap(job % 20) for job in jobs}

    # Aufgaben nach Maschinen gruppieren
    by_machine = {m: [] for m in machines}
    for task in tasks:
        by_machine[task["machine"]].append(task)

    for machine in machines:
        by_machine[machine].sort(key=lambda x: x["start"])

    fig, ax = plt.subplots(figsize=(16, 8))

    ax.set_title(
        f"JSSP Google OR-Tools (Makespan={result['objective']:.2f})",
        fontsize=18,
    )
    ax.set_xlabel("Zeit", fontsize=18)
    ax.set_ylabel("Maschine", fontsize=18)

    y_ticks = []
    y_labels = []
    bar_height = 0.8

    # Balken pro Maschine und Operation zeichnen
    for idx, machine in enumerate(machines):
        y_ticks.append(idx)
        y_labels.append(f"M{machine}")

        for task in by_machine[machine]:
            start = task["start"]
            duration = task["end"] - task["start"]
            color = job_to_color[task["job"]]

            ax.barh(
                idx,
                duration,
                left=start,
                height=bar_height,
                color=color,
                edgecolor="black",
                linewidth=1.5,
            )

            label = f"J{task['job'] + 1}-O{task['task'] + 1}"
            ax.text(
                start + duration / 2,
                idx,
                label,
                va="center",
                ha="center",
                fontsize=16,
                color="black",
                clip_on=True,
            )

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=16)
    ax.tick_params(axis="x", labelsize=16)
    ax.tick_params(axis="y", labelsize=16)

    plt.tight_layout()
    plt.show()


def main() -> None:
    """Parst CLI-Argumente, löst die Instanz und zeigt optional ein Gantt an."""
    p = argparse.ArgumentParser(
        description="OR-Tools Job-Shop Solver "
        "(mit optionalen Setupzeiten)"
    )
    p.add_argument("-f", "--file", help="Pfad zur .txt Datei")
    p.add_argument(
        "-t",
        "--time",
        type=time_limit_arg,
        default=None,
        help="Zeitlimit in Sekunden (0/None = kein Limit)",
    )
    p.add_argument(
        "-v",
        "--visualize",
        action="store_true",
        help="Gantt-Chart anzeigen",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Solver-Log anzeigen",
    )
    p.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Anzahl Threads",
    )

    # Setupzeiten
    p.add_argument(
        "--setup",
        action="store_true",
        help="Setupzeiten aktivieren",
    )
    p.add_argument(
        "--setup-seed",
        type=int,
        default=42,
        help="Seed für zufällige Setupzeiten "
        "(nur relevant mit --setup)",
    )

    args = p.parse_args()

    # Dateipfad aus Argument oder GUI beziehen
    path = args.file or pick_file_gui()
    if not path:
        print("Keine Datei ausgewählt.")
        sys.exit(1)

    if not os.path.isfile(path):
        print(f"Datei nicht gefunden: {path}")
        sys.exit(1)

    # Instanz einlesen
    jobs_data = read_swv_instance(path)

    # Solver aufrufen
    result = solve_jobshop(
        jobs_data,
        use_setup_times=args.setup,
        setup_seed=args.setup_seed,
        time_limit=args.time,
        threads=args.threads,
        verbose=args.verbose,
    )

    # Ergebnisse ausgeben
    print("\nMakespan:", result["objective"])
    if result.get("max_duration_in_instance") is not None:
        print("Max Dauer (Instanz):", result["max_duration_in_instance"])

    print("Setupzeiten:", "AN" if args.setup else "AUS")
    if args.setup:
        print("Setup-Seed:", args.setup_seed)

    # Optionales Gantt-Diagramm anzeigen
    if args.visualize:
        plot_gantt(result, title=os.path.basename(path))


if __name__ == "__main__":
    main()
