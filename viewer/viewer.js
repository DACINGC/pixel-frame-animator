'use strict';

/* 帧动画浏览器 —— 依赖 viewer 目录下的 scan.py / serve.py */

const $ = (id) => document.getElementById(id);
const ALL = '__all__';

const state = {
  data: null,
  server: false,          // 是否运行在本地服务下（决定能否重新扫描 / 导出 GIF）
  set: null,
  viewList: [],           // 当前动作过滤后的帧下标（指向 set.frames）
  idx: 0,
  clip: ALL,
  playing: false,
  fps: 12,
  zoom: 0,                // 0 = 适应窗口
  bg: 'checker',
  loop: true,
  ping: false,
  onion: false,
  grid: false,
  view: 'player',
  dir: 1,
  imgs: [],
  sheetImg: null,
  hideArchive: true,
  hideDupes: true,      // 内容重复的只留一个
  hideOld: true,        // -rN 迭代版本只留最新
  expanded: new Set(),  // 被点开「+N」的代表项 id
  query: '',
};

const canvas = $('stage');
const ctx = canvas.getContext('2d');

/* ---------------- 数据 ---------------- */

function fileUrl(rel) {
  if (state.server) return '/files/' + rel.split('/').map(encodeURIComponent).join('/');
  return '../' + rel;   // file:// 兜底：index.html 位于 <root>/viewer/
}

