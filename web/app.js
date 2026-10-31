/* Loan Saathi UI controller.
 *
 * Dependency-free on purpose: no framework, no build step, no chart library. For one screen that
 * has to work on venue wifi, a file the browser just runs beats a toolchain.
 *
 * One rule mirrors the backend: nothing here computes a displayed figure. Every number rendered
 * below arrives from /api/*, that is, from app/engine.py. The only arithmetic in this file is
 * layout maths for the chart.
 */

'use strict';

const $  = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const state = {
  lang: 'hi',
  demo: null,
  offerLoaded: false,
  shock: 0,          // percent, positive in the UI, sent as a negative fraction
  rightsized: null,
  audio: null,
  // What produced the reply on screen. The listen button replays it with speak:true, so
  // audio is only ever synthesised when somebody actually asks to hear something. Dragging
  // the slider therefore costs nothing, and the button still works on every view.
  replay: null,
};

/* ----------------------------------------------------------------- copy */

const T = {
  hi: {
    daily: 'रोज़ की किस्त', tenure: 'अवधि', total: 'कुल चुकाना',
    listen: 'सुनें', accept: 'यह लोन लें', acceptSmall: 'छोटा लोन लें',
    wait: 'गणना कर रहा हूँ',
    avgDay: 'औसत दिन', sales: 'बिक्री', fallBy: 'अगर बिक्री घटे',
    tilesNote: 'किस्त, आपकी औसत रोज़ की सेटलमेंट के हिस्से के रूप में।',
    fSettle: 'शॉक के बाद औसत सेटलमेंट',
    fCushion: 'किस्त कटने के बाद रोज़ बचत',
    fDays: (n) => `पिछले ${n} दिनों में कम पड़ने वाले दिन`,
    fShort: 'कुल कमी',
    original: 'मौजूदा ऑफ़र', suggested: 'सुझाया गया',
    perDay: '/दिन', less: 'रोज़ कम',
    rsSafe: 'यह ऑफ़र पहले से सुरक्षित सीमा में है।',
    cOk: 'सब ठीक है', cWatch: 'नज़र रखें', cWarn: 'सावधान', cAct: 'कार्रवाई ज़रूरी',
    belowBase: 'बेसलाइन से नीचे',
    pinTitle: 'ऐप में पुष्टि करें',
    pinCopy: 'लेंडर को अनुरोध भेजने के लिए अपना Paytm PIN डालें।',
    confirm: 'पुष्टि करें', cancel: 'रद्द करें',
    badPin: 'PIN ग़लत है', consented: 'पुष्टि दर्ज हो गई',
    rsBtn: 'छोटा लोन सुझाएँ',
    chips: ['अगर बिक्री 30% गिरी तो?', 'छोटा लोन सुझाओ', 'कुल कितना चुकाना है?', 'मेरा कारोबार कैसा चल रहा है?'],
    askPh: 'हिंदी में पूछें',
    readDoc: 'डॉक्यूमेंट पढ़ें', reading: 'पढ़ रहा हूँ...', docDone: 'डॉक्यूमेंट पढ़ लिया',
    failTimes: 'बार किस्त नहीं कट पाएगी', over: 'दिनों में',
    shut: 'दुकान बंद होने पर कम पड़ी', tradingDays: 'खुली दुकान में कम पड़ी',
    penalty: 'संभावित जुर्माना', headroom: 'इतने तक का लोन सुरक्षित',
    rhythmTitle: 'आपके हफ़्ते की चाल, आपके ही 90 दिनों से सीखी गई',
    listening: 'सुन रहा हूँ, रोकने के लिए दबाएँ',
    noMic: 'माइक उपलब्ध नहीं, टाइप करके पूछें',
    noStt: 'आवाज़ समझ नहीं पाया, टाइप करके पूछें',
    noAudio: 'ऑडियो उपलब्ध नहीं',
  },
  en: {
    daily: 'Daily', tenure: 'Tenure', total: 'Total payable',
    listen: 'Listen', accept: 'Take this loan', acceptSmall: 'Take the smaller loan',
    wait: 'Running the numbers',
    avgDay: 'Average day', sales: 'Sales', fallBy: 'If sales fall',
    tilesNote: 'The installment as a share of your average daily settlement.',
    fSettle: 'Average settlement after the shock',
    fCushion: 'Left per day after the debit',
    fDays: (n) => `Days short, in your last ${n}`,
    fShort: 'Total shortfall',
    original: 'Current offer', suggested: 'Suggested',
    perDay: '/day', less: 'less per day',
    rsSafe: 'This offer is already within the safe limit.',
    cOk: 'All steady', cWatch: 'Keep watching', cWarn: 'Caution', cAct: 'Action needed',
    belowBase: 'below baseline',
    pinTitle: 'Confirm in the app',
    pinCopy: 'Enter your Paytm PIN to send this request to the lender.',
    confirm: 'Confirm', cancel: 'Cancel',
    badPin: 'Incorrect PIN', consented: 'Consent recorded',
    rsBtn: 'Suggest a smaller loan',
    chips: ['What if sales drop 30%?', 'Suggest a smaller loan', 'What is the total payable?', 'How is my business doing?'],
    askPh: 'Ask in English',
    readDoc: 'Read document', reading: 'Reading...', docDone: 'Document read',
    failTimes: 'failed auto-debits predicted', over: 'over',
    shut: 'failures on shop-closed days', tradingDays: 'failures on open-shop days',
    penalty: 'likely penalties', headroom: 'safe to borrow up to',
    rhythmTitle: 'Your weekly rhythm, learned from your own 90 days',
    listening: 'Listening, tap to stop',
    noMic: 'Microphone unavailable, type instead',
    noStt: 'Could not hear that, type instead',
    noAudio: 'Audio unavailable',
  },
};

