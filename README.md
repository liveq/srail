# SRAIL — Claude Code MCP Server for Auto-Recovery

# SRAIL — Claude Code 자동 복구 MCP 서버

**Self-healing Recursive AI Improvement Loop**

> A Model Context Protocol (MCP) server that lets Claude Code automatically recover after reboot or crash, learning from each failure. Pure Python, cross-platform, zero dependencies.
>
> 재부팅이나 크래시 후 Claude Code를 자동으로 복구하는 MCP 서버. 실패할 때마다 학습하여 더 나은 재시도. 순수 Python, 크로스플랫폼, 외부 의존성 없음.

---

## Overview / 개요

When Claude Code is running long autonomous tasks (firmware flashing, large migrations, multi-step builds), a reboot or unexpected crash shouldn't kill the whole workflow. SRAIL is an MCP server that Claude Code uses to **register itself for automatic recovery** — it arms before reboot, and the OS brings it back.

장시간 자율 작업(펌웨어 복구, 대규모 마이그레이션, 멀티스텝 빌드 등) 중 재부팅이나 크래시가 발생해도 작업이 중단되지 않습니다. SRAIL은 Claude Code가 **스스로 자동 복구를 등록하는** MCP 서버입니다.

- **MCP 통합 / MCP integration** — `claude mcp add`로 설치, Claude Code가 자동으로 도구 인식
- **자기 관리 / Self-managed** — Claude Code가 스스로 켜고 끔. 사용자 개입 불필요
- **OS 자동시작 / OS-level autostart** — systemd (Linux) / launchd (macOS) / 작업 스케줄러 (Windows)
- **크래시 복구 / Crash recovery** — 실패 원인을 프롬프트에 반영하여 더 나은 재시도
- **크로스플랫폼 / Cross-platform** — Linux / macOS / Windows
- **무의존성 / Zero dependencies** — 순수 Python, pip 설치 불필요

## Install / 설치

```bash
git clone https://github.com/liveq/srail.git ~/srail
claude mcp add srail -- python3 ~/srail/srail.py
```

Claude Code를 재시작하면 `srail_start`, `srail_stop`, `srail_status` 도구가 자동으로 사용 가능합니다.

Restart Claude Code and the tools will be available automatically.

## How It Works / 사용 흐름

```
1. User: "Do this task. Reboot if you need to."
   사용자: "이 작업 해줘, 재부팅 필요하면 알아서 해"

2. Claude Code decides a reboot is needed
   Claude Code가 재부팅이 필요하다고 판단
   → srail_start(prompt="After reboot, continue the task", session_id="...", ...)
   → sudo reboot

3. System boots up / 시스템 부팅
   → OS autostart → Claude Code relaunches → resumes work
   → OS 자동시작 → Claude Code 자동 실행 → 이전 작업 재개

4. If Claude Code crashes / 크래시 발생 시
   → SRAIL detects → logs failure → improves prompt → auto-restarts
   → SRAIL 감지 → 실패 기록 → 프롬프트 개선 → 자동 재시작

5. Task complete / 작업 완료
   → Claude Code calls srail_stop() → autostart removed
   → Claude Code가 srail_stop() 호출 → 자동시작 해제
```

Monitor remotely via Claude Code's `/rc` URL on your smartphone.

외출 중에는 Claude Code의 `/rc` URL로 스마트폰에서 모니터링/개입 가능.

## MCP Tools / MCP 도구

### `srail_start` — 자동복구 등록 / Arm recovery

Call before rebooting. 재부팅 전에 호출.

| Parameter / 파라미터 | Required / 필수 | Description / 설명 |
|---|---|---|
| `prompt` | Yes | 재시작 시 프롬프트 / Prompt after restart |
| `session_id` | Yes | 세션 ID (`--resume`용) / Session ID for context preservation |
| `work_dir` | No | 작업 디렉토리 / Working directory |
| `permission` | No | 권한 모드: `default`, `auto`, `acceptEdits`, `bypassPermissions` |
| `terminal` | No | 터미널 지정 (미지정 시 자동감지) / Terminal override |
| `max_restarts` | No | 최대 재시작 횟수 (기본: 3) / Max crash retries |

### `srail_stop` — 자동복구 해제 / Disarm recovery

작업 완료 후 호출. Call when done.

### `srail_status` — 상태 확인 / Check state

ARMED / RUNNING / DONE / FAILED / STOPPED

## Permission Modes / 권한 모드

사용자가 보안 수준을 선택할 수 있습니다. Users choose their security level:

| Mode / 모드 | Description / 설명 |
|---|---|
| `default` | 모든 작업에 사용자 승인 필요 / All actions need approval |
| `auto` | 안전한 작업은 자동 승인 / Safe actions auto-approved |
| `acceptEdits` | 파일 편집 자동 승인 / File edits auto-approved |
| `bypassPermissions` | 모든 권한 건너뜀 (신뢰 환경 전용) / Skip all checks (trusted only) |

## OS Autostart / OS별 자동시작

| OS | Method / 방식 | Location / 위치 |
|---|---|---|
| Linux | XDG Autostart | `~/.config/autostart/srail.desktop` |
| macOS | launchd | `~/Library/LaunchAgents/com.srail.launcher.plist` |
| Windows | 작업 스케줄러 / Task Scheduler | `schtasks /sc onlogon` |

## Terminal Auto-Detection / 터미널 자동감지

SRAIL detects your current terminal and launches Claude Code in the same one after reboot.

현재 사용 중인 터미널을 자동 감지하여 재부팅 후 같은 터미널에서 Claude Code를 실행합니다.

gnome-terminal, konsole, kitty, alacritty, tilix, xterm, Warp, iTerm2, Terminal.app, Windows Terminal

## CLI Usage / CLI 사용

MCP 없이 직접 사용 가능. Also usable without MCP:

```bash
python3 ~/srail/srail.py status   # 상태 확인 / Check state
python3 ~/srail/srail.py stop     # 자동시작 해제 / Remove autostart
```

## Caution / 주의사항

- `bypassPermissions`는 모든 권한 체크를 건너뜁니다. 신뢰된 환경에서만 사용하세요.
- `bypassPermissions` skips all permission checks. Use only in trusted environments.
- 자동 재시작은 최대 횟수(기본 3회)까지만 시도합니다. / Auto-restart limited to max attempts (default: 3).
- `/rc`는 Claude Code 내장 기능이며 SRAIL과 독립적입니다. / `/rc` is built into Claude Code, independent of SRAIL.

## Born From / 탄생 배경

Born during a 72-hour SDX55 LTE modem firmware recovery session, where every reboot meant manually restarting Claude Code and losing context.

72시간 SDX55 LTE 모뎀 펌웨어 복구 작업 중, 재부팅마다 Claude Code를 수동으로 다시 시작하고 컨텍스트를 잃어야 하는 비효율에서 탄생했습니다.

## License

MIT
