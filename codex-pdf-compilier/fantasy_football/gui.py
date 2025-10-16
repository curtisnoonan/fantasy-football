from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .config import Config, load_config
from .espn_client import get_league
from .exporters import export_free_agents, export_matchups, export_player_stats, export_rosters, export_standings
from .logging_config import setup_logging

# Ensure analyze_players.py importable
try:
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except Exception:
    pass

try:
    from analyze_players import (
        load_rosters as ap_load_rosters,
        load_player_games as ap_load_player_games,
        compute_metrics as ap_compute_metrics,
        tag_categories as ap_tag_categories,
        load_player_positions as ap_load_player_positions,
    )
except Exception:
    ap_load_rosters = None  # type: ignore
    ap_load_player_games = None  # type: ignore
    ap_compute_metrics = None  # type: ignore
    ap_tag_categories = None  # type: ignore
    ap_load_player_positions = None  # type: ignore


class ConfigGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Fantasy Football Config")
        self.geometry("600x420")
        self.resizable(False, False)

        self.yaml_path = tk.StringVar(value="config.yaml")
        self.env_path = tk.StringVar(value=".env")
        self.league_id = tk.StringVar()
        self.season = tk.StringVar()
        self.week = tk.StringVar()
        self.espn_s2 = tk.StringVar()
        self.swid = tk.StringVar()
        self.output_dir = tk.StringVar(value="data/exports")
        self.log_dir = tk.StringVar(value="logs")
        self.log_level = tk.StringVar(value="INFO")

        self._last_paths: Dict[str, Optional[str]] = {
            "rosters": None,
            "player_stats": None,
            "standings": None,
            "matchups": None,
            "free_agents": None,
        }

        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}
        row = 0
        ttk.Label(self, text="YAML Config").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.yaml_path, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_yaml).grid(row=row, column=2, **pad)
        row += 1
        ttk.Label(self, text=".env File").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.env_path, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_env).grid(row=row, column=2, **pad)
        row += 1
        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=8)
        row += 1
        ttk.Label(self, text="League ID").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.league_id, width=22).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Season").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.season, width=22).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Week (for matchups)").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.week, width=22).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="ESPN_S2").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.espn_s2, width=44).grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="SWID").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.swid, width=44).grid(row=row, column=1, columnspan=2, sticky="w", **pad)
        row += 1
        ttk.Label(self, text="Output Dir").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.output_dir, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_output).grid(row=row, column=2, **pad)
        row += 1
        ttk.Label(self, text="Log Dir").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(self, textvariable=self.log_dir, width=44).grid(row=row, column=1, **pad)
        ttk.Button(self, text="Browse", command=self._browse_logdir).grid(row=row, column=2, **pad)
        row += 1
        ttk.Label(self, text="Log Level").grid(row=row, column=0, sticky="e", **pad)
        cb = ttk.Combobox(self, textvariable=self.log_level, values=["DEBUG", "INFO", "WARNING", "ERROR"], width=20, state="readonly")
        cb.grid(row=row, column=1, sticky="w", **pad)
        row += 1
        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", padx=10, pady=8)
        row += 1
        btns = ttk.Frame(self)
        btns.grid(row=row, column=0, columnspan=3, pady=8)
        ttk.Button(btns, text="Reload", command=self._load_current).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text="Export CSV (All)", command=self._export_all_bg).grid(row=0, column=1, padx=6)
        ttk.Button(btns, text="Analyze Players", command=self._analyze_players_bg).grid(row=0, column=2, padx=6)
        ttk.Button(btns, text="Close", command=self.destroy).grid(row=0, column=3, padx=6)
        row += 1
        status = ttk.Frame(self)
        status.grid(row=row, column=0, columnspan=3, sticky="ew", padx=10)
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(status, textvariable=self._status_var, anchor="w").grid(row=0, column=0, sticky="w")
        self._progress = ttk.Progressbar(status, mode="determinate", maximum=4, value=0)
        self._progress.grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _browse_yaml(self) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".yaml", filetypes=[("YAML", "*.yaml;*.yml"), ("All", "*.*")], initialfile=self.yaml_path.get())
        if p:
            self.yaml_path.set(p)

    def _browse_env(self) -> None:
        p = filedialog.asksaveasfilename(defaultextension=".env", filetypes=[("Env", "*.env"), ("All", "*.*")], initialfile=self.env_path.get())
        if p:
            self.env_path.set(p)

    def _browse_output(self) -> None:
        p = filedialog.askdirectory(initialdir=self.output_dir.get() or os.getcwd())
        if p:
            self.output_dir.set(p)

    def _browse_logdir(self) -> None:
        p = filedialog.askdirectory(initialdir=self.log_dir.get() or os.getcwd())
        if p:
            self.log_dir.set(p)

    def _load_current(self) -> None:
        try:
            cfg = load_config(config_path=self.yaml_path.get(), dotenv_path=self.env_path.get())
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load config: {e}")
            return
        self.league_id.set(str(cfg.league_id or ""))
        self.season.set(str(cfg.season or ""))
        if cfg.espn_s2:
            self.espn_s2.set(cfg.espn_s2)
        if cfg.swid:
            self.swid.set(cfg.swid)
        self.output_dir.set(cfg.output_dir or "data/exports")
        self.log_dir.set(cfg.log_dir or "logs")
        self.log_level.set((cfg.log_level or "INFO").upper())

    def _collect_values(self) -> Dict[str, Any]:
        vals: Dict[str, Any] = {}
        if (lid := self.league_id.get().strip()):
            if not lid.isdigit():
                raise ValueError("League ID must be an integer")
            vals["LEAGUE_ID"] = int(lid)
        if (season := self.season.get().strip()):
            if not season.isdigit():
                raise ValueError("Season must be an integer")
            vals["SEASON"] = int(season)
        vals["ESPN_S2"] = self.espn_s2.get().strip() or None
        vals["SWID"] = self.swid.get().strip() or None
        vals["OUTPUT_DIR"] = self.output_dir.get().strip() or "data/exports"
        vals["LOG_DIR"] = self.log_dir.get().strip() or "logs"
        vals["LOG_LEVEL"] = (self.log_level.get().strip() or "INFO").upper()
        return vals

    def _export_all_bg(self) -> None:
        try:
            vals = self._collect_values()
            if "LEAGUE_ID" not in vals or "SEASON" not in vals:
                messagebox.showerror("Export Error", "League ID and Season are required to export")
                return
            cfg = Config(
                league_id=vals.get("LEAGUE_ID"),
                season=vals.get("SEASON"),
                espn_s2=vals.get("ESPN_S2"),
                swid=vals.get("SWID"),
                output_dir=vals.get("OUTPUT_DIR", "data/exports"),
                log_dir=vals.get("LOG_DIR", "logs"),
                log_level=vals.get("LOG_LEVEL", "INFO"),
            )
            setup_logging(cfg.log_dir, cfg.log_level)

            week_str = self.week.get().strip()
            week_val = int(week_str) if week_str.isdigit() else None

            def worker() -> None:
                try:
                    self.after(0, lambda: self._status_var.set("Connecting to league..."))
                    league = get_league(cfg)
                    if week_val is None:
                        cw = getattr(league, "current_week", None)
                        if cw is not None:
                            week = int(cw)
                            self.after(0, lambda: self.week.set(str(week)))
                            week_val_local = week
                        else:
                            week_val_local = None
                    else:
                        week_val_local = week_val

                    self.after(0, lambda: self._progress_start(4 + (1 if week_val_local is not None else 0)))
                    self.after(0, lambda: self._progress_step("Exporting rosters..."))
                    r_path = export_rosters(league, cfg.output_dir, cfg.season or 0)
                    self._last_paths["rosters"] = r_path
                    self.after(0, lambda: self._progress_step("Exporting standings..."))
                    s_path = export_standings(league, cfg.output_dir, cfg.season or 0)
                    self._last_paths["standings"] = s_path
                    self.after(0, lambda: self._progress_step("Exporting player stats (all weeks)..."))
                    p_path = export_player_stats(league, cfg.output_dir, cfg.season or 0, weeks=None)
                    self._last_paths["player_stats"] = p_path
                    self.after(0, lambda: self._progress_step("Exporting free agents..."))
                    fa_path = export_free_agents(league, cfg.output_dir, cfg.season or 0, week=week_val_local)
                    self._last_paths["free_agents"] = fa_path
                    if week_val_local is not None:
                        self.after(0, lambda: self._progress_step(f"Exporting matchups (week {week_val_local})..."))
                        m_path = export_matchups(league, cfg.output_dir, cfg.season or 0, week_val_local)
                        self._last_paths["matchups"] = m_path
                    self.after(0, lambda: self._progress_finish("Export complete"))
                    self.after(0, lambda: messagebox.showinfo("Export", "Export complete."))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("Export Error", str(e)))
            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to start export: {e}")

    def _analyze_players_bg(self) -> None:
        if any(x is None for x in (ap_load_rosters, ap_load_player_games, ap_compute_metrics, ap_tag_categories)):
            messagebox.showerror("Analyze Error", "Analysis module not available. Ensure analyze_players.py exists.")
            return
        players_csv = self._last_paths.get("player_stats") or ""
        rosters_csv = self._last_paths.get("rosters") or ""
        if not players_csv or not os.path.exists(players_csv):
            players_csv = filedialog.askopenfilename(title="Select Players CSV", initialdir=self.output_dir.get() or os.getcwd(), filetypes=[("CSV", "*.csv"), ("All", "*.*")])
            if not players_csv:
                return
        if not rosters_csv or not os.path.exists(rosters_csv):
            rosters_csv = filedialog.askopenfilename(title="Select Rosters CSV", initialdir=self.output_dir.get() or os.getcwd(), filetypes=[("CSV", "*.csv"), ("All", "*.*")])
            if not rosters_csv:
                return

        def worker() -> None:
            try:
                self.after(0, lambda: self._status_var.set("Analyzing players..."))
                self.after(0, lambda: self._set_busy(True))
                ownership = ap_load_rosters(rosters_csv)  # type: ignore[misc]
                games = ap_load_player_games(players_csv)  # type: ignore[misc]
                metrics: List[Any] = []  # type: ignore[name-defined]
                for name, glist in games.items():
                    team = ownership.get(name.lower(), "Free Agent")
                    m = ap_compute_metrics(name, team, glist)  # type: ignore[misc]
                    metrics.append(m)
                # Enrich positions using players CSV
                try:
                    pos_map = ap_load_player_positions(players_csv)  # type: ignore[misc]
                    import re as _re
                    for m in metrics:
                        base = _re.sub(r"\s*\(IR\s*(?:-\s*[^\)]*)?\)\s*$", "", getattr(m, "name", ""))
                        pos_list = pos_map.get(base.lower(), []) if isinstance(pos_map, dict) else []
                        if pos_list:
                            from collections import Counter as _Counter
                            counts = _Counter([p.strip() for p in pos_list if p and p.strip()])
                            if counts:
                                setattr(m, "position", max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0])
                except Exception:
                    pass

                annotated, _cats = ap_tag_categories(metrics)  # type: ignore[misc]
                self.after(0, lambda: self._show_recommendations(annotated, players_csv, rosters_csv))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Analyze Error", f"Failed to analyze: {e}"))
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_recommendations(self, metrics: List[Any], players_csv: str, rosters_csv: str) -> None:
        win = tk.Toplevel(self)
        win.title("Analysis Results")
        win.geometry("1024x600")

        # Build IR + bye maps and infer current week
        import csv as _csv, re as _re
        ir_map: Dict[str, str] = {}
        current_week_val: Optional[int] = None
        try:
            with open(players_csv, "r", encoding="utf-8") as f:
                rdr = _csv.DictReader(f)
                if rdr.fieldnames and "current_week" in rdr.fieldnames:
                    for row in rdr:
                        cw = (row.get("current_week") or "").strip()
                        if cw.isdigit():
                            current_week_val = int(cw)
                            break
        except Exception:
            pass
        try:
            with open(rosters_csv, "r", encoding="utf-8") as f:
                rdr = _csv.DictReader(f)
                if rdr.fieldnames:
                    for row in rdr:
                        raw = (row.get("player_name") or "").strip()
                        base = _re.sub(r"\s*\(IR\s*(?:-\s*[^\)]*)?\)\s*$", "", raw)
                        inj = (row.get("injury_status") or "").strip().upper()
                        dur = (row.get("ir_duration") or "").strip()
                        if base and ("IR" in inj or "INJURY_RESERVE" in inj or "INJURED_RESERVE" in inj):
                            ir_map[base.lower()] = f"IR - {dur}" if dur else "IR"
                        if current_week_val is None and "current_week" in (rdr.fieldnames or []):
                            cw = (row.get("current_week") or "").strip()
                            if cw.isdigit():
                                current_week_val = int(cw)
        except Exception:
            pass
        player_bye: Dict[str, Optional[int]] = {}
        try:
            with open(players_csv, "r", encoding="utf-8") as f:
                rdr = _csv.DictReader(f)
                if rdr.fieldnames:
                    for row in rdr:
                        raw = (row.get("player_name") or row.get("name") or row.get("player") or "").strip()
                        if not raw:
                            continue
                        base = _re.sub(r"\s*\(IR\s*(?:-\s*[^\)]*)?\)\s*$", "", raw)
                        bw = (row.get("bye_week") or row.get("byeWeek") or "").strip()
                        if base and bw.isdigit() and base.lower() not in player_bye:
                            player_bye[base.lower()] = int(bw)
        except Exception:
            pass

        # Supplement IR map using players CSV (injury_status or lineup_slot IR)
        try:
            with open(players_csv, "r", encoding="utf-8") as f:
                rdr = _csv.DictReader(f)
                if rdr.fieldnames:
                    for row in rdr:
                        raw = (row.get("player_name") or row.get("name") or row.get("player") or "").strip()
                        if not raw:
                            continue
                        base = _re.sub(r"\s*\(IR\s*(?:-\s*[^\)]*)?\)\s*$", "", raw)
                        inj = (row.get("injury_status") or row.get("injuryStatus") or "").strip().upper()
                        slot = (row.get("lineup_slot") or row.get("slot_position") or "").strip().upper()
                        dur = (row.get("ir_duration") or row.get("IR_duration") or "").strip()
                        ir_flag = False
                        if ("IR" in inj) or ("INJURY_RESERVE" in inj) or ("INJURED_RESERVE" in inj):
                            ir_flag = True
                        if slot.startswith("IR"):
                            ir_flag = True
                        if base and ir_flag and base.lower() not in ir_map:
                            ir_map[base.lower()] = f"IR - {dur}" if dur else "IR"
        except Exception:
            pass

        # UI: Filters and table
        picker = ttk.Frame(win)
        picker.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(picker, text="My Team:").pack(side="left")
        teams: List[str] = []
        try:
            with open(rosters_csv, "r", encoding="utf-8") as f:
                rdr = _csv.DictReader(f)
                if rdr.fieldnames and "team_name" in rdr.fieldnames:
                    teams = sorted({(row.get("team_name") or "").strip() for row in rdr if (row.get("team_name") or "").strip()})
        except Exception:
            teams = []
        my_team_var = tk.StringVar(value=teams[0] if teams else "")
        ttk.Combobox(picker, textvariable=my_team_var, values=teams, width=26, state=("readonly" if teams else "disabled")).pack(side="left", padx=(6, 0))
        only_rec_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(picker, text="Show only recommended", variable=only_rec_var).pack(side="left", padx=(12, 0))

        table_frame = ttk.Frame(win)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        columns = ("player_name", "rec", "ir", "pos", "team", "games", "total_points", "avg_points", "recent_avg", "ratio", "category")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        heads = {
            "player_name": "Player",
            "rec": "",
            "ir": "IR",
            "pos": "Pos",
            "team": "Team",
            "games": "Games",
            "total_points": "Total",
            "avg_points": "Avg",
            "recent_avg": "Recent",
            "ratio": "Ratio",
            "category": "Category",
        }
        widths = {"player_name": 220, "rec": 28, "ir": 90, "pos": 70, "team": 160, "games": 60, "total_points": 90, "avg_points": 80, "recent_avg": 90, "ratio": 70, "category": 110}
        for k in columns:
            tree.heading(k, text=heads.get(k, k))
            tree.column(k, width=widths.get(k, 80), anchor=("center" if k == "rec" else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Scoring
        def rec_score_and_reasons(m: Any, ir: str) -> Tuple[int, List[str]]:
            score = 0
            reasons: List[str] = []
            cat = (getattr(m, "category", "") or "").lower()
            if "waiver" in cat:
                score += 3; reasons.append("Waiver (+3)")
            if "buy-low" in cat:
                score += 2; reasons.append("Buy-Low (+2)")
            if "sell-high" in cat:
                score -= 3; reasons.append("Sell-High (-3)")
            recent = float(getattr(m, "recent_avg", 0) or 0)
            ratio = float(getattr(m, "ratio", 0) or 0)
            if (getattr(m, "team", "") or "").strip().lower() == "free agent":
                if recent >= 8: score += 1; reasons.append(f"FA {round(recent,1)} ppg (+1)")
                elif recent <= 3: score -= 1; reasons.append(f"FA {round(recent,1)} ppg (-1)")
            if getattr(m, "total_expected", 0) and ratio < 0.85:
                score += 1; reasons.append(f"Undervalued {round(ratio,2)} (+1)")
            if getattr(m, "total_expected", 0) and ratio > 1.2:
                score -= 1; reasons.append(f"Overvalued {round(ratio,2)} (-1)")
            # IR penalty
            def _parse_ir(ir_s: str) -> Optional[int]:
                s = (ir_s or "").lower()
                if not s or s == "ir":
                    return None
                if "season" in s:
                    return 99
                import re as __re
                m2 = __re.search(r"(\d+)\s*w", s)
                if m2:
                    try:
                        return int(m2.group(1))
                    except Exception:
                        return None
                m3 = __re.search(r"until\s*wk\s*(\d{1,2})", s)
                if m3 and current_week_val is not None:
                    try:
                        wk = int(m3.group(1))
                        return max(0, wk - int(current_week_val))
                    except Exception:
                        return None
                return None
            w = _parse_ir(ir)
            if w is not None:
                if w >= 4: score -= 4; reasons.append(f"IR ~{w}w (-4)")
                elif w >= 2: score -= 2; reasons.append(f"IR ~{w}w (-2)")
                elif w >= 1: score -= 1; reasons.append(f"IR ~{w}w (-1)")
            elif (ir or "").strip():
                score -= 2; reasons.append("IR (unspecified) (-2)")
            return score, reasons

        # Build my-team map
        def load_my_team_map(team_name: str) -> Dict[str, str]:
            mp: Dict[str, str] = {}
            try:
                with open(rosters_csv, "r", encoding="utf-8") as f:
                    rdr = _csv.DictReader(f)
                    if not rdr.fieldnames:
                        return {}
                    for row in rdr:
                        if (row.get("team_name") or "").strip() != team_name:
                            continue
                        raw = (row.get("player_name") or "").strip()
                        base = _re.sub(r"\s*\(IR\s*(?:-\s*[^\)]*)?\)\s*$", "", raw)
                        pos = (row.get("position") or "").strip()
                        if base:
                            mp[base.lower()] = pos
            except Exception:
                return {}
            return mp

        metrics_by_name: Dict[str, Any] = {(getattr(x, "name", "").strip().lower()): x for x in metrics}

        def suggest_replacements(candidate: Any, my_team: str) -> List[str]:
            if not my_team:
                return ["Set 'My Team' to see suggestions"]
            my_map = load_my_team_map(my_team)
            cpos = (getattr(candidate, "position", "") or "").strip().upper()
            if cpos in ("D/ST", "DST"):
                cpos = "DST"
            items: List[tuple[str, str, float, float]] = []
            for nm_lower, pos in my_map.items():
                pos_u = (pos or "").upper()
                pos_u = "DST" if pos_u in ("D/ST", "DST") else pos_u
                if cpos and pos_u and pos_u != cpos:
                    continue
                mm = metrics_by_name.get(nm_lower)
                if not mm:
                    continue
                recent = float(getattr(mm, "recent_avg", 0) or 0)
                ratio = float(getattr(mm, "ratio", 0) or 0)
                items.append((nm_lower, pos_u or cpos or "", recent, ratio))
            items.sort(key=lambda t: (t[2], t[3]))
            out: List[str] = []
            for nm_lower, pos_u, recent, ratio in items:
                if nm_lower == getattr(candidate, "name", "").strip().lower():
                    continue
                out.append(f"- {nm_lower.title()} ({pos_u}) — {round(recent,1)} ppg, ratio {round(ratio,2)}")
                if len(out) >= 3:
                    break
            if not out:
                out = ["No obvious worse same-pos players on your team"]
            return out

        row_tips: Dict[str, str] = {}

        def refresh_table() -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            for m in metrics:
                base = _re.sub(r"\s*\(IR\s*(?:-\s*[^\)]*)?\)\s*$", "", getattr(m, "name", ""))
                ir = ir_map.get(base.lower(), "")
                score, reasons = rec_score_and_reasons(m, ir)
                rec_sym = "🟩" if score >= 2 else ""
                if only_rec_var.get() and not rec_sym:
                    continue
                ratio_val = round(float(getattr(m, "ratio", 0) or 0), 3) if getattr(m, "total_expected", 0) else ""
                values = (
                    getattr(m, "name", ""), rec_sym, ir, (getattr(m, "position", "") or ""), getattr(m, "team", "") or "Free Agent",
                    getattr(m, "games", 0), round(float(getattr(m, "total_actual", 0) or 0), 3), round(float(getattr(m, "avg_actual", 0) or 0), 3),
                    round(float(getattr(m, "recent_avg", 0) or 0), 3), ratio_val, getattr(m, "category", "")
                )
                iid = tree.insert("", "end", values=values)
                if rec_sym:
                    tip_lines: List[str] = []
                    pos_txt = (getattr(m, "position", "") or "").strip()
                    tip_lines.append(f"Add: {getattr(m,'name','')}" + (f" · {pos_txt}" if pos_txt else ""))
                    if ir:
                        tip_lines.append(f"IR: {ir}")
                    bw = player_bye.get(base.lower())
                    if bw is not None:
                        if current_week_val is not None and bw == current_week_val:
                            tip_lines.append(f"Bye: Wk {bw} (this week)")
                        else:
                            tip_lines.append(f"Bye: Wk {bw}")
                    tip_lines.append(f"Recent {round(float(getattr(m,'recent_avg',0) or 0),1)} ppg, Ratio {round(float(getattr(m,'ratio',0) or 0),2) if getattr(m,'total_expected',0)>0 else 0}")
                    tip_lines.append("Signals: " + "; ".join(reasons))
                    tip_lines.append("")
                    tip_lines.append("Suggested replacements:")
                    for s in suggest_replacements(m, my_team_var.get() or ""):
                        tip_lines.append(s)
                    row_tips[iid] = "\n".join(tip_lines)

        refresh_table()
        only_rec_var.trace_add("write", lambda *args: refresh_table())
        my_team_var.trace_add("write", lambda *args: refresh_table())

        # Tooltip for Rec
        tip_win: Optional[tk.Toplevel] = None
        tip_lbl: Optional[tk.Label] = None
        rec_col_id = f"#{columns.index('rec')+1}"

        def hide_tip() -> None:
            nonlocal tip_win, tip_lbl
            if tip_win is not None:
                try:
                    tip_win.destroy()
                except Exception:
                    pass
                tip_win = None
                tip_lbl = None

        def show_tip(text: str, x: int, y: int) -> None:
            nonlocal tip_win, tip_lbl
            if not text:
                hide_tip(); return
            if tip_win is None:
                tip_win = tk.Toplevel(win)
                tip_win.wm_overrideredirect(True)
                tip_win.attributes("-topmost", True)
                tip_lbl = tk.Label(tip_win, text=text, justify="left", background="#ffffe0", relief="solid", borderwidth=1, padx=6, pady=4)
                tip_lbl.pack()
            else:
                try:
                    tip_lbl.configure(text=text)  # type: ignore[union-attr]
                except Exception:
                    pass
            try:
                tip_win.wm_geometry(f"+{x+12}+{y+12}")
            except Exception:
                pass

        def on_move(event: tk.Event) -> None:  # type: ignore[name-defined]
            try:
                col = tree.identify_column(event.x)
                row = tree.identify_row(event.y)
                if col == rec_col_id and row in row_tips and row_tips.get(row):
                    show_tip(row_tips.get(row, ""), event.x_root, event.y_root)  # type: ignore[attr-defined]
                else:
                    hide_tip()
            except Exception:
                hide_tip()

        tree.bind("<Motion>", on_move)
        tree.bind("<Leave>", lambda e: hide_tip())


def main() -> None:
    app = ConfigGUI()
    app.mainloop()


if __name__ == "__main__":
    main()


def main() -> None:
    app = ConfigGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
