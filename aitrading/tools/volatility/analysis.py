# aitrading/tools/volatility/analysis.py

from typing import Dict, Any
import pandas as pd
import logfire

from .indicators import (
    calculate_atr, calculate_adx_components, calculate_efficiency_ratio,
    calculate_money_flow_ratio, calculate_normalized_atr
)


def analyze_volatility_nature(df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
    """
    Analyze volatility nature by combining multiple metrics.
    
    Returns:
        Dict with:
        - directional_strength: 0-1 (how directional the volatility is)
        - volatility_score: absolute volatility measure
        - chaos_ratio: proportion of non-directional volatility
    """
    try:
        # 1. Normalized ATR for price-relative volatility
        norm_atr = calculate_normalized_atr(df, period)
        
        # 2. ADX and directional components
        adx, pos_di, neg_di = calculate_adx_components(df, period)
        
        # 3. Efficiency Ratio for movement quality
        er = calculate_efficiency_ratio(df, period)
        
        # 4. Money Flow Ratio for volume confirmation
        mf_ratio = calculate_money_flow_ratio(df, period)
        
        # 5. Normalize money flow ratio to 0-1 range
        norm_mf = mf_ratio / (1 + mf_ratio)
        
        # 6. Calculate directional ratio from ADX components
        di_diff = abs(pos_di - neg_di)
        di_sum = pos_di + neg_di
        di_ratio = di_diff / di_sum
        
        # 7. Compose final directional strength with more weight on price efficiency
        directional_strength = (
            0.5 * er +         # Efficiency Ratio: primary measure of price efficiency
            0.3 * di_ratio +   # ADX components: trend strength confirmation
            0.2 * norm_mf      # Volume confirmation: validate with flow
        ).fillna(0)
        
        # Get final values (last in series)
        last_directional = float(directional_strength.iloc[-1])
        last_vol = float(norm_atr.iloc[-1])
        
        result = {
            'directional_strength': last_directional,
            'volatility_score': last_vol,
            'chaos_ratio': 1 - last_directional,
            'efficiency_ratio': float(er.iloc[-1]),
            'di_ratio': float(di_ratio.iloc[-1]),
            'money_flow_norm': float(norm_mf.iloc[-1])
        }
        
        logfire.debug(
            "Volatility nature analysis",
            raw_metrics=result,
            interpretation={
                "directional_quality": "strong" if last_directional > 0.7 else "moderate" if last_directional > 0.4 else "weak",
                "volatility_level": "very_high" if last_vol > 0.12 else "high" if last_vol > 0.06 else "normal" if last_vol > 0.03 else "low",
                "chaos_level": "high" if result['chaos_ratio'] > 0.6 else "moderate" if result['chaos_ratio'] > 0.3 else "low"
            }
        )
        
        return result
        
    except Exception as e:
        logfire.error(f"Error in analyze_volatility_nature: {str(e)}")
        return {
            'directional_strength': 0.0,
            'volatility_score': 0.0,
            'chaos_ratio': 1.0,
            'efficiency_ratio': 0.0,
            'di_ratio': 0.0,
            'money_flow_norm': 0.0
        }


def interpret_volatility(metrics: Dict[str, float]) -> Dict[str, Any]:
    """
    Interpret volatility nature and provide operational guidance.
    
    This function takes the raw volatility metrics and provides:
    1. Volatility classification
    2. Directionality assessment
    3. Trading implications
    4. Risk adjustment recommendations
    """
    vol_score = metrics['volatility_score']
    dir_strength = metrics['directional_strength']
    chaos_ratio = metrics['chaos_ratio']
    
    # Classify volatility considering both magnitude and nature
    if vol_score < 0.03:  # 3% della media mobile
        volatility_class = "LOW"
    elif vol_score < 0.06:  # 6% della media mobile
        volatility_class = "NORMAL"
    elif vol_score < 0.12:  # 12% della media mobile
        volatility_class = "HIGH"
    else:
        # Classifica EXTREME solo se anche caotica
        if chaos_ratio > 0.6:  # Alto caos
            volatility_class = "EXTREME"
        else:
            volatility_class = "HIGH"  # Alta ma direzionale
    
    # Classify directionality and implications
    is_strongly_directional = dir_strength > 0.7 and chaos_ratio < 0.3
    is_moderately_directional = dir_strength > 0.5 or chaos_ratio < 0.4
    
    if is_strongly_directional:
        directional_class = "STRONGLY_DIRECTIONAL"
        trading_implication = "STRONG_OPPORTUNITY"
    elif is_moderately_directional:
        directional_class = "MODERATELY_DIRECTIONAL"
        trading_implication = "OPPORTUNITY"
    elif dir_strength > 0.3:
        directional_class = "WEAKLY_DIRECTIONAL"
        trading_implication = "NEUTRAL"
    else:
        directional_class = "CHAOTIC"
        trading_implication = "RISK"
    
    # Override trading implication for high volatility cases
    if volatility_class == "EXTREME" and not is_strongly_directional:
        trading_implication = "RISK"
    
    # Calculate risk adjustment considering both volatility and directionality
    risk_adj = calculate_risk_adjustment(metrics)
    
    result = {
        'volatility_class': volatility_class,
        'directional_class': directional_class,
        'trading_implication': trading_implication,
        'risk_adjustment': risk_adj,
        'is_strongly_directional': is_strongly_directional,
        'is_moderately_directional': is_moderately_directional
    }
    
    logfire.info(
        "Volatility interpretation",
        metrics_summary={
            "vol_score": f"{vol_score:.3f}",
            "dir_strength": f"{dir_strength:.3f}",
            "chaos_ratio": f"{chaos_ratio:.3f}"
        },
        interpretation=result
    )
    
    return result


def calculate_risk_adjustment(metrics: Dict[str, float]) -> float:
    """
    Calculate risk adjustment based on volatility nature.
    
    Updated formula that:
    1. Rewards strong directional movement
    2. Penalizes chaos more than volatility
    3. Allows larger positions in directional volatility
    
    Returns:
        float: Position size multiplier (0.2-1.0)
    """
    base_multiplier = 1.0
    dir_strength = metrics['directional_strength']
    chaos_ratio = metrics['chaos_ratio']
    vol_score = metrics['volatility_score']
    
    # Reward for strong directional movement
    directional_bonus = dir_strength * 0.6
    
    # Heavy penalty for chaos
    chaos_penalty = chaos_ratio * 0.6
    
    # Lighter volatility penalty when movement is directional
    vol_penalty = vol_score * 0.3 * (chaos_ratio ** 0.5)  # Reduced impact when directional
    
    # Boosted multiplier for very directional moves
    if dir_strength > 0.7 and chaos_ratio < 0.3:
        base_multiplier = 1.2  # Allow slightly larger sizing for strong trends
    
    final_multiplier = (
        base_multiplier * 
        (1 + directional_bonus) * 
        (1 - chaos_penalty) * 
        (1 - vol_penalty)
    )
    
    # Ensure multiplier stays within bounds
    final_multiplier = max(0.2, min(1.0, final_multiplier))
    
    logfire.debug(
        "Risk adjustment calculation",
        components={
            "directional_bonus": directional_bonus,
            "chaos_penalty": chaos_penalty,
            "vol_penalty": vol_penalty,
            "base_multiplier": base_multiplier
        },
        final_multiplier=final_multiplier
    )
    
    return final_multiplier