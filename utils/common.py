import numpy as np


# 辅助函数，用于安全地格式化浮点数
def format_float(value, precision=4):
    if value is None or np.isnan(value) or math.isinf(value): # Added inf check
        return None
    return round(float(value), precision)

def format_bollinger_position(bollinger_position):
    """格式化布林带位置数据"""
    if not bollinger_position:
        return None
    
    formatted = {}
    for k, v in bollinger_position.items():
        if isinstance(v, float):
            formatted[k] = format_float(v, 2 if "percent" in k or "relative" in k else 4)
        else:
            formatted[k] = v
    return formatted

def format_wavetrend_data(wt_signal):
    """格式化WaveTrend数据"""
    if not wt_signal:
        return None
    
    return {
        "wt1": format_float(wt_signal.get("wt1"), 2),
        "wt2": format_float(wt_signal.get("wt2"), 2),
        "difference": format_float(wt_signal.get("wt_diff"), 2),
        "current_status_signal": wt_signal.get("status"),
        "trade_signal": wt_signal.get("signal")
    }

def get_ema_data(fast_ema, slow_ema, long_ema, current_price):
    """获取EMA数据"""
    if any(v is None for v in [fast_ema, slow_ema, long_ema, current_price]):
        return None
    
    return {
        "current_values": {
            "fast_ema": format_float(fast_ema, 4),
            "slow_ema": format_float(slow_ema, 4),
            "long_ema": format_float(long_ema, 4)
        },
        "price_relation": { 
            "above_fast_ema": bool(current_price > fast_ema),
            "above_slow_ema": bool(current_price > slow_ema),
            "above_long_ema": bool(current_price > long_ema),
            "percent_from_fast_ema": format_float((current_price / fast_ema - 1) * 100 if fast_ema != 0 else None, 2),
            "percent_from_slow_ema": format_float((current_price / slow_ema - 1) * 100 if slow_ema != 0 else None, 2),
            "percent_from_long_ema": format_float((current_price / long_ema - 1) * 100 if long_ema != 0 else None, 2)
        },
        "alignment": {
            "fast_above_slow": bool(fast_ema > slow_ema),
            "fast_above_long": bool(fast_ema > long_ema),
            "slow_above_long": bool(slow_ema > long_ema),
            "bullish_alignment": bool(fast_ema > slow_ema > long_ema),
            "bearish_alignment": bool(fast_ema < slow_ema < long_ema)
        }
    }

def get_sma_data(short_sma, mid_sma, long_sma, current_price):
    """获取SMA数据"""
    if any(v is None for v in [short_sma, mid_sma, long_sma, current_price]):
        return None
    
    return {
        "current_values": {
            "short_sma": format_float(short_sma, 4),
            "mid_sma": format_float(mid_sma, 4),
            "long_sma": format_float(long_sma, 4)
        },
        "price_relation": { 
            "above_short_sma": bool(current_price > short_sma),
            "above_mid_sma": bool(current_price > mid_sma),
            "above_long_sma": bool(current_price > long_sma),
            "percent_from_short_sma": format_float((current_price / short_sma - 1) * 100 if short_sma != 0 else None, 2),
            "percent_from_mid_sma": format_float((current_price / mid_sma - 1) * 100 if mid_sma != 0 else None, 2),
            "percent_from_long_sma": format_float((current_price / long_sma - 1) * 100 if long_sma != 0 else None, 2)
        },
        "alignment": {
            "short_above_mid": bool(short_sma > mid_sma),
            "short_above_long": bool(short_sma > long_sma),
            "mid_above_long": bool(mid_sma > long_sma),
            "bullish_alignment": bool(short_sma > mid_sma > long_sma),
            "bearish_alignment": bool(short_sma < mid_sma < long_sma)
        }
    }
