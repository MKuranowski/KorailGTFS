# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypeAlias, get_args

import requests
from google.protobuf import json_format
from impuls.tools.logs import initialize as initialize_logging

from .gtfs_rt import gtfs_realtime_pb2

Format: TypeAlias = Literal["binary", "readable", "json"]

URL = "https://gis.korail.com/api/train?bbox=126.0,34.2,129.6,38.7"
REFERER = "https://gis.korail.com/korailTalk/entrance"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 9; SM-G998B Build/SP1A.210812.016; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/129.0.6668.70 Safari/537.36 korailtalk AppVersion/6.4.1"
)


def fetch_raw_features() -> Any:
    with requests.get(URL, headers={"Referer": REFERER, "User-Agent": USER_AGENT}) as r:
        r.raise_for_status()
        return r.json()


def convert_features_to_feed(f: Any) -> gtfs_realtime_pb2.FeedMessage:
    timestamp = datetime.fromisoformat(f["timeStamp"])
    header = gtfs_realtime_pb2.FeedHeader(
        gtfs_realtime_version="2.0",
        incrementality=gtfs_realtime_pb2.FeedHeader.Incrementality.FULL_DATASET,
        timestamp=round(timestamp.timestamp()),
    )
    entities = [
        entity for feature in f["features"] for entity in convert_feature_to_entities(feature)
    ]
    return gtfs_realtime_pb2.FeedMessage(header=header, entity=entities)


def convert_feature_to_entities(f: Any) -> list[gtfs_realtime_pb2.FeedEntity]:
    if not is_valid_feature(f):
        return []

    trip_id = f["properties"]["trn_no"]
    return [
        gtfs_realtime_pb2.FeedEntity(
            id=f"position_{trip_id}",
            vehicle=convert_feature_to_vehicle_position(f),
        ),
        gtfs_realtime_pb2.FeedEntity(
            id=f"trip_update_{trip_id}",
            trip_update=convert_feature_to_trip_update(f),
        ),
    ]


def is_valid_feature(f: Any) -> bool:
    return f.get("properties", "").get("trn_clsf", "").casefold() != "srt"


def convert_feature_to_trip_update(f: Any) -> gtfs_realtime_pb2.TripUpdate:
    trip_id = f["properties"]["trn_no"]
    delay = (f["properties"]["delay"] or 0) * 60
    return gtfs_realtime_pb2.TripUpdate(
        trip=gtfs_realtime_pb2.TripDescriptor(
            trip_id=trip_id,
            schedule_relationship=gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.SCHEDULED,
        ),
        stop_time_update=[
            gtfs_realtime_pb2.TripUpdate.StopTimeUpdate(
                stop_sequence=0,
                departure=gtfs_realtime_pb2.TripUpdate.StopTimeEvent(delay=delay),
            )
        ],
        delay=delay,
    )


def convert_feature_to_vehicle_position(f: Any) -> gtfs_realtime_pb2.VehiclePosition:
    trip_id = f["properties"]["trn_no"]
    lon, lat = f["geometry"]["coordinates"]
    return gtfs_realtime_pb2.VehiclePosition(
        trip=gtfs_realtime_pb2.TripDescriptor(
            trip_id=trip_id,
            schedule_relationship=gtfs_realtime_pb2.TripDescriptor.ScheduleRelationship.SCHEDULED,
        ),
        position=gtfs_realtime_pb2.Position(latitude=lat, longitude=lon),
    )


def write_file_atomically(path: Path, content: str | bytes) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    if isinstance(content, str):
        tmp_path.write_text(content, encoding="utf-8")
    else:
        tmp_path.write_bytes(content)
    tmp_path.rename(path)


def run(output: Path, format: Format) -> None:
    features = fetch_raw_features()
    feed = convert_features_to_feed(features)

    match format:
        case "binary":
            serialized = feed.SerializeToString()
        case "readable":
            serialized = str(feed)
        case "json":
            serialized = json_format.MessageToJson(feed, indent=2, ensure_ascii=False)
        case _:
            raise ValueError(f"invalid --format {format!r}")

    write_file_atomically(output, serialized)


def loop(period_s: int, output: Path, format: Format) -> None:
    logger = logging.getLogger("KorailGTFSRealtime")
    initialize_logging(verbose=False)

    backoff = 1
    while True:
        last_run = time.monotonic()

        try:
            run(output, format)
            backoff = 1
            logger.info("%s updated successfully", output)
        except Exception:
            backoff += 1
            if backoff > 60:
                raise ValueError("updated failed too many times, aborting")
            logger.exception("update failed")

        next_run = last_run + (period_s * backoff)
        delta = next_run - time.monotonic()
        if delta > 0:
            time.sleep(delta)


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default="korail.pb",
        help="path to output gtfs-rt",
    )
    arg_parser.add_argument(
        "-f",
        "--format",
        choices=get_args(Format),
        default="binary",
        help="feed format",
    )
    arg_parser.add_argument(
        "-l",
        "--loop",
        type=int,
        help="run continuously updating the output file with the given interval (seconds)",
    )
    args = arg_parser.parse_args()

    if args.loop is None:
        run(args.output, args.format)
    elif args.loop <= 0:
        raise ValueError("--loop argument can't be negative")
    else:
        loop(args.loop, args.output, args.format)


if __name__ == "__main__":
    main()
