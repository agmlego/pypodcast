import concurrent.futures
import functools
import itertools
import tempfile
import traceback

import feedparser
import requests

from .config import open_feedfile, open_cache


def catch_errors(func):
    @functools.wraps(func)
    def _(*p, **kw):
        try:
            return func(*p, **kw)
        except Exception:
            traceback.print_exc()
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
                yield pool.submit(process_entry, feed, entry)


@catch_errors
def process_entry(
    feed: feedparser.FeedParserDict,
    entry: feedparser.FeedParserDict,
):
    with open_cache(entry.id) as cache:
        if cache:
            # We've processed this entry. Just exit.
            return
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
            providercls = ...
            metadata_provider = providercls(feed, entry, audiometa)



def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futs = list(process_feeds(pool))
        concurrent.futures.wait(futs)