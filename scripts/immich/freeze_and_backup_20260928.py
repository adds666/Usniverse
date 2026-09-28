import pathlib,subprocess,json,datetime,hashlib,os,tarfile
os.umask(0o077)
root=pathlib.Path('/home/ubuntu/immich-cutover-20260928');root.mkdir(exist_ok=False)
def run(*a,**kw):return subprocess.run(a,check=True,**kw)
def query(s):return subprocess.check_output(['docker','exec','immich_postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','immich','-Atc',s],text=True)
names=['immich_server','immich_machine_learning','immich_postgres','immich_redis']
(root/'restart-policies.json').write_text(subprocess.check_output(['docker','inspect','--format','{{.Name}} {{.HostConfig.RestartPolicy.Name}}',*names],text=True))
try:
 run('docker','update','--restart=no',*names,stdout=subprocess.DEVNULL)
 run('docker','stop','--time','120','immich_server','immich_machine_learning',stdout=subprocess.DEVNULL)
 (root/'source-frozen.json').write_text(json.dumps({'frozenAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 with (root/'immich.dump').open('wb') as f:run('docker','exec','immich_postgres','pg_dump','-U','postgres','-d','immich','-Fc',stdout=f)
 sql="select json_build_object('path',\"originalPath\",'checksum',encode(checksum,'hex'),'algorithm','sha1') from asset order by id"
 (root/'originals.jsonl').write_text(query(sql))
 counts=json.loads(query('select json_build_object(\'assets\',(select count(*) from asset),\'files\',(select count(*) from asset_file),\'users\',(select count(*) from "user"),\'albums\',(select count(*) from album))'))
 conf=pathlib.Path('/home/ubuntu/DockerContainers/immich-app')
 with tarfile.open(root/'configuration.tgz','w:gz') as t:
  for name in ['docker-compose.yml','.env','postgres_password.txt','hwaccel.ml.yml']:
   if (conf/name).exists():t.add(conf/name,arcname=name)
 report={'phase':'frozen_backup_complete','counts':counts,'sha256':hashlib.file_digest((root/'immich.dump').open('rb'),'sha256').hexdigest(),'created':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (root/'status.json').write_text(json.dumps(report));print(json.dumps(report),flush=True)
except BaseException:
 run('docker','update','--restart=always',*names,stdout=subprocess.DEVNULL)
 run('docker','start','immich_server','immich_machine_learning',stdout=subprocess.DEVNULL)
 raise