async function loadData(opts = {}) {
  const wantArchive = !state.hideArchive;
  try {
    const res = await fetch(`/api/scan?archive=${wantArchive ? 1 : 0}`, { cache: 'no-store' });
    if (!res.ok) throw new Error('bad status');
    state.data = await res.json();
    state.server = true;
  } catch (err) {
    state.data = window.PFA_STATIC_DATA || null;
    state.server = false;
  }
  if (!state.data) {
    $('emptyHint').textContent = '没有拿到索引数据，请在 viewer 目录运行：python serve.py';
    return;
  }
  renderStat();
  if (!state.server) $('refreshBtn').title = '离线模式：需重新运行 scan.py --static';
  renderTree();
  // 保留当前选中项；没有则选第一个可见项
  const wanted = decodeURIComponent((location.hash || '').replace(/^#/, ''));
  const current = state.set && state.data.sets.some(s => s.id === state.set.id) && !opts.reselect
    ? state.set.id : null;
  const first = filteredSets()[0];
  selectSet(current || (wanted && state.data.sets.some(s => s.id === wanted) ? wanted : (first ? first.id : null)));
}

function renderStat() {
  const d = state.data;
  const shown = filteredSets().length;
  $('stat').textContent = `显示 ${shown} / ${d.setCount} 个动画集 · ${d.frameCount} 帧`
    + (d.dupCount || d.oldCount ? ` · 已折叠重复 ${d.dupCount} / 旧版本 ${d.oldCount}` : '')
    + ' · ' + (state.server ? '实时扫描' : '静态索引（运行 serve.py 可实时刷新）');
}

/* 返回该动画集被隐藏的原因，null 表示要显示 */
function hiddenReason(s) {
  if (state.hideArchive && /(^|\/)_/.test(s.dir)) return 'archive';
  if (state.hideDupes && s.isDup && !state.expanded.has(s.dupOf)) return 'dup';
  if (state.hideOld && s.supersededBy && !state.expanded.has(s.supersededBy)) return 'old';
  return null;
}

function matchQuery(s, q) {
  if (!q) return true;
  const hay = [s.dir, s.name, s.title || '', s.projectId || '', ...s.clips.map(c => c.name)]
    .join(' ').toLowerCase();
  return hay.includes(q);
}

function filteredSets() {
  const q = state.query.trim().toLowerCase();
  return (state.data?.sets || []).filter(s => !hiddenReason(s) && matchQuery(s, q));
}

/* 某个代表项底下折叠了多少个（重复 + 旧版本） */
function hiddenFollowers(s) {
  const all = state.data?.sets || [];
  return all.filter(x => x !== s && (
    (state.hideDupes && x.isDup && x.dupOf === s.id) ||
    (state.hideOld && x.supersededBy === s.id)
  )).length;
}

/* ---------------- 侧边栏资源树 ---------------- */

function buildTree(sets) {
  const root = { name: '', children: new Map(), sets: [], frames: 0 };
  for (const s of sets) {
    const parts = s.dir.split('/');
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const key = parts[i];
      if (!node.children.has(key)) node.children.set(key, { name: key, children: new Map(), sets: [], frames: 0 });
      node = node.children.get(key);
      node.frames += s.frameCount;
    }
    node.sets.push(s);
    node.frames += s.frameCount;
  }
  root.frames = sets.reduce((a, s) => a + s.frameCount, 0);
  return root;
}

function renderTree() {
  const tree = $('tree');
  tree.innerHTML = '';
  const sets = filteredSets();
  if (!sets.length) {
    tree.innerHTML = '<div class="dim small" style="padding:8px">没有匹配的动画集</div>';
    return;
  }
  const root = buildTree(sets);
  // 顶层用扫描根目录名做标题
  tree.appendChild(folderRow(state.data.rootName || '根目录', root.frames, true));
  const box = document.createElement('div');
  box.className = 'tree-children';
  box.appendChild(nodeEl(root));
  tree.appendChild(box);
}

function folderRow(name, count, open) {
  const row = document.createElement('div');
  row.className = 'tree-row folder';
  row.innerHTML = `<span class="caret">${open ? '▾' : '▸'}</span><span>${name}</span>`
    + (count ? `<span class="tree-count">${count}</span>` : '');
  return row;
}

function nodeEl(node) {
  const wrap = document.createElement('div');
  wrap.className = 'tree-node';

  for (const child of node.children.values()) {
    const block = document.createElement('div');
    const row = folderRow(child.name, child.frames, true);
    const kids = document.createElement('div');
    kids.className = 'tree-children';
    kids.appendChild(nodeEl(child));
    row.addEventListener('click', () => {
      kids.classList.toggle('collapsed');
      row.querySelector('.caret').textContent = kids.classList.contains('collapsed') ? '▸' : '▾';
    });
    block.appendChild(row);
    block.appendChild(kids);
    wrap.appendChild(block);
  }

  for (const s of node.sets) wrap.appendChild(leafEl(s));
  return wrap;
}

function leafEl(s) {
  const row = document.createElement('div');
  row.className = 'tree-row leaf';
  row.dataset.id = s.id;
  if (state.set && state.set.id === s.id) row.classList.add('selected');
  if (s.isDup || s.supersededBy) row.classList.add('is-hidden-copy');

  const img = document.createElement('img');
  img.className = 'thumb';
  img.loading = 'lazy';
  img.src = fileUrl(s.frames[0].file);

  const name = document.createElement('span');
  name.className = 'leaf-name';
  name.textContent = s.name;
  name.title = `${s.dir}  ·  ${s.frameCount} 帧`;

  const meta = document.createElement('span');
  meta.className = 'leaf-clips';
  meta.textContent = s.clips.map(c => c.name).join('/');

  const tags = document.createElement('span');
  tags.className = 'leaf-tags';
  if (s.isDup) tags.appendChild(tagEl('重复', '内容与其他动画集完全相同'));
  if (s.supersededBy) tags.appendChild(tagEl('旧版', '存在更新的迭代版本：' + s.supersededBy));

  const count = document.createElement('span');
  count.className = 'tree-count';
  count.textContent = s.frameCount;

  row.append(img, name, meta, tags, count);

  // 「+N」展开被折叠的重复/旧版本
  const n = hiddenFollowers(s);
  if (n > 0) {
    const badge = document.createElement('span');
    const open = state.expanded.has(s.id);
    badge.className = 'leaf-badge' + (open ? ' open' : '');
    badge.textContent = open ? `−${n}` : `+${n}`;
    badge.title = `展开 ${n} 个被折叠的重复 / 旧版本`;
    badge.addEventListener('click', (e) => {
      e.stopPropagation();
      if (state.expanded.has(s.id)) state.expanded.delete(s.id);
      else state.expanded.add(s.id);
      renderTree();
      renderStat();
    });
    row.appendChild(badge);
  }

  row.addEventListener('click', () => selectSet(s.id));
  return row;
}

function tagEl(text, title) {
  const el = document.createElement('i');
  el.className = 'tag';
  el.textContent = text;
  el.title = title;
  return el;
}

/* ---------------- 选择动画集 ---------------- */

function selectSet(id) {
  const set = state.data.sets.find(s => s.id === id);
  if (!set) return;
  state.set = set;
  state.clip = ALL;
  state.idx = 0;
  state.dir = 1;
  state.playing = false;
  state.imgs = set.frames.map(f => {
    const im = new Image();
    im.onload = () => { if (state.set === set && currentFrame() === f) draw(); };
    im.src = fileUrl(f.file);
    return im;
  });
  state.sheetImg = set.sheet ? Object.assign(new Image(), { src: fileUrl(set.sheet.file) }) : null;

  location.hash = encodeURIComponent(id);
  $('empty').hidden = true;
  $('workspace').hidden = false;

  document.querySelectorAll('.tree-row.leaf').forEach(el => {
    el.classList.toggle('selected', el.dataset.id === id);
  });

  applyClip();
  renderMeta();
  renderSheet();
  renderPalette();
  switchView(state.view);
  setPlaying(true);
  requestAnimationFrame(() => { draw(); });
}

function renderMeta() {
  const s = state.set;
  $('setTitle').textContent = s.title || s.name;
  let path = `${s.dir}  ·  ${s.frameCount} 帧  ·  ${s.frameSize ? s.frameSize.join('×') : '?'}`
    + (s.projectId ? `  ·  ${s.projectId}` : '') + (s.revision ? ` rev${s.revision}` : '');
  if (s.isDup) path += `  ·  与「${s.dupOf}」内容相同`;
  if (s.supersededBy) path += `  ·  已有更新版本：${s.supersededBy}`;
  $('setPath').textContent = path;
  const desc = $('setDesc');
  if (s.description) { desc.hidden = false; desc.textContent = s.description; } else { desc.hidden = true; }

  const box = $('clips');
  box.innerHTML = '';
  const mk = (name, n, active) => {
    const b = document.createElement('button');
    b.className = 'clip-chip' + (active ? ' active' : '');
    b.innerHTML = `<b>${name}</b> ${n}`;
    b.addEventListener('click', () => { state.clip = name; applyClip(); });
    return b;
  };
  box.appendChild(mk('全部', s.frameCount, state.clip === ALL));
  for (const c of s.clips) box.appendChild(mk(c.name, c.frames.length, state.clip === c.name));
}

function applyClip() {
  const s = state.set;
  state.viewList = s.frames
    .map((f, i) => i)
    .filter(i => state.clip === ALL || s.frames[i].clip === state.clip);
  if (!state.viewList.length) state.viewList = s.frames.map((_, i) => i);
  if (state.idx >= state.viewList.length) state.idx = 0;
  $('frameRange').max = String(Math.max(0, state.viewList.length - 1));
  $('frameRange').value = String(state.idx);
  renderFilmstrip();
  renderGrid();
  updatePlayBtn();
  draw();
}

/* ---------------- 绘制 ---------------- */

function currentFrame() {
  if (!state.set || !state.viewList.length) return null;
  return state.set.frames[state.viewList[state.idx]];
}

function fitZoom(fw, fh) {
  const wrap = $('stageWrap');
  const w = Math.max(64, wrap.clientWidth - 24);
  const h = Math.max(64, wrap.clientHeight - 24);
  return Math.max(1, Math.min(48, Math.floor(Math.min(w / fw, h / fh))));
}

function draw() {
  const fr = currentFrame();
  if (!fr) return;
  const im = state.imgs[fr.index];
  const fw = fr.w || im.naturalWidth || 64;
  const fh = fr.h || im.naturalHeight || 64;
  const z = state.zoom || fitZoom(fw, fh);

  canvas.width = fw * z;
  canvas.height = fh * z;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = false;

  if (state.onion && state.viewList.length > 1) {
    const n = state.viewList.length;
    let p = state.idx - 1;
    if (p < 0) p = state.loop ? n - 1 : -1;
    if (p >= 0) {
      const pf = state.set.frames[state.viewList[p]];
      ctx.globalAlpha = 0.32;
      ctx.drawImage(state.imgs[pf.index], 0, 0, canvas.width, canvas.height);
      ctx.globalAlpha = 1;
    }
  }

  if (im.complete && im.naturalWidth) ctx.drawImage(im, 0, 0, canvas.width, canvas.height);

  if (state.grid) {
    ctx.strokeStyle = 'rgba(255,255,255,0.13)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (z >= 6) {
      for (let x = 0; x <= fw; x++) { ctx.moveTo(x * z + 0.5, 0); ctx.lineTo(x * z + 0.5, canvas.height); }
      for (let y = 0; y <= fh; y++) { ctx.moveTo(0, y * z + 0.5); ctx.lineTo(canvas.width, y * z + 0.5); }
    }
    ctx.stroke();
    ctx.strokeStyle = 'rgba(255,120,90,0.5)';
    ctx.beginPath();
    ctx.moveTo(canvas.width / 2 + 0.5, 0); ctx.lineTo(canvas.width / 2 + 0.5, canvas.height);
    ctx.moveTo(0, canvas.height - 0.5); ctx.lineTo(canvas.width, canvas.height - 0.5);
    ctx.stroke();
  }

  $('stageCorner').textContent = `${fw}×${fh} · ${z}x · ${state.idx + 1}/${state.viewList.length}`;
  $('frameLabel').textContent = `${state.idx + 1} / ${state.viewList.length}`;
  $('frameRange').value = String(state.idx);

  const info = [`${fr.id}`, `${fr.file}`, `${fw}×${fh}`];
  if (fr.rect) info.push(`rect ${fr.rect.join(',')}`);
  if (fr.sha) info.push(`sha ${fr.sha.slice(0, 12)}…`);
  $('frameInfo').textContent = info.join('   ·   ');

  document.querySelectorAll('.film-cell').forEach((el, i) => {
    el.classList.toggle('active', i === state.idx);
  });
  document.querySelectorAll('.grid-card').forEach(el => {
    el.classList.toggle('active', Number(el.dataset.pos) === state.idx);
  });
  document.querySelectorAll('.sheet-rect').forEach(el => {
    el.classList.toggle('active', Number(el.dataset.pos) === state.idx);
  });
  updatePlayBtn();
}

