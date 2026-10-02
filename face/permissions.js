/**
 * M26: the ONE permission the face's page may get: the microphone, for push-to-talk.
 *
 * What it demonstrates: a permission allowlist, like providers.toml for the network (D16).
 * In M18 every permission request was refused. Now exactly one passes:
 *   - the permission is 'media' (Chromium's name for microphone and camera),
 *   - for AUDIO ONLY: a request that also wants the camera is refused whole,
 *   - and only from our own page, app://pseudo. No other page can be loaded, but if one ever were,
 *     it couldn't open the microphone.
 * Everything else (camera, notifications, location, clipboard...) is still refused.
 * Electron asks in two ways: a REQUEST (getUserMedia wants the mic now) and a CHECK (may this page
 * use the mic at all, e.g. before listing devices). Both get the same answer.
 */

/** Is this URL (or origin) our own page? app://pseudo/... and nothing else. */
function isOurPage(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'app:' && parsed.host === 'pseudo';
  } catch {
    return false;
  }
}

/** setPermissionRequestHandler: details.mediaTypes lists what getUserMedia asked for. */
function allowRequest(permission, details) {
  const types = details && details.mediaTypes;
  return permission === 'media' && Array.isArray(types) && types.length > 0
    && types.every((type) => type === 'audio') && isOurPage(details.requestingUrl);
}

/** setPermissionCheckHandler: details.mediaType is 'audio', 'video' or 'unknown'. */
function allowCheck(permission, requestingOrigin, details) {
  return permission === 'media' && Boolean(details) && details.mediaType === 'audio' && isOurPage(requestingOrigin);
}

module.exports = { allowCheck, allowRequest, isOurPage };
