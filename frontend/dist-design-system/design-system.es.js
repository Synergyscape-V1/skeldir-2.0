import { jsx as f, jsxs as S, Fragment as G } from "react/jsx-runtime";
import * as c from "react";
import fe, { forwardRef as Gs, createElement as Zn, useState as z, useEffect as ee, useLayoutEffect as Ks, createContext as Lr, useContext as Fr, useRef as j, useId as qs, useCallback as Ce } from "react";
import * as wt from "react-dom";
import Ys, { createPortal as Xs } from "react-dom";
function Vr(e) {
  var t, n, r = "";
  if (typeof e == "string" || typeof e == "number") r += e;
  else if (typeof e == "object") if (Array.isArray(e)) {
    var o = e.length;
    for (t = 0; t < o; t++) e[t] && (n = Vr(e[t])) && (r && (r += " "), r += n);
  } else for (n in e) e[n] && (r && (r += " "), r += n);
  return r;
}
function Wr() {
  for (var e, t, n = 0, r = "", o = arguments.length; n < o; n++) (e = arguments[n]) && (t = Vr(e)) && (r && (r += " "), r += t);
  return r;
}
const hn = "-", Zs = (e) => {
  const t = Js(e), {
    conflictingClassGroups: n,
    conflictingClassGroupModifiers: r
  } = e;
  return {
    getClassGroupId: (a) => {
      const s = a.split(hn);
      return s[0] === "" && s.length !== 1 && s.shift(), Br(s, t) || Qs(a);
    },
    getConflictingClassGroupIds: (a, s) => {
      const l = n[a] || [];
      return s && r[a] ? [...l, ...r[a]] : l;
    }
  };
}, Br = (e, t) => {
  var a;
  if (e.length === 0)
    return t.classGroupId;
  const n = e[0], r = t.nextPart.get(n), o = r ? Br(e.slice(1), r) : void 0;
  if (o)
    return o;
  if (t.validators.length === 0)
    return;
  const i = e.join(hn);
  return (a = t.validators.find(({
    validator: s
  }) => s(i))) == null ? void 0 : a.classGroupId;
}, Qn = /^\[(.+)\]$/, Qs = (e) => {
  if (Qn.test(e)) {
    const t = Qn.exec(e)[1], n = t == null ? void 0 : t.substring(0, t.indexOf(":"));
    if (n)
      return "arbitrary.." + n;
  }
}, Js = (e) => {
  const {
    theme: t,
    prefix: n
  } = e, r = {
    nextPart: /* @__PURE__ */ new Map(),
    validators: []
  };
  return ta(Object.entries(e.classGroups), n).forEach(([i, a]) => {
    en(a, r, i, t);
  }), r;
}, en = (e, t, n, r) => {
  e.forEach((o) => {
    if (typeof o == "string") {
      const i = o === "" ? t : Jn(t, o);
      i.classGroupId = n;
      return;
    }
    if (typeof o == "function") {
      if (ea(o)) {
        en(o(r), t, n, r);
        return;
      }
      t.validators.push({
        validator: o,
        classGroupId: n
      });
      return;
    }
    Object.entries(o).forEach(([i, a]) => {
      en(a, Jn(t, i), n, r);
    });
  });
}, Jn = (e, t) => {
  let n = e;
  return t.split(hn).forEach((r) => {
    n.nextPart.has(r) || n.nextPart.set(r, {
      nextPart: /* @__PURE__ */ new Map(),
      validators: []
    }), n = n.nextPart.get(r);
  }), n;
}, ea = (e) => e.isThemeGetter, ta = (e, t) => t ? e.map(([n, r]) => {
  const o = r.map((i) => typeof i == "string" ? t + i : typeof i == "object" ? Object.fromEntries(Object.entries(i).map(([a, s]) => [t + a, s])) : i);
  return [n, o];
}) : e, na = (e) => {
  if (e < 1)
    return {
      get: () => {
      },
      set: () => {
      }
    };
  let t = 0, n = /* @__PURE__ */ new Map(), r = /* @__PURE__ */ new Map();
  const o = (i, a) => {
    n.set(i, a), t++, t > e && (t = 0, r = n, n = /* @__PURE__ */ new Map());
  };
  return {
    get(i) {
      let a = n.get(i);
      if (a !== void 0)
        return a;
      if ((a = r.get(i)) !== void 0)
        return o(i, a), a;
    },
    set(i, a) {
      n.has(i) ? n.set(i, a) : o(i, a);
    }
  };
}, jr = "!", ra = (e) => {
  const {
    separator: t,
    experimentalParseClassName: n
  } = e, r = t.length === 1, o = t[0], i = t.length, a = (s) => {
    const l = [];
    let u = 0, p = 0, d;
    for (let v = 0; v < s.length; v++) {
      let y = s[v];
      if (u === 0) {
        if (y === o && (r || s.slice(v, v + i) === t)) {
          l.push(s.slice(p, v)), p = v + i;
          continue;
        }
        if (y === "/") {
          d = v;
          continue;
        }
      }
      y === "[" ? u++ : y === "]" && u--;
    }
    const m = l.length === 0 ? s : s.substring(p), h = m.startsWith(jr), b = h ? m.substring(1) : m, g = d && d > p ? d - p : void 0;
    return {
      modifiers: l,
      hasImportantModifier: h,
      baseClassName: b,
      maybePostfixModifierPosition: g
    };
  };
  return n ? (s) => n({
    className: s,
    parseClassName: a
  }) : a;
}, oa = (e) => {
  if (e.length <= 1)
    return e;
  const t = [];
  let n = [];
  return e.forEach((r) => {
    r[0] === "[" ? (t.push(...n.sort(), r), n = []) : n.push(r);
  }), t.push(...n.sort()), t;
}, ia = (e) => ({
  cache: na(e.cacheSize),
  parseClassName: ra(e),
  ...Zs(e)
}), sa = /\s+/, aa = (e, t) => {
  const {
    parseClassName: n,
    getClassGroupId: r,
    getConflictingClassGroupIds: o
  } = t, i = [], a = e.trim().split(sa);
  let s = "";
  for (let l = a.length - 1; l >= 0; l -= 1) {
    const u = a[l], {
      modifiers: p,
      hasImportantModifier: d,
      baseClassName: m,
      maybePostfixModifierPosition: h
    } = n(u);
    let b = !!h, g = r(b ? m.substring(0, h) : m);
    if (!g) {
      if (!b) {
        s = u + (s.length > 0 ? " " + s : s);
        continue;
      }
      if (g = r(m), !g) {
        s = u + (s.length > 0 ? " " + s : s);
        continue;
      }
      b = !1;
    }
    const v = oa(p).join(":"), y = d ? v + jr : v, w = y + g;
    if (i.includes(w))
      continue;
    i.push(w);
    const C = o(g, b);
    for (let x = 0; x < C.length; ++x) {
      const E = C[x];
      i.push(y + E);
    }
    s = u + (s.length > 0 ? " " + s : s);
  }
  return s;
};
function ca() {
  let e = 0, t, n, r = "";
  for (; e < arguments.length; )
    (t = arguments[e++]) && (n = Hr(t)) && (r && (r += " "), r += n);
  return r;
}
const Hr = (e) => {
  if (typeof e == "string")
    return e;
  let t, n = "";
  for (let r = 0; r < e.length; r++)
    e[r] && (t = Hr(e[r])) && (n && (n += " "), n += t);
  return n;
};
function la(e, ...t) {
  let n, r, o, i = a;
  function a(l) {
    const u = t.reduce((p, d) => d(p), e());
    return n = ia(u), r = n.cache.get, o = n.cache.set, i = s, s(l);
  }
  function s(l) {
    const u = r(l);
    if (u)
      return u;
    const p = aa(l, n);
    return o(l, p), p;
  }
  return function() {
    return i(ca.apply(null, arguments));
  };
}
const H = (e) => {
  const t = (n) => n[e] || [];
  return t.isThemeGetter = !0, t;
}, zr = /^\[(?:([a-z-]+):)?(.+)\]$/i, ua = /^\d+\/\d+$/, da = /* @__PURE__ */ new Set(["px", "full", "screen"]), fa = /^(\d+(\.\d+)?)?(xs|sm|md|lg|xl)$/, pa = /\d+(%|px|r?em|[sdl]?v([hwib]|min|max)|pt|pc|in|cm|mm|cap|ch|ex|r?lh|cq(w|h|i|b|min|max))|\b(calc|min|max|clamp)\(.+\)|^0$/, ma = /^(rgba?|hsla?|hwb|(ok)?(lab|lch))\(.+\)$/, ga = /^(inset_)?-?((\d+)?\.?(\d+)[a-z]+|0)_-?((\d+)?\.?(\d+)[a-z]+|0)/, ha = /^(url|image|image-set|cross-fade|element|(repeating-)?(linear|radial|conic)-gradient)\(.+\)$/, de = (e) => Ae(e) || da.has(e) || ua.test(e), ge = (e) => De(e, "length", Sa), Ae = (e) => !!e && !Number.isNaN(Number(e)), Ft = (e) => De(e, "number", Ae), je = (e) => !!e && Number.isInteger(Number(e)), va = (e) => e.endsWith("%") && Ae(e.slice(0, -1)), D = (e) => zr.test(e), he = (e) => fa.test(e), ba = /* @__PURE__ */ new Set(["length", "size", "percentage"]), ya = (e) => De(e, ba, Ur), xa = (e) => De(e, "position", Ur), wa = /* @__PURE__ */ new Set(["image", "url"]), Ca = (e) => De(e, wa, Ra), Ea = (e) => De(e, "", Na), He = () => !0, De = (e, t, n) => {
  const r = zr.exec(e);
  return r ? r[1] ? typeof t == "string" ? r[1] === t : t.has(r[1]) : n(r[2]) : !1;
}, Sa = (e) => (
  // `colorFunctionRegex` check is necessary because color functions can have percentages in them which which would be incorrectly classified as lengths.
  // For example, `hsl(0 0% 0%)` would be classified as a length without this check.
  // I could also use lookbehind assertion in `lengthUnitRegex` but that isn't supported widely enough.
  pa.test(e) && !ma.test(e)
), Ur = () => !1, Na = (e) => ga.test(e), Ra = (e) => ha.test(e), Ta = () => {
  const e = H("colors"), t = H("spacing"), n = H("blur"), r = H("brightness"), o = H("borderColor"), i = H("borderRadius"), a = H("borderSpacing"), s = H("borderWidth"), l = H("contrast"), u = H("grayscale"), p = H("hueRotate"), d = H("invert"), m = H("gap"), h = H("gradientColorStops"), b = H("gradientColorStopPositions"), g = H("inset"), v = H("margin"), y = H("opacity"), w = H("padding"), C = H("saturate"), x = H("scale"), E = H("sepia"), N = H("skew"), R = H("space"), A = H("translate"), P = () => ["auto", "contain", "none"], _ = () => ["auto", "hidden", "clip", "visible", "scroll"], I = () => ["auto", D, t], k = () => [D, t], V = () => ["", de, ge], T = () => ["auto", Ae, D], M = () => ["bottom", "center", "left", "left-bottom", "left-top", "right", "right-bottom", "right-top", "top"], O = () => ["solid", "dashed", "dotted", "double", "none"], W = () => ["normal", "multiply", "screen", "overlay", "darken", "lighten", "color-dodge", "color-burn", "hard-light", "soft-light", "difference", "exclusion", "hue", "saturation", "color", "luminosity"], $ = () => ["start", "end", "center", "between", "around", "evenly", "stretch"], B = () => ["", "0", D], q = () => ["auto", "avoid", "all", "avoid-page", "page", "left", "right", "column"], K = () => [Ae, D];
  return {
    cacheSize: 500,
    separator: ":",
    theme: {
      colors: [He],
      spacing: [de, ge],
      blur: ["none", "", he, D],
      brightness: K(),
      borderColor: [e],
      borderRadius: ["none", "", "full", he, D],
      borderSpacing: k(),
      borderWidth: V(),
      contrast: K(),
      grayscale: B(),
      hueRotate: K(),
      invert: B(),
      gap: k(),
      gradientColorStops: [e],
      gradientColorStopPositions: [va, ge],
      inset: I(),
      margin: I(),
      opacity: K(),
      padding: k(),
      saturate: K(),
      scale: K(),
      sepia: B(),
      skew: K(),
      space: k(),
      translate: k()
    },
    classGroups: {
      // Layout
      /**
       * Aspect Ratio
       * @see https://tailwindcss.com/docs/aspect-ratio
       */
      aspect: [{
        aspect: ["auto", "square", "video", D]
      }],
      /**
       * Container
       * @see https://tailwindcss.com/docs/container
       */
      container: ["container"],
      /**
       * Columns
       * @see https://tailwindcss.com/docs/columns
       */
      columns: [{
        columns: [he]
      }],
      /**
       * Break After
       * @see https://tailwindcss.com/docs/break-after
       */
      "break-after": [{
        "break-after": q()
      }],
      /**
       * Break Before
       * @see https://tailwindcss.com/docs/break-before
       */
      "break-before": [{
        "break-before": q()
      }],
      /**
       * Break Inside
       * @see https://tailwindcss.com/docs/break-inside
       */
      "break-inside": [{
        "break-inside": ["auto", "avoid", "avoid-page", "avoid-column"]
      }],
      /**
       * Box Decoration Break
       * @see https://tailwindcss.com/docs/box-decoration-break
       */
      "box-decoration": [{
        "box-decoration": ["slice", "clone"]
      }],
      /**
       * Box Sizing
       * @see https://tailwindcss.com/docs/box-sizing
       */
      box: [{
        box: ["border", "content"]
      }],
      /**
       * Display
       * @see https://tailwindcss.com/docs/display
       */
      display: ["block", "inline-block", "inline", "flex", "inline-flex", "table", "inline-table", "table-caption", "table-cell", "table-column", "table-column-group", "table-footer-group", "table-header-group", "table-row-group", "table-row", "flow-root", "grid", "inline-grid", "contents", "list-item", "hidden"],
      /**
       * Floats
       * @see https://tailwindcss.com/docs/float
       */
      float: [{
        float: ["right", "left", "none", "start", "end"]
      }],
      /**
       * Clear
       * @see https://tailwindcss.com/docs/clear
       */
      clear: [{
        clear: ["left", "right", "both", "none", "start", "end"]
      }],
      /**
       * Isolation
       * @see https://tailwindcss.com/docs/isolation
       */
      isolation: ["isolate", "isolation-auto"],
      /**
       * Object Fit
       * @see https://tailwindcss.com/docs/object-fit
       */
      "object-fit": [{
        object: ["contain", "cover", "fill", "none", "scale-down"]
      }],
      /**
       * Object Position
       * @see https://tailwindcss.com/docs/object-position
       */
      "object-position": [{
        object: [...M(), D]
      }],
      /**
       * Overflow
       * @see https://tailwindcss.com/docs/overflow
       */
      overflow: [{
        overflow: _()
      }],
      /**
       * Overflow X
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-x": [{
        "overflow-x": _()
      }],
      /**
       * Overflow Y
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-y": [{
        "overflow-y": _()
      }],
      /**
       * Overscroll Behavior
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      overscroll: [{
        overscroll: P()
      }],
      /**
       * Overscroll Behavior X
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-x": [{
        "overscroll-x": P()
      }],
      /**
       * Overscroll Behavior Y
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-y": [{
        "overscroll-y": P()
      }],
      /**
       * Position
       * @see https://tailwindcss.com/docs/position
       */
      position: ["static", "fixed", "absolute", "relative", "sticky"],
      /**
       * Top / Right / Bottom / Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      inset: [{
        inset: [g]
      }],
      /**
       * Right / Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-x": [{
        "inset-x": [g]
      }],
      /**
       * Top / Bottom
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-y": [{
        "inset-y": [g]
      }],
      /**
       * Start
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      start: [{
        start: [g]
      }],
      /**
       * End
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      end: [{
        end: [g]
      }],
      /**
       * Top
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      top: [{
        top: [g]
      }],
      /**
       * Right
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      right: [{
        right: [g]
      }],
      /**
       * Bottom
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      bottom: [{
        bottom: [g]
      }],
      /**
       * Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      left: [{
        left: [g]
      }],
      /**
       * Visibility
       * @see https://tailwindcss.com/docs/visibility
       */
      visibility: ["visible", "invisible", "collapse"],
      /**
       * Z-Index
       * @see https://tailwindcss.com/docs/z-index
       */
      z: [{
        z: ["auto", je, D]
      }],
      // Flexbox and Grid
      /**
       * Flex Basis
       * @see https://tailwindcss.com/docs/flex-basis
       */
      basis: [{
        basis: I()
      }],
      /**
       * Flex Direction
       * @see https://tailwindcss.com/docs/flex-direction
       */
      "flex-direction": [{
        flex: ["row", "row-reverse", "col", "col-reverse"]
      }],
      /**
       * Flex Wrap
       * @see https://tailwindcss.com/docs/flex-wrap
       */
      "flex-wrap": [{
        flex: ["wrap", "wrap-reverse", "nowrap"]
      }],
      /**
       * Flex
       * @see https://tailwindcss.com/docs/flex
       */
      flex: [{
        flex: ["1", "auto", "initial", "none", D]
      }],
      /**
       * Flex Grow
       * @see https://tailwindcss.com/docs/flex-grow
       */
      grow: [{
        grow: B()
      }],
      /**
       * Flex Shrink
       * @see https://tailwindcss.com/docs/flex-shrink
       */
      shrink: [{
        shrink: B()
      }],
      /**
       * Order
       * @see https://tailwindcss.com/docs/order
       */
      order: [{
        order: ["first", "last", "none", je, D]
      }],
      /**
       * Grid Template Columns
       * @see https://tailwindcss.com/docs/grid-template-columns
       */
      "grid-cols": [{
        "grid-cols": [He]
      }],
      /**
       * Grid Column Start / End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start-end": [{
        col: ["auto", {
          span: ["full", je, D]
        }, D]
      }],
      /**
       * Grid Column Start
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start": [{
        "col-start": T()
      }],
      /**
       * Grid Column End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-end": [{
        "col-end": T()
      }],
      /**
       * Grid Template Rows
       * @see https://tailwindcss.com/docs/grid-template-rows
       */
      "grid-rows": [{
        "grid-rows": [He]
      }],
      /**
       * Grid Row Start / End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start-end": [{
        row: ["auto", {
          span: [je, D]
        }, D]
      }],
      /**
       * Grid Row Start
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start": [{
        "row-start": T()
      }],
      /**
       * Grid Row End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-end": [{
        "row-end": T()
      }],
      /**
       * Grid Auto Flow
       * @see https://tailwindcss.com/docs/grid-auto-flow
       */
      "grid-flow": [{
        "grid-flow": ["row", "col", "dense", "row-dense", "col-dense"]
      }],
      /**
       * Grid Auto Columns
       * @see https://tailwindcss.com/docs/grid-auto-columns
       */
      "auto-cols": [{
        "auto-cols": ["auto", "min", "max", "fr", D]
      }],
      /**
       * Grid Auto Rows
       * @see https://tailwindcss.com/docs/grid-auto-rows
       */
      "auto-rows": [{
        "auto-rows": ["auto", "min", "max", "fr", D]
      }],
      /**
       * Gap
       * @see https://tailwindcss.com/docs/gap
       */
      gap: [{
        gap: [m]
      }],
      /**
       * Gap X
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-x": [{
        "gap-x": [m]
      }],
      /**
       * Gap Y
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-y": [{
        "gap-y": [m]
      }],
      /**
       * Justify Content
       * @see https://tailwindcss.com/docs/justify-content
       */
      "justify-content": [{
        justify: ["normal", ...$()]
      }],
      /**
       * Justify Items
       * @see https://tailwindcss.com/docs/justify-items
       */
      "justify-items": [{
        "justify-items": ["start", "end", "center", "stretch"]
      }],
      /**
       * Justify Self
       * @see https://tailwindcss.com/docs/justify-self
       */
      "justify-self": [{
        "justify-self": ["auto", "start", "end", "center", "stretch"]
      }],
      /**
       * Align Content
       * @see https://tailwindcss.com/docs/align-content
       */
      "align-content": [{
        content: ["normal", ...$(), "baseline"]
      }],
      /**
       * Align Items
       * @see https://tailwindcss.com/docs/align-items
       */
      "align-items": [{
        items: ["start", "end", "center", "baseline", "stretch"]
      }],
      /**
       * Align Self
       * @see https://tailwindcss.com/docs/align-self
       */
      "align-self": [{
        self: ["auto", "start", "end", "center", "stretch", "baseline"]
      }],
      /**
       * Place Content
       * @see https://tailwindcss.com/docs/place-content
       */
      "place-content": [{
        "place-content": [...$(), "baseline"]
      }],
      /**
       * Place Items
       * @see https://tailwindcss.com/docs/place-items
       */
      "place-items": [{
        "place-items": ["start", "end", "center", "baseline", "stretch"]
      }],
      /**
       * Place Self
       * @see https://tailwindcss.com/docs/place-self
       */
      "place-self": [{
        "place-self": ["auto", "start", "end", "center", "stretch"]
      }],
      // Spacing
      /**
       * Padding
       * @see https://tailwindcss.com/docs/padding
       */
      p: [{
        p: [w]
      }],
      /**
       * Padding X
       * @see https://tailwindcss.com/docs/padding
       */
      px: [{
        px: [w]
      }],
      /**
       * Padding Y
       * @see https://tailwindcss.com/docs/padding
       */
      py: [{
        py: [w]
      }],
      /**
       * Padding Start
       * @see https://tailwindcss.com/docs/padding
       */
      ps: [{
        ps: [w]
      }],
      /**
       * Padding End
       * @see https://tailwindcss.com/docs/padding
       */
      pe: [{
        pe: [w]
      }],
      /**
       * Padding Top
       * @see https://tailwindcss.com/docs/padding
       */
      pt: [{
        pt: [w]
      }],
      /**
       * Padding Right
       * @see https://tailwindcss.com/docs/padding
       */
      pr: [{
        pr: [w]
      }],
      /**
       * Padding Bottom
       * @see https://tailwindcss.com/docs/padding
       */
      pb: [{
        pb: [w]
      }],
      /**
       * Padding Left
       * @see https://tailwindcss.com/docs/padding
       */
      pl: [{
        pl: [w]
      }],
      /**
       * Margin
       * @see https://tailwindcss.com/docs/margin
       */
      m: [{
        m: [v]
      }],
      /**
       * Margin X
       * @see https://tailwindcss.com/docs/margin
       */
      mx: [{
        mx: [v]
      }],
      /**
       * Margin Y
       * @see https://tailwindcss.com/docs/margin
       */
      my: [{
        my: [v]
      }],
      /**
       * Margin Start
       * @see https://tailwindcss.com/docs/margin
       */
      ms: [{
        ms: [v]
      }],
      /**
       * Margin End
       * @see https://tailwindcss.com/docs/margin
       */
      me: [{
        me: [v]
      }],
      /**
       * Margin Top
       * @see https://tailwindcss.com/docs/margin
       */
      mt: [{
        mt: [v]
      }],
      /**
       * Margin Right
       * @see https://tailwindcss.com/docs/margin
       */
      mr: [{
        mr: [v]
      }],
      /**
       * Margin Bottom
       * @see https://tailwindcss.com/docs/margin
       */
      mb: [{
        mb: [v]
      }],
      /**
       * Margin Left
       * @see https://tailwindcss.com/docs/margin
       */
      ml: [{
        ml: [v]
      }],
      /**
       * Space Between X
       * @see https://tailwindcss.com/docs/space
       */
      "space-x": [{
        "space-x": [R]
      }],
      /**
       * Space Between X Reverse
       * @see https://tailwindcss.com/docs/space
       */
      "space-x-reverse": ["space-x-reverse"],
      /**
       * Space Between Y
       * @see https://tailwindcss.com/docs/space
       */
      "space-y": [{
        "space-y": [R]
      }],
      /**
       * Space Between Y Reverse
       * @see https://tailwindcss.com/docs/space
       */
      "space-y-reverse": ["space-y-reverse"],
      // Sizing
      /**
       * Width
       * @see https://tailwindcss.com/docs/width
       */
      w: [{
        w: ["auto", "min", "max", "fit", "svw", "lvw", "dvw", D, t]
      }],
      /**
       * Min-Width
       * @see https://tailwindcss.com/docs/min-width
       */
      "min-w": [{
        "min-w": [D, t, "min", "max", "fit"]
      }],
      /**
       * Max-Width
       * @see https://tailwindcss.com/docs/max-width
       */
      "max-w": [{
        "max-w": [D, t, "none", "full", "min", "max", "fit", "prose", {
          screen: [he]
        }, he]
      }],
      /**
       * Height
       * @see https://tailwindcss.com/docs/height
       */
      h: [{
        h: [D, t, "auto", "min", "max", "fit", "svh", "lvh", "dvh"]
      }],
      /**
       * Min-Height
       * @see https://tailwindcss.com/docs/min-height
       */
      "min-h": [{
        "min-h": [D, t, "min", "max", "fit", "svh", "lvh", "dvh"]
      }],
      /**
       * Max-Height
       * @see https://tailwindcss.com/docs/max-height
       */
      "max-h": [{
        "max-h": [D, t, "min", "max", "fit", "svh", "lvh", "dvh"]
      }],
      /**
       * Size
       * @see https://tailwindcss.com/docs/size
       */
      size: [{
        size: [D, t, "auto", "min", "max", "fit"]
      }],
      // Typography
      /**
       * Font Size
       * @see https://tailwindcss.com/docs/font-size
       */
      "font-size": [{
        text: ["base", he, ge]
      }],
      /**
       * Font Smoothing
       * @see https://tailwindcss.com/docs/font-smoothing
       */
      "font-smoothing": ["antialiased", "subpixel-antialiased"],
      /**
       * Font Style
       * @see https://tailwindcss.com/docs/font-style
       */
      "font-style": ["italic", "not-italic"],
      /**
       * Font Weight
       * @see https://tailwindcss.com/docs/font-weight
       */
      "font-weight": [{
        font: ["thin", "extralight", "light", "normal", "medium", "semibold", "bold", "extrabold", "black", Ft]
      }],
      /**
       * Font Family
       * @see https://tailwindcss.com/docs/font-family
       */
      "font-family": [{
        font: [He]
      }],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-normal": ["normal-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-ordinal": ["ordinal"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-slashed-zero": ["slashed-zero"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-figure": ["lining-nums", "oldstyle-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-spacing": ["proportional-nums", "tabular-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-fraction": ["diagonal-fractions", "stacked-fractions"],
      /**
       * Letter Spacing
       * @see https://tailwindcss.com/docs/letter-spacing
       */
      tracking: [{
        tracking: ["tighter", "tight", "normal", "wide", "wider", "widest", D]
      }],
      /**
       * Line Clamp
       * @see https://tailwindcss.com/docs/line-clamp
       */
      "line-clamp": [{
        "line-clamp": ["none", Ae, Ft]
      }],
      /**
       * Line Height
       * @see https://tailwindcss.com/docs/line-height
       */
      leading: [{
        leading: ["none", "tight", "snug", "normal", "relaxed", "loose", de, D]
      }],
      /**
       * List Style Image
       * @see https://tailwindcss.com/docs/list-style-image
       */
      "list-image": [{
        "list-image": ["none", D]
      }],
      /**
       * List Style Type
       * @see https://tailwindcss.com/docs/list-style-type
       */
      "list-style-type": [{
        list: ["none", "disc", "decimal", D]
      }],
      /**
       * List Style Position
       * @see https://tailwindcss.com/docs/list-style-position
       */
      "list-style-position": [{
        list: ["inside", "outside"]
      }],
      /**
       * Placeholder Color
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/placeholder-color
       */
      "placeholder-color": [{
        placeholder: [e]
      }],
      /**
       * Placeholder Opacity
       * @see https://tailwindcss.com/docs/placeholder-opacity
       */
      "placeholder-opacity": [{
        "placeholder-opacity": [y]
      }],
      /**
       * Text Alignment
       * @see https://tailwindcss.com/docs/text-align
       */
      "text-alignment": [{
        text: ["left", "center", "right", "justify", "start", "end"]
      }],
      /**
       * Text Color
       * @see https://tailwindcss.com/docs/text-color
       */
      "text-color": [{
        text: [e]
      }],
      /**
       * Text Opacity
       * @see https://tailwindcss.com/docs/text-opacity
       */
      "text-opacity": [{
        "text-opacity": [y]
      }],
      /**
       * Text Decoration
       * @see https://tailwindcss.com/docs/text-decoration
       */
      "text-decoration": ["underline", "overline", "line-through", "no-underline"],
      /**
       * Text Decoration Style
       * @see https://tailwindcss.com/docs/text-decoration-style
       */
      "text-decoration-style": [{
        decoration: [...O(), "wavy"]
      }],
      /**
       * Text Decoration Thickness
       * @see https://tailwindcss.com/docs/text-decoration-thickness
       */
      "text-decoration-thickness": [{
        decoration: ["auto", "from-font", de, ge]
      }],
      /**
       * Text Underline Offset
       * @see https://tailwindcss.com/docs/text-underline-offset
       */
      "underline-offset": [{
        "underline-offset": ["auto", de, D]
      }],
      /**
       * Text Decoration Color
       * @see https://tailwindcss.com/docs/text-decoration-color
       */
      "text-decoration-color": [{
        decoration: [e]
      }],
      /**
       * Text Transform
       * @see https://tailwindcss.com/docs/text-transform
       */
      "text-transform": ["uppercase", "lowercase", "capitalize", "normal-case"],
      /**
       * Text Overflow
       * @see https://tailwindcss.com/docs/text-overflow
       */
      "text-overflow": ["truncate", "text-ellipsis", "text-clip"],
      /**
       * Text Wrap
       * @see https://tailwindcss.com/docs/text-wrap
       */
      "text-wrap": [{
        text: ["wrap", "nowrap", "balance", "pretty"]
      }],
      /**
       * Text Indent
       * @see https://tailwindcss.com/docs/text-indent
       */
      indent: [{
        indent: k()
      }],
      /**
       * Vertical Alignment
       * @see https://tailwindcss.com/docs/vertical-align
       */
      "vertical-align": [{
        align: ["baseline", "top", "middle", "bottom", "text-top", "text-bottom", "sub", "super", D]
      }],
      /**
       * Whitespace
       * @see https://tailwindcss.com/docs/whitespace
       */
      whitespace: [{
        whitespace: ["normal", "nowrap", "pre", "pre-line", "pre-wrap", "break-spaces"]
      }],
      /**
       * Word Break
       * @see https://tailwindcss.com/docs/word-break
       */
      break: [{
        break: ["normal", "words", "all", "keep"]
      }],
      /**
       * Hyphens
       * @see https://tailwindcss.com/docs/hyphens
       */
      hyphens: [{
        hyphens: ["none", "manual", "auto"]
      }],
      /**
       * Content
       * @see https://tailwindcss.com/docs/content
       */
      content: [{
        content: ["none", D]
      }],
      // Backgrounds
      /**
       * Background Attachment
       * @see https://tailwindcss.com/docs/background-attachment
       */
      "bg-attachment": [{
        bg: ["fixed", "local", "scroll"]
      }],
      /**
       * Background Clip
       * @see https://tailwindcss.com/docs/background-clip
       */
      "bg-clip": [{
        "bg-clip": ["border", "padding", "content", "text"]
      }],
      /**
       * Background Opacity
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/background-opacity
       */
      "bg-opacity": [{
        "bg-opacity": [y]
      }],
      /**
       * Background Origin
       * @see https://tailwindcss.com/docs/background-origin
       */
      "bg-origin": [{
        "bg-origin": ["border", "padding", "content"]
      }],
      /**
       * Background Position
       * @see https://tailwindcss.com/docs/background-position
       */
      "bg-position": [{
        bg: [...M(), xa]
      }],
      /**
       * Background Repeat
       * @see https://tailwindcss.com/docs/background-repeat
       */
      "bg-repeat": [{
        bg: ["no-repeat", {
          repeat: ["", "x", "y", "round", "space"]
        }]
      }],
      /**
       * Background Size
       * @see https://tailwindcss.com/docs/background-size
       */
      "bg-size": [{
        bg: ["auto", "cover", "contain", ya]
      }],
      /**
       * Background Image
       * @see https://tailwindcss.com/docs/background-image
       */
      "bg-image": [{
        bg: ["none", {
          "gradient-to": ["t", "tr", "r", "br", "b", "bl", "l", "tl"]
        }, Ca]
      }],
      /**
       * Background Color
       * @see https://tailwindcss.com/docs/background-color
       */
      "bg-color": [{
        bg: [e]
      }],
      /**
       * Gradient Color Stops From Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from-pos": [{
        from: [b]
      }],
      /**
       * Gradient Color Stops Via Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via-pos": [{
        via: [b]
      }],
      /**
       * Gradient Color Stops To Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to-pos": [{
        to: [b]
      }],
      /**
       * Gradient Color Stops From
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from": [{
        from: [h]
      }],
      /**
       * Gradient Color Stops Via
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via": [{
        via: [h]
      }],
      /**
       * Gradient Color Stops To
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to": [{
        to: [h]
      }],
      // Borders
      /**
       * Border Radius
       * @see https://tailwindcss.com/docs/border-radius
       */
      rounded: [{
        rounded: [i]
      }],
      /**
       * Border Radius Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-s": [{
        "rounded-s": [i]
      }],
      /**
       * Border Radius End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-e": [{
        "rounded-e": [i]
      }],
      /**
       * Border Radius Top
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-t": [{
        "rounded-t": [i]
      }],
      /**
       * Border Radius Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-r": [{
        "rounded-r": [i]
      }],
      /**
       * Border Radius Bottom
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-b": [{
        "rounded-b": [i]
      }],
      /**
       * Border Radius Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-l": [{
        "rounded-l": [i]
      }],
      /**
       * Border Radius Start Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ss": [{
        "rounded-ss": [i]
      }],
      /**
       * Border Radius Start End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-se": [{
        "rounded-se": [i]
      }],
      /**
       * Border Radius End End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ee": [{
        "rounded-ee": [i]
      }],
      /**
       * Border Radius End Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-es": [{
        "rounded-es": [i]
      }],
      /**
       * Border Radius Top Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tl": [{
        "rounded-tl": [i]
      }],
      /**
       * Border Radius Top Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tr": [{
        "rounded-tr": [i]
      }],
      /**
       * Border Radius Bottom Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-br": [{
        "rounded-br": [i]
      }],
      /**
       * Border Radius Bottom Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-bl": [{
        "rounded-bl": [i]
      }],
      /**
       * Border Width
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w": [{
        border: [s]
      }],
      /**
       * Border Width X
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-x": [{
        "border-x": [s]
      }],
      /**
       * Border Width Y
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-y": [{
        "border-y": [s]
      }],
      /**
       * Border Width Start
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-s": [{
        "border-s": [s]
      }],
      /**
       * Border Width End
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-e": [{
        "border-e": [s]
      }],
      /**
       * Border Width Top
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-t": [{
        "border-t": [s]
      }],
      /**
       * Border Width Right
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-r": [{
        "border-r": [s]
      }],
      /**
       * Border Width Bottom
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-b": [{
        "border-b": [s]
      }],
      /**
       * Border Width Left
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-l": [{
        "border-l": [s]
      }],
      /**
       * Border Opacity
       * @see https://tailwindcss.com/docs/border-opacity
       */
      "border-opacity": [{
        "border-opacity": [y]
      }],
      /**
       * Border Style
       * @see https://tailwindcss.com/docs/border-style
       */
      "border-style": [{
        border: [...O(), "hidden"]
      }],
      /**
       * Divide Width X
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-x": [{
        "divide-x": [s]
      }],
      /**
       * Divide Width X Reverse
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-x-reverse": ["divide-x-reverse"],
      /**
       * Divide Width Y
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-y": [{
        "divide-y": [s]
      }],
      /**
       * Divide Width Y Reverse
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-y-reverse": ["divide-y-reverse"],
      /**
       * Divide Opacity
       * @see https://tailwindcss.com/docs/divide-opacity
       */
      "divide-opacity": [{
        "divide-opacity": [y]
      }],
      /**
       * Divide Style
       * @see https://tailwindcss.com/docs/divide-style
       */
      "divide-style": [{
        divide: O()
      }],
      /**
       * Border Color
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color": [{
        border: [o]
      }],
      /**
       * Border Color X
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-x": [{
        "border-x": [o]
      }],
      /**
       * Border Color Y
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-y": [{
        "border-y": [o]
      }],
      /**
       * Border Color S
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-s": [{
        "border-s": [o]
      }],
      /**
       * Border Color E
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-e": [{
        "border-e": [o]
      }],
      /**
       * Border Color Top
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-t": [{
        "border-t": [o]
      }],
      /**
       * Border Color Right
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-r": [{
        "border-r": [o]
      }],
      /**
       * Border Color Bottom
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-b": [{
        "border-b": [o]
      }],
      /**
       * Border Color Left
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-l": [{
        "border-l": [o]
      }],
      /**
       * Divide Color
       * @see https://tailwindcss.com/docs/divide-color
       */
      "divide-color": [{
        divide: [o]
      }],
      /**
       * Outline Style
       * @see https://tailwindcss.com/docs/outline-style
       */
      "outline-style": [{
        outline: ["", ...O()]
      }],
      /**
       * Outline Offset
       * @see https://tailwindcss.com/docs/outline-offset
       */
      "outline-offset": [{
        "outline-offset": [de, D]
      }],
      /**
       * Outline Width
       * @see https://tailwindcss.com/docs/outline-width
       */
      "outline-w": [{
        outline: [de, ge]
      }],
      /**
       * Outline Color
       * @see https://tailwindcss.com/docs/outline-color
       */
      "outline-color": [{
        outline: [e]
      }],
      /**
       * Ring Width
       * @see https://tailwindcss.com/docs/ring-width
       */
      "ring-w": [{
        ring: V()
      }],
      /**
       * Ring Width Inset
       * @see https://tailwindcss.com/docs/ring-width
       */
      "ring-w-inset": ["ring-inset"],
      /**
       * Ring Color
       * @see https://tailwindcss.com/docs/ring-color
       */
      "ring-color": [{
        ring: [e]
      }],
      /**
       * Ring Opacity
       * @see https://tailwindcss.com/docs/ring-opacity
       */
      "ring-opacity": [{
        "ring-opacity": [y]
      }],
      /**
       * Ring Offset Width
       * @see https://tailwindcss.com/docs/ring-offset-width
       */
      "ring-offset-w": [{
        "ring-offset": [de, ge]
      }],
      /**
       * Ring Offset Color
       * @see https://tailwindcss.com/docs/ring-offset-color
       */
      "ring-offset-color": [{
        "ring-offset": [e]
      }],
      // Effects
      /**
       * Box Shadow
       * @see https://tailwindcss.com/docs/box-shadow
       */
      shadow: [{
        shadow: ["", "inner", "none", he, Ea]
      }],
      /**
       * Box Shadow Color
       * @see https://tailwindcss.com/docs/box-shadow-color
       */
      "shadow-color": [{
        shadow: [He]
      }],
      /**
       * Opacity
       * @see https://tailwindcss.com/docs/opacity
       */
      opacity: [{
        opacity: [y]
      }],
      /**
       * Mix Blend Mode
       * @see https://tailwindcss.com/docs/mix-blend-mode
       */
      "mix-blend": [{
        "mix-blend": [...W(), "plus-lighter", "plus-darker"]
      }],
      /**
       * Background Blend Mode
       * @see https://tailwindcss.com/docs/background-blend-mode
       */
      "bg-blend": [{
        "bg-blend": W()
      }],
      // Filters
      /**
       * Filter
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/filter
       */
      filter: [{
        filter: ["", "none"]
      }],
      /**
       * Blur
       * @see https://tailwindcss.com/docs/blur
       */
      blur: [{
        blur: [n]
      }],
      /**
       * Brightness
       * @see https://tailwindcss.com/docs/brightness
       */
      brightness: [{
        brightness: [r]
      }],
      /**
       * Contrast
       * @see https://tailwindcss.com/docs/contrast
       */
      contrast: [{
        contrast: [l]
      }],
      /**
       * Drop Shadow
       * @see https://tailwindcss.com/docs/drop-shadow
       */
      "drop-shadow": [{
        "drop-shadow": ["", "none", he, D]
      }],
      /**
       * Grayscale
       * @see https://tailwindcss.com/docs/grayscale
       */
      grayscale: [{
        grayscale: [u]
      }],
      /**
       * Hue Rotate
       * @see https://tailwindcss.com/docs/hue-rotate
       */
      "hue-rotate": [{
        "hue-rotate": [p]
      }],
      /**
       * Invert
       * @see https://tailwindcss.com/docs/invert
       */
      invert: [{
        invert: [d]
      }],
      /**
       * Saturate
       * @see https://tailwindcss.com/docs/saturate
       */
      saturate: [{
        saturate: [C]
      }],
      /**
       * Sepia
       * @see https://tailwindcss.com/docs/sepia
       */
      sepia: [{
        sepia: [E]
      }],
      /**
       * Backdrop Filter
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/backdrop-filter
       */
      "backdrop-filter": [{
        "backdrop-filter": ["", "none"]
      }],
      /**
       * Backdrop Blur
       * @see https://tailwindcss.com/docs/backdrop-blur
       */
      "backdrop-blur": [{
        "backdrop-blur": [n]
      }],
      /**
       * Backdrop Brightness
       * @see https://tailwindcss.com/docs/backdrop-brightness
       */
      "backdrop-brightness": [{
        "backdrop-brightness": [r]
      }],
      /**
       * Backdrop Contrast
       * @see https://tailwindcss.com/docs/backdrop-contrast
       */
      "backdrop-contrast": [{
        "backdrop-contrast": [l]
      }],
      /**
       * Backdrop Grayscale
       * @see https://tailwindcss.com/docs/backdrop-grayscale
       */
      "backdrop-grayscale": [{
        "backdrop-grayscale": [u]
      }],
      /**
       * Backdrop Hue Rotate
       * @see https://tailwindcss.com/docs/backdrop-hue-rotate
       */
      "backdrop-hue-rotate": [{
        "backdrop-hue-rotate": [p]
      }],
      /**
       * Backdrop Invert
       * @see https://tailwindcss.com/docs/backdrop-invert
       */
      "backdrop-invert": [{
        "backdrop-invert": [d]
      }],
      /**
       * Backdrop Opacity
       * @see https://tailwindcss.com/docs/backdrop-opacity
       */
      "backdrop-opacity": [{
        "backdrop-opacity": [y]
      }],
      /**
       * Backdrop Saturate
       * @see https://tailwindcss.com/docs/backdrop-saturate
       */
      "backdrop-saturate": [{
        "backdrop-saturate": [C]
      }],
      /**
       * Backdrop Sepia
       * @see https://tailwindcss.com/docs/backdrop-sepia
       */
      "backdrop-sepia": [{
        "backdrop-sepia": [E]
      }],
      // Tables
      /**
       * Border Collapse
       * @see https://tailwindcss.com/docs/border-collapse
       */
      "border-collapse": [{
        border: ["collapse", "separate"]
      }],
      /**
       * Border Spacing
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing": [{
        "border-spacing": [a]
      }],
      /**
       * Border Spacing X
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-x": [{
        "border-spacing-x": [a]
      }],
      /**
       * Border Spacing Y
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-y": [{
        "border-spacing-y": [a]
      }],
      /**
       * Table Layout
       * @see https://tailwindcss.com/docs/table-layout
       */
      "table-layout": [{
        table: ["auto", "fixed"]
      }],
      /**
       * Caption Side
       * @see https://tailwindcss.com/docs/caption-side
       */
      caption: [{
        caption: ["top", "bottom"]
      }],
      // Transitions and Animation
      /**
       * Tranisition Property
       * @see https://tailwindcss.com/docs/transition-property
       */
      transition: [{
        transition: ["none", "all", "", "colors", "opacity", "shadow", "transform", D]
      }],
      /**
       * Transition Duration
       * @see https://tailwindcss.com/docs/transition-duration
       */
      duration: [{
        duration: K()
      }],
      /**
       * Transition Timing Function
       * @see https://tailwindcss.com/docs/transition-timing-function
       */
      ease: [{
        ease: ["linear", "in", "out", "in-out", D]
      }],
      /**
       * Transition Delay
       * @see https://tailwindcss.com/docs/transition-delay
       */
      delay: [{
        delay: K()
      }],
      /**
       * Animation
       * @see https://tailwindcss.com/docs/animation
       */
      animate: [{
        animate: ["none", "spin", "ping", "pulse", "bounce", D]
      }],
      // Transforms
      /**
       * Transform
       * @see https://tailwindcss.com/docs/transform
       */
      transform: [{
        transform: ["", "gpu", "none"]
      }],
      /**
       * Scale
       * @see https://tailwindcss.com/docs/scale
       */
      scale: [{
        scale: [x]
      }],
      /**
       * Scale X
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-x": [{
        "scale-x": [x]
      }],
      /**
       * Scale Y
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-y": [{
        "scale-y": [x]
      }],
      /**
       * Rotate
       * @see https://tailwindcss.com/docs/rotate
       */
      rotate: [{
        rotate: [je, D]
      }],
      /**
       * Translate X
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-x": [{
        "translate-x": [A]
      }],
      /**
       * Translate Y
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-y": [{
        "translate-y": [A]
      }],
      /**
       * Skew X
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-x": [{
        "skew-x": [N]
      }],
      /**
       * Skew Y
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-y": [{
        "skew-y": [N]
      }],
      /**
       * Transform Origin
       * @see https://tailwindcss.com/docs/transform-origin
       */
      "transform-origin": [{
        origin: ["center", "top", "top-right", "right", "bottom-right", "bottom", "bottom-left", "left", "top-left", D]
      }],
      // Interactivity
      /**
       * Accent Color
       * @see https://tailwindcss.com/docs/accent-color
       */
      accent: [{
        accent: ["auto", e]
      }],
      /**
       * Appearance
       * @see https://tailwindcss.com/docs/appearance
       */
      appearance: [{
        appearance: ["none", "auto"]
      }],
      /**
       * Cursor
       * @see https://tailwindcss.com/docs/cursor
       */
      cursor: [{
        cursor: ["auto", "default", "pointer", "wait", "text", "move", "help", "not-allowed", "none", "context-menu", "progress", "cell", "crosshair", "vertical-text", "alias", "copy", "no-drop", "grab", "grabbing", "all-scroll", "col-resize", "row-resize", "n-resize", "e-resize", "s-resize", "w-resize", "ne-resize", "nw-resize", "se-resize", "sw-resize", "ew-resize", "ns-resize", "nesw-resize", "nwse-resize", "zoom-in", "zoom-out", D]
      }],
      /**
       * Caret Color
       * @see https://tailwindcss.com/docs/just-in-time-mode#caret-color-utilities
       */
      "caret-color": [{
        caret: [e]
      }],
      /**
       * Pointer Events
       * @see https://tailwindcss.com/docs/pointer-events
       */
      "pointer-events": [{
        "pointer-events": ["none", "auto"]
      }],
      /**
       * Resize
       * @see https://tailwindcss.com/docs/resize
       */
      resize: [{
        resize: ["none", "y", "x", ""]
      }],
      /**
       * Scroll Behavior
       * @see https://tailwindcss.com/docs/scroll-behavior
       */
      "scroll-behavior": [{
        scroll: ["auto", "smooth"]
      }],
      /**
       * Scroll Margin
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-m": [{
        "scroll-m": k()
      }],
      /**
       * Scroll Margin X
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mx": [{
        "scroll-mx": k()
      }],
      /**
       * Scroll Margin Y
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-my": [{
        "scroll-my": k()
      }],
      /**
       * Scroll Margin Start
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ms": [{
        "scroll-ms": k()
      }],
      /**
       * Scroll Margin End
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-me": [{
        "scroll-me": k()
      }],
      /**
       * Scroll Margin Top
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mt": [{
        "scroll-mt": k()
      }],
      /**
       * Scroll Margin Right
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mr": [{
        "scroll-mr": k()
      }],
      /**
       * Scroll Margin Bottom
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mb": [{
        "scroll-mb": k()
      }],
      /**
       * Scroll Margin Left
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ml": [{
        "scroll-ml": k()
      }],
      /**
       * Scroll Padding
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-p": [{
        "scroll-p": k()
      }],
      /**
       * Scroll Padding X
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-px": [{
        "scroll-px": k()
      }],
      /**
       * Scroll Padding Y
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-py": [{
        "scroll-py": k()
      }],
      /**
       * Scroll Padding Start
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-ps": [{
        "scroll-ps": k()
      }],
      /**
       * Scroll Padding End
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pe": [{
        "scroll-pe": k()
      }],
      /**
       * Scroll Padding Top
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pt": [{
        "scroll-pt": k()
      }],
      /**
       * Scroll Padding Right
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pr": [{
        "scroll-pr": k()
      }],
      /**
       * Scroll Padding Bottom
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pb": [{
        "scroll-pb": k()
      }],
      /**
       * Scroll Padding Left
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pl": [{
        "scroll-pl": k()
      }],
      /**
       * Scroll Snap Align
       * @see https://tailwindcss.com/docs/scroll-snap-align
       */
      "snap-align": [{
        snap: ["start", "end", "center", "align-none"]
      }],
      /**
       * Scroll Snap Stop
       * @see https://tailwindcss.com/docs/scroll-snap-stop
       */
      "snap-stop": [{
        snap: ["normal", "always"]
      }],
      /**
       * Scroll Snap Type
       * @see https://tailwindcss.com/docs/scroll-snap-type
       */
      "snap-type": [{
        snap: ["none", "x", "y", "both"]
      }],
      /**
       * Scroll Snap Type Strictness
       * @see https://tailwindcss.com/docs/scroll-snap-type
       */
      "snap-strictness": [{
        snap: ["mandatory", "proximity"]
      }],
      /**
       * Touch Action
       * @see https://tailwindcss.com/docs/touch-action
       */
      touch: [{
        touch: ["auto", "none", "manipulation"]
      }],
      /**
       * Touch Action X
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-x": [{
        "touch-pan": ["x", "left", "right"]
      }],
      /**
       * Touch Action Y
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-y": [{
        "touch-pan": ["y", "up", "down"]
      }],
      /**
       * Touch Action Pinch Zoom
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-pz": ["touch-pinch-zoom"],
      /**
       * User Select
       * @see https://tailwindcss.com/docs/user-select
       */
      select: [{
        select: ["none", "text", "all", "auto"]
      }],
      /**
       * Will Change
       * @see https://tailwindcss.com/docs/will-change
       */
      "will-change": [{
        "will-change": ["auto", "scroll", "contents", "transform", D]
      }],
      // SVG
      /**
       * Fill
       * @see https://tailwindcss.com/docs/fill
       */
      fill: [{
        fill: [e, "none"]
      }],
      /**
       * Stroke Width
       * @see https://tailwindcss.com/docs/stroke-width
       */
      "stroke-w": [{
        stroke: [de, ge, Ft]
      }],
      /**
       * Stroke
       * @see https://tailwindcss.com/docs/stroke
       */
      stroke: [{
        stroke: [e, "none"]
      }],
      // Accessibility
      /**
       * Screen Readers
       * @see https://tailwindcss.com/docs/screen-readers
       */
      sr: ["sr-only", "not-sr-only"],
      /**
       * Forced Color Adjust
       * @see https://tailwindcss.com/docs/forced-color-adjust
       */
      "forced-color-adjust": [{
        "forced-color-adjust": ["auto", "none"]
      }]
    },
    conflictingClassGroups: {
      overflow: ["overflow-x", "overflow-y"],
      overscroll: ["overscroll-x", "overscroll-y"],
      inset: ["inset-x", "inset-y", "start", "end", "top", "right", "bottom", "left"],
      "inset-x": ["right", "left"],
      "inset-y": ["top", "bottom"],
      flex: ["basis", "grow", "shrink"],
      gap: ["gap-x", "gap-y"],
      p: ["px", "py", "ps", "pe", "pt", "pr", "pb", "pl"],
      px: ["pr", "pl"],
      py: ["pt", "pb"],
      m: ["mx", "my", "ms", "me", "mt", "mr", "mb", "ml"],
      mx: ["mr", "ml"],
      my: ["mt", "mb"],
      size: ["w", "h"],
      "font-size": ["leading"],
      "fvn-normal": ["fvn-ordinal", "fvn-slashed-zero", "fvn-figure", "fvn-spacing", "fvn-fraction"],
      "fvn-ordinal": ["fvn-normal"],
      "fvn-slashed-zero": ["fvn-normal"],
      "fvn-figure": ["fvn-normal"],
      "fvn-spacing": ["fvn-normal"],
      "fvn-fraction": ["fvn-normal"],
      "line-clamp": ["display", "overflow"],
      rounded: ["rounded-s", "rounded-e", "rounded-t", "rounded-r", "rounded-b", "rounded-l", "rounded-ss", "rounded-se", "rounded-ee", "rounded-es", "rounded-tl", "rounded-tr", "rounded-br", "rounded-bl"],
      "rounded-s": ["rounded-ss", "rounded-es"],
      "rounded-e": ["rounded-se", "rounded-ee"],
      "rounded-t": ["rounded-tl", "rounded-tr"],
      "rounded-r": ["rounded-tr", "rounded-br"],
      "rounded-b": ["rounded-br", "rounded-bl"],
      "rounded-l": ["rounded-tl", "rounded-bl"],
      "border-spacing": ["border-spacing-x", "border-spacing-y"],
      "border-w": ["border-w-s", "border-w-e", "border-w-t", "border-w-r", "border-w-b", "border-w-l"],
      "border-w-x": ["border-w-r", "border-w-l"],
      "border-w-y": ["border-w-t", "border-w-b"],
      "border-color": ["border-color-s", "border-color-e", "border-color-t", "border-color-r", "border-color-b", "border-color-l"],
      "border-color-x": ["border-color-r", "border-color-l"],
      "border-color-y": ["border-color-t", "border-color-b"],
      "scroll-m": ["scroll-mx", "scroll-my", "scroll-ms", "scroll-me", "scroll-mt", "scroll-mr", "scroll-mb", "scroll-ml"],
      "scroll-mx": ["scroll-mr", "scroll-ml"],
      "scroll-my": ["scroll-mt", "scroll-mb"],
      "scroll-p": ["scroll-px", "scroll-py", "scroll-ps", "scroll-pe", "scroll-pt", "scroll-pr", "scroll-pb", "scroll-pl"],
      "scroll-px": ["scroll-pr", "scroll-pl"],
      "scroll-py": ["scroll-pt", "scroll-pb"],
      touch: ["touch-x", "touch-y", "touch-pz"],
      "touch-x": ["touch"],
      "touch-y": ["touch"],
      "touch-pz": ["touch"]
    },
    conflictingClassGroupModifiers: {
      "font-size": ["leading"]
    }
  };
}, Pa = /* @__PURE__ */ la(Ta);
function L(...e) {
  return Pa(Wr(e));
}
const er = (e) => typeof e == "boolean" ? `${e}` : e === 0 ? "0" : e, tr = Wr, qe = (e, t) => (n) => {
  var r;
  if ((t == null ? void 0 : t.variants) == null) return tr(e, n == null ? void 0 : n.class, n == null ? void 0 : n.className);
  const { variants: o, defaultVariants: i } = t, a = Object.keys(o).map((u) => {
    const p = n == null ? void 0 : n[u], d = i == null ? void 0 : i[u];
    if (p === null) return null;
    const m = er(p) || er(d);
    return o[u][m];
  }), s = n && Object.entries(n).reduce((u, p) => {
    let [d, m] = p;
    return m === void 0 || (u[d] = m), u;
  }, {}), l = t == null || (r = t.compoundVariants) === null || r === void 0 ? void 0 : r.reduce((u, p) => {
    let { class: d, className: m, ...h } = p;
    return Object.entries(h).every((b) => {
      let [g, v] = b;
      return Array.isArray(v) ? v.includes({
        ...i,
        ...s
      }[g]) : {
        ...i,
        ...s
      }[g] === v;
    }) ? [
      ...u,
      d,
      m
    ] : u;
  }, []);
  return tr(e, a, l, n == null ? void 0 : n.class, n == null ? void 0 : n.className);
}, Aa = qe(
  // Whitespace-nowrap: Badges should never wrap.
  "whitespace-nowrap inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 hover-elevate ",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground shadow-xs",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground shadow-xs",
        outline: " border [border-color:var(--badge-outline)] shadow-xs"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
);
function ka({ className: e, variant: t, ...n }) {
  return /* @__PURE__ */ f("div", { className: L(Aa({ variant: t }), e), ...n });
}
function nr(e, t) {
  if (typeof e == "function")
    return e(t);
  e != null && (e.current = t);
}
function Y(...e) {
  return (t) => {
    let n = !1;
    const r = e.map((o) => {
      const i = nr(o, t);
      return !n && typeof i == "function" && (n = !0), i;
    });
    if (n)
      return () => {
        for (let o = 0; o < r.length; o++) {
          const i = r[o];
          typeof i == "function" ? i() : nr(e[o], null);
        }
      };
  };
}
function U(...e) {
  return c.useCallback(Y(...e), e);
}
var _a = Symbol.for("react.lazy"), gt = c[" use ".trim().toString()];
function Oa(e) {
  return typeof e == "object" && e !== null && "then" in e;
}
function Gr(e) {
  return e != null && typeof e == "object" && "$$typeof" in e && e.$$typeof === _a && "_payload" in e && Oa(e._payload);
}
// @__NO_SIDE_EFFECTS__
function Kr(e) {
  const t = /* @__PURE__ */ Ia(e), n = c.forwardRef((r, o) => {
    let { children: i, ...a } = r;
    Gr(i) && typeof gt == "function" && (i = gt(i._payload));
    const s = c.Children.toArray(i), l = s.find(Ma);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
var $a = /* @__PURE__ */ Kr("Slot");
// @__NO_SIDE_EFFECTS__
function Ia(e) {
  const t = c.forwardRef((n, r) => {
    let { children: o, ...i } = n;
    if (Gr(o) && typeof gt == "function" && (o = gt(o._payload)), c.isValidElement(o)) {
      const a = Fa(o), s = La(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Da = Symbol("radix.slottable");
function Ma(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Da;
}
function La(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Fa(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
const Va = qe(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover-elevate active-elevate-2",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground border border-primary-border",
        destructive: "bg-destructive text-destructive-foreground border border-destructive-border",
        outline: (
          // Shows the background color of whatever card / sidebar / accent background it is inside of.
          // Inherits the current text color.
          " border [border-color:var(--button-outline)]  shadow-xs active:shadow-none "
        ),
        secondary: "border bg-secondary text-secondary-foreground border border-secondary-border ",
        // Add a transparent border so that when someone toggles a border on later, it doesn't shift layout/size.
        ghost: "border border-transparent"
      },
      // Heights are set as "min" heights, because sometimes Ai will place large amount of content
      // inside buttons. With a min-height they will look appropriate with small amounts of content,
      // but will expand to fit large amounts of content.
      size: {
        default: "min-h-9 px-4 py-2",
        sm: "min-h-8 rounded-md px-3 text-xs",
        lg: "min-h-10 rounded-md px-8",
        icon: "h-9 w-9"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
), J = c.forwardRef(
  ({ className: e, variant: t, size: n, asChild: r = !1, ...o }, i) => /* @__PURE__ */ f(
    r ? $a : "button",
    {
      className: L(Va({ variant: t, size: n, className: e })),
      ref: i,
      ...o
    }
  )
);
J.displayName = "Button";
const vn = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "div",
  {
    ref: n,
    className: L(
      "shadcn-card rounded-md bg-card text-card-foreground border border-card-border shadow-sm",
      e
    ),
    ...t
  }
));
vn.displayName = "Card";
const bn = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "div",
  {
    ref: n,
    className: L("flex flex-col space-y-1.5 p-6", e),
    ...t
  }
));
bn.displayName = "CardHeader";
const yn = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "div",
  {
    ref: n,
    className: L(
      "text-2xl font-semibold leading-none tracking-tight",
      e
    ),
    ...t
  }
));
yn.displayName = "CardTitle";
const xn = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "div",
  {
    ref: n,
    className: L("text-sm text-muted-foreground", e),
    ...t
  }
));
xn.displayName = "CardDescription";
const wn = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f("div", { ref: n, className: L("p-6 pt-0", e), ...t }));
wn.displayName = "CardContent";
const Wa = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "div",
  {
    ref: n,
    className: L("flex items-center p-6 pt-0", e),
    ...t
  }
));
Wa.displayName = "CardFooter";
const qr = c.forwardRef(
  ({ className: e, type: t, ...n }, r) => /* @__PURE__ */ f(
    "input",
    {
      type: t,
      className: L(
        "flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        e
      ),
      ref: r,
      ...n
    }
  )
);
qr.displayName = "Input";
var Ba = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Ye = Ba.reduce((e, t) => {
  const n = /* @__PURE__ */ Kr(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), ja = "Label", Yr = c.forwardRef((e, t) => /* @__PURE__ */ f(
  Ye.label,
  {
    ...e,
    ref: t,
    onMouseDown: (n) => {
      var o;
      n.target.closest("button, input, select, textarea") || ((o = e.onMouseDown) == null || o.call(e, n), !n.defaultPrevented && n.detail > 1 && n.preventDefault());
    }
  }
));
Yr.displayName = ja;
var Xr = Yr;
const Ha = qe(
  "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
), lt = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Xr,
  {
    ref: n,
    className: L(Ha(), e),
    ...t
  }
));
lt.displayName = Xr.displayName;
var za = "Separator", rr = "horizontal", Ua = ["horizontal", "vertical"], Zr = c.forwardRef((e, t) => {
  const { decorative: n, orientation: r = rr, ...o } = e, i = Ga(r) ? r : rr, s = n ? { role: "none" } : { "aria-orientation": i === "vertical" ? i : void 0, role: "separator" };
  return /* @__PURE__ */ f(
    Ye.div,
    {
      "data-orientation": i,
      ...s,
      ...o,
      ref: t
    }
  );
});
Zr.displayName = za;
function Ga(e) {
  return Ua.includes(e);
}
var Qr = Zr;
const tn = c.forwardRef(
  ({ className: e, orientation: t = "horizontal", decorative: n = !0, ...r }, o) => /* @__PURE__ */ f(
    Qr,
    {
      ref: o,
      decorative: n,
      orientation: t,
      className: L(
        "shrink-0 bg-border",
        t === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
        e
      ),
      ...r
    }
  )
);
tn.displayName = Qr.displayName;
function Ka(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, qa(o, ...t)];
}
function qa(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
function F(e, t, { checkForDefaultPrevented: n = !0 } = {}) {
  return function(o) {
    if (e == null || e(o), n === !1 || !o.defaultPrevented)
      return t == null ? void 0 : t(o);
  };
}
var te = globalThis != null && globalThis.document ? c.useLayoutEffect : () => {
}, Ya = c[" useInsertionEffect ".trim().toString()] || te;
function Me({
  prop: e,
  defaultProp: t,
  onChange: n = () => {
  },
  caller: r
}) {
  const [o, i, a] = Xa({
    defaultProp: t,
    onChange: n
  }), s = e !== void 0, l = s ? e : o;
  {
    const p = c.useRef(e !== void 0);
    c.useEffect(() => {
      const d = p.current;
      d !== s && console.warn(
        `${r} is changing from ${d ? "controlled" : "uncontrolled"} to ${s ? "controlled" : "uncontrolled"}. Components should not switch from controlled to uncontrolled (or vice versa). Decide between using a controlled or uncontrolled value for the lifetime of the component.`
      ), p.current = s;
    }, [s, r]);
  }
  const u = c.useCallback(
    (p) => {
      var d;
      if (s) {
        const m = Za(p) ? p(e) : p;
        m !== e && ((d = a.current) == null || d.call(a, m));
      } else
        i(p);
    },
    [s, e, i, a]
  );
  return [l, u];
}
function Xa({
  defaultProp: e,
  onChange: t
}) {
  const [n, r] = c.useState(e), o = c.useRef(n), i = c.useRef(t);
  return Ya(() => {
    i.current = t;
  }, [t]), c.useEffect(() => {
    var a;
    o.current !== n && ((a = i.current) == null || a.call(i, n), o.current = n);
  }, [n, o]), [n, r, i];
}
function Za(e) {
  return typeof e == "function";
}
function Qa(e) {
  const t = c.useRef({ value: e, previous: e });
  return c.useMemo(() => (t.current.value !== e && (t.current.previous = t.current.value, t.current.value = e), t.current.previous), [e]);
}
function Jr(e) {
  const [t, n] = c.useState(void 0);
  return te(() => {
    if (e) {
      n({ width: e.offsetWidth, height: e.offsetHeight });
      const r = new ResizeObserver((o) => {
        if (!Array.isArray(o) || !o.length)
          return;
        const i = o[0];
        let a, s;
        if ("borderBoxSize" in i) {
          const l = i.borderBoxSize, u = Array.isArray(l) ? l[0] : l;
          a = u.inlineSize, s = u.blockSize;
        } else
          a = e.offsetWidth, s = e.offsetHeight;
        n({ width: a, height: s });
      });
      return r.observe(e, { box: "border-box" }), () => r.unobserve(e);
    } else
      n(void 0);
  }, [e]), t;
}
function Ja(e, t) {
  return c.useReducer((n, r) => t[n][r] ?? n, e);
}
var we = (e) => {
  const { present: t, children: n } = e, r = ec(t), o = typeof n == "function" ? n({ present: r.isPresent }) : c.Children.only(n), i = U(r.ref, tc(o));
  return typeof n == "function" || r.isPresent ? c.cloneElement(o, { ref: i }) : null;
};
we.displayName = "Presence";
function ec(e) {
  const [t, n] = c.useState(), r = c.useRef(null), o = c.useRef(e), i = c.useRef("none"), a = e ? "mounted" : "unmounted", [s, l] = Ja(a, {
    mounted: {
      UNMOUNT: "unmounted",
      ANIMATION_OUT: "unmountSuspended"
    },
    unmountSuspended: {
      MOUNT: "mounted",
      ANIMATION_END: "unmounted"
    },
    unmounted: {
      MOUNT: "mounted"
    }
  });
  return c.useEffect(() => {
    const u = nt(r.current);
    i.current = s === "mounted" ? u : "none";
  }, [s]), te(() => {
    const u = r.current, p = o.current;
    if (p !== e) {
      const m = i.current, h = nt(u);
      e ? l("MOUNT") : h === "none" || (u == null ? void 0 : u.display) === "none" ? l("UNMOUNT") : l(p && m !== h ? "ANIMATION_OUT" : "UNMOUNT"), o.current = e;
    }
  }, [e, l]), te(() => {
    if (t) {
      let u;
      const p = t.ownerDocument.defaultView ?? window, d = (h) => {
        const g = nt(r.current).includes(CSS.escape(h.animationName));
        if (h.target === t && g && (l("ANIMATION_END"), !o.current)) {
          const v = t.style.animationFillMode;
          t.style.animationFillMode = "forwards", u = p.setTimeout(() => {
            t.style.animationFillMode === "forwards" && (t.style.animationFillMode = v);
          });
        }
      }, m = (h) => {
        h.target === t && (i.current = nt(r.current));
      };
      return t.addEventListener("animationstart", m), t.addEventListener("animationcancel", d), t.addEventListener("animationend", d), () => {
        p.clearTimeout(u), t.removeEventListener("animationstart", m), t.removeEventListener("animationcancel", d), t.removeEventListener("animationend", d);
      };
    } else
      l("ANIMATION_END");
  }, [t, l]), {
    isPresent: ["mounted", "unmountSuspended"].includes(s),
    ref: c.useCallback((u) => {
      r.current = u ? getComputedStyle(u) : null, n(u);
    }, [])
  };
}
function nt(e) {
  return (e == null ? void 0 : e.animationName) || "none";
}
function tc(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
// @__NO_SIDE_EFFECTS__
function nc(e) {
  const t = /* @__PURE__ */ rc(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(ic);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function rc(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = ac(o), s = sc(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var oc = Symbol("radix.slottable");
function ic(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === oc;
}
function sc(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function ac(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var cc = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Cn = cc.reduce((e, t) => {
  const n = /* @__PURE__ */ nc(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), Ct = "Checkbox", [lc] = Ka(Ct), [uc, En] = lc(Ct);
function dc(e) {
  const {
    __scopeCheckbox: t,
    checked: n,
    children: r,
    defaultChecked: o,
    disabled: i,
    form: a,
    name: s,
    onCheckedChange: l,
    required: u,
    value: p = "on",
    // @ts-expect-error
    internal_do_not_use_render: d
  } = e, [m, h] = Me({
    prop: n,
    defaultProp: o ?? !1,
    onChange: l,
    caller: Ct
  }), [b, g] = c.useState(null), [v, y] = c.useState(null), w = c.useRef(!1), C = b ? !!a || !!b.closest("form") : (
    // We set this to true by default so that events bubble to forms without JS (SSR)
    !0
  ), x = {
    checked: m,
    disabled: i,
    setChecked: h,
    control: b,
    setControl: g,
    name: s,
    form: a,
    value: p,
    hasConsumerStoppedPropagationRef: w,
    required: u,
    defaultChecked: be(o) ? !1 : o,
    isFormControl: C,
    bubbleInput: v,
    setBubbleInput: y
  };
  return /* @__PURE__ */ f(
    uc,
    {
      scope: t,
      ...x,
      children: fc(d) ? d(x) : r
    }
  );
}
var eo = "CheckboxTrigger", to = c.forwardRef(
  ({ __scopeCheckbox: e, onKeyDown: t, onClick: n, ...r }, o) => {
    const {
      control: i,
      value: a,
      disabled: s,
      checked: l,
      required: u,
      setControl: p,
      setChecked: d,
      hasConsumerStoppedPropagationRef: m,
      isFormControl: h,
      bubbleInput: b
    } = En(eo, e), g = U(o, p), v = c.useRef(l);
    return c.useEffect(() => {
      const y = i == null ? void 0 : i.form;
      if (y) {
        const w = () => d(v.current);
        return y.addEventListener("reset", w), () => y.removeEventListener("reset", w);
      }
    }, [i, d]), /* @__PURE__ */ f(
      Cn.button,
      {
        type: "button",
        role: "checkbox",
        "aria-checked": be(l) ? "mixed" : l,
        "aria-required": u,
        "data-state": so(l),
        "data-disabled": s ? "" : void 0,
        disabled: s,
        value: a,
        ...r,
        ref: g,
        onKeyDown: F(t, (y) => {
          y.key === "Enter" && y.preventDefault();
        }),
        onClick: F(n, (y) => {
          d((w) => be(w) ? !0 : !w), b && h && (m.current = y.isPropagationStopped(), m.current || y.stopPropagation());
        })
      }
    );
  }
);
to.displayName = eo;
var Sn = c.forwardRef(
  (e, t) => {
    const {
      __scopeCheckbox: n,
      name: r,
      checked: o,
      defaultChecked: i,
      required: a,
      disabled: s,
      value: l,
      onCheckedChange: u,
      form: p,
      ...d
    } = e;
    return /* @__PURE__ */ f(
      dc,
      {
        __scopeCheckbox: n,
        checked: o,
        defaultChecked: i,
        disabled: s,
        required: a,
        onCheckedChange: u,
        name: r,
        form: p,
        value: l,
        internal_do_not_use_render: ({ isFormControl: m }) => /* @__PURE__ */ S(G, { children: [
          /* @__PURE__ */ f(
            to,
            {
              ...d,
              ref: t,
              __scopeCheckbox: n
            }
          ),
          m && /* @__PURE__ */ f(
            io,
            {
              __scopeCheckbox: n
            }
          )
        ] })
      }
    );
  }
);
Sn.displayName = Ct;
var no = "CheckboxIndicator", ro = c.forwardRef(
  (e, t) => {
    const { __scopeCheckbox: n, forceMount: r, ...o } = e, i = En(no, n);
    return /* @__PURE__ */ f(
      we,
      {
        present: r || be(i.checked) || i.checked === !0,
        children: /* @__PURE__ */ f(
          Cn.span,
          {
            "data-state": so(i.checked),
            "data-disabled": i.disabled ? "" : void 0,
            ...o,
            ref: t,
            style: { pointerEvents: "none", ...e.style }
          }
        )
      }
    );
  }
);
ro.displayName = no;
var oo = "CheckboxBubbleInput", io = c.forwardRef(
  ({ __scopeCheckbox: e, ...t }, n) => {
    const {
      control: r,
      hasConsumerStoppedPropagationRef: o,
      checked: i,
      defaultChecked: a,
      required: s,
      disabled: l,
      name: u,
      value: p,
      form: d,
      bubbleInput: m,
      setBubbleInput: h
    } = En(oo, e), b = U(n, h), g = Qa(i), v = Jr(r);
    c.useEffect(() => {
      const w = m;
      if (!w) return;
      const C = window.HTMLInputElement.prototype, E = Object.getOwnPropertyDescriptor(
        C,
        "checked"
      ).set, N = !o.current;
      if (g !== i && E) {
        const R = new Event("click", { bubbles: N });
        w.indeterminate = be(i), E.call(w, be(i) ? !1 : i), w.dispatchEvent(R);
      }
    }, [m, g, i, o]);
    const y = c.useRef(be(i) ? !1 : i);
    return /* @__PURE__ */ f(
      Cn.input,
      {
        type: "checkbox",
        "aria-hidden": !0,
        defaultChecked: a ?? y.current,
        required: s,
        disabled: l,
        name: u,
        value: p,
        form: d,
        ...t,
        tabIndex: -1,
        ref: b,
        style: {
          ...t.style,
          ...v,
          position: "absolute",
          pointerEvents: "none",
          opacity: 0,
          margin: 0,
          // We transform because the input is absolutely positioned but we have
          // rendered it **after** the button. This pulls it back to sit on top
          // of the button.
          transform: "translateX(-100%)"
        }
      }
    );
  }
);
io.displayName = oo;
function fc(e) {
  return typeof e == "function";
}
function be(e) {
  return e === "indeterminate";
}
function so(e) {
  return be(e) ? "indeterminate" : e ? "checked" : "unchecked";
}
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
var pc = {
  xmlns: "http://www.w3.org/2000/svg",
  width: 24,
  height: 24,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round"
};
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const mc = (e) => e.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase().trim(), X = (e, t) => {
  const n = Gs(
    ({ color: r = "currentColor", size: o = 24, strokeWidth: i = 2, absoluteStrokeWidth: a, className: s = "", children: l, ...u }, p) => Zn(
      "svg",
      {
        ref: p,
        ...pc,
        width: o,
        height: o,
        stroke: r,
        strokeWidth: a ? Number(i) * 24 / Number(o) : i,
        className: ["lucide", `lucide-${mc(e)}`, s].join(" "),
        ...u
      },
      [
        ...t.map(([d, m]) => Zn(d, m)),
        ...Array.isArray(l) ? l : [l]
      ]
    )
  );
  return n.displayName = `${e}`, n;
};
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const ao = X("AlertCircle", [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["line", { x1: "12", x2: "12", y1: "8", y2: "12", key: "1pkeuh" }],
  ["line", { x1: "12", x2: "12.01", y1: "16", y2: "16", key: "4dfq90" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const co = X("AlertTriangle", [
  [
    "path",
    {
      d: "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z",
      key: "c3ski4"
    }
  ],
  ["path", { d: "M12 9v4", key: "juzpu7" }],
  ["path", { d: "M12 17h.01", key: "p32p05" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const lo = X("Archive", [
  ["rect", { width: "20", height: "5", x: "2", y: "3", rx: "1", key: "1wp1u1" }],
  ["path", { d: "M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8", key: "1s80jp" }],
  ["path", { d: "M10 12h4", key: "a56b0p" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const uo = X("CheckCircle", [
  ["path", { d: "M22 11.08V12a10 10 0 1 1-5.93-9.14", key: "g774vq" }],
  ["path", { d: "m9 11 3 3L22 4", key: "1pflzl" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const gc = X("Check", [["path", { d: "M20 6 9 17l-5-5", key: "1gmf2c" }]]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const hc = X("ChevronDown", [
  ["path", { d: "m6 9 6 6 6-6", key: "qrunsl" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const vc = X("Clock", [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["polyline", { points: "12 6 12 12 16 14", key: "68esgv" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const bc = X("Download", [
  ["path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", key: "ih7n3h" }],
  ["polyline", { points: "7 10 12 15 17 10", key: "2ggqvy" }],
  ["line", { x1: "12", x2: "12", y1: "15", y2: "3", key: "1vk2je" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const fo = X("Flag", [
  ["path", { d: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z", key: "i9b6wo" }],
  ["line", { x1: "4", x2: "4", y1: "22", y2: "15", key: "1cm3nv" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const yc = X("Info", [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M12 16v-4", key: "1dtifu" }],
  ["path", { d: "M12 8h.01", key: "e9boi3" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const xc = X("Loader2", [
  ["path", { d: "M21 12a9 9 0 1 1-6.219-8.56", key: "13zald" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const po = X("UserPlus", [
  ["path", { d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", key: "1yyitq" }],
  ["circle", { cx: "9", cy: "7", r: "4", key: "nufk8" }],
  ["line", { x1: "19", x2: "19", y1: "8", y2: "14", key: "1bvyxn" }],
  ["line", { x1: "22", x2: "16", y1: "11", y2: "11", key: "1shjgl" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const wc = X("User", [
  ["path", { d: "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2", key: "975kel" }],
  ["circle", { cx: "12", cy: "7", r: "4", key: "17ys0d" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const Cc = X("XCircle", [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "m15 9-6 6", key: "1uzhvr" }],
  ["path", { d: "m9 9 6 6", key: "z0biqf" }]
]);
/**
 * @license lucide-react v0.309.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */
const Et = X("X", [
  ["path", { d: "M18 6 6 18", key: "1bl5f8" }],
  ["path", { d: "m6 6 12 12", key: "d8bk6v" }]
]), Ec = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Sn,
  {
    ref: n,
    className: L(
      "peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
      e
    ),
    ...t,
    children: /* @__PURE__ */ f(
      ro,
      {
        className: L("flex items-center justify-center text-current"),
        children: /* @__PURE__ */ f(gc, { className: "h-4 w-4" })
      }
    )
  }
));
Ec.displayName = Sn.displayName;
const Sc = qe(
  "relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground",
  {
    variants: {
      variant: {
        default: "bg-background text-foreground",
        destructive: "border-destructive/50 text-destructive dark:border-destructive [&>svg]:text-destructive"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
), mo = c.forwardRef(({ className: e, variant: t, ...n }, r) => /* @__PURE__ */ f(
  "div",
  {
    ref: r,
    role: "alert",
    className: L(Sc({ variant: t }), e),
    ...n
  }
));
mo.displayName = "Alert";
const Nc = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "h5",
  {
    ref: n,
    className: L("mb-1 font-medium leading-none tracking-tight", e),
    ...t
  }
));
Nc.displayName = "AlertTitle";
const go = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "div",
  {
    ref: n,
    className: L("text-sm [&_p]:leading-relaxed", e),
    ...t
  }
));
go.displayName = "AlertDescription";
function Rc(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, Tc(o, ...t)];
}
function Tc(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
function Pc(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, Ac(o, ...t)];
}
function Ac(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
// @__NO_SIDE_EFFECTS__
function or(e) {
  const t = /* @__PURE__ */ kc(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(Oc);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function kc(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = Ic(o), s = $c(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var _c = Symbol("radix.slottable");
function Oc(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === _c;
}
function $c(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Ic(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
function ho(e) {
  const t = e + "CollectionProvider", [n, r] = Pc(t), [o, i] = n(
    t,
    { collectionRef: { current: null }, itemMap: /* @__PURE__ */ new Map() }
  ), a = (g) => {
    const { scope: v, children: y } = g, w = fe.useRef(null), C = fe.useRef(/* @__PURE__ */ new Map()).current;
    return /* @__PURE__ */ f(o, { scope: v, itemMap: C, collectionRef: w, children: y });
  };
  a.displayName = t;
  const s = e + "CollectionSlot", l = /* @__PURE__ */ or(s), u = fe.forwardRef(
    (g, v) => {
      const { scope: y, children: w } = g, C = i(s, y), x = U(v, C.collectionRef);
      return /* @__PURE__ */ f(l, { ref: x, children: w });
    }
  );
  u.displayName = s;
  const p = e + "CollectionItemSlot", d = "data-radix-collection-item", m = /* @__PURE__ */ or(p), h = fe.forwardRef(
    (g, v) => {
      const { scope: y, children: w, ...C } = g, x = fe.useRef(null), E = U(v, x), N = i(p, y);
      return fe.useEffect(() => (N.itemMap.set(x, { ref: x, ...C }), () => void N.itemMap.delete(x))), /* @__PURE__ */ f(m, { [d]: "", ref: E, children: w });
    }
  );
  h.displayName = p;
  function b(g) {
    const v = i(e + "CollectionConsumer", g);
    return fe.useCallback(() => {
      const w = v.collectionRef.current;
      if (!w) return [];
      const C = Array.from(w.querySelectorAll(`[${d}]`));
      return Array.from(v.itemMap.values()).sort(
        (N, R) => C.indexOf(N.ref.current) - C.indexOf(R.ref.current)
      );
    }, [v.collectionRef, v.itemMap]);
  }
  return [
    { Provider: a, Slot: u, ItemSlot: h },
    b,
    r
  ];
}
function Dc(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, Mc(o, ...t)];
}
function Mc(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
var Lc = c[" useId ".trim().toString()] || (() => {
}), Fc = 0;
function ke(e) {
  const [t, n] = c.useState(Lc());
  return te(() => {
    n((r) => r ?? String(Fc++));
  }, [e]), t ? `radix-${t}` : "";
}
// @__NO_SIDE_EFFECTS__
function Vc(e) {
  const t = /* @__PURE__ */ Wc(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(jc);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function Wc(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = zc(o), s = Hc(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Bc = Symbol("radix.slottable");
function jc(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Bc;
}
function Hc(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function zc(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var Uc = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], vo = Uc.reduce((e, t) => {
  const n = /* @__PURE__ */ Vc(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {});
function ne(e) {
  const t = c.useRef(e);
  return c.useEffect(() => {
    t.current = e;
  }), c.useMemo(() => (...n) => {
    var r;
    return (r = t.current) == null ? void 0 : r.call(t, ...n);
  }, []);
}
var Gc = c.createContext(void 0);
function bo(e) {
  const t = c.useContext(Gc);
  return e || t || "ltr";
}
var Vt = "rovingFocusGroup.onEntryFocus", Kc = { bubbles: !1, cancelable: !0 }, Xe = "RovingFocusGroup", [nn, yo, qc] = ho(Xe), [Yc, xo] = Dc(
  Xe,
  [qc]
), [Xc, Zc] = Yc(Xe), wo = c.forwardRef(
  (e, t) => /* @__PURE__ */ f(nn.Provider, { scope: e.__scopeRovingFocusGroup, children: /* @__PURE__ */ f(nn.Slot, { scope: e.__scopeRovingFocusGroup, children: /* @__PURE__ */ f(Qc, { ...e, ref: t }) }) })
);
wo.displayName = Xe;
var Qc = c.forwardRef((e, t) => {
  const {
    __scopeRovingFocusGroup: n,
    orientation: r,
    loop: o = !1,
    dir: i,
    currentTabStopId: a,
    defaultCurrentTabStopId: s,
    onCurrentTabStopIdChange: l,
    onEntryFocus: u,
    preventScrollOnEntryFocus: p = !1,
    ...d
  } = e, m = c.useRef(null), h = U(t, m), b = bo(i), [g, v] = Me({
    prop: a,
    defaultProp: s ?? null,
    onChange: l,
    caller: Xe
  }), [y, w] = c.useState(!1), C = ne(u), x = yo(n), E = c.useRef(!1), [N, R] = c.useState(0);
  return c.useEffect(() => {
    const A = m.current;
    if (A)
      return A.addEventListener(Vt, C), () => A.removeEventListener(Vt, C);
  }, [C]), /* @__PURE__ */ f(
    Xc,
    {
      scope: n,
      orientation: r,
      dir: b,
      loop: o,
      currentTabStopId: g,
      onItemFocus: c.useCallback(
        (A) => v(A),
        [v]
      ),
      onItemShiftTab: c.useCallback(() => w(!0), []),
      onFocusableItemAdd: c.useCallback(
        () => R((A) => A + 1),
        []
      ),
      onFocusableItemRemove: c.useCallback(
        () => R((A) => A - 1),
        []
      ),
      children: /* @__PURE__ */ f(
        vo.div,
        {
          tabIndex: y || N === 0 ? -1 : 0,
          "data-orientation": r,
          ...d,
          ref: h,
          style: { outline: "none", ...e.style },
          onMouseDown: F(e.onMouseDown, () => {
            E.current = !0;
          }),
          onFocus: F(e.onFocus, (A) => {
            const P = !E.current;
            if (A.target === A.currentTarget && P && !y) {
              const _ = new CustomEvent(Vt, Kc);
              if (A.currentTarget.dispatchEvent(_), !_.defaultPrevented) {
                const I = x().filter((O) => O.focusable), k = I.find((O) => O.active), V = I.find((O) => O.id === g), M = [k, V, ...I].filter(
                  Boolean
                ).map((O) => O.ref.current);
                So(M, p);
              }
            }
            E.current = !1;
          }),
          onBlur: F(e.onBlur, () => w(!1))
        }
      )
    }
  );
}), Co = "RovingFocusGroupItem", Eo = c.forwardRef(
  (e, t) => {
    const {
      __scopeRovingFocusGroup: n,
      focusable: r = !0,
      active: o = !1,
      tabStopId: i,
      children: a,
      ...s
    } = e, l = ke(), u = i || l, p = Zc(Co, n), d = p.currentTabStopId === u, m = yo(n), { onFocusableItemAdd: h, onFocusableItemRemove: b, currentTabStopId: g } = p;
    return c.useEffect(() => {
      if (r)
        return h(), () => b();
    }, [r, h, b]), /* @__PURE__ */ f(
      nn.ItemSlot,
      {
        scope: n,
        id: u,
        focusable: r,
        active: o,
        children: /* @__PURE__ */ f(
          vo.span,
          {
            tabIndex: d ? 0 : -1,
            "data-orientation": p.orientation,
            ...s,
            ref: t,
            onMouseDown: F(e.onMouseDown, (v) => {
              r ? p.onItemFocus(u) : v.preventDefault();
            }),
            onFocus: F(e.onFocus, () => p.onItemFocus(u)),
            onKeyDown: F(e.onKeyDown, (v) => {
              if (v.key === "Tab" && v.shiftKey) {
                p.onItemShiftTab();
                return;
              }
              if (v.target !== v.currentTarget) return;
              const y = tl(v, p.orientation, p.dir);
              if (y !== void 0) {
                if (v.metaKey || v.ctrlKey || v.altKey || v.shiftKey) return;
                v.preventDefault();
                let C = m().filter((x) => x.focusable).map((x) => x.ref.current);
                if (y === "last") C.reverse();
                else if (y === "prev" || y === "next") {
                  y === "prev" && C.reverse();
                  const x = C.indexOf(v.currentTarget);
                  C = p.loop ? nl(C, x + 1) : C.slice(x + 1);
                }
                setTimeout(() => So(C));
              }
            }),
            children: typeof a == "function" ? a({ isCurrentTabStop: d, hasTabStop: g != null }) : a
          }
        )
      }
    );
  }
);
Eo.displayName = Co;
var Jc = {
  ArrowLeft: "prev",
  ArrowUp: "prev",
  ArrowRight: "next",
  ArrowDown: "next",
  PageUp: "first",
  Home: "first",
  PageDown: "last",
  End: "last"
};
function el(e, t) {
  return t !== "rtl" ? e : e === "ArrowLeft" ? "ArrowRight" : e === "ArrowRight" ? "ArrowLeft" : e;
}
function tl(e, t, n) {
  const r = el(e.key, n);
  if (!(t === "vertical" && ["ArrowLeft", "ArrowRight"].includes(r)) && !(t === "horizontal" && ["ArrowUp", "ArrowDown"].includes(r)))
    return Jc[r];
}
function So(e, t = !1) {
  const n = document.activeElement;
  for (const r of e)
    if (r === n || (r.focus({ preventScroll: t }), document.activeElement !== n)) return;
}
function nl(e, t) {
  return e.map((n, r) => e[(t + r) % e.length]);
}
var rl = wo, ol = Eo;
// @__NO_SIDE_EFFECTS__
function il(e) {
  const t = /* @__PURE__ */ sl(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(cl);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function sl(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = ul(o), s = ll(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var al = Symbol("radix.slottable");
function cl(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === al;
}
function ll(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function ul(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var dl = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], St = dl.reduce((e, t) => {
  const n = /* @__PURE__ */ il(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), Nt = "Tabs", [fl] = Rc(Nt, [
  xo
]), No = xo(), [pl, Nn] = fl(Nt), Ro = c.forwardRef(
  (e, t) => {
    const {
      __scopeTabs: n,
      value: r,
      onValueChange: o,
      defaultValue: i,
      orientation: a = "horizontal",
      dir: s,
      activationMode: l = "automatic",
      ...u
    } = e, p = bo(s), [d, m] = Me({
      prop: r,
      onChange: o,
      defaultProp: i ?? "",
      caller: Nt
    });
    return /* @__PURE__ */ f(
      pl,
      {
        scope: n,
        baseId: ke(),
        value: d,
        onValueChange: m,
        orientation: a,
        dir: p,
        activationMode: l,
        children: /* @__PURE__ */ f(
          St.div,
          {
            dir: p,
            "data-orientation": a,
            ...u,
            ref: t
          }
        )
      }
    );
  }
);
Ro.displayName = Nt;
var To = "TabsList", Po = c.forwardRef(
  (e, t) => {
    const { __scopeTabs: n, loop: r = !0, ...o } = e, i = Nn(To, n), a = No(n);
    return /* @__PURE__ */ f(
      rl,
      {
        asChild: !0,
        ...a,
        orientation: i.orientation,
        dir: i.dir,
        loop: r,
        children: /* @__PURE__ */ f(
          St.div,
          {
            role: "tablist",
            "aria-orientation": i.orientation,
            ...o,
            ref: t
          }
        )
      }
    );
  }
);
Po.displayName = To;
var Ao = "TabsTrigger", ko = c.forwardRef(
  (e, t) => {
    const { __scopeTabs: n, value: r, disabled: o = !1, ...i } = e, a = Nn(Ao, n), s = No(n), l = $o(a.baseId, r), u = Io(a.baseId, r), p = r === a.value;
    return /* @__PURE__ */ f(
      ol,
      {
        asChild: !0,
        ...s,
        focusable: !o,
        active: p,
        children: /* @__PURE__ */ f(
          St.button,
          {
            type: "button",
            role: "tab",
            "aria-selected": p,
            "aria-controls": u,
            "data-state": p ? "active" : "inactive",
            "data-disabled": o ? "" : void 0,
            disabled: o,
            id: l,
            ...i,
            ref: t,
            onMouseDown: F(e.onMouseDown, (d) => {
              !o && d.button === 0 && d.ctrlKey === !1 ? a.onValueChange(r) : d.preventDefault();
            }),
            onKeyDown: F(e.onKeyDown, (d) => {
              [" ", "Enter"].includes(d.key) && a.onValueChange(r);
            }),
            onFocus: F(e.onFocus, () => {
              const d = a.activationMode !== "manual";
              !p && !o && d && a.onValueChange(r);
            })
          }
        )
      }
    );
  }
);
ko.displayName = Ao;
var _o = "TabsContent", Oo = c.forwardRef(
  (e, t) => {
    const { __scopeTabs: n, value: r, forceMount: o, children: i, ...a } = e, s = Nn(_o, n), l = $o(s.baseId, r), u = Io(s.baseId, r), p = r === s.value, d = c.useRef(p);
    return c.useEffect(() => {
      const m = requestAnimationFrame(() => d.current = !1);
      return () => cancelAnimationFrame(m);
    }, []), /* @__PURE__ */ f(we, { present: o || p, children: ({ present: m }) => /* @__PURE__ */ f(
      St.div,
      {
        "data-state": p ? "active" : "inactive",
        "data-orientation": s.orientation,
        role: "tabpanel",
        "aria-labelledby": l,
        hidden: !m,
        id: u,
        tabIndex: 0,
        ...a,
        ref: t,
        style: {
          ...e.style,
          animationDuration: d.current ? "0s" : void 0
        },
        children: m && i
      }
    ) });
  }
);
Oo.displayName = _o;
function $o(e, t) {
  return `${e}-trigger-${t}`;
}
function Io(e, t) {
  return `${e}-content-${t}`;
}
var ml = Ro, Do = Po, Mo = ko, Lo = Oo;
const ag = ml, gl = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Do,
  {
    ref: n,
    className: L(
      "inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground",
      e
    ),
    ...t
  }
));
gl.displayName = Do.displayName;
const hl = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Mo,
  {
    ref: n,
    className: L(
      "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
      e
    ),
    ...t
  }
));
hl.displayName = Mo.displayName;
const vl = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Lo,
  {
    ref: n,
    className: L(
      "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      e
    ),
    ...t
  }
));
vl.displayName = Lo.displayName;
function bl(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a);
    s.displayName = i + "Context";
    const l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, yl(o, ...t)];
}
function yl(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
var rn = { exports: {} }, Wt = {};
/**
 * @license React
 * use-sync-external-store-shim.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var ir;
function xl() {
  if (ir) return Wt;
  ir = 1;
  var e = fe;
  function t(d, m) {
    return d === m && (d !== 0 || 1 / d === 1 / m) || d !== d && m !== m;
  }
  var n = typeof Object.is == "function" ? Object.is : t, r = e.useState, o = e.useEffect, i = e.useLayoutEffect, a = e.useDebugValue;
  function s(d, m) {
    var h = m(), b = r({ inst: { value: h, getSnapshot: m } }), g = b[0].inst, v = b[1];
    return i(
      function() {
        g.value = h, g.getSnapshot = m, l(g) && v({ inst: g });
      },
      [d, h, m]
    ), o(
      function() {
        return l(g) && v({ inst: g }), d(function() {
          l(g) && v({ inst: g });
        });
      },
      [d]
    ), a(h), h;
  }
  function l(d) {
    var m = d.getSnapshot;
    d = d.value;
    try {
      var h = m();
      return !n(d, h);
    } catch {
      return !0;
    }
  }
  function u(d, m) {
    return m();
  }
  var p = typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u" ? u : s;
  return Wt.useSyncExternalStore = e.useSyncExternalStore !== void 0 ? e.useSyncExternalStore : p, Wt;
}
var Bt = {};
/**
 * @license React
 * use-sync-external-store-shim.development.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var sr;
function wl() {
  return sr || (sr = 1, process.env.NODE_ENV !== "production" && function() {
    function e(h, b) {
      return h === b && (h !== 0 || 1 / h === 1 / b) || h !== h && b !== b;
    }
    function t(h, b) {
      p || o.startTransition === void 0 || (p = !0, console.error(
        "You are using an outdated, pre-release alpha of React 18 that does not support useSyncExternalStore. The use-sync-external-store shim will not work correctly. Upgrade to a newer pre-release."
      ));
      var g = b();
      if (!d) {
        var v = b();
        i(g, v) || (console.error(
          "The result of getSnapshot should be cached to avoid an infinite loop"
        ), d = !0);
      }
      v = a({
        inst: { value: g, getSnapshot: b }
      });
      var y = v[0].inst, w = v[1];
      return l(
        function() {
          y.value = g, y.getSnapshot = b, n(y) && w({ inst: y });
        },
        [h, g, b]
      ), s(
        function() {
          return n(y) && w({ inst: y }), h(function() {
            n(y) && w({ inst: y });
          });
        },
        [h]
      ), u(g), g;
    }
    function n(h) {
      var b = h.getSnapshot;
      h = h.value;
      try {
        var g = b();
        return !i(h, g);
      } catch {
        return !0;
      }
    }
    function r(h, b) {
      return b();
    }
    typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStart(Error());
    var o = fe, i = typeof Object.is == "function" ? Object.is : e, a = o.useState, s = o.useEffect, l = o.useLayoutEffect, u = o.useDebugValue, p = !1, d = !1, m = typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u" ? r : t;
    Bt.useSyncExternalStore = o.useSyncExternalStore !== void 0 ? o.useSyncExternalStore : m, typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u" && typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop == "function" && __REACT_DEVTOOLS_GLOBAL_HOOK__.registerInternalModuleStop(Error());
  }()), Bt;
}
process.env.NODE_ENV === "production" ? rn.exports = xl() : rn.exports = wl();
var Cl = rn.exports;
function El() {
  return Cl.useSyncExternalStore(
    Sl,
    () => !0,
    () => !1
  );
}
function Sl() {
  return () => {
  };
}
var Rn = "Avatar", [Nl] = bl(Rn), [Rl, Fo] = Nl(Rn), Vo = c.forwardRef(
  (e, t) => {
    const { __scopeAvatar: n, ...r } = e, [o, i] = c.useState("idle");
    return /* @__PURE__ */ f(
      Rl,
      {
        scope: n,
        imageLoadingStatus: o,
        onImageLoadingStatusChange: i,
        children: /* @__PURE__ */ f(Ye.span, { ...r, ref: t })
      }
    );
  }
);
Vo.displayName = Rn;
var Wo = "AvatarImage", Bo = c.forwardRef(
  (e, t) => {
    const { __scopeAvatar: n, src: r, onLoadingStatusChange: o = () => {
    }, ...i } = e, a = Fo(Wo, n), s = Tl(r, i), l = ne((u) => {
      o(u), a.onImageLoadingStatusChange(u);
    });
    return te(() => {
      s !== "idle" && l(s);
    }, [s, l]), s === "loaded" ? /* @__PURE__ */ f(Ye.img, { ...i, ref: t, src: r }) : null;
  }
);
Bo.displayName = Wo;
var jo = "AvatarFallback", Ho = c.forwardRef(
  (e, t) => {
    const { __scopeAvatar: n, delayMs: r, ...o } = e, i = Fo(jo, n), [a, s] = c.useState(r === void 0);
    return c.useEffect(() => {
      if (r !== void 0) {
        const l = window.setTimeout(() => s(!0), r);
        return () => window.clearTimeout(l);
      }
    }, [r]), a && i.imageLoadingStatus !== "loaded" ? /* @__PURE__ */ f(Ye.span, { ...o, ref: t }) : null;
  }
);
Ho.displayName = jo;
function ar(e, t) {
  return e ? t ? (e.src !== t && (e.src = t), e.complete && e.naturalWidth > 0 ? "loaded" : "loading") : "error" : "idle";
}
function Tl(e, { referrerPolicy: t, crossOrigin: n }) {
  const r = El(), o = c.useRef(null), i = r ? (o.current || (o.current = new window.Image()), o.current) : null, [a, s] = c.useState(
    () => ar(i, e)
  );
  return te(() => {
    s(ar(i, e));
  }, [i, e]), te(() => {
    const l = (d) => () => {
      s(d);
    };
    if (!i) return;
    const u = l("loaded"), p = l("error");
    return i.addEventListener("load", u), i.addEventListener("error", p), t && (i.referrerPolicy = t), typeof n == "string" && (i.crossOrigin = n), () => {
      i.removeEventListener("load", u), i.removeEventListener("error", p);
    };
  }, [i, n, t]), a;
}
var zo = Vo, Uo = Bo, Go = Ho;
const Pl = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  zo,
  {
    ref: n,
    className: L(
      `
      after:content-[''] after:block after:absolute after:inset-0 after:rounded-full after:pointer-events-none after:border after:border-black/10 dark:after:border-white/10
      relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full`,
      e
    ),
    ...t
  }
));
Pl.displayName = zo.displayName;
const Al = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Uo,
  {
    ref: n,
    className: L("aspect-square h-full w-full", e),
    ...t
  }
));
Al.displayName = Uo.displayName;
const kl = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Go,
  {
    ref: n,
    className: L(
      "flex h-full w-full items-center justify-center rounded-full bg-muted",
      e
    ),
    ...t
  }
));
kl.displayName = Go.displayName;
function _l(e, t) {
  const n = c.createContext(t), r = (i) => {
    const { children: a, ...s } = i, l = c.useMemo(() => s, Object.values(s));
    return /* @__PURE__ */ f(n.Provider, { value: l, children: a });
  };
  r.displayName = e + "Provider";
  function o(i) {
    const a = c.useContext(n);
    if (a) return a;
    if (t !== void 0) return t;
    throw new Error(`\`${i}\` must be used within \`${e}\``);
  }
  return [r, o];
}
function Ol(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, $l(o, ...t)];
}
function $l(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
// @__NO_SIDE_EFFECTS__
function Il(e) {
  const t = /* @__PURE__ */ Dl(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(Ll);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function Dl(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = Vl(o), s = Fl(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Ml = Symbol("radix.slottable");
function Ll(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Ml;
}
function Fl(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Vl(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var Wl = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Ko = Wl.reduce((e, t) => {
  const n = /* @__PURE__ */ Il(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {});
function Bl(e, t) {
  e && wt.flushSync(() => e.dispatchEvent(t));
}
function jl(e, t = globalThis == null ? void 0 : globalThis.document) {
  const n = ne(e);
  c.useEffect(() => {
    const r = (o) => {
      o.key === "Escape" && n(o);
    };
    return t.addEventListener("keydown", r, { capture: !0 }), () => t.removeEventListener("keydown", r, { capture: !0 });
  }, [n, t]);
}
var Hl = "DismissableLayer", on = "dismissableLayer.update", zl = "dismissableLayer.pointerDownOutside", Ul = "dismissableLayer.focusOutside", cr, qo = c.createContext({
  layers: /* @__PURE__ */ new Set(),
  layersWithOutsidePointerEventsDisabled: /* @__PURE__ */ new Set(),
  branches: /* @__PURE__ */ new Set()
}), Rt = c.forwardRef(
  (e, t) => {
    const {
      disableOutsidePointerEvents: n = !1,
      onEscapeKeyDown: r,
      onPointerDownOutside: o,
      onFocusOutside: i,
      onInteractOutside: a,
      onDismiss: s,
      ...l
    } = e, u = c.useContext(qo), [p, d] = c.useState(null), m = (p == null ? void 0 : p.ownerDocument) ?? (globalThis == null ? void 0 : globalThis.document), [, h] = c.useState({}), b = U(t, (R) => d(R)), g = Array.from(u.layers), [v] = [...u.layersWithOutsidePointerEventsDisabled].slice(-1), y = g.indexOf(v), w = p ? g.indexOf(p) : -1, C = u.layersWithOutsidePointerEventsDisabled.size > 0, x = w >= y, E = Kl((R) => {
      const A = R.target, P = [...u.branches].some((_) => _.contains(A));
      !x || P || (o == null || o(R), a == null || a(R), R.defaultPrevented || s == null || s());
    }, m), N = ql((R) => {
      const A = R.target;
      [...u.branches].some((_) => _.contains(A)) || (i == null || i(R), a == null || a(R), R.defaultPrevented || s == null || s());
    }, m);
    return jl((R) => {
      w === u.layers.size - 1 && (r == null || r(R), !R.defaultPrevented && s && (R.preventDefault(), s()));
    }, m), c.useEffect(() => {
      if (p)
        return n && (u.layersWithOutsidePointerEventsDisabled.size === 0 && (cr = m.body.style.pointerEvents, m.body.style.pointerEvents = "none"), u.layersWithOutsidePointerEventsDisabled.add(p)), u.layers.add(p), lr(), () => {
          n && u.layersWithOutsidePointerEventsDisabled.size === 1 && (m.body.style.pointerEvents = cr);
        };
    }, [p, m, n, u]), c.useEffect(() => () => {
      p && (u.layers.delete(p), u.layersWithOutsidePointerEventsDisabled.delete(p), lr());
    }, [p, u]), c.useEffect(() => {
      const R = () => h({});
      return document.addEventListener(on, R), () => document.removeEventListener(on, R);
    }, []), /* @__PURE__ */ f(
      Ko.div,
      {
        ...l,
        ref: b,
        style: {
          pointerEvents: C ? x ? "auto" : "none" : void 0,
          ...e.style
        },
        onFocusCapture: F(e.onFocusCapture, N.onFocusCapture),
        onBlurCapture: F(e.onBlurCapture, N.onBlurCapture),
        onPointerDownCapture: F(
          e.onPointerDownCapture,
          E.onPointerDownCapture
        )
      }
    );
  }
);
Rt.displayName = Hl;
var Gl = "DismissableLayerBranch", Yo = c.forwardRef((e, t) => {
  const n = c.useContext(qo), r = c.useRef(null), o = U(t, r);
  return c.useEffect(() => {
    const i = r.current;
    if (i)
      return n.branches.add(i), () => {
        n.branches.delete(i);
      };
  }, [n.branches]), /* @__PURE__ */ f(Ko.div, { ...e, ref: o });
});
Yo.displayName = Gl;
function Kl(e, t = globalThis == null ? void 0 : globalThis.document) {
  const n = ne(e), r = c.useRef(!1), o = c.useRef(() => {
  });
  return c.useEffect(() => {
    const i = (s) => {
      if (s.target && !r.current) {
        let l = function() {
          Xo(
            zl,
            n,
            u,
            { discrete: !0 }
          );
        };
        const u = { originalEvent: s };
        s.pointerType === "touch" ? (t.removeEventListener("click", o.current), o.current = l, t.addEventListener("click", o.current, { once: !0 })) : l();
      } else
        t.removeEventListener("click", o.current);
      r.current = !1;
    }, a = window.setTimeout(() => {
      t.addEventListener("pointerdown", i);
    }, 0);
    return () => {
      window.clearTimeout(a), t.removeEventListener("pointerdown", i), t.removeEventListener("click", o.current);
    };
  }, [t, n]), {
    // ensures we check React component tree (not just DOM tree)
    onPointerDownCapture: () => r.current = !0
  };
}
function ql(e, t = globalThis == null ? void 0 : globalThis.document) {
  const n = ne(e), r = c.useRef(!1);
  return c.useEffect(() => {
    const o = (i) => {
      i.target && !r.current && Xo(Ul, n, { originalEvent: i }, {
        discrete: !1
      });
    };
    return t.addEventListener("focusin", o), () => t.removeEventListener("focusin", o);
  }, [t, n]), {
    onFocusCapture: () => r.current = !0,
    onBlurCapture: () => r.current = !1
  };
}
function lr() {
  const e = new CustomEvent(on);
  document.dispatchEvent(e);
}
function Xo(e, t, n, { discrete: r }) {
  const o = n.originalEvent.target, i = new CustomEvent(e, { bubbles: !1, cancelable: !0, detail: n });
  t && o.addEventListener(e, t, { once: !0 }), r ? Bl(o, i) : o.dispatchEvent(i);
}
var Yl = Rt, Xl = Yo;
// @__NO_SIDE_EFFECTS__
function Zl(e) {
  const t = /* @__PURE__ */ Ql(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(eu);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function Ql(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = nu(o), s = tu(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Jl = Symbol("radix.slottable");
function eu(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Jl;
}
function tu(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function nu(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var ru = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], ou = ru.reduce((e, t) => {
  const n = /* @__PURE__ */ Zl(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), jt = "focusScope.autoFocusOnMount", Ht = "focusScope.autoFocusOnUnmount", ur = { bubbles: !1, cancelable: !0 }, iu = "FocusScope", Zo = c.forwardRef((e, t) => {
  const {
    loop: n = !1,
    trapped: r = !1,
    onMountAutoFocus: o,
    onUnmountAutoFocus: i,
    ...a
  } = e, [s, l] = c.useState(null), u = ne(o), p = ne(i), d = c.useRef(null), m = U(t, (g) => l(g)), h = c.useRef({
    paused: !1,
    pause() {
      this.paused = !0;
    },
    resume() {
      this.paused = !1;
    }
  }).current;
  c.useEffect(() => {
    if (r) {
      let g = function(C) {
        if (h.paused || !s) return;
        const x = C.target;
        s.contains(x) ? d.current = x : ve(d.current, { select: !0 });
      }, v = function(C) {
        if (h.paused || !s) return;
        const x = C.relatedTarget;
        x !== null && (s.contains(x) || ve(d.current, { select: !0 }));
      }, y = function(C) {
        if (document.activeElement === document.body)
          for (const E of C)
            E.removedNodes.length > 0 && ve(s);
      };
      document.addEventListener("focusin", g), document.addEventListener("focusout", v);
      const w = new MutationObserver(y);
      return s && w.observe(s, { childList: !0, subtree: !0 }), () => {
        document.removeEventListener("focusin", g), document.removeEventListener("focusout", v), w.disconnect();
      };
    }
  }, [r, s, h.paused]), c.useEffect(() => {
    if (s) {
      fr.add(h);
      const g = document.activeElement;
      if (!s.contains(g)) {
        const y = new CustomEvent(jt, ur);
        s.addEventListener(jt, u), s.dispatchEvent(y), y.defaultPrevented || (su(du(Qo(s)), { select: !0 }), document.activeElement === g && ve(s));
      }
      return () => {
        s.removeEventListener(jt, u), setTimeout(() => {
          const y = new CustomEvent(Ht, ur);
          s.addEventListener(Ht, p), s.dispatchEvent(y), y.defaultPrevented || ve(g ?? document.body, { select: !0 }), s.removeEventListener(Ht, p), fr.remove(h);
        }, 0);
      };
    }
  }, [s, u, p, h]);
  const b = c.useCallback(
    (g) => {
      if (!n && !r || h.paused) return;
      const v = g.key === "Tab" && !g.altKey && !g.ctrlKey && !g.metaKey, y = document.activeElement;
      if (v && y) {
        const w = g.currentTarget, [C, x] = au(w);
        C && x ? !g.shiftKey && y === x ? (g.preventDefault(), n && ve(C, { select: !0 })) : g.shiftKey && y === C && (g.preventDefault(), n && ve(x, { select: !0 })) : y === w && g.preventDefault();
      }
    },
    [n, r, h.paused]
  );
  return /* @__PURE__ */ f(ou.div, { tabIndex: -1, ...a, ref: m, onKeyDown: b });
});
Zo.displayName = iu;
function su(e, { select: t = !1 } = {}) {
  const n = document.activeElement;
  for (const r of e)
    if (ve(r, { select: t }), document.activeElement !== n) return;
}
function au(e) {
  const t = Qo(e), n = dr(t, e), r = dr(t.reverse(), e);
  return [n, r];
}
function Qo(e) {
  const t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, {
    acceptNode: (r) => {
      const o = r.tagName === "INPUT" && r.type === "hidden";
      return r.disabled || r.hidden || o ? NodeFilter.FILTER_SKIP : r.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
    }
  });
  for (; n.nextNode(); ) t.push(n.currentNode);
  return t;
}
function dr(e, t) {
  for (const n of e)
    if (!cu(n, { upTo: t })) return n;
}
function cu(e, { upTo: t }) {
  if (getComputedStyle(e).visibility === "hidden") return !0;
  for (; e; ) {
    if (t !== void 0 && e === t) return !1;
    if (getComputedStyle(e).display === "none") return !0;
    e = e.parentElement;
  }
  return !1;
}
function lu(e) {
  return e instanceof HTMLInputElement && "select" in e;
}
function ve(e, { select: t = !1 } = {}) {
  if (e && e.focus) {
    const n = document.activeElement;
    e.focus({ preventScroll: !0 }), e !== n && lu(e) && t && e.select();
  }
}
var fr = uu();
function uu() {
  let e = [];
  return {
    add(t) {
      const n = e[0];
      t !== n && (n == null || n.pause()), e = pr(e, t), e.unshift(t);
    },
    remove(t) {
      var n;
      e = pr(e, t), (n = e[0]) == null || n.resume();
    }
  };
}
function pr(e, t) {
  const n = [...e], r = n.indexOf(t);
  return r !== -1 && n.splice(r, 1), n;
}
function du(e) {
  return e.filter((t) => t.tagName !== "A");
}
// @__NO_SIDE_EFFECTS__
function fu(e) {
  const t = /* @__PURE__ */ pu(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(gu);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function pu(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = vu(o), s = hu(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var mu = Symbol("radix.slottable");
function gu(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === mu;
}
function hu(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function vu(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var bu = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], yu = bu.reduce((e, t) => {
  const n = /* @__PURE__ */ fu(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), xu = "Portal", Tn = c.forwardRef((e, t) => {
  var s;
  const { container: n, ...r } = e, [o, i] = c.useState(!1);
  te(() => i(!0), []);
  const a = n || o && ((s = globalThis == null ? void 0 : globalThis.document) == null ? void 0 : s.body);
  return a ? Ys.createPortal(/* @__PURE__ */ f(yu.div, { ...r, ref: t }), a) : null;
});
Tn.displayName = xu;
// @__NO_SIDE_EFFECTS__
function Jo(e) {
  const t = /* @__PURE__ */ wu(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(Eu);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function wu(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = Nu(o), s = Su(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Cu = Symbol("radix.slottable");
function Eu(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Cu;
}
function Su(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Nu(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var Ru = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Ze = Ru.reduce((e, t) => {
  const n = /* @__PURE__ */ Jo(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), zt = 0;
function Tu() {
  c.useEffect(() => {
    const e = document.querySelectorAll("[data-radix-focus-guard]");
    return document.body.insertAdjacentElement("afterbegin", e[0] ?? mr()), document.body.insertAdjacentElement("beforeend", e[1] ?? mr()), zt++, () => {
      zt === 1 && document.querySelectorAll("[data-radix-focus-guard]").forEach((t) => t.remove()), zt--;
    };
  }, []);
}
function mr() {
  const e = document.createElement("span");
  return e.setAttribute("data-radix-focus-guard", ""), e.tabIndex = 0, e.style.outline = "none", e.style.opacity = "0", e.style.position = "fixed", e.style.pointerEvents = "none", e;
}
var se = function() {
  return se = Object.assign || function(t) {
    for (var n, r = 1, o = arguments.length; r < o; r++) {
      n = arguments[r];
      for (var i in n) Object.prototype.hasOwnProperty.call(n, i) && (t[i] = n[i]);
    }
    return t;
  }, se.apply(this, arguments);
};
function ei(e, t) {
  var n = {};
  for (var r in e) Object.prototype.hasOwnProperty.call(e, r) && t.indexOf(r) < 0 && (n[r] = e[r]);
  if (e != null && typeof Object.getOwnPropertySymbols == "function")
    for (var o = 0, r = Object.getOwnPropertySymbols(e); o < r.length; o++)
      t.indexOf(r[o]) < 0 && Object.prototype.propertyIsEnumerable.call(e, r[o]) && (n[r[o]] = e[r[o]]);
  return n;
}
function Pu(e, t, n) {
  if (n || arguments.length === 2) for (var r = 0, o = t.length, i; r < o; r++)
    (i || !(r in t)) && (i || (i = Array.prototype.slice.call(t, 0, r)), i[r] = t[r]);
  return e.concat(i || Array.prototype.slice.call(t));
}
var ut = "right-scroll-bar-position", dt = "width-before-scroll-bar", Au = "with-scroll-bars-hidden", ku = "--removed-body-scroll-bar-size";
function Ut(e, t) {
  return typeof e == "function" ? e(t) : e && (e.current = t), e;
}
function _u(e, t) {
  var n = z(function() {
    return {
      // value
      value: e,
      // last callback
      callback: t,
      // "memoized" public interface
      facade: {
        get current() {
          return n.value;
        },
        set current(r) {
          var o = n.value;
          o !== r && (n.value = r, n.callback(r, o));
        }
      }
    };
  })[0];
  return n.callback = t, n.facade;
}
var Ou = typeof window < "u" ? c.useLayoutEffect : c.useEffect, gr = /* @__PURE__ */ new WeakMap();
function $u(e, t) {
  var n = _u(null, function(r) {
    return e.forEach(function(o) {
      return Ut(o, r);
    });
  });
  return Ou(function() {
    var r = gr.get(n);
    if (r) {
      var o = new Set(r), i = new Set(e), a = n.current;
      o.forEach(function(s) {
        i.has(s) || Ut(s, null);
      }), i.forEach(function(s) {
        o.has(s) || Ut(s, a);
      });
    }
    gr.set(n, e);
  }, [e]), n;
}
function Iu(e) {
  return e;
}
function Du(e, t) {
  t === void 0 && (t = Iu);
  var n = [], r = !1, o = {
    read: function() {
      if (r)
        throw new Error("Sidecar: could not `read` from an `assigned` medium. `read` could be used only with `useMedium`.");
      return n.length ? n[n.length - 1] : e;
    },
    useMedium: function(i) {
      var a = t(i, r);
      return n.push(a), function() {
        n = n.filter(function(s) {
          return s !== a;
        });
      };
    },
    assignSyncMedium: function(i) {
      for (r = !0; n.length; ) {
        var a = n;
        n = [], a.forEach(i);
      }
      n = {
        push: function(s) {
          return i(s);
        },
        filter: function() {
          return n;
        }
      };
    },
    assignMedium: function(i) {
      r = !0;
      var a = [];
      if (n.length) {
        var s = n;
        n = [], s.forEach(i), a = n;
      }
      var l = function() {
        var p = a;
        a = [], p.forEach(i);
      }, u = function() {
        return Promise.resolve().then(l);
      };
      u(), n = {
        push: function(p) {
          a.push(p), u();
        },
        filter: function(p) {
          return a = a.filter(p), n;
        }
      };
    }
  };
  return o;
}
function Mu(e) {
  e === void 0 && (e = {});
  var t = Du(null);
  return t.options = se({ async: !0, ssr: !1 }, e), t;
}
var ti = function(e) {
  var t = e.sideCar, n = ei(e, ["sideCar"]);
  if (!t)
    throw new Error("Sidecar: please provide `sideCar` property to import the right car");
  var r = t.read();
  if (!r)
    throw new Error("Sidecar medium not found");
  return c.createElement(r, se({}, n));
};
ti.isSideCarExport = !0;
function Lu(e, t) {
  return e.useMedium(t), ti;
}
var ni = Mu(), Gt = function() {
}, Tt = c.forwardRef(function(e, t) {
  var n = c.useRef(null), r = c.useState({
    onScrollCapture: Gt,
    onWheelCapture: Gt,
    onTouchMoveCapture: Gt
  }), o = r[0], i = r[1], a = e.forwardProps, s = e.children, l = e.className, u = e.removeScrollBar, p = e.enabled, d = e.shards, m = e.sideCar, h = e.noRelative, b = e.noIsolation, g = e.inert, v = e.allowPinchZoom, y = e.as, w = y === void 0 ? "div" : y, C = e.gapMode, x = ei(e, ["forwardProps", "children", "className", "removeScrollBar", "enabled", "shards", "sideCar", "noRelative", "noIsolation", "inert", "allowPinchZoom", "as", "gapMode"]), E = m, N = $u([n, t]), R = se(se({}, x), o);
  return c.createElement(
    c.Fragment,
    null,
    p && c.createElement(E, { sideCar: ni, removeScrollBar: u, shards: d, noRelative: h, noIsolation: b, inert: g, setCallbacks: i, allowPinchZoom: !!v, lockRef: n, gapMode: C }),
    a ? c.cloneElement(c.Children.only(s), se(se({}, R), { ref: N })) : c.createElement(w, se({}, R, { className: l, ref: N }), s)
  );
});
Tt.defaultProps = {
  enabled: !0,
  removeScrollBar: !0,
  inert: !1
};
Tt.classNames = {
  fullWidth: dt,
  zeroRight: ut
};
var Fu = function() {
  if (typeof __webpack_nonce__ < "u")
    return __webpack_nonce__;
};
function Vu() {
  if (!document)
    return null;
  var e = document.createElement("style");
  e.type = "text/css";
  var t = Fu();
  return t && e.setAttribute("nonce", t), e;
}
function Wu(e, t) {
  e.styleSheet ? e.styleSheet.cssText = t : e.appendChild(document.createTextNode(t));
}
function Bu(e) {
  var t = document.head || document.getElementsByTagName("head")[0];
  t.appendChild(e);
}
var ju = function() {
  var e = 0, t = null;
  return {
    add: function(n) {
      e == 0 && (t = Vu()) && (Wu(t, n), Bu(t)), e++;
    },
    remove: function() {
      e--, !e && t && (t.parentNode && t.parentNode.removeChild(t), t = null);
    }
  };
}, Hu = function() {
  var e = ju();
  return function(t, n) {
    c.useEffect(function() {
      return e.add(t), function() {
        e.remove();
      };
    }, [t && n]);
  };
}, ri = function() {
  var e = Hu(), t = function(n) {
    var r = n.styles, o = n.dynamic;
    return e(r, o), null;
  };
  return t;
}, zu = {
  left: 0,
  top: 0,
  right: 0,
  gap: 0
}, Kt = function(e) {
  return parseInt(e || "", 10) || 0;
}, Uu = function(e) {
  var t = window.getComputedStyle(document.body), n = t[e === "padding" ? "paddingLeft" : "marginLeft"], r = t[e === "padding" ? "paddingTop" : "marginTop"], o = t[e === "padding" ? "paddingRight" : "marginRight"];
  return [Kt(n), Kt(r), Kt(o)];
}, Gu = function(e) {
  if (e === void 0 && (e = "margin"), typeof window > "u")
    return zu;
  var t = Uu(e), n = document.documentElement.clientWidth, r = window.innerWidth;
  return {
    left: t[0],
    top: t[1],
    right: t[2],
    gap: Math.max(0, r - n + t[2] - t[0])
  };
}, Ku = ri(), _e = "data-scroll-locked", qu = function(e, t, n, r) {
  var o = e.left, i = e.top, a = e.right, s = e.gap;
  return n === void 0 && (n = "margin"), `
  .`.concat(Au, ` {
   overflow: hidden `).concat(r, `;
   padding-right: `).concat(s, "px ").concat(r, `;
  }
  body[`).concat(_e, `] {
    overflow: hidden `).concat(r, `;
    overscroll-behavior: contain;
    `).concat([
    t && "position: relative ".concat(r, ";"),
    n === "margin" && `
    padding-left: `.concat(o, `px;
    padding-top: `).concat(i, `px;
    padding-right: `).concat(a, `px;
    margin-left:0;
    margin-top:0;
    margin-right: `).concat(s, "px ").concat(r, `;
    `),
    n === "padding" && "padding-right: ".concat(s, "px ").concat(r, ";")
  ].filter(Boolean).join(""), `
  }
  
  .`).concat(ut, ` {
    right: `).concat(s, "px ").concat(r, `;
  }
  
  .`).concat(dt, ` {
    margin-right: `).concat(s, "px ").concat(r, `;
  }
  
  .`).concat(ut, " .").concat(ut, ` {
    right: 0 `).concat(r, `;
  }
  
  .`).concat(dt, " .").concat(dt, ` {
    margin-right: 0 `).concat(r, `;
  }
  
  body[`).concat(_e, `] {
    `).concat(ku, ": ").concat(s, `px;
  }
`);
}, hr = function() {
  var e = parseInt(document.body.getAttribute(_e) || "0", 10);
  return isFinite(e) ? e : 0;
}, Yu = function() {
  c.useEffect(function() {
    return document.body.setAttribute(_e, (hr() + 1).toString()), function() {
      var e = hr() - 1;
      e <= 0 ? document.body.removeAttribute(_e) : document.body.setAttribute(_e, e.toString());
    };
  }, []);
}, Xu = function(e) {
  var t = e.noRelative, n = e.noImportant, r = e.gapMode, o = r === void 0 ? "margin" : r;
  Yu();
  var i = c.useMemo(function() {
    return Gu(o);
  }, [o]);
  return c.createElement(Ku, { styles: qu(i, !t, o, n ? "" : "!important") });
}, sn = !1;
if (typeof window < "u")
  try {
    var rt = Object.defineProperty({}, "passive", {
      get: function() {
        return sn = !0, !0;
      }
    });
    window.addEventListener("test", rt, rt), window.removeEventListener("test", rt, rt);
  } catch {
    sn = !1;
  }
var Re = sn ? { passive: !1 } : !1, Zu = function(e) {
  return e.tagName === "TEXTAREA";
}, oi = function(e, t) {
  if (!(e instanceof Element))
    return !1;
  var n = window.getComputedStyle(e);
  return (
    // not-not-scrollable
    n[t] !== "hidden" && // contains scroll inside self
    !(n.overflowY === n.overflowX && !Zu(e) && n[t] === "visible")
  );
}, Qu = function(e) {
  return oi(e, "overflowY");
}, Ju = function(e) {
  return oi(e, "overflowX");
}, vr = function(e, t) {
  var n = t.ownerDocument, r = t;
  do {
    typeof ShadowRoot < "u" && r instanceof ShadowRoot && (r = r.host);
    var o = ii(e, r);
    if (o) {
      var i = si(e, r), a = i[1], s = i[2];
      if (a > s)
        return !0;
    }
    r = r.parentNode;
  } while (r && r !== n.body);
  return !1;
}, ed = function(e) {
  var t = e.scrollTop, n = e.scrollHeight, r = e.clientHeight;
  return [
    t,
    n,
    r
  ];
}, td = function(e) {
  var t = e.scrollLeft, n = e.scrollWidth, r = e.clientWidth;
  return [
    t,
    n,
    r
  ];
}, ii = function(e, t) {
  return e === "v" ? Qu(t) : Ju(t);
}, si = function(e, t) {
  return e === "v" ? ed(t) : td(t);
}, nd = function(e, t) {
  return e === "h" && t === "rtl" ? -1 : 1;
}, rd = function(e, t, n, r, o) {
  var i = nd(e, window.getComputedStyle(t).direction), a = i * r, s = n.target, l = t.contains(s), u = !1, p = a > 0, d = 0, m = 0;
  do {
    if (!s)
      break;
    var h = si(e, s), b = h[0], g = h[1], v = h[2], y = g - v - i * b;
    (b || y) && ii(e, s) && (d += y, m += b);
    var w = s.parentNode;
    s = w && w.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? w.host : w;
  } while (
    // portaled content
    !l && s !== document.body || // self content
    l && (t.contains(s) || t === s)
  );
  return (p && Math.abs(d) < 1 || !p && Math.abs(m) < 1) && (u = !0), u;
}, ot = function(e) {
  return "changedTouches" in e ? [e.changedTouches[0].clientX, e.changedTouches[0].clientY] : [0, 0];
}, br = function(e) {
  return [e.deltaX, e.deltaY];
}, yr = function(e) {
  return e && "current" in e ? e.current : e;
}, od = function(e, t) {
  return e[0] === t[0] && e[1] === t[1];
}, id = function(e) {
  return `
  .block-interactivity-`.concat(e, ` {pointer-events: none;}
  .allow-interactivity-`).concat(e, ` {pointer-events: all;}
`);
}, sd = 0, Te = [];
function ad(e) {
  var t = c.useRef([]), n = c.useRef([0, 0]), r = c.useRef(), o = c.useState(sd++)[0], i = c.useState(ri)[0], a = c.useRef(e);
  c.useEffect(function() {
    a.current = e;
  }, [e]), c.useEffect(function() {
    if (e.inert) {
      document.body.classList.add("block-interactivity-".concat(o));
      var g = Pu([e.lockRef.current], (e.shards || []).map(yr), !0).filter(Boolean);
      return g.forEach(function(v) {
        return v.classList.add("allow-interactivity-".concat(o));
      }), function() {
        document.body.classList.remove("block-interactivity-".concat(o)), g.forEach(function(v) {
          return v.classList.remove("allow-interactivity-".concat(o));
        });
      };
    }
  }, [e.inert, e.lockRef.current, e.shards]);
  var s = c.useCallback(function(g, v) {
    if ("touches" in g && g.touches.length === 2 || g.type === "wheel" && g.ctrlKey)
      return !a.current.allowPinchZoom;
    var y = ot(g), w = n.current, C = "deltaX" in g ? g.deltaX : w[0] - y[0], x = "deltaY" in g ? g.deltaY : w[1] - y[1], E, N = g.target, R = Math.abs(C) > Math.abs(x) ? "h" : "v";
    if ("touches" in g && R === "h" && N.type === "range")
      return !1;
    var A = window.getSelection(), P = A && A.anchorNode, _ = P ? P === N || P.contains(N) : !1;
    if (_)
      return !1;
    var I = vr(R, N);
    if (!I)
      return !0;
    if (I ? E = R : (E = R === "v" ? "h" : "v", I = vr(R, N)), !I)
      return !1;
    if (!r.current && "changedTouches" in g && (C || x) && (r.current = E), !E)
      return !0;
    var k = r.current || E;
    return rd(k, v, g, k === "h" ? C : x);
  }, []), l = c.useCallback(function(g) {
    var v = g;
    if (!(!Te.length || Te[Te.length - 1] !== i)) {
      var y = "deltaY" in v ? br(v) : ot(v), w = t.current.filter(function(E) {
        return E.name === v.type && (E.target === v.target || v.target === E.shadowParent) && od(E.delta, y);
      })[0];
      if (w && w.should) {
        v.cancelable && v.preventDefault();
        return;
      }
      if (!w) {
        var C = (a.current.shards || []).map(yr).filter(Boolean).filter(function(E) {
          return E.contains(v.target);
        }), x = C.length > 0 ? s(v, C[0]) : !a.current.noIsolation;
        x && v.cancelable && v.preventDefault();
      }
    }
  }, []), u = c.useCallback(function(g, v, y, w) {
    var C = { name: g, delta: v, target: y, should: w, shadowParent: cd(y) };
    t.current.push(C), setTimeout(function() {
      t.current = t.current.filter(function(x) {
        return x !== C;
      });
    }, 1);
  }, []), p = c.useCallback(function(g) {
    n.current = ot(g), r.current = void 0;
  }, []), d = c.useCallback(function(g) {
    u(g.type, br(g), g.target, s(g, e.lockRef.current));
  }, []), m = c.useCallback(function(g) {
    u(g.type, ot(g), g.target, s(g, e.lockRef.current));
  }, []);
  c.useEffect(function() {
    return Te.push(i), e.setCallbacks({
      onScrollCapture: d,
      onWheelCapture: d,
      onTouchMoveCapture: m
    }), document.addEventListener("wheel", l, Re), document.addEventListener("touchmove", l, Re), document.addEventListener("touchstart", p, Re), function() {
      Te = Te.filter(function(g) {
        return g !== i;
      }), document.removeEventListener("wheel", l, Re), document.removeEventListener("touchmove", l, Re), document.removeEventListener("touchstart", p, Re);
    };
  }, []);
  var h = e.removeScrollBar, b = e.inert;
  return c.createElement(
    c.Fragment,
    null,
    b ? c.createElement(i, { styles: id(o) }) : null,
    h ? c.createElement(Xu, { noRelative: e.noRelative, gapMode: e.gapMode }) : null
  );
}
function cd(e) {
  for (var t = null; e !== null; )
    e instanceof ShadowRoot && (t = e.host, e = e.host), e = e.parentNode;
  return t;
}
const ld = Lu(ni, ad);
var ai = c.forwardRef(function(e, t) {
  return c.createElement(Tt, se({}, e, { ref: t, sideCar: ld }));
});
ai.classNames = Tt.classNames;
var ud = function(e) {
  if (typeof document > "u")
    return null;
  var t = Array.isArray(e) ? e[0] : e;
  return t.ownerDocument.body;
}, Pe = /* @__PURE__ */ new WeakMap(), it = /* @__PURE__ */ new WeakMap(), st = {}, qt = 0, ci = function(e) {
  return e && (e.host || ci(e.parentNode));
}, dd = function(e, t) {
  return t.map(function(n) {
    if (e.contains(n))
      return n;
    var r = ci(n);
    return r && e.contains(r) ? r : (console.error("aria-hidden", n, "in not contained inside", e, ". Doing nothing"), null);
  }).filter(function(n) {
    return !!n;
  });
}, fd = function(e, t, n, r) {
  var o = dd(t, Array.isArray(e) ? e : [e]);
  st[n] || (st[n] = /* @__PURE__ */ new WeakMap());
  var i = st[n], a = [], s = /* @__PURE__ */ new Set(), l = new Set(o), u = function(d) {
    !d || s.has(d) || (s.add(d), u(d.parentNode));
  };
  o.forEach(u);
  var p = function(d) {
    !d || l.has(d) || Array.prototype.forEach.call(d.children, function(m) {
      if (s.has(m))
        p(m);
      else
        try {
          var h = m.getAttribute(r), b = h !== null && h !== "false", g = (Pe.get(m) || 0) + 1, v = (i.get(m) || 0) + 1;
          Pe.set(m, g), i.set(m, v), a.push(m), g === 1 && b && it.set(m, !0), v === 1 && m.setAttribute(n, "true"), b || m.setAttribute(r, "true");
        } catch (y) {
          console.error("aria-hidden: cannot operate on ", m, y);
        }
    });
  };
  return p(t), s.clear(), qt++, function() {
    a.forEach(function(d) {
      var m = Pe.get(d) - 1, h = i.get(d) - 1;
      Pe.set(d, m), i.set(d, h), m || (it.has(d) || d.removeAttribute(r), it.delete(d)), h || d.removeAttribute(n);
    }), qt--, qt || (Pe = /* @__PURE__ */ new WeakMap(), Pe = /* @__PURE__ */ new WeakMap(), it = /* @__PURE__ */ new WeakMap(), st = {});
  };
}, pd = function(e, t, n) {
  n === void 0 && (n = "data-aria-hidden");
  var r = Array.from(Array.isArray(e) ? e : [e]), o = ud(e);
  return o ? (r.push.apply(r, Array.from(o.querySelectorAll("[aria-live], script"))), fd(r, o, n, "aria-hidden")) : function() {
    return null;
  };
}, Pt = "Dialog", [li] = Ol(Pt), [md, ie] = li(Pt), ui = (e) => {
  const {
    __scopeDialog: t,
    children: n,
    open: r,
    defaultOpen: o,
    onOpenChange: i,
    modal: a = !0
  } = e, s = c.useRef(null), l = c.useRef(null), [u, p] = Me({
    prop: r,
    defaultProp: o ?? !1,
    onChange: i,
    caller: Pt
  });
  return /* @__PURE__ */ f(
    md,
    {
      scope: t,
      triggerRef: s,
      contentRef: l,
      contentId: ke(),
      titleId: ke(),
      descriptionId: ke(),
      open: u,
      onOpenChange: p,
      onOpenToggle: c.useCallback(() => p((d) => !d), [p]),
      modal: a,
      children: n
    }
  );
};
ui.displayName = Pt;
var di = "DialogTrigger", fi = c.forwardRef(
  (e, t) => {
    const { __scopeDialog: n, ...r } = e, o = ie(di, n), i = U(t, o.triggerRef);
    return /* @__PURE__ */ f(
      Ze.button,
      {
        type: "button",
        "aria-haspopup": "dialog",
        "aria-expanded": o.open,
        "aria-controls": o.contentId,
        "data-state": kn(o.open),
        ...r,
        ref: i,
        onClick: F(e.onClick, o.onOpenToggle)
      }
    );
  }
);
fi.displayName = di;
var Pn = "DialogPortal", [gd, pi] = li(Pn, {
  forceMount: void 0
}), mi = (e) => {
  const { __scopeDialog: t, forceMount: n, children: r, container: o } = e, i = ie(Pn, t);
  return /* @__PURE__ */ f(gd, { scope: t, forceMount: n, children: c.Children.map(r, (a) => /* @__PURE__ */ f(we, { present: n || i.open, children: /* @__PURE__ */ f(Tn, { asChild: !0, container: o, children: a }) })) });
};
mi.displayName = Pn;
var ht = "DialogOverlay", gi = c.forwardRef(
  (e, t) => {
    const n = pi(ht, e.__scopeDialog), { forceMount: r = n.forceMount, ...o } = e, i = ie(ht, e.__scopeDialog);
    return i.modal ? /* @__PURE__ */ f(we, { present: r || i.open, children: /* @__PURE__ */ f(vd, { ...o, ref: t }) }) : null;
  }
);
gi.displayName = ht;
var hd = /* @__PURE__ */ Jo("DialogOverlay.RemoveScroll"), vd = c.forwardRef(
  (e, t) => {
    const { __scopeDialog: n, ...r } = e, o = ie(ht, n);
    return (
      // Make sure `Content` is scrollable even when it doesn't live inside `RemoveScroll`
      // ie. when `Overlay` and `Content` are siblings
      /* @__PURE__ */ f(ai, { as: hd, allowPinchZoom: !0, shards: [o.contentRef], children: /* @__PURE__ */ f(
        Ze.div,
        {
          "data-state": kn(o.open),
          ...r,
          ref: t,
          style: { pointerEvents: "auto", ...r.style }
        }
      ) })
    );
  }
), Ee = "DialogContent", hi = c.forwardRef(
  (e, t) => {
    const n = pi(Ee, e.__scopeDialog), { forceMount: r = n.forceMount, ...o } = e, i = ie(Ee, e.__scopeDialog);
    return /* @__PURE__ */ f(we, { present: r || i.open, children: i.modal ? /* @__PURE__ */ f(bd, { ...o, ref: t }) : /* @__PURE__ */ f(yd, { ...o, ref: t }) });
  }
);
hi.displayName = Ee;
var bd = c.forwardRef(
  (e, t) => {
    const n = ie(Ee, e.__scopeDialog), r = c.useRef(null), o = U(t, n.contentRef, r);
    return c.useEffect(() => {
      const i = r.current;
      if (i) return pd(i);
    }, []), /* @__PURE__ */ f(
      vi,
      {
        ...e,
        ref: o,
        trapFocus: n.open,
        disableOutsidePointerEvents: !0,
        onCloseAutoFocus: F(e.onCloseAutoFocus, (i) => {
          var a;
          i.preventDefault(), (a = n.triggerRef.current) == null || a.focus();
        }),
        onPointerDownOutside: F(e.onPointerDownOutside, (i) => {
          const a = i.detail.originalEvent, s = a.button === 0 && a.ctrlKey === !0;
          (a.button === 2 || s) && i.preventDefault();
        }),
        onFocusOutside: F(
          e.onFocusOutside,
          (i) => i.preventDefault()
        )
      }
    );
  }
), yd = c.forwardRef(
  (e, t) => {
    const n = ie(Ee, e.__scopeDialog), r = c.useRef(!1), o = c.useRef(!1);
    return /* @__PURE__ */ f(
      vi,
      {
        ...e,
        ref: t,
        trapFocus: !1,
        disableOutsidePointerEvents: !1,
        onCloseAutoFocus: (i) => {
          var a, s;
          (a = e.onCloseAutoFocus) == null || a.call(e, i), i.defaultPrevented || (r.current || (s = n.triggerRef.current) == null || s.focus(), i.preventDefault()), r.current = !1, o.current = !1;
        },
        onInteractOutside: (i) => {
          var l, u;
          (l = e.onInteractOutside) == null || l.call(e, i), i.defaultPrevented || (r.current = !0, i.detail.originalEvent.type === "pointerdown" && (o.current = !0));
          const a = i.target;
          ((u = n.triggerRef.current) == null ? void 0 : u.contains(a)) && i.preventDefault(), i.detail.originalEvent.type === "focusin" && o.current && i.preventDefault();
        }
      }
    );
  }
), vi = c.forwardRef(
  (e, t) => {
    const { __scopeDialog: n, trapFocus: r, onOpenAutoFocus: o, onCloseAutoFocus: i, ...a } = e, s = ie(Ee, n), l = c.useRef(null), u = U(t, l);
    return Tu(), /* @__PURE__ */ S(G, { children: [
      /* @__PURE__ */ f(
        Zo,
        {
          asChild: !0,
          loop: !0,
          trapped: r,
          onMountAutoFocus: o,
          onUnmountAutoFocus: i,
          children: /* @__PURE__ */ f(
            Rt,
            {
              role: "dialog",
              id: s.contentId,
              "aria-describedby": s.descriptionId,
              "aria-labelledby": s.titleId,
              "data-state": kn(s.open),
              ...a,
              ref: u,
              onDismiss: () => s.onOpenChange(!1)
            }
          )
        }
      ),
      /* @__PURE__ */ S(G, { children: [
        /* @__PURE__ */ f(xd, { titleId: s.titleId }),
        /* @__PURE__ */ f(Cd, { contentRef: l, descriptionId: s.descriptionId })
      ] })
    ] });
  }
), An = "DialogTitle", bi = c.forwardRef(
  (e, t) => {
    const { __scopeDialog: n, ...r } = e, o = ie(An, n);
    return /* @__PURE__ */ f(Ze.h2, { id: o.titleId, ...r, ref: t });
  }
);
bi.displayName = An;
var yi = "DialogDescription", xi = c.forwardRef(
  (e, t) => {
    const { __scopeDialog: n, ...r } = e, o = ie(yi, n);
    return /* @__PURE__ */ f(Ze.p, { id: o.descriptionId, ...r, ref: t });
  }
);
xi.displayName = yi;
var wi = "DialogClose", Ci = c.forwardRef(
  (e, t) => {
    const { __scopeDialog: n, ...r } = e, o = ie(wi, n);
    return /* @__PURE__ */ f(
      Ze.button,
      {
        type: "button",
        ...r,
        ref: t,
        onClick: F(e.onClick, () => o.onOpenChange(!1))
      }
    );
  }
);
Ci.displayName = wi;
function kn(e) {
  return e ? "open" : "closed";
}
var Ei = "DialogTitleWarning", [cg, Si] = _l(Ei, {
  contentName: Ee,
  titleName: An,
  docsSlug: "dialog"
}), xd = ({ titleId: e }) => {
  const t = Si(Ei), n = `\`${t.contentName}\` requires a \`${t.titleName}\` for the component to be accessible for screen reader users.

If you want to hide the \`${t.titleName}\`, you can wrap it with our VisuallyHidden component.

For more information, see https://radix-ui.com/primitives/docs/components/${t.docsSlug}`;
  return c.useEffect(() => {
    e && (document.getElementById(e) || console.error(n));
  }, [n, e]), null;
}, wd = "DialogDescriptionWarning", Cd = ({ contentRef: e, descriptionId: t }) => {
  const r = `Warning: Missing \`Description\` or \`aria-describedby={undefined}\` for {${Si(wd).contentName}}.`;
  return c.useEffect(() => {
    var i;
    const o = (i = e.current) == null ? void 0 : i.getAttribute("aria-describedby");
    t && o && (document.getElementById(t) || console.warn(r));
  }, [r, e, t]), null;
}, Ed = ui, Sd = fi, Nd = mi, Ni = gi, Ri = hi, Ti = bi, Pi = xi, Ai = Ci;
const Rd = Ed, lg = Sd, Td = Nd, ug = Ai, ki = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Ni,
  {
    ref: n,
    className: L(
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      e
    ),
    ...t
  }
));
ki.displayName = Ni.displayName;
const _i = c.forwardRef(({ className: e, children: t, ...n }, r) => /* @__PURE__ */ S(Td, { children: [
  /* @__PURE__ */ f(ki, {}),
  /* @__PURE__ */ S(
    Ri,
    {
      ref: r,
      className: L(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 glass-modal p-6 duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        e
      ),
      ...n,
      children: [
        t,
        /* @__PURE__ */ S(Ai, { className: "absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground", children: [
          /* @__PURE__ */ f(Et, { className: "h-4 w-4" }),
          /* @__PURE__ */ f("span", { className: "sr-only", children: "Close" })
        ] })
      ]
    }
  )
] }));
_i.displayName = Ri.displayName;
const Oi = ({
  className: e,
  ...t
}) => /* @__PURE__ */ f(
  "div",
  {
    className: L(
      "flex flex-col space-y-1.5 text-center sm:text-left",
      e
    ),
    ...t
  }
);
Oi.displayName = "DialogHeader";
const $i = ({
  className: e,
  ...t
}) => /* @__PURE__ */ f(
  "div",
  {
    className: L(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
      e
    ),
    ...t
  }
);
$i.displayName = "DialogFooter";
const Ii = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Ti,
  {
    ref: n,
    className: L(
      "text-lg font-semibold leading-none tracking-tight",
      e
    ),
    ...t
  }
));
Ii.displayName = Ti.displayName;
const Di = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Pi,
  {
    ref: n,
    className: L("text-sm text-muted-foreground", e),
    ...t
  }
));
Di.displayName = Pi.displayName;
const Mi = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  "textarea",
  {
    className: L(
      "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
      e
    ),
    ref: n,
    ...t
  }
));
Mi.displayName = "Textarea";
function Pd(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, Ad(o, ...t)];
}
function Ad(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
// @__NO_SIDE_EFFECTS__
function kd(e) {
  const t = /* @__PURE__ */ _d(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find($d);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function _d(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = Dd(o), s = Id(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Od = Symbol("radix.slottable");
function $d(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Od;
}
function Id(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Dd(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var Md = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Le = Md.reduce((e, t) => {
  const n = /* @__PURE__ */ kd(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {});
function Ld(e, t) {
  e && wt.flushSync(() => e.dispatchEvent(t));
}
// @__NO_SIDE_EFFECTS__
function Fd(e) {
  const t = /* @__PURE__ */ Vd(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(Bd);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function Vd(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = Hd(o), s = jd(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var Wd = Symbol("radix.slottable");
function Bd(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === Wd;
}
function jd(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Hd(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var zd = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Ud = zd.reduce((e, t) => {
  const n = /* @__PURE__ */ Fd(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), Gd = Object.freeze({
  // See: https://github.com/twbs/bootstrap/blob/main/scss/mixins/_visually-hidden.scss
  position: "absolute",
  border: 0,
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  whiteSpace: "nowrap",
  wordWrap: "normal"
}), Kd = "VisuallyHidden", At = c.forwardRef(
  (e, t) => /* @__PURE__ */ f(
    Ud.span,
    {
      ...e,
      ref: t,
      style: { ...Gd, ...e.style }
    }
  )
);
At.displayName = Kd;
var qd = At, _n = "ToastProvider", [On, Yd, Xd] = ho("Toast"), [Li] = Pd("Toast", [Xd]), [Zd, kt] = Li(_n), Fi = (e) => {
  const {
    __scopeToast: t,
    label: n = "Notification",
    duration: r = 5e3,
    swipeDirection: o = "right",
    swipeThreshold: i = 50,
    children: a
  } = e, [s, l] = c.useState(null), [u, p] = c.useState(0), d = c.useRef(!1), m = c.useRef(!1);
  return n.trim() || console.error(
    `Invalid prop \`label\` supplied to \`${_n}\`. Expected non-empty \`string\`.`
  ), /* @__PURE__ */ f(On.Provider, { scope: t, children: /* @__PURE__ */ f(
    Zd,
    {
      scope: t,
      label: n,
      duration: r,
      swipeDirection: o,
      swipeThreshold: i,
      toastCount: u,
      viewport: s,
      onViewportChange: l,
      onToastAdd: c.useCallback(() => p((h) => h + 1), []),
      onToastRemove: c.useCallback(() => p((h) => h - 1), []),
      isFocusedToastEscapeKeyDownRef: d,
      isClosePausedRef: m,
      children: a
    }
  ) });
};
Fi.displayName = _n;
var Vi = "ToastViewport", Qd = ["F8"], an = "toast.viewportPause", cn = "toast.viewportResume", Wi = c.forwardRef(
  (e, t) => {
    const {
      __scopeToast: n,
      hotkey: r = Qd,
      label: o = "Notifications ({hotkey})",
      ...i
    } = e, a = kt(Vi, n), s = Yd(n), l = c.useRef(null), u = c.useRef(null), p = c.useRef(null), d = c.useRef(null), m = U(t, d, a.onViewportChange), h = r.join("+").replace(/Key/g, "").replace(/Digit/g, ""), b = a.toastCount > 0;
    c.useEffect(() => {
      const v = (y) => {
        var C;
        r.length !== 0 && r.every((x) => y[x] || y.code === x) && ((C = d.current) == null || C.focus());
      };
      return document.addEventListener("keydown", v), () => document.removeEventListener("keydown", v);
    }, [r]), c.useEffect(() => {
      const v = l.current, y = d.current;
      if (b && v && y) {
        const w = () => {
          if (!a.isClosePausedRef.current) {
            const N = new CustomEvent(an);
            y.dispatchEvent(N), a.isClosePausedRef.current = !0;
          }
        }, C = () => {
          if (a.isClosePausedRef.current) {
            const N = new CustomEvent(cn);
            y.dispatchEvent(N), a.isClosePausedRef.current = !1;
          }
        }, x = (N) => {
          !v.contains(N.relatedTarget) && C();
        }, E = () => {
          v.contains(document.activeElement) || C();
        };
        return v.addEventListener("focusin", w), v.addEventListener("focusout", x), v.addEventListener("pointermove", w), v.addEventListener("pointerleave", E), window.addEventListener("blur", w), window.addEventListener("focus", C), () => {
          v.removeEventListener("focusin", w), v.removeEventListener("focusout", x), v.removeEventListener("pointermove", w), v.removeEventListener("pointerleave", E), window.removeEventListener("blur", w), window.removeEventListener("focus", C);
        };
      }
    }, [b, a.isClosePausedRef]);
    const g = c.useCallback(
      ({ tabbingDirection: v }) => {
        const w = s().map((C) => {
          const x = C.ref.current, E = [x, ...ff(x)];
          return v === "forwards" ? E : E.reverse();
        });
        return (v === "forwards" ? w.reverse() : w).flat();
      },
      [s]
    );
    return c.useEffect(() => {
      const v = d.current;
      if (v) {
        const y = (w) => {
          var E, N, R;
          const C = w.altKey || w.ctrlKey || w.metaKey;
          if (w.key === "Tab" && !C) {
            const A = document.activeElement, P = w.shiftKey;
            if (w.target === v && P) {
              (E = u.current) == null || E.focus();
              return;
            }
            const k = g({ tabbingDirection: P ? "backwards" : "forwards" }), V = k.findIndex((T) => T === A);
            Yt(k.slice(V + 1)) ? w.preventDefault() : P ? (N = u.current) == null || N.focus() : (R = p.current) == null || R.focus();
          }
        };
        return v.addEventListener("keydown", y), () => v.removeEventListener("keydown", y);
      }
    }, [s, g]), /* @__PURE__ */ S(
      Xl,
      {
        ref: l,
        role: "region",
        "aria-label": o.replace("{hotkey}", h),
        tabIndex: -1,
        style: { pointerEvents: b ? void 0 : "none" },
        children: [
          b && /* @__PURE__ */ f(
            ln,
            {
              ref: u,
              onFocusFromOutsideViewport: () => {
                const v = g({
                  tabbingDirection: "forwards"
                });
                Yt(v);
              }
            }
          ),
          /* @__PURE__ */ f(On.Slot, { scope: n, children: /* @__PURE__ */ f(Le.ol, { tabIndex: -1, ...i, ref: m }) }),
          b && /* @__PURE__ */ f(
            ln,
            {
              ref: p,
              onFocusFromOutsideViewport: () => {
                const v = g({
                  tabbingDirection: "backwards"
                });
                Yt(v);
              }
            }
          )
        ]
      }
    );
  }
);
Wi.displayName = Vi;
var Bi = "ToastFocusProxy", ln = c.forwardRef(
  (e, t) => {
    const { __scopeToast: n, onFocusFromOutsideViewport: r, ...o } = e, i = kt(Bi, n);
    return /* @__PURE__ */ f(
      At,
      {
        tabIndex: 0,
        ...o,
        ref: t,
        style: { position: "fixed" },
        onFocus: (a) => {
          var u;
          const s = a.relatedTarget;
          !((u = i.viewport) != null && u.contains(s)) && r();
        }
      }
    );
  }
);
ln.displayName = Bi;
var Qe = "Toast", Jd = "toast.swipeStart", ef = "toast.swipeMove", tf = "toast.swipeCancel", nf = "toast.swipeEnd", ji = c.forwardRef(
  (e, t) => {
    const { forceMount: n, open: r, defaultOpen: o, onOpenChange: i, ...a } = e, [s, l] = Me({
      prop: r,
      defaultProp: o ?? !0,
      onChange: i,
      caller: Qe
    });
    return /* @__PURE__ */ f(we, { present: n || s, children: /* @__PURE__ */ f(
      sf,
      {
        open: s,
        ...a,
        ref: t,
        onClose: () => l(!1),
        onPause: ne(e.onPause),
        onResume: ne(e.onResume),
        onSwipeStart: F(e.onSwipeStart, (u) => {
          u.currentTarget.setAttribute("data-swipe", "start");
        }),
        onSwipeMove: F(e.onSwipeMove, (u) => {
          const { x: p, y: d } = u.detail.delta;
          u.currentTarget.setAttribute("data-swipe", "move"), u.currentTarget.style.setProperty("--radix-toast-swipe-move-x", `${p}px`), u.currentTarget.style.setProperty("--radix-toast-swipe-move-y", `${d}px`);
        }),
        onSwipeCancel: F(e.onSwipeCancel, (u) => {
          u.currentTarget.setAttribute("data-swipe", "cancel"), u.currentTarget.style.removeProperty("--radix-toast-swipe-move-x"), u.currentTarget.style.removeProperty("--radix-toast-swipe-move-y"), u.currentTarget.style.removeProperty("--radix-toast-swipe-end-x"), u.currentTarget.style.removeProperty("--radix-toast-swipe-end-y");
        }),
        onSwipeEnd: F(e.onSwipeEnd, (u) => {
          const { x: p, y: d } = u.detail.delta;
          u.currentTarget.setAttribute("data-swipe", "end"), u.currentTarget.style.removeProperty("--radix-toast-swipe-move-x"), u.currentTarget.style.removeProperty("--radix-toast-swipe-move-y"), u.currentTarget.style.setProperty("--radix-toast-swipe-end-x", `${p}px`), u.currentTarget.style.setProperty("--radix-toast-swipe-end-y", `${d}px`), l(!1);
        })
      }
    ) });
  }
);
ji.displayName = Qe;
var [rf, of] = Li(Qe, {
  onClose() {
  }
}), sf = c.forwardRef(
  (e, t) => {
    const {
      __scopeToast: n,
      type: r = "foreground",
      duration: o,
      open: i,
      onClose: a,
      onEscapeKeyDown: s,
      onPause: l,
      onResume: u,
      onSwipeStart: p,
      onSwipeMove: d,
      onSwipeCancel: m,
      onSwipeEnd: h,
      ...b
    } = e, g = kt(Qe, n), [v, y] = c.useState(null), w = U(t, (T) => y(T)), C = c.useRef(null), x = c.useRef(null), E = o || g.duration, N = c.useRef(0), R = c.useRef(E), A = c.useRef(0), { onToastAdd: P, onToastRemove: _ } = g, I = ne(() => {
      var M;
      (v == null ? void 0 : v.contains(document.activeElement)) && ((M = g.viewport) == null || M.focus()), a();
    }), k = c.useCallback(
      (T) => {
        !T || T === 1 / 0 || (window.clearTimeout(A.current), N.current = (/* @__PURE__ */ new Date()).getTime(), A.current = window.setTimeout(I, T));
      },
      [I]
    );
    c.useEffect(() => {
      const T = g.viewport;
      if (T) {
        const M = () => {
          k(R.current), u == null || u();
        }, O = () => {
          const W = (/* @__PURE__ */ new Date()).getTime() - N.current;
          R.current = R.current - W, window.clearTimeout(A.current), l == null || l();
        };
        return T.addEventListener(an, O), T.addEventListener(cn, M), () => {
          T.removeEventListener(an, O), T.removeEventListener(cn, M);
        };
      }
    }, [g.viewport, E, l, u, k]), c.useEffect(() => {
      i && !g.isClosePausedRef.current && k(E);
    }, [i, E, g.isClosePausedRef, k]), c.useEffect(() => (P(), () => _()), [P, _]);
    const V = c.useMemo(() => v ? Yi(v) : null, [v]);
    return g.viewport ? /* @__PURE__ */ S(G, { children: [
      V && /* @__PURE__ */ f(
        af,
        {
          __scopeToast: n,
          role: "status",
          "aria-live": r === "foreground" ? "assertive" : "polite",
          children: V
        }
      ),
      /* @__PURE__ */ f(rf, { scope: n, onClose: I, children: wt.createPortal(
        /* @__PURE__ */ f(On.ItemSlot, { scope: n, children: /* @__PURE__ */ f(
          Yl,
          {
            asChild: !0,
            onEscapeKeyDown: F(s, () => {
              g.isFocusedToastEscapeKeyDownRef.current || I(), g.isFocusedToastEscapeKeyDownRef.current = !1;
            }),
            children: /* @__PURE__ */ f(
              Le.li,
              {
                tabIndex: 0,
                "data-state": i ? "open" : "closed",
                "data-swipe-direction": g.swipeDirection,
                ...b,
                ref: w,
                style: { userSelect: "none", touchAction: "none", ...e.style },
                onKeyDown: F(e.onKeyDown, (T) => {
                  T.key === "Escape" && (s == null || s(T.nativeEvent), T.nativeEvent.defaultPrevented || (g.isFocusedToastEscapeKeyDownRef.current = !0, I()));
                }),
                onPointerDown: F(e.onPointerDown, (T) => {
                  T.button === 0 && (C.current = { x: T.clientX, y: T.clientY });
                }),
                onPointerMove: F(e.onPointerMove, (T) => {
                  if (!C.current) return;
                  const M = T.clientX - C.current.x, O = T.clientY - C.current.y, W = !!x.current, $ = ["left", "right"].includes(g.swipeDirection), B = ["left", "up"].includes(g.swipeDirection) ? Math.min : Math.max, q = $ ? B(0, M) : 0, K = $ ? 0 : B(0, O), We = T.pointerType === "touch" ? 10 : 2, Ne = { x: q, y: K }, et = { originalEvent: T, delta: Ne };
                  W ? (x.current = Ne, at(ef, d, et, {
                    discrete: !1
                  })) : xr(Ne, g.swipeDirection, We) ? (x.current = Ne, at(Jd, p, et, {
                    discrete: !1
                  }), T.target.setPointerCapture(T.pointerId)) : (Math.abs(M) > We || Math.abs(O) > We) && (C.current = null);
                }),
                onPointerUp: F(e.onPointerUp, (T) => {
                  const M = x.current, O = T.target;
                  if (O.hasPointerCapture(T.pointerId) && O.releasePointerCapture(T.pointerId), x.current = null, C.current = null, M) {
                    const W = T.currentTarget, $ = { originalEvent: T, delta: M };
                    xr(M, g.swipeDirection, g.swipeThreshold) ? at(nf, h, $, {
                      discrete: !0
                    }) : at(
                      tf,
                      m,
                      $,
                      {
                        discrete: !0
                      }
                    ), W.addEventListener("click", (B) => B.preventDefault(), {
                      once: !0
                    });
                  }
                })
              }
            )
          }
        ) }),
        g.viewport
      ) })
    ] }) : null;
  }
), af = (e) => {
  const { __scopeToast: t, children: n, ...r } = e, o = kt(Qe, t), [i, a] = c.useState(!1), [s, l] = c.useState(!1);
  return uf(() => a(!0)), c.useEffect(() => {
    const u = window.setTimeout(() => l(!0), 1e3);
    return () => window.clearTimeout(u);
  }, []), s ? null : /* @__PURE__ */ f(Tn, { asChild: !0, children: /* @__PURE__ */ f(At, { ...r, children: i && /* @__PURE__ */ S(G, { children: [
    o.label,
    " ",
    n
  ] }) }) });
}, cf = "ToastTitle", Hi = c.forwardRef(
  (e, t) => {
    const { __scopeToast: n, ...r } = e;
    return /* @__PURE__ */ f(Le.div, { ...r, ref: t });
  }
);
Hi.displayName = cf;
var lf = "ToastDescription", zi = c.forwardRef(
  (e, t) => {
    const { __scopeToast: n, ...r } = e;
    return /* @__PURE__ */ f(Le.div, { ...r, ref: t });
  }
);
zi.displayName = lf;
var Ui = "ToastAction", Gi = c.forwardRef(
  (e, t) => {
    const { altText: n, ...r } = e;
    return n.trim() ? /* @__PURE__ */ f(qi, { altText: n, asChild: !0, children: /* @__PURE__ */ f($n, { ...r, ref: t }) }) : (console.error(
      `Invalid prop \`altText\` supplied to \`${Ui}\`. Expected non-empty \`string\`.`
    ), null);
  }
);
Gi.displayName = Ui;
var Ki = "ToastClose", $n = c.forwardRef(
  (e, t) => {
    const { __scopeToast: n, ...r } = e, o = of(Ki, n);
    return /* @__PURE__ */ f(qi, { asChild: !0, children: /* @__PURE__ */ f(
      Le.button,
      {
        type: "button",
        ...r,
        ref: t,
        onClick: F(e.onClick, o.onClose)
      }
    ) });
  }
);
$n.displayName = Ki;
var qi = c.forwardRef((e, t) => {
  const { __scopeToast: n, altText: r, ...o } = e;
  return /* @__PURE__ */ f(
    Le.div,
    {
      "data-radix-toast-announce-exclude": "",
      "data-radix-toast-announce-alt": r || void 0,
      ...o,
      ref: t
    }
  );
});
function Yi(e) {
  const t = [];
  return Array.from(e.childNodes).forEach((r) => {
    if (r.nodeType === r.TEXT_NODE && r.textContent && t.push(r.textContent), df(r)) {
      const o = r.ariaHidden || r.hidden || r.style.display === "none", i = r.dataset.radixToastAnnounceExclude === "";
      if (!o)
        if (i) {
          const a = r.dataset.radixToastAnnounceAlt;
          a && t.push(a);
        } else
          t.push(...Yi(r));
    }
  }), t;
}
function at(e, t, n, { discrete: r }) {
  const o = n.originalEvent.currentTarget, i = new CustomEvent(e, { bubbles: !0, cancelable: !0, detail: n });
  t && o.addEventListener(e, t, { once: !0 }), r ? Ld(o, i) : o.dispatchEvent(i);
}
var xr = (e, t, n = 0) => {
  const r = Math.abs(e.x), o = Math.abs(e.y), i = r > o;
  return t === "left" || t === "right" ? i && r > n : !i && o > n;
};
function uf(e = () => {
}) {
  const t = ne(e);
  te(() => {
    let n = 0, r = 0;
    return n = window.requestAnimationFrame(() => r = window.requestAnimationFrame(t)), () => {
      window.cancelAnimationFrame(n), window.cancelAnimationFrame(r);
    };
  }, [t]);
}
function df(e) {
  return e.nodeType === e.ELEMENT_NODE;
}
function ff(e) {
  const t = [], n = document.createTreeWalker(e, NodeFilter.SHOW_ELEMENT, {
    acceptNode: (r) => {
      const o = r.tagName === "INPUT" && r.type === "hidden";
      return r.disabled || r.hidden || o ? NodeFilter.FILTER_SKIP : r.tabIndex >= 0 ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
    }
  });
  for (; n.nextNode(); ) t.push(n.currentNode);
  return t;
}
function Yt(e) {
  const t = document.activeElement;
  return e.some((n) => n === t ? !0 : (n.focus(), document.activeElement !== t));
}
var pf = Fi, Xi = Wi, Zi = ji, Qi = Hi, Ji = zi, es = Gi, ts = $n;
const mf = pf, ns = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Xi,
  {
    ref: n,
    className: L(
      "fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]",
      e
    ),
    ...t
  }
));
ns.displayName = Xi.displayName;
const gf = qe(
  "group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border p-6 pr-8 shadow-lg transition-all data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full",
  {
    variants: {
      variant: {
        default: "border bg-background text-foreground",
        destructive: "destructive group border-destructive bg-destructive text-destructive-foreground"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
), rs = c.forwardRef(({ className: e, variant: t, ...n }, r) => /* @__PURE__ */ f(
  Zi,
  {
    ref: r,
    className: L(gf({ variant: t }), e),
    ...n
  }
));
rs.displayName = Zi.displayName;
const hf = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  es,
  {
    ref: n,
    className: L(
      "inline-flex h-8 shrink-0 items-center justify-center rounded-md border bg-transparent px-3 text-sm font-medium ring-offset-background transition-colors hover:bg-secondary focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 group-[.destructive]:border-muted/40 group-[.destructive]:hover:border-destructive/30 group-[.destructive]:hover:bg-destructive group-[.destructive]:hover:text-destructive-foreground group-[.destructive]:focus:ring-destructive",
      e
    ),
    ...t
  }
));
hf.displayName = es.displayName;
const os = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  ts,
  {
    ref: n,
    className: L(
      "absolute right-2 top-2 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity hover:text-foreground focus:opacity-100 focus:outline-none focus:ring-2 group-hover:opacity-100 group-[.destructive]:text-red-300 group-[.destructive]:hover:text-red-50 group-[.destructive]:focus:ring-red-400 group-[.destructive]:focus:ring-offset-red-600",
      e
    ),
    "toast-close": "",
    ...t,
    children: /* @__PURE__ */ f(Et, { className: "h-4 w-4" })
  }
));
os.displayName = ts.displayName;
const is = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Qi,
  {
    ref: n,
    className: L("text-sm font-semibold", e),
    ...t
  }
));
is.displayName = Qi.displayName;
const ss = c.forwardRef(({ className: e, ...t }, n) => /* @__PURE__ */ f(
  Ji,
  {
    ref: n,
    className: L("text-sm opacity-90", e),
    ...t
  }
));
ss.displayName = Ji.displayName;
const vf = 1, bf = 1e6;
let Xt = 0;
function yf() {
  return Xt = (Xt + 1) % Number.MAX_SAFE_INTEGER, Xt.toString();
}
const Zt = /* @__PURE__ */ new Map(), wr = (e) => {
  if (Zt.has(e))
    return;
  const t = setTimeout(() => {
    Zt.delete(e), ze({
      type: "REMOVE_TOAST",
      toastId: e
    });
  }, bf);
  Zt.set(e, t);
}, xf = (e, t) => {
  switch (t.type) {
    case "ADD_TOAST":
      return {
        ...e,
        toasts: [t.toast, ...e.toasts].slice(0, vf)
      };
    case "UPDATE_TOAST":
      return {
        ...e,
        toasts: e.toasts.map(
          (n) => n.id === t.toast.id ? { ...n, ...t.toast } : n
        )
      };
    case "DISMISS_TOAST": {
      const { toastId: n } = t;
      return n ? wr(n) : e.toasts.forEach((r) => {
        wr(r.id);
      }), {
        ...e,
        toasts: e.toasts.map(
          (r) => r.id === n || n === void 0 ? {
            ...r,
            open: !1
          } : r
        )
      };
    }
    case "REMOVE_TOAST":
      return t.toastId === void 0 ? {
        ...e,
        toasts: []
      } : {
        ...e,
        toasts: e.toasts.filter((n) => n.id !== t.toastId)
      };
  }
}, ft = [];
let pt = { toasts: [] };
function ze(e) {
  pt = xf(pt, e), ft.forEach((t) => {
    t(pt);
  });
}
function wf({ ...e }) {
  const t = yf(), n = (o) => ze({
    type: "UPDATE_TOAST",
    toast: { ...o, id: t }
  }), r = () => ze({ type: "DISMISS_TOAST", toastId: t });
  return ze({
    type: "ADD_TOAST",
    toast: {
      ...e,
      id: t,
      open: !0,
      onOpenChange: (o) => {
        o || r();
      }
    }
  }), {
    id: t,
    dismiss: r,
    update: n
  };
}
function Cf() {
  const [e, t] = c.useState(pt);
  return c.useEffect(() => (ft.push(t), () => {
    const n = ft.indexOf(t);
    n > -1 && ft.splice(n, 1);
  }), [e]), {
    ...e,
    toast: wf,
    dismiss: (n) => ze({ type: "DISMISS_TOAST", toastId: n })
  };
}
function dg() {
  const { toasts: e } = Cf();
  return /* @__PURE__ */ S(mf, { children: [
    e.map(function({ id: t, title: n, description: r, action: o, ...i }) {
      return /* @__PURE__ */ S(rs, { ...i, children: [
        /* @__PURE__ */ S("div", { className: "grid gap-1", children: [
          n && /* @__PURE__ */ f(is, { children: n }),
          r && /* @__PURE__ */ f(ss, { children: r })
        ] }),
        o,
        /* @__PURE__ */ f(os, {})
      ] }, t);
    }),
    /* @__PURE__ */ f(ns, {})
  ] });
}
const Ef = {
  text: /* @__PURE__ */ S(G, { children: [
    /* @__PURE__ */ f("div", { className: "skeleton-loader h-4 w-full rounded-md", "aria-hidden": "true" }),
    /* @__PURE__ */ f("div", { className: "skeleton-loader h-4 w-3/4 rounded-md", "aria-hidden": "true" }),
    /* @__PURE__ */ f("div", { className: "skeleton-loader h-4 w-5/6 rounded-md", "aria-hidden": "true" })
  ] }),
  avatar: /* @__PURE__ */ S(G, { children: [
    /* @__PURE__ */ f("div", { className: "skeleton-loader h-12 w-12 rounded-full", "aria-hidden": "true" }),
    /* @__PURE__ */ f("div", { className: "skeleton-loader h-4 w-32 rounded-md", "aria-hidden": "true" })
  ] }),
  card: /* @__PURE__ */ f("div", { className: "skeleton-loader h-32 w-full rounded-md", "aria-hidden": "true" }),
  activityList: /* @__PURE__ */ f("div", { className: "space-y-2", children: [1, 2].map((e) => /* @__PURE__ */ S("div", { className: "p-3 rounded-md skeleton-loader", children: [
    /* @__PURE__ */ f("div", { className: "h-4 w-3/4 rounded-md bg-current opacity-60 mb-2", "aria-hidden": "true" }),
    /* @__PURE__ */ f("div", { className: "h-3 w-1/2 rounded-md bg-current opacity-40", "aria-hidden": "true" })
  ] }, e)) })
};
function In({ status: e, message: t, onRetry: n, skeletonVariant: r = "text" }) {
  const [o, i] = z(e), [a, s] = z(!1);
  return ee(() => {
    if (e !== o && o === "loading") {
      performance.now(), s(!0);
      const u = setTimeout(() => {
        i(e), s(!1);
      }, e === "success" ? 250 : e === "error" ? 200 : 300);
      return () => clearTimeout(u);
    } else i(e);
  }, [e, o]), o === "success" && !a ? null : /* @__PURE__ */ S("div", { className: "flex flex-col items-center justify-center gap-3 py-8", "aria-live": "polite", role: "status", "aria-busy": o === "loading", children: [
    (o === "loading" || a) && /* @__PURE__ */ f("div", { className: `w-full space-y-3 ${a ? e === "success" ? "status-loading-to-success" : e === "error" ? "status-loading-to-error" : "status-loading-to-empty" : ""}`, children: Ef[r] }),
    o === "error" && !a && /* @__PURE__ */ S("div", { className: "status-error-enter flex flex-col items-center gap-3 text-center", children: [
      /* @__PURE__ */ f(ao, { className: "h-12 w-12 text-[var(--status-error-icon)]", "data-testid": "icon-error" }),
      /* @__PURE__ */ f("p", { className: "text-sm text-[var(--status-error-text)]", "data-testid": "text-error-message", children: t || "Something went wrong. Please try again." }),
      /* @__PURE__ */ f(J, { onClick: n, variant: "default", "aria-label": "Retry loading data", "data-testid": "button-retry", children: "Retry" })
    ] }),
    o === "empty" && /* @__PURE__ */ S("div", { className: "status-empty-enter flex flex-col items-center gap-3 text-center", children: [
      /* @__PURE__ */ f("svg", { className: "empty-icon h-16 w-16 text-[var(--status-empty-icon)]", viewBox: "0 0 306.028 306.028", "aria-hidden": "true", "data-testid": "icon-empty", children: /* @__PURE__ */ f("path", { fill: "currentColor", d: "M285.498,113.47H81.32V15h179.688v76.277c0,4.142,3.357,7.5,7.5,7.5s7.5-3.358,7.5-7.5V7.5c0-4.142-3.357-7.5-7.5-7.5H73.82c-4.143,0-7.5,3.358-7.5,7.5v113.47c0,0.438,0.045,0.864,0.117,1.281v149.841c0,10.441-8.494,18.936-18.936,18.936h-0.534c-10.441,0-18.937-8.495-18.937-18.936V91.963h18.937c4.143,0,7.5-3.358,7.5-7.5s-3.357-7.5-7.5-7.5H20.531c-4.143,0-7.5,3.358-7.5,7.5v187.629c0,18.712,15.224,33.936,33.937,33.936h0.534h201.197c24.427,0,44.299-19.873,44.299-44.299V120.97C292.998,116.828,289.64,113.47,285.498,113.47z M277.998,261.729c0,16.155-13.144,29.299-29.299,29.299H75.649c3.653-5.412,5.788-11.929,5.788-18.936V128.47h196.561V261.729z M98.011,41.633h49.663c4.143,0,7.5-3.358,7.5-7.5s-3.357-7.5-7.5-7.5H98.011c-4.143,0-7.5,3.358-7.5,7.5S93.869,41.633,98.011,41.633z M192.257,55.205H98.011c-4.143,0-7.5,3.358-7.5,7.5s3.357,7.5,7.5,7.5h94.246c4.143,0,7.5-3.358,7.5-7.5S196.4,55.205,192.257,55.205z M192.257,83.777H98.011c-4.143,0-7.5,3.358-7.5,7.5s3.357,7.5,7.5,7.5h94.246c4.143,0,7.5-3.358,7.5-7.5S196.4,83.777,192.257,83.777z M220.174,55.205c-4.143,0-7.5,3.358-7.5,7.5s3.357,7.5,7.5,7.5h20.417c4.143,0,7.5-3.358,7.5-7.5s-3.357-7.5-7.5-7.5H220.174z" }) }),
      /* @__PURE__ */ f("p", { className: "text-base text-[var(--status-error-text)]", "data-testid": "text-empty-message", children: t || "No data available" })
    ] })
  ] });
}
const Sf = {
  loading: {
    status: "loading",
    data: [],
    onRetry: () => {
    }
  },
  empty: {
    status: "empty",
    data: [],
    onRetry: () => {
    }
  },
  error: {
    status: "error",
    data: [],
    onRetry: () => {
      console.log("[fixture] ActivitySection retry");
    }
  },
  populated: {
    status: "success",
    data: [
      { id: 1, action: "Invoice #4821 reconciled with Stripe", time: "2026-02-10T14:30:00Z" },
      { id: 2, action: "Platform sync completed (Shopify)", time: "2026-02-10T13:15:00Z" },
      { id: 3, action: "Variance flagged on PayPal channel", time: "2026-02-10T11:02:00Z" }
    ],
    onRetry: () => {
    }
  }
}, Nf = {
  loading: {
    status: "loading",
    overallConfidence: 0,
    verifiedTransactionPercentage: 0,
    lastUpdated: "",
    trend: "stable",
    onRetry: () => {
    }
  },
  empty: {
    status: "empty",
    overallConfidence: 0,
    verifiedTransactionPercentage: 0,
    lastUpdated: "",
    trend: "stable",
    onRetry: () => {
    }
  },
  error: {
    status: "error",
    overallConfidence: 0,
    verifiedTransactionPercentage: 0,
    lastUpdated: "",
    trend: "stable",
    onRetry: () => {
      console.log("[fixture] DataConfidenceBar retry");
    }
  },
  populated: {
    status: "success",
    overallConfidence: 87,
    verifiedTransactionPercentage: 45,
    lastUpdated: "2 minutes ago",
    trend: "increasing",
    onRetry: () => {
    }
  }
}, Rf = {
  loading: {
    status: "loading",
    username: "",
    email: "",
    onRetry: () => {
    }
  },
  empty: {
    status: "empty",
    username: "",
    email: "",
    onRetry: () => {
    }
  },
  error: {
    status: "error",
    username: "",
    email: "",
    onRetry: () => {
      console.log("[fixture] UserInfoCard retry");
    }
  },
  populated: {
    status: "success",
    username: "alice.chen",
    email: "alice@skeldir.io",
    lastLogin: "2026-02-10T09:30:00Z",
    onRetry: () => {
    }
  }
}, fg = {
  ActivitySection: Sf,
  DataConfidenceBar: Nf,
  UserInfoCard: Rf
}, pg = ["loading", "empty", "error", "populated"];
function mg({ status: e, data: t, onRetry: n }) {
  return /* @__PURE__ */ S(
    vn,
    {
      className: "shadow-xl bg-brand-alice/60 border-brand-jordy/30",
      children: [
        /* @__PURE__ */ S(bn, { children: [
          /* @__PURE__ */ f(yn, { className: "text-brand-cool-black", children: "Recent Activity" }),
          /* @__PURE__ */ f(xn, { className: "text-brand-cool-black/70", children: "Your recent account activity" })
        ] }),
        /* @__PURE__ */ f(wn, { children: e === "success" && t.length > 0 ? /* @__PURE__ */ f("div", { className: "space-y-2", "data-testid": "list-activity", children: t.map((r) => /* @__PURE__ */ S("div", { className: "p-3 rounded-md bg-brand-alice/50", children: [
          /* @__PURE__ */ f("p", { className: "font-medium text-brand-cool-black", children: r.action }),
          /* @__PURE__ */ f("p", { className: "text-sm text-brand-cool-black/70", children: new Date(r.time).toLocaleString() })
        ] }, r.id)) }) : /* @__PURE__ */ f(
          In,
          {
            ...e === "error" ? {
              status: "error",
              message: "Failed to load activity",
              onRetry: n,
              skeletonVariant: "activityList"
            } : e === "empty" ? {
              status: "empty",
              message: "No recent activity found",
              skeletonVariant: "activityList"
            } : {
              status: "loading",
              skeletonVariant: "activityList"
            }
          }
        ) })
      ]
    }
  );
}
function gg({ status: e, username: t, email: n, lastLogin: r, onRetry: o }) {
  return /* @__PURE__ */ S(
    vn,
    {
      className: "shadow-xl bg-brand-alice/60 border-brand-jordy/30",
      "data-testid": "card-user-info",
      "data-status": e,
      children: [
        /* @__PURE__ */ S(bn, { children: [
          /* @__PURE__ */ S(yn, { className: "flex items-center space-x-2 text-brand-cool-black", children: [
            /* @__PURE__ */ f(wc, { className: "w-5 h-5" }),
            /* @__PURE__ */ f("span", { children: "Profile Information" })
          ] }),
          /* @__PURE__ */ f(xn, { className: "text-brand-cool-black/70", children: "Your account details and recent activity" })
        ] }),
        /* @__PURE__ */ f(wn, { className: "space-y-4", children: e === "success" ? /* @__PURE__ */ S("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4", children: [
          /* @__PURE__ */ S("div", { children: [
            /* @__PURE__ */ f("label", { className: "text-sm font-medium text-brand-cool-black/80", children: "Username" }),
            /* @__PURE__ */ f("p", { className: "text-lg font-medium text-brand-cool-black", "data-testid": "text-username", children: t })
          ] }),
          /* @__PURE__ */ S("div", { children: [
            /* @__PURE__ */ f("label", { className: "text-sm font-medium text-brand-cool-black/80", children: "Email" }),
            /* @__PURE__ */ f("p", { className: "text-lg font-medium text-brand-cool-black", "data-testid": "text-email", children: n })
          ] }),
          r && /* @__PURE__ */ S("div", { className: "md:col-span-2", children: [
            /* @__PURE__ */ f("label", { className: "text-sm font-medium text-brand-cool-black/80", children: "Last Login" }),
            /* @__PURE__ */ f("p", { className: "text-lg font-medium text-brand-cool-black", "data-testid": "text-last-login", children: new Date(r).toLocaleString() })
          ] })
        ] }) : /* @__PURE__ */ f(
          In,
          {
            ...e === "error" ? {
              status: "error",
              message: "Failed to load profile",
              onRetry: o,
              skeletonVariant: "card"
            } : e === "empty" ? {
              status: "empty",
              message: "No profile data available",
              skeletonVariant: "card"
            } : {
              status: "loading",
              skeletonVariant: "card"
            }
          }
        ) })
      ]
    }
  );
}
const Cr = ({
  size: e = 24,
  className: t = "",
  confidence: n,
  "aria-label": r
}) => {
  const i = {
    high: "#10B981",
    medium: "#F59E0B",
    low: "#EF4444"
  }[n];
  return /* @__PURE__ */ S(
    "svg",
    {
      width: e,
      height: e,
      viewBox: "0 0 24 24",
      fill: "none",
      xmlns: "http://www.w3.org/2000/svg",
      className: t,
      role: r ? "img" : "presentation",
      "aria-label": r,
      children: [
        /* @__PURE__ */ f(
          "path",
          {
            d: "M12 2.5L4 6v6c0 5.52 3.82 10.69 8 12 4.18-1.31 8-6.48 8-12V6l-8-3.5z",
            stroke: i,
            strokeWidth: "1.5",
            strokeLinecap: "round",
            strokeLinejoin: "round",
            fill: "none"
          }
        ),
        /* @__PURE__ */ f(
          "circle",
          {
            cx: "12",
            cy: "11",
            r: "4",
            stroke: i,
            strokeWidth: "1",
            opacity: "0.3",
            fill: "none"
          }
        ),
        /* @__PURE__ */ f(
          "circle",
          {
            cx: "12",
            cy: "11",
            r: "6.5",
            stroke: i,
            strokeWidth: "0.8",
            opacity: "0.2",
            fill: "none"
          }
        ),
        n === "high" && /* @__PURE__ */ f(
          "path",
          {
            d: "M9 11.5l2 2 4-4",
            stroke: i,
            strokeWidth: "2",
            strokeLinecap: "round",
            strokeLinejoin: "round"
          }
        ),
        n === "medium" && /* @__PURE__ */ f(
          "path",
          {
            d: "M12 8v4m0 3h.01",
            stroke: i,
            strokeWidth: "2",
            strokeLinecap: "round",
            strokeLinejoin: "round"
          }
        ),
        n === "low" && /* @__PURE__ */ f(
          "path",
          {
            d: "M10 10l4 4m0-4l-4 4",
            stroke: i,
            strokeWidth: "2",
            strokeLinecap: "round",
            strokeLinejoin: "round"
          }
        )
      ]
    }
  );
}, Tf = ({
  size: e = 24,
  className: t = "",
  direction: n,
  "aria-label": r
}) => {
  const o = {
    up: "#10B981",
    down: "#EF4444",
    stable: "#6B7280"
  };
  return /* @__PURE__ */ S(
    "svg",
    {
      width: e,
      height: e,
      viewBox: "0 0 24 24",
      fill: "none",
      xmlns: "http://www.w3.org/2000/svg",
      className: t,
      role: r ? "img" : "presentation",
      "aria-label": r,
      children: [
        n === "up" && /* @__PURE__ */ S(G, { children: [
          /* @__PURE__ */ f(
            "path",
            {
              d: "M3 17l6-6 4 4 8-8",
              stroke: o.up,
              strokeWidth: "2",
              strokeLinecap: "round",
              strokeLinejoin: "round"
            }
          ),
          /* @__PURE__ */ f(
            "path",
            {
              d: "M17 7h4v4",
              stroke: o.up,
              strokeWidth: "2",
              strokeLinecap: "round",
              strokeLinejoin: "round"
            }
          )
        ] }),
        n === "down" && /* @__PURE__ */ S(G, { children: [
          /* @__PURE__ */ f(
            "path",
            {
              d: "M3 7l6 6 4-4 8 8",
              stroke: o.down,
              strokeWidth: "2",
              strokeLinecap: "round",
              strokeLinejoin: "round"
            }
          ),
          /* @__PURE__ */ f(
            "path",
            {
              d: "M17 17h4v-4",
              stroke: o.down,
              strokeWidth: "2",
              strokeLinecap: "round",
              strokeLinejoin: "round"
            }
          )
        ] }),
        n === "stable" && /* @__PURE__ */ f(
          "path",
          {
            d: "M5 12h14",
            stroke: o.stable,
            strokeWidth: "2",
            strokeLinecap: "round"
          }
        )
      ]
    }
  );
};
function Pf(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, Af(o, ...t)];
}
function Af(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
const kf = ["top", "right", "bottom", "left"], ye = Math.min, Z = Math.max, vt = Math.round, ct = Math.floor, ce = (e) => ({
  x: e,
  y: e
}), _f = {
  left: "right",
  right: "left",
  bottom: "top",
  top: "bottom"
}, Of = {
  start: "end",
  end: "start"
};
function un(e, t, n) {
  return Z(e, ye(t, n));
}
function pe(e, t) {
  return typeof e == "function" ? e(t) : e;
}
function me(e) {
  return e.split("-")[0];
}
function Fe(e) {
  return e.split("-")[1];
}
function Dn(e) {
  return e === "x" ? "y" : "x";
}
function Mn(e) {
  return e === "y" ? "height" : "width";
}
const $f = /* @__PURE__ */ new Set(["top", "bottom"]);
function ae(e) {
  return $f.has(me(e)) ? "y" : "x";
}
function Ln(e) {
  return Dn(ae(e));
}
function If(e, t, n) {
  n === void 0 && (n = !1);
  const r = Fe(e), o = Ln(e), i = Mn(o);
  let a = o === "x" ? r === (n ? "end" : "start") ? "right" : "left" : r === "start" ? "bottom" : "top";
  return t.reference[i] > t.floating[i] && (a = bt(a)), [a, bt(a)];
}
function Df(e) {
  const t = bt(e);
  return [dn(e), t, dn(t)];
}
function dn(e) {
  return e.replace(/start|end/g, (t) => Of[t]);
}
const Er = ["left", "right"], Sr = ["right", "left"], Mf = ["top", "bottom"], Lf = ["bottom", "top"];
function Ff(e, t, n) {
  switch (e) {
    case "top":
    case "bottom":
      return n ? t ? Sr : Er : t ? Er : Sr;
    case "left":
    case "right":
      return t ? Mf : Lf;
    default:
      return [];
  }
}
function Vf(e, t, n, r) {
  const o = Fe(e);
  let i = Ff(me(e), n === "start", r);
  return o && (i = i.map((a) => a + "-" + o), t && (i = i.concat(i.map(dn)))), i;
}
function bt(e) {
  return e.replace(/left|right|bottom|top/g, (t) => _f[t]);
}
function Wf(e) {
  return {
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    ...e
  };
}
function as(e) {
  return typeof e != "number" ? Wf(e) : {
    top: e,
    right: e,
    bottom: e,
    left: e
  };
}
function yt(e) {
  const {
    x: t,
    y: n,
    width: r,
    height: o
  } = e;
  return {
    width: r,
    height: o,
    top: n,
    left: t,
    right: t + r,
    bottom: n + o,
    x: t,
    y: n
  };
}
function Nr(e, t, n) {
  let {
    reference: r,
    floating: o
  } = e;
  const i = ae(t), a = Ln(t), s = Mn(a), l = me(t), u = i === "y", p = r.x + r.width / 2 - o.width / 2, d = r.y + r.height / 2 - o.height / 2, m = r[s] / 2 - o[s] / 2;
  let h;
  switch (l) {
    case "top":
      h = {
        x: p,
        y: r.y - o.height
      };
      break;
    case "bottom":
      h = {
        x: p,
        y: r.y + r.height
      };
      break;
    case "right":
      h = {
        x: r.x + r.width,
        y: d
      };
      break;
    case "left":
      h = {
        x: r.x - o.width,
        y: d
      };
      break;
    default:
      h = {
        x: r.x,
        y: r.y
      };
  }
  switch (Fe(t)) {
    case "start":
      h[a] -= m * (n && u ? -1 : 1);
      break;
    case "end":
      h[a] += m * (n && u ? -1 : 1);
      break;
  }
  return h;
}
const Bf = async (e, t, n) => {
  const {
    placement: r = "bottom",
    strategy: o = "absolute",
    middleware: i = [],
    platform: a
  } = n, s = i.filter(Boolean), l = await (a.isRTL == null ? void 0 : a.isRTL(t));
  let u = await a.getElementRects({
    reference: e,
    floating: t,
    strategy: o
  }), {
    x: p,
    y: d
  } = Nr(u, r, l), m = r, h = {}, b = 0;
  for (let g = 0; g < s.length; g++) {
    const {
      name: v,
      fn: y
    } = s[g], {
      x: w,
      y: C,
      data: x,
      reset: E
    } = await y({
      x: p,
      y: d,
      initialPlacement: r,
      placement: m,
      strategy: o,
      middlewareData: h,
      rects: u,
      platform: a,
      elements: {
        reference: e,
        floating: t
      }
    });
    p = w ?? p, d = C ?? d, h = {
      ...h,
      [v]: {
        ...h[v],
        ...x
      }
    }, E && b <= 50 && (b++, typeof E == "object" && (E.placement && (m = E.placement), E.rects && (u = E.rects === !0 ? await a.getElementRects({
      reference: e,
      floating: t,
      strategy: o
    }) : E.rects), {
      x: p,
      y: d
    } = Nr(u, m, l)), g = -1);
  }
  return {
    x: p,
    y: d,
    placement: m,
    strategy: o,
    middlewareData: h
  };
};
async function Ue(e, t) {
  var n;
  t === void 0 && (t = {});
  const {
    x: r,
    y: o,
    platform: i,
    rects: a,
    elements: s,
    strategy: l
  } = e, {
    boundary: u = "clippingAncestors",
    rootBoundary: p = "viewport",
    elementContext: d = "floating",
    altBoundary: m = !1,
    padding: h = 0
  } = pe(t, e), b = as(h), v = s[m ? d === "floating" ? "reference" : "floating" : d], y = yt(await i.getClippingRect({
    element: (n = await (i.isElement == null ? void 0 : i.isElement(v))) == null || n ? v : v.contextElement || await (i.getDocumentElement == null ? void 0 : i.getDocumentElement(s.floating)),
    boundary: u,
    rootBoundary: p,
    strategy: l
  })), w = d === "floating" ? {
    x: r,
    y: o,
    width: a.floating.width,
    height: a.floating.height
  } : a.reference, C = await (i.getOffsetParent == null ? void 0 : i.getOffsetParent(s.floating)), x = await (i.isElement == null ? void 0 : i.isElement(C)) ? await (i.getScale == null ? void 0 : i.getScale(C)) || {
    x: 1,
    y: 1
  } : {
    x: 1,
    y: 1
  }, E = yt(i.convertOffsetParentRelativeRectToViewportRelativeRect ? await i.convertOffsetParentRelativeRectToViewportRelativeRect({
    elements: s,
    rect: w,
    offsetParent: C,
    strategy: l
  }) : w);
  return {
    top: (y.top - E.top + b.top) / x.y,
    bottom: (E.bottom - y.bottom + b.bottom) / x.y,
    left: (y.left - E.left + b.left) / x.x,
    right: (E.right - y.right + b.right) / x.x
  };
}
const jf = (e) => ({
  name: "arrow",
  options: e,
  async fn(t) {
    const {
      x: n,
      y: r,
      placement: o,
      rects: i,
      platform: a,
      elements: s,
      middlewareData: l
    } = t, {
      element: u,
      padding: p = 0
    } = pe(e, t) || {};
    if (u == null)
      return {};
    const d = as(p), m = {
      x: n,
      y: r
    }, h = Ln(o), b = Mn(h), g = await a.getDimensions(u), v = h === "y", y = v ? "top" : "left", w = v ? "bottom" : "right", C = v ? "clientHeight" : "clientWidth", x = i.reference[b] + i.reference[h] - m[h] - i.floating[b], E = m[h] - i.reference[h], N = await (a.getOffsetParent == null ? void 0 : a.getOffsetParent(u));
    let R = N ? N[C] : 0;
    (!R || !await (a.isElement == null ? void 0 : a.isElement(N))) && (R = s.floating[C] || i.floating[b]);
    const A = x / 2 - E / 2, P = R / 2 - g[b] / 2 - 1, _ = ye(d[y], P), I = ye(d[w], P), k = _, V = R - g[b] - I, T = R / 2 - g[b] / 2 + A, M = un(k, T, V), O = !l.arrow && Fe(o) != null && T !== M && i.reference[b] / 2 - (T < k ? _ : I) - g[b] / 2 < 0, W = O ? T < k ? T - k : T - V : 0;
    return {
      [h]: m[h] + W,
      data: {
        [h]: M,
        centerOffset: T - M - W,
        ...O && {
          alignmentOffset: W
        }
      },
      reset: O
    };
  }
}), Hf = function(e) {
  return e === void 0 && (e = {}), {
    name: "flip",
    options: e,
    async fn(t) {
      var n, r;
      const {
        placement: o,
        middlewareData: i,
        rects: a,
        initialPlacement: s,
        platform: l,
        elements: u
      } = t, {
        mainAxis: p = !0,
        crossAxis: d = !0,
        fallbackPlacements: m,
        fallbackStrategy: h = "bestFit",
        fallbackAxisSideDirection: b = "none",
        flipAlignment: g = !0,
        ...v
      } = pe(e, t);
      if ((n = i.arrow) != null && n.alignmentOffset)
        return {};
      const y = me(o), w = ae(s), C = me(s) === s, x = await (l.isRTL == null ? void 0 : l.isRTL(u.floating)), E = m || (C || !g ? [bt(s)] : Df(s)), N = b !== "none";
      !m && N && E.push(...Vf(s, g, b, x));
      const R = [s, ...E], A = await Ue(t, v), P = [];
      let _ = ((r = i.flip) == null ? void 0 : r.overflows) || [];
      if (p && P.push(A[y]), d) {
        const T = If(o, a, x);
        P.push(A[T[0]], A[T[1]]);
      }
      if (_ = [..._, {
        placement: o,
        overflows: P
      }], !P.every((T) => T <= 0)) {
        var I, k;
        const T = (((I = i.flip) == null ? void 0 : I.index) || 0) + 1, M = R[T];
        if (M && (!(d === "alignment" ? w !== ae(M) : !1) || // We leave the current main axis only if every placement on that axis
        // overflows the main axis.
        _.every(($) => ae($.placement) === w ? $.overflows[0] > 0 : !0)))
          return {
            data: {
              index: T,
              overflows: _
            },
            reset: {
              placement: M
            }
          };
        let O = (k = _.filter((W) => W.overflows[0] <= 0).sort((W, $) => W.overflows[1] - $.overflows[1])[0]) == null ? void 0 : k.placement;
        if (!O)
          switch (h) {
            case "bestFit": {
              var V;
              const W = (V = _.filter(($) => {
                if (N) {
                  const B = ae($.placement);
                  return B === w || // Create a bias to the `y` side axis due to horizontal
                  // reading directions favoring greater width.
                  B === "y";
                }
                return !0;
              }).map(($) => [$.placement, $.overflows.filter((B) => B > 0).reduce((B, q) => B + q, 0)]).sort(($, B) => $[1] - B[1])[0]) == null ? void 0 : V[0];
              W && (O = W);
              break;
            }
            case "initialPlacement":
              O = s;
              break;
          }
        if (o !== O)
          return {
            reset: {
              placement: O
            }
          };
      }
      return {};
    }
  };
};
function Rr(e, t) {
  return {
    top: e.top - t.height,
    right: e.right - t.width,
    bottom: e.bottom - t.height,
    left: e.left - t.width
  };
}
function Tr(e) {
  return kf.some((t) => e[t] >= 0);
}
const zf = function(e) {
  return e === void 0 && (e = {}), {
    name: "hide",
    options: e,
    async fn(t) {
      const {
        rects: n
      } = t, {
        strategy: r = "referenceHidden",
        ...o
      } = pe(e, t);
      switch (r) {
        case "referenceHidden": {
          const i = await Ue(t, {
            ...o,
            elementContext: "reference"
          }), a = Rr(i, n.reference);
          return {
            data: {
              referenceHiddenOffsets: a,
              referenceHidden: Tr(a)
            }
          };
        }
        case "escaped": {
          const i = await Ue(t, {
            ...o,
            altBoundary: !0
          }), a = Rr(i, n.floating);
          return {
            data: {
              escapedOffsets: a,
              escaped: Tr(a)
            }
          };
        }
        default:
          return {};
      }
    }
  };
}, cs = /* @__PURE__ */ new Set(["left", "top"]);
async function Uf(e, t) {
  const {
    placement: n,
    platform: r,
    elements: o
  } = e, i = await (r.isRTL == null ? void 0 : r.isRTL(o.floating)), a = me(n), s = Fe(n), l = ae(n) === "y", u = cs.has(a) ? -1 : 1, p = i && l ? -1 : 1, d = pe(t, e);
  let {
    mainAxis: m,
    crossAxis: h,
    alignmentAxis: b
  } = typeof d == "number" ? {
    mainAxis: d,
    crossAxis: 0,
    alignmentAxis: null
  } : {
    mainAxis: d.mainAxis || 0,
    crossAxis: d.crossAxis || 0,
    alignmentAxis: d.alignmentAxis
  };
  return s && typeof b == "number" && (h = s === "end" ? b * -1 : b), l ? {
    x: h * p,
    y: m * u
  } : {
    x: m * u,
    y: h * p
  };
}
const Gf = function(e) {
  return e === void 0 && (e = 0), {
    name: "offset",
    options: e,
    async fn(t) {
      var n, r;
      const {
        x: o,
        y: i,
        placement: a,
        middlewareData: s
      } = t, l = await Uf(t, e);
      return a === ((n = s.offset) == null ? void 0 : n.placement) && (r = s.arrow) != null && r.alignmentOffset ? {} : {
        x: o + l.x,
        y: i + l.y,
        data: {
          ...l,
          placement: a
        }
      };
    }
  };
}, Kf = function(e) {
  return e === void 0 && (e = {}), {
    name: "shift",
    options: e,
    async fn(t) {
      const {
        x: n,
        y: r,
        placement: o
      } = t, {
        mainAxis: i = !0,
        crossAxis: a = !1,
        limiter: s = {
          fn: (v) => {
            let {
              x: y,
              y: w
            } = v;
            return {
              x: y,
              y: w
            };
          }
        },
        ...l
      } = pe(e, t), u = {
        x: n,
        y: r
      }, p = await Ue(t, l), d = ae(me(o)), m = Dn(d);
      let h = u[m], b = u[d];
      if (i) {
        const v = m === "y" ? "top" : "left", y = m === "y" ? "bottom" : "right", w = h + p[v], C = h - p[y];
        h = un(w, h, C);
      }
      if (a) {
        const v = d === "y" ? "top" : "left", y = d === "y" ? "bottom" : "right", w = b + p[v], C = b - p[y];
        b = un(w, b, C);
      }
      const g = s.fn({
        ...t,
        [m]: h,
        [d]: b
      });
      return {
        ...g,
        data: {
          x: g.x - n,
          y: g.y - r,
          enabled: {
            [m]: i,
            [d]: a
          }
        }
      };
    }
  };
}, qf = function(e) {
  return e === void 0 && (e = {}), {
    options: e,
    fn(t) {
      const {
        x: n,
        y: r,
        placement: o,
        rects: i,
        middlewareData: a
      } = t, {
        offset: s = 0,
        mainAxis: l = !0,
        crossAxis: u = !0
      } = pe(e, t), p = {
        x: n,
        y: r
      }, d = ae(o), m = Dn(d);
      let h = p[m], b = p[d];
      const g = pe(s, t), v = typeof g == "number" ? {
        mainAxis: g,
        crossAxis: 0
      } : {
        mainAxis: 0,
        crossAxis: 0,
        ...g
      };
      if (l) {
        const C = m === "y" ? "height" : "width", x = i.reference[m] - i.floating[C] + v.mainAxis, E = i.reference[m] + i.reference[C] - v.mainAxis;
        h < x ? h = x : h > E && (h = E);
      }
      if (u) {
        var y, w;
        const C = m === "y" ? "width" : "height", x = cs.has(me(o)), E = i.reference[d] - i.floating[C] + (x && ((y = a.offset) == null ? void 0 : y[d]) || 0) + (x ? 0 : v.crossAxis), N = i.reference[d] + i.reference[C] + (x ? 0 : ((w = a.offset) == null ? void 0 : w[d]) || 0) - (x ? v.crossAxis : 0);
        b < E ? b = E : b > N && (b = N);
      }
      return {
        [m]: h,
        [d]: b
      };
    }
  };
}, Yf = function(e) {
  return e === void 0 && (e = {}), {
    name: "size",
    options: e,
    async fn(t) {
      var n, r;
      const {
        placement: o,
        rects: i,
        platform: a,
        elements: s
      } = t, {
        apply: l = () => {
        },
        ...u
      } = pe(e, t), p = await Ue(t, u), d = me(o), m = Fe(o), h = ae(o) === "y", {
        width: b,
        height: g
      } = i.floating;
      let v, y;
      d === "top" || d === "bottom" ? (v = d, y = m === (await (a.isRTL == null ? void 0 : a.isRTL(s.floating)) ? "start" : "end") ? "left" : "right") : (y = d, v = m === "end" ? "top" : "bottom");
      const w = g - p.top - p.bottom, C = b - p.left - p.right, x = ye(g - p[v], w), E = ye(b - p[y], C), N = !t.middlewareData.shift;
      let R = x, A = E;
      if ((n = t.middlewareData.shift) != null && n.enabled.x && (A = C), (r = t.middlewareData.shift) != null && r.enabled.y && (R = w), N && !m) {
        const _ = Z(p.left, 0), I = Z(p.right, 0), k = Z(p.top, 0), V = Z(p.bottom, 0);
        h ? A = b - 2 * (_ !== 0 || I !== 0 ? _ + I : Z(p.left, p.right)) : R = g - 2 * (k !== 0 || V !== 0 ? k + V : Z(p.top, p.bottom));
      }
      await l({
        ...t,
        availableWidth: A,
        availableHeight: R
      });
      const P = await a.getDimensions(s.floating);
      return b !== P.width || g !== P.height ? {
        reset: {
          rects: !0
        }
      } : {};
    }
  };
};
function _t() {
  return typeof window < "u";
}
function Ve(e) {
  return ls(e) ? (e.nodeName || "").toLowerCase() : "#document";
}
function Q(e) {
  var t;
  return (e == null || (t = e.ownerDocument) == null ? void 0 : t.defaultView) || window;
}
function ue(e) {
  var t;
  return (t = (ls(e) ? e.ownerDocument : e.document) || window.document) == null ? void 0 : t.documentElement;
}
function ls(e) {
  return _t() ? e instanceof Node || e instanceof Q(e).Node : !1;
}
function re(e) {
  return _t() ? e instanceof Element || e instanceof Q(e).Element : !1;
}
function le(e) {
  return _t() ? e instanceof HTMLElement || e instanceof Q(e).HTMLElement : !1;
}
function Pr(e) {
  return !_t() || typeof ShadowRoot > "u" ? !1 : e instanceof ShadowRoot || e instanceof Q(e).ShadowRoot;
}
const Xf = /* @__PURE__ */ new Set(["inline", "contents"]);
function Je(e) {
  const {
    overflow: t,
    overflowX: n,
    overflowY: r,
    display: o
  } = oe(e);
  return /auto|scroll|overlay|hidden|clip/.test(t + r + n) && !Xf.has(o);
}
const Zf = /* @__PURE__ */ new Set(["table", "td", "th"]);
function Qf(e) {
  return Zf.has(Ve(e));
}
const Jf = [":popover-open", ":modal"];
function Ot(e) {
  return Jf.some((t) => {
    try {
      return e.matches(t);
    } catch {
      return !1;
    }
  });
}
const ep = ["transform", "translate", "scale", "rotate", "perspective"], tp = ["transform", "translate", "scale", "rotate", "perspective", "filter"], np = ["paint", "layout", "strict", "content"];
function Fn(e) {
  const t = Vn(), n = re(e) ? oe(e) : e;
  return ep.some((r) => n[r] ? n[r] !== "none" : !1) || (n.containerType ? n.containerType !== "normal" : !1) || !t && (n.backdropFilter ? n.backdropFilter !== "none" : !1) || !t && (n.filter ? n.filter !== "none" : !1) || tp.some((r) => (n.willChange || "").includes(r)) || np.some((r) => (n.contain || "").includes(r));
}
function rp(e) {
  let t = xe(e);
  for (; le(t) && !$e(t); ) {
    if (Fn(t))
      return t;
    if (Ot(t))
      return null;
    t = xe(t);
  }
  return null;
}
function Vn() {
  return typeof CSS > "u" || !CSS.supports ? !1 : CSS.supports("-webkit-backdrop-filter", "none");
}
const op = /* @__PURE__ */ new Set(["html", "body", "#document"]);
function $e(e) {
  return op.has(Ve(e));
}
function oe(e) {
  return Q(e).getComputedStyle(e);
}
function $t(e) {
  return re(e) ? {
    scrollLeft: e.scrollLeft,
    scrollTop: e.scrollTop
  } : {
    scrollLeft: e.scrollX,
    scrollTop: e.scrollY
  };
}
function xe(e) {
  if (Ve(e) === "html")
    return e;
  const t = (
    // Step into the shadow DOM of the parent of a slotted node.
    e.assignedSlot || // DOM Element detected.
    e.parentNode || // ShadowRoot detected.
    Pr(e) && e.host || // Fallback.
    ue(e)
  );
  return Pr(t) ? t.host : t;
}
function us(e) {
  const t = xe(e);
  return $e(t) ? e.ownerDocument ? e.ownerDocument.body : e.body : le(t) && Je(t) ? t : us(t);
}
function Ge(e, t, n) {
  var r;
  t === void 0 && (t = []), n === void 0 && (n = !0);
  const o = us(e), i = o === ((r = e.ownerDocument) == null ? void 0 : r.body), a = Q(o);
  if (i) {
    const s = fn(a);
    return t.concat(a, a.visualViewport || [], Je(o) ? o : [], s && n ? Ge(s) : []);
  }
  return t.concat(o, Ge(o, [], n));
}
function fn(e) {
  return e.parent && Object.getPrototypeOf(e.parent) ? e.frameElement : null;
}
function ds(e) {
  const t = oe(e);
  let n = parseFloat(t.width) || 0, r = parseFloat(t.height) || 0;
  const o = le(e), i = o ? e.offsetWidth : n, a = o ? e.offsetHeight : r, s = vt(n) !== i || vt(r) !== a;
  return s && (n = i, r = a), {
    width: n,
    height: r,
    $: s
  };
}
function Wn(e) {
  return re(e) ? e : e.contextElement;
}
function Oe(e) {
  const t = Wn(e);
  if (!le(t))
    return ce(1);
  const n = t.getBoundingClientRect(), {
    width: r,
    height: o,
    $: i
  } = ds(t);
  let a = (i ? vt(n.width) : n.width) / r, s = (i ? vt(n.height) : n.height) / o;
  return (!a || !Number.isFinite(a)) && (a = 1), (!s || !Number.isFinite(s)) && (s = 1), {
    x: a,
    y: s
  };
}
const ip = /* @__PURE__ */ ce(0);
function fs(e) {
  const t = Q(e);
  return !Vn() || !t.visualViewport ? ip : {
    x: t.visualViewport.offsetLeft,
    y: t.visualViewport.offsetTop
  };
}
function sp(e, t, n) {
  return t === void 0 && (t = !1), !n || t && n !== Q(e) ? !1 : t;
}
function Se(e, t, n, r) {
  t === void 0 && (t = !1), n === void 0 && (n = !1);
  const o = e.getBoundingClientRect(), i = Wn(e);
  let a = ce(1);
  t && (r ? re(r) && (a = Oe(r)) : a = Oe(e));
  const s = sp(i, n, r) ? fs(i) : ce(0);
  let l = (o.left + s.x) / a.x, u = (o.top + s.y) / a.y, p = o.width / a.x, d = o.height / a.y;
  if (i) {
    const m = Q(i), h = r && re(r) ? Q(r) : r;
    let b = m, g = fn(b);
    for (; g && r && h !== b; ) {
      const v = Oe(g), y = g.getBoundingClientRect(), w = oe(g), C = y.left + (g.clientLeft + parseFloat(w.paddingLeft)) * v.x, x = y.top + (g.clientTop + parseFloat(w.paddingTop)) * v.y;
      l *= v.x, u *= v.y, p *= v.x, d *= v.y, l += C, u += x, b = Q(g), g = fn(b);
    }
  }
  return yt({
    width: p,
    height: d,
    x: l,
    y: u
  });
}
function It(e, t) {
  const n = $t(e).scrollLeft;
  return t ? t.left + n : Se(ue(e)).left + n;
}
function ps(e, t) {
  const n = e.getBoundingClientRect(), r = n.left + t.scrollLeft - It(e, n), o = n.top + t.scrollTop;
  return {
    x: r,
    y: o
  };
}
function ap(e) {
  let {
    elements: t,
    rect: n,
    offsetParent: r,
    strategy: o
  } = e;
  const i = o === "fixed", a = ue(r), s = t ? Ot(t.floating) : !1;
  if (r === a || s && i)
    return n;
  let l = {
    scrollLeft: 0,
    scrollTop: 0
  }, u = ce(1);
  const p = ce(0), d = le(r);
  if ((d || !d && !i) && ((Ve(r) !== "body" || Je(a)) && (l = $t(r)), le(r))) {
    const h = Se(r);
    u = Oe(r), p.x = h.x + r.clientLeft, p.y = h.y + r.clientTop;
  }
  const m = a && !d && !i ? ps(a, l) : ce(0);
  return {
    width: n.width * u.x,
    height: n.height * u.y,
    x: n.x * u.x - l.scrollLeft * u.x + p.x + m.x,
    y: n.y * u.y - l.scrollTop * u.y + p.y + m.y
  };
}
function cp(e) {
  return Array.from(e.getClientRects());
}
function lp(e) {
  const t = ue(e), n = $t(e), r = e.ownerDocument.body, o = Z(t.scrollWidth, t.clientWidth, r.scrollWidth, r.clientWidth), i = Z(t.scrollHeight, t.clientHeight, r.scrollHeight, r.clientHeight);
  let a = -n.scrollLeft + It(e);
  const s = -n.scrollTop;
  return oe(r).direction === "rtl" && (a += Z(t.clientWidth, r.clientWidth) - o), {
    width: o,
    height: i,
    x: a,
    y: s
  };
}
const Ar = 25;
function up(e, t) {
  const n = Q(e), r = ue(e), o = n.visualViewport;
  let i = r.clientWidth, a = r.clientHeight, s = 0, l = 0;
  if (o) {
    i = o.width, a = o.height;
    const p = Vn();
    (!p || p && t === "fixed") && (s = o.offsetLeft, l = o.offsetTop);
  }
  const u = It(r);
  if (u <= 0) {
    const p = r.ownerDocument, d = p.body, m = getComputedStyle(d), h = p.compatMode === "CSS1Compat" && parseFloat(m.marginLeft) + parseFloat(m.marginRight) || 0, b = Math.abs(r.clientWidth - d.clientWidth - h);
    b <= Ar && (i -= b);
  } else u <= Ar && (i += u);
  return {
    width: i,
    height: a,
    x: s,
    y: l
  };
}
const dp = /* @__PURE__ */ new Set(["absolute", "fixed"]);
function fp(e, t) {
  const n = Se(e, !0, t === "fixed"), r = n.top + e.clientTop, o = n.left + e.clientLeft, i = le(e) ? Oe(e) : ce(1), a = e.clientWidth * i.x, s = e.clientHeight * i.y, l = o * i.x, u = r * i.y;
  return {
    width: a,
    height: s,
    x: l,
    y: u
  };
}
function kr(e, t, n) {
  let r;
  if (t === "viewport")
    r = up(e, n);
  else if (t === "document")
    r = lp(ue(e));
  else if (re(t))
    r = fp(t, n);
  else {
    const o = fs(e);
    r = {
      x: t.x - o.x,
      y: t.y - o.y,
      width: t.width,
      height: t.height
    };
  }
  return yt(r);
}
function ms(e, t) {
  const n = xe(e);
  return n === t || !re(n) || $e(n) ? !1 : oe(n).position === "fixed" || ms(n, t);
}
function pp(e, t) {
  const n = t.get(e);
  if (n)
    return n;
  let r = Ge(e, [], !1).filter((s) => re(s) && Ve(s) !== "body"), o = null;
  const i = oe(e).position === "fixed";
  let a = i ? xe(e) : e;
  for (; re(a) && !$e(a); ) {
    const s = oe(a), l = Fn(a);
    !l && s.position === "fixed" && (o = null), (i ? !l && !o : !l && s.position === "static" && !!o && dp.has(o.position) || Je(a) && !l && ms(e, a)) ? r = r.filter((p) => p !== a) : o = s, a = xe(a);
  }
  return t.set(e, r), r;
}
function mp(e) {
  let {
    element: t,
    boundary: n,
    rootBoundary: r,
    strategy: o
  } = e;
  const a = [...n === "clippingAncestors" ? Ot(t) ? [] : pp(t, this._c) : [].concat(n), r], s = a[0], l = a.reduce((u, p) => {
    const d = kr(t, p, o);
    return u.top = Z(d.top, u.top), u.right = ye(d.right, u.right), u.bottom = ye(d.bottom, u.bottom), u.left = Z(d.left, u.left), u;
  }, kr(t, s, o));
  return {
    width: l.right - l.left,
    height: l.bottom - l.top,
    x: l.left,
    y: l.top
  };
}
function gp(e) {
  const {
    width: t,
    height: n
  } = ds(e);
  return {
    width: t,
    height: n
  };
}
function hp(e, t, n) {
  const r = le(t), o = ue(t), i = n === "fixed", a = Se(e, !0, i, t);
  let s = {
    scrollLeft: 0,
    scrollTop: 0
  };
  const l = ce(0);
  function u() {
    l.x = It(o);
  }
  if (r || !r && !i)
    if ((Ve(t) !== "body" || Je(o)) && (s = $t(t)), r) {
      const h = Se(t, !0, i, t);
      l.x = h.x + t.clientLeft, l.y = h.y + t.clientTop;
    } else o && u();
  i && !r && o && u();
  const p = o && !r && !i ? ps(o, s) : ce(0), d = a.left + s.scrollLeft - l.x - p.x, m = a.top + s.scrollTop - l.y - p.y;
  return {
    x: d,
    y: m,
    width: a.width,
    height: a.height
  };
}
function Qt(e) {
  return oe(e).position === "static";
}
function _r(e, t) {
  if (!le(e) || oe(e).position === "fixed")
    return null;
  if (t)
    return t(e);
  let n = e.offsetParent;
  return ue(e) === n && (n = n.ownerDocument.body), n;
}
function gs(e, t) {
  const n = Q(e);
  if (Ot(e))
    return n;
  if (!le(e)) {
    let o = xe(e);
    for (; o && !$e(o); ) {
      if (re(o) && !Qt(o))
        return o;
      o = xe(o);
    }
    return n;
  }
  let r = _r(e, t);
  for (; r && Qf(r) && Qt(r); )
    r = _r(r, t);
  return r && $e(r) && Qt(r) && !Fn(r) ? n : r || rp(e) || n;
}
const vp = async function(e) {
  const t = this.getOffsetParent || gs, n = this.getDimensions, r = await n(e.floating);
  return {
    reference: hp(e.reference, await t(e.floating), e.strategy),
    floating: {
      x: 0,
      y: 0,
      width: r.width,
      height: r.height
    }
  };
};
function bp(e) {
  return oe(e).direction === "rtl";
}
const yp = {
  convertOffsetParentRelativeRectToViewportRelativeRect: ap,
  getDocumentElement: ue,
  getClippingRect: mp,
  getOffsetParent: gs,
  getElementRects: vp,
  getClientRects: cp,
  getDimensions: gp,
  getScale: Oe,
  isElement: re,
  isRTL: bp
};
function hs(e, t) {
  return e.x === t.x && e.y === t.y && e.width === t.width && e.height === t.height;
}
function xp(e, t) {
  let n = null, r;
  const o = ue(e);
  function i() {
    var s;
    clearTimeout(r), (s = n) == null || s.disconnect(), n = null;
  }
  function a(s, l) {
    s === void 0 && (s = !1), l === void 0 && (l = 1), i();
    const u = e.getBoundingClientRect(), {
      left: p,
      top: d,
      width: m,
      height: h
    } = u;
    if (s || t(), !m || !h)
      return;
    const b = ct(d), g = ct(o.clientWidth - (p + m)), v = ct(o.clientHeight - (d + h)), y = ct(p), C = {
      rootMargin: -b + "px " + -g + "px " + -v + "px " + -y + "px",
      threshold: Z(0, ye(1, l)) || 1
    };
    let x = !0;
    function E(N) {
      const R = N[0].intersectionRatio;
      if (R !== l) {
        if (!x)
          return a();
        R ? a(!1, R) : r = setTimeout(() => {
          a(!1, 1e-7);
        }, 1e3);
      }
      R === 1 && !hs(u, e.getBoundingClientRect()) && a(), x = !1;
    }
    try {
      n = new IntersectionObserver(E, {
        ...C,
        // Handle <iframe>s
        root: o.ownerDocument
      });
    } catch {
      n = new IntersectionObserver(E, C);
    }
    n.observe(e);
  }
  return a(!0), i;
}
function wp(e, t, n, r) {
  r === void 0 && (r = {});
  const {
    ancestorScroll: o = !0,
    ancestorResize: i = !0,
    elementResize: a = typeof ResizeObserver == "function",
    layoutShift: s = typeof IntersectionObserver == "function",
    animationFrame: l = !1
  } = r, u = Wn(e), p = o || i ? [...u ? Ge(u) : [], ...Ge(t)] : [];
  p.forEach((y) => {
    o && y.addEventListener("scroll", n, {
      passive: !0
    }), i && y.addEventListener("resize", n);
  });
  const d = u && s ? xp(u, n) : null;
  let m = -1, h = null;
  a && (h = new ResizeObserver((y) => {
    let [w] = y;
    w && w.target === u && h && (h.unobserve(t), cancelAnimationFrame(m), m = requestAnimationFrame(() => {
      var C;
      (C = h) == null || C.observe(t);
    })), n();
  }), u && !l && h.observe(u), h.observe(t));
  let b, g = l ? Se(e) : null;
  l && v();
  function v() {
    const y = Se(e);
    g && !hs(g, y) && n(), g = y, b = requestAnimationFrame(v);
  }
  return n(), () => {
    var y;
    p.forEach((w) => {
      o && w.removeEventListener("scroll", n), i && w.removeEventListener("resize", n);
    }), d == null || d(), (y = h) == null || y.disconnect(), h = null, l && cancelAnimationFrame(b);
  };
}
const Cp = Gf, Ep = Kf, Sp = Hf, Np = Yf, Rp = zf, Or = jf, Tp = qf, Pp = (e, t, n) => {
  const r = /* @__PURE__ */ new Map(), o = {
    platform: yp,
    ...n
  }, i = {
    ...o.platform,
    _c: r
  };
  return Bf(e, t, {
    ...o,
    platform: i
  });
};
var Ap = typeof document < "u", kp = function() {
}, mt = Ap ? Ks : kp;
function xt(e, t) {
  if (e === t)
    return !0;
  if (typeof e != typeof t)
    return !1;
  if (typeof e == "function" && e.toString() === t.toString())
    return !0;
  let n, r, o;
  if (e && t && typeof e == "object") {
    if (Array.isArray(e)) {
      if (n = e.length, n !== t.length) return !1;
      for (r = n; r-- !== 0; )
        if (!xt(e[r], t[r]))
          return !1;
      return !0;
    }
    if (o = Object.keys(e), n = o.length, n !== Object.keys(t).length)
      return !1;
    for (r = n; r-- !== 0; )
      if (!{}.hasOwnProperty.call(t, o[r]))
        return !1;
    for (r = n; r-- !== 0; ) {
      const i = o[r];
      if (!(i === "_owner" && e.$$typeof) && !xt(e[i], t[i]))
        return !1;
    }
    return !0;
  }
  return e !== e && t !== t;
}
function vs(e) {
  return typeof window > "u" ? 1 : (e.ownerDocument.defaultView || window).devicePixelRatio || 1;
}
function $r(e, t) {
  const n = vs(e);
  return Math.round(t * n) / n;
}
function Jt(e) {
  const t = c.useRef(e);
  return mt(() => {
    t.current = e;
  }), t;
}
function _p(e) {
  e === void 0 && (e = {});
  const {
    placement: t = "bottom",
    strategy: n = "absolute",
    middleware: r = [],
    platform: o,
    elements: {
      reference: i,
      floating: a
    } = {},
    transform: s = !0,
    whileElementsMounted: l,
    open: u
  } = e, [p, d] = c.useState({
    x: 0,
    y: 0,
    strategy: n,
    placement: t,
    middlewareData: {},
    isPositioned: !1
  }), [m, h] = c.useState(r);
  xt(m, r) || h(r);
  const [b, g] = c.useState(null), [v, y] = c.useState(null), w = c.useCallback(($) => {
    $ !== N.current && (N.current = $, g($));
  }, []), C = c.useCallback(($) => {
    $ !== R.current && (R.current = $, y($));
  }, []), x = i || b, E = a || v, N = c.useRef(null), R = c.useRef(null), A = c.useRef(p), P = l != null, _ = Jt(l), I = Jt(o), k = Jt(u), V = c.useCallback(() => {
    if (!N.current || !R.current)
      return;
    const $ = {
      placement: t,
      strategy: n,
      middleware: m
    };
    I.current && ($.platform = I.current), Pp(N.current, R.current, $).then((B) => {
      const q = {
        ...B,
        // The floating element's position may be recomputed while it's closed
        // but still mounted (such as when transitioning out). To ensure
        // `isPositioned` will be `false` initially on the next open, avoid
        // setting it to `true` when `open === false` (must be specified).
        isPositioned: k.current !== !1
      };
      T.current && !xt(A.current, q) && (A.current = q, wt.flushSync(() => {
        d(q);
      }));
    });
  }, [m, t, n, I, k]);
  mt(() => {
    u === !1 && A.current.isPositioned && (A.current.isPositioned = !1, d(($) => ({
      ...$,
      isPositioned: !1
    })));
  }, [u]);
  const T = c.useRef(!1);
  mt(() => (T.current = !0, () => {
    T.current = !1;
  }), []), mt(() => {
    if (x && (N.current = x), E && (R.current = E), x && E) {
      if (_.current)
        return _.current(x, E, V);
      V();
    }
  }, [x, E, V, _, P]);
  const M = c.useMemo(() => ({
    reference: N,
    floating: R,
    setReference: w,
    setFloating: C
  }), [w, C]), O = c.useMemo(() => ({
    reference: x,
    floating: E
  }), [x, E]), W = c.useMemo(() => {
    const $ = {
      position: n,
      left: 0,
      top: 0
    };
    if (!O.floating)
      return $;
    const B = $r(O.floating, p.x), q = $r(O.floating, p.y);
    return s ? {
      ...$,
      transform: "translate(" + B + "px, " + q + "px)",
      ...vs(O.floating) >= 1.5 && {
        willChange: "transform"
      }
    } : {
      position: n,
      left: B,
      top: q
    };
  }, [n, s, O.floating, p.x, p.y]);
  return c.useMemo(() => ({
    ...p,
    update: V,
    refs: M,
    elements: O,
    floatingStyles: W
  }), [p, V, M, O, W]);
}
const Op = (e) => {
  function t(n) {
    return {}.hasOwnProperty.call(n, "current");
  }
  return {
    name: "arrow",
    options: e,
    fn(n) {
      const {
        element: r,
        padding: o
      } = typeof e == "function" ? e(n) : e;
      return r && t(r) ? r.current != null ? Or({
        element: r.current,
        padding: o
      }).fn(n) : {} : r ? Or({
        element: r,
        padding: o
      }).fn(n) : {};
    }
  };
}, $p = (e, t) => ({
  ...Cp(e),
  options: [e, t]
}), Ip = (e, t) => ({
  ...Ep(e),
  options: [e, t]
}), Dp = (e, t) => ({
  ...Tp(e),
  options: [e, t]
}), Mp = (e, t) => ({
  ...Sp(e),
  options: [e, t]
}), Lp = (e, t) => ({
  ...Np(e),
  options: [e, t]
}), Fp = (e, t) => ({
  ...Rp(e),
  options: [e, t]
}), Vp = (e, t) => ({
  ...Op(e),
  options: [e, t]
});
// @__NO_SIDE_EFFECTS__
function Wp(e) {
  const t = /* @__PURE__ */ Bp(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(Hp);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function Bp(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = Up(o), s = zp(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var jp = Symbol("radix.slottable");
function Hp(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === jp;
}
function zp(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function Up(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var Gp = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Kp = Gp.reduce((e, t) => {
  const n = /* @__PURE__ */ Wp(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), qp = "Arrow", bs = c.forwardRef((e, t) => {
  const { children: n, width: r = 10, height: o = 5, ...i } = e;
  return /* @__PURE__ */ f(
    Kp.svg,
    {
      ...i,
      ref: t,
      width: r,
      height: o,
      viewBox: "0 0 30 10",
      preserveAspectRatio: "none",
      children: e.asChild ? n : /* @__PURE__ */ f("polygon", { points: "0,0 30,0 15,10" })
    }
  );
});
bs.displayName = qp;
var Yp = bs;
function Xp(e, t = []) {
  let n = [];
  function r(i, a) {
    const s = c.createContext(a), l = n.length;
    n = [...n, a];
    const u = (d) => {
      var y;
      const { scope: m, children: h, ...b } = d, g = ((y = m == null ? void 0 : m[e]) == null ? void 0 : y[l]) || s, v = c.useMemo(() => b, Object.values(b));
      return /* @__PURE__ */ f(g.Provider, { value: v, children: h });
    };
    u.displayName = i + "Provider";
    function p(d, m) {
      var g;
      const h = ((g = m == null ? void 0 : m[e]) == null ? void 0 : g[l]) || s, b = c.useContext(h);
      if (b) return b;
      if (a !== void 0) return a;
      throw new Error(`\`${d}\` must be used within \`${i}\``);
    }
    return [u, p];
  }
  const o = () => {
    const i = n.map((a) => c.createContext(a));
    return function(s) {
      const l = (s == null ? void 0 : s[e]) || i;
      return c.useMemo(
        () => ({ [`__scope${e}`]: { ...s, [e]: l } }),
        [s, l]
      );
    };
  };
  return o.scopeName = e, [r, Zp(o, ...t)];
}
function Zp(...e) {
  const t = e[0];
  if (e.length === 1) return t;
  const n = () => {
    const r = e.map((o) => ({
      useScope: o(),
      scopeName: o.scopeName
    }));
    return function(i) {
      const a = r.reduce((s, { useScope: l, scopeName: u }) => {
        const d = l(i)[`__scope${u}`];
        return { ...s, ...d };
      }, {});
      return c.useMemo(() => ({ [`__scope${t.scopeName}`]: a }), [a]);
    };
  };
  return n.scopeName = t.scopeName, n;
}
// @__NO_SIDE_EFFECTS__
function Qp(e) {
  const t = /* @__PURE__ */ Jp(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(tm);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function Jp(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = rm(o), s = nm(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var em = Symbol("radix.slottable");
function tm(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === em;
}
function nm(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function rm(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var om = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], ys = om.reduce((e, t) => {
  const n = /* @__PURE__ */ Qp(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), Bn = "Popper", [xs, ws] = Xp(Bn), [im, Cs] = xs(Bn), Es = (e) => {
  const { __scopePopper: t, children: n } = e, [r, o] = c.useState(null);
  return /* @__PURE__ */ f(im, { scope: t, anchor: r, onAnchorChange: o, children: n });
};
Es.displayName = Bn;
var Ss = "PopperAnchor", Ns = c.forwardRef(
  (e, t) => {
    const { __scopePopper: n, virtualRef: r, ...o } = e, i = Cs(Ss, n), a = c.useRef(null), s = U(t, a), l = c.useRef(null);
    return c.useEffect(() => {
      const u = l.current;
      l.current = (r == null ? void 0 : r.current) || a.current, u !== l.current && i.onAnchorChange(l.current);
    }), r ? null : /* @__PURE__ */ f(ys.div, { ...o, ref: s });
  }
);
Ns.displayName = Ss;
var jn = "PopperContent", [sm, am] = xs(jn), Rs = c.forwardRef(
  (e, t) => {
    var zn, Un, Gn, Kn, qn, Yn;
    const {
      __scopePopper: n,
      side: r = "bottom",
      sideOffset: o = 0,
      align: i = "center",
      alignOffset: a = 0,
      arrowPadding: s = 0,
      avoidCollisions: l = !0,
      collisionBoundary: u = [],
      collisionPadding: p = 0,
      sticky: d = "partial",
      hideWhenDetached: m = !1,
      updatePositionStrategy: h = "optimized",
      onPlaced: b,
      ...g
    } = e, v = Cs(jn, n), [y, w] = c.useState(null), C = U(t, (Be) => w(Be)), [x, E] = c.useState(null), N = Jr(x), R = (N == null ? void 0 : N.width) ?? 0, A = (N == null ? void 0 : N.height) ?? 0, P = r + (i !== "center" ? "-" + i : ""), _ = typeof p == "number" ? p : { top: 0, right: 0, bottom: 0, left: 0, ...p }, I = Array.isArray(u) ? u : [u], k = I.length > 0, V = {
      padding: _,
      boundary: I.filter(lm),
      // with `strategy: 'fixed'`, this is the only way to get it to respect boundaries
      altBoundary: k
    }, { refs: T, floatingStyles: M, placement: O, isPositioned: W, middlewareData: $ } = _p({
      // default to `fixed` strategy so users don't have to pick and we also avoid focus scroll issues
      strategy: "fixed",
      placement: P,
      whileElementsMounted: (...Be) => wp(...Be, {
        animationFrame: h === "always"
      }),
      elements: {
        reference: v.anchor
      },
      middleware: [
        $p({ mainAxis: o + A, alignmentAxis: a }),
        l && Ip({
          mainAxis: !0,
          crossAxis: !1,
          limiter: d === "partial" ? Dp() : void 0,
          ...V
        }),
        l && Mp({ ...V }),
        Lp({
          ...V,
          apply: ({ elements: Be, rects: Xn, availableWidth: js, availableHeight: Hs }) => {
            const { width: zs, height: Us } = Xn.reference, tt = Be.floating.style;
            tt.setProperty("--radix-popper-available-width", `${js}px`), tt.setProperty("--radix-popper-available-height", `${Hs}px`), tt.setProperty("--radix-popper-anchor-width", `${zs}px`), tt.setProperty("--radix-popper-anchor-height", `${Us}px`);
          }
        }),
        x && Vp({ element: x, padding: s }),
        um({ arrowWidth: R, arrowHeight: A }),
        m && Fp({ strategy: "referenceHidden", ...V })
      ]
    }), [B, q] = As(O), K = ne(b);
    te(() => {
      W && (K == null || K());
    }, [W, K]);
    const We = (zn = $.arrow) == null ? void 0 : zn.x, Ne = (Un = $.arrow) == null ? void 0 : Un.y, et = ((Gn = $.arrow) == null ? void 0 : Gn.centerOffset) !== 0, [Ws, Bs] = c.useState();
    return te(() => {
      y && Bs(window.getComputedStyle(y).zIndex);
    }, [y]), /* @__PURE__ */ f(
      "div",
      {
        ref: T.setFloating,
        "data-radix-popper-content-wrapper": "",
        style: {
          ...M,
          transform: W ? M.transform : "translate(0, -200%)",
          // keep off the page when measuring
          minWidth: "max-content",
          zIndex: Ws,
          "--radix-popper-transform-origin": [
            (Kn = $.transformOrigin) == null ? void 0 : Kn.x,
            (qn = $.transformOrigin) == null ? void 0 : qn.y
          ].join(" "),
          // hide the content if using the hide middleware and should be hidden
          // set visibility to hidden and disable pointer events so the UI behaves
          // as if the PopperContent isn't there at all
          ...((Yn = $.hide) == null ? void 0 : Yn.referenceHidden) && {
            visibility: "hidden",
            pointerEvents: "none"
          }
        },
        dir: e.dir,
        children: /* @__PURE__ */ f(
          sm,
          {
            scope: n,
            placedSide: B,
            onArrowChange: E,
            arrowX: We,
            arrowY: Ne,
            shouldHideArrow: et,
            children: /* @__PURE__ */ f(
              ys.div,
              {
                "data-side": B,
                "data-align": q,
                ...g,
                ref: C,
                style: {
                  ...g.style,
                  // if the PopperContent hasn't been placed yet (not all measurements done)
                  // we prevent animations so that users's animation don't kick in too early referring wrong sides
                  animation: W ? void 0 : "none"
                }
              }
            )
          }
        )
      }
    );
  }
);
Rs.displayName = jn;
var Ts = "PopperArrow", cm = {
  top: "bottom",
  right: "left",
  bottom: "top",
  left: "right"
}, Ps = c.forwardRef(function(t, n) {
  const { __scopePopper: r, ...o } = t, i = am(Ts, r), a = cm[i.placedSide];
  return (
    // we have to use an extra wrapper because `ResizeObserver` (used by `useSize`)
    // doesn't report size as we'd expect on SVG elements.
    // it reports their bounding box which is effectively the largest path inside the SVG.
    /* @__PURE__ */ f(
      "span",
      {
        ref: i.onArrowChange,
        style: {
          position: "absolute",
          left: i.arrowX,
          top: i.arrowY,
          [a]: 0,
          transformOrigin: {
            top: "",
            right: "0 0",
            bottom: "center 0",
            left: "100% 0"
          }[i.placedSide],
          transform: {
            top: "translateY(100%)",
            right: "translateY(50%) rotate(90deg) translateX(-50%)",
            bottom: "rotate(180deg)",
            left: "translateY(50%) rotate(-90deg) translateX(50%)"
          }[i.placedSide],
          visibility: i.shouldHideArrow ? "hidden" : void 0
        },
        children: /* @__PURE__ */ f(
          Yp,
          {
            ...o,
            ref: n,
            style: {
              ...o.style,
              // ensures the element can be measured correctly (mostly for if SVG)
              display: "block"
            }
          }
        )
      }
    )
  );
});
Ps.displayName = Ts;
function lm(e) {
  return e !== null;
}
var um = (e) => ({
  name: "transformOrigin",
  options: e,
  fn(t) {
    var v, y, w;
    const { placement: n, rects: r, middlewareData: o } = t, a = ((v = o.arrow) == null ? void 0 : v.centerOffset) !== 0, s = a ? 0 : e.arrowWidth, l = a ? 0 : e.arrowHeight, [u, p] = As(n), d = { start: "0%", center: "50%", end: "100%" }[p], m = (((y = o.arrow) == null ? void 0 : y.x) ?? 0) + s / 2, h = (((w = o.arrow) == null ? void 0 : w.y) ?? 0) + l / 2;
    let b = "", g = "";
    return u === "bottom" ? (b = a ? d : `${m}px`, g = `${-l}px`) : u === "top" ? (b = a ? d : `${m}px`, g = `${r.floating.height + l}px`) : u === "right" ? (b = `${-l}px`, g = a ? d : `${h}px`) : u === "left" && (b = `${r.floating.width + l}px`, g = a ? d : `${h}px`), { data: { x: b, y: g } };
  }
});
function As(e) {
  const [t, n = "center"] = e.split("-");
  return [t, n];
}
var dm = Es, fm = Ns, pm = Rs, mm = Ps;
// @__NO_SIDE_EFFECTS__
function gm(e) {
  const t = /* @__PURE__ */ hm(e), n = c.forwardRef((r, o) => {
    const { children: i, ...a } = r, s = c.Children.toArray(i), l = s.find(bm);
    if (l) {
      const u = l.props.children, p = s.map((d) => d === l ? c.Children.count(u) > 1 ? c.Children.only(null) : c.isValidElement(u) ? u.props.children : null : d);
      return /* @__PURE__ */ f(t, { ...a, ref: o, children: c.isValidElement(u) ? c.cloneElement(u, void 0, p) : null });
    }
    return /* @__PURE__ */ f(t, { ...a, ref: o, children: i });
  });
  return n.displayName = `${e}.Slot`, n;
}
// @__NO_SIDE_EFFECTS__
function hm(e) {
  const t = c.forwardRef((n, r) => {
    const { children: o, ...i } = n;
    if (c.isValidElement(o)) {
      const a = xm(o), s = ym(i, o.props);
      return o.type !== c.Fragment && (s.ref = r ? Y(r, a) : a), c.cloneElement(o, s);
    }
    return c.Children.count(o) > 1 ? c.Children.only(null) : null;
  });
  return t.displayName = `${e}.SlotClone`, t;
}
var ks = Symbol("radix.slottable");
// @__NO_SIDE_EFFECTS__
function vm(e) {
  const t = ({ children: n }) => /* @__PURE__ */ f(G, { children: n });
  return t.displayName = `${e}.Slottable`, t.__radixId = ks, t;
}
function bm(e) {
  return c.isValidElement(e) && typeof e.type == "function" && "__radixId" in e.type && e.type.__radixId === ks;
}
function ym(e, t) {
  const n = { ...t };
  for (const r in t) {
    const o = e[r], i = t[r];
    /^on[A-Z]/.test(r) ? o && i ? n[r] = (...s) => {
      const l = i(...s);
      return o(...s), l;
    } : o && (n[r] = o) : r === "style" ? n[r] = { ...o, ...i } : r === "className" && (n[r] = [o, i].filter(Boolean).join(" "));
  }
  return { ...e, ...n };
}
function xm(e) {
  var r, o;
  let t = (r = Object.getOwnPropertyDescriptor(e.props, "ref")) == null ? void 0 : r.get, n = t && "isReactWarning" in t && t.isReactWarning;
  return n ? e.ref : (t = (o = Object.getOwnPropertyDescriptor(e, "ref")) == null ? void 0 : o.get, n = t && "isReactWarning" in t && t.isReactWarning, n ? e.props.ref : e.props.ref || e.ref);
}
var wm = [
  "a",
  "button",
  "div",
  "form",
  "h2",
  "h3",
  "img",
  "input",
  "label",
  "li",
  "nav",
  "ol",
  "p",
  "select",
  "span",
  "svg",
  "ul"
], Cm = wm.reduce((e, t) => {
  const n = /* @__PURE__ */ gm(`Primitive.${t}`), r = c.forwardRef((o, i) => {
    const { asChild: a, ...s } = o, l = a ? n : t;
    return typeof window < "u" && (window[Symbol.for("radix-ui")] = !0), /* @__PURE__ */ f(l, { ...s, ref: i });
  });
  return r.displayName = `Primitive.${t}`, { ...e, [t]: r };
}, {}), [Dt] = Pf("Tooltip", [
  ws
]), Mt = ws(), _s = "TooltipProvider", Em = 700, pn = "tooltip.open", [Sm, Hn] = Dt(_s), Os = (e) => {
  const {
    __scopeTooltip: t,
    delayDuration: n = Em,
    skipDelayDuration: r = 300,
    disableHoverableContent: o = !1,
    children: i
  } = e, a = c.useRef(!0), s = c.useRef(!1), l = c.useRef(0);
  return c.useEffect(() => {
    const u = l.current;
    return () => window.clearTimeout(u);
  }, []), /* @__PURE__ */ f(
    Sm,
    {
      scope: t,
      isOpenDelayedRef: a,
      delayDuration: n,
      onOpen: c.useCallback(() => {
        window.clearTimeout(l.current), a.current = !1;
      }, []),
      onClose: c.useCallback(() => {
        window.clearTimeout(l.current), l.current = window.setTimeout(
          () => a.current = !0,
          r
        );
      }, [r]),
      isPointerInTransitRef: s,
      onPointerInTransitChange: c.useCallback((u) => {
        s.current = u;
      }, []),
      disableHoverableContent: o,
      children: i
    }
  );
};
Os.displayName = _s;
var Ke = "Tooltip", [Nm, Lt] = Dt(Ke), $s = (e) => {
  const {
    __scopeTooltip: t,
    children: n,
    open: r,
    defaultOpen: o,
    onOpenChange: i,
    disableHoverableContent: a,
    delayDuration: s
  } = e, l = Hn(Ke, e.__scopeTooltip), u = Mt(t), [p, d] = c.useState(null), m = ke(), h = c.useRef(0), b = a ?? l.disableHoverableContent, g = s ?? l.delayDuration, v = c.useRef(!1), [y, w] = Me({
    prop: r,
    defaultProp: o ?? !1,
    onChange: (R) => {
      R ? (l.onOpen(), document.dispatchEvent(new CustomEvent(pn))) : l.onClose(), i == null || i(R);
    },
    caller: Ke
  }), C = c.useMemo(() => y ? v.current ? "delayed-open" : "instant-open" : "closed", [y]), x = c.useCallback(() => {
    window.clearTimeout(h.current), h.current = 0, v.current = !1, w(!0);
  }, [w]), E = c.useCallback(() => {
    window.clearTimeout(h.current), h.current = 0, w(!1);
  }, [w]), N = c.useCallback(() => {
    window.clearTimeout(h.current), h.current = window.setTimeout(() => {
      v.current = !0, w(!0), h.current = 0;
    }, g);
  }, [g, w]);
  return c.useEffect(() => () => {
    h.current && (window.clearTimeout(h.current), h.current = 0);
  }, []), /* @__PURE__ */ f(dm, { ...u, children: /* @__PURE__ */ f(
    Nm,
    {
      scope: t,
      contentId: m,
      open: y,
      stateAttribute: C,
      trigger: p,
      onTriggerChange: d,
      onTriggerEnter: c.useCallback(() => {
        l.isOpenDelayedRef.current ? N() : x();
      }, [l.isOpenDelayedRef, N, x]),
      onTriggerLeave: c.useCallback(() => {
        b ? E() : (window.clearTimeout(h.current), h.current = 0);
      }, [E, b]),
      onOpen: x,
      onClose: E,
      disableHoverableContent: b,
      children: n
    }
  ) });
};
$s.displayName = Ke;
var mn = "TooltipTrigger", Is = c.forwardRef(
  (e, t) => {
    const { __scopeTooltip: n, ...r } = e, o = Lt(mn, n), i = Hn(mn, n), a = Mt(n), s = c.useRef(null), l = U(t, s, o.onTriggerChange), u = c.useRef(!1), p = c.useRef(!1), d = c.useCallback(() => u.current = !1, []);
    return c.useEffect(() => () => document.removeEventListener("pointerup", d), [d]), /* @__PURE__ */ f(fm, { asChild: !0, ...a, children: /* @__PURE__ */ f(
      Cm.button,
      {
        "aria-describedby": o.open ? o.contentId : void 0,
        "data-state": o.stateAttribute,
        ...r,
        ref: l,
        onPointerMove: F(e.onPointerMove, (m) => {
          m.pointerType !== "touch" && !p.current && !i.isPointerInTransitRef.current && (o.onTriggerEnter(), p.current = !0);
        }),
        onPointerLeave: F(e.onPointerLeave, () => {
          o.onTriggerLeave(), p.current = !1;
        }),
        onPointerDown: F(e.onPointerDown, () => {
          o.open && o.onClose(), u.current = !0, document.addEventListener("pointerup", d, { once: !0 });
        }),
        onFocus: F(e.onFocus, () => {
          u.current || o.onOpen();
        }),
        onBlur: F(e.onBlur, o.onClose),
        onClick: F(e.onClick, o.onClose)
      }
    ) });
  }
);
Is.displayName = mn;
var Rm = "TooltipPortal", [hg, Tm] = Dt(Rm, {
  forceMount: void 0
}), Ie = "TooltipContent", Ds = c.forwardRef(
  (e, t) => {
    const n = Tm(Ie, e.__scopeTooltip), { forceMount: r = n.forceMount, side: o = "top", ...i } = e, a = Lt(Ie, e.__scopeTooltip);
    return /* @__PURE__ */ f(we, { present: r || a.open, children: a.disableHoverableContent ? /* @__PURE__ */ f(Ms, { side: o, ...i, ref: t }) : /* @__PURE__ */ f(Pm, { side: o, ...i, ref: t }) });
  }
), Pm = c.forwardRef((e, t) => {
  const n = Lt(Ie, e.__scopeTooltip), r = Hn(Ie, e.__scopeTooltip), o = c.useRef(null), i = U(t, o), [a, s] = c.useState(null), { trigger: l, onClose: u } = n, p = o.current, { onPointerInTransitChange: d } = r, m = c.useCallback(() => {
    s(null), d(!1);
  }, [d]), h = c.useCallback(
    (b, g) => {
      const v = b.currentTarget, y = { x: b.clientX, y: b.clientY }, w = $m(y, v.getBoundingClientRect()), C = Im(y, w), x = Dm(g.getBoundingClientRect()), E = Lm([...C, ...x]);
      s(E), d(!0);
    },
    [d]
  );
  return c.useEffect(() => () => m(), [m]), c.useEffect(() => {
    if (l && p) {
      const b = (v) => h(v, p), g = (v) => h(v, l);
      return l.addEventListener("pointerleave", b), p.addEventListener("pointerleave", g), () => {
        l.removeEventListener("pointerleave", b), p.removeEventListener("pointerleave", g);
      };
    }
  }, [l, p, h, m]), c.useEffect(() => {
    if (a) {
      const b = (g) => {
        const v = g.target, y = { x: g.clientX, y: g.clientY }, w = (l == null ? void 0 : l.contains(v)) || (p == null ? void 0 : p.contains(v)), C = !Mm(y, a);
        w ? m() : C && (m(), u());
      };
      return document.addEventListener("pointermove", b), () => document.removeEventListener("pointermove", b);
    }
  }, [l, p, a, u, m]), /* @__PURE__ */ f(Ms, { ...e, ref: i });
}), [Am, km] = Dt(Ke, { isInside: !1 }), _m = /* @__PURE__ */ vm("TooltipContent"), Ms = c.forwardRef(
  (e, t) => {
    const {
      __scopeTooltip: n,
      children: r,
      "aria-label": o,
      onEscapeKeyDown: i,
      onPointerDownOutside: a,
      ...s
    } = e, l = Lt(Ie, n), u = Mt(n), { onClose: p } = l;
    return c.useEffect(() => (document.addEventListener(pn, p), () => document.removeEventListener(pn, p)), [p]), c.useEffect(() => {
      if (l.trigger) {
        const d = (m) => {
          const h = m.target;
          h != null && h.contains(l.trigger) && p();
        };
        return window.addEventListener("scroll", d, { capture: !0 }), () => window.removeEventListener("scroll", d, { capture: !0 });
      }
    }, [l.trigger, p]), /* @__PURE__ */ f(
      Rt,
      {
        asChild: !0,
        disableOutsidePointerEvents: !1,
        onEscapeKeyDown: i,
        onPointerDownOutside: a,
        onFocusOutside: (d) => d.preventDefault(),
        onDismiss: p,
        children: /* @__PURE__ */ S(
          pm,
          {
            "data-state": l.stateAttribute,
            ...u,
            ...s,
            ref: t,
            style: {
              ...s.style,
              "--radix-tooltip-content-transform-origin": "var(--radix-popper-transform-origin)",
              "--radix-tooltip-content-available-width": "var(--radix-popper-available-width)",
              "--radix-tooltip-content-available-height": "var(--radix-popper-available-height)",
              "--radix-tooltip-trigger-width": "var(--radix-popper-anchor-width)",
              "--radix-tooltip-trigger-height": "var(--radix-popper-anchor-height)"
            },
            children: [
              /* @__PURE__ */ f(_m, { children: r }),
              /* @__PURE__ */ f(Am, { scope: n, isInside: !0, children: /* @__PURE__ */ f(qd, { id: l.contentId, role: "tooltip", children: o || r }) })
            ]
          }
        )
      }
    );
  }
);
Ds.displayName = Ie;
var Ls = "TooltipArrow", Om = c.forwardRef(
  (e, t) => {
    const { __scopeTooltip: n, ...r } = e, o = Mt(n);
    return km(
      Ls,
      n
    ).isInside ? null : /* @__PURE__ */ f(mm, { ...o, ...r, ref: t });
  }
);
Om.displayName = Ls;
function $m(e, t) {
  const n = Math.abs(t.top - e.y), r = Math.abs(t.bottom - e.y), o = Math.abs(t.right - e.x), i = Math.abs(t.left - e.x);
  switch (Math.min(n, r, o, i)) {
    case i:
      return "left";
    case o:
      return "right";
    case n:
      return "top";
    case r:
      return "bottom";
    default:
      throw new Error("unreachable");
  }
}
function Im(e, t, n = 5) {
  const r = [];
  switch (t) {
    case "top":
      r.push(
        { x: e.x - n, y: e.y + n },
        { x: e.x + n, y: e.y + n }
      );
      break;
    case "bottom":
      r.push(
        { x: e.x - n, y: e.y - n },
        { x: e.x + n, y: e.y - n }
      );
      break;
    case "left":
      r.push(
        { x: e.x + n, y: e.y - n },
        { x: e.x + n, y: e.y + n }
      );
      break;
    case "right":
      r.push(
        { x: e.x - n, y: e.y - n },
        { x: e.x - n, y: e.y + n }
      );
      break;
  }
  return r;
}
function Dm(e) {
  const { top: t, right: n, bottom: r, left: o } = e;
  return [
    { x: o, y: t },
    { x: n, y: t },
    { x: n, y: r },
    { x: o, y: r }
  ];
}
function Mm(e, t) {
  const { x: n, y: r } = e;
  let o = !1;
  for (let i = 0, a = t.length - 1; i < t.length; a = i++) {
    const s = t[i], l = t[a], u = s.x, p = s.y, d = l.x, m = l.y;
    p > r != m > r && n < (d - u) * (r - p) / (m - p) + u && (o = !o);
  }
  return o;
}
function Lm(e) {
  const t = e.slice();
  return t.sort((n, r) => n.x < r.x ? -1 : n.x > r.x ? 1 : n.y < r.y ? -1 : n.y > r.y ? 1 : 0), Fm(t);
}
function Fm(e) {
  if (e.length <= 1) return e.slice();
  const t = [];
  for (let r = 0; r < e.length; r++) {
    const o = e[r];
    for (; t.length >= 2; ) {
      const i = t[t.length - 1], a = t[t.length - 2];
      if ((i.x - a.x) * (o.y - a.y) >= (i.y - a.y) * (o.x - a.x)) t.pop();
      else break;
    }
    t.push(o);
  }
  t.pop();
  const n = [];
  for (let r = e.length - 1; r >= 0; r--) {
    const o = e[r];
    for (; n.length >= 2; ) {
      const i = n[n.length - 1], a = n[n.length - 2];
      if ((i.x - a.x) * (o.y - a.y) >= (i.y - a.y) * (o.x - a.x)) n.pop();
      else break;
    }
    n.push(o);
  }
  return n.pop(), t.length === 1 && n.length === 1 && t[0].x === n[0].x && t[0].y === n[0].y ? t : t.concat(n);
}
var Vm = Os, Wm = $s, Bm = Is, Fs = Ds;
const jm = Vm, Ir = Wm, Dr = Bm, gn = c.forwardRef(({ className: e, sideOffset: t = 8, ...n }, r) => /* @__PURE__ */ f(
  Fs,
  {
    ref: r,
    sideOffset: t,
    collisionPadding: 16,
    avoidCollisions: !0,
    className: L(
      "z-50 overflow-hidden rounded-md glass-tooltip px-3 py-2.5 text-sm animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 origin-[--radix-tooltip-content-transform-origin]",
      e
    ),
    ...n
  }
));
gn.displayName = Fs.displayName;
const Hm = Lr(void 0), zm = () => {
  const e = Fr(Hm);
  if (e === void 0)
    throw new Error("useVerificationSyncContext must be used within a VerificationSyncProvider");
  return e;
}, Mr = (e, t = 500, n = !0) => {
  var u;
  const [r, o] = z(e), i = j(null), a = j(e), s = j(null), l = j(
    typeof window < "u" && ((u = window.matchMedia) == null ? void 0 : u.call(window, "(prefers-reduced-motion: reduce)").matches)
  );
  return ee(() => {
    if (!n || l.current) {
      o(e);
      return;
    }
    if (Math.abs(e - r) < 0.01)
      return;
    a.current = r, s.current = null;
    const p = (d) => {
      s.current === null && (s.current = d);
      const m = d - s.current, h = Math.min(m / t, 1), b = 1 - Math.pow(1 - h, 3), g = a.current + (e - a.current) * b;
      o(g), h < 1 ? i.current = requestAnimationFrame(p) : o(e);
    };
    return i.current = requestAnimationFrame(p), () => {
      i.current && cancelAnimationFrame(i.current);
    };
  }, [e, t, n]), r;
};
function vg({
  status: e,
  overallConfidence: t,
  verifiedTransactionPercentage: n,
  lastUpdated: r,
  trend: o,
  onRetry: i,
  className: a = ""
}) {
  const l = ((x) => x >= 85 ? "high" : x >= 70 ? "medium" : "low")(t), p = {
    high: {
      bg: "bg-green-50 dark:bg-green-950/30",
      border: "border-green-200 dark:border-green-800",
      text: "text-green-700 dark:text-green-400",
      icon: "text-green-600 dark:text-green-500",
      badge: "bg-green-100 dark:bg-green-900/50 text-green-800 dark:text-green-300"
    },
    medium: {
      bg: "bg-amber-50 dark:bg-amber-950/30",
      border: "border-amber-200 dark:border-amber-800",
      text: "text-amber-700 dark:text-amber-400",
      icon: "text-amber-600 dark:text-amber-500",
      badge: "bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300"
    },
    low: {
      bg: "bg-red-50 dark:bg-red-950/30",
      border: "border-red-200 dark:border-red-800",
      text: "text-red-700 dark:text-red-400",
      icon: "text-red-600 dark:text-red-500",
      badge: "bg-red-100 dark:bg-red-900/50 text-red-800 dark:text-red-300"
    }
  }[l], d = o === "increasing" ? "up" : o === "decreasing" ? "down" : "stable", m = {
    increasing: "text-green-600 dark:text-green-500",
    decreasing: "text-red-600 dark:text-red-500",
    stable: "text-muted-foreground"
  }, h = {
    increasing: "Improving",
    decreasing: "Declining",
    stable: "Stable"
  }, b = {
    high: "High accuracy",
    medium: "Medium accuracy",
    low: "Needs attention"
  }, { highlightedComponent: g, isAnimating: v } = zm(), y = Mr(
    t,
    500,
    v
  ), w = Mr(
    n,
    500,
    v
  ), C = g === "confidence" && v;
  return e !== "success" ? /* @__PURE__ */ f(
    "div",
    {
      className: `data-confidence-bar border-t border-b border-border bg-muted/30 py-4 px-6 ${a}`,
      role: "status",
      "aria-live": "polite",
      "aria-label": "Data confidence bar",
      "data-testid": "data-confidence-bar",
      "data-status": e,
      children: /* @__PURE__ */ f(
        In,
        {
          ...e === "error" ? {
            status: "error",
            message: "Failed to load confidence data",
            onRetry: i,
            skeletonVariant: "card"
          } : e === "empty" ? {
            status: "empty",
            message: "No confidence data available",
            skeletonVariant: "card"
          } : {
            status: "loading",
            skeletonVariant: "card"
          }
        }
      )
    }
  ) : /* @__PURE__ */ f(jm, { children: /* @__PURE__ */ f(
    "div",
    {
      className: `data-confidence-bar ${p.bg} border-t ${p.border} border-b py-4 px-6
                    transition-colors duration-300 ease-in-out
                    ${C ? "ring-4 ring-blue-300 ring-opacity-50 animate-pulse-once" : ""}
                    ${a}`,
      role: "status",
      "aria-live": "polite",
      "aria-label": `Data confidence: ${t}%, trend ${o}`,
      "data-testid": "data-confidence-bar",
      "data-status": "success",
      "data-protected-zone": "verification-status",
      children: /* @__PURE__ */ S("div", { className: "flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4", children: [
        /* @__PURE__ */ S("div", { className: "flex items-start lg:items-center gap-4", children: [
          /* @__PURE__ */ f(
            Cr,
            {
              size: 24,
              confidence: l,
              "aria-label": `${l} confidence level`,
              className: "flex-shrink-0 mt-1 lg:mt-0",
              "data-testid": "icon-integrity-seal"
            }
          ),
          /* @__PURE__ */ S("div", { className: "flex-1 min-w-0", children: [
            /* @__PURE__ */ S(Ir, { children: [
              /* @__PURE__ */ f(Dr, { asChild: !0, children: /* @__PURE__ */ S("div", { className: "flex flex-wrap items-center gap-2 mb-1.5 cursor-help", children: [
                /* @__PURE__ */ S("h3", { className: `text-base font-semibold ${p.text} tabular-nums`, "data-testid": "text-confidence-status", children: [
                  "Verification Status: ",
                  Math.round(y),
                  "% Data Confidence"
                ] }),
                /* @__PURE__ */ S(
                  "div",
                  {
                    className: "flex items-center gap-1",
                    "data-testid": "trend-indicator",
                    children: [
                      /* @__PURE__ */ f(
                        Tf,
                        {
                          size: 16,
                          direction: d,
                          "aria-label": `Trend: ${h[o]}`
                        }
                      ),
                      /* @__PURE__ */ f("span", { className: `text-xs font-medium ${m[o]} hidden sm:inline`, children: h[o] })
                    ]
                  }
                )
              ] }) }),
              /* @__PURE__ */ f(
                gn,
                {
                  className: "max-w-md p-4 bg-gray-900 text-white rounded-lg shadow-xl",
                  sideOffset: 8,
                  side: "bottom",
                  children: /* @__PURE__ */ S("div", { className: "space-y-3", children: [
                    /* @__PURE__ */ S("div", { className: "flex items-center gap-2", children: [
                      /* @__PURE__ */ f(Cr, { size: 20, confidence: "high", "aria-label": "Data confidence", className: "flex-shrink-0" }),
                      /* @__PURE__ */ f("p", { className: "font-semibold text-blue-100", children: "Data Confidence Score" })
                    ] }),
                    /* @__PURE__ */ S("p", { className: "text-gray-200 leading-relaxed", children: [
                      "This score represents the ",
                      /* @__PURE__ */ f("strong", { className: "text-white", children: "overall reliability of your revenue data" }),
                      " based on platform reconciliation completeness, match accuracy, and data freshness."
                    ] }),
                    /* @__PURE__ */ S("div", { className: "space-y-2", children: [
                      /* @__PURE__ */ f("p", { className: "text-xs font-medium text-gray-300", children: "Score Interpretation:" }),
                      /* @__PURE__ */ S("div", { className: "space-y-1.5 text-xs", children: [
                        /* @__PURE__ */ S("div", { className: "flex items-center gap-2", children: [
                          /* @__PURE__ */ f("div", { className: "w-2 h-2 rounded-full bg-green-500" }),
                          /* @__PURE__ */ S("span", { className: "text-gray-300", children: [
                            /* @__PURE__ */ f("strong", { className: "text-green-400", children: "85-100%:" }),
                            " High confidence — Safe for strategic decisions"
                          ] })
                        ] }),
                        /* @__PURE__ */ S("div", { className: "flex items-center gap-2", children: [
                          /* @__PURE__ */ f("div", { className: "w-2 h-2 rounded-full bg-amber-500" }),
                          /* @__PURE__ */ S("span", { className: "text-gray-300", children: [
                            /* @__PURE__ */ f("strong", { className: "text-amber-400", children: "70-84%:" }),
                            " Medium confidence — Use with caution"
                          ] })
                        ] }),
                        /* @__PURE__ */ S("div", { className: "flex items-center gap-2", children: [
                          /* @__PURE__ */ f("div", { className: "w-2 h-2 rounded-full bg-red-500" }),
                          /* @__PURE__ */ S("span", { className: "text-gray-300", children: [
                            /* @__PURE__ */ f("strong", { className: "text-red-400", children: "<70%:" }),
                            " Low confidence — Wait for verification"
                          ] })
                        ] })
                      ] })
                    ] }),
                    /* @__PURE__ */ f("div", { className: "pt-3 border-t border-gray-700", children: /* @__PURE__ */ S("p", { className: "text-xs text-gray-400 leading-relaxed", children: [
                      o === "increasing" && /* @__PURE__ */ S(G, { children: [
                        /* @__PURE__ */ f("strong", { className: "text-green-400", children: "Increasing:" }),
                        " More transactions are being verified over time"
                      ] }),
                      o === "decreasing" && /* @__PURE__ */ S(G, { children: [
                        /* @__PURE__ */ f("strong", { className: "text-red-400", children: "Decreasing:" }),
                        " New unverified transactions are outpacing verification"
                      ] }),
                      o === "stable" && /* @__PURE__ */ S(G, { children: [
                        /* @__PURE__ */ f("strong", { className: "text-gray-300", children: "Stable:" }),
                        " Verification rate is maintaining consistent levels"
                      ] })
                    ] }) })
                  ] })
                }
              )
            ] }),
            /* @__PURE__ */ S("div", { className: "flex flex-wrap items-center gap-x-4 gap-y-2", children: [
              /* @__PURE__ */ S(Ir, { children: [
                /* @__PURE__ */ f(Dr, { asChild: !0, children: /* @__PURE__ */ f("div", { className: "flex items-center gap-1.5", children: /* @__PURE__ */ S("span", { className: "text-xs text-muted-foreground cursor-help tabular-nums", "data-testid": "text-verification-rate", children: [
                  Math.round(w),
                  "% of transactions fully verified"
                ] }) }) }),
                /* @__PURE__ */ S(
                  gn,
                  {
                    className: "max-w-xs p-3 bg-gray-900 text-white rounded-lg shadow-xl",
                    sideOffset: 5,
                    side: "bottom",
                    children: [
                      /* @__PURE__ */ S("p", { className: "text-gray-200 leading-relaxed", children: [
                        "This represents the ",
                        /* @__PURE__ */ f("strong", { className: "text-white", children: "percentage of individual transactions" }),
                        " that have been matched with platform records, not the revenue dollar amount."
                      ] }),
                      /* @__PURE__ */ f("p", { className: "text-xs text-gray-400 mt-2", children: "Example: If you have 100 transactions totaling $10,000, and 45 transactions worth $9,000 are verified, this would show 45% (not 90%)." })
                    ]
                  }
                )
              ] }),
              /* @__PURE__ */ f("div", { className: "flex items-center gap-1.5", children: /* @__PURE__ */ f(ka, { variant: "secondary", className: `rounded-full ${p.badge}`, "data-testid": "badge-accuracy", children: b[l] }) })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ S("div", { className: "flex items-center text-xs text-muted-foreground lg:ml-auto flex-shrink-0", "data-testid": "text-last-updated", children: [
          /* @__PURE__ */ f(vc, { className: "w-3.5 h-3.5 mr-1.5", "aria-hidden": "true" }),
          /* @__PURE__ */ S("span", { children: [
            /* @__PURE__ */ f("span", { className: "hidden sm:inline", children: "Updated " }),
            /* @__PURE__ */ f("span", { className: "font-medium", children: r })
          ] })
        ] })
      ] })
    }
  ) });
}
const Um = (e, t) => ({
  high: `High confidence (${t}%, ≥70%). Attribution model shows strong statistical significance.`,
  medium: `Medium confidence (${t}%, 30-69%). Model indicates moderate correlation strength.`,
  low: `Low confidence (${t}%, <30%). Limited data or weak statistical patterns detected.`
})[e];
function Gm({ tier: e, score: t, visible: n, badgeRef: r, tooltipId: o }) {
  const [i, a] = z({ top: -9999, left: -9999, placement: "above", align: "center" }), [s, l] = z(!1), u = j(null), p = j(!1), d = j(!1), m = j();
  if (ee(() => {
    if (!n || !r.current || !u.current) {
      p.current = !1, l(!1);
      return;
    }
    if (p.current)
      return;
    p.current = !0;
    const b = () => {
      var _, I;
      const v = (_ = r.current) == null ? void 0 : _.getBoundingClientRect(), y = (I = u.current) == null ? void 0 : I.getBoundingClientRect();
      if (!v || !y) return;
      const w = window.innerWidth, C = 20, x = 10;
      let E = v.top - y.height - x - C, N = v.left + v.width / 2 - y.width / 2, R = "above", A = "center";
      E < 20 && (E = v.bottom + x + C, R = "below");
      const P = 20 + C;
      N < P ? (N = P, A = "left") : N + y.width > w - P && (N = w - y.width - P, A = "right"), a({ top: E, left: N, placement: R, align: A }), l(!0);
    };
    requestAnimationFrame(() => {
      b();
    });
    const g = () => {
      p.current && (d.current = !0, m.current && clearTimeout(m.current), requestAnimationFrame(() => {
        var _, I;
        const v = (_ = r.current) == null ? void 0 : _.getBoundingClientRect(), y = (I = u.current) == null ? void 0 : I.getBoundingClientRect();
        if (!v || !y) return;
        const w = window.innerWidth, C = 20, x = 10;
        let E = v.top - y.height - x - C, N = v.left + v.width / 2 - y.width / 2, R = "above", A = "center";
        E < 20 && (E = v.bottom + x + C, R = "below");
        const P = 20 + C;
        N < P ? (N = P, A = "left") : N + y.width > w - P && (N = w - y.width - P, A = "right"), a({ top: E, left: N, placement: R, align: A });
      }), m.current = window.setTimeout(() => {
        d.current = !1;
      }, 150));
    };
    return window.addEventListener("scroll", g, !0), () => {
      window.removeEventListener("scroll", g, !0), m.current && clearTimeout(m.current);
    };
  }, [n, r, e]), ee(() => {
    n || (p.current = !1, l(!1));
  }, [n]), !n) return null;
  const h = r.current ? r.current.getBoundingClientRect().left + r.current.getBoundingClientRect().width / 2 - i.left - 6 : 0;
  return Xs(
    /* @__PURE__ */ S(
      "div",
      {
        ref: u,
        id: o,
        role: "tooltip",
        className: "confidence-tooltip fixed px-4 py-3 rounded-lg max-w-[280px] pointer-events-none",
        style: {
          top: `${i.top}px`,
          left: `${i.left}px`,
          backgroundColor: "#1F2937",
          color: "#FFFFFF",
          zIndex: 9999,
          fontSize: "0.875rem",
          lineHeight: 1.6,
          opacity: s ? 1 : 0,
          boxShadow: "0 4px 16px 0 rgba(0, 0, 0, 0.3)"
        },
        "data-testid": "confidence-tooltip",
        "data-tooltip-tier": e,
        children: [
          Um(e, t),
          /* @__PURE__ */ f(
            "div",
            {
              className: "absolute",
              style: {
                left: `${h}px`,
                [i.placement === "above" ? "bottom" : "top"]: "-6px",
                width: 0,
                height: 0,
                borderLeft: "6px solid transparent",
                borderRight: "6px solid transparent",
                [i.placement === "above" ? "borderTop" : "borderBottom"]: "6px solid #1F2937"
              }
            }
          )
        ]
      }
    ),
    document.body
  );
}
const Km = (e) => e >= 70 ? "high" : e >= 30 ? "medium" : "low", qm = (e) => ({
  high: "var(--confidence-tier-high)",
  medium: "var(--confidence-tier-medium)",
  low: "var(--confidence-tier-low)"
})[e], Ym = (e) => ({
  high: "14, 133, 60",
  // hsl(142, 76%, 28%) for light mode
  medium: "136, 92, 4",
  // hsl(38, 95%, 28%) for light mode  
  low: "185, 28, 28"
  // hsl(0, 84%, 40%) for light mode
})[e];
function bg({ score: e, className: t = "" }) {
  const n = typeof e == "number" && !isNaN(e) ? Math.max(0, Math.min(100, e)) : null, [r, o] = z(0), [i, a] = z(!1), [s, l] = z(!1), [u, p] = z(!1), d = j(null), m = j(), h = j(), b = j(), g = j(0), v = qs(), y = n !== null ? Km(n) : "low", w = qm(y), C = Ym(y);
  ee(() => {
    if (!(!d.current || n === null))
      return b.current = new IntersectionObserver(
        ([_]) => l(_.isIntersecting),
        { threshold: 0.1 }
      ), b.current.observe(d.current), () => {
        var _;
        return (_ = b.current) == null ? void 0 : _.disconnect();
      };
  }, [n]), ee(() => {
    if (!s || n === null) return;
    h.current && cancelAnimationFrame(h.current), p(!0);
    const _ = performance.now(), I = 600, k = g.current, V = (T) => {
      const M = T - _, O = Math.min(M / I, 1), W = 1 - Math.pow(1 - O, 3), $ = Math.floor(k + (n - k) * W);
      g.current = $, o($), O < 1 ? h.current = requestAnimationFrame(V) : p(!1);
    };
    return h.current = requestAnimationFrame(V), () => {
      h.current && (cancelAnimationFrame(h.current), h.current = void 0);
    };
  }, [s, n]), ee(() => () => {
    m.current && clearTimeout(m.current), h.current && cancelAnimationFrame(h.current);
  }, []);
  const x = (_) => {
    m.current && clearTimeout(m.current), m.current = window.setTimeout(() => {
      a(!0);
    }, 150);
  }, E = (_) => {
    m.current && clearTimeout(m.current), m.current = window.setTimeout(() => {
      a(!1);
    }, 200);
  }, N = () => a(!0), R = () => a(!1), A = (_) => {
    _.key === "Escape" && a(!1);
  };
  if (n === null)
    return /* @__PURE__ */ f("span", { className: "text-sm text-muted-foreground", children: "—" });
  const P = u ? "off" : "polite";
  return /* @__PURE__ */ S(G, { children: [
    /* @__PURE__ */ S(
      "div",
      {
        ref: d,
        className: `confidence-badge inline-flex items-center gap-2 px-3.5 py-1.5 rounded-[20px] border min-w-[80px] h-8 cursor-help ${t}`,
        style: {
          backgroundColor: "var(--confidence-badge-bg)",
          backdropFilter: "blur(var(--confidence-badge-blur))",
          borderColor: `rgba(${C}, 0.3)`,
          boxShadow: `0 2px 12px rgba(${C}, 0.15)`,
          background: `linear-gradient(rgba(${C}, 0.12), rgba(${C}, 0.12)), var(--confidence-badge-bg)`
        },
        "aria-label": `Confidence score: ${n}%, ${y} confidence`,
        "aria-describedby": i ? v : void 0,
        "aria-live": P,
        onMouseEnter: x,
        onMouseLeave: E,
        onFocus: N,
        onBlur: R,
        onKeyDown: A,
        tabIndex: 0,
        "data-testid": `confidence-badge-${y}`,
        "data-tier": y,
        "data-score": n,
        children: [
          /* @__PURE__ */ f(
            "div",
            {
              className: `tier-dot ${y === "high" ? "tier-dot-high" : ""} w-2 h-2 rounded-full`,
              style: { backgroundColor: w },
              "data-testid": `tier-dot-${y}`
            }
          ),
          /* @__PURE__ */ S(
            "span",
            {
              className: "confidence-percentage text-sm font-bold",
              style: { color: w, letterSpacing: "-0.5px" },
              "data-testid": "confidence-percentage",
              children: [
                r,
                "%"
              ]
            }
          )
        ]
      }
    ),
    /* @__PURE__ */ f(
      Gm,
      {
        tier: y,
        score: n,
        visible: i,
        badgeRef: d,
        tooltipId: v
      }
    )
  ] });
}
function yg({
  action: e,
  selectedCount: t,
  selectedTransactions: n,
  onConfirm: r,
  onCancel: o
}) {
  const [i, a] = z(""), [s, l] = z(""), [u, p] = z(""), [d, m] = z({}), b = {
    mark_reviewed: {
      title: "Mark as Reviewed",
      icon: uo,
      iconColor: "text-green-600 dark:text-green-500",
      bgColor: "bg-green-50 dark:bg-green-950/30",
      description: `Mark ${t} transaction${t !== 1 ? "s" : ""} as reviewed. These transactions will be considered verified and won't count toward variance.`,
      warningText: "This action will update reconciliation status and may affect overall match percentage.",
      confirmButton: "Mark as Reviewed",
      confirmColor: "bg-green-600 hover:bg-green-700 dark:bg-green-700 dark:hover:bg-green-800"
    },
    flag_investigation: {
      title: "Flag for Investigation",
      icon: fo,
      iconColor: "text-amber-600 dark:text-amber-500",
      bgColor: "bg-amber-50 dark:bg-amber-950/30",
      description: `Flag ${t} transaction${t !== 1 ? "s" : ""} for manual investigation. These will remain in the unmatched list until resolved.`,
      warningText: "Flagged transactions require follow-up action before reconciliation can complete.",
      confirmButton: "Flag Transactions",
      confirmColor: "bg-amber-600 hover:bg-amber-700 dark:bg-amber-700 dark:hover:bg-amber-800"
    },
    exclude_variance: {
      title: "Exclude from Variance Calculation",
      icon: lo,
      iconColor: "text-gray-600 dark:text-gray-400",
      bgColor: "bg-gray-50 dark:bg-gray-950/30",
      description: `Exclude ${t} transaction${t !== 1 ? "s" : ""} from variance calculations. Use this for known exceptions or legacy data.`,
      warningText: "Excluded transactions will not appear in future reconciliation reports.",
      confirmButton: "Exclude Transactions",
      confirmColor: "bg-gray-600 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-800"
    },
    assign_user: {
      title: "Assign for Investigation",
      icon: po,
      iconColor: "text-blue-600 dark:text-blue-400",
      bgColor: "bg-blue-50 dark:bg-blue-950/30",
      description: `Assign ${t} transaction${t !== 1 ? "s" : ""} to a team member for investigation.`,
      warningText: "Assigned user will receive a notification with transaction details.",
      confirmButton: "Assign Transactions",
      confirmColor: "bg-blue-600 hover:bg-blue-700 dark:bg-blue-700 dark:hover:bg-blue-800"
    }
  }[e], g = b.icon, v = () => {
    const x = {};
    return e === "assign_user" ? s || (x.assignUser = "Please select a user to assign") : e === "exclude_variance" ? !u || u.trim().length === 0 ? x.reason = "Please provide a reason for exclusion" : u.trim().length < 10 && (x.reason = "Reason must be at least 10 characters") : e === "flag_investigation" && i && i.trim().length > 0 && i.trim().length < 10 && (x.notes = "Note must be at least 10 characters or empty"), m(x), Object.keys(x).length === 0;
  }, y = () => {
    if (!v())
      return;
    const x = {};
    e === "assign_user" && s && (x.assignedUserId = s), i && i.trim() && (x.notes = i.trim()), u && u.trim() && (x.reason = u.trim()), r(x);
  }, w = () => e === "assign_user" ? !!s : e === "exclude_variance" ? !!u && u.trim().length >= 10 : !(e === "flag_investigation" && i && i.trim().length > 0 && i.trim().length < 10), C = n.reduce((x, E) => x + E.amount_cents / 100, 0);
  return /* @__PURE__ */ f(Rd, { open: !0, onOpenChange: (x) => {
    x || o();
  }, children: /* @__PURE__ */ S(_i, { className: "max-w-2xl", "data-testid": "modal-bulk-action", children: [
    /* @__PURE__ */ S(Oi, { children: [
      /* @__PURE__ */ S("div", { className: "flex items-center space-x-3", children: [
        /* @__PURE__ */ f("div", { className: `p-2 rounded-md ${b.bgColor}`, children: /* @__PURE__ */ f(g, { className: `w-6 h-6 ${b.iconColor}` }) }),
        /* @__PURE__ */ f(Ii, { className: "text-xl", "data-testid": "text-modal-title", children: b.title })
      ] }),
      /* @__PURE__ */ f(Di, { "data-testid": "text-modal-description", children: b.description })
    ] }),
    /* @__PURE__ */ S("div", { className: "space-y-6", children: [
      /* @__PURE__ */ S("div", { className: "bg-muted/30 border border-border rounded-md p-4", children: [
        /* @__PURE__ */ f("h3", { className: "text-sm font-semibold text-foreground mb-3", children: "Selection Summary" }),
        /* @__PURE__ */ S("div", { className: "grid grid-cols-2 gap-4 text-sm", children: [
          /* @__PURE__ */ S("div", { children: [
            /* @__PURE__ */ f("span", { className: "text-muted-foreground", children: "Transactions:" }),
            /* @__PURE__ */ f("span", { className: "ml-2 font-semibold text-foreground", "data-testid": "text-summary-count", children: t })
          ] }),
          /* @__PURE__ */ S("div", { children: [
            /* @__PURE__ */ f("span", { className: "text-muted-foreground", children: "Total Amount:" }),
            /* @__PURE__ */ S("span", { className: "ml-2 font-semibold text-foreground", "data-testid": "text-summary-amount", children: [
              "$",
              C.toLocaleString("en-US", { minimumFractionDigits: 2 })
            ] })
          ] }),
          /* @__PURE__ */ S("div", { children: [
            /* @__PURE__ */ f("span", { className: "text-muted-foreground", children: "Platforms:" }),
            /* @__PURE__ */ f("span", { className: "ml-2 font-semibold text-foreground", "data-testid": "text-summary-platforms", children: [...new Set(n.map((x) => x.platform_name))].join(", ") })
          ] }),
          /* @__PURE__ */ S("div", { children: [
            /* @__PURE__ */ f("span", { className: "text-muted-foreground", children: "Date Range:" }),
            /* @__PURE__ */ S("span", { className: "ml-2 font-semibold text-foreground", "data-testid": "text-summary-date-range", children: [
              new Date(Math.min(...n.map((x) => new Date(x.timestamp).getTime()))).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
              " - ",
              new Date(Math.max(...n.map((x) => new Date(x.timestamp).getTime()))).toLocaleDateString("en-US", { month: "short", day: "numeric" })
            ] })
          ] })
        ] })
      ] }),
      e === "assign_user" && /* @__PURE__ */ S("div", { children: [
        /* @__PURE__ */ S(lt, { htmlFor: "assigned-user", className: "mb-2", children: [
          "Assign to Team Member ",
          /* @__PURE__ */ f("span", { className: "text-destructive", children: "*" })
        ] }),
        /* @__PURE__ */ S(
          "select",
          {
            id: "assigned-user",
            value: s,
            onChange: (x) => {
              l(x.target.value), m((E) => ({ ...E, assignUser: "" }));
            },
            className: `mt-2 flex h-9 w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background
                           focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2
                           ${d.assignUser ? "border-destructive" : "border-input"}`,
            "data-testid": "select-assign-user",
            children: [
              /* @__PURE__ */ f("option", { value: "", children: "Select team member..." }),
              /* @__PURE__ */ f("option", { value: "user1", children: "John Smith (Finance)" }),
              /* @__PURE__ */ f("option", { value: "user2", children: "Sarah Johnson (Accounting)" }),
              /* @__PURE__ */ f("option", { value: "user3", children: "Mike Chen (Operations)" })
            ]
          }
        ),
        d.assignUser && /* @__PURE__ */ f("p", { className: "mt-1 text-sm text-destructive", "data-testid": "error-assign-user", children: d.assignUser })
      ] }),
      (e === "flag_investigation" || e === "exclude_variance") && /* @__PURE__ */ S("div", { children: [
        /* @__PURE__ */ S(lt, { htmlFor: "reason", className: "mb-2", children: [
          "Reason ",
          e === "exclude_variance" && /* @__PURE__ */ f("span", { className: "text-destructive", children: "*" })
        ] }),
        /* @__PURE__ */ f(
          qr,
          {
            id: "reason",
            type: "text",
            value: u,
            onChange: (x) => {
              p(x.target.value), m((E) => ({ ...E, reason: "" }));
            },
            placeholder: "e.g., Legacy data from migration, Known refund processing delay",
            className: `mt-2 ${d.reason ? "border-destructive" : ""}`,
            required: e === "exclude_variance",
            "data-testid": "input-reason"
          }
        ),
        d.reason && /* @__PURE__ */ f("p", { className: "mt-1 text-sm text-destructive", "data-testid": "error-reason", children: d.reason })
      ] }),
      /* @__PURE__ */ S("div", { children: [
        /* @__PURE__ */ f(lt, { htmlFor: "notes", className: "mb-2", children: "Notes (Optional)" }),
        /* @__PURE__ */ f(
          Mi,
          {
            id: "notes",
            value: i,
            onChange: (x) => {
              a(x.target.value), m((E) => ({ ...E, notes: "" }));
            },
            rows: 3,
            placeholder: "Add any additional context or notes...",
            className: `mt-2 resize-none ${d.notes ? "border-destructive" : ""}`,
            "data-testid": "textarea-notes"
          }
        ),
        d.notes && /* @__PURE__ */ f("p", { className: "mt-1 text-sm text-destructive", "data-testid": "error-notes", children: d.notes })
      ] }),
      /* @__PURE__ */ S(mo, { className: "bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900", children: [
        /* @__PURE__ */ f(co, { className: "h-5 w-5 text-amber-600 dark:text-amber-500" }),
        /* @__PURE__ */ f(go, { className: "text-amber-800 dark:text-amber-200", "data-testid": "text-warning-message", children: b.warningText })
      ] })
    ] }),
    /* @__PURE__ */ S($i, { children: [
      /* @__PURE__ */ f(
        J,
        {
          variant: "outline",
          onClick: o,
          "data-testid": "button-cancel-action",
          children: "Cancel"
        }
      ),
      /* @__PURE__ */ f(
        J,
        {
          onClick: y,
          disabled: !w(),
          className: `text-white ${b.confirmColor}`,
          "data-testid": "button-confirm-action",
          children: b.confirmButton
        }
      )
    ] })
  ] }) });
}
function xg({
  selectedCount: e,
  selectedTotalAmount: t,
  onMarkReviewed: n,
  onFlagInvestigation: r,
  onExcludeVariance: o,
  onAssignUser: i,
  onExport: a,
  onClearSelection: s,
  isProcessing: l
}) {
  return /* @__PURE__ */ f("div", { className: "sticky top-0 z-10 bg-blue-600 dark:bg-blue-700 border-b border-blue-700 dark:border-blue-800 shadow-lg", children: /* @__PURE__ */ S("div", { className: "px-6 py-4 flex items-center justify-between", children: [
    /* @__PURE__ */ S("div", { className: "flex items-center space-x-4", children: [
      /* @__PURE__ */ S("div", { className: "text-white", children: [
        /* @__PURE__ */ f("span", { className: "font-semibold text-lg", "data-testid": "text-selected-count", children: e }),
        /* @__PURE__ */ S("span", { className: "ml-1 text-blue-100", children: [
          "transaction",
          e !== 1 ? "s" : "",
          " selected"
        ] })
      ] }),
      /* @__PURE__ */ f(tn, { orientation: "vertical", className: "h-6 bg-blue-400 dark:bg-blue-500" }),
      /* @__PURE__ */ S("div", { className: "text-white", children: [
        /* @__PURE__ */ S("span", { className: "font-semibold", "data-testid": "text-selected-amount", children: [
          "$",
          t.toLocaleString("en-US", { minimumFractionDigits: 2 })
        ] }),
        /* @__PURE__ */ f("span", { className: "ml-1 text-blue-100", children: "total amount" })
      ] })
    ] }),
    /* @__PURE__ */ f("div", { className: "flex items-center space-x-2", children: l ? /* @__PURE__ */ S("div", { className: "flex items-center space-x-2 text-white", "data-testid": "indicator-processing", children: [
      /* @__PURE__ */ f(xc, { className: "w-4 h-4 animate-spin" }),
      /* @__PURE__ */ f("span", { className: "text-sm", children: "Processing..." })
    ] }) : /* @__PURE__ */ S(G, { children: [
      /* @__PURE__ */ S(
        J,
        {
          variant: "secondary",
          size: "sm",
          className: "bg-white text-blue-600 border-transparent hover:bg-blue-50",
          onClick: n,
          "data-testid": "button-mark-reviewed",
          children: [
            /* @__PURE__ */ f(uo, {}),
            "Mark Reviewed"
          ]
        }
      ),
      /* @__PURE__ */ S(
        J,
        {
          variant: "ghost",
          size: "sm",
          className: "bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400",
          onClick: r,
          "data-testid": "button-flag-investigation",
          children: [
            /* @__PURE__ */ f(fo, {}),
            "Flag for Investigation"
          ]
        }
      ),
      /* @__PURE__ */ S(
        J,
        {
          variant: "ghost",
          size: "sm",
          className: "bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400",
          onClick: o,
          "data-testid": "button-exclude-variance",
          children: [
            /* @__PURE__ */ f(lo, {}),
            "Exclude from Variance"
          ]
        }
      ),
      /* @__PURE__ */ S(
        J,
        {
          variant: "ghost",
          size: "sm",
          className: "bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400",
          onClick: i,
          "data-testid": "button-assign-user",
          children: [
            /* @__PURE__ */ f(po, {}),
            "Assign"
          ]
        }
      ),
      /* @__PURE__ */ f(tn, { orientation: "vertical", className: "h-6 bg-blue-400 dark:bg-blue-500" }),
      /* @__PURE__ */ S(
        J,
        {
          variant: "ghost",
          size: "sm",
          className: "bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-400",
          onClick: a,
          title: "Export selected transactions to CSV",
          "data-testid": "button-export-selected",
          children: [
            /* @__PURE__ */ f(bc, {}),
            "Export"
          ]
        }
      ),
      /* @__PURE__ */ f(
        J,
        {
          variant: "ghost",
          size: "icon",
          className: "text-white hover:bg-blue-500",
          onClick: s,
          title: "Clear selection",
          "data-testid": "button-clear-selection",
          children: /* @__PURE__ */ f(Et, { className: "w-5 h-5" })
        }
      )
    ] }) })
  ] }) });
}
const Xm = {
  info: {
    icon: yc,
    role: "status",
    ariaLive: "polite",
    duration: 5e3,
    borderColor: "hsl(var(--brand-tufts))",
    iconColor: "hsl(var(--brand-tufts))"
  },
  warning: {
    icon: co,
    role: "status",
    ariaLive: "polite",
    duration: 8e3,
    borderColor: "hsl(var(--brand-warning))",
    iconColor: "hsl(var(--brand-warning))"
  },
  error: {
    icon: ao,
    role: "alert",
    ariaLive: "assertive",
    duration: 1e4,
    borderColor: "hsl(var(--destructive))",
    iconColor: "hsl(var(--destructive))"
  },
  critical: {
    icon: Cc,
    role: "alert",
    ariaLive: "assertive",
    duration: 0,
    borderColor: "hsl(var(--brand-critical))",
    iconColor: "hsl(var(--brand-critical))"
  }
}, Zm = { info: 5e3, warning: 7e3, error: 1e4, critical: null };
function Qm({ severity: e = "info", timeoutMs: t, onDismiss: n, onPause: r, onResume: o }) {
  const i = t !== void 0 ? t === 0 ? null : t : Zm[e], a = j(null), s = j(n), l = j(0), u = j(0), p = j(!1), d = j(null), m = j(null), h = j(!1), [b, g] = z(0), [v, y] = z(i ?? 0), [w, C] = z(!1);
  ee(() => {
    s.current = n;
  }, [n]);
  const x = Ce(() => {
    if (!i || p.current) return;
    const P = performance.now() - l.current;
    g(Math.min(P / i, 1)), y(Math.max(i - P, 0)), P < i && (m.current = requestAnimationFrame(x));
  }, [i]), E = Ce(() => {
    !i || p.current || (d.current && clearTimeout(d.current), m.current && cancelAnimationFrame(m.current), u.current = performance.now() - l.current, p.current = !0, C(!0), r == null || r());
  }, [i, r]), N = Ce(() => {
    !i || !p.current || (l.current = performance.now() - u.current, p.current = !1, C(!1), d.current = setTimeout(() => !h.current && (h.current = !0, s.current()), i - u.current), m.current = requestAnimationFrame(x), o == null || o());
  }, [i, x, o]), R = Ce(() => {
    i && (d.current && clearTimeout(d.current), m.current && cancelAnimationFrame(m.current), h.current = !1, u.current = 0, p.current = !1, g(0), y(i), C(!1), l.current = performance.now(), d.current = setTimeout(() => !h.current && (h.current = !0, s.current()), i), m.current = requestAnimationFrame(x));
  }, [i, x]), A = Ce(() => {
    d.current && clearTimeout(d.current), m.current && cancelAnimationFrame(m.current), h.current = !0;
  }, []);
  return ee(() => {
    if (i)
      return l.current = performance.now(), d.current = setTimeout(() => !h.current && (h.current = !0, s.current()), i), m.current = requestAnimationFrame(x), () => {
        d.current && clearTimeout(d.current), m.current && cancelAnimationFrame(m.current);
      };
  }, [i, x]), ee(() => {
    const P = a.current;
    if (P)
      return P.addEventListener("mouseenter", E), P.addEventListener("mouseleave", N), P.addEventListener("focusin", E), P.addEventListener("focusout", N), () => {
        P.removeEventListener("mouseenter", E), P.removeEventListener("mouseleave", N), P.removeEventListener("focusin", E), P.removeEventListener("focusout", N);
      };
  }, [E, N]), { progress: b, remainingMs: v, isPaused: w, pause: E, resume: N, reset: R, cancel: A, elementRef: a };
}
const Jm = "data:image/svg+xml,%3csvg%20xmlns='http://www.w3.org/2000/svg'%20width='24'%20height='24'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='currentColor'%20stroke-width='2'%20stroke-linecap='round'%20stroke-linejoin='round'%3e%3crect%20x='9'%20y='9'%20width='13'%20height='13'%20rx='2'%20ry='2'%3e%3c/rect%3e%3cpath%20d='M5%2015H4a2%202%200%200%201-2-2V4a2%202%200%200%201%202-2h9a2%202%200%200%201%202%202v1'%3e%3c/path%3e%3c/svg%3e", eg = "data:image/svg+xml,%3csvg%20width='24'%20height='24'%20viewBox='0%200%2024%2024'%20fill='none'%20xmlns='http://www.w3.org/2000/svg'%3e%3cpath%20d='M20%206L9%2017L4%2012'%20stroke='%23468BE6'%20stroke-width='2.5'%20stroke-linecap='round'%20stroke-linejoin='round'/%3e%3c/svg%3e";
function tg({ correlationId: e, disableEntranceAnimation: t = !1 }) {
  const [n, r] = z(!1), [o, i] = z(!1), a = e.split("-"), s = typeof window < "u" && window.innerWidth < 768, l = () => {
    navigator.clipboard.writeText(e), r(!0), setTimeout(() => r(!1), 2e3);
  };
  return /* @__PURE__ */ S("div", { className: "relative", onMouseEnter: () => i(!0), onMouseLeave: () => i(!1), onFocus: () => i(!0), onBlur: () => i(!1), children: [
    /* @__PURE__ */ S(
      "div",
      {
        onClick: l,
        onKeyDown: (u) => (u.key === "Enter" || u.key === " ") && (u.preventDefault(), l()),
        role: "button",
        tabIndex: 0,
        "aria-label": `Correlation ID: ${e}, click to copy`,
        "data-testid": "correlation-id-display",
        className: `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md cursor-pointer font-mono text-[11px] tracking-normal border ${n ? "animate-[copyPulse_500ms_ease-out]" : ""}`,
        style: { background: "rgba(233,245,255,0.4)", backdropFilter: "blur(8px)", borderColor: "rgba(9,47,100,0.12)", color: "rgba(9,47,100,0.7)", ...t ? {} : { animation: "correlationEnter 250ms cubic-bezier(0.4,0,0.2,1) 100ms forwards", opacity: 0 } },
        children: [
          /* @__PURE__ */ f("span", { className: "flex items-center gap-0.5", "aria-live": "polite", children: s ? `${a[0]}...${a[4]}` : a.map((u, p) => /* @__PURE__ */ S("span", { style: { opacity: [0.9, 0.85, 0.8, 0.85, 0.9][p] }, className: "transition-opacity duration-150 hover:opacity-100", children: [
            u,
            p < 4 && /* @__PURE__ */ f("span", { className: "mx-0.5 text-[9px]", style: { opacity: 0.1 }, children: "|" })
          ] }, p)) }),
          /* @__PURE__ */ f("img", { src: n ? eg : Jm, alt: "", className: `w-3 h-3 ${n ? "animate-[iconMorph_150ms_ease]" : ""}`, style: { opacity: 0.6 } }),
          n && /* @__PURE__ */ f("span", { className: "sr-only", children: "Copied to clipboard" })
        ]
      }
    ),
    o && /* @__PURE__ */ f("div", { className: "absolute bottom-full left-0 mb-1 px-2 py-1 rounded text-[10px] font-mono whitespace-nowrap animate-[fullTooltipShow_200ms_ease_150ms_forwards] opacity-0", style: { background: "rgba(233,245,255,0.95)", color: "rgba(9,47,100,0.8)", zIndex: 1e4 }, children: e })
  ] });
}
function ng({ config: e, index: t, totalBanners: n, onDismiss: r }) {
  const { severity: o, message: i, action: a, id: s, correlationId: l } = e, u = Xm[o], p = u.icon, [d, m] = z(!0), [h, b] = z(!1), [g, v] = z(!1), [y, w] = z(!1), C = j(null), x = j(null), E = j(null), N = j(null);
  j(performance.now());
  const R = j(!1), A = e.duration ?? u.duration;
  e.duration !== void 0 && e.duration !== 0 && e.duration < 1e3 && console.warn(`[ErrorBanner] Duration ${e.duration}ms < 1000ms minimum`);
  const P = () => {
    b(!0);
  }, _ = Qm({
    severity: o,
    timeoutMs: A,
    onDismiss: () => {
      R.current = !0, b(!0);
    }
  });
  ee(() => {
    N.current = document.activeElement, setTimeout(() => {
      E.current ? E.current.focus() : x.current && x.current.focus();
    }, 0);
  }, []), ee(() => {
    const T = (M) => {
      const O = C.current;
      M.key === "Escape" && O && (O === document.activeElement || O.contains(document.activeElement)) && (M.preventDefault(), P());
    };
    return document.addEventListener("keydown", T), () => document.removeEventListener("keydown", T);
  }, []);
  const I = (T) => {
    T.animationName === "bannerSlideIn" || T.animationName === "bannerFadeIn" ? (m(!1), C.current && (C.current.style.willChange = "auto")) : (T.animationName === "bannerSlideOut" || T.animationName === "bannerFadeOut") && (r(s, R.current ? "auto" : "manual"), setTimeout(() => {
      if (t < n - 1) {
        const M = document.querySelector(`[data-banner-id][data-index="${t + 1}"]`), O = M == null ? void 0 : M.querySelector('[aria-label^="Close"]');
        if (O) {
          O.focus();
          return;
        }
      }
      N.current && document.contains(N.current) ? N.current.focus() : document.body.focus();
    }, 0));
  }, k = 80 + t * 76, V = typeof window < "u" && window.innerWidth <= 640 ? { bottom: `${k}px` } : { top: `${k}px`, right: "24px" };
  return /* @__PURE__ */ f(
    "div",
    {
      ref: C,
      className: `error-banner-container fixed z-[9999] w-[400px] ${d ? "banner-enter" : h ? "banner-exit" : "banner-reposition"}`,
      style: V,
      "data-index": t,
      "data-banner-id": s,
      role: u.role,
      "aria-live": u.ariaLive,
      "aria-atomic": "true",
      "aria-label": `${o.charAt(0).toUpperCase() + o.slice(1)} notification`,
      onAnimationEnd: I,
      tabIndex: -1,
      children: /* @__PURE__ */ f(
        "div",
        {
          ref: _.elementRef,
          className: `relative rounded-lg p-3 backdrop-blur-[16px] shadow-[0_4px_16px_rgba(9,47,100,0.1)] border-l-4 ${o === "critical" ? "banner-bg-critical" : "banner-bg-default"}`,
          style: { borderLeftColor: u.borderColor },
          children: /* @__PURE__ */ S("div", { className: "flex items-start gap-3", children: [
            /* @__PURE__ */ f(
              p,
              {
                className: "error-banner-icon w-5 h-5 flex-shrink-0",
                style: { color: u.iconColor },
                "aria-hidden": "true"
              }
            ),
            /* @__PURE__ */ S("div", { className: "flex-1 min-w-0", children: [
              /* @__PURE__ */ f(
                "p",
                {
                  className: "error-banner-message text-sm leading-relaxed text-brand-cool-black",
                  "data-testid": `text-banner-message-${s}`,
                  children: i
                }
              ),
              a && /* @__PURE__ */ f(
                J,
                {
                  ref: E,
                  variant: "ghost",
                  onClick: a.onClick,
                  className: "mt-1.5 min-h-[44px] hover:underline text-brand-tufts",
                  style: { textUnderlineOffset: "3px" },
                  "data-testid": `button-action-${a.testId || o}`,
                  children: a.label
                }
              ),
              l && /* @__PURE__ */ S(G, { children: [
                /* @__PURE__ */ S(
                  "button",
                  {
                    onClick: () => {
                      w(!0), v(!g);
                    },
                    onKeyDown: (T) => {
                      (T.key === "Enter" || T.key === " ") && (T.preventDefault(), w(!0), v(!g));
                    },
                    className: "mt-2 inline-flex items-center gap-1 text-xs font-medium transition-all duration-150 opacity-50 hover:opacity-100 text-brand-cool-black",
                    "aria-expanded": g,
                    "aria-controls": `advanced-details-${s}`,
                    "data-testid": `button-toggle-details-${s}`,
                    children: [
                      /* @__PURE__ */ f(
                        hc,
                        {
                          className: `w-3.5 h-3.5 transition-transform duration-200 ${g ? "rotate-180" : ""}`
                        }
                      ),
                      /* @__PURE__ */ f("span", { children: "Advanced details" })
                    ]
                  }
                ),
                /* @__PURE__ */ f(
                  "div",
                  {
                    id: `advanced-details-${s}`,
                    className: `overflow-hidden ${!y && !g ? "advanced-details-collapsed" : ""}`,
                    style: {
                      animation: g ? "detailsExpand 250ms cubic-bezier(0.4, 0, 0.2, 1) forwards" : y ? "detailsCollapse 200ms cubic-bezier(0.4, 0, 0.2, 1) forwards" : "none",
                      ...y && {
                        maxHeight: g ? "100px" : "0",
                        opacity: g ? 1 : 0
                      }
                    },
                    "aria-hidden": !g,
                    children: /* @__PURE__ */ f(tg, { correlationId: l, disableEntranceAnimation: !0 })
                  }
                )
              ] })
            ] }),
            /* @__PURE__ */ f(
              J,
              {
                ref: x,
                variant: "ghost",
                size: "icon",
                onClick: P,
                className: "min-w-[44px] min-h-[44px] -mr-2 -mt-2 opacity-60 hover:opacity-100 hover:scale-110 border-transparent text-brand-cool-black",
                "aria-label": `Close ${o} notification`,
                "data-testid": `button-close-banner-${s}`,
                children: /* @__PURE__ */ f(Et, { className: "w-6 h-6" })
              }
            )
          ] })
        }
      )
    }
  );
}
const Vs = Lr(null);
function wg() {
  const e = Fr(Vs);
  if (!e)
    return null;
  const { banners: t, dismissBanner: n } = e;
  return /* @__PURE__ */ f(G, { children: t.map((r, o) => /* @__PURE__ */ f(
    ng,
    {
      config: r,
      index: o,
      totalBanners: t.length,
      onDismiss: n
    },
    r.id
  )) });
}
const rg = 3;
function Cg({ children: e }) {
  const [t, n] = z([]), r = Ce((i) => {
    const a = `banner-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`, s = {
      ...i,
      id: a,
      createdAt: Date.now()
    };
    return console.log(
      `[ErrorBanner:Create] id=${a} severity=${i.severity} correlationId=${i.correlationId || "none"} time=${(/* @__PURE__ */ new Date()).toISOString()}`
    ), n((l) => {
      if (l.length >= rg) {
        const u = l.findIndex((p) => p.severity !== "critical");
        if (u >= 0) {
          const p = l.slice(), d = p.splice(u, 1)[0];
          return console.log(
            `[ErrorBanner:Evicted] id=${d.id} severity=${d.severity} correlationId=${d.correlationId || "none"} reason=non-critical,queue-full time=${(/* @__PURE__ */ new Date()).toISOString()}`
          ), [...p, s];
        } else {
          const p = l[0];
          return console.log(
            `[ErrorBanner:Evicted] id=${p.id} severity=${p.severity} correlationId=${p.correlationId || "none"} reason=all-critical,oldest-first time=${(/* @__PURE__ */ new Date()).toISOString()}`
          ), [...l.slice(1), s];
        }
      }
      return [...l, s];
    }), a;
  }, []), o = Ce((i, a = "manual") => {
    n((s) => {
      const l = s.find((u) => u.id === i);
      return l && console.log(
        `[ErrorBanner:${a === "auto" ? "AutoDismiss" : "ManualDismiss"}] id=${i} severity=${l.severity} correlationId=${l.correlationId || "none"} time=${(/* @__PURE__ */ new Date()).toISOString()}`
      ), s.filter((u) => u.id !== i);
    });
  }, []);
  return /* @__PURE__ */ f(Vs.Provider, { value: { banners: t, showBanner: r, dismissBanner: o }, children: e });
}
const Eg = "1.0.0", Sg = {
  D0: "Token Foundation",
  D1: "Atomic Primitives",
  D2: "Composite Assemblies"
};
export {
  mg as ActivitySection,
  mo as Alert,
  go as AlertDescription,
  Nc as AlertTitle,
  Pl as Avatar,
  kl as AvatarFallback,
  Al as AvatarImage,
  ka as Badge,
  yg as BulkActionModal,
  xg as BulkActionToolbar,
  J as Button,
  vn as Card,
  wn as CardContent,
  xn as CardDescription,
  Wa as CardFooter,
  bn as CardHeader,
  yn as CardTitle,
  Ec as Checkbox,
  bg as ConfidenceScoreBadge,
  Sg as DESIGN_SYSTEM_LAYERS,
  Eg as DESIGN_SYSTEM_VERSION,
  vg as DataConfidenceBar,
  Rd as Dialog,
  ug as DialogClose,
  _i as DialogContent,
  Di as DialogDescription,
  $i as DialogFooter,
  Oi as DialogHeader,
  ki as DialogOverlay,
  Td as DialogPortal,
  Ii as DialogTitle,
  lg as DialogTrigger,
  ng as ErrorBanner,
  wg as ErrorBannerContainer,
  Cg as ErrorBannerProvider,
  qr as Input,
  lt as Label,
  In as RequestStatus,
  tn as Separator,
  ag as Tabs,
  vl as TabsContent,
  gl as TabsList,
  hl as TabsTrigger,
  Mi as Textarea,
  rs as Toast,
  hf as ToastAction,
  os as ToastClose,
  ss as ToastDescription,
  mf as ToastProvider,
  is as ToastTitle,
  ns as ToastViewport,
  dg as Toaster,
  gg as UserInfoCard,
  Sf as activitySectionFixtures,
  fg as allDataBearingFixtures,
  Aa as badgeVariants,
  Va as buttonVariants,
  L as cn,
  Nf as dataConfidenceBarFixtures,
  pg as stateKeys,
  Rf as userInfoCardFixtures
};
//# sourceMappingURL=design-system.es.js.map
