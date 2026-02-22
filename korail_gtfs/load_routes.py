# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import json

from impuls import Task, TaskRuntime
from impuls.model import Route, Translation
from impuls.tools.color import text_color_for


class LoadRoutes(Task):
    def __init__(self, resource: str = "routes.csv") -> None:
        super().__init__()
        self.resource = resource

    def execute(self, r: TaskRuntime) -> None:
        with r.db.transaction():
            rows = list(r.resources[self.resource].csv())
            r.db.create_many(
                Route,
                (
                    Route(
                        id=row["id"],
                        agency_id="korail",
                        short_name=row["name_ko"],
                        long_name="",
                        type=Route.Type.RAIL,
                        color=row["color"],
                        text_color=text_color_for(row["color"]),
                        extra_fields_json=json.dumps(
                            {
                                "route_type_extended": row["extended_type"],
                            }
                        ),
                    )
                    for row in rows
                ),
            )
            r.db.create_many(
                Translation,
                (
                    Translation(
                        table_name="routes",
                        record_id=row["id"],
                        field_name="route_short_name",
                        language="en",
                        translation=row["name_en"],
                    )
                    for row in rows
                ),
            )
