"""Smoke/abuse test for the running PrintLab API.

Start PrintLab, then:

    venv\\Scripts\\python.exe tools\\test_api.py

Never calls /api/generate (that spends plan usage), and cleans up anything it
creates. Skips with exit 0 if the server isn't running.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8123"
FAILED = []


def call(method, path, payload=None, timeout=180):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{'' if ok else '  ' + str(detail)[:150]}")
    if not ok:
        FAILED.append(label)


try:
    status, health = call("GET", "/api/health", timeout=5)
except Exception:  # noqa: BLE001
    print("PrintLab isn't running on 127.0.0.1:8123 — skipping API tests.")
    sys.exit(0)

print("health")
check("health responds", status == 200, health)
check("engine found", bool(health.get("claude")), health)

print("\nhostile part names must 404, never 500 or escape parts/")
for name in ["../../../etc/passwd", "..\\..\\app", "....//app", " ",
             "part;rm -rf /", "$(whoami)", "a" * 300]:
    st, body = call("GET", "/api/params/" + urllib.parse.quote(name, safe=""))
    check(f"rejects {name[:24]!r}", st in (400, 404), f"{st} {body}")

print("\nrerun contract")
st, body = call("POST", "/api/rerun", {"part": "nope_not_real"})
check("unknown part 404s", st == 404, f"{st} {body}")

st, body = call("POST", "/api/rerun", {"part": "calibration_cube"})
check("plain rebuild succeeds", st == 200 and body.get("ok") is True, body)

# a tweak that grows the part past the build plate is NOT a success
st, body = call("POST", "/api/rerun",
                {"part": "calibration_cube", "overrides": {"size": 99999}})
check("oversized rebuild reports failure",
      st == 200 and body.get("ok") is False, body)
check("oversized rebuild says why",
      "TOO BIG" in str(body.get("log", "")), body.get("log", "")[-120:])

# a nonsense value must be ignored rather than crash the build
st, body = call("POST", "/api/rerun",
                {"part": "calibration_cube", "overrides": {"size": "banana"}})
check("non-numeric override ignored", st == 200 and body.get("ok") is True, body)

st, body = call("POST", "/api/rerun",
                {"part": "calibration_cube", "overrides": {"no_such_key": 5}})
check("unknown override key ignored", st == 200 and body.get("ok") is True, body)

# leave it as it started
call("POST", "/api/rerun", {"part": "calibration_cube"})

print("\nduplicate/rename/delete lifecycle")
st, dup = call("POST", "/api/duplicate", {"part": "calibration_cube"})
made = dup.get("part") if isinstance(dup, dict) else None
check("duplicate creates an auto-named copy", st == 200 and bool(made), dup)
if made:
    st, body = call("POST", "/api/rename", {"part": made, "to": "phone_stand"})
    check("rename onto an existing name is refused",
          body.get("ok") is False, body)
    st, body = call("POST", "/api/rename", {"part": made, "to": "../escape"})
    check("rename to a path is refused", body.get("ok") is False, body)
    st, body = call("POST", "/api/delete", {"part": made})
    check("delete removes the copy", st == 200, body)

st, parts = call("GET", "/api/parts")
names = {p["name"] for p in parts} if isinstance(parts, list) else set()
check("no leftover copies", not any(n.endswith(("_2", "_3")) for n in names),
      sorted(names))
check("real parts still present", "calibration_cube" in names, sorted(names))

print()
if FAILED:
    print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
    sys.exit(1)
print("all API checks passed")
