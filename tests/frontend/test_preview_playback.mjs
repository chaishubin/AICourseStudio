import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    stopVoicePreview()'), source.indexOf('    // ── Multi-file upload'))
    + source.slice(source.indexOf('    async startCoursePreviewPlayback('), source.indexOf('    updateCoursePreviewPagePlayerState('));
const { Preview } = await import(`data:text/javascript,${encodeURIComponent(`export class Preview { ${methods} }`)}`);
const deferred = () => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
};

function setup() {
    const audios = [];
    globalThis.Audio = class {
        constructor(url) { this.src = url; this.pending = deferred(); this.events = {}; audios.push(this); }
        play() { return this.pending.promise; }
        pause() { this.pending.reject(new DOMException('play interrupted by pause', 'AbortError')); }
        removeAttribute() {}
        load() {}
        addEventListener(name, handler) { this.events[name] = handler; }
    };
    const app = new Preview();
    app.errors = [];
    app.elements = { coursePreviewModule: { dataset: { taskId: 'task' } } };
    app.showStatus = (_, message) => app.errors.push(message);
    app.updateCoursePreviewPagePlayerState = () => {};
    app.clearCoursePreviewSubtitlePlayback = () => {};
    app.activateCoursePreviewSubtitles = () => {};
    app.goToPreviewPage = () => {};
    app.renderCourseFocusEditor = () => {};
    app.makeSubtitleCues = () => [];
    app.previewCardByPage = () => ({ querySelector: () => ({ value: 'script' }) });
    app.savePreviewScripts = async () => true;
    app.nextPreviewPageNumber = () => { throw new Error('stale ended handler'); };
    return { app, audios };
}
const button = () => ({ classList: { add() {}, remove() {} } });
const voiceResponse = () => ({ ok: true, blob: async () => new Blob(['audio']) });
const courseResponse = url => ({ ok: true, json: async () => ({ audio_url: url }) });
const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); };

test('stopping a pending voice play releases its URL and does not show an error', async () => {
    const { app, audios } = setup();
    globalThis.fetch = async () => voiceResponse();
    const playing = app.playVoicePreview('tts', 'voice', button());
    await flush();
    assert.equal(audios.length, 1);
    assert.ok(app.voicePreviewAudioUrl);
    app.stopVoicePreview();
    await playing;
    assert.equal(app.voicePreviewAudioUrl, null);
    assert.deepEqual(app.errors, []);
});

test('an old voice rejection and media event cannot stop the replacement', async () => {
    const { app, audios } = setup();
    globalThis.fetch = async () => voiceResponse();
    const first = app.playVoicePreview('tts', 'a', button());
    await flush();
    const second = app.playVoicePreview('tts', 'b', button());
    await flush();
    audios[0].events.error();
    assert.equal(app.voicePreviewAudio, audios[1]);
    audios[1].pending.resolve();
    await Promise.all([first, second]);
    assert.deepEqual(app.errors, []);
    app.stopVoicePreview();
});

test('a voice response arriving after stop never creates audio', async () => {
    const { app, audios } = setup();
    const response = deferred();
    globalThis.fetch = () => response.promise;
    const playing = app.playVoicePreview('tts', 'a', button());
    app.stopVoicePreview();
    response.resolve(voiceResponse());
    await playing;
    assert.equal(audios.length, 0);
});

test('stopping course audio while play is pending does not report failure', async () => {
    const { app, audios } = setup();
    globalThis.fetch = async () => courseResponse('course.mp3');
    app.coursePreviewPlaying = true;
    const playing = app.playCoursePreviewPage(1);
    await flush();
    app.stopCoursePreviewPlayback();
    await playing;
    audios[0].events.ended();
    audios[0].events.error();
    assert.deepEqual(app.errors, []);
});

test('old page audio arriving after a new start cannot replace current audio', async () => {
    const { app, audios } = setup();
    const old = deferred();
    globalThis.fetch = async url => url.includes('page-audio') ? old.promise : null;
    app.coursePreviewPlaying = true;
    const first = app.playCoursePreviewPage(1);
    app.stopCoursePreviewPlayback();
    globalThis.fetch = async () => courseResponse('new.mp3');
    const second = app.startCoursePreviewPlayback(2);
    await flush();
    old.resolve(courseResponse('old.mp3'));
    await first;
    assert.equal(audios.length, 1);
    assert.equal(audios[0].src, 'new.mp3');
    audios[0].pending.resolve();
    await second;
    assert.deepEqual(app.errors, []);
});

test('stopping during script save prevents delayed playback', async () => {
    const { app, audios } = setup();
    const save = deferred();
    app.savePreviewScripts = () => save.promise;
    globalThis.fetch = () => { throw new Error('should not fetch'); };
    const playing = app.startCoursePreviewPlayback(1);
    app.stopCoursePreviewPlayback();
    save.resolve(true);
    await playing;
    assert.equal(audios.length, 0);
});

test('current playback errors remain visible', async () => {
    const { app, audios } = setup();
    globalThis.fetch = async () => courseResponse('broken.mp3');
    app.coursePreviewPlaying = true;
    const playing = app.playCoursePreviewPage(1);
    await flush();
    audios[0].pending.reject(new DOMException('Unsupported audio', 'NotSupportedError'));
    await playing;
    assert.deepEqual(app.errors, ['Unsupported audio']);
    assert.equal(app.coursePreviewPlaying, false);
});
