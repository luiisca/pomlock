def hex_ok(color_value: str) -> bool:
    """True if '#RRGGBB' has valid hex digits after the '#'."""
    try:
        int(color_value[1:], 16)
        return True
    except ValueError:
        return False
