


const API = 'http://localhost:8000';

let allJobs = [];
let selectedJob = null;
let lastRunUtc = null;
let filters = { new: false, remote: false, unapplied: false };

// ── Boot ──
async function init() {
    await fetchLastRun();
    await fetchJobs();
}

async function fetchLastRun() {
    try {
        const res = await fetch(`${API}/runs/latest`);
        const data = await res.json();
        lastRunUtc = data.previous_run_utc;
    } catch (e) {
        console.warn('Could not fetch last run:', e);
    }
}

async function fetchJobs() {
    try {
        const res = await fetch(`${API}/jobs`);
        allJobs = await res.json();
        document.getElementById('loading').style.display = 'none';
        renderList();
    } catch (e) {
        document.getElementById('loading').textContent = 'failed to connect to api';
    }
}

// ── Filtering ──
function getFilteredJobs() {
    const company = document.getElementById('company-filter').value.trim().toLowerCase();

    return allJobs.filter(j => {
        if (filters.remote && !j.is_remote) return false;
        if (filters.unapplied && j.applied) return false;
        if (filters.new && lastRunUtc && j.first_seen_utc <= lastRunUtc) return false;
        if (company && !j.company.toLowerCase().includes(company)) return false;
        return true;
    });
}

function toggleFilter(name) {
    filters[name] = !filters[name];
    document.getElementById(`btn-${name}`).classList.toggle('active', filters[name]);
    renderList();
}

document.getElementById('company-filter').addEventListener('input', renderList);

// ── Render List ──
function renderList() {
    const jobs = getFilteredJobs();
    const list = document.getElementById('job-list');
    const empty = document.getElementById('list-empty');

    // Remove old job items
    list.querySelectorAll('.job-item').forEach(el => el.remove());

    document.getElementById('job-count').textContent = `${jobs.length} jobs`;

    if (jobs.length === 0) {
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';

    jobs.forEach(job => {
        const el = document.createElement('div');
        el.className = 'job-item' + (selectedJob?.id === job.id ? ' selected' : '');
        el.onclick = () => selectJob(job);

        const isNew = lastRunUtc && job.first_seen_utc > lastRunUtc;

        el.innerHTML = `
        <div class="job-item-title">${job.title}</div>
        <div class="job-item-company">${job.company}</div>
        <div class="job-item-meta">
          ${job.is_remote ? '<span class="badge remote">remote</span>' : ''}
          ${isNew ? '<span class="badge new">new</span>' : ''}
          ${job.applied ? '<span class="badge applied">applied</span>' : ''}
        </div>
      `;

        list.appendChild(el);
    });
}

// ── Job Detail ──
function selectJob(job) {
    selectedJob = job;

    document.querySelectorAll('.job-item').forEach(el => el.classList.remove('selected'));
    event.currentTarget.classList.add('selected');

    document.getElementById('detail-empty').style.display = 'none';
    const content = document.getElementById('detail-content');
    content.classList.add('visible');

    const isNew = lastRunUtc && job.first_seen_utc > lastRunUtc;
    document.getElementById('d-keywords').textContent = job.matched_keywords || '—';
    document.getElementById('d-company').textContent = job.company;
    document.getElementById('d-title').textContent = job.title;
    document.getElementById('d-location').textContent = job.location_text || '—';
    document.getElementById('d-department').textContent = job.department || '—';
    document.getElementById('d-office').textContent = job.office || '—';
    document.getElementById('d-first-seen').textContent = job.first_seen_utc?.slice(0, 10) || '—';
    document.getElementById('d-description').textContent = job.description_text || 'No description available.';

    // Meta badges
    const meta = document.getElementById('d-meta');
    meta.innerHTML = `
      ${job.is_remote ? '<span class="badge remote">remote</span>' : '<span class="badge">on-site</span>'}
      ${isNew ? '<span class="badge new">new</span>' : ''}
      ${job.applied ? '<span class="badge applied">applied</span>' : ''}
    `;

    // Applied button state
    const applyBtn = document.getElementById('btn-apply');
    applyBtn.textContent = job.applied ? '✓ applied' : 'mark applied';
}

function openJob() {
    if (selectedJob) window.open(selectedJob.job_url, '_blank');
}

async function toggleApplied() {
    if (!selectedJob) return;

    const newState = !selectedJob.applied;

    try {
        await fetch(`${API}/jobs/${selectedJob.id}/applied`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ applied: newState }),
        });

        // Update local state
        selectedJob.applied = newState;
        const job = allJobs.find(j => j.id === selectedJob.id);
        if (job) job.applied = newState;

        // Refresh UI
        selectJob(selectedJob);
        renderList();
    } catch (e) {
        console.error('Failed to update applied status:', e);
    }
}

