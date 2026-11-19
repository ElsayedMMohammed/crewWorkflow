import pathlib, subprocess, sys, tempfile, unittest
SCRIPT=pathlib.Path(__file__).resolve().parents[1]/'bin'/'workflow.py'
class WorkflowTests(unittest.TestCase):
    def run_cmd(self, cwd, *args, ok=True):
        p=subprocess.run([sys.executable,str(SCRIPT),*args],cwd=cwd,capture_output=True,text=True)
        if ok: self.assertEqual(p.returncode,0,p.stderr)
        return p
    def test_state_and_approval(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d); (p/'.workflow').mkdir(); (p/'.workflow'/'task-template.md').write_text('ID {{TASK_ID}} {{TITLE}} {{DATE}}')
            self.run_cmd(d,'init'); self.assertIn('task-001',self.run_cmd(d,'new','Demo').stdout)
            self.assertNotEqual(self.run_cmd(d,'transition','task-001','IMPLEMENTING',ok=False).returncode,0)
            self.run_cmd(d,'transition','task-001','READY')
            self.assertNotEqual(self.run_cmd(d,'transition','task-001','IMPLEMENTING',ok=False).returncode,0)
            self.run_cmd(d,'transition','task-001','IMPLEMENTING','--approved')
            self.run_cmd(d,'transition','task-001','VALIDATING')
            self.run_cmd(d,'transition','task-001','CAPTAIN_REVIEW')
            self.assertNotEqual(self.run_cmd(d,'transition','task-001','COMMITTING',ok=False).returncode,0)
            self.run_cmd(d,'transition','task-001','COMMITTING','--captain-approved')
    def test_recovery_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d); (p/'.workflow').mkdir(); (p/'.workflow'/'task-template.md').write_text('{{TASK_ID}}')
            self.run_cmd(d,'init'); self.run_cmd(d,'new','Demo')
            for _ in range(3): self.run_cmd(d,'recovery-attempt','task-001','tester')
            self.assertNotEqual(self.run_cmd(d,'recovery-attempt','task-001','tester',ok=False).returncode,0)
if __name__=='__main__': unittest.main()
