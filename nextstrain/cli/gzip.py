"""
Gzip stream utilities.
"""
import zlib
from io import BufferedIOBase
from typing import BinaryIO
from .util import warn


class GzipCompressingReader(BufferedIOBase):
    """
    Compress a data stream as it is being read.

    The constructor takes an existing, readable byte *stream*.  Calls to this
    class's :meth:`.read` method will read data from the source *stream* and
    return a compressed copy.
    """
    def __init__(self, stream: BinaryIO):
        if not stream.readable():
            raise ValueError('"stream" argument must be readable.')

        self.stream = stream
        self.__buffer = b''
        self.__gzip = zlib.compressobj(
            level = zlib.Z_BEST_COMPRESSION,
            wbits = 16 + zlib.MAX_WBITS,    # Offset of 16 is gzip encapsulation
            memLevel = 9,                   # Memory is ~cheap; use it for better compression
        )

    def readable(self):
        return True

    def read(self, size = None):
        assert size != 0
        assert self.stream

        if size is None:
            size = -1

        # Keep reading chunks until we have a bit of compressed data to return,
        # since returning an empty byte string would be interpreted as EOF.
        while not self.__buffer and self.__gzip:
            chunk = self.stream.read(size)

            self.__buffer += self.__gzip.compress(chunk)

            if not chunk or size < 0:
                # Read to EOF on underlying stream, so flush any remaining
                # compressed data and return whatever we have.  We'll return an
                # empty byte string as EOF ourselves on any subsequent calls.
                self.__buffer += self.__gzip.flush(zlib.Z_FINISH)
                self.__gzip = None

        if size > 0 and len(self.__buffer) > size:
            # This should be pretty rare since we're reading N bytes and then
            # *compressing* to fewer bytes.  It could happen in the rare case
            # of lots of data still stuck in the buffer from a previous call.
            compressed = self.__buffer[0:size]
            self.__buffer = self.__buffer[size:]
        else:
            compressed = self.__buffer
            self.__buffer = b''

        return compressed

    def close(self):
        if self.stream:
            try:
                self.stream.close()
            finally:
                self.stream = None


class GzipDecompressingWriter(BufferedIOBase):
    """
    Decompress a gzip data stream as it is being written.

    The constructor takes an existing, writable byte *stream*.  Data written to
    this class's :meth:`.write` will be decompressed and then passed along to
    the destination *stream*.
    """
    # Offset of 32 means we will accept a zlib or gzip encapsulation, per
    # <https://docs.python.org/3/library/zlib.html#zlib.decompress>.  Seems no
    # downside to applying Postel's Law here.
    #
    def __init__(self, stream: BinaryIO):
        if not stream.writable():
            raise ValueError('"stream" argument must be writable.')

        self.stream = stream
        self.__gunzip = zlib.decompressobj(32 + zlib.MAX_WBITS)

    def writable(self):
        return True

    def write(self, data: bytes): # type: ignore[override]
        assert self.stream and self.__gunzip
        return self.stream.write(self.__gunzip.decompress(data))

    def flush(self):
        assert self.stream and self.__gunzip
        super().flush()
        self.stream.flush()

    def close(self):
        if self.stream:
            assert self.__gunzip
            try:
                self.stream.write(self.__gunzip.flush())
                self.stream.close()
            finally:
                self.stream = None
                self.__gunzip = None


def ContentDecodingWriter(encoding, stream):
    """
    Wrap a writeable *stream* in a layer which decodes *encoding*.

    *encoding* is expected to be a ``Content-Encoding`` HTTP header value.
    ``gzip`` and ``deflate`` are supported.  Unsupported values will issue a
    warning and return the *stream* unwrapped.  An *encoding* of ``None`` will
    also return the stream unwrapped, but without a warning.
    """
    if encoding is not None and encoding.lower() in {"gzip", "deflate"}:
        return GzipDecompressingWriter(stream)
    else:
        if encoding is not None:
            warn("Ignoring unknown content encoding «%s»" % encoding)
        return stream
