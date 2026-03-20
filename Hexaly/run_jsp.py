#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ausführungsskript für den JSP-Hexaly-Solver.

Diese Datei dient zum:
- Einlesen von Kommandozeilenargumenten
- Optionalen Auswählen einer Instanzdatei über einen Dateidialog
- Übergeben der Parameter an den Hexaly-Solver
- Starten der Berechnung und optionalen Visualisierung

Autor: Niklas Schmitt
Datum: 20.03.2026
"""

from __future__ import annotations

import argparse
import os
import sys

from jsp_solver import solve_from_jsplib


def pick_file_gui(initial_dir: str | None = None) -> str | None:
    """Öffnet einen Datei-Dialog zur Auswahl einer Instanzdatei."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        # Falls Tkinter nicht verfügbar ist, kann keine GUI-Auswahl erfolgen.
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    path = filedialog.askopenfilename(
        title="Instanz auswählen",
        initialdir=initial_dir or os.getcwd(),
        filetypes=[
            ("Text files", "*.txt"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return path or None


def time_limit_arg(raw: str) -> int | None:
    """Wandelt das Zeitlimit-Argument in Sekunden oder None um."""
    s = raw.strip().lower()

    # Diese Eingaben bedeuten: kein Zeitlimit.
    if s in {"", "none", "null", "nolimit", "unlimited"}:
        return None

    t = int(s)

    # Nur positive Werte gelten als Zeitlimit.
    return t if t > 0 else None


def main() -> None:
    """Parst Kommandozeilenargumente und startet den Solver."""
    p = argparse.ArgumentParser(
        description=(
            "Aktiviert JSSP Solver mit .txt Datei "
            "(optional Setupzeiten)."
        )
    )
    p.add_argument(
        "-f",
        "--file",
        help="Pfad zur .txt Datei",
    )
    p.add_argument(
        "-t",
        "--time",
        type=time_limit_arg,
        default=None,
        help="Zeitlimit in Sekunden (0/None = kein Limit).",
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
        help="Zusätzliche Ausgaben",
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
        help="Sequenzabhängige Setupzeiten aktivieren",
    )
    p.add_argument(
        "--setup-seed",
        type=int,
        default=None,
        help="Seed für Setupzeiten",
    )
    p.add_argument(
        "--max-setup",
        type=int,
        default=None,
        help="Max Setupzeit (Default: max processing time)",
    )

    args = p.parse_args()

    # Entweder Dateipfad aus Argument übernehmen oder per GUI auswählen.
    path = args.file or pick_file_gui()

    if not path:
        print("Keine Datei ausgewählt.")
        sys.exit(1)

    if not os.path.isfile(path):
        print(f"Datei nicht gefunden: {path}")
        sys.exit(1)

    solve_from_jsplib(
        path=path,
        time_limit=args.time,
        visualize=args.visualize,
        verbose=args.verbose,
        threads=args.threads,
        with_setup=args.setup,
        setup_seed=args.setup_seed,
        max_setup=args.max_setup,
    )


if __name__ == "__main__":
    main()
