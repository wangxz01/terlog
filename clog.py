#!/usr/bin/env python3
"""
clog - 终端命令历史增强记录工具
将终端中的临时命令历史，转化为可主动保存、可附加上下文、可长期检索的结构化操作日志。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime


# ============================================================
# 颜色系统
# ============================================================

class C:
    """ANSI 颜色常量"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[1;31m'
    GREEN = '\033[1;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    GRAY = '\033[0;37m'
    BG_GREEN = '\033[42m\033[30m'
    BG_RED = '\033[41m\033[30m'


_no_color = False


def colored(text, color):
    """给文本上色"""
    if _no_color:
        return str(text)
    return f"{color}{text}{C.RESET}"


# ============================================================
# 配置
# ============================================================

DEFAULT_DATA_DIR = os.path.expanduser("~/.clog")
DEFAULT_DATA_FILE = "commands.jsonl"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "data_dir": DEFAULT_DATA_DIR,
    "sensitive_words": [
        "password", "passwd", "token", "secret", "api_key",
        "apikey", "private_key", "access_key", "secret_key",
        "credential", "auth_token",
    ],
    "mask_str": "******",
}


def load_config():
    config_path = os.path.join(DEFAULT_DATA_DIR, CONFIG_FILE)
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except (json.JSONDecodeError, IOError):
            pass
    return config


def save_config(config):
    os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
    config_path = os.path.join(DEFAULT_DATA_DIR, CONFIG_FILE)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


# ============================================================
# 数据存储
# ============================================================

def get_data_file(config):
    data_dir = config.get("data_dir", DEFAULT_DATA_DIR)
    return os.path.join(data_dir, DEFAULT_DATA_FILE)


def ensure_data_dir(config):
    data_dir = config.get("data_dir", DEFAULT_DATA_DIR)
    os.makedirs(data_dir, exist_ok=True)


