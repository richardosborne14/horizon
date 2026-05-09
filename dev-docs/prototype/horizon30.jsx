import { useState, useMemo, useCallback } from "react";

// ═══════════════════════════════════════════════════════════════════════════
// HORIZON 30 v2 — Life-Entity Wealth Engine for French Freelancers
// ═══════════════════════════════════════════════════════════════════════════

const fmt = (n) => new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);
const fmtK = (n) => n >= 1e6 ? `${(n/1e6).toFixed(1)}M€` : n >= 1000 ? `${Math.round(n/1000)}k€` : fmt(n);
const fmtPct = (n) => `${(n*100).toFixed(1)}%`;
const YR = 2026;

// ── AE cotisation schedules with projected increases ───────────────────────
const AE_SCHEDULES = {
  bnc_non_reglementee: [{y:2026,r:.262},{y:2027,r:.268},{y:2028,r:.275},{y:2030,r:.285},{y:2035,r:.295}],
  bic_services: [{y:2026,r:.237},{y:2028,r:.245},{y:2030,r:.255},{y:2035,r:.265}],
  bic_vente: [{y:2026,r:.148},{y:2028,r:.155},{y:2030,r:.162}],
  bnc_cipav: [{y:2026,r:.254},{y:2028,r:.262},{y:2030,r:.272}],
};
function getRate(type, year) {
  const s = AE_SCHEDULES[type] || AE_SCHEDULES.bnc_non_reglementee;
  let r = s[0].r; for (const x of s) { if (year >= x.y) r = x.r; } return r;
}

function cafEstimate(kids20, monthlyInc, year) {
  if (kids20 < 2) return 0;
  const base = kids20 === 2 ? 148 : kids20 === 3 ? 338 : 338 + (kids20 - 3) * 190;
  const f = monthlyInc * 12 > 70000 + kids20 * 5000 ? 0.5 : 1;
  return base * f * Math.pow(1.015, year - YR);
}

const VEHICLES = {
  livret_a:  { label: "Livret A",            rate:.025, taxFree:true,  ceil:22950,  color:"#22d3ee" },
  ldds:      { label: "LDDS",                rate:.025, taxFree:true,  ceil:12000,  color:"#06b6d4" },
  av_euro:   { label: "Assurance Vie (€)",    rate:.027, taxRate:.172,  ceil:null,   color:"#a78bfa" },
  av_uc:     { label: "Assurance Vie (UC)",   rate:.06,  taxRate:.172,  ceil:null,   color:"#8b5cf6" },
  pea:       { label: "PEA",                  rate:.07,  taxRate:.172,  ceil:150000, color:"#f59e0b" },
  scpi:      { label: "SCPI",                 rate:.045, taxRate:.30,   ceil:null,   color:"#10b981" },
  per:       { label: "PER (retraite)",       rate:.04,  taxRate:.172,  ceil:null,   color:"#ec4899" },
};

const SCALES = {
  optimistic:  { label:"Optimiste",  infl:.018, cost:.02,  emoji:"☀️", color:"#10b981" },
  moderate:    { label:"Modéré",     infl:.025, cost:.03,  emoji:"⛅",  color:"#f59e0b" },
  pessimistic: { label:"Pessimiste", infl:.035, cost:.045, emoji:"🌧️", color:"#ef4444" },
};

const GROWTH = {
  conservative: { label:"Prudent",      rate:.01, desc:"Stabilité. Vous gardez vos clients, pas de gros changements." },
  moderate:     { label:"Modéré",       rate:.03, desc:"Croissance naturelle : bouche à oreille, légère hausse des tarifs." },
  ambitious:    { label:"Ambitieux",    rate:.06, desc:"Nouveaux services, prospection active, montée en gamme." },
  custom:       { label:"Personnalisé", rate:null,desc:"Vous définissez votre propre taux." },
};

const SECTIONS = [
  { id:"identity", label:"Identité",  icon:"◉" },
  { id:"revenue",  label:"Revenus",   icon:"◈" },
  { id:"expenses", label:"Charges",   icon:"▤" },
  { id:"life",     label:"Vie",       icon:"♦" },
  { id:"savings",  label:"Épargne",   icon:"◆" },
  { id:"projects", label:"Projets",   icon:"⚡" },
  { id:"runway",   label:"Horizon",   icon:"→" },
];

// ═══════════════════════════════════════════════════════════════════════════
// PROJECTION ENGINE
// ═══════════════════════════════════════════════════════════════════════════

