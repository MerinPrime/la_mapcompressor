from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.relations import get_relations, get_target

if TYPE_CHECKING:
    from src.map import Arrow, GameMap


@dataclass(eq=False)
class GraphNode:
    arrow: 'Arrow'
    connections: list['GraphNode']
    back_connections: list['GraphNode']


class Graph:
    def __init__(self, map: 'GameMap') -> None:
        self.nodes: dict[tuple[int, int], GraphNode] = {}
        self._build(map)

    def _build(self, map: 'GameMap') -> None:
        for chunk in map.chunks.values():
            for arrow in chunk.arrows.values():
                self.nodes[(arrow.global_x, arrow.global_y)] = GraphNode(
                    arrow=arrow,
                    connections=[],
                    back_connections=[],
                )

        for (x, y), node in self.nodes.items():
            for relation in get_relations(node.arrow.type):
                target_x, target_y = get_target(
                    x,
                    y,
                    node.arrow.rotation,
                    node.arrow.flipped,
                    relation,
                )

                target = self.nodes.get((target_x, target_y))

                if target is None:
                    continue

                node.connections.append(target)
                target.back_connections.append(node)
