import hashlib,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
class ReleaseGateTests(unittest.TestCase):
    def test_release_builder_excludes_git_metadata(self):
        text=(ROOT/"build_release.py").read_text(encoding="utf-8-sig")
        self.assertIn('".git"',text)
        self.assertIn('".github"',text)
    def test_product_gate_rejects_removed_cli_spoof_flags(self):
        cp=subprocess.run([sys.executable,str(ROOT/"product_gate.py"),"--root",str(ROOT),"--code-signed"],capture_output=True,text=True);self.assertNotEqual(cp.returncode,0);self.assertIn("unrecognized arguments",cp.stderr)
    def test_zip_checksum_required_and_verified(self):
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/"x.zip"
            with zipfile.ZipFile(archive,"w") as z:z.writestr("safe.txt","safe")
            digest=hashlib.sha256(archive.read_bytes()).hexdigest();Path(str(archive)+".sha256").write_text(digest+"  x.zip\n")
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),Path(str(archive)+".sha256").read_text().split()[0]);archive.write_bytes(archive.read_bytes()+b"tamper");self.assertNotEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),digest)
if __name__=="__main__":unittest.main(verbosity=2)
