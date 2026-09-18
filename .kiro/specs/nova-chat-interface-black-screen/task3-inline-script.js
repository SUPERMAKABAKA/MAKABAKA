
const $=s=>document.querySelector(s);
const svgArrow='<svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M7 17L17 7M17 7H8M17 7v9" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* ---- auth state ---- */
let token=localStorage.getItem("nova_token")||null;
let username=localStorage.getItem("nova_user")||null;
let mode="login";

/* live reduced-motion query: read on demand so a mid-session OS change is
   respected without a reload */
const mqReduce=window.matchMedia?window.matchMedia("(prefers-reduced-motion:reduce)"):null;
const prefersReduced=()=>!!(mqReduce&&mqReduce.matches);

const welcomeScreen=$("#welcomeScreen"), authScreen=$("#authScreen"), appScreen=$("#appScreen");
const authForm=$("#authForm"), authErr=$("#authErr"), authSubmit=$("#authSubmit");
const uInput=$("#username"), pInput=$("#password");

const pwToggle=$("#pwToggle"), pwIcon=$("#pwIcon"), pwHint=$("#pwHint");
const tabLogin=$("#tabLogin"), tabRegister=$("#tabRegister");

/* ============================================================
   VIEW ROUTING:  welcome -> auth -> app
   ------------------------------------------------------------
   Three top-level views live in one document. `setView` is the single
   place that swaps them, so the hero animation is always stopped when
   it leaves the screen and the app's coloured ambient layers are always
   restored when the product opens. The welcome -> auth step pushes a
   history entry, so browser Back returns to the welcome page.
   ============================================================ */
let view="welcome", pushedAuth=false;

function setView(name){
  view=name;
  document.body.classList.toggle("front", name!=="app");
  welcomeScreen.classList.toggle("hidden", name!=="welcome");
  authScreen.classList.toggle("hidden", name!=="auth");
  appScreen.classList.toggle("hidden", name!=="app");
  if(name==="welcome") startHero(); else stopHero();
}

/* Start / "Sign in": open the dedicated auth view. The decorative products
   recede and the headline lifts away first, but only for ~0.26s - the form is
   never gated behind a long animation. */
function openAuth(){
  if(view==="auth") return;
  if(!pushedAuth){ try{ history.pushState({nova:"auth"},"","#/auth"); pushedAuth=true; }catch(e){} }
  const go=()=>{ welcomeScreen.classList.remove("wp-leaving"); setView("auth");
    requestAnimationFrame(()=>{ try{ uInput.focus({preventScroll:true}); }catch(e){ uInput.focus(); } }); };
  if(view==="welcome" && !prefersReduced()){
    welcomeScreen.classList.add("wp-leaving");
    heroExit();
    setTimeout(go,260);
  }else go();
}

/* return to the welcome page, resetting the form to a clean signed-out state */
function enterWelcome(){
  hideAuthDone();
  uInput.value=""; pInput.value=""; setPwVisible(false); setMode("login");
  setView("welcome");
}
function backToWelcome(){
  if(pushedAuth){ history.back(); return; }         // popstate finishes the job
  try{ history.replaceState({nova:"welcome"},"",location.pathname+location.search); }catch(e){}
  enterWelcome();
}
window.addEventListener("popstate",()=>{
  pushedAuth=false;
  if(token&&username) return;                       // signed in: stay in the app
  if(location.hash==="#/auth"){ pushedAuth=true; setView("auth"); }
  else enterWelcome();
});

$("#wpStart").addEventListener("click",openAuth);
$("#wpSignIn").addEventListener("click",openAuth);
$("#authBack").addEventListener("click",backToWelcome);

function setMode(m){
  mode=m; const login=m==="login";
  tabLogin.classList.toggle("on",login);
  tabRegister.classList.toggle("on",!login);
  tabLogin.setAttribute("aria-pressed",login?"true":"false");
  tabRegister.setAttribute("aria-pressed",login?"false":"true");
  $("#authTitle").textContent=login?"Welcome back":"Meet your shopping companion";
  $("#authSub").textContent=login?"Sign in to continue with Nova.":"Create an account to get started.";
  authSubmit.textContent=login?"Sign in":"Create account";
  // login asks for an existing password; register shows the real rule enforced
  // by the server (password min_length=4) as guidance
  pInput.placeholder=login?"Enter your password":"Create a password";
  if(pwHint) pwHint.hidden=login;
  pInput.setAttribute("autocomplete",login?"current-password":"new-password");
  showErr("");
}
tabLogin.onclick=()=>setMode("login");
tabRegister.onclick=()=>setMode("register");
function showErr(t){ authErr.textContent=t; authErr.classList.toggle("show",!!t); }

/* ---- show / hide password ---- */
const PW_EYE='<path d="M2.6 12S6.2 5.8 12 5.8 21.4 12 21.4 12 17.8 18.2 12 18.2 2.6 12 2.6 12z"/>'+
  '<circle cx="12" cy="12" r="3.1"/>';
const PW_EYE_OFF='<path d="M4 4l16 16"/>'+
  '<path d="M9.7 6.2A9.6 9.6 0 0 1 12 5.8c5.8 0 9.4 6.2 9.4 6.2a17.6 17.6 0 0 1-3.1 3.9"/>'+
  '<path d="M6.4 8.3A17.7 17.7 0 0 0 2.6 12S6.2 18.2 12 18.2c1.1 0 2.2-.2 3.2-.6"/>'+
  '<path d="M9.9 9.9a3.1 3.1 0 0 0 4.2 4.2"/>';
function setPwVisible(on){
  pInput.type=on?"text":"password";
  pwIcon.innerHTML=on?PW_EYE_OFF:PW_EYE;
  pwToggle.setAttribute("aria-pressed",on?"true":"false");
  pwToggle.setAttribute("aria-label",on?"Hide password":"Show password");
}
if(pwToggle){
  setPwVisible(false);
  pwToggle.addEventListener("click",()=>{ setPwVisible(pInput.type==="password"); pInput.focus(); });
}

/* brief confirmation shown ONLY on a real 2xx from /auth/login|register.
   Nothing here fakes authentication and no timer stands in for it. */
const authDone=$("#authDone");
function hideAuthDone(){ if(authDone) authDone.classList.remove("show"); }
async function authSucceeded(){
  if(authDone){
    $("#authDoneT").textContent=(mode==="login"?"Welcome back, ":"You're all set, ")+username;
    $("#authDoneS").textContent="Opening Nova...";
    authDone.classList.add("show");
    await sleep(prefersReduced()?140:620);
    hideAuthDone();
  }
  enterApp();
}

authForm.addEventListener("submit",async e=>{
  e.preventDefault();
  const u=uInput.value.trim(), p=pInput.value;
  if(u.length<2){ showErr("Username needs at least 2 characters"); return; }
  if(p.length<4){ showErr("Password needs at least 4 characters"); return; }
  authSubmit.disabled=true; authSubmit.textContent=mode==="login"?"Signing in...":"Creating...";
  try{
    const res=await fetch("/auth/"+mode,{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({username:u,password:p})});
    const data=await res.json();
    if(!res.ok){ showErr(data.error||"Something went wrong"); return; }
    token=data.token; username=data.username;
    localStorage.setItem("nova_token",token); localStorage.setItem("nova_user",username);
    await authSucceeded();
  }catch(err){ showErr("Network error. Is the server running?"); }
  // clear the loading state without calling setMode(), which would also wipe the
  // error we just set - server errors ("Invalid username or password",
  // "Username already exists") need to stay on screen
  finally{ authSubmit.disabled=false; authSubmit.textContent=mode==="login"?"Sign in":"Create account"; }
});

function enterApp(){
  setView("app");
  pushedAuth=false;
  try{ history.replaceState({nova:"app"},"","#/app"); }catch(e){}
  $("#userName").textContent=username; $("#userAv").textContent=(username[0]||"?").toUpperCase();
  input.focus();
}
$("#logout").onclick=()=>{
  token=null;username=null; localStorage.removeItem("nova_token"); localStorage.removeItem("nova_user");
  streamInner.innerHTML=""; streamInner.appendChild(welcome); welcome.style.display="";
  for(const k in sessions) delete sessions[k]; histEl.innerHTML=""; sessionId=newId();
  pushedAuth=false;
  try{ history.replaceState({nova:"welcome"},"",location.pathname+location.search); }catch(e){}
  enterWelcome();
};


/* ---- chat ---- */
const streamInner=$("#streamInner"), stream=$("#stream"), input=$("#input"),
  sendBtn=$("#send"), welcome=$("#welcome"), histEl=$("#hist");
let sessionId=newId(), busy=false;
function newId(){ return "s-"+Math.random().toString(36).slice(2,10); }
/* session store: sessionId -> { title, html } (html = streamInner snapshot) */
const sessions={};
/* Persist the current session's conversation as an innerHTML snapshot */
function saveSession(){ if(sessions[sessionId]) sessions[sessionId].html=streamInner.innerHTML; }
/* Switch the visible conversation to an existing session's snapshot */
function switchToSession(id){
  if(!sessions[id]) return;
  saveSession();
  sessionId=id;
  streamInner.innerHTML=sessions[id].html;
  if(typeof closeProduct==="function") closeProduct();
  welcome.style.display="none"; stopWelcomeVisuals();
  [...histEl.children].forEach(h=>h.classList.toggle("on",h.dataset.session===id));
  $("#topMeta").textContent="Tell me what you want to buy";
  scrollDown();
}
function autosize(){ input.style.height="auto"; input.style.height=Math.min(input.scrollHeight,140)+"px"; }
input.addEventListener("input",()=>{ autosize(); sendBtn.disabled=!input.value.trim()||busy; });
input.addEventListener("keydown",e=>{ if(e.key==="Enter"&&!e.shiftKey){ e.preventDefault(); doSend(); }});
sendBtn.addEventListener("click",doSend);
document.querySelectorAll(".chip").forEach(c=>c.addEventListener("click",()=>{
  input.value=c.textContent; autosize(); sendBtn.disabled=false; input.focus();
}));
$("#newChat").onclick=()=>{
  saveSession();
  sessionId=newId(); streamInner.innerHTML=""; streamInner.appendChild(welcome);
  if(typeof closeProduct==="function") closeProduct();
  welcome.style.display=""; $("#topMeta").textContent="Tell me what you want to buy";
  [...histEl.children].forEach(h=>h.classList.remove("on"));
};

