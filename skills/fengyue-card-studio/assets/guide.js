/* Each instance owns its events and fields. No global IDs, external libraries or navigation. */
(()=>{'use strict';
for(const root of document.querySelectorAll('.fy-guide[data-interactive="true"]')){
 if(root.dataset.ready==='true')continue;
 const configNode=root.querySelector('[data-config]');if(!configNode)continue;
 const cfg=JSON.parse(configNode.textContent),panels=[...root.querySelectorAll('[data-panel]')],tabs=[...root.querySelectorAll('[data-tab]')];
 const prefix='fy-'+(globalThis.crypto?.randomUUID?.()||Math.random().toString(36).slice(2));
 panels.forEach((panel,i)=>{panel.id=prefix+'-panel-'+i;panel.setAttribute('aria-labelledby',prefix+'-tab-'+i);tabs[i].id=prefix+'-tab-'+i;tabs[i].setAttribute('aria-controls',panel.id);});
 const form=root.querySelector('form'),output=root.querySelector('[data-output]'),feedback=root.querySelector('[data-feedback]'),copy=root.querySelector('[data-copy]'),generate=root.querySelector('[data-generate]');
 let dirty=true,manual=false,counter=0,busy=false;
 const byKey=new Map(cfg.fields.map(field=>[field.key,field]));
 function openPanel(index,focus=false){panels.forEach((p,i)=>p.hidden=i!==index);tabs.forEach((t,i)=>{t.setAttribute('aria-selected',String(i===index));t.tabIndex=i===index?0:-1;});if(focus)tabs[index].focus();}
 function fields(){return [...root.querySelectorAll('[data-input]')];}
 function sync(){const all=fields(),filled=all.filter(el=>el.value.trim()).length;
  root.querySelector('[data-completion]').textContent=filled+' / '+all.length;
  root.querySelector('[data-progress]').style.width=(all.length?filled/all.length*100:0)+'%';
  const n=root.querySelector('[data-extra-count]');if(n)n.textContent=root.querySelectorAll('[data-extra-person]').length+' 位';
  root.querySelector('[data-output-count]').textContent=output.value.length+' 字符';
 }
 function markChanged(){dirty=true;if(output.value){feedback.textContent=manual?'资料已修改。点击“重新生成”会替换你手动编辑的结果，请先保留需要的内容。':'资料已修改，复制时会先更新为最新开局。';generate.textContent='重新生成开局';}sync();}
 function collect(){
  const lines=['【本局开局资料】','作品：'+cfg.title],chosen=root.querySelector('[data-opening]:checked');
  if(chosen){const opening=cfg.openings[Number(chosen.value)];lines.push('','【开局选择】',opening.title,opening.text);}
  const grouped=new Map();
  for(const el of fields()){
   const f=byKey.get(el.dataset.input),value=el.value.trim();
   if(f.required&&!value){openPanel(2);el.focus();feedback.textContent='请填写“'+f.label+'”。';el.setCustomValidity('请填写此项');el.reportValidity();return null;}
   el.setCustomValidity('');
   if(!value)continue;
   const group=f.group||'角色资料';if(!grouped.has(group))grouped.set(group,[]);grouped.get(group).push(f.label+'：'+value);
  }
  for(const [group,items] of grouped)lines.push('','【'+group+'】',...items);
  let activePeople=0;
  for(const person of root.querySelectorAll('[data-extra-person]')){
   const items=[...person.querySelectorAll('[data-person-field]')].filter(el=>el.value.trim()).map(el=>el.dataset.label+'：'+el.value.trim());
   if(items.length)lines.push('','【补充人物 '+(++activePeople)+'】',...items);
  }
  if(cfg.fixed_notes?.length)lines.push('','【作品既定前提】',...cfg.fixed_notes);
  lines.push('',cfg.start_instruction||'请承接以上已确认资料和所选开局进入故事，空白选填项不构成隐藏设定，保留我的回应与决定。');
  return lines.join('\n');
 }
 function build(){const text=collect();if(text===null)return false;output.value=text;dirty=false;manual=false;copy.disabled=false;generate.textContent='重新生成开局';feedback.textContent='开局已汇总。可以在下方修改，然后复制到聊天中发送。';sync();return true;}
 function selectText(){output.focus();output.select();output.setSelectionRange(0,output.value.length);}
 async function copyText(){if(busy)return;
  if(dirty&&manual){feedback.textContent='表单与手动编辑的结果不同。请先重新生成或保存编辑内容，避免复制旧设定。';generate.focus();return;}
  if((dirty||!output.value.trim())&&!build())return;
  const text=output.value;busy=true;copy.disabled=true;
  try{
   let done=false;
   try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);done=true;}}catch{}
   if(!done){selectText();try{done=document.execCommand('copy')===true;}catch{}}
   if(done){feedback.textContent='已复制完整开局。粘贴到聊天输入框即可开始。';}
   else{selectText();feedback.textContent='自动复制不可用，已选中完整开局。电脑按 Ctrl+C；手机长按文本选择复制。';}
  }finally{busy=false;copy.disabled=!output.value.trim();}
 }
 function addPerson(){const template=root.querySelector('template[data-person-template]');if(!template)return;
  const clone=template.content.cloneNode(true);clone.querySelector('[data-person-number]').textContent=String(++counter).padStart(2,'0');root.querySelector('[data-people-list]').append(clone);markChanged();
 }
 form.addEventListener('submit',event=>event.preventDefault());
 root.addEventListener('input',event=>{if(event.target===output){manual=true;copy.disabled=!output.value.trim();sync();return;}if(event.target.matches('input,textarea,select')){event.target.setCustomValidity?.('');markChanged();}});
 root.addEventListener('change',event=>{if(event.target.matches('input,textarea,select'))markChanged();});
 root.addEventListener('click',event=>{const tab=event.target.closest('[data-tab]'),go=event.target.closest('[data-go]');if(tab&&root.contains(tab))openPanel(Number(tab.dataset.tab));if(go&&root.contains(go))openPanel(Number(go.dataset.go));
  const remove=event.target.closest('[data-remove-person]');if(remove&&root.contains(remove)){remove.closest('[data-extra-person]').remove();markChanged();}
 });
 tabs.forEach((tab,i)=>tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(i+1)%tabs.length;if(event.key==='ArrowLeft')next=(i+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();openPanel(next,true);}}));
 generate.addEventListener('click',()=>build());copy.addEventListener('click',copyText);
 root.querySelector('[data-add-person]')?.addEventListener('click',addPerson);
 root.querySelector('[data-reset]').addEventListener('click',()=>{if(!window.confirm('清空已填写资料和生成结果？'))return;form.reset();root.querySelector('[data-people-list]')?.replaceChildren();output.value='';counter=0;dirty=true;manual=false;copy.disabled=true;generate.textContent='汇总我的开局';feedback.textContent='已清空，可以重新填写。';sync();});
 root.querySelectorAll('[data-js-button]').forEach(button=>button.disabled=false);copy.disabled=true;
 root.querySelector('[data-runtime-note]').hidden=true;root.dataset.ready='true';openPanel(0);sync();
}
})();
