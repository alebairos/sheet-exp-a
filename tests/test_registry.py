import os
import tempfile
import unittest

import src.functions as functions
from src.functions import register, registry


class RegistryTest(unittest.TestCase):
    def test_register_decorator_returns_fn(self):
        @register("zz_unit_probe")
        def probe():
            return 7
        self.assertEqual(probe(), 7)
        r = registry()
        self.assertIn("ZZ_UNIT_PROBE", r)
        self.assertEqual(r["ZZ_UNIT_PROBE"](), 7)

    def test_registry_is_a_copy(self):
        r = registry()
        r["NOPE"] = None
        self.assertNotIn("NOPE", registry())

    def test_group_packages_exist(self):
        base = os.path.dirname(functions.__file__)
        for g in ("math", "logic_text", "lookup"):
            self.assertTrue(os.path.isfile(os.path.join(base, g, "__init__.py")), g)


if __name__ == "__main__":
    unittest.main()
