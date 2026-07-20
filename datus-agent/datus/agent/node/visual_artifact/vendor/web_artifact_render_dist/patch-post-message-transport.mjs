import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const upstreamPackage = "@datus/web-artifact-render@0.1.7";
const upstreamSha256 = "37aad622dadc7d0b4213cc2ef403038bc9081033caff5cd3f6a216966105d378";
const patchedSha256 = "4c8c89cc47578b80b8732a180f4a245655c00429e9f0ba2b7d6a0c6f57561745";
const bundlePath = fileURLToPath(new URL("./index.umd.js", import.meta.url));

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

function assertSha256(label, content, expected) {
  const actual = sha256(content);
  if (actual !== expected) {
    throw new Error(`${label}: SHA-256 mismatch (expected ${expected}, got ${actual})`);
  }
}

function applyPatch(upstreamBundle) {
  let bundle = upstreamBundle;

  function replaceOnce(label, before, after) {
    const first = bundle.indexOf(before);
    if (first === -1) throw new Error(`${label}: expected upstream anchor was not found`);
    if (bundle.indexOf(before, first + before.length) !== -1) {
      throw new Error(`${label}: upstream anchor is no longer unique`);
    }
    bundle = `${bundle.slice(0, first)}${after}${bundle.slice(first + before.length)}`;
  }

  const providerFactoryBefore = "function UOe(e){if(e.provider){if(e.provider.mode===\"bundled\")return new kH(e.provider.queries??[]);if(e.provider.mode===\"remote\")return new Hie(e.provider);throw new Error(`Unknown provider mode: ${e.provider.mode}`)}return new kH(e.queries??[])}";
  const providerFactoryAfter = "function UOe(e){if(e.provider){if(e.provider.mode===\"bundled\")return new kH(e.provider.queries??[]);if(e.provider.mode===\"remote\")return new Hie(e.provider);if(e.provider.mode===\"post-message\")return new DatusPostMessageQueryProvider(e.provider);throw new Error(`Unknown provider mode: ${e.provider.mode}`)}return new kH(e.queries??[])}";

  const providerInsertionAnchor = "}function m$e({minHeight:e=320";
  const postMessageProvider = `}let datusPostMessageRequestSequence=0;class DatusPostMessageQueryProvider{constructor(t){const{dashboardSlug:n,requestType:r=\"datus-artifact/query\",resultType:a=\"datus-artifact/query-result\",timeoutMs:o=3e4}=t;if(!n)throw new Error(\"PostMessageQueryArtifactProvider: dashboardSlug is required\");this.options={...t,requestType:r,resultType:a,timeoutMs:o}}async querySql(t,n){const{dashboardSlug:r,publishedVersion:a,requestType:o,resultType:i,timeoutMs:c}=this.options,s=iu(t),u={dashboard_slug:r,query_slug:s,params:n??{}};typeof a==\"number\"&&(u.published_version=a),datusPostMessageRequestSequence+=1;const p=Date.now().toString(36)+\"-\"+datusPostMessageRequestSequence.toString(36);return new Promise((h,f)=>{const m=window.top;if(!m){f(new Error(\"Dashboard query host is unavailable\"));return}let v;const _=()=>{clearTimeout(v),window.removeEventListener(\"message\",w),window.removeEventListener(\"pagehide\",k)},w=b=>{const C=b.data;if(b.source!==m||!C||typeof C!=\"object\"||C.type!==i||C.requestId!==p)return;_();const E=C.payload;if(!(C.status>=200&&C.status<300)||!E||E.success!==!0){f(new Error(E&&typeof E.errorMessage==\"string\"?E.errorMessage:\"Query \\\'\"+t+\"\\\' failed\"));return}if(!E.data){f(new Error(\"Query \\\'\"+t+\"\\\' returned no result data\"));return}h(E.data)},k=b=>{if(b.persisted)return;_(),f(new DOMException(\"Artifact preview was closed\",\"AbortError\"))};window.addEventListener(\"message\",w),window.addEventListener(\"pagehide\",k),v=setTimeout(()=>{_(),f(new Error(\"Query \\\'\"+t+\"\\\' timed out\"))},c),m.postMessage({type:o,requestId:p,body:u},\"*\")})}}function m$e({minHeight:e=320`;

  const dashboardComponentBefore = 'B2={dashboard:"_dashboard_19jt0_1",frame:"_frame_19jt0_7"},$2=({dashboardSlug:r,renderFiles:e,queryEndpoint:n,publishedVersion:o,queryHeaders:i,queryTimeoutMs:c,title:l,className:d,refreshKey:f,sourceMaps:p,editable:m})=>{const g=x.useMemo(()=>({mode:"remote",dashboardSlug:r,endpoint:n,publishedVersion:o,headers:i,timeoutMs:c}),[r,n,o,i,c]);return Z.createElement("div",{className:`${B2.dashboard} ${d??""}`.trim()},Z.createElement(q2,{key:f??0,renderFiles:e,provider:g,kind:"dashboard",slug:r,sourceMaps:p,editable:m,title:l,className:B2.frame}))};';
  const dashboardComponentAfter = 'B2={dashboard:"_dashboard_19jt0_1",frame:"_frame_19jt0_7"},$2=({dashboardSlug:r,renderFiles:e,queryEndpoint:n,publishedVersion:o,queryHeaders:i,queryTimeoutMs:c,queryTransport:l,title:d,className:f,refreshKey:p,sourceMaps:m,editable:g})=>{const v=x.useMemo(()=>l?{...l,mode:"post-message",dashboardSlug:r,publishedVersion:o,timeoutMs:l.timeoutMs??c}:{mode:"remote",dashboardSlug:r,endpoint:n,publishedVersion:o,headers:i,timeoutMs:c},[r,n,o,i,c,l]);return Z.createElement("div",{className:`${B2.dashboard} ${f??""}`.trim()},Z.createElement(q2,{key:p??0,renderFiles:e,provider:v,kind:"dashboard",slug:r,sourceMaps:m,editable:g,title:d,className:B2.frame}))};';

  const copyHelperAnchor = 'const $t={frame:"_frame_q7x45_1"';
  const copyHelper = 'async function datusCopyText(r){const e=navigator.clipboard;if(e&&typeof e.writeText==="function")try{await e.writeText(r);return}catch{}const n=document.createElement("textarea"),o=typeof document.getSelection==="function"?document.getSelection():null,i=o&&o.rangeCount>0?o.getRangeAt(0).cloneRange():null;n.value=r,n.setAttribute("readonly",""),n.style.position="fixed",n.style.left="-9999px",n.style.opacity="0",document.body.appendChild(n),n.focus(),n.select();try{typeof n.setSelectionRange==="function"&&n.setSelectionRange(0,n.value.length);if(typeof document.execCommand!=="function"||!document.execCommand("copy"))throw new Error("Clipboard copy failed")}finally{n.parentNode&&n.parentNode.removeChild(n),i&&o&&(o.removeAllRanges(),o.addRange(i))}}const $t={frame:"_frame_q7x45_1"';

  const copyFixActionBefore = 'onClick:()=>{const W=G(!0);navigator.clipboard.writeText(W),uc.success("Fix prompt copied")}';
  const copyFixActionAfter = 'onClick:async()=>{const W=G(!0);try{await datusCopyText(W),uc.success("Fix prompt copied")}catch{uc.error("Fix prompt copy failed")}}';

  const initDashboardBefore = 'function y6(r){const{rootId:e="root",dataScriptId:n="datus-dashboard-data",detail:o,lang:i,queryEndpoint:c,publishedVersion:l,queryHeaders:d,queryTimeoutMs:f}=r;G2();const p=o??W2(n,"__DATUS_DASHBOARD_DATA__","[DatusArtifact:dashboard]"),m=M2({lng:i});U2({entry:"dashboard",el:`#${e}`,render:()=>Z.createElement(qh,{i18n:m},p?(()=>{const{renderFiles:g}=V2(p.files);return Z.createElement($2,{dashboardSlug:p.slug,renderFiles:g,queryEndpoint:c,publishedVersion:l??p.published_version,queryHeaders:d,queryTimeoutMs:f,title:p.name})})():K2(`No dashboard data found. Provide IDashboardDetail inline via options.detail or in a <script id="${n}" type="application/json"> tag.`))})}';
  const initDashboardAfter = 'function y6(r){const{rootId:e="root",dataScriptId:n="datus-dashboard-data",detail:o,lang:i,queryEndpoint:c,publishedVersion:l,queryHeaders:d,queryTimeoutMs:f,queryTransport:p}=r;G2();const m=o??W2(n,"__DATUS_DASHBOARD_DATA__","[DatusArtifact:dashboard]"),g=M2({lng:i});U2({entry:"dashboard",el:`#${e}`,render:()=>Z.createElement(qh,{i18n:g},m?(()=>{const{renderFiles:v}=V2(m.files);return Z.createElement($2,{dashboardSlug:m.slug,renderFiles:v,queryEndpoint:c,publishedVersion:l??m.published_version,queryHeaders:d,queryTimeoutMs:f,queryTransport:p,title:m.name})})():K2(`No dashboard data found. Provide IDashboardDetail inline via options.detail or in a <script id="${n}" type="application/json"> tag.`))})}';

  replaceOnce("inner provider", providerInsertionAnchor, postMessageProvider);
  replaceOnce("inner provider factory", providerFactoryBefore, providerFactoryAfter);
  replaceOnce("dashboard component", dashboardComponentBefore, dashboardComponentAfter);
  replaceOnce("dashboard initializer", initDashboardBefore, initDashboardAfter);
  replaceOnce("copy helper", copyHelperAnchor, copyHelper);
  replaceOnce("copy fix action", copyFixActionBefore, copyFixActionAfter);
  return bundle;
}

const args = process.argv.slice(2);
if (args.length > 1 || (args.length === 1 && args[0] !== "--check")) {
  throw new Error("Usage: node patch-post-message-transport.mjs [--check]");
}

const currentBundle = readFileSync(bundlePath, "utf8");
if (args[0] === "--check") {
  assertSha256("patched renderer", currentBundle, patchedSha256);
  console.log(`Verified patched ${upstreamPackage} renderer: ${patchedSha256}`);
} else {
  assertSha256(`upstream ${upstreamPackage} renderer`, currentBundle, upstreamSha256);
  const patchedBundle = applyPatch(currentBundle);
  assertSha256("generated patched renderer", patchedBundle, patchedSha256);
  writeFileSync(bundlePath, patchedBundle);
  console.log(`Patched ${upstreamPackage} renderer: ${patchedSha256}`);
}
