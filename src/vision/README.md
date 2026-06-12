# 视觉识别引擎 (src/vision)

## 模块概述

视觉识别引擎是阴阳师辅助脚本的核心感知层，负责从设备截图中提取结构化信息。
上层任务通过统一接口调用视觉能力，无需关心底层实现细节。

## 架构设计

```
VisionFinder (门面)
    ├── TemplateMatcher   — OpenCV 多尺度模板匹配
    ├── OCREngine         — rapidocr-onnxruntime 文字识别（单例）
    └── ColorDetector     — HSV 颜色空间检测

SceneRecognizer (场景识别)
    └── 组合上述三大引擎进行场景状态判断
```

## 文件说明

| 文件 | 职责 |
|------|------|
| `__init__.py` | 模块导出 |
| `matcher.py` | TemplateMatcher + MatchResult |
| `ocr.py` | OCREngine + TextResult |
| `color.py` | ColorDetector |
| `scene.py` | GameScene 枚举 + SceneRecognizer |
| `finder.py` | VisionFinder（门面模式统一接口） |

## 核心接口

### TemplateMatcher
```python
matcher = TemplateMatcher()
result = matcher.match(screenshot, "common/start_btn.png", threshold=0.8)
results = matcher.match_multi(screenshot, "enemy_marker.png", max_count=5)
result = matcher.match_in_region(screenshot, "btn.png", region=(0.5, 0.8, 1.0, 1.0))
best = matcher.match_best(screenshot, ["btn_a.png", "btn_b.png"])
```

### OCREngine
```python
ocr = OCREngine()  # 单例
texts = ocr.recognize(screenshot, region=(0.0, 0.0, 0.3, 0.1))
result = ocr.find_text(screenshot, "体力")
number = ocr.read_number(screenshot, region=(0.1, 0.05, 0.2, 0.1))
```

### ColorDetector
```python
detector = ColorDetector()
is_red = detector.detect_color(screenshot, hsv_lower=(0, 100, 100), hsv_upper=(10, 255, 255))
pos = detector.find_color_position(screenshot, hsv_lower, hsv_upper)
hsv = detector.get_pixel_color(screenshot, x=100, y=200)
```

### VisionFinder（推荐统一使用）
```python
finder = VisionFinder(screenshot_func=device.screenshot, click_func=device.click)
result = finder.find_image("common/accept_btn.png")
finder.click_image("common/accept_btn.png")
result = finder.wait_image("battle/victory.png", timeout=60)
text = finder.wait_text("战斗胜利", timeout=10)
exists = finder.exists("popup/network_error.png")
```

### SceneRecognizer
```python
recognizer = SceneRecognizer(matcher, ocr, detector)
scene = recognizer.recognize(screenshot)
recognizer.wait_scene(GameScene.BATTLE_RESULT, timeout=300, screenshot_func=device.screenshot)
```

## 技术要点

- **多尺度匹配**：对模板进行 0.8/0.9/1.0/1.1/1.2 倍缩放后分别匹配，取最高置信度
- **模板缓存**：`cv2.imread` 结果缓存在 `dict` 中，避免重复磁盘 IO
- **OCR 单例**：`OCREngine.__new__` 确保模型只加载一次
- **归一化坐标**：所有 `region` 参数使用 `(x1, y1, x2, y2)` 归一化 0~1 比例
- **NMS 去重**：多目标匹配使用非极大值抑制去除重叠框
- **场景缓存**：`SceneRecognizer` 在 TTL 内复用上次识别结果
