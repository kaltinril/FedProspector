#!/usr/bin/env python3
"""FedProspector Service Manager.

Usage:
    python fed_prospector.py <command> [service]

Commands:  build | start | stop | restart | status
Services:  all (default) | db | api | ui | poller
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / "fed_prospector" / ".env")

MYSQL_BIN = Path(os.environ.get("MYSQL_BIN_DIR", ""))
if not MYSQL_BIN.is_dir():
    # Try to find mysqld on PATH
    mysqld_path = shutil.which("mysqld")
    MYSQL_BIN = Path(mysqld_path).parent if mysqld_path else Path("mysql/bin")
API_PROJECT = SCRIPT_DIR / "api" / "src" / "FedProspector.Api"
API_SLN = SCRIPT_DIR / "api" / "FedProspector.slnx"
API_EXE = "FedProspector.Api.exe"
MYSQL_EXE = "mysqld.exe"
MYSQL_ROOT_PASS = os.environ.get("MYSQL_ROOT_PASS", "")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
API_PORT = int(os.environ.get("API_PORT", "5056"))
UI_PORT = int(os.environ.get("UI_PORT", "5173"))
ASPNETCORE_ENV = os.environ.get("ASPNETCORE_ENVIRONMENT", "Development")
API_URL = f"http://localhost:{API_PORT}"
POLLER_TITLE = "FedProspect Poller"
POLLER_DIR = SCRIPT_DIR / "fed_prospector"


def is_running(image_name: str) -> bool:
    """Check if a Windows process is running by image name."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            capture_output=True, text=True, timeout=5,
        )
        return image_name.lower() in result.stdout.lower()
    except Exception:
        return False


def kill_process(image_name: str) -> bool:
    """Force-kill a process by image name."""
    try:
        subprocess.run(
            ["taskkill", "/IM", image_name, "/F"],
            capture_output=True, timeout=10,
        )
        return True
    except Exception:
        return False


def mysql_admin(*args: str, timeout: int = 10) -> int:
    """Run mysqladmin with root credentials."""
    cmd = [str(MYSQL_BIN / "mysqladmin"), "-u", "root", f"-p{MYSQL_ROOT_PASS}", *args]
    result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return result.returncode


def url_reachable(url: str) -> bool:
    """Check if a URL responds (any HTTP response counts as reachable)."""
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except urllib.error.HTTPError:
        # Server responded (e.g. 503 degraded) — it's running
        return True
    except Exception:
        return False