const t = () => T[state.lang];

/* ----------------------------------------------------------------- helpers */

/** Indian digit grouping: 1,26,000 rather than 126,000. */
function inr(n) {
  if (n === null || n === undefined) return '';
  const v = Math.round(Math.abs(n));
  const s = String(v);
  let body;
  if (s.length <= 3) {
    body = s;
  } else {
    const tail = s.slice(-3);
    let head = s.slice(0, -3);
    const pairs = [];
    while (head.length > 2) { pairs.unshift(head.slice(-2)); head = head.slice(0, -2); }
    if (head) pairs.unshift(head);
    body = pairs.join(',') + ',' + tail;
  }
  return (n < 0 ? '-' : '') + '₹' + body;
}

const icon = (id, cls = 'i') => `<svg class="${cls}"><use href="#${id}"/></svg>`;

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || j.error || msg; } catch { /* keep statusText */ }
    const e = new Error(msg); e.status = res.status; throw e;
  }
  return res.json();
}

const postJson = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

function snack(msg) {
  const el = $('#snack');
  el.textContent = msg;
  el.classList.add('up');
  clearTimeout(snack.t);
  snack.t = setTimeout(() => el.classList.remove('up'), 2600);
}

/** How we colour a burden figure. A presentation choice, not a judgement about the loan. */
function level(pct) {
  if (pct < 15) return 'lo';
  if (pct < 20) return 'md';
  return 'hi';
}

/* ----------------------------------------------------------------- narration */

function showReply(payload, { speak = false, replay = null } = {}) {
  if (replay) state.replay = replay;
  const say = $('#say');
  say.textContent = payload.text;
  say.classList.remove('wait');
  $('#sb-say').textContent = payload.text;

  const tag = $('#tag-src');
  tag.textContent = 'Loan Saathi assistant';
  tag.classList.remove('llm');

  state.audio = payload.audio || null;
  // Enabled whenever we know how to re-fetch the audio, even if we have not fetched it yet.
  $('#btn-play').disabled = !(state.audio || state.replay);
  if (speak && state.audio) play();
}

function waiting() {
  const say = $('#say');
  say.textContent = t().wait;
  say.classList.add('wait');
}

async function play() {
  // No audio yet for this view: ask the server for it now, then play. This is the only path
  // that triggers text-to-speech, and the result is cached by content hash server-side.
  if (!state.audio && state.replay) {
    const btn = $('#btn-play');
    btn.disabled = true;
    try {
      const out = await api(state.replay.path, postJson({ ...state.replay.body, speak: true }));
      state.audio = out.audio || null;
    } catch {
      /* fall through to the snack below */
    }
    btn.disabled = false;
  }
  if (!state.audio) { snack(t().noAudio); return; }
  const p = $('#player');
  p.src = state.audio;
  $('#sbox').classList.add('on');
  p.onended = () => $('#sbox').classList.remove('on');
  p.play().catch(() => $('#sbox').classList.remove('on'));
}

/* ----------------------------------------------------------------- offer */

