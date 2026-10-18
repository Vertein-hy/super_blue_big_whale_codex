'use strict';
(() => {
  const {config, source} = window.PET_DATA;
  const el = id => document.getElementById(id);
  const cache = new Map();
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let mode = 'native', index = 0, playing = !reduced, images = [], loaded = false;
  let previous = null, accumulator = 0, generation = 0, background = 0;
  const backgrounds = ['checker','light','dark'];
  const names = ['棋盘','浅色','深色'];
  const contexts = [];
  for (const pet of config.pets) {
    const card = document.createElement('article'); card.className = 'card';
    const top = document.createElement('div'); top.className='card-top';
    const title = document.createElement('h2'); title.textContent=pet.displayName.replace('小鲸 · ','');
    const pill = document.createElement('span'); pill.className='pill'; pill.textContent='透明素材';
    top.append(title,pill);
    const stage=document.createElement('div'); stage.className='stage checker';
    const canvas=document.createElement('canvas'); canvas.width=512; canvas.height=556;
    canvas.setAttribute('aria-label',pet.displayName+'，点击挥手');canvas.setAttribute('role','button');canvas.tabIndex=0;
    canvas.addEventListener('click',wave);canvas.addEventListener('keydown',event=>{
      if(event.key==='Enter'||event.key===' '){event.preventDefault();wave();}
    });
    stage.append(canvas); contexts.push(canvas.getContext('2d'));
    const bottom=document.createElement('div');bottom.className='card-bottom';
    const id=document.createElement('code');id.textContent=pet.id;
    const hint=document.createElement('span');hint.textContent='点一下，向你挥手';
    bottom.append(id,hint);card.append(top,stage,bottom);el('cards').append(card);
  }
  function loadImage(path) {
    if(!cache.has(path))cache.set(path,new Promise((resolve,reject)=>{
      const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('无法读取 '+path+'。请完整解压工程，不要只打开 ZIP 里的 HTML。'));img.src=path;
    }));return cache.get(path);
  }
  function row(){return config.rows.find(r=>r.state===el('action').value)||config.rows[0];}
  function action(){return source.outfits[0].actions.find(a=>a.id===el('action').value)||source.outfits[0].actions[0];}
  function durations(){return mode==='native'?row().durations_ms:Array(24).fill(1000/action().fps);}
  function updateInfo(){const n=durations().length;el('scrub').max=String(n-1);el('scrub').value=String(index);el('frame-info').textContent=String(index+1).padStart(2,'0')+' / '+String(n).padStart(2,'0')+' 帧';el('play').textContent=playing?'暂停':'播放';}
  function draw(){
    if(!loaded)return;
    for(let i=0;i<contexts.length;i++){
      const ctx=contexts[i];const cw=ctx.canvas.width,ch=ctx.canvas.height;ctx.clearRect(0,0,cw,ch);
      if(mode==='native'){
        const r=row();ctx.drawImage(images[i],index*192,r.row*208,192,208,0,0,cw,ch);
      }else{
        const size=512;ctx.drawImage(images[i],(index%6)*320,Math.floor(index/6)*320,320,320,0,(ch-size)/2,size,size);
      }
    }updateInfo();
  }
  async function selectAction(){
    const ticket=++generation;loaded=false;index=0;accumulator=0;previous=null;el('error').hidden=true;
    const paths=config.pets.map(p=>mode==='native'?'pets/'+p.id+'/spritesheet.webp':
      source.outfits.find(o=>o.id===p.source_outfit).actions.find(a=>a.id===el('action').value).sheet);
    el('status').textContent='正在读取本地素材…';updateInfo();
    try{
      const next=await Promise.all(paths.map(loadImage));if(ticket!==generation)return;
      images=next;loaded=true;draw();
      el('status').textContent=(mode==='native'?'按已核验的原生行序和逐帧时长循环预览。':'当前为原始 24 帧循环预览；不代表 Codex 支持 24 帧自定义状态。')+(reduced?' 已根据系统减少动态效果设置默认暂停。':'');
      el('note').textContent=mode==='native'?
        '本包采用 8×9 的 V1 兼容格式，不含 V2 的 16 向视线。工作中和审阅中复用了不同片段的歪头眨眼；左移动水平翻转了服饰配件。此页只展示图集，不模拟真实 Codex 事件触发。':
        '全部 27 组动作各保留 24 帧。轻快小跑、困困点头、开心摇摆保留在原始素材中，并不拥有单独的 Codex 原生触发状态。工具可将无损精灵图重新导出为 648 张透明 PNG。';
    }catch(error){if(ticket!==generation)return;el('error').textContent=error.message;el('error').hidden=false;el('status').textContent='素材读取失败';}
  }
  function setMode(next){mode=next;for(const b of document.querySelectorAll('[data-mode]'))b.setAttribute('aria-pressed',String(b.dataset.mode===mode));el('action').replaceChildren();
    const options=mode==='native'?config.rows.map(r=>[r.state,r.label+' · '+r.state]):source.outfits[0].actions.map(a=>[a.id,a.name]);
    for(const [value,label]of options){const option=document.createElement('option');option.value=value;option.textContent=label;el('action').append(option);}selectAction();
  }
  function wave(){el('action').value=mode==='native'?'waving':'05_wave';playing=true;selectAction();}
  document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.mode)));
  el('action').addEventListener('change',selectAction);
  el('play').addEventListener('click',()=>{playing=!playing;previous=null;updateInfo();});
  el('step').addEventListener('click',()=>{playing=false;index=(index+1)%durations().length;accumulator=0;draw();});
  el('scrub').addEventListener('input',()=>{playing=false;index=Number(el('scrub').value);accumulator=0;draw();});
  el('background').addEventListener('click',()=>{background=(background+1)%3;for(const stage of document.querySelectorAll('.stage'))stage.className='stage '+backgrounds[background];el('background').textContent='背景：'+names[background];});
  document.addEventListener('visibilitychange',()=>{previous=null;});
  function tick(time){
    if(previous!==null&&playing&&loaded&&!document.hidden){
      accumulator+=Math.min(time-previous,250)*Number(el('speed').value);const d=durations();let changed=false;
      while(accumulator>=d[index]){accumulator-=d[index];index=(index+1)%d.length;changed=true;}
      if(changed)draw();
    }previous=time;requestAnimationFrame(tick);
  }
  setMode('native');requestAnimationFrame(tick);
})();
