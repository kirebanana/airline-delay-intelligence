import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BUILD = Path(__file__).resolve().parents[1] / "containers/jobs/build.py"


@unittest.skipUnless(
    BUILD.is_file(), "Build-context contract needs source checkout; resource tests run in image"
)
class BuildContextTests(unittest.TestCase):
    def test_context_contains_only_the_explicit_airline_name_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("tempfile.mkdtemp", return_value=directory),
                patch("subprocess.run") as docker,
            ):
                runpy.run_path(str(BUILD), run_name="__main__")
            resources = list((Path(directory) / "src/airline_warehouse").glob("*.json"))
            self.assertEqual([p.name for p in resources], ["airline_names.json"])
            data = json.loads(resources[0].read_text())
            self.assertEqual(data["airlines"]["20368"]["name"], "Allegiant Air")
            docker.assert_called_once()
            self.assertEqual(docker.call_args.args[0][-1], directory)
