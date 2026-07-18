# lib/config_loader.py — read config/device_secrets.toml
#
# MicroPython has no `tomllib`. Rather than ship a full TOML parser we do a
# tiny, dependency-free line reader that handles the subset this project uses:
# [section] headers, key = "value" / key = true|false / key = 123, and #
# comments. That is all device_secrets.toml needs.

def _coerce(v):
    v = v.strip()
    if v[:1] == '"' and v[-1:] == '"':
        return v[1:-1]
    if v[:1] == "'" and v[-1:] == "'":
        return v[1:-1]
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(v)
    except ValueError:
        return v


def load_secrets(path="config/device_secrets.toml"):
    """Return nested dict {section: {key: value}}. Missing file -> {}."""
    result = {}
    section = None
    try:
        f = open(path)
    except OSError:
        print("[config] %s not found; using defaults" % path)
        return result
    try:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                result[section] = {}
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.strip()
            # strip trailing inline comment. For a quoted value, keep only up to
            # its closing quote (so `key = "x"  # note` -> "x"); for a bare
            # value, cut at the first '#'.
            if val[:1] in ('"', "'"):
                q = val[0]
                end = val.find(q, 1)
                if end != -1:
                    val = val[:end + 1]
            else:
                val = val.split("#", 1)[0]
            key = key.strip()
            target = result.setdefault(section or "", {})
            target[key] = _coerce(val)
    finally:
        f.close()
    return result
