"""Resource limits for remote downloads and decompression.

The byte budgets are deliberately generous: real-world XMLTV guides and Xtream
catalogues routinely reach hundreds of MiB. They exist to stop a hostile or broken
source from exhausting memory/disk or holding a worker forever, not to police
normal providers.
"""

MIB = 1024 * 1024
GIB = 1024 * MIB

MAX_PLAYLIST_DOWNLOAD_BYTES = 200 * MIB
MAX_EPG_DOWNLOAD_BYTES = 500 * MIB
MAX_XTREAM_RESPONSE_BYTES = 200 * MIB
MAX_EPG_DECOMPRESSED_BYTES = 1 * GIB

DOWNLOAD_CHUNK_BYTES = 64 * 1024

# Total wall-clock budget per download. Best-effort: checked between reads, so a server
# trickling data can overrun it (each socket read is still bounded by the request timeout).
PLAYLIST_DOWNLOAD_DEADLINE_SECONDS = 300
EPG_DOWNLOAD_DEADLINE_SECONDS = 900
XTREAM_DOWNLOAD_DEADLINE_SECONDS = 300
