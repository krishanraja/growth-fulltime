"""The protocol copy is Control Center's bundle, byte for byte (integration plan I-11, 2026-11-14).

docs/control-center/ holds Control Center's public-safe protocol bundle: the protocol, both schemas, the example
report and bundle.json, which names each file's sha256 and one bundle_sha256. This test fails when a file was edited
in place or the copy is incomplete. Refresh the copy from Control Center's docs/app/growth/protocol-bundle/ instead of
editing it; capabilities serve protocol_bundle so a run can say whether the copy is current.
"""
import hashlib
import json
import pathlib
import unittest

DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "control-center"


def bundle_hash(version, files):
    text = "version %s\n" % version + "".join("%s %s\n" % (p, files[p]) for p in sorted(files))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ProtocolBundleTest(unittest.TestCase):
    def test_every_file_matches_its_sha256(self):
        bundle = json.loads((DIR / "bundle.json").read_text(encoding="utf-8"))
        self.assertTrue(bundle["files"], "a bundle with no files proves nothing")
        for name, want in bundle["files"].items():
            # Line endings as the bundle has them (LF): a Windows checkout may hand back CRLF.
            got = hashlib.sha256((DIR / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            self.assertEqual(got, want, "%s differs from Control Center's bundle; refresh it, never edit it" % name)

    def test_the_bundle_hash_is_the_documented_recipe(self):
        bundle = json.loads((DIR / "bundle.json").read_text(encoding="utf-8"))
        self.assertEqual(bundle_hash(bundle["version"], bundle["files"]), bundle["bundle_sha256"])
        header = (DIR / "ENGINE-PROTOCOL.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("version %s" % bundle["version"], header)


if __name__ == "__main__":
    unittest.main()
