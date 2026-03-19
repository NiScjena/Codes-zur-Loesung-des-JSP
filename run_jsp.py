from __future__ import annotations

import argparse
import os
import sys

from jsp_solver import solve_from_jsplib


def pick_file_gui(initial_dir: str | None = None) -> str | None:
    """öffnet Datei-Auswahl (Tkinter), optional"""
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


def main() -> None:
    p = argparse.ArgumentParser(description="JSSP Gurobi Solver (optional Setupzeiten)")
    p.add_argument("-f", "--file", help="Pfad zur Instanzdatei (.txt)")
    p.add_argument("--time", type=float, default=60.0, help="Zeitlimit in Sekunden")
    p.add_argument("-v", "--visualize", action="store_true", help="Gantt anzeigen/speichern")
    p.add_argument("--verbose", action="store_true", help="Mehr Ausgabe")

    # Setupzeiten
    p.add_argument("--setup", action="store_true", help="Sequenzabhängige Setupzeiten aktivieren")
    p.add_argument("--setup-seed", type=int, default=None, help="Seed für Setupzeiten")
    p.add_argument("--max-setup", type=int, default=None, help="Max Setupzeit (Default: max processing time)")

    args = p.parse_args()

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
        with_setup=args.setup,
        setup_seed=args.setup_seed,
        max_setup=args.max_setup,
    )


if __name__ == "__main__":
    main()
