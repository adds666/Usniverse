import pathlib,subprocess,json,hashlib,os
os.umask(0o077)
root=pathlib.Path('/opt/immich'); recovery=root/'recovery'
expected=json.loads((recovery/'status.json').read_text())
assert expected['phase']=='frozen_backup_complete'
assert hashlib.file_digest((recovery/'immich.dump').open('rb'),'sha256').hexdigest()==expected['sha256']
def sql(s):return subprocess.run(['docker','exec','-i','immich-database-1','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','immich','-At'],input=s,text=True,capture_output=True,check=True).stdout.strip()
assert sql("select count(*) from information_schema.tables where table_schema='public'")=='0'
with (recovery/'immich.dump').open('rb') as dump,(root/'restore.log').open('w') as log:
 subprocess.run(['docker','exec','-i','immich-database-1','pg_restore','--exit-on-error','--no-owner','-U','postgres','-d','immich'],stdin=dump,stdout=log,stderr=log,check=True)
counts=json.loads(sql('select json_build_object(\'assets\',(select count(*) from asset),\'files\',(select count(*) from asset_file),\'users\',(select count(*) from "user"),\'albums\',(select count(*) from album));'))
assert counts==expected['counts'],(counts,expected['counts'])
raw=sql("select value from system_metadata where key='system-config'")
cfg=json.loads(raw) if raw else {}
(root/'restored-system-config.json').write_text(json.dumps(cfg))
cfg.setdefault('machineLearning',{})['urls']=['http://immich-machine-learning:3003']
cfg.setdefault('ffmpeg',{})['threads']=2
for name in ['backgroundTask','smartSearch','metadataExtraction','faceDetection','search','sidecar','library','migration','thumbnailGeneration','videoConversion','notifications','ocr','workflow','editor']:
 cfg.setdefault('job',{}).setdefault(name,{})['concurrency']=1
payload=json.dumps(cfg).replace("'","''")
sql("insert into system_metadata (key,value) values ('system-config','"+payload+"'::jsonb) on conflict (key) do update set value=excluded.value;")
report={'phase':'restored_not_started','counts':counts,'databaseSha256':expected['sha256']}
(root/'restore-complete.json').write_text(json.dumps(report));print(json.dumps(report))
