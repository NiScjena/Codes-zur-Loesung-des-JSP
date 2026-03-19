from __future__ import annotations

import argparse
import os
import sys

from jsp_solver import solve_from_jsplib


def pick_file_gui(initial_dir: str | None = None) -> str | None:
    """öffnet Datei-Auswahl (Tkinter)"""
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
    s = raw.strip().lower()
    if s in {"", "none", "null", "nolimit", "unlimited"}:
        return None
    t = int(s)
    return t if t > 0 else None


def main() -> None:
    p = argparse.ArgumentParser(description="Aktiviert JSSP Solver mit .txt Datei (optional Setupzeiten).")
    p.add_argument("-f", "--file", help="Pfad zur .txt Datei")
    p.add_argument(
        "-t",
        "--time",
        type=time_limit_arg,
        default=None,
        help="Zeitlimit in Sekunden (0/None = kein Limit).",
    )
    p.add_argument("-v", "--visualize", action="store_true", help="Gantt-Chart anzeigen")
    p.add_argument("--verbose", action="store_true", help="Zusätzliche Ausgaben")
    p.add_argument("--threads", type=int, default=None, help="Anzahl Threads")

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
        threads=args.threads,
        with_setup=args.setup,
        setup_seed=args.setup_seed,
        max_setup=args.max_setup,
    )


if __name__ == "__main__":
    main()
