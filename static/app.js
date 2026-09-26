const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];

const state = {
  page: "home",
  workout: null,
  run: null,
  dashboard: null,
  profile: null,
  timerStartedAt: null,
  timerHandle: null,
  calendar: {
    weekStart: null,
    selectedDate: null,
    plans: [],
    editingId: null,
    loaded: false,
  },
  health: {
    assessment: null,
    loaded: false,
    formConfigured: false,
    formQuestions: [],
    profile: null,
    signatureHasInk: false,
  },
  settings: {
    anamnesisQuestions: [],
    editingQuestionId: null,
  },
};

function toast(message){
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(()=>el.classList.remove("show"), 2600);
}

async function api(path, options={}){
  const r = await fetch(path, {
    headers: {"Content-Type":"application/json", ...(options.headers||{})},
    ...options,
  });
  if(!r.ok){
    let detail = "Não foi possível concluir a ação.";
    try{ const d = await r.json(); detail = d.detail || detail; }catch{}
    throw new Error(detail);
  }
  return r.json();
}

const pageMeta = {
  home:["Bom dia, Júnior!","Disciplina hoje. Resultados sempre."],
  workouts:["Calendário de treinos","Planejamento semanal e organização dos treinos."],
  run:["Corrida","Métricas reais. Evolução constante."],
  evolution:["Minha evolução","Consistência vira resultado."],
  community:["Comunidade","Evolua com quem também está em movimento."],
  profile:["Meu perfil","Sua jornada, suas conexões."],
  settings:["Configurações","Parametrize as regras e formulários do RITMOX."],
};

function navigate(page){
  if(!$("#page-"+page)) page = "home";
  state.page = page;
  document.body.dataset.page = page;
  $$(".page").forEach(x=>x.classList.toggle("active",x.id==="page-"+page));
  $$("[data-page]").forEach(x=>x.classList.toggle("active",x.dataset.page===page));
  const meta = pageMeta[page] || pageMeta.home;
  $("#pageTitle").textContent = meta[0];
  $("#pageSubtitle").textContent = meta[1];
  history.replaceState(null,"","#"+page);
  if(page==="home") setTimeout(drawProgressChart,50);
  if(page==="run") setTimeout(drawRunChart,50);
  if(page==="workouts") setTimeout(()=>loadHealthGate(),20);
  if(page==="profile") setTimeout(()=>Promise.all([loadUserProfile(),loadProfileAnamnesis()]),20);
  if(page==="settings") setTimeout(()=>loadAnamnesisSettings(),20);
  window.scrollTo({top:0,behavior:"smooth"});
}


function formatLoad(v){
  return Number(v||0).toLocaleString("pt-BR",{maximumFractionDigits:0})+" kg";
}

function renderDashboard(d){
  state.dashboard=d;
  const distance=Number(d.stats.distance_km).toLocaleString("pt-BR",{minimumFractionDigits:1})+" km";
  const load=formatLoad(d.stats.total_load_kg);
  $("#statWorkouts").textContent=d.stats.workouts;
  $("#statDistance").textContent=distance;
  $("#statLoad").textContent=load;
  $("#statTime").textContent=d.stats.active_time;
  if($("#mStatWorkouts")) $("#mStatWorkouts").textContent=d.stats.workouts;
  if($("#mStatDistance")) $("#mStatDistance").textContent=distance;
  if($("#mStatLoad")) $("#mStatLoad").textContent=load;
  if($("#mStatTime")) $("#mStatTime").textContent=d.stats.active_time;
  if(d.empty){
    $("#homeWorkoutTitle").textContent="Nenhum treino programado";
    if($("#mHomeWorkoutTitle")) $("#mHomeWorkoutTitle").textContent="Nenhum treino programado";
    if($("#mHomeRunTitle")) $("#mHomeRunTitle").textContent="Nenhuma corrida registrada";
  }
  drawProgressChart();
}

function renderWorkout(w){
  state.workout=w;
  if(!$("#workoutTitle")) return;
  if(!w){
    $("#workoutTitle").textContent="Nenhum treino cadastrado";
    $("#workoutSubtitle").textContent="Crie seu primeiro treino de musculação.";
    $("#homeWorkoutTitle").textContent="Nenhum treino programado";
    $("#workoutProgress").style.width="0%";
    $("#exerciseList").innerHTML=`<article class="exercise empty-card">
      <div class="exercise-thumb">+</div>
      <div>
        <h4>Comece do zero</h4>
        <p>Seus exercícios, séries, repetições e cargas aparecerão aqui.</p>
      </div>
    </article>`;
    $("#startWorkoutBtn").textContent="Criar primeiro treino";
    if($("#mWorkoutTitle")) $("#mWorkoutTitle").textContent="Nenhum treino cadastrado";
    if($("#mWorkoutMeta")) $("#mWorkoutMeta").textContent="Crie seu primeiro treino de musculação.";
    if($("#mWorkoutProgress")) $("#mWorkoutProgress").style.width="0%";
    if($("#mHomeWorkoutTitle")) $("#mHomeWorkoutTitle").textContent="Nenhum treino programado";
    if($("#mExerciseFocus")) $("#mExerciseFocus").innerHTML=`
      <div class="m-empty-exercise">
        <div class="m-empty-plus">+</div>
        <strong>Comece seu primeiro treino</strong>
        <p>Adicione exercícios, séries, repetições e cargas.</p>
        <button id="mCreateWorkoutBtn" class="m-primary-action">Criar treino</button>
      </div>`;
    if($("#mNextExercise")) $("#mNextExercise").innerHTML=`
      <small>PRÓXIMO EXERCÍCIO</small>
      <div><span class="m-next-thumb">—</span><p><strong>Nenhum exercício</strong><small>Seu próximo exercício aparecerá aqui</small></p><span>›</span></div>`;
    const create=$("#mCreateWorkoutBtn");
    if(create) create.onclick=()=>toast("A tela de criação de treinos entra na próxima etapa.");
    return;
  }
  $("#workoutTitle").textContent=w.title;
  $("#workoutSubtitle").textContent=w.subtitle;
  $("#homeWorkoutTitle").textContent=w.title;
  if($("#mHomeWorkoutTitle")) $("#mHomeWorkoutTitle").textContent=w.title;
  if($("#mWorkoutTitle")) $("#mWorkoutTitle").textContent=w.title;
  if($("#mWorkoutMeta")) $("#mWorkoutMeta").textContent=w.subtitle;
  const total=w.exercises.reduce((a,e)=>a+e.sets_total,0);
  const done=w.exercises.reduce((a,e)=>a+e.sets_done,0);
  const progress=(total?done/total*100:0)+"%";
  $("#workoutProgress").style.width=progress;
  if($("#mWorkoutProgress")) $("#mWorkoutProgress").style.width=progress;
  $("#startWorkoutBtn").textContent=w.started ? "Treino em andamento" : "Iniciar treino";
  $("#exerciseList").innerHTML=w.exercises.map((e,i)=>{
    const complete=e.sets_done>=e.sets_total;
    return `<article class="exercise" data-exercise-id="${e.id}">
      <div class="exercise-thumb">${String(i+1).padStart(2,"0")}</div>
      <div>
        <h4>${e.name}</h4>
        <p>${e.muscle}</p>
        <div class="exercise-stats"><span>${e.sets_total} séries</span><span>${e.reps} reps</span><span>${String(e.load_kg).replace(".",",")} kg</span></div>
      </div>
      <div class="set-controls">
        <button data-undo="${e.id}" title="Desfazer série">−</button>
        <button class="${complete?"done":""}" data-complete="${e.id}">${complete?"✓ Concluído":e.sets_done+"/"+e.sets_total+" séries"}</button>
      </div>
    </article>`;
  }).join("");
  $$("[data-complete]").forEach(b=>b.onclick=()=>completeSet(Number(b.dataset.complete)));
  $$("[data-undo]").forEach(b=>b.onclick=()=>undoSet(Number(b.dataset.undo)));

  const current=w.exercises.find(e=>e.sets_done<e.sets_total) || w.exercises[0];
  const currentIndex=Math.max(0,w.exercises.findIndex(e=>e.id===current?.id));
  const next=w.exercises[currentIndex+1];
  if(current && $("#mExerciseFocus")){
    $("#mExerciseFocus").innerHTML=`
      <div class="m-exercise-visual"><span class="m-exercise-badge">EXERCÍCIO ${currentIndex+1} DE ${w.exercises.length}</span></div>
      <div class="m-exercise-info">
        <h3>${current.name}</h3>
        <p>${current.muscle || "Treino de musculação"}</p>
        <div class="m-exercise-stats">
          <div><small>Séries</small><strong>${current.sets_total}</strong></div>
          <div><small>Repetições</small><strong>${current.reps}</strong></div>
          <div><small>Carga</small><strong>${String(current.load_kg).replace(".",",")} kg</strong></div>
        </div>
        <button class="m-primary-action" id="mCompleteSetBtn">${current.sets_done>=current.sets_total?"Exercício concluído":"Concluir série · "+current.sets_done+"/"+current.sets_total}</button>
      </div>`;
    const btn=$("#mCompleteSetBtn");
    if(btn) btn.onclick=()=>completeSet(current.id);
  }
  if($("#mNextExercise")){
    $("#mNextExercise").innerHTML=next ? `
      <small>PRÓXIMO EXERCÍCIO</small>
      <div><span class="m-next-thumb">${String(currentIndex+2).padStart(2,"0")}</span><p><strong>${next.name}</strong><small>${next.sets_total} séries · ${next.reps} repetições</small></p><span>›</span></div>`
      : `<small>PRÓXIMO EXERCÍCIO</small><div><span class="m-next-thumb">✓</span><p><strong>Último exercício</strong><small>Você está no fim deste treino</small></p><span>›</span></div>`;
  }
}

async function completeSet(id){
  try{
    const r=await api(`/api/exercises/${id}/complete-set`,{method:"POST"});
    await loadWorkout();
    if(r.workout_completed) toast("Treino concluído. Excelente consistência.");
    else toast("Série registrada.");
  }catch(e){toast(e.message)}
}

async function undoSet(id){
  try{
    await api(`/api/exercises/${id}/undo-set`,{method:"POST"});
    await loadWorkout();
    toast("Último registro desfeito.");
  }catch(e){toast(e.message)}
}