def port_in_use(port: int) -> bool:
    """Check if a TCP port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


# -- DB ---------------------------------------------------------------

def start_db():
    if is_running(MYSQL_EXE):
        print("  [DB]  Already running.")
        return
    mysql_bin_path = MYSQL_BIN / MYSQL_EXE
    if not mysql_bin_path.is_file():
        print(f"  [DB]  ERROR: MySQL binary not found at: {mysql_bin_path}")
        print("        Fix: Set MYSQL_BIN_DIR in fed_prospector/.env to your MySQL bin directory")
        return
    if port_in_use(DB_PORT):
        print(f"  [DB]  ERROR: Port {DB_PORT} is already in use.")
        print(f"        Another process may be using this port. Check with: netstat -ano | findstr :{DB_PORT}")
        return
    print("  [DB]  Starting MySQL ...")
    subprocess.Popen(
        f'start "MySQL" /MIN "{mysql_bin_path}" --console --secure-file-priv=',
        shell=True,
    )
    for i in range(30):
        time.sleep(1)
        if mysql_admin("ping") == 0:
            print(f"  [DB]  MySQL is ready.  (port {DB_PORT})")
            return
        if i == 9:
            print("  [DB]  Still waiting for MySQL to respond...")
        elif i == 19:
            print("  [DB]  Still waiting... checking common issues")
    print("  [DB]  TIMEOUT: MySQL did not respond after 30 seconds.")
    print("        Possible causes:")
    print("        - Data directory may be corrupted")
    print("        - Insufficient disk space")
    print("        - Check MySQL error log for details")


def stop_db(force: bool = False):
    if not is_running(MYSQL_EXE):
        print("  [DB]  Not running.")
        return
    if force:
        print("  [DB]  Force-killing MySQL ...")
        kill_process(MYSQL_EXE)
        time.sleep(2)
        print("  [DB]  Stopped.")
        return
    print("  [DB]  Shutting down MySQL ...")
    try:
        mysql_admin("shutdown", timeout=30)
        print("  [DB]  Stopped.")
    except subprocess.TimeoutExpired:
        print("  [DB]  ERROR: Shutdown timed out after 30 seconds.")
        print("        MySQL may be blocked (e.g. console text selection).")
        print("        Retry, or use: fed_prospector stop db --force")


def check_db():
    if is_running(MYSQL_EXE):
        print(f"  [DB]  Running  (port {DB_PORT})")
    else:
        print("  [DB]  Stopped")


# -- API --------------------------------------------------------------

def build_api():
    print("  [API] Building ...")
    result = subprocess.run(
        ["dotnet", "build", str(API_SLN), "--verbosity", "quiet"],
        timeout=120,
    )
    if result.returncode == 0:
        print("  [API] Build succeeded.")
        return True
    else:
        print("  [API] Build FAILED.")
        return False


def _api_env() -> dict[str, str]:
    """Build environment variables for the .NET API process.

    Reads DB_PASSWORD and JWT_SECRET_KEY from fed_prospector/.env and maps
    them to the ASP.NET Core config keys (using __ separator convention).
    """
    env = {**os.environ}
    db_password = os.environ.get("DB_PASSWORD", "")
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "")

    if db_password:
        conn = (
            f"Server=localhost;Port={DB_PORT};Database=fed_contracts;"
            f"User=fed_app;Password={db_password};"
            f"SslMode=None;AllowPublicKeyRetrieval=True"
        )
        env["ConnectionStrings__DefaultConnection"] = conn

    if jwt_secret:
        env["Jwt__SecretKey"] = jwt_secret

    env["ASPNETCORE_ENVIRONMENT"] = ASPNETCORE_ENV
    env["ASPNETCORE_URLS"] = f"http://localhost:{API_PORT}"
    return env


def start_api():
    if is_running(API_EXE):
        print("  [API] Already running.")
        return
    if port_in_use(API_PORT):
        print(f"  [API] ERROR: Port {API_PORT} is already in use.")
        print(f"        Another process may be using this port. Check with: netstat -ano | findstr :{API_PORT}")
        return
    env = _api_env()
    if not env.get("Jwt__SecretKey"):
        print("  [API] WARNING: JWT_SECRET_KEY not set in fed_prospector/.env")
        print("        Auth will fail. Add: JWT_SECRET_KEY=<at-least-32-chars>")
    print(f"  [API] Starting .NET API ({ASPNETCORE_ENV}) ...")
    subprocess.Popen(
        f'start "FedProspector API" /MIN dotnet run --no-build --project "{API_PROJECT}"',
        shell=True,
        env=env,
    )
    for i in range(60):
        time.sleep(1)
        if url_reachable(f"{API_URL}/health"):
            print(f"  [API] Ready ({i+1}s).  Swagger: {API_URL}/swagger")
            print(f"                    Health:  {API_URL}/health")
            return
        if i == 14:
            print("  [API] Still waiting for API to respond...")
        elif i == 29:
            print("  [API] Still waiting... this is taking longer than expected")
    print("  [API] TIMEOUT: API did not respond after 60 seconds.")
    print("        Possible causes:")
    print("        - Build may be needed first (run: python fed_prospector.py build api)")
    print("        - MySQL may not be running (run: python fed_prospector.py start db)")
    print(f"        - Check manually: {API_URL}/health")


def stop_api():
    if not is_running(API_EXE):
        print("  [API] Not running.")
        return
    print("  [API] Stopping ...")
    kill_process(API_EXE)
    print("  [API] Stopped.")


def check_api():
    if is_running(API_EXE):
        print(f"  [API] Running  ({API_URL}/swagger)")
    else:
        print("  [API] Stopped")


# -- UI ---------------------------------------------------------------

def build_ui():
    ui_dir = SCRIPT_DIR / "ui"
    if not (ui_dir / "package.json").is_file():
        print("  [UI]  ERROR: No package.json found in ui/")
        return False
    print("  [UI]  Building (npm run build) ...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ui_dir),
        timeout=120,
        shell=True,
    )
    if result.returncode == 0:
        print("  [UI]  Build succeeded.")
        return True
    else:
        print("  [UI]  Build FAILED.")
        return False


def start_ui():
    if port_in_use(UI_PORT):
        print(f"  [UI]  Already running (port {UI_PORT}).")
        return
    ui_dir = SCRIPT_DIR / "ui"
    if not (ui_dir / "package.json").is_file():
        print("  [UI]  ERROR: No package.json found in ui/")
        return
    print("  [UI]  Starting Vite dev server ...")
    subprocess.Popen(
        f'start "FedProspect UI" /MIN cmd /c "cd /d {ui_dir} && npm run dev -- --port {UI_PORT}"',
        shell=True,
    )
    for i in range(30):
        time.sleep(1)
        if port_in_use(UI_PORT):
            print(f"  [UI]  Ready.  http://localhost:{UI_PORT}")
            return
        if i == 9:
            print("  [UI]  Still waiting for Vite to start...")
    print("  [UI]  TIMEOUT: Vite did not start after 30 seconds.")


def stop_ui():
    if not port_in_use(UI_PORT):
        print("  [UI]  Not running.")
        return
    print("  [UI]  Stopping Vite dev server ...")
    # Find PID listening on the UI port and kill it with its child processes
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if f":{UI_PORT}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(
                    ["taskkill", "/PID", pid, "/F", "/T"],
                    capture_output=True, timeout=10,
                )
                break
    except Exception:
        pass
    # Wait for port to actually free up
    for _ in range(10):
        if not port_in_use(UI_PORT):
            break
        time.sleep(1)
    print("  [UI]  Stopped.")


def check_ui():
    if port_in_use(UI_PORT):
        print(f"  [UI]  Running  (http://localhost:{UI_PORT})")
    else:
        print("  [UI]  Stopped")


# -- Poller ------------------------------------------------------------

def _poller_is_running() -> bool:
    """Check if the poller window is running by its window title."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"WINDOWTITLE eq {POLLER_TITLE}"],
            capture_output=True, text=True, timeout=5,
        )
        # tasklist prints "INFO: No tasks are running..." when nothing matches
        return "python" in result.stdout.lower()
    except Exception:
        return False


