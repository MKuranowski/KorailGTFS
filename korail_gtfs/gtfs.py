# SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
# SPDX-License-Identifier: GPL-3.0-or-later

GTFS_HEADERS = {
    "agency.txt": [
        "agency_id",
        "agency_name",
        "agency_url",
        "agency_timezone",
        "agency_lang",
    ],
    "stops.txt": [
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
    ],
    "routes.txt": [
        "route_id",
        "agency_id",
        "route_short_name",
        "route_long_name",
        "route_type",
        "route_type_extended",
        "route_color",
        "route_text_color",
    ],
    "trips.txt": [
        "trip_id",
        "route_id",
        "service_id",
        "trip_short_name",
    ],
    "stop_times.txt": [
        "trip_id",
        "stop_sequence",
        "stop_id",
        "arrival_time",
        "departure_time",
    ],
    "calendar.txt": [
        "service_id",
        "start_date",
        "end_date",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ],
    "feed_info.txt": [
        "feed_publisher_name",
        "feed_publisher_url",
        "feed_lang",
    ],
    "translations.txt": [
        "table_name",
        "record_id",
        "field_name",
        "language",
        "translation",
    ],
}
