# 阴阳师全自动托管辅助脚本

> AI 自主开发项目 — 基于 ADB + OpenCV + OCR，macOS 通过 USB/WiFi 连接安卓真机，实现阴阳师全日常自动化。

## 功能特性

- **全自动托管** — 定时启动 → 执行全日常 → 自动退出，无需人工干预
- **多副本支持** — 御魂（八岐大蛇）、觉醒、结界突破、百鬼夜行、地域鬼王、石距、秘闻副本等
- **智能停止** — OCR 识别剩余次数、弹窗检测、按钮灰色检测，精准判断任务结束
- **活动模板引擎** — YAML 配置驱动，无需写代码即可快速适配新活动
- **微信通知** — 支持 WxPusher / Server酱 / 企业微信，任务完成、异常告警、每日报告推送
- **人类模拟** — 贝塞尔曲线滑动轨迹 + 随机坐标偏移 + 随机延迟，降低检测风险
- **CLI 快捷操作** — 14 个命令覆盖设备管理、任务执行、调度控制、配置管理全流程

## 安装

### 环境要求

- Python 3.10+
- ADB（Android Debug Bridge）
- 安卓真机（已开启 USB 调试）
- macOS / Linux / Windows

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/yinyngshi.git
cd yinyngshi

# 2. 安装依赖（使用 uv）
uv sync

# 3. 创建用户配置文件
cp config/user_config.yaml.example config/user_config.yaml

# 4. 编辑配置文件，填写设备序列号、通知 Token 等
#    或直接使用 CLI 命令编辑：
uv run yys config edit
```

## 快速开始

```bash
# 1. 查看已连接的设备
uv run yys devices

# 2. 连接设备（USB 或 WiFi）
uv run yys connect <设备序列号>
uv run yys connect 192.168.1.100:5555   # WiFi 连接

# 3. 启动阴阳师
uv run yys start

# 4. 运行单个任务（如御魂副本 30 次）
uv run yys run orochi --count 30

# 5. 运行全部日常任务
uv run yys run-all

