from collections import Counter
from itertools import pairwise

from src.buffer import ByteBuffer, zigzag_decode, zigzag_encode
from src.graph import Graph, GraphNode
from src.map import Arrow, GameMap
from src.relations import get_relations, get_target
from src.types import ArrowType

CHUNK = 16
MAX_MASK = 0x1F
ESCAPE = 255
TWO_BYTE_RANKS = 128

Symbol = tuple[int, int]


def _position(node: GraphNode) -> tuple[int, int]:
    return node.arrow.global_x, node.arrow.global_y


def get_roots(graph: Graph) -> list[GraphNode]:
    unvisited = set(graph.nodes.values())
    roots: list[GraphNode] = []

    def mark(start: GraphNode) -> None:
        stack = [start]

        while stack:
            node = stack.pop()

            if node not in unvisited:
                continue

            unvisited.remove(node)
            stack.extend(node.connections)

    main_roots = sorted(
        (node for node in graph.nodes.values() if not node.back_connections),
        key=_position,
    )
    fallback = sorted(graph.nodes.values(), key=_position)

    for root in (*main_roots, *fallback):
        if root in unvisited:
            mark(root)
            roots.append(root)

    return roots


def _take_children(
    node: GraphNode,
    visited: set[GraphNode],
) -> tuple[int, list[GraphNode]]:
    arrow = node.arrow
    by_position = {_position(connection): connection for connection in node.connections}

    mask = 0
    children: list[GraphNode] = []

    for index, relation in enumerate(get_relations(arrow.type)):
        target = get_target(
            arrow.global_x,
            arrow.global_y,
            arrow.rotation,
            arrow.flipped,
            relation,
        )
        child = by_position.get(target)

        if child is None or child in visited:
            continue

        visited.add(child)
        children.append(child)
        mask |= 1 << index

    if mask > MAX_MASK:
        raise ValueError(f'Relations mask does not fit 5 bits: {mask}')

    return mask, children


def _collect_symbols(
    root: GraphNode,
    visited: set[GraphNode],
    symbols: list[Symbol],
) -> None:
    visited.add(root)
    stack = [root]

    while stack:
        node = stack.pop()
        mask, children = _take_children(node, visited)
        arrow = node.arrow

        meta = int(arrow.flipped) | (arrow.rotation << 1) | (mask << 3)
        symbols.append((arrow.type.value, meta))

        stack.extend(reversed(children))


def _write_rank(buffer: ByteBuffer, rank: int) -> None:
    if rank < ESCAPE:
        buffer.write_uint8(rank)
    else:
        buffer.write_uint8(ESCAPE)
        buffer.write_varint32(rank - ESCAPE)


def _read_rank(buffer: ByteBuffer) -> int:
    rank = buffer.read_uint8()

    if rank == ESCAPE:
        rank += buffer.read_varint32()

    return rank


def _build_palette(symbols: list[Symbol]) -> list[Symbol]:
    frequency = Counter(symbols)
    by_frequency = sorted(frequency, key=lambda symbol: (-frequency[symbol], symbol))
    bounds = (0, ESCAPE, ESCAPE + TWO_BYTE_RANKS, len(by_frequency))

    palette: list[Symbol] = []

    for start, stop in pairwise(bounds):
        palette.extend(sorted(by_frequency[start:stop]))

    return palette


def graphv4_compress(game_map: GameMap) -> bytes:
    graph = Graph(game_map)

    if not graph.nodes:
        return b''

    roots = get_roots(graph)

    dx = ByteBuffer()
    dy = ByteBuffer()
    symbols: list[Symbol] = []
    visited: set[GraphNode] = set()

    last_x = 0
    last_y = 0

    for root in roots:
        x, y = _position(root)

        dx.write_varint32(zigzag_encode(x - last_x))
        dy.write_varint32(zigzag_encode(y - last_y))

        last_x = x
        last_y = y

        _collect_symbols(root, visited, symbols)

    palette = _build_palette(symbols)
    rank_of = {symbol: rank for rank, symbol in enumerate(palette)}

    head = ByteBuffer()
    head.write_varint32(len(roots))
    head.write_varint32(len(palette))

    body = ByteBuffer()

    for symbol in symbols:
        _write_rank(body, rank_of[symbol])

    return b''.join(
        (
            bytes(head.bytes),
            bytes(dx.bytes),
            bytes(dy.bytes),
            bytes(type_id for type_id, _ in palette),
            bytes(meta for _, meta in palette),
            bytes(body.bytes),
        )
    )


def _read_deltas(buffer: ByteBuffer, count: int) -> list[int]:
    values: list[int] = []
    value = 0

    for _ in range(count):
        value += zigzag_decode(buffer.read_varint32())
        values.append(value)

    return values


def _read_tree(
    game_map: GameMap,
    x: int,
    y: int,
    buffer: ByteBuffer,
    table_types: list[int],
    table_meta: list[int],
) -> None:
    stack = [(x, y)]

    while stack:
        cx, cy = stack.pop()

        rank = _read_rank(buffer)

        if rank >= len(table_types):
            raise ValueError(f'Invalid palette index: {rank}')

        arrow_type = ArrowType(table_types[rank])
        meta = table_meta[rank]

        flipped = bool(meta & 1)
        rotation = (meta >> 1) & 3
        mask = meta >> 3

        chunk_x, local_x = divmod(cx, CHUNK)
        chunk_y, local_y = divmod(cy, CHUNK)

        game_map.get_or_create_chunk(chunk_x, chunk_y).set_arrow(
            local_x,
            local_y,
            Arrow(arrow_type, rotation, flipped, cx, cy),
        )

        children = [
            get_target(cx, cy, rotation, flipped, relation)
            for index, relation in enumerate(get_relations(arrow_type))
            if mask >> index & 1
        ]

        stack.extend(reversed(children))


def graphv4_decompress(data: bytes) -> GameMap:
    game_map = GameMap()

    if not data:
        return game_map

    buffer = ByteBuffer(data)

    roots_count = buffer.read_varint32()
    palette_size = buffer.read_varint32()

    xs = _read_deltas(buffer, roots_count)
    ys = _read_deltas(buffer, roots_count)

    table_types = [buffer.read_uint8() for _ in range(palette_size)]
    table_meta = [buffer.read_uint8() for _ in range(palette_size)]

    for x, y in zip(xs, ys, strict=True):
        _read_tree(game_map, x, y, buffer, table_types, table_meta)

    return game_map
