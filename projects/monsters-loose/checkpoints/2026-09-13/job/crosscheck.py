import whisper,torch,json,pathlib,gc
out=pathlib.Path(r'C:\audio\shared\amtw-runtime\jobs\monsters-loose-word-timing-20260913')
samples=pathlib.Path(r'C:\Users\arneg\OneDrive\Documents\Bitwig Studio\Projects\MonstersUndone.cleaned-groove\samples')
torch.set_num_threads(6)
for name,role,filename in [('large-v3-turbo','lead-original','Set the Monsters Loose (Lead Vocal).wav'),('medium','lead-medium','Set the Monsters Loose (Lead Vocal) - Renaissance.wav')]:
 model=whisper.load_model(name,device='cuda',download_root=r'C:\Users\arneg\.cache\whisper')
 print('TRANSCRIBING',role,flush=True)
 result=model.transcribe(str(samples/filename),language='en',word_timestamps=True,condition_on_previous_text=False,temperature=0,verbose=False)
 (out/f'{role}.whisper.raw.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
 print(role,result['text'],flush=True)
 del model;gc.collect();torch.cuda.empty_cache()
