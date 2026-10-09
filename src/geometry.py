ROTATION_MATRICES = [
    {'fx': 0, 'fy': 1, 'sx': 1, 'sy': 0},
    {'fx': -1, 'fy': 0, 'sx': 0, 'sy': 1},
    {'fx': 0, 'fy': -1, 'sx': -1, 'sy': 0},
    {'fx': 1, 'fy': 0, 'sx': 0, 'sy': -1},
]


def get_relative_position(
    x: int,
    y: int,
    rotation: int,
    flipped: bool,
    forward: int = -1,
    sideways: int = 0,
) -> tuple[int, int]:
    matrix = ROTATION_MATRICES[rotation]

    if flipped:
        sideways = -sideways

    return (
        x + forward * matrix['fx'] + sideways * matrix['sx'],
        y + forward * matrix['fy'] + sideways * matrix['sy'],
    )
