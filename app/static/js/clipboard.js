/* Phase 6 SRCH-01: WYSIWYG clipboard serializer (D-12, D-13).
 * Reads visible profile-card DOM, formats key:value lines, and copies via
 * navigator.clipboard.writeText. Unexpanded sections (aria-expanded="false")
 * emit one "Not loaded" line — never their field rows.
 */
(function () {
  'use strict';
  function clean(t) { return (t || '').replace(/\s+/g, ' ').trim(); }

  function serializeCard(cardEl) {
    var lines = [];
    cardEl.querySelectorAll('[data-copy-field]').forEach(function (el) {
      if (el.closest('[role="region"]')) return;
      lines.push(el.dataset.copyField + ': ' + clean(el.textContent));
    });
    cardEl.querySelectorAll('button[aria-controls]').forEach(function (header) {
      var expanded = header.getAttribute('aria-expanded') === 'true';
      var body = document.getElementById(header.getAttribute('aria-controls'));
      lines.push('');
      lines.push(clean(header.textContent));
      if (!expanded || !body) { lines.push('Not loaded'); return; }
      var fields = body.querySelectorAll('[data-copy-field]');
      if (fields.length === 0) { lines.push('No data'); return; }
      fields.forEach(function (el) {
        lines.push(el.dataset.copyField + ': ' + clean(el.textContent));
      });
    });
    return lines.join('\n');
  }

  window.copyProfileToClipboard = function (cardEl) {
    var fail = function () { showToast("Couldn't copy. Select the text and copy manually.", 'error'); };
    if (!cardEl) { fail(); return; }
    if (!navigator.clipboard || !navigator.clipboard.writeText) { fail(); return; }
    navigator.clipboard.writeText(serializeCard(cardEl)).then(
      function () { showToast('Copied profile to clipboard', 'success'); },
      fail
    );
  };
})();