function renderRun(r){
  state.run=r;
  if(!r){
    $("#runTitle").textContent="Nenhuma corrida registrada";
    $("#runDistance").textContent="0,00 km";
    $("#runDuration").textContent="00:00";
    $("#metricDistance").textContent="0,00";
    $("#metricTime").textContent="00:00";
    $("#metricPace").textContent="--:--";
    $("#runCalories").textContent="0";
    $("#runHeart").textContent="0";
    $("#runElevation").textContent="0";
    if($("#mRunTitle")) $("#mRunTitle").textContent="Nenhuma corrida registrada";
    if($("#mRunDistance")) $("#mRunDistance").textContent="0,00";
    if($("#mRunDuration")) $("#mRunDuration").textContent="00:00";
    if($("#mMetricDistance")) $("#mMetricDistance").textContent="0,00";
    if($("#mMetricTime")) $("#mMetricTime").textContent="00:00";
    if($("#mMetricPace")) $("#mMetricPace").textContent="--:--";
    if($("#mRunCalories")) $("#mRunCalories").textContent="0";
    if($("#mRunHeart")) $("#mRunHeart").textContent="0";
    if($("#mRunElevation")) $("#mRunElevation").textContent="0";
    if($("#mHomeRunTitle")) $("#mHomeRunTitle").textContent="Nenhuma corrida registrada";
    drawRunChart();
    return;
  }
  $("#runTitle").textContent=r.title;
  $("#runDistance").textContent=Number(r.distance_km).toLocaleString("pt-BR",{minimumFractionDigits:2})+" km";
  $("#runDuration").textContent=r.duration;
  $("#metricDistance").textContent=Number(r.distance_km).toLocaleString("pt-BR",{minimumFractionDigits:2});
  $("#metricTime").textContent=r.duration;
  $("#metricPace").textContent=r.avg_pace;
  $("#runCalories").textContent=r.calories;
  $("#runHeart").textContent=r.avg_hr;
  $("#runElevation").textContent=r.elevation_m;
  if($("#mRunTitle")) $("#mRunTitle").textContent=r.title;
  if($("#mRunDistance")) $("#mRunDistance").textContent=Number(r.distance_km).toLocaleString("pt-BR",{minimumFractionDigits:2});
  if($("#mRunDuration")) $("#mRunDuration").textContent=r.duration;
  if($("#mMetricDistance")) $("#mMetricDistance").textContent=Number(r.distance_km).toLocaleString("pt-BR",{minimumFractionDigits:2});
  if($("#mMetricTime")) $("#mMetricTime").textContent=r.duration;
  if($("#mMetricPace")) $("#mMetricPace").textContent=r.avg_pace;
  if($("#mRunCalories")) $("#mRunCalories").textContent=r.calories;
  if($("#mRunHeart")) $("#mRunHeart").textContent=r.avg_hr;
  if($("#mRunElevation")) $("#mRunElevation").textContent=r.elevation_m;
  if($("#mHomeRunTitle")) $("#mHomeRunTitle").textContent=r.title;
  drawRunChart();
}

async function loadDashboard(){
  try{ renderDashboard(await api("/api/dashboard")); }catch(e){toast(e.message)}
}
async function loadWorkout(){
  try{ renderWorkout(await api("/api/workouts/current")); }catch(e){toast(e.message)}
}
async function loadRun(){
  try{ renderRun(await api("/api/runs/latest")); }catch(e){toast(e.message)}
}

function fitCanvas(canvas, cssHeight){
  if(!canvas) return null;
  const width=Math.max(280,canvas.parentElement.clientWidth-4);
  const dpr=Math.min(window.devicePixelRatio||1,2);
  canvas.style.width=width+"px";
  canvas.style.height=cssHeight+"px";
  canvas.width=width*dpr;
  canvas.height=cssHeight*dpr;
  const ctx=canvas.getContext("2d");
  ctx.setTransform(dpr,0,0,dpr,0,0);
  return {ctx,width,height:cssHeight};
}

