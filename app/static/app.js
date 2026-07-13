const SECTORS = window.JMK_SECTORS;
const STATUSES = window.JMK_STATUSES;

const SOURCES = [
  {name:"GHANEPS", org:"Ghana Electronic Procurement System", url:"https://www.ghaneps.gov.gh/", note:"The mandatory e-procurement platform for Ghanaian public entities.", type:"Tenders"},
  {name:"PPA Tender Portal", org:"Public Procurement Authority (Ghana)", url:"https://tenders.ppa.gov.gh/tenders", note:"Government tender notices across ministries, departments and assemblies.", type:"Tenders"},
  {name:"UNGM", org:"UN Global Marketplace", url:"https://www.ungm.org/Public/Notice", note:"UN agency tenders covering Ghana.", type:"Tenders"},
  {name:"ReliefWeb", org:"UN OCHA", url:"https://reliefweb.int/jobs", note:"Humanitarian and development consultancy calls.", type:"Tenders"},
  {name:"Devex", org:"Devex", url:"https://www.devex.com/jobs", note:"Global development-sector RFPs and consulting opportunities.", type:"Tenders"},
  {name:"DevelopmentAid", org:"DevelopmentAid", url:"https://www.developmentaid.org/tenders/search", note:"Aggregated tenders from major donors.", type:"Tenders"},
  {name:"World Bank Procurement", org:"World Bank Group", url:"https://projects.worldbank.org/en/projects-operations/procurement", note:"Bank-financed project tenders, including Ghana operations.", type:"Tenders"},
  {name:"AfDB Procurement", org:"African Development Bank", url:"https://www.afdb.org/en/projects-and-operations/procurement", note:"Bank-financed operations across Africa, including Ghana.", type:"Tenders"},
  {name:"TED", org:"EU Tenders Electronic Daily", url:"https://ted.europa.eu/", note:"EU-funded external action tenders — search 'Ghana'.", type:"Tenders"},
  {name:"Jobsinghana.com — NGO/IGO/INGO", org:"Jobsinghana.com", url:"https://www.jobsinghana.com/jobs/indexnew.php?device=d&indu=130", note:"Consistently useful for donor-funded consultancy calls and TORs.", type:"Jobs — Ghana"},
  {name:"Ghana Current Jobs — NGO/International Agencies", org:"Ghana Current Jobs", url:"https://www.ghanacurrentjobs.com/category/ngo-international-agencies/", note:"NGO and international-agency roles, including M&E and advisory positions.", type:"Jobs — Ghana"},
  {name:"NGO Jobs in Africa — Ghana", org:"NGO Jobs in Africa", url:"https://ngojobsinafrica.com/job-location/ghana/", note:"Ghana-filtered listings from Africa's largest NGO-focused job site.", type:"Jobs — Ghana"},
  {name:"Jobberman Ghana — Consulting & Strategy", org:"Jobberman", url:"https://www.jobberman.com.gh/jobs/consulting-strategy", note:"Ghana's largest general job board, filtered to Consulting & Strategy.", type:"Jobs — Ghana"},
  {name:"Jobberman Ghana — Research, Teaching & Training", org:"Jobberman", url:"https://www.jobberman.com.gh/jobs/research-teaching-training", note:"Same board, filtered to Research, Teaching & Training roles.", type:"Jobs — Ghana"},
  {name:"JobWeb Ghana", org:"JobWeb Ghana", url:"https://jobwebghana.com/jobs/", note:"General Ghana job board — worth filtering for research/consultancy roles.", type:"Jobs — Ghana"},
  {name:"BusinessGhana Jobs", org:"BusinessGhana", url:"https://www.businessghana.com/site/jobs", note:"General board with an on-site NGO/IGO/INGO filter.", type:"Jobs — Ghana"},
  {name:"Ghanajob.com", org:"Ghanajob.com", url:"https://www.ghanajob.com/", note:"General Ghana recruitment site, checked for research/consultancy-shaped roles.", type:"Jobs — Ghana"}
];

let editingId = null;
let pipelineItems = [];
let quickFilter = 'all';

