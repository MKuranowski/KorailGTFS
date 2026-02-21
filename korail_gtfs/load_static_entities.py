# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from impuls import Task, TaskRuntime
from impuls.model import Agency, Entity, FeedInfo, Translation

ENTITIES: list[Entity] = [
    Agency(
        id="korail",
        name="코레일",
        url="https://www.korail.com/",
        timezone="Asia/Seoul",
        lang="ko",
    ),
    Translation(
        table_name="agency",
        record_id="korail",
        field_name="agency_name",
        language="en",
        translation="Korail",
    ),
    Translation(
        table_name="agency",
        record_id="korail",
        field_name="agency_url",
        language="en",
        translation="https://www.korail.com/global/eng/intro",
    ),
    FeedInfo(
        publisher_name="Mikołaj Kuranowski",
        publisher_url="https://mkuran.pl/gtfs/",
        lang="ko",
    ),
]


class LoadStaticEntities(Task):
    def execute(self, r: TaskRuntime) -> None:
        with r.db.transaction():
            for entity in ENTITIES:
                r.db.create(entity)