function project(p) {
  const { age, targetAge, monthlyGross, growthRate, aeType, expenses: baseExp,
    scale, alloc, assets, kids, pets, cars, tech, projects, recurring,
    cesu, charity, cafOvr, statusChange, goal } = p;

  const sc = SCALES[scale] || SCALES.moderate;
  const years = targetAge - age;
  const bals = { ...assets };
  const out = [];

  for (let y = 0; y < years; y++) {
    const yr = YR + y;
    const a = age + y;
    const inf = Math.pow(1 + sc.infl, y);
    const costF = Math.pow(1 + sc.cost, y);

    // Revenue
    const gross = monthlyGross * 12 * Math.pow(1 + growthRate, y);
    const aeR = getRate(aeType, yr);
    let statusBonus = 0;
    if (statusChange?.enabled && yr >= statusChange.year) statusBonus = statusChange.savings || 0;
    const charges = gross * aeR - statusBonus;

    // Base expenses
    const baseE = baseExp * 12 * costF;

    // Kids
    let kidE = 0, activeKids = 0;
    for (const k of (kids || [])) {
      const ka = k.age + y;
      if (ka > 25) continue;
      activeKids++;
      for (const e of (k.expenses || [])) {
        if (ka >= e.from && ka <= e.to)
          kidE += (e.monthly ? e.amt * 12 : e.amt) * inf;
      }
    }

    // Pets
    let petE = 0;
    for (const pet of (pets || [])) {
      const pa = pet.age + y;
      const life = pet.type === "dog" ? 13 : pet.type === "cat" ? 18 : 12;
      if (pa > life) continue;
      petE += (pet.cost || 800) * inf;
      if (pa < 2 || pa > life - 3) petE += 300 * inf;
    }

    // Cars
    let carE = 0;
    for (const c of (cars || [])) {
      const ca = c.age + y;
      carE += (c.annual || 2400) * inf;
      if (ca > 0 && ca % (c.cycle || 8) === 0) carE += (c.replace || 18000) * inf;
      if (ca >= 4 && (ca - 4) % 2 === 0) carE += 80 * inf; // CT
    }

    // Tech
    let techE = 0;
    for (const t of (tech || [])) {
      const ta = t.age + y;
      if (ta > 0 && ta % (t.cycle || 3) === 0) techE += (t.replace || 1200) * inf;
    }

    // Recurring
    let recE = 0;
    for (const r of (recurring || [])) {
      if (yr >= r.from && yr <= r.to) recE += r.amount * inf;
    }

    // Projects
    let projE = 0, projI = 0;
    for (const pr of (projects || [])) {
      if (pr.type === "invest" && yr >= pr.start) {
        if (yr === pr.start) projE += pr.cost || 0;
        const owned = yr - pr.start;
        if (owned > 0) {
          projI += (pr.income || 0) * Math.pow(1.02, owned);
          projE += (pr.expenses || 0) * inf;
          projE += Math.max(0, (pr.income || 0) - (pr.expenses || 0)) * (pr.tax || .30);
        }
      }
      if (pr.type === "event" && yr === pr.year) projE += pr.cost || 0;
    }

    // CAF
    const k20 = (kids || []).filter(k => k.age + y < 20).length;
    const caf = (cafOvr != null ? (k20 > 0 ? cafOvr * 12 * Math.pow(1.015, y) : 0)
      : cafEstimate(k20, monthlyGross * Math.pow(1 + growthRate, y), yr) * 12);

    // Tax breaks
    const cesuCr = Math.min((cesu || 0) * inf * .5, 6000);
    const charityCr = Math.min((charity || 0) * inf * .66, 20000);

    const totalE = baseE + kidE + petE + carE + techE + recE + projE;
    const totalI = gross + caf + projI + cesuCr + charityCr;
    const net = totalI - charges - 300 * inf - totalE + statusBonus;

    // Investments
    let invested = 0, returns = 0;
    for (const [vk, mo] of Object.entries(alloc || {})) {
      if (!mo || mo <= 0) continue;
      const sp = VEHICLES[vk]; if (!sp) continue;
      const b = bals[vk] || 0;
      const contrib = mo * 12;
      const er = Math.max(.005, sp.rate - sc.infl * .25);
      const ret = b * er;
      const nr = sp.taxFree ? ret : ret * (1 - (sp.taxRate || 0));
      bals[vk] = Math.min(b + contrib + nr, sp.ceil ? sp.ceil * inf : Infinity);
      invested += contrib;
      returns += nr;
    }

    const wealth = Object.values(bals).reduce((s, v) => s + v, 0);
    const passive = wealth * .04 / 12;
    const totalMonthlyInc = (gross + projI + caf) / 12 + passive;

    out.push({
      yr, age: a, gross, charges, aeR, baseE, kidE, petE, carE, techE, recE,
      projE, projI, caf, totalE, totalI, net, invested, returns, wealth, passive,
      activeKids, statusBonus, totalMonthlyInc,
      goalHit: goal ? totalMonthlyInc >= goal : false,
    });
  }
  return out;
}

// ═══════════════════════════════════════════════════════════════════════════
// UI PRIMITIVES
// ═══════════════════════════════════════════════════════════════════════════

function Inp({ label, value, onChange, suffix, hint, type="number", min=0, step=50, placeholder, className="" }) {
  return (
    <div className={className}>
      {label && <label className="block text-[10px] font-semibold text-zinc-400 mb-1 uppercase tracking-wider">{label}</label>}
      <div className="relative">
        <input type={type} min={min} step={step} value={value} placeholder={placeholder}
          onChange={e => onChange(type === "number" ? (parseFloat(e.target.value) || 0) : e.target.value)}
          className="w-full bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/15 transition-all placeholder:text-zinc-600" />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 text-[10px] font-mono">{suffix}</span>}
      </div>
      {hint && <p className="text-[10px] text-zinc-500 mt-0.5 leading-tight">{hint}</p>}
    </div>
  );
}

