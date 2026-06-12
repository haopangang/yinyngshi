---
name: full-stack-engineer
model: "[Qwen3.7-Max](qmodel_latest)"
skills: []
mcpServers: []
additionalPrompt: ""
---

# 阴阳师辅助脚本 - 开发规范

## 项目概述
基于 ADB + OpenCV + PaddleOCR 的阴阳师全自动托管辅助脚本，CLI优先，配置驱动。

## ❗ 核心原则（AI 自主开发项目）

本项目完全由 AI 主导开发，以下原则必须严格遵守：

### 1. 架构稳定性优先
- **禁止因局部功能引发全局重构**：新增功能必须适配现有架构，而不是让架构适配功能
- **分层设计不可突破**：设备层→视觉层→任务层→调度层→通知层，上层可以调用下层，下层绝不可反向依赖上层
- **接口先行**：先定义模块间接口（基类/协议），再实现具体功能
- **新增功能只允许扩展，不允许修改已有接口签名**

### 2. 测试与用户协作
- **可以要求用户配合测试**：当需要真机截图、实际游戏界面图片、或验证真机操作效果时，应主动告知用户需要什么图片/操作
- **明确告知用户需求**：告诉用户需要提供什么截图、放在哪个目录、文件命名规则
- **提供清晰的测试步骤**：给用户明确的操作指导（如“请截取阴阳师主界面截图并保存到 assets/templates/common/main_screen.png”）

### 3. 设计前思考
- 每次开发新功能前，先思考：
  - 这个功能属于哪一层？
  - 是否需要新增接口？还是现有接口已足够？
  - 会不会影响其他模块？如果会，要先和用户确认
  - 这个改动 3 个月后还能稳定工作吗？

## 项目结构约定

```
yinyngshi/
├── pyproject.toml
├── config/
│   ├── default.yaml            # 默认配置
│   └── user_config.yaml.example # 用户配置模板
├── src/
│   ├── __init__.py
│   ├── config.py               # pydantic 配置模型
│   ├── logger.py               # loguru 日志
│   ├── constants.py            # 全局常量
│   ├── device/                 # 设备控制层
│   ├── vision/                 # 视觉识别层
│   ├── tasks/                  # 任务执行层
│   ├── scheduler/              # 调度层
│   └── notify/                 # 通知层
├── assets/                         # ⭐ 所有图片资源统一在此
│   ├── templates/              # 模板图片（用于识别匹配）
│   │   ├── common/             # 通用UI元素（确认/取消/关闭/返回）
│   │   ├── navigation/         # 导航界面（主界面、各入口）
│   │   ├── orochi/             # 御魂副本相关
│   │   ├── awakening/          # 觉醒副本相关
│   │   ├── breakthrough/       # 结界突破相关
│   │   ├── hyakki/             # 百鬼夜行相关
│   │   ├── daily/              # 日常任务相关
│   │   ├── guild/              # 寮任务相关
│   │   └── error/              # 异常弹窗（网络断开/崩溃/更新）
│   ├── screenshots/            # 测试截图（用户提供的真机截图）
│   │   ├── raw/                # 原始截图（未裁剪）
│   │   └── annotated/          # 标注图（标记了坐标/区域）
│   └── README.md               # 图片资源管理规范
├── tests/
│   ├── fixtures/               # 测试固定数据（截图、配置）
│   ├── test_device/
│   ├── test_vision/
│   ├── test_tasks/
│   ├── test_scheduler/
│   └── test_notify/
├── docs/
├── cli.py
└── main.py
```

## 图片资源管理规范（强制）

本项目依赖大量图片进行屏幕识别，图片管理必须规范。

### 目录规则
- **模板图片**：`assets/templates/<功能模块>/<描述性文件名>.png`
- **测试截图**：`assets/screenshots/raw/<场景描述>.png`
- **测试固定数据**：`tests/fixtures/<模块名>/`

### 命名规则
- 全部小写，snake_case
- 格式：`<功能>_<状态/描述>.png`
- 示例：
  - `assets/templates/common/btn_confirm.png` — 确认按钮
  - `assets/templates/common/btn_cancel.png` — 取消按钮
  - `assets/templates/orochi/layer_select.png` — 御魂层数选择
  - `assets/templates/orochi/challenge_btn.png` — 挑战按钮
  - `assets/templates/navigation/main_screen.png` — 主界面
  - `assets/templates/error/network_disconnect.png` — 网络断开弹窗
  - `assets/screenshots/raw/main_screen_1080p.png` — 1080p主界面截图

### 图片要求
- 模板图片必须是 **裁剪后的局部图片**（只包含目标元素，不包含多余背景）
- 格式统一 PNG
- 每个模板目录下必须有 `_manifest.yaml` 文件记录每张图片的用途和匹配参数

### _manifest.yaml 示例
```yaml
# assets/templates/orochi/_manifest.yaml
templates:
  - file: challenge_btn.png
    description: "御魂副本挑战按钮"
    threshold: 0.85
    region: [0.6, 0.8, 1.0, 1.0]  # ROI区域 [x1, y1, x2, y2] 归一化坐标
  - file: layer_select.png
    description: "层数选择界面"
    threshold: 0.8
    region: [0.3, 0.2, 0.7, 0.8]
```

### 用户协作流程（当需要新图片时）
1. 告知用户需要什么截图（明确场景）
2. 告知保存路径和文件名
3. 用户提供后，AI 自动裁剪并生成模板 + 更新 _manifest.yaml

