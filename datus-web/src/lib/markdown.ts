import MarkdownIt from "markdown-it";

/** Shared MarkdownIt instance used across the app. */
export const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
});

// Block dangerous URI schemes (XSS prevention)
const SAFE_SCHEMES = /^(https?|mailto|tel):/i;
const ABSOLUTE_SCHEME = /^[a-z][a-z0-9+\-.]*:/i;
md.validateLink = (url: string) => {
  const normalized = url.trim();
  if (SAFE_SCHEMES.test(normalized)) return true;
  if (ABSOLUTE_SCHEME.test(normalized) || normalized.startsWith("//")) return false;
  return true;
};

md.enable("table");
md.enable("strikethrough");

// Open all links in a new tab
const defaultRender =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options);
  };
md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noreferrer");
  return defaultRender(tokens, idx, options, env, self);
};
