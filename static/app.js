/* TRM Lab. Interactividad con Plotly con CDN y endpoints Python; no hay datos simulados. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const money = (n, dec = 2) => n == null ? '—' : new Intl.NumberFormat('es-CO', {minimumFractionDigits:dec, maximumFractionDigits:dec}).format(n);
  const short = (d) => d ? new Date(`${d}T12:00:00`).toLocaleDateString('es-CO', {day:'numeric', month:'short', year:'numeric'}) : '—';
  const state = {group:'month',start:'',end:'', latestDate:'', loading:false, first:true, refreshId:0};
  const base = {paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'DM Sans, Arial, sans-serif',color:'#a5b6cc',size:11},margin:{t:12,b:60,l:71,r:18},showlegend:false,
    xaxis:{gridcolor:'#253248',linecolor:'#3a4b61',zeroline:false,tickfont:{color:'#98abc1',size:10},automargin:true},
    yaxis:{gridcolor:'#253248',linecolor:'#3a4b61',zeroline:false,tickfont:{color:'#98abc1',size:10},automargin:true,tickformat:',.0f',title:{text:'COP por 1 USD',font:{size:10,color:'#7e91a9'}}}};
  const config = {responsive:true,displaylogo:false,modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d','toggleSpikelines','zoomIn2d','zoomOut2d'],toImageButtonOptions:{format:'png',filename:'TRM_Colombia',height:660,width:1300,scale:2}};
  function params(refresh=false){const p=new URLSearchParams();if(state.start)p.set('start',state.start);if(state.end)p.set('end',state.end);p.set('group',state.group);if(refresh)p.set('refresh','1');return p.toString()}
  function showError(message){$('errorMessage').textContent=message;$('errorMessage').hidden=false}
  function clearError(){$('errorMessage').hidden=true}
  function busy(v){state.loading=v;document.body.classList.toggle('is-loading',v);$('refreshBtn').disabled=v;$('applyBtn').disabled=v}
  const traceColors = ['#67b4ff','#36cbae','#f3ae64','#c398ff'];
  async function drawBox(data){
    const labels=[];const values=[];
    data.groups.forEach(g=>g.values.forEach(v=>{labels.push(g.name);values.push(v)}));
    const tickangle = data.groups.length > 8 ? -45 : 0;
    const layout={...base,margin:{t:10,b:tickangle?96:62,l:67,r:16}};
    // Una etiqueta por grupo, pero sin colapsar cajas de periodos diferentes.
    layout.xaxis={...base.xaxis,type:'category',categoryorder:'array',categoryarray:data.groups.map(g=>g.name),tickangle,
      tickfont:{color:'#9caec4',size:data.groups.length>25?8:10},automargin:true};
    layout.yaxis={...base.yaxis};
    const options={type:'box',x:labels,y:values,name:'TRM oficial',boxpoints:'outliers',fillcolor:'rgba(78,155,244,0.34)',line:{color:'#80c2ff',width:1.8},marker:{color:'#a7d7ff',size:4,opacity:.8},whiskerwidth:.6,
      hovertemplate:'%{x}<br>TRM: %{y:,.2f} COP<extra></extra>',quartilemethod:'linear',showlegend:false};
    await Plotly.react('boxChart',[options],layout,config);
  }
  async function drawTrend(data){
    const series=data.series;
    const layout={...base,margin:{t:8,b:47,l:64,r:14}};
    layout.xaxis={...base.xaxis,type:'date',tickformat:'%b %Y'};
    layout.yaxis={...base.yaxis};
    await Plotly.react('trendChart',[{type:'scatter',mode:'lines',x:series.map(x=>x.date),y:series.map(x=>x.value),line:{color:'#6fb6ff',width:2},hovertemplate:'%{x|%d/%m/%Y}<br>%{y:,.2f} COP<extra></extra>',name:'TRM'}],layout,{...config,displayModeBar:false});
  }
  async function drawHeat(data){
    const months=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
    const layout={...base,margin:{t:8,b:50,l:51,r:22},xaxis:{...base.xaxis,type:'category',side:'bottom'},yaxis:{...base.yaxis,type:'category',title:undefined,autorange:'reversed'},coloraxis:{showscale:false}};
    const z=data.heatmap.map(x=>x.months);
    const yrs=data.heatmap.map(x=>String(x.year));
    await Plotly.react('heatmapChart',[{type:'heatmap',x:months,y:yrs,z,colorscale:[[0,'#162f4a'],[.3,'#2b6391'],[.6,'#4e98bf'],[1,'#88d1dc']],showscale:false,xgap:3,ygap:3,
      hovertemplate:'%{y} · %{x}<br>TRM media: %{z:,.2f} COP<extra></extra>'}],layout,{...config,displayModeBar:false});
  }
  function fillKpis(data){const s=data.stats,m=data.meta;
    $('latestValue').innerHTML=`${money(s.latest)}<small> COP</small>`;
    $('latestDate').textContent=`Vigencia ${short(m.latest_date)}`;
    const sign=s.change>0?'+':'';const changeSign=s.change<0?'negative':s.change>0?'positive':'neutral';
    $('deltaChip').className=`delta ${changeSign}`;
    $('deltaChip').textContent=`${sign}${money(s.change)} COP vs. registro anterior`;
    $('meanValue').textContent=money(s.mean);$('medianValue').textContent=money(s.median);
    $('rangeValue').textContent=money(s.max-s.min);$('rangeSub').textContent=`Mín ${money(s.min,0)} · Máx ${money(s.max,0)}`;
    $('obsCounter').textContent=money(s.observations,0);$('q1Value').textContent=`$ ${money(s.q1)}`;$('q3Value').textContent=`$ ${money(s.q3)}`;
    $('iqrValue').textContent=`$ ${money(s.iqr)}`;$('stdValue').textContent=`$ ${money(s.std)}`;$('outlierValue').textContent=money(s.outliers,0);
    $('changeValue').textContent=`${s.range_change_pct>0?'+':''}${money(s.range_change_pct)} %`;
    $('insightText').textContent=`En este intervalo, el 50 % central de las observaciones se concentra entre ${money(s.q1)} y ${money(s.q3)} COP por USD. El rango intercuartílico es ${money(s.iqr)} COP; valores más alejados pueden clasificarse como atípicos.`;
    $('footerDate').textContent=short(m.latest_date);$('syncDate').textContent=m.consulted_at?new Date(m.consulted_at).toLocaleString('es-CO',{timeZone:'America/Bogota',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'No disponible';
    $('warningMessage').hidden=!m.warning;
    if(m.warning)$('warningMessage').textContent=m.warning;
    state.latestDate=m.latest_date;
    if(state.first){state.start=m.filters.start;state.end=m.filters.end;state.first=false}
    $('startDate').value=state.start;$('endDate').value=state.end;
    $('startDate').min=m.coverage_start;$('startDate').max=m.coverage_end;
    $('endDate').min=m.coverage_start;$('endDate').max=m.coverage_end;
  }
  async function load(refresh=false){
    if(state.loading)return;
    busy(true);clearError();
    try{
      const query=params(refresh);const response=await fetch(`/api/trm?${query}`,{cache:'no-store'});
      const result=await response.json();
      if(!response.ok)throw new Error(result.error||`Error HTTP ${response.status}`);
      fillKpis(result);
      await Promise.all([drawBox(result),drawTrend(result),drawHeat(result)]);
      const img=$('seabornImg');const place=$('seabornLoading');
      place.textContent='Generando gráfico Seaborn…';place.hidden=false;img.hidden=true;
      const key=++state.refreshId;
      img.onload=()=>{if(key===state.refreshId){place.hidden=true;img.hidden=false}};
      img.onerror=()=>{if(key===state.refreshId){place.textContent='No se pudo generar la visualización Seaborn. Puedes intentar actualizar.'}};
      img.src=`/api/seaborn.png?${params()}&v=${Date.now()}`;
    }catch(e){showError(`No fue posible visualizar los datos: ${e.message}. La página no muestra valores de ejemplo como si fueran reales.`);}
    finally{busy(false)}
  }
  function applyDates(){const start=$('startDate').value,end=$('endDate').value;if(start&&end&&start>end){showError('La fecha inicial debe ser anterior o igual a la final.');return}
    state.start=start;state.end=end;document.querySelectorAll('[data-period]').forEach(b=>b.classList.remove('selected'));load();}
  function relativeMonths(n){const date=new Date(`${state.latestDate || new Date().toISOString().slice(0,10)}T12:00:00`);date.setMonth(date.getMonth()-n);return date.toISOString().slice(0,10)}
  function setup(){
    $('todayLabel').textContent='Colombia · GMT-5';
    $('applyBtn').addEventListener('click',applyDates);
    $('refreshBtn').addEventListener('click',()=>load(true));
    $('exportBtn').addEventListener('click',()=>{window.location.href=`/api/export.csv?${params()}`});
    $('downloadPlot').addEventListener('click',()=>Plotly.downloadImage('boxChart',{format:'png',filename:'Distribucion_TRM',width:1500,height:750,scale:2}));
    document.querySelectorAll('[data-group]').forEach(b=>b.addEventListener('click',()=>{state.group=b.dataset.group;document.querySelectorAll('[data-group]').forEach(x=>x.classList.toggle('active',x===b));load()}));
    document.querySelectorAll('[data-period]').forEach(b=>b.addEventListener('click',()=>{
      if(!state.latestDate)return;
      state.end=state.latestDate;state.start=relativeMonths(Number(b.dataset.period));
      document.querySelectorAll('[data-period]').forEach(x=>x.classList.toggle('selected',x===b));load();
    }));
    $('mobileMenu').addEventListener('click',()=>{$('sidebar').classList.toggle('open')});
    document.querySelectorAll('.nav-link').forEach(a=>a.addEventListener('click',()=>{$('sidebar').classList.remove('open');document.querySelectorAll('.nav-link').forEach(x=>x.classList.toggle('active',x===a))}));
    window.setInterval(()=>{if(!document.hidden)load()},20*60*1000);
    if(typeof Plotly==='undefined'){showError('No se pudo cargar Plotly. Comprueba la conexión a Internet para descargar Plotly.');return}
    load();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup);else setup();
})();
