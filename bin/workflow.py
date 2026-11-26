#!/usr/bin/env python3
"""Small, dependency-free task registry, PR review registry and safe Git commit helper."""
import argparse, datetime, hashlib, json, os, pathlib, re, subprocess, sys
ROOT = pathlib.Path.cwd()
STATE = ROOT / '.workflow' / 'state.json'
TASKS = ROOT / 'tasks'
STATUSES = {'DRAFT','READY','IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW','COMMITTING','COMPLETED','BLOCKED'}
ALLOWED = {'DRAFT':{'READY'}, 'READY':{'IMPLEMENTING','DRAFT'}, 'IMPLEMENTING':{'VALIDATING','CAPTAIN_REVIEW','BLOCKED'}, 'VALIDATING':{'IMPLEMENTING','CAPTAIN_REVIEW','BLOCKED'}, 'CAPTAIN_REVIEW':{'IMPLEMENTING','COMMITTING','BLOCKED'}, 'COMMITTING':{'COMPLETED','BLOCKED'}, 'BLOCKED':{'IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW'}, 'COMPLETED':set()}
REVIEW_STATUSES = {'REVIEWING','AWAITING_ANSWERS','DONE','CLOSED'}
VERDICTS = ('APPROVE','REQUEST_CHANGES','REJECT')
MAX_QUESTION_ROUNDS = 2
def load():
    s = json.loads(STATE.read_text()) if STATE.exists() else {'tasks':{},'active_task':None}
    s.setdefault('reviews', {})
    return s
def save(s):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(s,indent=2)+'\n'); tmp.replace(STATE)
def slugify(title):
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return (slug[:60].rstrip('-') or 'untitled')
def taskfile(t, state=None):
    state = state or load()
    entry = state['tasks'].get(t, {})
    recorded = entry.get('file')
    if recorded:
        path = ROOT / recorded
        if path.resolve().parent != TASKS.resolve():
            sys.exit('Invalid task path in registry')
        return path
    legacy = TASKS / (t + '.md')
    if legacy.exists(): return legacy
    matches = sorted(TASKS.glob(t + '-*.md'))
    if len(matches) == 1: return matches[0]
    if len(matches) > 1: sys.exit('Ambiguous task files: ' + t)
    return legacy

def init(args):
    TASKS.mkdir(exist_ok=True); STATE.parent.mkdir(exist_ok=True); save(load()); print('Initialized workflow registry')
def new(args):
    s=load(); n=max([int(k.split('-')[1]) for k in s['tasks'] if re.fullmatch(r'task-\d+',k)] or [0])+1
    t=f'task-{n:03d}'; filename=f'{t}-{slugify(args.title)}.md'; s['tasks'][t]={'file':f'tasks/{filename}','mode':None,'title':args.title,'status':'DRAFT','dependencies':[],'related':[],'attempts':{'developer':0,'tester':0},'validation_round':0,'sessions':{},'events':[]}
    TASKS.mkdir(exist_ok=True); template=(ROOT/'.workflow'/'task-template.md').read_text()
    taskfile(t,s).write_text(template.replace('{{TASK_ID}}',t).replace('{{TITLE}}',args.title).replace('{{DATE}}',datetime.date.today().isoformat()))
    save(s); print(t)
def status(args):
    s=load()
    if args.task:
        print(json.dumps(s['tasks'].get(args.task,{}),indent=2)); return
    print(json.dumps({'active_task':s['active_task'],'tasks':{k:v['status'] for k,v in s['tasks'].items()},'reviews':{k:{'status':v['status'],'verdict':v.get('verdict')} for k,v in s['reviews'].items()}},indent=2))