function drawProgressChart(){
  const canvas=$("#progressChart");
  if(!canvas || !canvas.parentElement.offsetParent) return;
  const fit=fitCanvas(canvas, window.innerWidth > 700 ? 105 : 180); if(!fit)return;
  const {ctx,width,height}=fit;
  const data=(state.dashboard&&state.dashboard.weekly)||Array(12).fill(0);
  ctx.clearRect(0,0,width,height);
  ctx.strokeStyle="rgba(255,255,255,.07)";
  ctx.lineWidth=1;
  for(let y=25;y<height-25;y+=42){ctx.beginPath();ctx.moveTo(10,y);ctx.lineTo(width-10,y);ctx.stroke()}
  const pad=18, base=height-24, max=Math.max(1,...data)+2, gap=(width-pad*2)/data.length;
  data.forEach((v,i)=>{
    const h=v/max*(height-60);
    const x=pad+i*gap+gap*.14;
    const bw=Math.max(6,gap*.22);
    ctx.fillStyle="#00e5ff";
    ctx.fillRect(x,base-h*.72,bw,h*.72);
    ctx.fillStyle="#ff2d7a";
    ctx.fillRect(x+bw+3,base-h,bw,h);
  });
  ctx.strokeStyle="#8b5cf6";
  ctx.lineWidth=2;
  ctx.beginPath();
  data.forEach((v,i)=>{
    const x=pad+i*gap+gap*.45;
    const y=base-(v/max*(height-72))*.83-14;
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.stroke();
}

function drawRunChart(){
  const canvas=$("#runChart");
  if(!canvas || !canvas.parentElement.offsetParent) return;
  const fit=fitCanvas(canvas, window.innerWidth > 700 ? 150 : 150); if(!fit)return;
  const {ctx,width,height}=fit;
  const vals=state.run ? [4.8,6.2,3.9,5.6,4.5,6.8,3.7,5.2,7.1,4.9,5.8,4.3] : Array(12).fill(0);
  ctx.clearRect(0,0,width,height);
  for(let y=28;y<height-28;y+=40){ctx.strokeStyle="rgba(255,255,255,.06)";ctx.beginPath();ctx.moveTo(8,y);ctx.lineTo(width-8,y);ctx.stroke()}
  const pad=16, base=height-25, gap=(width-pad*2)/vals.length, max=8;
  vals.forEach((v,i)=>{
    const h=v/max*(height-55), x=pad+i*gap+gap*.2, bw=Math.max(7,gap*.52);
    const g=ctx.createLinearGradient(0,base-h,0,base);
    g.addColorStop(0,"#00e5ff");g.addColorStop(1,"#2370ff");
    ctx.fillStyle=g;
    ctx.fillRect(x,base-h,bw,h);
  });
}

function startLocalTimer(){
  if(state.timerHandle)return;
  state.timerStartedAt=Date.now();
  state.timerHandle=setInterval(()=>{
    const sec=Math.floor((Date.now()-state.timerStartedAt)/1000);
    const mm=String(Math.floor(sec/60)).padStart(2,"0");
    const ss=String(sec%60).padStart(2,"0");
    $("#workoutTimer").textContent=mm+":"+ss;
  },1000);
}

if($("#startWorkoutBtn")) $("#startWorkoutBtn").onclick=async()=>{
  if(!state.workout) return;
  try{
    const w=await api(`/api/workouts/${state.workout.id}/start`,{method:"POST"});
    renderWorkout(w); startLocalTimer(); toast("Treino iniciado.");
  }catch(e){toast(e.message)}
};

if($("#addModalityBtn")) $("#addModalityBtn").onclick=()=>$("#modalityDialog").showModal();
$("#saveModalityBtn").onclick=async(ev)=>{
  ev.preventDefault();
  const name=$("#modalityName").value.trim();
  const icon=$("#modalityIcon").value.trim()||"●";
  if(!name)return;
  try{
    await api("/api/modalities",{method:"POST",body:JSON.stringify({name,icon})});
    $("#modalityDialog").close();
    $("#modalityForm").reset();
    toast(name+" adicionada à estrutura do RITMOX.");
  }catch(e){toast(e.message)}
};

$("#stravaBtn").onclick=async()=>{
  try{
    const s=await api("/api/integrations/strava");
    if(!s.configured) toast("Interface pronta. Falta configurar as credenciais OAuth do Strava no Render.");
    else toast("Credenciais detectadas. Próxima etapa: concluir o fluxo OAuth.");
  }catch(e){toast(e.message)}
};

$("#comingSoonBtn").onclick=()=>toast("Comunidade, desafios e rankings entram nas próximas etapas.");

document.addEventListener("click",(ev)=>{
  const healthAction=ev.target.closest("[data-health-action]");
  if(healthAction){
    ev.preventDefault();
    const action=healthAction.dataset.healthAction;
    if(action==="assessment") openHealthAssessment();
    if(action==="clearance") openClearanceDialog();
    if(action==="review") openHealthAssessment();
    return;
  }

  const target=ev.target.closest("[data-page]");
  if(target){
    ev.preventDefault();
    navigate(target.dataset.page);
    return;
  }

  const more=ev.target.closest(".m-more");
  if(more){
    ev.preventDefault();
    toast("Mais opções serão adicionadas nesta tela.");
    return;
  }

  const runTab=ev.target.closest(".m-run-tabs button");
  if(runTab){
    $$(".m-run-tabs button").forEach(b=>b.classList.remove("active"));
    runTab.classList.add("active");
    if(runTab.textContent.trim()!=="Resumo"){
      toast(runTab.textContent.trim()+" ficará disponível quando houver uma corrida registrada.");
    }
  }
});
$$("[data-open]").forEach(card=>card.addEventListener("click",(ev)=>{
  if(ev.target.closest("button")) ev.preventDefault();
  navigate(card.dataset.open);
}));
$$(".hero-action").forEach(btn=>btn.addEventListener("click",(ev)=>{
  ev.stopPropagation();
  const card=btn.closest("[data-open]");
  navigate(card.dataset.open);
}));

$("#globalSearch").addEventListener("input",ev=>{
  const q=ev.target.value.trim().toLowerCase();
  if(!q)return;
  if(["corrida","run","pace","ritmo"].some(x=>q.includes(x))) navigate("run");
  else if(["treino","musculação","musculacao","agachamento","exercício","exercicio"].some(x=>q.includes(x))) navigate("workouts");
});



function openDialogSafe(dialog){
  if(!dialog) return;
  dialog.hidden=false;
  dialog.classList.add("is-open");
  document.body.classList.add("modal-open");
  const first=dialog.querySelector("input,select,textarea,button");
  setTimeout(()=>first?.focus(),30);
}

function closeDialogSafe(dialog){
  if(!dialog) return;
  dialog.classList.remove("is-open");
  dialog.hidden=true;
  if(!$(".app-modal-overlay.is-open")) document.body.classList.remove("modal-open");
}

function questionTypeLabel(type){
  const map={
    yes_no:"Sim / Não",
    text:"Texto curto",
    textarea:"Texto longo",
    number:"Número",
    date:"Data",
    select:"Seleção única",
    multiselect:"Múltipla seleção"
  };
  return map[type]||type;
}

async function loadAnamnesisFormConfig(force=false){
  if(state.health.formQuestions.length && !force) return {
    configured:state.health.formConfigured,
    questions:state.health.formQuestions
  };
  const result=await api("/api/anamnesis/form");
  state.health.formConfigured=!!result.configured;
  state.health.formQuestions=result.questions||[];
  return result;
}

function renderDynamicAnamnesis(){
  const host=$("#dynamicAnamnesisQuestions");
  if(!host) return;
  const questions=state.health.formQuestions||[];
  const saved=state.health.assessment?.data?.answers||{};
  if(!questions.length){
    host.innerHTML=`<div class="anamnesis-not-configured">
      <strong>Anamnese ainda não parametrizada</strong>
      <p>Adicione as perguntas em Configurações → Anamnese.</p>
      <button type="button" class="ghost-btn" data-page="settings">Abrir configurações</button>
    </div>`;
    return;
  }

  const sections=[];
  questions.forEach(q=>{
    let group=sections.find(x=>x.name===q.section);
    if(!group){ group={name:q.section,questions:[]}; sections.push(group); }
    group.questions.push(q);
  });

  host.innerHTML=sections.map((group,sectionIndex)=>`
    <fieldset class="health-section dynamic-health-section">
      <legend>${sectionIndex+1}. ${escapeHTML(group.name)}</legend>
      <div class="dynamic-question-list">
        ${group.questions.map(renderAnamnesisQuestion).join("")}
      </div>
    </fieldset>
  `).join("");

  questions.forEach(q=>{
    const value=saved[String(q.id)];
    if(value===undefined || value===null) return;
    const root=host.querySelector(`[data-question="${q.id}"]`);
    if(!root) return;
    if(q.question_type==="multiselect"){
      const selected=new Set(Array.isArray(value)?value:[]);
      root.querySelectorAll("[data-anamnesis-option]").forEach(btn=>{
        const checked=selected.has(btn.dataset.value);
        btn.setAttribute("aria-checked",checked?"true":"false");
        btn.classList.toggle("is-checked",checked);
      });
    }else{
      const input=root.querySelector("[data-answer]");
      if(!input) return;
      if(q.question_type==="yes_no" && typeof value==="boolean"){
        input.value=value?"sim":"nao";
      }else{
        input.value=value;
      }
    }
  });

  setAriaCheck($("#haConsentTruthful"),!!state.health.assessment?.data?.consent_truthful);
  setAriaCheck($("#haConsentScreening"),!!state.health.assessment?.data?.consent_screening);
  setAriaCheck($("#haSignatureConfirm"),false);
}

function renderAnamnesisQuestion(q){
  const req=q.required?'<span class="required-mark">*</span>':"";
  const help=q.help_text?`<small class="question-help">${escapeHTML(q.help_text)}</small>`:"";
  const common=`data-question="${q.id}"`;
  const controlId=`anamnesis-control-${q.id}`;
  let control="";

  if(q.question_type==="yes_no"){
    control=`<select id="${controlId}" data-answer ${q.required?"required":""}>
      <option value="">Selecione</option>
      <option value="sim">Sim</option>
      <option value="nao">Não</option>
    </select>`;
  }else if(q.question_type==="textarea"){
    control=`<textarea id="${controlId}" data-answer rows="3" ${q.required?"required":""} placeholder="${escapeHTML(q.placeholder||"")}"></textarea>`;
  }else if(q.question_type==="number"){
    control=`<input id="${controlId}" data-answer type="number" step="any" ${q.required?"required":""} placeholder="${escapeHTML(q.placeholder||"")}">`;
  }else if(q.question_type==="date"){
    control=`<input id="${controlId}" data-answer type="date" ${q.required?"required":""}>`;
  }else if(q.question_type==="select"){
    control=`<select id="${controlId}" data-answer ${q.required?"required":""}>
      <option value="">Selecione</option>
      ${(q.options||[]).map(opt=>`<option value="${escapeHTML(opt)}">${escapeHTML(opt)}</option>`).join("")}
    </select>`;
  }else if(q.question_type==="multiselect"){
    control=`<div class="dynamic-multiselect" role="group" aria-labelledby="anamnesis-label-${q.id}">
      ${(q.options||[]).map(opt=>`<button type="button" class="dynamic-checkbox-option" data-anamnesis-option data-value="${escapeHTML(opt)}" role="checkbox" aria-checked="false">
        <span class="dynamic-checkbox-box" aria-hidden="true"></span>
        <span class="dynamic-checkbox-text">${escapeHTML(opt)}</span>
      </button>`).join("")}
    </div>`;
  }else{
    control=`<input id="${controlId}" data-answer type="text" ${q.required?"required":""} placeholder="${escapeHTML(q.placeholder||"")}">`;
  }

  const labelFor=q.question_type==="multiselect"?"":` for="${controlId}"`;
  return `<div class="dynamic-question" ${common}>
    <label id="anamnesis-label-${q.id}" class="question-label"${labelFor}>${escapeHTML(q.label)} ${req}</label>
    ${help}
    ${control}
  </div>`;
}

function collectDynamicAnswers(){
  const answers={};
  (state.health.formQuestions||[]).forEach(q=>{
    const root=$(`[data-question="${q.id}"]`,$("#dynamicAnamnesisQuestions"));
    if(!root) return;
    if(q.question_type==="multiselect"){
      answers[String(q.id)]=$$('[data-anamnesis-option][aria-checked="true"]',root).map(btn=>btn.dataset.value);
    }else{
      const input=$("[data-answer]",root);
      if(!input) return;
      if(q.question_type==="yes_no"){
        answers[String(q.id)]=input.value===""?null:input.value==="sim";
      }else if(q.question_type==="number"){
        answers[String(q.id)]=input.value===""?null:Number(input.value);
      }else{
        answers[String(q.id)]=input.value;
      }
    }
  });
  return answers;
}


function clearAnamnesisFeedback(){
  const box=$("#anamnesisFormFeedback");
  if(box){box.hidden=true;box.innerHTML="";}
  $$(".dynamic-question.has-error").forEach(el=>el.classList.remove("has-error"));
  $$(".health-section.has-error").forEach(el=>el.classList.remove("has-error"));
}
function showAnamnesisFeedback(title,messages=[]){
  const box=$("#anamnesisFormFeedback");
  if(!box) return;
  const list=(messages||[]).filter(Boolean);
  box.innerHTML="<strong>"+escapeHTML(title)+"</strong>"+(list.length?"<ul>"+list.map(x=>"<li>"+escapeHTML(x)+"</li>").join("")+"</ul>":"");
  box.hidden=false;
}
function signatureNameFromForm(answers){
  const typed=$("#haSignatureName")?.value.trim()||"";
  if(typed) return typed;
  const q=(state.health.formQuestions||[]).find(item=>(item.label||"").toLowerCase().includes("nome completo"));
  if(!q) return "";
  const value=answers?.[String(q.id)];
  return typeof value==="string"?value.trim():"";
}
function validateHealthAssessment(answers){
  clearAnamnesisFeedback();
  const messages=[];
  let firstElement=null;
  (state.health.formQuestions||[]).forEach(q=>{
    const value=answers[String(q.id)];
    const empty=value===null||value===undefined||value===""||(Array.isArray(value)&&value.length===0);
    const root=$(`[data-question="${q.id}"]`,$("#dynamicAnamnesisQuestions"));
    const invalid=q.required&&empty;
    root?.classList.toggle("has-error",invalid);
    if(invalid){
      messages.push(q.label);
      if(!firstElement) firstElement=root;
    }
  });

  if(!isAriaChecked($("#haConsentTruthful"))){
    messages.push("Confirme que as respostas são verdadeiras e atuais.");
    $("#haConsentTruthful")?.closest(".health-section")?.classList.add("has-error");
    if(!firstElement) firstElement=$("#haConsentTruthful");
  }
  if(!isAriaChecked($("#haConsentScreening"))){
    messages.push("Confirme a declaração sobre a finalidade da triagem.");
    $("#haConsentScreening")?.closest(".health-section")?.classList.add("has-error");
    if(!firstElement) firstElement=$("#haConsentScreening");
  }

  const signatureName=signatureNameFromForm(answers);
  if(signatureName.length<2){
    messages.push("Informe o nome do aluno responsável pela assinatura.");
    $("#haSignatureSection")?.classList.add("has-error");
    if(!firstElement) firstElement=$("#haSignatureName");
  }
  if(!state.health.signatureHasInk){
    messages.push("Assine no campo de assinatura antes de salvar.");
    $("#haSignatureSection")?.classList.add("has-error");
    if(!firstElement) firstElement=$("#haSignatureCanvas");
  }
  if(!isAriaChecked($("#haSignatureConfirm"))){
    messages.push("Confirme que a assinatura pertence ao aluno.");
    $("#haSignatureSection")?.classList.add("has-error");
    if(!firstElement) firstElement=$("#haSignatureConfirm");
  }
  return {ok:messages.length===0,messages,firstElement,signatureName};
}
function clearHealthSignaturePad(){
  const canvas=$("#haSignatureCanvas");
  if(!canvas) return;
  const ctx=canvas.getContext("2d");
  ctx.clearRect(0,0,canvas.width,canvas.height);
  state.health.signatureHasInk=false;
  const status=$("#haSignatureStatus");
  if(status){status.textContent="Aguardando assinatura";status.classList.remove("is-signed");}
}
function setupHealthSignaturePad(){
  const canvas=$("#haSignatureCanvas");
  if(!canvas) return;
  clearHealthSignaturePad();
  setAriaCheck($("#haSignatureConfirm"),false);

  const answers=collectDynamicAnswers();
  const signatureName=$("#haSignatureName");
  if(signatureName){
    signatureName.dataset.userEdited="";
    signatureName.value=signatureNameFromForm(answers);
  }

  const nameQ=(state.health.formQuestions||[]).find(item=>(item.label||"").toLowerCase().includes("nome completo"));
  if(nameQ&&signatureName){
    const source=$(`[data-question="${nameQ.id}"] [data-answer]`,$("#dynamicAnamnesisQuestions"));
    if(source&&!source.dataset.signatureSyncBound){
      source.dataset.signatureSyncBound="1";
      source.addEventListener("input",()=>{
        if(!signatureName.dataset.userEdited) signatureName.value=source.value||"";
      });
    }
    signatureName.oninput=()=>{signatureName.dataset.userEdited="1";};
  }

  if(canvas.dataset.signatureBound==="1") return;
  canvas.dataset.signatureBound="1";
  canvas.style.touchAction="none";
  const ctx=canvas.getContext("2d");
  ctx.strokeStyle="#ff2d7a";
  ctx.lineWidth=6;
  ctx.lineCap="round";
  ctx.lineJoin="round";
  let drawing=false;

  function point(ev){
    const rect=canvas.getBoundingClientRect();
    return {
      x:(ev.clientX-rect.left)*(canvas.width/rect.width),
      y:(ev.clientY-rect.top)*(canvas.height/rect.height)
    };
  }
  canvas.addEventListener("pointerdown",ev=>{
    ev.preventDefault();
    drawing=true;
    canvas.setPointerCapture?.(ev.pointerId);
    const p=point(ev);
    ctx.beginPath();
    ctx.moveTo(p.x,p.y);
  });
  canvas.addEventListener("pointermove",ev=>{
    if(!drawing) return;
    ev.preventDefault();
    const p=point(ev);
    ctx.lineTo(p.x,p.y);
    ctx.stroke();
    state.health.signatureHasInk=true;
    const status=$("#haSignatureStatus");
    if(status){status.textContent="Assinatura registrada";status.classList.add("is-signed");}
    $("#haSignatureSection")?.classList.remove("has-error");
  });
  const finish=ev=>{
    if(!drawing) return;
    drawing=false;
    try{canvas.releasePointerCapture?.(ev.pointerId);}catch{}
  };
  canvas.addEventListener("pointerup",finish);
  canvas.addEventListener("pointercancel",finish);
  canvas.addEventListener("pointerleave",ev=>{if(ev.buttons===0) finish(ev);});
}

async function openHealthAssessment(){
  try{
    await loadAnamnesisFormConfig(true);
    if(!state.health.formConfigured){
      toast("Configure as perguntas da anamnese antes de aplicá-la.");
      navigate("settings");
      return;
    }
    renderDynamicAnamnesis();
    openDialogSafe($("#healthAssessmentDialog"));
    setupHealthSignaturePad();
    clearAnamnesisFeedback();
  }catch(e){toast(e.message)}
}

function closeHealthAssessment(){
  closeDialogSafe($("#healthAssessmentDialog"));
}

async function submitHealthAssessment(ev){
  ev.preventDefault();
  let submitBtn=null;
  let originalText="Concluir e salvar";
  try{
    if(!state.health.formConfigured){
      showAnamnesisFeedback("A anamnese ainda não foi parametrizada.");
      toast("A anamnese ainda não foi parametrizada.");
      return;
    }

    const answers=collectDynamicAnswers();
    const validation=validateHealthAssessment(answers);
    if(!validation.ok){
      showAnamnesisFeedback("Existem pendências antes de salvar.",validation.messages);
      toast(`Revise ${validation.messages.length} pendência${validation.messages.length===1?"":"s"} antes de salvar.`);
      validation.firstElement?.scrollIntoView({behavior:"smooth",block:"center"});
      return;
    }

    const payload={
      answers,
      consent_truthful:isAriaChecked($("#haConsentTruthful")),
      consent_screening:isAriaChecked($("#haConsentScreening")),
      signature_requested:false,
      signature_name:validation.signatureName,
      signature_data:$("#haSignatureCanvas").toDataURL("image/png"),
      signature_confirmed:isAriaChecked($("#haSignatureConfirm"))
    };

    submitBtn=$("#submitHealthAssessmentBtn");
    originalText=submitBtn?.textContent||originalText;
    if(submitBtn){
      submitBtn.disabled=true;
      submitBtn.textContent="Salvando...";
      submitBtn.setAttribute("aria-busy","true");
    }
    clearAnamnesisFeedback();

    const result=await api("/api/health-assessment",{method:"POST",body:JSON.stringify(payload)});
    state.health.assessment=result;
    state.health.loaded=true;
    closeHealthAssessment();
    renderHealthGate();
    toast("Anamnese salva com assinatura no perfil do aluno.");
    if(result.training_allowed){
      await loadTrainingCalendar(false);
    }
  }catch(e){
    const message=e?.message||"Ocorreu um erro inesperado ao salvar.";
    showAnamnesisFeedback("Não foi possível salvar a anamnese.",[message]);
    toast("Erro ao salvar: "+message);
    console.error("Falha ao salvar anamnese",e);
  }finally{
    if(submitBtn){
      submitBtn.disabled=false;
      submitBtn.textContent=originalText;
      submitBtn.removeAttribute("aria-busy");
    }
  }
}

async function loadHealthGate(){
  if(!$("#healthGate")) return;
  try{
    const [assessment,form]=await Promise.all([
      api("/api/health-assessment/latest"),
      api("/api/anamnesis/form")
    ]);
    state.health.assessment=assessment;
    state.health.loaded=true;
    state.health.formConfigured=!!form.configured;
    state.health.formQuestions=form.questions||[];
    renderHealthGate();
    if(assessment?.training_allowed && form.configured){
      await loadTrainingCalendar(false);
    }
  }catch(e){toast(e.message)}
}



function profileInitial(name){
  return (String(name||"Júnior").trim().charAt(0)||"J").toUpperCase();
}
function profileBirthLabel(value){
  if(!value) return "Não informada";
  const parts=value.split("-");
  return parts.length===3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value;
}
async function loadUserProfile(){
  try{
    state.profile=await api("/api/profile");
    renderUserProfile();
  }catch(e){
    toast(e.message);
  }
}
function applyProfilePhoto(el,photo,name){
  if(!el) return;
  if(photo){
    el.style.backgroundImage=`url("${photo}")`;
    el.style.backgroundSize="cover";
    el.style.backgroundPosition="center";
    el.textContent="";
    el.classList.add("has-photo");
  }else{
    el.style.backgroundImage="";
    el.textContent=profileInitial(name);
    el.classList.remove("has-photo");
  }
}
function renderUserProfile(){
  const p=state.profile||{name:"Júnior",email:"",birth_date:"",goals:"",photo_data:""};
  const name=p.name||"Júnior";
  const first=name.trim().split(/s+/)[0]||"Júnior";
  if($("#profileNameTitle")) $("#profileNameTitle").textContent=name;
  if($("#profileAvatarFallback")) $("#profileAvatarFallback").textContent=profileInitial(name);
  if($("#profileInfoName")) $("#profileInfoName").textContent=name;
  if($("#profileInfoEmail")) $("#profileInfoEmail").textContent=p.email||"Não informado";
  if($("#profileInfoBirth")) $("#profileInfoBirth").textContent=profileBirthLabel(p.birth_date);
  if($("#profileInfoGoals")) $("#profileInfoGoals").textContent=p.goals||"Não informado";

  const photo=$("#profilePhotoImage");
  const fallback=$("#profileAvatarFallback");
  if(photo&&fallback){
    if(p.photo_data){
      photo.src=p.photo_data;
      photo.hidden=false;
      fallback.hidden=true;
    }else{
      photo.removeAttribute("src");
      photo.hidden=true;
      fallback.hidden=false;
    }
  }

  applyProfilePhoto($(".m-avatar"),p.photo_data,name);
  applyProfilePhoto($(".avatar-btn"),p.photo_data,name);
  const mobileGreeting=$(".m-greeting h1");
  if(mobileGreeting) mobileGreeting.textContent=`Bom dia, ${first}!`;
  pageMeta.home[0]=`Bom dia, ${first}!`;
  if(state.page==="home"&&$("#pageTitle")) $("#pageTitle").textContent=pageMeta.home[0];
}
function openProfileEditDialog(focusName=false){
  const p=state.profile||{name:"Júnior",email:"",birth_date:"",goals:""};
  $("#profileEditName").value=p.name||"Júnior";
  $("#profileEditEmail").value=p.email||"";
  $("#profileEditBirth").value=p.birth_date||"";
  $("#profileEditGoals").value=p.goals||"";
  openDialogSafe($("#profileEditDialog"));
  setTimeout(()=>focusName?$("#profileEditName")?.focus():$("#profileEditEmail")?.focus(),40);
}
function closeProfileEditDialog(){
  closeDialogSafe($("#profileEditDialog"));
}
async function saveProfileEdit(ev){
  ev.preventDefault();
  const p=state.profile||{};
  const payload={
    name:$("#profileEditName").value.trim(),
    email:$("#profileEditEmail").value.trim(),
    birth_date:$("#profileEditBirth").value,
    goals:$("#profileEditGoals").value.trim(),
    photo_data:p.photo_data||""
  };
  const btn=$("#saveProfileEditBtn");
  const old=btn?.textContent||"Salvar alterações";
  if(btn){btn.disabled=true;btn.textContent="Salvando...";}
  try{
    state.profile=await api("/api/profile",{method:"PUT",body:JSON.stringify(payload)});
    renderUserProfile();
    closeProfileEditDialog();
    toast("Perfil atualizado.");
  }catch(e){
    toast(e.message);
  }finally{
    if(btn){btn.disabled=false;btn.textContent=old;}
  }
}
function resizeProfilePhoto(file){
  return new Promise((resolve,reject)=>{
    if(!file||!file.type.startsWith("image/")){reject(new Error("Selecione uma imagem válida."));return;}
    if(file.size>12*1024*1024){reject(new Error("A imagem deve ter no máximo 12 MB."));return;}
    const reader=new FileReader();
    reader.onerror=()=>reject(new Error("Não foi possível ler a imagem."));
    reader.onload=()=>{
      const img=new Image();
      img.onerror=()=>reject(new Error("Formato de imagem não suportado."));
      img.onload=()=>{
        const size=512;
        const canvas=document.createElement("canvas");
        canvas.width=size; canvas.height=size;
        const ctx=canvas.getContext("2d");
        const crop=Math.min(img.naturalWidth,img.naturalHeight);
        const sx=(img.naturalWidth-crop)/2;
        const sy=(img.naturalHeight-crop)/2;
        ctx.drawImage(img,sx,sy,crop,crop,0,0,size,size);
        resolve(canvas.toDataURL("image/jpeg",0.84));
      };
      img.src=reader.result;
    };
    reader.readAsDataURL(file);
  });
}
async function handleProfilePhoto(file){
  try{
    const photo=await resizeProfilePhoto(file);
    const current=state.profile||await api("/api/profile");
    state.profile=await api("/api/profile",{
      method:"PUT",
      body:JSON.stringify({
        name:current.name||"Júnior",
        email:current.email||"",
        birth_date:current.birth_date||"",
        goals:current.goals||"",
        photo_data:photo
      })
    });
    renderUserProfile();
    toast("Foto de perfil atualizada.");
  }catch(e){
    toast(e.message);
  }finally{
    const input=$("#profilePhotoInput");
    if(input) input.value="";
  }
}

function isAriaChecked(el){
  return !!el && el.getAttribute("aria-checked")==="true";
}
function setAriaCheck(el,checked){
  if(!el) return;
  el.setAttribute("aria-checked",checked?"true":"false");
  el.classList.toggle("is-checked",!!checked);
}
function toggleAriaCheck(el){ if(el) setAriaCheck(el,!isAriaChecked(el)); }
function formatDateTimeBR(value){
  if(!value) return "—";
  const d=new Date(value);
  return Number.isNaN(d.getTime())?String(value):d.toLocaleString("pt-BR",{dateStyle:"short",timeStyle:"short"});
}
function assessmentStatusLabel(a){
  if(!a) return "Sem anamnese";
  if(a.professional_clearance) return "Liberada";
  if(a.risk_status==="attention_required") return "Requer avaliação";
  return "Concluída";
}
function signatureStatusLabel(a){
  if(!a) return "—";
  if(a.signature_status==="signed") return "Assinada";
  if(a.signature_status==="pending") return "Assinatura pendente";
  return "Não solicitada";
}
async function loadProfileAnamnesis(){
  if(!$("#profileAnamnesisCard")) return;
  try{ state.health.profile=await api("/api/profile/anamnesis"); renderProfileAnamnesis(); }
  catch(e){ $("#profileAnamnesisSubtitle").textContent="Não foi possível carregar a anamnese."; toast(e.message); }
}
function renderProfileAnamnesis(){
  const latest=state.health.profile?.latest||null;
  const status=$("#profileAnamnesisStatus"), subtitle=$("#profileAnamnesisSubtitle"), meta=$("#profileAnamnesisMeta");
  const view=$("#viewProfileAnamnesisBtn"), sign=$("#signProfileAnamnesisBtn"), pdf=$("#exportProfileAnamnesisBtn");
  if(!latest){
    status.textContent="Não preenchida"; status.className="status-pill"; subtitle.textContent="Nenhuma anamnese foi salva neste perfil.";
    meta.innerHTML=""; view.hidden=sign.hidden=pdf.hidden=true; return;
  }
  status.textContent=assessmentStatusLabel(latest);
  status.className="status-pill "+(latest.risk_status==="attention_required"&&!latest.professional_clearance?"warning":"connected");
  subtitle.textContent="Última atualização: "+formatDateTimeBR(latest.updated_at||latest.completed_at);
  meta.innerHTML=
    '<div class="profile-meta-tile"><span class="profile-meta-icon pink"><svg><use href="#i-file"/></svg></span><span><small>TRIAGEM</small><strong>'+escapeHTML(assessmentStatusLabel(latest))+'</strong></span></div>'+
    '<div class="profile-meta-tile"><span class="profile-meta-icon cyan"><svg><use href="#i-file"/></svg></span><span><small>ASSINATURA</small><strong>'+escapeHTML(signatureStatusLabel(latest))+'</strong></span></div>'+
    '<div class="profile-meta-tile"><span class="profile-meta-icon purple">#</span><span><small>REGISTRO</small><strong>#'+latest.id+'</strong></span></div>';
  view.hidden=false; pdf.hidden=false; sign.hidden=latest.signature_status!=="pending";
}
function answerText(value){
  if(value===null||value===undefined||value==="") return "Não informado";
  if(typeof value==="boolean") return value?"Sim":"Não";
  if(Array.isArray(value)) return value.length?value.join(", "):"Não informado";
  return String(value);
}
function openProfileAnamnesis(){
  const a=state.health.profile?.latest; if(!a) return;
  const questions=a.data?.questions_snapshot||[], answers=a.data?.answers||{}; let current=""; const body=[];
  questions.forEach(q=>{
    if(q.section!==current){current=q.section;body.push("<h4>"+escapeHTML(current||"Geral")+"</h4>");}
    body.push('<div class="profile-answer-row"><strong>'+escapeHTML(q.label||"Pergunta")+'</strong><span>'+escapeHTML(answerText(answers[String(q.id)]))+'</span></div>');
  });
  body.push("<h4>Declarações e assinatura</h4>");
  body.push('<div class="profile-answer-row"><strong>Respostas verdadeiras e atuais</strong><span>'+(a.data?.consent_truthful?"Confirmado":"Não confirmado")+'</span></div>');
  body.push('<div class="profile-answer-row"><strong>Ciência da triagem</strong><span>'+(a.data?.consent_screening?"Confirmado":"Não confirmado")+'</span></div>');
  body.push('<div class="profile-answer-row"><strong>Assinatura</strong><span>'+escapeHTML(signatureStatusLabel(a))+(a.signature?.signer_name?" · "+escapeHTML(a.signature.signer_name):"")+'</span></div>');
  $("#profileAnamnesisDetails").innerHTML=body.join(""); openDialogSafe($("#profileAnamnesisDialog"));
}
function exportProfileAnamnesis(){
  const a=state.health.profile?.latest; if(!a){toast("Nenhuma anamnese salva no perfil.");return;}
  window.open("/api/health-assessment/"+a.id+"/pdf?ts="+Date.now(),"_blank");
}
function openSignatureDialog(){
  const a=state.health.profile?.latest; if(!a||a.signature_status!=="pending") return;
  const questions=a.data?.questions_snapshot||[];
  const nameQ=questions.find(q=>(q.label||"").toLowerCase().includes("nome completo"));
  const savedName=nameQ?a.data?.answers?.[String(nameQ.id)]:"";
  $("#signatureName").value=savedName||""; setAriaCheck($("#signatureAccept"),false); openDialogSafe($("#signatureDialog"));
}
async function submitSignature(ev){
  ev.preventDefault(); const a=state.health.profile?.latest; if(!a) return;
  const signer_name=$("#signatureName").value.trim(), accepted=isAriaChecked($("#signatureAccept"));
  if(signer_name.length<2){toast("Informe o nome completo para assinar.");return;}
  if(!accepted){toast("Confirme a declaração de assinatura eletrônica.");return;}
  try{
    const result=await api("/api/health-assessment/"+a.id+"/signature",{method:"POST",body:JSON.stringify({signer_name:signer_name,accepted:true})});
    closeDialogSafe($("#signatureDialog")); state.health.profile=await api("/api/profile/anamnesis"); state.health.assessment=result;
    renderProfileAnamnesis(); toast("Anamnese assinada e atualizada no perfil.");
  }catch(e){toast(e.message)}
}

function requestStatusText(request){
  if(!request) return "";
  if(request.status==="pending") return "Solicitação enviada · aguardando análise do profissional";
  if(request.status==="approved") return "Liberação aprovada pelo profissional";
  if(request.status==="rejected") return "Solicitação não aprovada · revise a orientação profissional";
  return "";
}

function renderHealthGate(){
  const gate=$("#healthGate");
  const calendar=$("#trainingCalendar");
  if(!gate || !calendar) return;
  const assessment=state.health.assessment;
  const startBtn=$("#startHealthAssessmentBtn");
  const configBtn=$("#configureAnamnesisBtn");
  const requestBtn=$("#registerClearanceBtn");
  const flags=$("#healthGateFlags");

  [startBtn,configBtn,requestBtn].forEach(btn=>{if(btn) btn.hidden=true;});
  requestBtn.disabled=false;
  requestBtn.classList.remove("is-pending");
  flags.innerHTML="";

  if(!state.health.formConfigured){
    gate.hidden=false;
    calendar.hidden=true;
    $("#healthGateTitle").textContent="Configure a anamnese antes de utilizá-la";
    $("#healthGateText").textContent="Ainda não existem perguntas cadastradas. Abra Configurações → Anamnese e monte o formulário que será aplicado ao aluno.";
    configBtn.hidden=false;
    return;
  }

  if(!assessment){
    gate.hidden=false;
    calendar.hidden=true;
    $("#healthGateTitle").textContent="Antes do primeiro treino, complete a anamnese";
    $("#healthGateText").textContent="A anamnese configurada está pronta. O aluno precisa respondê-la antes do planejamento.";
    startBtn.textContent="Preencher anamnese";
    startBtn.hidden=false;
    return;
  }

  if(assessment.training_allowed){
    gate.hidden=true;
    calendar.hidden=false;
    $("#healthStatusText").textContent=assessment.professional_clearance
      ? `Anamnese concluída · liberação aprovada por ${assessment.clearance_provider||"profissional responsável"}`
      : "Anamnese concluída · sem respostas configuradas como alerta";
    return;
  }

  gate.hidden=false;
  calendar.hidden=true;
  $("#healthGateTitle").textContent="Avaliação profissional necessária";
  $("#healthGateText").textContent="A anamnese identificou respostas parametrizadas como alerta. O planejamento permanece bloqueado.";
  flags.innerHTML=(assessment.red_flags||[]).map(flag=>`<div class="health-flag">${escapeHTML(flag)}</div>`).join("");
  startBtn.textContent="Revisar anamnese";
  startBtn.hidden=false;
  requestBtn.hidden=false;

  const request=assessment.clearance_request;
  if(request?.status==="pending"){
    requestBtn.textContent="Solicitação enviada · aguardando profissional";
    requestBtn.disabled=true;
    requestBtn.classList.add("is-pending");
  }else if(request?.status==="rejected"){
    requestBtn.textContent="Solicitar nova avaliação profissional";
  }else{
    requestBtn.textContent="Solicitar liberação ao profissional";
  }
  if(request){
    flags.insertAdjacentHTML("beforeend",`<div class="health-request-status ${request.status}">${escapeHTML(requestStatusText(request))}</div>`);
  }
}

function openClearanceDialog(){
  const assessment=state.health.assessment;
  if(!assessment){
    toast("Conclua a anamnese antes de solicitar a liberação profissional.");
    return;
  }
  if(assessment.training_allowed){
    toast("O planejamento já está liberado.");
    return;
  }
  const current=assessment.clearance_request;
  $("#clearanceProvider").value=current?.professional_name||"";
  $("#clearanceEmail").value=current?.professional_email||"";
  $("#clearanceMessage").value=current?.message||"";
  openDialogSafe($("#clearanceDialog"));
}

function closeClearanceDialog(){
  closeDialogSafe($("#clearanceDialog"));
}

async function submitClearance(ev){
  ev.preventDefault();
  const professional_name=$("#clearanceProvider").value.trim();
  const professional_email=$("#clearanceEmail").value.trim();
  const message=$("#clearanceMessage").value.trim();
  if(!professional_name||!professional_email){
    toast("Informe o profissional responsável e o e-mail.");
    return;
  }
  try{
    await api("/api/clearance-requests",{
      method:"POST",
      body:JSON.stringify({professional_name,professional_email,message})
    });
    state.health.assessment=await api("/api/health-assessment/latest");
    closeClearanceDialog();
    renderHealthGate();
    toast("Solicitação enviada ao profissional. A aprovação não pode ser feita pelo aluno.");
  }catch(e){toast(e.message)}
}

async function loadAnamnesisSettings(){
  const host=$("#anamnesisQuestionList");
  if(!host) return;
  try{
    const questions=await api("/api/settings/anamnesis/questions");
    state.settings.anamnesisQuestions=questions||[];
    state.health.formQuestions=(questions||[]).filter(q=>q.active);
    state.health.formConfigured=state.health.formQuestions.length>0;
    renderAnamnesisSettings();
  }catch(e){toast(e.message)}
}

function renderAnamnesisSettings(){
  const list=$("#anamnesisQuestionList");
  const summary=$("#anamnesisSettingsSummary");
  if(!list||!summary) return;
  const questions=state.settings.anamnesisQuestions||[];
  const active=questions.filter(q=>q.active).length;
  const alerts=questions.filter(q=>q.active&&q.risk_enabled).length;
  const sections=[...new Set(questions.map(q=>q.section))];
  summary.innerHTML=`<span><strong>${questions.length}</strong> pergunta${questions.length===1?"":"s"}</span>
    <span><strong>${sections.length}</strong> seções</span>
    <span><strong>${active}</strong> ativa${active===1?"":"s"}</span>
    <span><strong>${alerts}</strong> com regra de alerta</span>`;

  if(!questions.length){
    list.innerHTML=`<div class="settings-empty">
      <strong>Nenhuma pergunta cadastrada</strong>
      <p>Use “Restaurar padrão” para carregar a anamnese RITMOX ou “Nova pergunta” para começar do zero.</p>
    </div>`;
    return;
  }

  let globalIndex=0;
  list.innerHTML=sections.map(section=>{
    const sectionQuestions=questions.filter(q=>q.section===section);
    const cards=sectionQuestions.map(q=>{
      globalIndex+=1;
      return `<article class="question-setting-card ${q.active?"":"is-inactive"}">
        <div class="question-order">${String(globalIndex).padStart(2,"0")}</div>
        <div class="question-setting-main">
          <div class="question-setting-meta">
            <span class="question-type-badge">${escapeHTML(questionTypeLabel(q.question_type))}</span>
            ${q.required?'<span class="required-badge">Obrigatória</span>':""}
            ${q.risk_enabled?'<span class="risk-badge">Alerta</span>':""}
            ${q.active?"":'<span class="inactive-badge">Inativa</span>'}
          </div>
          <h4>${escapeHTML(q.label)}</h4>
          ${q.help_text?`<p>${escapeHTML(q.help_text)}</p>`:""}
        </div>
        <button type="button" class="icon-action" data-edit-anamnesis-question="${q.id}" aria-label="Editar pergunta">✎</button>
      </article>`;
    }).join("");
    return `<section class="question-section-group">
      <button type="button" class="question-section-toggle" data-toggle-question-section>
        <span><strong>${escapeHTML(section)}</strong><small>${sectionQuestions.length} pergunta${sectionQuestions.length===1?"":"s"}</small></span>
        <span class="question-section-chevron">⌄</span>
      </button>
      <div class="question-section-body">${cards}</div>
    </section>`;
  }).join("");
}

async function restoreDefaultAnamnesis(){
  const hasExisting=(state.settings.anamnesisQuestions||[]).length>0;
  const message=hasExisting
    ?"Restaurar a anamnese padrão substituirá todas as perguntas atuais. Deseja continuar?"
    :"Carregar a anamnese padrão completa do RITMOX?";
  if(!confirm(message)) return;
  try{
    const result=await api("/api/settings/anamnesis/restore-default",{method:"POST",body:"{}"});
    await loadAnamnesisSettings();
    toast(`Anamnese padrão restaurada com ${result.count} perguntas.`);
  }catch(e){toast(e.message)}
}

function updateQuestionEditorVisibility(){
  const type=$("#aqType").value;
  const risk=$("#aqRiskEnabled").checked;
  $("#aqOptionsField").hidden=!["select","multiselect"].includes(type);
  $("#aqRiskValuesField").hidden=!risk;
  $("#aqRiskMessageField").hidden=!risk;
  if(type==="yes_no" && risk && !$("#aqRiskValues").value.trim()){
    $("#aqRiskValues").value="Sim";
  }
}

function openAnamnesisQuestionEditor(question=null){
  state.settings.editingQuestionId=question?.id||null;
  $("#questionEditorEyebrow").textContent=question?"EDITAR PERGUNTA":"NOVA PERGUNTA";
  $("#questionEditorTitle").textContent=question?"Editar pergunta":"Configurar pergunta";
  $("#aqSection").value=question?.section||"Geral";
  $("#aqType").value=question?.question_type||"yes_no";
  $("#aqLabel").value=question?.label||"";
  $("#aqHelp").value=question?.help_text||"";
  $("#aqPlaceholder").value=question?.placeholder||"";
  $("#aqOptions").value=(question?.options||[]).join("\n");
  $("#aqRequired").checked=!!question?.required;
  $("#aqActive").checked=question?!!question.active:true;
  $("#aqRiskEnabled").checked=!!question?.risk_enabled;
  $("#aqRiskValues").value=(question?.risk_values||[]).join(", ");
  $("#aqRiskMessage").value=question?.risk_message||"";
  $("#deleteAnamnesisQuestionBtn").hidden=!question;
  updateQuestionEditorVisibility();
  openDialogSafe($("#anamnesisQuestionDialog"));
}

function closeAnamnesisQuestionEditor(){
  closeDialogSafe($("#anamnesisQuestionDialog"));
  state.settings.editingQuestionId=null;
}

function anamnesisQuestionPayload(){
  const existing=state.settings.anamnesisQuestions.find(q=>q.id===state.settings.editingQuestionId);
  const options=$("#aqOptions").value.split(/\n|,/).map(x=>x.trim()).filter(Boolean);
  const risks=$("#aqRiskValues").value.split(",").map(x=>x.trim()).filter(Boolean);
  return {
    section:$("#aqSection").value.trim()||"Geral",
    label:$("#aqLabel").value.trim(),
    question_type:$("#aqType").value,
    help_text:$("#aqHelp").value.trim(),
    placeholder:$("#aqPlaceholder").value.trim(),
    options,
    required:$("#aqRequired").checked,
    risk_enabled:$("#aqRiskEnabled").checked,
    risk_values:risks,
    risk_message:$("#aqRiskMessage").value.trim(),
    active:$("#aqActive").checked,
    position:existing?.position || ((state.settings.anamnesisQuestions.length+1)*10)
  };
}

async function saveAnamnesisQuestion(ev){
  ev.preventDefault();
  const payload=anamnesisQuestionPayload();
  if(payload.label.length<2){
    toast("Digite a pergunta.");
    return;
  }
  const id=state.settings.editingQuestionId;
  try{
    await api(id?`/api/settings/anamnesis/questions/${id}`:"/api/settings/anamnesis/questions",{
      method:id?"PUT":"POST",
      body:JSON.stringify(payload)
    });
    closeAnamnesisQuestionEditor();
    await loadAnamnesisSettings();
    toast(id?"Pergunta atualizada.":"Pergunta adicionada à anamnese.");
  }catch(e){toast(e.message)}
}

async function deleteAnamnesisQuestion(){
  const id=state.settings.editingQuestionId;
  if(!id) return;
  if(!confirm("Excluir esta pergunta da anamnese?")) return;
  try{
    await api(`/api/settings/anamnesis/questions/${id}`,{method:"DELETE"});
    closeAnamnesisQuestionEditor();
    await loadAnamnesisSettings();
    toast("Pergunta excluída.");
  }catch(e){toast(e.message)}
}

function localISO(d){
  const y=d.getFullYear();
  const m=String(d.getMonth()+1).padStart(2,"0");
  const day=String(d.getDate()).padStart(2,"0");
  return `${y}-${m}-${day}`;
}

function parseISODate(value){
  const [y,m,d]=value.split("-").map(Number);
  return new Date(y,m-1,d);
}

function startOfWeek(input){
  const d=new Date(input.getFullYear(),input.getMonth(),input.getDate());
  const weekday=(d.getDay()+6)%7;
  d.setDate(d.getDate()-weekday);
  return d;
}

function addDays(input,days){
  const d=new Date(input.getFullYear(),input.getMonth(),input.getDate());
  d.setDate(d.getDate()+days);
  return d;
}

function formatWeekRange(start){
  const end=addDays(start,6);
  const opts={day:"2-digit",month:"short"};
  const left=start.toLocaleDateString("pt-BR",opts).replace(".","");
  const right=end.toLocaleDateString("pt-BR",{...opts,year:"numeric"}).replace(".","");
  return `${left} — ${right}`;
}

function modalityClass(modality){
  if(modality==="musculacao") return "strength";
  if(modality==="corrida") return "running";
  return "other";
}

function modalityLabel(modality){
  const map={musculacao:"Musculação",corrida:"Corrida",funcional:"Funcional",ciclismo:"Ciclismo",outro:"Outra"};
  return map[modality]||modality;
}

function modalityIcon(modality){
  if(modality==="musculacao"){
    return $(".m-feature-strength img")?.src || "/static/assets/validated/muscle-approved.png";
  }
  if(modality==="corrida"){
    return $(".m-feature-run img")?.src || "/static/assets/validated/run-approved.png";
  }
  return "/static/assets/validated/evolution.webp";
}

function escapeHTML(value){
  return String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]));
}

