import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    async recommendSmartCuts()'), source.indexOf('    async uploadEditedPresentation('));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${methods} }`)}`);

function view() {
    const app = new Preview();
    app.script = '新讲稿';
    app.focus = [];
    app.errors = [];
    app.elements = {
        coursePreviewModule: { dataset: { taskId: 'task', qualityMode: 'balanced' } },
        coursePreviewSaveState: { classList: { add() {}, remove() {} } },
        smartCutRecommendBtn: {}, smartCutApplyBtn: {},
        cutDurationMinutes: { value: '5' }
    };
    app.previewSaveSequence = 0;
    app.collectSpeechSettings = () => ({ tts_engine: 'edge-tts', voice: app.voice || 'voice-a' });
    app.collectPreviewMediaSettings = () => ({ burn_subtitles: true });
    app.smartCutApplied = false;
    app.smartCutSegments = [];
    app.collectPreviewScripts = () => [{ page_number: 1, script: app.script, focus_cues: app.focus }];
    app.collectSmartCutSegments = () => app.smartCutSegments;
    app.previewCardByPage = () => null;
    app.renderSmartCutSegments = () => { app.renders = (app.renders || 0) + 1; };
    app.updateCourseDurationEstimate = () => {};
    app.showStatus = (type, message) => { if (type === 'error') app.errors.push(message); };
    return app;
}

const ok = data => ({ ok: true, json: async () => data });

test('save immediately synchronizes cues, events and duration without a page reload', async () => {
    const app = view();
    const length = {};
    const label = {};
    const card = { dataset: {}, querySelector: selector => selector === '.course-preview-length' ? length : label };
    app.previewCardByPage = () => card;
    app.renderCourseFocusEditor = value => { assert.equal(value, card); app.focusRendered = true; };
    globalThis.fetch = async () => ok({ pages: [{
        page_number: 1, script: '新讲稿', estimated_seconds: 8,
        focus_cues: [{ text: '新讲稿' }], focus_events: null,
        lesson_segment: { id: 2, title: '新段' }
    }], lesson_segments: [] });
    assert.equal(await app.savePreviewScripts(), true);
    assert.deepEqual(card._focusCues, [{ text: '新讲稿' }]);
    assert.equal(card._focusEvents, null);
    assert.equal(card.dataset.estimatedSeconds, '8');
    assert.equal(label.textContent, '第 2 段 · 新段');
    assert.equal(app.focusRendered, true);
});

test('unapplied manual draft survives automatic saves', async () => {
    const app = view();
    const draft = [{ title: '手工范围', start_page: 1, end_page: 3 }];
    app.smartCutSegments = draft;
    globalThis.fetch = async () => ok({ lesson_segments: [{ title: '旧已应用范围' }] });
    await app.savePreviewScripts();
    assert.equal(app.smartCutSegments, draft);
    assert.equal(app.smartCutApplied, false);
});

test('automatic draft is refreshed using latest saved script', async () => {
    const app = view();
    app.smartCutSegments = [{ title: '旧建议' }];
    app.smartCutRecommendationOptions = { target_minutes: 5, priority: 'duration' };
    globalThis.fetch = async (_, init) => {
        assert.deepEqual(JSON.parse(init.body).recommendation_options, app.smartCutRecommendationOptions);
        return ok({ lesson_segments: [], recommended_segments: [{ title: '新建议' }] });
    };
    await app.savePreviewScripts();
    assert.equal(app.smartCutSegments[0].title, '新建议');
    assert.equal(app.smartCutApplied, false);
});

test('saving is serialized and edits made during a request are persisted before completion', async () => {
    const app = view();
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    let running = 0;
    let peak = 0;
    const saved = [];
    globalThis.fetch = async (_, init) => {
        running += 1;
        peak = Math.max(peak, running);
        saved.push(JSON.parse(init.body).pages[0].script);
        if (saved.length === 1) await gate;
        running -= 1;
        return ok({ lesson_segments: [] });
    };
    const first = app.savePreviewScripts();
    await Promise.resolve();
    app.script = '最新修复讲稿';
    const second = app.savePreviewScripts();
    release();
    assert.deepEqual(await Promise.all([first, second]), [true, true]);
    assert.equal(peak, 1);
    assert.equal(saved.at(-1), '最新修复讲稿');
    assert.equal(saved[0], '新讲稿');
});

test('failed saves prevent recommending and applying cuts', async () => {
    const app = view();
    let calls = 0;
    globalThis.fetch = async () => {
        calls += 1;
        return { ok: false, json: async () => ({ error: '保存失败' }) };
    };
    await app.recommendSmartCuts();
    await app.applySmartCuts();
    assert.equal(calls, 2); // Only PATCH requests; neither cut endpoint is called.
    assert.equal(app.errors.length, 2);
});

test('voice edits made during save are persisted before preview can start', async () => {
    const app = view();
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    const voices = [];
    globalThis.fetch = async (_, init) => {
        voices.push(JSON.parse(init.body).voice);
        if (voices.length === 1) await gate;
        return ok({ lesson_segments: [] });
    };
    const saving = app.savePreviewScripts();
    await Promise.resolve();
    app.voice = 'voice-b';
    release();
    assert.equal(await saving, true);
    assert.deepEqual(voices, ['voice-a', 'voice-b']);
});
