# SRAIL — Self-healing Recursive AI Improvement Loop

> An MCP tool that lets Claude Code automatically recover after reboot or crash, improving with each failure.
>
> Claude Code가 재부팅/크래시 후 자동으로 살아나고, 실패할 때마다 더 나아지는 자율 복구 MCP 도구

## Overview / 개요

During long autonomous tasks, if a reboot is needed or Claude Code unexpectedly terminates, SRAIL automatically recovers it.

장시간 자율 작업 중 재부팅이 필요하거나, Claude Code가 예기치 않게 종료되어도 자동으로 복구합니다.

- Claude Code **arms and disarms itself** — no user intervention needed
- **OS-level autostart** restores Claude Code after reboot
- On crash, **failure reason is fed back into the prompt** for smarter retries
- **Cross-platform**: Linux / macOS / Windows
- Pure Python, zero external dependencies

## Install / 설치

```bash
git clone https://github.com/liveq/srail.git ~/srail
claude mcp add srail -- python3 ~/srail/srail.py
```

Restart Claude Code and the tools `srail_start`, `srail_stop`, `srail_status` will be available automatically.

## How It Works / 사용 흐름

```
1. User: "Do this task. Reboot if you need to."
   사용자: "이 작업 해줘, 재부팅 필요하면 알아서 해"

2. Claude Code decides a reboot is needed
   → srail_start(prompt="After reboot, continue flashing NAND", session_id="...", ...)
   → sudo reboot

3. System boots up
   → OS autostart triggers → Claude Code relaunches → resumes work
   → OS 자동시작 → Claude Code 자동 실행 → 이전 작업 재개

4. If Claude Code crashes
   → SRAIL detects it → logs failure → improves prompt → auto-restarts
   → SRAIL 감지 → 실패 원인 기록 → 프롬프트 개선 → 자동 재시작

5. Task complete
   → Claude Code calls srail_stop() → autostart removed
```

Monitor remotely via Claude Code's `/rc` URL on your smartphone while away.

## MCP Tools / MCP 도구

### `srail_start`

Arm SRAIL for automatic recovery. Call before rebooting.

자동복구를 등록합니다. 재부팅 전에 호출하세요.

| Parameter | Required | Description |
|---|---|---|
| `prompt` | Yes | Prompt to give Claude Code after restart |
| `session_id` | Yes | Current session ID for `--resume` (preserves conversation context) |
| `work_dir` | No | Working directory (default: current directory) |
| `permission` | No | `default`, `auto`, `acceptEdits`, `bypassPermissions` (default: `default`) |
| `terminal` | No | Terminal to use. Auto-detected if omitted. Options: gnome-terminal, konsole, kitty, alacritty, warp, iterm, terminal.app, windows-terminal |
| `max_restarts` | No | Max restart attempts on crash (default: 3) |

### `srail_stop`

Disarm SRAIL. Call when the task is complete.

자동복구를 해제합니다. 작업 완료 후 호출하세요.

### `srail_status`

Check current SRAIL state. (ARMED / RUNNING / DONE / FAILED / STOPPED)

## Permission Modes / 권한 모드

Users can choose their preferred security level:

| Mode | Description |
|---|---|
| `default` | All actions require user approval / 모든 작업에 사용자 승인 필요 |
| `auto` | Safe actions auto-approved / 안전한 작업은 자동 승인 |
| `acceptEdits` | File edits auto-approved / 파일 편집은 자동 승인 |
| `bypassPermissions` | Skip all permission checks (trusted environments only) / 모든 권한 체크 건너뜀 |

## OS Autostart / OS별 자동시작 방식

| OS | Method | Location |
|---|---|---|
| Linux | XDG Autostart | `~/.config/autostart/srail.desktop` |
| macOS | launchd | `~/Library/LaunchAgents/com.srail.launcher.plist` |
| Windows | Task Scheduler | `schtasks /sc onlogon` |

## Terminal Auto-Detection / 터미널 자동감지

SRAIL detects your current terminal and launches Claude Code in the same terminal after reboot — so you see it right on screen when you return.

Supported: gnome-terminal, konsole, kitty, alacritty, tilix, xterm, Warp, iTerm2, Terminal.app, Windows Terminal

## CLI Usage

You can also use SRAIL directly without MCP:

```bash
python3 ~/srail/srail.py status   # Check state
python3 ~/srail/srail.py stop     # Remove autostart
```

## Caution / 주의사항

- `bypassPermissions` skips all permission checks. Use only in trusted environments.
- Auto-restart is limited to max attempts (default: 3).
- The `/rc` feature is built into Claude Code and works independently of SRAIL.

## Born From / 탄생 배경

Born during a 72-hour SDX55 LTE modem firmware recovery session, where every reboot meant manually restarting Claude Code and re-explaining context.

72시간 SDX55 LTE 모뎀 펌웨어 복구 작업 중, 재부팅마다 수동으로 Claude Code를 다시 시작해야 하는 비효율에서 탄생했습니다.

## License

MIT
