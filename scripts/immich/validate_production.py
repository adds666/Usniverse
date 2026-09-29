import pathlib,subprocess,json,hashlib,secrets,uuid,urllib.request,datetime,zlib,struct,time
root=pathlib.Path('/opt/immich')
def sql(s):return subprocess.run(['docker','exec','-i','immich-database-1','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','immich','-At'],input=s,text=True,capture_output=True,check=True).stdout.strip()
def request(path,key=None,method='GET',data=None,ctype=None):
 headers={}
 if key:headers['x-api-key']=key
 if ctype:headers['Content-Type']=ctype
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:2283/api/'+path,headers=headers,data=data,method=method),timeout=120) as r:return r.status,r.read()
report={'ping':json.loads(request('server/ping')[1]),'version':json.loads(request('server/version')[1])}
expected=int(sql('select count(*) from asset'))
rows=json.loads(sql('select json_agg(t) from (select id,"ownerId",encode(checksum,\'hex\') checksum from asset where type=\'IMAGE\' and "deletedAt" is null order by "createdAt" desc limit 5) t;'))
matched=0
for row in rows:
 token=secrets.token_hex(32);kid=str(uuid.uuid4());hashed=hashlib.sha256(token.encode()).hexdigest()
 sql(f'''insert into api_key(id,name,key,"userId",permissions) values ('{kid}','cutover-read-validation',decode('{hashed}','hex'),'{row['ownerId']}',ARRAY['all']);''')
 try:assert hashlib.sha1(request('assets/'+row['id']+'/original',token)[1]).hexdigest()==row['checksum'];matched+=1
 finally:sql(f"delete from api_key where id='{kid}';")
report['originalsDownloadedAndChecksumMatched']=matched
owner=rows[0]['ownerId'];token=secrets.token_hex(32);kid=str(uuid.uuid4());hashed=hashlib.sha256(token.encode()).hexdigest()
sql(f'''insert into api_key(id,name,key,"userId",permissions) values ('{kid}','cutover-upload-validation',decode('{hashed}','hex'),'{owner}',ARRAY['all']);''')
asset=None
try:
 def chunk(t,d):return struct.pack('!I',len(d))+t+d+struct.pack('!I',zlib.crc32(t+d)&0xffffffff)
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',8,8,8,2,0,0,0))+chunk(b'tEXt',b'Validation\x00'+uuid.uuid4().hex.encode())+chunk(b'IDAT',zlib.compress(b''.join(b'\x00'+bytes([0,128,255])*8 for _ in range(8))))+chunk(b'IEND',b'')
 boundary=uuid.uuid4().hex;parts=[];now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 fields={'fileCreatedAt':now,'fileModifiedAt':now,'isFavorite':'false'}
 if report['version']['major'] < 3:fields.update({'deviceAssetId':str(uuid.uuid4()),'deviceId':'usniverse-cutover-validation'})
 for k,v in fields.items():parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
 parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="assetData"; filename="usniverse-cutover-validation.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+png+b'\r\n');parts.append(f'--{boundary}--\r\n'.encode())
 status,data=request('assets',token,'POST',b''.join(parts),'multipart/form-data; boundary='+boundary);result=json.loads(data)
 assert status==201 and result.get('status')=='created',result
 asset=result['id'];assert str(uuid.UUID(asset))==asset
 assert hashlib.sha1(request('assets/'+asset+'/original',token)[1]).digest()==hashlib.sha1(png).digest()
 report['syntheticUploadAndDownloadPassed']=True
finally:
 if asset:
  request('assets',token,'DELETE',json.dumps({'ids':[asset],'force':True}).encode(),'application/json')
  for _ in range(60):
   if sql(f"select count(*) from asset where id='{asset}'")=='0':break
   time.sleep(2)
  assert sql(f"select count(*) from asset where id='{asset}'")=='0','Synthetic test asset cleanup pending'
 sql(f"delete from api_key where id='{kid}';")
report['syntheticAssetRemoved']=True
report['finalAssetCount']=int(sql('select count(*) from asset'))
assert report['finalAssetCount']>=expected
(root/'production-validation.json').write_text(json.dumps(report));print(json.dumps(report))
