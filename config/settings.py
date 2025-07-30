"""
Configuration settings for Forex Trading Bot
"""

import os
from typing import Dict, List

# API Configuration
API_TIMEOUT = 10
MAX_RETRY_ATTEMPTS = 3
RATE_LIMIT_BUFFER = 1  # seconds

# Supported Forex Pairs
MAJOR_PAIRS = [
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF',
    'AUD/USD', 'USD/CAD', 'NZD/USD'
]

CROSS_PAIRS = [
    'EUR/GBP', 'EUR/JPY', 'EUR/CHF', 'EUR/AUD',
    'GBP/JPY', 'GBP/CHF', 'AUD/JPY', 'CAD/JPY'
]

COMMODITY_PAIRS = [
    'XAU/USD',  # Gold
    'XAG/USD',  # Silver
    'XPD/USD',  # Palladium
    'XPT/USD'   # Platinum
]

ALL_PAIRS = MAJOR_PAIRS + CROSS_PAIRS + COMMODITY_PAIRS

# Technical Analysis Settings
TECHNICAL_SETTINGS = {
    'ema_fast': 12,
    'ema_slow': 26,
    'rsi_period': 14,
    'rsi_overbought': 70,
    'rsi_oversold': 30,
    'bb_period': 20,
    'bb_std_dev': 2,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'adx_period': 14
}

# Data Fetching Settings
DATA_SETTINGS = {
    'default_interval': '1min',
    'max_historical_points': 100,
    'cache_duration': 60,  # seconds
    'fallback_delay': 2    # seconds between API attempts
}

# Logging Configuration
LOG_SETTINGS = {
    'log_level': 'INFO',
    'max_log_size_mb': 10,
    'backup_count': 5,
    'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

# Telegram Bot Settings
TELEGRAM_SETTINGS = {
    'max_message_length': 4000,
    'button_timeout': 300,  # 5 minutes
    'analysis_timeout': 30  # seconds
}

def get_env_var(key: str, default: str = None) -> str:
    """Get environment variable with default fallback"""
    return os.getenv(key, default)

def validate_environment() -> Dict[str, bool]:
    """Validate all required environment variables"""
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'TWELVE_DATA_API_KEY',
        'ALPHA_VANTAGE_API_KEY'
    ]
    return {var: bool(os.getenv(var)) for var in required_vars}
