"""Reviewed prepared-content identity, separate from mutable artifact claims.

This fixed-source contract admits only the source-derived payload independently
reconstructed from the four checksum-pinned NOAA bodies. Corrected sources require
a reviewed registry update, not acceptance of a newly self-signed manifest.
"""

TRUSTED = {
    "contract": "den-ghcnh-aviation-independent-60m-v2",
    "mapping_sha256": "f79b018b0efc142cd6775621597c3c65ba3bfb268a92d472f65152f6c270b8b9",
    "payload_sha256": "720a533904bcf5829cf1071219743b54366f92bcc777f16007f90edba6ca7d76",
    "payload_bytes": 83671259,
    "rows": 120708,
    "weather_id": "b09c9b959da0a56b81638be8855f577af685db8d6849097dc952d8a9a4f6a167",
}


def verify_trusted_weather(manifest):
    if any(manifest.get(key) != value for key, value in TRUSTED.items()):
        raise ValueError("Weather content is not the reviewed source-derived payload")
