# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterable
from dataclasses import dataclass, field
from xml.sax import parse as sax_parse
from xml.sax.handler import ContentHandler as SAXContentHandler
from xml.sax.xmlreader import AttributesImpl as SAXAttributes

from impuls import Task, TaskRuntime
from impuls.model import Stop, Translation
from impuls.tools.types import StrPath


@dataclass
class Station:
    id: str
    name: str
    lat: float
    lon: float
    translations: dict[str, str] = field(default_factory=dict[str, str], repr=False)

    def as_stop(self) -> Stop:
        return Stop(self.id, self.name, self.lat, self.lon)

    def as_translations(self) -> Iterable[Translation]:
        for lang, translation in self.translations.items():
            yield Translation(
                table_name="stops",
                record_id=self.id,
                field_name="stop_name",
                language=lang,
                translation=translation,
            )


class OSMStopLoader(SAXContentHandler):
    stations: dict[str, Station]

    _in_node: bool
    _node_position: tuple[float, float]
    _tags: dict[str, str]

    def __init__(self) -> None:
        super().__init__()
        self.stations = {}
        self._in_node = False
        self._node_position = 0.0, 0.0
        self._tags = {}

    def startElement(self, name: str, attrs: SAXAttributes) -> None:
        if name == "node":
            self._in_node = True
            self._node_position = float(attrs["lat"]), float(attrs["lon"])
            self._tags.clear()

        elif name == "tag" and self._in_node:
            self._tags[attrs["k"]] = attrs["v"]

    def endElement(self, name: str) -> None:
        if name == "node":
            if self._tags.get("railway") == "station":
                id = self._tags["ref"]
                name_ko = self._tags["name"]
                name_en = self._tags["name:en"]
                self.stations[id] = Station(id, name_ko, *self._node_position, {"en": name_en})

            self._in_node = False

    @classmethod
    def load_all(cls, path: StrPath) -> dict[str, Station]:
        self = cls()
        sax_parse(path, self)
        return self.stations


class LoadStops(Task):
    def __init__(self, resource: str = "geo.osm") -> None:
        super().__init__()
        self.resource = resource

    def execute(self, r: TaskRuntime) -> None:
        osm_path = r.resources[self.resource].stored_at
        stations = OSMStopLoader.load_all(osm_path)

        with r.db.transaction():
            r.db.create_many(
                Stop,
                (i.as_stop() for i in stations.values()),
            )
            r.db.create_many(
                Translation,
                (t for s in stations.values() for t in s.as_translations()),
            )
