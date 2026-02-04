const API_BASE = '/api';

// State
let agents = [];
let currentAgent = null;

let currentConfig = {};

// DOM Elements
const agentListEl = document.getElementById('agent-list');
const welcomeScreen = document.getElementById('welcome-screen');
const agentDetail = document.getElementById('agent-detail');
const currentAgentNameEl = document.getElementById('current-agent-name');
const configForm = document.getElementById('config-form');
const addAgentBtn = document.getElementById('add-agent-btn');
const saveBtn = document.getElementById('save-btn');
const deleteBtn = document.getElementById('delete-btn');

const newAgentModal = document.getElementById('new-agent-modal');
const createAgentBtn = document.getElementById('create-agent-btn');
const newAgentNameInput = document.getElementById('new-agent-name');

const appPasswordBtn = document.getElementById('app-password-btn');
const authStatusText = document.getElementById('auth-status-text');
const appPasswordModal = document.getElementById('app-password-modal');
const saveAppPasswordBtn = document.getElementById('save-app-password-btn');
const testConnectionBtn = document.getElementById('test-connection-btn');
const appPasswordEmailInput = document.getElementById('gmail-address');
const appPasswordInput = document.getElementById('app-password');
const appPasswordErrorEl = document.getElementById('app-password-error');
const connectionStatusEl = document.getElementById('connection-status');

// Init
async function init() {
    await fetchAgents();
    setupEventListeners();
}

// Fetch Agents
async function fetchAgents() {
    try {
        const res = await fetch(`${API_BASE}/agents`);
        agents = await res.json();
        renderAgentList();
    } catch (err) {
        console.error('Failed to fetch agents:', err);
    }
}

// Render Agent List
function renderAgentList() {
    agentListEl.innerHTML = '';
    agents.forEach(agent => {
        const li = document.createElement('li');
        li.className = `agent-item ${currentAgent === agent.name ? 'active' : ''}`;
        li.innerHTML = `
            <i class="fas fa-robot"></i>
            <span>${agent.name}</span>
        `;
        li.onclick = () => selectAgent(agent.name);
        agentListEl.appendChild(li);
    });
}

// Select Agent
async function selectAgent(name) {
    currentAgent = name;
    renderAgentList();

    welcomeScreen.classList.add('hidden');
    agentDetail.classList.remove('hidden');
    currentAgentNameEl.textContent = name;

    try {
        const res = await fetch(`${API_BASE}/agents/${name}`);
        const data = await res.json();
        currentConfig = jsyaml.load(data.config_content);
        renderConfigForm(currentConfig);
        checkAuthStatus(name);
    } catch (err) {
        console.error('Failed to fetch agent config:', err);
        configForm.innerHTML = '<p class="error">Error loading configuration</p>';
    }
}

// Render Config Form
function renderConfigForm(config) {
    configForm.innerHTML = '';

    const sections = {
        'agent': 'General Settings',
        'email': 'Email Configuration',
        'classification': 'AI & Classification',
        'deletion': 'Retention & Deletion',
        'logging': 'Logging'
    };

    for (const [sectionKey, sectionTitle] of Object.entries(sections)) {
        const sectionData = config[sectionKey] || {};

        // Section Header
        const header = document.createElement('div');
        header.className = 'form-section';
        header.textContent = sectionTitle;
        configForm.appendChild(header);

        // Fields
        for (const [key, value] of Object.entries(sectionData)) {
            // Skip fields without any alternatives available presently
            if (key === 'provider' || key === 'use_ai_model') continue;

            const fieldId = `field-${sectionKey}-${key}`;
            const fieldWrapper = document.createElement('div');
            fieldWrapper.className = 'form-field';

            const label = document.createElement('label');
            label.setAttribute('for', fieldId);
            label.textContent = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

            let input;
            if (key === 'action_on_deletion') {
                input = document.createElement('select');
                const options = [
                    { value: 'move_to_trash', text: 'Move to Trash' },
                    { value: 'apply_label', text: 'Apply Label (MarkForDeletion)' }
                ];
                options.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt.value;
                    option.textContent = opt.text;
                    if (value === opt.value) option.selected = true;
                    input.appendChild(option);
                });
            } else if (key === 'level' && sectionKey === 'logging') {
                input = document.createElement('select');
                const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
                levels.forEach(lvl => {
                    const option = document.createElement('option');
                    option.value = lvl;
                    option.textContent = lvl;
                    if (value === lvl) option.selected = true;
                    input.appendChild(option);
                });
            } else if (typeof value === 'boolean') {
                input = document.createElement('input');
                input.type = 'checkbox';
                input.checked = value;
            } else if (Array.isArray(value)) {
                fieldWrapper.classList.add('full');
                input = document.createElement('textarea');
                input.value = value.join('\n');
                input.placeholder = 'One item per line';
                input.rows = 3;
            } else {
                input = document.createElement('input');
                input.type = (typeof value === 'number') ? 'number' : 'text';
                input.value = value;
            }

            input.id = fieldId;
            input.dataset.section = sectionKey;
            input.dataset.key = key;
            input.dataset.type = typeof value;
            if (Array.isArray(value)) input.dataset.type = 'array';

            fieldWrapper.appendChild(label);
            fieldWrapper.appendChild(input);
            configForm.appendChild(fieldWrapper);
        }
    }
}

