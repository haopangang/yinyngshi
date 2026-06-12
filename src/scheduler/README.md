# 智能调度系统 (src/scheduler/)

阴阳师辅助脚本的调度层，负责任务定时、规划、体力管理、异常恢复和运行监控。

## 模块结构

| 文件 | 类 | 说明 |
|------|-----|------|
| `scheduler.py` | `TaskScheduler` | APScheduler 定时任务管理，支持 SQLite 持久化 |
| `planner.py` | `DailyPlanner` | 每日任务规划器，生成计划并按优先级执行 |
| `stamina.py` | `StaminaManager` | 体力管理：OCR 识别、预算控制、道具使用 |
| `recovery.py` | `RecoveryManager` | 异常恢复：弹窗/网络/崩溃/断连，指数退避重试 |
| `monitor.py` | `RuntimeMonitor` | 运行状态监控：统计记录、日报生成、JSON 持久化 |

## 依赖关系

```
调度层 (scheduler)
├── 任务层 (tasks)    — create_task(), BaseTask, TaskResult
├── 设备层 (device)   — DeviceController, AppManager, ScreenCapture
├── 视觉层 (vision)   — VisionFinder, OCREngine
└── 配置层 (config)   — SchedulerConfig, StaminaConfig, RecoveryConfig
```

## 快速使用

```python
from src.scheduler import TaskScheduler, DailyPlanner, RuntimeMonitor

# 定时调度
scheduler = TaskScheduler()
scheduler.start()
scheduler.add_daily_job("08:00", run_daily_tasks, "morning_plan")

# 任务规划
planner = DailyPlanner(device, vision, screen, app_manager)
plan = planner.create_plan(scheduler_config)
planner.execute_plan(plan)

# 运行监控
monitor = RuntimeMonitor()
monitor.start_task("orochi")
# ... 执行任务 ...
monitor.end_task("orochi", result)
report = monitor.get_daily_report()
monitor.save_stats("data/stats.json")
```

## 异常恢复策略

采用责任链模式，依次检测并处理：

1. **弹窗干扰** → 查找关闭按钮模板并点击
2. **网络错误** → 指数退避等待 + 重连
3. **游戏崩溃** → 检测进程 → 重启游戏
4. **设备断连** → 重新建立 ADB 连接

重试策略：指数退避 1s → 2s → 4s → 8s，最多 3 次。
