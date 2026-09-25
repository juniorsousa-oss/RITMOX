const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];

const state = {
  page: "home",
  workout: null,
  run: null,
  dashboard: null,
  timerStartedAt: null,
  timerHandle: null,
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
  workouts:["Treino de hoje","Musculação • evolução de força"],
  run:["Corrida","Métricas reais. Evolução constante."],
  evolution:["Minha evolução","Consistência vira resultado."],
  community:["Comunidade","Evolua com quem também está em movimento."],
  profile:["Meu perfil","Sua jornada, suas conexões."],
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
  $("[data-complete]").forEach(b=>b.onclick=()=>completeSet(Number(b.dataset.complete)));
  $("[data-undo]").forEach(b=>b.onclick=()=>undoSet(Number(b.dataset.undo)));

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
  const fit=fitCanvas(canvas,230); if(!fit)return;
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
  const fit=fitCanvas(canvas,220); if(!fit)return;
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

$("#startWorkoutBtn").onclick=async()=>{
  if(!state.workout){
    toast("O cadastro do primeiro treino será a próxima tela que vamos construir.");
    return;
  }
  try{
    const w=await api(`/api/workouts/${state.workout.id}/start`,{method:"POST"});
    renderWorkout(w); startLocalTimer(); toast("Treino iniciado.");
  }catch(e){toast(e.message)}
};

$("#addModalityBtn").onclick=()=>$("#modalityDialog").showModal();
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

$("[data-page]").forEach(b=>b.addEventListener("click",()=>navigate(b.dataset.page)));
$$("[data-open]").forEach(card=>card.addEventListener("click",(ev)=>{
  if(ev.target.closest("button")) ev.preventDefault();
  navigate(card.dataset.open);
}));
$$(".hero-action").forEach(btn=>btn.addEventListener("click",(ev)=>{
  ev.stopPropagation();
  const card=btn.closest("[data-open]");
  navigate(card.dataset.open);
  if(card.dataset.open==="workouts") $("#startWorkoutBtn").click();
}));

$("#globalSearch").addEventListener("input",ev=>{
  const q=ev.target.value.trim().toLowerCase();
  if(!q)return;
  if(["corrida","run","pace","ritmo"].some(x=>q.includes(x))) navigate("run");
  else if(["treino","musculação","musculacao","agachamento","exercício","exercicio"].some(x=>q.includes(x))) navigate("workouts");
});

window.addEventListener("resize",()=>{
  clearTimeout(window._resize);
  window._resize=setTimeout(()=>{drawProgressChart();drawRunChart()},120);
});

(async function init(){
  await Promise.all([loadDashboard(),loadWorkout(),loadRun()]);
  const hash=location.hash.replace("#","");
  navigate(pageMeta[hash]?hash:"home");
})();
