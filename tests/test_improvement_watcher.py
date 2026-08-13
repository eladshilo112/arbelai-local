import hashlib,importlib.util,io,json,tempfile,unittest,urllib.error,zipfile
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location("watcher",ROOT/"engine"/"improvement_watcher.py");wmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(wmod)

class Response:
    def __init__(self,data,status=200,headers=None):self.raw=data if isinstance(data,bytes) else json.dumps(data).encode();self.stream=io.BytesIO(self.raw);self.status=status;self.headers=headers or {"Content-Length":str(len(self.raw))}
    def read(self,n=-1):return self.stream.read(n)
    def __enter__(self):return self
    def __exit__(self,*args):return False

def make_root(folder,enabled=True,ram=32*1024**3,disk=100*1024**3):
    root=Path(folder);(root/"config").mkdir(parents=True)
    for name in ["IMPROVEMENT_WATCHER.json","REVOCATIONS.json","CVE_POLICY.json"]:(root/"config"/name).write_bytes((ROOT/"config"/name).read_bytes())
    config=json.loads((root/"config"/"IMPROVEMENT_WATCHER.json").read_text(encoding="utf-8-sig"));config["enabled"]=enabled;(root/"config"/"IMPROVEMENT_WATCHER.json").write_text(json.dumps(config))
    sources={"version":1,"allowed_hosts":["api.github.com","api.osv.dev","github.com"],"sources":[{"id":"openvino","kind":"runtime","publisher":"Intel","official":True,"channel":"stable","metadata_type":"github_release","metadata_url":"https://api.github.com/repos/openvinotoolkit/openvino/releases/latest","project_url":"https://github.com/openvinotoolkit/openvino","license":"Apache-2.0","os":["Windows"],"architectures":["AMD64"],"hardware_tags":["cpu"]}]};(root/"config"/"IMPROVEMENT_SOURCES.json").write_text(json.dumps(sources));(root/"config"/"MACHINE_PROFILE.json").write_text(json.dumps({"ram":{"total_bytes":ram},"storage":{"free_bytes":disk}}));(root/"config"/"WORKLOAD_PROFILE.json").write_text(json.dumps({"priorities":["extraction"]}));return root