def append_record(record, config):
    ensure_data_dir(config)
    data_file = get_data_file(config)
    with open(data_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_all_records(config):
    data_file = get_data_file(config)
    if not os.path.exists(data_file):
        return []
    records = []
    with open(data_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: 第 {line_num} 行数据格式错误，已跳过", file=sys.stderr)
    return records


# ============================================================
# 上下文信息
# ============================================================

def gather_context():
    return {
        "pwd": os.environ.get("PWD", os.getcwd()),
        "user": os.environ.get("USER", os.getenv("LOGNAME", "unknown")),
        "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "shell": os.environ.get("SHELL", "unknown"),
    }


# ============================================================
# 敏感信息脱敏
# ============================================================

def mask_sensitive(command, config):
    sensitive_words = config.get("sensitive_words", DEFAULT_CONFIG["sensitive_words"])
    mask = config.get("mask_str", "******")
    if not sensitive_words:
        return command

    words_pattern = "|".join(re.escape(w) for w in sensitive_words)
    result = command

    # URL userinfo (http://user:pass@host)
    result = re.sub(r'(https?://)\S+:\S+(@)', rf'\1{mask}\2', result, flags=re.IGNORECASE)
    # --key=value
    result = re.sub(rf'(?i)(--(?:{words_pattern}))\s*(=)\s*\S+', rf'\1\2{mask}', result)
    # --key value
    result = re.sub(rf'(?i)(--(?:{words_pattern}))\s+(\S+)', rf'\1 {mask}', result)
    # KEY=VALUE (如 DB_PASSWORD=xxx, api_key=xxx)
    result = re.sub(rf'(?i)(?<![a-zA-Z])((?:{words_pattern}))\s*=\s*\S+', rf'\1={mask}', result)
    # KEY value (如 token ghp_xxx, password xxx)
    result = re.sub(rf'(?i)(?<![a-zA-Z])((?:{words_pattern}))\s+(\S+)', rf'\1 {mask}', result)

    return result


# ============================================================
# 命令实现
# ============================================================

def _generate_id(config):
    records = read_all_records(config)
    return max((r.get("id", 0) for r in records), default=0) + 1


def cmd_record(args, config):
    commands_raw = args.cmds
    if not commands_raw:
        print("错误: 未检测到要记录的命令。请确保已正确加载 clog 的 shell function。", file=sys.stderr)
        return 1

    commands = [c.strip() for c in commands_raw.split("\n") if c.strip()]
    if not commands:
        print("错误: 未检测到有效命令。", file=sys.stderr)
        return 1

    n = args.n if args.n else 1
    if n > len(commands):
        n = len(commands)
    commands = commands[:n]

    # 脱敏
    masked_commands = []
    has_masked = False
    for cmd in commands:
        masked = mask_sensitive(cmd, config)
        if masked != cmd:
            has_masked = True
        masked_commands.append(masked)

    ctx = gather_context()
    timestamp = datetime.now().isoformat()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    note = args.message or ""

    # 读取终端输出
    output = ""
    if args.output_file and os.path.exists(args.output_file):
        with open(args.output_file, "r", encoding="utf-8", errors="replace") as f:
            output = f.read().strip()

    exit_code = args.exit_code if args.exit_code is not None else None

    record = {
        "id": _generate_id(config),
        "timestamp": timestamp,
        "commands": masked_commands,
        "output": output,
        "exit_code": exit_code,
        "masked": has_masked,
        "pwd": ctx["pwd"],
        "user": ctx["user"],
        "hostname": ctx["hostname"],
        "shell": ctx["shell"],
        "tags": tags,
        "note": note,
    }

    # 清理空值
    record = {k: v for k, v in record.items()
              if v is not None and v != "" and v != [] and v is not False}

    append_record(record, config)

    # 彩色反馈
    print()
    print(colored(f"  已记录 {len(masked_commands)} 条命令", C.GREEN + C.BOLD))

    for i, cmd in enumerate(masked_commands):
        if len(masked_commands) == 1:
            prefix = "  "
        elif i < len(masked_commands) - 1:
            prefix = "  ├── "
        else:
            prefix = "  └── "
        masked_mark = colored(" [已脱敏]", C.YELLOW) if has_masked and masked_commands[i] != commands[i] else ""
        print(f"{prefix}{colored(cmd, C.CYAN)}{masked_mark}")

    if tags:
        print(f"  标签: {colored(', '.join(tags), C.MAGENTA)}")
    if note:
        print(f"  备注: {colored(note, C.GRAY)}")
    if exit_code is not None:
        if exit_code == 0:
            print(f"  状态: {colored('成功', C.GREEN)}")
        else:
            print(f"  状态: {colored(f'失败 (退出码: {exit_code})', C.RED)}")
    if output:
        preview = output.split("\n")[0][:50]
        print(f"  输出: {colored(preview + '...', C.DIM)}")
    print()
    return 0


def cmd_list(args, config):
    records = read_all_records(config)
    if not records:
        print("暂无记录。使用 clog 开始记录命令。")
        return 0

    if args.tag:
        tag_lower = args.tag.lower()
        records = [r for r in records
                   if tag_lower in [t.lower() for t in r.get("tags", [])]]
        if not records:
            print(f"标签 '{args.tag}' 下暂无记录。")
            return 0

    limit = args.limit if args.limit else 20
    total = len(records)
    records = records[-limit:]

    print(f"\n{colored(f'  最近 {len(records)} 条记录 (共 {total} 条)', C.BOLD)}\n")
    _print_grouped_records(records)
    return 0


def cmd_search(args, config):
    records = read_all_records(config)
    if not records:
        print("暂无记录。")
        return 0

    keyword = args.keyword.lower()
    results = []
    for r in records:
        parts = r.get("commands", []) + r.get("tags", []) + [r.get("note", "")]
        searchable = " ".join(str(p) for p in parts).lower()
        if keyword in searchable:
            results.append(r)

    if not results:
        print(f"未找到包含 '{args.keyword}' 的记录。")
        return 0

    limit = args.limit if args.limit else 50
    results = results[-limit:]

    print(f"\n{colored(f'  找到 {len(results)} 条匹配记录', C.BOLD)}\n")
    _print_grouped_records(results)
    return 0


def cmd_tags(args, config):
    records = read_all_records(config)
    if not records:
        print("暂无记录。")
        return 0

    tag_counts = {}
    for r in records:
        for tag in r.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        print("暂无标签。")
        return 0

    print(f"\n{colored('  标签列表', C.BOLD)}\n")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        print(f"  {colored(tag, C.MAGENTA)}  ({colored(str(count), C.YELLOW)} 条记录)")
    return 0


def cmd_show(args, config):
    records = read_all_records(config)
    record = next((r for r in records if r.get("id") == args.id), None)

    if not record:
        print(f"未找到 ID 为 {args.id} 的记录。", file=sys.stderr)
        return 1

    rid = record.get("id", "?")
    ts = record.get("timestamp", "")
    date_str = ts[:10] if len(ts) >= 10 else ts
    time_str = ts[11:19] if len(ts) >= 19 else ""
    commands = record.get("commands", [])
    exit_code = record.get("exit_code")
    tags = record.get("tags", [])
    note = record.get("note", "")
    output = record.get("output", "")

    print(f"\n{colored(f'  记录 #{rid}', C.BOLD)}")
    print(f"  {colored('时间:', C.GRAY)}     {date_str} {time_str}")
    print(f"  {colored('目录:', C.GRAY)}     {record.get('pwd', '')}")
    print(f"  {colored('用户:', C.GRAY)}     {record.get('user', '')}@{record.get('hostname', '')}")
    print(f"  {colored('Shell:', C.GRAY)}    {record.get('shell', '')}")

    # 命令树
    print(f"  {colored('命令:', C.GRAY)}")
    for i, cmd in enumerate(commands):
        if len(commands) == 1:
            prefix = "    "
        elif i < len(commands) - 1:
            prefix = "    ├── "
        else:
            prefix = "    └── "
        print(f"  {prefix}{colored(cmd, C.CYAN)}")

    if tags:
        print(f"  {colored('标签:', C.GRAY)}     {colored(', '.join(tags), C.MAGENTA)}")
    if note:
        print(f"  {colored('备注:', C.GRAY)}     {colored(note, C.GRAY)}")
    if record.get("masked"):
        print(f"  {colored('脱敏:', C.GRAY)}     {colored('是', C.YELLOW)}")

    if exit_code is not None:
        if exit_code == 0:
            status = colored("成功", C.GREEN)
        else:
            status = colored(f"失败 (退出码: {exit_code})", C.RED)
        print(f"  {colored('状态:', C.GRAY)}     {status}")

    # 终端输出
    if output:
        print(f"\n  {colored('─── 终端输出 ───', C.BOLD)}")
        lines = output.split("\n")
        for line in lines[:30]:
            print(f"  {colored(line, C.DIM)}")
        if len(lines) > 30:
            print(f"  {colored(f'... (还有 {len(lines) - 30} 行)', C.DIM)}")

    print()
    return 0


def cmd_delete(args, config):
    records = read_all_records(config)
    new_records = [r for r in records if r.get("id") != args.id]
    if len(new_records) == len(records):
        print(f"未找到 ID 为 {args.id} 的记录。", file=sys.stderr)
        return 1

    data_file = get_data_file(config)
    with open(data_file, "w", encoding="utf-8") as f:
        for r in new_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"已删除记录 #{args.id}。")
    return 0


def cmd_stats(args, config):
    records = read_all_records(config)
    if not records:
        print("暂无记录。")
        return 0

    total = len(records)
    total_cmds = sum(len(r.get("commands", [])) for r in records)
    masked = sum(1 for r in records if r.get("masked"))
    tagged = sum(1 for r in records if r.get("tags"))
    with_output = sum(1 for r in records if r.get("output"))
    failed = sum(1 for r in records if r.get("exit_code") is not None and r["exit_code"] != 0)

    dir_counts = {}
    for r in records:
        d = r.get("pwd", "unknown")
        dir_counts[d] = dir_counts.get(d, 0) + 1

    date_counts = {}
    for r in records:
        ts = r.get("timestamp", "")
        date_str = ts[:10] if ts else "unknown"
        date_counts[date_str] = date_counts.get(date_str, 0) + 1

    print(f"\n{colored('  统计信息', C.BOLD)}\n")
    print(f"  记录次数:   {colored(str(total), C.YELLOW)}")
    print(f"  命令总数:   {colored(str(total_cmds), C.YELLOW)}")
    print(f"  已脱敏:     {colored(str(masked), C.YELLOW)}")
    print(f"  有标签:     {colored(str(tagged), C.YELLOW)}")
    print(f"  含输出:     {colored(str(with_output), C.YELLOW)}")
    print(f"  失败命令:   {colored(str(failed), C.RED) if failed else colored('0', C.GREEN)}")

    print(f"\n  {colored('按日期:', C.BOLD)}")
    for date, count in sorted(date_counts.items(), reverse=True)[:10]:
        bar = colored("█" * min(count, 30), C.GREEN)
        print(f"    {date}  {bar} {count}")

    print(f"\n  {colored('按目录 (Top 5):', C.BOLD)}")
    for d, count in sorted(dir_counts.items(), key=lambda x: -x[1])[:5]:
        short_d = d if len(d) <= 45 else "..." + d[-42:]
        print(f"    {short_d}  {colored(str(count), C.YELLOW)}")
    print()
    return 0


# ============================================================
# 格式化输出 (分组模式)
# ============================================================

def _print_grouped_records(records):
    """每次 clog 调用作为一条记录展示"""
    for r in records:
        rid = r.get("id", "?")
        ts = r.get("timestamp", "")
        date_str = ts[:10] if len(ts) >= 10 else ""
        time_str = ts[11:19] if len(ts) >= 19 else ts
        commands = r.get("commands", [])
        tags = r.get("tags", [])
        note = r.get("note", "")
        exit_code = r.get("exit_code")
        has_output = bool(r.get("output"))

        # 状态标记
        status = ""
        if exit_code is not None:
            if exit_code == 0:
                status = f" {colored('OK', C.GREEN)}"
            else:
                status = f" {colored(f'FAIL({exit_code})', C.RED)}"

        output_mark = f" {colored('[有输出]', C.BLUE)}" if has_output else ""
        cmd_count = f"{len(commands)}条" if len(commands) > 1 else ""
        count_str = f" {colored(cmd_count, C.DIM)}" if cmd_count else ""

        tag_str = f" {colored('[' + ', '.join(tags) + ']', C.MAGENTA)}" if tags else ""
        note_str = f" {colored('-- ' + note, C.GRAY)}" if note else ""

        # 头行: #ID  日期 时间  状态  [标签]  -- 备注
        header = f"  {colored(f'#{rid}', C.YELLOW)}  {colored(date_str + ' ' + time_str, C.GRAY)}{status}{output_mark}{count_str}{tag_str}{note_str}"
        print(header)

        # 命令树
        for i, cmd in enumerate(commands):
            display_cmd = cmd if len(cmd) <= 70 else cmd[:67] + "..."
            if len(commands) == 1:
                print(f"        {colored(display_cmd, C.CYAN)}")
            elif i < len(commands) - 1:
                print(f"        {colored('├──', C.DIM)} {colored(display_cmd, C.CYAN)}")
            else:
                print(f"        {colored('└──', C.DIM)} {colored(display_cmd, C.CYAN)}")

        # 输出预览
        output = r.get("output", "")
        if output:
            first_line = output.strip().split("\n")[0][:60]
            print(f"        {colored('>' + first_line + '...', C.DIM)}")

        print()  # 记录间空行


# ============================================================
# CLI
# ============================================================

_SUBCOMMANDS = {"record", "list", "ls", "search", "s", "tags", "show", "delete", "rm", "del", "stats", "init"}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="clog",
        description="clog - 终端命令历史增强记录工具",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # record
    p = subparsers.add_parser("record", help="记录命令")
    p.add_argument("-n", type=int, default=1, help="记录最近 N 条命令")
    p.add_argument("-t", "--tags", type=str, help="标签，逗号分隔")
    p.add_argument("-m", "--message", type=str, help="备注")
    p.add_argument("--cmds", type=str, default=None, help="命令文本 (shell function 传入)")
    p.add_argument("--output-file", type=str, default=None, help="终端输出文件路径", dest="output_file")
    p.add_argument("--exit-code", type=int, default=None, help="退出码", dest="exit_code")

    # list
    p = subparsers.add_parser("list", aliases=["ls"], help="查看记录列表")
    p.add_argument("--tag", type=str, help="按标签过滤")
    p.add_argument("-n", "--limit", type=int, default=20, help="显示数量")

    # search
    p = subparsers.add_parser("search", aliases=["s"], help="搜索记录")
    p.add_argument("keyword", type=str, help="搜索关键词")
    p.add_argument("-n", "--limit", type=int, default=50, help="显示数量")

    # others
    subparsers.add_parser("tags", help="列出所有标签")
    p = subparsers.add_parser("show", help="显示记录详情")
    p.add_argument("id", type=int, help="记录 ID")
    p = subparsers.add_parser("delete", aliases=["rm", "del"], help="删除记录")
    p.add_argument("id", type=int, help="记录 ID")
    subparsers.add_parser("stats", help="统计信息")
    subparsers.add_parser("init", help="初始化")

    return parser


def main():
    global _no_color

    argv = sys.argv[1:]

    # 检测颜色开关
    if "--no-color" in argv:
        _no_color = True
        argv = [a for a in argv if a != "--no-color"]

    # 自动插入 record 子命令
    if not argv:
        argv = ["record"]
    elif argv[0] not in _SUBCOMMANDS and not argv[0].startswith("-"):
        argv = ["record"] + argv
    elif argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv = ["record"] + argv

    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()

    if args.command == "init":
        ensure_data_dir(config)
        save_config(config)
        print(f"clog 已初始化。")
        print(f"  数据目录: {config['data_dir']}")
        return 0

    dispatch = {
        "record": cmd_record,
        "list": cmd_list, "ls": cmd_list,
        "search": cmd_search, "s": cmd_search,
        "tags": cmd_tags,
        "show": cmd_show,
        "delete": cmd_delete, "rm": cmd_delete, "del": cmd_delete,
        "stats": cmd_stats,
    }
    handler = dispatch.get(args.command)
    if handler:
        return handler(args, config)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
