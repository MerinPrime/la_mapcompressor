import base64
import struct
from typing import Optional, Union
from urllib.parse import quote, unquote

from lzstring import LZString


class ByteBuffer:
    __slots__ = ("bytes", "endian", "offset")

    def __init__(
        self, _bytes: Optional[bytearray] = None, *, big_endian: bool = True
    ) -> None:
        if _bytes is None:
            self.bytes: bytearray = bytearray()
        else:
            self.bytes: bytearray = _bytes
        self.offset: int = 0
        self.endian: str = ">" if big_endian else "<"

    @property
    def size(self) -> int:
        return len(self.bytes)

    def set_endian(self, endian: str) -> None:
        if endian not in ("<", ">"):
            raise ValueError(
                f'Invalid value for endian: "{endian}". Expected either "<" (little-endian) or ">" (big-endian)',
            )
        self.endian = endian

    def set_little_endian(self) -> None:
        self.endian = "<"

    def set_big_endian(self) -> None:
        self.endian = ">"

    def read_bytes(self, count: int = 1) -> bytearray:
        if self.offset + count > self.size:
            raise EOFError(
                f"Not enough bytes to read. Requested {count}, available {self.size - self.offset}",
            )
        data = self.bytes[self.offset : self.offset + count]
        self.offset += count
        return data

    def from_base64(
        self,
        data: str,
        *,
        uri_encoded: bool = False,
        lz_encoded: bool = False,
        case_encoded: bool = False,
    ) -> "ByteBuffer":
        if uri_encoded:
            data = unquote(data)
        if case_encoded:
            head, tail = data[:101], data[101:]
            data = head.swapcase() + tail
        if lz_encoded:
            data = LZString.decompressFromEncodedURIComponent(data)
            if data is None:
                raise ValueError("LZString decompression failed")
        self.bytes += base64.b64decode(data)
        return self

    def to_base64(
        self,
        *,
        uri_encode: bool = False,
        lz_encode: bool = False,
        case_encode: bool = False,
    ) -> str:
        encoded = base64.b64encode(self.bytes)
        encoded = encoded.decode("ascii")
        if lz_encode:
            encoded = LZString.compressToEncodedURIComponent(encoded)
            if encoded is None:
                raise ValueError("LZString compression failed")
        if case_encode:
            head, tail = encoded[:101], encoded[101:]
            encoded = head.swapcase() + tail
        if uri_encode:
            encoded = quote(encoded)
        return encoded

    def read_uint8(self) -> int:
        return struct.unpack(self.endian + "B", self.read_bytes(1))[0]

    def read_int8(self) -> int:
        return struct.unpack(self.endian + "b", self.read_bytes(1))[0]

    def read_uint16(self) -> int:
        return struct.unpack(self.endian + "H", self.read_bytes(2))[0]

    def read_int16(self) -> int:
        return struct.unpack(self.endian + "h", self.read_bytes(2))[0]

    def read_uint32(self) -> int:
        return struct.unpack(self.endian + "I", self.read_bytes(4))[0]

    def read_int32(self) -> int:
        return struct.unpack(self.endian + "i", self.read_bytes(4))[0]

    def read_uint64(self) -> int:
        return struct.unpack(self.endian + "Q", self.read_bytes(8))[0]

    def read_int64(self) -> int:
        return struct.unpack(self.endian + "q", self.read_bytes(8))[0]

    def read_varint32(self) -> int:
        value = 0
        shift = 0
        for _ in range(5):
            byte = self.read_uint8()
            value |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return value
            shift += 7
        raise ValueError("Encoded varint32 is too large")

    def read_varint64(self) -> int:
        value = 0
        shift = 0
        for _ in range(10):
            byte = self.read_uint8()
            value |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return value
            shift += 7
        raise ValueError("Encoded varint64 is too large")

    def read_float32(self) -> float:
        return struct.unpack(self.endian + "f", self.read_bytes(4))[0]

    def read_float64(self) -> float:
        return struct.unpack(self.endian + "d", self.read_bytes(8))[0]

    def read_str(self) -> str:
        length = self.read_uint8()
        return self.read_bytes(length).decode("utf-8")

    def read_utf(self) -> str:
        length = self.read_uint16()
        return self.read_bytes(length).decode("utf-8")

    def read_vstr(self) -> str:
        length = self.read_varint32()
        return self.read_bytes(length).decode("utf-8")

    def write_bytes(self, data: Union[bytearray, bytes]) -> None:
        data_len = len(data)
        if self.offset + data_len > self.size:
            self.bytes.extend(b"\x00" * (self.offset + data_len - self.size))
        self.bytes[self.offset : self.offset + data_len] = data
        self.offset += data_len

    def write_uint8(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "B", value))

    def write_bool(self, value: bool) -> None:
        self.write_uint8(int(value))

    def write_int8(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "b", value))

    def write_uint16(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "H", value))

    def write_int16(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "h", value))

    def write_uint32(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "I", value))

    def write_int32(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "i", value))

    def write_uint64(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "Q", value))

    def write_int64(self, value: int) -> None:
        self.write_bytes(struct.pack(self.endian + "q", value))

    def write_varint32(self, value: int) -> None:
        if value > 0xFFFFFFFF:
            raise ValueError("Value for varint32 encoding is too large")
        value &= 0xFFFFFFFF
        while True:
            byte = value & 0x7F
            value >>= 7
            if value == 0:
                self.write_uint8(byte)
                break
            else:
                self.write_uint8(byte | 0x80)

    def write_varint64(self, value: int) -> None:
        if value > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("Value for varint64 encoding is too large")
        data = bytearray()
        for _ in range(10):
            byte = value & 0x7F
            value >>= 7
            if value == 0:
                data.append(byte)
                break
            data.append(byte | 0x80)
        self.write_bytes(data)

    def write_float32(self, value: float) -> None:
        self.write_bytes(struct.pack(self.endian + "f", value))

    def write_float64(self, value: float) -> None:
        self.write_bytes(struct.pack(self.endian + "d", value))

    def write_str(self, value: str) -> None:
        bs = value.encode("utf-8")
        self.write_uint8(len(bs))
        self.write_bytes(bs)

    def write_utf(self, value: str) -> None:
        bs = value.encode("utf-8")
        self.write_uint16(len(bs))
        self.write_bytes(bs)

    def write_vstr(self, value: str) -> None:
        bs = value.encode("utf-8")
        self.write_varint32(len(bs))
        self.write_bytes(bs)

    def read_bool(self) -> bool:
        return self.read_uint8() == 1
