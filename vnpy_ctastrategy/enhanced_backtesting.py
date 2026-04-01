"""
增强的回测指标计算模块
在原有回测框架基础上增加更多重要的回测指标
"""
from typing import List, Dict, Tuple
from copy import copy
import numpy as np
from pandas import DataFrame
from vnpy.trader.object import TradeData
from vnpy.trader.constant import Direction


def calculate_daily_trading_hours(vt_symbol: str) -> float:
    """
    计算品种每日实际交易时长（小时）

    注意：这里返回的是实际交易时间，不包含休息时间。

    Args:
        vt_symbol: 品种代码，如 "rb2605.SHFE"

    Returns:
        每日交易时长（小时），默认返回24（对于未知品种）
    """
    try:
        from vnpy.trader.utility import extract_vt_symbol
    except ImportError:
        return 24.0

    try:
        symbol, exchange = extract_vt_symbol(vt_symbol)
        exchange_str = exchange.value if hasattr(exchange, 'value') else str(exchange)
        symbol_upper = symbol.upper()
        exchange_upper = exchange_str.upper()

        # 中国期货日盘实际交易时长（不含休息时间）
        # 9:00-10:15(75分钟) + 10:30-11:30(60分钟) + 13:30-15:00(90分钟) = 225分钟 = 3.75小时
        CN_DAY_SESSION_HOURS = 3.75

        # 中国期货夜盘时长（按品种分类）
        # 格式：{品种前缀: 夜盘时长(小时)}
        CN_NIGHT_SESSION_HOURS = {
            # 无夜盘品种
            "无": 0,

            # 夜盘到23:00的品种（2小时）
            "23:00": 2.0,
            # 螺纹钢、热卷、线材、燃油、纸浆、橡胶、沥青、焦煤、焦炭、动力煤、铁矿石等

            # 夜盘到01:00的品种（4小时）
            "01:00": 4.0,
            # 铜、铝、锌、铅、镍、锡、不锈钢、甲醇、PTA、棉花、白糖、菜油、菜粕、玻璃、纯碱、短纤等

            # 夜盘到02:30的品种（5.5小时）
            "02:30": 5.5,
            # 黄金、白银、原油
        }

        # 品种夜盘收盘时间映射
        NIGHT_CLOSE_MAP = {
            # 上期所 (SHFE)
            "RB": "23:00",  # 螺纹钢
            "HC": "23:00",  # 热卷
            "WR": "23:00",  # 线材
            "FU": "01:00",  # 燃油
            "SP": "23:00",  # 纸浆
            "RU": "23:00",  # 橡胶
            "BU": "23:00",  # 沥青
            "CU": "01:00",  # 铜
            "AL": "01:00",  # 铝
            "ZN": "01:00",  # 锌
            "PB": "01:00",  # 铅
            "NI": "01:00",  # 镍
            "SN": "01:00",  # 锡
            "SS": "01:00",  # 不锈钢
            "AU": "02:30",  # 黄金
            "AG": "02:30",  # 白银
            "AD": "01:00",  # 铸造铝
            "AO": "01:00",  # 氧化铝
            "BR": "23:00",  # 丁二烯橡胶

            # 上期能源 (INE)
            "SC": "02:30",  # 原油
            "NR": "23:00",  # 20号胶
            "LU": "23:00",  # 低硫燃油
            "BC": "01:00",  # 国际铜
            "EC": "无",     # 集运指数（无夜盘）

            # 大商所 (DCE)
            "J": "23:00",   # 焦炭
            "JM": "23:00",  # 焦煤
            "ZC": "23:00",  # 动力煤（郑商所品种，但代码在DCE也有）
            "I": "23:00",   # 铁矿石
            "A": "23:00",   # 豆一
            "B": "23:00",   # 豆二
            "M": "23:00",   # 豆粕
            "Y": "23:00",   # 豆油
            "P": "23:00",   # 棕榈油
            "C": "23:00",   # 玉米
            "CS": "23:00",  # 淀粉
            "JD": "23:00",  # 鸡蛋
            "L": "23:00",   # 塑料
            "V": "23:00",   # PVC
            "PP": "23:00",  # 聚丙烯
            "EB": "23:00",  # 苯乙烯
            "EG": "23:00",  # 乙二醇
            "PG": "01:00",  # 液化石油气
            "BB": "无",     # 胶合板（无夜盘）
            "BZ": "无",     # 苯（无夜盘）
            "FB": "无",     # 纤维板（无夜盘）
            "LG": "无",     # 原木（无夜盘）
            "LH": "无",     # 生猪（无夜盘）
            "RR": "无",     # 粳米（无夜盘）

            # 郑商所 (CZCE)
            "SR": "23:00",  # 白糖
            "CF": "23:00",  # 棉花
            "TA": "23:00",  # PTA
            "MA": "23:00",  # 甲醇
            "FG": "23:00",  # 玻璃
            "SA": "23:00",  # 纯碱
            "OI": "23:00",  # 菜油
            "RM": "23:00",  # 菜粕
            "PF": "23:00",  # 短纤
            "AP": "无",     # 苹果（无夜盘）
            "CJ": "无",     # 红枣（无夜盘）
            "UR": "23:00",  # 尿素
            "SF": "无",     # 硅铁（无夜盘）
            "SM": "无",     # 锰硅（无夜盘）
            "CY": "23:00",  # 棉纱
            "JR": "无",     # 粳稻（无夜盘）
            "LR": "无",     # 晚籼稻（无夜盘）
            "PK": "无",     # 花生（无夜盘）
            "PM": "无",     # 普麦（无夜盘）
            "PR": "23:00",  # 瓶片
            "PX": "23:00",  # 对二甲苯
            "RI": "无",     # 早籼稻（无夜盘）
            "RS": "无",     # 菜籽（无夜盘）
            "WH": "无",     # 强麦（无夜盘）

            # 广期所 (GFEX)
            "SI": "23:00",  # 工业硅
            "LC": "23:00",  # 碳酸锂
            "PS": "无",     # 聚苯乙烯（无夜盘）
        }

        # 中金所品种（无夜盘）
        if exchange_upper == "CFFEX":
            # 9:30-11:30(2小时) + 13:00-15:00(2小时) = 4小时
            return 4.0

        # 中国期货市场
        if exchange_upper in ["SHFE", "DCE", "CZCE", "INE", "GFEX"]:
            # 获取品种前缀（去掉月份数字）
            prefix = ""
            for char in symbol_upper:
                if char.isalpha():
                    prefix += char
                else:
                    break

            # 查找夜盘收盘时间
            night_close = NIGHT_CLOSE_MAP.get(prefix, "23:00")  # 默认到23:00
            night_hours = CN_NIGHT_SESSION_HOURS.get(night_close, 2.0)

            return CN_DAY_SESSION_HOURS + night_hours

        # A股市场
        if exchange_upper in ["SSE", "SZSE"]:
            # 9:30-11:30(2小时) + 13:00-15:00(2小时) = 4小时
            return 4.0

        # 其他市场默认24小时
        return 24.0

    except Exception:
        return 24.0  # 出错时返回默认值


