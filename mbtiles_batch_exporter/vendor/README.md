# Bundled XML protection

ElementTree subset of **defusedxml 0.7.1**, Christian Heimes, PSF license
(see defusedxml/LICENSE.txt). Source: https://github.com/tiran/defusedxml
PyPI wheel SHA-256: `a352e7e428770286cc899e2542b6cdaedb2b4953ff269a210103ec58f6198a61`.

Only __init__.py, common.py and ElementTree.py are included. The plugin uses
ElementTree.parse/fromstring and exceptions, with default entity and external
reference rejection. The unused global defuse_stdlib() API and its _apply_defusing helper were
removed; other XML frontends are not bundled. No pip, global
monkey patching, or installation-time network access is required.

Unused Python 2 import/parser branches and their PY3 flag were also removed:
the plugin requires Python 3.10 or newer. The Python 3 parser behavior is unchanged.
Apart from these removals, upstream code is
unchanged except for narrowly scoped Bandit comments on ElementTree imports
(the implementation of the protected parser itself). Upstream formatting
is retained. Never replace these imports with an unprotected parser fallback.
