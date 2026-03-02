#!/usr/bin/env python3
"""FedProspector Service Manager.

Usage:
    python fed_prospector.py <command> [service]

Commands:  build | start | stop | restart | status
Services:  all (default) | db | api | ui
"""

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MYSQL_BIN = Path(r"D:\mysql\bin")
API_PROJECT = SCRIPT_DIR / "api" / "src" / "FedProspector.Api"
API_SLN = SCRIPT_DIR / "api" / "FedProspector.Api.slnx"
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
    """Check if a URL responds."""
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


# -- DB ---------------------------------------------------------------

def start_db():
    if is_running(MYSQL_EXE):
        print("  [DB]  Already running.")
        return
    print("  [DB]  Starting MySQL ...")
    subprocess.Popen(
        f'start "MySQL" /MIN "{MYSQL_BIN / MYSQL_EXE}" --console --secure-file-priv=',
        shell=True,
    )
    while mysql_admin("ping") != 0:
        time.sleep(1)
    print("  [DB]  MySQL is ready.  (port 3306)")


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
    else:
        print("  [API] Build FAILED.")
        sys.exit(1)


def start_api():
    if is_running(API_EXE):
        print("  [API] Already running.")
        return
    print("  [API] Starting .NET API (no build) ...")
    subprocess.Popen(
        f'start "FedProspector API" /MIN dotnet run --no-build --project "{API_PROJECT}"',
        shell=True,
    )
    for _ in range(30):
        time.sleep(1)
        if url_reachable(f"{API_URL}/health"):
            print(f"  [API] Ready.  Swagger: {API_URL}/swagger")
            print(f"                Health:  {API_URL}/health")
            return
    print("  [API] Started but health check not responding after 30s.")
    print(f"        Check manually: {API_URL}/health")


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
    for svc in targets:
        fn = SERVICE_MAP[svc]["build"]
        if fn:
            fn()


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
