#!/usr/bin/env python3
"""Small, dependency-free task registry and safe Git commit helper."""
import argparse, datetime, json, os, pathlib, re, subprocess, sys
ROOT = pathlib.Path.cwd()
STATE = ROOT / '.workflow' / 'state.json'
TASKS = ROOT / 'tasks'
STATUSES = {'DRAFT','READY','IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW','COMMITTING','COMPLETED','BLOCKED'}
ALLOWED = {'DRAFT':{'READY'}, 'READY':{'IMPLEMENTING','DRAFT'}, 'IMPLEMENTING':{'VALIDATING','BLOCKED'}, 'VALIDATING':{'IMPLEMENTING','CAPTAIN_REVIEW','BLOCKED'}, 'CAPTAIN_REVIEW':{'IMPLEMENTING','COMMITTING','BLOCKED'}, 'COMMITTING':{'COMPLETED','BLOCKED'}, 'BLOCKED':{'IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW'}, 'COMPLETED':set()}
def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {'tasks':{},'active_task':None}
def save(s):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(s,indent=2)+'\n'); tmp.replace(STATE)
def taskfile(t): return TASKS / (t+'.md')
def init(args):
    TASKS.mkdir(exist_ok=True); STATE.parent.mkdir(exist_ok=True); save(load()); print('Initialized workflow registry')
def new(args):
    s=load(); n=max([int(k.split('-')[1]) for k in s['tasks'] if re.fullmatch(r'task-\d+',k)] or [0])+1
    t=f'task-{n:03d}'; s['tasks'][t]={'title':args.title,'status':'DRAFT','dependencies':[],'related':[],'attempts':{'developer':0,'tester':0},'validation_round':0,'sessions':{},'events':[]}
    TASKS.mkdir(exist_ok=True); template=(ROOT/'.workflow'/'task-template.md').read_text()
    taskfile(t).write_text(template.replace('{{TASK_ID}}',t).replace('{{TITLE}}',args.title).replace('{{DATE}}',datetime.date.today().isoformat()))
    save(s); print(t)
def status(args):
    s=load()
    if args.task:
        print(json.dumps(s['tasks'].get(args.task,{}),indent=2)); return
    print(json.dumps({'active_task':s['active_task'],'tasks':{k:v['status'] for k,v in s['tasks'].items()}},indent=2))
def transition(args):
    s=load(); t=args.task; d=s['tasks'].get(t)
    if not d: sys.exit('Unknown task')
    old=d['status']; new=args.to
    if new not in ALLOWED[old]: sys.exit(f'Invalid transition: {old} -> {new}')
    if new in {'IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW','COMMITTING'} and s['active_task'] not in (None,t): sys.exit('Another task is active')
    if new=='IMPLEMENTING' and old=='READY' and not args.approved: sys.exit('Requires --approved: user approved specification')
    if new=='COMMITTING' and not args.captain_approved: sys.exit('Requires --captain-approved: Captain reviewed implementation')
    if new in {'IMPLEMENTING','VALIDATING','CAPTAIN_REVIEW','COMMITTING'}: s['active_task']=t
    if new=='COMPLETED': s['active_task']=None
    d['status']=new; d['events'].append({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'from':old,'to':new,'note':args.note or ''})
    save(s); print(f'{t}: {old} -> {new}')
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
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('init').set_defaults(fn=init)
    a=sub.add_parser('new'); a.add_argument('title'); a.set_defaults(fn=new)
    a=sub.add_parser('status'); a.add_argument('task',nargs='?'); a.set_defaults(fn=status)
    a=sub.add_parser('transition'); a.add_argument('task'); a.add_argument('to',choices=sorted(STATUSES)); a.add_argument('--approved',action='store_true'); a.add_argument('--captain-approved',action='store_true'); a.add_argument('--note'); a.set_defaults(fn=transition)
    a=sub.add_parser('recovery-attempt'); a.add_argument('task'); a.add_argument('role',choices=['developer','tester']); a.set_defaults(fn=attempt)
    a=sub.add_parser('recovered'); a.add_argument('task'); a.add_argument('role',choices=['developer','tester']); a.set_defaults(fn=recovered)
    a=sub.add_parser('session'); a.add_argument('task'); a.add_argument('role',choices=['developer','tester']); a.add_argument('terminal'); a.set_defaults(fn=session)
    a=sub.add_parser('event'); a.add_argument('task'); a.add_argument('type'); a.add_argument('sender'); a.add_argument('id'); a.add_argument('--artifact',default=''); a.set_defaults(fn=event)
    a=sub.add_parser('commit'); a.add_argument('task'); a.add_argument('--message',required=True); a.add_argument('--body',required=True); a.add_argument('files',nargs='+'); a.set_defaults(fn=commit)
    args=p.parse_args(); args.fn(args)
if __name__=='__main__': main()
