---
name: dev-stack
description: "Manage the FedProspect dev stack: start, stop, restart, build, or check status of MySQL, .NET API, and Vite UI. Use when the user says 'start the stack', 'stop mysql', 'restart api', 'is anything running', 'build everything', 'spin up dev', 'tear down the stack', or any variation of managing dev services. Usage: /dev-stack <command> [service]"
argument-hint: "<start|stop|restart|status|build> [all|db|api|ui]"
disable-model-invocation: true
---

# Dev Stack Manager

Manage the local development services (MySQL, C# API, Vite UI).

## Arguments

- `$ARGUMENTS` = `<command> [service]`
- Command: `start`, `stop`, `restart`, `status`, `build`
- Service: `all` (default), `db`, `api`, `ui`

## Commands

```bash
python fed_prospector.py <command> [service]
```

| Command | What It Does |
|---------|-------------|
| `start [service]` | Start service(s). Waits for each to be ready before returning |
| `stop [service]` | Graceful shutdown. Add `--force` for hard kill |
| `restart [service]` | Stop + start |
| `status [service]` | Check what's running and show URLs |
| `build [service]` | Build API (`dotnet build`) and/or UI (`npm run build`) |

## Examples

```bash
python fed_prospector.py start all       # spin up everything
python fed_prospector.py status          # check what's running
python fed_prospector.py restart api     # bounce the API after code changes
python fed_prospector.py build api       # build C# solution
python fed_prospector.py build ui        # npm run build
python fed_prospector.py stop db --force # force-kill MySQL
```

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| MySQL | 3306 | — |
| API | 5056 | http://localhost:5056 |
| UI | 5173 | http://localhost:5173 |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port conflict | `netstat -ano | findstr :<port>` then `taskkill /PID <pid> /F` |
| MySQL won't start | Check data dir exists at `E:/mysql/data`, check disk space, check error log |
| API won't start | Build first (`build api`), ensure MySQL is running |
| UI won't start | Ensure `node_modules` installed (`cd ui && npm install`) |
| Stop hangs | Use `--force` flag: `python fed_prospector.py stop --force` |
