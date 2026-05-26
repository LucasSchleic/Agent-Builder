import { _esc } from './utils.js';

/**
 * ConfigPanel — right-side panel for editing the selected block's config.
 *
 * Renders form fields based on the selected block type, then POSTs
 * updates via /api/workflow/block/update/.
 */
export class ConfigPanel {
    constructor(state, api, modal) {
        this.state  = state;
        this.api    = api;
        this.modal  = modal;
        this.canvas = null; // injected by main.js
        this._body  = document.getElementById('config-body');
    }

    setCanvas(canvas) { this.canvas = canvas; }

    render() {
        if (!this.state.selectedBlockId || !this.state.workflow) {
            this._body.innerHTML = '<div class="no-selection">Click a block to configure it.</div>';
            return;
        }
        const block = this.state.workflow.blocks.find(b => b.id === this.state.selectedBlockId);
        if (!block) { this._body.innerHTML = ''; return; }

        const fields = this._fieldsFor(block);
        this._body.innerHTML =
            `<div class="config-block-title">${_esc(block.name)}<span>${_esc(block.type)}</span></div>` +
            `<div class="config-field"><label>Name</label><input type="text" id="cf-block-name" value="${_esc(block.name)}" spellcheck="false"></div>` +
            fields.map(f => this._fieldHtml(f, block.config)).join('') +
            `<button class="config-save-btn" id="cfg-save">Save</button>`;

        document.getElementById('cfg-save').addEventListener('click', () => this._save(block, fields));
    }

    // ── Field definitions per block type ──────────────────────────────────

    _fieldsFor(block) {
        switch (block.type) {
            case 'LLMBlock': return [
                { key: 'api_url',         label: 'API URL',          type: 'text' },
                { key: 'model_name',      label: 'Model Name',       type: 'text' },
                { key: 'temperature',     label: 'Temperature',      type: 'number' },
                { key: 'api_key_env_var', label: 'API Key Env Var',  type: 'text' },
            ];
            case 'AgentBlock': return [
                { key: 'system_prompt',  label: 'System Prompt',   type: 'textarea', rows: 4 },
                { key: 'user_prompt',    label: 'User Prompt',     type: 'textarea', rows: 6 },
                { key: 'memory_enabled', label: 'Memory Enabled',  type: 'checkbox' },
                { key: 'llm_block_id',   label: 'LLM Block ID',    type: 'text' },
            ];
            case 'HTTPBlock': return [
                { key: 'method',  label: 'Method',         type: 'select',   options: ['GET','POST','PUT','DELETE'] },
                { key: 'url',     label: 'URL',            type: 'text' },
                { key: 'headers', label: 'Headers (JSON)', type: 'textarea', json: true, rows: 4 },
                { key: 'body',    label: 'Body (JSON)',    type: 'textarea', json: true, rows: 6 },
            ];
            case 'PythonScriptBlock': {
                const base = [
                    { key: 'function_name', label: 'Function Name', type: 'text' },
                    { key: 'script_code',   label: 'Script Code',   type: 'textarea', rows: 18 },
                ];
                const dc = block.config.detected_config || {};
                const cfgFields = Object.entries(dc).map(([k, v]) => ({
                    key:       `__cfg__${k}`,
                    label:     v.label,
                    type:      typeof v.default === 'number' ? 'number' : 'text',
                    cfgValue:  v.value,
                    configVar: k,
                }));
                if (cfgFields.length) {
                    base.push({ key: '__cfg_sep__', type: 'separator', label: 'Config Fields' });
                    base.push(...cfgFields);
                }
                return base;
            }
            default: return [];
        }
    }

    _fieldHtml(f, cfg) {
        if (f.type === 'separator')
            return `<div class="config-separator">${f.label}</div>`;
        const val = f.cfgValue !== undefined ? f.cfgValue : cfg[f.key];
        if (f.type === 'checkbox')
            return `<div class="config-field"><label>
                        <input type="checkbox" id="cf-${f.key}" ${val ? 'checked' : ''}> ${f.label}
                    </label></div>`;
        if (f.type === 'select') {
            const opts = (f.options ?? []).map(o =>
                `<option value="${o}"${val === o ? ' selected' : ''}>${o}</option>`).join('');
            return `<div class="config-field"><label>${f.label}</label><select id="cf-${f.key}">${opts}</select></div>`;
        }
        if (f.type === 'textarea') {
            const display = f.json && typeof val === 'object' ? JSON.stringify(val, null, 2) : (val ?? '');
            const rows = f.rows ?? 5;
            return `<div class="config-field"><label>${f.label}</label><textarea id="cf-${f.key}" rows="${rows}">${_esc(String(display))}</textarea></div>`;
        }
        return `<div class="config-field"><label>${f.label}</label>
                    <input type="${f.type}" id="cf-${f.key}" value="${_esc(String(val ?? ''))}">
                </div>`;
    }

    // ── Save config ────────────────────────────────────────────────────────

    async _save(block, fields) {
        const config = {};
        fields.forEach(f => {
            if (f.configVar || f.type === 'separator') return; // handled separately
            const el = document.getElementById(`cf-${f.key}`);
            if (!el) return;
            if (f.type === 'checkbox')    config[f.key] = el.checked;
            else if (f.type === 'number') config[f.key] = parseFloat(el.value) || 0;
            else if (f.json) {
                try { config[f.key] = JSON.parse(el.value); } catch { config[f.key] = el.value; }
            } else config[f.key] = el.value;
        });

        const nameEl = document.getElementById('cf-block-name');
        const name = nameEl ? nameEl.value.trim() : block.name;

        // Collect updated detected_config values from ALL_CAPS fields.
        const dcUpdates = {};
        fields.filter(f => f.configVar).forEach(f => {
            const el = document.getElementById(`cf-${f.key}`);
            if (!el) return;
            // Preserve original type: number inputs must stay numbers, not strings.
            dcUpdates[f.configVar] = f.type === 'number' ? (parseFloat(el.value) || 0) : el.value;
        });
        if (Object.keys(dcUpdates).length) {
            const dc = block.config.detected_config || {};
            Object.entries(dcUpdates).forEach(([k, v]) => {
                if (dc[k]) dc[k] = { ...dc[k], value: v };
            });
            config.detected_config = dc;
        }

        const data = await this.api.post('/api/workflow/block/update/', {
            workflow: this.state.workflow, block_id: block.id, config, name,
        });
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.canvas.update(data.workflow);
    }
}
