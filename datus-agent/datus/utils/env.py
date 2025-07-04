import os
from typing import Any, Optional

from dotenv import load_dotenv


# Load environment variables from .env file
def try_load_dotenv():
    try:
        load_dotenv()
    except OSError:
        pass


def get_env(key: str, default: Any = None) -> Optional[str]:
    """
    Get environment variable value

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        Environment variable value or default value
    """
    return os.getenv(key, default)


def get_env_int(key: str, default: int = 0) -> int:
    """
    Get integer value from environment variable

    Args:
        key: Environment variable name
        default: Default integer value if not found or invalid

    Returns:
        Integer value from environment variable or default value
    """
    value = get_env(key)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def get_env_float(key: str, default: float = 0.0) -> float:
    """
    Get float value from environment variable

    Args:
        key: Environment variable name
        default: Default float value if not found or invalid

    Returns:
        Float value from environment variable or default value
    """
    value = get_env(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Get boolean value from environment variable

    Args:
        key: Environment variable name
        default: Default boolean value if not found

    Returns:
        Boolean value from environment variable or default value
    """
    value = get_env(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "y", "on")


def get_env_list(key: str, default: Optional[list] = None, separator: str = ",") -> list:
    """
    Get list value from environment variable

    Args:
        key: Environment variable name
        default: Default list value if not found
        separator: Separator string to split the value

    Returns:
        List value from environment variable or default value
    """
    value = get_env(key)
    if value is None:
        return default if default is not None else []
    return [item.strip() for item in value.split(separator)]
