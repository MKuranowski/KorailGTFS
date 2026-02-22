# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ScrapedStopTime:
    stop: str
    time: int

    def as_json(self) -> dict[str, Any]:
        return {"stop": self.stop, "time": self.time}


@dataclass
class ScrapedTrip:
    number: str
    kind: str
    note: str
    stops: list[ScrapedStopTime]

    def as_json(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "kind": self.kind,
            "note": self.note,
            "stops": [i.as_json() for i in self.stops],
        }


@dataclass
class HeaderIndices:
    number: int
    kind: int | str
    note: int | str


@dataclass
class StationIndex:
    name: str
    index: int
    departure_offset: tuple[int, int] | None = None
    allow_if_departure_only: bool = False


class Order(Protocol):
    def with_(self, __other: int) -> tuple[int, int]: ...


@dataclass
class RowOrder(Order):
    row: int

    def with_(self, col: int) -> tuple[int, int]:
        return (self.row, col)


@dataclass
class ColumnOrder(Order):
    col: int

    def with_(self, row: int) -> tuple[int, int]:
        return (row, self.col)
