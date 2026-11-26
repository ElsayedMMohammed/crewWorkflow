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
            self.assertEqual(path.parent.name,'.agent-tasks')
            self.assertTrue(path.exists())
            state=json.loads((pathlib.Path(d)/'.workflow/state.json').read_text())
            self.assertEqual(state['tasks']['task-001']['file'],'.agent-tasks/task-001-comparison-tab-readiness.md')
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
            old=root/'.agent-tasks/task-001.md'
            (root/'.agent-tasks/task-001-old-task.md').rename(old)
            state=json.loads((root/'.workflow/state.json').read_text())
            del state['tasks']['task-001']['file']
            (root/'.workflow/state.json').write_text(json.dumps(state))
            self.assertEqual(pathlib.Path(self.run_cmd(d,'path','task-001').stdout.strip()),old)
    def test_migrates_old_tasks_folder(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d); root=pathlib.Path(d)
            # simulate a pre-V1.3 install: registry points at tasks/, files live there, plus an unrelated project file
            self.run_cmd(d,'new','Old layout')
            (root/'tasks').mkdir()
            (root/'.agent-tasks/task-001-old-layout.md').rename(root/'tasks/task-001-old-layout.md')
            (root/'tasks/task-002.md').write_text('unregistered legacy task')
            (root/'tasks/roadmap.md').write_text('project-owned, not a workflow task')
            state=json.loads((root/'.workflow/state.json').read_text())
            state['tasks']['task-001']['file']='tasks/task-001-old-layout.md'
            (root/'.workflow/state.json').write_text(json.dumps(state))
            self.assertIn('Migrated 2 task file(s)', self.run_cmd(d,'init').stdout)
            state=json.loads((root/'.workflow/state.json').read_text())
            self.assertEqual(state['tasks']['task-001']['file'],'.agent-tasks/task-001-old-layout.md')
            self.assertTrue((root/'.agent-tasks/task-001-old-layout.md').exists())
            self.assertTrue((root/'.agent-tasks/task-002.md').exists())
            self.assertTrue((root/'tasks/roadmap.md').exists())  # untouched
            self.assertEqual(pathlib.Path(self.run_cmd(d,'path','task-001').stdout.strip()).parent.name,'.agent-tasks')
            self.assertNotIn('Migrated', self.run_cmd(d,'init').stdout)  # idempotent
    def test_old_folder_removed_when_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d); root=pathlib.Path(d)
            (root/'tasks').mkdir(); (root/'tasks/task-005.md').write_text('x')
            self.run_cmd(d,'init')
            self.assertFalse((root/'tasks').exists())
            self.assertTrue((root/'.agent-tasks/task-005.md').exists())
    def test_scratch(self):
        with tempfile.TemporaryDirectory() as d:
            self.fixture(d); self.run_cmd(d,'new','Report')
            scratch=pathlib.Path(self.run_cmd(d,'scratch','task-001').stdout.strip())
            self.assertTrue(scratch.is_dir())
            self.assertEqual(scratch.parent.name,'runs')

FAKE_GH = """#!/usr/bin/env python3
import json, os, pathlib, sys
d = pathlib.Path(os.environ['FAKE_GH_DIR']); a = sys.argv[1:]
if a[:2] == ['api', 'user']: print('me-user')
elif a[:2] == ['pr', 'list'] and 'review-requested:@me' in a: print((d / 'requested.json').read_text())
elif a[:2] == ['pr', 'list'] and 'reviewed-by:@me' in a: print((d / 'reviewed.json').read_text())
elif a[:2] == ['pr', 'list']: print((d / 'list.json').read_text())
elif a[:2] == ['pr', 'view']: print((d / 'view.json').read_text())
else: sys.exit('unexpected gh call: ' + ' '.join(a))
"""

