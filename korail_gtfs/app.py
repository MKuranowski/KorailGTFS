# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from argparse import ArgumentParser, Namespace

from impuls import App, LocalResource, Pipeline, PipelineOptions
from impuls.tasks import ExecuteSQL, RemoveUnusedEntities, SaveGTFS

from .gtfs import GTFS_HEADERS
from .load_routes import LoadRoutes
from .load_schedules import LoadSchedules
from .load_static_entities import LoadStaticEntities
from .load_stops import LoadStops


class KorailGTFS(App):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("-o", "--output", default="korail.zip")

    def prepare(self, args: Namespace, options: PipelineOptions) -> Pipeline:
        return Pipeline(
            tasks=[
                LoadStaticEntities(),
                LoadStops(),
                LoadRoutes(),
                LoadSchedules("ktx.xlsx", "standard.xlsx", "itx-cheongchun.xlsx"),
                # TODO: GenerateCalendarExceptions
                RemoveUnusedEntities(),
                ExecuteSQL(
                    task_name="RemoveUnusedStopTranslations",
                    statement=(
                        "DELETE FROM translations "
                        "WHERE table_name = 'stops' "
                        "AND NOT EXISTS (SELECT 1 FROM stops WHERE"
                        " stops.stop_id = translations.record_id)"
                    ),
                ),
                ExecuteSQL(
                    task_name="RemoveUnusedRouteTranslations",
                    statement=(
                        "DELETE FROM translations "
                        "WHERE table_name = 'routes' "
                        "AND NOT EXISTS (SELECT 1 FROM routes WHERE"
                        " routes.route_id = translations.record_id)"
                    ),
                ),
                SaveGTFS(GTFS_HEADERS, args.output, ensure_order=True),
            ],
            resources={
                "itx-cheongchun.xlsx": LocalResource("data/itx-cheongchun.xlsx"),
                "ktx.xlsx": LocalResource("data/ktx.xlsx"),
                "standard.xlsx": LocalResource("data/standard.xlsx"),
                "routes.csv": LocalResource("data/routes.csv"),
                "geo.osm": LocalResource("data/geo.osm"),
            },
            options=options,
        )