## 技术栈
- Python 3.10+
- uiautomator2（设备控制）
- OpenCV（图像识别）
- ppocr-onnx（OCR）
- APScheduler（定时调度）
- pydantic v2（配置校验）
- loguru（日志）
- Typer（CLI）
- httpx（HTTP通知）

## 代码风格规范
- 使用类型注解（Python 3.10+ 语法：`list[str]` 而非 `List[str]`）
- 日志使用 loguru：`from src.logger import logger`
- 配置通过 pydantic 模型，不直接操作 dict
- 异步操作使用 asyncio（通知发送等IO密集操作）
- 模块间通过依赖注入，避免循环导入
- 使用 `__all__` 控制模块导出

## 新增任务的模板流程

当需要新增一个游戏副本/日常任务时：

1. 在 `src/tasks/` 下创建新文件，如 `new_task.py`
2. 继承 `BaseTask` 基类
3. 实现生命周期方法：
   - `pre_check()`: 检查前置条件（体力、进入条件等）
   - `navigate()`: 从主界面导航到目标界面
   - `run()`: 执行主逻辑循环
   - `on_error(e)`: 异常处理
   - `cleanup()`: 清理，回到主界面
4. 使用 `@register_task` 装饰器注册
5. 在 `config/default.yaml` 中添加默认配置
6. 在 `assets/templates/` 下添加对应的模板图片目录
7. 编写测试用例

```python
# 示例模板
from src.tasks.base import BaseTask, register_task

@register_task("new_dungeon")
class NewDungeonTask(BaseTask):
    name = "新副本"
    priority = 5
    stamina_cost = 6

    def pre_check(self) -> bool:
        return self.check_stamina(self.stamina_cost)

    def navigate(self):
        self.go_to_main()
        self.click_image("navigation/dungeon_entry.png")
        self.wait_scene("dungeon_main")

    def run(self):
        for i in range(self.config.count):
            self.click_image("new_dungeon/challenge.png")
            self.wait_battle_end()
            self.collect_reward()
            logger.info(f"完成第 {i+1}/{self.config.count} 次")

    def on_error(self, e):
        logger.error(f"副本执行异常: {e}")
        self.recovery.handle(e)

    def cleanup(self):
        self.go_to_main()
```

## 测试要求
- 每个模块必须有对应的单元测试
- 使用 pytest 框架
- Mock ADB设备操作（不需要真机即可测试逻辑）
- 模板匹配测试使用固定的测试截图
- 测试覆盖率目标：核心逻辑 >80%

## 命名约定
- 文件名：snake_case（如 `adb_client.py`）
- 类名：PascalCase（如 `OrochiTask`）
- 函数/方法：snake_case（如 `find_image()`）
- 常量：UPPER_SNAKE_CASE（如 `GAME_PACKAGE`）
- 配置键：snake_case（如 `auto_use_sushi`）

## Git 自动管理（强制要求）

本项目为 AI 自主开发项目，所有代码改动必须自动管理 Git 并推送。

### 分支策略
- `main`：稳定主分支，只通过 PR 或确认后合并
- `feature/xxx`：功能开发分支（如 `feature/device-layer`、`feature/vision-engine`）
- `fix/xxx`：修复分支
- `docs/xxx`：文档更新分支

### 强制工作流（每次任务完成后必须执行）
1. **创建/切换分支**：每个 Task 开始前，基于 main 创建对应的 feature 分支
2. **频繁提交**：每完成一个有意义的改动（如完成一个模块、一个文件）就 commit
3. **自动 push**：每次 commit 后立即 `git push origin <branch>`
4. **Commit 消息规范**：中文，格式 `类型: 描述`
   - `feat: 新增御魂副本自动化`
   - `docs: 更新技术方案文档`
   - `fix: 修复设备断连重试逻辑`
   - `refactor: 重构视觉识别模块`
   - `test: 新增配置加载单元测试`
   - `chore: 更新依赖版本`

### Git 操作命令模板
```bash
# 任务开始
git checkout main
git pull origin main
git checkout -b feature/task-name

# 开发过程中频繁提交
git add .
git commit -m "feat: 完成xxx模块"
git push origin feature/task-name

# 任务完成后（如果是最终交付）
git checkout main
git merge feature/task-name
git push origin main
```

### 注意事项
- **绝不跳过 push**：所有 commit 必须推送到远程
- **先 init 仓库**：如果项目还没有 git 仓库，第一步先 `git init` + 设置 remote
- **不要用 force push**：除非明确要求
- **.gitignore 必须到位**：确保 logs/、config/user_config.yaml、__pycache__/ 等不被提交

## 文档要求（强制）

本项目所有改动都必须有对应文档，确保 AI 可持续迭代。

### 文档更新规则
1. **新增模块**：必须在模块目录下创建 README.md 说明模块职责、接口、使用方式
2. **新增功能**：必须更新 docs/PRD.md 的功能列表
3. **架构变更**：必须更新 docs/TECH_DESIGN.md
4. **配置变更**：必须更新 config/default.yaml 的注释 + user_config.yaml.example
5. **API 变更**：必须更新对应的 docstring

### 每个 Python 文件必须包含
- 模块级 docstring（说明文件职责）
- 类级 docstring（说明类的作用）
- 关键函数的 docstring（参数、返回值、异常说明）

### CHANGELOG
- 每个版本迭代维护 `CHANGELOG.md`
- 格式：日期 + 版本号 + 变更列表