class WatcherTests(unittest.TestCase):
    def release(self,digest=None,size=1024,license_unused=None):return {"tag_name":"2026.1.0","published_at":"2026-08-14T00:00:00Z","assets":[{"name":"runtime.zip","browser_download_url":"https://github.com/runtime.zip","size":size,"digest":"sha256:"+digest if digest else None}]}
    def test_online_mock_metadata_and_dedup(self):
        payload=b"x"*1024;digest=hashlib.sha256(payload).hexdigest();calls=[]
        def opener(req,**kwargs):
            calls.append(req.full_url)
            if "osv.dev" in req.full_url:return Response({"vulns":[]},headers={"Content-Length":"13","X-Mock-Signature":"trusted-test-fixture"})
            return Response(self.release(digest),headers={"Content-Length":"400","X-Mock-Signature":"trusted-test-fixture"})
        with tempfile.TemporaryDirectory() as d:
            watcher=wmod.Watcher(make_root(d),opener=opener);first=watcher.discover();second=watcher.discover();self.assertEqual(len(first["candidates"]),1);self.assertEqual(len(second["candidates"]),1);self.assertEqual(first["candidates"][0]["state"],"awaiting_user_approval");self.assertTrue(first["candidates"][0]["cve_gate"]["promotion_allowed"])
    def test_malicious_metadata_without_hash_rejected(self):
        def opener(req,**kwargs):return Response({"vulns":[]}) if "osv.dev" in req.full_url else Response(self.release(None))
        with tempfile.TemporaryDirectory() as d:
            result=wmod.Watcher(make_root(d),opener=opener).discover();self.assertEqual(result["candidates"][0]["state"],"rejected");self.assertIn("verified_compatible_artifact_unavailable",result["candidates"][0]["reasons"])
    def test_timeout_and_rate_limit_are_source_failure(self):
        attempts={"n":0}
        def opener(req,**kwargs):attempts["n"]+=1;raise urllib.error.HTTPError(req.full_url,429,"rate",{},None)
        with tempfile.TemporaryDirectory() as d:
            result=wmod.Watcher(make_root(d),opener=opener,sleep=lambda _:None).discover();self.assertTrue(result["source_failures"]);self.assertEqual(attempts["n"],3)
    def test_cve_unknown_allows_isolated_canary_but_blocks_security_promotion(self):
        payload=b"x";digest=hashlib.sha256(payload).hexdigest()
        def opener(req,**kwargs):return Response(self.release(digest,1)) if "github" in req.full_url else (_ for _ in ()).throw(TimeoutError())
        with tempfile.TemporaryDirectory() as d:
            watcher=wmod.Watcher(make_root(d),opener=opener,sleep=lambda _:None);candidate=watcher.discover()["candidates"][0];self.assertFalse(candidate["cve_gate"]["promotion_allowed"])
            watcher.opener=lambda req,**kw:Response(payload);watcher.canary(candidate["id"],"APPROVE-CANARY-"+candidate["id"]);self.assertEqual(candidate["state"],"canary_downloaded")
    def test_license_unknown_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=make_root(d);sources=json.loads((root/"config"/"IMPROVEMENT_SOURCES.json").read_text());sources["sources"][0]["license"]=None;(root/"config"/"IMPROVEMENT_SOURCES.json").write_text(json.dumps(sources));payload=b"x";digest=hashlib.sha256(payload).hexdigest();opener=lambda req,**kw:Response({"vulns":[]}) if "osv" in req.full_url else Response(self.release(digest,1));candidate=wmod.Watcher(root,opener=opener).discover()["candidates"][0];self.assertEqual(candidate["license_gate"]["status"],"unknown");self.assertEqual(candidate["state"],"rejected")
    def test_low_ram_and_disk_rejected(self):
        payload=b"x";digest=hashlib.sha256(payload).hexdigest();opener=lambda req,**kw:Response({"vulns":[]}) if "osv" in req.full_url else Response(self.release(digest,6*1024**3))
        with tempfile.TemporaryDirectory() as d:
            candidate=wmod.Watcher(make_root(d,ram=8*1024**3,disk=4*1024**3),opener=opener).discover()["candidates"][0];self.assertFalse(candidate["memory_fit"]["fit"]);self.assertEqual(candidate["state"],"rejected")
    def prepared_candidate(self,root,payload=b"canary"):
        digest=hashlib.sha256(payload).hexdigest();watcher=wmod.Watcher(root,opener=lambda req,**kw:Response(payload,status=200));candidate={"id":"candidate123","state":"awaiting_user_approval","source":{"source_id":"openvino","version":"2026.1.0","assets":[{"name":"runtime.bin","url":"https://github.com/runtime.bin","size":len(payload),"sha256":digest}]},"license_gate":{"promotion_allowed":True},"cve_gate":{"promotion_allowed":True},"history":[]};watcher.state["candidates"][candidate["id"]]=candidate;wmod.atomic(watcher.state_path,watcher.state);return watcher,candidate
    def test_hash_mismatch_and_partial_download(self):
        with tempfile.TemporaryDirectory() as d:
            watcher,candidate=self.prepared_candidate(make_root(d));candidate["source"]["assets"][0]["sha256"]="0"*64
            with self.assertRaises(RuntimeError):watcher.canary(candidate["id"],"APPROVE-CANARY-"+candidate["id"])
            self.assertTrue((watcher.root/"canary"/candidate["id"]/"downloads"/"runtime.bin.part").exists())
    def test_size_mismatch_blocks_canary_and_preserves_production(self):
        with tempfile.TemporaryDirectory() as d:
            watcher,candidate=self.prepared_candidate(make_root(d),b"short");candidate["source"]["assets"][0]["size"]=99;watcher.state["production"]={"candidate_id":"stable"}
            with self.assertRaisesRegex(RuntimeError,"size_mismatch"):watcher.canary(candidate["id"],"APPROVE-CANARY-"+candidate["id"])
            self.assertEqual(watcher.state["production"]["candidate_id"],"stable")
    def test_malicious_archive_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/"bad.zip"
            with zipfile.ZipFile(archive,"w") as z:z.writestr("../escape.txt","x")
            with self.assertRaisesRegex(RuntimeError,"malicious_archive_path"):wmod.safe_extract(archive,root/"out")
            link=root/"link.zip";info=zipfile.ZipInfo("link");info.create_system=3;info.external_attr=(0o120777<<16)
            with zipfile.ZipFile(link,"w") as z:z.writestr(info,"target")
            with self.assertRaisesRegex(RuntimeError,"archive_symlink_rejected"):wmod.safe_extract(link,root/"out2")
    def test_regression_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            watcher,candidate=self.prepared_candidate(make_root(d));candidate["state"]="security_passed";base=watcher.root/"base.json";result=watcher.root/"result.json";base.write_text(json.dumps({"average_quality":.9,"stability_success_rate":1,"average_tokens_per_second":10,"peak_ram_bytes":100}));result.write_text(json.dumps({"average_quality":.8,"stability_success_rate":1,"average_tokens_per_second":12,"peak_ram_bytes":100,"privacy_gate_passed":True}));comparison=watcher.compare(candidate["id"],base,result);self.assertFalse(comparison["quality_no_regression"]);self.assertEqual(candidate["state"],"rejected")
    def test_benchmark_comparator_passes_measurable_improvement(self):
        with tempfile.TemporaryDirectory() as d:
            watcher,candidate=self.prepared_candidate(make_root(d));candidate["state"]="security_passed";base=watcher.root/"base.json";result=watcher.root/"result.json";base.write_text(json.dumps({"average_quality":.9,"stability_success_rate":1,"average_tokens_per_second":10,"peak_ram_bytes":100}));result.write_text(json.dumps({"average_quality":.9,"stability_success_rate":1,"average_tokens_per_second":11,"peak_ram_bytes":105,"privacy_gate_passed":True}));comparison=watcher.compare(candidate["id"],base,result);self.assertTrue(comparison["improvement_justified"]);self.assertEqual(candidate["state"],"benchmark_passed")
    def test_promotion_rollback_revocation(self):
        with tempfile.TemporaryDirectory() as d:
            watcher,candidate=self.prepared_candidate(make_root(d));candidate["state"]="benchmark_passed";watcher.state["production"]={"candidate_id":"old","source_id":"openvino","version":"2025.1"};production=watcher.promote(candidate["id"],"APPROVE-PROMOTION-"+candidate["id"]);self.assertEqual(production["candidate_id"],candidate["id"]);restored=watcher.rollback(candidate["id"],"APPROVE-ROLLBACK-"+candidate["id"]);self.assertEqual(restored["candidate_id"],"old");candidate["state"]="awaiting_user_approval";watcher.revoke(candidate["id"],"test");self.assertEqual(candidate["state"],"revoked")
    def test_revocation_added_after_discovery_blocks_canary(self):
        with tempfile.TemporaryDirectory() as d:
            root=make_root(d);watcher,candidate=self.prepared_candidate(root);(root/"config"/"REVOCATIONS.json").write_text(json.dumps({"revoked":[{"source_id":"openvino","version":"2026.1.0"}]}))
            with self.assertRaisesRegex(RuntimeError,"candidate_revoked"):watcher.canary(candidate["id"],"APPROVE-CANARY-"+candidate["id"])
            self.assertEqual(candidate["state"],"revoked")
    def test_source_specific_license_allowlist(self):
        with tempfile.TemporaryDirectory() as d:
            watcher=wmod.Watcher(make_root(d));source={"license_allowlist":["custom-safe"]};self.assertTrue(watcher.license_gate(source,"custom-safe")["promotion_allowed"]);self.assertFalse(watcher.license_gate(source,"mit")["promotion_allowed"])
    def test_downgrade_protection_and_last_known_good(self):
        with tempfile.TemporaryDirectory() as d:
            watcher,candidate=self.prepared_candidate(make_root(d));candidate["state"]="benchmark_passed";candidate["source"]["version"]="2025.1";watcher.state["production"]={"candidate_id":"newer","source_id":"openvino","version":"2026.1"}
            with self.assertRaisesRegex(RuntimeError,"downgrade_blocked"):watcher.promote(candidate["id"],"APPROVE-PROMOTION-"+candidate["id"])
            self.assertEqual(watcher.state["production"]["candidate_id"],"newer")
    def test_duplicate_candidate_enters_cooldown(self):
        payload=b"x"*1024;digest=hashlib.sha256(payload).hexdigest()
        def opener(req,**kwargs):return Response({"vulns":[]}) if "osv.dev" in req.full_url else Response(self.release(digest))
        with tempfile.TemporaryDirectory() as d:
            watcher=wmod.Watcher(make_root(d),opener=opener);watcher.discover();candidate=watcher.discover()["candidates"][0];self.assertTrue(candidate["cooldown"]["active"]);self.assertGreater(candidate["cooldown"]["remaining_days"],0)
    def test_darwin_asset_is_never_classified_as_windows(self):
        with tempfile.TemporaryDirectory() as d:
            watcher=wmod.Watcher(make_root(d));record={"assets":[{"name":"ollama-darwin.zip"},{"name":"ollama-windows-amd64.zip"},{"name":"portable.gguf"}]};names=[x["name"] for x in watcher.compatible_assets(record)];self.assertNotIn("ollama-darwin.zip",names);self.assertIn("ollama-windows-amd64.zip",names);self.assertIn("portable.gguf",names)

if __name__=="__main__":unittest.main(verbosity=2)
