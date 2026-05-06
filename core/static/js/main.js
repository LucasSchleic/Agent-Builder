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

// Singletons
const api    = new Api();
const modal  = new Modal();

// UI components (UML: UI package)
const canvas      = new Canvas(AppState, api, modal);
const configPanel = new ConfigPanel(AppState, api, modal);
const toolbox     = new Toolbox(AppState, api, modal);
const wfPanel     = new WorkflowListPanel(AppState, api, modal);
const toolbar     = new Toolbar(AppState, api, modal);

// Wire cross-references (avoids circular module imports)
canvas.setConfigPanel(configPanel);
configPanel.setCanvas(canvas);
toolbox.setCanvas(canvas);
wfPanel.setCanvas(canvas);
toolbar.setCanvas(canvas);
toolbar.setWorkflowListPanel(wfPanel);

// Boot
canvas.init();
toolbox.init();
toolbar.init();

wfPanel.display_workflows();
canvas.render_workflow(null); // show empty canvas hint
