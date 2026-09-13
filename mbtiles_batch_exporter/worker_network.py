# SPDX-License-Identifier: GPL-2.0-only

"""Transfer QGIS proxy configuration as plain data over a private stdin pipe."""

from qgis.core import QgsNetworkAccessManager, QgsSettings, QgsSettingsTree
from qgis.PyQt.QtNetwork import QNetworkProxy, QNetworkProxyFactory

# The native settings tree replaced the legacy proxy keys in newer QGIS.
# Keep the pipe protocol stable; translate only the local profile keys.
_PROXY_KEYS = {
    legacy: f"proxy/{native if QgsSettingsTree.node('proxy') else legacy}"
    for legacy, native in (
        ("proxyEnabled", "proxy-enabled"),
        ("proxyType", "proxy-type"),
        ("proxyHost", "proxy-host"),
        ("proxyPort", "proxy-port"),
        ("proxyExcludedUrls", "proxy-excluded-urls"),
        ("noProxyUrls", "no-proxy-urls"),
    )
}


def network_snapshot():
    """Called only on the desktop main thread; never log the returned data."""
    settings = QgsSettings()
    manager = QgsNetworkAccessManager.instance()
    enabled = settings.value(_PROXY_KEYS["proxyEnabled"], False, type=bool)
    keys = ("proxyType", "proxyHost", "proxyPort", "proxyExcludedUrls", "noProxyUrls")
    values = {key: settings.value(_PROXY_KEYS[key]) for key in keys}
    values["proxyEnabled"] = enabled
    # The live manager has already resolved the profile's authentication config.
    proxy = manager.fallbackProxy()
    return {
        "version": 1,
        "settings": values,
        "timeout": manager.timeout(),
        "system": enabled and QNetworkProxyFactory.usesSystemConfiguration(),
        "credentials": {
            "host": proxy.hostName() if enabled else "",
            "port": proxy.port() if enabled else 0,
            "user": proxy.user() if enabled else "",
            "password": proxy.password() if enabled else "",
        },
    }


def configure_network(snapshot, diagnostic=None):
    """Called before opening a layer in a worker's isolated QGIS profile."""
    if snapshot.get("version") != 1:
        raise ValueError("Unsupported network protocol")
    settings = QgsSettings()
    settings.remove("proxy")
    for key, value in snapshot["settings"].items():
        if value is not None:
            settings.setValue(_PROXY_KEYS[key], value)
    # Never persist the proxy password, user name or the desktop auth database.
    settings.sync()
    QNetworkProxyFactory.setUseSystemConfiguration(snapshot["system"])
    if not snapshot["settings"]["proxyEnabled"]:
        QNetworkProxy.setApplicationProxy(
            QNetworkProxy(QNetworkProxy.ProxyType.NoProxy)
        )
    manager = QgsNetworkAccessManager.instance()
    manager.setupDefaultProxyAndCache()
    manager.setTimeout(snapshot["timeout"])
    credentials = snapshot["credentials"]

    def authenticate(proxy, authenticator):
        if diagnostic:
            diagnostic.emit("proxy_authentication_requested")
        if (
            proxy.hostName() == credentials["host"]
            and proxy.port() == credentials["port"]
            and credentials["user"]
        ):
            authenticator.setUser(credentials["user"])
            authenticator.setPassword(credentials["password"])

    manager.proxyAuthenticationRequired.connect(authenticate)
    # Qt retains the connected callable for the process lifetime.
    return authenticate
