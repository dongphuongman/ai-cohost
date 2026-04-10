import type { PlatformAdapter, SmartPasteResult } from '@/adapters/types';

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function getInputText(el: HTMLElement): string {
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
    return el.value;
  }
  return el.textContent ?? '';
}

function showSendHint(input: HTMLElement): void {
  const hint = document.createElement('div');
  hint.textContent = 'Nhấn Enter để gửi';
  hint.style.cssText =
    'position:absolute;z-index:999999;background:#5B47E0;color:#fff;padding:4px 10px;' +
    'border-radius:6px;font-size:12px;white-space:nowrap;pointer-events:none;' +
    'box-shadow:0 2px 8px rgba(0,0,0,.15);';

  const rect = input.getBoundingClientRect();
  hint.style.left = `${rect.left + window.scrollX}px`;
  hint.style.top = `${rect.top + window.scrollY - 30}px`;
  document.body.appendChild(hint);

  setTimeout(() => hint.remove(), 4000);
}

/**
 * Smart paste text into the platform's comment input.
 *
 * BOUNDARY: NEVER dispatch Enter keypress, NEVER click send button,
 * NEVER simulate submit events. The user must press Enter themselves.
 */
export async function smartPaste(
  text: string,
  adapter: PlatformAdapter,
): Promise<SmartPasteResult> {
  // 1. Find input
  const input = adapter.findCommentInput();
  if (!input) {
    return { success: false, error: 'input_not_found' };
  }

  // Check if input is disabled
  if (
    (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) &&
    input.disabled
  ) {
    return { success: false, error: 'input_disabled' };
  }

  // 2. Focus input
  input.focus();
  await sleep(100);

  // 3. Select all existing content (to replace)
  if (input instanceof HTMLElement && input.isContentEditable) {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(input);
    selection?.removeAllRanges();
    selection?.addRange(range);
  } else if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
    input.select();
  }

  // 4. Insert text — try multiple methods
  // Method 1: execCommand (works best with React/Vue managed inputs)
  let inserted = document.execCommand('insertText', false, text);

  if (!inserted) {
    // Method 2: ClipboardEvent
    const clipboardData = new DataTransfer();
    clipboardData.setData('text/plain', text);
    const pasteEvent = new ClipboardEvent('paste', {
      clipboardData,
      bubbles: true,
      cancelable: true,
    });
    input.dispatchEvent(pasteEvent);
    inserted = true;
  }

  // 5. Verify text was inserted
  await sleep(200);
  const verifySnippet = text.substring(0, 20);
  let currentText = getInputText(input);

  if (!currentText.includes(verifySnippet)) {
    // Method 3: Direct value set (last resort, may not trigger framework state)
    if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        'value',
      )?.set;
      nativeInputValueSetter?.call(input, text);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } else if (input.isContentEditable) {
      // For contenteditable, set innerHTML directly
      input.textContent = text;
      input.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
    }
  }

  // 6. Final verify
  await sleep(100);
  currentText = getInputText(input);
  if (!currentText.includes(verifySnippet)) {
    return { success: false, error: 'paste_failed' };
  }

  // 7. Show tooltip near input
  showSendHint(input);

  return { success: true };
}
