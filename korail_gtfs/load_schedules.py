# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from operator import itemgetter
from typing import Self, cast

from impuls import DBConnection, Task, TaskRuntime
from impuls.errors import DataError, MultipleDataErrors
from impuls.model import Calendar, Date, StopTime, TimePoint, Trip
from impuls.tools.types import StrPath

from .scrape import ScrapedTrip, scrape_from_xlsx

KOREAN_WEEKDAYS_TO_MASK = {c: 1 << i for i, c in enumerate("월화수목금토일")}

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
LAST_NIGHT_CUTOFF = 22 * HOUR
EARLY_MORNING_CUTOFF = 4 * HOUR


@dataclass
class _ConvertedTrips:
    calendars: list[Calendar] = field(default_factory=list[Calendar])
    trips: list[Trip] = field(default_factory=list[Trip])
    stop_times: list[StopTime] = field(default_factory=list[StopTime])

    def apply(self, db: DBConnection) -> None:
        with db.transaction():
            db.create_many(Calendar, self.calendars)
            db.create_many(Trip, self.trips)
            db.create_many(StopTime, self.stop_times)


@dataclass
class _CombinedScrapedTrip:
    # TODO: Don't assume a train stops only once at a specific station.
    #       Some trains on the Seohae line stop twice at Hongseong (like 1241)

    number: str
    kind: str
    note: str
    stops: dict[str, int] = field(default_factory=dict[str, int])

    @classmethod
    def from_scraped_trip(cls, t: ScrapedTrip) -> Self:
        return cls(
            number=t.number,
            kind=t.kind,
            note=t.note,
            stops={_slugify(i.stop): i.time for i in t.stops},
        )

    def merge_with(self, t: ScrapedTrip) -> None:
        assert self.number == t.number
        if self.kind != t.kind:
            raise DataError(f"Trip {self.number} has different kinds: {self.kind} and {t.kind}")
        if self.note != t.note:
            raise DataError(f"Trip {self.number} has different notes: {self.note} and {t.note}")

        for i in t.stops:
            self.stops.setdefault(_slugify(i.stop), i.time)


class LoadSchedules(Task):
    def __init__(self, *resources: str) -> None:
        super().__init__()
        self.resources = resources
        self.start_date = Date.today()
        self.end_date = self.start_date.add_days(365)

        self.stops = dict[str, str]()
        self.routes = dict[str, str]()

        self.unknown_stops = set[str]()
        self.inserted_calendars = set[int]()

    def clear(self) -> None:
        self.stops.clear()
        self.routes.clear()
        self.unknown_stops.clear()
        self.inserted_calendars.clear()

    def execute(self, r: TaskRuntime) -> None:
        self.clear()
        self.stops = _create_stop_lookup(r.db)
        self.routes = _create_route_lookup(r.db)

        for resource in self.resources:
            self.logger.info("Loading schedules from %s", self.resources)
            self.load_schedules_from_xlsx(r.db, r.resources[resource].stored_at)

        self.check_for_unknown_stops()

    def load_schedules_from_xlsx(self, db: DBConnection, path: StrPath) -> None:
        scraped = scrape_from_xlsx(str(path))
        converted = self.convert_scraped_trips(scraped)
        converted.apply(db)

    def convert_scraped_trips(self, scraped: Iterable[ScrapedTrip]) -> _ConvertedTrips:
        converted = _ConvertedTrips()
        for trip in _deduplicate_scraped_trips(scraped).values():
            # Create the calendar
            # TODO: Create more readable calendar_id
            calendar_id = _note_to_calendar_mask(trip.note)
            if calendar_id not in self.inserted_calendars:
                converted.calendars.append(self.create_calendar(calendar_id))

            # Create the trip
            trip_id = trip.number
            converted.trips.append(
                Trip(
                    id=trip_id,
                    route_id=self.match_route(trip.kind),
                    calendar_id=str(calendar_id),
                    short_name=trip.number,
                )
            )

            # Create the stop_times
            converted.stop_times.extend(self.match_stops(trip_id, trip.stops))

        return converted

    def create_calendar(self, mask: int) -> Calendar:
        self.inserted_calendars.add(mask)
        c = Calendar(id=str(mask), start_date=self.start_date, end_date=self.end_date)
        for i in range(7):
            if mask & 1:
                match i:
                    case 0:
                        c.monday = True
                    case 1:
                        c.tuesday = True
                    case 2:
                        c.wednesday = True
                    case 3:
                        c.thursday = True
                    case 4:
                        c.friday = True
                    case 5:
                        c.saturday = True
                    case 6:
                        c.sunday = True
                    case _:
                        raise ValueError(f"invalid weekday: {i}")
            mask >>= 1
        return c

    def match_route(self, kind: str) -> str:
        return self.routes[_slugify(kind)]

    def match_stops(self, trip_id: str, stops: Mapping[str, int]) -> Iterable[StopTime]:
        # Check if trip runs late at night, and if so, shift past-midnight departures
        if any(i >= LAST_NIGHT_CUTOFF for i in stops.values()):
            stops = {
                name: (time + DAY if time < EARLY_MORNING_CUTOFF else time)
                for name, time in stops.items()
            }

        for idx, (name, time) in enumerate(sorted(stops.items(), key=itemgetter(1))):
            if stop_id := self.stops.get(name):
                timepoint = TimePoint(seconds=time)
                yield StopTime(
                    trip_id=trip_id,
                    stop_sequence=idx,
                    stop_id=stop_id,
                    arrival_time=timepoint,
                    departure_time=timepoint,
                )
            else:
                self.unknown_stops.add(name)

    def check_for_unknown_stops(self) -> None:
        if self.unknown_stops:
            raise MultipleDataErrors(
                when="schedule scraping",
                errors=[DataError(f"unknown stop: {name}") for name in sorted(self.unknown_stops)],
            )


def _create_stop_lookup(db: DBConnection) -> dict[str, str]:
    with db.raw_execute("SELECT stop_id, name FROM stops") as query:
        return {_slugify(cast(str, i[1])): cast(str, i[0]) for i in query}


def _create_route_lookup(db: DBConnection) -> dict[str, str]:
    with db.raw_execute("SELECT route_id, long_name FROM routes") as query:
        return {_slugify(cast(str, i[1])): cast(str, i[0]) for i in query}


def _deduplicate_scraped_trips(scraped: Iterable[ScrapedTrip]) -> dict[str, _CombinedScrapedTrip]:
    unique = dict[str, _CombinedScrapedTrip]()
    for t in scraped:
        if existing := unique.get(t.number):
            existing.merge_with(t)
        else:
            unique[t.number] = _CombinedScrapedTrip.from_scraped_trip(t)
    return unique


def _note_to_calendar_mask(note: str) -> int:
    match note:
        case "" | "매일":
            return 0b111_1111
        case "평일":
            return 0b001_1111
        case "휴일":
            return 0b110_0000
        case _:
            mask = 0
            for c in note:
                mask |= KOREAN_WEEKDAYS_TO_MASK[c]
            return mask


def _slugify(x: str) -> str:
    return re.sub(r"[-_ ()]", "", x)
