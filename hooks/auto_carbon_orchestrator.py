#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PreInvocation hook for Carbon-Neon Orchestrator (v1.1).
Automatically activates smart "Primary Carbon commands Secondary Neon workers
(with Micro-Edit Fast Lane & Carbon Personal Takeover)" mode whenever the
user's main conversation is running on a Gemini 4 Carbon model.
"""

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
SKILL_PATH = str(PLUGIN_DIR / "skills" / "carbon-neon-orchestrator" / "SKILL.md")

STATE_VERSION = "carbon_v2"

ACTIVATE_SYSTEM_MSG = (
    "[Carbon-Neon Orchestrator 已随 Carbon 模型自动激活]\n"
    "当前主会话正在使用 Gemini 4 Carbon 模型，启用智能「主 Carbon 统筹攻坚 · 副 Neon 主力干活」模式：\n"
    "1. 【默认分工原则】常规工程执行（代码检索、多文件功能开发、重构、写单测、跑构建/Lint、分支合入）一律通过原生 `swarm` 工具派给 Gemini 4 Neon 节点干活"
    "（默认主力 `\"gemini-4-neon-high\"`，复杂逻辑/深审 `\"gemini-4-neon-xhigh\"`，快速侦察/哨兵 `\"gemini-4-neon-medium\"`/`\"low\"`；切勿将模型名传给 `invoke_subagent`/`run_workflow`），"
    "由你（Carbon）负责架构设计、锁定接口契约、划分独占文件边界与终审把关。\n"
    "2. 【微调快车道（仅限同时满足全部 4 条红线时 Carbon 直接秒回/秒改，缺一不可）】\n"
    "   (a) 纯口头问答，或目标文件路径已知（最多 1-2 次只读查看即可定位，无需全库盲搜）；\n"
    "   (b) 最多只改 1 个文件，且新增/修改总行数 ≤ 20 行；\n"
    "   (c) 无需运行耗时构建、单测套件或报错修复循环；\n"
    "   (d) 独立原子修改（改完即全部结束），或用户当次明确要求你亲自直接改。\n"
    "   -> 但凡违反任一条（如 ≥2 个文件、>20 行新代码、需查调用链或需跑测试验证），严禁走快车道，必须派 Neon！\n"
    "3. 【防传话失真】若用户上传了截图/设计稿或有复杂前置上下文，必须在 Brief 中附上图片/参考文件绝对路径让 Neon 直接 `read_file` 查看原图，"
    "或对 `swarm add` 传入 `fork: \"coordinator\"` 继承完整热上下文；终审时 Carbon 需亲自抽查核心改动文件。\n"
    "4. 【高难任务与卡壳熔断：Carbon 亲自上阵】拒绝无脑甩锅：\n"
    "   - 事前预判：遇极高难度核心算法/严密数学物理建模/高精细度单文件视觉创作等 Neon 明显难以胜任的核心灵魂部分，由 Carbon 亲自编写核心内核（外围脚手架与测试仍派 Neon）；\n"
    "   - 事中两振熔断：若某个问题 Neon 连续 2 轮修不好、原地打转或交付质量明显拉胯，立即停止继续派 Neon 盲试，由 Carbon 亲自读取现场并上手修复攻坚！\n"
    "5. 【完整作战规范】首次派发 `swarm` 前请先 `read_file` 阅读 `" + SKILL_PATH + "`（多写并发必开 `workspace: \"share\"`、先合入再 `kill`、首轮末尾单独一行原样输出 `open_board`）。\n"
    "（注：若当前会话本身已是 Swarm Worker 子节点或 Subagent，请忽略本条编排指令，直接完成分配给你的具体任务。）"
)

DEACTIVATE_SYSTEM_MSG = (
    "[Carbon-Neon Orchestrator 已暂停] 检测到当前会话模型已切换离 Gemini 4 Carbon，"
    "退出默认「Carbon 指挥 + Neon 干活」编排约束，恢复当前模型的常规直接执行模式。"
)


def detect_model_from_transcript(transcript_path: str) -> str:
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    try:
        size = os.path.getsize(transcript_path)
        with open(transcript_path, "rb") as f:
            if size > 65536:
                f.seek(size - 65536)
            tail = f.read().decode("utf-8", errors="ignore")
        # Support version numbers containing dots (e.g. "Gemini 4.5 Carbon (High).")
        matches = re.findall(
            r"changed setting `Model Selection` from .*? to ([^\n<]+?)\.(?:\s|\\n|$)",
            tail,
        )
        if matches:
            return matches[-1].strip()
    except Exception:
        return ""
    return ""


def is_subagent_or_swarm_worker(last_user_input: str, transcript_path: str) -> bool:
    # Only check true swarm_worker tags; NEVER filter `startswith("@")` because
    # human users frequently start prompts with `@file` mentions in chat!
    if "<swarm_worker>" in (last_user_input or ""):
        return True
    if transcript_path and os.path.isfile(transcript_path):
        try:
            with open(transcript_path, "rb") as f:
                head = f.read(16384).decode("utf-8", errors="ignore")
            if "<swarm_worker>" in head:
                return True
        except Exception:
            pass
    return False


def load_state(marker: Path) -> tuple[str, int]:
    if not marker.is_file():
        return "", -1
    try:
        raw = marker.read_text(encoding="utf-8").strip()
        if raw.startswith("{"):
            obj = json.loads(raw)
            return str(obj.get("mode") or ""), int(obj.get("steps", -1))
        return raw, -1
    except Exception:
        return "", -1


def save_state(marker: Path, mode: str, steps: int) -> None:
    # Prune state files older than 14 days occasionally so directory never bloats
    try:
        parent = marker.parent
        files = list(parent.glob("*.mode"))
        if len(files) > 200:
            files.sort(key=lambda p: p.stat().st_mtime)
            for old in files[:-100]:
                old.unlink(missing_ok=True)
    except Exception:
        pass
    marker.write_text(
        json.dumps({"mode": mode, "steps": steps}), encoding="utf-8"
    )


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        print("{}")
        return

    payload = json.loads(raw)
    conv_id = str(payload.get("conversationId") or "default")
    model_name = str(payload.get("modelName") or "").strip()
    transcript_path = str(payload.get("transcriptPath") or "").strip()
    last_user_input = str(payload.get("lastUserInput") or "")
    cur_steps = int(payload.get("initialNumSteps") or 0)

    if is_subagent_or_swarm_worker(last_user_input, transcript_path):
        print("{}")
        return

    effective_model = model_name
    if not effective_model or effective_model.lower() in ("auto", "none", "default"):
        fallback = detect_model_from_transcript(transcript_path)
        if fallback:
            effective_model = fallback

    m_lower = effective_model.lower()
    is_carbon = ("carbon" in m_lower) and ("orchestrator" not in m_lower)

    state_dir = Path(
        os.environ.get("PLUGIN_DATA")
        or str(Path(tempfile.gettempdir()) / "agy-carbon-neon-orchestrator-state")
    )
    state_dir.mkdir(parents=True, exist_ok=True)
    conv_hash = hashlib.sha256(conv_id.encode("utf-8")).hexdigest()[:24]
    marker = state_dir / f"{conv_hash}.mode"

    prev_mode, prev_steps = load_state(marker)
    # If conversation underwent `/compact` or step rewind, cur_steps drops below prev_steps
    compacted_or_rewound = (prev_steps >= 0 and cur_steps < prev_steps)

    if is_carbon:
        if prev_mode == STATE_VERSION and not compacted_or_rewound:
            save_state(marker, STATE_VERSION, cur_steps)
            print("{}")
            return
        save_state(marker, STATE_VERSION, cur_steps)
        out = {
            "injectSteps": [
                {
                    "systemMessage": {
                        "systemMessage": ACTIVATE_SYSTEM_MSG
                    }
                }
            ]
        }
        print(json.dumps(out, ensure_ascii=False))
    else:
        if prev_mode.startswith("carbon"):
            save_state(marker, "non_carbon", cur_steps)
            out = {
                "injectSteps": [
                    {
                        "systemMessage": {
                            "systemMessage": DEACTIVATE_SYSTEM_MSG
                        }
                    }
                ]
            }
            print(json.dumps(out, ensure_ascii=False))
        else:
            print("{}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
