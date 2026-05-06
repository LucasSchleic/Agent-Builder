/**
 * WorkflowListPanel — shows saved workflows in the left panel.
 *
 * UML methods:
 *   display_workflows()
 *   select_workflow(workflow_name)
 */
export class WorkflowListPanel {
    constructor(state, api, modal) {
        this.state  = state;
        this.api    = api;
        this.modal  = modal;
        this.canvas = null; // injected by main.js
        this._panel = document.getElementById('workflow-list-panel');
    }

    setCanvas(canvas) { this.canvas = canvas; }

    async display_workflows() {
        const data = await this.api.get('/api/workflows/');
        const wfs  = data.workflows ?? [];
        this._panel.innerHTML = '';

        if (!wfs.length) {
            this._panel.innerHTML = '<div style="color:#bbb;font-size:11px;opacity:0.6;padding:4px 2px">No saved workflows</div>';
            return;
        }

        wfs.forEach(name => {
            const btn = document.createElement('button');
            btn.className   = 'workflow-item';
            btn.textContent = name.replace('.json', '');
            if (this.state.workflow?.name + '.json' === name)
                btn.classList.add('active');
            btn.addEventListener('click', () => this.select_workflow(name));
            this._panel.appendChild(btn);
        });
    }

    async select_workflow(workflowName) {
        const data = await this.api.get(`/api/workflow/load/${workflowName}/`);
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.state.positions       = {};
        this.state.selectedBlockId = null;
        this.canvas.update(data.workflow);
        this.display_workflows();
    }
}
