"""PrintLab desktop app server.

Serves the UI at http://127.0.0.1:8123, lists parts, re-runs part scripts
with tweaked parameters (free, instant), and spawns Claude Code headless
(`claude -p`, billed to the user's existing plan) to forge new parts.
"""
import ast
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent
PARTS = ROOT / "parts"
OUT = ROOT / "output"
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"
PORT = 8123

app = FastAPI()
JOBS = {}          # id -> {status, log[], part, summary, error}
DIMS_CACHE = {}    # (path, mtime) -> stats dict


# ------------------------------------------------------------- claude engine

def find_claude():
    on_path = shutil.which("claude")
    if on_path:
        return on_path
    bundled = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude-code"
    if bundled.exists():
        exes = sorted(bundled.glob("*/claude.exe"), key=lambda p: p.stat().st_mtime)
        if exes:
            return str(exes[-1])
    return None


def clean_env():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("CLAUDE"):
            del env[key]
    env["PRINTLAB_P"] = ""
    return env


FORGE_PROMPT = """You are the geometry engine inside PrintLab, a personal 3D
print file maker. A user (not a developer) typed this request into the app:

<<<{request}>>>

{mode_line}

Rules — follow exactly:
- Conventions and helpers: read CLAUDE.md and lib3d.py in this repo if unsure.
- The script's tunable dimensions live in `P = lib3d.params({{...}})` at the
  top, every value a plain number or string literal with a short comment.
- All booleans via lib3d.union/difference/intersection. Units are mm.
- The export name must equal the script filename stem:
  lib3d.export(build(), "<stem>").
- Run it with: venv\\Scripts\\python.exe parts\\<stem>.py
  Iterate until the output line says watertight=True and plate_fit=OK.
- Touch nothing outside parts/ and output/.
- Design for FDM printing: flat face down, >=2mm walls, no floating geometry.

Your FINAL reply must be exactly two lines:
PART=<stem>
SUMMARY=<one plain-English sentence describing what you made>
"""

MODE_NEW = ("Create a NEW part script at parts/<stem>.py — pick a short "
            "snake_case stem that describes the part.")
MODE_EDIT = ("Revise the EXISTING part script parts/{part}.py per the request "
             "(edit its P defaults and/or geometry). Keep the same filename.")