function drawOffer() {
  const o = state.rightsized || (state.offerLoaded ? state.demo.offer : null);
  const m = state.demo.merchant;

  $('#m-name').textContent = m.name;
  $('#m-meta').textContent = m.category + ', ' + m.city;

  $('#o-amount').textContent = o ? inr(o.loan_amount) : 'Upload your offer';
  $('#o-lender').textContent = o ? state.demo.offer.lender_name : 'Add a loan document to begin';
  $('#o-daily').textContent = o ? inr(o.daily_installment) : '—';
  $('#o-tenure').textContent = o ? o.tenor_days + 'd' : '—';
  $('#o-total').textContent = o ? inr(o.total_payable) : '—';

  $('#l-daily').textContent = t().daily;
  $('#l-tenure').textContent = t().tenure;
  $('#l-total').textContent = t().total;
  $('#key-emi').textContent = o ? inr(o.daily_installment) : '—';

  $('#btn-accept-t').textContent = state.rightsized ? t().acceptSmall : t().accept;
}

/* ----------------------------------------------------------------- tiles */

/** The three figures from slide 6 of the deck. Values come from /api/simulate. */
function drawTiles(byShock) {
  const rows = [
    { pct: 0,  label: t().avgDay },
    { pct: 30, label: t().sales + ' 30%' },
    { pct: 50, label: t().sales + ' 50%' },
  ];
  const baseline = byShock[0] ? byShock[0].burden_pct : null;

  $('#tiles').innerHTML = rows.map(({ pct, label }) => {
    const s = byShock[pct];
    if (!s) return '';
    const on = Math.abs(state.shock - pct) < 0.01 ? ' on' : '';
    // Track fills at 30% burden. Purely visual scaling.
    const w = Math.min(100, (s.burden_pct / 30) * 100);
    const delta = (baseline !== null && pct > 0)
      ? '+' + (s.burden_pct - baseline).toFixed(1) + ' pts'
      : inr(s.installment) + t().perDay;
    return `
      <div class="tile ${level(s.burden_pct)}${on}">
        <div class="tile-k">${label}</div>
        <div class="tile-v num">${s.burden_pct}%</div>
        <div class="tile-s num">${delta}</div>
        <div class="tile-track"><span style="width:${w}%"></span></div>
      </div>`;
  }).join('');

}

/* ----------------------------------------------------------------- figures */

function drawFigs(sim) {
  const short = sim.shortfall_days > 0;
  const cells = [
    { k: t().fSettle,                  v: inr(sim.shocked_avg) },
    { k: t().fCushion,                 v: inr(sim.daily_cushion) },
    { k: t().fDays(sim.shock_days),    v: String(sim.shortfall_days), bad: short },
    { k: t().fShort,                   v: inr(sim.cumulative_shortfall), bad: short },
  ];
  $('#figs').innerHTML = cells.map((c) => `
    <div class="fig${c.bad ? ' bad' : ''}">
      <div class="fig-k">${c.k}</div>
      <div class="fig-v num">${c.v}</div>
    </div>`).join('');
}

/* ----------------------------------------------------------------- chart */

/** Hand-rolled SVG: 90 settlement bars plus the installment line. No chart library. */
function drawChart(shockPct) {
  const daily = state.demo.settlements.daily;
  const emi = (state.rightsized || state.demo.offer).daily_installment;
  const W = 720, H = 150, gap = 1.3;
  const bw = (W - gap * (daily.length - 1)) / daily.length;

  const shocked = daily.map((d) => d * (1 - shockPct / 100));
  // Scale is pinned to the unshocked maximum so bars visibly shrink as the shock deepens,
  // instead of the chart rescaling and hiding the effect.
  const ceiling = Math.max(...daily, emi) * 1.06;
  const y = (v) => H - (v / ceiling) * H;

  const grid = [0.5, 1].map((f) =>
    `<line x1="0" x2="${W}" y1="${y(ceiling * f).toFixed(2)}" y2="${y(ceiling * f).toFixed(2)}" `
    + `stroke="#eef1f6" stroke-width="1"/>`).join('');

  const bars = shocked.map((v, i) => {
    const x = i * (bw + gap);
    const h = Math.max(1.5, H - y(v));
    const miss = v < emi;
    return `<rect x="${x.toFixed(2)}" y="${(H - h).toFixed(2)}" width="${bw.toFixed(2)}" `
         + `height="${h.toFixed(2)}" rx="0.7" fill="${miss ? '#c2780c' : '#00baf2'}" `
         + `opacity="${miss ? 1 : 0.88}"/>`;
  }).join('');

  const ey = y(emi).toFixed(2);
  $('#chart').innerHTML = grid + bars
    + `<line x1="0" x2="${W}" y1="${ey}" y2="${ey}" stroke="#c9362c" stroke-width="1.4" stroke-dasharray="4 3"/>`;

  $('#ax-hi').textContent = inr(ceiling);
  $('#ax-mid').textContent = inr(ceiling / 2);
}

