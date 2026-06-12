---
name: qa
model: "[Qwen3.7-Max](qmodel_latest)"
skills: []
mcpServers: []
additionalPrompt: ""
---

# 阴阳师辅助脚本 - 测试保障规范

## 测试框架与工具
- **pytest**: 主要测试框架
- **pytest-asyncio**: 异步测试支持
- **pytest-mock / unittest.mock**: Mock ADB 设备操作
- **pytest-cov**: 覆盖率统计

## 测试分类

### 单元测试
每个模块必须有对应的单元测试，重点覆盖：

#### 设备控制层 (`src/device/`)
- Mock ADB 命令，测试连接重试、超时处理
- 测试截图获取的异常路径（设备无响应、权限拒绝）
- 测试触摸事件参数校验

#### 视觉识别层 (`src/vision/`)
- 使用固定的测试截图（`tests/fixtures/`）
- 测试模板匹配的阈值边界条件
- 测试 OCR 识别的准确率（数字、中文）
- 测试图像预处理函数的正确性

#### 任务执行层 (`src/tasks/`)
- 测试 `BaseTask` 的生命周期方法调用顺序
- 测试 `pre_check()` 的资源不足场景
- 测试 `on_error()` 的异常恢复路径
- 测试任务注册装饰器的正确性

#### 调度层 (`src/scheduler/`)
- 测试任务优先级排序
- 测试定时任务的触发逻辑
- 测试体力恢复计算

#### 配置管理 (`src/config.py`)
- 测试 pydantic 模型的校验规则
- 测试默认配置的完整性
- 测试配置文件的加载和合并

### 集成测试
- 端到端任务流程（Mock 设备，但测试完整任务链）
- 调度器与任务的协作
- 配置加载与任务初始化的联动

### 性能测试
- 单次截图+识别的耗时基准
- 模板匹配的内存占用
- OCR 初始化和推理的耗时

## 测试目录结构

```
tests/
├── conftest.py           # pytest fixtures
├── fixtures/             # 测试用的固定截图和模板
│   ├── screenshots/
│   └── templates/
├── unit/
│   ├── test_device/
│   ├── test_vision/
│   ├── test_tasks/
│   ├── test_scheduler/
│   └── test_config.py
├── integration/
│   └── test_task_flow.py
└── performance/
    └── test_benchmark.py
```

## 覆盖率要求
- 核心业务逻辑：>80%
- 工具函数：>90%
- 异常处理路径：必须覆盖

## 测试命名约定
- 测试文件：`test_<module_name>.py`
- 测试函数：`test_<function>_<scenario>`（如 `test_find_image_not_found`）
- 测试类：`Test<ClassName>`（如 `TestOrochiTask`）

## Mock 策略
- **ADB 操作**：Mock `uiautomator2` 的所有设备交互
- **图像操作**：使用固定截图，不依赖 OpenCV 实际计算（或测试 OpenCV 本身时使用真实数据）
- **OCR**：Mock 模型推理，返回预设结果
- **网络请求**：Mock `httpx` 的通知发送
