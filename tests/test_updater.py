import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location("updater", Path(__file__).resolve().parents[1] / "roles/mirror/files/updater.py")
u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)

class Checks(unittest.TestCase):
    def test_dns_disabled_and_proxy_encoding(self):
        with patch.object(u, "api") as api:
            u.publish_dns({"dns": {"enabled": False}})
            u.check_dns({"dns": {"enabled": False}})
            api.assert_not_called()
        env, _ = u.proxy_environment({"proxy": {"host": "proxy.example.com:443", "login": "a/b", "password": "x@y"}})
        self.assertEqual(env["https_proxy"], "https://a%2Fb:x%40y@proxy.example.com:443")

    def test_dns_payload_and_verification(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "dns.txt").write_text("1.4.6:63:28171\n")
            c = {"webroot": t, "dns": {"enabled": True, "zone_id": "zone", "record_name": "mirror.example.com."}}
            with patch.object(u, "api", side_effect=[{"access_token":"TOKEN"},{"done": True}]) as api:
                u.publish_dns(c)
                payload = api.call_args.args[2]
                self.assertEqual(payload["replacements"][0]["data"], ['"1.4.6:63:28171"'])
            with patch.object(u, "api", side_effect=[{"access_token":"TOKEN"},{"data":['"1.4.6:63:28171"']}]):
                u.check_dns(c)
            Path(t, "dns.txt").write_text('bad"value')
            with self.assertRaises(ValueError):u.advertisement(c)

    def test_failed_update_never_publishes(self):
        with patch.object(u.subprocess, "run", return_value=u.subprocess.CompletedProcess([],1,"failed")), patch.object(u,"publish_dns") as publish:
            with self.assertRaises(RuntimeError):u.update({"webroot":"/data"})
            publish.assert_not_called()