function Sel({ label, value, onChange, options }) {
  return (
    <div>
      {label && <label className="block text-[10px] font-semibold text-zinc-400 mb-1 uppercase tracking-wider">{label}</label>}
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full bg-zinc-900/60 border border-zinc-700/40 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-teal-500/50">
        {options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </div>
  );
}

function Card({ children, title, icon, accent }) {
  const ac = { teal:"border-l-teal-500", amber:"border-l-amber-500", rose:"border-l-rose-500",
    purple:"border-l-purple-500", emerald:"border-l-emerald-500", sky:"border-l-sky-500" };
  return (
    <div className={`border border-zinc-800/60 rounded-xl bg-zinc-900/40 overflow-hidden ${accent ? `border-l-2 ${ac[accent]||""}` : ""}`}>
      {title && (
        <div className="px-5 py-3 border-b border-zinc-800/40 flex items-center gap-2">
          {icon && <span className="text-sm">{icon}</span>}
          <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wide">{title}</h3>
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}

function Stat({ label, value, sub, color="teal" }) {
  const c = { teal:"text-teal-400", emerald:"text-emerald-400", amber:"text-amber-400", rose:"text-rose-400", purple:"text-purple-400" };
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/40 rounded-lg p-3">
      <p className="text-[9px] text-zinc-500 uppercase tracking-widest">{label}</p>
      <p className={`text-lg font-mono font-bold ${c[color]||c.teal}`}>{value}</p>
      {sub && <p className="text-[10px] text-zinc-500">{sub}</p>}
    </div>
  );
}

function Chart({ data, height=100, color="#2dd4bf", goalLine }) {
  if (!data || data.length < 2) return null;
  const vals = data.map(d => d.v);
  const max = Math.max(...vals, goalLine || 0);
  const min = Math.min(...vals, 0);
  const range = max - min || 1;
  const w = 400, h = height;
  const pts = data.map((d, i) => `${(i/(data.length-1))*w},${h-((d.v-min)/range)*h*.85-h*.07}`).join(" ");
  const area = pts + ` ${w},${h} 0,${h}`;
  const gY = goalLine != null ? h-((goalLine-min)/range)*h*.85-h*.07 : null;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" style={{height}}>
      <defs><linearGradient id={`g${color.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity=".25"/><stop offset="100%" stopColor={color} stopOpacity="0"/>
      </linearGradient></defs>
      <polygon points={area} fill={`url(#g${color.slice(1)})`}/>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2"/>
      {gY!=null && <line x1="0" y1={gY} x2={w} y2={gY} stroke="#f59e0b" strokeWidth="1" strokeDasharray="6,4" opacity=".6"/>}
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// IDENTITY
// ═══════════════════════════════════════════════════════════════════════════

function Identity({ d, set }) {
  return (
    <div className="space-y-5 animate-in">
      <div className="bg-teal-950/20 border border-teal-900/30 rounded-xl p-4">
        <p className="text-xs text-teal-300/80"><strong className="text-teal-200">Configuration initiale.</strong> Ces valeurs définissent votre situation fiscale et familiale. Elles changent rarement.</p>
      </div>

      <Card title="Vous" icon="👤" accent="teal">
        <div className="grid grid-cols-3 gap-4">
          <Inp label="Âge actuel" value={d.age} onChange={v=>set("age",v)} suffix="ans" step={1} />
          <Inp label="Âge retraite visé" value={d.targetAge} onChange={v=>set("targetAge",v)} suffix="ans" step={1}
            hint="L'âge où vous voulez pouvoir choisir de ne plus travailler" />
          <Inp label="Parts fiscales" value={d.taxParts} onChange={v=>set("taxParts",v)} suffix="" step={.5} min={1}
            hint="1=seul · 2=couple · +0.5/enfant · +1 au 3ème" />
        </div>
      </Card>

      <Card title="Statut & Activité" icon="📋" accent="amber">
        <div className="grid grid-cols-2 gap-4">
          <Sel label="Statut actuel" value={d.status} onChange={v=>set("status",v)} options={[
            {v:"ae",l:"Auto-Entrepreneur (AE)"},{v:"eirl",l:"EIRL / EI"},{v:"eurl",l:"EURL"},{v:"sasu",l:"SASU"}
          ]}/>
          <Sel label="Type d'activité" value={d.aeType} onChange={v=>set("aeType",v)} options={[
            {v:"bic_vente",l:"BIC Vente — ~14,8% avec VL"},
            {v:"bic_services",l:"BIC Services — ~23,7% avec VL"},
            {v:"bnc_non_reglementee",l:"BNC Non réglementée — ~26,2% avec VL"},
            {v:"bnc_cipav",l:"BNC CIPAV — ~25,4% avec VL"},
          ]}/>
        </div>
        <div className="mt-3 flex items-center gap-3 p-3 rounded-lg bg-zinc-800/30">
          <input type="checkbox" checked={d.hasVL} onChange={e=>set("hasVL",e.target.checked)}
            className="rounded border-zinc-600 bg-zinc-800 text-teal-500"/>
          <div>
            <span className="text-sm text-zinc-300">Versement libératoire de l'IR</span>
            <p className="text-[10px] text-zinc-500">Ajoute ~2,2% mais simplifie l'IR. Total actuel : ~{fmtPct(getRate(d.aeType, YR))}</p>
          </div>
        </div>
        <div className="mt-4 p-3 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
          <p className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-2">Évolution prévue des cotisations</p>
          <div className="flex gap-3">
            {(AE_SCHEDULES[d.aeType]||[]).map((s,i) => (
              <div key={i} className="text-center flex-1">
                <p className="text-[9px] text-zinc-500">{s.y}</p>
                <p className="text-xs font-mono font-bold text-amber-400">{fmtPct(s.r)}</p>
              </div>
            ))}
          </div>
          <p className="text-[9px] text-zinc-600 mt-1">Projections basées sur les tendances législatives. L'outil applique ces taux automatiquement dans la projection.</p>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// REVENUE
// ═══════════════════════════════════════════════════════════════════════════

function Revenue({ d, set }) {
  const r = getRate(d.aeType, YR);
  return (
    <div className="space-y-5 animate-in">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="CA brut mensuel" value={fmt(d.monthlyGross)} color="teal"/>
        <Stat label="Cotisations mensuelles" value={fmt(d.monthlyGross*r)} sub={fmtPct(r)} color="rose"/>
        <Stat label="Net après cotisations" value={fmt(d.monthlyGross*(1-r))} color="emerald"/>
      </div>

      <Card title="Chiffre d'affaires" icon="💰" accent="teal">
        <Inp label="CA brut mensuel moyen" value={d.monthlyGross} onChange={v=>set("monthlyGross",v)}
          hint="Votre chiffre d'affaires moyen encaissé, avant toute déduction"/>
      </Card>

      <Card title="Croissance annuelle du CA" icon="📈" accent="emerald">
        <p className="text-xs text-zinc-400 mb-4">Comment votre CA va évoluer ? Choisissez un profil ou définissez votre taux.</p>
        <div className="grid grid-cols-4 gap-2 mb-4">
          {Object.entries(GROWTH).map(([k,g]) => (
            <button key={k} onClick={() => { set("growthPreset",k); if(g.rate!=null) set("growthRate",g.rate); }}
              className={`p-3 rounded-lg border text-left transition-all ${
                d.growthPreset===k ? "border-teal-600/50 bg-teal-950/20" : "border-zinc-800/40 bg-zinc-900/30 hover:border-zinc-700"}`}>
              <p className={`text-xs font-semibold ${d.growthPreset===k?"text-teal-300":"text-zinc-300"}`}>{g.label}</p>
              {g.rate!=null && <p className="text-sm font-mono font-bold text-zinc-200 mt-0.5">{fmtPct(g.rate)}/an</p>}
              <p className="text-[10px] text-zinc-500 mt-1 leading-tight">{g.desc}</p>
            </button>
          ))}
        </div>
        {d.growthPreset==="custom" && (
          <Inp label="Taux personnalisé" value={d.growthRate*100} onChange={v=>set("growthRate",v/100)} suffix="%" step={.5}/>
        )}
        <div className="mt-4 p-3 rounded-lg bg-zinc-800/20 border border-zinc-800/40">
          <p className="text-[10px] text-zinc-400 font-semibold uppercase tracking-wider mb-2">Votre CA sur 5 ans</p>
          <div className="flex gap-3">
            {[0,1,2,3,4].map(y => (
              <div key={y} className="flex-1 text-center">
                <p className="text-[9px] text-zinc-500">{YR+y}</p>
                <p className="text-xs font-mono font-bold text-zinc-200">{fmt(d.monthlyGross*Math.pow(1+d.growthRate,y))}</p>
                <p className="text-[9px] text-zinc-600">/mois</p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card title="Avantages fiscaux" icon="🏛️" accent="purple">
        <div className="grid grid-cols-2 gap-4">
          <Inp label="CESU annuel (ménage, jardin...)" value={d.cesu} onChange={v=>set("cesu",v)}
            hint={`Crédit d'impôt 50% → économie ${fmt(Math.min(d.cesu*.5,6000))}/an`}/>
          <Inp label="Dons caritatifs annuels" value={d.charity} onChange={v=>set("charity",v)}
            hint={`Réduction 66% → économie ${fmt(Math.min(d.charity*.66,20000))}/an`}/>
        </div>
        <div className="mt-3 p-3 rounded-lg bg-purple-950/15 border border-purple-900/20">
          <p className="text-[10px] text-purple-300/70">
            <strong>💡</strong> Employer quelqu'un en CESU (ménage, garde d'enfants) = 50% de crédit d'impôt, plafonné à 12 000€/an. Une des rares optimisations accessibles aux AE.
          </p>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPENSES
// ═══════════════════════════════════════════════════════════════════════════

function Expenses({ d, set }) {
  const total = Object.values(d.expenses).reduce((s,v)=>s+v, 0);
  return (
    <div className="space-y-5 animate-in">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Total mensuel" value={fmt(total)} sub="base 2026" color="amber"/>
        <Stat label="Total annuel" value={fmt(total*12)} color="amber"/>
      </div>

      <Card title="Dépenses mensuelles fixes (base 2026)" icon="📊" accent="amber">
        <p className="text-xs text-zinc-400 mb-4">
          Saisissez vos dépenses actuelles. L'inflation est appliquée automatiquement — vous choisissez le scénario dans l'onglet Horizon.
        </p>
        <div className="grid grid-cols-3 gap-3">
          {[["loyer","Loyer / Crédit"],["energie","Énergie"],["internet","Internet & tél"],
            ["assurance","Assurances"],["transport","Carburant / Transport"],["alimentation","Alimentation"],
            ["sante","Santé / Mutuelle"],["loisirs","Loisirs"],["abonnements","Abonnements"],
            ["impots","Impôts locaux"],["credit","Crédits en cours"],["divers","Divers"]
          ].map(([k,l]) => (
            <Inp key={k} label={l} value={d.expenses[k]||0}
              onChange={v=>set("expenses",{...d.expenses,[k]:v})} className="min-w-0"/>
          ))}
        </div>
      </Card>

      <Card title="Impact de l'inflation sur vos charges" icon="📉" accent="rose">
        <div className="space-y-2">
          {Object.entries(SCALES).map(([k,s]) => (
            <div key={k} className="flex items-center gap-3 p-2 rounded-lg bg-zinc-800/20">
              <span className="text-sm">{s.emoji}</span>
              <span className="text-xs text-zinc-400 w-20">{s.label}</span>
              <div className="flex-1 flex gap-4">
                {[5,10,20,30].map(y => (
                  <div key={y} className="text-center flex-1">
                    <p className="text-[9px] text-zinc-500">+{y} ans</p>
                    <p className="text-xs font-mono" style={{color:s.color}}>{fmt(total*Math.pow(1+s.cost,y))}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Allocations familiales (CAF)" icon="👨‍👩‍👧‍👦" accent="purple">
        <p className="text-xs text-zinc-400 mb-3">
          2+ enfants de moins de 20 ans → la CAF verse des allocations. Saisissez votre montant réel ou laissez l'estimation.
        </p>
        <Inp label="CAF mensuelle actuelle (0 = estimation auto)" value={d.cafOvr||0}
          onChange={v=>set("cafOvr",v||null)} hint="Basé sur revenu et nombre d'enfants < 20 ans"/>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// LIFE ENTITIES
// ═══════════════════════════════════════════════════════════════════════════

function Life({ d, set }) {
  const addKid = () => set("kids", [...(d.kids||[]), {
    name:`Enfant ${(d.kids||[]).length+1}`, age:0,
    expenses:[
      {label:"Crèche / Garde",from:0,to:3,amt:500,monthly:true},
      {label:"Cantine + périscolaire",from:3,to:11,amt:150,monthly:true},
      {label:"Camp d'été",from:6,to:17,amt:800,monthly:false},
      {label:"Activités extra",from:6,to:18,amt:100,monthly:true},
      {label:"Permis + 1ère voiture",from:18,to:18,amt:5000,monthly:false},
      {label:"Études supérieures",from:18,to:23,amt:500,monthly:true},
    ]
  }]);

  return (
    <div className="space-y-5 animate-in">
      <div className="bg-sky-950/20 border border-sky-900/30 rounded-xl p-4">
        <p className="text-xs text-sky-300/80">
          <strong className="text-sky-200">Entités de vie.</strong> Enfants, animaux, voitures, tech — chaque élément a un cycle de coûts qui évolue. Les enfants génèrent des coûts qui disparaissent quand ils grandissent. Les voitures se remplacent. L'outil intègre tout dans la projection.
        </p>
      </div>

      {/* KIDS */}
      <Card title="Enfants" icon="👶" accent="purple">
        {(d.kids||[]).map((kid, ki) => (
          <div key={ki} className="border border-zinc-800/40 rounded-lg p-4 bg-zinc-800/10 mb-3">
            <div className="flex items-center gap-3 mb-3">
              <Inp label="Prénom" value={kid.name} onChange={v=>{const k=[...d.kids];k[ki]={...k[ki],name:v};set("kids",k);}} type="text" className="flex-1"/>
              <Inp label="Âge" value={kid.age} onChange={v=>{const k=[...d.kids];k[ki]={...k[ki],age:v};set("kids",k);}} suffix="ans" step={1} className="w-24"/>
              <button onClick={()=>set("kids",d.kids.filter((_,i)=>i!==ki))} className="text-zinc-500 hover:text-rose-400 mt-4">✕</button>
            </div>
            <p className="text-[10px] text-zinc-500 mb-2 uppercase tracking-wider font-semibold">Dépenses prévues</p>
            <div className="space-y-1.5">
              {kid.expenses.map((exp, ei) => {
                const ka = kid.age;
                const active = ka >= exp.from && ka <= exp.to;
                const past = ka > exp.to;
                return (
                  <div key={ei} className={`flex items-center gap-2 text-xs p-2 rounded ${past?"opacity-30":active?"bg-purple-950/20":""}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${active?"bg-purple-400":past?"bg-zinc-800":"bg-zinc-600"}`}/>
                    <input type="text" value={exp.label} className="flex-1 bg-transparent text-zinc-300 text-xs focus:outline-none"
                      onChange={e=>{const k=[...d.kids];const x=[...k[ki].expenses];x[ei]={...x[ei],label:e.target.value};k[ki]={...k[ki],expenses:x};set("kids",k);}}/>
                    <span className="text-zinc-500 text-[10px] font-mono">{exp.from}→{exp.to} ans</span>
                    <input type="number" value={exp.amt}
                      className="w-16 bg-zinc-800/40 border border-zinc-700/30 rounded px-1.5 py-0.5 text-xs font-mono text-right text-white focus:outline-none"
                      onChange={e=>{const k=[...d.kids];const x=[...k[ki].expenses];x[ei]={...x[ei],amt:parseFloat(e.target.value)||0};k[ki]={...k[ki],expenses:x};set("kids",k);}}/>
                    <span className="text-[10px] text-zinc-500">{exp.monthly?"€/mois":"€/an"}</span>
                  </div>
                );
              })}
            </div>
            <button onClick={()=>{const k=[...d.kids];k[ki]={...k[ki],expenses:[...k[ki].expenses,{label:"Nouveau poste",from:0,to:18,amt:100,monthly:true}]};set("kids",k);}}
              className="text-[10px] text-zinc-500 hover:text-teal-400 mt-2">+ Ajouter un poste</button>
          </div>
        ))}
        <button onClick={addKid} className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">
          + Ajouter un enfant
        </button>
      </Card>

      {/* PETS */}
      <Card title="Animaux" icon="🐾" accent="emerald">
        {(d.pets||[]).map((pet, pi) => (
          <div key={pi} className="flex items-end gap-3 mb-2">
            <Inp label="Nom" value={pet.name} onChange={v=>{const p=[...d.pets];p[pi]={...p[pi],name:v};set("pets",p);}} type="text" className="flex-1"/>
            <Sel label="Type" value={pet.type} onChange={v=>{const p=[...d.pets];p[pi]={...p[pi],type:v};set("pets",p);}}
              options={[{v:"dog",l:"Chien"},{v:"cat",l:"Chat"},{v:"other",l:"Autre"}]}/>
            <Inp label="Âge" value={pet.age} onChange={v=>{const p=[...d.pets];p[pi]={...p[pi],age:v};set("pets",p);}} suffix="ans" step={1} className="w-20"/>
            <Inp label="Coût/an" value={pet.cost} onChange={v=>{const p=[...d.pets];p[pi]={...p[pi],cost:v};set("pets",p);}} className="w-24"
              hint="Nourriture, véto, vaccins"/>
            <button onClick={()=>set("pets",d.pets.filter((_,i)=>i!==pi))} className="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
          </div>
        ))}
        <button onClick={()=>set("pets",[...(d.pets||[]),{name:"Animal",type:"dog",age:0,cost:900}])}
          className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">+ Ajouter un animal</button>
      </Card>

      {/* CARS */}
      <Card title="Véhicules" icon="🚗" accent="amber">
        {(d.cars||[]).map((car, ci) => (
          <div key={ci} className="flex items-end gap-2 mb-2 flex-wrap">
            <Inp label="Nom" value={car.name} onChange={v=>{const c=[...d.cars];c[ci]={...c[ci],name:v};set("cars",c);}} type="text" className="flex-1 min-w-[100px]"/>
            <Sel label="Type" value={car.type} onChange={v=>{const c=[...d.cars];c[ci]={...c[ci],type:v};set("cars",c);}}
              options={[{v:"petrol",l:"Essence"},{v:"diesel",l:"Diesel"},{v:"electric",l:"Électrique"},{v:"hybrid",l:"Hybride"}]}/>
            <Inp label="Âge" value={car.age} onChange={v=>{const c=[...d.cars];c[ci]={...c[ci],age:v};set("cars",c);}} suffix="ans" step={1} className="w-16"/>
            <Inp label="Coût/an" value={car.annual} onChange={v=>{const c=[...d.cars];c[ci]={...c[ci],annual:v};set("cars",c);}} className="w-24" hint="Assurance+essence+entretien"/>
            <Inp label="Rempl. tous les" value={car.cycle} onChange={v=>{const c=[...d.cars];c[ci]={...c[ci],cycle:v};set("cars",c);}} suffix="ans" step={1} className="w-20"/>
            <Inp label="Coût rempl." value={car.replace} onChange={v=>{const c=[...d.cars];c[ci]={...c[ci],replace:v};set("cars",c);}} className="w-24"/>
            <button onClick={()=>set("cars",d.cars.filter((_,i)=>i!==ci))} className="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
          </div>
        ))}
        <button onClick={()=>set("cars",[...(d.cars||[]),{name:"Voiture",type:"petrol",age:3,annual:2400,cycle:8,replace:18000}])}
          className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">+ Ajouter un véhicule</button>
      </Card>

      {/* TECH */}
      <Card title="Tech" icon="💻" accent="sky">
        {(d.tech||[]).map((t, ti) => (
          <div key={ti} className="flex items-end gap-3 mb-2">
            <Inp label="Appareil" value={t.name} onChange={v=>{const x=[...d.tech];x[ti]={...x[ti],name:v};set("tech",x);}} type="text" className="flex-1"/>
            <Inp label="Âge" value={t.age} onChange={v=>{const x=[...d.tech];x[ti]={...x[ti],age:v};set("tech",x);}} suffix="ans" step={1} className="w-20"/>
            <Inp label="Rempl." value={t.cycle} onChange={v=>{const x=[...d.tech];x[ti]={...x[ti],cycle:v};set("tech",x);}} suffix="ans" step={1} className="w-20"/>
            <Inp label="Coût futur" value={t.replace} onChange={v=>{const x=[...d.tech];x[ti]={...x[ti],replace:v};set("tech",x);}} className="w-24" hint="Inflation auto"/>
            <button onClick={()=>set("tech",d.tech.filter((_,i)=>i!==ti))} className="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
          </div>
        ))}
        <button onClick={()=>set("tech",[...(d.tech||[]),{name:"Appareil",age:1,cycle:3,replace:1200}])}
          className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">+ Ajouter un appareil</button>
      </Card>

      {/* RECURRING */}
      <Card title="Dépenses récurrentes à durée limitée" icon="🔄" accent="rose">
        <p className="text-xs text-zinc-400 mb-3">Remboursements de prêt, colonies, sport enfant — ce qui revient chaque année mais a une date de fin.</p>
        {(d.recurring||[]).map((r, i) => (
          <div key={i} className="flex items-end gap-2 mb-2">
            <Inp label="Description" value={r.label} onChange={v=>{const x=[...d.recurring];x[i]={...x[i],label:v};set("recurring",x);}} type="text" className="flex-1"/>
            <Inp label="€/an" value={r.amount} onChange={v=>{const x=[...d.recurring];x[i]={...x[i],amount:v};set("recurring",x);}} className="w-20"/>
            <Inp label="De" value={r.from} onChange={v=>{const x=[...d.recurring];x[i]={...x[i],from:v};set("recurring",x);}} suffix="" step={1} className="w-20"/>
            <Inp label="À" value={r.to} onChange={v=>{const x=[...d.recurring];x[i]={...x[i],to:v};set("recurring",x);}} suffix="" step={1} className="w-20"/>
            <button onClick={()=>set("recurring",d.recurring.filter((_,j)=>j!==i))} className="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
          </div>
        ))}
        <button onClick={()=>set("recurring",[...(d.recurring||[]),{label:"",amount:0,from:YR,to:YR+5}])}
          className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">+ Ajouter</button>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SAVINGS
// ═══════════════════════════════════════════════════════════════════════════

function Savings({ d, set }) {
  const totalM = Object.values(d.alloc||{}).reduce((s,v)=>s+v,0);
  const totalE = Object.values(d.assets||{}).reduce((s,v)=>s+v,0);
  return (
    <div className="space-y-5 animate-in">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Épargne existante" value={fmtK(totalE)} color="purple"/>
        <Stat label="Versement mensuel" value={fmt(totalM)} color="teal"/>
        <Stat label="Versement annuel" value={fmt(totalM*12)} color="teal"/>
      </div>

      <Card title="Épargne & allocation mensuelle" icon="◆" accent="purple">
        {Object.entries(VEHICLES).map(([k,v]) => (
          <div key={k} className="border border-zinc-800/30 rounded-lg p-3 mb-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2.5 h-2.5 rounded-full" style={{backgroundColor:v.color}}/>
              <span className="text-xs font-semibold text-zinc-200">{v.label}</span>
              <span className="text-[10px] text-zinc-500 font-mono ml-auto">
                {fmtPct(v.rate)}/an {v.taxFree?"• net":"• "+fmtPct(v.taxRate||0)+" PFU"}
                {v.ceil && ` • plafond ${fmtK(v.ceil)}`}
              </span>
            </div>
            <div className="flex gap-3">
              <Inp label="Solde actuel" value={d.assets?.[k]||0} onChange={val=>set("assets",{...d.assets,[k]:val})} className="flex-1"/>
              <Inp label="Versement mensuel" value={d.alloc?.[k]||0} onChange={val=>set("alloc",{...d.alloc,[k]:val})} className="flex-1"/>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// PROJECTS
// ═══════════════════════════════════════════════════════════════════════════

function Projects({ d, set }) {
  return (
    <div className="space-y-5 animate-in">
      <Card title="Investissements" icon="🏡" accent="emerald">
        <p className="text-xs text-zinc-400 mb-4">Immobilier locatif, gîte — chaque projet a son mini bilan : revenus, charges, fiscalité.</p>
        {(d.projects||[]).filter(p=>p.type==="invest").map((pr, _i) => {
          const pi = (d.projects||[]).indexOf(pr);
          const net = (pr.income||0) - (pr.expenses||0);
          const taxed = net * (1-(pr.tax||.30));
          return (
            <div key={pi} className="border border-zinc-800/40 rounded-lg p-4 mb-3 bg-zinc-800/10">
              <div className="flex items-start gap-3 mb-3">
                <Inp label="Nom" value={pr.label} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],label:v};set("projects",p);}} type="text" className="flex-1"/>
                <Inp label="Année" value={pr.start} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],start:v};set("projects",p);}} suffix="" step={1} className="w-24"/>
                <button onClick={()=>set("projects",d.projects.filter((_,j)=>j!==pi))} className="text-zinc-500 hover:text-rose-400 mt-4">✕</button>
              </div>
              <div className="grid grid-cols-4 gap-3">
                <Inp label="Coût d'achat" value={pr.cost} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],cost:v};set("projects",p);}}/>
                <Inp label="Revenus/an" value={pr.income} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],income:v};set("projects",p);}}/>
                <Inp label="Charges/an" value={pr.expenses} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],expenses:v};set("projects",p);}} hint="Ménage, entretien, assurance"/>
                <Inp label="Imposition" value={(pr.tax||.3)*100} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],tax:v/100};set("projects",p);}} suffix="%" step={1}/>
              </div>
              <div className="mt-3 p-2 rounded bg-zinc-800/30 flex gap-4 text-xs">
                <span className="text-zinc-400">Brut: <strong className="text-zinc-200">{fmt(net)}</strong>/an</span>
                <span className="text-zinc-400">Net: <strong className="text-emerald-400">{fmt(taxed)}</strong>/an</span>
                <span className="text-zinc-400">Rendement: <strong className="text-teal-400">{pr.cost?fmtPct(taxed/pr.cost):"—"}</strong></span>
              </div>
            </div>
          );
        })}
        <button onClick={()=>set("projects",[...(d.projects||[]),{type:"invest",label:"Nouveau projet",start:2035,cost:80000,income:8000,expenses:2500,tax:.30}])}
          className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">+ Ajouter un investissement</button>
      </Card>

      <Card title="Événements ponctuels" icon="🎉" accent="amber">
        <p className="text-xs text-zinc-400 mb-4">Mariage, grand voyage, grosse rénovation — dépenses one-shot.</p>
        {(d.projects||[]).filter(p=>p.type==="event").map((pr, _i) => {
          const pi = (d.projects||[]).indexOf(pr);
          return (
            <div key={pi} className="flex items-end gap-3 mb-2">
              <Inp label="Description" value={pr.label} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],label:v};set("projects",p);}} type="text" className="flex-1"/>
              <Inp label="Année" value={pr.year} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],year:v};set("projects",p);}} suffix="" step={1} className="w-24"/>
              <Inp label="Coût" value={pr.cost} onChange={v=>{const p=[...d.projects];p[pi]={...p[pi],cost:v};set("projects",p);}} className="w-28"/>
              <button onClick={()=>set("projects",d.projects.filter((_,j)=>j!==pi))} className="text-zinc-500 hover:text-rose-400 mb-2">✕</button>
            </div>
          );
        })}
        <button onClick={()=>set("projects",[...(d.projects||[]),{type:"event",label:"Événement",year:2030,cost:10000}])}
          className="w-full py-2 rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-400 hover:text-teal-300 hover:border-teal-800 transition-colors">+ Ajouter</button>
      </Card>

      <Card title="Changement de statut juridique" icon="🔄" accent="teal">
        <p className="text-xs text-zinc-400 mb-3">
          AE → EIRL/EURL : déduire vos vraies charges (internet 50€, bureau 200€, voiture 250€, repas 150€ = 650€/mois = 7 800€/an). Si ça dépasse l'abattement forfaitaire de 34%, votre base imposable baisse.
        </p>
        <div className="flex items-center gap-3 mb-3 p-3 rounded-lg bg-zinc-800/30">
          <input type="checkbox" checked={d.statusChange?.enabled}
            onChange={e=>set("statusChange",{...d.statusChange,enabled:e.target.checked})}
            className="rounded border-zinc-600 bg-zinc-800 text-teal-500"/>
          <span className="text-sm text-zinc-300">Simuler un changement de statut</span>
        </div>
        {d.statusChange?.enabled && (
          <div className="grid grid-cols-3 gap-3">
            <Inp label="Année" value={d.statusChange.year} onChange={v=>set("statusChange",{...d.statusChange,year:v})} suffix="" step={1}/>
            <Sel label="Nouveau statut" value={d.statusChange.newStatus} onChange={v=>set("statusChange",{...d.statusChange,newStatus:v})}
              options={[{v:"eirl",l:"EIRL / EI"},{v:"eurl",l:"EURL"},{v:"sasu",l:"SASU"}]}/>
            <Inp label="Économie nette/an" value={d.statusChange.savings} onChange={v=>set("statusChange",{...d.statusChange,savings:v})}
              hint="Gain annuel vs rester AE"/>
          </div>
        )}
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// RUNWAY — THE MAIN VIEW
// ═══════════════════════════════════════════════════════════════════════════