function markPreset(pct) {
  $$('#presets button').forEach((b) => {
    b.setAttribute('aria-pressed', String(Number(b.dataset.pct) === pct));
  });
}

/* ----------------------------------------------------------------- actions */

async function boot() {
  state.demo = await api('/api/demo');
  state.offerLoaded = Boolean(state.demo.offer_loaded);
  drawOffer();
  drawKfs();
  drawChips();
  $('#ask').placeholder = t().askPh;
  if (!state.demo.voice_enabled) $('#btn-mic').title = t().noMic;
  if (state.offerLoaded) {
    setOfferControls(true);
    await runShock(0, { speak: false, mode: 'explain' });
    loadRisk();
  } else {
    docBox('', 'Upload your loan offer or Key Facts Statement. Loan Saathi reads only the loan terms; your existing 90-day sales history is already connected and will stay in use.');
    $('#say').textContent = 'Upload a loan document to get started.';
    $('#say').classList.remove('wait');
    setOfferControls(false);
  }
}

function setOfferControls(enabled) {
  ['#btn-accept', '#btn-rs', '#btn-coach', '#shock', '#btn-play'].forEach((selector) => {
    const element = $(selector);
    if (element) element.disabled = !enabled;
  });
}

async function loadTiles() {
  // narrate:false keeps these three calls numbers-only. With a Sarvam key set they would
  // otherwise run an LLM pass and a TTS render for text that is never shown or played.
  const [a, b, c] = await Promise.all([
    api('/api/simulate', postJson({ shock_pct: 0,    shock_days: 30, lang: state.lang, narrate: false })),
    api('/api/simulate', postJson({ shock_pct: -0.3, shock_days: 30, lang: state.lang, narrate: false })),
    api('/api/simulate', postJson({ shock_pct: -0.5, shock_days: 30, lang: state.lang, narrate: false })),
  ]);
  drawTiles({ 0: a.numbers, 30: b.numbers, 50: c.numbers });
}

async function runShock(pct, { speak = true, mode = 'auto' } = {}) {
  state.shock = pct;
  $('#shock-out').textContent = pct + '%';
  $('#shock').value = pct;
  markPreset(pct);
  drawChart(pct);
  waiting();

  try {
    // speak:false on every automatic render. The listen button fetches audio on demand.
    const isOpening = pct === 0 && mode === 'explain';
    const replay = isOpening
      ? { path: '/api/explain', body: { lang: state.lang } }
      : { path: '/api/simulate', body: { shock_pct: -pct / 100, shock_days: 30, lang: state.lang } };
    const out = await api(replay.path, postJson({ ...replay.body, speak: false }));
    drawFigs(out.numbers);
    showReply(out, { speak: false, replay });
    loadRisk(pct);
    if (speak) play();
    await loadTiles();
  } catch (err) {
    $('#say').textContent = err.message;
    $('#say').classList.remove('wait');
  }
}

async function runRightsize(speak = true) {
  waiting();
  const body = {
    shock_pct: -0.30,
    ceiling: state.demo.assumptions.rightsize_ceiling_pct / 100,
    lang: state.lang,
  };
  const out = await api('/api/rightsize', postJson({ ...body, speak }));
  showReply(out, { speak, replay: { path: '/api/rightsize', body } });

  const rs = out.numbers;
  if (!rs.changed) {
    $('#rs-out').innerHTML = `<div class="notice good">${icon('i-check')}
      <div><div class="notice-t">${t().rsSafe}</div></div></div>`;
    return;
  }

  const o = state.demo.offer;
  $('#rs-out').innerHTML = `
    <div class="cmp">
      <div class="cmp-c">
        <div class="cmp-k">${t().original}</div>
        <div class="cmp-v num">${inr(o.loan_amount)}</div>
        <div class="cmp-s num">${inr(o.daily_installment)}${t().perDay}</div>
      </div>
      <div class="cmp-ar">${icon('i-arrow')}</div>
      <div class="cmp-c pick">
        <div class="cmp-k">${t().suggested}</div>
        <div class="cmp-v num">${inr(rs.loan_amount)}</div>
        <div class="cmp-s num">${inr(rs.daily_installment)}${t().perDay}, ${inr(rs.saved_per_day)} ${t().less}</div>
      </div>
    </div>
    <p class="footnote inline">
      Burden at a 30% fall in sales drops to <strong class="num">${rs.burden_pct}%</strong>, under the
      <strong class="num">${rs.ceiling_pct}%</strong> comfort ceiling. That ceiling is our demo
      assumption, not a Paytm or lender rule.
    </p>`;

  // Swap the phone's offer card so the merchant decides on the new numbers.
  state.rightsized = {
    loan_amount: rs.loan_amount,
    daily_installment: rs.daily_installment,
    tenor_days: rs.tenor_days,
    total_payable: rs.total_payable,
  };
  drawOffer();
  drawChart(state.shock);
  $('#btn-reset').hidden = false;
}