def start_poller(clear_queue: bool = False):
    if _poller_is_running():
        print("  [POL] Already running.")
        return
    print("  [POL] Starting request poller ...")
    cmd = f'start "{POLLER_TITLE}" /MIN python main.py job process-requests --watch'
    if clear_queue:
        cmd += " --clear-queue"
        print("  [POL] Clearing pending requests before starting ...")
    subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(POLLER_DIR),
    )
    time.sleep(2)
    if _poller_is_running():
        print("  [POL] Ready.  (polling data_load_request every 5s)")
    else:
        print("  [POL] WARNING: Poller may not have started. Check the console window.")


def stop_poller():
    if not _poller_is_running():
        print("  [POL] Not running.")
        return
    print("  [POL] Stopping ...")
    try:
        subprocess.run(
            ["taskkill", "/FI", f"WINDOWTITLE eq {POLLER_TITLE}", "/F", "/T"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass
    print("  [POL] Stopped.")


def check_poller():
    if _poller_is_running():
        print("  [POL] Running  (polling data_load_request)")
    else:
        print("  [POL] Stopped")


# -- Commands ----------------------------------------------------------

SERVICE_MAP = {
    "db":     {"start": start_db,     "stop": stop_db,     "check": check_db,     "build": None},
    "api":    {"start": start_api,    "stop": stop_api,    "check": check_api,    "build": build_api},
    "ui":     {"start": start_ui,     "stop": stop_ui,     "check": check_ui,     "build": build_ui},
    "poller": {"start": start_poller, "stop": stop_poller, "check": check_poller, "build": None},
}

ALL_SERVICES = ["db", "api", "ui", "poller"]


def cmd_build(service: str):
    targets = ALL_SERVICES if service == "all" else [service]
    build_targets = [s for s in targets if SERVICE_MAP[s]["build"]]
    # Stop services that need building, plus the poller (it loads Python
    # modules that may change).  Stop in reverse order (poller/UI before API).
    stop_targets = [s for s in reversed(targets)
                    if SERVICE_MAP[s]["build"] or s == "poller"]
    poller_was_running = _poller_is_running() if "poller" in stop_targets else False
    for svc in stop_targets:
        SERVICE_MAP[svc]["stop"]() if svc != "db" else None
    # Build
    failures = []
    for svc in build_targets:
        success = SERVICE_MAP[svc]["build"]()
        if success is False:
            failures.append(svc)
    if failures:
        print(f"\n  Build failed for: {', '.join(failures)}")
        sys.exit(1)
    # Start services back up (API first, then UI, then poller)
    for svc in targets:
        if svc == "poller":
            if poller_was_running:
                start_poller()
        elif SERVICE_MAP[svc]["build"] and svc not in failures:
            SERVICE_MAP[svc]["start"]()


def cmd_start(service: str, clear_queue: bool = False):
    targets = ALL_SERVICES if service == "all" else [service]
    for svc in targets:
        if svc == "poller":
            start_poller(clear_queue=clear_queue)
        else:
            SERVICE_MAP[svc]["start"]()


def cmd_stop(service: str, force: bool = False):
    targets = list(reversed(ALL_SERVICES)) if service == "all" else [service]
    for svc in targets:
        stop_fn = SERVICE_MAP[svc]["stop"]
        if svc == "db":
            stop_fn(force=force)
        else:
            stop_fn()


def cmd_restart(service: str, force: bool = False):
    cmd_stop(service, force=force)
    time.sleep(2)
    cmd_start(service)


def cmd_status(_service: str):
    print()
    print("  FedProspector Service Status")
    print("  ============================")
    for svc in ALL_SERVICES:
        SERVICE_MAP[svc]["check"]()
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="fed_prospector.py",
        description="FedProspector Service Manager",
    )
    parser.add_argument(
        "command",
        choices=["build", "start", "stop", "restart", "status"],
        help="build | start | stop | restart | status",
    )
    parser.add_argument(
        "service",
        nargs="?",
        default="all",
        choices=["all", "db", "api", "ui", "poller"],
        help="all (default) | db | api | ui | poller",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force-kill services instead of graceful shutdown (stop/restart only)",
    )
    parser.add_argument(
        "--clear-queue",
        action="store_true",
        help="Cancel all pending poller requests before starting (start only, poller only)",
    )
    args = parser.parse_args()

    if args.command in ("stop", "restart"):
        {"stop": cmd_stop, "restart": cmd_restart}[args.command](args.service, force=args.force)
    elif args.command == "start":
        cmd_start(args.service, clear_queue=args.clear_queue)
    else:
        {"build": cmd_build, "status": cmd_status}[args.command](args.service)


if __name__ == "__main__":
    main()
