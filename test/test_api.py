import unittest
import tempfile
import shutil

from fastapi.testclient import TestClient

from s4 import s4_api


class TestAPI(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.s4_path = tempfile.mkdtemp()
        s4_api.db_base_path = self.s4_path
        self.client = TestClient(s4_api)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.s4_path)
