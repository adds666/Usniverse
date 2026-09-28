import subprocess,json,uuid,secrets,hashlib,urllib.request,pathlib,time
base=pathlib.Path('/opt/immich-rehearsal')
def sql(s):
 r=subprocess.run(['docker','exec','-i','immich-rehearsal-database-1','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','immich','-At'],input=s,text=True,capture_output=True,check=True);return r.stdout.strip()
def get(path,key=None):
 req=urllib.request.Request('http://127.0.0.1:2283/api/'+path,headers={'x-api-key':key} if key else {})
 with urllib.request.urlopen(req,timeout=120) as r:return r.read()
report={'version':json.loads(get('server/version')),'ping':json.loads(get('server/ping'))}
rows=json.loads(sql('select coalesce(json_agg(t),\'[]\') from (select id,"ownerId",encode(checksum,\'hex\') checksum from asset where type=\'IMAGE\' and "deletedAt" is null order by id limit 3) t;'))
matched=0
for row in rows:
 key=secrets.token_hex(32); kid=str(uuid.uuid4());hashed=hashlib.sha256(key.encode()).hexdigest()
 sql(f'''insert into api_key (id,name,key,"userId",permissions) values ('{kid}','isolated-rehearsal-test',decode('{hashed}','hex'),'{row['ownerId']}',ARRAY['all']);''')
 try:
  blob=get('assets/'+row['id']+'/original',key)
  assert hashlib.sha1(blob).hexdigest()==row['checksum'];matched+=1
 finally: sql(f"delete from api_key where id='{kid}';")
report['originalsDownloadedAndChecksumMatched']=matched
(base/'api-validation.json').write_text(json.dumps(report));print(json.dumps(report))