async function runCoach(speak = true) {
  waiting();
  const out = await api('/api/coach?lang=' + state.lang + '&speak=' + speak);
  showReply(out, { speak, replay: { path: '/api/ask', body: { text: 'coach', lang: state.lang } } });

  const c = out.numbers;
  const label = { ok: t().cOk, watch: t().cWatch, warn: t().cWarn, act: t().cAct }[c.tier];
  const ic    = { ok: 'i-check', watch: 'i-eye', warn: 'i-alert', act: 'i-alert' }[c.tier];
  const cls   = { ok: ' good', watch: '', warn: ' warn', act: ' act' }[c.tier];

  $('#coach').innerHTML = `
    <div class="notice${cls}">
      ${icon(ic)}
      <div>
        <div class="notice-t">${label}, <span class="num">${c.drop_pct}%</span> ${t().belowBase}</div>
        <div class="notice-b">
          Trailing 7 day average <strong class="num">${inr(c.last_7_avg)}</strong> against a 90 day
          baseline of <strong class="num">${inr(c.baseline_avg)}</strong>. The installment is now
          <strong class="num">${c.burden_now_pct}%</strong> of daily takings.
          ${c.handoff_suggested
            ? '<br><strong>A restructuring request has been routed to a support specialist.</strong>'
            : ''}
        </div>
      </div>
    </div>`;

}

/* ----------------------------------------------------------------- consent */

function openPin() {
  $('#pin-err').textContent = '';
  $$('#pin-modal input').forEach((i) => { i.value = ''; });
  $('#pin-modal').hidden = false;
  $$('#pin-modal input')[0].focus();
}

async function sendPin() {
  const pin = $$('#pin-modal input').map((i) => i.value).join('');
  if (pin.length < 4) { $('#pin-err').textContent = t().badPin; return; }

  const o = state.rightsized || state.demo.offer;
  try {
    const out = await api('/api/confirm', postJson({
      pin, loan_amount: o.loan_amount, daily_installment: o.daily_installment, lang: state.lang,
    }));
    $('#pin-modal').hidden = true;
    showReply(out, { speak: true });
    snack(t().consented);
  } catch (err) {
    $('#pin-err').textContent = err.status === 401 ? t().badPin : err.message;
    $$('#pin-modal input').forEach((i) => { i.value = ''; });
    $$('#pin-modal input')[0].focus();
  }
}

/* ----------------------------------------------------------------- ask */

async function ask(text) {
  if (!text.trim()) return;
  if (!state.offerLoaded) {
    docBox('', 'Upload your loan document first. Then you can ask about the offer, repayment, or a sales drop.');
    return;
  }
  $('#ask').value = '';
  waiting();
  const body = { text, lang: state.lang };
  const out = await api('/api/ask', postJson({ ...body, speak: true }));
  showReply(out, { speak: true, replay: { path: '/api/ask', body } });

  await syncPanel(out);
}

/** Move the data panel to match an answer that has already been rendered and spoken. */
async function syncPanel(out) {
  if (out.intent === 'shock' && out.numbers && out.numbers.shock_pct !== undefined) {
    const pct = Math.round(Math.abs(out.numbers.shock_pct * 100));
    state.shock = pct;
    $('#shock').value = pct;
    $('#shock-out').textContent = pct + '%';
    markPreset(pct);
    drawChart(pct);
    drawFigs(out.numbers);
    loadRisk(pct);
    // The panel that moved is below the fold now that the forecast sits on top, so bring it
    // into view. Otherwise an answered question looks like nothing happened.
    document.querySelector('.right').scrollTo({ top: $('#risk-sec').offsetHeight - 40,
                                                behavior: 'smooth' });
    await loadTiles();
  } else if (out.intent === 'rightsize') {
    await runRightsize();
  } else if (out.intent === 'coach') {
    await runCoach();
  }
}

/* Voice is optional by design. Any failure routes the merchant to the text box. */
const rec = { mr: null, chunks: [] };

