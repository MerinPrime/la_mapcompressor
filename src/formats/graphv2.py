from __future__ import annotations

from src.buffer import zigzag_decode, zigzag_encode
from src.graph import Graph, GraphNode
from src.map import Arrow, GameMap
from src.relations import get_relations, get_target
from src.types import ArrowType

_MAGIC = 0xD2
_TYPE_BITS = max(1, max(int(arrow_type.value) for arrow_type in ArrowType).bit_length())
_MAX_U32 = 0xFFFFFFFF


class _BitWriter:
    """LSB-first bit writer. Values can cross byte boundaries."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.bit_offset = 0

    def write_bits(self, value: int, count: int) -> None:
        if count < 0:
            raise ValueError('Bit count cannot be negative')
        if count == 0:
            if value != 0:
                raise ValueError(f'Value {value} does not fit in 0 bits')
            return
        if value < 0 or value >= (1 << count):
            raise ValueError(f'Value {value} does not fit in {count} bits')

        for bit_index in range(count):
            if self.bit_offset % 8 == 0:
                self.data.append(0)

            bit = (value >> bit_index) & 1
            self.data[-1] |= bit << (self.bit_offset % 8)
            self.bit_offset += 1

    def write_varuint32(self, value: int) -> None:
        if not 0 <= value <= _MAX_U32:
            raise ValueError(f'Value outside uint32 range: {value}')

        while value >= 0x80:
            self.write_bits((value & 0x7F) | 0x80, 8)
            value >>= 7

        self.write_bits(value, 8)

    def to_bytes(self) -> bytes:
        return bytes(self.data)


class _BitReader:
    """LSB-first bit reader matching _BitWriter."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.bit_offset = 0

    @property
    def bits_remaining(self) -> int:
        return len(self.data) * 8 - self.bit_offset

    def read_bits(self, count: int) -> int:
        if count < 0:
            raise ValueError('Bit count cannot be negative')
        if count > self.bits_remaining:
            raise ValueError('Unexpected end of GraphV2 data')

        value = 0
        for bit_index in range(count):
            byte_index = self.bit_offset // 8
            bit_in_byte = self.bit_offset % 8
            bit = (self.data[byte_index] >> bit_in_byte) & 1
            value |= bit << bit_index
            self.bit_offset += 1

        return value

    def read_varuint32(self) -> int:
        value = 0
        shift = 0

        while shift <= 28:
            byte = self.read_bits(8)
            value |= (byte & 0x7F) << shift

            if not byte & 0x80:
                if value > _MAX_U32:
                    raise ValueError('GraphV2 varint exceeds uint32')
                return value

            shift += 7

        raise ValueError('Invalid GraphV2 varint')


def get_roots(graph: Graph) -> list[GraphNode]:
    unvisited = set(graph.nodes.values())
    roots: list[GraphNode] = []

    def traverse(node: GraphNode) -> None:
        if node not in unvisited:
            return

        unvisited.remove(node)
        for connection in node.connections:
            traverse(connection)

    main_roots = sorted(
        (node for node in graph.nodes.values() if not node.back_connections),
        key=lambda node: (node.arrow.global_x, node.arrow.global_y),
    )

    for root in main_roots:
        if root in unvisited:
            traverse(root)
            roots.append(root)

    while unvisited:
        root = min(
            unvisited,
            key=lambda node: (node.arrow.global_x, node.arrow.global_y),
        )
        traverse(root)
        roots.append(root)

    roots.sort(key=lambda node: (node.arrow.global_x, node.arrow.global_y))
    return roots


def graphv2_compress(game_map: GameMap) -> bytes:
    """Serialize a map with node fields packed into a continuous bitstream."""
    graph = Graph(game_map)
    roots = get_roots(graph)

    writer = _BitWriter()
    writer.write_bits(_MAGIC, 8)
    writer.write_varuint32(len(roots))

    last_x = 0
    last_y = 0
    visited: set[GraphNode] = set()

    for root in roots:
        x = root.arrow.global_x
        y = root.arrow.global_y

        writer.write_varuint32(zigzag_encode(x - last_x))
        writer.write_varuint32(zigzag_encode(y - last_y))
        _write_node(writer, root, visited)

        last_x = x
        last_y = y

    return writer.to_bytes()


def _write_node(
    writer: _BitWriter,
    node: GraphNode,
    visited: set[GraphNode],
) -> None:
    visited.add(node)
    arrow = node.arrow
    relations = get_relations(arrow.type)

    children: list[GraphNode] = []
    relations_mask = 0
    connections_by_position = {
        (connection.arrow.global_x, connection.arrow.global_y): connection
        for connection in node.connections
    }

    for index, relation in enumerate(relations):
        child_x, child_y = get_target(
            arrow.global_x,
            arrow.global_y,
            arrow.rotation,
            arrow.flipped,
            relation,
        )
        child = connections_by_position.get((child_x, child_y))

        if child is None or child in visited:
            continue

        visited.add(child)
        children.append(child)
        relations_mask |= 1 << index

    type_value = int(arrow.type.value)
    if type_value >= (1 << _TYPE_BITS):
        raise ValueError(f'Arrow type does not fit in {_TYPE_BITS} bits')

    writer.write_bits(type_value, _TYPE_BITS)
    writer.write_bits(arrow.rotation, 2)
    writer.write_bits(int(arrow.flipped), 1)
    writer.write_bits(relations_mask, len(relations))

    for child in children:
        _write_node(writer, child, visited)


def graphv2_decompress(data: bytes) -> GameMap:
    reader = _BitReader(data)
    game_map = GameMap()

    if not data:
        raise ValueError('Empty GraphV2 data')

    magic = reader.read_bits(8)
    if magic != _MAGIC:
        raise ValueError(f'Invalid GraphV2 magic: 0x{magic:02X}')

    roots_count = reader.read_varuint32()
    last_x = 0
    last_y = 0

    for _ in range(roots_count):
        x = last_x + zigzag_decode(reader.read_varuint32())
        y = last_y + zigzag_decode(reader.read_varuint32())
        _read_node(reader, game_map, x, y)
        last_x = x
        last_y = y

    # The unused bits of the final byte must be zero padding.
    while reader.bits_remaining:
        if reader.read_bits(1):
            raise ValueError('Non-zero trailing padding in GraphV2 data')

    return game_map


def _read_node(
    reader: _BitReader,
    game_map: GameMap,
    x: int,
    y: int,
) -> None:
    type_value = reader.read_bits(_TYPE_BITS)

    try:
        arrow_type = ArrowType(type_value)
    except ValueError as error:
        raise ValueError(f'Unknown ArrowType value: {type_value}') from error

    rotation = reader.read_bits(2)
    flipped = bool(reader.read_bits(1))
    relations = get_relations(arrow_type)
    relations_mask = reader.read_bits(len(relations))

    arrow = Arrow(
        arrow_type=arrow_type,
        rotation=rotation,
        flipped=flipped,
        global_x=x,
        global_y=y,
    )

    chunk_x, local_x = divmod(x, 16)
    chunk_y, local_y = divmod(y, 16)
    chunk = game_map.get_or_create_chunk(chunk_x, chunk_y)
    chunk.set_arrow(local_x, local_y, arrow)

    for index, relation in enumerate(relations):
        if not relations_mask & (1 << index):
            continue

        child_x, child_y = get_target(x, y, rotation, flipped, relation)
        _read_node(reader, game_map, child_x, child_y)