async function loadTrainingCalendar(preserveSelection=true){
  if(!$("#weekCalendar")) return;
  const today=new Date();
  if(!state.calendar.weekStart) state.calendar.weekStart=startOfWeek(today);
  const start=state.calendar.weekStart;
  const end=addDays(start,6);
  try{
    const plans=await api(`/api/training-plans?start_date=${localISO(start)}&end_date=${localISO(end)}`);
    state.calendar.plans=plans;
    if(!preserveSelection || !state.calendar.selectedDate){
      const todayISO=localISO(today);
      const startISO=localISO(start), endISO=localISO(end);
      state.calendar.selectedDate=(todayISO>=startISO&&todayISO<=endISO)?todayISO:startISO;
    }
    state.calendar.loaded=true;
    renderTrainingCalendar();
    syncTodayPlanToHome();
  }catch(e){
    toast(e.message);
  }
}

function renderTrainingCalendar(){
  const calendar=$("#weekCalendar");
  if(!calendar) return;
  const start=state.calendar.weekStart;
  $("#weekRange").textContent=formatWeekRange(start);

  const weekdayNames=["SEG","TER","QUA","QUI","SEX","SÁB","DOM"];
  const todayISO=localISO(new Date());
  calendar.innerHTML=Array.from({length:7},(_,i)=>{
    const d=addDays(start,i);
    const iso=localISO(d);
    const plans=state.calendar.plans.filter(p=>p.planned_date===iso);
    const chips=plans.slice(0,2).map(p=>`
      <span class="day-chip ${modalityClass(p.modality)}"><i></i><span>${escapeHTML(p.title)}</span></span>`
    ).join("");
    const more=plans.length>2?`<span class="more-chip">+${plans.length-2} treino(s)</span>`:"";
    return `<button type="button" class="calendar-day ${iso===state.calendar.selectedDate?"selected":""} ${iso===todayISO?"today":""}" data-calendar-date="${iso}">
      <span class="calendar-day-head">
        <span class="calendar-weekday">${weekdayNames[i]}</span>
        <span class="calendar-count">${plans.length?plans.length+" treino"+(plans.length>1?"s":""):""}</span>
      </span>
      <strong class="calendar-date-num">${d.getDate()}</strong>
      <span class="calendar-day-plans">${chips}${more}</span>
    </button>`;
  }).join("");

  const total=state.calendar.plans.length;
  $("#weekPlanCount").textContent=total ? `${total} treino${total>1?"s":""} planejado${total>1?"s":""}` : "Nenhum treino planejado";
  renderSelectedDay();
}

