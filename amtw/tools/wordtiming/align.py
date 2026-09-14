"""WhisperX alignment-only worker in the recovered speech runtime.

The ASR draft is not the performed lyric. This worker consumes a separately
reconciled transcript, preserving its uncertainty and provenance. Missing
timings remain missing: interpolation and next-onset duration filling would
repeat the failure of the Rivers lyric animation. CTC confidence is NOT a
calibrated probability of correct singing timing or proof a word was sung.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys


def stamp(sec):
    ms = round(sec * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'


def run(args):
    sys.path.insert(0, str(Path(args.runtime)/'tools/word-timing'))
    import numpy as np
    import soundfile as sf
    import torch
    import whisper
    from whisperx.alignment import align, load_align_model
    import nltk
    nltk.data.path.insert(0, str(Path(args.runtime)/'models/word-timing/nltk'))
    nltk.download('punkt_tab', download_dir=nltk.data.path[0], quiet=True)
    torch.set_num_threads(6)
    source = Path(args.audio).resolve()
    spec = json.loads(Path(args.performance).read_text(encoding='utf-8-sig'))
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    wav = whisper.load_audio(str(source))
    duration = len(wav)/16000
    if not math.isfinite(args.offset) or args.offset < 0:
        raise ValueError('Offset must be finite and nonnegative')
    for p in spec['phrases']:
        if not (0 <= p['start'] < p['end'] <= duration) or not p['text'].strip():
            raise ValueError(f'Invalid phrase window or text: {p}')
    model, metadata = load_align_model('en', 'cuda', model_dir=str(Path(args.runtime)/'models/word-timing'))
    phrases, words = [], []
    for index, p in enumerate(spec['phrases']):
        # Unresolved nonlexical events get an interval, not invented word edges.
        result = ({'segments': [], 'word_segments': []} if p.get('kind') == 'unresolved_event' else align([dict(start=p['start'], end=p['end'], text=p['text'])],
                       model, metadata, wav, 'cuda', interpolate_method='ignore',
                       return_char_alignments=True))
        item = dict(p)
        item['window_source_start'], item['window_source_end'] = p['start'], p['end']
        item.pop('start'); item.pop('end')
        item['words'], item['alignment_segments'] = [], result['segments']
        heard = result['word_segments']
        # Alignment failure must not silently discard an entire authored phrase.
        if not heard and p.get('kind') != 'unresolved_event':
            heard = [{'word': token} for token in p['text'].split()]
        for wi, w in enumerate(heard):
            flags = []
            s, e = w.get('start'), w.get('end')
            valid = s is not None and e is not None and math.isfinite(s) and math.isfinite(e) and e > s
            if not valid:
                flags.append('unaligned'); s = e = None
            score = w.get('score')
            if score is None or score < .55:
                flags.append('weak_acoustic_match')
            if p.get('text_status') == 'needs_review':
                flags.append('text_review')
            if p.get('kind') == 'vocalization':
                flags.append('vocalization_syllables_provisional')
            if valid:
                if e-s < .06: flags.append('very_short')
                if e-s > .65: flags.append('sustain_review')
                if abs(s-p['start']) < .04 or abs(e-p['end']) < .04:
                    flags.append('window_edge')
            record = dict(id=f"{p['id']}-w{wi+1:03}", phrase_id=p['id'], role=spec.get('role','lead'),
                          text=w['word'], kind=p.get('kind','lyric'),
                          source_start=s, source_end=e,
                          start=round(s+args.offset,6) if valid else None,
                          end=round(e+args.offset,6) if valid else None,
                          alignment_score=score, flags=flags, status='needs_review' if flags else 'machine_aligned')
            item['words'].append(record); words.append(record)
        valid_words = [w for w in item['words'] if w['start'] is not None]
        item['start'] = min((w['start'] for w in valid_words), default=p['start']+args.offset)
        item['end'] = max((w['end'] for w in valid_words), default=p['end']+args.offset)
        # A separate energy extent helps spot held vowels that CTC abbreviates.
        # It is NOT automatically merged into word timings: breath, bleed and
        # reverb can be audible beyond the actual articulation.
        crop = wav[int(p['start']*16000):int(p['end']*16000)]
        frames = len(crop)//160
        if frames:
            rms = np.sqrt(np.mean(crop[:frames*160].reshape(-1,160)**2,axis=1))
            active = np.flatnonzero(rms > max(10**(-48/20),float(rms.max())*.05))
            if len(active):
                item['audible_extent_candidate'] = dict(start=round(p['start']+active[0]*.01+args.offset,6),
                                                       end=round(p['start']+(active[-1]+1)*.01+args.offset,6),
                                                       method='10ms energy, max(-48dBFS, local peak RMS minus 26dB); not verified word edges')
                if valid_words and item['audible_extent_candidate']['end']-item['end']>.2:
                    valid_words[-1]['flags'].append('audible_tail_after_alignment')
                    valid_words[-1]['status']='needs_review'
                if valid_words and item['start']-item['audible_extent_candidate']['start']>.2:
                    valid_words[0]['flags'].append('audible_attack_before_alignment')
                    valid_words[0]['status']='needs_review'
        phrases.append(item)
        print(f"{index+1}/{len(spec['phrases'])} {item['start']:.3f}-{item['end']:.3f} {p['text']}",flush=True)
    # Overlap is reported, not silently clamped. It can expose a repeated word
    # aligned twice in adjacent windows, or be a real separate vocal layer.
    prev = None
    for w in words:
        if w['start'] is not None:
            if prev and w['start'] < prev['end']-.025:
                w['flags'].append('overlap_previous_word'); w['status']='needs_review'
            prev=w
    with source.open('rb') as f:
        source_hash = hashlib.file_digest(f,'sha256').hexdigest()
    data=dict(schema_version=1, timebase='master_seconds', role=spec.get('role','lead'),
              source_audio=str(source), source_sha256=source_hash,
              source_duration=duration, stem_offset_seconds=args.offset, lyric_source=spec.get('lyric_source'),
              master_preview=spec.get('master_preview'),
              method='WhisperX 3.8.6 / WAV2VEC2_ASR_BASE_960H; no timestamp interpolation; independent word starts/ends',
              timing_status='first_pass_not_listening_verified', phrases=phrases, words=words)
    (out/'words.json').write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    columns=['id','phrase_id','role','text','kind','start','end','source_start','source_end','alignment_score','status','flags']
    with (out/'words.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for w in words: writer.writerow({**w,'flags':'; '.join(w['flags'])})
    vtt=['WEBVTT','']
    for p in phrases:
        vtt.extend([p['id'],f"{stamp(p['start'])} --> {stamp(p['end'])}",p['text'],''])
    (out/'phrases.vtt').write_text('\n'.join(vtt),encoding='utf-8')
    lines=['# Performed lyric timing review','',
           'First acoustic alignment pass; no listening verification. Times are master-relative seconds.',
           'Word ends are independent. Scores are acoustic alignment diagnostics, not correctness probabilities.',
           '',f"Source: {source}",f"Stem offset: {args.offset:.9f} s",'',
           '| Phrase | Master start–end | Performed text hypothesis | Review note |','|---|---:|---|---|']
    for p in phrases:
        flags=sorted({f for w in p['words'] for f in w['flags']})
        lines.append(f"| {p['id']} | {p['start']:.3f}–{p['end']:.3f} | {p['text']} | {p.get('note','')} {'; '.join(flags)} |")
    (out/'review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Audition proxy has the same video clock, with sample-rounded leading pad.
    stereo,sr=sf.read(source,always_2d=True)
    sf.write(out/'vocal.wav',np.pad(stereo,((round(args.offset*sr),0),(0,0))),sr,subtype='PCM_16')
    page=Path(__file__).with_name('review.html').read_text(encoding='utf-8')
    # A JSON data script escapes '<' so lyric text cannot close the script tag.
    page=page.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
    (out/'review.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(words=len(words),unaligned=sum(w['start'] is None for w in words),
                         flagged=sum(bool(w['flags']) for w in words))))
    print(out/'review.html');print(out/'words.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['audio','performance','out','runtime']: parser.add_argument('--'+name,required=True)
    parser.add_argument('--offset',type=float,default=0)
    run(parser.parse_args())
