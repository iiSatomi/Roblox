import { createState, setEnabled, setPolicy, applyValues, pause, resume, stop, featureStatus } from './model.mjs';

const catalog = await fetch('./catalog.json').then(response => {
  if (!response.ok) throw new Error('Local catalog could not load');
  return response.json();
});
let state = createState(catalog.features);
let pageId = 'overview';
let query = '';
let permission = false;
let customValues = {};
const history = [];
const content = document.querySelector('#content');
const symbols = ['⌂','◇','⚔','♟','□','$','⇄','⚑','✓','✦','▤','⚙','≡'];
const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const enabled = () => catalog.features.filter(feature => state.enabled[feature.id]);
const matches = feature => `${feature.id} ${feature.label} ${feature.description}`.toLowerCase().includes(query);
function log(text) { history.unshift({text,time:new Date().toLocaleTimeString()}); history.splice(40); }
function switchRow(feature) {
  return `<label class="switch"><input type="checkbox" data-enable="${feature.id}" aria-label="${escape(feature.label)}" ${state.enabled[feature.id]?'checked':''}><span class="switch-track"></span></label>`;
}
function control(field, feature) {
  const value = customValues[`${feature.id}/${field.label}`] ?? field.value;
  if (field.type === 'select') return `<label>${escape(field.label)}<select data-custom="${escape(feature.id+'/'+field.label)}" aria-label="${escape(field.label)}">${field.options.map(option=>`<option ${option===value?'selected':''}>${escape(option)}</option>`).join('')}</select></label>`;
  return `<label>${escape(field.label)}<input data-custom="${escape(feature.id+'/'+field.label)}" aria-label="${escape(field.label)}" type="number" min="${field.min??0}" ${field.max?'max="'+field.max+'"':''} value="${escape(value)}"></label>`;
}
function featureCard(feature) {
  let status = featureStatus(state, feature);
  if (['combat','warCombat'].includes(feature.id) && state.enabled[feature.id] && !permission && !['Stopped','Paused'].includes(status.label)) status={label:'Waiting',reason:'Allow player attacks separately. A target policy never grants permission.'};
  return `<article class="feature" data-feature="${feature.id}"><div class="feature-head"><div><h3>${escape(feature.label)}</h3><p class="feature-description">${escape(feature.description)}</p></div>${switchRow(feature)}</div>
    <div class="feature-actions">${feature.policies.length?`<label>Goal / policy<select aria-label="${escape(feature.label)} policy" data-policy="${feature.id}">${feature.policies.map(policy=>`<option ${state.policies[feature.id]===policy?'selected':''}>${escape(policy)}</option>`).join('')}</select></label>`:''}${feature.sensitive?'<span class="sensitive">Separate permission and limits</span>':''}</div>
    ${feature.limits?`<p class="limits">${escape(feature.limits)}</p>`:''}
    ${feature.custom.length?`<details ${state.policies[feature.id]==='Custom'?'open':''}><summary>Custom · ${feature.custom.length} useful overrides</summary><div class="custom-grid">${feature.custom.map(field=>control(field,feature)).join('')}</div><p class="notice">Preview values only. No account configuration is loaded or saved.</p></details>`:''}
    <div class="status-line"><span class="badge ${status.label}">${status.label}</span><span>${escape(status.reason)}</span></div></article>`;
}
function pageHeading(page) {
  return `<div class="page-head"><div><div class="eyebrow">IDLE MAFIA / EMBER RECODE</div><h1>${escape(page.label)}</h1><p>${escape(page.description)}</p></div><span class="badge">Design preview</span></div>`;
}
function overview() {
  const active = enabled();
  const status = state.stopped?'Stopped':state.paused?'Paused':active.length?'Choices prepared':'All activities off';
  return `<div class="overview-columns"><section class="session-panel"><div class="session-heading"><h2>Your session</h2><span class="badge ${state.stopped?'Stopped':state.paused?'Paused':''}">${status}</span></div><div class="session-title">${active.length?`${active.length} activities selected`:'A clear place to start'}</div><p class="session-help">Turn on what you want and choose a goal. The hub explains the next step; routine details follow native state.</p><div class="button-row"><button class="button" data-command="sample">Load sample choices</button><button class="button secondary" data-command="${state.paused||state.stopped?'resume':'pause'}">${state.paused||state.stopped?'Resume':'Pause'}</button><button class="button secondary" data-command="reset">Reset preview</button></div><p class="notice">These controls change this preview only. No account is connected.</p></section>
    <section class="context-panel"><h2>Current context <span class="badge">Sample</span></h2><div class="context-row"><span>Cash / bank</span><strong>$4.2M / $18M</strong></div><div class="context-row"><span>Health / stamina</span><strong>${state.scenario==='lowHealth'?'34%':'82%'} / 24</strong></div><div class="context-row"><span>Native automation</span><strong>${state.scenario==='nativeJobs'?'Auto Jobs active':'None in sample'}</strong></div><div class="context-row"><span>Native evidence build</span><strong>${catalog.evidenceBuild}</strong></div></section></div>
    <label class="scenario">Try a sample situation<select id="scenario" aria-label="Sample situation">${[['normal','Normal conditions'],['lowHealth','Low health'],['nativeJobs','Native Auto Jobs active'],['closedMarket','Market shop closed'],['unconfirmed','Sent action still unconfirmed']].map(([value,label])=>`<option value="${value}" ${state.scenario===value?'selected':''}>${label}</option>`).join('')}</select></label>
    <div class="section-heading"><h2>Your activities</h2><span>One reason per routine</span></div><div class="activity-list">${active.length?active.map(feature=>{const result=featureStatus(state,feature);return `<div class="activity-row"><div><h3>${escape(feature.label)}</h3><p>${escape(result.reason)}</p></div><button class="text-button" data-page="${feature.page}">Open settings →</button></div>`;}).join(''):'<div class="empty">Nothing selected. Load the sample choices or open a feature page.</div>'}</div>`;
}
function specialPage() {
  if (pageId === 'profiles') return `<div class="info-panel">Profile layout preview. No account files are read, imported or overwritten.</div><div class="profile-row"><strong>Active profile</strong><span>Local sample · memory only</span></div><div class="profile-row"><strong>Selected profile</strong><select aria-label="Sample profile"><option>Sample farming choices</option></select><button class="button" data-command="sample">Apply sample choices</button></div><p class="notice">Selecting a real profile will never be the same as activating it. Import changes and permissions will be reviewed first.</p>`;
  if (pageId === 'settings') return `<div class="info-panel">Keep common preferences here once. Native costs, timers and protocol internals are automatic facts, not dozens of settings.</div><div class="profile-row"><strong>Appearance</strong><span>Slate surfaces · copper accent · motion follows your browser preference</span></div><div class="profile-row"><strong>Shared limits</strong><span>Health, stamina, cash reserves and spending policies will have one authoritative home.</span></div><div class="profile-row"><strong>Technical details</strong><span>Compatibility, state age and request history live in Activity.</span></div>`;
  if (pageId === 'activity') return `<div class="info-panel">UI changes in this local preview. These are not gameplay actions or confirmed server outcomes.</div><div class="activity-list">${history.length?history.map(row=>`<div class="activity-row"><span>${escape(row.text)}</span><span class="muted">${escape(row.time)}</span></div>`).join(''):'<div class="empty">No local changes yet.</div>'}</div>`;
  return '';
}
function render() {
  document.querySelector('#navigation').innerHTML=catalog.pages.map((page,index)=>`<button data-page="${page.id}" ${pageId===page.id?'aria-current="page"':''}><span class="nav-symbol" aria-hidden="true">${symbols[index]}</span>${escape(page.label)}</button>`).join('');
  const page=catalog.pages.find(page=>page.id===pageId);
  document.querySelector('#breadcrumb').textContent=page.label;
  const filtered=catalog.features.filter(feature=>feature.page===pageId&&matches(feature));
  const notice=pageId==='combat'?`<div class="permission-line"><label><input id="player-permission" type="checkbox" ${permission?'checked':''}>Allow player attacks <span class="muted">· sample permission only</span></label></div>`:'';
  const body=pageId==='overview'&&!query?overview():['profiles','settings','activity'].includes(pageId)&&!query?specialPage():`${notice}<div class="feature-list">${filtered.length?filtered.map(featureCard).join(''):'<div class="empty">No matching feature on this page.</div>'}</div>`;
  content.innerHTML=pageHeading(page)+body;
  document.querySelector('#session-state').textContent=state.stopped?'Stopped · explicit Resume required':state.paused?'Paused · choices kept':`${enabled().length} sample activities selected · 0 gameplay requests`;
}
document.addEventListener('click',event=>{
  const nav=event.target.closest('[data-page]');
  if(nav){pageId=nav.dataset.page;query='';document.querySelector('#search').value='';render();content.scrollTop=0;return;}
  const command=event.target.closest('[data-command]')?.dataset.command;
  if(command==='sample') state=applyValues(state,{jobs:true,operations:true,collect:true,properties:true,bank:true});
  if(command==='pause') state=pause(state);
  if(command==='resume') state=resume(state);
  if(command==='reset'){state=createState(catalog.features);permission=false;customValues={};}
  if(command){log(`Preview: ${command}`);render();}
});
document.addEventListener('change',event=>{
  const target=event.target;
  if(target.dataset.enable){state=setEnabled(state,target.dataset.enable,target.checked);log(`${target.checked?'Selected':'Cleared'}: ${target.getAttribute('aria-label')}`);render();}
  if(target.dataset.policy){state=setPolicy(state,target.dataset.policy,target.value);log(`Policy: ${target.value}`);render();}
  if(target.dataset.custom) customValues[target.dataset.custom]=target.value;
  if(target.id==='scenario'){state={...state,scenario:target.value};render();}
  if(target.id==='player-permission'){permission=target.checked;render();}
});
document.querySelector('#search').addEventListener('input',event=>{query=event.target.value.trim().toLowerCase();if(query){const found=catalog.features.find(matches);if(found)pageId=found.page;}render();});
function emergencyStop(){state=stop(state);permission=false;log('Emergency Stop · sample switches cleared');render();}
document.querySelector('#stop').addEventListener('click',emergencyStop);
document.addEventListener('keydown',event=>{if(event.key==='F8'){event.preventDefault();emergencyStop();}});
render();