function renderSelectedDay(){
  const selected=state.calendar.selectedDate;
  if(!selected) return;
  const d=parseISODate(selected);
  const plans=state.calendar.plans.filter(p=>p.planned_date===selected);
  const full=d.toLocaleDateString("pt-BR",{weekday:"long",day:"2-digit",month:"long"});
  $("#selectedDayEyebrow").textContent=selected===localISO(new Date())?"HOJE":"DIA SELECIONADO";
  $("#selectedDayTitle").textContent=full.charAt(0).toUpperCase()+full.slice(1);
  $("#selectedDaySubtitle").textContent=plans.length ? `${plans.length} treino${plans.length>1?"s":""} planejado${plans.length>1?"s":""} para este dia.` : "Nenhum treino planejado para este dia.";

  const list=$("#dayPlanList");
  if(!plans.length){
    list.innerHTML=`<div class="day-empty"><div><span class="day-empty-icon"><svg><use href="#i-calendar"/></svg></span><strong>Dia livre</strong><span>Inclua um treino para começar o planejamento.</span></div></div>`;
    return;
  }
  list.innerHTML=plans.map(p=>`
    <article class="day-plan-card">
      <div class="day-plan-icon"><img src="${modalityIcon(p.modality)}" alt=""></div>
      <div class="day-plan-info">
        <h4>${escapeHTML(p.title)}</h4>
        <p>${escapeHTML(modalityLabel(p.modality))}</p>
        <div class="day-plan-meta">
          <span>◷ ${p.duration_min} min</span>
          <span>◌ ${structureCountLabel(p)}</span>
          ${p.notes?`<span>✦ ${escapeHTML(p.notes)}</span>`:""}
        </div>
      </div>
      <div class="day-plan-actions">
        <button type="button" class="icon-action" data-edit-plan="${p.id}" aria-label="Editar ${escapeHTML(p.title)}">✎</button>
      </div>
    </article>
  `).join("");
}

