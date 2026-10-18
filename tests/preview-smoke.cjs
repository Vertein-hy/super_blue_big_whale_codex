/* Logic-only smoke checks. This is deliberately NOT a real browser rendering test. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=path.resolve(__dirname,'..');
function setup(reduced=false){
  const all=[];const draws=[];const raf=[];
  class Element {
    constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.attributes={};this.dataset={};this._value='';this.className='';this.textContent='';this.hidden=false;all.push(this);}
    append(...items){this.children.push(...items);if(this.tagName==='select'&&this.children.length===items.length)this._value=this.children[0]?.value||'';}
    replaceChildren(...items){this.children=[];this._value='';this.append(...items);}
    set value(value){this._value=String(value);}get value(){return this._value;}
    setAttribute(key,value){this.attributes[key]=String(value);}
    addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
    emit(name,event={}){for(const fn of this.listeners[name]||[])fn(event);}
    getContext(){return {canvas:this,clearRect(){},drawImage(...args){draws.push(args);}};}
  }
  const elements={};
  for(const id of ['cards','action','speed','scrub','frame-info','play','error','status','note','step','background'])elements[id]=new Element(['action','speed'].includes(id)?'select':'div');
  elements.speed.value='1';
  const tabs=['native','source'].map(mode=>{const b=new Element('button');b.dataset.mode=mode;return b;});
  const document={hidden:false,getElementById:id=>elements[id],createElement:tag=>new Element(tag),
    querySelectorAll:query=>query==='[data-mode]'?tabs:all.filter(e=>e.className.split(' ').includes('stage')),
    addEventListener(){}};
  class LocalImage {
    set src(value){this._src=value;if(!fs.existsSync(path.join(root,value)))throw new Error('Missing real asset '+value);queueMicrotask(()=>this.onload());}
    get src(){return this._src;}
  }
  const context=vm.createContext({window:{matchMedia:()=>({matches:reduced})},document,Image:LocalImage,requestAnimationFrame:fn=>raf.push(fn),console});
  vm.runInContext(fs.readFileSync(path.join(root,'preview-data.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(root,'preview.js'),'utf8'),context);
  return {elements,tabs,all,draws,raf,document,tick(time){assert.ok(raf.length);raf.shift()(time);}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  let checks=0;
  const app=setup();await settle();
  assert.equal(app.elements.cards.children.length,3);assert.equal(app.elements.action.children.length,9);assert.equal(app.draws.length,3);checks++;
  assert.equal(app.elements['frame-info'].textContent,'01 / 06 帧');assert.equal(app.elements.play.textContent,'暂停');checks++;
  app.tick(0);app.tick(200);app.tick(300);assert.equal(app.elements['frame-info'].textContent,'02 / 06 帧');checks++;
  app.elements.play.emit('click');app.tick(400);app.tick(700);assert.equal(app.elements['frame-info'].textContent,'02 / 06 帧');assert.equal(app.elements.play.textContent,'播放');checks++;
  app.elements.step.emit('click');assert.equal(app.elements['frame-info'].textContent,'03 / 06 帧');checks++;
  app.elements.scrub.value='5';app.elements.scrub.emit('input');assert.equal(app.elements['frame-info'].textContent,'06 / 06 帧');checks++;
  app.elements.background.emit('click');assert.ok(app.all.filter(e=>e.className==='stage light').length===3);checks++;
  app.tabs[1].emit('click');await settle();assert.equal(app.elements.action.children.length,9);assert.equal(app.elements['frame-info'].textContent,'01 / 24 帧');checks++;
  app.elements.action.value='08_dance';app.elements.action.emit('change');await settle();assert.ok(app.draws.slice(-3).every(d=>d[0].src.endsWith('08_dance.webp')));checks++;
  app.all.find(e=>e.tagName==='canvas').emit('click');await settle();assert.equal(app.elements.action.value,'05_wave');assert.equal(app.elements.play.textContent,'暂停');checks++;
  app.elements.scrub.value='23';app.elements.scrub.emit('input');assert.ok(app.draws.slice(-3).every(d=>d[1]===1600&&d[2]===960&&d[3]===320&&d[4]===320));checks++;
  app.tabs[0].emit('click');await settle();app.elements.action.value='running-left';app.elements.action.emit('change');await settle();assert.equal(app.elements['frame-info'].textContent,'01 / 08 帧');assert.ok(app.draws.slice(-3).every(d=>d[2]===416&&d[3]===192&&d[4]===208));checks++;
  const accessible=setup(true);await settle();assert.equal(accessible.elements.play.textContent,'播放');assert.match(accessible.elements.status.textContent,/减少动态/);checks++;
  console.log(JSON.stringify({status:'PASS',checks,method:'Node VM with minimal DOM and local image-path verification',real_browser_render_tested:false},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