def run_forge(job_id, request, part=None):
    job = JOBS[job_id]
    claude = find_claude()
    if not claude:
        job.update(status="error", error="Claude engine not found on this PC.")
        return
    mode_line = MODE_EDIT.format(part=part) if part else MODE_NEW
    prompt = FORGE_PROMPT.format(request=request, mode_line=mode_line)
    cmd = [claude, "-p", prompt,
           "--output-format", "stream-json", "--verbose",
           "--model", "opus", "--max-turns", "30",
           "--allowedTools", "Read,Glob,Grep,Write,Edit,Bash"]
    try:
        proc = subprocess.Popen(
            cmd, cwd=ROOT, env=clean_env(),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    except OSError as exc:
        job.update(status="error", error=f"Could not start engine: {exc}")
        return

    final_text = ""
    deadline = time.time() + 600
    for line in proc.stdout:
        if time.time() > deadline:
            proc.kill()
            job.update(status="error", error="Timed out after 10 minutes.")
            return
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            if "Not logged in" in line or "/login" in line:
                job.update(status="auth")
            else:
                job["log"].append(line[:200])
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            job["log"].append("engine started, reading your request…")
        elif kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and block.get("text", "").strip():
                    job["log"].append(block["text"].strip()[:300])
                elif block.get("type") == "tool_use":
                    job["log"].append(_describe_tool(block))
        elif kind == "result":
            final_text = event.get("result") or ""
            if event.get("is_error") and "login" in final_text.lower():
                job.update(status="auth")
    proc.wait()

    if job["status"] == "auth":
        return
    made = re.search(r"PART=([\w-]+)", final_text)
    summary = re.search(r"SUMMARY=(.+)", final_text)
    if made and (OUT / f"{made.group(1)}.stl").exists():
        job.update(status="done", part=made.group(1),
                   summary=summary.group(1).strip() if summary else "")
        job["log"].append("done.")
    elif "Not logged in" in final_text:
        job.update(status="auth")
    else:
        job.update(status="error",
                   error=(final_text[:400] or "Engine finished without producing a part."))


def _describe_tool(block):
    name = block.get("name", "")
    inp = block.get("input", {})
    target = Path(str(inp.get("file_path", ""))).name
    if name in ("Write", "Edit"):
        return f"writing {target or 'part script'}…"
    if name == "Bash":
        cmd = str(inp.get("command", ""))
        return "building the mesh…" if ".py" in cmd else "running a check…"
    if name in ("Read", "Glob", "Grep"):
        return f"checking {target or 'the toolkit'}…"
    return f"{name.lower()}…"


# ------------------------------------------------------------- part scripts

def part_stats(stl: Path):
    key = (str(stl), stl.stat().st_mtime)
    if key in DIMS_CACHE:
        return DIMS_CACHE[key]
    import trimesh
    mesh = trimesh.load(stl, force="mesh")
    stats = {
        "dims": [round(float(d), 1) for d in mesh.extents],
        "watertight": bool(mesh.is_watertight),
        "volume_cm3": round(float(mesh.volume) / 1000, 1) if mesh.is_watertight else None,
        "tris": int(len(mesh.faces)),
        "mtime": stl.stat().st_mtime,
    }
    DIMS_CACHE[key] = stats
    return stats


def read_params(part):
    src = (PARTS / f"{part}.py").read_text(encoding="utf-8")
    match = re.search(r"P\s*=\s*lib3d\.params\((\{.*?\})\)", src, re.S)
    if not match:
        return {}
    try:
        return ast.literal_eval(match.group(1))
    except (ValueError, SyntaxError):
        return {}


def safe_part(name):
    if not re.fullmatch(r"[\w-]+", name or "") or not (PARTS / f"{name}.py").exists():
        return None
    return name


def retarget_export(src, old, new):
    """Point a part script's lib3d.export() call at a new stem."""
    return re.subn(rf'(lib3d\.export\([^"\']*["\']){re.escape(old)}(["\'])',
                   rf"\g<1>{new}\g<2>", src)


def run_part(part, overrides=None):
    env = clean_env()
    if overrides:
        env["PRINTLAB_P"] = json.dumps(overrides)
    proc = subprocess.run(
        [str(VENV_PY), str(PARTS / f"{part}.py")], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW)
    out = (proc.stdout + proc.stderr).strip()
    ok = (proc.returncode == 0 and "watertight=True" in out
          and "watertight=False" not in out)
    return ok, out


# ---------------------------------------------------------------------- api

@app.get("/api/health")
def health():
    return {"claude": bool(find_claude()), "port": PORT}


@app.get("/api/parts")
def list_parts():
    items = []
    for script in sorted(PARTS.glob("*.py")):
        stl = OUT / f"{script.stem}.stl"
        bodies = sorted(f.name.split(".")[1]
                        for f in OUT.glob(f"{script.stem}.*.stl"))
        item = {"name": script.stem, "has_stl": stl.exists(), "bodies": bodies}
        if stl.exists():
            try:
                stats = dict(part_stats(stl))
                if bodies:
                    # combined preview is touching shells — judge per body
                    per = [part_stats(OUT / f"{script.stem}.{b}.stl")
                           for b in bodies]
                    stats["watertight"] = all(s["watertight"] for s in per)
                    stats["volume_cm3"] = round(
                        sum(s["volume_cm3"] or 0 for s in per), 1)
                    stats["tris"] = sum(s["tris"] for s in per)
                item.update(stats)
            except Exception as exc:  # unreadable STL shouldn't kill the list
                item["error"] = str(exc)[:120]
        items.append(item)
    items.sort(key=lambda i: -(i.get("mtime") or 0))
    return items


@app.get("/api/params/{part}")
def get_params(part: str):
    part = safe_part(part)
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    return read_params(part)


@app.post("/api/rerun")
async def rerun(body: dict):
    part = safe_part(body.get("part"))
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    ok, out = run_part(part, body.get("overrides") or {})
    return {"ok": ok, "log": out[-600:]}


@app.post("/api/bake")
async def bake(body: dict):
    part = safe_part(body.get("part"))
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    overrides = body.get("overrides") or {}
    path = PARTS / f"{part}.py"
    src = path.read_text(encoding="utf-8")
    match = re.search(r"(P\s*=\s*lib3d\.params\(\{)(.*?)(\}\))", src, re.S)
    if not match:
        return {"ok": False, "error": "couldn't find the params block"}
    block = match.group(2)
    for key, val in overrides.items():
        lit = json.dumps(val)
        block, n = re.subn(rf'("{key}"\s*:\s*)[^,\n#]+', rf"\g<1>{lit}", block, count=1)
        if not n:
            return {"ok": False, "error": f"couldn't update '{key}'"}
    path.write_text(src[:match.start(2)] + block + src[match.end(2):], encoding="utf-8")
    ok, out = run_part(part)
    return {"ok": ok, "log": out[-600:]}


@app.post("/api/delete")
async def delete_part(body: dict):
    part = safe_part(body.get("part"))
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    trash = ROOT / "trash"
    trash.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (PARTS / f"{part}.py").rename(trash / f"{part}.{stamp}.py")
    stl = OUT / f"{part}.stl"
    if stl.exists():
        stl.rename(trash / f"{part}.{stamp}.stl")
    return {"ok": True}


def _valid_new_name(name):
    return bool(re.fullmatch(r"[a-z][a-z0-9_]{1,40}", name or "")) \
        and not (PARTS / f"{name}.py").exists()


@app.post("/api/rename")
async def rename_part(body: dict):
    part = safe_part(body.get("part"))
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    to = (body.get("to") or "").strip()
    if not _valid_new_name(to):
        return {"ok": False, "error": "name must be unused snake_case (a-z, 0-9, _)"}
    path = PARTS / f"{part}.py"
    src, hits = retarget_export(path.read_text(encoding="utf-8"), part, to)
    if not hits:
        return {"ok": False, "error": "couldn't update the script's export name"}
    (PARTS / f"{to}.py").write_text(src, encoding="utf-8")
    path.unlink()
    stl = OUT / f"{part}.stl"
    if stl.exists():
        stl.rename(OUT / f"{to}.stl")
    return {"ok": True, "part": to}


@app.post("/api/duplicate")
async def duplicate_part(body: dict):
    part = safe_part(body.get("part"))
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    n = 2
    while not _valid_new_name(f"{part}_{n}"):
        n += 1
    to = f"{part}_{n}"
    src, hits = retarget_export((PARTS / f"{part}.py").read_text(encoding="utf-8"),
                                part, to)
    if not hits:
        return {"ok": False, "error": "couldn't update the script's export name"}
    (PARTS / f"{to}.py").write_text(src, encoding="utf-8")
    run_part(to)
    return {"ok": True, "part": to}


@app.post("/api/generate")
async def generate(body: dict):
    request = (body.get("prompt") or "").strip()
    if not request:
        return JSONResponse({"error": "empty prompt"}, status_code=400)
    part = safe_part(body.get("part")) if body.get("part") else None
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"status": "running", "log": ["sending to the engine…"],
                    "part": part, "summary": "", "error": ""}
    threading.Thread(target=run_forge, args=(job_id, request, part),
                     daemon=True).start()
    return {"job": job_id}


