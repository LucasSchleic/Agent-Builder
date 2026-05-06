/** Thin HTTP client — all responses are parsed as JSON. */
export class Api {
    async _parse(r) {
        const text = await r.text();
        try { return JSON.parse(text); }
        catch { return { error: `Server error ${r.status}: ${text.slice(0, 200)}` }; }
    }

    async get(url) {
        const r = await fetch(url);
        return this._parse(r);
    }

    async post(url, body) {
        const r = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        return this._parse(r);
    }
}
