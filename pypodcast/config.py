import contextlib
import functools
import json
import os
import pathlib

import tomlkit


FEEDFILE = 'feeds.toml'
CACHEDIR = '.pypodcast-cache'


@functools.cache
def get_data_dir() -> pathlib.Path:
    if 'PYPODCAST_DATA' in os.environ:
        dir = pathlib.Path(os.environ['PYPODCAST_DATA'])
    else:
        dir = pathlib.Path.cwd()
    dir.mkdir(parents=True, exist_ok=True)
    return dir


@functools.cache
def get_cache_dir() -> pathlib.Path:
    dir = get_data_dir() / CACHEDIR
    dir.mkdir(parents=True, exist_ok=True)
    return True

@contextlib.contextmanager
def open_feedfile(*, create: bool = True):
    """
    Open the feedfile for updating
    """
    path = get_data_dir() / FEEDFILE
    try:
        f = open(path, 'r+t', encoding='utf-8')
    except FileNotFoundError:
        if create:
            f = open(path, 'w+t', encoding='utf-8')
        else:
            raise
    with f:
        doc = tomlkit.parse(f.read())

        yield doc

        f.seek(0)
        f.write(tomlkit.dumps(doc))
        f.truncate()

@contextlib.contextmanager
def open_cache(ident):
    # FIXME: Implement this
    yield {}