function updatePlayBtn() {
  $('btnPlay').textContent = state.playing ? '❚❚' : '▶';
}

/* ---------------- 播放 ---------------- */

let lastTs = 0, acc = 0;
function tick(ts) {
  if (state.playing && state.viewList.length > 0) {
    if (!lastTs) lastTs = ts;
    acc += ts - lastTs;
    lastTs = ts;
    const interval = 1000 / state.fps;
    if (acc >= interval) {
      let steps = Math.floor(acc / interval);
      acc -= steps * interval;
      steps = Math.min(steps, 6);
      for (let i = 0; i < steps; i++) advance();
      draw();
    }
  } else {
    lastTs = 0; acc = 0;
  }
  requestAnimationFrame(tick);
}

function advance() {
  const n = state.viewList.length;
  if (n === 0) return;
  if (state.ping) {
    state.idx += state.dir;
    if (state.idx >= n) {
      if (state.loop) { state.dir = -1; state.idx = n > 1 ? n - 2 : 0; }
      else { state.idx = n - 1; setPlaying(false); }
    } else if (state.idx < 0) {
      if (state.loop) { state.dir = 1; state.idx = n > 1 ? 1 : 0; }
      else { state.idx = 0; setPlaying(false); }
    }
  } else {
    state.idx++;
    if (state.idx >= n) {
      if (state.loop) state.idx = 0;
      else { state.idx = n - 1; setPlaying(false); }
    }
  }
}

