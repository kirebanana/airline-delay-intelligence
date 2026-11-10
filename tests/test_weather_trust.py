import hashlib
import json
import unittest

from airline_warehouse.weather import validate_frozen_weather, validate_v2_records
from airline_warehouse.weather_trust import TRUSTED, verify_trusted_weather


class TrustedContentTests(unittest.TestCase):
    def test_reviewed_identity_is_accepted(self):
        verify_trusted_weather(dict(TRUSTED))

    def test_coordinated_self_signed_changes_are_rejected(self):
        forged = dict(TRUSTED)
        forged["payload_sha256"] = hashlib.sha256(b"fabricated raw and value\n").hexdigest()
        forged["weather_id"] = hashlib.sha256(
            json.dumps(forged, sort_keys=True).encode()
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "reviewed source-derived"):
            verify_trusted_weather(forged)
        with self.assertRaisesRegex(ValueError, "reviewed source-derived"):
            validate_v2_records(forged, [])
        with self.assertRaisesRegex(ValueError, "reviewed source-derived"):
            validate_frozen_weather(None, "RELEASE_" + "A" * 24, forged)

    def test_preserved_records_must_equal_reviewed_payload_not_just_claim_it(self):
        with self.assertRaisesRegex(ValueError, "trusted source-derived content"):
            validate_v2_records(dict(TRUSTED), ['{"raw":"17.8","value":17.8}'])
