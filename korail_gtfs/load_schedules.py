# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from operator import attrgetter
from typing import cast

from impuls import DBConnection, Task, TaskRuntime
from impuls.errors import DataError, MultipleDataErrors
from impuls.model import Calendar, Date, StopTime, TimePoint, Trip
from impuls.tools.types import StrPath

from .scrape import ScrapedStopTime, ScrapedTrip, scrape_from_xlsx

STOP_ALIASES = {"평내호평": ["평내호"]}

KOREAN_WEEKDAYS_TO_MASK = {c: 1 << i for i, c in enumerate("월화수목금토일")}

SECOND = 1
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE
DAY = 24 * HOUR
LATE_NIGHT_CUTOFF = 22 * HOUR
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
            self.logger.info("Loading schedules from %s", resource)
            self.load_schedules_from_xlsx(r.db, r.resources[resource].stored_at)

        self.check_for_unknown_stops()

    def load_schedules_from_xlsx(self, db: DBConnection, path: StrPath) -> None:
        scraped = scrape_from_xlsx(str(path))
        converted = self.convert_scraped_trips(scraped)
        converted.apply(db)

    def convert_scraped_trips(self, scraped: Iterable[ScrapedTrip]) -> _ConvertedTrips:
        converted = _ConvertedTrips()
        for trip in _deduplicate_scraped_trips(scraped):
            # Create the calendar
            # TODO: Create more readable calendar_id
            calendar_id = _note_to_calendar_mask(trip.note)
            if calendar_id not in self.inserted_calendars:
                converted.calendars.append(self.create_calendar(calendar_id))

            # Create the trip
            trip_id = re.sub(r"^[A-Z]", "", trip.number)
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

    def match_stops(self, trip_id: str, scraped: list[ScrapedStopTime]) -> Iterable[StopTime]:
        # Check if trip runs late at night, and if so, shift past-midnight departures
        if any(i.time >= LATE_NIGHT_CUTOFF for i in scraped):
            for st in scraped:
                if st.time < EARLY_MORNING_CUTOFF:
                    st.time += DAY

        # Ensure stop-times are sorted on time
        scraped.sort(key=attrgetter("time"))

        # Generate impuls StopTime objects
        for i, st in enumerate(scraped):
            stop_slug = _slugify(st.stop)
            if stop_id := self.stops.get(stop_slug):
                timepoint = TimePoint(seconds=st.time)
                yield StopTime(
                    trip_id=trip_id,
                    stop_sequence=i,
                    stop_id=stop_id,
                    arrival_time=timepoint,
                    departure_time=timepoint,
                )
            else:
                self.unknown_stops.add(stop_slug)

    def check_for_unknown_stops(self) -> None:
        if self.unknown_stops:
            raise MultipleDataErrors(
                when="schedule scraping",
                errors=[DataError(f"unknown stop: {name}") for name in sorted(self.unknown_stops)],
            )


def _create_stop_lookup(db: DBConnection) -> dict[str, str]:
    with db.raw_execute("SELECT stop_id, name FROM stops") as query:
        lookup = {_slugify(cast(str, i[1])): cast(str, i[0]) for i in query}

    for name, aliases in STOP_ALIASES.items():
        if id := lookup[name]:
            for alias in aliases:
                lookup[alias] = id

    return lookup


def _create_route_lookup(db: DBConnection) -> dict[str, str]:
    with db.raw_execute("SELECT route_id, short_name FROM routes") as query:
        return {_slugify(cast(str, i[1])): cast(str, i[0]) for i in query}


def _deduplicate_scraped_trips(scraped: Iterable[ScrapedTrip]) -> Iterable[ScrapedTrip]:
    # Group trips by the number
    by_number = defaultdict[str, list[ScrapedTrip]](list)
    for trip in scraped:
        by_number[trip.number].append(trip)

    # Deduplicate them
    for group in by_number.values():
        yield _merge_scraped_trips(group)


def _merge_scraped_trips(trips: Sequence[ScrapedTrip]) -> ScrapedTrip:
    # Fast path when there's nothing to merge
    if len(trips) == 1:
        return trips[0]

    # Check that all trains have the same details
    numbers = set(i.number for i in trips)
    kinds = set(i.kind for i in trips)
    notes = set(i.note for i in trips)
    if len(numbers) != 1 or len(kinds) != 1 or len(notes) != 1:
        raise ValueError(f"can't merge trains with different details: {numbers=} {kinds=} {notes=}")

    # Merge all stop-times together
    all_stop_times = [j for i in trips for j in i.stops]
    all_stop_times.sort(key=attrgetter("time"))

    # Merge consecutive stop-times at the same stop
    stop_times = list[ScrapedStopTime]()
    for st in all_stop_times:
        if stop_times and stop_times[-1].stop == st.stop:
            stop_times[-1].time = st.time
        else:
            stop_times.append(st)

    return replace(trips[0], stops=stop_times)


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