function setPlaying(on) {
  state.playing = on && state.viewList.length > 1;
  lastTs = 0; acc = 0;
  updatePlayBtn();
}

function goto(pos) {
  const n = state.viewList.length;
  if (!n) return;
  state.idx = ((pos % n) + n) % n;
  draw();
}

/* ---------------- 各视图 ---------------- */

function renderFilmstrip() {
  const box = $('filmstrip');
  box.innerHTML = '';
  state.viewList.forEach((fi, pos) => {
    const fr = state.set.frames[fi];
    const cell = document.createElement('div');
    cell.className = 'film-cell' + (pos === state.idx ? ' active' : '');
    const img = document.createElement('img');
    img.src = fileUrl(fr.file);
    img.loading = 'lazy';
    img.title = fr.id;
    const label = document.createElement('div');
    label.className = 'fi';
    label.textContent = `${pos + 1}. ${fr.id}`;
    cell.append(img, label);
    cell.addEventListener('click', () => { goto(pos); scrollFilm(pos); });
    box.appendChild(cell);
  });
}

function scrollFilm(pos) {
  const cell = document.querySelectorAll('.film-cell')[pos];
  if (cell) cell.scrollIntoView({ block: 'nearest', inline: 'center' });
}

function renderGrid() {
  const box = $('gridView');
  box.innerHTML = '';
  state.viewList.forEach((fi, pos) => {
    const fr = state.set.frames[fi];
    const card = document.createElement('div');
    card.className = 'grid-card' + (pos === state.idx ? ' active' : '');
    card.dataset.pos = String(pos);
    const img = document.createElement('img');
    img.src = fileUrl(fr.file);
    img.loading = 'lazy';
    const label = document.createElement('div');
    label.className = 'gi';
    label.textContent = `${pos + 1}. ${fr.id}`;
    card.append(img, label);
    card.addEventListener('click', () => { goto(pos); switchView('player'); });
    box.appendChild(card);
  });
}