function runKindLabel(kind){
  const map={
    run_easy:"Treino leve",
    run_long:"Longão",
    run_interval:"Intervalado",
    run_tempo:"Tempo / Limiar",
    run_progressive:"Progressivo",
    run_fartlek:"Fartlek",
    run_recovery:"Recuperação"
  };
  return map[kind]||"Treino de corrida";
}

function structureCountLabel(plan){
  const n=plan.exercise_count||0;
  if(plan.modality==="corrida") return `${n} bloco${n===1?"":"s"}`;
  if(plan.modality==="musculacao") return `${n} exercício${n===1?"":"s"}`;
  return `${n} atividade${n===1?"":"s"}`;
}

function configurePlanStructure(modality){
  state.calendar.formModality=modality;
  const eyebrow=$("#planStructureEyebrow");
  const title=$("#planStructureTitle");
  const hint=$("#planStructureHint");
  const add=$("#addExerciseRowBtn");
  const name=$("#planTitle");
  if(modality==="corrida"){
    eyebrow.textContent="BLOCOS DE CORRIDA";
    title.textContent="Estrutura da corrida";
    hint.textContent="Monte o treino com blocos leves, longos, intervalados, tempo, progressivo ou fartlek.";
    add.textContent="＋ Adicionar bloco";
    name.placeholder="Ex.: Intervalado 8 × 400 m";
  }else if(modality==="musculacao"){
    eyebrow.textContent="EXERCÍCIOS";
    title.textContent="Estrutura da musculação";
    hint.textContent="Adicione os exercícios com séries, repetições e carga.";
    add.textContent="＋ Adicionar exercício";
    name.placeholder="Ex.: Inferiores — Força e Hipertrofia";
  }else{
    eyebrow.textContent="ATIVIDADES";
    title.textContent="Estrutura do treino";
    hint.textContent="Adicione as atividades que compõem este treino.";
    add.textContent="＋ Adicionar atividade";
    name.placeholder="Ex.: Treino funcional";
  }
  renderExerciseEditorEmpty();
}

