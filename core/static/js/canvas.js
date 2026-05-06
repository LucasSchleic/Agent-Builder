import { BlockUI } from './block_ui.js';

/**
 * Canvas — editing surface. Implements the Observer Subscriber interface.
 *
 * UML methods:
 *   render_workflow(workflow)
 *   add_block_ui(block)
 *   remove_block_ui(block_id)
 *   move_block(block_id, x, y)
 *   connect_ports(source_port_id, target_port_id)   [via _handlePortClick]
 *   delete_connection(connection_id)
 *   update(workflow)   ← Subscriber interface
 */
export class Canvas {
    constructor(state, api, modal) {
        this.state     = state;
        this.api       = api;
        this.modal     = modal;
        this.configPanel = null; // injected by main.js after construction

        this._el    = document.getElementById('canvas');
        this._svg   = document.getElementById('svg-layer');
        this._hint  = document.getElementById('canvas-hint');
    }

    /** Called by main.js to wire the config panel after both are instantiated. */
    setConfigPanel(cp) { this.configPanel = cp; }

    init() {
        this._bindDrag();
        this._bindDropFromToolbox();
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') { this._cancelConnect(); this.selectBlock(null); }
        });
    }

    // ── Subscriber interface ──────────────────────────────────────────────

    /** Receives the updated workflow from any API call and re-renders. */
    update(workflow) {
        this.state.workflow = workflow;
        this.render_workflow(workflow);
    }

    // ── Rendering ─────────────────────────────────────────────────────────

    render_workflow(workflow) {
        this._hint.style.display = workflow ? 'none' : 'block';
        this._clearBlocks();
        if (!workflow) { this._clearSvg(); return; }
        workflow.blocks.forEach((block, i) => {
            if (!this.state.positions[block.id])
                this.state.positions[block.id] = { x: 30 + (i % 4) * 210, y: 30 + Math.floor(i / 4) * 170 };
            this.add_block_ui(block);
        });
        // Defer SVG until layout is resolved
        requestAnimationFrame(() => this._renderConnections());
        if (this.configPanel) this.configPanel.render();
    }

    add_block_ui(block) {
        const ui = new BlockUI(block, this.state, {
            onSelect:    id => this.selectBlock(id),
            onDelete:    id => this.remove_block_ui(id),
            onPortClick: (bid, pid, dir) => this._handlePortClick(bid, pid, dir),
        });
        this._el.appendChild(ui.render());
    }

    async remove_block_ui(blockId) {
        const data = await this.api.post('/api/workflow/block/remove/', {
            workflow: this.state.workflow, block_id: blockId,
        });
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        delete this.state.positions[blockId];
        if (this.state.selectedBlockId === blockId) this.state.selectedBlockId = null;
        this.update(data.workflow);
    }

    move_block(blockId, x, y) {
        this.state.positions[blockId] = { x, y };
    }

    selectBlock(blockId) {
        this.state.selectedBlockId = blockId;
        this._el.querySelectorAll('.block-ui').forEach(el =>
            el.classList.toggle('selected', el.dataset.blockId === blockId));
        if (this.configPanel) this.configPanel.render();
    }

    // ── Connections ───────────────────────────────────────────────────────

    _handlePortClick(blockId, portId, dir) {
        if (!this.state.connectingFrom) {
            if (dir !== 'output') return;
            this.state.connectingFrom = { blockId, portId };
            const dot = this._el.querySelector(`[data-port-id="${portId}"][data-block-id="${blockId}"] .port-dot`);
            if (dot) dot.classList.add('active');
            this._el.addEventListener('mousemove', this._onMouseMovePreview);
        } else {
            if (dir === 'input' && blockId !== this.state.connectingFrom.blockId)
                this.connect_ports(this.state.connectingFrom.portId, portId,
                                   this.state.connectingFrom.blockId, blockId);
            this._cancelConnect();
        }
    }

    async connect_ports(srcPortId, tgtPortId, srcBlockId, tgtBlockId) {
        const data = await this.api.post('/api/workflow/connection/add/', {
            workflow: this.state.workflow,
            source_block_id: srcBlockId, source_port_id: srcPortId,
            target_block_id: tgtBlockId, target_port_id: tgtPortId,
        });
        if (data.error) { this.modal.show('Connection Error', data.error, [{ label: 'OK' }]); return; }
        this.update(data.workflow);
    }

    async delete_connection(connId) {
        if (!confirm('Delete this connection?')) return;
        const data = await this.api.post('/api/workflow/connection/remove/', {
            workflow: this.state.workflow, connection_id: connId,
        });
        if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }
        this.update(data.workflow);
    }

    // ── SVG connections ───────────────────────────────────────────────────

    _renderConnections() {
        this._clearSvg();
        if (!this.state.workflow) return;
        const ns = 'http://www.w3.org/2000/svg';

        this.state.workflow.connections.forEach(conn => {
            const src = this._portCenter(conn.source_block_id, conn.source_port_id);
            const tgt = this._portCenter(conn.target_block_id, conn.target_port_id);
            if (!src || !tgt) return;

            const d = this._bezier(src, tgt);
            const g = document.createElementNS(ns, 'g');
            g.classList.add('conn-group');

            const hit = document.createElementNS(ns, 'path');
            hit.setAttribute('d', d);
            hit.setAttribute('class', 'conn-path-hit');
            hit.addEventListener('click', () => this.delete_connection(conn.id));

            const path = document.createElementNS(ns, 'path');
            path.setAttribute('d', d);
            path.setAttribute('class', 'conn-path');

            g.appendChild(hit);
            g.appendChild(path);
            this._svg.appendChild(g);
        });

        // Preview line stays on top
        const prev = document.createElementNS(ns, 'path');
        prev.id = 'preview-line';
        prev.setAttribute('d', '');
        prev.setAttribute('stroke', '#ff80ff');
        prev.setAttribute('stroke-width', '2');
        prev.setAttribute('stroke-dasharray', '7 4');
        prev.setAttribute('fill', 'none');
        prev.setAttribute('pointer-events', 'none');
        this._svg.appendChild(prev);
    }

    _portCenter(blockId, portId) {
        const portEl = this._el.querySelector(`[data-port-id="${portId}"][data-block-id="${blockId}"]`);
        if (!portEl) return null;
        const dot = portEl.querySelector('.port-dot');
        if (!dot) return null;
        const cr = this._el.getBoundingClientRect();
        const dr = dot.getBoundingClientRect();
        return { x: dr.left + dr.width / 2 - cr.left, y: dr.top + dr.height / 2 - cr.top };
    }

    _bezier(a, b) {
        const cx = Math.abs(b.x - a.x) * 0.55;
        return `M ${a.x} ${a.y} C ${a.x + cx} ${a.y}, ${b.x - cx} ${b.y}, ${b.x} ${b.y}`;
    }

    // ── Drag blocks (mouse events) ────────────────────────────────────────

    _bindDrag() {
        let drag = null;

        this._el.addEventListener('mousedown', e => {
            const header = e.target.closest('.block-header');
            if (!header || e.target.closest('.block-delete')) return;
            const blockEl = header.closest('.block-ui');
            const bid = blockEl.dataset.blockId;
            const pos = this.state.positions[bid] ?? { x: 0, y: 0 };
            drag = { bid, sx: e.clientX, sy: e.clientY, ox: pos.x, oy: pos.y };
            e.preventDefault();
        });

        document.addEventListener('mousemove', e => {
            if (!drag) return;
            const x = drag.ox + e.clientX - drag.sx;
            const y = drag.oy + e.clientY - drag.sy;
            this.move_block(drag.bid, x, y);
            const blockEl = this._el.querySelector(`[data-block-id="${drag.bid}"]`);
            if (blockEl) { blockEl.style.left = x + 'px'; blockEl.style.top = y + 'px'; }
            requestAnimationFrame(() => this._renderConnections());
        });

        document.addEventListener('mouseup', () => { drag = null; });
    }

    // ── Drag from toolbox (HTML5 DnD) ────────────────────────────────────

    _bindDropFromToolbox() {
        this._el.addEventListener('dragover', e => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            this._el.classList.add('drag-over');
        });

        this._el.addEventListener('dragleave', e => {
            if (!this._el.contains(e.relatedTarget))
                this._el.classList.remove('drag-over');
        });

        this._el.addEventListener('drop', async e => {
            e.preventDefault();
            this._el.classList.remove('drag-over');

            const blockType = e.dataTransfer.getData('text/plain');
            if (!blockType || !this.state.workflow) return;

            // Calculate drop position relative to canvas
            const rect = this._el.getBoundingClientRect();
            const dropX = Math.max(0, e.clientX - rect.left - 85);
            const dropY = Math.max(0, e.clientY - rect.top  - 20);

            const oldIds = new Set(this.state.workflow.blocks.map(b => b.id));
            const data   = await this.api.post('/api/workflow/block/add/', {
                workflow: this.state.workflow, block_type: blockType,
            });
            if (data.error) { this.modal.show('Error', data.error, [{ label: 'OK' }]); return; }

            // Place the new block at the exact drop coordinates
            const newBlock = data.workflow.blocks.find(b => !oldIds.has(b.id));
            if (newBlock) this.state.positions[newBlock.id] = { x: dropX, y: dropY };

            this.update(data.workflow);
        });
    }

    // ── Preview bezier while connecting ──────────────────────────────────

    _onMouseMovePreview = e => {
        if (!this.state.connectingFrom) return;
        const cr   = this._el.getBoundingClientRect();
        const mouse = { x: e.clientX - cr.left, y: e.clientY - cr.top };
        const src  = this._portCenter(this.state.connectingFrom.blockId,
                                      this.state.connectingFrom.portId);
        const line = document.getElementById('preview-line');
        if (src && line) line.setAttribute('d', this._bezier(src, mouse));
    };

    _cancelConnect() {
        this.state.connectingFrom = null;
        this._el.querySelectorAll('.port-dot.active').forEach(d => d.classList.remove('active'));
        const line = document.getElementById('preview-line');
        if (line) line.setAttribute('d', '');
        this._el.removeEventListener('mousemove', this._onMouseMovePreview);
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    _clearBlocks() { this._el.querySelectorAll('.block-ui').forEach(e => e.remove()); }

    _clearSvg() {
        const ns   = 'http://www.w3.org/2000/svg';
        this._svg.innerHTML = '';
        const prev = document.createElementNS(ns, 'path');
        prev.id = 'preview-line';
        prev.setAttribute('d', '');
        prev.setAttribute('stroke', '#ff80ff');
        prev.setAttribute('stroke-width', '2');
        prev.setAttribute('stroke-dasharray', '7 4');
        prev.setAttribute('fill', 'none');
        prev.setAttribute('pointer-events', 'none');
        this._svg.appendChild(prev);
    }
}