def generate_trade_pairs(trades: List[TradeData]) -> List[Dict]:
    """
    生成交易配对，用于计算交易级别的统计指标
    """
    long_trades: List[TradeData] = []
    short_trades: List[TradeData] = []
    trade_pairs: List[Dict] = []

    for trade in trades:
        trade: TradeData = copy(trade)

        if trade.direction == Direction.LONG:
            same_direction: List[TradeData] = long_trades
            opposite_direction: List[TradeData] = short_trades
        else:
            same_direction: List[TradeData] = short_trades
            opposite_direction: List[TradeData] = long_trades

        while trade.volume and opposite_direction:
            open_trade: TradeData = opposite_direction[0]

            close_volume = min(open_trade.volume, trade.volume)
            
            # 计算持仓时间（以小时为单位）
            holding_time_hours = (trade.datetime - open_trade.datetime).total_seconds() / 3600
            
            d: Dict = {
                "open_dt": open_trade.datetime,
                "open_price": open_trade.price,
                "close_dt": trade.datetime,
                "close_price": trade.price,
                "direction": open_trade.direction,
                "volume": close_volume,
                "holding_time_hours": holding_time_hours,
            }
            trade_pairs.append(d)

            open_trade.volume -= close_volume
            if not open_trade.volume:
                opposite_direction.pop(0)

            trade.volume -= close_volume

        if trade.volume:
            same_direction.append(trade)

    return trade_pairs