/* ===== left history sidebar collapse/expand ===== */
const appEl=$("#appScreen");
$("#sideToggle").onclick=()=>{ appEl.classList.toggle("side-collapsed"); };

/* ===== right panel: recommended products + in-panel embedded shopping browser ===== */
let activeRecCard=null;
let brProducts=[];
// Build an embeddable shopping-search URL that ALLOWS iframing (Amazon/Google block
// framing (Amazon/Shopee/Lazada block it via X-Frame-Options / CSP frame-ancestors;
// AliExpress allows it). Clicking a product loads its results right inside the panel
// iframe - native click/scroll/link, zero anti-bot.
function embedSearchUrl(q){
  return "https://www.aliexpress.com/wholesale?SearchText="+encodeURIComponent(q);
}
function extShopUrl(q){
  // external "open on Amazon" jump for the real product page in a new tab
  return "https://www.amazon.com/s?k="+encodeURIComponent(q);
}
function openRecommendationsPanel(recs){
  brProducts=(recs||[]).map(r=>({title:(r.title||r.product_id||"Product"), q:(r.title||r.product_id||"product")}));
  if(!brProducts.length) return;
  const tabs=$("#ppProdTabs"); tabs.innerHTML="";
  brProducts.forEach((p,i)=>{
    const b=document.createElement("button"); b.className="pp-prodtab"+(i===0?" on":"");
    b.textContent=p.title; b.title=p.title;
    b.addEventListener("click",()=>selectProduct(i));
    tabs.appendChild(b);
  });
  $("#ppTitle").textContent="Shopping browser";
  appEl.classList.add("panel-open"); $("#productPanel").setAttribute("aria-hidden","false");
  selectProduct(0);
  setTimeout(fitEmbed, 400);   // after slide-in transition, panel has final width
}
// Fit the embedded desktop site into the panel width: render the iframe at a fixed
// logical width (FW) and scale it DOWN so the whole page fits (no horizontal scroll),
// growing/shrinking as the panel resizes.
const EMBED_FW=1180;
function fitEmbed(){
  const wrap=$("#ppWebwrap"), frame=$("#ppWebframe");
  if(!wrap||!frame) return;
  const cw=wrap.clientWidth||wrap.getBoundingClientRect().width;
  const ch=wrap.clientHeight||wrap.getBoundingClientRect().height;
  if(cw<10||ch<10) return;
  const scale=cw/EMBED_FW;
  frame.style.width=EMBED_FW+"px";
  frame.style.height=Math.ceil(ch/scale)+"px";     // fill panel height after scaling
  frame.style.transform="scale("+scale.toFixed(4)+")";
}
function selectProduct(i){
  const tabs=$("#ppProdTabs").children;
  [...tabs].forEach((t,k)=>t.classList.toggle("on",k===i));
  const p=brProducts[i]; if(!p) return;
  const url=embedSearchUrl(p.q);
  const frame=$("#ppWebframe");
  frame.src=url;
  $("#ppWebwrap").classList.add("live");
  requestAnimationFrame(fitEmbed);
  $("#plEmpty").style.display="none";
  $("#ppUrl").textContent=url.replace(/^https?:\/\//,"").slice(0,52);
  $("#ppExt").href=extShopUrl(p.q);
  $("#ppRank").textContent="Viewing #"+(i+1);
}
// ---- draggable resizer: user can widen/narrow the panel; iframe follows live ----
(function wirePanelResizer(){
  const rz=$("#ppResizer"); if(!rz) return;
  let dragging=false;
  function px(e){ return (e.touches?e.touches[0].clientX:e.clientX); }
  function onMove(e){
    if(!dragging) return;
    // panel occupies the right edge; width = distance from cursor to right edge
    const w=Math.max(300, Math.min(window.innerWidth-320, window.innerWidth-px(e)));
    appEl.style.setProperty("--pw", w+"px");
    fitEmbed();
  }
  function stop(){ if(!dragging) return; dragging=false; appEl.classList.remove("resizing");
    document.removeEventListener("mousemove",onMove); document.removeEventListener("mouseup",stop);
    document.removeEventListener("touchmove",onMove); document.removeEventListener("touchend",stop); }
  function start(e){ dragging=true; appEl.classList.add("resizing"); e.preventDefault();
    document.addEventListener("mousemove",onMove); document.addEventListener("mouseup",stop);
    document.addEventListener("touchmove",onMove,{passive:false}); document.addEventListener("touchend",stop); }
  rz.addEventListener("mousedown",start);
  rz.addEventListener("touchstart",start,{passive:false});
})();
// keep the embedded page fitted on window resize + whenever the panel box changes
window.addEventListener("resize",()=>{ if(appEl.classList.contains("panel-open")) fitEmbed(); });
if(typeof ResizeObserver!=="undefined"){
  const wrap=$("#ppWebwrap");
  if(wrap){ new ResizeObserver(()=>{ if(appEl.classList.contains("panel-open")) fitEmbed(); }).observe(wrap); }
}
function closeProduct(){
  appEl.classList.remove("panel-open");
  $("#productPanel").setAttribute("aria-hidden","true");
  if(activeRecCard){ activeRecCard.classList.remove("active"); activeRecCard=null; }
  const frame=$("#ppWebframe"); if(frame){ frame.src="about:blank"; }
  $("#ppWebwrap").classList.remove("live"); $("#plEmpty").style.display="";
}

/* ===== floating Nova mascot: refs, state + mini panel ===== */
const novaBuddy=$("#novaBuddy"), nbPanel=$("#nbPanel");
let buddyStateTimer=null;
function buddySetState(state){
  if(!novaBuddy) return;
  novaBuddy.classList.remove("thinking","happy");
  if(buddyStateTimer){ clearTimeout(buddyStateTimer); buddyStateTimer=null; }
  if(state==="thinking"){ novaBuddy.classList.add("thinking"); }
  else if(state==="happy"){ novaBuddy.classList.add("happy"); buddyStateTimer=setTimeout(()=>novaBuddy.classList.remove("happy"),700); }
}
function toggleBuddyPanel(force){
  if(!nbPanel||!novaBuddy) return;
  const open = force!==undefined ? force : !nbPanel.classList.contains("open");
  nbPanel.classList.toggle("open",open);
  novaBuddy.classList.toggle("panel-open",open);
}
if(novaBuddy){
  novaBuddy.addEventListener("click",(e)=>{ e.stopPropagation(); toggleBuddyPanel(); });
  nbPanel.querySelectorAll(".nb-quick").forEach(b=>{
    b.addEventListener("click",()=>{
      toggleBuddyPanel(false);
      input.value=b.textContent; autosize(); sendBtn.disabled=busy||!input.value.trim(); input.focus();
      if(!busy) doSend();
    });
  });
  $("#nbNewChat").addEventListener("click",()=>{ toggleBuddyPanel(false); $("#newChat").click(); });
}
if(novaBuddy){
  // click outside closes the mini panel
  document.addEventListener("click",(e)=>{
    if(nbPanel.classList.contains("open") && !nbPanel.contains(e.target) && !novaBuddy.contains(e.target)){
      toggleBuddyPanel(false);
    }
  });
}
$("#ppClose").onclick=closeProduct;
/* Create a history entry bound to the current session and wire up switching */
function pushHistory(text){
  const title=text.length>42?text.slice(0,42)+"...":text;
  sessions[sessionId]={title, html:streamInner.innerHTML};
  const it=document.createElement("div"); it.className="hist-item on";
  it.textContent=title; it.title=text; it.dataset.session=sessionId;
  it.addEventListener("click",()=>switchToSession(it.dataset.session));
  [...histEl.children].forEach(h=>h.classList.remove("on")); histEl.prepend(it);
}
function addUser(text){
  if(welcome.parentNode){ welcome.style.display="none"; stopWelcomeVisuals(); }
  const m=document.createElement("div"); m.className="msg user";
  m.innerHTML='<div class="avatar me">'+esc((username||"U")[0].toUpperCase())+'</div><div class="bubble"></div>';
  m.querySelector(".bubble").textContent=text; streamInner.appendChild(m); scrollDown();
}
function addThinking(){
  const m=document.createElement("div"); m.className="msg ai";
  m.innerHTML='<div class="avatar ai">N</div><div class="bubble"><div class="thinking">'+
    '<div class="nova-orb"><div class="ring a"></div><div class="ring b"></div><div class="core"></div></div>'+
    '<span class="think-txt">Reading your profile and searching products</span></div></div>';
  streamInner.appendChild(m); scrollDown(); return m;
}
function aiBubble(){
  const m=document.createElement("div"); m.className="msg ai";
  m.innerHTML='<div class="avatar ai">N</div><div class="bubble"><div class="who">Nova</div><div class="body"></div></div>';
  streamInner.appendChild(m); return m;
}
function appendToken(body,text,caret){
  const span=document.createElement("span"); span.className="tok"; span.textContent=text;
  body.insertBefore(span,caret); scrollDown();
}
function renderRecs(container,recs,status){
  const wrap=document.createElement("div"); wrap.className="recs";
  const cards=[];
  recs.forEach((r,i)=>{
    const pos=(r.summary&&r.summary.positives||[]).slice(0,3);
    const neg=(r.summary&&r.summary.negatives||[]).slice(0,3);
    const card=document.createElement("div"); card.className="rec"; card.style.animationDelay=(i*90)+"ms";
    card.innerHTML=
      '<div class="rec-head"><div><div class="rec-title">'+esc(r.title||r.product_id)+'</div>'+
      '<div class="rec-open-hint">Click to browse on Amazon -></div></div>'+
      '<div class="rec-rank">#'+String(i+1).padStart(2,"0")+'</div></div>'+
      '<div class="rec-reason">'+esc(r.reason||"")+'</div>'+
      '<div class="rec-summary">'+
        '<div class="sum pos"><div class="sum-h"><i></i>Pros</div><ul>'+(pos.map(p=>'<li>'+esc(p)+'</li>').join("")||'<li>N/A</li>')+'</ul></div>'+
        '<div class="sum neg"><div class="sum-h"><i></i>Cons</div><ul>'+(neg.map(p=>'<li>'+esc(p)+'</li>').join("")||'<li>N/A</li>')+'</ul></div>'+
      '</div>';
    // clicking a card opens the live panel and browses THAT product on Amazon
    card.addEventListener("click",()=>{
      [...wrap.querySelectorAll(".rec.active")].forEach(e=>e.classList.remove("active"));
      card.classList.add("active"); activeRecCard=card;
      openRecommendationsPanel(recs); selectProduct(i);
    });
    wrap.appendChild(card); cards.push(card);
  });
  container.appendChild(wrap);
  if(status==="insufficient"){
    const n=document.createElement("div"); n.className="notices";
    n.innerHTML='<div class="notice">Few items matched. Showing all available results.</div>';
    container.appendChild(n);
  }
  scrollDown();
}
function renderNotices(container,notices){
  if(!notices||!notices.length) return;
  const n=document.createElement("div"); n.className="notices";
  n.innerHTML=notices.map(x=>'<div class="notice">'+esc(x)+'</div>').join("");
  container.appendChild(n); scrollDown();
}
function renderReact(container,steps){
  if(!steps||!steps.length) return;
  const box=document.createElement("div"); box.className="react";
  let html='<div class="react-h">Nova reasoning</div>';
  steps.forEach(st=>{
    html+='<div class="react-step">'+
      '<div class="react-k">Thought</div><div class="react-v">'+esc(st.thought||"")+'</div>'+
      '<div class="react-k">Plan</div><div class="react-v">'+esc(st.plan||"")+'</div>'+
      '<div class="react-k">Action</div><div class="react-v act">'+esc(st.action||"")+'</div>'+
    '</div>';
  });
  box.innerHTML=html; container.appendChild(box); scrollDown();
}
function renderOptions(container,options){
  if(!options||!options.length) return;
  const wrap=document.createElement("div"); wrap.className="opts";
  options.forEach(o=>{
    const b=document.createElement("button"); b.type="button"; b.className="opt"; b.textContent=o;
    b.addEventListener("click",()=>{
      if(busy) return;
      [...wrap.children].forEach(c=>c.classList.remove("picked"));
      b.classList.add("picked"); wrap.classList.add("done");
      input.value=o; doSend();
    });
    wrap.appendChild(b);
  });
  container.appendChild(wrap); scrollDown();
}

async function doSend(){
  const text=input.value.trim(); if(!text||busy) return;
  busy=true; sendBtn.disabled=true; buddySetState("thinking");
  if(!histEl.querySelector(".hist-item.on")) pushHistory(text);
  addUser(text); input.value=""; autosize();
  const think=addThinking();
  try{
    const res=await fetch("/chat/stream",{method:"POST",
      headers:{"Content-Type":"application/json",...(token?{"Authorization":"Bearer "+token}:{})},
      body:JSON.stringify({session_id:sessionId,message:text})});
    if(!res.ok||!res.body){ think.remove(); const m=aiBubble();
      await typeFallback(m.querySelector(".body"),"Sorry, the request failed. Please try again."); return; }

    think.remove();
    const m=aiBubble(); const body=m.querySelector(".body");
    const caret=document.createElement("span"); caret.className="caret"; body.appendChild(caret);

    const reader=res.body.getReader(); const dec=new TextDecoder(); let buf="";
    let recsData=null;
    while(true){
      const {value,done}=await reader.read(); if(done) break;
      buf+=dec.decode(value,{stream:true});
      let idx;
      while((idx=buf.indexOf("\n\n"))>=0){
        const raw=buf.slice(0,idx); buf=buf.slice(idx+2);
        const ev=parseSSE(raw); if(!ev) continue;
        if(ev.event==="token"){ appendToken(body, ev.data.text, caret); }
        else if(ev.event==="recommendations"){ recsData=ev.data; }
        else if(ev.event==="error"){ appendToken(body, ev.data.error||"Request failed", caret); }
      }
    }
    caret.remove();
    if(recsData){
      renderReact(body, recsData.react_steps);
      if(recsData.recommendations&&recsData.recommendations.length){
        renderRecs(body, recsData.recommendations, recsData.status);
        $("#topMeta").textContent="Recommended "+recsData.recommendations.length+" products";
        buddySetState("happy");
      } else {
        renderOptions(body, recsData.options);
      }
      renderNotices(body, recsData.notices);
    }
  }catch(err){ think.remove(); const m=aiBubble();
    await typeFallback(m.querySelector(".body"),"Network error. Please check the server and retry."); }
  finally{ busy=false; sendBtn.disabled=!input.value.trim(); input.focus(); scrollDown(); saveSession();
    if(!novaBuddy.classList.contains("happy")) buddySetState("idle"); }
}
function parseSSE(raw){
  let event="message",data="";
  raw.split("\n").forEach(l=>{ if(l.startsWith("event:")) event=l.slice(6).trim();
    else if(l.startsWith("data:")) data+=l.slice(5).trim(); });
  try{ return {event,data:JSON.parse(data||"{}")}; }catch{ return {event,data:{}}; }
}
async function typeFallback(el,text){ el.textContent=""; for(const ch of text){ el.textContent+=ch; await sleep(14);} scrollDown(); }
function scrollDown(){ stream.scrollTop=stream.scrollHeight; }

/* ---- chat redesign overrides ---- */
let historyOpener=null, productPanelOpener=null, profileOpener=null;
const recommendationGroups=new Map();
function syncSendState(){ sendBtn.disabled=busy||!input.value.trim(); }
function autosize(){ input.style.height="auto"; input.style.height=Math.min(input.scrollHeight,140)+"px"; }
function setActiveHistory(id){ [...histEl.children].forEach(item=>{ const on=item.dataset.session===id; item.classList.toggle("on",on); if(on)item.setAttribute("aria-current","true"); else item.removeAttribute("aria-current"); }); }
function saveSession(){ if(sessions[sessionId]) sessions[sessionId].html=streamInner.innerHTML; }
function closeProfileMenu({restoreFocus=true}={}){ const menu=$("#profileMenu"), control=$("#profileControl"); menu.hidden=true; control.setAttribute("aria-expanded","false"); if(restoreFocus&&profileOpener) profileOpener.focus(); }
function openProfileMenu(){ closeHistoryDrawer({restoreFocus:false}); setBuddyPanel(false,{restoreFocus:false}); const menu=$("#profileMenu"), control=$("#profileControl"); profileOpener=control; menu.hidden=false; control.setAttribute("aria-expanded","true"); }
function getDrawerFocusables(){ return [...$("#historyDrawer").querySelectorAll('button:not([disabled])')]; }
function openHistoryDrawer(){ closeProfileMenu({restoreFocus:false}); setBuddyPanel(false,{restoreFocus:false}); closeProduct({restoreFocus:false}); historyOpener=$("#sideToggle"); $("#historyBackdrop").hidden=false; const drawer=$("#historyDrawer"); drawer.setAttribute("aria-hidden","false"); appEl.classList.add("history-open"); $("#sideToggle").setAttribute("aria-expanded","true"); const shell=$("#appScreen .chat-shell"); if("inert" in shell) shell.inert=true; const active=histEl.querySelector(".hist-item.on"); (active||$("#historyClose")).focus(); }
function closeHistoryDrawer({restoreFocus=true}={}){ const drawer=$("#historyDrawer"); if(drawer.getAttribute("aria-hidden")==="true") return; $("#historyBackdrop").hidden=true; drawer.setAttribute("aria-hidden","true"); appEl.classList.remove("history-open"); $("#sideToggle").setAttribute("aria-expanded","false"); const shell=$("#appScreen .chat-shell"); if("inert" in shell) shell.inert=false; if(restoreFocus&&historyOpener) historyOpener.focus(); }
function pushHistory(text){ if(sessions[sessionId]) return; const title=text.length>42?text.slice(0,42)+"...":text; sessions[sessionId]={title,html:streamInner.innerHTML}; const item=document.createElement("button"); item.type="button"; item.className="hist-item on"; item.textContent=title; item.title=text; item.dataset.session=sessionId; histEl.prepend(item); setActiveHistory(sessionId); }
function switchToSession(id){ if(!sessions[id]) return; saveSession(); sessionId=id; streamInner.innerHTML=sessions[id].html; setActiveHistory(id); closeProduct({restoreFocus:false}); closeHistoryDrawer(); $("#topMeta").textContent="Ready to help you shop"; syncSendState(); scrollDown(); }
function resetChat(){ saveSession(); sessionId=newId(); streamInner.innerHTML=""; streamInner.appendChild(welcome); welcome.style.display=""; setActiveHistory(""); closeProduct({restoreFocus:false}); closeHistoryDrawer({restoreFocus:false}); closeProfileMenu({restoreFocus:false}); setBuddyPanel(false,{restoreFocus:false}); $("#topMeta").textContent="Ready to help you shop"; input.value=""; autosize(); syncSendState(); input.focus(); }
function embedSearchUrl(q){ return "https://www.aliexpress.com/wholesale?SearchText="+encodeURIComponent(q); }
function extShopUrl(q){ return "https://www.amazon.com/s?k="+encodeURIComponent(q); }
function openRecommendationsPanel(recs){ brProducts=(recs||[]).map(r=>({title:r.title||r.product_id||"Product",q:r.title||r.product_id||"product"})); if(!brProducts.length) return; closeHistoryDrawer({restoreFocus:false}); closeProfileMenu({restoreFocus:false}); setBuddyPanel(false,{restoreFocus:false}); const tabs=$("#ppProdTabs"); tabs.innerHTML=""; brProducts.forEach((p,index)=>{ const tab=document.createElement("button"); tab.type="button"; tab.className="pp-prodtab"; tab.textContent=p.title; tab.addEventListener("click",()=>selectProduct(index)); tabs.appendChild(tab); }); $("#ppTitle").textContent="Shopping browser"; appEl.classList.add("panel-open"); $("#productPanel").setAttribute("aria-hidden","false"); setTimeout(fitEmbed,180); }
function selectProduct(index){ const product=brProducts[index]; if(!product) return; [...$("#ppProdTabs").children].forEach((tab,i)=>tab.classList.toggle("on",i===index)); const frame=$("#ppWebframe"), url=embedSearchUrl(product.q); frame.src=url; $("#ppWebwrap").classList.add("live"); $("#plEmpty").style.display="none"; $("#ppUrl").textContent=url.replace(/^https?:\/\//,"").slice(0,52); $("#ppExt").href=extShopUrl(product.q); $("#ppRank").textContent="Viewing #"+(index+1); requestAnimationFrame(fitEmbed); }
function clearActiveRecommendationCards(){ appEl.querySelectorAll(".rec.active").forEach(card=>{ card.classList.remove("active"); card.setAttribute("aria-pressed","false"); }); }
function closeProduct({restoreFocus=true}={}){ appEl.classList.remove("panel-open"); $("#productPanel").setAttribute("aria-hidden","true"); clearActiveRecommendationCards(); activeRecCard=null; const frame=$("#ppWebframe"); if(frame)frame.src="about:blank"; $("#ppWebwrap").classList.remove("live"); $("#plEmpty").style.display=""; if(restoreFocus&&productPanelOpener&&productPanelOpener.isConnected) productPanelOpener.focus(); }
function fitEmbed(){ const wrap=$("#ppWebwrap"),frame=$("#ppWebframe"); if(!wrap||!frame)return; const width=wrap.clientWidth||wrap.getBoundingClientRect().width,height=wrap.clientHeight||wrap.getBoundingClientRect().height; if(width<10||height<10)return; const scale=width/EMBED_FW; frame.style.width=EMBED_FW+"px"; frame.style.height=Math.ceil(height/scale)+"px"; frame.style.transform="scale("+scale.toFixed(4)+")"; }
function novaReadField(obj,keys){ for(const k of keys){ const v=obj&&obj[k]; if(v!==undefined&&v!==null&&String(v).trim()!=="") return String(v); } return ""; }
function novaSafeImg(v){ return typeof v==="string"&&/^https?:\/\//i.test(v.trim())?v.trim():""; }
function renderRecs(container,recs,status){ const wrap=document.createElement("div"); wrap.className="recs"; const groupId="rec-"+Math.random().toString(36).slice(2); recommendationGroups.set(groupId,recs); recs.forEach((rec,index)=>{ const pos=(rec.summary&&rec.summary.positives||[]).slice(0,3),neg=(rec.summary&&rec.summary.negatives||[]).slice(0,3),title=rec.title||rec.product_id||"Product"; const image=novaSafeImg(novaReadField(rec,["image","image_url","product_image","thumbnail","thumbnail_url"])); const price=novaReadField(rec,["price","price_text"]),rating=novaReadField(rec,["rating","rating_score"]),match=novaReadField(rec,["match_score","matchScore","match_percentage","match"]),review=novaReadField(rec,["review_summary","reviewSummary","review"]); const badge=index===0?"Best Match":index===1?"Smart Save":index===2?"Upgrade":""; const card=document.createElement("button"); card.type="button"; card.className="rec"; card.dataset.recGroup=groupId; card.dataset.recIndex=String(index); card.setAttribute("aria-label","View recommendation "+(index+1)+": "+title); card.setAttribute("aria-pressed","false"); const priceRow=(price||rating||match)?('<div class="rec-price-row">'+(price?'<span class="rec-price">'+esc(price)+'</span>':'')+(rating?'<span class="rec-rating">★ '+esc(rating)+'</span>':'')+(match?'<span class="rec-match">'+esc(match)+' match</span>':'')+'</div>'):''; const reviewRow=review?('<div class="rec-review"><strong>Review summary</strong>'+esc(review)+'</div>'):''; card.innerHTML='<div class="rec-media">'+(image?'<img src="'+esc(image)+'" alt="" loading="lazy">':'<span class="rec-media-fallback">Image not provided</span>')+(badge?'<span class="rec-badge">'+badge+'</span>':'')+'</div><div class="rec-body"><div class="rec-head"><div class="rec-title">'+esc(title)+'</div><div class="rec-rank">#'+String(index+1).padStart(2,"0")+'</div></div>'+priceRow+'<div class="rec-reason">'+esc(rec.reason||"")+'</div><div class="rec-summary"><div class="sum"><div class="sum-h">Pros</div><ul>'+(pos.map(v=>"<li>"+esc(v)+"</li>").join("")||"<li>Not provided</li>")+'</ul></div><div class="sum"><div class="sum-h">Cons</div><ul>'+(neg.map(v=>"<li>"+esc(v)+"</li>").join("")||"<li>Not provided</li>")+'</ul></div></div>'+reviewRow+'<span class="rec-cta">View Product</span></div>'; wrap.appendChild(card); }); container.appendChild(wrap); if(status==="insufficient")renderNotices(container,["Few items matched. Showing all available results."]); scrollDown(); }
function renderReact(container,steps){ if(!steps||!steps.length)return; const box=document.createElement("div"); box.className="react"; box.innerHTML='<div class="react-h">Nova details</div>'+steps.map(step=>'<div class="react-step"><div class="react-k">Thought</div><div class="react-v">'+esc(step.thought||"")+'</div><div class="react-k">Plan</div><div class="react-v">'+esc(step.plan||"")+'</div><div class="react-k">Action</div><div class="react-v">'+esc(step.action||"")+'</div></div>').join(""); container.appendChild(box); }
function renderNotices(container,notices){ if(!notices||!notices.length)return; const wrap=document.createElement("div"); wrap.className="notices"; notices.forEach(note=>{const item=document.createElement("div");item.className="notice";item.textContent=note;wrap.appendChild(item);});container.appendChild(wrap); }
function renderOptions(container,options){ if(!options||!options.length)return; const wrap=document.createElement("div"); wrap.className="opts"; options.forEach(option=>{const button=document.createElement("button");button.type="button";button.className="opt";button.textContent=option;button.setAttribute("aria-pressed","false");wrap.appendChild(button);});container.appendChild(wrap); }
function addThinking(){ const message=document.createElement("div");message.className="msg ai";message.innerHTML='<div class="avatar ai">N</div><div class="bubble"><div class="thinking" role="status" aria-live="polite"><span>Nova is reviewing your request…</span><span class="agent-stages"><span class="agent-stage on">搜索商品</span><span class="agent-stage">比较价格</span><span class="agent-stage">分析评论</span><span class="agent-stage">生成推荐</span></span></div></div>';streamInner.appendChild(message);scrollDown();return message; }
function aiBubble(){ const message=document.createElement("div");message.className="msg ai";message.innerHTML='<div class="avatar ai">N</div><div class="bubble"><div class="who">Nova</div><div class="body"></div></div>';streamInner.appendChild(message);return message; }
function addUser(text){ if(welcome.parentNode)welcome.style.display="none"; const message=document.createElement("div");message.className="msg user";message.innerHTML='<div class="bubble"></div>';message.querySelector(".bubble").textContent=text;streamInner.appendChild(message);scrollDown(); }
function appendToken(body,text,caret){ const tokenEl=document.createElement("span"); tokenEl.className="tok";tokenEl.textContent=text;body.insertBefore(tokenEl,caret);scrollDown(); }
async function typeFallback(el,text){ el.textContent=text;scrollDown(); }
function setBuddyPanel(open,{restoreFocus=true}={}){ const panel=$("#nbPanel"),button=$("#novaBuddy"); panel.setAttribute("aria-hidden",open?"false":"true");button.setAttribute("aria-expanded",open?"true":"false");button.classList.toggle("panel-open",open);if(open){closeHistoryDrawer({restoreFocus:false});closeProfileMenu({restoreFocus:false});closeProduct({restoreFocus:false});panel.querySelector("button").focus();}else if(restoreFocus)button.focus(); }
async function doSend(){ const text=input.value.trim(); if(!text||busy)return; busy=true;syncSendState(); if(!sessions[sessionId])pushHistory(text); addUser(text); input.value="";autosize();const thinking=addThinking();try{const res=await fetch("/chat/stream",{method:"POST",headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{})},body:JSON.stringify({session_id:sessionId,message:text})});if(!res.ok||!res.body){thinking.remove();const reply=aiBubble();await typeFallback(reply.querySelector(".body"),"Sorry, the request failed. Please try again.");return;}thinking.remove();const reply=aiBubble(),body=reply.querySelector(".body"),caret=document.createElement("span");caret.className="caret";body.appendChild(caret);const reader=res.body.getReader(),decoder=new TextDecoder();let buffer="",responseData=null;while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let divider;while((divider=buffer.indexOf("\n\n"))>=0){const event=parseSSE(buffer.slice(0,divider));buffer=buffer.slice(divider+2);if(!event)continue;if(event.event==="token")appendToken(body,event.data.text||"",caret);else if(event.event==="recommendations")responseData=event.data;else if(event.event==="error")appendToken(body,event.data.error||"Request failed",caret);}}caret.remove();if(responseData){renderReact(body,responseData.react_steps);if(responseData.recommendations&&responseData.recommendations.length){renderRecs(body,responseData.recommendations,responseData.status);$("#topMeta").textContent="Recommendations ready";}else renderOptions(body,responseData.options);renderNotices(body,responseData.notices);}}catch(error){thinking.remove();const reply=aiBubble();await typeFallback(reply.querySelector(".body"),"Network error. Please check the server and retry.");}finally{busy=false;syncSendState();input.focus();scrollDown();saveSession();}}
$("#newChat").onclick=resetChat;$("#sideToggle").onclick=openHistoryDrawer;$("#historyClose").onclick=()=>closeHistoryDrawer();$("#historyBackdrop").onclick=()=>closeHistoryDrawer();$("#profileControl").onclick=()=>$("#profileMenu").hidden?openProfileMenu():closeProfileMenu();$("#ppClose").onclick=()=>closeProduct();$("#novaBuddy").onclick=()=>setBuddyPanel($("#nbPanel").getAttribute("aria-hidden")==="true",{restoreFocus:false});$("#nbNewChat").onclick=()=>{setBuddyPanel(false,{restoreFocus:false});resetChat();};
input.addEventListener("input",()=>{autosize();syncSendState();});input.addEventListener("keydown",event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();doSend();}});sendBtn.onclick=doSend;
streamInner.addEventListener("click",event=>{const chip=event.target.closest(".chip"),option=event.target.closest(".opt"),card=event.target.closest(".rec"),history=event.target.closest(".hist-item");if(chip&&!busy){input.value=chip.textContent;autosize();doSend();}if(option&&!busy&&!option.parentElement.classList.contains("done")){const group=option.parentElement;[...group.children].forEach(button=>{button.classList.toggle("picked",button===option);button.setAttribute("aria-pressed",button===option?"true":"false");});group.classList.add("done");input.value=option.textContent;doSend();}if(card){const recs=recommendationGroups.get(card.dataset.recGroup);const index=Number(card.dataset.recIndex);if(recs&&Number.isInteger(index)){clearActiveRecommendationCards();card.classList.add("active");card.setAttribute("aria-pressed","true");activeRecCard=card;productPanelOpener=card;openRecommendationsPanel(recs);selectProduct(index);setTimeout(()=>$("#ppClose").focus(),0);}}if(history)switchToSession(history.dataset.session);});
document.addEventListener("click",event=>{if(!$("#profileMenu").hidden&&!event.target.closest(".profile-wrap"))closeProfileMenu({restoreFocus:false});if($("#nbPanel").getAttribute("aria-hidden")==="false"&&!event.target.closest("#nbPanel")&&!event.target.closest("#novaBuddy")){const explicitTarget=event.target.closest('button,a,input,textarea,select,[tabindex]:not([tabindex="-1"])');setBuddyPanel(false,{restoreFocus:!explicitTarget});}});
document.addEventListener("keydown",event=>{if(event.key!=="Escape"&&event.key!=="Tab")return;if(event.key==="Escape"){if($("#historyDrawer").getAttribute("aria-hidden")==="false")closeHistoryDrawer();else if(!$("#profileMenu").hidden)closeProfileMenu();else if($("#nbPanel").getAttribute("aria-hidden")==="false")setBuddyPanel(false);else if(appEl.classList.contains("panel-open"))closeProduct();return;}if($("#historyDrawer").getAttribute("aria-hidden")==="false"){const focusables=getDrawerFocusables(),first=focusables[0],last=focusables[focusables.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
const panelResizer=$("#ppResizer");function syncPanelResizerA11y(){const maximum=Math.max(300,window.innerWidth-320),current=parseInt(getComputedStyle(appEl).getPropertyValue("--pw"),10)||Math.min(640,maximum);panelResizer.setAttribute("aria-valuemax",String(maximum));panelResizer.setAttribute("aria-valuenow",String(Math.max(300,Math.min(maximum,current))));}syncPanelResizerA11y();window.addEventListener("resize",syncPanelResizerA11y);panelResizer.addEventListener("pointerdown",event=>{event.preventDefault();panelResizer.setPointerCapture(event.pointerId);const move=moveEvent=>{const width=Math.max(300,Math.min(window.innerWidth-320,window.innerWidth-moveEvent.clientX));appEl.style.setProperty("--pw",width+"px");panelResizer.setAttribute("aria-valuenow",String(width));fitEmbed();};const stop=()=>{panelResizer.removeEventListener("pointermove",move);panelResizer.removeEventListener("pointerup",stop);};panelResizer.addEventListener("pointermove",move);panelResizer.addEventListener("pointerup",stop);});
panelResizer.addEventListener("keydown",event=>{if(!["ArrowLeft","ArrowRight"].includes(event.key))return;event.preventDefault();const current=parseInt(getComputedStyle(appEl).getPropertyValue("--pw"),10)||Math.min(640,window.innerWidth-320);const next=Math.max(300,Math.min(window.innerWidth-320,current+(event.key==="ArrowLeft"?24:-24)));appEl.style.setProperty("--pw",next+"px");panelResizer.setAttribute("aria-valuenow",String(next));fitEmbed();});
histEl.addEventListener("click",event=>{const item=event.target.closest(".hist-item");if(item)switchToSession(item.dataset.session);});
document.querySelectorAll(".nb-quick,#nbNewChat").forEach(button=>{const replacement=button.cloneNode(true);button.replaceWith(replacement);if(replacement.id==="nbNewChat")replacement.addEventListener("click",()=>{setBuddyPanel(false,{restoreFocus:false});resetChat();});else replacement.addEventListener("click",()=>{if(busy)return;setBuddyPanel(false,{restoreFocus:false});input.value=replacement.textContent;autosize();doSend();});});
if(window.visualViewport)window.visualViewport.addEventListener("resize",()=>{if(document.activeElement===input)requestAnimationFrame(scrollDown);});

/* ============================================================
   VISUALS: native 3D canvas artwork + mouse-follow spotlight
   No WebGL, no libraries. 2D canvas + simple perspective proj.
   ============================================================ */
const reduceMotion=window.matchMedia&&window.matchMedia("(prefers-reduced-motion:reduce)").matches;

/* ---- theme bridge ----
   Canvas can't resolve CSS custom properties, so read the palette tokens from
   :root once at boot. Retheming the product = editing the :root block only;
   the canvas artwork follows automatically. */
const THEME=(function(){
  const cs=getComputedStyle(document.documentElement);
  const pick=(name,fb)=>{ const v=cs.getPropertyValue(name).trim(); return v||fb; };
  return {
    accent:pick("--accent-rgb","255,122,69"),      // coral: primary
    accent2:pick("--accent-2-rgb","255,180,84"),   // amber: secondary
    soft:pick("--accent-soft-rgb","255,219,195"),  // near-white warm: highlights
    onAccent:pick("--on-accent","#2c0c02")         // ink drawn on top of accent fills
  };
})();
/* rgba("r,g,b", alpha) -> "rgba(r,g,b,a)" */
const rgbaStr=(triplet,a)=>"rgba("+triplet+","+(+a).toFixed(3)+")";

/* ---- reusable spotlight: follows mouse inside a container ---- */
function makeSpotlight(container,glowEl){
  if(!container||!glowEl) return {destroy(){}};
  let tx=0,ty=0,cx=0,cy=0,raf=0,active=false;
  function center(){ const r=container.getBoundingClientRect(); tx=r.width/2; ty=r.height/2; }
  function tick(){
    raf=0;
    cx+=(tx-cx)*.16; cy+=(ty-cy)*.16;
    glowEl.style.transform="translate("+cx+"px,"+cy+"px)";
    if(Math.abs(tx-cx)>.4||Math.abs(ty-cy)>.4) raf=requestAnimationFrame(tick);
  }
  function schedule(){ if(!raf) raf=requestAnimationFrame(tick); }
  function onMove(e){
    if(reduceMotion) return;
    const r=container.getBoundingClientRect();
    tx=e.clientX-r.left; ty=e.clientY-r.top; schedule();
  }
  function onEnter(){ container.classList.add("lit"); }
  function onLeave(){ if(reduceMotion) return; container.classList.remove("lit"); center(); schedule(); }
  center();
  if(reduceMotion){
    container.classList.add("lit");
    glowEl.style.transform="translate("+tx+"px,"+ty+"px)";
  }else{
    glowEl.style.transform="translate("+tx+"px,"+ty+"px)";
    container.addEventListener("mousemove",onMove);
    container.addEventListener("mouseenter",onEnter);
    container.addEventListener("mouseleave",onLeave);
  }
  return {destroy(){ if(raf)cancelAnimationFrame(raf);
    container.removeEventListener("mousemove",onMove);
    container.removeEventListener("mouseenter",onEnter);
    container.removeEventListener("mouseleave",onLeave); }};
}

/* ---- reusable 3D globe bound to a canvas ---- */
/* Latitude/longitude grid sampling on a unit sphere. Grid points form a
   clear rotating "globe net"; deterministic continent disks are marked
   land=true and drawn brighter/larger; the equator ring is highlighted;
   one satellite point orbits a tilted path. No libraries, 2D canvas +
   perspective projection only. */
function makeOrb(canvas,opts){
  opts=opts||{};
  const ctx=canvas.getContext("2d");
  if(!ctx) return {destroy(){}};
  // density preset: "dense" (auth) draws a crisper globe, otherwise sparser.
  const DENSE=(opts.mode==="dense")||(opts.count||420)>=360;
  const LINKS=opts.links!==false;       // draw faint latitude + longitude ring lines
  const DAMP=0.06;                       // rotation follow damping
  const LAT_STEP=DENSE?10:14;            // degrees between latitude rings
  const LON_STEP=DENSE?9:14;             // base degrees between longitude samples
  const LON_LINE_STEP=DENSE?15:30;       // degrees between meridian (longitude) arcs
  const ARC_SEG=DENSE?64:48;             // samples per grid arc (higher = smoother)
  const LINE_A=DENSE?1.0:0.85;           // scale for grid-line alpha (welcome dimmer)
  const LAT_MAX=80;                      // clamp near the poles
  let W=0,H=0,DPR=1,R=1,cxp=0,cyp=0;
  let spinY=0;                           // continuous auto-rotation (like a spinning planet)
  let curX=0,curY=0,tgtX=0,tgtY=0;       // damped mouse tilt
  let orbitA=0;                          // satellite orbit angle
  let raf=0,pts=[],rings=[],meridians=[];

  const D2R=Math.PI/180;
  const OUTLINES=false;                  // continent borders disabled: plates shown by dense fill points only

  function latLonToVec(latDeg,lonDeg){
    const la=latDeg*D2R, lo=lonDeg*D2R;
    const cl=Math.cos(la);
    return {x:cl*Math.cos(lo), y:Math.sin(la), z:cl*Math.sin(lo)};
  }

  // Deterministic continent plates as closed spherical polygons: each is an
  // ordered ring of [lat,lon] vertices. Shapes are stylised (not a real map)
  // but sized and scattered like plates: large landmasses, small ones, an
  // irregular outline, and a polar band. Order of vertices defines the border.
  const CONTINENTS=[
    // North America (large, upper-left region)
    [[62,-128],[70,-96],[58,-72],[46,-64],[30,-80],[24,-100],[34,-118],[50,-126]],
    // South America (tapering, lower-left)
    [[10,-70],[2,-52],[-14,-42],[-32,-54],[-50,-68],[-30,-72],[-12,-78]],
    // Europe (small, cluster upper-mid)
    [[60,-6],[64,18],[54,36],[44,26],[40,6],[48,-8]],
    // Africa (big, mid, irregular)
    [[34,-6],[30,28],[12,44],[-8,40],[-30,26],[-34,18],[-14,10],[6,2]],
    // Asia (largest, upper-right)
    [[66,44],[72,96],[62,140],[42,148],[26,120],[20,84],[32,54],[52,42]],
    // Oceania (small, lower-right)
    [[-12,120],[-14,142],[-28,150],[-38,144],[-32,124],[-22,118]],
    // Antarctic band (thin polar strip at the bottom)
    [[-72,-160],[-70,-80],[-72,0],[-70,80],[-72,160],[-78,120],[-80,0],[-78,-120]]
  ].map(ring=>ring.map(p=>latLonToVec(p[0],p[1])));

  // Spherical linear interpolation between two unit vectors (great-circle path).
  function slerp(a,b,t){
    let d=a.x*b.x+a.y*b.y+a.z*b.z;
    if(d>1)d=1; else if(d<-1)d=-1;
    const om=Math.acos(d);
    if(om<1e-4) return {x:a.x,y:a.y,z:a.z};
    const so=Math.sin(om), w1=Math.sin((1-t)*om)/so, w2=Math.sin(t*om)/so;
    return {x:a.x*w1+b.x*w2, y:a.y*w1+b.y*w2, z:a.z*w1+b.z*w2};
  }

  // Precompute densely-sampled border points (unit vectors) for each plate so
  // draw() only has to rotate + project them. Sampling along great-circle arcs
  // keeps the outline smooth as the globe turns.
  function buildBorder(ring){
    const out=[]; const STEP=DENSE?0.16:0.28;
    for(let i=0;i<ring.length;i++){
      const a=ring[i], b=ring[(i+1)%ring.length];
      let d=a.x*b.x+a.y*b.y+a.z*b.z; if(d>1)d=1; else if(d<-1)d=-1;
      const seg=Math.max(2,Math.ceil(Math.acos(d)/STEP));
      for(let s=0;s<seg;s++) out.push(slerp(a,b,s/seg));
    }
    return out;
  }
  const BORDERS=CONTINENTS.map(buildBorder);

  // Point-in-spherical-polygon test via signed-angle winding. A point counts as
  // land if it is inside any plate ring; used to light land points brighter than
  // ocean points so the plate faces read as filled.
  function insideRing(v,ring){
    let ang=0;
    for(let i=0;i<ring.length;i++){
      const a=ring[i], b=ring[(i+1)%ring.length];
      // vectors from v to each vertex, projected onto the tangent plane at v
      const av={x:a.x-v.x,y:a.y-v.y,z:a.z-v.z};
      const bv={x:b.x-v.x,y:b.y-v.y,z:b.z-v.z};
      const ta=tangent(av,v), tb=tangent(bv,v);
      const la=Math.hypot(ta.x,ta.y,ta.z), lb=Math.hypot(tb.x,tb.y,tb.z);
      if(la<1e-6||lb<1e-6) continue;
      let dot=(ta.x*tb.x+ta.y*tb.y+ta.z*tb.z)/(la*lb);
      if(dot>1)dot=1; else if(dot<-1)dot=-1;
      // sign of the turn via the sphere normal (v itself)
      const cx=ta.y*tb.z-ta.z*tb.y, cy=ta.z*tb.x-ta.x*tb.z, cz=ta.x*tb.y-ta.y*tb.x;
      const s=(cx*v.x+cy*v.y+cz*v.z)>=0?1:-1;
      ang+=s*Math.acos(dot);
    }
    return Math.abs(ang)>Math.PI;   // ~2*PI winding when enclosed
  }
  function tangent(w,n){ // remove the component of w along n
    const d=w.x*n.x+w.y*n.y+w.z*n.z;
    return {x:w.x-d*n.x, y:w.y-d*n.y, z:w.z-d*n.z};
  }
  function isLand(v){
    for(let i=0;i<CONTINENTS.length;i++){ if(insideRing(v,CONTINENTS[i])) return true; }
    return false;
  }

  // build latitude/longitude grid points on the unit sphere
  for(let lat=-LAT_MAX; lat<=LAT_MAX; lat+=LAT_STEP){
    const la=lat*D2R;
    const cl=Math.cos(la);
    // fewer longitude samples near the poles (scale by cos(lat))
    const n=Math.max(6, Math.round((360/LON_STEP)*Math.max(0.25,cl)));
    const equator=Math.abs(lat)<LAT_STEP*0.5;   // lat ~ 0 highlighted ring
    for(let k=0;k<n;k++){
      const lon=(k/n)*360-180;
      const v=latLonToVec(lat,lon);
      pts.push({x:v.x,y:v.y,z:v.z,land:isLand(v),equator});
    }
  }
  // continent fill points: scan the sphere on a finer grid and keep only the
  // samples that fall inside a plate polygon. This packs the plate interiors so
  // landmasses read as solid faces (not just a sparse lat/lon lattice) while the
  // OUTLINES borders still bound them. Built once here and cached in pts so
  // draw() only projects them; isLand() is never called per frame. dense fills
  // tightly (auth globe), sparse fills lightly (welcome stays restrained). A
  // hard cap keeps the total point budget in check so rAF stays smooth.
  const FILL_STEP=DENSE?2.4:4.5;               // smaller step => denser continent interiors (higher plate particle density)
  const FILL_CAP=DENSE?2600:360;               // raised cap so the denser grid isn't clipped (dense continents read solid)
  let fillCount=0;
  for(let lat=-LAT_MAX; lat<=LAT_MAX && fillCount<FILL_CAP; lat+=FILL_STEP){
    const la=lat*D2R, cl=Math.cos(la);
    const n=Math.max(6, Math.round((360/FILL_STEP)*Math.max(0.25,cl)));
    for(let k=0;k<n && fillCount<FILL_CAP;k++){
      const lon=(k/n)*360-180;
      const v=latLonToVec(lat,lon);
      if(isLand(v)){
        // deterministic pseudo-random per-point "city" flag: only a subset of
        // land fill points glow on the night side, so lights read as scattered
        // city clusters rather than a solid lit continent. Hash lat/lon so the
        // pattern is stable across frames and screen sizes.
        const h=Math.sin(lat*12.9898+lon*78.233)*43758.5453;
        const city=(h-Math.floor(h))<0.34;
        pts.push({x:v.x,y:v.y,z:v.z,land:true,equator:false,fill:true,city});
        fillCount++;
      }
    }
  }
  // latitude ring definitions (horizontal rings, for faint connecting arcs)
  for(let lat=-LAT_MAX; lat<=LAT_MAX; lat+=LAT_STEP){
    rings.push({lat, equator:Math.abs(lat)<LAT_STEP*0.5});
  }
  // meridian (longitude) definitions: vertical half-rings pole to pole at a
  // fixed longitude. lon 0 (prime meridian) drawn a touch brighter.
  for(let lon=0; lon<360; lon+=LON_LINE_STEP){
    meridians.push({lon, prime:lon===0});
  }

  function resize(){
    const rect=canvas.getBoundingClientRect();
    DPR=Math.min(window.devicePixelRatio||1,2);
    W=Math.max(1,Math.round(rect.width)); H=Math.max(1,Math.round(rect.height));
    canvas.width=Math.round(W*DPR); canvas.height=Math.round(H*DPR);
    ctx.setTransform(DPR,0,0,DPR,0,0);
    cxp=W/2; cyp=H/2; R=Math.min(W,H)*0.36;
  }

  function onMove(e){
    if(reduceMotion) return;
    const rect=canvas.getBoundingClientRect();
    const nx=(e.clientX-rect.left)/rect.width-0.5;
    const ny=(e.clientY-rect.top)/rect.height-0.5;
    tgtY=nx*0.9; tgtX=ny*0.9;
  }

  // rotate a unit vector around Y then X, then project to screen
  function project(px,py,pz,cosY,sinY,cosX,sinX){
    let x=px*cosY - pz*sinY;
    let z=px*sinY + pz*cosY;
    let y=py*cosX - z*sinX;
    z=py*sinX + z*cosX;
    const persp=1/(2.2 - z);
    // also return rotated world coords (x,y,z) so the day/night lighting can dot
    // each point normal against a fixed sun direction in view space.
    return {sx:cxp + x*R*persp*2.2, sy:cyp + y*R*persp*2.2, x, y, z, persp};
  }

  function draw(){
    ctx.clearRect(0,0,W,H);
    if(!reduceMotion){ spinY+=0.0026; orbitA+=0.010; }   // gentle planet spin
    curX+=(tgtX-curX)*DAMP; curY+=(tgtY-curY)*DAMP;
    const tiltX=curX, tiltY=spinY+curY;   // auto-spin plus damped mouse tilt
    const cosY=Math.cos(tiltY),sinY=Math.sin(tiltY);
    const cosX=Math.cos(tiltX),sinX=Math.sin(tiltX);

    // faint latitude + longitude grid arcs so the globe net reads clearly.
    // Front segments (z>=-0.15) draw at full grid alpha; back segments draw at
    // a low alpha instead of being cut, keeping the net continuous and giving
    // the sphere a see-through, volumetric feel. Each visible edge is stroked
    // on its own so front/back alpha can differ without breaking the arc.
    if(LINKS){
      ctx.lineWidth=DENSE?1:0.9;
      const strokeArc=function(sample, frontA, backA){
        // sample(i) -> projected point for i in [0..ARC_SEG]
        let prev=sample(0);
        for(let s=1;s<=ARC_SEG;s++){
          const cur=sample(s);
          // an edge is "front" when both endpoints are on the near hemisphere
          const front=(prev.z>=-0.15 && cur.z>=-0.15);
          const al=(front?frontA:backA)*LINE_A;
          ctx.strokeStyle=rgbaStr(THEME.accent,al);
          ctx.beginPath();
          ctx.moveTo(prev.sx,prev.sy);
          ctx.lineTo(cur.sx,cur.sy);
          ctx.stroke();
          prev=cur;
        }
      };
      // latitude rings (horizontal): full circle at fixed lat
      for(let ri=0;ri<rings.length;ri++){
        const ring=rings[ri];
        const la=ring.lat*D2R, cl=Math.cos(la), sy0=Math.sin(la);
        const frontA=ring.equator?0.17:0.10;   // equator toned down: only a touch brighter than plain rings
        const backA=ring.equator?0.05:0.03;
        strokeArc(function(s){
          const lon=(s/ARC_SEG)*Math.PI*2;
          return project(cl*Math.cos(lon), sy0, cl*Math.sin(lon), cosY,sinY,cosX,sinX);
        }, frontA, backA);
      }
      // meridians (vertical): half-ring from south pole to north pole at fixed lon
      for(let mi=0;mi<meridians.length;mi++){
        const m=meridians[mi];
        const lo=m.lon*D2R, clo=Math.cos(lo), slo=Math.sin(lo);
        const frontA=m.prime?0.13:0.10;
        const backA=m.prime?0.04:0.03;
        strokeArc(function(s){
          const la=(-Math.PI/2)+(s/ARC_SEG)*Math.PI;   // -90deg .. +90deg
          const cl=Math.cos(la), sy0=Math.sin(la);
          return project(cl*clo, sy0, cl*slo, cosY,sinY,cosX,sinX);
        }, frontA, backA);
      }
    }

    // grid points (painter order via depth; front bright, back faint)
    const proj=[];
    for(let i=0;i<pts.length;i++){
      const pt=pts[i];
      const p=project(pt.x,pt.y,pt.z,cosY,sinY,cosX,sinX);
      p.land=pt.land; p.equator=pt.equator; p.fill=pt.fill; p.city=pt.city;
      proj.push(p);
    }
    proj.sort((a,b)=>a.z-b.z);
    // Day/night lighting: a fixed sun direction in VIEW space (upper-left, a bit
    // toward the viewer). Each point normal (its rotated x,y,z) is dotted with
    // the sun to get illum in [-1..1]: >0 day side, <0 night side. As the globe
    // spins, the terminator sweeps across, so regions cross from day to night.
    // Day: cool teal, brighter. Night: much dimmer teal; land "city" points glow
    // warm amber like satellite night imagery, brightest deep on the night side.
    const SUN={x:0.42,y:-0.30,z:-0.85};      // sun BEHIND the viewer: night hemisphere faces us, so city lights sit on the front-center (not the edge)
    const slen=Math.hypot(SUN.x,SUN.y,SUN.z);
    for(let i=0;i<proj.length;i++){
      const p=proj[i];
      const depth=(p.z+1)/2;                 // 0 back .. 1 front
      const pf=0.6+0.4*p.persp;              // softened perspective contribution
      // illum: dot(normal, sun) in [-1..1]. day = t in [0..1], night when <0.
      const illum=(p.x*SUN.x + p.y*SUN.y + p.z*SUN.z)/slen;
      const day=Math.max(0,illum);           // 0 on/again night .. 1 full day
      const night=Math.max(0,-illum);        // 0 day .. 1 deep night
      let r,al;
      if(p.fill){
        r=Math.max(0.5,Math.min(1.4,(0.7+depth*1.5)*pf)); al=0.28+depth*0.5;
      }else if(p.equator){
        r=Math.max(0.5,Math.min(2.2,(0.6+depth*1.3)*pf)); al=0.16+depth*0.3;
      }else if(p.land){
        r=Math.max(0.5,Math.min(1.4,(0.7+depth*1.5)*pf)); al=0.3+depth*0.5;
      }else{
        r=Math.max(0.5,Math.min(1.6,(0.5+depth*1.2)*pf)); al=0.09+depth*0.26;
      }
      // Night-side land "cities" glow amber, but ONLY on the near (front)
      // hemisphere (p.z>=0.02) so lights never render on the far side showing
      // through the globe. Back-side / day-side points fall to the teal branch.
      // brighter on the day side and dimmed on the night side.
      if(p.land && p.city && night>0.12 && p.z>=0.02){
        // city light in the accent family: a bright warm-white core with a soft
        // amber bloom, so lights glow like city clusters that harmonize with the
        // palette. Strengthens toward deep night, softly twinkles.
        const tw=0.82+0.18*Math.sin(spinY*7+p.x*40+p.y*33);
        const g=Math.min(1,(0.35+night*0.85))*tw;
        const rad=Math.max(0.7,Math.min(1.9,r*(1.05+night*0.5)));
        // bright warm-white core
        ctx.fillStyle=rgbaStr(THEME.soft,g*(0.55+depth*0.4));
        ctx.beginPath(); ctx.arc(p.sx,p.sy,rad,0,6.283); ctx.fill();
        // soft amber bloom halo
        ctx.fillStyle=rgbaStr(THEME.accent2,g*0.18*(0.4+depth*0.6));
        ctx.beginPath(); ctx.arc(p.sx,p.sy,rad*2.1,0,6.283); ctx.fill();
      }else{
        // accent coral, day-lit brighter, night dimmer. Sunlit land shifts toward
        // the amber secondary so plates read a touch golden under "sunlight".
        const lightMul=0.42+0.85*day + 0.12;   // ~0.54 night .. ~1.39 full day
        const a=Math.max(0.03,Math.min(0.95,al*lightMul));
        const col=(p.land && day>0.25)?THEME.accent2:THEME.accent;
        ctx.fillStyle=rgbaStr(col,a);
        ctx.beginPath(); ctx.arc(p.sx,p.sy,r,0,6.283); ctx.fill();
      }
    }

    // continent plate outlines: stroke each border as a poly-line of projected
    // great-circle samples. Front edges (both endpoints near hemisphere) are
    // bright; edges wrapping to the back fade out so the sphere keeps its volume.
    if(OUTLINES){
      ctx.lineWidth=1.1; ctx.lineJoin="round"; ctx.lineCap="round";
      for(let bi=0;bi<BORDERS.length;bi++){
        const bd=BORDERS[bi];
        let prev=project(bd[0].x,bd[0].y,bd[0].z,cosY,sinY,cosX,sinX);
        for(let s=1;s<=bd.length;s++){
          const q=bd[s%bd.length];
          const cur=project(q.x,q.y,q.z,cosY,sinY,cosX,sinX);
          const front=(prev.z>=-0.15 && cur.z>=-0.15);
          const al=front?0.5:0.07;               // brighter than grid net when on the front
          ctx.strokeStyle=rgbaStr(THEME.accent,al);
          ctx.beginPath(); ctx.moveTo(prev.sx,prev.sy); ctx.lineTo(cur.sx,cur.sy); ctx.stroke();
          prev=cur;
        }
      }
    }

    raf=requestAnimationFrame(draw);
  }

  resize();
  window.addEventListener("resize",resize);
  if(!reduceMotion) canvas.addEventListener("mousemove",onMove);
  if(reduceMotion){ draw(); if(raf){cancelAnimationFrame(raf);raf=0;} } // one static frame
  else raf=requestAnimationFrame(draw);

  return {destroy(){
    if(raf) cancelAnimationFrame(raf); raf=0;
    window.removeEventListener("resize",resize);
    canvas.removeEventListener("mousemove",onMove);
  }};
}

/* ============================================================
   WELCOME HERO - layered 2.5D shopping scene
   ------------------------------------------------------------
   ASSET APPROACH: the cart and each product are SEPARATE inline-SVG
   layers, hand-authored with gradient shading, dimensional edges,
   highlights and their own contact shadows. Nothing is a single
   flattened picture that gets tilted, so every object is transformed
   independently. No external images, no 3D library, no emoji, no flat
   outline icons.

   MOTION
     entrance  products rise from the real basket mouth (measured from
               the cart element) and travel outward along soft arcs into
               the resting fan; ~1.15s plus a 72ms per-object stagger.
               Start is clickable from the first frame.
     idle      very subtle float with per-object timing; the cart stays
               essentially still.
     pointer   parallax weighted by depth, so foreground objects move
               more than background ones.
     drag      a small overall turn with inertia that springs back to the
               resting composition; clamped, so nothing flips or shows
               the flat side of a layer. Arrow keys do the same, Home /
               Escape recentres.
     reduced   prefers-reduced-motion renders the final composition in a
               single frame: no entrance, no float, no parallax, no
               inertia, no rAF loop, no drag affordance.
     hidden    the loop is cancelled while the tab is hidden and when the
               view is left (destroy()).
   ============================================================ */
function makeHero(root){
  const art=root.querySelector(".wp-art");
  const main=root.querySelector(".wp-main");
  const cartIn=root.querySelector(".wp-cart-in");
  const hint=root.querySelector(".wp-hint");
  const objs=Array.prototype.slice.call(root.querySelectorAll(".wp-obj"));
  if(!art||!objs.length) return {start(){},exit(){},destroy(){}};

  /* resting composition. d = desktop [x%, y%, px width, deg], m = mobile.
     depth 0 = far background, 1 = near foreground. tier 2 objects are the
     four outer ones and are dropped on small screens. */
  const SPEC={
    headphones:{depth:.92,tier:1,bow:-1,d:[22,30,96,-12],m:[15,20,60,-12]},
    sneaker:   {depth:.96,tier:1,bow: 1,d:[78,27,104,10],m:[85,18,64,10]},
    camera:    {depth:.62,tier:1,bow:-1,d:[12,52,78,-9], m:[10,42,50,-9]},
    handbag:   {depth:.66,tier:1,bow: 1,d:[88,52,84,9],  m:[90,43,52,9]},
    watch:     {depth:.46,tier:2,bow:-1,d:[33,13,66,-16],m:[24,10,44,-16]},
    skincare:  {depth:.50,tier:2,bow: 1,d:[67,12,62,14], m:[76,9,42,14]},
    speaker:   {depth:.30,tier:2,bow:-1,d:[5,26,58,-7],  m:[4,30,40,-7]},
    book:      {depth:.32,tier:2,bow: 1,d:[95,22,62,12], m:[96,26,42,12]}
  };
  const FALLBACK={depth:.5,tier:1,bow:1,d:[50,40,70,0],m:[50,40,50,0]};

  const items=objs.map((el,i)=>{
    const sp=SPEC[el.dataset.obj]||FALLBACK;
    return {el,sp,i,
      ph:i*1.73+0.4,                       // idle phase offset - varied timing
      fr:0.00040+0.00012*((i%3)+1),        // idle frequency
      ax:3+(i%3)*1.5, ay:5+(i%4)*1.7,      // idle amplitude (px)
      tx:0,ty:0,w:60,rotF:0,hidden:false};
  });

  const ENTER=1150, STAGGER=72, EXIT=300;
  const easeOut=x=>1-Math.pow(1-x,3);
  const clamp=(v,a,b)=>v<a?a:(v>b?b:v);

  let W=0,H=0,mobile=false,basket={x:0,y:0};
  let raf=0,running=false,t0=0,exiting=false,exitT0=0;
  let px=0,py=0,tpx=0,tpy=0;               // damped pointer parallax
  let turnX=0,turnY=0,vx=0,vy=0;           // drag turn + inertia
  let dragging=false,lastX=0,lastY=0,pid=null;

  function measure(){
    const r=art.getBoundingClientRect();
    if(!r.width||!r.height) return false;
    W=r.width; H=r.height;
    mobile=W<760;
    const k=clamp(W/1440,.7,1.14);
    // the emission point is read from the REAL cart element, so products always
    // leave from the basket mouth however the cart is sized or positioned
    const c=cartIn?cartIn.getBoundingClientRect():null;
    if(c&&c.width){ basket.x=c.left-r.left+c.width*0.53; basket.y=c.top-r.top+c.height*0.34; }
    else { basket.x=W/2; basket.y=H*0.42; }
    for(const it of items){
      const set=mobile?it.sp.m:it.sp.d;
      it.hidden=mobile&&it.sp.tier===2;
      it.el.style.display=it.hidden?"none":"";
      it.tx=W*set[0]/100; it.ty=H*set[1]/100;
      it.w=set[2]*(mobile?1:k);
      it.rotF=set[3];
      it.el.style.width=it.w.toFixed(1)+"px";
      // restrained depth of field: only the two farthest edge objects soften
      it.el.style.filter=it.sp.depth<.36?"blur(.7px)":"";
    }
    return true;
  }

  function frame(now){
    raf=0;
    const red=prefersReduced();
    if(!t0) t0=now;
    const el=red?(ENTER+items.length*STAGGER+1):(now-t0);

    if(red){ px=py=tpx=tpy=0; turnX=turnY=vx=vy=0; }
    else{
      px+=(tpx-px)*0.08; py+=(tpy-py)*0.08;
      if(!dragging){
        turnX+=vx; turnY+=vy;
        vx*=0.90; vy*=0.90;
        turnX*=0.90; turnY*=0.90;          // spring back to the resting pose
        if(Math.abs(vx)<0.02) vx=0;
        if(Math.abs(vy)<0.02) vy=0;
        if(Math.abs(turnX)<0.05) turnX=0;
        if(Math.abs(turnY)<0.05) turnY=0;
      }
    }

    const exitP=exiting?clamp((now-exitT0)/EXIT,0,1):0;
    const exitE=easeOut(exitP);

    for(const it of items){
      if(it.hidden) continue;
      const p=red?1:clamp((el-it.i*STAGGER)/ENTER,0,1);
      const e=easeOut(p);
      const dx=it.tx-basket.x, dy=it.ty-basket.y;
      let x=basket.x+dx*e, y=basket.y+dy*e;
      // bow the path outward so objects arc rather than sliding in a straight line
      const len=Math.hypot(dx,dy)||1;
      const bow=Math.sin(Math.PI*e)*(mobile?15:26)*it.sp.bow;
      x+=-dy/len*bow; y+=dx/len*bow*0.55;
      const dep=it.sp.depth;
      if(!red){
        x+=Math.sin(el*it.fr+it.ph)*it.ax;
        y+=Math.cos(el*it.fr*0.82+it.ph*1.3)*it.ay;
        x+=px*(0.30+dep*0.95)+turnX*(0.35+dep);
        y+=py*(0.22+dep*0.70)+turnY*(0.30+dep*0.80);
      }
      let sc=0.62+0.38*e, op=clamp(p*2.1,0,1), rot=it.rotF*e;
      if(exitP){                            // Start pressed: recede + fade out
        x+=(it.tx-W/2)*0.34*exitE; y-=18*exitE;
        sc*=1-0.14*exitE; op*=1-exitE;
      }
      it.el.style.transform="translate3d("+x.toFixed(1)+"px,"+y.toFixed(1)+"px,0)"+
        " translate(-50%,-50%) rotate("+rot.toFixed(2)+"deg) scale("+sc.toFixed(3)+")";
      it.el.style.opacity=op.toFixed(3);
    }

    if(cartIn){                             // the cart stays essentially still
      const cx=red?0:px*0.16+turnX*0.20, cy=red?0:py*0.12+turnY*0.16;
      const cs=1-0.03*exitE;
      cartIn.style.transform="translate3d("+cx.toFixed(1)+"px,"+cy.toFixed(1)+"px,0) scale("+cs.toFixed(3)+")";
      cartIn.style.opacity=(1-0.55*exitE).toFixed(3);
    }

    if(red){ if(exiting&&exitP<1) raf=requestAnimationFrame(frame); return; }
    if(!running||document.hidden) return;
    raf=requestAnimationFrame(frame);
  }

  function kick(){ if(running&&!raf&&!document.hidden) raf=requestAnimationFrame(frame); }

  /* ---- pointer parallax over the whole stage ---- */
  function onHover(e){
    if(prefersReduced()) return;
    const r=art.getBoundingClientRect(); if(!r.width) return;
    tpx=((e.clientX-r.left)/r.width-0.5)*-46;
    tpy=((e.clientY-r.top)/r.height-0.5)*-26;
    kick();
  }
  function onHoverOut(){ tpx=0; tpy=0; kick(); }

  /* ---- drag: a small clamped turn, then inertia back to rest ---- */
  function onDown(e){
    if(prefersReduced()) return;
    if(e.pointerType==="mouse"&&e.button!==0) return;
    dragging=true; pid=e.pointerId; lastX=e.clientX; lastY=e.clientY; vx=0; vy=0;
    art.classList.add("dragging");
    try{ art.setPointerCapture(pid); }catch(err){}
    kick();
  }
  function onDrag(e){
    if(!dragging) return;
    const dx=e.clientX-lastX, dy=e.clientY-lastY;
    lastX=e.clientX; lastY=e.clientY;
    turnX=clamp(turnX+dx*0.55,-56,56);
    turnY=clamp(turnY+dy*0.34,-34,34);
    vx=dx*0.30; vy=dy*0.18;
    kick();
  }
  function onUp(){
    if(!dragging) return;
    dragging=false; art.classList.remove("dragging");
    if(pid!==null){ try{ art.releasePointerCapture(pid); }catch(err){} pid=null; }
    kick();
  }
  function onKey(e){
    if(prefersReduced()) return;
    let kx=0,ky=0;
    if(e.key==="ArrowLeft") kx=-1;
    else if(e.key==="ArrowRight") kx=1;
    else if(e.key==="ArrowUp") ky=-1;
    else if(e.key==="ArrowDown") ky=1;
    else if(e.key==="Home"||e.key==="Escape"){ turnX=0;turnY=0;vx=0;vy=0; e.preventDefault(); kick(); return; }
    else return;
    e.preventDefault();
    turnX=clamp(turnX+kx*22,-56,56);
    turnY=clamp(turnY+ky*14,-34,34);
    vx=0; vy=0; kick();
  }

  function onResize(){ measure(); kick(); }
  function onVis(){ if(document.hidden){ if(raf){cancelAnimationFrame(raf);raf=0;} } else kick(); }

  window.addEventListener("resize",onResize);
  document.addEventListener("visibilitychange",onVis);
  if(main){ main.addEventListener("pointermove",onHover); main.addEventListener("pointerleave",onHoverOut); }
  art.addEventListener("pointerdown",onDown);
  art.addEventListener("pointermove",onDrag);
  art.addEventListener("pointerup",onUp);
  art.addEventListener("pointercancel",onUp);
  art.addEventListener("keydown",onKey);

  return {
    start(){
      running=true; exiting=false; t0=0;
      turnX=turnY=vx=vy=px=py=tpx=tpy=0;
      // no drag affordance when the interaction itself is switched off
      if(prefersReduced()){ art.removeAttribute("tabindex"); if(hint) hint.style.display="none"; }
      else{ art.setAttribute("tabindex","0"); if(hint) hint.style.display=""; }
      if(!measure()) requestAnimationFrame(()=>{ measure(); kick(); });
      kick();
    },
    exit(){ exiting=true; exitT0=performance.now(); kick(); },
    destroy(){
      running=false; if(raf){ cancelAnimationFrame(raf); raf=0; }
      window.removeEventListener("resize",onResize);
      document.removeEventListener("visibilitychange",onVis);
      if(main){ main.removeEventListener("pointermove",onHover); main.removeEventListener("pointerleave",onHoverOut); }
      art.removeEventListener("pointerdown",onDown);
      art.removeEventListener("pointermove",onDrag);
      art.removeEventListener("pointerup",onUp);
      art.removeEventListener("pointercancel",onUp);
      art.removeEventListener("keydown",onKey);
      art.classList.remove("dragging");
      dragging=false; pid=null;
    }
  };
}

/* ---- lifecycle wiring ---- */
let hero=null;
/* welcome-page hero (front of house). Rebuilt on entry so the entrance plays
   again, and fully destroyed on exit so no rAF loop survives the view. */
function startHero(){
  const root=$("#welcomeScreen"); if(!root) return;
  root.classList.remove("wp-leaving");
  if(!hero) hero=makeHero(root);
  hero.start();
}
function stopHero(){ if(hero){ hero.destroy(); hero=null; } }
function heroExit(){ if(hero) hero.exit(); }

/* boot: an existing session goes straight into the app (unchanged behaviour);
   otherwise the welcome page is the front door, and #/auth is honoured as a
   direct sign-in link */
if(token&&username){ enterApp(); }
else{
  setMode("login");
  if(location.hash==="#/auth"){ pushedAuth=true; setView("auth"); uInput.focus(); }
  else setView("welcome");
}

