"""任务基类与结果定义

定义任务执行的完整生命周期和结果数据结构。
所有游戏任务必须继承 BaseTask 并实现抽象方法。
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.device.controller import DeviceController
    from src.device.screen import ScreenCapture
    from src.vision.finder import VisionFinder


@dataclass
class TaskResult:
    """任务执行结果数据类
    
    记录单次任务执行的完整结果信息，包括成功状态、执行次数、
    错误次数、耗时和详细信息。
    
    Attributes:
        success: 任务是否成功完成
        run_count: 实际执行次数
        error_count: 执行过程中遇到的错误次数
        elapsed_time: 总耗时（秒）
        details: 额外的详细信息字典
    """
    
    success: bool
    run_count: int = 0
    error_count: int = 0
    elapsed_time: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有字段的字典
        """
        return {
            "success": self.success,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "elapsed_time": self.elapsed_time,
            "details": self.details,
        }


class BaseTask(ABC):
    """任务基类，定义完整生命周期
    
    所有游戏任务必须继承此类并实现抽象方法。任务执行遵循固定生命周期：
    __init__ -> pre_check -> navigate -> run -> cleanup
    
    任务层依赖设备层（DeviceController）和视觉层（VisionFinder），
    但不依赖调度层和通知层，保持架构稳定性。
    
    Attributes:
        name: 任务名称（中文或英文标识）
        priority: 优先级，数值越小优先级越高（1最高）
        stamina_cost: 单次执行消耗的体力值
        enabled: 是否启用该任务
        
    Example:
        >>> class MyTask(BaseTask):
        ...     name = "示例任务"
        ...     priority = 5
        ...     stamina_cost = 10
        ...     
        ...     def pre_check(self) -> bool:
        ...         return self.check_stamina(self.stamina_cost)
        ...     
        ...     def navigate(self) -> bool:
        ...         return self.go_to_main()
        ...     
        ...     def run(self) -> TaskResult:
        ...         # 执行任务逻辑
        ...         return TaskResult(success=True, run_count=1)
    """
    
    # 子类必须定义这些类属性
    name: str = ""
    priority: int = 5
    stamina_cost: int = 0
    enabled: bool = True
    
    def __init__(
        self,
        device: DeviceController,
        vision: VisionFinder,
        screen: ScreenCapture,
        config: dict[str, Any],
    ) -> None:
        """初始化任务实例
        
        Args:
            device: 设备控制器，提供点击、滑动等操作
            vision: 视觉查找器，提供图像识别、文字识别等功能
            screen: 截图管理器，提供屏幕截图功能
            config: 任务配置字典，包含任务特定的参数
        """
        self.device = device
        self.vision = vision
        self.screen = screen
        self.config = config
        
        # 从配置中读取通用参数
        self.enabled = config.get("enabled", self.enabled)
        self.priority = config.get("priority", self.priority)
        
        # 内部状态
        self._run_count = 0
        self._error_count = 0
        self._start_time: Optional[float] = None
        
        logger.info(f"任务初始化: {self.name} (priority={self.priority}, enabled={self.enabled})")
    
    # ------------------------------------------------------------------
    # 抽象方法：子类必须实现
    # ------------------------------------------------------------------
    
    @abstractmethod
    def pre_check(self) -> bool:
        """前置条件检查
        
        在执行任务前检查必要条件，如：
        - 体力是否充足
        - 是否满足进入条件
        - 必要的道具是否存在
        
        Returns:
            True 表示条件满足可以执行，False 表示不满足应跳过
        """
        pass
    
    @abstractmethod
    def navigate(self) -> bool:
        """从当前界面导航到任务界面
        
        执行必要的界面跳转操作，确保进入任务起始界面。
        可能需要：
        - 返回主界面
        - 点击特定入口
        - 等待界面加载
        
        Returns:
            True 表示导航成功，False 表示导航失败
        """
        pass
    
    @abstractmethod
    def run(self) -> TaskResult:
        """执行任务主逻辑
        
        实现任务的核心业务流程，包括：
        - 点击操作
        - 等待响应
        - 循环执行
        - 结果收集
        
        Returns:
            TaskResult 包含执行结果的详细信息
        """
        pass
    
    # ------------------------------------------------------------------
    # 可选覆盖方法
    # ------------------------------------------------------------------
    
    def on_error(self, error: Exception) -> bool:
        """异常处理钩子
        
        当任务执行过程中发生异常时调用，子类可覆盖以实现自定义恢复逻辑。
        默认实现记录错误日志并返回 False。
        
        Args:
            error: 捕获到的异常对象
            
        Returns:
            True 表示已恢复可继续执行，False 表示无法恢复应终止
        """
        logger.error(f"任务 {self.name} 发生错误: {error}")
        return False
    
    def cleanup(self) -> None:
        """任务清理钩子
        
        在任务结束后执行清理操作，如：
        - 返回主界面
        - 关闭弹窗
        - 重置状态
        
        默认实现调用 go_to_main()。子类可覆盖以自定义清理逻辑。
        """
        logger.debug(f"任务 {self.name} 执行清理")
        self.go_to_main()
    
    # ------------------------------------------------------------------
    # 辅助方法：提供常用操作封装
    # ------------------------------------------------------------------
    
    def click_image(self, template: str, timeout: float = 5.0) -> bool:
        """查找图片并点击
        
        使用视觉查找器在屏幕上查找指定模板图片，找到后点击其中心位置。
        
        Args:
            template: 模板图片路径（相对于 assets/templates/）
            timeout: 等待超时时间（秒）
            
        Returns:
            True 表示找到并点击成功，False 表示超时未找到
        """
        logger.debug(f"点击图片: {template} (timeout={timeout}s)")
        result = self.vision.wait_image(template, timeout=timeout)
        if result is None:
            logger.warning(f"未找到图片: {template}")
            return False
        
        # 点击中心位置
        center_x, center_y = result.center()
        self.device.click(center_x, center_y)
        return True
    
    def wait_scene(self, scene: str, timeout: float = 30.0) -> bool:
        """等待进入指定场景
        
        使用视觉查找器等待指定场景出现。
        
        Args:
            scene: 场景名称或模板路径
            timeout: 超时时间（秒）
            
        Returns:
            True 表示在超时内进入目标场景
        """
        logger.debug(f"等待场景: {scene} (timeout={timeout}s)")
        result = self.vision.wait_image(scene, timeout=timeout)
        return result is not None
    
    def check_stamina(self, required: int) -> bool:
        """检查体力是否充足
        
        通过 OCR 识别当前体力值，并与需求值比较。
        
        Args:
            required: 需要的体力值
            
        Returns:
            True 表示体力充足
        """
        logger.debug(f"检查体力: 需要 {required}")
        # 查找体力数字区域并 OCR
        result = self.vision.find_text("体力", region=(0.0, 0.0, 0.3, 0.1))
        if result is None:
            logger.warning("未找到体力显示")
            return False
        
        # 提取数字（简化实现，实际需解析 OCR 结果）
        # TODO: 实现完整的体力数值解析
        return True
    
    def go_to_main(self) -> bool:
        """返回游戏主界面
        
        通过多次点击返回键或点击主页按钮，确保回到主界面。
        
        Returns:
            True 表示成功返回主界面
        """
        logger.debug("返回主界面")
        # 尝试点击主页按钮
        if self.click_image("common/home_btn.png", timeout=2.0):
            return True
        
        # 否则按返回键
        try:
            self.device.press_key("back")
            time.sleep(1.0)
            return True
        except Exception as e:
            logger.error(f"返回主界面失败: {e}")
            return False
    
    def random_sleep(self, min_s: float, max_s: float) -> None:
        """随机休眠一段时间
        
        模拟人类操作间隔，降低被检测风险。
        
        Args:
            min_s: 最小休眠秒数
            max_s: 最大休眠秒数
        """
        self.device.random_delay(min_s, max_s)
    
    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    
    def _execute(self) -> TaskResult:
        """执行任务完整生命周期（内部使用）
        
        按顺序执行：pre_check -> navigate -> run -> cleanup
        
        Returns:
            TaskResult 包含完整执行结果
        """
        self._start_time = time.time()
        logger.info(f"开始执行任务: {self.name}")
        
        try:
            # 前置检查
            if not self.pre_check():
                logger.warning(f"任务 {self.name} 前置检查失败")
                return TaskResult(success=False, details={"reason": "pre_check_failed"})
            
            # 导航
            if not self.navigate():
                logger.warning(f"任务 {self.name} 导航失败")
                return TaskResult(success=False, details={"reason": "navigate_failed"})
            
            # 执行主逻辑
            result = self.run()
            
            # 清理
            self.cleanup()
            
            # 计算耗时
            result.elapsed_time = time.time() - self._start_time
            logger.info(f"任务 {self.name} 完成: success={result.success}, elapsed={result.elapsed_time:.1f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"任务 {self.name} 执行异常: {e}")
            self._error_count += 1
            
            # 尝试恢复
            if self.on_error(e):
                logger.info(f"任务 {self.name} 已从错误中恢复")
            
            # 清理
            try:
                self.cleanup()
            except Exception as cleanup_error:
                logger.error(f"清理失败: {cleanup_error}")
            
            elapsed = time.time() - self._start_time
            return TaskResult(
                success=False,
                run_count=self._run_count,
                error_count=self._error_count,
                elapsed_time=elapsed,
                details={"error": str(e)},
            )