function escapeHtml(s){
  return (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function populateSelect(el, options, includeAll){
  el.innerHTML = (includeAll ? '<option value="">All</option>' : '') +
    options.map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join('');
}
function daysLeft(deadline){
  if(!deadline) return null;
  return Math.ceil((new Date(deadline+'T23:59:59') - new Date()) / 86400000);
}
function deadlineChip(deadline){
  if(!deadline) return '';
  const dl = daysLeft(deadline);
  const label = new Date(deadline+'T00:00:00').toLocaleDateString('en-GB',{day:'2-digit',month:'short'});
  let cls = 'safe';
  if(dl !== null && dl <= 7) cls = 'urgent';
  return `<span class="chip ${cls}">${label} · ${dl}d</span>`;
}
function starRating(score){
  const stars = Math.round((score||0) / 20);
  return '★'.repeat(stars) + '☆'.repeat(5 - stars);
}
const AVATAR_COLORS = ['#283088','#F06020','#2E6B4F','#6B4FA0','#B0472E','#1D6E8F'];
function avatarColor(name){
  let hash = 0;
  for(let i=0;i<(name||'').length;i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}
function initials(name){
  if(!name) return '—';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]||'')[0] + (parts[1] ? parts[1][0] : (parts[0]||'')[1] || '')).toUpperCase();
}

// ---------- theme ----------
const THEME_ORDER = ['light', 'dark', 'signature'];
const SUN_ICON = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON_ICON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
const SIGNATURE_ICON = '<path d="M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4L12 2z"/>';
const THEME_ICONS = { light: MOON_ICON, dark: SIGNATURE_ICON, signature: SUN_ICON };
const THEME_LABELS = { light: 'Switch to dark mode', dark: 'Switch to JMK Signature theme', signature: 'Switch to light mode' };

function applyTheme(theme){
  if(!THEME_ORDER.includes(theme)) theme = 'light';
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('themeIcon');
  const btn = document.getElementById('themeToggle');
  if(icon) icon.innerHTML = THEME_ICONS[theme];
  if(btn) btn.title = THEME_LABELS[theme];
}
function toggleTheme(){
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  const next = THEME_ORDER[(THEME_ORDER.indexOf(cur) + 1) % THEME_ORDER.length];
  applyTheme(next);
  localStorage.setItem('jmk-theme', next);
}

// ---------- navigation ----------
const SECTION_META = {
  dashboard: ["Dashboard", "AI-powered consultancy opportunity intelligence"],
  opportunities: ["Opportunities", "Everything the daily crawl has found, scored against JMK's sectors"],
  pipeline: ["Pipeline", "Opportunities you're actively tracking, from intake to award"],
  assistant: ["AI Assistant", "Ask questions about the current opportunity list"],
  sources: ["Source Watchlist", "Where the daily crawl looks — Ghana platforms first"],
  settings: ["Settings", "Crawl controls and platform info"],
};
function switchSection(section){
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.section === section));
  document.querySelectorAll('.section').forEach(s => s.classList.toggle('active', s.id === 'section-' + section));
  const meta = SECTION_META[section];
  if(meta){
    document.getElementById('sectionTitle').textContent = meta[0];
    document.getElementById('sectionSubtitle').textContent = meta[1];
  }
  if(section === 'opportunities') loadAllOpportunities();
  if(section === 'pipeline') loadPipeline();
  if(section === 'settings') loadCrawlStatus('crawlStatusBox');
  if(section === 'sources') renderSources();
}

// ---------- dashboard ----------
let sectorChartInstance = null;
let dashboardOpportunities = [];

function greet(){
  const hour = new Date().getHours();
  const word = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  document.getElementById('greetingText').textContent = word + '!';
  document.getElementById('todayDate').textContent = new Date().toLocaleDateString('en-GB', {weekday:'long', day:'2-digit', month:'long', year:'numeric'});
}

