# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from impuls import Task, TaskRuntime
from impuls.model import Stop, Translation


class LoadStops(Task):
    def __init__(self, resource: str = "stops.csv") -> None:
        super().__init__()
        self.resource = resource

    def execute(self, r: TaskRuntime) -> None:
        with r.db.transaction():
            rows = list(r.resources[self.resource].csv())
            r.db.create_many(
                Stop,
                (
                    Stop(
                        id=row["id"],
                        name=row["name_ko"],
                        lat=float(row["lat"]),
                        lon=float(row["lon"]),
                    )
                    for row in rows
                ),
            )
            r.db.create_many(
                Translation,
                (
                    Translation(
                        table_name="stops",
                        record_id=row["id"],
                        field_name="stop_name",
                        language="en",
                        translation=row["name_en"],
                    )
                    for row in rows
                ),
            )
