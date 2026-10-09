from typing import final


@final
class ByteBuffer:
    def __init__(self, data: bytes | bytearray = b''):
        self.bytes = bytearray(data)
        self.offset = 0

    @property
    def size(self) -> int:
        return len(self.bytes)

    def write_uint8(self, value: int) -> None:
        self.bytes.append(value)

    def write_uint16(self, value: int) -> None:
        self.bytes.extend(value.to_bytes(2, 'little'))

    def write_uint32(self, value: int) -> None:
        self.bytes.extend(value.to_bytes(4, 'little'))

    def read_uint8(self) -> int:
        value = self.bytes[self.offset]
        self.offset += 1
        return value

    def read_uint16(self) -> int:
        value = int.from_bytes(
            self.bytes[self.offset : self.offset + 2],
            'little',
        )
        self.offset += 2
        return value

    def read_uint32(self) -> int:
        value = int.from_bytes(
            self.bytes[self.offset : self.offset + 4],
            'little',
        )
        self.offset += 4
        return value

    def write_varint32(self, value: int) -> None:
        while value >= 0x80:
            self.bytes.append((value & 0x7F) | 0x80)
            value >>= 7

        self.bytes.append(value)

    def read_varint32(self) -> int:
        value = 0
        shift = 0

        while True:
            byte = self.read_uint8()
            value |= (byte & 0x7F) << shift

            if not byte & 0x80:
                return value

            shift += 7


def zigzag_encode(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)
