# 设备控制层 (Device Layer)

## 模块职责

设备控制层是阴阳师辅助脚本的**最底层模块**，负责与 Android 设备的直接交互。上层模块（engine、tasks、scene 等）均通过本层实现对设备的控制。

核心能力：
- **ADB 连接管理**：支持 USB / WiFi 连接，内置心跳检测与自动重连
- **设备操作控制**：点击、长按、滑动（贝塞尔曲线）、输入文字、按键，均内置随机偏移与随机延迟
- **应用生命周期管理**：启动 / 停止 / 重启应用，提供阴阳师游戏专用快捷方法
- **截图管理**：获取设备截图（OpenCV 格式），支持缓存机制与文件保存

## 类关系图

```
ADBClient (adb_client.py)
├── 封装 uiautomator2.Device
├── 管理连接状态 & 心跳检测
└── 提供底层 device 属性
        │
        ├──> DeviceController (controller.py)
        │       └── 点击 / 滑动 / 长按 / 输入 / 按键
        │
        ├──> AppManager (app_manager.py)
        │       └── 启动 / 停止 / 重启应用 & 阴阳师快捷方法
        │
        └──> ScreenCapture (screen.py)
                └── 截图获取 / 缓存 / 保存
```

## 使用示例

### 1. 连接设备

```python
from src.device import ADBClient

# USB 连接
client = ADBClient(serial="emulator-5554")

# WiFi 连接
client = ADBClient()
client.connect_wifi("192.168.1.100", port=5555)

# 查看已连接设备
print(client.list_devices())
```

### 2. 操作控制

```python
from src.device import ADBClient, DeviceController

client = ADBClient(serial="emulator-5554")
ctrl = DeviceController(client)

# 点击（自动带随机偏移 ±3~5px + 随机延迟 0.3~0.8s）
ctrl.click(500, 800)

# 点击区域中心
ctrl.click_center((100, 200, 300, 400))

# 长按 2 秒
ctrl.long_press(500, 800, duration=2.0)

# 直线滑动
ctrl.swipe(200, 800, 200, 200)

# 贝塞尔曲线滑动（模拟人类手指轨迹）
ctrl.swipe_bezier(start=(200, 800), end=(200, 200))

# 按键
ctrl.press_key("back")
ctrl.press_key("home")
```

### 3. 应用管理

```python
from src.device import ADBClient, AppManager

client = ADBClient(serial="emulator-5554")
app = AppManager(client)

# 启动 / 停止阴阳师
app.start_onmyoji()
app.stop_onmyoji()

# 检查运行状态
if app.is_onmyoji_running():
    print("阴阳师正在运行")

# 唤醒 & 解锁屏幕
app.wake_screen()
app.unlock_screen()
```

### 4. 截图

```python
from src.device import ADBClient, ScreenCapture

client = ADBClient(serial="emulator-5554")
screen = ScreenCapture(client, max_age_ms=500)

# 获取截图（OpenCV BGR 格式）
img = screen.capture()

# 带缓存截图（500ms 内重复请求直接返回缓存）
img = screen.capture_cached()

# 保存截图到文件
screen.save_screenshot("screenshots/test.png")

# 获取屏幕尺寸
w, h = screen.get_screen_size()
print(f"屏幕尺寸: {w} x {h}")
```

## 注意事项

1. **设备层为最底层**：不可依赖 engine、tasks、scene 等上层模块
2. **依赖 uiautomator2**：使用前需确保已安装 `uiautomator2` 和 `opencv-python`
3. **ADB 环境**：系统需安装 Android SDK Platform Tools 并确保 `adb` 命令可用
4. **开发者选项**：设备需开启 USB 调试，WiFi 连接需先通过 USB 执行 `adb tcpip 5555`
5. **模拟器适配**：不同模拟器（雷电、MuMu、夜神等）的 ADB 端口可能不同
6. **随机偏移**：点击操作默认加入 ±3~5px 随机偏移，模拟人类行为
7. **随机延迟**：每次操作后加入 0.3~0.8s 随机延迟，可在初始化时配置
8. **心跳检测**：ADBClient 每 30s 检查设备连接状态，断线自动重连；可通过 `heartbeat_interval=0` 禁用
9. **截图缓存**：500ms 内的重复截图请求返回缓存，降低设备通信开销
