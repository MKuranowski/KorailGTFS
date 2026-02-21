# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from argparse import ArgumentParser, Namespace

from impuls import App, LocalResource, Pipeline, PipelineOptions
from impuls.tasks import SaveGTFS

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
                LoadSchedules("ktx.xlsx", "standard.xlsx"),
                # TODO: GenerateCalendarExceptions
                # TODO: RemoveUnusedEntities
                # TODO: RemoveUnusedTranslations
                SaveGTFS(GTFS_HEADERS, args.output, ensure_order=True),
            ],
            resources={
                "ktx.xlsx": LocalResource("data/ktx.xlsx"),
                "standard.xlsx": LocalResource("data/standard.xlsx"),
                "routes.csv": LocalResource("data/routes.csv"),
                "stops.csv": LocalResource("data/stops.csv"),
            },
            options=options,
        )