function renderSheet() {
  const box = $('sheetCanvas');
  const note = $('sheetNote');
  box.innerHTML = '';
  const s = state.set;
  if (!s.sheet) {
    note.textContent = '该动画集没有 sprite-sheet.png（图集视图不可用）';
    return;
  }
  const img = state.sheetImg;
  if (!img) { note.textContent = ''; return; }

  const sheetW = (s.sheet.size && s.sheet.size[0]) || img.naturalWidth || 1;
  const sheetH = (s.sheet.size && s.sheet.size[1]) || img.naturalHeight || 1;
  img.style.width = '100%';
  box.appendChild(img);

  const place = () => {
    box.querySelectorAll('.sheet-rect').forEach(el => el.remove());
    const rect = img.getBoundingClientRect();
    const kx = rect.width / sheetW, ky = rect.height / sheetH;
    s.frames.forEach((fr, i) => {
      const r = fr.rect || [i * (fr.w || 0), 0, fr.w || 0, fr.h || 0];
      const el = document.createElement('div');
      el.className = 'sheet-rect';
      el.style.left = (r[0] * kx) + 'px';
      el.style.top = (r[1] * ky) + 'px';
      el.style.width = (r[2] * kx) + 'px';
      el.style.height = (r[3] * ky) + 'px';
      const pos = state.viewList.indexOf(i);
      el.dataset.pos = String(pos);
      const tag = document.createElement('span');
      tag.textContent = fr.id;
      el.appendChild(tag);
      el.addEventListener('click', () => {
        if (pos < 0) { state.clip = ALL; applyClip(); }
        goto(state.viewList.indexOf(i));
        switchView('player');
      });
      box.appendChild(el);
    });
    note.textContent = `图集 ${sheetW}×${sheetH} · ${s.frames.length} 帧 · ${s.sheet.file}`;
  };

  if (img.complete && img.naturalWidth) place();
  else img.onload = place;
}

