import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const method = source.slice(source.indexOf('    async pollBackgroundReview('), source.indexOf('    renderCourseReview('));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${method} }`)}`);

function setup() {
    const app = new Preview();
    app.elements = { coursePreviewModule: { hidden: false, dataset: { taskId: 'task' } } };
    app.reviewPollToken = {};
    app.results = [];
    app.renderCourseReview = (...args) => app.results.push(args);
    return app;
}

test('background review updates the current preview without reloading scripts', async () => {
    const app = setup();
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ ai_review: { status: 'passed' }, quality_mode: 'premium' }) });
    await app.pollBackgroundReview('task', app.reviewPollToken);
    assert.deepEqual(app.results, [[{ status: 'passed' }, 'premium']]);
});

test('obsolete poll response cannot overwrite a newer request or another task', async () => {
    const app = setup();
    let resolve;
    globalThis.fetch = () => new Promise(done => { resolve = done; });
    const pending = app.pollBackgroundReview('task', app.reviewPollToken);
    app.reviewPollToken = {};
    resolve({ ok: true, json: async () => ({ ai_review: { status: 'passed' } }) });
    await pending;
    assert.deepEqual(app.results, []);
    app.elements.coursePreviewModule.dataset.taskId = 'other';
    await app.pollBackgroundReview('task', app.reviewPollToken);
    assert.deepEqual(app.results, []);
});
