# 活动配置编写指南

本目录存放活动 YAML 配置文件，每个活动对应一个 `.yaml` 文件。
通过编写配置文件即可快速适配新活动，**无需写 Python 代码**。

## 快速开始

1. 复制 `_example.yaml` 并重命名为你的活动名，如 `spring_event.yaml`
2. 修改配置内容（名称、步骤、模板路径等）
3. 将活动相关模板图片放入 `assets/templates/events/<活动名>/`
4. 启动脚本，活动将自动被发现和注册

## 文件命名规则

| 命名 | 说明 |
|------|------|
| `your_event.yaml` | 正式活动文件，自动加载 |
| `_example.yaml` | 以 `_` 开头，作为模板/示例，自动跳过 |

## 配置结构

```yaml
name: "活动名称"            # 必填
description: "活动描述"      # 可选
enabled: true               # 是否启用

start_date: "2024-01-01"    # 可选，活动有效期
end_date: "2024-01-15"      # 可选

limits:                     # 任务限制
  daily_count: 30
  stamina_cost: 0

remaining_count:            # OCR 剩余次数识别（可选）
  enabled: true
  roi: [0.7, 0.05, 0.95, 0.12]
  pattern: "(\\d+)/\\d+"

stop_conditions:            # 停止条件列表（可选）
  - type: count_zero
  - type: template_match
    template: "events/xxx/no_chance.png"
  - type: button_disabled
    template: "events/xxx/btn_disabled.png"
  - type: timeout
    minutes: 60

navigation:                 # 导航步骤（可选）
  - action: click_template
    template: "events/xxx/entry.png"
    wait: 2

steps:                      # 执行步骤（必填）
  - action: click_template
    template: "events/xxx/challenge.png"
    wait: 1
```

## 支持的 Action 类型

### click_template — 识别模板图片并点击
```yaml
- action: click_template
  template: "events/xxx/btn.png"  # 必填
  threshold: 0.8                   # 匹配阈值（0~1）
  region: [0.4, 0.8, 0.6, 0.9]    # 可选，限定搜索区域
  timeout: 10                      # 等待模板出现的超时秒数
  wait: 1                          # 点击后等待秒数
```

### click_position — 点击指定坐标
```yaml
- action: click_position
  x: 540          # 像素坐标
  y: 960
  wait: 1

# 或使用归一化坐标 (0~1)
- action: click_position
  x: 0.5
  y: 0.8
  normalized: true
  wait: 1
```

### wait_template — 等待模板出现
```yaml
- action: wait_template
  template: "events/xxx/result.png"
  timeout: 120    # 最长等待秒数
  wait: 1         # 检测到后额外等待
```

### wait_template_disappear — 等待模板消失
```yaml
- action: wait_template_disappear
  template: "events/xxx/loading.png"
  timeout: 30
  wait: 0.5
```

### wait — 固定等待
```yaml
- action: wait
  seconds: 2
```

### swipe — 滑动操作
```yaml
- action: swipe
  x1: 540     # 起点
  y1: 1200
  x2: 540     # 终点
  y2: 600
  duration: 0.5  # 滑动持续时间
  wait: 1
```

### ocr_check — OCR 读取并判断
```yaml
- action: ocr_check
  text: "挑战"                  # 查找的文字
  expect: "挑战"                # 可选，检查结果是否包含
  region: [0.4, 0.8, 0.6, 0.9] # 可选，限定 OCR 区域
```

### click_ocr — 识别文字并点击
```yaml
- action: click_ocr
  text: "确定"
  region: [0.3, 0.4, 0.7, 0.6]
  wait: 1
```

## 停止条件类型

| type | 说明 | 必填参数 |
|------|------|---------|
| `count_zero` | OCR 读取剩余次数为 0 | 需配置 `remaining_count` |
| `template_match` | 检测到特定图片（弹窗） | `template`, `threshold` |
| `button_disabled` | 按钮变灰 | `template`, `threshold` |
| `timeout` | 超时保护 | `minutes` |

## 模板图片规范

- 存放路径：`assets/templates/events/<活动名>/`
- 格式：PNG
- 命名：snake_case，描述性命名（如 `challenge_btn.png`）
- 要求：裁剪后的局部图片，只包含目标元素

## 常见问题

**Q: 活动没有被自动加载？**
- 检查文件名是否以 `_` 开头（会被跳过）
- 检查 `enabled` 是否为 `true`
- 检查 `start_date` / `end_date` 是否在有效期内

**Q: 步骤执行失败怎么办？**
- 检查模板图片路径是否正确
- 降低 `threshold` 值（如 0.7）
- 增大 `timeout` 等待时间
- 查看日志定位失败步骤
