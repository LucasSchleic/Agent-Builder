/**
 * Toolbar — global workflow actions.
 *
 * UML methods:
 *   new_workflow()
 *   save_workflow()
 *   save_as_workflow()
 *   load_workflow()
 *   export_workflow()
 *   run_workflow()
 */
export class Toolbar {
    constructor(state, api, modal) {
        this.state  = state;
        this.api    = api;
        this.modal  = modal;
        this.canvas = null;     // injected by main.js
        this.wfPanel = null;    // injected by main.js
    }

    setCanvas(canvas)          { this.canvas  = canvas; }
    setWorkflowListPanel(wfp)  { this.wfPanel = wfp; }

    init() {
        document.getElementById('btn-new').addEventListener('click',     () => this.new_workflow());
        document.getElementById('btn-save').addEventListener('click',    () => this.save_workflow());
        document.getElementById('btn-save-as').addEventListener('click', () => this.save_as_workflow());
        document.getElementById('btn-load').addEventListener('click',    () => this.load_workflow());
        document.getElementById('btn-export').addEventListener('click',  () => this.export_workflow());
        document.getElementById('btn-run').addEventListener('click',     () => this.run_workflow());
    }

    new_workflow() {
        this.modal.prompt('New Workflow', 'Workflow name', async name => {
            if (!name) return;
            const data = await this.api.post('/api/workflow/new/', { name });
            if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
            this.state.positions      = {};
            this.state.selectedBlockId = null;
            this.canvas.update(data.workflow);
            this.wfPanel.display_workflows();
        });
    }

    async save_workflow() {
        if (!this.state.workflow) {
            this.modal.show('Nothing to save', 'Create a workflow first.', [{ label: 'OK' }]);
            return;
        }
        const data = await this.api.post('/api/workflow/save/', { workflow: this.state.workflow });
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.modal.show('Saved', `"${this.state.workflow.name}" saved.`, [{ label: 'OK' }], false);
        this.wfPanel.display_workflows();
    }

    save_as_workflow() {
        if (!this.state.workflow) {
            this.modal.show('Nothing to save', 'Create a workflow first.', [{ label: 'OK' }]);
            return;
        }
        this.modal.prompt('Save As', 'New workflow name', async name => {
            if (!name) return;
            const wf   = { ...this.state.workflow, name };
            const data = await this.api.post('/api/workflow/save/', { workflow: wf });
            if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
            this.state.workflow = wf;
            this.wfPanel.display_workflows();
        });
    }

    async load_workflow() {
        const data = await this.api.get('/api/workflows/');
        const wfs  = data.workflows ?? [];
        if (!wfs.length) {
            this.modal.show('No saved workflows', 'Use "Save" to save a workflow first.', [{ label: 'OK' }]);
            return;
        }
        const html = wfs.map(n =>
            `<button class="wf-load-btn" data-name="${n}">${n.replace('.json', '')}</button>`
        ).join('');
        this.modal.showHtml('Load Workflow', html, [{ label: 'Cancel', secondary: true }]);
        document.querySelectorAll('.wf-load-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                this.modal.hide();
                await this._doLoad(btn.dataset.name);
            });
        });
    }

    async _doLoad(name) {
        const data = await this.api.get(`/api/workflow/load/${name}/`);
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.state.positions       = {};
        this.state.selectedBlockId = null;
        this.canvas.update(data.workflow);
        this.wfPanel.display_workflows();
    }

    async export_workflow() {
        if (!this.state.workflow) {
            this.modal.show('Nothing to export', 'Create a workflow first.', [{ label: 'OK' }]);
            return;
        }
        const data = await this.api.post('/api/workflow/export/', { workflow: this.state.workflow });
        if (data.error) { this.modal.show('Export Error', data.error, [{ label: 'OK' }]); return; }
        this.modal.show('Exported Script', data.script, [
            { label: 'Copy', action: () => navigator.clipboard?.writeText(data.script) },
            { label: 'Close' },
        ], true);
    }

    async run_workflow() {
        if (!this.state.workflow) {
            this.modal.show('Nothing to run', 'Create a workflow first.', [{ label: 'OK' }]);
            return;
        }
        const data = await this.api.post('/api/workflow/run/', { workflow: this.state.workflow });
        if (data.error) { this.modal.show('Run Error', data.error, [{ label: 'OK' }]); return; }
        this.modal.show('Run Result', JSON.stringify(data.context, null, 2), [{ label: 'OK' }], true);
    }
}