function openPlanDialog(plan=null,dateValue=null){
  if(!state.health.assessment?.training_allowed){
    toast("Conclua a anamnese e a triagem de segurança antes de planejar treinos.");
    loadHealthGate();
    return;
  }
  const dialog=$("#planDialog");
  if(!dialog) return;
  state.calendar.editingId=plan?.id||null;
  $("#planDialogEyebrow").textContent=plan?"EDITAR TREINO":"NOVO TREINO";
  $("#planDialogTitle").textContent=plan?"Editar treino planejado":"Planejar treino";
  $("#planDate").value=plan?.planned_date||dateValue||state.calendar.selectedDate||localISO(new Date());
  const modality=plan?.modality||"musculacao";
  $("#planModality").value=modality;
  $("#planTitle").value=plan?.title||"";
  $("#planDuration").value=plan?.duration_min||45;
  $("#planNotes").value=plan?.notes||"";
  $("#deletePlanBtn").hidden=!plan;
  $("#plannedExerciseRows").innerHTML="";
  configurePlanStructure(modality);

  const sourceBlocks=(plan?.blocks&&plan.blocks.length)
    ? plan.blocks
    : (plan?.exercises||[]).map(e=>({
        kind:"strength",
        name:e.name,
        detail:e.muscle,
        sets_total:e.sets_total,
        reps:e.reps,
        load_kg:e.load_kg
      }));
  sourceBlocks.forEach(block=>addExerciseRow(block,modality));
  renderExerciseEditorEmpty();
  dialog.showModal();
  setTimeout(()=>$("#planTitle")?.focus(),30);
}

function closePlanDialog(){
  const dialog=$("#planDialog");
  if(dialog?.open) dialog.close();
  state.calendar.editingId=null;
}

function runKindOptions(selected){
  const options=[
    ["run_easy","Treino leve"],
    ["run_long","Longão"],
    ["run_interval","Intervalado"],
    ["run_tempo","Tempo / Limiar"],
    ["run_progressive","Progressivo"],
    ["run_fartlek","Fartlek"],
    ["run_recovery","Recuperação"]
  ];
  return options.map(([value,label])=>`<option value="${value}" ${value===selected?"selected":""}>${label}</option>`).join("");
}

function updateRunBlockVisibility(row){
  const kind=row.querySelector('[data-field="kind"]')?.value||"run_easy";
  const intervalLike=["run_interval","run_fartlek"].includes(kind);
  row.querySelectorAll("[data-interval-only]").forEach(el=>el.classList.toggle("is-hidden",!intervalLike));
  const distanceLabel=row.querySelector("[data-distance-label]");
  if(distanceLabel) distanceLabel.firstChild.textContent=intervalLike?"Distância por repetição (km)":"Distância (km)";
}

function addExerciseRow(data={},forcedModality=null){
  const host=$("#plannedExerciseRows");
  if(!host) return;
  const modality=forcedModality||$("#planModality").value;
  const empty=host.querySelector(".exercise-editor-empty");
  if(empty) empty.remove();

  const row=document.createElement("div");
  row.className=`planned-exercise-row planned-block-row ${modality==="corrida"?"run-block":"strength-block"}`;

  if(modality==="corrida"){
    const kind=(data.kind&&data.kind.startsWith("run_"))?data.kind:"run_easy";
    row.innerHTML=`
      <label>Tipo do bloco
        <select data-field="kind">${runKindOptions(kind)}</select>
      </label>
      <label data-distance-label>Distância (km)
        <input data-field="distance_km" type="number" min="0" max="500" step="0.1" value="${Number(data.distance_km||0)}" placeholder="Ex.: 6">
      </label>
      <label>Duração (min)
        <input data-field="duration_min" type="number" min="0" max="600" value="${Number(data.duration_min||0)}" placeholder="Ex.: 35">
      </label>
      <label>Ritmo alvo
        <input data-field="pace_target" maxlength="30" value="${escapeHTML(data.pace_target||"")}" placeholder="Ex.: 5:20–5:40/km">
      </label>
      <label>Intensidade
        <select data-field="intensity">
          <option value="" ${!data.intensity?"selected":""}>Livre</option>
          <option value="Z1" ${data.intensity==="Z1"?"selected":""}>Z1</option>
          <option value="Z2" ${data.intensity==="Z2"?"selected":""}>Z2</option>
          <option value="Z3" ${data.intensity==="Z3"?"selected":""}>Z3</option>
          <option value="Z4" ${data.intensity==="Z4"?"selected":""}>Z4</option>
          <option value="Z5" ${data.intensity==="Z5"?"selected":""}>Z5</option>
        </select>
      </label>
      <label data-interval-only>Repetições
        <input data-field="repetitions" type="number" min="0" max="100" value="${Number(data.repetitions||0)}" placeholder="Ex.: 8">
      </label>
      <label data-interval-only>Recuperação (s)
        <input data-field="rest_sec" type="number" min="0" max="3600" value="${Number(data.rest_sec||0)}" placeholder="Ex.: 90">
      </label>
      <button type="button" class="remove-exercise-btn" aria-label="Remover bloco">×</button>`;
    row.querySelector('[data-field="kind"]').addEventListener("change",()=>updateRunBlockVisibility(row));
    updateRunBlockVisibility(row);
  }else{
    row.innerHTML=`
      <input type="hidden" data-field="kind" value="strength">
      <label>Exercício<input data-field="name" maxlength="160" value="${escapeHTML(data.name||"")}" placeholder="Ex.: Agachamento livre"></label>
      <label>Grupo muscular<input data-field="detail" maxlength="160" value="${escapeHTML(data.detail||data.muscle||"")}" placeholder="Quadríceps / Glúteos"></label>
      <label>Séries<input data-field="sets_total" type="number" min="1" max="30" value="${Number(data.sets_total||4)}"></label>
      <label>Repetições<input data-field="reps" maxlength="30" value="${escapeHTML(data.reps||"8-10")}"></label>
      <label>Carga kg<input data-field="load_kg" type="number" min="0" max="2000" step="0.5" value="${Number(data.load_kg||0)}"></label>
      <button type="button" class="remove-exercise-btn" aria-label="Remover exercício">×</button>`;
  }

  row.querySelector(".remove-exercise-btn").addEventListener("click",()=>{
    row.remove();
    renderExerciseEditorEmpty();
  });
  host.appendChild(row);
  renderExerciseEditorEmpty();
}

function renderExerciseEditorEmpty(){
  const host=$("#plannedExerciseRows");
  if(!host) return;
  const empty=host.querySelector(".exercise-editor-empty");
  if(empty) empty.remove();
  if(!host.querySelector(".planned-block-row")){
    const el=document.createElement("div");
    el.className="exercise-editor-empty";
    const modality=$("#planModality")?.value||"musculacao";
    el.textContent=modality==="corrida"
      ?"Nenhum bloco adicionado. Ex.: treino leve, longão, intervalado ou tempo."
      : modality==="musculacao"
        ?"Nenhum exercício adicionado. Ex.: agachamento, supino ou remada."
        :"Nenhuma atividade adicionada.";
    host.appendChild(el);
  }
}

function collectPlanForm(){
  const modality=$("#planModality").value;
  const rows=$$(".planned-block-row",$("#plannedExerciseRows"));
  const blocks=rows.map(row=>{
    if(modality==="corrida"){
      const kind=row.querySelector('[data-field="kind"]').value;
      return {
        kind,
        name:runKindLabel(kind),
        detail:"",
        sets_total:0,
        reps:"",
        load_kg:0,
        distance_km:Number(row.querySelector('[data-field="distance_km"]').value||0),
        duration_min:Number(row.querySelector('[data-field="duration_min"]').value||0),
        pace_target:row.querySelector('[data-field="pace_target"]').value.trim(),
        repetitions:Number(row.querySelector('[data-field="repetitions"]')?.value||0),
        rest_sec:Number(row.querySelector('[data-field="rest_sec"]')?.value||0),
        intensity:row.querySelector('[data-field="intensity"]').value
      };
    }
    return {
      kind:"strength",
      name:row.querySelector('[data-field="name"]').value.trim(),
      detail:row.querySelector('[data-field="detail"]').value.trim(),
      sets_total:Number(row.querySelector('[data-field="sets_total"]').value||1),
      reps:row.querySelector('[data-field="reps"]').value.trim()||"1",
      load_kg:Number(row.querySelector('[data-field="load_kg"]').value||0),
      distance_km:0,
      duration_min:0,
      pace_target:"",
      repetitions:0,
      rest_sec:0,
      intensity:""
    };
  }).filter(block=>modality==="corrida" || block.name);

  return {
    planned_date:$("#planDate").value,
    title:$("#planTitle").value.trim(),
    modality,
    duration_min:Number($("#planDuration").value||45),
    notes:$("#planNotes").value.trim(),
    exercises:[],
    blocks
  };
}

