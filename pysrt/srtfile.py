# -*- coding: utf-8 -*-
import os
import sys
import codecs
from UserList import UserList
from itertools import chain
from copy import copy
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from pysrt.srtexc import InvalidItem
from pysrt.srtitem import SubRipItem


class SubRipFile(UserList, object):
    """
    SubRip file descriptor.

    Provide a pure Python mapping on all metadata.

    SubRipFile(items, eol, path, encoding)

    items -> list of SubRipItem. Default to [].
    eol -> str: end of line character. Default to linesep used in opened file
        if any else to os.linesep.
    path -> str: path where file will be saved. To open an existant file see
        SubRipFile.open.
    encoding -> str: encoding used at file save. Default to utf-8.
    """
    ERROR_PASS = 0
    ERROR_LOG = 1
    ERROR_RAISE = 2

    DEFAULT_ENCODING = 'utf_8'

    BOMS = ((codecs.BOM_UTF32_LE, 'utf_32_le'),
            (codecs.BOM_UTF32_BE, 'utf_32_be'),
            (codecs.BOM_UTF16_LE, 'utf_16_le'),
            (codecs.BOM_UTF16_BE, 'utf_16_be'),
            (codecs.BOM_UTF8, 'utf_8'))
    CODECS_BOMS = dict((codec, unicode(bom, codec)) for bom, codec in BOMS)
    BIGGER_BOM = max(len(bom) for bom, encoding in BOMS)

    def __init__(self, items=None, eol=None, path=None, encoding='utf-8'):
        UserList.__init__(self, items or [])
        self._eol = eol
        self.path = path
        self.encoding = encoding

    def _get_eol(self):
        return self._eol or os.linesep

    def _set_eol(self, eol):
        self._eol = self._eol or eol

    eol = property(_get_eol, _set_eol)

    @classmethod
    def _handle_error(cls, error, error_handling, path, index):
        path = path and os.path.abspath(path)
        if error_handling == cls.ERROR_RAISE:
            error.args = (path, index) + error.args
            raise error
        if error_handling == cls.ERROR_LOG:
            sys.stderr.write('PySRT-InvalidItem(%s:%s): \n' % (path, index))
            sys.stderr.write(error.args[0].encode('ascii', 'replace'))
            sys.stderr.write('\n')

    @classmethod
    def open(cls, path='', encoding=None, error_handling=ERROR_PASS, eol=None):
        """
        open([path, [encoding]])

        If you do not provide any encoding, it can be detected if the file
        contain a bit order mark, unless it is set to utf-8 as default.
        """
        new_file = cls(path=path, encoding=encoding)
        source_file = cls._open_unicode_file(path, claimed_encoding=encoding)
        new_file.read(source_file, error_handling=error_handling)
        eol = eol or cls._extract_newline(source_file)
        if eol is not None:
            new_file.eol = eol
        source_file.close()
        return new_file

    def read(self, source_file, error_handling=ERROR_PASS):
        string_buffer = []
        for index, line in enumerate(chain(source_file, u'\n')):
            if line.strip():
                string_buffer.append(line)
            else:
                source = u''.join(string_buffer)
                string_buffer = []
                if source.strip():
                    try:
                        self.append(SubRipItem.from_string(source))
                    except InvalidItem, error:
                        self._handle_error(error, error_handling, self.path, index)
        return self

    @staticmethod
    def _extract_newline(file_descriptor):
        if hasattr(file_descriptor, 'newlines') and file_descriptor.newlines:
            if isinstance(file_descriptor.newlines, basestring):
                return file_descriptor.newlines
            else:
                return file_descriptor.newlines[0]

    @classmethod
    def _detect_encoding(cls, path):
        file_descriptor = open(path)
        first_chars = file_descriptor.read(cls.BIGGER_BOM)
        file_descriptor.close()

        for bom, encoding in cls.BOMS:
            if first_chars.startswith(bom):
                return encoding

        # TODO: maybe a chardet integration
        return cls.DEFAULT_ENCODING

    @classmethod
    def _open_unicode_file(cls, path, claimed_encoding=None):
        encoding = claimed_encoding or cls._detect_encoding(path)
        source_file = codecs.open(path, 'rU', encoding=encoding)
        
        # get rid of BOM if any
        possible_bom = cls.CODECS_BOMS.get(encoding, None)
        if possible_bom:
            file_bom = source_file.read(len(possible_bom))
            if not file_bom == possible_bom:
                source_file.seek(0) # if not rewind
        return source_file

    @classmethod
    def from_string(cls, source, **kwargs):
        error_handling = kwargs.pop('error_handling', None)
        new_file = cls(**kwargs)
        new_file.read(source.splitlines(True), error_handling=error_handling)
        return new_file

    def slice(self, starts_before=None, starts_after=None, ends_before=None,
              ends_after=None):
        clone = copy(self)

        if starts_before:
            clone.data = (i for i in clone.data if i.start < starts_before)
        if starts_after:
            clone.data = (i for i in clone.data if i.start > starts_after)
        if ends_before:
            clone.data = (i for i in clone.data if i.end < ends_before)
        if ends_after:
            clone.data = (i for i in clone.data if i.end > ends_after)

        clone.data = list(clone.data)
        return clone

    def shift(self, *args, **kwargs):
        """shift(hours, minutes, seconds, milliseconds, ratio)

        Shift `start` and `end` attributes of each items of file either by
        applying a ratio or by adding an offset.

        `ratio` should be either an int or a float.
        Example to convert subtitles from 23.9 fps to 25 fps:
        >>> subs.shift(ratio=25/23.9)

        All "time" arguments are optional and have a default value of 0.
        Example to delay all subs from 2 seconds and half
        >>> subs.shift(seconds=2, milliseconds=500)
        """
        for item in self:
            item.shift(*args, **kwargs)

    def clean_indexes(self):
        self.sort()
        for index, item in enumerate(self):
            item.index = index + 1

    def save(self, path=None, encoding=None, eol=None):
        """
        save([path][, encoding][, eol])

        Use init path if no other provided.
        Use init encoding if no other provided.
        Use init eol if no other provided.
        """
        path = path or self.path

        save_file = open(path, 'w+')
        self.write_into(save_file, encoding=encoding, eol=eol)
        save_file.close()

    def write_into(self, io, encoding=None, eol=None):
        encoding = encoding or self.encoding
        output_eol = eol or self.eol

        for item in self:
            string_repr = unicode(item)
            if output_eol != '\n':
                string_repr = string_repr.replace('\n', output_eol)
            io.write(string_repr.encode(encoding))
