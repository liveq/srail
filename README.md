# SRAIL — Self-healing Recursive AI Improvement Loop

> Claude Code가 재부팅/크래시 후 자동으로 살아나고, 실패할 때마다 더 나아지는 자율 복구 MCP 도구

## 개요

장시간 자율 작업 중 재부팅이 필요하거나, Claude Code가 예기치 않게 종료되어도 자동으로 복구합니다.

- Claude Code가 **스스로 켜고 끄는** 도구 (사용자 개입 불필요)
- 재부팅 후 **OS 자동시작**으로 Claude Code 재실행
- 크래시 시 **실패 원인을 프롬프트에 반영**하여 재시도
- **크로스플랫폼**: Linux / macOS / Windows
- 순수 Python, 외부 의존성 없음

## 설치

```bash
git clone https://github.com/YOUR_USERNAME/srail.git ~/srail
claude mcp add srail -- python3 ~/srail/srail.py
```

Claude Code를 재시작하면 `srail_start`, `srail_stop`, `srail_status` 도구가 자동으로 사용 가능해집니다.

## 사용 흐름

```
1. 사용자: "이 작업 해줘, 재부팅 필요하면 알아서 해"

2. Claude Code: 작업 중 재부팅 필요 판단
   → srail_start(prompt="재부팅 후 이어서 할 작업", session_id="...", ...)
   → sudo reboot

3. 시스템 부팅
   → OS 자동시작 → Claude Code 자동 실행 → 이전 작업 재개

4. 작업 중 크래시 발생
   → SRAIL 감지 → 실패 원인 기록 → 프롬프트 개선 → 자동 재시작

5. 작업 완료
   → Claude Code: srail_stop() → 자동시작 해제
```

사용자는 작업 중 `/rc` URL로 스마트폰에서 모니터링/개입 가능.

## MCP 도구

### `srail_start`

자동복구를 등록합니다. 재부팅 전에 호출하세요.

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `prompt` | O | 재시작 시 Claude Code에게 전달할 프롬프트 |
| `session_id` | O | 현재 세션 ID (`--resume`용, 대화 컨텍스트 유지) |
| `work_dir` | X | 작업 디렉토리 (기본: 현재 디렉토리) |
| `permission` | X | `default`, `auto`, `acceptEdits`, `bypassPermissions` (기본: `default`) |
| `terminal` | X | 터미널 지정 (기본: 자동감지). gnome-terminal, konsole, kitty, alacritty, warp, iterm, terminal.app, windows-terminal |
| `max_restarts` | X | 최대 재시작 횟수 (기본: 3) |

### `srail_stop`

자동복구를 해제합니다. 작업 완료 후 호출하세요.

### `srail_status`

현재 SRAIL 상태를 확인합니다. (ARMED/RUNNING/DONE/FAILED/STOPPED)

## 권한 모드

사용자가 원하는 보안 수준을 선택할 수 있습니다:

| 모드 | 설명 |
|---|---|
| `default` | 모든 작업에 사용자 승인 필요 |
| `auto` | 안전한 작업은 자동 승인 |
| `acceptEdits` | 파일 편집은 자동 승인 |
| `bypassPermissions` | 모든 권한 체크 건너뜀 (신뢰된 환경 전용) |

## OS별 자동시작 방식

| OS | 방식 | 등록 위치 |
|---|---|---|
| Linux | XDG Autostart | `~/.config/autostart/srail.desktop` |
| macOS | launchd | `~/Library/LaunchAgents/com.srail.launcher.plist` |
| Windows | Task Scheduler | `schtasks /sc onlogon` |

## 터미널 자동감지

SRAIL은 현재 사용 중인 터미널을 자동으로 감지하여 재부팅 후 같은 터미널에서 Claude Code를 실행합니다.

지원 터미널: gnome-terminal, konsole, kitty, alacritty, tilix, xterm, Warp, iTerm2, Terminal.app, Windows Terminal

## CLI 사용

MCP 없이 직접 사용할 수도 있습니다:

```bash
python3 ~/srail/srail.py status   # 상태 확인
python3 ~/srail/srail.py stop     # 자동시작 해제
```

## 주의사항

- `bypassPermissions` 모드는 모든 권한 체크를 건너뜁니다. 신뢰된 환경에서만 사용하세요.
- 자동 재시작은 최대 횟수(기본 3회)까지만 시도합니다.
- `/rc` 기능은 Claude Code 내장 기능이며, SRAIL과 독립적으로 사용합니다.

## 라이선스

MIT