class PRTests(unittest.TestCase):
    def setUp(self):
        import os, json
        self.tmp = tempfile.TemporaryDirectory(); t = pathlib.Path(self.tmp.name)
        self.gh_dir = t / 'gh'; self.gh_dir.mkdir()
        gh = self.gh_dir / 'gh'; gh.write_text(FAKE_GH); gh.chmod(0o755)
        self.env = dict(os.environ, WORKFLOW_GH=str(gh), FAKE_GH_DIR=str(self.gh_dir),
                        WORKFLOW_WORKTREE_ROOT=str(t / 'wt'), GIT_AUTHOR_NAME='T', GIT_AUTHOR_EMAIL='t@example.com',
                        GIT_COMMITTER_NAME='T', GIT_COMMITTER_EMAIL='t@example.com')
        # bare "GitHub" remote with main and a PR head ref
        remote = t / 'remote.git'; seed = t / 'seed'; self.repo = t / 'repo'
        self.git(t, 'init', '-q', '--bare', str(remote))
        self.git(t, 'init', '-q', '-b', 'main', str(seed))
        (seed / 'app.py').write_text('x = 1\n'); self.git(seed, 'add', '.'); self.git(seed, 'commit', '-qm', 'base')
        self.git(seed, 'push', '-q', str(remote), 'main')
        self.git(seed, 'checkout', '-qb', 'feature'); (seed / 'feature.py').write_text('y = 2\n')
        self.git(seed, 'add', '.'); self.git(seed, 'commit', '-qm', 'feature')
        self.git(seed, 'push', '-q', str(remote), 'feature:refs/pull/7/head')
        self.git(t, 'clone', '-q', str(remote), str(self.repo))
        (self.repo / '.workflow').mkdir(); (self.repo / '.workflow' / 'task-template.md').write_text('{{TASK_ID}}')
        (self.gh_dir / 'view.json').write_text(json.dumps({'number': 7, 'title': 'Add feature', 'url': 'u', 'author': {'login': 'bob'},
            'state': 'OPEN', 'isDraft': False, 'baseRefName': 'main', 'headRefName': 'feature', 'headRefOid': 'x', 'isCrossRepository': False}))
        self.run_cmd('init')
    def tearDown(self): self.tmp.cleanup()
    def git(self, cwd, *a):
        subprocess.run(['git', *a], cwd=cwd, check=True, capture_output=True, env=self.env)
    def run_cmd(self, *args, ok=True):
        p = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, capture_output=True, text=True, env=self.env)
        if ok: self.assertEqual(p.returncode, 0, p.stderr)
        else: self.assertNotEqual(p.returncode, 0, p.stdout)
        return p

    def test_prs_categorized_by_review_request(self):
        import json
        (self.gh_dir / 'list.json').write_text(json.dumps([
            {'number': 1, 'title': 'Direct', 'body': '<!-- tpl -->Adds   caching', 'author': {'login': 'bob'},
             'assignees': [], 'isDraft': False, 'reviewRequests': [{'login': 'Me-User'}]},
            {'number': 2, 'title': 'Assigned only', 'body': '', 'author': {'login': 'me-user'},
             'assignees': [{'login': 'me-user'}], 'isDraft': True, 'reviewRequests': [{'login': 'alice'}]},
            {'number': 3, 'title': 'Team', 'body': '', 'author': {'login': 'bob'}, 'assignees': [],
             'isDraft': False, 'reviewRequests': [{'name': 'core', 'slug': 'core'}]},
            {'number': 4, 'title': 'Reviewed', 'body': '', 'author': {'login': 'bob'}, 'assignees': [],
             'isDraft': False, 'reviewRequests': []}]))
        (self.gh_dir / 'requested.json').write_text(json.dumps([{'number': 1}, {'number': 3}]))
        (self.gh_dir / 'reviewed.json').write_text(json.dumps([{'number': 4}]))
        out = json.loads(self.run_cmd('prs', '--json').stdout)
        self.assertEqual([p['number'] for p in out['my_reviews']], [1, 3, 4])
        self.assertEqual([p['number'] for p in out['others']], [2])  # assignment alone does not count
        mine = {p['number']: p for p in out['my_reviews']}
        self.assertEqual(mine[1]['body_excerpt'], 'Adds caching')
        self.assertFalse(mine[1]['requested_via_team']); self.assertTrue(mine[3]['requested_via_team'])
        self.assertTrue(mine[4]['reviewed_by_me']); self.assertFalse(mine[4]['review_requested_from_me'])
        self.assertTrue(out['others'][0]['assigned_to_me'])
        text = self.run_cmd('prs').stdout
        self.assertIn('Your reviews (@me-user, requested or already reviewed): 3', text)
        self.assertIn('#2 Assigned only', text); self.assertIn('already reviewed', text)

    def test_review_lifecycle(self):
        import json
        info = json.loads(self.run_cmd('review-start', '#7').stdout)
        wt = pathlib.Path(info['worktree'])
        self.assertTrue((wt / 'feature.py').exists()); self.assertEqual(info['head_ref'], 'refs/workflow/pr/7/head')
        self.assertFalse((self.repo / 'feature.py').exists())  # user's working tree untouched
        self.assertFalse(str(wt).startswith(str(self.repo)))
        self.assertTrue(pathlib.Path(info['scratch']).is_dir())
        self.run_cmd('review-start', '7', ok=False)  # already in progress
        # question budget: two rounds, then refused
        for _ in range(2):
            self.run_cmd('review-questions', '7'); self.run_cmd('review-answered', 'pr-7')
        self.run_cmd('review-questions', '7', ok=False)
        self.run_cmd('review-verdict', '7', 'MERGE', ok=False)
        self.run_cmd('review-verdict', '7', 'REQUEST_CHANGES')
        state = json.loads((self.repo / '.workflow/state.json').read_text())
        self.assertEqual(state['reviews']['pr-7']['verdict'], 'REQUEST_CHANGES')
        # re-review after verdict starts a new round with a fresh question budget
        info2 = json.loads(self.run_cmd('review-start', '7').stdout)
        self.assertEqual(info2['round'], 2); self.assertNotEqual(info2['report'], info['report'])
        self.run_cmd('review-questions', '7')
        self.run_cmd('review-answered', '7'); self.run_cmd('review-verdict', '7', 'APPROVE')
        self.run_cmd('review-cleanup', '7')
        self.assertFalse(wt.exists())
        refs = subprocess.run(['git', 'for-each-ref', 'refs/workflow'], cwd=self.repo, capture_output=True, text=True).stdout
        self.assertEqual(refs.strip(), '')
        self.assertEqual(json.loads(self.run_cmd('review-status', '7').stdout)['status'], 'CLOSED')

    def test_closed_pr_refused(self):
        import json
        view = json.loads((self.gh_dir / 'view.json').read_text()); view['state'] = 'MERGED'
        (self.gh_dir / 'view.json').write_text(json.dumps(view))
        self.run_cmd('review-start', '7', ok=False)

if __name__=='__main__': unittest.main()
