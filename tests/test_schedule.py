import importlib.util,tempfile,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent.parent;spec=importlib.util.spec_from_file_location("schedule",ROOT/"engine"/"improvement_schedule.py");schedule=importlib.util.module_from_spec(spec);spec.loader.exec_module(schedule)
class ScheduleTests(unittest.TestCase):
    def test_windows_enable_idempotent_and_user_scoped(self):
        calls=[]
        with mock.patch.object(schedule,"run",side_effect=lambda c:(calls.append(c) or {"ok":True})):
            first=schedule.windows("enable",ROOT,"APPROVE-WEEKLY-METADATA-CHECK");second=schedule.windows("enable",ROOT,"APPROVE-WEEKLY-METADATA-CHECK")
        self.assertTrue(first["ok"] and second["ok"]);self.assertIn("/F",calls[0]);self.assertNotIn("/RU",calls[0]);self.assertEqual(calls[0][:5],calls[1][:5]);self.assertEqual(calls[0][-1],calls[1][-1])
    def test_schedule_requires_opt_in(self):
        with self.assertRaises(SystemExit):schedule.windows("enable",ROOT,None)
    def test_mac_and_linux_templates_are_user_scoped(self):
        text=(ROOT/"engine"/"improvement_schedule.py").read_text(encoding="utf-8");self.assertIn("LaunchAgents",text);self.assertIn("systemd\"/\"user",text);self.assertNotIn("/Library/LaunchDaemons",text);self.assertNotIn("sudo",text)
if __name__=="__main__":unittest.main(verbosity=2)