// Get Config From Form
function getConfigFromForm() {
    const newConfig = JSON.parse(JSON.stringify(currentConfig)); // Deep clone

    configForm.querySelectorAll('input, textarea, select').forEach(input => {
        const section = input.dataset.section;
        const key = input.dataset.key;
        const type = input.dataset.type;

        let value;
        if (type === 'boolean') {
            value = input.checked;
        } else if (type === 'number') {
            value = parseFloat(input.value);
        } else if (type === 'array') {
            value = input.value.split('\n').map(s => s.trim()).filter(s => s !== '');
        } else {
            value = input.value;
        }

        if (!newConfig[section]) newConfig[section] = {};
        newConfig[section][key] = value;
    });

    return newConfig;
}

// Save Config
async function saveConfig() {
    if (!currentAgent) return;

    const configObj = getConfigFromForm();
    const yamlContent = jsyaml.dump(configObj);

    try {
        const res = await fetch(`${API_BASE}/agents/${currentAgent}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: currentAgent, config_content: yamlContent })
        });

        if (res.ok) {
            alert('Configuration saved! The agent will use the new settings in its next run.');
            currentConfig = configObj;
        } else {
            const err = await res.json();
            alert(`Error: ${err.detail}`);
        }
    } catch (err) {
        console.error('Failed to save config:', err);
        alert('Failed to save configuration');
    }
}

// Auth Status
async function checkAuthStatus(name) {
    authStatusText.textContent = 'Checking...';
    authStatusText.style.color = 'var(--text-secondary)';

    try {
        // Check for app password first
        const credResponse = await fetch(`${API_BASE}/auth/credentials/${name}`);
        const credData = await credResponse.json();

        if (credData.configured) {
            authStatusText.textContent = `App Password: ${credData.email}`;
            authStatusText.style.color = 'var(--success)';
            return;
        }

        authStatusText.textContent = 'Authentication Required';
        authStatusText.style.color = 'var(--danger)';
    } catch (err) {
        console.error('Auth check failed:', err);
        authStatusText.textContent = 'Status Unknown';
        authStatusText.style.color = 'var(--text-secondary)';
    }
}

// Open app password modal
function openAppPasswordModal() {
    appPasswordModal.classList.remove('hidden');
    appPasswordEmailInput.value = '';
    appPasswordInput.value = '';
    appPasswordErrorEl.classList.add('hidden');
    connectionStatusEl.classList.add('hidden');
}

// Save app password
async function saveAppPassword() {
    const email = appPasswordEmailInput.value.trim();
    const password = appPasswordInput.value.trim();

    appPasswordErrorEl.classList.add('hidden');

    if (!email || !password) {
        appPasswordErrorEl.textContent = 'Please fill in both email and password';
        appPasswordErrorEl.classList.remove('hidden');
        return false;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/credentials/${currentAgent}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, app_password: password })
        });

        const data = await response.json();

        if (!response.ok) {
            appPasswordErrorEl.textContent = data.detail || 'Failed to save credentials';
            appPasswordErrorEl.classList.remove('hidden');
            return false;
        }

        // Success
        alert('Credentials saved successfully!');
        appPasswordModal.classList.add('hidden');
        checkAuthStatus(currentAgent);
        return true;
    } catch (error) {
        appPasswordErrorEl.textContent = 'Network error: ' + error.message;
        appPasswordErrorEl.classList.remove('hidden');
        return false;
    }
}

// Test connection
async function testConnection() {
    connectionStatusEl.textContent = 'Testing connection...';
    connectionStatusEl.style.background = 'rgba(59, 130, 246, 0.1)';
    connectionStatusEl.style.color = 'var(--accent)';
    connectionStatusEl.classList.remove('hidden');

    // First save credentials
    const saved = await saveAppPassword();
    if (!saved) {
        connectionStatusEl.classList.add('hidden');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/test/${currentAgent}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.status === 'success') {
            connectionStatusEl.textContent = '✓ ' + data.message;
            connectionStatusEl.style.background = 'rgba(34, 197, 94, 0.1)';
            connectionStatusEl.style.color = 'var(--success)';
        } else {
            connectionStatusEl.textContent = '✗ ' + data.message;
            connectionStatusEl.style.background = 'rgba(239, 68, 68, 0.1)';
            connectionStatusEl.style.color = 'var(--danger)';
        }
    } catch (error) {
        connectionStatusEl.textContent = '✗ Connection test failed: ' + error.message;
        connectionStatusEl.style.background = 'rgba(239, 68, 68, 0.1)';
        connectionStatusEl.style.color = 'var(--danger)';
    }
}

// (OAuth functions removed)

// Create Agent
async function createAgent() {
    const name = newAgentNameInput.value.trim();
    if (!name) return;

    const template = {
        agent: { name, schedule_interval_minutes: 15, enabled: true },
        email: { provider: 'gmail', address: 'user@example.com' },
        classification: { use_ai_model: true, confidence_threshold: 0.6, topics_i_care_about: [] },
        deletion: { action_on_deletion: 'move_to_trash', delete_promotional: true, dry_run: true },
        logging: { level: 'INFO', file: `logs/${name}.log` }
    };

    try {
        const res = await fetch(`${API_BASE}/agents`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, config_content: jsyaml.dump(template) })
        });

        if (res.ok) {
            newAgentModal.classList.add('hidden');
            newAgentNameInput.value = '';
            await fetchAgents();
            selectAgent(name);
        } else {
            const err = await res.json();
            alert(`Error: ${err.detail}`);
        }
    } catch (err) {
        console.error('Failed to create agent:', err);
        alert('Failed to create agent');
    }
}

// Delete Agent
async function deleteAgent() {
    if (!currentAgent || !confirm(`Are you sure you want to delete ${currentAgent}?`)) return;

    try {
        const res = await fetch(`${API_BASE}/agents/${currentAgent}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            currentAgent = null;
            welcomeScreen.classList.remove('hidden');
            agentDetail.classList.add('hidden');
            await fetchAgents();
        } else {
            alert('Failed to delete agent');
        }
    } catch (err) {
        console.error('Failed to delete agent:', err);
    }
}



// Event Listeners
function setupEventListeners() {
    if (addAgentBtn) addAgentBtn.onclick = () => newAgentModal.classList.remove('hidden');
    if (createAgentBtn) createAgentBtn.onclick = createAgent;
    if (saveBtn) saveBtn.onclick = saveConfig;
    if (deleteBtn) deleteBtn.onclick = deleteAgent;

    // App Password buttons
    if (appPasswordBtn) appPasswordBtn.onclick = openAppPasswordModal;
    if (saveAppPasswordBtn) saveAppPasswordBtn.onclick = saveAppPassword;
    if (testConnectionBtn) testConnectionBtn.onclick = testConnection;

    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.onclick = (e) => {
            const modal = e.target.closest('.modal');
            if (modal) modal.classList.add('hidden');
        };
    });
}

// Start
init();
