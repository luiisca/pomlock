def plural(str: str, n: int) -> str:
    return f"{str}{"" if n == 1 else 's'}"


def deep_merge(dest, src):
    dest_copy = dest.copy()
    for k, v in src.items():
        if (
            k in dest_copy
            and isinstance(dest_copy[k], dict)
            and isinstance(v, dict)
        ):
            dest_copy[k] = deep_merge(dest_copy[k], v)
        else:
            dest_copy[k] = v
    return dest_copy
