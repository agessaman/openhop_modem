"""Exercise the configure-time workaround with IDF's real generator."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

FIRMWARE = Path(__file__).resolve().parents[1]
IDF = Path(os.environ.get('IDF_PATH', Path.home() / '.platformio/packages/framework-espidf'))


@unittest.skipUnless(IDF.exists(), 'installed ESP-IDF required')
class EmbedTests(unittest.TestCase):
    def test_generates_exact_idf_assembly_and_fails_for_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cert = tmp / 'https_server.crt'
            cert.write_text('test certificate\n')
            actual, expected = tmp / 'actual.S', tmp / 'expected.S'
            common = ['cmake', f'-DDATA_FILE={cert}', '-DFILE_TYPE=TEXT']
            subprocess.run(common + [f'-DSOURCE_FILE={expected}', '-P', str(IDF / 'tools/cmake/scripts/data_file_embed_asm.cmake')], check=True)
            cmd = common + [f'-DSOURCE_FILE={actual}', f'-DIDF_PATH={IDF}', '-P', str(FIRMWARE / 'tools/idf_embed.cmake')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(actual.read_bytes(), expected.read_bytes())
            cert.unlink()
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
