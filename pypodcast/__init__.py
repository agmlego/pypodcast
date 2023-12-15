from collections.abc import Mapping
import concurrent.futures
import functools
import itertools
import mimetypes
import tempfile
import traceback

import arrow
import feedparser
import mutagen
import mutagen.mp3
import mutagen.id3
import requests
import rich.console
import rich.traceback

from .config import open_feedfile, open_cache, get_data_dir
from .junk_drawer import import_string, gentle_format


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
            print(f"{feedconfig=}")
            feed = feedparser.parse(feedconfig['url'])
            # TODO: Update feedfile based on HTTP status

            for entry in feed.entries:
                process_entry(feedconfig, feed, entry)
                return []
                # yield pool.submit(process_entry, feedconfig, feed, entry)


@catch_errors
def process_entry(
    config: Mapping,
    feed: feedparser.FeedParserDict,
    entry: feedparser.FeedParserDict,
):
    with open_cache(entry.id) as cache:
        if cache:
            # We've processed this entry. Just exit.
            return
        print(entry.title)
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

            dest = get_data_dir() / (gentle_format(config['filepattern'], metadata_provider) + _get_ext(audiometa.mime))
            dest.parent.mkdir(parents=True, exist_ok=True)
            audiobuf.seek(0)
            dest.write_bytes(audiobuf.read())



def _get_ext(mimes: list[str]) -> str:
    for mime in mimes:
        ext = mimetypes.guess_extension(mime)
        if ext:
            return ext
    else:
        raise ValueError("No extension found for any of {mimes!r}")


def dl_blob(url) -> bytes:
    """
    Gets the binary data of a URL
    """
    print(f"dl_blob {url=}")
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.content


@functools.singledispatch
def fix_tags(tags, feed, entry):
    raise NotImplementedError("Unknown format {tags!r}")


@fix_tags.register
def _(tags: mutagen.mp3.MP3, provider):
    tags['PCST:'] = mutagen.id3.PCST(1)
    if art := provider.episode_art:
        print(f"fix_tags {art=}")
        if isinstance(art, str):
            # URL, download it
            art = dl_blob(art)

        tags['APIC:'] = mutagen.id3.APIC(
            encoding=0,
            mime='image/jpeg',  # FIXME: Actually pull this from somewhere
            type=3, desc=u'Track',
            data=art
        )
    if epnum := provider.episode_number:
        tags['TRCK:'] = mutagen.id3.TRCK(text=str(epnum))
    if title := provider.episode_title:
        tags['TIT2:'] = mutagen.id3.TIT2(text=title)
    if sub := provider.episode_subtitle:
        tags['TIT3:'] = mutagen.id3.TIT3(text=sub)
    if summary := provider.summary:
        tags['COMM:'] = mutagen.id3.COMM(
            lang='eng',
            desc=u'Summary',
            text=summary
        )
        tags['TDES:'] = mutagen.id3.TDES(text=summary)
    if album := provider.album:
        tags['TALB:'] = mutagen.id3.TALB(text=album)
    if cat := provider.category:
        if isinstance(cat, list):
            cat = ', '.join(cat)
        tags['TCAT:'] = mutagen.id3.TCAT(text=cat)
        tags['TCON:'] = mutagen.id3.TCON(text=cat + ', Podcast')
    else:
        tags['TCON:'] = mutagen.id3.TCON(text='Podcast')
    if cr := provider.copyright:
        tags['TCOP:'] = mutagen.id3.TCOP(text=cr)
    if pub := provider.pub_date:
        assert isinstance(pub, arrow.Arrow)
        tags['TDOR:'] = mutagen.id3.TDOR(text=pub.to('utc').isoformat())
    if epid := provider.episode_id:
        tags['TGID:'] = mutagen.id3.TGID(text=epid)


def main():
    rich.traceback.install(show_locals=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        futs = list(process_feeds(pool))
        concurrent.futures.wait(futs)