import unittest


class ServerSmokeTests(unittest.TestCase):
    """Guards against SDK majors that rename the server API.

    mcp 2.x removed ``mcp.server.fastmcp`` (renamed to ``MCPServer``); without
    this import check, CI stays green while the server is unusable.
    """

    def test_server_imports(self):
        from tecnocasa_mcp import server

        self.assertIsNotNone(server.mcp)
        self.assertIsNotNone(server.client)

    def test_version_is_semver(self):
        from tecnocasa_mcp import __version__

        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))
