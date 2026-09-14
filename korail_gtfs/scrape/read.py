# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os.path
from collections.abc import Iterable
from contextlib import closing

from impuls.tools.types import StrPath
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook as ExcelWorkbook
from openpyxl.worksheet.worksheet import Worksheet as ExcelWorksheet

from . import detect, extract
from .model import ColumnOrder, RowOrder, ScrapedTrip

logger = logging.getLogger("Scraper")


def xlsx(path: StrPath) -> Iterable[ScrapedTrip]:
    """Scrapes all trips from an .xlsx file stored at the provided path."""

    with closing(load_workbook(path)) as wb:
        yield from workbook(wb, path)


def workbook(wb: ExcelWorkbook, path: StrPath = "") -> Iterable[ScrapedTrip]:
    """Scrapes all trips from the provided excel workbook.
    The path argument is only used for logging.
    """
    filename = os.path.basename(path)
    itx_cheongchun_only = "cheongchun" in filename or "청춘" in filename
    if "monfri" in filename:
        weekday_override = "평일"
    elif "satsun" in filename:
        weekday_override = "휴일"
    else:
        weekday_override = ""

    for ws in wb.worksheets:
        if "보는방법" in ws.title or (itx_cheongchun_only and "ITX청춘" not in ws.title):
            continue
        logger.debug("Parsing %s, worksheet %s", path, ws.title)
        yield from worksheet(ws, weekday_override=weekday_override)


def worksheet(ws: ExcelWorksheet, weekday_override: str = "") -> Iterable[ScrapedTrip]:
    """Scrapes all trips from all tables in the provided excel worksheet."""
    for table in detect.tables(ws, weekday_override):
        for idx in table.trains:
            order = RowOrder(idx) if table.row_order else ColumnOrder(idx)
            yield extract.trip(ws, table.header, table.stations, order)
