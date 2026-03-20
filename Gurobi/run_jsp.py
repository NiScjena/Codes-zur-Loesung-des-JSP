#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Startskript für den JSSP-Gurobi-Solver.

Diese Datei dient zum:
- Einlesen von Kommandozeilenargumenten
- Optionalen Auswählen einer Instanzdatei über einen Dateidialog
- Übergeben der Parameter an den Solver
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
    """Öffnet optional einen Datei-Dialog per Tkinter.

    Gibt den ausgewählten Dateipfad zurück oder None,
    falls Tkinter nicht verfügbar ist oder keine Datei gewählt wurde.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None

    # Unsichtbares Tk-Hauptfenster erzeugen.
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # Datei-Auswahldialog öffnen.
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


def main() -> None:
    """Parst Argumente, lädt eine Instanzdatei und startet den Solver."""
    p = argparse.ArgumentParser(
        description="JSSP Gurobi Solver (optional Setupzeiten)"
    )
    p.add_argument(
        "-f",
        "--file",
        help="Pfad zur Instanzdatei (.txt)",
    )
    p.add_argument(
        "--time",
        type=float,
        default=60.0,
        help="Zeitlimit in Sekunden",
    )
    p.add_argument(
        "-v",
        "--visualize",
        action="store_true",
        help="Gantt anzeigen/speichern",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Mehr Ausgabe",
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

    # Entweder Pfad aus Argumenten oder Auswahl über GUI.
    path = args.file or pick_file_gui()

    if not path:
        print("Keine Datei ausgewählt.")
        sys.exit(1)

    if not os.path.isfile(path):
        print(f"Datei nicht gefunden: {path}")
        sys.exit(1)

    # Solver mit den übergebenen Parametern starten.
    solve_from_jsplib(
        path=path,
        time_limit=args.time,
        visualize=args.visualize,
        verbose=args.verbose,
        with_setup=args.setup,
        setup_seed=args.setup_seed,
        max_setup=args.max_setup,
    )


if __name__ == "__main__":
    main()
