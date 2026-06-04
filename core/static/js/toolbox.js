/**
 * Toolbox — lists available block types and adds them to the workflow.
 *
 * UML methods:
 *   add_block(workflow, creator)       — here "creator" is just the block_type string
 *   list_available_block_types()
 *
 * Supports two interaction modes:
 *   1. Click a button → block is placed at a default position on the canvas.
 *   2. Drag a button onto the canvas → block is placed at the drop coordinates
 *      (drop handled by Canvas._bindDropFromToolbox).
 */
export class Toolbox {
    constructor(state, api, modal) {
        this.state  = state;
        this.api    = api;
        this.modal  = modal;
        this.canvas = null; // injected by main.js
    }

    setCanvas(canvas) { this.canvas = canvas; }

    init() {
        document.querySelectorAll('.toolbox-btn').forEach(btn => {
            // Click — add at default position
            btn.addEventListener('click', () => {
                if (!this.state.workflow) {
                    this.modal.show('No workflow', 'Create or load a workflow first.', [{ label: 'OK' }]);
                    return;
                }
                this.add_block(this.state.workflow, btn.dataset.blockType);
            });

            // HTML5 drag start — canvas drop handler picks it up
            btn.addEventListener('dragstart', e => {
                if (!this.state.workflow) {
                    this.modal.show('No workflow', 'Create or load a workflow first.', [{ label: 'OK' }]);
                    e.preventDefault();
                    return;
                }
                e.dataTransfer.setData('text/plain', btn.dataset.blockType);
                e.dataTransfer.effectAllowed = 'copy';
                btn.classList.add('dragging');
            });

            btn.addEventListener('dragend', () => btn.classList.remove('dragging'));
        });

        this.loadCustomBlocks();
        document.addEventListener('customBlockSaved', () => this.loadCustomBlocks());
    }

    async loadCustomBlocks() {
        const container = document.getElementById('toolbox-custom');
        if (!container) return;
        const data = await this.api.get('/api/blocks/custom/');
        container.innerHTML = '';
        if (!data.blocks || !data.blocks.length) return;

        const title = document.createElement('div');
        title.className = 'toolbox-section-title';
        title.textContent = 'Blocs sauvegardés';
        container.appendChild(title);

        data.blocks.forEach(item => {
            const btn = document.createElement('button');
            btn.className = 'toolbox-btn toolbox-btn-custom';
            btn.draggable = true;
            btn.dataset.template = JSON.stringify(item.data);
            btn.textContent = item.data.name || item.filename;
            this._bindCustomBtn(btn);
            container.appendChild(btn);
        });
    }

    _bindCustomBtn(btn) {
        btn.addEventListener('click', async () => {
            if (!this.state.workflow) {
                this.modal.show('No workflow', 'Create or load a workflow first.', [{ label: 'OK' }]);
                return;
            }
            await this._addCustomBlock(this.state.workflow, JSON.parse(btn.dataset.template));
        });

        btn.addEventListener('dragstart', e => {
            if (!this.state.workflow) { e.preventDefault(); return; }
            e.dataTransfer.setData('application/custom-block', btn.dataset.template);
            e.dataTransfer.setData('text/plain', '');
            e.dataTransfer.effectAllowed = 'copy';
            btn.classList.add('dragging');
        });

        btn.addEventListener('dragend', () => btn.classList.remove('dragging'));
    }

    async _addCustomBlock(workflow, template) {
        const data = await this.api.post('/api/workflow/block/add_custom/', { workflow, template });
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.canvas.update(data.workflow);
    }

    list_available_block_types() {
        return ['LLMBlock', 'AgentBlock', 'HTTPBlock', 'PythonScriptBlock', 'BufferMemoryBlock'];
    }

    async add_block(workflow, blockType) {
        const data = await this.api.post('/api/workflow/block/add/', {
            workflow, block_type: blockType,
        });
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.canvas.update(data.workflow);
    }
}
