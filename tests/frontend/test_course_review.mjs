import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    renderCourseReview('), source.indexOf('    updatePageSubtitleSample('));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${methods} }`)}`);

function view() {
    const app = new Preview();
    app.elements = {
        coursePreviewModule: { dataset: {} }, aiReviewPanel: { dataset: {} },
        aiReviewSummary: {}, aiReviewMeta: {}, aiReviewFixAllBtn: {},
        aiReviewFindings: { querySelectorAll: () => [] }
    };
    app._esc = app._escAttr = value => String(value);
    app.messages = [];
    app.showStatus = (type, message) => app.messages.push({ type, message });
    app.renderCourseReview({
        review_completed: true, status: 'warning', findings: [
            { page_number: 1, message: '讲稿过长', replacement_script: '修复讲稿' },
            { page_number: 2, message: '检查结构' }
        ]
    });
    app.textarea = { value: '原讲稿', dispatchEvent: () => app.markCourseReviewStale(1) };
    app.previewCardByPage = () => ({ querySelector: () => app.textarea });
    return app;
}

test('saved fixes collapse into history while manual issues remain outside it', async () => {
    const app = view();
    let finish;
    app.savePreviewScripts = () => new Promise(resolve => { finish = resolve; });
    const saving = app.applyCourseReviewFixes();
    assert.equal(app.elements.aiReviewFixAllBtn.disabled, true);
    assert.equal(app.messages.length, 0);
    assert.equal(app.currentAIReview.findings.length, 2);
    app.renderCourseReview({ ...app.currentAIReview, applied_pages: [1],
        findings: app.currentAIReview.findings.map((item, i) => ({ ...item, applied: i === 0 })) });
    finish(true);
    await saving;
    assert.match(app.elements.aiReviewFindings.innerHTML, /已应用并保存/);
    assert.match(app.elements.aiReviewFindings.innerHTML, /需手动处理/);
    assert.match(app.elements.aiReviewFindings.innerHTML, /课程包装/);
    const html = app.elements.aiReviewFindings.innerHTML;
    const historyStart = html.indexOf('<details class="ai-review-applied-group"');
    assert.ok(historyStart > html.indexOf('data-page-number="2"'));
    assert.ok(historyStart < html.indexOf('data-page-number="1"'));
    assert.match(html, /已应用并保存 1 页讲稿/);
    assert.doesNotMatch(html, /<details[^>]*\bopen(?:\s|=|>)/);
    assert.equal(app.elements.aiReviewFixAllBtn.hidden, true);
    assert.equal(app.messages.at(-1).type, 'success');
    app.markCourseReviewStale(1);
    assert.equal(app.elements.aiReviewFixAllBtn.hidden, false);
    assert.deepEqual(app.currentAIReview.applied_pages, []);
});

test('failed save can retry unchanged replacement and never reports success early', async () => {
    const app = view();
    let attempts = 0;
    app.savePreviewScripts = async () => { attempts += 1; return false; };
    await app.applyCourseReviewFixes();
    assert.equal(app.textarea.value, '修复讲稿');
    assert.equal(app.messages.at(-1).type, 'error');
    assert.equal(app.elements.aiReviewFixAllBtn.disabled, false);
    assert.doesNotMatch(app.elements.aiReviewFindings.innerHTML, /class="ai-review-applied-group"/);
    assert.match(app.elements.aiReviewFindings.innerHTML, /应用讲稿修复/);
    await app.applyCourseReviewFixes();
    assert.equal(attempts, 2);
    assert.equal(app.messages.some(item => item.type === 'success'), false);
});
