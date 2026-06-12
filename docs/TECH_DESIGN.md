# 阴阳师辅助脚本 — 技术方案设计

> 版本：v1.0 | 最后更新：2026-06-12

---

## 目录

- [1. 系统架构概览](#1-系统架构概览)
- [2. 技术选型与理由](#2-技术选型与理由)
- [3. 核心模块设计](#3-核心模块设计)
  - [3.1 设备控制层](#31-设备控制层)
  - [3.2 视觉识别层](#32-视觉识别层)
  - [3.3 任务执行层](#33-任务执行层)
  - [3.4 调度层](#34-调度层)
  - [3.5 通知层](#35-通知层)
  - [3.6 异常恢复机制](#36-异常恢复机制)
- [4. 数据流图](#4-数据流图)
- [5. 配置管理方案](#5-配置管理方案)
- [6. 性能与稳定性设计](#6-性能与稳定性设计)
- [7. 借鉴的开源项目](#7-借鉴的开源项目)
- [8. 目录结构总览](#8-目录结构总览)

---

## 1. 系统架构概览

```
                         ┌─────────────────────┐
                         │     CLI 入口层       │
                         │  (Typer / 命令解析)  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      调度层          │
                         │ (APScheduler/cron)   │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │  任务执行层   │ │  任务执行层   │ │  任务执行层   │
           │ (御魂副本)   │ │ (每日任务)   │ │ (寮突破)     │
           └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                  │                │                 │
                  └────────────────┼─────────────────┘
                                   ▼
                         ┌─────────────────────┐
                         │     视觉识别层       │
                         │ (OpenCV + OCR + HSV) │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   设备控制层 (ADB)   │
                         │ (uiautomator2)       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Android 设备/模拟器 │
                         └─────────────────────┘

  横切关注点：
  ┌────────────────────────────────────────────┐
  │  通知层 (WxPusher)  │  日志 (loguru)       │
  │  配置管理 (YAML+pydantic)  │  异常恢复     │
  └────────────────────────────────────────────┘
```

### 分层职责

| 层级 | 职责 | 依赖方向 |
|------|------|---------|
| CLI 入口层 | 命令解析、参数校验、用户交互 | → 调度层 |
| 调度层 | 定时触发、任务规划、体力管理 | → 任务层 |
| 任务执行层 | 具体游戏任务的流程控制 | → 视觉层、设备层 |
| 视觉识别层 | 截图分析、场景判断、OCR | → 设备层 |
| 设备控制层 | ADB通信、点击/滑动、截图 | → Android设备 |
| 通知层（横切） | 结果推送、异常告警 | 被各层调用 |

---

## 2. 技术选型与理由

| 领域 | 选择 | 理由 | 备选方案 |
|------|------|------|---------|
| **ADB 控制库** | `uiautomator2` | 功能最全面：点击/滑动/截图/input 一体化；Python原生；社区活跃 | `adb-shell`（轻量但功能少）、`scrcpy`（延迟低但集成复杂） |
| **图像识别** | `OpenCV` 模板匹配 | 速度快（单帧 <50ms）、准确率高、多尺度支持好；C底层 | `Pillow`（功能弱）、`pyautogui`（桌面端不适用） |
| **OCR** | `rapidocr-onnxruntime`（ppocr-onnx） | 中文识别精度最高；ONNX Runtime 推理无需安装 PaddlePaddle；模型小 | `Tesseract`（中文差）、`EasyOCR`（速度慢） |
| **配置管理** | `YAML` + `pydantic v2` | YAML 人类可读可编辑；pydantic 提供类型校验、默认值、序列化 | `TOML`（生态弱）、`JSON`（不可注释） |
| **任务调度** | `APScheduler` | 支持 CronTrigger / IntervalTrigger；可持久化到 SQLite；任务可动态增删 | `schedule`（功能简单）、`celery`（过重） |
| **CLI 框架** | `Typer` | 自动生成 help；类型提示即参数校验；支持子命令嵌套 | `Click`（样板代码多）、`argparse`（原始） |
| **日志** | `loguru` | 零配置彩色输出；自动轮转；异常 traceback 美化；sink 机制灵活 | `logging`（配置繁琐）、`structlog`（过重） |
| **通知推送** | `WxPusher` + `httpx` | 微信直达；免费额度充足；httpx 异步支持好 | `Server酱`（收费）、`企微机器人`（需企业认证） |
| **Python 版本** | `3.11+` | `TaskGroup` 异步原生支持；`tomllib` 内置；性能提升 | `3.10`（可用但无新特性） |
| **包管理** | `uv` | 极快的依赖解析和安装；兼容 pip；lockfile 支持 | `poetry`（慢）、`pip`（无lock） |

---

## 3. 核心模块设计

### 3.1 设备控制层

**职责**：封装所有与 Android 设备的 ADB 交互，对上层屏蔽设备差异。

#### 3.1.1 连接管理

```
连接策略：
  1. 优先 USB 连接（稳定低延迟）
  2. 回退 WiFi 连接（ADB TCP/IP 模式，端口 5555）
  3. 心跳检测：每 30s 发送 `device.info` 探活
  4. 自动重连：检测到断开后，指数退避重试（1s → 2s → 4s → 最大30s）
```

#### 3.1.2 操作控制

| 操作 | 实现 | 防检测策略 |
|------|------|-----------|
| 点击 | `d.click(x, y)` | ±5px 随机偏移 + 10~50ms 随机延迟 |
| 长按 | `d.long_click(x, y, duration)` | duration 加 ±100ms 随机 |
| 滑动 | 贝塞尔曲线路径生成 | 控制点随机化，速度非线性 |
| 截图 | `d.screenshot(format="opencv")` | 直接返回 numpy array，避免磁盘IO |
| 输入 | `d.send_keys(text)` | 逐字符输入，间隔 50~150ms |

#### 3.1.3 应用管理

- **启动**：`d.app_start("com.netease.onmyoji")`，等待启动完成（检测进程+首帧渲染）
- **退出**：`d.app_stop("com.netease.onmyoji")`，确认进程已终止
- **进程检测**：轮询 `d.app_current()` 判断游戏是否在前台

#### 3.1.4 代码示例

```python
# yys/device/controller.py
import random
import time
import uiautomator2 as u2
from loguru import logger

class DeviceController:
    """设备控制器：封装 ADB 操作"""

    PACKAGE = "com.netease.onmyoji"

    def __init__(self, serial: str | None = None):
        self.serial = serial
        self.device: u2.Device | None = None

    def connect(self) -> None:
        """连接设备，优先 USB，回退 WiFi"""
        try:
            self.device = u2.connect(self.serial) if self.serial else u2.connect()
            info = self.device.info  # 心跳验证
            logger.info(f"已连接设备: {self.device.serial} ({info['displayWidth']}x{info['displayHeight']})")
        except Exception as e:
            logger.error(f"设备连接失败: {e}")
            raise

    def click(self, x: int, y: int, offset: int = 5) -> None:
        """带随机偏移的点击，模拟人类操作"""
        rx = x + random.randint(-offset, offset)
        ry = y + random.randint(-offset, offset)
        time.sleep(random.uniform(0.01, 0.05))
        self.device.click(rx, ry)
        logger.debug(f"点击 ({rx}, {ry})")

    def swipe_bezier(self, sx: int, sy: int, ex: int, ey: int, steps: int = 20) -> None:
        """贝塞尔曲线滑动"""
        import numpy as np
        # 随机控制点
        cp1 = (sx + (ex - sx) * 0.3 + random.randint(-30, 30),
                sy + (ey - sy) * 0.1 + random.randint(-30, 30))
        cp2 = (sx + (ex - sx) * 0.7 + random.randint(-30, 30),
                sy + (ey - sy) * 0.9 + random.randint(-30, 30))
        t = np.linspace(0, 1, steps)
        # 三次贝塞尔
        xs = (1-t)**3 * sx + 3*(1-t)**2*t * cp1[0] + 3*(1-t)*t**2 * cp2[0] + t**3 * ex
        ys = (1-t)**3 * sy + 3*(1-t)**2*t * cp1[1] + 3*(1-t)*t**2 * cp2[1] + t**3 * ey
        self.device.swipe_points(list(zip(xs.astype(int), ys.astype(int))), 0.05)

    def screenshot(self):
        """截图并返回 numpy array (BGR)"""
        return self.device.screenshot(format="opencv")

    def ensure_game_foreground(self) -> bool:
        """确保游戏在前台，否则启动"""
        current = self.device.app_current()
        if current["package"] == self.PACKAGE:
            return True
        logger.warning("游戏不在前台，正在启动...")
        self.device.app_start(self.PACKAGE, wait=True)
        time.sleep(5)  # 等待加载
        return True
```

---

### 3.2 视觉识别层

**职责**：分析游戏截图，识别当前场景、UI元素、文字信息，为任务层提供决策依据。

#### 3.2.1 模板匹配

```python
# yys/vision/matcher.py
import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path

@dataclass
class MatchResult:
    found: bool
    x: int = 0          # 匹配中心 x
    y: int = 0          # 匹配中心 y
    confidence: float = 0.0
    scale: float = 1.0

class TemplateMatcher:
    """多尺度模板匹配器"""

    def __init__(self, template_dir: str = "assets/templates"):
        self.template_dir = Path(template_dir)
        self._cache: dict[str, np.ndarray] = {}

    def load_template(self, name: str) -> np.ndarray:
        if name not in self._cache:
            path = self.template_dir / f"{name}.png"
            self._cache[name] = cv2.imread(str(path), cv2.IMREAD_COLOR)
        return self._cache[name]

    def match(
        self,
        screenshot: np.ndarray,
        template_name: str,
        threshold: float = 0.85,
        roi: tuple[int, int, int, int] | None = None,
        scales: list[float] | None = None,
    ) -> MatchResult:
        """
        多尺度模板匹配
        :param roi: (x, y, w, h) 感兴趣区域，缩小搜索范围
        :param scales: 缩放比例列表，适配不同分辨率
        """
        template = self.load_template(template_name)
        search_area = screenshot
        offset_x, offset_y = 0, 0

        if roi:
            x, y, w, h = roi
            search_area = screenshot[y:y+h, x:x+w]
            offset_x, offset_y = x, y

        if scales is None:
            scales = [0.8, 0.9, 1.0, 1.1, 1.2]

        best_val, best_loc, best_scale = 0.0, (0, 0), 1.0

        for scale in scales:
            resized = cv2.resize(template, None, fx=scale, fy=scale)
            if resized.shape[0] > search_area.shape[0] or resized.shape[1] > search_area.shape[1]:
                continue
            result = cv2.matchTemplate(search_area, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > best_val:
                best_val, best_loc, best_scale = max_val, max_loc, scale

        if best_val >= threshold:
            th, tw = template.shape[:2]
            sw, sh = int(tw * best_scale), int(th * best_scale)
            cx = best_loc[0] + sw // 2 + offset_x
            cy = best_loc[1] + sh // 2 + offset_y
            return MatchResult(found=True, x=cx, y=cy, confidence=best_val, scale=best_scale)

        return MatchResult(found=False, confidence=best_val)
```

#### 3.2.2 OCR 识别

```python
# yys/vision/ocr.py
from rapidocr_onnxruntime import RapidOCR

class GameOCR:
    """游戏 OCR：识别数字和中文"""

    def __init__(self):
        self.engine = RapidOCR()

    def recognize(self, image, region: tuple[int, int, int, int] | None = None) -> list[dict]:
        """识别图像中的文字，返回 [{text, confidence, bbox}, ...]"""
        if region:
            x, y, w, h = region
            image = image[y:y+h, x:x+w]
        result, _ = self.engine(image)
        if not result:
            return []
        return [{"text": line[1], "confidence": line[2], "bbox": line[0]} for line in result]

    def find_number(self, image, region=None) -> int | None:
        """提取第一个数字（体力、金币等）"""
        import re
        texts = self.recognize(image, region)
        for item in texts:
            match = re.search(r"\d+", item["text"])
            if match:
                return int(match.group())
        return None
```

#### 3.2.3 颜色检测

```python
# yys/vision/color.py
import cv2
import numpy as np

def detect_color(
    image: np.ndarray,
    hsv_lower: tuple[int, int, int],
    hsv_upper: tuple[int, int, int],
    min_area: int = 100,
) -> list[tuple[int, int, int, int]]:
    """
    HSV 颜色检测，返回匹配的矩形区域列表 [(x, y, w, h), ...]
    用途：检测按钮高亮、红点提示、血量条等
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    results = []
    for cnt in contours:
        if cv2.contourArea(cnt) >= min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            results.append((x, y, w, h))
    return results
```

#### 3.2.4 场景识别状态机

游戏场景用枚举 + 状态转换表描述，所有任务基于当前场景决策。

```python
# yys/vision/scene.py
from enum import Enum, auto

class Scene(Enum):
    """游戏场景枚举"""
    LOGIN           = auto()  # 登录界面
    MAIN_CITY       = auto()  # 主界面/庭院
    BATTLE_PREPARE  = auto()  # 战斗准备（选阵容）
    BATTLING        = auto()  # 战斗中
    BATTLE_RESULT   = auto()  # 战斗结算
    EXPLORE_MAP     = auto()  # 探索地图
    GACHA           = auto()  # 召唤界面
    GUILD           = auto()  # 阴阳寮
    SHOP            = auto()  # 商店
    DIALOG          = auto()  # 弹窗/对话框
    LOADING         = auto()  # 加载画面
    UNKNOWN         = auto()  # 未知场景

# 场景转换规则：from_scene -> [to_scenes]
SCENE_TRANSITIONS: dict[Scene, list[Scene]] = {
    Scene.LOGIN:          [Scene.MAIN_CITY, Scene.LOADING],
    Scene.MAIN_CITY:      [Scene.BATTLE_PREPARE, Scene.EXPLORE_MAP, Scene.GUILD,
                           Scene.SHOP, Scene.GACHA, Scene.DIALOG],
    Scene.BATTLE_PREPARE: [Scene.BATTLING, Scene.MAIN_CITY],
    Scene.BATTLING:       [Scene.BATTLE_RESULT],
    Scene.BATTLE_RESULT:  [Scene.BATTLE_PREPARE, Scene.MAIN_CITY],
    Scene.EXPLORE_MAP:    [Scene.BATTLE_PREPARE, Scene.MAIN_CITY],
    Scene.LOADING:        [Scene.MAIN_CITY, Scene.LOGIN],
    Scene.DIALOG:         [Scene.MAIN_CITY],
}

class SceneDetector:
    """场景检测器：基于模板匹配+颜色特征判断当前场景"""

    # 每个场景的特征模板列表（至少匹配一个即认定）
    SCENE_FEATURES: dict[Scene, list[str]] = {
        Scene.LOGIN:          ["login_btn", "login_logo"],
        Scene.MAIN_CITY:      ["main_explore_btn", "main_guild_btn", "main_summon_btn"],
        Scene.BATTLE_PREPARE: ["prepare_start_btn", "prepare_team_panel"],
        Scene.BATTLING:       ["battle_auto_btn", "battle_speed_btn"],
        Scene.BATTLE_RESULT:  ["result_confirm_btn", "result_reward_panel"],
        Scene.LOADING:        ["loading_bar"],
        Scene.DIALOG:         ["dialog_close_btn"],
    }

    def __init__(self, matcher):
        self.matcher = matcher
        self.current_scene: Scene = Scene.UNKNOWN
        self.last_scene: Scene = Scene.UNKNOWN

    def detect(self, screenshot) -> Scene:
        for scene, templates in self.SCENE_FEATURES.items():
            for tpl in templates:
                result = self.matcher.match(screenshot, tpl, threshold=0.8)
                if result.found:
                    self.last_scene = self.current_scene
                    self.current_scene = scene
                    return scene
        self.last_scene = self.current_scene
        self.current_scene = Scene.UNKNOWN
        return Scene.UNKNOWN
```

---

### 3.3 任务执行层

**职责**：实现具体的游戏任务逻辑，基于场景状态机驱动执行。

#### 3.3.1 任务基类设计

```python
# yys/task/base.py
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field
from loguru import logger

class TaskStatus(Enum):
    IDLE      = auto()
    RUNNING   = auto()
    PAUSED    = auto()
    COMPLETED = auto()
    FAILED    = auto()

@dataclass
class TaskResult:
    success: bool
    message: str = ""
    stats: dict = field(default_factory=dict)  # e.g. {"runs": 10, "souls": 35}

class BaseTask(ABC):
    """任务基类：定义生命周期"""

    name: str = "base"
    priority: int = 0           # 优先级，越大越先执行
    max_retries: int = 3

    def __init__(self, device, vision, config):
        self.device = device
        self.vision = vision
        self.config = config
        self.status = TaskStatus.IDLE
        self._retry_count = 0

    # ---- 生命周期 ----
    def pre_check(self) -> bool:
        """执行前检查（体力是否充足、是否在正确页面等）"""
        return True

    @abstractmethod
    def execute(self) -> TaskResult:
        """核心执行逻辑"""
        ...

    def on_success(self, result: TaskResult) -> None:
        """成功回调"""
        logger.info(f"[{self.name}] 完成: {result.message}")

    def on_failure(self, error: Exception) -> None:
        """失败回调"""
        self._retry_count += 1
        if self._retry_count <= self.max_retries:
            logger.warning(f"[{self.name}] 失败，重试 {self._retry_count}/{self.max_retries}")
        else:
            logger.error(f"[{self.name}] 达到最大重试次数，放弃")
            self.status = TaskStatus.FAILED

    def run(self) -> TaskResult:
        """完整执行流程"""
        self.status = TaskStatus.RUNNING
        try:
            if not self.pre_check():
                return TaskResult(success=False, message="前置检查未通过")
            result = self.execute()
            if result.success:
                self.on_success(result)
                self.status = TaskStatus.COMPLETED
            return result
        except Exception as e:
            self.on_failure(e)
            return TaskResult(success=False, message=str(e))
```

#### 3.3.2 注册表模式

```python
# yys/task/registry.py
from typing import Type

_TASK_REGISTRY: dict[str, Type[BaseTask]] = {}

def register_task(name: str):
    """装饰器：注册任务到全局注册表"""
    def decorator(cls):
        _TASK_REGISTRY[name] = cls
        cls.name = name
        return cls
    return decorator

def get_task(name: str) -> Type[BaseTask]:
    if name not in _TASK_REGISTRY:
        raise KeyError(f"未注册的任务: {name}")
    return _TASK_REGISTRY[name]

def list_tasks() -> list[str]:
    return list(_TASK_REGISTRY.keys())

# 使用示例
@register_task("souls")
class SoulsTask(BaseTask):
    """御魂副本任务"""
    priority = 10

    def execute(self) -> TaskResult:
        # 1. 导航到御魂副本
        # 2. 选择层数
        # 3. 循环战斗
        # 4. 统计结果
        return TaskResult(success=True, message="御魂10层x30完成", stats={"runs": 30})
```

#### 3.3.3 任务编排与优先级

```python
# yys/task/orchestrator.py
class TaskOrchestrator:
    """任务编排器：按优先级和依赖关系执行任务"""

    def __init__(self, device, vision, config):
        self.device = device
        self.vision = vision
        self.config = config

    def run_plan(self, task_names: list[str]) -> list[TaskResult]:
        """按计划顺序执行任务列表"""
        tasks = []
        for name in task_names:
            cls = get_task(name)
            tasks.append(cls(self.device, self.vision, self.config))

        # 按优先级降序排序
        tasks.sort(key=lambda t: t.priority, reverse=True)

        results = []
        for task in tasks:
            logger.info(f"▶ 开始执行: {task.name} (优先级={task.priority})")
            result = task.run()
            results.append(result)
            if not result.success and task.status == TaskStatus.FAILED:
                logger.error(f"✖ 任务 {task.name} 最终失败，跳过")
        return results
```

---

### 3.4 调度层

**职责**：管理定时任务、体力规划、每日任务计划。

#### 3.4.1 APScheduler 配置

```python
# yys/scheduler/engine.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from loguru import logger

class SchedulerEngine:
    """调度引擎"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url="sqlite:///jobs.db")},
            timezone="Asia/Shanghai",
        )

    def start(self):
        self.scheduler.start()
        logger.info("调度引擎已启动")

    def add_daily_task(self, job_id: str, func, hour: int, minute: int = 0, **kwargs):
        """添加每日定时任务"""
        self.scheduler.add_job(
            func,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        logger.info(f"已添加每日任务: {job_id} @ {hour:02d}:{minute:02d}")

    def add_interval_task(self, job_id: str, func, minutes: int, **kwargs):
        """添加间隔任务（如体力检查）"""
        self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
```

#### 3.4.2 每日任务规划器

```python
# yys/scheduler/planner.py
from dataclasses import dataclass

@dataclass
class DailyPlan:
    """每日计划"""
    souls_runs: int = 30        # 御魂副本次数
    explore_runs: int = 0       # 探索副本次数
    guild_tasks: bool = True    # 阴阳寮任务
    arena_runs: int = 5         # 斗技次数
    demon_encounter: bool = True # 逢魔之时
    mail_collect: bool = True   # 收邮件

class DailyPlanner:
    """每日任务规划器：根据配置生成执行计划"""

    DEFAULT_SCHEDULE = [
        # (时间,    任务名,              参数)
        ("06:30",  "daily_login",       {}),          # 早起登录
        ("06:35",  "mail_collect",      {}),          # 收邮件
        ("07:00",  "guild_tasks",       {}),          # 寮任务
        ("12:00",  "souls",             {"runs": 15}),# 午间御魂
        ("18:00",  "demon_encounter",   {}),          # 逢魔之时
        ("20:00",  "souls",             {"runs": 15}),# 晚间御魂
        ("21:00",  "arena",             {"runs": 5}), # 斗技
        ("22:00",  "daily_summary",     {}),          # 每日总结
    ]

    def __init__(self, plan: DailyPlan, scheduler: SchedulerEngine):
        self.plan = plan
        self.scheduler = scheduler

    def apply(self):
        """将计划注册到调度器"""
        for time_str, task_name, kwargs in self.DEFAULT_SCHEDULE:
            h, m = map(int, time_str.split(":"))
            self.scheduler.add_daily_task(
                job_id=f"daily_{task_name}",
                func=self._run_task,
                hour=h, minute=m,
                task_name=task_name, **kwargs,
            )
```

#### 3.4.3 体力管理算法

```python
# yys/scheduler/stamina.py

class StaminaManager:
    """体力管理器：智能分配体力"""

    MAX_STAMINA = 100          # 体力上限（实际可超到 800+）
    RECOVERY_RATE = 1          # 每5分钟恢复1点
    SOUL_COST = 6              # 御魂副本消耗

    def __init__(self, device, vision):
        self.device = device
        self.vision = vision

    def get_current_stamina(self) -> int:
        """通过 OCR 读取当前体力值"""
        screenshot = self.device.screenshot()
        return self.vision.ocr.find_number(screenshot, region=(280, 15, 80, 30)) or 0

    def calc_available_runs(self, stamina: int, cost: int = SOUL_COST) -> int:
        """计算可用副本次数"""
        return max(0, stamina // cost)

    def should_wait_for_stamina(self, target_runs: int, current_stamina: int) -> int:
        """计算需要等待的分钟数以达到目标次数"""
        needed = target_runs * self.SOUL_COST
        if current_stamina >= needed:
            return 0
        deficit = needed - current_stamina
        return deficit * 5  # 每点体力5分钟
```

---

### 3.5 通知层

**职责**：将任务结果、异常告警推送到用户。

#### 3.5.1 通知基类与多通道分发

```python
# yys/notify/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NotifyMessage:
    title: str
    content: str
    level: str = "info"   # info / warning / error
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class NotifyChannel(ABC):
    """通知通道基类"""

    @abstractmethod
    async def send(self, message: NotifyMessage) -> bool: ...

class NotifyDispatcher:
    """多通道通知分发器"""

    def __init__(self):
        self.channels: list[NotifyChannel] = []

    def add_channel(self, channel: NotifyChannel):
        self.channels.append(channel)

    async def dispatch(self, message: NotifyMessage):
        for ch in self.channels:
            try:
                await ch.send(message)
            except Exception as e:
                logger.error(f"通知发送失败 [{ch.__class__.__name__}]: {e}")
```

#### 3.5.2 WxPusher 接入

```python
# yys/notify/wxpusher.py
import httpx

class WxPusherChannel(NotifyChannel):
    """微信推送 (WxPusher)"""

    API_URL = "https://wxpusher.zjiecode.com/api/send/message"

    def __init__(self, app_token: str, uids: list[str]):
        self.app_token = app_token
        self.uids = uids

    async def send(self, message: NotifyMessage) -> bool:
        payload = {
            "appToken": self.app_token,
            "content": f"【{message.title}】\n{message.content}",
            "summary": message.title,
            "contentType": 1,  # 纯文本
            "uids": self.uids,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.API_URL, json=payload, timeout=10)
            return resp.status_code == 200
```

#### 3.5.3 消息模板

```python
# yys/notify/templates.py

TEMPLATES = {
    "task_complete": "✔ {task_name} 完成\n耗时: {duration}\n{stats}",
    "task_failed":   "✖ {task_name} 失败\n原因: {error}\n重试次数: {retries}",
    "daily_summary": "📊 每日总结\n御魂: {souls_runs}次 | 斗技: {arena_runs}次\n体力剩余: {stamina}\n总耗时: {total_time}",
    "stamina_low":   "⚡ 体力不足\n当前: {current}/{max}\n预计恢复: {wait_min}分钟",
    "error_alert":   "🚨 异常告警\n类型: {error_type}\n详情: {detail}\n时间: {time}",
}
```

#### 3.5.4 频率限制

```python
# yys/notify/rate_limiter.py
import time
from collections import defaultdict

class RateLimiter:
    """通知频率限制：同类消息最小间隔 + 每日总量上限"""

    def __init__(self, min_interval_sec: int = 60, daily_max: int = 50):
        self.min_interval = min_interval_sec
        self.daily_max = daily_max
        self._last_sent: dict[str, float] = defaultdict(float)
        self._daily_count: dict[str, int] = defaultdict(int)
        self._day_marker: str = ""

    def allow(self, key: str) -> bool:
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        if today != self._day_marker:
            self._daily_count.clear()
            self._day_marker = today

        if now - self._last_sent[key] < self.min_interval:
            return False
        if self._daily_count[key] >= self.daily_max:
            return False

        self._last_sent[key] = now
        self._daily_count[key] += 1
        return True
```

---

### 3.6 异常恢复机制

#### 3.6.1 弹窗检测策略

```python
# yys/recovery/popup.py

class PopupDetector:
    """弹窗检测与自动关闭"""

    # 已知弹窗模板列表（关闭按钮）
    KNOWN_POPUPS = [
        "popup_close",          # 通用关闭
        "popup_confirm",        # 确认弹窗
        "popup_ad_close",       # 广告弹窗
        "popup_update_later",   # 更新提示-稍后
        "popup_network_retry",  # 网络重试
        "popup_back_to_game",   # 回到游戏
    ]

    def __init__(self, matcher):
        self.matcher = matcher

    def check_and_close(self, screenshot) -> bool:
        """检测并关闭弹窗，返回是否处理了弹窗"""
        for popup in self.KNOWN_POPUPS:
            result = self.matcher.match(screenshot, popup, threshold=0.8)
            if result.found:
                # 点击关闭按钮
                self.matcher.device.click(result.x, result.y)
                time.sleep(1)
                logger.info(f"已关闭弹窗: {popup}")
                return True
        return False
```

#### 3.6.2 异常恢复流程

```
正常运行 ──▶ 检测到异常?
              │
              ├─ 弹窗 ──────▶ 自动关闭弹窗 ──▶ 继续运行
              │
              ├─ 游戏崩溃 ──▶ 重启游戏 ──▶ 等待加载 ──▶ 恢复到断点场景
              │
              ├─ 网络断开 ──▶ 等待30s ──▶ 检测网络
              │                            ├─ 恢复 ──▶ 点击重连 ──▶ 继续
              │                            └─ 未恢复 ──▶ 等待5min ──▶ 重试 ──▶ 通知用户
              │
              ├─ 场景超时 ──▶ 尝试ESC/返回 ──▶ 回到主城 ──▶ 重新导航
              │
              └─ 未知场景 ──▶ 截图保存 ──▶ 多次返回 ──▶ 仍未识别 ──▶ 通知用户
```

#### 3.6.3 重试策略（指数退避）

```python
# yys/recovery/retry.py
import time
from functools import wraps
from loguru import logger

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """指数退避重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        logger.error(f"[{func.__name__}] 第{attempt}次重试失败: {e}")
                        raise
                    logger.warning(f"[{func.__name__}] 第{attempt}次失败，{delay:.1f}s后重试: {e}")
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)  # 指数增长，上限 max_delay
        return wrapper
    return decorator
```

---

## 4. 数据流图

```
┌──────────┐
│ APScheduler│  (定时触发 / 手动触发)
└────┬─────┘
     │ trigger
     ▼
┌──────────────┐
│ DailyPlanner │  查询计划，确定当前要执行的任务
└────┬─────────┘
     │ task_name + params
     ▼
┌──────────────────┐
│ TaskOrchestrator │  实例化任务，按优先级排序
└────┬─────────────┘
     │ BaseTask.run()
     ▼
┌────────────────────────────────────────────────────────┐
│                    任务执行循环                          │
│                                                        │
│  ① device.screenshot() ──▶ 截图(numpy array)           │
│         │                                              │
│  ② vision.detect(screenshot) ──▶ Scene 枚举            │
│         │                                              │
│  ③ 根据 Scene 决策下一步操作                             │
│     ├─ Scene.BATTLING → 等待，定期截图检查               │
│     ├─ Scene.BATTLE_RESULT → 点击确认，进入下一局        │
│     ├─ Scene.BATTLE_PREPARE → 点击开始                  │
│     ├─ Scene.DIALOG → 关闭弹窗                         │
│     └─ Scene.UNKNOWN → 异常恢复流程                     │
│         │                                              │
│  ④ device.click() / device.swipe_bezier() ──▶ 执行操作  │
│         │                                              │
│  ⑤ 循环 ①-④ 直到任务完成                                │
└────┬───────────────────────────────────────────────────┘
     │ TaskResult
     ▼
┌──────────────┐
│ NotifyDispatcher │  推送结果/异常给用户
└────┬─────────┘
     │ WxPusher / Server酱
     ▼
┌──────────┐
│ 用户微信  │
└──────────┘
```

---

## 5. 配置管理方案

### 5.1 分层配置

```
config/
├── default.yaml        # 默认配置（随代码发布，不要修改）
├── user_config.yaml    # 用户自定义配置（覆盖 default，gitignore）
└── secrets.yaml        # 敏感信息（token等，gitignore）
```

加载优先级：`secrets.yaml` > `user_config.yaml` > `default.yaml`

### 5.2 Pydantic 模型定义

```python
# yys/config/models.py
from pydantic import BaseModel, Field
from pathlib import Path

class DeviceConfig(BaseModel):
    serial: str | None = None              # 设备序列号，None=自动检测
    connection: str = "usb"                # usb / wifi
    screenshot_method: str = "adb"         # adb / minicap
    heartbeat_interval: int = 30           # 心跳间隔(秒)

class VisionConfig(BaseModel):
    template_dir: str = "assets/templates"
    match_threshold: float = 0.85
    ocr_enabled: bool = True
    screenshot_scale: float = 1.0

class StaminaConfig(BaseModel):
    max_stamina: int = 800
    reserve_stamina: int = 100             # 保留体力
    auto_recover: bool = True              # 体力不足时自动等待

class ScheduleConfig(BaseModel):
    timezone: str = "Asia/Shanghai"
    enabled: bool = True
    daily_plan: list[dict] = Field(default_factory=list)

class NotifyConfig(BaseModel):
    enabled: bool = False
    wxpusher_token: str = ""
    wxpusher_uids: list[str] = Field(default_factory=list)
    server_chan_key: str = ""
    rate_limit_sec: int = 60
    daily_max: int = 50

class AntiDetectConfig(BaseModel):
    click_offset: int = 5                  # 点击随机偏移(px)
    click_delay: tuple[float, float] = (0.01, 0.05)
    swipe_randomize: bool = True
    rest_interval: tuple[int, int] = (30, 120)  # 每N分钟休息
    rest_duration: tuple[int, int] = (10, 60)   # 休息秒数

class AppConfig(BaseModel):
    """顶层配置"""
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    stamina: StaminaConfig = Field(default_factory=StaminaConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    anti_detect: AntiDetectConfig = Field(default_factory=AntiDetectConfig)
    log_level: str = "INFO"
    log_file: str = "logs/yys.log"
```

### 5.3 配置加载与热更新

```python
# yys/config/loader.py
import yaml
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .models import AppConfig
from loguru import logger

def deep_merge(base: dict, override: dict) -> dict:
    """深度合并两个字典"""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_config(config_dir: str = "config") -> AppConfig:
    """分层加载配置"""
    config_path = Path(config_dir)
    merged = {}
    for name in ["default.yaml", "user_config.yaml", "secrets.yaml"]:
        fpath = config_path / name
        if fpath.exists():
            with open(fpath) as f:
                data = yaml.safe_load(f) or {}
                merged = deep_merge(merged, data)
    return AppConfig(**merged)

class ConfigReloader(FileSystemEventHandler):
    """配置文件热更新（watchdog）"""

    def __init__(self, config_dir: str, callback):
        self.config_dir = config_dir
        self.callback = callback
        self.observer = Observer()

    def start(self):
        self.observer.schedule(self, self.config_dir, recursive=False)
        self.observer.start()

    def on_modified(self, event):
        if event.src_path.endswith((".yaml", ".yml")):
            logger.info(f"配置变更，重新加载: {event.src_path}")
            new_config = load_config(self.config_dir)
            self.callback(new_config)
```

---

## 6. 性能与稳定性设计

### 6.1 截图频率优化

| 场景 | 截图频率 | 理由 |
|------|---------|------|
| 战斗中 | 每 2s | 自动战斗无需频繁检查 |
| 战斗结算 | 每 0.5s | 需快速检测结算完成 |
| 菜单导航 | 每 1s | 平衡响应速度和性能 |
| 等待状态 | 每 5s | 空闲时降低频率 |
| 弹窗检测 | 每次操作后 | 操作后立即检查是否弹出弹窗 |

### 6.2 内存管理

- **截图不持久化**：`screenshot()` 返回 numpy array，用完即释放，不写磁盘
- **模板缓存 LRU**：最多缓存 50 个模板图片，超出自动淘汰
- **OCR 引擎复用**：全局单例，不重复加载模型
- **日志轮转**：`loguru` 配置 10MB 轮转，保留 7 天

### 6.3 长时间运行稳定性

```python
# 核心循环中插入休息机制
def run_with_rest(task_func, anti_detect_config: AntiDetectConfig):
    """带休息的执行循环"""
    import random, time
    task_func()
    rest_min, rest_max = anti_detect_config.rest_interval
    rest_interval = random.randint(rest_min, rest_max) * 60  # 转为秒
    # 每 N 分钟休息一次
    time.sleep(random.randint(*anti_detect_config.rest_duration))
```

- **内存泄漏监控**：每 30 分钟记录一次 `psutil.Process().memory_info()`
- **ADB 连接保活**：心跳 + 自动重连（见 3.1.1）
- **SQLite 定期 VACUUM**：调度器 job store 定期压缩

### 6.4 反检测策略

| 策略 | 实现方式 |
|------|---------|
| 操作随机化 | 点击坐标 ±5px 偏移、延迟随机、滑动贝塞尔曲线 |
| 时间随机化 | 任务启动时间 ±5 分钟抖动 |
| 休息模拟 | 每 30~120 分钟暂停 10~60 秒 |
| 操作节奏 | 不固定间隔，模拟人类操作节奏 |
| 避免完美路径 | 偶尔多点击一次再返回（概率 5%） |

---

## 7. 借鉴的开源项目

### 7.1 OAS (Onmyoji Auto Script)

- **GitHub**: https://github.com/runhey/OnmyojiAutoScript
- **借鉴点**：
  - 场景状态机设计：将游戏场景枚举化，通过模板匹配驱动状态转换
  - 任务编排模式：注册表 + 基类生命周期
  - 模板资源组织方式

### 7.2 Alas (Azur Lane Auto Script)

- **GitHub**: https://github.com/LmeSzinc/AzurLaneAutoScript
- **借鉴点**：
  - 调度系统设计：APScheduler + 任务规划 + 持久化
  - 异常恢复机制：分级异常处理、指数退避重试
  - 配置管理：分层 YAML + 热更新
  - 整体项目架构和模块划分

### 7.3 uiautomator2

- **GitHub**: https://github.com/openatx/uiautomator2
- **借鉴点**：
  - 设备控制 API 封装：click / swipe / screenshot / app 管理
  - 连接管理：USB / WiFi 连接、自动重连
  - 作为本项目设备层的底层依赖

---

## 8. 目录结构总览

```
yinyngshi/
├── pyproject.toml              # 项目元数据与依赖（uv 管理）
├── uv.lock                     # 依赖锁文件
├── .gitignore
├── README.md
│
├── config/                     # 配置文件
│   ├── default.yaml            # 默认配置
│   ├── user_config.yaml        # 用户配置（gitignore）
│   └── secrets.yaml            # 敏感信息（gitignore）
│
├── assets/                     # 静态资源
│   ├── templates/              # 模板图片（按钮、场景特征等）
│   │   ├── scene/              # 场景识别模板
│   │   ├── button/             # 按钮模板
│   │   └── popup/              # 弹窗模板
│   └── fonts/                  # 字体文件（OCR 用）
│
├── yys/                        # 主源码
│   ├── __init__.py
│   ├── __main__.py             # python -m yys 入口
│   │
│   ├── cli/                    # CLI 层
│   │   ├── __init__.py
│   │   ├── main.py             # Typer 主应用
│   │   ├── run_cmd.py          # run 子命令
│   │   └── config_cmd.py       # config 子命令
│   │
│   ├── device/                 # 设备控制层
│   │   ├── __init__.py
│   │   ├── controller.py       # 设备控制器
│   │   ├── connection.py       # 连接管理
│   │   └── adb_utils.py        # ADB 工具函数
│   │
│   ├── vision/                 # 视觉识别层
│   │   ├── __init__.py
│   │   ├── matcher.py          # 模板匹配
│   │   ├── ocr.py              # OCR 识别
│   │   ├── color.py            # 颜色检测
│   │   └── scene.py            # 场景识别状态机
│   │
│   ├── task/                   # 任务执行层
│   │   ├── __init__.py
│   │   ├── base.py             # 任务基类
│   │   ├── registry.py         # 任务注册表
│   │   ├── orchestrator.py     # 任务编排器
│   │   └── tasks/              # 具体任务实现
│   │       ├── __init__.py
│   │       ├── souls.py        # 御魂副本
│   │       ├── explore.py      # 探索副本
│   │       ├── guild.py        # 阴阳寮任务
│   │       ├── arena.py        # 斗技
│   │       ├── demon.py        # 逢魔之时
│   │       └── daily.py        # 每日杂项（邮件、商店等）
│   │
│   ├── scheduler/              # 调度层
│   │   ├── __init__.py
│   │   ├── engine.py           # APScheduler 引擎
│   │   ├── planner.py          # 每日任务规划
│   │   └── stamina.py          # 体力管理
│   │
│   ├── notify/                 # 通知层
│   │   ├── __init__.py
│   │   ├── base.py             # 通知基类与分发器
│   │   ├── wxpusher.py         # WxPusher 通道
│   │   ├── templates.py        # 消息模板
│   │   └── rate_limiter.py     # 频率限制
│   │
│   ├── recovery/               # 异常恢复
│   │   ├── __init__.py
│   │   ├── popup.py            # 弹窗检测
│   │   ├── crash.py            # 崩溃恢复
│   │   └── retry.py            # 重试策略
│   │
│   └── config/                 # 配置管理
│       ├── __init__.py
│       ├── models.py           # Pydantic 模型
│       └── loader.py           # 配置加载器
│
├── tests/                      # 测试
│   ├── conftest.py
│   ├── test_device.py
│   ├── test_vision.py
│   ├── test_task.py
│   └── test_scheduler.py
│
├── logs/                       # 运行日志（gitignore）
└── docs/                       # 文档
    └── TECH_DESIGN.md          # 本文档
```
