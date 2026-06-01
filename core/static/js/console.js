/**
 * RunConsole — bottom-of-canvas panel that streams block execution events.
 *
 * Reads from POST /api/workflow/run/stream/ via fetch() + ReadableStream
 * so each SSE event is rendered as soon as it arrives, giving the user
 * live feedback instead of a single modal at the end.
 */
export class RunConsole {
    constructor() {
        this._panel  = document.getElementById('console-panel');
        this._output = document.getElementById('console-output');
        document.getElementById('console-close')
            .addEventListener('click', () => this.hide());
    }

    show() {
        this._panel.classList.add('visible');
        this._output.innerHTML = '';
    }

    hide() {
        this._panel.classList.remove('visible');
    }

    // ── Public entry point ─────────────────────────────────────────────

    async run(workflow) {
        this.show();
        this._line('info', '▶ Démarrage de l\'exécution…');
        try {
            const resp = await fetch('/api/workflow/run/stream/', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ workflow }),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ error: resp.statusText }));
                this._line('error', `✗ ${err.error ?? resp.statusText}`);
                return;
            }
            await this._readStream(resp.body);
        } catch (err) {
            this._line('error', `✗ ${err.message}`);
        }
    }

    // ── Stream reading ─────────────────────────────────────────────────

    async _readStream(body) {
        const reader  = body.getReader();
        const decoder = new TextDecoder();
        let   buffer  = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            // SSE messages are separated by double newlines.
            const parts = buffer.split('\n\n');
            buffer = parts.pop(); // keep the incomplete trailing chunk
            for (const part of parts) {
                const trimmed = part.trim();
                if (trimmed.startsWith('data: ')) {
                    try { this._handle(JSON.parse(trimmed.slice(6))); }
                    catch { /* ignore malformed JSON */ }
                }
            }
        }
    }

    // ── Event handlers ─────────────────────────────────────────────────

    _handle(ev) {
        switch (ev.type) {
            case 'start':
                this._line('info',
                    `Workflow : <strong>${_esc(ev.workflow)}</strong> — ${ev.total} bloc(s)`);
                break;

            case 'block_start':
                // Inject an element we can update in-place when the block finishes.
                this._output.insertAdjacentHTML('beforeend',
                    `<div class="console-line console-running" id="blk-${_esc(ev.block_id)}">`
                    + `⟳ <strong>${_esc(ev.block_name)}</strong>`
                    + ` <span class="console-type">${_esc(ev.block_type)}</span>`
                    + ` — en cours…</div>`
                );
                this._scroll();
                break;

            case 'block_done': {
                const el = document.getElementById(`blk-${ev.block_id}`);
                if (el) {
                    el.className = 'console-line console-done';
                    el.innerHTML =
                        `✓ <strong>${_esc(ev.block_name)}</strong>`
                        + `<div class="console-output">${this._fmt(ev.output)}</div>`;
                }
                this._scroll();
                break;
            }

            case 'block_error': {
                const el = document.getElementById(`blk-${ev.block_id}`);
                if (el) {
                    el.className = 'console-line console-error';
                    el.innerHTML =
                        `✗ <strong>${_esc(ev.block_name)}</strong>`
                        + `<div class="console-output">${_esc(ev.error)}</div>`;
                }
                this._scroll();
                break;
            }

            case 'done':
                this._line('separator', '─'.repeat(52));
                this._line('info', '✔ Exécution terminée.');
                break;

            case 'error':
                this._line('error', `✗ ${_esc(ev.error)}`);
                break;
        }
    }

    // ── Helpers ────────────────────────────────────────────────────────

    _line(cls, html) {
        this._output.insertAdjacentHTML('beforeend',
            `<div class="console-line console-${cls}">${html}</div>`);
        this._scroll();
    }

    _scroll() {
        this._output.scrollTop = this._output.scrollHeight;
    }

    _fmt(value) {
        if (value === null || value === undefined) return '<em>(pas de sortie)</em>';
        const str = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
        const preview = str.length > 600 ? str.slice(0, 600) + '\n…(tronqué)' : str;
        return _esc(preview).replace(/\n/g, '<br>');
    }
}

function _esc(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