function renderPalette() {
  const box = $('paletteRow');
  box.innerHTML = '';
  const pal = state.set.palette;
  if (!pal || !pal.length) return;
  const label = document.createElement('span');
  label.className = 'plabel';
  label.textContent = `调色板 ${pal.length} 色`;
  box.appendChild(label);
  pal.forEach(c => {
    const sw = document.createElement('div');
    sw.className = 'swatch';
    sw.style.background = `rgba(${c[0]},${c[1]},${c[2]},${(c[3] ?? 255) / 255})`;
    sw.title = `rgba(${c.join(',')})`;
    box.appendChild(sw);
  });
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.view === view));
  const isPlayer = view === 'player';
  $('stageArea').hidden = !isPlayer;
  $('filmstrip').parentElement.hidden = !isPlayer;
  $('gridView').hidden = view !== 'grid';
  $('sheetView').hidden = view !== 'sheet';
  if (view === 'sheet') requestAnimationFrame(() => renderSheet());
  draw();
}

/* ---------------- 交互绑定 ---------------- */

$('search').addEventListener('input', (e) => {
  state.query = e.target.value; renderTree(); renderStat();
});
$('hideArchive').addEventListener('change', async (e) => {
  state.hideArchive = e.target.checked;
  // 归档目录是服务端跳过扫描的，要显示就得重新请求一次
  if (state.server) await loadData();
  else { renderTree(); renderStat(); }
});
$('hideDupes').addEventListener('change', (e) => {
  state.hideDupes = e.target.checked; renderTree(); renderStat();
});
$('hideOld').addEventListener('change', (e) => {
  state.hideOld = e.target.checked; renderTree(); renderStat();
});
$('refreshBtn').addEventListener('click', async () => {
  if (!state.server) {
    toast('离线模式无法重新扫描。请在 viewer 目录运行：<b>python serve.py</b>');
    return;
  }
  await loadData();
  toast('已重新扫描目录');
});
document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => switchView(t.dataset.view)));

$('btnPlay').addEventListener('click', () => setPlaying(!state.playing));
$('btnPrev').addEventListener('click', () => { setPlaying(false); goto(state.idx - 1); scrollFilm(state.idx); });
$('btnNext').addEventListener('click', () => { setPlaying(false); goto(state.idx + 1); scrollFilm(state.idx); });
$('btnFirst').addEventListener('click', () => { setPlaying(false); goto(0); scrollFilm(0); });
$('btnLast').addEventListener('click', () => { setPlaying(false); goto(state.viewList.length - 1); scrollFilm(state.idx); });

$('frameRange').addEventListener('input', (e) => { setPlaying(false); goto(Number(e.target.value)); });
$('fpsRange').addEventListener('input', (e) => {
  state.fps = Number(e.target.value); $('fpsLabel').textContent = String(state.fps);
});
$('zoomSel').addEventListener('change', (e) => { state.zoom = Number(e.target.value); draw(); });
$('bgSel').addEventListener('change', (e) => {
  state.bg = e.target.value;
  const wrap = $('stageWrap');
  wrap.className = 'stage-wrap bg-' + state.bg;
  draw();
});
$('loopChk').addEventListener('change', (e) => { state.loop = e.target.checked; });
$('pingChk').addEventListener('change', (e) => { state.ping = e.target.checked; });
$('onionChk').addEventListener('change', (e) => { state.onion = e.target.checked; draw(); });
$('gridChk').addEventListener('change', (e) => { state.grid = e.target.checked; draw(); });

$('openDirBtn').addEventListener('click', async () => {
  if (!state.set) return;
  if (state.server) {
    await fetch('/api/open', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: state.set.dir }),
    });
    toast('已在文件管理器中打开：<b>' + state.set.dir + '</b>');
  } else {
    copyText(state.set.abs);
    toast('离线模式已复制路径：<b>' + state.set.abs + '</b>');
  }
});