async function loadDashboard(){
  greet();
  let stats = {};
  try{
    stats = await fetch('/api/opportunities/stats').then(r => r.json());
  }catch(e){ console.error(e); }

  document.getElementById('kpiGrid').innerHTML = `
    <div class="kpi-card clickable" data-quick="all"><div class="num">${stats.totalOpportunities ?? 0}</div><div class="lbl">Opportunities found</div></div>
    <div class="kpi-card orange clickable" data-quick="highPriority"><div class="num">${stats.highPriority ?? 0}</div><div class="lbl">High priority</div></div>
    <div class="kpi-card orange clickable" data-quick="closing48h"><div class="num">${stats.closingIn48h ?? 0}</div><div class="lbl">Closing in 48h</div></div>
    <div class="kpi-card clickable" data-quick="hasDonor"><div class="num">${stats.activeDonors ?? 0}</div><div class="lbl">Active donors</div></div>
    <div class="kpi-card clickable" data-quick="all"><div class="num">${stats.averageMatch ?? 0}%</div><div class="lbl">Avg. match score</div></div>
  `;
  document.querySelectorAll('#kpiGrid .kpi-card').forEach(card => {
    card.addEventListener('click', () => {
      quickFilter = card.dataset.quick;
      switchSection('opportunities');
    });
  });

  const totalSources = 9 + 8; // tender portals + Ghana job platforms (always checked)
  document.getElementById('scanSummary').textContent =
    `Scanned ${totalSources} sources and found ${stats.totalOpportunities ?? 0} opportunities matching JMK's scope.`;

  try{ buildInsights(stats); }catch(e){ console.error('insights failed', e); }
  try{ buildSectorChart(stats.sectorBreakdown || {}); }catch(e){ console.error('sector chart failed', e); }
  try{ buildTopDonors(stats.topDonors || []); }catch(e){ console.error('top donors failed', e); }
  try{ await loadCrawlStatus('scanStatusMini'); }catch(e){ console.error('scan status failed', e); }

  try{
    dashboardOpportunities = await fetch('/api/opportunities').then(r => r.json());
  }catch(e){ dashboardOpportunities = []; }
  renderDashboardOpportunities();
}

function buildInsights(stats){
  const bits = [];
  if((stats.totalOpportunities ?? 0) > 0){
    bits.push(`Scanned all watchlist sources and identified <strong>${stats.totalOpportunities}</strong> opportunities.`);
    if(stats.highPriority) bits.push(`<strong>${stats.highPriority}</strong> are high priority (80%+ match).`);
    if(stats.closingIn48h) bits.push(`<strong>${stats.closingIn48h}</strong> close within 48 hours — worth checking today.`);
    const topSector = Object.entries(stats.sectorBreakdown || {}).sort((a,b) => b[1]-a[1])[0];
    if(topSector) bits.push(`<strong>${escapeHtml(topSector[0])}</strong> is the most active sector right now.`);
    const topDonorNames = (stats.topDonors || []).slice(0,3).map(d => escapeHtml(d.name));
    if(topDonorNames.length) bits.push(`Recent postings from <strong>${topDonorNames.join(', ')}</strong>.`);
  } else {
    bits.push('No opportunities yet — run a crawl to populate this dashboard.');
  }
  document.getElementById('insightsText').innerHTML = bits.join(' ');
}

function buildSectorChart(breakdown){
  const labels = Object.keys(breakdown);
  const data = Object.values(breakdown);
  const colors = ['#283088','#F06020','#2E6B4F','#6B4FA0','#B0472E','#1D6E8F','#9B9FC0','#C23B23'];
  const ctx = document.getElementById('sectorChart');
  if(typeof Chart === 'undefined'){
    document.getElementById('sectorLegend').innerHTML = labels.length
      ? labels.map((l,i) => `<div class="legend-row"><span>${escapeHtml(l)}</span><span class="amt">${data[i]}</span></div>`).join('')
      : '<div class="empty" style="padding:10px;">No sector data yet.</div>';
    return;
  }
  if(sectorChartInstance) sectorChartInstance.destroy();
  if(labels.length === 0){
    document.getElementById('sectorLegend').innerHTML = '<div class="empty" style="padding:10px;">No sector data yet.</div>';
    return;
  }
  sectorChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
    options: { plugins: { legend: { display: false }, tooltip: { enabled: true } }, cutout: '68%' }
  });
  const total = data.reduce((a,b) => a+b, 0);
  document.getElementById('sectorLegend').innerHTML = labels.map((l, i) => `
    <div class="legend-row">
      <span class="legend-dot" style="background:${colors[i % colors.length]}"></span>
      <span>${escapeHtml(l)}</span>
      <span class="amt">${data[i]} (${Math.round(data[i]/total*100)}%)</span>
    </div>`).join('');
}

