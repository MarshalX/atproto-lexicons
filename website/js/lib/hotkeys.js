const isApple = /mac|iphone|ipad/i.test(navigator.userAgentData?.platform || navigator.platform || '');

function isTyping(target) {
  return target instanceof HTMLElement && (target.isContentEditable || /^(input|textarea|select)$/i.test(target.tagName));
}

function parse(combo) {
  const keys = combo.toLowerCase().split('+');
  return { key: keys.pop(), mod: keys.includes('mod'), shift: keys.includes('shift'), alt: keys.includes('alt') };
}

function matches(event, { key, mod, shift, alt }) {
  const modPressed = isApple ? event.metaKey : event.ctrlKey;
  const otherMod = isApple ? event.ctrlKey : event.metaKey;

  // a plain key is matched as typed, so "/" works on layouts where it needs shift
  return (
    event.key.toLowerCase() === key && modPressed === mod && !otherMod && event.altKey === alt && (!mod || event.shiftKey === shift)
  );
}

export function bindHotkeys(bindings) {
  const entries = bindings.flatMap(([combos, action]) => combos.map((combo) => [parse(combo), action]));

  document.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || event.isComposing) return;

    for (const [combo, action] of entries) {
      if (!matches(event, combo) || (!combo.mod && isTyping(event.target))) continue;

      event.preventDefault();
      action(event);
      return;
    }
  });
}
