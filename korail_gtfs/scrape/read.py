# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
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
    for ws in wb.worksheets:
        if "보는방법" in ws.title:
            continue
        logger.debug("Parsing %s, worksheet %s", path, ws.title)
        yield from worksheet(ws)


def worksheet(ws: ExcelWorksheet) -> Iterable[ScrapedTrip]:
    """Scrapes all trips from all tables in the provided excel worksheet."""
    for table in detect.tables(ws):
        for idx in table.trains:
            order = RowOrder(idx) if table.row_order else ColumnOrder(idx)
            yield extract.trip(ws, table.header, table.stations, order)