function buildTopDonors(donors){
  const container = document.getElementById('topDonors');
  if(!donors.length){
    container.innerHTML = '<div class="empty" style="padding:10px;">No donor data yet.</div>';
    return;
  }
  const max = Math.max(...donors.map(d => d.count));
  container.innerHTML = donors.map(d => `
    <div class="donor-row">
      <div class="donor-avatar" style="background:${avatarColor(d.name)}">${initials(d.name)}</div>
      <div class="donor-info">
        <div class="donor-name">${escapeHtml(d.name)}</div>
        <div class="donor-bar-track"><div class="donor-bar-fill" style="width:${(d.count/max*100)}%"></div></div>
      </div>
      <div class="donor-count">${d.count}</div>
    </div>`).join('');
}

function renderDashboardOpportunities(){
  const search = (document.getElementById('dashSearch').value || '').toLowerCase();
  const sort = document.getElementById('dashSort').value;
  let list = dashboardOpportunities.slice();
  if(search){
    list = list.filter(o => (o.title||'').toLowerCase().includes(search) || (o.org||'').toLowerCase().includes(search) || (o.sector||'').toLowerCase().includes(search));
  }
  if(sort === 'deadline'){
    list.sort((a,b) => (a.deadline||'9999-99-99').localeCompare(b.deadline||'9999-99-99'));
  } else {
    list.sort((a,b) => b.match_score - a.match_score);
  }
  const top = list.slice(0, 6);
  document.getElementById('topOpportunities').innerHTML = top.length
    ? top.map(renderOppCard).join('')
    : '<div class="empty">No opportunities yet — run a crawl from Settings, or the Scan Status panel, to populate this.</div>';
  wireOppCardButtons(document.getElementById('topOpportunities'));
}

function matchTier(score){
  if(score >= 90) return {label:'Excellent', cls:'excellent'};
  if(score >= 80) return {label:'Strong', cls:'strong'};
  if(score >= 60) return {label:'Moderate', cls:'moderate'};
  return {label:'Low', cls:'low'};
}

function renderOppCard(o){
  const orgLine = o.org || (o.kind === 'job' ? 'Employer not specified' : 'Funder not specified');
  const tier = matchTier(o.match_score);
  return `
    <div class="opp-card">
      <div class="opp-card-head">
        <div class="opp-avatar" style="background:${avatarColor(orgLine)}">${initials(orgLine)}</div>
        <div class="opp-top" style="flex:1;">
          <div>
            <p class="opp-title">${escapeHtml(o.title)}</p>
            <div class="opp-org">${escapeHtml(orgLine)}${o.location ? ' · ' + escapeHtml(o.location) : ''}</div>
          </div>
          <div class="match-badge">
            <span class="pct ${tier.cls}">${o.match_score}%</span>
            <span class="tier-label ${tier.cls}">${tier.label}</span>
          </div>
        </div>
      </div>
      <div class="match-bar-track"><div class="match-bar-fill ${tier.cls}" style="width:${o.match_score}%"></div></div>
      <div class="opp-meta">
        <span class="chip sector">${escapeHtml(o.sector || 'Unsectored')}</span>
        ${o.source_tier ? `<span class="chip ${o.source_tier === 'International' ? 'intl' : 'ghana'}">${escapeHtml(o.source_tier)}</span>` : ''}
        ${deadlineChip(o.deadline)}
      </div>
      ${o.match_reason ? `<div class="opp-reason"><strong>Why this matches JMK:</strong> ${escapeHtml(o.match_reason)}</div>` : ''}
      <div class="opp-actions">
        <button class="btn secondary small" data-track="${o.id}">+ Track in Pipeline</button>
        ${o.source_url ? `<a href="${escapeHtml(o.source_url)}" target="_blank" rel="noopener">View source ↗</a>` : ''}
      </div>
    </div>`;
}