def transition(args):
    s=load(); t=args.task; d=s['tasks'].get(t)
    if not d: sys.exit('Unknown task')
    old=d['status']; new=args.to
    if new not in ALLOWED[old]: sys.exit(f'Invalid transition: {old} -> {new}')
    if new in {'IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW','COMMITTING'} and s['active_task'] not in (None,t): sys.exit('Another task is active')
    if new=='IMPLEMENTING' and old=='READY' and not args.approved: sys.exit('Requires --approved: user approved specification')
    if new=='IMPLEMENTING' and old=='READY' and d.get('mode') not in ('light','full'): sys.exit('Select approved mode first: workflow.py mode TASK light|full')
    if new=='COMMITTING' and not args.captain_approved: sys.exit('Requires --captain-approved: Captain reviewed implementation')
    if new=='CAPTAIN_REVIEW' and old=='IMPLEMENTING' and d.get('mode')!='light': sys.exit('Only light mode can skip independent validation')
    if new in {'IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW','COMMITTING'}: s['active_task']=t
    if new=='COMPLETED': s['active_task']=None
    d['status']=new; d['events'].append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'from':old,'to':new,'note':args.note or ''})
    save(s); print(f'{t}: {old} -> {new}')
def mode(args):
    s=load(); d=s['tasks'].get(args.task)
    if not d: sys.exit('Unknown task')
    if d['status'] not in ('DRAFT','READY'): sys.exit('Cannot change mode after implementation begins')
    d['mode']=args.mode
    save(s); print(f'{args.task}: mode={args.mode} (user must approve in task spec)')
def path(args):
    s=load()
    if args.task not in s['tasks']: sys.exit('Unknown task')
    print(taskfile(args.task,s))
def scratch(args):
    s=load()
    if args.task not in s['tasks']: sys.exit('Unknown task')
    d=ROOT/'.workflow'/'runs'/args.task
    d.mkdir(parents=True,exist_ok=True)
    print(d.resolve())
def attempt(args):
    s=load(); d=s['tasks'][args.task]; n=d['attempts'][args.role]+1
    if n>3: sys.exit('Recovery exhausted: BLOCK and escalate to user; do not retry')
    d['attempts'][args.role]=n; save(s)
    print(f'{args.role} recovery attempt {n}/3')
def recovered(args):
    s=load(); s['tasks'][args.task]['attempts'][args.role]=0; save(s); print('Recovery counter reset after verified useful progress')
def session(args):
    s=load(); s['tasks'][args.task]['sessions'][args.role]=args.terminal; save(s); print('Session recorded')
