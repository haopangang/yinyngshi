# 模板图片管理规范

## 目录结构

```
assets/templates/
├── common/          # 通用模板（按钮、图标等跨场景复用）
├── scene/           # 场景识别专用模板
├── daily/           # 日常任务模板
│   ├── orochi/      # 八岐大蛇/御魂
│   ├── awakening/   # 觉醒副本
│   └── ...
├── battle/          # 战斗相关模板
└── README.md        # 本文件
```

## 命名规则

- 使用小写英文字母和下划线：`start_btn.png`、`explore_chapter.png`
- 命名格式：`[功能/场景]_[描述].png`
- 示例：
  - `common/accept_btn.png` — 通用确认按钮
  - `scene/main_screen_btn.png` — 主界面特征按钮
  - `orochi/orochi_banner.png` — 八岐大蛇入口标识

## 图片要求

| 项目 | 要求 |
|------|------|
| 格式 | PNG（无透明通道时使用 PNG-24） |
| 尺寸 | 尽量裁剪到最小有效区域，去除无关背景 |
| 分辨率 | 基于 2340×1080 基准分辨率截取 |
| 颜色空间 | RGB（代码中使用 cv2 读取为 BGR） |
| 文件大小 | 单张建议 < 500KB |

## _manifest.yaml 格式说明

每个子目录下可放置 `_manifest.yaml`，记录模板元信息：

```yaml
# assets/templates/common/_manifest.yaml
templates:
  - name: accept_btn.png
    description: "通用确认/接受按钮"
    category: common
    threshold: 0.85
    tags: [button, confirm]

  - name: cancel_btn.png
    description: "通用取消按钮"
    category: common
    threshold: 0.85
    tags: [button, cancel]
```

字段说明：
- `name`: 模板文件名
- `description`: 用途说明
- `category`: 分类
- `threshold`: 建议匹配阈值（默认 0.8）
- `tags`: 标签，便于检索

## 如何新增模板

1. 在对应子目录下放置 PNG 图片
2. 在 `_manifest.yaml` 中添加条目（如无则创建）
3. 在代码中使用相对路径引用：`"common/accept_btn.png"`
4. 建议先用单张截图测试匹配阈值是否合理
