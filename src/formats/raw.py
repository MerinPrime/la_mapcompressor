from src.map import CHUNK_SIZE, Arrow, GameMap
from src.types import ArrowType


def raw_load(data: bytes) -> GameMap:
    game_map = GameMap()

    if len(data) < 4:
        return game_map

    offset = 0

    version, offset = _read_uint16(data, offset)

    if version != 0:
        raise ValueError(f'Unsupported save version: {version}')

    chunks_count, offset = _read_uint16(data, offset)

    for _ in range(chunks_count):
        chunk_x, offset = _read_chunk_coordinate(data, offset)
        chunk_y, offset = _read_chunk_coordinate(data, offset)

        types_count = data[offset] + 1
        offset += 1

        chunk = game_map.get_or_create_chunk(chunk_x, chunk_y)

        for _ in range(types_count):
            arrow_type_id = data[offset]
            type_count = data[offset + 1] + 1
            offset += 2

            try:
                arrow_type = ArrowType(arrow_type_id)
            except ValueError:
                arrow_type = ArrowType.EMPTY

            for _ in range(type_count):
                position = data[offset]
                rotation_byte = data[offset + 1]
                offset += 2

                local_x = position & 0xF
                local_y = position >> 4

                rotation = rotation_byte & 0x3
                flipped = bool(rotation_byte & 0x4)

                global_x = chunk_x * CHUNK_SIZE + local_x
                global_y = chunk_y * CHUNK_SIZE + local_y

                arrow = Arrow(
                    arrow_type=arrow_type,
                    rotation=rotation,
                    flipped=flipped,
                    global_x=global_x,
                    global_y=global_y,
                )

                chunk.set_arrow(local_x, local_y, arrow)

    return game_map


def raw_save(game_map: GameMap) -> bytes:
    data = bytearray()

    _write_uint16(data, 0)
    _write_uint16(data, len(game_map.chunks))

    for chunk in sorted(
        game_map.chunks.values(),
        key=lambda chunk: (chunk.x, chunk.y),
    ):
        _write_chunk_coordinate(data, chunk.x)
        _write_chunk_coordinate(data, chunk.y)

        arrows_by_type: dict[ArrowType, list[Arrow]] = {}

        for arrow in chunk.arrows.values():
            arrows_by_type.setdefault(arrow.type, []).append(arrow)

        data.append(len(arrows_by_type) - 1)

        for arrow_type in sorted(
            arrows_by_type, key=lambda arrow_type: arrow_type.value
        ):
            arrows = arrows_by_type[arrow_type]

            data.append(arrow_type.value)
            data.append(len(arrows) - 1)

            for arrow in sorted(
                arrows,
                key=lambda arrow: (arrow.global_x, arrow.global_y),
            ):
                local_x = arrow.global_x - chunk.x * CHUNK_SIZE
                local_y = arrow.global_y - chunk.y * CHUNK_SIZE

                if not 0 <= local_x < CHUNK_SIZE:
                    raise ValueError(f'Invalid local X: {local_x}')

                if not 0 <= local_y < CHUNK_SIZE:
                    raise ValueError(f'Invalid local Y: {local_y}')

                position = local_x | (local_y << 4)
                rotation_byte = arrow.rotation | (int(arrow.flipped) << 2)

                data.append(position)
                data.append(rotation_byte)

    return bytes(data)


def _read_uint16(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    if offset + 2 > len(data):
        raise ValueError('Unexpected end of data')

    value = data[offset] | (data[offset + 1] << 8)

    return value, offset + 2


def _write_uint16(
    data: bytearray,
    value: int,
) -> None:
    data.append(value & 0xFF)
    data.append((value >> 8) & 0xFF)


def _read_chunk_coordinate(
    data: bytes,
    offset: int,
) -> tuple[int, int]:
    value, offset = _read_uint16(data, offset)

    if value & 0x8000:
        value = -(value & 0x7FFF)

    return value, offset


def _write_chunk_coordinate(
    data: bytearray,
    value: int,
) -> None:
    if value < 0:
        value = (-value) | 0x8000

    _write_uint16(data, value)