def calculate_trade_statistics(trade_pairs: List[Dict], size: float, vt_symbol: str = "") -> Dict:
    """
    计算交易级别的统计指标

    Args:
        trade_pairs: 交易配对列表
        size: 合约乘数
        vt_symbol: 品种代码，用于计算准确的持仓天数
    """
    # 计算品种每日实际交易时长
    daily_trading_hours = calculate_daily_trading_hours(vt_symbol) if vt_symbol else 24.0

    if not trade_pairs:
        return {
            "win_rate": 0.0,
            "average_win_loss_ratio": 0.0,
            "optimal_position_ratio": 0.0,
            "profit_factor": 0.0,
            "average_trade": 0.0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            # 多头空头笔数统计
            "long_trade_count": 0,
            "short_trade_count": 0,
            "average_holding_time_days": 0.0,
            "average_holding_time_hours": 0.0,
            "max_holding_time_hours": 0.0,
            "min_holding_time_hours": 0.0,
            "median_holding_time_hours": 0.0,
            # 每日交易时长（用于调试和显示）
            "daily_trading_hours": daily_trading_hours
        }

    # 计算每笔交易的盈亏和统计多头空头笔数
    trade_pnls = []
    holding_times = []
    long_trade_count = 0
    short_trade_count = 0
    
    for pair in trade_pairs:
        if pair["direction"] == Direction.LONG:
            pnl = (pair["close_price"] - pair["open_price"]) * pair["volume"] * size
            long_trade_count += 1
        else:
            pnl = (pair["open_price"] - pair["close_price"]) * pair["volume"] * size
            short_trade_count += 1
        
        trade_pnls.append(pnl)
        holding_times.append(pair["holding_time_hours"])

    # 基础统计
    winning_trades = [pnl for pnl in trade_pnls if pnl > 0]
    losing_trades = [pnl for pnl in trade_pnls if pnl < 0]

    win_rate = len(winning_trades) / len(trade_pnls)
    average_win = np.mean(winning_trades) if winning_trades else 0
    average_loss = abs(np.mean(losing_trades)) if losing_trades else 0
    average_win_loss_ratio = average_win / average_loss if average_loss else 0

    # 计算凯利公式最优仓位
    optimal_position = calculate_kelly_ratio(win_rate, average_win, average_loss)

    # 计算获利因子
    total_wins = np.sum(winning_trades) if winning_trades else 0
    total_losses = abs(np.sum(losing_trades)) if losing_trades else 0
    profit_factor = total_wins / total_losses if total_losses else 0

    # 计算平均每笔交易盈亏
    average_trade = np.mean(trade_pnls)

    # 计算最大连续盈利和亏损次数
    consecutive_wins = 0
    consecutive_losses = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    for pnl in trade_pnls:
        if pnl > 0:
            consecutive_wins += 1
            consecutive_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
        elif pnl < 0:
            consecutive_losses += 1
            consecutive_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
    
    # 确保返回的是整数类型
    max_consecutive_wins = int(max_consecutive_wins)
    max_consecutive_losses = int(max_consecutive_losses)

    # 持仓时间统计（同时提供小时和天为单位）
    average_holding_time_hours = np.mean(holding_times) if holding_times else 0
    max_holding_time_hours = np.max(holding_times) if holding_times else 0
    min_holding_time_hours = np.min(holding_times) if holding_times else 0
    median_holding_time_hours = np.median(holding_times) if holding_times else 0

    # 转换为天为单位（使用品种每日实际交易时长）
    # 例如：螺纹钢每日交易约10小时，则持仓10小时 = 1个交易日
    average_holding_time_days = average_holding_time_hours / daily_trading_hours
    max_holding_time_days = max_holding_time_hours / daily_trading_hours
    min_holding_time_days = min_holding_time_hours / daily_trading_hours
    median_holding_time_days = median_holding_time_hours / daily_trading_hours

    return {
        "win_rate": win_rate,
        "average_win_loss_ratio": average_win_loss_ratio,
        "optimal_position_ratio": optimal_position,
        "profit_factor": profit_factor,
        "average_trade": average_trade,
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
        # 多头空头笔数统计
        "long_trade_count": long_trade_count,
        "short_trade_count": short_trade_count,
        # 小时为单位的持仓时间
        "average_holding_time_hours": average_holding_time_hours,
        "max_holding_time_hours": max_holding_time_hours,
        "min_holding_time_hours": min_holding_time_hours,
        "median_holding_time_hours": median_holding_time_hours,
        # 天为单位的持仓时间（基于品种实际交易时长）
        "average_holding_time_days": average_holding_time_days,
        "max_holding_time_days": max_holding_time_days,
        "min_holding_time_days": min_holding_time_days,
        "median_holding_time_days": median_holding_time_days,
        # 每日交易时长（用于调试和显示）
        "daily_trading_hours": daily_trading_hours
    }


