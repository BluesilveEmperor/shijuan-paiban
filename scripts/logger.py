"""日志记录器 - 记录运行时日志"""

import os
import sys
import time
from datetime import datetime
from typing import Optional, List


class TaskLogger:
    """任务日志记录器"""

    def __init__(self, log_dir: str, task_name: str = ""):
        self.log_dir = log_dir
        self.task_name = task_name
        self.step_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime('%Y%m%d_%H%M%S')

    def _get_timestamp_ms(self) -> str:
        """获取毫秒级时间戳"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    def _get_agent_info(self) -> dict:
        """获取 AGENT 工具信息"""
        return {
            'tool': 'opencode',
            'version': self._get_tool_version(),
            'model': 'LongCat-2.0 (longcat/LongCat-2.0)',
        }

    def _get_tool_version(self) -> str:
        """获取工具版本号"""
        try:
            import subprocess
            result = subprocess.run(
                ['opencode', '--version'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def start_step(self, step_name: str) -> dict:
        """记录步骤开始，返回步骤上下文"""
        self.step_counter += 1
        step_info = {
            'step_name': step_name,
            'step_number': self.step_counter,
            'start_time': self._get_timestamp_ms(),
            'agent_info': self._get_agent_info(),
            'tool_calls': [],
            'context_summary': {},
            'conversation': [],
        }
        return step_info

    def log_tool_call(self, step_info: dict, tool_name: str, params: str, result: str):
        """记录工具调用"""
        step_info['tool_calls'].append({
            'tool': tool_name,
            'params': params,
            'result': result,
            'timestamp': self._get_timestamp_ms(),
        })

    def log_context(self, step_info: dict, key: str, value: str):
        """记录上下文摘要"""
        step_info['context_summary'][key] = value

    def log_conversation(self, step_info: dict, role: str, content: str):
        """记录对话"""
        step_info['conversation'].append({
            'role': role,
            'content': content,
            'timestamp': self._get_timestamp_ms(),
        })

    def end_step(self, step_info: dict, status: str = "成功", problems: List[str] = None):
        """记录步骤结束，写入日志文件"""
        end_time = datetime.now()
        start_time = datetime.strptime(step_info['start_time'], '%Y-%m-%d %H:%M:%S.%f')
        duration = (end_time - start_time).total_seconds()

        filename = f"{step_info['step_number']:02d}_{self._get_timestamp()}_{step_info['step_name']}.txt"
        filepath = os.path.join(self.log_dir, filename)

        agent = step_info['agent_info']

        content = f"""{'=' * 48}
步骤：{step_info['step_name']}
编号：{step_info['step_number']:02d}
AGENT工具：{agent['tool']}
工具版本：{agent['version']}
大模型：{agent['model']}
开始时间：{step_info['start_time']}
结束时间：{end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}
耗时：{duration:.3f}秒
状态：{status}
{'=' * 48}

--- [工具调用链] ---
"""

        for i, tc in enumerate(step_info['tool_calls'], 1):
            content += f"{i}. {tc['tool']}(\"{tc['params']}\") → {tc['result']}\n"

        content += f"""
--- [关键上下文摘要] ---
"""

        for k, v in step_info['context_summary'].items():
            content += f"- {k}：{v}\n"

        if problems:
            content += f"\n--- [遇到的问题] ---\n"
            for p in problems:
                content += f"- {p}\n"

        content += f"""
--- [完整对话记录] ---
"""

        for conv in step_info['conversation']:
            content += f"[{conv['role']}]: {conv['content']}\n"

        content += "\n"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return filepath
