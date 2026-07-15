// Thin wrapper around the local API Studio backend.
const API = {
  async listProjects() {
    const r = await fetch('/api/projects');
    return (await r.json()).projects || [];
  },
  async createProject(name) {
    const r = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    return r.json();
  },
  async loadProject(name) {
    const r = await fetch('/api/projects/' + encodeURIComponent(name));
    return r.json();
  },
  async saveProject(name, bundle) {
    const r = await fetch('/api/projects/' + encodeURIComponent(name), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bundle),
    });
    return r.json();
  },
  async deleteProject(name) {
    const r = await fetch('/api/projects/' + encodeURIComponent(name), { method: 'DELETE' });
    return r.json();
  },
  // Send an HTTP request through the backend proxy (avoids CORS).
  async send(req) {
    const r = await fetch('/api/proxy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    return r.json();
  },
};

window.API = API;
