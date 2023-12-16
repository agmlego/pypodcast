from collections.abc import Mapping
import concurrent.futures
import functools
import itertools
import logging
import mimetypes
import tempfile

import arrow
import feedparser
import mutagen
import mutagen.mp3
import mutagen.id3
from pathvalidate import sanitize_filename, sanitize_filepath
import requests
import rich.console
from rich.logging import RichHandler
import rich.traceback

from .config import open_feedfile, open_cache, get_data_dir
from .junk_drawer import import_string, gentle_format

logging.getLogger("urllib3").setLevel(logging.WARNING)
FORMAT = "%(message)s"
logging.basicConfig(
    level="DEBUG", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)

log = logging.getLogger("pypodcast")


def catch_errors(func):
    @functools.wraps(func)
    def _(*p, **kw):
        try:
            return func(*p, **kw)
        except Exception:
            rich.console.Console().print_exception(show_locals=False)
    return _


@catch_errors
def process_feeds(pool: concurrent.futures.Executor):
    """
    Run through the feeds and do HTTP stuff
    """
    with open_feedfile() as feedfile:
        for feedconfig in feedfile['feed']:
            log.debug(f"{feedconfig=}")
            feed = feedparser.parse(feedconfig['url'])
            # TODO: Update feedfile based on HTTP status

            for entry in feed.entries:
                process_entry(feedconfig, feed, entry)
                yield pool.submit(process_entry, feedconfig, feed, entry)


