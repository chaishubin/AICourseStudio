import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../web/static/js/main.js', import.meta.url), 'utf8');
const methods = source.slice(source.indexOf('    voiceGender('), source.indexOf('    renderVoicePreviewList('));
const { Voices } = await import(`data:text/javascript,${encodeURIComponent(`export class Voices { ${methods} }`)}`);
const voices = new Voices();

test('provider gender takes priority and handles case', () => {
    assert.equal(voices.voiceGender({ gender: 'Female', id: 'male-test' }), 'female');
    assert.equal(voices.voiceGender({ gender: 'Male', name: '声音' }), 'male');
});

test('gender markers work across provider IDs without confusing female and male', () => {
    for (const id of ['zh_female_vv_uranus_bigtts', 'female-shaonv', 'Chinese (Mandarin)_Mature_Woman', 'lovely_girl']) {
        assert.equal(voices.voiceGender({ id }), 'female', id);
    }
    for (const id of ['zh_male_dayi_saturn_bigtts', 'male-qn-qingse', 'clever_boy']) {
        assert.equal(voices.voiceGender({ id }), 'male', id);
    }
    assert.equal(voices.voiceGender({ id: 'custom-123', name: '自定义音色' }), 'unknown');
});

test('grouping preserves provider order and includes unmarked voices', () => {
    const input = [{ id: 'female-a' }, { id: 'male-a' }, { id: 'custom' }, { id: 'female-b' }];
    const groups = voices.groupVoicesByGender(input);
    assert.deepEqual(groups.map(group => group.gender), ['male', 'female', 'unknown']);
    assert.deepEqual(groups[1].voices.map(voice => voice.id), ['female-a', 'female-b']);
    assert.deepEqual(input.map(voice => voice.id), ['female-a', 'male-a', 'custom', 'female-b']);
});
