def egp(value: float) -> str:
    if value is None:
        return "—"
    return f"EGP {value:,.0f}"


def pct(value: float, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}%"


def num(value: float) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:,.0f}"


def delta_pct(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return (after - before) / before * 100


def delta_str(before: float, after: float, format_fn=num) -> str:
    d = delta_pct(before, after)
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:.1f}% (Before: {format_fn(before)})"