/** Re-encode recorded audio as 16 kHz mono 16-bit WAV.
 *
 * MediaRecorder produces a streaming WebM container with no duration in its header, which
 * Sarvam's transcriber rejects. Decoding it here and emitting a plain WAV removes the
 * ambiguity entirely: WAV is the format the endpoint is known to accept.
 */
async function toWav(blob) {
  const RATE = 16000;
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
  ctx.close();

  const frames = Math.max(1, Math.round(decoded.duration * RATE));
  const off = new OfflineAudioContext(1, frames, RATE);
  const src = off.createBufferSource();
  src.buffer = decoded;
  src.connect(off.destination);
  src.start();
  const pcm = (await off.startRendering()).getChannelData(0);

  const bytes = new ArrayBuffer(44 + pcm.length * 2);
  const dv = new DataView(bytes);
  const ascii = (off_, str) => {
    for (let i = 0; i < str.length; i++) dv.setUint8(off_ + i, str.charCodeAt(i));
  };
  ascii(0, 'RIFF');
  dv.setUint32(4, 36 + pcm.length * 2, true);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  dv.setUint32(16, 16, true);          // PCM header size
  dv.setUint16(20, 1, true);           // format: PCM
  dv.setUint16(22, 1, true);           // channels: mono
  dv.setUint32(24, RATE, true);
  dv.setUint32(28, RATE * 2, true);    // byte rate
  dv.setUint16(32, 2, true);           // block align
  dv.setUint16(34, 16, true);          // bits per sample
  ascii(36, 'data');
  dv.setUint32(40, pcm.length * 2, true);

  let o = 44;
  for (let i = 0; i < pcm.length; i++, o += 2) {
    const v = Math.max(-1, Math.min(1, pcm[i]));
    dv.setInt16(o, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  return new Blob([bytes], { type: 'audio/wav' });
}

async function toggleMic() {
  if (rec.mr && rec.mr.state === 'recording') { rec.mr.stop(); return; }
  if (!navigator.mediaDevices || !window.MediaRecorder) { snack(t().noMic); return; }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    snack(t().noMic);
    return;
  }

  rec.chunks = [];
  rec.mr = new MediaRecorder(stream);
  rec.mr.ondataavailable = (e) => rec.chunks.push(e.data);

  rec.mr.onstop = async () => {
    stream.getTracks().forEach((tr) => tr.stop());
    $('#btn-mic').classList.remove('live');
    $('#btn-mic').innerHTML = icon('i-mic');

    waiting();
    try {
      const raw = new Blob(rec.chunks, { type: rec.mr.mimeType || 'audio/webm' });
      const wav = await toWav(raw);

      const form = new FormData();
      form.append('audio', wav, 'clip.wav');
      form.append('lang', state.lang);

      const res = await fetch('/api/voice/ask', { method: 'POST', body: form });
      if (!res.ok) throw new Error('stt');
      const out = await res.json();
      $('#ask').value = out.transcript || '';
      showReply(out, { speak: true, replay: { path: '/api/ask', body: { text: out.transcript, lang: state.lang } } });
      // Sync the panel from THIS response. Re-posting the transcript to /api/ask would run
      // the whole thing twice and restart the audio mid-sentence on the hero beat.
      await syncPanel(out);
    } catch {
      $('#say').textContent = t().noStt;
      $('#say').classList.remove('wait');
      snack(t().noStt);
    }
  };

  rec.mr.start();
  $('#btn-mic').classList.add('live');
  $('#btn-mic').innerHTML = icon('i-stop');
  snack(t().listening);
}

/* ----------------------------------------------------------------- static */

function drawKfs() {
  const hi = state.lang === 'hi';
  $('#kfs').innerHTML = state.offerLoaded
    ? state.demo.offer.kfs
      .map((r) => `<tr><td>${hi ? r.label_hi : r.label}</td><td class="num">${r.value}</td></tr>`)
      .join('')
    : '<tr><td colspan="2" class="kfs-empty">Upload a loan document to view its key facts.</td></tr>';
}

function drawChips() {
  $('#chips').innerHTML = t().chips.map((c) => `<button class="chip">${c}</button>`).join('');
  $$('#chips .chip').forEach((b) => {
    b.onclick = () => ask(b.textContent).catch((e) => snack(e.message));
  });
}

async function setLang(lang) {
  state.lang = lang;
  $('#lang-hi').setAttribute('aria-pressed', String(lang === 'hi'));
  $('#lang-en').setAttribute('aria-pressed', String(lang === 'en'));
  document.documentElement.lang = lang;

  $('#btn-play-t').textContent = t().listen;
  $('#ask').placeholder = t().askPh;
  $('#pin-h').textContent = t().pinTitle;
  $('#pin-copy').textContent = t().pinCopy;
  $('#pin-ok').textContent = t().confirm;
  $('#pin-cancel').textContent = t().cancel;
  $('#btn-rs').textContent = t().rsBtn;
  $('#btn-doc-t').textContent = t().readDoc;

  drawOffer();
  drawKfs();
  drawChips();
  if (!state.offerLoaded) return;
  loadRisk();
  await runShock(state.shock, { speak: false, mode: state.shock === 0 ? 'explain' : 'auto' });
}

/* ----------------------------------------------------------------- wiring */

$('#shock').addEventListener('input', (e) => {
  // Repaint the chart live while dragging, call the API only once the drag settles.
  state.shock = Number(e.target.value);
  $('#shock-out').textContent = state.shock + '%';
  markPreset(state.shock);
  drawChart(state.shock);
});

$$('#presets button').forEach((b) => {
  b.onclick = () => runShock(Number(b.dataset.pct));
});
$('#shock').addEventListener('change', (e) => runShock(Number(e.target.value)));

$('#btn-play').onclick = play;
$('#btn-rs').onclick = () => runRightsize().catch((e) => snack(e.message));
$('#btn-coach').onclick = () => runCoach().catch((e) => snack(e.message));
$('#btn-accept').onclick = openPin;
$('#btn-mic').onclick = () => toggleMic();
$('#pin-ok').onclick = () => sendPin();
$('#pin-cancel').onclick = () => { $('#pin-modal').hidden = true; };
$('#lang-hi').onclick = () => setLang('hi');
$('#lang-en').onclick = () => setLang('en');

$('#btn-reset').onclick = async () => {
  state.rightsized = null;
  $('#rs-out').innerHTML = '';
  $('#btn-reset').hidden = true;
  drawOffer();
  await runShock(state.shock, { speak: false });
};

$('#ask').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') ask(e.target.value).catch((err) => snack(err.message));
});

