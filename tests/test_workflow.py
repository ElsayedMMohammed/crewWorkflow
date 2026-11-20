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
            self.run_cmd(d,'mode','task-001','full')
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

class V11Tests(WorkflowTests):
    def fixture(self, d):
        p=pathlib.Path(d); (p/'.workflow').mkdir(); (p/'.workflow'/'task-template.md').write_text('{{TASK_ID}} {{TITLE}}')
        self.run_cmd(d,'init')
    def test_slugged_path_and_light_review(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d)
            self.run_cmd(d,'new','Comparison Tab Readiness!')
            path=pathlib.Path(self.run_cmd(d,'path','task-001').stdout.strip())
            self.assertEqual(path.name,'task-001-comparison-tab-readiness.md')
            self.assertTrue(path.exists())
            state=json.loads((pathlib.Path(d)/'.workflow/state.json').read_text())
            self.assertEqual(state['tasks']['task-001']['file'],'tasks/task-001-comparison-tab-readiness.md')
            self.run_cmd(d,'mode','task-001','light')
            self.run_cmd(d,'transition','task-001','READY')
            self.run_cmd(d,'transition','task-001','IMPLEMENTING','--approved')
            self.run_cmd(d,'transition','task-001','CAPTAIN_REVIEW')
    def test_full_cannot_skip_tester(self):
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d); self.run_cmd(d,'new','Feature')
            self.run_cmd(d,'mode','task-001','full'); self.run_cmd(d,'transition','task-001','READY')
            self.run_cmd(d,'transition','task-001','IMPLEMENTING','--approved')
            self.assertNotEqual(self.run_cmd(d,'transition','task-001','CAPTAIN_REVIEW',ok=False).returncode,0)
    def test_legacy_path(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d); self.run_cmd(d,'new','Old task')
            root=pathlib.Path(d)
            old=root/'tasks/task-001.md'
            (root/'tasks/task-001-old-task.md').rename(old)
            state=json.loads((root/'.workflow/state.json').read_text())
            del state['tasks']['task-001']['file']
            (root/'.workflow/state.json').write_text(json.dumps(state))
            self.assertEqual(pathlib.Path(self.run_cmd(d,'path','task-001').stdout.strip()),old)
    def test_scratch(self):
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d); self.run_cmd(d,'new','Report')
            scratch=pathlib.Path(self.run_cmd(d,'scratch','task-001').stdout.strip())
            self.assertTrue(scratch.is_dir())
            self.assertEqual(scratch.parent.name,'runs')

if __name__=='__main__': unittest.main()
