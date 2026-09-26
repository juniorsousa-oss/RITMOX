/* RITMOX unified Instagram Story exporter — fixed 1080x1920 template */
function ritmoxWorkoutStats(w){
  const logs=(w&&w.exercises?w.exercises:[]).flatMap(function(e){return (e.set_logs||[]).map(function(log){return Object.assign({},log,{exercise:e.name})})});
  const reps=logs.reduce(function(s,x){return s+Number(x.reps_done||0)},0);
  const volume=logs.reduce(function(s,x){return s+Number(x.reps_done||0)*Number(x.load_kg||0)},0);
  const rests=logs.map(function(x){return Number(x.rest_sec||0)}).filter(Boolean);
  const best=logs.reduce(function(acc,x){return Number(x.load_kg||0)>Number(acc&&acc.load_kg||0)?x:acc},null);
  let duration=Number(w&&w.duration_min||0);
  if(w&&w.started_at&&w.completed_at)duration=Math.max(1,Math.round((new Date(w.completed_at)-new Date(w.started_at))/60000));
  return {duration:duration,exercises:(w&&w.exercises||[]).length,sets:logs.length,reps:reps,volume:volume,avgRest:rests.length?Math.round(rests.reduce(function(a,b){return a+b},0)/rests.length):0,best:best};
}
function ritmoxStoryBox(ctx,x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=fill;ctx.fill();if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=2;ctx.stroke()}}
function ritmoxStoryMetric(ctx,x,y,label,value,icon){ritmoxStoryBox(ctx,x,y,397,126,22,"rgba(5,15,35,.90)","rgba(220,55,255,.55)");ctx.fillStyle="#ff2d9a";ctx.font="700 30px Arial";ctx.fillText(icon,x+22,y+58);ctx.fillStyle="#aab3c8";ctx.font="500 20px Arial";ctx.fillText(label,x+78,y+36);ctx.fillStyle="#fff";ctx.font="800 31px Arial";ctx.fillText(value,x+78,y+78)}
function ritmoxStoryFit(ctx,text,maxWidth,size){while(size>28){ctx.font="900 "+size+"px Arial";if(ctx.measureText(text).width<=maxWidth)break;size-=2}return size}
function buildWorkoutStoryCanvas(w){
  const c=document.createElement("canvas");c.width=1080;c.height=1920;const ctx=c.getContext("2d");
  const bg=ctx.createLinearGradient(0,0,1080,1920);bg.addColorStop(0,"#090515");bg.addColorStop(.48,"#160526");bg.addColorStop(1,"#020914");ctx.fillStyle=bg;ctx.fillRect(0,0,1080,1920);
  for(let i=0;i<18;i++){const x=(i*173)%1080,y=(i*307)%1920,r=150+(i%4)*45,g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,i%2?"rgba(255,0,145,.18)":"rgba(123,35,255,.17)");g.addColorStop(1,"rgba(0,0,0,0)");ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2)}
  ritmoxStoryBox(ctx,72,170,936,1570,46,"rgba(4,10,28,.93)","#ff21cf");
  ctx.fillStyle="#fff";ctx.font="900 48px Arial";ctx.fillText("RITMO",118,280);ctx.fillStyle="#ff2d9a";ctx.fillText("X",280,280);
  ritmoxStoryBox(ctx,118,320,360,54,27,"rgba(144,21,178,.24)","#b629ef");ctx.fillStyle="#f1e9ff";ctx.font="600 22px Arial";ctx.fillText("Treino concluído",145,355);
  ctx.fillStyle="#fff";ctx.font="900 78px Arial";ctx.fillText("TREINO",118,470);const gr=ctx.createLinearGradient(118,0,760,0);gr.addColorStop(0,"#ff168f");gr.addColorStop(1,"#c320ff");ctx.fillStyle=gr;ctx.font="900 82px Arial";ctx.fillText("CONCLUÍDO",118,555);
  const modality=w.modality==="corrida"?"CORRIDA":w.modality==="ciclismo"?"CICLISMO":w.modality==="musculacao"?"MUSCULAÇÃO":String(w.modality||"TREINO").toUpperCase();ctx.fillStyle="#d9ddeb";ctx.font="500 24px Arial";ctx.fillText("R E S U M O   D O   "+modality,120,605);
  const title=String(w.title||"Treino"),ts=ritmoxStoryFit(ctx,title,820,48);ctx.fillStyle="#fff";ctx.font="900 "+ts+"px Arial";ctx.fillText(title,120,690);const date=new Date(w.completed_at||Date.now()).toLocaleDateString("pt-BR",{day:"2-digit",month:"short",year:"numeric"}).toUpperCase();ctx.fillStyle="#aab3c8";ctx.font="500 23px Arial";ctx.fillText(date,120,730);
  const s=ritmoxWorkoutStats(w),metrics=[["Duração",s.duration+" min","◷"],["Exercícios",String(s.exercises),"✚"],["Séries concluídas",String(s.sets),"☷"],["Repetições",String(s.reps),"↻"],["Carga total",Math.round(s.volume).toLocaleString("pt-BR")+" kg","KG"],["Descanso médio",s.avgRest+" s","◴"]];
  metrics.forEach(function(m,i){ritmoxStoryMetric(ctx,118+(i%2)*421,790+Math.floor(i/2)*150,m[0],m[1],m[2])});
  const sy=1240;ritmoxStoryBox(ctx,110,sy,860,300,28,"rgba(5,14,33,.92)","#b629ef");ctx.fillStyle="#ff2d9a";ctx.font="900 34px Arial";ctx.fillText("100% CONCLUÍDO",145,sy+70);ctx.fillStyle="#aab3c8";ctx.font="500 21px Arial";ctx.fillText("Melhor carga",145,sy+130);ctx.fillStyle="#fff";ctx.font="800 28px Arial";ctx.fillText(s.best?s.best.exercise+" • "+Number(s.best.load_kg).toLocaleString("pt-BR")+" kg":"Treino completo",145,sy+170);ctx.fillStyle="#aab3c8";ctx.font="500 21px Arial";ctx.fillText("Volume total",145,sy+225);ctx.fillStyle="#fff";ctx.font="800 31px Arial";ctx.fillText(Math.round(s.volume).toLocaleString("pt-BR")+" kg",145,sy+265);
  ctx.textAlign="center";ctx.fillStyle="#d8dce8";ctx.font="500 24px Arial";ctx.fillText("E V O L U Ç Ã O   É   C O N S I S T Ê N C I A.",540,1620);ctx.fillStyle="#8993aa";ctx.font="500 20px Arial";ctx.fillText("Exportado pelo RITMOX",540,1685);ctx.textAlign="left";return c;
}
async function exportWorkoutStory(w){
  if(!w||!w.completed){if(typeof toast==="function")toast("Finalize o treino antes de exportar.");return}
  const canvas=buildWorkoutStoryCanvas(w),blob=await new Promise(function(resolve){canvas.toBlob(resolve,"image/png",1)});if(!blob)return;
  const name="ritmox-"+String(w.title||"treino").toLowerCase().replace(/[^a-z0-9]+/g,"-")+".png",file=new File([blob],name,{type:"image/png"});
  try{if(navigator.canShare&&navigator.canShare({files:[file]})&&navigator.share){await navigator.share({files:[file],title:"Treino concluído • RITMOX"})}else{const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(function(){URL.revokeObjectURL(url)},1000);if(typeof toast==="function")toast("Imagem do Story gerada.")}}catch(e){if(e&&e.name!=="AbortError"&&typeof toast==="function")toast("Não foi possível compartilhar a imagem.")}
}