// PIN boxes: advance on entry, backspace to the previous box, Enter submits.
$$('#pin-modal input').forEach((input, i, all) => {
  input.addEventListener('input', () => {
    input.value = input.value.replace(/\D/g, '');
    if (input.value && i < all.length - 1) all[i + 1].focus();
    if (all.every((x) => x.value)) sendPin();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !input.value && i > 0) all[i - 1].focus();
    if (e.key === 'Enter') sendPin();
  });
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') $('#pin-modal').hidden = true;
});

boot().catch((err) => {
  $('#say').textContent = err.message;
  $('#say').classList.remove('wait');
});

/* ----------------------------------------------------------------- document reading
 *
 * The step a calculator cannot do: hand it the lender's Key Fact Statement and let Sarvam's
 * document model find the terms. Everything after it is the same deterministic engine.
 * The extracted fields are shown on screen deliberately, so the AI step is visible rather
 * than absorbed silently, and so a wrong read is obvious instead of quietly driving the maths.
 */

function docBox(cls, html) {
  $('#doc-status').innerHTML = `<div class="docbox ${cls}">${html}</div>`;
}

async function readDocument(file) {
  const label = $('#btn-doc-t').textContent;
  $('#btn-doc').disabled = true;
  $$('[data-upload]').forEach((button) => { button.disabled = true; });
  $('#btn-doc-t').textContent = t().reading;
  docBox('', `<span class="spin"></span>Sarvam Doc AI is reading <b>${file.name}</b>.
              This takes a few seconds.`);
  waiting();

  try {
    const form = new FormData();
    form.append('file', file, file.name);
    const res = await fetch('/api/document', { method: 'POST', body: form });
    const out = await res.json();

    if (!out.ok) {
      docBox('err', `Could not use this document: <b>${out.reason}</b><br>
                     Please upload a valid loan offer or Key Facts Statement.`);
      return;
    }

    const o = out.offer;
    const fields = [
      [t().daily, inr(o.daily_installment)],
      [t().tenure, o.tenor_days + 'd'],
      [t().total, inr(o.total_payable)],
      ['Rate', o.interest_rate_pa + '%'],
      ['Fee', inr(o.processing_fee)],
    ];
    docBox('ok', `Read from <b>${file.name}</b> by Sarvam Doc AI
        (${o.pages_read || 1} page). Lender: <b>${o.lender_name}</b>.
        Loan terms came from the document; your existing 90-day sales history remains the basis for the personalised calculations.
        <div class="docfields">${fields.map(([k, v]) =>
          `<div class="docfield"><div class="k">${k}</div><div class="v num">${v}</div></div>`
        ).join('')}</div>`);

    // The offer on the server has changed, so re-read everything from it.
    state.demo = await api('/api/demo');
    state.offerLoaded = true;
    setOfferControls(true);
    state.rightsized = null;
    $('#btn-reset').hidden = true;
    $('#rs-out').innerHTML = '';
    drawOffer();
    drawKfs();
    await runShock(0, { speak: false, mode: 'explain' });
    loadRisk();          // the document changed the terms, so re-predict
    snack(t().docDone);
  } catch (err) {
    docBox('err', `Could not read the document: ${err.message}. Your sales history is unchanged. Please try again.`);
  } finally {
    $('#btn-doc').disabled = false;
    $$('[data-upload]').forEach((button) => { button.disabled = false; });
    $('#btn-doc-t').textContent = label;
  }
}

