"""Read-only API for the dashboard: uvicorn backend.main:app --reload

The SQLite file is opened with mode=ro on every request, so this process can never write to
it and always sees runs that an eval is still adding.
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import db
from backend.api_shapes import call_row, compare_warnings, run_detail, run_summary
from backend.eval.validation import open_readonly

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
DEFAULT_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
MAX_COMPARE = 10


def create_app(db_path: Optional[Path] = None, dist_dir: Optional[Path] = None) -> FastAPI:
    path = Path(db_path or os.environ.get("DB_PATH") or db.DEFAULT_DB)
    dist = DEFAULT_DIST if dist_dir is None else Path(dist_dir)
    app = FastAPI(title="CollectionsLab API")
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["GET"],
                       allow_headers=["*"])

    def get_conn():
        if not path.exists():
            raise HTTPException(503, "database not found")
        conn = open_readonly(path)
        try:
            yield conn
        finally:
            conn.close()

    def counts(conn: sqlite3.Connection, run_id: int) -> dict[str, int]:
        rows = conn.execute("SELECT status, COUNT(*) AS c FROM calls WHERE run_id = ? "
                            "GROUP BY status", (run_id,))
        return {r["status"]: r["c"] for r in rows}

    def load_run(conn: sqlite3.Connection, run_id: int) -> dict:
        if conn.execute("SELECT 1 FROM runs WHERE id = ?", (run_id,)).fetchone() is None:
            raise HTTPException(404, f"run {run_id} not found")
        run = db.get_run(conn, run_id)
        run.pop("scenarios", None)  # the full pool is large and the dashboard never needs it
        return run

    @app.get("/api/health")
    def health():
        return {"status": "ok", "db": path.exists()}

    @app.get("/api/runs")
    def list_runs(conn=Depends(get_conn)):
        ids = [r["id"] for r in conn.execute("SELECT id FROM runs ORDER BY updated_at DESC, id DESC")]
        return [run_summary(load_run(conn, i), counts(conn, i)) for i in ids]

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: int, conn=Depends(get_conn)):
        return run_detail(load_run(conn, run_id), counts(conn, run_id))

    @app.get("/api/runs/{run_id}/calls")
    def list_calls(run_id: int, conn=Depends(get_conn)):
        load_run(conn, run_id)
        return [call_row(c) for c in db.get_calls(conn, run_id)]

    @app.get("/api/calls/{run_id}/{idx}")
    def get_call(run_id: int, idx: int, conn=Depends(get_conn)):
        run = load_run(conn, run_id)
        call = next((c for c in db.get_calls(conn, run_id) if c["idx"] == idx), None)
        if call is None:
            raise HTTPException(404, f"call {idx} not found in run {run_id}")
        return {**call, "prompt_version": run["prompt_version"],
                "judge_version": run["judge_version"], "models": run["models"]}

    @app.get("/api/compare")
    def compare(run_ids: str = Query(...), conn=Depends(get_conn)):
        try:
            ids = list(dict.fromkeys(int(p) for p in run_ids.split(",") if p.strip()))
        except ValueError:
            raise HTTPException(400, "run_ids must be comma-separated integers")
        if not ids or len(ids) > MAX_COMPARE:
            raise HTTPException(400, f"give 1 to {MAX_COMPARE} run ids")
        runs = [run_detail(load_run(conn, i), counts(conn, i)) for i in ids]
        return {"runs": runs, "warnings": compare_warnings(runs)}

    @app.get("/api/{rest:path}")
    def api_not_found(rest: str):
        raise HTTPException(404, "not found")

    if dist.is_dir():  # registered last so /api routes win
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


app = create_app()
