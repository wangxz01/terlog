#!/usr/bin/env bash
# clog 安装脚本
# 自动部署 shell function 到 ~/.bashrc

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOG_SH="$SCRIPT_DIR/clog.sh"
BASHRC="$HOME/.bashrc"

echo "=== clog 安装程序 ==="
echo ""

# 检查 Python3
if ! command -v python3 &>/dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3。"
    exit 1
fi

echo "[1/4] Python3 已就绪: $(python3 --version)"

# 初始化 clog 数据目录
python3 "$SCRIPT_DIR/clog.py" init
echo "[2/4] 数据目录已初始化。"

# 复制 clog.sh 到 ~/.clog/ 方便统一管理
CLOG_TARGET_DIR="$HOME/.clog"
mkdir -p "$CLOG_TARGET_DIR"
cp "$CLOG_SH" "$CLOG_TARGET_DIR/clog.sh"
cp "$SCRIPT_DIR/clog.py" "$CLOG_TARGET_DIR/clog.py"
chmod +x "$CLOG_TARGET_DIR/clog.sh"
chmod +x "$CLOG_TARGET_DIR/clog.py"
echo "[3/4] 文件已复制到 $CLOG_TARGET_DIR/"

# 检查 ~/.bashrc 中是否已配置
MARKER="# >>> clog >>>"
if grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
    echo "[4/4] ~/.bashrc 中已存在 clog 配置，跳过。"
else
    echo "" >> "$BASHRC"
    echo "$MARKER" >> "$BASHRC"
    echo "[ -f \$HOME/.clog/clog.sh ] && source \$HOME/.clog/clog.sh" >> "$BASHRC"
    echo "# <<< clog <<<" >> "$BASHRC"
    echo "[4/4] 已添加 clog 到 ~/.bashrc。"
fi

echo ""
echo "=== 安装完成! ==="
echo ""
echo "现在请运行以下命令使 clog 生效:"
echo "  source ~/.bashrc"
echo ""
echo "或者直接在当前终端加载:"
echo "  source $CLOG_TARGET_DIR/clog.sh"
echo ""
echo "使用方法:"
echo "  clog              记录上一条命令"
echo "  clog -n 3         记录最近 3 条命令"
echo "  clog -t tag1 -m '备注'  带标签和备注记录"
echo "  clog list         查看记录列表"
echo "  clog search 关键词     搜索记录"
echo "  clog tags         查看所有标签"
echo "  clog stats        查看统计信息"
