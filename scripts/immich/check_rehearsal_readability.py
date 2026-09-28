import pathlib,json,os,concurrent.futures
root=pathlib.Path('/opt/immich-rehearsal')
rows=[json.loads(s) for s in (root/'originals.jsonl').read_text().splitlines()]
def check(row):
 prefix='/usr/src/app/upload/'
 assert row['path'].startswith(prefix)
 rel=pathlib.PurePosixPath(row['path'][len(prefix):]);assert '..' not in rel.parts
 p=pathlib.Path('/mnt/Global_Share/Adam/Photos')/rel
 try:
  with p.open('rb') as f: f.read(1)
  return True
 except OSError:return False
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e: results=list(e.map(check,rows))
report={'expected':len(rows),'readable':sum(results),'failed':len(rows)-sum(results)}
(root/'readability.json').write_text(json.dumps(report));print(json.dumps(report))
raise SystemExit(0 if all(results) else 1)
