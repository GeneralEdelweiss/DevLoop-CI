"""Standalone generic validation helpers, independent of any product runtime."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile


_DEVICE = re.compile(r'(?i)(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?\Z')


def portable_path(value):
    """Lexical portable relative file name, not a filesystem confinement check."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValueError('Invalid path')
    for part in value.split('/'):
        if (not part or part in ('.', '..') or part.endswith(('.', ' '))
                or part.lower() == '.git' or _DEVICE.fullmatch(part)
                or any(ord(c) < 32 or c in '<>:"\\|?*' for c in part)):
            raise ValueError('Nonportable path component')
    return value


def path_inventory(paths):
    """Reject case-insensitive duplicate paths and file/directory collisions."""
    files, directories = set(), set()
    for path in paths:
        key = portable_path(path).casefold()
        parents = {'/'.join(key.split('/')[:i]) for i in range(1, len(key.split('/')))}
        if key in files or key in directories or parents & files:
            raise ValueError('Colliding paths')
        files.add(key)
        directories.update(parents)
    return files


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    def reject(value):
        raise ValueError('Nonfinite JSON constant')

    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Nonfinite JSON number')
        return number

    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject, parse_float=finite)


def atomic_json(path, value):
    """Publish complete JSON in a trusted directory; leave old data on failure."""
    path = Path(path)
    raw = json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True).encode('utf-8')
    # Validate the actual serialization, including ambiguous converted dict keys.
    strict_json(raw)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.state-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_blob(raw, expected_digest):
    """Bind exact bytes to a trusted SHA-256; do not normalize line endings."""
    if (not isinstance(raw, bytes) or not isinstance(expected_digest, str)
            or not re.fullmatch(r'[a-f0-9]{64}', expected_digest)
            or hashlib.sha256(raw).hexdigest() != expected_digest):
        raise ValueError('Byte digest mismatch')
