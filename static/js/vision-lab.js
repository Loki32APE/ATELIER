(function(){
 const root=document.getElementById('tab-scratchpad');if(!root)return;
 let initialSettings={};try{initialSettings=JSON.parse(localStorage.getItem('ape_settings_v1')||'{}')||{};}catch(e){}
 let mode=initialSettings.defaultMode==='advanced'?'advanced':'basic',protectedInstructions='';
 if(initialSettings.targetModel)root.querySelector('#vlModel').value=initialSettings.targetModel;
 const modules=[...root.querySelectorAll('textarea[data-vl-module]')],generate=root.querySelector('#vlGenerateBtn'),progress=root.querySelector('#vlProgress'),output=root.querySelector('#vlOutputCard'),prompt=root.querySelector('#vlPromptOutput'),repairBox=root.querySelector('#vlRepairCompare');
 const editButton=document.createElement('button');editButton.type='button';editButton.className='btn btn-secondary';editButton.textContent='Edit';editButton.setAttribute('aria-controls','vlPromptOutput');root.querySelector('.vl-output-actions').insertBefore(editButton,root.querySelector('#vlValidateBtn'));prompt.readOnly=true;
 editButton.addEventListener('click',()=>{if(prompt.readOnly){prompt.readOnly=false;editButton.textContent='Done editing';prompt.focus();prompt.setSelectionRange(prompt.value.length,prompt.value.length);showToast('Editing enabled. Re-validate your changes before using the prompt.');}else{prompt.readOnly=true;editButton.textContent='Edit';showToast('Editing finished. Re-validate your changes before using the prompt.');}});
 
 async function initializeCatalogFields(){
   generate.disabled=true;root.querySelector('#vlSampleBtn').disabled=true;progress.hidden=false;progress.textContent='Loading creative presets…';
   root.setAttribute('aria-busy','true');
   const catalogRoots=[...root.querySelectorAll('[data-vl-fields],[data-vl-advanced-fields]')];
   catalogRoots.forEach(node=>{node.classList.add('vl-skeleton-group');node.replaceChildren();for(let i=0;i<3;i++){const row=document.createElement('span');row.className='vl-skeleton-row';row.setAttribute('aria-hidden','true');node.appendChild(row);}});
   try{
     const catalog=await AtelierCatalogService.loadVisualLabCatalog();
     Object.entries(catalog.modules).forEach(([moduleId,definition])=>{
       const basic=root.querySelector('[data-vl-fields="'+moduleId+'"]');
       const advanced=root.querySelector('[data-vl-advanced-fields="'+moduleId+'"]');
       if(!basic||!advanced)return;
       basic.replaceChildren();
       advanced.replaceChildren();
       (definition.basic||[]).forEach(field=>basic.appendChild(createCatalogField(moduleId,field)));
       (definition.advanced||[]).forEach(field=>advanced.appendChild(createCatalogField(moduleId,field)));
     });
   }catch(error){
     catalogRoots.forEach(node=>{node.classList.remove('vl-skeleton-group');node.replaceChildren();});
     root.querySelectorAll('[data-vl-fields]').forEach(node=>{
       const status=document.createElement('div');
       status.className='vl-catalog-status';
       status.setAttribute('role','status');
       status.textContent='Preset options could not load. You can still describe this module in the text field below.';
       node.appendChild(status);
     });
     console.warn('Visual Lab catalog unavailable:',error.message);
   }finally{
     catalogRoots.forEach(node=>node.classList.remove('vl-skeleton-group'));
     root.removeAttribute('aria-busy');
     generate.disabled=false;root.querySelector('#vlSampleBtn').disabled=false;progress.hidden=true;
   }
 }
 function createCatalogField(moduleId,field){
   if(field.type==='multi'){
     const group=document.createElement('fieldset');
     group.className='vl-field vl-field-multi';
     const legend=document.createElement('legend');legend.textContent=field.label||field.id;group.appendChild(legend);
     (field.options||[]).forEach(option=>{
       const label=document.createElement('label');label.className='vl-choice-chip';
       const input=document.createElement('input');input.type='checkbox';input.value=option;
       input.dataset.vlChoice=field.id;input.dataset.vlModule=moduleId;
       input.setAttribute('aria-label',(field.label||field.id)+': '+option);
       input.addEventListener('change',()=>label.classList.toggle('is-selected',input.checked));
       const text=document.createElement('span');text.textContent=option;
       label.append(input,text);group.appendChild(label);
     });
     return group;
   }
   const wrapper=document.createElement('div');wrapper.className='vl-field';
   const label=document.createElement('label'),select=document.createElement('select');
   const id='vl-'+moduleId+'-'+field.id;
   label.htmlFor=id;label.textContent=field.label||field.id;
   select.id=id;select.dataset.vlChoice=field.id;select.dataset.vlModule=moduleId;
   select.setAttribute('aria-label',field.label||field.id);
   select.add(new Option('Any / not specified',''));
   (field.options||[]).forEach(option=>select.add(new Option(option,option)));
   wrapper.append(label,select);return wrapper;
 }

 function collect(){
  const selections={};
  modules.forEach(el=>{
    const id=el.dataset.vlModule,card=el.closest('.vl-module-card'),detail={},choices={};
    if(card)card.querySelectorAll('[data-vl-choice]').forEach(control=>{
      const key=control.dataset.vlChoice;
      if(control.type==='checkbox'){
        if(control.checked){if(!Array.isArray(choices[key]))choices[key]=[];choices[key].push(control.value);}
      }else if(control.value)choices[key]=control.value;
    });
    if(Object.keys(choices).length)detail.choices=choices;
    if(el.value.trim())detail.description=el.value.trim();
    const extra=root.querySelector('[data-vl-extra="'+id+'"]');
    if(mode==='advanced'&&extra&&extra.value.trim())detail.advanced_notes=extra.value.trim();
    if(Object.keys(detail).length)selections[id]=detail;
  });
  let language='English';try{const saved=JSON.parse(localStorage.getItem('ape_settings_v1')||'{}');if(['English','Hindi','Odia'].includes(saved.language))language=saved.language;}catch(e){}
  return {mode,language,instructions:root.querySelector('#vlInstructions').value,selections,target_model_id:root.querySelector('#vlModel').value};
}
 root.querySelectorAll('.vl-mode').forEach(btn=>btn.addEventListener('click',()=>{mode=btn.dataset.mode;root.dataset.mode=mode;root.querySelectorAll('.vl-mode').forEach(b=>{const on=b===btn;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});}));
 root.querySelector('#vlClearBtn').addEventListener('click',()=>{if(!confirm('Clear all Visual Lab selections and instructions?'))return;modules.forEach(el=>el.value='');root.querySelectorAll('[data-vl-extra]').forEach(el=>el.value='');root.querySelectorAll('[data-vl-choice]').forEach(el=>{if(el.type==='checkbox')el.checked=false;else el.value='';});root.querySelector('#vlInstructions').value='';protectedInstructions='';prompt.value='';prompt.readOnly=true;editButton.textContent='Edit';output.hidden=true;repairBox.hidden=true;showToast('Visual Lab brief cleared');});
 root.querySelector('#vlSampleBtn').addEventListener('click',()=>{
   const hasContent=modules.some(el=>el.value.trim())||[...root.querySelectorAll('[data-vl-choice]')].some(el=>el.type==='checkbox'?el.checked:el.value)||root.querySelector('#vlInstructions').value.trim();
   if(hasContent&&!confirm('Replace the current brief with the sample?'))return;
   modules.forEach(el=>el.value='');root.querySelectorAll('[data-vl-extra]').forEach(el=>el.value='');root.querySelectorAll('[data-vl-choice]').forEach(el=>{if(el.type==='checkbox')el.checked=false;else el.value='';});
   const setSelect=(moduleId,fieldId,value)=>{const control=root.querySelector('[data-vl-module="'+moduleId+'"]')?.closest('.vl-module-card')?.querySelector('[data-vl-choice="'+fieldId+'"]');if(control&&[...control.options].some(option=>option.value===value))control.value=value;};
   setSelect('appearance_identity','presentation','Feminine');setSelect('appearance_identity','age_range','Adult');setSelect('outfit_styling','garment_type','Sambalpuri saree');setSelect('outfit_styling','fabric','Sambalpuri cotton');setSelect('outfit_styling','garment_colour','Maroon');setSelect('poses_expressions','pose','Standing');setSelect('poses_expressions','framing','Three-quarter');setSelect('themes_environment','environment','Outdoor');setSelect('themes_environment','location','Garden');setSelect('lighting_composition','lighting','Golden hour sunlight');setSelect('camera_photography','focal_length','85mm portrait');setSelect('output_rendering','aspect_ratio','4:5');
   const styling=root.querySelector('textarea[data-vl-module="outfit_styling"]');if(styling)styling.value='Handwoven Sambalpuri cotton saree with a carefully pleated drape and natural fabric texture.';
   const pose=root.querySelector('textarea[data-vl-module="poses_expressions"]');if(pose)pose.value='Relaxed shoulders, one hand lightly holding the pallu, calm direct gaze.';
   root.querySelectorAll('[data-vl-choice][type="checkbox"]').forEach(control=>{if(control.dataset.vlModule==='outfit_styling'&&control.value==='Zari border')control.checked=true;});
   const instructions=root.querySelector('#vlInstructions');instructions.value='Keep the textile weave visible. Use a natural, respectful editorial portrait with realistic hands and anatomy.';
   mode='advanced';root.dataset.mode=mode;root.querySelectorAll('.vl-mode').forEach(button=>{const active=button.dataset.mode===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
   showToast('Sample brief loaded. Review it, then generate when ready.');root.querySelector('#vl-section-styling').scrollIntoView({behavior:'smooth',block:'start'});
 });
 async function poll(id,accessToken){const deadline=Date.now()+180000;while(Date.now()<deadline){await new Promise(r=>setTimeout(r,1600));const response=await fetch('/status/'+encodeURIComponent(id),{headers:{'Authorization':'Bearer '+accessToken}}),data=await response.json();if(response.status===404||data.status==='error')throw new Error(data.error||'Generation job expired.');if(data.status==='done')return data;progress.textContent=data.step||'Atelier is composing your prompt…';}throw new Error('Visual Lab timed out. Please try again.');}
 generate.addEventListener('click',async()=>{if(generate.disabled)return;const payload=collect();if(!payload.instructions.trim()&&!Object.keys(payload.selections).length){showToast('Add at least one creative detail before generating.');return;}generate.disabled=true;progress.hidden=false;progress.textContent='Structuring your creative brief…';try{const response=await fetch('/vision-lab/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),body=await response.json();if(!response.ok)throw new Error(body.error||'Could not start Visual Lab.');const result=await poll(body.job_id,body.access_token);prompt.value=result.prompt||'';prompt.readOnly=true;editButton.textContent='Edit';protectedInstructions=payload.instructions;output.hidden=false;repairBox.hidden=true;const quality=result.quality||{};root.querySelector('#vlQualityBadge').textContent='Quality '+(quality.score??'Not scored')+'/100';const notice=root.querySelector('#vlReviewNotice'),notes=[...(result.rule_findings||[]).map(x=>x.message),...(quality.issues||[]).map(x=>x.message),...(result.optimization_warnings||[])];notice.hidden=!notes.length&&result.processing_status!=='needs_review';notice.textContent=notes.join(' · ')||'Review recommended before final use.';root.querySelector('#vlOutputMeta').textContent=(result.ai_status==='completed'?'AI reasoning completed':'Deterministic fallback · '+(result.provider_error||'AI unavailable'))+' · '+(result.model_profile?.display_name||'Model profile')+' · Output language: '+(result.output_language||'English');showToast('Visual Lab prompt is ready.');output.scrollIntoView({behavior:'smooth',block:'start'});}catch(error){showToast(error.message||'Visual Lab request failed.');}finally{generate.disabled=false;progress.hidden=true;}});
 root.querySelector('#vlCopyBtn').addEventListener('click',async()=>{if(!prompt.value.trim())return showToast('No prompt to copy.');try{await navigator.clipboard.writeText(prompt.value);showToast('Master prompt copied.');}catch(e){showToast('Copy failed. Select and copy manually.');}});
 root.querySelector('#vlRepairBtn').addEventListener('click',async e=>{const btn=e.currentTarget;if(!prompt.value.trim())return;btn.disabled=true;btn.textContent='Repairing…';try{const response=await fetch('/vision-lab/repair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:prompt.value,instructions:protectedInstructions,target_model_id:root.querySelector('#vlModel').value})}),result=await response.json();if(!response.ok)throw new Error(result.error||'Repair unavailable.');repairBox.hidden=false;repairBox.replaceChildren();const title=document.createElement('strong');title.textContent='Repair proposal · original remains unchanged';const candidate=document.createElement('textarea');candidate.rows=9;candidate.value=result.repaired_prompt||'';const score=document.createElement('p');score.textContent='Original quality: '+result.original_quality.score+'/100 · Proposed quality: '+result.repaired_quality.score+'/100';const actions=document.createElement('div');actions.className='decision-row';const accept=document.createElement('button');accept.className='btn btn-primary';accept.textContent='Accept proposal';const reject=document.createElement('button');reject.className='btn btn-secondary';reject.textContent='Keep original';accept.onclick=()=>{prompt.value=candidate.value;prompt.readOnly=true;editButton.textContent='Edit';repairBox.hidden=true;showToast('Repair proposal accepted.');};reject.onclick=()=>{repairBox.hidden=true;showToast('Original prompt retained.');};actions.append(accept,reject);repairBox.append(title,score,candidate,actions);}catch(error){showToast(error.message||'Repair failed.');}finally{btn.disabled=false;btn.textContent='Propose repair';}});

 const profileKey='atelier_vision_lab_profiles_v1';
 function readProfiles(){try{const data=JSON.parse(localStorage.getItem(profileKey)||'[]');return Array.isArray(data)?data.filter(x=>x&&typeof x.name==='string'&&x.payload&&typeof x.payload==='object'):[];}catch(e){return [];}}
 function refreshProfiles(){const select=root.querySelector('#vlProfileSelect'),current=select.value;select.replaceChildren(new Option('Choose saved profile',''));readProfiles().forEach((item,index)=>select.add(new Option(item.name,String(index))));if([...select.options].some(x=>x.value===current))select.value=current;}
 root.querySelector('#vlSaveProfileBtn').addEventListener('click',()=>{const name=root.querySelector('#vlProfileName').value.trim();if(!name)return showToast('Enter a name for this creative profile.');const profiles=readProfiles();const found=profiles.findIndex(x=>x.name.toLowerCase()===name.toLowerCase());const record={name,payload:collect(),updated_at:new Date().toISOString()};if(found>=0){if(!confirm('A profile with this name exists. Replace it?'))return;profiles[found]=record;}else profiles.push(record);try{localStorage.setItem(profileKey,JSON.stringify(profiles));refreshProfiles();showToast('Creative profile saved on this device.');}catch(e){showToast('Could not save profile. Device storage may be full.');}});
 root.querySelector('#vlLoadProfileBtn').addEventListener('click',()=>{const select=root.querySelector('#vlProfileSelect');if(!select.value)return showToast('Choose a saved profile first.');const item=readProfiles()[Number(select.value)];if(!item)return showToast('Choose a saved profile first.');const data=item.payload;mode=data.mode==='advanced'?'advanced':'basic';root.dataset.mode=mode;root.querySelectorAll('.vl-mode').forEach(b=>{const on=b.dataset.mode===mode;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});modules.forEach(el=>{
  const id=el.dataset.vlModule,value=data.selections?.[id],card=el.closest('.vl-module-card');
  el.value=typeof value==='string'?value:(value?.description||'');
  const extra=root.querySelector('[data-vl-extra="'+id+'"]');
  if(extra)extra.value=value?.advanced_notes||'';
  if(card)card.querySelectorAll('[data-vl-choice]').forEach(control=>{
    const selected=value?.choices?.[control.dataset.vlChoice];
    if(control.type==='checkbox'){control.checked=Array.isArray(selected)&&selected.includes(control.value);control.closest('.vl-choice-chip')?.classList.toggle('is-selected',control.checked);}
    else control.value=typeof selected==='string'?selected:'';
  });
});root.querySelector('#vlInstructions').value=data.instructions||'';protectedInstructions=data.instructions||'';root.querySelector('#vlModel').value=data.target_model_id||'';showToast('Creative profile loaded.');});
 root.querySelector('#vlDeleteProfileBtn').addEventListener('click',()=>{const select=root.querySelector('#vlProfileSelect'),index=Number(select.value);if(!select.value)return showToast('Choose a saved profile first.');const profiles=readProfiles();if(!profiles[index]||!confirm('Delete this saved creative profile?'))return;profiles.splice(index,1);localStorage.setItem(profileKey,JSON.stringify(profiles));refreshProfiles();showToast('Creative profile deleted.');});
 async function validateCurrentPrompt(){const text=prompt.value;if(!text.trim())return showToast('There is no prompt to validate.');const button=root.querySelector('#vlValidateBtn');button.disabled=true;button.textContent='Checking…';try{const response=await fetch('/vision-lab/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:text,instructions:protectedInstructions,target_model_id:root.querySelector('#vlModel').value})}),data=await response.json();if(!response.ok)throw new Error(data.error||'Validation failed.');root.querySelector('#vlQualityBadge').textContent='Quality '+data.quality.score+'/100';const notice=root.querySelector('#vlReviewNotice'),issues=(data.quality.issues||[]).map(x=>x.message);notice.hidden=!issues.length;notice.textContent=issues.join(' · ');root.querySelector('#vlOutputMeta').textContent='Manual edit validated · '+data.model_profile.display_name+' · '+data.quality.metrics.characters+' characters';prompt.readOnly=true;editButton.textContent='Edit';showToast(data.quality.passed?'Prompt validation passed.':'Review the prompt issues above.');}catch(e){showToast(e.message||'Validation failed.');}finally{button.disabled=false;button.textContent='Re-validate edits';}}
 root.querySelector('#vlValidateBtn').addEventListener('click',validateCurrentPrompt);
 refreshProfiles();
 root.dataset.mode=mode;
 root.querySelectorAll('.vl-mode').forEach(button=>{const active=button.dataset.mode===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
 initializeCatalogFields();
})();

