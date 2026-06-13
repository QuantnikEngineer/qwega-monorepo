"""
Confidence Scoring Algorithm - PROTECTED IP

Proprietary algorithm for calculating final confidence scores
based on multiple factors.
"""

from typing import Optional


def calculate_confidence(
    ai_score: int,
    current_cpu: float,
    historical_avg: float,
    alert_frequency: int,
    memory_pressure: Optional[float] = None,
    deployment_age_days: Optional[int] = None
) -> int:
    """
    Calculate final confidence score using proprietary algorithm.
    
    This combines:
    - AI model's confidence
    - Deviation from historical baseline
    - Alert frequency (recurring issues)
    - Additional signals (memory, deployment age)
    
    Returns: Confidence score 0-100
    """
    
    # Start with AI score as base
    confidence = float(ai_score)
    
    # Factor 1: Deviation from baseline
    # Higher deviation = higher confidence that it's a real issue
    if historical_avg > 0:
        deviation_ratio = current_cpu / historical_avg
        if deviation_ratio > 2.0:  # More than 2x baseline
            confidence += 10
        elif deviation_ratio > 1.5:  # 1.5-2x baseline
            confidence += 5
        elif deviation_ratio < 0.8:  # Below baseline (recovering)
            confidence -= 10
    
    # Factor 2: Alert frequency
    # Recurring alerts indicate persistent issue
    if alert_frequency >= 5:
        confidence += 10
    elif alert_frequency >= 3:
        confidence += 5
    elif alert_frequency == 0:
        confidence -= 5  # First time, might be noise
    
    # Factor 3: Absolute CPU level
    # Very high CPU has higher certainty
    if current_cpu >= 95:
        confidence += 10
    elif current_cpu >= 85:
        confidence += 5
    elif current_cpu < 60:
        confidence -= 10  # Moderate load, less certain
    
    # Factor 4: Memory pressure correlation (if available)
    if memory_pressure is not None:
        if memory_pressure > 85 and current_cpu > 85:
            confidence += 5  # Both high = resource exhaustion
    
    # Factor 5: Deployment age (if available)
    if deployment_age_days is not None:
        if deployment_age_days < 7:
            confidence -= 5  # New deployment, behavior not established
    
    # Clamp to valid range
    confidence = max(0, min(100, int(confidence)))
    
    return confidence


def should_auto_remediate(
    confidence: int,
    auto_threshold: int,
    require_human_approval: bool,
    is_production: bool = False
) -> bool:
    """
    Determine if auto-remediation should proceed.
    
    Additional safety checks beyond simple threshold comparison.
    """
    
    if require_human_approval:
        return False
    
    if confidence < auto_threshold:
        return False
    
    # Production environments have stricter requirements
    if is_production and confidence < 90:
        return False
    
    return True


def calculate_replica_recommendation(
    current_cpu: float,
    current_replicas: int,
    min_replicas: int,
    max_replicas: int,
    target_cpu_utilization: float = 70.0
) -> int:
    """
    Calculate recommended replica count based on CPU utilization.
    
    Uses a simple linear scaling model targeting specified CPU utilization.
    """
    
    if current_cpu <= 0 or current_replicas <= 0:
        return current_replicas
    
    # Calculate replicas needed to achieve target utilization
    # Formula: new_replicas = current_replicas * (current_cpu / target_cpu)
    desired_replicas = int(current_replicas * (current_cpu / target_cpu_utilization))
    
    # Round up to ensure we don't under-provision
    if desired_replicas > current_replicas:
        desired_replicas = min(desired_replicas + 1, max_replicas)
    
    # Apply limits
    recommended = max(min_replicas, min(max_replicas, desired_replicas))
    
    return recommended
