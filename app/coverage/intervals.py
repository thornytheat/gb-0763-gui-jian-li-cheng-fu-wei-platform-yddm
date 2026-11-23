def union(intervals):
    """Merge half-open intervals; touching intervals collapse, empty ones vanish."""
    merged = []
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def clip(intervals, lo, hi):
    """Intersect intervals with the half-open window [lo, hi)."""
    if hi <= lo:
        return []
    return [(max(lo, a), min(hi, b)) for a, b in intervals if min(hi, b) > max(lo, a)]


def complement(intervals, lo, hi):
    """The parts of [lo, hi) not covered by the already merged intervals."""
    cursor, holes = lo, []
    for a, b in intervals:
        if a > cursor:
            holes.append((cursor, min(a, hi)))
        cursor = max(cursor, b)
        if cursor >= hi:
            break
    if cursor < hi:
        holes.append((cursor, hi))
    return [(a, b) for a, b in holes if b > a]