def event(args):
    s=load(); d=s['tasks'][args.task]; eid=args.id
    if any(x.get('id')==eid for x in d['events']): print('Duplicate event ignored'); return
    d['events'].append({'id':eid,'type':args.type,'from':args.sender,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifact':args.artifact}); save(s); print('Event recorded')
def commit(args):
    s=load(); d=s['tasks'][args.task]
    if d['status']!='COMMITTING': sys.exit('Task must be COMMITTING')
    if not args.files: sys.exit('Explicit task-related paths required')
    def git(*a): return subprocess.run(['git',*a],text=True,capture_output=True,check=True).stdout.strip()
    try:
        git('rev-parse','--show-toplevel'); name=git('config','user.name'); email=git('config','user.email')
        if not name or not email: sys.exit('Configure your own git user.name and user.email first')
        staged=git('diff','--cached','--name-only')
        if staged: sys.exit('Index already contains staged changes; unstage or handle manually')
        git('add','--',*args.files)
        staged=git('diff','--cached','--name-only')
        if not staged: sys.exit('No staged changes')
        git('commit','-m',args.message,'-m',args.body)
        print(git('rev-parse','HEAD'))
    except subprocess.CalledProcessError as exc:
        sys.exit(f'Git failed: {exc.stderr.strip()}')
# ---------------------------------------------------------------- PR reviews
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def gh_bin(): return os.environ.get('WORKFLOW_GH','gh')
def run(cmd, cwd=None):
    try:
        return subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,check=True).stdout.strip()
    except FileNotFoundError:
        sys.exit(f'Command not found: {cmd[0]}')
    except subprocess.CalledProcessError as exc:
        sys.exit(f'{" ".join(cmd[:3])} failed: {exc.stderr.strip()}')
def gh_json(*a): return json.loads(run([gh_bin(),*a]) or 'null')
def git(*a, cwd=None): return run(['git',*a],cwd=cwd)
def parse_pr(value):
    m = re.fullmatch(r'(?:#|pr-|PR-)?(\d+)', value.strip()) or re.search(r'/pull/(\d+)', value)
    if not m: sys.exit(f'Not a PR number: {value!r} (use 12, #12, pr-12 or a PR URL)')
    return int(m.group(1))
def worktree_path(n):
    base = os.environ.get('WORKFLOW_WORKTREE_ROOT') or str(pathlib.Path.home()/'.cache'/'myagenticworkflow'/'worktrees')
    tag = hashlib.sha1(str(ROOT.resolve()).encode()).hexdigest()[:8]
    return pathlib.Path(base)/f'{ROOT.resolve().name}-{tag}'/f'pr-{n}'
def review_entry(s, n):
    r = s['reviews'].get(f'pr-{n}')
    if not r: sys.exit(f'Unknown review: pr-{n} (run review-start first)')
    return r
def log(r, event, note=''): r['events'].append({'at':now(),'event':event,'note':note})

def categorize(prs, login, requested_numbers=(), reviewed_numbers=()):
    """Split PRs into those involving the user's review (requested directly, via a team, or already reviewed) and others."""
    me = (login or '').lower(); via_search = set(requested_numbers); reviewed_set = set(reviewed_numbers); mine, others = [], []
    for pr in prs:
        assignees = [a.get('login','') for a in pr.get('assignees') or []]
        direct = me in [x.get('login','').lower() for x in pr.get('reviewRequests') or [] if x.get('login')]
        requested = direct or pr['number'] in via_search
        reviewed = pr['number'] in reviewed_set
        body = re.sub(r'<!--.*?-->', '', pr.get('body') or '', flags=re.S)
        body = ' '.join(body.split())
        item = {'number':pr['number'],'title':pr.get('title',''),'url':pr.get('url',''),
                'author':(pr.get('author') or {}).get('login',''),'assignees':assignees,
                'draft':bool(pr.get('isDraft')),'review_requested_from_me':requested,
                'requested_via_team':requested and not direct,
                'reviewed_by_me':reviewed,
                'assigned_to_me':me in [a.lower() for a in assignees],
                'authored_by_me':(pr.get('author') or {}).get('login','').lower()==me,
                'base':pr.get('baseRefName',''),'head':pr.get('headRefName',''),
                'body_excerpt':body[:400]+('...' if len(body)>400 else '')}
        (mine if requested or reviewed else others).append(item)
    return {'login':login,'my_reviews':mine,'others':others}
def prs(args):
    login = run([gh_bin(),'api','user','--jq','.login'])
    data = gh_json('pr','list','--state','open','--limit',str(args.limit),'--json',
                   'number,title,body,url,author,assignees,isDraft,reviewRequests,baseRefName,headRefName')
    # GitHub search also covers review requests made to teams the user belongs to.
    search = lambda q: [x['number'] for x in gh_json('pr','list','--state','open','--limit',str(args.limit),'--search',q,'--json','number') or []]
    out = categorize(data or [], login, search('review-requested:@me'), search('reviewed-by:@me'))
    if args.json: print(json.dumps(out,indent=2)); return
    for label, key in ((f'Your reviews (@{login}, requested or already reviewed)','my_reviews'),('Other open PRs','others')):
        print(f'## {label}: {len(out[key])}')
        for p in out[key]:
            status = 'review requested' if p['review_requested_from_me'] else ''
            if p['reviewed_by_me']: status = 'reviewed, re-requested' if status else 'already reviewed'
            tags = [t for t,on in ((status,bool(status)),('draft',p['draft']),('via team',p['requested_via_team']),('assigned to you',p['assigned_to_me']),('authored by you',p['authored_by_me'])) if on]
            print(f"#{p['number']} {p['title']}  [by @{p['author']}{'; ' + ', '.join(tags) if tags else ''}]")
            print(f"    {p['body_excerpt'] or '(no description)'}")
        print()

def review_start(args):
    n = parse_pr(args.pr); key = f'pr-{n}'
    meta = gh_json('pr','view',str(n),'--json','number,title,url,author,state,isDraft,baseRefName,headRefName,headRefOid,isCrossRepository')
    if meta.get('state','OPEN') != 'OPEN' and not args.force:
        sys.exit(f"PR #{n} is {meta.get('state')}; pass --force to review anyway")
    s = load(); r = s['reviews'].get(key)
    if r and r['status'] in ('REVIEWING','AWAITING_ANSWERS') and not args.force:
        sys.exit(f'Review {key} is already {r["status"]}; pass --force to restart it')
    head_ref, base_ref = f'refs/workflow/pr/{n}/head', f'refs/workflow/pr/{n}/base'
    git('fetch','--no-tags',args.remote,f'+refs/pull/{n}/head:{head_ref}',f"+refs/heads/{meta['baseRefName']}:{base_ref}")
    head_sha = git('rev-parse',head_ref)
    wt = worktree_path(n); git('worktree','prune')
    if (wt/'.git').exists():
        git('checkout','--detach','--force',head_ref,cwd=wt); git('clean','-fd',cwd=wt)
    else:
        wt.parent.mkdir(parents=True,exist_ok=True); git('worktree','add','--detach',str(wt),head_ref)
    scratch = ROOT/'.workflow'/'runs'/key; scratch.mkdir(parents=True,exist_ok=True)
    rnd = (r or {}).get('round',0)+1
    r = r or {'pr':n,'events':[],'session':None}
    r.update({'title':meta.get('title',''),'url':meta.get('url',''),'author':(meta.get('author') or {}).get('login',''),
              'base':meta['baseRefName'],'head':meta.get('headRefName',''),'head_sha':head_sha,'base_ref':base_ref,'head_ref':head_ref,
              'worktree':str(wt),'scratch':str(scratch.resolve()),'report':str((scratch/f'review-r{rnd}.md').resolve()),
              'questions':str((scratch/f'questions-r{rnd}.md').resolve()),'status':'REVIEWING','verdict':None,'question_rounds':0,'round':rnd})
    log(r,'START',f'round {rnd} at {head_sha[:12]}')
    s['reviews'][key] = r; save(s)
    print(json.dumps({k:r[k] for k in ('pr','title','url','author','base','head','head_sha','base_ref','head_ref','worktree','scratch','report','questions','round')},indent=2))
def review_questions(args):
    s = load(); n = parse_pr(args.pr); r = review_entry(s,n)
    if r['status'] != 'REVIEWING': sys.exit(f"Review pr-{n} is {r['status']}, not REVIEWING")
    if r['question_rounds'] >= MAX_QUESTION_ROUNDS:
        sys.exit('Question budget exhausted: tell Reviewer to proceed with explicitly stated assumptions')
    r['question_rounds'] += 1; r['status'] = 'AWAITING_ANSWERS'; log(r,'QUESTIONS',f"round {r['question_rounds']}/{MAX_QUESTION_ROUNDS}")
    save(s); print(f"pr-{n}: questions round {r['question_rounds']}/{MAX_QUESTION_ROUNDS}")
def review_answered(args):
    s = load(); n = parse_pr(args.pr); r = review_entry(s,n)
    if r['status'] != 'AWAITING_ANSWERS': sys.exit(f"Review pr-{n} is {r['status']}, not AWAITING_ANSWERS")
    r['status'] = 'REVIEWING'; log(r,'ANSWERED',args.note or ''); save(s); print(f'pr-{n}: answers relayed, REVIEWING')
def review_verdict(args):
    s = load(); n = parse_pr(args.pr); r = review_entry(s,n)
    if r['status'] not in ('REVIEWING','DONE'): sys.exit(f"Review pr-{n} is {r['status']}; cannot record a verdict")
    r['status'] = 'DONE'; r['verdict'] = args.verdict; log(r,'VERDICT',args.verdict+(f': {args.note}' if args.note else ''))
    save(s); print(f'pr-{n}: {args.verdict}')
def review_session(args):
    s = load(); r = review_entry(s,parse_pr(args.pr)); r['session'] = args.terminal; save(s); print('Session recorded')
def review_status(args):
    s = load()
    if args.pr: print(json.dumps(review_entry(s,parse_pr(args.pr)),indent=2)); return
    print(json.dumps({k:{'title':v.get('title'),'status':v['status'],'verdict':v.get('verdict'),'round':v.get('round')} for k,v in s['reviews'].items()},indent=2))
def review_cleanup(args):
    s = load(); n = parse_pr(args.pr); r = review_entry(s,n)
    wt = pathlib.Path(r['worktree'])
    if wt.exists(): git('worktree','remove','--force',str(wt))
    git('worktree','prune')
    for ref in (r['head_ref'],r['base_ref']):
        subprocess.run(['git','update-ref','-d',ref],capture_output=True)
    r['status'] = 'CLOSED'; log(r,'CLEANUP','worktree and refs removed; scratch reports kept' if not args.purge else 'worktree, refs and scratch removed')
    if args.purge:
        import shutil; shutil.rmtree(r['scratch'],ignore_errors=True)
    save(s); print(f'pr-{n}: cleaned up')
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('init').set_defaults(fn=init)
    a=sub.add_parser('new'); a.add_argument('title'); a.set_defaults(fn=new)
    a=sub.add_parser('status'); a.add_argument('task',nargs='?'); a.set_defaults(fn=status)
    a=sub.add_parser('transition'); a.add_argument('task'); a.add_argument('to',choices=sorted(STATUSES)); a.add_argument('--approved',action='store_true'); a.add_argument('--captain-approved',action='store_true'); a.add_argument('--note'); a.set_defaults(fn=transition)
    a=sub.add_parser('mode'); a.add_argument('task'); a.add_argument('mode',choices=['light','full']); a.set_defaults(fn=mode)
    a=sub.add_parser('path'); a.add_argument('task'); a.set_defaults(fn=path)
    a=sub.add_parser('scratch'); a.add_argument('task'); a.set_defaults(fn=scratch)
    a=sub.add_parser('recovery-attempt'); a.add_argument('task'); a.add_argument('role',choices=['developer','tester']); a.set_defaults(fn=attempt)
    a=sub.add_parser('recovered'); a.add_argument('task'); a.add_argument('role',choices=['developer','tester']); a.set_defaults(fn=recovered)
    a=sub.add_parser('session'); a.add_argument('task'); a.add_argument('role',choices=['developer','tester']); a.add_argument('terminal'); a.set_defaults(fn=session)
    a=sub.add_parser('event'); a.add_argument('task'); a.add_argument('type'); a.add_argument('sender'); a.add_argument('id'); a.add_argument('--artifact',default=''); a.set_defaults(fn=event)
    a=sub.add_parser('commit'); a.add_argument('task'); a.add_argument('--message',required=True); a.add_argument('--body',required=True); a.add_argument('files',nargs='+'); a.set_defaults(fn=commit)
    a=sub.add_parser('prs',help='list open PRs grouped by assignment to the gh user'); a.add_argument('--json',action='store_true'); a.add_argument('--limit',type=int,default=100); a.set_defaults(fn=prs)
    a=sub.add_parser('review-start'); a.add_argument('pr'); a.add_argument('--remote',default='origin'); a.add_argument('--force',action='store_true'); a.set_defaults(fn=review_start)
    a=sub.add_parser('review-questions'); a.add_argument('pr'); a.set_defaults(fn=review_questions)
    a=sub.add_parser('review-answered'); a.add_argument('pr'); a.add_argument('--note'); a.set_defaults(fn=review_answered)
    a=sub.add_parser('review-verdict'); a.add_argument('pr'); a.add_argument('verdict',choices=VERDICTS); a.add_argument('--note'); a.set_defaults(fn=review_verdict)
    a=sub.add_parser('review-session'); a.add_argument('pr'); a.add_argument('terminal'); a.set_defaults(fn=review_session)
    a=sub.add_parser('review-status'); a.add_argument('pr',nargs='?'); a.set_defaults(fn=review_status)
    a=sub.add_parser('review-cleanup'); a.add_argument('pr'); a.add_argument('--purge',action='store_true',help='also delete scratch reports'); a.set_defaults(fn=review_cleanup)
    args=p.parse_args(); args.fn(args)
if __name__=='__main__': main()