def calculate_kelly_ratio(win_rate: float, average_win: float, average_loss: float) -> float:
    """计算凯利公式最优仓位"""
    if not average_loss or average_win <= 0 or win_rate <= 0:
        return 0

    p = win_rate
    q = 1 - p
    b = average_win / average_loss

    # 凯利公式计算
    f_star = (b * p - q) / b

    # 限制仓位在0-1之间
    f_star = max(0, min(1, f_star))

    # 使用半凯利仓位
    return f_star * 0.5


def calculate_advanced_metrics(daily_df: DataFrame, capital: float, risk_free: float = 0.02, annual_days: int = 240) -> Dict:
    """
    计算高级风险指标
    """
    if daily_df.empty:
        return {}

    # 计算日收益率
    daily_returns = daily_df["net_pnl"] / capital
    
    # 计算下行波动率
    mar = risk_free / annual_days  # 日度最小可接受收益率
    downside_returns = []
    for daily_return in daily_returns:
        downside_diff = daily_return - mar
        if downside_diff < 0:
            downside_returns.append(downside_diff)

    down_std = np.sqrt(np.mean(np.square(downside_returns))) if downside_returns else 0
    annual_down_std = down_std * np.sqrt(annual_days)  # 年化下行波动率

    # 计算索提诺比率
    annual_return = daily_returns.mean() * annual_days
    if annual_down_std:
        sortino_ratio = (annual_return - risk_free) / annual_down_std
    else:
        sortino_ratio = 0

    # 计算卡尔马比率
    max_ddpercent = daily_df["ddpercent"].min() if "ddpercent" in daily_df.columns else 0
    calmar_ratio = abs(annual_return * 100 / max_ddpercent) if max_ddpercent else 0

    return {
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "annual_down_std": annual_down_std,
    }


def calculate_monthly_statistics(trade_pairs: List[Dict], size: float) -> DataFrame:
    """
    计算月度统计数据
    """
    if not trade_pairs:
        return DataFrame()

    # 计算每笔交易的盈亏
    trade_data = []
    for pair in trade_pairs:
        if pair["direction"] == Direction.LONG:
            pnl = (pair["close_price"] - pair["open_price"]) * pair["volume"] * size
        else:
            pnl = (pair["open_price"] - pair["close_price"]) * pair["volume"] * size
        
        trade_data.append({
            "close_dt": pair["close_dt"],
            "pnl": pnl
        })

    if not trade_data:
        return DataFrame()

    # 创建DataFrame
    trade_df = DataFrame(trade_data)
    trade_df["close_dt"] = trade_df["close_dt"].dt.tz_localize(None)
    trade_df["month"] = trade_df["close_dt"].dt.to_period("M")

    # 计算每月的统计数据
    monthly_stats = trade_df.groupby("month").agg(
        total_trades=("pnl", "size"),
        win_rate=("pnl", lambda x: (x > 0).sum() / x.size if x.size > 0 else 0),
        total_pnl=("pnl", "sum")
    ).reset_index()

    # 将win_rate转换为百分比
    monthly_stats["win_rate"] = (monthly_stats["win_rate"] * 100).apply(lambda x: f"{x:.2f}%")

    return monthly_stats


