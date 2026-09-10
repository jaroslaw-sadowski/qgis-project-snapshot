# SPDX-License-Identifier: GPL-2.0-only


def classFactory(iface):
    from .plugin import ProjectSnapshotPlugin

    return ProjectSnapshotPlugin(iface)
