# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import cast

from impuls import DBConnection, Task, TaskRuntime
from impuls.model import Translation


@dataclass
class StopName:
    default: str
    translations: dict[str, str] = field(default_factory=dict[str, str])


class GenerateHeadsigns(Task):
    def execute(self, r: TaskRuntime) -> None:
        stop_names = self.get_stop_names(r.db)
        trip_last_stops = self.get_trip_last_stops(r.db)
        trip_headsigns = {
            trip_id: headsign
            for trip_id, last_stop in trip_last_stops.items()
            if (headsign := stop_names.get(last_stop))
        }
        self.set_headsigns(r.db, trip_headsigns)

    def get_stop_names(self, db: DBConnection) -> dict[str, StopName]:
        # Get default stop names
        with db.raw_execute("SELECT stop_id, name FROM stops") as q:
            names = {i[0]: StopName(i[1]) for i in cast(Iterable[tuple[str, str]], q)}

        # Get translated stop names
        with db.raw_execute(
            "SELECT record_id, language, translation "
            "FROM translations "
            "WHERE table_name = 'stops' AND field_name = 'stop_name'"
        ) as q:
            for stop_id, language, translation in cast(Iterable[tuple[str, str, str]], q):
                if name := names.get(stop_id):
                    name.translations[language] = translation

        return names

    def get_trip_last_stops(self, db: DBConnection) -> dict[str, str]:
        with db.raw_execute(
            "SELECT trip_id, stop_id FROM stop_times "
            "GROUP BY trip_id HAVING stop_sequence = MAX(stop_sequence)"
        ) as q:
            return {i[0]: i[1] for i in cast(Iterable[tuple[str, str]], q)}

    def set_headsigns(self, db: DBConnection, headsigns: Mapping[str, StopName]) -> None:
        with db.transaction():
            db.raw_execute_many(
                "UPDATE trips SET headsign = ? WHERE trip_id = ?",
                ((name.default, trip_id) for trip_id, name in headsigns.items()),
            )
            db.create_many(
                Translation,
                (
                    Translation(
                        table_name="trips",
                        record_id=trip_id,
                        field_name="trip_headsign",
                        language=lang,
                        translation=translation,
                    )
                    for trip_id, name in headsigns.items()
                    for lang, translation in name.translations.items()
                ),
            )
