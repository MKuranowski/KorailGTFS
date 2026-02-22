# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import re
from collections.abc import Callable, Iterable
from typing import Any

from openpyxl.worksheet.worksheet import Worksheet as ExcelWorksheet

from .model import HeaderIndices, Order, ScrapedStopTime, ScrapedTrip, StationIndex


def trip(
    ws: ExcelWorksheet,
    header: HeaderIndices,
    stations: Iterable[StationIndex],
    index: Order,
) -> ScrapedTrip:
    """Extracts an entire scraped trip from a worksheet, using the provided indices."""
    t = ScrapedTrip(
        number=cell(ws, index.with_(header.number)),
        kind=(cell(ws, index.with_(header.kind)) if isinstance(header.kind, int) else header.kind),
        note=(
            cell(ws, index.with_(header.note), note)
            if isinstance(header.note, int)
            else header.note
        ),
        stops=[],
    )

    for station in stations:
        arr_coords = index.with_(station.index)
        arr = cell(ws, arr_coords, time)

        # NOTE: We deliberately also ignore `arr == 0`, most excel files use time "0:00:00"
        #       to mark does-not-stop.

        if station.departure_offset:
            dep_coords = (
                arr_coords[0] + station.departure_offset[0],
                arr_coords[1] + station.departure_offset[1],
            )
            dep = cell(ws, dep_coords, time)

            if dep and (arr or station.allow_if_departure_only):
                t.stops.append(ScrapedStopTime(station.name, dep))
            elif arr:
                t.stops.append(ScrapedStopTime(station.name, arr))

        elif arr:
            t.stops.append(ScrapedStopTime(station.name, arr))

    return t


def string(cell_value: Any) -> str:
    """Converts a cell value into a string. This is almost equivalent to `str(cell_value)`,
    with the notable exception that `str(None)` gives an empty string.

    >>> string(42)
    '42'
    >>> string("  foo  ")
    'foo'
    >>> string(None)
    ''
    >>> string(datetime(2025, 12, 25, 14, 8))
    '2025-12-25 14:08:00'
    """

    match cell_value:
        case None:
            return ""
        case _:
            return str(cell_value).strip()


def time(cell_value: Any) -> int | None:
    """Converts a cell value into a clockface time, as seconds-since-midnight.

    >>> time(datetime.time(8, 15, 30))
    29730
    >>> time(datetime.datetime(2020, 5, 1, 8, 15, 30))
    29730
    >>> time(datetime.timedelta(hours=8, minutes=15, seconds=30))
    29730
    >>> time("2020-05-01T08:15:30")
    29730
    >>> time("8:15")
    29700
    >>> time("foo")
    None
    >>> time(None)
    None
    """
    match cell_value:
        case datetime.time() | datetime.datetime():
            return cell_value.hour * 3600 + cell_value.minute * 60 + cell_value.second
        case datetime.timedelta():
            return round(cell_value.total_seconds())
        case str():
            if m := re.search(r"([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?", cell_value):
                hour = int(m[1])
                minute = int(m[2])
                second = int(m[3]) if m[3] else 0
                return hour * 3600 + minute * 60 + second
            return None
        case None:
            return None
        case _:
            raise _type_error("time", cell_value)


def note(cell_value: Any) -> str:
    """Extracts a train note from a cell value.

    This is almost equivalent to `string(cell_value)`, except that values of temporal types
    cause the empty string to be returned, and "through service" sub-strings are stripped.

    >>> note("매일")
    '매일'
    >>> note("휴일 경부선경유")
    '휴일'
    >>> note(datetime.time(0, 0, 0))
    ''
    """
    match cell_value:
        case datetime.time() | datetime.datetime() | datetime.timedelta():
            return ""
        case str():
            return re.sub(r"\w{1,3}선\s*경유", "", cell_value.strip()).strip()
        case _:
            return string(cell_value)


def station_name(cell_value: Any) -> str:
    """Extracts a station name from a cell value.

    If the value is not None and not a string, a TypeError is raised.

    Enclosing parentheses are removed, and any trailing "도착" (arrival) or "출발" (departure) words
    are stripped.

    >>> station_name("서울")
    '서울'
    >>> station_name("(부산)")
    '부산'
    >>> station_name("팡교(경기)")
    '팡교(경기)'
    >>> station_name("동대구(도착)")
    '동대구'
    """

    match cell_value:
        case None:
            return ""
        case str():
            name = cell_value.strip()
        case _:
            raise _type_error("station name", cell_value)

    # Remove enclosing parenthesis
    if name and name[0] == "(" and name[-1] == ")":
        name = name[1:-1]

    # Remove "arrival" or "departure" suffix
    name = re.sub(r"\s*(도착|출발)$", "", name)
    name = re.sub(r"\s*\((도착|출발)\)$", "", name)

    return name


def _type_error(what: str, value: Any) -> TypeError:
    return TypeError(
        f"don't know how to extract {what} name from {value!r} "
        f"(of type {value.__class__.__qualname__})"
    )


def cell[T](ws: ExcelWorksheet, coords: tuple[int, int], extract: Callable[[Any], T] = string) -> T:
    """Extracts a value from a specific cell, using the provided value converter-and-validator,
    which defaults to `extract.string`.
    """
    return extract(ws.cell(*coords).value)
