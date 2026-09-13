import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import liveries


class TextureDimensionsTests(unittest.TestCase):
    def test_runtime_textures_are_capped_at_1024(self):
        for original, expected in (
            ((4096, 4096), (1024, 1024)),
            ((2048, 2048), (1024, 1024)),
            ((1024, 1024), (1024, 1024)),
            ((2048, 256), (1024, 128)),
            ((256, 2048), (128, 1024)),
        ):
            with self.subTest(original=original):
                self.assertEqual(liveries.texture_dimensions(original), expected)

    def test_small_textures_are_not_upscaled(self):
        for size in ((256, 256), (128, 128), (4, 4), (256, 4)):
            with self.subTest(size=size):
                self.assertEqual(liveries.texture_dimensions(size), size)

    def test_shared_colour_and_light_reuse_one_small_copy(self):
        with tempfile.TemporaryDirectory(prefix="kc390-shared-1k-") as temporary:
            root = Path(temporary)
            (root / "Textures").mkdir()
            destination = root / "livery"
            destination.mkdir()
            source = root / "Textures" / "form.dds"
            Image.new("RGBA", (2048, 256), (90, 130, 80, 155)).save(source)
            original_hash = liveries.digest(source)
            bindings = [
                {"material": "formation_light", "slot": slot, "texture": "form", "shared": True}
                for slot in (0, "SELF_ILLUMINATION")
            ]
            manifest = {"parts": {}}

            def convert(png, folder, role, converter):
                self.assertEqual(role, "colour")
                dds = folder / (png.stem + ".dds")
                with Image.open(png) as image:
                    self.assertEqual(image.getchannel("A").getextrema(), (155, 155))
                    image.resize(liveries.texture_dimensions(image.size)).save(dds)
                return dds

            with patch.object(liveries, "ROOT", root), patch.object(liveries, "export_dds", side_effect=convert) as exporter:
                result = liveries.limit_shared_textures(root, "fab", destination, bindings, manifest)
            exporter.assert_called_once()
            self.assertTrue(all(not binding["shared"] for binding in result))
            self.assertEqual([binding["slot"] for binding in result], [0, "SELF_ILLUMINATION"])
            self.assertEqual(result[0]["texture"], result[1]["texture"])
            self.assertEqual(liveries.digest(source), original_hash)
            self.assertEqual((manifest["shared_overrides"]["form"]["width"], manifest["shared_overrides"]["form"]["height"]), (1024, 128))


class LiveryProtectionTests(unittest.TestCase):
    def test_rebuild_preserves_externally_edited_dds(self):
        with tempfile.TemporaryDirectory(prefix="kc390-livery-test-") as temporary:
            root = Path(temporary)
            directory = root / "Liveries" / "KC-390" / liveries.LIVERY_NAMES["fab"]
            directory.mkdir(parents=True)
            texture = directory / "edited.dds"
            original = b"Externally edited texture: must not be overwritten"
            texture.write_bytes(original)
            manifest = {"parts": {"test": {"maps": {"colour": {"texture": "edited", "sha256": "0" * 64}}}}}
            (directory / "build.json").write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(liveries, "ROOT", root), patch.object(liveries, "verify_originals"):
                with self.assertRaisesRegex(ValueError, "external edits"):
                    liveries.build(root, None)
            self.assertEqual(texture.read_bytes(), original)
            self.assertFalse((root / "Liveries" / "KC-390" / liveries.LIVERY_NAMES["embraer"]).exists())

    def test_rebuild_refuses_unowned_livery_directory(self):
        with tempfile.TemporaryDirectory(prefix="kc390-livery-test-") as temporary:
            root = Path(temporary)
            directory = root / "Liveries" / "KC-390" / liveries.LIVERY_NAMES["fab"]
            directory.mkdir(parents=True)
            with patch.object(liveries, "ROOT", root), patch.object(liveries, "verify_originals"):
                with self.assertRaisesRegex(ValueError, "unowned livery"):
                    liveries.build(root, None)
            self.assertEqual(list(directory.iterdir()), [])

    @unittest.skipUnless(shutil.which("lua"), "Lua is required for the descriptor round-trip test")
    def test_self_illumination_remains_symbolic(self):
        source = liveries.ROOT / "Liveries" / "KC-390" / "FAB Standard" / "description.lua"
        bindings = liveries.load_livery(source)
        self.assertEqual(sum(binding["slot"] == "SELF_ILLUMINATION" for binding in bindings), 2)
        with tempfile.TemporaryDirectory(prefix="kc390-livery-test-") as temporary:
            descriptor = Path(temporary) / "description.lua"
            liveries.write_livery(descriptor, bindings, "Round trip")
            self.assertEqual(liveries.load_livery(descriptor), bindings)


if __name__ == "__main__":
    unittest.main()