# <img src="mbtiles_batch_exporter/icon.svg" width="40" height="40" alt=""> qgis-project-snapshot

[Polski](README.md) · English

A QGIS plugin for preserving project data and appearance for later offline use.
It helps document the maps and data behind an analysis, feasibility study or
infrastructure project before the original services and databases change.

Creates a separate project copy with layer groups, order, visibility and styles.
Stores vector features with attributes and map images in GeoPackage, and copies
source rasters and available project resources to local files. PNG preserves
transparency with strong lossless compression. Maps can retain the project CRS,
including EPSG:2180.

The plugin is free and open source (GNU GPL v2). You can inspect, modify and
share the code under the [licence](LICENSE).

## How to use

Requires QGIS 3.40 with PyQt5 and GDAL 3.7 or newer. The interface selects Polish
or English based on the QGIS language. Current version for testing: **0.9.3**.

1. Install the package using **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Open your project and choose **Plugins → qgis-project-snapshot → Archive project…**
   or the map-in-an-archive-box toolbar icon.
3. Choose a folder, area (map view or polygons), layers and map detail.
   Select **Create archive**. Hover over controls for explanations.
4. Read the report, then open the project copy without internet or the company network.
   Keep the **entire archive folder**, not just the `.qgz` file.

Downloads use the active QGIS proxy configuration, exclusions and available
saved credentials. No separate proxy setup is needed in the plugin.
Concurrency is adjusted using CPU, RAM and each server's responses. The window shows active tasks, limits, queues, pauses and a log.
During export, only missing tiles are repaired in the same archive. The manual
retry on the result screen creates a new archive of the selected layers.

The [team guide](docs/team-guide.md), also included in the ZIP, provides detailed
Polish instructions and an English quick start.

## Data and limitations

The plugin connects to the databases and services referenced by your project
to retrieve data. It does not replace the source project. It uses QGIS libraries
and standard Python without extra installations. Archives and reports may contain
company data and layer names.

Archive dates describe acquisition times, not a simultaneous snapshot of all
sources. Map images preserve the chosen area and detail levels. The report
identifies missing layers, empty images and dependencies requiring inspection.
Fonts, form code and all expression dependencies are not automatically bundled.
There is no resume after closing QGIS. Source providers' terms still apply,
including restrictions on bulk downloads of standard OSM tiles.

Developed through vibe coding with AI assistance. Check completeness, appearance
and offline access before relying on an archive. Distribution terms and the
absence of warranty are described in the [licence](LICENSE).

## Checks performed

- 70 QGIS tests covering data storage and reading, maps, reporting, Polish/English,
  cancellation, server limits and missing-tile repair.
- Installation ZIP checks: native QGIS discovery and loading, the archive dialog,
  unloading and tests running against the packaged code.
- Ruff: PEP 8/pycodestyle rules (E/W), Pyflakes (F), imports (I) and formatting
  using the project configuration (88 characters).
- Python syntax, ZIP integrity and package/source consistency checks.
- A controlled fixed/adaptive concurrency benchmark with identical output tiles.

Test environment: Ubuntu, QGIS 3.40.15. Windows, MSSQL and complete company
projects still need acceptance on the user's workstation. These are local checks,
not QGIS certification or a guarantee for every project.
[Reports and documentation](docs/README.md).

## Package and development

The repository contains source code. To build the **0.9.3** ZIP, run:

```bash
python3 scripts/build_plugin.py
```

This creates `qgis-project-snapshot-0.9.3.zip` and its SHA-256 checksum in `dist/`,
which is not tracked in Git. Building a ZIP does not publish it in the QGIS plugin catalogue.

[Build and tests](docs/development.md) · [Architecture](docs/architecture.md) ·
[Session handover](docs/PROJECT_STATE.md) · [Agent instructions](AGENTS.md)

Author: Jarosław Sadowski · Licence: GNU GPL v2 ·
[Issues](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues)