@app.get("/api/job/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    return job or JSONResponse({"error": "unknown job"}, status_code=404)


@app.post("/api/connect")
async def connect():
    claude = find_claude()
    if not claude:
        return {"ok": False, "error": "Claude engine not found."}
    subprocess.Popen([str(ROOT / "tools" / "engine_login.bat"), claude],
                     cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
    return {"ok": True}


def find_bambu():
    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "Bambu Studio" / "bambu-studio.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Bambu Studio" / "bambu-studio.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "BambuStudio" / "bambu-studio.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Bambu Studio" / "bambu-studio.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return shutil.which("bambu-studio")


@app.post("/api/open")
async def open_target(body: dict):
    part = safe_part(body.get("part"))
    if not part:
        return JSONResponse({"error": "unknown part"}, status_code=404)
    body_stls = sorted(OUT.glob(f"{part}.*.stl"))
    stls = body_stls or [OUT / f"{part}.stl"]
    if body.get("target") == "folder":
        subprocess.Popen(["explorer", "/select,", str(stls[0])])
        return {"ok": True}
    bambu = find_bambu()
    if bambu:
        # multi-body: Bambu Studio offers "load as single object with parts"
        subprocess.Popen([bambu, *map(str, stls)])
    elif len(stls) == 1 and stls[0].exists():
        os.startfile(stls[0])  # default STL app
    else:
        subprocess.Popen(["explorer", "/select,", str(stls[0])])
    return {"ok": True}


app.mount("/output", StaticFiles(directory=OUT), name="output")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            print("PrintLab is already running.")
            raise SystemExit(0)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
