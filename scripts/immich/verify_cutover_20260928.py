import pathlib,subprocess,json,hashlib,os,datetime,concurrent.futures
os.umask(0o077)
root=pathlib.Path('/srv/immich-cutover-backup');recovery=root/'recovery/cutover-20260928';media=root/'media'
def status(phase,**kw):
 p=root/'cutover-status.tmp';p.write_text(json.dumps({'phase':phase,'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw}));p.replace(root/'status.json')
def relative(path):
 prefix='/usr/src/app/upload/';assert path.startswith(prefix)
 rel=pathlib.PurePosixPath(path[len(prefix):]);assert not rel.is_absolute() and '..' not in rel.parts
 return str(rel)
def copy_exact(paths):
 if not paths:return
 manifest=root/'repair-files.list';manifest.write_bytes(b'\0'.join(p.encode() for p in sorted(paths))+b'\0')
 with (root/'logs/cutover-direct-copy.log').open('a') as log:
  subprocess.run(['rsync','-a','--numeric-ids','--ignore-times','--from0','--files-from='+str(manifest),'/mnt/immich-backup-source/Adam/Photos/',str(media)+'/'],stdout=log,stderr=log,check=True)
try:
 assert subprocess.check_output(['findmnt','-n','-o','SOURCE','-T',str(root)],text=True).strip()=='rpool/immich-cutover-backup'
 expected=json.loads((recovery/'status.json').read_text());assert expected['phase']=='frozen_backup_complete'
 assert hashlib.file_digest((recovery/'immich.dump').open('rb'),'sha256').hexdigest()==expected['sha256']
 rows=[json.loads(x) for x in (recovery/'originals.jsonl').read_text().splitlines()]
 assert len(rows)==expected['counts']['assets']
 originals={relative(r['path']):r['checksum'] for r in rows};assert len(originals)==len(rows) and all(r['algorithm']=='sha1' for r in rows)
 records=[json.loads(x) for x in (recovery/'media-paths.jsonl').read_text().splitlines()]
 assert sum(r['table']=='asset_file' for r in records)==expected['counts']['files']
 paths={relative(r['path']) for r in records}|set(originals)
 missing={p for p in paths if not (media/p).is_file()}
 status('copying_missing_references',missing=len(missing));copy_exact(missing)
 def check(rel):
  p=media/rel;assert p.resolve().is_relative_to(media.resolve())
  h1=hashlib.sha1() if rel in originals else None;h256=hashlib.sha256();size=0
  with p.open('rb') as f:
   while chunk:=f.read(4*1024*1024):
    h256.update(chunk);size+=len(chunk)
    if h1:h1.update(chunk)
  return {'path':rel,'bytes':size,'sha256':h256.hexdigest()},h1 is None or h1.hexdigest()==originals[rel]
 status('verifying',expected=len(originals),referencedFiles=len(paths))
 bad=[];results=[];matched=0
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for i,(record,match) in enumerate(pool.map(check,sorted(paths)),1):
   results.append(record)
   if not match:bad.append(record['path'])
   elif record['path'] in originals:matched+=1
   if i%1000==0:status('verifying',filesChecked=i,referencedFiles=len(paths),originalsMatched=matched,originalsExpected=len(originals))
 if bad:
  status('repairing_originals',count=len(bad));copy_exact(set(bad))
  replacements={}
  for p in bad:
   record,match=check(p);assert match,'Original checksum mismatch after direct copy';matched+=1;replacements[p]=record
  results=[replacements.get(r['path'],r) for r in results]
 assert matched==len(originals)
 with (root/'cutover-files.sha256.jsonl').open('w') as f:
  for r in results:f.write(json.dumps(r)+'\n')
 report={'phase':'verified','originalsExpected':len(originals),'originalsMatched':matched,'failed':0,'referencedFilesHashed':len(paths),'referencesInitiallyMissing':len(missing),'originalsRepaired':len(bad),'databaseSha256':expected['sha256'],'counts':expected['counts'],'method':'database-referenced media verified against frozen database; prior full-folder backup retained'}
 (root/'cutover-verification.json').write_text(json.dumps(report))
 snap='rpool/immich-cutover-backup@verified-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 subprocess.run(['zfs','snapshot',snap],check=True);subprocess.run(['zfs','hold','immich-recovery',snap],check=True)
 status('verified',snapshot=snap,**{k:v for k,v in report.items() if k!='phase'});print(json.dumps(report))
except BaseException as e:
 status('failed',error=type(e).__name__);raise