# 6. 启动全自动托管（定时调度）
uv run yys daemon
```

## CLI 命令一览

| 命令 | 功能 |
|------|------|
| `yys devices` | 列出已连接的 ADB 设备 |
| `yys connect <serial>` | 连接设备（支持 USB / WiFi） |
| `yys start` | 启动阴阳师 |
| `yys stop` | 退出阴阳师 |
| `yys click <x> <y>` | 点击指定屏幕坐标 |
| `yys swipe <x1> <y1> <x2> <y2>` | 执行滑动操作 |
| `yys screenshot [output]` | 截取当前屏幕并保存 |
| `yys run <task> [-c N]` | 运行指定任务（可指定次数） |
| `yys run-all` | 运行全部日常任务 |
| `yys tasks` | 列出所有已注册任务 |
| `yys daemon [start\|stop]` | 启动/停止调度守护进程 |
| `yys status` | 查看设备状态和今日统计 |
| `yys report` | 生成每日运行报告 |
| `yys config show` | 显示当前完整配置 |
| `yys config edit` | 编辑用户配置文件 |

所有命令均支持 `--device / -d` 参数指定设备，`--verbose` 启用调试日志。

## 配置说明

配置采用**默认配置 + 用户配置覆盖**的机制：

- `config/default.yaml` — 默认配置（请勿直接修改）
- `config/user_config.yaml` — 用户配置，只需填写需要覆盖的项

主要配置项：

| 分类 | 说明 |
|------|------|
| `device` | 设备序列号、ADB 路径 |
| `game` | 游戏包名、启动 Activity |
| `stamina` | 体力管理（自动使用寿司、每日上限） |
| `tasks` | 任务列表（启用/禁用、层数、次数、优先级） |
| `scheduler` | 调度器（启用、起止时间） |
| `notify` | 通知渠道（WxPusher / Server酱 / 企微）及事件 |
| `recovery` | 异常恢复（自动重启、最大重试、超时） |
| `logging` | 日志级别、文件路径、轮转策略 |

## 活动模板

通过编写 YAML 配置文件即可快速适配新活动，无需修改 Python 代码：

1. 复制 `config/events/_example.yaml` 并重命名（如 `spring_event.yaml`）
2. 修改活动名称、步骤、模板图片路径等配置
3. 将活动相关模板图片放入 `assets/templates/events/<活动名>/`
4. 脚本自动发现并加载活动

支持的操作：`click_template`、`click_position`、`wait_template`、`swipe`、`ocr_check`、`click_ocr` 等。

详细配置格式参见 [config/events/README.md](config/events/README.md)。

## 项目结构

```
yinyngshi/
├── cli.py                      # CLI 入口（Typer）
├── main.py                     # 程序主入口
├── pyproject.toml              # 项目配置 & 依赖
├── config/
│   ├── default.yaml            # 默认配置
│   ├── user_config.yaml.example # 用户配置模板
│   └── events/                 # 活动 YAML 配置
├── src/
│   ├── config/                 # 配置加载 & Pydantic 模型
│   ├── device/                 # 设备控制层（ADB、点击、滑动、截图）
│   ├── vision/                 # 视觉识别层（模板匹配、OCR、颜色检测）
│   ├── tasks/                  # 任务执行层（各副本实现 + 活动引擎）
│   ├── scheduler/              # 调度层（APScheduler、体力管理、监控）
│   ├── notify/                 # 通知层（微信推送、企微、Server酱）
│   ├── recovery/               # 异常恢复
│   ├── logger/                 # 日志配置（loguru）
│   └── utils/                  # 工具函数 & 常量
├── assets/
│   └── templates/              # 模板图片（按功能模块分目录）
├── tests/                      # 单元测试
├── docs/                       # 设计文档
└── logs/                       # 运行日志
```

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主语言 |
| uiautomator2 | 安卓设备控制 |
| OpenCV | 图像识别 & 模板匹配 |
| RapidOCR (ONNX) | 文字识别（OCR） |
| APScheduler | 定时任务调度（SQLite 持久化） |
| Pydantic v2 | 配置模型校验 |
| Typer + Rich | CLI 界面 & 终端美化 |
| loguru | 日志管理 |
| httpx | 异步 HTTP（通知推送） |
| NumPy | 数值计算（贝塞尔曲线等） |

## 开发者说明

### 新增任务

1. 在 `src/tasks/` 下创建新文件（如 `new_task.py`）
2. 继承 `BaseTask` 基类，实现 `pre_check()` / `navigate()` / `run()` 方法
3. 使用 `@register_task("task_name")` 装饰器注册
4. 在 `config/default.yaml` 的 `tasks` 列表中添加默认配置
5. 在 `assets/templates/` 下添加对应模板图片

```python
from src.tasks.base import BaseTask, TaskResult
from src.tasks.registry import register_task

@register_task("new_dungeon")
class NewDungeonTask(BaseTask):
    name = "新副本"
    priority = 5
    stamina_cost = 6

    def pre_check(self) -> bool:
        return self.check_stamina(self.stamina_cost)

    def navigate(self) -> bool:
        self.go_to_main()
        return self.click_image("navigation/dungeon_entry.png")

    def run(self) -> TaskResult:
        for i in range(self.config.get("count", 10)):
            self.click_image("new_dungeon/challenge.png")
            # ...
        return TaskResult(success=True, run_count=self.config.get("count", 10))
```

### 分支策略

| 分支 | 用途 |
|------|------|
| `main` | 稳定主分支 |
| `feature/xxx` | 功能开发 |
| `fix/xxx` | Bug 修复 |
| `docs/xxx` | 文档更新 |

Commit 消息格式：`类型: 描述`（如 `feat: 新增御魂副本自动化`）
