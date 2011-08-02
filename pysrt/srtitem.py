# -*- coding: utf-8 -*-
"""
SubRip's subtitle parser
"""
import re

from pysrt.srtexc import InvalidItem
from pysrt.srttime import SubRipTime


class SubRipItem(object):
    """
    SubRipItem(index, start, end, text)

    index -> int: index of item in file. 0 by default.
    start, end -> SubRipTime or coercible.
    text -> unicode: text content for item.
    """
    TIME_PATTERN = r'\d{2}:\d{2}:\d{2}[,\.]\d{3}'

    ITEM_PATTERN = (
        r'\A(?P<index>\d+)$'
        r'^(?P<start>%(time)s)\s-->\s(?P<end>%(time)s)[\ XY\:\d]*$'
        r'^(?P<text>.*)\Z') % {'time': TIME_PATTERN}

    RE_ITEM = re.compile(ITEM_PATTERN, re.DOTALL | re.MULTILINE)

    ITEM_PATTERN = u'%s\n%s --> %s\n%s\n'

    def __init__(self, index=0, start=None, end=None, text='', **kwargs):
        self.index = int(index)
        self.start = SubRipTime.coerce(start)
        self.end = SubRipTime.coerce(end)
        self.text = unicode(text)

    def __unicode__(self):
        return self.ITEM_PATTERN % (self.index, self.start, self.end,
                                    self.text)

    def __cmp__(self, other):
        return cmp(self.start, other.start) \
            or cmp(self.end, other.end)

    def shift(self, *args, **kwargs):
        """
        shift(hours, minutes, seconds, milliseconds, ratio)

        Add given values to start and end attributes.
        All arguments are optional and have a default value of 0.
        """
        self.start.shift(*args, **kwargs)
        self.end.shift(*args, **kwargs)

    @classmethod
    def from_string(cls, source):
        match = cls.RE_ITEM.match(source.replace('\r', ''))
        if not match:
            raise InvalidItem(source)

        data = dict(match.groupdict())
        for group in ('start', 'end'):
            data[group] = SubRipTime.from_string(data[group])
        return cls(**data)
