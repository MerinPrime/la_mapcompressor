from src.buffer import ByteBuffer, zigzag_decode, zigzag_encode
from src.graph import Graph, GraphNode
from src.map import Arrow, GameMap
from src.relations import get_relations, get_target
from src.types import ArrowType


def get_roots(graph: 'Graph') -> list[GraphNode]:
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
        key=lambda node: (
            node.arrow.global_x,
            node.arrow.global_y,
        ),
    )

    for root in main_roots:
        if root not in unvisited:
            continue

        traverse(root)
        roots.append(root)

    while unvisited:
        root = min(
            unvisited,
            key=lambda node: (
                node.arrow.global_x,
                node.arrow.global_y,
            ),
        )

        traverse(root)
        roots.append(root)

    return roots


def graphv1_compress(game_map: GameMap) -> bytes:
    graph = Graph(game_map)

    if not graph.nodes:
        return b''

    buffer = ByteBuffer()
    visited: set[GraphNode] = set()

    last_x = 0
    last_y = 0

    for root in get_roots(graph):
        x = root.arrow.global_x
        y = root.arrow.global_y

        buffer.write_varint32(zigzag_encode(x - last_x))
        buffer.write_varint32(zigzag_encode(y - last_y))

        _write_node(buffer, root, visited)

        last_x = x
        last_y = y

    return bytes(buffer.bytes)


def _write_node(
    buffer: ByteBuffer,
    node: GraphNode,
    visited: set[GraphNode],
) -> None:
    visited.add(node)

    relations_mask = 0
    children: list[GraphNode] = []

    arrow = node.arrow

    for index, relation in enumerate(get_relations(arrow.type)):
        child_x, child_y = get_target(
            arrow.global_x,
            arrow.global_y,
            arrow.rotation,
            arrow.flipped,
            relation,
        )

        child = next(
            (
                connection
                for connection in node.connections
                if (
                    connection.arrow.global_x,
                    connection.arrow.global_y,
                )
                == (child_x, child_y)
            ),
            None,
        )

        if child is None or child in visited:
            continue

        visited.add(child)
        children.append(child)
        relations_mask |= 1 << index

    metadata = int(arrow.flipped) | (arrow.rotation << 1) | (relations_mask << 3)

    buffer.write_uint8(arrow.type.value)
    buffer.write_uint8(metadata)

    for child in children:
        _write_node(buffer, child, visited)


def graphv1_decompress(data: bytes) -> GameMap:
    buffer = ByteBuffer(data)
    game_map = GameMap()

    last_x = 0
    last_y = 0

    while buffer.offset < buffer.size:
        x = last_x + zigzag_decode(buffer.read_varint32())
        y = last_y + zigzag_decode(buffer.read_varint32())

        _read_node(
            buffer,
            game_map,
            x,
            y,
        )

        last_x = x
        last_y = y

    return game_map


def _read_node(
    buffer: ByteBuffer,
    game_map: GameMap,
    x: int,
    y: int,
) -> None:
    arrow_type = ArrowType(buffer.read_uint8())
    metadata = buffer.read_uint8()

    rotation = (metadata >> 1) & 0x3
    flipped = bool(metadata & 1)
    relations_mask = metadata >> 3

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

    for index, relation in enumerate(get_relations(arrow_type)):
        if not relations_mask & (1 << index):
            continue

        child_x, child_y = get_target(
            x,
            y,
            rotation,
            flipped,
            relation,
        )

        _read_node(
            buffer,
            game_map,
            child_x,
            child_y,
        )
