#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI回测存储模型

使用MySQL数据库存储回测交易记录和决策记录
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional
from functools import wraps

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, Index
)
from sqlalchemy.exc import OperationalError

# 使用vnpy_mysql的基础设施
try:
    from vnpy_mysql.mysql_database import Base, engine, get_db_session, close_db_session
except ImportError:
    # 本地配置回退
    from sqlalchemy import create_engine
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    from vnpy.trader.setting import SETTINGS

    Base = declarative_base()
    DATABASE_URL = f"mysql+pymysql://{SETTINGS['database.user']}:{SETTINGS['database.password']}@{SETTINGS['database.host']}:{SETTINGS['database.port']}/{SETTINGS['database.database']}?charset=utf8mb4"
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def get_db_session():
        return SessionLocal()

    def close_db_session(session):
        session.close()


logger = logging.getLogger("backtest_storage")

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1

# MySQL错误代码
DEADLOCK_ERROR = 1213
CONNECTION_LOST_ERROR = 2013
SERVER_GONE_ERROR = 2006
LOCK_TIMEOUT_ERROR = 1205


def retry_on_db_error(max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    """数据库操作重试装饰器

    处理常见的数据库错误并自动重试：
    - 死锁错误 (1213)
    - 连接丢失错误 (2013)
    - 服务器丢失错误 (2006)
    - 锁超时错误 (1205)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    error_code = e.orig.args[0] if hasattr(e, 'orig') and e.orig.args else None

                    # 检查是否是可重试的错误
                    if error_code in (DEADLOCK_ERROR, LOCK_TIMEOUT_ERROR,
                                    CONNECTION_LOST_ERROR, SERVER_GONE_ERROR):
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"数据库操作遇到错误(代码:{error_code}), "
                                f"正在重试({attempt+1}/{max_retries})"
                            )
                            time.sleep(retry_delay * (attempt + 1))  # 指数退避
                            last_error = e
                            continue

                    # 不可重试的错误，直接抛出
                    logger.error(f"数据库操作失败: {e}")
                    raise
                except Exception as e:
                    last_error = e
                    logger.error(f"未预期的数据库错误: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    raise

            # 所有重试都失败了
            if last_error:
                raise last_error
            raise Exception("未知原因导致的操作失败")

        return wrapper
    return decorator


class DbBacktestTrade(Base):
    """回测交易记录ORM模型"""
    __tablename__ = 'backtest_trades'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 回测运行ID
    run_id = Column(String(100), nullable=False, index=True)
    # 交易时间
    trade_time = Column(DateTime, nullable=False, index=True)
    # 合约代码
    symbol = Column(String(50), nullable=False, index=True)
    # 交易方向 (LONG/SHORT)
    side = Column(String(10), nullable=False)
    # 操作类型 (open/close/add/reduce)
    action = Column(String(20), nullable=False)
    # 成交数量
    quantity = Column(Float, nullable=False)
    # 成交价格
    price = Column(Float, nullable=False)
    # 总手续费
    fee = Column(Float, nullable=False)
    # 按比例手续费部分
    fee_rate_portion = Column(Float, nullable=False)
    # 固定手续费部分
    fixed_fee_portion = Column(Float, nullable=False)
    # 已实现盈亏
    realized_pnl = Column(Float, default=0.0)
    # 持仓ID
    position_id = Column(String(100), nullable=True)
    # 备注
    note = Column(Text, nullable=True)
    # 记录创建时间
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # 创建复合索引
    __table_args__ = (
        Index('idx_runid_time', 'run_id', 'trade_time'),
        Index('idx_runid_symbol', 'run_id', 'symbol'),
    )


class DbBacktestDecision(Base):
    """回测决策记录ORM模型"""
    __tablename__ = 'backtest_decisions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 回测运行ID
    run_id = Column(String(100), nullable=False, index=True)
    # 决策时间
    decision_time = Column(DateTime, nullable=False, index=True)
    # 决策周期
    decision_cycle = Column(Integer, nullable=False)
    # 上下文哈希（用于缓存）
    context_hash = Column(String(64), nullable=False, index=True)
    # 决策内容 (JSON格式)
    decision_data = Column(Text, nullable=False)
    # 是否使用缓存
    cached = Column(Boolean, default=False, nullable=False)
    # AI调用成本
    ai_cost = Column(Float, default=0.0)
    # 延迟（毫秒）
    latency_ms = Column(Float, default=0.0)
    # 记录创建时间
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # 创建复合索引
    __table_args__ = (
        Index('idx_runid_decision_time', 'run_id', 'decision_time'),
        Index('idx_runid_context_hash', 'run_id', 'context_hash'),
    )


@retry_on_db_error()
def save_backtest_trade(
    run_id: str,
    trade_time: datetime,
    symbol: str,
    side: str,
    action: str,
    quantity: float,
    price: float,
    fee: float,
    fee_rate_portion: float,
    fixed_fee_portion: float,
    realized_pnl: float = 0.0,
    position_id: Optional[str] = None,
    note: str = ""
) -> bool:
    """保存回测交易记录

    Args:
        run_id: 回测运行ID
        trade_time: 交易时间
        symbol: 合约代码
        side: 交易方向 (LONG/SHORT)
        action: 操作类型 (open/close/add/reduce)
        quantity: 成交数量
        price: 成交价格
        fee: 总手续费
        fee_rate_portion: 按比例手续费部分
        fixed_fee_portion: 固定手续费部分
        realized_pnl: 已实现盈亏
        position_id: 持仓ID
        note: 备注

    Returns:
        是否保存成功
    """
    session = get_db_session()
    try:
        trade = DbBacktestTrade(
            run_id=run_id,
            trade_time=trade_time,
            symbol=symbol,
            side=side,
            action=action,
            quantity=quantity,
            price=price,
            fee=fee,
            fee_rate_portion=fee_rate_portion,
            fixed_fee_portion=fixed_fee_portion,
            realized_pnl=realized_pnl,
            position_id=position_id,
            note=note
        )
        session.add(trade)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"保存回测交易记录失败: {e}")
        raise
    finally:
        close_db_session(session)


@retry_on_db_error()
def save_backtest_decision(
    run_id: str,
    decision_time: datetime,
    decision_cycle: int,
    context_hash: str,
    decision_data: dict,
    cached: bool = False,
    ai_cost: float = 0.0,
    latency_ms: float = 0.0
) -> bool:
    """保存回测决策记录

    Args:
        run_id: 回测运行ID
        decision_time: 决策时间
        decision_cycle: 决策周期
        context_hash: 上下文哈希
        decision_data: 决策内容（字典）
        cached: 是否使用缓存
        ai_cost: AI调用成本
        latency_ms: 延迟（毫秒）

    Returns:
        是否保存成功
    """
    session = get_db_session()
    try:
        decision = DbBacktestDecision(
            run_id=run_id,
            decision_time=decision_time,
            decision_cycle=decision_cycle,
            context_hash=context_hash,
            decision_data=json.dumps(decision_data, ensure_ascii=False),
            cached=cached,
            ai_cost=ai_cost,
            latency_ms=latency_ms
        )
        session.add(decision)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"保存回测决策记录失败: {e}")
        raise
    finally:
        close_db_session(session)


@retry_on_db_error()
def get_backtest_trades(run_id: str) -> list:
    """获取指定回测的交易记录

    Args:
        run_id: 回测运行ID

    Returns:
        DbBacktestTrade对象列表
    """
    session = get_db_session()
    try:
        results = session.query(DbBacktestTrade).filter(
            DbBacktestTrade.run_id == run_id
        ).order_by(DbBacktestTrade.trade_time.asc()).all()
        return results
    except Exception as e:
        logger.error(f"获取回测交易记录失败: {e}")
        raise
    finally:
        close_db_session(session)


@retry_on_db_error()
def get_backtest_decisions(run_id: str) -> list:
    """获取指定回测的决策记录

    Args:
        run_id: 回测运行ID

    Returns:
        DbBacktestDecision对象列表
    """
    session = get_db_session()
    try:
        results = session.query(DbBacktestDecision).filter(
            DbBacktestDecision.run_id == run_id
        ).order_by(DbBacktestDecision.decision_time.asc()).all()
        return results
    except Exception as e:
        logger.error(f"获取回测决策记录失败: {e}")
        raise
    finally:
        close_db_session(session)


def create_backtest_tables():
    """创建回测存储数据表"""
    try:
        Base.metadata.create_all(engine)
        logger.info("回测存储数据表创建成功！")
    except Exception as e:
        logger.error(f"创建回测存储数据表失败: {e}")
        raise e


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建数据表
    create_backtest_tables()
