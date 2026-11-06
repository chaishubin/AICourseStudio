import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    async loadVoices('), source.indexOf('    renderVoicePreviewList('))
    + source.slice(source.indexOf('    collectCoursePackagingOptions()'), source.indexOf('    async loadPackagingTemplates('))
    + source.slice(source.indexOf('    async cancelCourse()'), source.indexOf('    // ── Slides'));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${methods} }`)}`);

test('late voice-list response cannot overwrite a newer engine selection', async () => {
    const app = new Preview();
    app.elements = { ttsEngine: { value: 'edge-tts' }, voiceSelect: { value: '' },
        customVoice: { value: '' }, voicePreviewList: {}, volcengineExpressionGroup: {} };
    app.stopVoicePreview = app.updatePreviewSpeechSummary = () => {};
    app.renderVoicePreviewList = engine => { app.renderedEngine = engine; };
    globalThis.document = { createElement: () => ({ appendChild() {} }) };
    app.elements.voiceSelect.appendChild = () => {};
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    globalThis.fetch = async url => {
        if (url.includes('edge-tts')) await gate;
        return { ok: true, json: async () => ({ voices: [{ id: 'new', name: '新音色' }] }) };
    };
    const oldRequest = app.loadVoices();
    app.elements.ttsEngine.value = 'minimax';
    await app.loadVoices();
    release();
    await oldRequest;
    assert.equal(app.renderedEngine, 'minimax');
    assert.equal(app.elements.voiceSelect.disabled, false);
});

test('returning to strategy clears the old file strategy and cut state', async () => {
    const app = new Preview();
    const item = { strategy: { voice: 'old' } };
    app.elements = { coursePreviewModule: { dataset: { taskId: 'task' } }, cancelCourseBtn: {} };
    app.getItemByTaskId = () => ({ index: 0, item });
    app.updateItem = (_, updates) => Object.assign(item, updates);
    app.stopCoursePreviewPlayback = app.renderFileList = app.renderResultsGrid = app.updateBatchSummary = app.showStatus = () => {};
    app.smartCutSegments = [{ id: 1 }];
    app.smartCutApplied = true;
    globalThis.window = { VidPPTUI: { confirm: async () => true } };
    globalThis.document = { getElementById: () => ({ scrollIntoView() {} }) };
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ success: true }) });
    await app.cancelCourse();
    assert.equal(item.strategy, null);
    assert.equal(item.status, 'pending');
    assert.equal(item.taskId, null);
    assert.deepEqual(app.smartCutSegments, []);
    assert.equal(app.smartCutApplied, false);
});

test('clearing editable packaging text does not restore a stale saved value', () => {
    const app = new Preview();
    app.elements = { packagingIntroTitle: { value: '' }, packagingOutroTitle: { value: '' },
        packagingDepartment: { value: '' } };
    app.state = {};
    app.packagingLayout = { intro: {}, outro: {} };
    globalThis.localStorage = { getItem: () => JSON.stringify({ packaging_intro_title: '旧片头',
        packaging_outro_title: '旧片尾', packaging_department: '旧院系' }) };
    const options = app.collectCoursePackagingOptions();
    assert.equal(options.packaging_intro_title, '');
    assert.equal(options.packaging_outro_title, '');
    assert.equal(options.packaging_department, '');
});
