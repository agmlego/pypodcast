import re

import arrow
import markdownify


class Provider:
    """
    Takes the feed, entry, and audio tags, and condenses it into metadata
    """
    def __init__(self, feed, entry, tags):
        self.feed = feed
        self.entry = entry
        self.tags = tags

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            pass

        try:
            return self.entry[key]
        except KeyError:
            pass

        try:
            return self.feed[key]
        except KeyError:
            pass

        raise KeyError(f"Cannot find {key!r}")

    @property
    def episode_id(self) -> str:
        raise NotImplementedError
    
    @property
    def episode_url(self) -> str:
        raise NotImplementedError

    @property
    def episode_art(self) -> str | bytes:
        raise NotImplementedError

    @property
    def episode_number(self):
        raise NotImplementedError

    @property
    def episode_title(self):
        raise NotImplementedError

    @property
    def episode_subtitle(self):
        raise NotImplementedError

    @property
    def summary(self) -> str:
        raise NotImplementedError

    @property
    def album(self) -> str:
        raise NotImplementedError

    @property
    def season(self) -> str:
        raise NotImplementedError

    @property
    def category(self) -> str | list[str]:
        raise NotImplementedError

    @property
    def copyright(self) -> str:
        raise NotImplementedError

    @property
    def pub_date(self) -> arrow.Arrow:
        raise NotImplementedError
    
    @property
    def hosts(self) -> str | list[str]:
        raise NotImplementedError
    
    @property
    def guests(self) -> str | list[str]:
        raise NotImplementedError
    
    @property
    def editors(self) -> str | list[str]:
        raise NotImplementedError
    
    @property
    def directors(self) -> str | list[str]:
        raise NotImplementedError
    
    @property
    def producers(self) -> str | list[str]:
        raise NotImplementedError
    
    @property
    def publisher(self) -> str:
        raise NotImplementedError
    
    


class Nightvale(Provider):
    @property
    def episode_id(self):
        return self.entry.id
    
    @property
    def episode_art(self):
        return self.entry.image.href

    @property
    def episode_number(self):
        num, _ = self._num_title()
        return num

    @property
    def episode_title(self):
        _, title = self._num_title()
        return title

    @property
    def episode_subtitle(self):
        return self.entry.subtitle

    @property
    def summary(self):
        return markdownify.markdownify(self.entry.description)

    def _num_title(self):
        if match := re.search(r'^(\d+)\s*-\s*(.+)$', self.entry.title):
            return int(match[1]), match[2]
        else:
            return 0, self.entry.title

    @property
    def album(self):
        # FIXME: Sort this out better (ANGRY KEYSMASH)
        num, _ = self._num_title()
        if num:
            return "Welcome to Night Vale"
        else:
            return ""

    @property
    def category(self):
        return ['Fiction', 'Science Fiction']

    @property
    def copyright(self):
        return self.feed.copyright

    @property
    def pub_date(self):
        return arrow.get(self.entry.published_parsed)
    
    @property
    def episode_url(self) -> str:
        for link in self.entry.links:
            if link.rel == 'alternate':
                return link.href
        return None

    @property
    def season(self) -> str:
        return None
    
    @property
    def guests(self) -> str | list[str]:
        return [a.name for a in self.entry.authors]
    
    @property
    def hosts(self) -> str | list[str]:
        g = []
        for line in self.summary.split('\n'):
            if 'Narrated' in line:
                g.append(line.split(' by ')[-1])
            
            if 'Weather' in line:
                g.append(line.split(': ')[-1])

        return g
    
    @property
    def editors(self) -> str | list[str]:
        for line in self.summary.split('\n'):
            if 'Written' in line:
                return line.split(' by ')[-1]

        return None
    
    @property
    def directors(self) -> str | list[str]:
        for line in self.summary.split('\n'):
            if 'Music' in line:
                return line.split(': ')[-1]

        return None
    
    @property
    def producers(self) -> str | list[str]:
        for line in self.summary.split('\n'):
            if 'Logo' in line:
                return line.split(': ')[-1]

        return None
    
    @property
    def publisher(self) -> str:
        return self.feed.publisher
    
    


class Patreon(Provider):
    pass


class Transistor(Provider):
    pass