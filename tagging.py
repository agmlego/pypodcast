import json
from typing import Dict, List
from os.path import join, isfile
from os import makedirs
from io import BytesIO
import feedparser
import requests
from mutagen.id3 import APIC, TXXX
from mutagen.mp3 import MP3
from pathvalidate import sanitize_filename, sanitize_filepath

maxLimit = 1000


def get_entries(url: str) -> List:
    feed = feedparser.parse(url)
    return feed['entries']


def make_file(entry: Dict) -> None:
    mp3url = None
    for link in entry['links']:
        if link['rel'] == 'enclosure' or 'mpeg' in link['type']:
            mp3url = link['href']
            break
    mp3 = requests.get(mp3url).content
    tags = MP3(BytesIO(mp3))
    artist = 'UNKNOWN'
    if 'TPE1' in tags:
        artist = tags['TPE1'].text[0]
    album = 'UNKNOWN'
    if 'TALB' in tags:
        album = tags['TALB'].text[0]
    pth = sanitize_filepath(join(
        'podcasts',
        artist,
        album
    ), platform='auto')
    makedirs(pth, exist_ok=True)
    fpth = join(pth, sanitize_filename(entry['title']+'.mp3',
                                       platform='auto'))
    print(fpth)
    with open(fpth, 'wb') as mp3file:
        mp3file.write(mp3)

    tags = MP3(filename=fpth)
    fix_tags(tags=tags, entry=entry)


def fix_tags(tags: MP3, entry: Dict) -> None:
    art = requests.get(entry['image']['href']).content
    tags['APIC:'] = APIC(
        encoding=0,
        mime='image/jpeg',
        type=3, desc=u'Cover',
        data=art
    )
    tags['TXXX:Summary'] = TXXX(
        encoding=1,
        desc=u'Summary',
        text=entry['summary']
    )
    tags['TXXX:ID'] = TXXX(
        encoding=1,
        desc=u'ID',
        text=entry['id']
    )
    tags['TXXX:Link'] = TXXX(
        encoding=1,
        desc=u'Link',
        text=entry['link']
    )
    tags.save()


if __name__ == '__main__':
    if isfile('cache.json'):
        cache = json.load(open('cache.json'))
    else:
        cache = {}

    urls = [
    ]
    for url in urls:
        limit = 0
        if url not in cache:
            print(f'Adding {url} to cache')
            cache[url] = []
        entries = get_entries(url)
        print(f'Reading next {maxLimit} entries of {
              len(entries)-len(cache[url])} remaining ({len(entries)} total)')

        for entry in entries:
            if entry['id'] in cache[url]:
                print(f'Skipping {entry["title"]}!')
                continue
            limit += 1
            print(
                f'{limit}/{maxLimit} Adding id:{entry["id"]} to cache on {url}')
            cache[url].append(entry['id'])
            try:
                make_file(entry)
            except Exception as e:
                del cache[url][-1]
                print(f'Much error! {e}')
                limit -= 1
            json.dump(cache, open('cache.json', 'w'))
            if limit > maxLimit:
                break
