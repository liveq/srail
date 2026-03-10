#!/usr/bin/env python3
"""
SRAIL — Self-healing Recursive AI Improvement Loop
MCP Server for Claude Code

Registers OS-level autostart so Claude Code survives reboots and crashes.
Pure Python, no external dependencies. Cross-platform (Linux/Mac/Windows).
"""

import json
import sys
import os
import platform
import subprocess
import signal
import time
from pathlib import Path
from datetime import datetime

# ─── Paths ───────────────────────────────────────────────────────────────────

SRAIL_DIR = Path(__file__).parent.resolve()
STATE_DIR = SRAIL_DIR / "state"
PROMPTS_DIR = SRAIL_DIR / "prompts"
HISTORY_DIR = PROMPTS_DIR / "prompt_history"
CONFIG_FILE = SRAIL_DIR / "config.json"
STATE_FILE = STATE_DIR / "state.json"
FAILURE_LOG = STATE_DIR / "failure.log"
LAUNCHER_SCRIPT = SRAIL_DIR / "launcher.py"

for d in [STATE_DIR, PROMPTS_DIR, HISTORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ─── State Management ───────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

def log_failure(reason: str):
    with open(FAILURE_LOG, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {reason}\n")


# ─── Terminal Detection ─────────────────────────────────────────────────────

def detect_terminal() -> str:
    """Detect the current terminal emulator."""
    system = platform.system()

    if system == "Darwin":
        term = os.environ.get("TERM_PROGRAM", "")
        if "iTerm" in term:
            return "iterm"
        if "WarpTerminal" in term or "Warp" in term:
            return "warp"
        return "terminal.app"

    elif system == "Linux":
        # Check environment variables
        env = os.environ
        if any(k for k in env if "WARP" in k.upper()):
            return "warp"
        if "GNOME_TERMINAL_SERVICE" in env or "GNOME_TERMINAL_SCREEN" in env:
            return "gnome-terminal"
        if "KONSOLE_VERSION" in env or "KONSOLE_DBUS_SESSION" in env:
            return "konsole"
        if "KITTY_WINDOW_ID" in env:
            return "kitty"
        if "ALACRITTY_SOCKET" in env or "ALACRITTY_LOG" in env:
            return "alacritty"
        if "TILIX_ID" in env:
            return "tilix"

        # Fallback: check parent process tree
        try:
            ppid = os.getppid()
            while ppid > 1:
                cmdline = Path(f"/proc/{ppid}/cmdline").read_bytes()
                cmd = cmdline.split(b'\x00')[0].decode(errors='ignore').lower()
                for name in ["warp", "gnome-terminal", "konsole", "kitty",
                             "alacritty", "tilix", "xterm", "xfce4-terminal"]:
                    if name in cmd:
                        return name
                stat = Path(f"/proc/{ppid}/stat").read_text()
                ppid = int(stat.split(')')[1].split()[1])
        except Exception:
            pass

        # Last resort
        return "gnome-terminal"

    elif system == "Windows":
        # Check parent process
        try:
            import ctypes
            # Windows Terminal sets WT_SESSION
            if "WT_SESSION" in os.environ:
                return "windows-terminal"
        except Exception:
            pass
        return "windows-terminal"

    return "unknown"


# ─── Terminal Launch Commands ────────────────────────────────────────────────

def get_terminal_launch_cmd(terminal: str, claude_cmd: str) -> list:
    """Return the command to launch Claude Code in a visible terminal window."""
    system = platform.system()

    if system == "Linux":
        cmds = {
            "gnome-terminal": ["gnome-terminal", "--", "bash", "-c", claude_cmd],
            "konsole": ["konsole", "-e", "bash", "-c", claude_cmd],
            "kitty": ["kitty", "bash", "-c", claude_cmd],
            "alacritty": ["alacritty", "-e", "bash", "-c", claude_cmd],
            "tilix": ["tilix", "-e", claude_cmd],
            "xterm": ["xterm", "-e", claude_cmd],
            "xfce4-terminal": ["xfce4-terminal", "-e", claude_cmd],
            "warp": ["warp-terminal", "--", "bash", "-c", claude_cmd],  # Warp Linux
        }
        return cmds.get(terminal, ["gnome-terminal", "--", "bash", "-c", claude_cmd])

    elif system == "Darwin":
        if terminal == "iterm":
            apple_script = f'''
            tell application "iTerm"
                create window with default profile command "bash -c '{claude_cmd}'"
                activate
            end tell'''
            return ["osascript", "-e", apple_script]
        elif terminal == "warp":
            apple_script = f'''
            tell application "Warp"
                activate
                delay 1
                tell application "System Events"
                    keystroke "bash -c '{claude_cmd}'"
                    key code 36
                end tell
            end tell'''
            return ["osascript", "-e", apple_script]
        else:
            apple_script = f'''
            tell application "Terminal"
                do script "bash -c '{claude_cmd}'"
                activate
            end tell'''
            return ["osascript", "-e", apple_script]

    elif system == "Windows":
        cmds = {
            "windows-terminal": ["cmd", "/c", "start", "wt", "cmd", "/k", claude_cmd],
            "powershell": ["cmd", "/c", "start", "powershell", "-NoExit", "-Command", claude_cmd],
            "cmd": ["cmd", "/c", "start", "cmd", "/k", claude_cmd],
        }
        return cmds.get(terminal, ["cmd", "/c", "start", "wt", "cmd", "/k", claude_cmd])

    return ["bash", "-c", claude_cmd]


# ─── Claude Command Builder ─────────────────────────────────────────────────

def find_claude_binary() -> str:
    """Find the Claude Code binary path."""
    # Check common locations
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path.home() / ".claude" / "local" / "claude",
        Path("/usr/local/bin/claude"),
    ]

    # Windows
    if platform.system() == "Windows":
        candidates += [
            Path.home() / "AppData" / "Local" / "Programs" / "claude-code" / "claude.exe",
            Path.home() / ".local" / "bin" / "claude.exe",
        ]

    for c in candidates:
        if c.exists():
            return str(c)

    # Try PATH
    import shutil
    found = shutil.which("claude")
    if found:
        return found

    return "claude"  # hope it's in PATH


def build_claude_cmd(state: dict) -> str:
    """Build the claude command string from saved state."""
    claude = find_claude_binary()
    parts = [claude]

    # Permission mode
    permission = state.get("permission", "default")
    if permission == "bypassPermissions":
        parts.append("--dangerously-skip-permissions")
    elif permission != "default":
        parts.extend(["--permission-mode", permission])

    # Resume session
    session_id = state.get("session_id")
    if session_id:
        parts.extend(["--resume", session_id])

    # Print mode with prompt (non-interactive for automation)
    prompt = state.get("prompt", "이전 작업을 이어서 진행해라.")
    parts.extend(["-p", json.dumps(prompt)])

    return " ".join(parts)


# ─── OS Autostart Registration ───────────────────────────────────────────────

def _create_launcher_script(state: dict):
    """Create the launcher.py that OS autostart will execute."""
    launcher_code = f'''#!/usr/bin/env python3
"""SRAIL Launcher — executed by OS autostart after reboot."""
import json
import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime

SRAIL_DIR = Path("{SRAIL_DIR}")
STATE_FILE = SRAIL_DIR / "state" / "state.json"
FAILURE_LOG = SRAIL_DIR / "state" / "failure.log"

def load_state():
    return json.loads(STATE_FILE.read_text())

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

def log_failure(reason):
    with open(FAILURE_LOG, "a") as f:
        f.write(f"[{{datetime.now().isoformat()}}] {{reason}}\\n")

def update_prompt_with_failure(state, reason):
    """Append failure info to prompt for next attempt."""
    original = state.get("original_prompt", state.get("prompt", ""))
    failures = state.get("failure_count", 0)
    state["prompt"] = (
        f"{{original}}\\n\\n"
        f"[SRAIL] 이전 시도 실패 ({{failures}}회). 마지막 원인: {{reason}}\\n"
        f"실패를 반영하여 다른 접근법을 시도해라."
    )
    return state

def main():
    state = load_state()
    if state.get("status") != "ARMED":
        print("[SRAIL] Not armed, exiting.")
        return

    state["status"] = "RUNNING"
    save_state(state)

    max_restarts = state.get("max_restarts", 3)
    terminal = state.get("terminal", "gnome-terminal")
    work_dir = state.get("work_dir", str(Path.home()))

    # Wait for desktop environment to be ready (Linux/Mac)
    time.sleep(5)

    for attempt in range(max_restarts + 1):
        state = load_state()
        state["failure_count"] = attempt
        state["last_attempt"] = datetime.now().isoformat()
        save_state(state)

        # Build claude command
        claude = state.get("claude_binary", "claude")
        parts = [claude]

        permission = state.get("permission", "default")
        if permission == "bypassPermissions":
            parts.append("--dangerously-skip-permissions")
        elif permission != "default":
            parts.extend(["--permission-mode", permission])

        session_id = state.get("session_id")
        if session_id:
            parts.extend(["--resume", session_id])

        prompt = state.get("prompt", "이전 작업을 이어서 진행해라.")
        parts.extend(["-p", json.dumps(prompt)])

        claude_cmd = " ".join(parts)

        # Launch in terminal
        print(f"[SRAIL] Attempt {{attempt + 1}}/{{max_restarts + 1}}: {{claude_cmd}}")

        try:
            # Run in working directory, visible in terminal
            env = os.environ.copy()
            result = subprocess.run(
                ["bash", "-c", f"cd {{json.dumps(work_dir)}} && {{claude_cmd}}"],
                env=env,
                timeout=None  # no timeout — let it run
            )

            if result.returncode == 0:
                print("[SRAIL] Claude Code exited normally.")
                state = load_state()
                state["status"] = "DONE"
                save_state(state)
                return
            else:
                reason = f"exit code {{result.returncode}}"
                print(f"[SRAIL] Claude Code crashed: {{reason}}")
                log_failure(reason)
                state = load_state()
                state = update_prompt_with_failure(state, reason)
                save_state(state)

        except Exception as e:
            reason = str(e)
            print(f"[SRAIL] Error: {{reason}}")
            log_failure(reason)
            state = load_state()
            state = update_prompt_with_failure(state, reason)
            save_state(state)

        if attempt < max_restarts:
            print(f"[SRAIL] Restarting in 5 seconds...")
            time.sleep(5)

    # All attempts exhausted
    state = load_state()
    state["status"] = "FAILED"
    save_state(state)
    print(f"[SRAIL] Max restarts ({{max_restarts}}) exceeded. Giving up.")

if __name__ == "__main__":
    main()
'''
    LAUNCHER_SCRIPT.write_text(launcher_code)
    LAUNCHER_SCRIPT.chmod(0o755)


def register_autostart(state: dict) -> str:
    """Register OS-level autostart. Returns status message."""
    system = platform.system()
    terminal = state.get("terminal", detect_terminal())
    state["terminal"] = terminal

    _create_launcher_script(state)

    python = sys.executable or "python3"
    launcher_cmd = f"{python} {LAUNCHER_SCRIPT}"

    if system == "Linux":
        return _register_linux(launcher_cmd, terminal, state)
    elif system == "Darwin":
        return _register_macos(launcher_cmd, terminal, state)
    elif system == "Windows":
        return _register_windows(launcher_cmd, terminal, state)
    else:
        return f"Unsupported OS: {system}"


def _register_linux(launcher_cmd: str, terminal: str, state: dict) -> str:
    """Register via systemd user service + XDG autostart."""
    work_dir = state.get("work_dir", str(Path.home()))

    # Terminal launch wrapper
    terminal_cmd = get_terminal_launch_cmd(terminal, launcher_cmd)
    terminal_cmd_str = " ".join(f'"{c}"' if " " in c else c for c in terminal_cmd)

    # XDG autostart (works with GNOME, KDE, XFCE, etc.)
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = autostart_dir / "srail.desktop"
    desktop_file.write_text(f"""[Desktop Entry]
Type=Application
Name=SRAIL - Claude Code Recovery
Comment=Self-healing Recursive AI Improvement Loop
Exec={terminal_cmd_str}
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
StartupNotify=false
""")

    return f"Linux autostart registered (XDG): {desktop_file}\nTerminal: {terminal}"


def _register_macos(launcher_cmd: str, terminal: str, state: dict) -> str:
    """Register via launchd."""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_file = plist_dir / "com.srail.launcher.plist"

    terminal_cmd = get_terminal_launch_cmd(terminal, launcher_cmd)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.srail.launcher</string>
    <key>ProgramArguments</key>
    <array>
        {"".join(f"        <string>{c}</string>{chr(10)}" for c in terminal_cmd)}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{SRAIL_DIR}/state/launcher.log</string>
    <key>StandardErrorPath</key>
    <string>{SRAIL_DIR}/state/launcher.log</string>
</dict>
</plist>"""

    plist_file.write_text(plist_content)
    return f"macOS autostart registered (launchd): {plist_file}\nTerminal: {terminal}"


def _register_windows(launcher_cmd: str, terminal: str, state: dict) -> str:
    """Register via Windows Task Scheduler."""
    python = sys.executable or "python"
    task_name = "SRAIL_Claude_Recovery"

    # Create a batch wrapper
    bat_file = SRAIL_DIR / "launcher.bat"
    bat_file.write_text(f'@echo off\n"{python}" "{LAUNCHER_SCRIPT}"\n')

    terminal_cmd = get_terminal_launch_cmd(terminal, str(bat_file))
    cmd_str = " ".join(terminal_cmd)

    # schtasks command
    schtasks_cmd = [
        "schtasks", "/create", "/f",
        "/tn", task_name,
        "/tr", cmd_str,
        "/sc", "onlogon",
        "/rl", "highest",
        "/delay", "0000:15"  # 15 second delay after logon
    ]

    try:
        subprocess.run(schtasks_cmd, check=True, capture_output=True)
        return f"Windows autostart registered (Task Scheduler): {task_name}\nTerminal: {terminal}"
    except subprocess.CalledProcessError as e:
        return f"Windows registration failed: {e.stderr.decode()}"
    except FileNotFoundError:
        return f"Windows batch file created at {bat_file}. Manual Task Scheduler registration needed."


def unregister_autostart() -> str:
    """Remove OS-level autostart."""
    system = platform.system()
    messages = []

    if system == "Linux":
        desktop_file = Path.home() / ".config" / "autostart" / "srail.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
            messages.append(f"Removed: {desktop_file}")

    elif system == "Darwin":
        plist_file = Path.home() / "Library" / "LaunchAgents" / "com.srail.launcher.plist"
        if plist_file.exists():
            subprocess.run(["launchctl", "unload", str(plist_file)], capture_output=True)
            plist_file.unlink()
            messages.append(f"Removed: {plist_file}")

    elif system == "Windows":
        task_name = "SRAIL_Claude_Recovery"
        try:
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                check=True, capture_output=True
            )
            messages.append(f"Removed task: {task_name}")
        except Exception:
            pass

        bat_file = SRAIL_DIR / "launcher.bat"
        if bat_file.exists():
            bat_file.unlink()
            messages.append(f"Removed: {bat_file}")

    # Clean state
    state = load_state()
    state["status"] = "STOPPED"
    save_state(state)

    if LAUNCHER_SCRIPT.exists():
        LAUNCHER_SCRIPT.unlink()
        messages.append(f"Removed: {LAUNCHER_SCRIPT}")

    return "\n".join(messages) if messages else "No autostart entries found."


# ─── MCP Server (JSON-RPC over stdio) ───────────────────────────────────────

class MCPServer:
    """Minimal MCP server implementing JSON-RPC over stdio."""

    TOOLS = [
        {
            "name": "srail_start",
            "description": (
                "Register SRAIL autostart for Claude Code recovery after reboot or crash. "
                "Call this before executing a reboot command. "
                "Claude Code will automatically restart after reboot with the given prompt."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to give Claude Code after restart. Describe what to continue doing."
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Current Claude Code session ID for --resume. Pass your session ID to preserve conversation context."
                    },
                    "work_dir": {
                        "type": "string",
                        "description": "Working directory for Claude Code. Defaults to current directory."
                    },
                    "permission": {
                        "type": "string",
                        "enum": ["default", "auto", "acceptEdits", "bypassPermissions"],
                        "description": "Permission mode. 'default' requires user approval, 'bypassPermissions' skips all permission checks. Default: 'default'"
                    },
                    "terminal": {
                        "type": "string",
                        "description": "Terminal to launch in. Auto-detected if not specified. Options: gnome-terminal, konsole, kitty, alacritty, warp, iterm, terminal.app, windows-terminal"
                    },
                    "max_restarts": {
                        "type": "integer",
                        "description": "Maximum restart attempts on crash. Default: 3"
                    }
                },
                "required": ["prompt", "session_id"]
            }
        },
        {
            "name": "srail_stop",
            "description": (
                "Unregister SRAIL autostart. Call this when the task is complete "
                "and automatic recovery is no longer needed."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "srail_status",
            "description": "Check current SRAIL status, including whether autostart is armed and failure history.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]

    def __init__(self):
        self.running = True

    def handle_request(self, request: dict) -> dict:
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "srail", "version": "2.0.0"}
            })

        elif method == "notifications/initialized":
            return None  # no response for notifications

        elif method == "tools/list":
            return self._response(req_id, {"tools": self.TOOLS})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            return self._handle_tool_call(req_id, tool_name, arguments)

        elif method == "ping":
            return self._response(req_id, {})

        else:
            return self._error(req_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, req_id, tool_name: str, args: dict) -> dict:
        try:
            if tool_name == "srail_start":
                result = self._tool_start(args)
            elif tool_name == "srail_stop":
                result = self._tool_stop()
            elif tool_name == "srail_status":
                result = self._tool_status()
            else:
                return self._error(req_id, -32602, f"Unknown tool: {tool_name}")

            return self._response(req_id, {
                "content": [{"type": "text", "text": result}]
            })
        except Exception as e:
            return self._response(req_id, {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            })

    def _tool_start(self, args: dict) -> str:
        prompt = args["prompt"]
        session_id = args["session_id"]
        work_dir = args.get("work_dir", os.getcwd())
        permission = args.get("permission", "default")
        terminal = args.get("terminal")
        max_restarts = args.get("max_restarts", 3)

        # Detect terminal if not specified
        if not terminal:
            terminal = detect_terminal()

        # Find claude binary
        claude_binary = find_claude_binary()

        # Build state
        state = {
            "status": "ARMED",
            "prompt": prompt,
            "original_prompt": prompt,
            "session_id": session_id,
            "work_dir": work_dir,
            "permission": permission,
            "terminal": terminal,
            "max_restarts": max_restarts,
            "claude_binary": claude_binary,
            "armed_at": datetime.now().isoformat(),
            "failure_count": 0
        }
        save_state(state)

        # Register OS autostart
        result = register_autostart(state)

        return (
            f"SRAIL armed successfully.\n"
            f"{result}\n"
            f"Session: {session_id}\n"
            f"Permission: {permission}\n"
            f"Max restarts: {max_restarts}\n"
            f"Claude binary: {claude_binary}\n\n"
            f"You can now safely reboot. Claude Code will restart automatically."
        )

    def _tool_stop(self) -> str:
        result = unregister_autostart()
        return f"SRAIL disarmed.\n{result}"

    def _tool_status(self) -> str:
        state = load_state()
        if not state:
            return "SRAIL is not configured. No state file found."

        status = state.get("status", "UNKNOWN")
        lines = [
            f"Status: {status}",
            f"Terminal: {state.get('terminal', 'not set')}",
            f"Permission: {state.get('permission', 'not set')}",
            f"Session ID: {state.get('session_id', 'not set')}",
            f"Work dir: {state.get('work_dir', 'not set')}",
            f"Max restarts: {state.get('max_restarts', 3)}",
            f"Failure count: {state.get('failure_count', 0)}",
            f"Armed at: {state.get('armed_at', 'N/A')}",
            f"Last attempt: {state.get('last_attempt', 'N/A')}",
        ]

        # Show recent failures
        if FAILURE_LOG.exists():
            failures = FAILURE_LOG.read_text().strip().split("\n")[-5:]
            if failures and failures[0]:
                lines.append("\nRecent failures:")
                lines.extend(f"  {f}" for f in failures)

        return "\n".join(lines)

    def _response(self, req_id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    def run(self):
        """Main loop: read JSON-RPC from stdin, write responses to stdout."""
        # Unbuffered output
        sys.stdout = open(sys.stdout.fileno(), 'w', buffering=1)

        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                response = self.handle_request(request)

                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError as e:
                sys.stderr.write(f"[SRAIL] JSON decode error: {e}\n")
            except KeyboardInterrupt:
                break
            except Exception as e:
                sys.stderr.write(f"[SRAIL] Error: {e}\n")


# ─── CLI Interface ───────────────────────────────────────────────────────────

def cli_main():
    """CLI interface for manual use."""
    if len(sys.argv) < 2:
        print("Usage: srail.py [serve|status|stop]")
        print("  serve  — Run as MCP server (stdio)")
        print("  status — Show current state")
        print("  stop   — Unregister autostart")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "serve":
        server = MCPServer()
        server.run()
    elif cmd == "status":
        state = load_state()
        if state:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print("No state found.")
    elif cmd == "stop":
        print(unregister_autostart())
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_main()
    else:
        # Default: run as MCP server
        server = MCPServer()
        server.run()
