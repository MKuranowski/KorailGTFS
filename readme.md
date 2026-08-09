KorailGTFS
==========

Description
-----------

Generates GTFS Schedule and GTFS Realtime feeds for intercity and regional services of [KORAIL (코레일)](https://www.korail.com/),
South Korea's national rail operator. Data comes from [published Excel schedules](https://www.korail.com/ticket/reserve/train-timeTable),
and a manually curated dataset of stations.

Prebuilt files, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), are available on <https://mkuran.pl/gtfs/>.


Running
-------

KorailGTFS is written in Python with the [Impuls framework](https://github.com/MKuranowski/Impuls).

To set up the project, run:

```terminal
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install -Ur requirements.txt
```

Then, run:

```terminal
$ python -m korail_gtfs
```

The resulting schedules will be put in a file called `korail.zip`.

To create the realtime feed, run:

```terminal
$ python -m korail_gtfs.realtime
```

The resulting realtime feed will be put in a file called `korail.pb`. Automatic updates of that file can be achieved by adding a `--loop` argument.

License
-------

KorailGTFS is distributed under GNU GPL v3 (or any later version).

    © Copyright 2026 Mikołaj Kuranowski

    KorailGTFS is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 3 of the License, or (at your option) any later version.

    KorailGTFS is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along with KorailGTFS. If not, see http://www.gnu.org/licenses/.
