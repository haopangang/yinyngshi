---
name: debugger
model: "[Qwen3.7-Max](qmodel_latest)"
skills: []
mcpServers: []
additionalPrompt: ""
---

# 阴阳师辅助脚本 - 调试指导

## 项目架构理解

本脚本是阴阳师全自动托管辅助，基于 ADB + OpenCV + PaddleOCR，分层架构：

```
src/
├── device/       # 设备控制：ADB连接、截图、触摸模拟
├── vision/       # 视觉识别：模板匹配、OCR、场景判定
├── tasks/        # 任务执行：各副本/日常任务的自动化逻辑
├── scheduler/    # 调度层：任务排队、定时、优先级
└── notify/       # 通知层：执行结果推送
```

## 常见问题排查

### 1. 设备连接失败
- 检查 ADB 服务是否运行：`adb devices`
- 确认 USB 调试已开启
- 检查 uiautomator2 服务状态
- 查看 `src/device/adb_client.py` 的连接重试逻辑
- 检查设备序列号配置是否正确

### 2. 图像识别失败
- 确认模板图片存在且路径正确（`assets/templates/`）
- 检查分辨率是否匹配（模板图片通常基于 1080p 制作）
- 降低匹配阈值测试：`match_threshold` 配置项
- 查看截图是否正确获取（保存截图用于人工对比）
- 检查图像预处理流程（灰度化、缩放等）

### 3. OCR 识别错误
- 确认 ppocr-onnx 模型文件已加载
- 检查 ROI 区域裁剪是否准确
- 验证游戏内文字是否被其他 UI 元素遮挡
- 查看 `src/vision/ocr.py` 中的预处理步骤

### 4. 任务执行卡死
- 检查场景状态机是否卡在某个中间状态
- 查看 `pre_check()` 是否因条件不满足而一直等待
- 确认 `wait_battle_end()` 等等待方法有超时退出
- 检查是否有未捕获的弹窗阻断了流程

### 5. 调度异常
- 确认 APScheduler 时区配置正确
- 检查任务优先级冲突
- 查看体力恢复计算是否准确

## 日志分析

日志使用 loguru，输出在控制台和日志文件中。

### 日志级别含义
- `DEBUG`: 详细的设备操作、图像匹配坐标
- `INFO`: 任务执行进度、关键决策点
- `WARNING`: 非致命异常（识别失败但可重试）
- `ERROR`: 需要人工干预的错误

### 常用排查命令
```bash
# 查看最近的错误日志
grep "ERROR" logs/*.log | tail -20

# 查看设备操作日志
grep "device" logs/*.log

# 查看任务执行历史
grep "task" logs/*.log
```
