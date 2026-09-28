import subprocess,json,pathlib
root=pathlib.Path('/opt/immich/recovery')
def sql(s):return subprocess.run(['docker','exec','-i','immich-database-1','psql','-X','-v','ON_ERROR_STOP=1','-U','postgres','-d','immich','-At'],input=s,text=True,capture_output=True,check=True).stdout.strip()
cols=json.loads(sql("select json_agg(t) from (select table_name,column_name from information_schema.columns where table_schema='public' and table_name in ('asset','asset_file','person','user') and column_name ilike '%path' and data_type in ('text','character varying')) t"))
count=0
with (root/'media-paths.jsonl').open('w') as f:
 for c in cols:
  table=c['table_name'];column=c['column_name']
  data=sql(f'''select json_build_object('path',"{column}",'table','{table}','column','{column}') from "{table}" where "{column}" is not null and "{column}" <> '';''')
  if data:f.write(data+'\n');count+=len(data.splitlines())
print('Database-referenced media records:',count)