function wireOppCardButtons(container){
  container.querySelectorAll('[data-track]').forEach(btn => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Added ✓';
      await fetch(`/api/board/from-opportunity/${btn.dataset.track}`, { method: 'POST' });
    });
  });
}

// ---------- opportunities (full list) ----------
const QUICK_FILTER_LABELS = {
  all: null,
  highPriority: 'High priority (80%+ match)',
  closing48h: 'Closing within 48 hours',
  hasDonor: 'Has an identified donor/employer',
};

function renderQuickFilterChip(){
  const el = document.getElementById('quickFilterChip');
  const label = QUICK_FILTER_LABELS[quickFilter];
  if(!label){ el.innerHTML = ''; return; }
  el.innerHTML = `<div class="quick-filter-chip">Filtered: ${escapeHtml(label)} <button type="button" id="clearQuickFilter">✕</button></div>`;
  document.getElementById('clearQuickFilter').addEventListener('click', () => {
    quickFilter = 'all';
    loadAllOpportunities();
  });
}

async function loadAllOpportunities(){
  const kind = document.getElementById('filterKind').value;
  const sector = document.getElementById('filterSector').value;
  const params = new URLSearchParams();
  if(kind) params.set('kind', kind);
  let items = await fetch('/api/opportunities?' + params.toString()).then(r => r.json());
  if(sector) items = items.filter(o => o.sector === sector);
  if(quickFilter === 'highPriority') items = items.filter(o => o.match_score >= 80);
  if(quickFilter === 'closing48h') items = items.filter(o => {
    if(!o.deadline) return false;
    const dl = daysLeft(o.deadline);
    return dl !== null && dl >= 0 && dl <= 2;
  });
  if(quickFilter === 'hasDonor') items = items.filter(o => !!o.org);
  renderQuickFilterChip();
  const container = document.getElementById('allOpportunities');
  container.innerHTML = items.length
    ? items.map(renderOppCard).join('')
    : '<div class="empty">No opportunities match these filters yet.</div>';
  wireOppCardButtons(container);
}

// ---------- pipeline ----------
async function loadPipeline(){
  pipelineItems = await fetch('/api/board').then(r => r.json());
  renderPipeline();
}
function renderPipeline(){
  const statusFilter = document.getElementById('pipelineFilterStatus').value;
  let list = pipelineItems.slice();
  if(statusFilter) list = list.filter(i => i.status === statusFilter);
  const container = document.getElementById('pipelineList');
  if(list.length === 0){
    container.innerHTML = '<div class="empty">Nothing in the pipeline yet. Track an opportunity or add one manually.</div>';
    return;
  }
  container.innerHTML = list.map(item => `
    <div class="pipe-item" data-id="${item.id}">
      <div class="pipe-top">
        <div>
          <p class="pipe-title">${escapeHtml(item.title)}</p>
          <div class="pipe-sub">${escapeHtml(item.funder || 'Funder not specified')}${item.sector ? ' · ' + escapeHtml(item.sector) : ''}</div>
        </div>
        ${deadlineChip(item.deadline)}
      </div>
      ${item.notes ? `<div class="opp-reason" style="margin-top:6px;">${escapeHtml(item.notes)}</div>` : ''}
      <div class="pipe-actions">
        <select class="status-select" data-id="${item.id}">
          ${STATUSES.map(s => `<option value="${s}" ${s===item.status?'selected':''}>${s}</option>`).join('')}
        </select>
        <button class="btn secondary small" data-edit="${item.id}">Edit</button>
      </div>
    </div>
  `).join('');
  container.querySelectorAll('.status-select').forEach(sel => {
    sel.addEventListener('change', async e => {
      await fetch(`/api/board/${e.target.dataset.id}`, {
        method: 'PUT', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({status: e.target.value})
      });
      await loadPipeline();
    });
  });
  container.querySelectorAll('[data-edit]').forEach(btn => {
    btn.addEventListener('click', () => openForm(btn.dataset.edit));
  });
}

