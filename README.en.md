# <img src="mbtiles_batch_exporter/icon.svg" width="40" height="40" alt=""> QGIS Project Snapshot

[Polski](README.md) · English · Version **1.0.0**

## What it is and what it does

QGIS Project Snapshot creates a local copy of a QGIS project for later offline
use. It helps preserve project data and map appearance before the original
databases or services change.

It saves a project copy, vector features with attributes, map images, local
rasters and available resources, and a report in a separate folder. It preserves
layer groups, order, visibility and styles. PNG maps retain transparency.
You choose the layers, area and detail levels; the original project stays unchanged.

## Installation requirements

- **QGIS 3.40 or a later 3.x release**, with Qt5/PyQt5 and GDAL 3.7 or newer.
  The plugin uses libraries supplied with QGIS; no separate Python installation
  or additional packages are needed.
- Access to the project's sources during export and enough disk space.
- Permission to download and store the selected data and maps.

The interface uses Polish or English according to the QGIS language.
Tested with QGIS 3.40 on Ubuntu. Other environments, especially company databases
and authentication, need checking on your own workstation.

## How to install

1. Obtain the **`qgis-project-snapshot-1.0.0.zip`** release package.
   Use the plugin's installation ZIP, not a ZIP of the entire repository.
2. In QGIS, choose **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the package and install it. Restart QGIS when upgrading.

Once publication is approved in the [QGIS plugin catalogue](https://plugins.qgis.org/),
you will be able to search for **QGIS Project Snapshot** directly in the plugin
manager. Providing a ZIP does not mean catalogue approval.

## How to use

1. Open a project and choose **Plugins → QGIS Project Snapshot → Archive project…**
   or the map-in-an-archive-box toolbar icon.
2. Choose a folder, area (map view or polygons), layers and map detail.
   Hover over an option for an explanation.
3. Select **Create archive**, then read the report when the export finishes.
4. Open the project copy without access to the original services and databases.
   Check its data and appearance. Keep the **entire archive folder**, not just
   the `.qgz` file.

The report identifies missing data, empty results and dependencies that need
checking. Not all fonts, forms and expressions can be transferred automatically.
The archive date describes acquisition time, not a simultaneous state of all
sources. Archives and reports may contain confidential data; inspect them before sharing.

## Automatic parallel downloads

The plugin downloads maps in separate QGIS processes. It starts with one task
per server and gradually increases concurrency using available RAM, CPU,
download speed and server responses. Errors reduce the load or trigger a pause.
You do not need to set the number of processes manually.

The window shows active tasks and limits. **Queued layers** counts layers waiting
to download from the server in that row. Automatic adjustment helps speed up
exports but does not guarantee maximum throughput. Downloads use the active
QGIS network settings. Exports cannot resume after closing QGIS.

## Data licences and service terms

**Check and respect each layer's licence and its provider's terms before
exporting.** This includes downloading, copying, offline storage, redistribution,
required attribution and service limits. Being able to display a map in QGIS
does not grant permission to archive it.

For example, the standard **`tile.openstreetmap.org` service does not permit
downloading maps for offline use**. Choose a source whose terms explicitly
allow it; see the [OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/).

The plugin does not grant rights to third-party content or check its licence
automatically. Users are responsible for choosing data and using it lawfully.
To the extent permitted by applicable law, the author accepts no liability for
users' unauthorized copying or distribution of content.

## Plugin licence and development

Author: **Jarosław Sadowski**. The plugin is free and open source under
**GNU GPL version 2 (GPL-2.0-only)**; see [LICENSE](LICENSE) for the terms
and warranty disclaimer. This licence covers the plugin, not downloaded data.

The project was developed through **vibe coding with AI assistance**.
Check each archive's completeness and offline operation before relying on it.

## Help and feedback

[Detailed guide](docs/team-guide.md) ·
[Bug reports and suggestions](https://github.com/jaroslaw-sadowski/qgis-project-snapshot/issues) ·
[Development documentation and ZIP build instructions](docs/development.md)

Include your QGIS and plugin versions and steps to reproduce the problem in a report.
Do not publish passwords, confidential projects or company data.
