import json,subprocess,pathlib
code='''import requests,json
r=requests.post("http://127.0.0.1:3003/predict",data={"entries":json.dumps({"clip":{"textual":{"modelName":"ViT-B-32__openai"}}}),"text":"a landscape"},timeout=900)
r.raise_for_status()
d=r.json();print(json.dumps({"httpStatus":r.status_code,"resultKeys":list(d),"resultLength":len(d.get("clip",[]))}))'''
r=subprocess.run(['docker','exec','immich-rehearsal-immich-machine-learning-1','python','-c',code],capture_output=True,text=True)
pathlib.Path('/opt/immich-rehearsal/ml-test.log').write_text(r.stdout+r.stderr)
if r.returncode:print('ML inference failed; see private ml-test.log');raise SystemExit(r.returncode)
pathlib.Path('/opt/immich-rehearsal/ml-validation.json').write_text(r.stdout);print(r.stdout)
