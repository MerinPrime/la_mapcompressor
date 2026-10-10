import base64
import lzma
import sys
import zlib
from pathlib import Path

from src.formats.graphv1 import graphv1_compress, graphv1_decompress
from src.formats.graphv2 import graphv2_compress, graphv2_decompress
from src.formats.raw import raw_load, raw_save
from src.map import GameMap

sys.setrecursionlimit(100000)


def zlib_compress(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def lzma_compress(data: bytes) -> bytes:
    f = [
        {
            'id': lzma.FILTER_LZMA2,
            'preset': 9 | lzma.PRESET_EXTREME,
            'lc': 3,
            'lp': 0,
            'pb': 2,
        }
    ]
    return lzma.compress(data, format=lzma.FORMAT_RAW, filters=f)


def handle_map(game_map: GameMap):
    raw = raw_save(game_map)

    formats = [
        ('raw', raw_save, raw_load),
        ('graphv2', graphv2_compress, graphv2_decompress),
        ('graphv1', graphv1_compress, graphv1_decompress),
    ]

    print('VALIDATION')
    encoded_formats: list[tuple[str, bytes]] = []
    for format_name, format_save, format_load in formats:
        print(f'{format_name}: ', end='')

        encoded = format_save(game_map)
        encoded_restored = raw_save(format_load(encoded))

        assert raw == encoded_restored

        encoded_formats.append((format_name, encoded))

        print('OK')

    print('\nRAW')
    prev_len = len(encoded_formats[0][1])
    for format_name, encoded in encoded_formats:
        print(f'{format_name}: {len(encoded):,} B ({len(encoded) / prev_len:.2%})')
        prev_len = len(encoded)

    print('\nZLIB compression')
    prev_len = len(zlib.compress(encoded_formats[0][1]))
    for format_name, encoded in encoded_formats:
        compressed = zlib_compress(encoded)

        print(
            f'{format_name}: '
            f'{len(compressed):,} B '
            f'({len(compressed) / prev_len:.2%}) '
            f'({len(compressed) / len(encoded):.2%})'
        )
        prev_len = len(compressed)

    print('\nLZMA compression')
    prev_len = len(lzma.compress(encoded_formats[0][1]))
    for format_name, encoded in encoded_formats:
        compressed = lzma_compress(encoded)

        print(
            f'{format_name}: '
            f'{len(compressed):,} B '
            f'({len(compressed) / prev_len:.2%}) '
            f'({len(compressed) / len(encoded):.2%})'
        )
        prev_len = len(compressed)


def main() -> None:
    for path in Path('./maps').glob('*'):
        if path.is_file():
            text = path.read_text(encoding='utf-8')
            print(f'--- {path.name} ---')
            raw = base64.b64decode(text)
            game_map = raw_load(raw)
            handle_map(game_map)


if __name__ == '__main__':
    main()
