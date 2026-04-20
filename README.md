# System Info MCP Server

A small [Model Context Protocol](https://modelcontextprotocol.io) server built with FastMCP. It exposes system metrics, process helpers, and file cleanup tools so a client (for example Claude or the MCP Inspector) can query or act on your machine in a controlled way.

## What it provides

**System**

- CPU, memory, disk, and related host information.

**Processes**

- List running processes.
- Find processes using a lot of resources.
- Terminate a process after explicit confirmation.

**Files**

- Scan a directory for large, duplicate, or old files (cleanup candidates).
- Delete a file after explicit confirmation.

**Resource**

- A short cleanup hint at `file://cleanup-report`.

## Requirements

- Python 3.10 or newer
- Dependencies are listed in `requirements.txt` (FastMCP, psutil, and related packages).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate the venv with `source .venv/bin/activate` instead.

## Run the server

From the project root:

```bash
python -m src.server
```

To try it interactively, you can use the MCP Inspector (for example `npx @modelcontextprotocol/inspector python -m src.server`).

## Safety notes

Tools that stop processes or delete files expect a confirmation flag where noted. Leave confirmation off if you want the tool to refuse the action rather than run it by mistake.

## License

See [LICENSE](LICENSE) (MIT).

