class Provider:
	"""
	Takes the feed, entry, and audio tags, and condenses it into metadata
	"""
	def __init__(self, feed, entry):
		self.feed = feed
		self.entry = entry

	def __getitem__(self, key):
		try:
			return getattr(self)
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

		raise KeyError("Cannot find {key!r}")