@catch_errors
def process_entry(
    config: Mapping,
    feed: feedparser.FeedParserDict,
    entry: feedparser.FeedParserDict,
):
    cache_key = f"{feed.href}#{entry.id}"
    with open_cache(cache_key) as cache:
        if cache:
            # We've processed this entry. Just exit.
            return
        log.info(f"{feed.feed.title}: {entry.title}")
        # 1. Figure out where the godsdamned audio is
        urls = {
            (bit.type, bit.href)
            for bit in itertools.chain(
                entry.enclosures,
                entry.links,
                entry.get('content', []),
            )
            if bit.type.startswith('audio/')
        }
        (audio_type, audio_url), = urls

        # 2. Download the audio
        with tempfile.SpooledTemporaryFile() as audiobuf:
            with requests.Session() as http:
                resp = http.get(audio_url, stream=True)
                resp.raise_for_status()
                for chunk in resp.iter_content(None):
                    audiobuf.write(chunk)

            audiobuf.seek(0)

            # 3. Spin up mutagen
            audiometa = mutagen.File(fileobj=audiobuf)

            # 4. Instantiate the provider
            providercls = import_string(config['provider'])
            metadata_provider = providercls(feed.feed, entry, audiometa)

            # 5. Fix up audio tags
            fix_tags(audiometa, metadata_provider)

            # 6. Write out the audio file
            audiobuf.seek(0)
            audiometa.save(fileobj=audiobuf)

            dest = get_data_dir() / sanitize_filepath(
                gentle_format(config['filepattern'],metadata_provider)
                + _get_ext(audiometa.mime)
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            log.info(f'-> {dest}')
            audiobuf.seek(0)
            dest.write_bytes(audiobuf.read())

            cache['processed'] = 'yes'


def _get_ext(mimes: list[str]) -> str:
    for mime in mimes:
        ext = mimetypes.guess_extension(mime)
        if ext:
            return ext
    raise ValueError("No extension found for any of {mimes!r}")


def dl_blob(url) -> bytes:
    """
    Gets the binary data of a URL
    """
    resp = requests.get(url)
    resp.raise_for_status()

    # guard against extended MIME types
    assert ';' not in resp.headers['Content-Type']
    return resp.content, resp.headers['Content-Type']


@functools.singledispatch
def fix_tags(tags, feed, entry):
    raise NotImplementedError("Unknown format {tags!r}")


@fix_tags.register
def _(tags: mutagen.mp3.MP3, provider):
    tags['PCST:'] = mutagen.id3.PCST(1)
    if art := provider.episode_art:
        if isinstance(art, str):
            # URL, download it
            art, mimetype = dl_blob(art)
        tags['APIC:'] = mutagen.id3.APIC(
            encoding=0,
            mime=mimetype,
            type=3, desc='Track',
            data=art
        )
    if epnum := provider.episode_number:
        tags.tags.delall('TRCK')
        tags['TRCK:'] = mutagen.id3.TRCK(text=str(epnum))
    if epurl := provider.episode_url:
        tags.tags.delall('WOAR')
        tags['WOAR:'] = mutagen.id3.WOAR(url=str(epurl))
    if title := provider.episode_title:
        tags.tags.delall('TIT2')
        tags['TIT2:'] = mutagen.id3.TIT2(text=title)
    if sub := provider.episode_subtitle:
        tags.tags.delall('TIT3')
        tags['TIT3:'] = mutagen.id3.TIT3(text=sub)
    if hosts := provider.hosts:
        tags.tags.delall('TPE1')
        if isinstance(hosts, list):
            hosts = ', '.join(hosts)
        tags['TPE1:'] = mutagen.id3.TPE1(text=hosts)
    if guests := provider.guests:
        tags.tags.delall('TPE2')
        if isinstance(guests, list):
            guests = ', '.join(guests)
        tags['TPE2:'] = mutagen.id3.TPE2(text=guests)
    if directors := provider.directors:
        tags.tags.delall('TPE3')
        if isinstance(directors, list):
            directors = ', '.join(directors)
        tags['TPE3:'] = mutagen.id3.TPE3(text=directors)
    if editors := provider.editors:
        tags.tags.delall('TPE4')
        if isinstance(editors, list):
            editors = ', '.join(editors)
        tags['TPE4:'] = mutagen.id3.TPE4(text=editors)
    if producers := provider.producers:
        tags.tags.delall('TPRO')
        if isinstance(producers, list):
            producers = ', '.join(producers)
        tags['TPRO:'] = mutagen.id3.TPRO(text=producers)
    if publisher := provider.publisher:
        tags.tags.delall('TPUB')
        tags['TPUB:'] = mutagen.id3.TPUB(text=publisher)
    if summary := provider.summary:
        tags.tags.delall('COMM')
        tags.tags.delall('TDES')
        tags['COMM:'] = mutagen.id3.COMM(
            lang='eng',
            desc=u'Summary',
            text=summary
        )
        tags['TDES:'] = mutagen.id3.TDES(text=summary)
    if album := provider.album:
        tags.tags.delall('TALB')
        tags['TALB:'] = mutagen.id3.TALB(text=album)
    if season := provider.season:
        tags.tags.delall('TPOS')
        tags['TPOS:'] = mutagen.id3.TPOS(text=season)
    if cat := provider.category:
        tags.tags.delall('TCAT')
        tags.tags.delall('TCON')
        if isinstance(cat, list):
            cat = ', '.join(cat)
        tags['TCAT:'] = mutagen.id3.TCAT(text=cat)
        tags['TCON:'] = mutagen.id3.TCON(text=cat + ', Podcast')
    else:
        tags.tags.delall('TCON')
        tags['TCON:'] = mutagen.id3.TCON(text='Podcast')
    if cr := provider.copyright:
        tags.tags.delall('TCOP')
        tags['TCOP:'] = mutagen.id3.TCOP(text=cr)
    if pubdate := provider.pub_date:
        assert isinstance(pubdate, arrow.Arrow)
        tags.tags.delall('TDOR')
        tags.tags.delall('TDRC')
        tags['TDOR:'] = mutagen.id3.TDOR(text=pubdate.to('utc').isoformat())
        tags['TDRC:'] = mutagen.id3.TDRC(text=str(pubdate.to('utc').year))
    if epid := provider.episode_id:
        tags['TGID:'] = mutagen.id3.TGID(text=epid)


def main():
    try:
        rich.traceback.install(show_locals=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            futs = list(process_feeds(pool))
            concurrent.futures.wait(futs)
    except KeyboardInterrupt:
        pass
