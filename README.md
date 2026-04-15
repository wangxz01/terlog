# clog - 终端命令历史增强记录工具

将终端中的临时命令历史，转化为可主动保存、可附加上下文、可长期检索的结构化操作日志。

---

## 为什么需要 clog？

Bash / Zsh 自带的 `history` 只保存命令文本，缺少上下文：

- 看不到命令执行时间、所在目录、是否成功
- 无法给命令打标签、写备注
- 不方便按关键词或标签检索
- 重要的调试流程、环境配置过程很难复盘

**clog** 在不替代 Shell 的前提下，为命令历史增加「结构化记录 + 上下文补充 + 日志存储 + 后续检索」能力。

---

## 功能特性

- **手动触发记录** — 只记录你想记的命令，不打扰正常工作流
- **终端输出捕获** — 通过 `crun` 运行命令，自动捕获输出和退出码
- **敏感信息脱敏** — 自动检测并脱敏 password / token / API_KEY 等
- **标签 & 备注** — 给记录添加分类标签和文字说明
- **上下文信息** — 自动记录时间、目录、用户、主机名、Shell 类型
- **彩色分组展示** — 每次 `clog` 调用作为一条记录，多命令用树形结构展示
- **关键词搜索** — 按命令内容、标签、备注搜索
- **统计面板** — 按日期、目录统计记录数据

---

## 快速开始

### 安装

```bash
git clone https://github.com/wangxz01/terlog.git
cd terlog
bash install.sh
source ~/.bashrc
```

### 基本用法

```bash
# 记录上一条命令
clog

# 记录最近 3 条命令
clog -n 3

# 带标签和备注
clog -t deploy -m "部署到生产环境"

# 运行命令并捕获输出（之后用 clog 记录）
crun git status
clog -t git

# 查看记录列表
clog list

# 搜索记录
clog search docker

# 查看记录详情（含终端输出）
clog show 1

# 查看所有标签
clog tags

# 查看统计信息
clog stats

# 删除记录
clog delete 1
```

---

## 使用场景

### 场景 1：记录一次关键操作

```bash
git rebase main
clog                              # 自动提取上一条命令，附带时间和目录
```

### 场景 2：记录一组配置流程

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
clog -n 3 -t setup -m "初始化Python项目"
```

### 场景 3：捕获命令输出并记录

```bash
crun npm test                     # 运行命令，输出照常显示
clog -t test -m "单元测试"         # 输出和退出码自动带上
clog show 3                       # 查看时能看到完整输出
```

### 场景 4：排查问题时记录过程

```bash
clog -n 5 -t debug -m "排查登录接口401问题"
# 之后可以随时搜回来
clog search 401
```

---

## 命令一览

| 命令 | 说明 |
|------|------|
| `clog` | 记录上一条命令 |
| `clog -n N` | 记录最近 N 条命令 |
| `clog -t tag1,tag2` | 添加标签 |
| `clog -m "备注"` | 添加备注 |
| `crun <命令>` | 运行命令并捕获输出 |
| `clog list` | 查看记录列表 |
| `clog list --tag deploy` | 按标签过滤 |
| `clog search <关键词>` | 搜索记录 |
| `clog show <ID>` | 查看记录详情（含终端输出） |
| `clog tags` | 列出所有标签 |
| `clog stats` | 统计信息 |
| `clog delete <ID>` | 删除记录 |

---

## 数据存储

- 格式：JSON Lines（每行一条 JSON 记录）
- 位置：`~/.clog/commands.jsonl`
- 配置：`~/.clog/config.json`

每条记录包含：

```json
{
  "id": 1,
  "timestamp": "2026-04-15T12:00:00",
  "commands": ["git status"],
  "output": "On branch main\nnothing to commit",
  "exit_code": 0,
  "pwd": "/home/user/project",
  "user": "user",
  "hostname": "laptop",
  "shell": "/bin/bash",
  "tags": ["git"],
  "note": "查看仓库状态"
}
```

---

## 技术实现

- **Shell function** (`clog.sh`) — 在当前 Shell 环境中提取历史命令、捕获退出码和输出
- **Python 程序** (`clog.py`) — 负责参数解析、数据脱敏、结构化存储和查询检索
- **优先支持 Bash**，后续可扩展到 Zsh

---

## 许可证

MIT License