// --OpenAI--
let tailorDiffs = {};

async function startTailor() {
    if (!selectedJob) return;

    tailorDiffs = {};

    const overlay = document.getElementById('modal-overlay');
    const loading = document.getElementById('modal-loading');
    const content = document.getElementById('modal-content');
    const diffsEl = document.getElementById('modal-diffs');
    const title = document.getElementById('modal-title');

    title.textContent = 'tailor resume';
    content.textContent = '';
    diffsEl.style.display = 'none';
    loading.style.display = 'block';
    overlay.classList.add('visible');

    try {
        const res = await fetch(`${API}/jobs/${selectedJob.id}/tailor/diff`, {
            method: 'POST',
        });
        const data = await res.json();
        tailorDiffs = data.diffs;
        renderDiffs(tailorDiffs);
        diffsEl.style.display = 'block';
    } catch (e) {
        content.textContent = 'Failed to get suggestions. Check your API key and resume path.';
    } finally {
        loading.style.display = 'none';
    }
}

function renderDiffs(diffs) {
    const container = document.getElementById('diff-sections');
    container.innerHTML = '';

    for (const [section, diff] of Object.entries(diffs)) {
        const unchanged = diff.original.trim() === diff.suggested.trim();
        const el = document.createElement('div');
        el.className = 'diff-section';
        el.dataset.section = section;
        el.dataset.choice = unchanged ? 'accepted' : 'pending';

        el.innerHTML = `
            <div class="diff-section-header">
                <span class="diff-section-name">${section}</span>
                <div class="diff-toggle">
                    <button onclick="setChoice('${section}', 'accepted')"
                        class="${unchanged ? 'accepted' : ''}">
                        ${unchanged ? '✓ no changes' : 'accept'}
                    </button>
                    ${!unchanged ? `<button onclick="setChoice('${section}', 'rejected')">reject</button>` : ''}
                </div>
            </div>
            <div class="diff-cols">
                <div class="diff-col">
                    <div class="diff-col-label">original</div>
                    ${diff.original.trim()}
                </div>
                <div class="diff-col">
                    <div class="diff-col-label">suggested</div>
                    ${diff.suggested.trim()}
                </div>
            </div>
        `;
        container.appendChild(el);
    }
}

function setChoice(section, choice) {
    const el = document.querySelector(`.diff-section[data-section="${section}"]`);
    if (!el) return;
    el.dataset.choice = choice;

    const btns = el.querySelectorAll('.diff-toggle button');
    btns[0].className = choice === 'accepted' ? 'accepted' : '';
    if (btns[1]) btns[1].className = choice === 'rejected' ? 'rejected' : '';
}

