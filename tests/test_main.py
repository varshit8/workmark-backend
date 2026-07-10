import importlib
import os
import sys
import unittest
from unittest.mock import patch


class MainImportTests(unittest.TestCase):
    def test_import_succeeds_without_required_env_vars(self):
        sys.modules.pop("main", None)

        with patch.dict(os.environ, {}, clear=True):
            with patch("dotenv.load_dotenv", return_value=False):
                module = importlib.import_module("main")

        self.assertTrue(hasattr(module, "app"))


if __name__ == "__main__":
    unittest.main()
