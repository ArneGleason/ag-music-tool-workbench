"""Task-specific reconciliation; original recognition is retained beside this file."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
raw = json.loads((ROOT/'lead-original.whisper.raw.json').read_text(encoding='utf-8'))
# Explicit performance rows: rough SOURCE-audio windows, not final word edges.
# Wording is reconciled with the arranged worksheet and three ASR passes.
# No written lyric is assumed present just because it appears in the sheet.
rows = [
(0,1.7,'Undone.'),
(8.1,14.8,'Undone until we set the monsters loose, oh my.'),
(15.8,20.2,'La da da na na na na na na.'),
(20.8,25.4,'Got the hang of every face you made.'),
(25.7,30.6,"Have the knot before it's time to tie."),
(31.2,35.8,"Unpronounced announcement that you've come undone."),
(36.3,40.8,'Undone, undone, undone, undone.'),
(41.9,45.5,'What kind of monster would you like to make now?'),
(45.1,48.0,'That last one set the town on fire.'),
(47.5,50.7,'Now make one that is twice as mean.'),
(50.1,53.6,'And fifty feet or maybe higher.'),
(54.4,61.1,'Undone until we set the monsters loose, oh my.'),
(61.7,65.4,'Got a zoo here to keep the monsters in.'),
(64.9,67.6,'So we can see them stomping around.'),
(67.1,70.4,'Watch them try to eat the keeper whole.'),
(69.8,73.9,'Zoo keeper keeps them all from breaking out.'),
(73.3,78.0,'One, one, almost, just, just now, got out.'),
(77.7,81.9,"Your eye roll tells me what, what your face can't say."),
(81.3,84.5,"You can't believe they even call that place a zoo."),
(83.8,87.1,'Choose your favorite monster beast.'),
(86.5,90.0,'Suit the way you wanna be, be, be.'),
(89.3,92.2,'Hunting Ed, head hunting Ted.'),
(91.7,95.5,"Hide and seek's the game that monsters play."),
(95.7,97.7,'And play.'),
(98.3,100.5,'And play.'),
(100.9,103.9,'And play, baby.'),
(103.7,107.2,'Five, four, three more to go.'),
(106.6,108.7,'Now only two.'),
(108.6,113.8,"The final fight between the meanest ones, I'll bet you."),
(113.2,117.9,'One has that kick, that kick that knock you down.'),
(117.4,120.3,'Down, down, down, down.'),
(119.8,123.6,'What kind of monster would you like to make now?'),
(123.2,126.0,'That last one set the town on fire.'),
(125.6,128.6,'Now make one that is twice as mean.'),
(128.1,131.3,'And fifty feet or maybe higher.'),
(131.0,133.8,'Undone, undone, undone, undone.'),
(133.3,137.3,'Until we set the monsters loose.'),
(137.2,139.6,'Oh my.'),
(140.4,144.9,'They can shrink down to fit in any scene, just as mean.'),
(145.4,150.0,'Grow up to be ten times or more.'),
(150.8,154.5,'Change to smoke and drift through anything.'),
(154.3,157.2,'Through the keyhole in the steel door.'),
(156.6,160.5,'No way! Yes way!'),
(160.9,166.8,"You're right, just right now, but you know I don't mind."),
(166.1,171.6,'Spend time watching monsters crash around.'),
(171.0,175.1,'Got the hang of every face.'),
(175.9,179.0,'You made.'),
(179.0,182.8,'Undone.'),
(182.8,186.6,'Choose your favorite monster beast.'),
(186.1,189.8,'Suit the way you wanna be, be, be.'),
(189.3,192.1,'Hunting Ed, head hunting Ted.'),
(191.4,195.4,"Hide and seek's the game that monsters play."),
(195.4,197.6,'And play.'),
(197.3,200.3,'And play.'),
(199.9,202.6,'And play.'),
(202.2,204.3,'And play.'),
(205.8,208.5,'Undone.'),
]
uncertain = {
2:'Wordless ad-lib detected by original/turbo and clean/medium; la/da/na spelling and syllable count provisional.',
6:'Four repeat candidates in both turbo passes; medium detects three. Verify count.',
8:'Worksheet says town of fire; ASR supports on fire. Performance wording provisional.',
14:'Whole appears in the worksheet and clean/turbo, omitted by other passes; verify.',
20:'Worksheet has be be be; turbo collapses repeats. Verify against audio.',
25:'Baby is an extra candidate in both turbo passes; medium reports repeated play instead.',
30:'Four down repeats after the preceding down in all three passes; verify boundaries.',
32:'Second chorus uses worksheet wording to repair severe ASR errors; verify That/The and on/of.',
35:'Repeat/vocalization unresolved: original says na syllables; medium says on and on; worksheet has undone. Hypothesis only.',
38:'Any scene from lyric sheet replaces ASR anything; They/It and syllable boundary need listening.',
43:'But you from sheet versus Let/That in ASR; verify performed connector.',
45:'Sheet resolves badly recognized reprise; verify stretched face.',
47:'Sheet-only candidate in an ASR gap; retain as a hypothesis until acoustic evidence supports it.',
49:'Repeat count be be be supported by original/turbo and medium; verify.',
52:'Closing and play candidate from original; other passes partly omit it.',
53:'Closing and play candidate; ASR segmentation disagrees.',
54:'Closing and play candidate; ASR segmentation disagrees.',
55:'Closing and play candidate; ASR segmentation disagrees.',
56:'Original/turbo says I am no; worksheet says Undone. Verify final word.',
}
phrases=[]
for i,(start,end,text) in enumerate(rows):
 refs=[{'start':s['start'],'end':s['end'],'text':s['text'].strip()} for s in raw['segments'] if min(end,s['end'])-max(start,s['start'])>0.2]
 phrases.append(dict(id=f'lead-{i+1:03}',start=start,end=end,text=text,kind='vocalization' if i==2 else 'lyric',
                     text_status='needs_review' if i in uncertain else 'lyric_reconciled',
                     note=uncertain.get(i,''),raw_candidates=refs))
doc=dict(schema_version=1,timebase='source_seconds',role='lead',
         lyric_source='https://docs.google.com/document/d/1qY_kvt5ykP-dRfeW8F32nODp9pwMCTr7itkDVvTKoKk/edit',
         review_status='machine_reconciled_not_listening_verified',phrases=phrases)
(ROOT/'lead.performance.json').write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8')
print('Wrote',len(phrases),'performance phrase hypotheses')