$('gifBtn').addEventListener('click', async () => {
  if (!state.set) return;
  if (!state.server) { toast('导出 GIF 需要本地服务：请运行 <b>start.bat</b> 或 <b>python serve.py</b>'); return; }
  const fr = currentFrame();
  const z = state.zoom || fitZoom(fr.w, fr.h);
  const bg = state.bg === 'checker' ? 'transparent' : state.bg;
  const url = `/api/gif?set=${encodeURIComponent(state.set.id)}&clip=${encodeURIComponent(state.clip)}`
    + `&fps=${state.fps}&scale=${z}&bg=${bg}`;
  toast('正在生成 GIF…');
  try {
    const res = await fetch(url);
    const out = await res.json();
    if (!out.ok) { toast('导出失败：' + (out.error || '未知错误')); return; }
    toast(`已导出 <b>${out.name}</b>（${state.fps}fps, ${z}x） <a href="${out.file}" download="${out.name}">下载</a>`);
  } catch (err) {
    toast('导出失败：' + err);
  }
});

$('helpBtn').addEventListener('click', () => { $('helpModal').hidden = false; });
$('helpClose').addEventListener('click', () => { $('helpModal').hidden = true; });
$('helpModal').addEventListener('click', (e) => { if (e.target.id === 'helpModal') $('helpModal').hidden = true; });

window.addEventListener('resize', () => draw());

window.addEventListener('keydown', (e) => {
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'select' || tag === 'textarea') {
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  if (!$('helpModal').hidden && e.key !== '?') { $('helpModal').hidden = true; return; }
  const n = state.viewList.length;
  if (!n) return;
  const step = e.shiftKey ? 5 : 1;
  switch (e.key) {
    case ' ': e.preventDefault(); setPlaying(!state.playing); break;
    case 'ArrowLeft': e.preventDefault(); setPlaying(false); goto(state.idx - step); scrollFilm(state.idx); break;
    case 'ArrowRight': e.preventDefault(); setPlaying(false); goto(state.idx + step); scrollFilm(state.idx); break;
    case 'Home': e.preventDefault(); setPlaying(false); goto(0); scrollFilm(0); break;
    case 'End': e.preventDefault(); setPlaying(false); goto(n - 1); scrollFilm(state.idx); break;
    case 'ArrowUp': e.preventDefault(); setFps(state.fps + 1); break;
    case 'ArrowDown': e.preventDefault(); setFps(state.fps - 1); break;
    case '+': case '=': setZoom(state.zoom ? state.zoom + 1 : 2); break;
    case '-': case '_': setZoom((state.zoom || fitZoom(currentFrame().w, currentFrame().h)) - 1); break;
    case 'f': case 'F': setZoom(0); break;
    case 'o': case 'O': $('onionChk').checked = !$('onionChk').checked; state.onion = $('onionChk').checked; draw(); break;
    case 'g': case 'G': $('gridChk').checked = !$('gridChk').checked; state.grid = $('gridChk').checked; draw(); break;
    case '1': switchView('player'); break;
    case '2': switchView('grid'); break;
    case '3': switchView('sheet'); break;
    case '/': e.preventDefault(); $('search').focus(); break;
    default: break;
  }
});

function setFps(v) {
  state.fps = Math.max(1, Math.min(30, v));
  $('fpsRange').value = String(state.fps);
  $('fpsLabel').textContent = String(state.fps);
}

function setZoom(v) {
  state.zoom = Math.max(0, Math.min(16, v));
  $('zoomSel').value = String(state.zoom);
  draw();
}

/* ---------------- 小工具 ---------------- */

let toastTimer = null;
function toast(html) {
  const el = $('toast');
  el.innerHTML = html;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
}

function copyText(text) {
  if (navigator.clipboard) navigator.clipboard.writeText(text).catch(() => {});
}

/* ---------------- 启动 ---------------- */

loadData();
requestAnimationFrame(tick);
