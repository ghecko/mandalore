import re
from datetime import datetime
from typing import Tuple, Union


# Generic text generation functions

def boolFormatter(val: bool) -> str:
    """Generic text formatter for bool value"""
    return '[green]On :heavy_check_mark:[/green] ' if val else '[orange3]Off :axe:[/orange3]'


def getColor(val: Union[bool, int, str]) -> Tuple[str, str]:
    """Generic text color getter for bool value"""
    if type(val) is str:
        try:
            val = int(val)
        except ValueError:
            val = False
    return ('[green]', '[/green]') if val else ('[orange3]', '[/orange3]')


def formatSize(size: Union[int, float], precision: int = 1) -> str:
    """Text formatter from a number of bytes to a human-readable size."""
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    suffix_index = 0
    calc = float(size)
    while calc > 1024 and suffix_index < len(suffixes) - 1:
        suffix_index += 1
        calc = calc / 1024
    return "%.*f%s" % (precision, calc, suffixes[suffix_index])


def formatDate(raw_date: str) -> str:
    """Format a date label (ISO 8601 date or datetime) for display. Unknown formats are returned as-is."""
    for date_format, display_format in (("%Y-%m-%dT%H:%M:%SZ", "%d/%m/%Y %H:%M"),
                                        ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"),
                                        ("%Y-%m-%d", "%d/%m/%Y")):
        try:
            return datetime.strptime(raw_date.strip(), date_format).strftime(display_format)
        except ValueError:
            continue
    return raw_date


def richLen(text: str) -> int:
    """Get real length of a text without Rich colors"""
    # remove rich color tags
    color_removed = re.sub(r"\[/?[^]]+]", '', text, flags=re.MULTILINE)
    # replace emoji by two random char (because emoji are wide)
    emoji_removed = re.sub(r":[a-z-_+()\d'’.&]+:", 'XX', color_removed, flags=re.MULTILINE)
    return len(emoji_removed)


def getArchColor(arch: str) -> str:
    if arch.startswith("arm"):
        color = "slate_blue3"
    elif "amd64" == arch:
        color = "medium_orchid3"
    else:
        color = "yellow3"
    return color
