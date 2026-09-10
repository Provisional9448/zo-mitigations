import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("package_install", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_preview_install_and_remove_preserves_untracked(self):
        with tempfile.TemporaryDirectory() as scratch:
            destination = Path(scratch) / "installed"
            plan = installer.install(destination)
            self.assertFalse(destination.exists())
            self.assertFalse(plan["applied"])
            installer.install(destination, True)
            self.assertTrue((destination / "zo_mitigations" / "__main__.py").is_file())
            self.assertTrue((destination / "tests" / "test_install.py").is_file())
            (destination / "runtime").mkdir()
            (destination / "runtime" / "checkpoint.json").write_text("{}")
            (destination / "keep-empty").mkdir()
            installer.uninstall(destination)
            self.assertTrue((destination / "README.md").exists())
            installer.uninstall(destination, True)
            self.assertTrue((destination / "runtime" / "checkpoint.json").is_file())
            self.assertTrue((destination / "keep-empty").is_dir())
            self.assertFalse((destination / "README.md").exists())

    def test_existing_target_and_edited_content_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            destination = Path(scratch) / "installed"
            installer.install(destination, True)
            with self.assertRaises(ValueError):
                installer.install(destination, True)
            (destination / "README.md").write_text("local edits")
            with self.assertRaises(ValueError):
                installer.uninstall(destination, True)
            self.assertTrue((destination / "install.py").exists())

    def test_symlink_and_hidden_content_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch) / "source"
            root.mkdir()
            private = Path(scratch) / "outside"
            private.mkdir()
            (private / "private.md").write_text("fixture")
            (root / "docs").symlink_to(private, target_is_directory=True)
            with patch.object(installer, "ROOT", root), patch.object(installer, "CONTENT", ("docs",)):
                with self.assertRaises(ValueError):
                    installer.sources()
                (root / "docs").unlink()
                (root / "docs").mkdir()
                (root / "docs" / ".env").write_text("fixture")
                with self.assertRaises(ValueError):
                    installer.sources()


if __name__ == "__main__":
    unittest.main()
