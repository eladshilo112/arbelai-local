import hashlib,importlib.util,json,os,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location("portable",ROOT/"portable.py");portable=importlib.util.module_from_spec(spec);spec.loader.exec_module(portable)
sys.path.insert(0,str(ROOT/"engine"));import arbelai

class ProductTests(unittest.TestCase):
    def test_official_https_allowlist(self):
        self.assertTrue(portable.allowed_download_url("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"))
        self.assertFalse(portable.allowed_download_url("http://api.github.com/x"));self.assertFalse(portable.allowed_download_url("https://evil.example/x"));self.assertFalse(portable.allowed_download_url("https://user:pass@github.com/x"))
    def test_sha_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x";p.write_bytes(b"safe");good=hashlib.sha256(b"safe").hexdigest();self.assertTrue(portable.verify_sha256(p,good));p.write_bytes(b"tampered");self.assertFalse(portable.verify_sha256(p,good))
    def test_zip_slip(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/"bad.zip"
            with zipfile.ZipFile(a,"w") as z:z.writestr("../escape.txt","bad")
            with self.assertRaises(RuntimeError):portable.safe_extract_zip(a,Path(d)/"out")
            self.assertFalse((Path(d)/"escape.txt").exists())
    def test_privacy_redaction(self):
        secret="api_"+"key="+"abcdefghijk";scan=arbelai.privacy_scan(secret+" user@example.com")
        self.assertEqual(scan["risk"],"high");self.assertNotIn("abcdefghijk",scan["redacted_text"]);self.assertNotIn("user@example.com",scan["redacted_text"])
    def test_restricted_safe_route(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"config").mkdir();(root/"config"/"ROUTING_POLICY.json").write_text(json.dumps({"critical_task_types":[],"task_rules":{"default":{"local_candidates":[],"cloud_tier":"strong"}}}));(root/"config"/"MODEL_REGISTRY.json").write_text('{"models":{}}');arbelai.set_root(root);self.assertEqual(arbelai.route("unknown",privacy="secret")["execution"],"blocked")
        arbelai.set_root(ROOT)
    def test_resume_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"node";a=portable.Installer(target,True,True,offline=True);a.checkpoint("phase",{"value":1});b=portable.Installer(target,True,True,offline=True);self.assertEqual(b.state["checkpoints"]["phase"]["payload"]["value"],1)
    def test_backup_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"node";target.mkdir();p=target/"existing.txt";p.write_text("before");a=portable.Installer(target,False,True,offline=True);a.write(p,b"after");self.assertEqual(p.read_text(),"after");a.rollback(True);self.assertEqual(p.read_text(),"before")
    def test_config_conflict_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"node";target.mkdir();p=target/"existing.txt";p.write_text("before");a=portable.Installer(target,False,True,offline=True);a.write(p,b"after");p.write_text("user change");a.rollback(True);self.assertEqual(p.read_text(),"user change")
    def test_safe_low_resource_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            a=portable.Installer(Path(d)/"node",False,True,offline=True);a.current_profile={"compatibility":{"local_download_allowed":False}};r=a.install_candidates({"models":[],"runtime":{}});self.assertEqual(r["reason"],"safe_fallback_context_only")
    def test_unicode_path_dry_run_offline(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"משתמש עם רווחים";cp=subprocess.run([sys.executable,str(ROOT/"portable.py"),"bootstrap","--target",str(target),"--dry-run","--non-interactive","--offline"],capture_output=True,text=True,timeout=60);self.assertEqual(cp.returncode,0,cp.stderr);self.assertTrue((target/".arbelai-install"/"state.json").exists())
    def test_update_checker_never_installs(self):
        cp=subprocess.run([sys.executable,str(ROOT/"engine"/"update_checker.py"),"--root",str(ROOT),"--offline"],capture_output=True,text=True);self.assertEqual(cp.returncode,0);self.assertFalse(json.loads(cp.stdout)["installed"])
    def test_improvement_watcher_offline(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"config").mkdir();(root/"config"/"IMPROVEMENT_WATCHER.json").write_bytes((ROOT/"config"/"IMPROVEMENT_WATCHER.json").read_bytes());cp=subprocess.run([sys.executable,str(ROOT/"engine"/"improvement_watcher.py"),"--root",str(root),"--offline"],capture_output=True,text=True);self.assertEqual(cp.returncode,0);self.assertEqual(json.loads(cp.stdout)["status"],"offline_no_change")
    def test_no_telemetry_default(self):
        privacy=json.loads((ROOT/"config"/"PRIVACY.json").read_text(encoding="utf-8-sig"));self.assertFalse(privacy["telemetry"]["enabled"]);self.assertIsNone(privacy["telemetry"]["endpoint"])
    def test_mcp_stdio_no_listener_config(self):
        text=(ROOT/"engine"/"mcp_server.py").read_text(encoding="utf-8");self.assertIn('"stdio"',json.dumps({"transport":"stdio"}));self.assertNotIn("ThreadingHTTPServer",text);self.assertNotIn("0.0.0.0",text)
    def test_mcp_initialize_roundtrip(self):
        message=json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}).encode();wire=b"Content-Length: "+str(len(message)).encode()+b"\r\n\r\n"+message
        cp=subprocess.run([sys.executable,str(ROOT/"engine"/"mcp_server.py")],input=wire,capture_output=True,timeout=10);self.assertEqual(cp.returncode,0,cp.stderr.decode(errors="ignore"));self.assertIn(b'"serverInfo"',cp.stdout);self.assertNotIn(b"http://",cp.stdout)
    def test_no_remote_shell_execution(self):
        text="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in ROOT.rglob("*.py"));self.assertNotIn("shell"+"=True",text);self.assertNotIn("os."+"system(",text)

if __name__=="__main__":unittest.main(verbosity=2)
