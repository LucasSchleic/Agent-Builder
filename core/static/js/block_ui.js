import { _esc } from './utils.js';

/**
 * BlockUI — visual card for a single block on the canvas.
 *
 * UML attributes : block_id, x, y
 * UML methods    : move(x, y), open_config(), delete()
 *
 * Callbacks injected by Canvas:
 *   onSelect(blockId)               — block was clicked
 *   onDelete(blockId)               — delete button clicked
 *   onPortClick(blockId, portId, dir) — port dot clicked
 */
export class BlockUI {
    constructor(block, state, { onSelect, onDelete, onPortClick }) {
        this.block      = block;
        this.state      = state;
        this.onSelect   = onSelect;
        this.onDelete   = onDelete;
        this.onPortClick = onPortClick;
        this.el         = null;
    }

    get block_id() { return this.block.id; }
    get x() { return this.state.positions[this.block.id]?.x ?? 0; }
    get y() { return this.state.positions[this.block.id]?.y ?? 0; }

    /** Move the card to (x, y) — updates state and DOM. */
    move(x, y) {
        this.state.positions[this.block.id] = { x, y };
        if (this.el) {
            this.el.style.left = x + 'px';
            this.el.style.top  = y + 'px';
        }
    }

    /** Highlight this block as selected. */
    open_config() {
        this.onSelect(this.block.id);
    }

    /** Trigger deletion through Canvas. */
    delete() {
        this.onDelete(this.block.id);
    }

    /** Build and return the DOM element. */
    render() {
        const pos = this.state.positions[this.block.id] ?? { x: 30, y: 30 };
        const el = document.createElement('div');
        el.className   = 'block-ui' + (this.state.selectedBlockId === this.block.id ? ' selected' : '');
        el.dataset.blockId = this.block.id;
        el.style.cssText   = `left:${pos.x}px;top:${pos.y}px`;

        el.innerHTML = `
            <div class="block-header">
                <span class="block-name">${_esc(this.block.name)}</span>
                <span class="block-type-badge">${_esc(this.block.type)}</span>
                <button class="block-delete" title="Delete block">✕</button>
            </div>
            <div class="block-ports-l" id="pl-${this.block.id}"></div>
            <div class="block-ports-r" id="pr-${this.block.id}"></div>`;

        (this.block.input_ports  ?? []).forEach(p => el.querySelector(`#pl-${this.block.id}`).appendChild(this._portEl(p, 'input')));
        (this.block.output_ports ?? []).forEach(p => el.querySelector(`#pr-${this.block.id}`).appendChild(this._portEl(p, 'output')));

        // Select on click (ignore delete and port clicks)
        el.addEventListener('mousedown', e => {
            if (!e.target.closest('.block-delete') && !e.target.closest('.port-dot'))
                this.open_config();
        });

        el.querySelector('.block-delete').addEventListener('click', e => {
            e.stopPropagation();
            this.delete();
        });

        this.el = el;
        return el;
    }

    _portEl(port, dir) {
        const div = document.createElement('div');
        div.className            = `port ${dir}-port`;
        div.dataset.portId       = port.id;
        div.dataset.blockId      = this.block.id;
        div.dataset.direction    = dir;
        div.title = dir === 'output' ? 'Drag to connect' : 'Drop connection here';

        const dot = '<span class="port-dot"></span>';
        const lbl = `<span class="port-label">${_esc(port.name)}</span>`;
        // dot always first in DOM — row-reverse on output puts it visually to the right
        div.innerHTML = dot + lbl;

        div.querySelector('.port-dot').addEventListener('click', e => {
            e.stopPropagation();
            this.onPortClick(this.block.id, port.id, dir);
        });

        return div;
    }
}
