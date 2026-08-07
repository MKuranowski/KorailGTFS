# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from urllib.parse import urljoin

import requests
from impuls import HTTPResource
from impuls.model import Date

BASE_URL = "https://www.korail.com/file/cubedata/COMMON/"
LIST_URL = "https://www.korail.com/com/userBoard.do?schBcid=ticketTable&mode=list"
SCHEDULES_TO_FIND = {
    "ktx.xlsx": "KTX",
    "standard.xlsx": "일반열차",
    "itx-cheongchun.xlsx": "ITX-청춘",
}

logger = logging.getLogger("FindFiles")


@dataclass(frozen=True)
class File:
    name: str
    url: str
    code: str
    upload_date: Date

    @cached_property
    def start_date(self) -> Date:
        m = re.search(
            r"([0-9]{4})[년.-]\s*([0-9]{1,2})[월.-]\s*([0-9]{1,2})[일.]?\s*(?:기준|부터)",
            self.name,
        )
        if not m:
            raise ValueError(f"unable to extract start date from {self.name!r}")
        return Date(int(m[1]), int(m[2]), int(m[3]))


def list_all_files() -> list[File]:
    with requests.get(LIST_URL) as r:
        data = r.json()

    return [
        File(
            name=i["bdTitle"],
            url=urljoin(BASE_URL, i["fileId"][0]),
            code=i["bdCodeName"],
            upload_date=Date.from_ymd_str(i["regdt"]),
        )
        for i in data["boardList"]
    ]


def find_matching_files(all_files: Iterable[File], typ: str) -> list[File]:
    return [i for i in all_files if "시간표" in i.code and typ in i.name]


def find_current_file(files: Iterable[File], today: Date | None = None) -> File:
    today = today or Date.today()
    best: File | None = None

    for candidate in files:
        if best is None:
            # no best candidate - pick the first one
            best = candidate

        elif candidate.start_date > today and best.start_date > today:
            # both candidate and best start in the future - pick whichever starts sooner
            best = candidate if candidate.start_date < best.start_date else best

        elif candidate.start_date > today:
            # candidate starts in the future, best in the past - candidate can't be best
            continue

        elif best.start_date > today:
            # candidate starts in the past, best in the future - candidate must be best
            best = candidate

        else:
            # both candidate and best start in the past - pick whichever starts later
            best = candidate if candidate.start_date > best.start_date else best

    if not best:
        raise KeyError("empty files sequence")
    return best


def find_current_matching_file(files: Iterable[File], typ: str, today: Date | None = None) -> File:
    matching = find_matching_files(files, typ)
    if not matching:
        raise ValueError(f"no files matching {typ!r}")

    return find_current_file(matching, today)


def find_all_schedules_to_scrape(today: Date | None = None) -> dict[str, HTTPResource]:
    logger.info("Listing all files from https://www.korail.com/ticket/reserve/train-timeTable")
    files = list_all_files()

    resources = dict[str, HTTPResource]()
    for filename, typ in SCHEDULES_TO_FIND.items():
        file = find_current_matching_file(files, typ, today)
        logger.info("%s: using %r", filename, file.name)
        resources[filename] = HTTPResource.get(file.url)
    return resources
