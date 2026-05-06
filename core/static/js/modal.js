/** Modal dialog — text alerts, code views, text prompts, and HTML body. */
export class Modal {
    constructor() {
        this._overlay = document.getElementById('modal-overlay');
        this._title   = document.getElementById('modal-title');
        this._input   = document.getElementById('modal-input');
        this._body    = document.getElementById('modal-body');
        this._buttons = document.getElementById('modal-buttons');

        // Close on backdrop click
        this._overlay.addEventListener('click', e => {
            if (e.target === this._overlay) this.hide();
        });
    }

    /** Show plain text or monospace code. */
    show(title, text, buttons = [], isCode = false) {
        this._title.textContent = title;
        this._input.style.display = 'none';
        this._body.className = isCode ? '' : 'plain';
        this._body.textContent = text;
        this._setButtons(buttons);
        this._overlay.classList.add('active');
    }

    /** Show arbitrary HTML in the body (for load lists etc.). */
    showHtml(title, html, buttons = []) {
        this._title.textContent = title;
        this._input.style.display = 'none';
        this._body.className = 'plain';
        this._body.innerHTML = html;
        this._setButtons(buttons);
        this._overlay.classList.add('active');
    }

    /** Show a single-line text prompt and call callback(value) on confirm. */
    prompt(title, placeholder, callback) {
        this._title.textContent = title;
        this._body.textContent = '';
        this._input.style.display = 'block';
        this._input.value = '';
        this._input.placeholder = placeholder;
        this._input.onkeydown = e => {
            if (e.key === 'Enter') { this.hide(); callback(this._input.value.trim()); }
        };
        this._setButtons([
            { label: 'OK',     action: () => callback(this._input.value.trim()) },
            { label: 'Cancel', secondary: true },
        ]);
        this._overlay.classList.add('active');
        this._input.focus();
    }

    hide() { this._overlay.classList.remove('active'); }

    _setButtons(buttons) {
        this._buttons.innerHTML = '';
        buttons.forEach(b => {
            const btn = document.createElement('button');
            btn.className = 'modal-btn' + (b.secondary ? ' secondary' : '');
            btn.textContent = b.label;
            btn.onclick = () => { this.hide(); if (b.action) b.action(); };
            this._buttons.appendChild(btn);
        });
    }
}
