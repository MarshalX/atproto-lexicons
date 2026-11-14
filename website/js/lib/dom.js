const SVG_NS = 'http://www.w3.org/2000/svg';

export const $ = (selector, root = document) => root.querySelector(selector);

export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);

  for (const [name, value] of Object.entries(props)) {
    if (value === false || value == null) continue;

    if (name === 'class') node.className = value;
    else if (name === 'text') node.textContent = value;
    else if (name === 'style') node.style.cssText = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? '' : value);
  }

  node.append(...children.flat().filter((child) => child != null && child !== false));
  return node;
}

export function icon(name, size = 16, className = '') {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', `icon ${className}`.trim());
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('aria-hidden', 'true');

  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);

  return svg;
}
