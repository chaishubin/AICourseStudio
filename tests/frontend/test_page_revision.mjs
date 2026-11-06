import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    async generatePageRevision('), source.indexOf('    renderCourseReview('));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${methods} }`)}`);

function view() {
    const app = new Preview();
    const nodes = {
        '.page-revision-feedback': { value: '纠正 PLC 概念', focus() {} },
        '.page-revision-status': {},
        '.page-revision-generate': {},
        '.page-revision-apply': {},
        '.page-revision-result': { hidden: true },
        '.page-revision-candidate': {},
        '.course-preview-script': { value: '原讲稿', dispatchEvent() {} },
        '.page-reviewed': { checked: true }
    };
    const card = { dataset: { pageNumber: '2' }, querySelector: selector => nodes[selector] };
    app.elements = { coursePreviewModule: { dataset: { taskId: 'task' } } };
    app.previewCardByPage = () => card;
    app.savePreviewScripts = async () => true;
    app.stopCoursePreviewPlayback = () => {};
    return { app, card, nodes };
}

const ok = () => ({ ok: true, json: async () => ({ script: '新讲稿', base_script: '原讲稿' }) });

test('generation previews a candidate and applies it only after explicit selection', async () => {
    const { app, card, nodes } = view();
    globalThis.fetch = async (_, init) => {
        assert.deepEqual(JSON.parse(init.body), { page_number: 2, feedback: '纠正 PLC 概念', script: '原讲稿' });
        return ok();
    };
    await app.generatePageRevision(card);
    assert.equal(nodes['.course-preview-script'].value, '原讲稿');
    assert.equal(nodes['.page-revision-candidate'].value, '新讲稿');
    assert.equal(nodes['.page-revision-result'].hidden, false);
    let finishSave;
    app.savePreviewScripts = () => new Promise(resolve => { finishSave = resolve; });
    const saving = app.applyPageRevision(card);
    assert.equal(nodes['.course-preview-script'].value, '新讲稿');
    assert.equal(nodes['.page-reviewed'].checked, false);
    assert.match(nodes['.page-revision-status'].textContent, /正在保存/);
    finishSave(true);
    await saving;
    assert.match(nodes['.page-revision-status'].textContent, /新讲稿已保存/);
    assert.equal(card._revision, null);
});

test('save failure stops generation before calling the model', async () => {
    const { app, card, nodes } = view();
    app.savePreviewScripts = async () => false;
    globalThis.fetch = () => { throw new Error('must not call'); };
    await app.generatePageRevision(card);
    assert.match(nodes['.page-revision-status'].textContent, /保存失败/);
    assert.equal(card._revisionBusy, false);
    assert.equal(nodes['.page-revision-generate'].disabled, false);
});

test('a failed request preserves the script and feedback for retry', async () => {
    const { app, card, nodes } = view();
    globalThis.fetch = async () => ({ ok: false, json: async () => ({ error: 'AI 服务不可用' }) });
    await app.generatePageRevision(card);
    assert.equal(nodes['.course-preview-script'].value, '原讲稿');
    assert.equal(nodes['.page-revision-feedback'].value, '纠正 PLC 概念');
    assert.equal(nodes['.page-revision-result'].hidden, true);
    assert.equal(nodes['.page-revision-status'].textContent, 'AI 服务不可用');
});

test('edits made during generation cannot be overwritten', async () => {
    const { app, card, nodes } = view();
    globalThis.fetch = async () => {
        nodes['.course-preview-script'].value = '我手动改过的讲稿';
        return ok();
    };
    await app.generatePageRevision(card);
    assert.equal(nodes['.page-revision-result'].hidden, true);
    assert.equal(nodes['.course-preview-script'].value, '我手动改过的讲稿');
    assert.match(nodes['.page-revision-status'].textContent, /生成期间你修改/);
});

test('edits after generation cannot be overwritten by applying the candidate', async () => {
    const { app, card, nodes } = view();
    globalThis.fetch = async () => ok();
    await app.generatePageRevision(card);
    nodes['.course-preview-script'].value = '我手动改过的讲稿';
    await app.applyPageRevision(card);
    assert.equal(nodes['.course-preview-script'].value, '我手动改过的讲稿');
    assert.match(nodes['.page-revision-status'].textContent, /根据最新讲稿重新生成/);
});

test('a response arriving after switching courses does not alter the old view', async () => {
    const { app, card, nodes } = view();
    globalThis.fetch = async () => {
        app.elements.coursePreviewModule.dataset.taskId = 'other-task';
        return ok();
    };
    await app.generatePageRevision(card);
    assert.equal(nodes['.page-revision-result'].hidden, true);
    assert.equal(card._revision, null);
});

test('applying keeps the generated script visible when saving fails', async () => {
    const { app, card, nodes } = view();
    globalThis.fetch = async () => ok();
    await app.generatePageRevision(card);
    app.savePreviewScripts = async () => false;
    await app.applyPageRevision(card);
    assert.equal(nodes['.course-preview-script'].value, '新讲稿');
    assert.match(nodes['.page-revision-status'].textContent, /保存失败/);
    assert.doesNotMatch(nodes['.page-revision-status'].textContent, /已保存/);
    assert.equal(nodes['.page-revision-apply'].disabled, false);
});
