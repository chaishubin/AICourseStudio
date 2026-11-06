import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    visibleCourseFocusEvents('), source.indexOf('    syncCourseFocusCue('));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${methods} }`)}`);

function card(events) {
    return {
        _focusCues: [{ text: '讲解', start: 2, end: 4, target_id: 'old', timing_source: 'segment_audio' }],
        _focusEvents: events
    };
}

test('changing a cue replaces its interval and preserves neighboring manual calibration', () => {
    const app = new Preview();
    const page = card([{ start: 0, end: 6, target_ids: ['old'], manual: true }]);
    app.updateCourseFocusCueTarget(page, 0, 'new');
    assert.deepEqual(page._focusEvents.map(e => [e.start, e.end, e.target_ids]), [
        [0, 2, ['old']], [2, 4, ['new']], [4, 6, ['old']]
    ]);
    assert.equal(page._focusCues[0].manual, true);
    assert.equal(page._focusCues[0].target_id, 'new');
    assert.equal(page._focusCues[0].timing_source, 'segment_audio');
    assert.equal(page._focusEvents[1].reviewed, true);
});

test('whole-page selection clears only the selected narration interval', () => {
    const app = new Preview();
    const page = card([{ start: 0, end: 6, target_ids: ['old'] }]);
    app.updateCourseFocusCueTarget(page, 0, '');
    assert.deepEqual(page._focusEvents[1].target_ids, []);
    assert.equal(page._focusCues[0].anchor_id, '');
    assert.deepEqual(page._focusEvents[0].target_ids, ['old']);
});

test('mapping can be edited before timing exists without dropping manual events', () => {
    const app = new Preview();
    const events = [{ start: 0, end: 6, target_ids: ['old'], manual: true, needs_review: true }];
    const page = card(events);
    delete page._focusCues[0].start;
    delete page._focusCues[0].end;
    app.updateCourseFocusCueTarget(page, 0, 'new');
    assert.equal(page._focusCues[0].target_id, 'new');
    assert.equal(page._focusEvents, events);
});

test('cue mapping stays enabled with an independent focus timeline', () => {
    class Element {
        constructor() { this.children = []; this.dataset = {}; this.style = {}; this.listeners = {}; }
        set innerHTML(value) { this.html = value; this.children = []; this.select = new Element(); }
        querySelector() { return this.select; }
        appendChild(node) { this.children.push(node); }
        prepend(node) { this.children.unshift(node); }
        addEventListener(type, handler) { this.listeners[type] = handler; }
    }
    globalThis.document = { createElement: () => new Element() };
    const app = new Preview();
    app.elements = {};
    app._esc = app._escAttr = value => value;
    const overlay = new Element();
    const editor = new Element();
    const page = card([{ start: 2, end: 4, target_ids: ['old'] }]);
    page._focusTargets = [{ id: 'old', text: '原位置' }, { id: 'new', text: '新位置' }];
    page.querySelector = selector => selector === '.course-focus-overlays' ? overlay : editor;
    app.renderCourseFocusEditor(page);
    const row = editor.children.find(node => node.className === 'course-focus-cue-row');
    assert.notEqual(row.select.disabled, true);
    assert.equal(row.children[0].className, 'course-focus-cue-seek');
});

test('restoring automatic mapping removes only that interval override', () => {
    const app = new Preview();
    const page = card([
        { start: 0, end: 6, target_ids: ['old'], manual: true },
        { start: 6, end: 8, target_ids: ['other'], manual: true }
    ]);
    page._focusCues[0].action = 'clear';
    page._focusCues[0].reviewed = true;
    app.updateCourseFocusCueTarget(page, 0, null);
    assert.equal(page._focusCues[0].manual, false);
    assert.equal(page._focusCues[0].action, undefined);
    assert.equal(page._focusCues[0].reviewed, undefined);
    assert.equal(page._focusEventsManualClear, false);
    assert.deepEqual(page._focusEvents.map(e => [e.start, e.end]), [[0, 2], [4, 6], [6, 8]]);
});

test('page visibility preserves saved mappings and shows only manual choices when requested', () => {
    const app = new Preview();
    const events = [{ target_id: 'auto' }, { target_id: 'manual', manual: true }];
    const page = { _focusMode: 'off' };
    assert.deepEqual(app.visibleCourseFocusEvents(page, events), []);
    page._focusMode = 'manual';
    assert.deepEqual(app.visibleCourseFocusEvents(page, events), [events[1]]);
    page._focusMode = 'auto';
    assert.equal(app.visibleCourseFocusEvents(page, events), events);
    assert.equal(events.length, 2);
});