async function savePlan(ev){
  ev.preventDefault();
  const payload=collectPlanForm();
  if(!payload.planned_date || payload.title.length<2){
    toast("Informe a data e o nome do treino.");
    return;
  }
  try{
    const id=state.calendar.editingId;
    await api(id?`/api/training-plans/${id}`:"/api/training-plans",{
      method:id?"PUT":"POST",
      body:JSON.stringify(payload),
    });
    state.calendar.selectedDate=payload.planned_date;
    state.calendar.weekStart=startOfWeek(parseISODate(payload.planned_date));
    closePlanDialog();
    await loadTrainingCalendar(true);
    toast(id?"Treino atualizado.":"Treino incluído no calendário.");
  }catch(e){toast(e.message)}
}

async function deleteCurrentPlan(){
  const id=state.calendar.editingId;
  if(!id) return;
  if(!confirm("Excluir este treino planejado?")) return;
  try{
    await api(`/api/training-plans/${id}`,{method:"DELETE"});
    closePlanDialog();
    await loadTrainingCalendar(true);
    toast("Treino excluído do calendário.");
  }catch(e){toast(e.message)}
}

function syncTodayPlanToHome(){
  const today=localISO(new Date());
  const todayPlans=state.calendar.plans.filter(p=>p.planned_date===today);
  const strength=todayPlans.find(p=>p.modality==="musculacao");
  const run=todayPlans.find(p=>p.modality==="corrida");
  if(strength){
    if($("#homeWorkoutTitle")) $("#homeWorkoutTitle").textContent=strength.title;
    if($("#mHomeWorkoutTitle")) $("#mHomeWorkoutTitle").textContent=strength.title;
  }
  if(run && $("#mHomeRunTitle")) $("#mHomeRunTitle").textContent=run.title;
}

document.addEventListener("click",async ev=>{
  const sectionToggle=ev.target.closest("[data-toggle-question-section]");
  if(sectionToggle){
    const group=sectionToggle.closest(".question-section-group");
    group?.classList.toggle("is-collapsed");
    return;
  }

  const editQuestion=ev.target.closest("[data-edit-anamnesis-question]");
  if(editQuestion){
    const id=Number(editQuestion.dataset.editAnamnesisQuestion);
    const q=state.settings.anamnesisQuestions.find(item=>item.id===id);
    if(q) openAnamnesisQuestionEditor(q);
    return;
  }

  const day=ev.target.closest("[data-calendar-date]");
  if(day){
    state.calendar.selectedDate=day.dataset.calendarDate;
    renderTrainingCalendar();
    return;
  }
  const edit=ev.target.closest("[data-edit-plan]");
  if(edit){
    const id=Number(edit.dataset.editPlan);
    const plan=state.calendar.plans.find(p=>p.id===id) || await api(`/api/training-plans/${id}`);
    openPlanDialog(plan);
  }
});

if($("#prevWeekBtn")) $("#prevWeekBtn").onclick=()=>{
  state.calendar.weekStart=addDays(state.calendar.weekStart||startOfWeek(new Date()),-7);
  state.calendar.selectedDate=localISO(state.calendar.weekStart);
  loadTrainingCalendar(true);
};
if($("#nextWeekBtn")) $("#nextWeekBtn").onclick=()=>{
  state.calendar.weekStart=addDays(state.calendar.weekStart||startOfWeek(new Date()),7);
  state.calendar.selectedDate=localISO(state.calendar.weekStart);
  loadTrainingCalendar(true);
};
if($("#todayWeekBtn")) $("#todayWeekBtn").onclick=()=>{
  state.calendar.weekStart=startOfWeek(new Date());
  state.calendar.selectedDate=localISO(new Date());
  loadTrainingCalendar(true);
};
if($("#addPlanTopBtn")) $("#addPlanTopBtn").onclick=()=>openPlanDialog(null,state.calendar.selectedDate);
if($("#addPlanDayBtn")) $("#addPlanDayBtn").onclick=()=>openPlanDialog(null,state.calendar.selectedDate);
if($("#addExerciseRowBtn")) $("#addExerciseRowBtn").onclick=()=>addExerciseRow();
if($("#planModality")) $("#planModality").addEventListener("change",ev=>{
  const next=ev.target.value;
  const rows=$$(".planned-block-row",$("#plannedExerciseRows"));
  if(rows.length && next!==state.calendar.formModality){
    const ok=confirm("Ao mudar a modalidade, a estrutura atual será limpa para evitar campos incompatíveis. Continuar?");
    if(!ok){
      ev.target.value=state.calendar.formModality||"musculacao";
      return;
    }
    $("#plannedExerciseRows").innerHTML="";
  }
  configurePlanStructure(next);
});
if($("#closePlanDialog")) $("#closePlanDialog").onclick=closePlanDialog;
if($("#cancelPlanBtn")) $("#cancelPlanBtn").onclick=closePlanDialog;
if($("#deletePlanBtn")) $("#deletePlanBtn").onclick=deleteCurrentPlan;
if($("#planForm")) $("#planForm").addEventListener("submit",savePlan);

if($("#restoreDefaultAnamnesisBtn")) $("#restoreDefaultAnamnesisBtn").onclick=restoreDefaultAnamnesis;
if($("#addAnamnesisQuestionBtn")) $("#addAnamnesisQuestionBtn").onclick=()=>openAnamnesisQuestionEditor();
if($("#closeAnamnesisQuestionBtn")) $("#closeAnamnesisQuestionBtn").onclick=closeAnamnesisQuestionEditor;
if($("#cancelAnamnesisQuestionBtn")) $("#cancelAnamnesisQuestionBtn").onclick=closeAnamnesisQuestionEditor;
if($("#anamnesisQuestionForm")) $("#anamnesisQuestionForm").addEventListener("submit",saveAnamnesisQuestion);
if($("#deleteAnamnesisQuestionBtn")) $("#deleteAnamnesisQuestionBtn").onclick=deleteAnamnesisQuestion;
if($("#aqType")) $("#aqType").addEventListener("change",updateQuestionEditorVisibility);
if($("#aqRiskEnabled")) $("#aqRiskEnabled").addEventListener("change",updateQuestionEditorVisibility);

if($("#clearHaSignatureBtn")) $("#clearHaSignatureBtn").onclick=clearHealthSignaturePad;
if($("#startHealthAssessmentBtn")) $("#startHealthAssessmentBtn").onclick=openHealthAssessment;
if($("#reviewHealthAssessmentBtn")) $("#reviewHealthAssessmentBtn").onclick=openHealthAssessment;
if($("#closeHealthAssessmentBtn")) $("#closeHealthAssessmentBtn").onclick=closeHealthAssessment;
if($("#cancelHealthAssessmentBtn")) $("#cancelHealthAssessmentBtn").onclick=closeHealthAssessment;
if($("#submitHealthAssessmentBtn")) $("#submitHealthAssessmentBtn").onclick=submitHealthAssessment;
if($("#registerClearanceBtn")) $("#registerClearanceBtn").onclick=openClearanceDialog;
if($("#closeClearanceBtn")) $("#closeClearanceBtn").onclick=closeClearanceDialog;
if($("#cancelClearanceBtn")) $("#cancelClearanceBtn").onclick=closeClearanceDialog;
if($("#clearanceForm")) $("#clearanceForm").addEventListener("submit",submitClearance);


if($("#viewProfileAnamnesisBtn")) $("#viewProfileAnamnesisBtn").onclick=openProfileAnamnesis;
if($("#exportProfileAnamnesisBtn")) $("#exportProfileAnamnesisBtn").onclick=exportProfileAnamnesis;
if($("#exportProfileAnamnesisDialogBtn")) $("#exportProfileAnamnesisDialogBtn").onclick=exportProfileAnamnesis;
if($("#signProfileAnamnesisBtn")) $("#signProfileAnamnesisBtn").onclick=openSignatureDialog;
if($("#closeProfileAnamnesisBtn")) $("#closeProfileAnamnesisBtn").onclick=()=>closeDialogSafe($("#profileAnamnesisDialog"));
if($("#closeProfileAnamnesisFooterBtn")) $("#closeProfileAnamnesisFooterBtn").onclick=()=>closeDialogSafe($("#profileAnamnesisDialog"));
if($("#closeSignatureBtn")) $("#closeSignatureBtn").onclick=()=>closeDialogSafe($("#signatureDialog"));
if($("#cancelSignatureBtn")) $("#cancelSignatureBtn").onclick=()=>closeDialogSafe($("#signatureDialog"));
if($("#signatureForm")) $("#signatureForm").addEventListener("submit",submitSignature);


if($("#changeProfilePhotoBtn")) $("#changeProfilePhotoBtn").onclick=()=>$("#profilePhotoInput")?.click();
if($("#profilePhotoInput")) $("#profilePhotoInput").addEventListener("change",ev=>handleProfilePhoto(ev.target.files?.[0]));
if($("#editProfileNameBtn")) $("#editProfileNameBtn").onclick=()=>openProfileEditDialog(true);
if($("#editProfileDataBtn")) $("#editProfileDataBtn").onclick=()=>openProfileEditDialog(false);
$$("[data-profile-edit]").forEach(btn=>btn.onclick=()=>openProfileEditDialog(false));
if($("#closeProfileEditBtn")) $("#closeProfileEditBtn").onclick=closeProfileEditDialog;
if($("#cancelProfileEditBtn")) $("#cancelProfileEditBtn").onclick=closeProfileEditDialog;
if($("#profileEditForm")) $("#profileEditForm").addEventListener("submit",saveProfileEdit);
if($("#privacyProfileBtn")) $("#privacyProfileBtn").onclick=()=>toast("Privacidade e segurança entram na próxima etapa.");
if($("#supportProfileBtn")) $("#supportProfileBtn").onclick=()=>toast("Central de ajuda e suporte entra na próxima etapa.");

window.addEventListener("resize",()=>{
  clearTimeout(window._resize);
  window._resize=setTimeout(()=>{drawProgressChart();drawRunChart()},120);
});

(async function init(){
  const workoutNavSource=$(".bottom-nav [data-page='workouts'] img")?.src;
  const desktopWorkoutIcon=$(".side-nav [data-page='workouts'] img");
  if(workoutNavSource && desktopWorkoutIcon) desktopWorkoutIcon.src=workoutNavSource;

  await Promise.all([loadDashboard(),loadRun(),loadUserProfile()]);
  const hash=location.hash.replace("#","");
  navigate(pageMeta[hash]?hash:"home");
})();

function handleAriaCheckboxClick(ev){
  const option=ev.target.closest("[data-anamnesis-option],[data-consent-toggle]");
  if(!option) return;
  ev.preventDefault();
  toggleAriaCheck(option);
}
document.addEventListener("click",handleAriaCheckboxClick);
