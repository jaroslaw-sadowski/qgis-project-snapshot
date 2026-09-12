# SPDX-License-Identifier: GPL-2.0-only

"""Controlled fixed/adaptive comparison, using real QGIS and loopback WMS only."""

import argparse
import json
import sqlite3
import time
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from qgis.core import QgsGeometry, QgsRectangle
from test_adaptive import AdaptiveWmsTests

from mbtiles_batch_exporter.archive import create_archive


def benchmark(output):
    case = AdaptiveWmsTests()
    case.setUp()
    case.server.delay = 0.12
    case.area = QgsGeometry.fromRect(QgsRectangle(500000, 500000, 501200, 501200))
    rows = []
    try:
        maps = [
            case.add_map("127.0.0.1" if i % 2 == 0 else "localhost", f"Map {i}")
            for i in range(6)
        ]
        for adaptive in (False, True):
            started = time.monotonic()
            before = len(case.server.requests)
            activity = []
            with patch(
                "mbtiles_batch_exporter.archive.detect_resources",
                return_value={"cpu": 2, "memory": 8 * 1024**3, "online": True},
            ):
                result = create_archive(
                    case.project,
                    [m.id() for m in maps],
                    case.area,
                    case.crs,
                    case.folder,
                    zoom_min=18,
                    zoom_max=18,
                    workers=4,
                    per_server_limit=2,
                    adaptive=adaptive,
                    server_activity=lambda values: activity.extend(values),
                )
            manifest = json.loads(
                (result / "diagnostyka" / "manifest.json").read_text()
            )
            images = {}
            with closing(sqlite3.connect(result / "dane" / "dane.gpkg")) as db:
                for record in manifest["layers"]:
                    if record["status"] == "excluded":
                        continue
                    assert record["status"] == "saved", record
                    tiles = db.execute(
                        "SELECT zoom_level,tile_column,tile_row,tile_data "
                        f'FROM "{record["table"]}" '
                        "ORDER BY zoom_level,tile_column,tile_row"
                    ).fetchall()
                    images[record["id"]] = sha256(
                        b"".join(t[3] for t in tiles)
                    ).hexdigest()
            rows.append(
                {
                    "mode": "adaptive" if adaptive else "fixed",
                    "seconds": round(time.monotonic() - started, 3),
                    "getmap_requests": len(case.server.requests) - before,
                    "png_sha256": images,
                    "offline_audit": manifest["local_layer_audit"]["passed"],
                    "peak_processes": max(
                        (
                            sum(r["processes"] for r in activity[i : i + 2])
                            for i in range(0, len(activity), 2)
                        ),
                        default=4,
                    ),
                    "adaptive": manifest["adaptive"],
                }
            )
            print(rows[-1]["mode"], rows[-1]["seconds"], flush=True)
        assert rows[0]["png_sha256"] == rows[1]["png_sha256"]
        output.write_text(
            json.dumps(
                {
                    "scenario": (
                        "6 maps, 2 host aliases, 1.2 km square, zoom 18; 120 ms "
                        "server delay"
                    ),
                    "resource_budget": (
                        "2 CPU / 8 GiB injected for repeatable initial cap; live "
                        "RAM check enabled"
                    ),
                    "results": rows,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        case.tearDown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    benchmark(parser.parse_args().output)
