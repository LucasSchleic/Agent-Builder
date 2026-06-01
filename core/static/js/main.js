/**
 * main.js — application bootstrap.
 *
 * Creates all UI component instances, injects cross-references,
 * and starts the application.
 */
import { AppState }           from './state.js';
import { Api }                from './api.js';
import { Modal }              from './modal.js';
import { Canvas }             from './canvas.js';
import { Toolbox }            from './toolbox.js';
import { Toolbar }            from './toolbar.js';
import { WorkflowListPanel }  from './workflow_list_panel.js';
import { ConfigPanel }        from './config_panel.js';
import { RunConsole }         from './console.js';

// Singletons
const api    = new Api();
const modal  = new Modal();

// UI components (UML: UI package)
const canvas      = new Canvas(AppState, api, modal);
const configPanel = new ConfigPanel(AppState, api, modal);
const toolbox     = new Toolbox(AppState, api, modal);
const wfPanel     = new WorkflowListPanel(AppState, api, modal);
const toolbar     = new Toolbar(AppState, api, modal);
const runConsole  = new RunConsole();

// Wire cross-references (avoids circular module imports)
canvas.setConfigPanel(configPanel);
configPanel.setCanvas(canvas);
toolbox.setCanvas(canvas);
wfPanel.setCanvas(canvas);
toolbar.setCanvas(canvas);
toolbar.setWorkflowListPanel(wfPanel);
toolbar.setRunConsole(runConsole);

// Boot
canvas.init();
toolbox.init();
toolbar.init();

// Config panel resize handle
(function () {
    const resizer = document.getElementById('config-resizer');
    let startX = 0, startWidth = 0;

    resizer.addEventListener('mousedown', e => {
        e.preventDefault();
        startX     = e.clientX;
        startWidth = document.getElementById('config-panel').getBoundingClientRect().width;
        resizer.classList.add('dragging');
        document.body.style.cursor     = 'col-resize';
        document.body.style.userSelect = 'none';
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup',   onUp);
    });

    function onMove(e) {
        const newWidth = Math.max(180, Math.min(700, startWidth + (startX - e.clientX)));
        document.documentElement.style.setProperty('--config-width', newWidth + 'px');
    }

    function onUp() {
        resizer.classList.remove('dragging');
        document.body.style.cursor     = '';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup',   onUp);
    }
}());

wfPanel.display_workflows();
canvas.render_workflow(null); // show empty canvas hint

// Status bar — keep workflow name in sync
const _statusWorkflow = document.getElementById('status-workflow');
const _origUpdate = canvas.update.bind(canvas);
canvas.update = function(workflow) {
    _origUpdate(workflow);
    _statusWorkflow.textContent = AppState.workflow ? AppState.workflow.name : '';
};
