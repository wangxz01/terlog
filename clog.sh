#!/usr/bin/env bash
# clog.sh - Shell function 定义
#
# 使用方法:
#   source clog.sh
#   clog                   # 记录上一条命令 (自动捕获退出码)
#   clog -n 3              # 记录最近 3 条命令
#   clog -t tag1 -m "备注"  # 带标签和备注
#   crun <命令>            # 运行命令并捕获输出 (之后用 clog 记录)
#   clog list / search / tags / stats / show / delete

_CLOG_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_CLOG_PYTHON="$_CLOG_SCRIPT_DIR/clog.py"
_CLOG_LAST_EXIT=0
_CLOG_LAST_OUTPUT=""
_CLOG_OUTPUT_FILE="/tmp/clog_output_$$"

# ── PROMPT_COMMAND: 追踪每条命令的退出码 ──
_clog_precmd() {
    _CLOG_LAST_EXIT=$?
}

if [[ -z "$PROMPT_COMMAND" ]]; then
    PROMPT_COMMAND="_clog_precmd"
else
    # 不覆盖已有的 PROMPT_COMMAND
    if [[ "$PROMPT_COMMAND" != *"_clog_precmd"* ]]; then
        PROMPT_COMMAND="_clog_precmd; $PROMPT_COMMAND"
    fi
fi

# ── crun: 运行命令并捕获输出 ──
# 用法: crun <命令> [参数...]
# 例如: crun git status
#       crun npm install
crun() {
    if [ $# -eq 0 ]; then
        echo "用法: crun <命令> [参数...]" >&2
        echo "运行命令并捕获输出，之后可用 clog 记录。" >&2
        return 1
    fi

    # 清空上次的输出
    : > "$_CLOG_OUTPUT_FILE"

    # 运行命令，同时输出到终端和临时文件
    "$@" 2>&1 | tee "$_CLOG_OUTPUT_FILE"
    local _pipe_exit=${PIPESTATUS[0]}

    _CLOG_LAST_EXIT=$_pipe_exit
    _CLOG_LAST_OUTPUT=$(cat "$_CLOG_OUTPUT_FILE")

    return $_pipe_exit
}

# ── clog: 主命令 ──
clog() {
    local _subcmds="list ls search s tags show stats init delete rm del"

    for _cmd in $_subcmds; do
        if [ "$1" = "$_cmd" ]; then
            python3 "$_CLOG_PYTHON" "$@"
            return $?
        fi
    done

    # ── 记录模式 ──

    # 解析 -n 参数
    local _n=1 _i
    for _i in $(seq 1 $#); do
        eval "_arg=\${$_i}"
        if [ "$_arg" = "-n" ]; then
            _i=$((_i + 1))
            eval "_n=\${$_i}"
            break
        fi
    done

    # 获取历史命令
    local _hist_cmds
    _hist_cmds=$(fc -l -n -r | head -n "$_n" | awk '{sub(/^[ \t]+/, ""); print}' | tac)

    if [ -z "$_hist_cmds" ]; then
        echo "错误: 无法获取历史命令。请确保 history 功能已启用。" >&2
        return 1
    fi

    # 构建参数
    local _args=(record --cmds "$_hist_cmds" --exit-code "$_CLOG_LAST_EXIT")

    # 如果有输出文件，传递给 Python
    if [ -s "$_CLOG_OUTPUT_FILE" ]; then
        _args+=(--output-file "$_CLOG_OUTPUT_FILE")
    fi

    # 追加用户的额外参数 (-t, -m 等)
    _args+=("$@")

    python3 "$_CLOG_PYTHON" "${_args[@]}"
    local _result=$?

    # 记录后清空输出
    : > "$_CLOG_OUTPUT_FILE"
    _CLOG_LAST_OUTPUT=""

    return $_result
}

# ── 直接执行提示 ──
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "clog.sh 应该被 source 加载，而非直接执行。"
    echo ""
    echo "  source ${BASH_SOURCE[0]}"
    echo ""
    echo "或将以下行添加到 ~/.bashrc:"
    echo "  [ -f ${BASH_SOURCE[0]} ] && source ${BASH_SOURCE[0]}"
fi
