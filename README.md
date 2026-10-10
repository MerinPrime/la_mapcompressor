Map serialization algorithm for improved compression

Tests:

--- computer ---
RAW
raw: 451,420 B (100.00%)
graphv2: 264,743 B (58.65%)
graphv1: 439,302 B (165.94%)
graphv4: 227,564 B (51.80%)

ZLIB compression
raw: 133,389 B (99.94%) (29.55%)
graphv2: 64,769 B (48.56%) (24.46%)
graphv1: 53,745 B (82.98%) (12.23%)
graphv4: 47,312 B (88.03%) (20.79%)

LZMA compression
raw: 95,159 B (99.78%) (21.08%)
graphv2: 57,195 B (60.10%) (21.60%)
graphv1: 44,114 B (77.13%) (10.04%)
graphv4: 41,790 B (94.73%) (18.36%)

--- 32kb ---
RAW
raw: 725,917 B (100.00%)
graphv2: 399,799 B (55.08%)
graphv1: 702,382 B (175.68%)
graphv4: 352,134 B (50.13%)

ZLIB compression
raw: 47,442 B (99.00%) (6.54%)
graphv2: 9,233 B (19.46%) (2.31%)
graphv1: 6,397 B (69.28%) (0.91%)
graphv4: 4,598 B (71.88%) (1.31%)

LZMA compression
raw: 13,332 B (99.20%) (1.84%)
graphv2: 6,104 B (45.78%) (1.53%)
graphv1: 3,059 B (50.11%) (0.44%)
graphv4: 2,901 B (94.83%) (0.82%)
