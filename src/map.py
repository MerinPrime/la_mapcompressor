from typing import final

from src.types import ArrowType

CHUNK_SIZE = 16


@final
class Arrow:
    def __init__(
        self,
        arrow_type: ArrowType,
        rotation: int,
        flipped: bool,
        global_x: int,
        global_y: int,
    ) -> None:
        self.type = arrow_type
        self.rotation = rotation
        self.flipped = flipped
        self.global_x = global_x
        self.global_y = global_y


@final
class Chunk:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
        self.arrows: dict[tuple[int, int], Arrow] = {}

    def get_arrow(self, x: int, y: int) -> Arrow | None:
        return self.arrows.get((x, y))

    def set_arrow(self, x: int, y: int, arrow: Arrow) -> None:
        self.arrows[(x, y)] = arrow


@final
class GameMap:
    def __init__(self) -> None:
        self.chunks: dict[tuple[int, int], Chunk] = {}

    def get_or_create_chunk(self, x: int, y: int) -> Chunk:
        coords = (x, y)

        if coords not in self.chunks:
            self.chunks[coords] = Chunk(x, y)

        return self.chunks[coords]