def calculate_interval_statistics(trade_pairs: List[Dict], size: float) -> DataFrame:
    """
    计算每个半小时交易区间的统计数据
    """
    if not trade_pairs:
        return DataFrame()

    # 计算每笔交易的盈亏
    trade_data = []
    for pair in trade_pairs:
        if pair["direction"] == Direction.LONG:
            pnl = (pair["close_price"] - pair["open_price"]) * pair["volume"] * size
        else:
            pnl = (pair["open_price"] - pair["close_price"]) * pair["volume"] * size
        
        # 创建半小时区间标识
        open_dt = pair["open_dt"]
        interval_start = f"{open_dt.hour:02d}:{open_dt.minute // 30 * 30:02d}"
        
        trade_data.append({
            "interval_start": interval_start,
            "pnl": pnl
        })

    if not trade_data:
        return DataFrame()

    # 创建DataFrame
    trade_df = DataFrame(trade_data)

    # 按半小时区间分组计算统计数据
    interval_stats = trade_df.groupby("interval_start").agg(
        total_trades=("pnl", "size"),
        win_rate=("pnl", lambda x: (x > 0).sum() / x.size if x.size > 0 else 0),
        total_pnl=("pnl", "sum")
    ).reset_index()

    # 格式化胜率
    interval_stats["win_rate"] = (interval_stats["win_rate"] * 100).apply(lambda x: f"{x:.2f}%")

    # 按total_pnl升序排序
    interval_stats = interval_stats.sort_values(by="total_pnl", ascending=True)

    return interval_stats


def calculate_comprehensive_rating(statistics: Dict) -> float:
    """
    计算综合评分
    基于多个指标的加权平均，使用对数变换处理极端值
    """
    try:
        # 获取关键指标
        ewm_sharpe = statistics.get("ewm_sharpe", 0)
        max_ddpercent = statistics.get("max_ddpercent", 0)
        win_rate = statistics.get("win_rate", 0)
        average_win_loss_ratio = statistics.get("average_win_loss_ratio", 0)
        calmar_ratio = statistics.get("calmar_ratio", 0)
        
        # 归一化处理
        normalized_sharpe = (
            0 if ewm_sharpe <= 0
            else np.log1p(ewm_sharpe)  # 使用log1p避免极端值影响
        )

        # 最大回撤处理（越小越好）
        normalized_drawdown = 1 - min(abs(max_ddpercent) / 100, 1)  # 限制在0-1之间

        # 盈亏比处理
        normalized_winloss = (
            0 if average_win_loss_ratio <= 1
            else np.log1p(average_win_loss_ratio - 1)
        )

        # 胜率处理
        normalized_winrate = (
            0 if win_rate < 0.35  # 保留最低门槛
            else win_rate
        )

        # 卡尔马比率处理
        normalized_calmar = (
            0 if calmar_ratio <= 0
            else np.log1p(calmar_ratio)
        )

        # 综合评分
        overall_rating = (
            0.35 * normalized_sharpe +     # EWM Sharpe权重35%
            0.30 * normalized_drawdown +   # 最大回撤权重30%
            0.20 * normalized_winrate +    # 胜率权重20%
            0.10 * normalized_winloss +    # 盈亏比权重10%
            0.05 * normalized_calmar       # 卡尔马比率权重5%
        )

        return overall_rating

    except Exception:
        return 0