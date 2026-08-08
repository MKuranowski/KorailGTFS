# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import date
from typing import Literal, cast

from holidays import country_holidays
from impuls import DBConnection, Task, TaskRuntime
from impuls.model import Date


class GenerateCalendarExceptions(Task):
    def execute(self, r: TaskRuntime) -> None:
        start_date = self.get_calendar_extreme(r.db, "start_date")
        end_date = self.get_calendar_extreme(r.db, "end_date")
        holidays = [
            i.isoformat()
            for i in cast(list[date], country_holidays("KR")[start_date:end_date])  # type: ignore
        ]

        to_deactivate = self.get_active_calendars(r.db, sunday=False)
        to_activate = self.get_active_calendars(r.db, sunday=True)

        with r.db.transaction():
            r.db.raw_execute_many(
                "INSERT INTO calendar_exceptions (date,calendar_id,exception_type) VALUES (?,?,2)",
                ((holiday, calendar) for holiday in holidays for calendar in to_deactivate),
            )
            r.db.raw_execute_many(
                "INSERT INTO calendar_exceptions (date,calendar_id,exception_type) VALUES (?,?,1)",
                ((holiday, calendar) for holiday in holidays for calendar in to_activate),
            )

    def get_calendar_extreme(
        self,
        db: DBConnection,
        col: Literal["start_date", "end_date"],
    ) -> Date:
        with db.raw_execute(f"SELECT DISTINCT {col} FROM calendars") as q:
            rows = [cast(str, i[0]) for i in q]

        if len(rows) == 0:
            raise ValueError("empty calendars")
        elif len(rows) > 1:
            raise ValueError(f"multiple different {col}s: {', '.join(rows)}")

        return Date.from_ymd_str(rows[0])

    def get_active_calendars(self, db: DBConnection, sunday: bool) -> list[str]:
        with db.raw_execute("SELECT calendar_id FROM calendars WHERE sunday = ?", (sunday,)) as q:
            return [cast(str, i[0]) for i in q]
