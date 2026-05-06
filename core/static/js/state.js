/**
 * AppState — shared singleton holding all runtime UI state.
 *
 * workflow       : current workflow data as returned by the API
 * positions      : blockId → {x, y} — purely UI, not persisted server-side
 * selectedBlockId: id of the block whose config is shown in the right panel
 * connectingFrom : {blockId, portId} while the user is wiring an output port
 */
export const AppState = {
    workflow: null,
    positions: {},
    selectedBlockId: null,
    connectingFrom: null,
};
