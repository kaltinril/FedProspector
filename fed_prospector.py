#!/usr/bin/env python3
"""FedProspector Service Manager.

Usage:
    python fed_prospector.py <command> [service]

Commands:  build | start | stop | restart | status
Services:  all (default) | db | api | ui
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
MYSQL_ROOT_PASS = "root_2026"
API_URL = "http://localhost:5056"


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


def mysql_admin(*args: str) -> int:
    """Run mysqladmin with root credentials."""
    cmd = [str(MYSQL_BIN / "mysqladmin"), "-u", "root", f"-p{MYSQL_ROOT_PASS}", *args]
    result = subprocess.run(cmd, capture_output=True, timeout=10)
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
            s.bind(("127.0.0.1", port))
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
    if port_in_use(3306):
        print("  [DB]  ERROR: Port 3306 is already in use.")
        print("        Another process may be using this port. Check with: netstat -ano | findstr :3306")
        return
    print("  [DB]  Starting MySQL ...")
    subprocess.Popen(
        f'start "MySQL" /MIN "{mysql_bin_path}" --console --secure-file-priv=',
        shell=True,
    )
    for i in range(30):
        time.sleep(1)
        if mysql_admin("ping") == 0:
            print("  [DB]  MySQL is ready.  (port 3306)")
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


def stop_db():
    if not is_running(MYSQL_EXE):
        print("  [DB]  Not running.")
        return
    print("  [DB]  Shutting down MySQL ...")
    mysql_admin("shutdown")
    print("  [DB]  Stopped.")


def check_db():
    if is_running(MYSQL_EXE):
        print("  [DB]  Running  (port 3306)")
    else:
        print("  [DB]  Stopped")


# -- API --------------------------------------------------------------

def build_api():
    print("  [API] Building (Release) ...")
    result = subprocess.run(
        ["dotnet", "build", str(API_SLN), "-c", "Release", "--verbosity", "quiet"],
        timeout=120,
    )
    if result.returncode == 0:
        print("  [API] Build succeeded.")
        return True
    else:
        print("  [API] Build FAILED.")
        return False


def start_api():
    if is_running(API_EXE):
        print("  [API] Already running.")
        return
    if port_in_use(5056):
        print("  [API] ERROR: Port 5056 is already in use.")
        print("        Another process may be using this port. Check with: netstat -ano | findstr :5056")
        return
    print("  [API] Starting .NET API (no build) ...")
    subprocess.Popen(
        f'start "FedProspector API" /MIN dotnet run --no-build -c Release --project "{API_PROJECT}"',
        shell=True,
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


# -- UI (placeholder) -------------------------------------------------

def build_ui():
    print("  [UI]  Not yet implemented. (Awaiting frontend framework selection)")


def start_ui():
    print("  [UI]  Not yet implemented.")


def stop_ui():
    print("  [UI]  Not yet implemented.")


def check_ui():
    print("  [UI]  Not yet implemented")


# -- Commands ----------------------------------------------------------

SERVICE_MAP = {
    "db":  {"start": start_db,  "stop": stop_db,  "check": check_db,  "build": None},
    "api": {"start": start_api, "stop": stop_api, "check": check_api, "build": build_api},
    "ui":  {"start": start_ui,  "stop": stop_ui,  "check": check_ui,  "build": build_ui},
}

ALL_SERVICES = ["db", "api", "ui"]


def cmd_build(service: str):
    targets = ALL_SERVICES if service == "all" else [service]
    failures = []
    for svc in targets:
        fn = SERVICE_MAP[svc]["build"]
        if fn:
            success = fn()
            if success is False:
                failures.append(svc)
    if failures:
        print(f"\n  Build failed for: {', '.join(failures)}")
        sys.exit(1)


def cmd_start(service: str):
    targets = ALL_SERVICES if service == "all" else [service]
    for svc in targets:
        SERVICE_MAP[svc]["start"]()


def cmd_stop(service: str):
    targets = list(reversed(ALL_SERVICES)) if service == "all" else [service]
    for svc in targets:
        SERVICE_MAP[svc]["stop"]()


def cmd_restart(service: str):
    cmd_stop(service)
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
        choices=["all", "db", "api", "ui"],
        help="all (default) | db | api | ui",
    )
    args = parser.parse_args()

    commands = {
        "build": cmd_build,
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
    }
    commands[args.command](args.service)


if __name__ == "__main__":
    main()
