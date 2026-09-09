def classFactory(iface):
    from .plugin import MBTilesBatchExporterPlugin
    return MBTilesBatchExporterPlugin(iface)
