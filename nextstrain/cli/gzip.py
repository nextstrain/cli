"""
Gzip stream utilities.
"""
import zlib
from io import BufferedIOBase
from typing import BinaryIO


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
        self.__gzip = zlib.compressobj(
            level = zlib.Z_BEST_COMPRESSION,
            wbits = 16 + zlib.MAX_WBITS,    # Offset of 16 is gzip encapsulation
            memLevel = 9,                   # Memory is ~cheap; use it for better compression
        )

    def readable(self):
        return True

    def read(self, size = None):
        return self._compress(self.stream.read(size))

    def read1(self, size = None):
        return self._compress(self.stream.read1(size)) # type: ignore

    def _compress(self, data: bytes):
        if self.__gzip:
            if data:
                return self.__gzip.compress(data)
            else:
                # EOF on underlying stream, flush any remaining compressed
                # data.  On the next call, we'll return EOF too.
                try:
                    return self.__gzip.flush(zlib.Z_FINISH)
                finally:
                    self.__gzip = None # type: ignore
        else:
            # Already hit EOF on the underlying stream and flushed.
            return b''

    def close(self):
        if self.stream:
            try:
                self.stream.close()
            finally:
                self.stream = None
