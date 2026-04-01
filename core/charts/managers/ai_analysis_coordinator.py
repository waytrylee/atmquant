#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI分析协调器
负责协调AI分析任务，支持多模型对比和多周期分析
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from vnpy.event import EventEngine, Event
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore

from core.charts.prompts.market_analysis_prompts import ANALYSIS_AI_PROMPT
from core.charts.utils.market_data_collector import MarketDataCollector
from core.logging.alert_manager import alert_manager


class AIAnalysisCoordinator(QtCore.QObject):
    """AI分析协调器"""

    # Qt信号
    analysis_started = QtCore.Signal(str)  # 分析开始信号 (task_id)
    analysis_completed = QtCore.Signal(str, dict)  # 分析完成信号 (task_id, result)
    analysis_failed = QtCore.Signal(str, str)  # 分析失败信号 (task_id, error_msg)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine, position_manager=None):
        """
        初始化AI分析协调器

        Args:
            main_engine: vnpy主引擎
            event_engine: vnpy事件引擎
            position_manager: PositionManager实例（可选）
        """
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.position_manager = position_manager

        # AI客户端字典（延迟初始化）
        self.ai_clients: Dict[str, Any] = {}

        # 活动线程引用
        self.active_threads: Dict[str, QtCore.QThread] = {}

    def _get_ai_client(self, model_name: str):
        """
        获取或创建AI客户端（延迟初始化）

        Args:
            model_name: 模型名称

        Returns:
            AI客户端实例，如果无法创建则返回None
        """
        if model_name in self.ai_clients:
            return self.ai_clients[model_name]

        # 尝试创建客户端
        try:
            from core.ai_clients.factory import AIClientFactory
            from config.ai_keys_config import get_ai_api_key, get_api_base_url

            # 根据模型名称推断提供商
            if "deepseek" in model_name.lower():
                provider = "deepseek"
            elif "claude" in model_name.lower() or "sonnet" in model_name.lower():
                provider = "claude"
            elif "gemini" in model_name.lower():
                provider = "gemini"
            elif "gpt" in model_name.lower():
                provider = "openai"
            else:
                provider = "openai"  # 默认使用OpenAI

            api_key = get_ai_api_key(provider)
            if not api_key:
                print(f"警告: {model_name} 的 API key 未配置")
                return None

            api_base = get_api_base_url(provider)

            client = AIClientFactory.create(
                model_name=model_name,
                api_key=api_key,
                api_base=api_base
            )
            self.ai_clients[model_name] = client
            return client

        except Exception as e:
            print(f"创建 {model_name} 客户端失败: {e}")
            return None

    def analyze_single_model(
        self,
        chart,  # EnhancedChartWidget
        vt_symbol: str,
        model_name: str,
        model_type: str = "deepseek"
    ) -> None:
        """
        单模型分析

        Args:
            chart: 图表组件
            vt_symbol: 合约代码
            model_name: 模型名称（如 "deepseek-chat"）
            model_type: 模型类型（deepseek/claude/gemini/openai）
        """
        task_id = f"single_{model_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.analysis_started.emit(task_id)

        # 创建分析线程
        thread = self._create_analysis_thread(
            task_id,
            chart,
            vt_symbol,
            model_name,
            model_type,
            "single"
        )

        # 保存线程引用
        self.active_threads[task_id] = thread

        # 启动线程
        thread.start()

    def _create_analysis_thread(
        self,
        task_id: str,
        chart,
        vt_symbol: str,
        model_name: str,
        model_type: str,
        mode: str,  # "single", "multi_model", "multi_timeframe"
        models: List[Dict[str, str]] = None,
        charts: Dict[str, Any] = None
    ) -> QtCore.QThread:
        """创建分析线程"""

        class AIAnalysisThread(QtCore.QThread):
            """AI分析线程"""
            result_signal = QtCore.Signal(dict)
            error_signal = QtCore.Signal(str)

            def __init__(self, coordinator, task_id, chart, vt_symbol, model_name, model_type, mode, models, charts, parent=None):
                super().__init__(parent)
                self.coordinator = coordinator
                self.task_id = task_id
                self.chart = chart
                self.vt_symbol = vt_symbol
                self.model_name = model_name
                self.model_type = model_type
                self.mode = mode
                self.models = models
                self.charts = charts
                self._loop = None

            def run(self):
                self._loop = None
                try:
                    # 创建新的事件循环
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)

                    if self.mode == "single":
                        result = self._loop.run_until_complete(
                            self.coordinator._async_single_analysis(
                                self.chart, self.vt_symbol, self.model_name, self.model_type
                            )
                        )
                    elif self.mode == "multi_model":
                        result = self._loop.run_until_complete(
                            self.coordinator._async_multi_model_analysis(
                                self.chart, self.vt_symbol, self.models
                            )
                        )
                    elif self.mode == "multi_timeframe":
                        result = self._loop.run_until_complete(
                            self.coordinator._async_multi_timeframe_analysis(
                                self.charts, self.vt_symbol, self.model_name, self.model_type
                            )
                        )
                    else:
                        raise ValueError(f"Unknown analysis mode: {self.mode}")

                    self.result_signal.emit(result)

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.error_signal.emit(str(e))

                finally:
                    # 清理事件循环（改进版，Python 3.13兼容）
                    if self._loop:
                        try:
                            # 第一步：取消所有未完成的任务
                            try:
                                pending_tasks = asyncio.all_tasks(self._loop)
                                for task in pending_tasks:
                                    if not task.done():
                                        task.cancel()
                            except Exception as e:
                                print(f"取消任务时出错: {e}")

                            # 第二步：等待所有任务完成或取消（带超时保护）
                            try:
                                if pending_tasks:
                                    # 使用asyncio.wait替代gather，更安全
                                    self._loop.run_until_complete(
                                        asyncio.wait(pending_tasks, timeout=2.0, return_when=asyncio.ALL_COMPLETED)
                                    )
                            except asyncio.TimeoutError:
                                print(f"等待任务完成超时")
                            except Exception as e:
                                print(f"等待任务完成时出错: {e}")

                            # 第三步：关闭异步生成器（带超时保护）
                            try:
                                self._loop.run_until_complete(
                                    asyncio.wait_for(self._loop.shutdown_asyncgens(), timeout=1.0)
                                )
                            except asyncio.TimeoutError:
                                print(f"关闭异步生成器超时")
                            except Exception as e:
                                print(f"关闭异步生成器时出错: {e}")

                            # 第四步：关闭执行器（带超时保护）
                            try:
                                self._loop.run_until_complete(
                                    asyncio.wait_for(self._loop.shutdown_default_executor(), timeout=1.0)
                                )
                            except asyncio.TimeoutError:
                                print(f"关闭执行器超时")
                            except Exception as e:
                                print(f"关闭执行器时出错: {e}")

                            # 第五步：关闭事件循环
                            try:
                                if not self._loop.is_closed():
                                    self._loop.close()
                            except Exception as e:
                                print(f"关闭事件循环时出错: {e}")

                        except Exception as e:
                            print(f"清理事件循环时发生未捕获的异常: {e}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            self._loop = None
                            # 重置事件循环（Python 3.10+）
                            try:
                                asyncio.set_event_loop(None)
                            except Exception:
                                pass

        # 创建线程实例
        thread = AIAnalysisThread(
            self, task_id, chart, vt_symbol, model_name, model_type, mode, models, charts, parent=None
        )

        # 连接信号
        thread.result_signal.connect(lambda result: self._on_thread_result(task_id, result))
        thread.error_signal.connect(lambda error: self._on_thread_error(task_id, error))

        return thread

    def _on_thread_result(self, task_id: str, result: dict):
        """线程完成回调"""
        self.analysis_completed.emit(task_id, result)

        # 清理线程引用
        if task_id in self.active_threads:
            thread = self.active_threads[task_id]
            try:
                thread.deleteLater()
            except:
                pass
            del self.active_threads[task_id]

    def _on_thread_error(self, task_id: str, error_msg: str):
        """线程错误回调"""
        self.analysis_failed.emit(task_id, f"分析失败: {error_msg}")

        # 清理线程引用
        if task_id in self.active_threads:
            thread = self.active_threads[task_id]
            try:
                thread.deleteLater()
            except:
                pass
            del self.active_threads[task_id]

    async def _async_single_analysis(
        self,
        chart,
        vt_symbol: str,
        model_name: str,
        model_type: str
    ) -> dict:
        """异步单模型分析（简化版）"""
        # 采集市场数据（启用所有增强功能）
        market_data = MarketDataCollector.collect_from_chart(
            chart,
            vt_symbol,
            position_manager=self.position_manager,
            include_multi_timeframe=True,
            include_position=True,
            include_auxiliary=True
        )

        # 执行AI分析
        response = await self._async_analyze(market_data, model_name, model_type)

        # 返回结果
        return {
            "model": model_name,
            "type": model_type,
            "result": response,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    async def _async_analyze(
        self,
        market_data: Dict[str, Any],
        model_name: str,
        model_type: str
    ) -> str:
        """异步执行AI分析"""
        from core.logging.logger_manager import get_logger
        logger = get_logger("ai_analysis")

        client = self._get_ai_client(model_name)
        if not client:
            raise ValueError(f"无法创建AI客户端: {model_name}，请检查API key配置")

        # 记录请求信息
        logger.info(f"开始AI分析 - 模型: {model_name}")
        logger.debug(f"市场数据: {market_data}")
        logger.debug(f"系统提示词: {ANALYSIS_AI_PROMPT[:200]}...")  # 只记录前200个字符

        try:
            # 调用AI客户端 - UnifiedAIClient使用analyze方法
            # 注意：UnifiedAIClient内部已使用async with管理httpx.AsyncClient
            # 不需要在此处手动关闭客户端
            response, elapsed_time = await client.analyze(
                market_data=market_data,
                system_prompt=ANALYSIS_AI_PROMPT,
                temperature=0.3
            )

            # 记录响应信息
            logger.info(f"AI分析完成 - 模型: {model_name}, 耗时: {elapsed_time:.2f}秒")
            logger.info(f"AI响应长度: {len(response)} 字符")
            logger.debug(f"AI完整响应:\n{response}")

            return response
        except Exception as e:
            # 记录异常信息
            logger.error(f"AI分析失败 - 模型: {model_name}, 错误: {e}")
            raise

    def analyze_multi_model(
        self,
        chart,
        vt_symbol: str,
        models: List[Dict[str, str]]
    ) -> str:
        """
        多模型对比分析

        Args:
            chart: 图表组件
            vt_symbol: 合约代码
            models: 模型列表，如 [
                {"type": "deepseek", "name": "deepseek-chat"},
                {"type": "claude", "name": "claude-sonnet-4-5-20250929"}
            ]

        Returns:
            task_id: 任务ID
        """
        task_id = f"multi_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.analysis_started.emit(task_id)

        # 创建分析线程
        thread = self._create_analysis_thread(
            task_id,
            chart,
            vt_symbol,
            None,  # model_name not used in multi_model
            None,  # model_type not used in multi_model
            "multi_model",
            models=models
        )

        # 保存线程引用
        self.active_threads[task_id] = thread

        # 启动线程
        thread.start()

        return task_id

    async def _async_multi_model_analysis(
        self,
        chart,
        vt_symbol: str,
        models: List[Dict[str, str]]
    ) -> dict:
        """异步多模型分析（简化版）"""
        # 采集市场数据（启用所有增强功能）
        market_data = MarketDataCollector.collect_from_chart(
            chart,
            vt_symbol,
            position_manager=self.position_manager,
            include_multi_timeframe=True,
            include_position=True,
            include_auxiliary=True
        )

        # 创建所有分析任务
        tasks = [
            self._async_analyze(
                market_data,
                model["name"],
                model["type"]
            )
            for model in models
        ]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        analysis_results = []
        for i, result in enumerate(results):
            model = models[i]
            if isinstance(result, Exception):
                analysis_results.append({
                    "model": model["name"],
                    "type": model["type"],
                    "result": f"分析失败: {str(result)}",
                    "success": False
                })
            else:
                analysis_results.append({
                    "model": model["name"],
                    "type": model["type"],
                    "result": result,
                    "success": True
                })

        # 返回结果
        return {
            "mode": "multi_model",
            "results": analysis_results,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def analyze_multi_timeframe(
        self,
        charts: Dict[str, Any],  # {period: chart}
        vt_symbol: str,
        model_name: str,
        model_type: str = "deepseek"
    ) -> str:
        """
        多周期分析

        Args:
            charts: 周期到图表的映射，如 {"15min": chart1, "1hour": chart2}
            vt_symbol: 合约代码
            model_name: 模型名称
            model_type: 模型类型

        Returns:
            task_id: 任务ID
        """
        task_id = f"multi_tf_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.analysis_started.emit(task_id)

        # 创建分析线程
        thread = self._create_analysis_thread(
            task_id,
            None,  # chart not used in multi_timeframe
            vt_symbol,
            model_name,
            model_type,
            "multi_timeframe",
            charts=charts
        )

        # 保存线程引用
        self.active_threads[task_id] = thread

        # 启动线程
        thread.start()

        return task_id

    async def _async_multi_timeframe_analysis(
        self,
        charts: Dict[str, Any],
        vt_symbol: str,
        model_name: str,
        model_type: str
    ) -> dict:
        """异步多周期分析"""
        # 检查是否是新的数据结构（直接传入聚合后的K线数据）
        if charts and isinstance(list(charts.values())[0], dict) and 'bars' in list(charts.values())[0]:
            # 新数据结构：{period: {'bars': [...], 'interval': period}}
            multi_data = {
                "symbol": vt_symbol,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "timeframes": {}
            }

            for period, data in charts.items():
                bars = data['bars']
                if bars:
                    # 计算指标数据（为聚合后的K线也提供指标支持）
                    indicators = MarketDataCollector._calculate_indicators_for_bars(bars)

                    multi_data["timeframes"][period] = {
                        "count": len(bars),
                        "bars": MarketDataCollector._format_bars(bars[-20:]),
                        "indicators": indicators
                    }
        else:
            # 旧数据结构：{period: chart_object}
            multi_data = MarketDataCollector.collect_multi_timeframe(charts, vt_symbol)

        # 为每个周期创建分析任务
        tasks = []
        periods = []
        for period, data in multi_data.get("timeframes", {}).items():
            periods.append(period)
            # 构造单周期市场数据
            period_market_data = {
                "symbol": vt_symbol,
                "datetime": multi_data["datetime"],
                "current_interval": period,
                "recent_bars_info": {
                    "current_timeframe": {
                        "timeframe": period,
                        "count": data["count"],
                        "bars": data["bars"]
                    }
                },
                "indicators": data.get("indicators", {})
            }
            tasks.append(
                self._async_analyze(period_market_data, model_name, model_type)
            )

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        timeframe_results = []
        for i, result in enumerate(results):
            period = periods[i]
            if isinstance(result, Exception):
                timeframe_results.append({
                    "period": period,
                    "result": f"分析失败: {str(result)}",
                    "success": False
                })
            else:
                timeframe_results.append({
                    "period": period,
                    "result": result,
                    "success": True
                })

        # 返回结果
        return {
            "mode": "multi_timeframe",
            "model": model_name,
            "type": model_type,
            "results": timeframe_results,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def send_notification(self, content: str, vt_symbol: str) -> None:
        """
        发送通知

        Args:
            content: 通知内容
            vt_symbol: 合约代码
        """
        try:
            alert_manager.send_alert(
                content=content,
                symbol=vt_symbol,
                force_send=True
            )
        except Exception as e:
            print(f"发送通知失败: {e}")

    def cleanup(self) -> None:
        """清理资源"""
        # 终止所有活动线程
        for task_id, thread in list(self.active_threads.items()):
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(1000)  # 等待最多1秒
                    if thread.isRunning():
                        # 如果线程仍在运行，强制终止
                        thread.terminate()
                        thread.wait(500)
                thread.deleteLater()
            except Exception as e:
                print(f"清理线程 {task_id} 时出错: {e}")

        self.active_threads.clear()

        # 清理AI客户端
        # 注意：UnifiedAIClient实例本身不持有长期的httpx连接
        # httpx.AsyncClient在analyze()方法中通过async with自动管理
        # 因此只需要清除客户端引用即可，不需要手动关闭httpx连接
        self.ai_clients.clear()
