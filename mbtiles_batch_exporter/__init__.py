def classFactory(iface):
    from .plugin import ProjectSnapshotPlugin

    return ProjectSnapshotPlugin(iface)
