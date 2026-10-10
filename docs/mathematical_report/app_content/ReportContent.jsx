import React,{useState,useEffect,useRef} from 'react';
import {RichNarrative,ReportSection,useDataApp} from '../../data-app-public.jsx';
import chapters from './chapters.json';import checks from './checks.json';
import {ProseBlock,GlossaryView,BibliographyView,CodeView,ComparisonsView,GraphView,HypothesesView,MathView,termMap,ReportDataProvider,useMathematicalData} from './MathematicalViews.jsx';
import './mathematical.css';import './katex-offline.css';
import './scholarly.css';

export function ReportContent(){
 return <ReportDataProvider><ReportBody/></ReportDataProvider>;
}
function ReportBody(){
 const{equationMap}=useMathematicalData();
 const{appTitle,setAppTitle,canEdit,mode,reviewedPeriodRows,visible}=useDataApp();
 const[view,setView]=useState('chapter-00');const[selected,setSelected]=useState('');const[code,setCode]=useState(null);const[search,setSearch]=useState('');const[tip,setTip]=useState(null);const article=useRef(null);
 const tipTimer=useRef(null),hideTimer=useRef(null),hoverTarget=useRef(null);
 const clearTipTimers=()=>{clearTimeout(tipTimer.current);clearTimeout(hideTimer.current);hoverTarget.current=null};
 const closeTip=()=>{clearTipTimers();setTip(null)};
 useEffect(()=>()=>{clearTimeout(tipTimer.current);clearTimeout(hideTimer.current)},[]);
 useEffect(()=>{const update=()=>{let h;try{h=decodeURIComponent(location.hash.slice(1))}catch{h='chapter-00'};setTip(null);if(h.startsWith('code-')&&h!=='code-browser'){const m=/^code-([a-f0-9]+)-(\d+)-(\d+)$/.exec(h);if(m){setCode({sourceId:m[1],start:Number(m[2]),end:Number(m[3])});setView('code-browser')}}else if(h.startsWith('term-')){setSelected(h.slice(5));setView('glossary')}else if(h.startsWith('ref-')){setSelected(h.slice(4));setView('bibliography')}else if(equationMap[h])setView(equationMap[h].chapter);else if(chapters.some(c=>c.id===h)||['comparisons','relations','glossary','bibliography','code-browser','hypotheses','all-chapters'].includes(h))setView(h);if(h)setTimeout(()=>{const target=document.getElementById(h)||(h.startsWith('code-')?document.getElementById('code-browser'):null);const bank=target?.closest('.formula-bank');if(bank)bank.open=true;target?.scrollIntoView({block:'start'})},160)};update();window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update)},[]);
 useEffect(()=>{clearTipTimers();setTip(null);article.current?.querySelectorAll('a[href^="#term-"],a[href^="#eq-"]').forEach(a=>a.removeAttribute('title'))},[view]);
 const showTip=(e,keyboard=false)=>{
  if(e.target.closest?.('.term-tooltip')){clearTimeout(hideTimer.current);return}
  const a=e.target.closest?.('a');if(!a)return;
  const h=a.getAttribute('href')||'';
  const item=h.startsWith('#term-')?termMap[h.slice(6)]:h.startsWith('#eq-')?equationMap[h.slice(1)]:null;
  if(!item)return;
  clearTimeout(hideTimer.current);
  if(!keyboard&&hoverTarget.current===a)return;
  clearTimeout(tipTimer.current);hoverTarget.current=a;setTip(null);
  const display=()=>{if(!a.isConnected||(!keyboard&&!a.matches(':hover')))return;const r=a.getBoundingClientRect();setTip({kind:h.startsWith('#term-')?'term':'math',item,x:Math.max(12,Math.min(r.left,window.innerWidth-350)),y:Math.max(85,Math.min(r.bottom+10,window.innerHeight-230))})};
  if(keyboard)display();else tipTimer.current=setTimeout(display,1000);
 };
 const leaveTip=e=>{
  const a=e.target.closest?.('a'),panel=e.target.closest?.('.term-tooltip');
  const next=e.relatedTarget;
  if(a&&next&&a.contains(next))return;
  if(panel&&next&&panel.contains(next))return;
  if(!a&&!panel)return;
  clearTimeout(tipTimer.current);hoverTarget.current=null;
  if(next?.closest?.('.term-tooltip'))return;
  clearTimeout(hideTimer.current);hideTimer.current=setTimeout(()=>setTip(null),180);
 };
 const hits=search.length>=2?chapters.filter(c=>c.search.toLowerCase().includes(search.toLowerCase())):[];const shown=view==='all-chapters'?chapters:chapters.filter(c=>c.id===view);
 return <article ref={article} lang="pl" className="report-content report-page qml-math" aria-label="Monografia matematyczna QML" onMouseOver={e=>showTip(e)} onMouseOut={leaveTip} onFocus={e=>showTip(e,true)} onBlur={leaveTip} onKeyDown={e=>{if(e.key==='Escape')closeTip()}}>
 <header className="report-hero"><h1 data-data-app-title contentEditable={canEdit&&mode==='edit'} suppressContentEditableWarning onBlur={canEdit&&mode==='edit'?e=>setAppTitle(e.currentTarget.textContent.trim()||appTitle):undefined}>{appTitle}</h1><RichNarrative id="math-intro" value="**Opracowanie: 5 października 2026 · korekta: 9 października 2026.** Dowody, wyprowadzenia, hipotezy i konkretne implementacje. Wyniki benchmarków są zachowanymi danymi projektu; daty i reżimy podano przy źródłach. Raport działa offline."/><p className="report-counts" data-reviewed-rows>{checks.words.toLocaleString('pl-PL')} słów · {checks.equations} zapisów matematycznych · {checks.code_references} precyzyjnych odnośników do kodu · {checks.sources} źródła</p></header>
 <div className="math-navigation"><label>Rozdział <select value={chapters.some(c=>c.id===view)?view:''} onChange={e=>{if(e.target.value)location.hash=e.target.value}}><option value="">Wybierz rozdział</option>{chapters.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></label><nav aria-label="Narzędzia raportu">{[['comparisons','Wykresy'],['relations','Grafy'],['hypotheses','Hipotezy'],['glossary','Słownik'],['bibliography','Bibliografia'],['code-browser','Kod'],['all-chapters','Cały tekst']].map(([id,label])=><a key={id} className={view===id?'active':''} href={'#'+id}>{label}</a>)}</nav><label>Szukaj w całej monografii <input id="report-search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Wpisz zagadnienie, hipotezę albo wzór"/></label>{search.length>=2&&<div className="search-results" aria-live="polite"><p>{hits.length} pasujących rozdziałów</p>{hits.map(c=><a href={'#'+c.id} key={c.id} onClick={()=>setSearch('')}>{c.title}</a>)}</div>}</div>
 {shown.map(c=><section id={c.id} key={c.id} className="math-chapter">{visible('section-'+c.id)&&<ReportSection id={'section-'+c.id} title={c.title} queryId={c.queryId} sourceRows={reviewedPeriodRows(c.queryId)} showHeading={false}>{c.blocks.map(b=><ProseBlock key={b.id} block={b}/>)}</ReportSection>}<div className="chapter-footer"><a href="#bibliography">Bibliografia</a><a href="#code-browser">Sprawdź kod</a><a href="#relations">Powiązania matematyczne</a>{chapters[chapters.indexOf(c)+1]&&<a href={'#'+chapters[chapters.indexOf(c)+1].id}>Następny rozdział →</a>}</div></section>)}
 {view==='comparisons'&&<ComparisonsView/>}{view==='relations'&&<GraphView/>}{view==='hypotheses'&&<HypothesesView/>}{view==='glossary'&&<GlossaryView selected={selected}/>} {view==='bibliography'&&<BibliographyView selected={selected} chapters={chapters}/>} {view==='code-browser'&&<CodeView selection={code}/>}
 {tip&&<aside className="term-tooltip" id="math-tooltip" role="tooltip" style={{left:tip.x,top:tip.y}}><button aria-label="Zamknij objaśnienie" onClick={closeTip}>×</button>{tip.kind==='term'?<><strong>{tip.item.term}</strong><p>{tip.item.short}</p><a href={'#term-'+tip.item.id}>Rozwinięte wyjaśnienie →</a></>:<><MathView id={tip.item.id} anchor={false}/><a href={'#'+tip.item.id}>Przejdź do wzoru →</a></>}</aside>}
 </article>;
}
