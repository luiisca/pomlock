def plural(str: str, n: int) -> str:
    return f"{str}{"" if n == 1 else 's'}"