async function applyTailor() {
    const status = document.getElementById('tailor-status');
    const sections = document.querySelectorAll('.diff-section');
    const approved = {};

    for (const el of sections) {
        const section = el.dataset.section;
        const choice = el.dataset.choice;
        const diff = tailorDiffs[section];
        if (!diff) continue;
        approved[section] = choice === 'accepted' ? diff.suggested : diff.original;
    }

    status.textContent = 'saving...';
    try {
        const res = await fetch(`${API}/jobs/${selectedJob.id}/tailor/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved }),
        });
        const data = await res.json();
        status.textContent = `✓ saved: ${data.path.split('/').pop()}`;
    } catch (e) {
        status.textContent = '✗ failed to save';
    }
}

// --MODAL--
function closeModal(e) {
    if (e && e.target !== document.getElementById('modal-overlay')) return;
    document.getElementById('modal-overlay').classList.remove('visible');
}

function toggleControls() {
    const panel = document.getElementById('controls-panel');
    const overlay = document.getElementById('controls-overlay');
    const isOpening = !panel.classList.contains('visible');

    panel.classList.toggle('visible');
    overlay.classList.toggle('visible');

    if (isOpening) loadSettings();


}

function closeControls(e) {
    if (e && e.target !== document.getElementById('controls-overlay')) return;
    document.getElementById('controls-panel').classList.remove('visible');
    document.getElementById('controls-overlay').classList.remove('visible');
}

async function runCommand(command) {
    const btn = event.currentTarget;
    const log = document.getElementById('controls-log');

    // Disable all buttons while running
    document.querySelectorAll('.control-btn').forEach(b => b.disabled = true);
    btn.classList.add('running');
    btn.textContent = 'running...';
    log.textContent = '';

    try {
        const res = await fetch(`${API}/run/${command}`, { method: 'POST' });
        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            log.textContent += decoder.decode(value);
            log.scrollTop = log.scrollHeight;
        }

        btn.classList.remove('running');
        btn.classList.add('success');
        btn.textContent = '✓ done';

        // Refresh jobs list after monitor or run
        if (command === 'monitor' || command === 'run') {
            await fetchJobs();
        }

    } catch (e) {
        btn.classList.remove('running');
        btn.classList.add('error');
        btn.textContent = '✗ error';
        log.textContent += '\nFailed to run command.';
    } finally {
        document.querySelectorAll('.control-btn').forEach(b => b.disabled = false);
        // Reset button text after 3 seconds
        setTimeout(() => {
            btn.classList.remove('success', 'error');
            btn.textContent = 'run';
        }, 3000);
    }
}


// Tab switching
function switchTab(tab) {
    const commands = document.getElementById('tab-commands');
    const settings = document.getElementById('tab-settings');

    if (tab === 'commands') {
        commands.style.display = 'flex';
        commands.style.flexDirection = 'column';
        settings.style.display = 'none';
    } else {
        commands.style.display = 'none';
        settings.style.display = 'flex';
        settings.style.flexDirection = 'column';
        loadSettings();
    }

    document.querySelectorAll('.controls-tab').forEach((t, i) => {
        t.classList.toggle('active', (i === 0 && tab === 'commands') || (i === 1 && tab === 'settings'));
    });
}

// Array fields
const ARRAY_FIELDS = [
    'filters-keywords',
    'filters-local_city_tokens',
    'filters-local_state_tokens',
    'filters-remote_tokens',
    'filters-exclude_if_not_local_tokens',
    'filters-role_tokens',
    'filters-exclude_title_tokens',
    'ats-greenhouse_likely_engineering_tokens',
];

async function loadSettings() {
    try {
        const res = await fetch(`${API}/config`);
        const cfg = await res.json();

        // Simple fields
        document.getElementById('cfg-discovery-max_pages').value = cfg.discovery.max_pages;
        document.getElementById('cfg-discovery-max_workers').value = cfg.discovery.max_workers;
        document.getElementById('cfg-monitor-max_workers').value = cfg.monitor.max_workers;
        document.getElementById('cfg-filters-home_zip').value = cfg.filters.home_zip;

        // Array fields — join as comma separated
        document.getElementById('cfg-filters-keywords').value = cfg.filters.keywords.join(', ');
        document.getElementById('cfg-filters-local_city_tokens').value = cfg.filters.local_city_tokens.join(', ');
        document.getElementById('cfg-filters-local_state_tokens').value = cfg.filters.local_state_tokens.join(', ');
        document.getElementById('cfg-filters-remote_tokens').value = cfg.filters.remote_tokens.join(', ');
        document.getElementById('cfg-filters-exclude_if_not_local_tokens').value = cfg.filters.exclude_if_not_local_tokens.join(', ');
        document.getElementById('cfg-filters-role_tokens').value = cfg.filters.role_tokens.join(', ');
        document.getElementById('cfg-filters-exclude_title_tokens').value = cfg.filters.exclude_title_tokens.join(', ');
        document.getElementById('cfg-ats-greenhouse_likely_engineering_tokens').value = cfg.ats.greenhouse.likely_engineering_tokens.join(', ');

    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

function splitField(val) {
    return val.split(',').map(s => s.trim()).filter(Boolean);
}

async function saveSettings() {
    const status = document.getElementById('settings-status');
    status.textContent = 'saving...';

    const payload = {
        discovery: {
            max_pages: parseInt(document.getElementById('cfg-discovery-max_pages').value),
            max_workers: parseInt(document.getElementById('cfg-discovery-max_workers').value),
        },
        monitor: {
            max_workers: parseInt(document.getElementById('cfg-monitor-max_workers').value),
        },
        filters: {
            home_zip: document.getElementById('cfg-filters-home_zip').value.trim(),
            keywords: splitField(document.getElementById('cfg-filters-keywords').value),
            local_city_tokens: splitField(document.getElementById('cfg-filters-local_city_tokens').value),
            local_state_tokens: splitField(document.getElementById('cfg-filters-local_state_tokens').value),
            remote_tokens: splitField(document.getElementById('cfg-filters-remote_tokens').value),
            exclude_if_not_local_tokens: splitField(document.getElementById('cfg-filters-exclude_if_not_local_tokens').value),
            role_tokens: splitField(document.getElementById('cfg-filters-role_tokens').value),
            exclude_title_tokens: splitField(document.getElementById('cfg-filters-exclude_title_tokens').value),
        },
        ats: {
            greenhouse: {
                likely_engineering_tokens: splitField(document.getElementById('cfg-ats-greenhouse_likely_engineering_tokens').value),
            }
        }
    };

    try {
        await fetch(`${API}/config`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        status.textContent = '✓ saved';
        setTimeout(() => status.textContent = '', 2000);
    } catch (e) {
        status.textContent = '✗ failed';
    }
}

init();