$('[data-upload]').onclick = () => $('#doc-file').click();
$('#btn-doc').onclick = () => $('#doc-file').click();
$('#doc-file').onchange = (e) => {
  const f = e.target.files && e.target.files[0];
  e.target.value = '';                 // so re-picking the same file fires again
  if (f) readDocument(f);
};


/* ----------------------------------------------------------------- risk forecast
 *
 * The part of the page where a model, rather than a division, produces the answer. The
 * learned weekday rhythm is drawn deliberately: it is the visible evidence that something
 * was fitted to this merchant's history instead of assumed.
 */

const DAYS_SHORT = {
  hi: ['सोम', 'मंगल', 'बुध', 'गुरु', 'शुक्र', 'शनि', 'रवि'],
  en: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
};

async function loadRisk(shockPct = state.shock) {
  // The prediction answers the scenario currently on screen, so asking "what if sales fall
  // 30%" moves the headline number too. Without this the top of the page sits still while
  // the panels below it change, which reads as the app being broken.
  try {
    const r = await api(`/api/risk?lang=${state.lang}&speak=false&shock_pct=${-shockPct / 100}`);
    drawRisk(r);
  } catch (err) {
    $('#risk-body').innerHTML = `<div class="docbox err">${err.message}</div>`;
  }
}

function drawRisk(r) {
  const n = r.numbers;
  const total = Math.max(n.expected_miss_days, 0.01);
  const closurePct = (n.closure_miss_days / total) * 100;
  const tradingPct = (n.trading_miss_days / total) * 100;

  const factors = r.profile.weekday_factor;
  const peak = Math.max(...factors);
  const rhythm = factors.map((f, i) => `
    <div>
      <div class="track"><div class="fill${f === peak ? ' hi' : ''}"
           style="height:${Math.round((f / peak) * 100)}%"></div></div>
      <div class="d">${DAYS_SHORT[state.lang][i]}</div>
      <div class="f num">${f.toFixed(2)}</div>
    </div>`).join('');

  const scenario = n.sales_shock_pct
    ? `<span class="scen">${t().sales} -${n.sales_shock_pct}%</span>` : '';

  $('#risk-body').innerHTML = `
    ${scenario}
    <div class="risk-head">
      <div class="risk-big ${n.risk_band}">
        <div class="n num">${n.expected_miss_days}</div>
        <div class="u">${t().failTimes} ${t().over} ${n.horizon_days} ${state.lang === 'hi' ? '' : 'days'}</div>
      </div>
      <div class="risk-split">
        <div class="risk-bar">
          <i class="closure" style="width:${closurePct}%"></i>
          <i class="trading" style="width:${tradingPct}%"></i>
        </div>
        <div class="risk-legend">
          <span title="Predicted instalment shortfalls caused by shop closures">
            <i style="background:#c2780c"></i>${n.closure_miss_days} ${t().shut}</span>
          <span title="Predicted instalment shortfalls while the shop is trading">
            <i style="background:#c9362c"></i>${n.trading_miss_days} ${t().tradingDays}</span>
        </div>
        <div class="figs" style="margin-top:12px;grid-template-columns:repeat(2,minmax(0,1fr))">
          <div class="fig"><div class="fig-k">${t().penalty}</div>
            <div class="fig-v num">${inr(n.expected_penalty)}</div></div>
          <div class="fig"><div class="fig-k">${t().headroom}</div>
            <div class="fig-v num">${inr(r.safe.headroom_amount)}</div></div>
        </div>
      </div>
    </div>

    <div class="risk-why">
      <span class="src">Personalised repayment view</span>
      ${r.text}
    </div>

    <div class="footnote inline" style="margin-top:16px;padding-top:12px">
      ${t().rhythmTitle}
      <div class="rhythm">${rhythm}</div>
    </div>`;
}