function Runway({ d, set }) {
  const [scale, setScale] = useState("moderate");
  const totalExp = Object.values(d.expenses||{}).reduce((s,v)=>s+v,0);

  const tl = useMemo(() => project({
    age:d.age, targetAge:d.targetAge, monthlyGross:d.monthlyGross, growthRate:d.growthRate,
    aeType:d.aeType, expenses:totalExp, scale, alloc:d.alloc, assets:d.assets,
    kids:d.kids, pets:d.pets, cars:d.cars, tech:d.tech, projects:d.projects,
    recurring:d.recurring, cesu:d.cesu, charity:d.charity, cafOvr:d.cafOvr,
    statusChange:d.statusChange, goal:d.goal,
  }), [d, scale]);

  const last = tl[tl.length-1];
  const goalYr = tl.find(t=>t.goalHit);

  const milestones = [];
  for (const [amt,lbl,col] of [[1e5,"100k€","#22d3ee"],[25e4,"250k€","#a78bfa"],[5e5,"500k€","#f59e0b"],[1e6,"1M€","#10b981"]]) {
    const h = tl.find(t=>t.wealth>=amt);
    if (h) milestones.push({label:lbl, year:h.yr, age:h.age, color:col});
  }

  return (
    <div className="space-y-5 animate-in">
      <div>
        <p className="text-[10px] text-zinc-400 uppercase tracking-widest mb-2 font-semibold">Scénario économique</p>
        <div className="flex gap-1.5">
          {Object.entries(SCALES).map(([k,s]) => (
            <button key={k} onClick={()=>setScale(k)}
              className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all border ${
                scale===k ? "border-zinc-600 bg-zinc-800 text-white" : "border-zinc-800/40 bg-zinc-900/30 text-zinc-500 hover:text-zinc-300"}`}>
              {s.emoji} {s.label}
            </button>
          ))}
        </div>
      </div>

      <Card title="Objectif de revenu mensuel à la retraite" icon="🎯" accent="teal">
        <p className="text-xs text-zinc-400 mb-3">Combien voulez-vous toucher (travail + passif + projets) pour ne plus dépendre de personne ?</p>
        <Inp label="Objectif mensuel" value={d.goal||0} onChange={v=>set("goal",v)}
          hint={goalYr ? `✓ Atteint en ${goalYr.yr} (à ${goalYr.age} ans)` : d.goal ? "Pas encore atteint — augmentez l'épargne ou ajoutez des projets" : ""}/>
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <Stat label={`Patrimoine à ${d.targetAge} ans (${last?.yr})`} value={fmtK(last?.wealth||0)} color="teal"/>
        <Stat label="Revenu passif mensuel" value={fmt(last?.passive||0)} sub="Règle des 4%" color="emerald"/>
      </div>

      <Card title="Trajectoire patrimoine" accent="teal">
        <Chart data={tl.map(t=>({v:t.wealth}))} height={140} color="#2dd4bf"/>
        <div className="flex justify-between text-[9px] text-zinc-500 font-mono mt-1">
          <span>{tl[0]?.yr} ({d.age} ans)</span>
          <span>{last?.yr} ({d.targetAge} ans)</span>
        </div>
      </Card>

      <Card title="Revenu total mensuel (travail + passif + projets)" accent="emerald">
        <Chart data={tl.map(t=>({v:t.totalMonthlyInc}))} height={120} color="#10b981" goalLine={d.goal}/>
        <div className="flex justify-between text-[9px] text-zinc-500 font-mono mt-1">
          <span>{fmt(tl[0]?.totalMonthlyInc||0)}/mois</span>
          {d.goal>0 && <span className="text-amber-400">Objectif: {fmt(d.goal)}</span>}
          <span>{fmt(last?.totalMonthlyInc||0)}/mois</span>
        </div>
      </Card>

      {milestones.length>0 && (
        <Card title="Jalons">
          <div className="relative pl-4">
            <div className="absolute left-[7px] top-0 bottom-0 w-px bg-zinc-800"/>
            {milestones.map((m,i) => (
              <div key={i} className="flex items-center gap-3 py-2">
                <div className="w-4 h-4 rounded-full border-2 bg-zinc-950 z-10 flex items-center justify-center" style={{borderColor:m.color}}>
                  <div className="w-1.5 h-1.5 rounded-full" style={{backgroundColor:m.color}}/>
                </div>
                <span className="text-sm font-mono font-bold" style={{color:m.color}}>{m.label}</span>
                <span className="text-xs text-zinc-500">→ {m.year} (à {m.age} ans)</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="Projection détaillée">
        <div className="overflow-x-auto -mx-5 px-5">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-zinc-500 text-[9px] uppercase tracking-wider border-b border-zinc-800">
                {["An","Âge","CA brut","Cotis.","Cotis.%","Vie","Enfants","Projets","Net","Patrimoine","Passif/m"].map(h =>
                  <th key={h} className="py-2 text-right first:text-left">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {tl.filter((_,i) => i%5===0 || i===tl.length-1).map(t => (
                <tr key={t.yr} className="border-t border-zinc-800/30 hover:bg-zinc-800/10">
                  <td className="py-1.5 font-mono text-zinc-400">{t.yr}</td>
                  <td className="font-mono text-zinc-300 text-right">{t.age}</td>
                  <td className="font-mono text-zinc-300 text-right">{fmtK(t.gross)}</td>
                  <td className="font-mono text-rose-400/70 text-right">{fmtK(t.charges)}</td>
                  <td className="font-mono text-rose-400/50 text-right">{fmtPct(t.aeR)}</td>
                  <td className="font-mono text-amber-400/70 text-right">{fmtK(t.baseE)}</td>
                  <td className="font-mono text-purple-400/70 text-right">{t.kidE>0?fmtK(t.kidE):"—"}</td>
                  <td className="font-mono text-sky-400/70 text-right">{t.projI>0?`+${fmtK(t.projI)}`:t.projE>0?`-${fmtK(t.projE)}`:"—"}</td>
                  <td className={`font-mono text-right font-medium ${t.net>=0?"text-teal-400":"text-rose-400"}`}>{fmtK(t.net)}</td>
                  <td className="font-mono font-bold text-white text-right">{fmtK(t.wealth)}</td>
                  <td className="font-mono text-emerald-400 text-right">{fmt(t.passive)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {last && (
        <div className="space-y-3">
          {last.passive >= (d.goal || totalExp) && d.goal > 0 && (
            <div className="bg-emerald-950/15 border border-emerald-900/30 rounded-xl p-4">
              <p className="text-sm text-emerald-300">
                <strong>🏆 Objectif atteint.</strong> À {d.targetAge} ans, vos revenus passifs ({fmt(last.passive)}/mois) couvrent votre objectif. Vous n'avez pas besoin de la retraite d'État.
              </p>
            </div>
          )}
          {last.passive < (d.goal || totalExp) && d.goal > 0 && (
            <div className="bg-amber-950/15 border border-amber-900/30 rounded-xl p-4">
              <p className="text-sm text-amber-300">
                <strong>⚠️ Gap à combler.</strong> Passifs projetés : {fmt(last.passive)}/mois vs objectif {fmt(d.goal)}. Pistes : épargne mensuelle ↑, immobilier locatif, ou changement de statut pour dégager plus de marge.
              </p>
            </div>
          )}
          <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-xl p-4">
            <p className="text-[10px] text-zinc-500">
              <strong className="text-zinc-400">⚖️</strong> Simulateur uniquement. Ne constitue pas un conseil financier, fiscal ou juridique. Rendements historiques moyens, cotisations projetées sur tendances législatives.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════

export default function App() {
  const [sec, setSec] = useState("identity");
  const [st, setSt] = useState({
    age:40, targetAge:70, taxParts:2.5, status:"ae", aeType:"bnc_non_reglementee", hasVL:true,
    monthlyGross:5000, growthRate:.03, growthPreset:"moderate", cesu:0, charity:0, cafOvr:null,
    expenses: { loyer:800,energie:120,internet:60,assurance:100,transport:200,alimentation:400,sante:50,loisirs:150,abonnements:50,impots:100,credit:0,divers:100 },
    kids: [
      { name:"Aînée", age:10, expenses:[
        {label:"Cantine + périscolaire",from:3,to:11,amt:150,monthly:true},
        {label:"Camp d'été",from:6,to:17,amt:800,monthly:false},
        {label:"Activités extra",from:6,to:18,amt:100,monthly:true},
        {label:"Lycée",from:15,to:18,amt:600,monthly:false},
        {label:"Permis + voiture",from:18,to:18,amt:5000,monthly:false},
        {label:"Études supérieures",from:18,to:23,amt:500,monthly:true},
      ]},
      { name:"Petit(e)", age:1, expenses:[
        {label:"Crèche",from:0,to:3,amt:500,monthly:true},
        {label:"Cantine + périscolaire",from:3,to:11,amt:150,monthly:true},
        {label:"Camp d'été",from:6,to:17,amt:800,monthly:false},
        {label:"Activités extra",from:6,to:18,amt:100,monthly:true},
        {label:"Permis + voiture",from:18,to:18,amt:5000,monthly:false},
        {label:"Études supérieures",from:18,to:23,amt:500,monthly:true},
      ]},
    ],
    pets: [{name:"Le chien",type:"dog",age:4,cost:900}],
    cars: [{name:"Voiture principale",type:"petrol",age:5,annual:2400,cycle:8,replace:18000}],
    tech: [{name:"MacBook Pro",age:2,cycle:4,replace:2500},{name:"iPhone",age:1,cycle:3,replace:1300}],
    recurring: [{label:"Vacances d'été",amount:3000,from:2026,to:2055}],
    alloc: { livret_a:200, ldds:100, av_euro:200, pea:200, per:100, scpi:0, av_uc:150 },
    assets: { livret_a:5000, ldds:2000, av_euro:0, pea:0, per:0, scpi:0, av_uc:0 },
    projects: [
      {type:"invest",label:"Petit gîte rural",start:2035,cost:80000,income:8000,expenses:2500,tax:.30},
      {type:"event",label:"Gros voyage famille",year:2030,cost:8000},
    ],
    statusChange: {enabled:true,year:2028,newStatus:"eirl",savings:3600},
    goal: 4000,
  });

  const set = useCallback((k,v) => setSt(prev => ({...prev,[k]:v})), []);

  return (
    <div className="min-h-screen bg-zinc-950 text-white" style={{fontFamily:"'Inter',-apple-system,sans-serif"}}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet"/>
      <style>{`
        *{scrollbar-width:thin;scrollbar-color:#27272a transparent}
        .animate-in{animation:si .25s ease-out}
        @keyframes si{from{opacity:0;transform:translateY(6px)}to{opacity:1}}
        select option{background:#18181b}
        input[type=number]::-webkit-inner-spin-button{opacity:.3}
      `}</style>

      <header className="border-b border-zinc-800/50 bg-zinc-950/95 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-md bg-gradient-to-br from-teal-400 to-cyan-600 flex items-center justify-center text-[10px] font-extrabold text-white">H</div>
            <div>
              <h1 className="text-sm font-bold tracking-tight">HORIZON 30</h1>
              <p className="text-[9px] text-zinc-500 tracking-widest uppercase">Moteur patrimonial freelance</p>
            </div>
          </div>
          <p className="text-[10px] text-zinc-600 font-mono">{st.age}→{st.targetAge} ans • {st.targetAge-st.age} ans de runway</p>
        </div>
      </header>

      <div className="max-w-6xl mx-auto flex">
        <nav className="w-44 flex-shrink-0 border-r border-zinc-800/40 min-h-[calc(100vh-56px)] py-4 px-3 sticky top-14 self-start">
          <div className="space-y-1">
            {SECTIONS.map(s => (
              <button key={s.id} onClick={()=>setSec(s.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-2 ${
                  sec===s.id ? "bg-zinc-800/60 text-white" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/20"}`}>
                <span className="text-[10px] w-4 text-center opacity-60">{s.icon}</span>{s.label}
              </button>
            ))}
          </div>
          <div className="mt-6 space-y-2 border-t border-zinc-800/40 pt-4">
            <p className="text-[9px] text-zinc-600 uppercase tracking-widest font-semibold">Aperçu</p>
            <div className="text-[10px] space-y-1.5 text-zinc-400">
              <div className="flex justify-between"><span>CA/mois</span><span className="font-mono text-zinc-200">{fmt(st.monthlyGross)}</span></div>
              <div className="flex justify-between"><span>Enfants</span><span className="font-mono text-zinc-200">{(st.kids||[]).length}</span></div>
              <div className="flex justify-between"><span>Épargne/m</span><span className="font-mono text-teal-400">{fmt(Object.values(st.alloc||{}).reduce((s,v)=>s+v,0))}</span></div>
              <div className="flex justify-between"><span>Projets</span><span className="font-mono text-zinc-200">{(st.projects||[]).filter(p=>p.type==="invest").length}</span></div>
            </div>
          </div>
        </nav>

        <main className="flex-1 py-5 px-6 min-w-0">
          {sec==="identity" && <Identity d={st} set={set}/>}
          {sec==="revenue" && <Revenue d={st} set={set}/>}
          {sec==="expenses" && <Expenses d={st} set={set}/>}
          {sec==="life" && <Life d={st} set={set}/>}
          {sec==="savings" && <Savings d={st} set={set}/>}
          {sec==="projects" && <Projects d={st} set={set}/>}
          {sec==="runway" && <Runway d={st} set={set}/>}
        </main>
      </div>

      <footer className="border-t border-zinc-800/30 py-5 text-center">
        <p className="text-[9px] text-zinc-700 max-w-lg mx-auto">Horizon 30 est un simulateur. Ne constitue pas un conseil financier, fiscal ou juridique.</p>
      </footer>
    </div>
  );
}
