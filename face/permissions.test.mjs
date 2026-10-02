// M26: the face's page may use the microphone (audio only, our own page) and nothing else (permissions.js).
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const { allowCheck, allowRequest } = createRequire(import.meta.url)('./permissions.js');

const PAGE = 'app://pseudo/index.html';

describe('allowRequest', () => {
  it('lets our page open the microphone', () => {
    expect(allowRequest('media', { mediaTypes: ['audio'], requestingUrl: PAGE })).toBe(true);
  });

  it('refuses the camera, even asked together with the microphone', () => {
    expect(allowRequest('media', { mediaTypes: ['video'], requestingUrl: PAGE })).toBe(false);
    expect(allowRequest('media', { mediaTypes: ['audio', 'video'], requestingUrl: PAGE })).toBe(false);
    expect(allowRequest('media', { mediaTypes: [], requestingUrl: PAGE })).toBe(false);
  });

  it('refuses any other page, and any other permission', () => {
    for (const url of ['https://example.invalid/', 'file:///C:/x.html', 'app://other/index.html', 'not a url', undefined]) {
      expect(allowRequest('media', { mediaTypes: ['audio'], requestingUrl: url })).toBe(false);
    }
    for (const permission of ['notifications', 'geolocation', 'clipboard-read', 'display-capture', 'openExternal']) {
      expect(allowRequest(permission, { mediaTypes: ['audio'], requestingUrl: PAGE })).toBe(false);
    }
    expect(allowRequest('media', undefined)).toBe(false);
  });
});

describe('allowCheck', () => {
  it('answers like allowRequest: the microphone, for our page, only', () => {
    expect(allowCheck('media', 'app://pseudo', { mediaType: 'audio' })).toBe(true);
    expect(allowCheck('media', 'app://pseudo', { mediaType: 'video' })).toBe(false);
    expect(allowCheck('media', 'app://pseudo', { mediaType: 'unknown' })).toBe(false);
    expect(allowCheck('media', 'https://example.invalid', { mediaType: 'audio' })).toBe(false);
    expect(allowCheck('notifications', 'app://pseudo', { mediaType: 'audio' })).toBe(false);
    expect(allowCheck('media', 'app://pseudo', undefined)).toBe(false);
  });
});