function openForm(id){
  editingId = id || null;
  const item = id ? pipelineItems.find(i => i.id === id) : null;
  document.getElementById('formTitle').textContent = item ? 'Edit Pipeline Item' : 'Add to Pipeline';
  document.getElementById('f_title').value = item?.title || '';
  document.getElementById('f_funder').value = item?.funder || '';
  document.getElementById('f_sector').value = item?.sector || SECTORS[0];
  document.getElementById('f_status').value = item?.status || 'New';
  document.getElementById('f_deadline').value = item?.deadline || '';
  document.getElementById('f_value').value = item?.value || '';
  document.getElementById('f_ref').value = item?.ref || '';
  document.getElementById('f_link').value = item?.link || '';
  document.getElementById('f_notes').value = item?.notes || '';
  document.getElementById('deleteBtn').style.display = item ? 'inline-block' : 'none';
  document.getElementById('formPanel').classList.add('open');
  document.getElementById('formOverlay').classList.add('open');
}
function closeFormPanel(){
  document.getElementById('formPanel').classList.remove('open');
  document.getElementById('formOverlay').classList.remove('open');
  editingId = null;
}
async function handleFormSubmit(e){
  e.preventDefault();
  const data = {
    title: document.getElementById('f_title').value.trim(),
    funder: document.getElementById('f_funder').value.trim(),
    sector: document.getElementById('f_sector').value,
    status: document.getElementById('f_status').value,
    deadline: document.getElementById('f_deadline').value,
    value: document.getElementById('f_value').value.trim(),
    ref: document.getElementById('f_ref').value.trim(),
    link: document.getElementById('f_link').value.trim(),
    notes: document.getElementById('f_notes').value.trim(),
  };
  if(editingId){
    await fetch(`/api/board/${editingId}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
  } else {
    await fetch('/api/board', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
  }
  closeFormPanel();
  await loadPipeline();
}
async function handleDelete(){
  if(!editingId) return;
  await fetch(`/api/board/${editingId}`, { method: 'DELETE' });
  closeFormPanel();
  await loadPipeline();
}

// ---------- AI assistant ----------
const SUGGESTED_QUESTIONS = [
  "Which tenders close this week?",
  "Show me jobs closing this month",
  "WASH opportunities",
  "Education opportunities",
  "Governance opportunities",
  "Gender and social inclusion opportunities",
  "Agricultural sector tenders",
  "Show me the best matches",
];
function renderSuggestionChips(){
  const el = document.getElementById('suggestionChips');
  if(!el) return;
  el.innerHTML = SUGGESTED_QUESTIONS.map(q => `<button class="suggestion-chip" type="button">${escapeHtml(q)}</button>`).join('');
  el.querySelectorAll('.suggestion-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('assistantInput').value = btn.textContent;
      askAssistant();
    });
  });
}
function addChatMsg(text, cls){
  const chat = document.getElementById('assistantChat');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + cls;
  div.innerHTML = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}
async function askAssistant(){
  const input = document.getElementById('assistantInput');
  const question = input.value.trim();
  if(!question) return;
  addChatMsg(escapeHtml(question), 'user');
  input.value = '';
  try{
    const res = await fetch('/api/assistant/ask', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({question})
    });
    const data = await res.json();
    let html = `<div>${escapeHtml(data.explanation)} Found <strong>${data.count}</strong> match(es).</div>`;
    if(data.results.length){
      html += '<div class="opp-grid" style="margin-top:10px;">' + data.results.slice(0,6).map(o => renderOppCard({
        id:o.id, kind:o.kind, title:o.title, org:o.org, sector:o.sector, deadline:o.deadline,
        match_score:o.matchScore, match_reason:o.matchReason, source:o.source, source_url:o.sourceUrl,
        source_tier:o.sourceTier, location: ''
      })).join('') + '</div>';
    }
    addChatMsg(html, 'bot');
    wireOppCardButtons(document.getElementById('assistantChat'));
  }catch(e){
    addChatMsg('Something went wrong answering that — try again.', 'bot');
  }
}

// ---------- sources ----------
function timeAgo(iso){
  if(!iso) return 'Not yet scanned';
  const diffMin = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if(diffMin < 1) return 'Just now';
  if(diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if(diffHr < 24) return `${diffHr}h ago`;
  return `${Math.round(diffHr / 24)}d ago`;
}

async function renderSources(){
  let sourceStats = {};
  try{
    const s = await fetch('/api/crawl/status').then(r => r.json());
    sourceStats = JSON.parse(s.source_stats || '{}');
  }catch(e){ /* first load, or no crawl yet — show as not-yet-scanned */ }

  const groups = {};
  SOURCES.forEach(s => { groups[s.type] = groups[s.type] || []; groups[s.type].push(s); });
  document.getElementById('sourceList').innerHTML = Object.keys(groups).map(type => `
    <div class="source-group">
      <div class="source-group-label">${escapeHtml(type)}</div>
      ${groups[type].map(s => {
        const stat = sourceStats[s.name];
        const ok = stat ? stat.status === 'ok' : null;
        const dot = ok === null ? '⚪' : (ok ? '🟢' : '🔴');
        const statusText = ok === null ? 'Not yet scanned' : (ok ? timeAgo(stat.last_checked) : 'Unreachable last run');
        const newToday = stat ? stat.new_today : null;
        return `
        <div class="source">
          <div class="source-row">
            <a href="${s.url}" target="_blank" rel="noopener">${escapeHtml(s.name)}</a><span class="org">— ${escapeHtml(s.org)}</span>
          </div>
          <div class="source-status">
            <span>${dot} ${escapeHtml(statusText)}</span>
            ${newToday !== null ? `<span class="new-today">${newToday} new last scan</span>` : ''}
          </div>
          <div class="note">${escapeHtml(s.note)}</div>
        </div>`;
      }).join('')}
    </div>`).join('');
}

// ---------- settings ----------
function renderCrawlStatusBox(targetId, s){
  const el = document.getElementById(targetId);
  if(!el) return;
  const working = s.state === 'running';
  el.innerHTML = `
    ${working ? '<div class="agent-working">🔄 Agent is working — checking 17 sources, this can take 1-2 minutes...</div>' : ''}
    <div class="row"><span>State</span><span>${escapeHtml(s.state)}</span></div>
    <div class="row"><span>Tenders in feed</span><span>${s.tenders_in_feed}</span></div>
    <div class="row"><span>Jobs in feed</span><span>${s.jobs_in_feed}</span></div>
    <div class="row"><span>New items last run</span><span>${s.new_items_last_run}</span></div>
    <div class="row"><span>Email sent last run</span><span>${s.email_sent ? 'Yes' : 'No'}</span></div>
    ${s.email_note ? `<div class="row"><span>Email note</span><span>${escapeHtml(s.email_note)}</span></div>` : ''}
    ${s.error ? `<div class="row"><span>Last error</span><span>${escapeHtml(s.error)}</span></div>` : ''}
  `;
}

async function loadCrawlStatus(targetId){
  targetId = targetId || 'crawlStatusBox';
  const s = await fetch('/api/crawl/status').then(r => r.json());
  renderCrawlStatusBox(targetId, s);
  return s;
}

async function triggerCrawl(btnId, statusTargetId){
  const btn = document.getElementById(btnId);
  btn.disabled = true;
  btn.textContent = '🔄 Agent is working...';
  const token = window.JMK_CRON_SECRET ? `?token=${encodeURIComponent(window.JMK_CRON_SECRET)}` : '';
  const res = await fetch('/api/crawl/run' + token, { method: 'POST' }).then(r => r.json());

  if(res.status !== 'started' && res.status !== 'already running'){
    btn.disabled = false;
    btn.textContent = 'Run Crawl Now';
    alert('Could not start the crawl: ' + (res.error || JSON.stringify(res)));
    return;
  }

  pollUntilDone(btnId, statusTargetId);
}

async function pollUntilDone(btnId, statusTargetId){
  const btn = document.getElementById(btnId);
  const s = await loadCrawlStatus(statusTargetId);
  if(s.state === 'running'){
    btn.disabled = true;
    btn.textContent = '🔄 Agent is working...';
    setTimeout(() => pollUntilDone(btnId, statusTargetId), 3000);
  } else {
    btn.disabled = false;
    btn.textContent = s.error ? 'Run Crawl Now (last run had an error)' : 'Run Crawl Now';
    const dashSection = document.getElementById('section-dashboard');
    if(dashSection && dashSection.classList.contains('active')) loadDashboard();
  }
}

async function clearAndRescan(){
  const btn = document.getElementById('clearRescanBtn');
  if(!confirm('This deletes all currently crawled opportunities (not your Pipeline items) and starts a fresh scan. Continue?')) return;
  btn.disabled = true;
  btn.textContent = 'Clearing...';
  const token = window.JMK_CRON_SECRET ? `?token=${encodeURIComponent(window.JMK_CRON_SECRET)}` : '';
  await fetch('/api/opportunities' + token, { method: 'DELETE' });
  btn.textContent = 'Clear Old Data & Rescan';
  btn.disabled = false;
  triggerCrawl('triggerCrawlBtn', 'crawlStatusBox');
}

// ---------- init ----------
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(localStorage.getItem('jmk-theme') || 'light');
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);

  const sidebarEl = document.querySelector('.sidebar');
  const overlayEl = document.getElementById('sidebarOverlay');
  function openMobileMenu(){ sidebarEl.classList.add('open'); overlayEl.classList.add('open'); }
  function closeMobileMenu(){ sidebarEl.classList.remove('open'); overlayEl.classList.remove('open'); }
  document.getElementById('mobileMenuBtn').addEventListener('click', openMobileMenu);
  overlayEl.addEventListener('click', closeMobileMenu);

  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      if(btn.dataset.section === 'opportunities') quickFilter = 'all';
      switchSection(btn.dataset.section);
      closeMobileMenu();
    });
  });

  populateSelect(document.getElementById('filterSector'), SECTORS, true);
  populateSelect(document.getElementById('f_sector'), SECTORS, false);
  populateSelect(document.getElementById('f_status'), STATUSES, false);
  populateSelect(document.getElementById('pipelineFilterStatus'), STATUSES, true);

  document.getElementById('filterKind').addEventListener('change', loadAllOpportunities);
  document.getElementById('filterSector').addEventListener('change', loadAllOpportunities);
  document.getElementById('refreshOppBtn').addEventListener('click', loadAllOpportunities);
  document.getElementById('pipelineFilterStatus').addEventListener('change', renderPipeline);

  document.getElementById('addPipelineBtn').addEventListener('click', () => openForm(null));
  document.getElementById('closeForm').addEventListener('click', closeFormPanel);
  document.getElementById('cancelForm').addEventListener('click', closeFormPanel);
  document.getElementById('formOverlay').addEventListener('click', closeFormPanel);
  document.getElementById('pipelineForm').addEventListener('submit', handleFormSubmit);
  document.getElementById('deleteBtn').addEventListener('click', handleDelete);

  document.getElementById('assistantSendBtn').addEventListener('click', askAssistant);
  document.getElementById('assistantInput').addEventListener('keydown', e => { if(e.key === 'Enter') askAssistant(); });

  document.getElementById('triggerCrawlBtn').addEventListener('click', () => triggerCrawl('triggerCrawlBtn', 'crawlStatusBox'));
  document.getElementById('clearRescanBtn').addEventListener('click', clearAndRescan);
  document.getElementById('runScanTopBtn').addEventListener('click', () => triggerCrawl('runScanTopBtn', 'scanStatusMini'));
  document.getElementById('dashSearch').addEventListener('input', renderDashboardOpportunities);
  document.getElementById('dashSort').addEventListener('change', renderDashboardOpportunities);
  document.getElementById('viewAllBtn').addEventListener('click', () => switchSection('opportunities'));

  renderSources();
  renderSuggestionChips();
  loadDashboard();
});
