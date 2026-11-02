(function () {
  var canvas = document.getElementById("chart-field");
  if (!canvas) return;
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ctx = canvas.getContext("2d");
  var UP = "#22c55e";
  var DOWN = "#ef4444";
  var LIME = "#C6F04A";
  var candles = [];
  var model = null;
  var modelAt = 0;
  var width = 0;
  var height = 0;
  var drawn = 0;
  var last = 0;
  var phase = "build";
  var phaseAt = 0;
  var ORDER_MS = 5200;
  var markIn = {};

  function bar(open, close, high, low) {
    return { open: open, close: close, high: high, low: low };
  }

  var setups = [
    {
      caption: "Liquidity sweep · OB · FVG · MSS",
      candles: [
        bar(100, 99, 101, 98.4),
        bar(99, 97.8, 99.4, 97.2),
        bar(97.8, 98.9, 99.2, 97.4),
        bar(98.9, 96.6, 99, 96.2),
        bar(96.6, 99.4, 102.5, 96.4),
        bar(99.4, 96.1, 99.6, 95.6),
        bar(96.1, 94.2, 96.4, 93.8),
        bar(94.2, 92.8, 94.5, 92.2),
        bar(92.8, 91.6, 93.1, 91.1),
        bar(91.6, 89.4, 92, 82.4),
        bar(89.4, 95.6, 96.2, 89),
        bar(95.6, 99.1, 99.6, 95.2),
        bar(99.1, 103.9, 104.4, 98.8),
        bar(103.9, 100.4, 104.2, 97.6),
        bar(100.4, 105.2, 105.6, 100),
        bar(105.2, 104.3, 106, 103.6),
        bar(104.3, 107.8, 108.2, 104),
        bar(107.8, 106.9, 108.4, 106.2),
        bar(106.9, 110.8, 111.2, 106.6),
        bar(110.8, 109.6, 111.2, 109.2),
        bar(109.6, 111.4, 111.8, 109.2),
        bar(111.4, 110.2, 111.8, 109.8),
        bar(110.2, 112.4, 112.8, 110),
        bar(112.4, 111.1, 112.8, 110.6),
        bar(111.1, 113.2, 113.6, 110.8),
        bar(113.2, 112.4, 113.6, 111.8),
        bar(112.4, 114.1, 114.4, 112)
      ],
      side: "long",
      entry: 98.4,
      entryAt: 13,
      points: 100,
      sl: 95.6,
      tp: 106.8,
      exitAt: 16,
      win: true,
      grade: "A+",
      result: "+3.0R",
      title: "Bullish FVG long",
      read: "Liquidity sweep into an order block and a bullish FVG, then MSS.",
      note: "Limit buy after London swept the Asia low. The stop is 30 points under the entry. The 100-point target filled. Winner, +3.3R.",
      marks: [
        { name: "Asia low", kind: "level", role: "context", reveal: 3, at: 3, price: 96.2 },
        { name: "Asia high", kind: "level", role: "context", reveal: 4, at: 4, price: 102.5 },
        { name: "London low", kind: "level", role: "context", reveal: 9, at: 9, price: 82.4 },
        { name: "London high", kind: "level", role: "context", reveal: 12, at: 12, price: 104.4 },
        { name: "Liquidity sweep", kind: "sweep", role: "confluence", reveal: 9, i: 9, wick: "low" },
        { name: "OB", kind: "zone", role: "confluence", style: "ob", reveal: 10, i0: 9, i1: 9, topAt: 9, topKey: "open", botAt: 9, botKey: "close" },
        { name: "FVG", kind: "zone", role: "confluence", style: "fvg", reveal: 12, i0: 10, i1: 12, topAt: 12, topKey: "low", botAt: 10, botKey: "high" },
        { name: "MSS", kind: "line", role: "confluence", reveal: 12, i0: 4, i1: 12, priceAt: 4, priceKey: "high" }
      ]
    },
    {
      caption: "Sweep · FVG · BB",
      candles: [
        bar(90, 92.2, 92.6, 89.6),
        bar(92.2, 94.4, 94.8, 91.8),
        bar(94.4, 96.3, 96.8, 94.2),
        bar(96.3, 98.6, 99.4, 96),
        bar(98.6, 95.2, 98.8, 94.8),
        bar(95.2, 92.4, 95.6, 91.8),
        bar(92.4, 89.1, 92.6, 88.4),
        bar(89.1, 86.2, 89.4, 83.8),
        bar(86.2, 91.6, 92.1, 85.8),
        bar(91.6, 96.4, 96.9, 91.2),
        bar(96.4, 99.2, 99.6, 96.1),
        bar(99.2, 95.2, 99.4, 94.6),
        bar(95.2, 94.8, 96.2, 94.4),
        bar(94.8, 93, 95, 92.7),
        bar(93, 94.2, 94.8, 92.4),
        bar(94.2, 93.4, 94.6, 93),
        bar(93.4, 94.8, 95.1, 93.2),
        bar(94.8, 93.6, 95, 93.2),
        bar(93.6, 94.4, 94.8, 93.2),
        bar(94.4, 93.1, 94.6, 92.8),
        bar(93.1, 94, 94.3, 92.8),
        bar(94, 93.2, 94.2, 92.9),
        bar(93.2, 93.8, 94.1, 92.8)
      ],
      side: "long",
      entry: 95.4,
      entryAt: 11,
      points: 120,
      sl: 93.6,
      tp: 100.8,
      exitAt: 13,
      win: false,
      grade: "C",
      result: "-1.0R",
      title: "Breaker long",
      read: "Liquidity sweep into a bullish FVG and a breaker block.",
      note: "Limit buy after London swept the Asia low. The 30-point stop filled before the 100-point target. Loser, -1R.",
      marks: [
        { name: "Asia low", kind: "level", role: "context", reveal: 0, at: 0, price: 89.6 },
        { name: "Asia high", kind: "level", role: "context", reveal: 2, at: 2, price: 96.8 },
        { name: "London low", kind: "level", role: "context", reveal: 7, at: 7, price: 83.8 },
        { name: "London high", kind: "level", role: "context", reveal: 10, at: 10, price: 99.6 },
        { name: "BB", kind: "zone", role: "confluence", style: "bb", reveal: 7, i0: 6, i1: 6, topAt: 6, topKey: "high", botAt: 6, botKey: "low" },
        { name: "Liquidity sweep", kind: "sweep", role: "confluence", reveal: 7, i: 7, wick: "low" },
        { name: "FVG", kind: "zone", role: "confluence", style: "fvg", reveal: 9, i0: 7, i1: 9, topAt: 9, topKey: "low", botAt: 7, botKey: "high" }
      ]
    },
    {
      caption: "Sweep · FVG · MSS · BB",
      candles: [
        bar(105.8, 106.6, 107, 105.2),
        bar(106.6, 105.4, 106.8, 104.4),
        bar(105.4, 107.2, 107.6, 105),
        bar(107.2, 107.8, 108.2, 106.8),
        bar(108, 106.2, 108.4, 105.8),
        bar(106.2, 104.4, 106.6, 103.8),
        bar(104.4, 102.2, 104.8, 101.6),
        bar(102.2, 105.6, 106, 101.8),
        bar(105.6, 109.4, 113.6, 105.2),
        bar(109.4, 105.6, 109.6, 105.2),
        bar(105.6, 102, 105.8, 101.6),
        bar(102, 100.2, 102.4, 99.6),
        bar(100.2, 104.2, 105, 99.8),
        bar(104.2, 101.4, 104.4, 100.8),
        bar(101.4, 106.4, 107.4, 101.2),
        bar(106.4, 109.6, 110.2, 106),
        bar(109.6, 108.2, 110, 107.8),
        bar(108.2, 110.4, 110.8, 108),
        bar(110.4, 109.1, 110.8, 108.6),
        bar(109.1, 111.2, 111.6, 108.8),
        bar(111.2, 110.4, 111.6, 110),
        bar(110.4, 111.6, 112, 110),
        bar(111.6, 110.8, 112.2, 110.4),
        bar(110.8, 112.4, 112.8, 110.6),
        bar(112.4, 111.6, 112.8, 111.2)
      ],
      side: "short",
      entry: 104.6,
      entryAt: 12,
      points: 100,
      sl: 106.8,
      tp: 98,
      exitAt: 14,
      win: false,
      grade: "C+",
      result: "-1.0R",
      title: "Bearish breaker short",
      read: "Liquidity sweep into a bearish FVG, with MSS and a breaker.",
      note: "Limit sell after London swept the Asia high. The 30-point stop filled before the 100-point target. Loser, -1R.",
      marks: [
        { name: "Asia low", kind: "level", role: "context", reveal: 1, at: 1, price: 104.4 },
        { name: "Asia high", kind: "level", role: "context", reveal: 3, at: 3, price: 108.2 },
        { name: "London high", kind: "level", role: "context", reveal: 8, at: 8, price: 113.6 },
        { name: "London low", kind: "level", role: "context", reveal: 11, at: 11, price: 99.6 },
        { name: "Liquidity sweep", kind: "sweep", role: "confluence", reveal: 8, i: 8, wick: "high" },
        { name: "BB", kind: "zone", role: "confluence", style: "bb", reveal: 9, i0: 8, i1: 8, topAt: 8, topKey: "open", botAt: 8, botKey: "close" },
        { name: "FVG", kind: "zone", role: "confluence", style: "fvg-down", reveal: 11, i0: 9, i1: 11, topAt: 9, topKey: "low", botAt: 11, botKey: "high" },
        { name: "MSS", kind: "line", role: "confluence", reveal: 12, i0: 6, i1: 11, priceAt: 6, priceKey: "low" }
      ]
    },
    {
      caption: "SMT · Sweep · OB · iFVG",
      candles: [
        bar(112, 110.2, 112.4, 109.8),
        bar(110.2, 108.4, 110.6, 108),
        bar(108.4, 109.2, 109.6, 107.6),
        bar(109.2, 105.4, 109.4, 105),
        bar(105.4, 102.2, 105.6, 101.6),
        bar(102.2, 99.1, 102.4, 98.6),
        bar(99.1, 97.6, 99.4, 97),
        bar(97.6, 96.8, 98, 96.2),
        bar(96.8, 94.6, 97, 88.2),
        bar(94.6, 99.8, 100.2, 94.2),
        bar(99.8, 105.6, 106, 99.4),
        bar(105.6, 102.8, 105.8, 102.5),
        bar(102.8, 106.8, 107.2, 102.6),
        bar(106.8, 105.9, 107.4, 105.2),
        bar(105.9, 109.2, 109.6, 105.6),
        bar(109.2, 108.4, 109.6, 108),
        bar(108.4, 110.2, 110.6, 108.2),
        bar(110.2, 109.4, 110.6, 109),
        bar(109.4, 111.1, 111.4, 109.2),
        bar(111.1, 110.2, 111.4, 109.8),
        bar(110.2, 112, 112.4, 110),
        bar(112, 111.2, 112.4, 110.8),
        bar(111.2, 112.6, 113, 111)
      ],
      side: "long",
      entry: 103.2,
      entryAt: 11,
      points: 110,
      sl: 101.2,
      tp: 109.2,
      exitAt: 14,
      win: true,
      grade: "B",
      result: "+3.0R",
      title: "iFVG long",
      read: "Liquidity sweep into an order block and an inverted FVG.",
      note: "Limit buy after London swept the Asia low. The stop is 30 points under the entry. The 100-point target filled. Winner, +3.3R.",
      marks: [
        { name: "Asia high", kind: "level", role: "context", reveal: 0, at: 0, price: 112.4 },
        { name: "Asia low", kind: "level", role: "context", reveal: 3, at: 3, price: 105 },
        { name: "iFVG", kind: "zone", role: "confluence", style: "ifvg", reveal: 6, i0: 4, i1: 6, topAt: 4, topKey: "low", botAt: 6, botKey: "high" },
        { name: "SMT", kind: "smt", role: "confluence", reveal: 7, at: 8, prices: [null, null, null, 105.4, 102.6, 99.4, 97.8, 96.6, 95.4, 99.2, 104.8, 103.4, 106.2, null, null] },
        { name: "London low", kind: "level", role: "context", reveal: 8, at: 8, price: 88.2 },
        { name: "Liquidity sweep", kind: "sweep", role: "confluence", reveal: 8, i: 8, wick: "low" },
        { name: "OB", kind: "zone", role: "confluence", style: "ob", reveal: 9, i0: 8, i1: 8, topAt: 8, topKey: "open", botAt: 8, botKey: "close" },
        { name: "London high", kind: "level", role: "context", reveal: 10, at: 10, price: 106 }
      ]
    }
  ];

  var RISK = 30;

  function targetPoints(raw) {
    var points = Number(raw.points);
    if (!(points >= 80 && points <= 120)) points = 100;
    if (points <= RISK) points = 100;
    return points;
  }

  function scaleSetup(raw) {
    var entry = raw.entry;
    var long = raw.side === "long";
    var up = long;
    var priceShift = 0;
    if (!long) {
      entry = 95;
      up = true;
      priceShift = entry - raw.entry;
    }
    var reward = targetPoints(raw);
    var wickKey = (up && raw.win) || (!up && !raw.win) ? "high" : "low";

    function signed(price) {
      var adjusted = price + priceShift;
      return up ? adjusted - entry : entry - adjusted;
    }

    function fromSigned(dist) {
      var value = up ? entry + dist : entry - dist;
      return Math.round(value * 10) / 10;
    }

    var signedBars = raw.candles.map(function (candle) {
      return {
        open: signed(candle.open),
        close: signed(candle.close),
        high: signed(candle.high),
        low: signed(candle.low)
      };
    });
    var maxFav = 0.0001;
    var maxAdv = 0.0001;
    signedBars.forEach(function (candle, index) {
      if (index > raw.exitAt) return;
      ["open", "close", "high", "low"].forEach(function (key) {
        if (index === raw.exitAt && key === wickKey) return;
        var dist = candle[key];
        if (dist > maxFav) maxFav = dist;
        if (-dist > maxAdv) maxAdv = -dist;
      });
    });
    var sFav = (raw.win ? reward * 0.82 : Math.min(64, reward - 16)) / maxFav;
    var sAdv = 22 / maxAdv;

    function mapDist(dist) {
      return dist >= 0 ? dist * sFav : dist * sAdv;
    }

    function emit(mapped) {
      var prices = ["open", "close", "high", "low"].map(function (key) {
        return fromSigned(mapped[key]);
      });
      return {
        open: prices[0],
        close: prices[1],
        high: Math.max.apply(null, prices),
        low: Math.min.apply(null, prices)
      };
    }

    var candles = signedBars.map(function (candle, index) {
      if (index > raw.exitAt) {
        return emit({ open: 0, close: 0, high: 0, low: 0 });
      }
      var mapped = {
        open: mapDist(candle.open),
        close: mapDist(candle.close),
        high: mapDist(candle.high),
        low: mapDist(candle.low)
      };
      if (index === raw.exitAt) {
        mapped[wickKey] = raw.win ? reward : -RISK;
        var rawCandle = raw.candles[index];
        if (raw.win && rawCandle.close >= rawCandle.open) mapped.close = Math.max(mapped.close, reward - 8);
        if (!raw.win && rawCandle.close <= rawCandle.open) mapped.close = Math.min(mapped.close, -(RISK - 6));
      }
      if (index === raw.entryAt) {
        var values = [mapped.open, mapped.close, mapped.high, mapped.low];
        if (Math.min.apply(null, values) > 0) mapped[up ? "low" : "high"] = 0;
        if (Math.max.apply(null, values) < 0) mapped[up ? "high" : "low"] = 0;
      }
      return emit(mapped);
    });
    var sl = Math.round((up ? entry - RISK : entry + RISK) * 10) / 10;
    var tp = Math.round((up ? entry + reward : entry - reward) * 10) / 10;
    if (up && !(tp > entry && entry > sl && tp > sl)) {
      sl = Math.round((entry - RISK) * 10) / 10;
      tp = Math.round((entry + reward) * 10) / 10;
    }
    if (!up && !(tp < entry && entry < sl && (entry - tp) > (sl - entry))) {
      sl = Math.round((entry + RISK) * 10) / 10;
      tp = Math.round((entry - reward) * 10) / 10;
    }
    var rMultiple = Math.round((reward / RISK) * 10) / 10;
    var rText = rMultiple.toFixed(1);
    var outcome = raw.win
      ? "The stop is 30 points under the entry. The " + reward + "-point target filled. Winner, +" + rText + "R."
      : "The 30-point stop filled before the " + reward + "-point target. Loser, -1R.";
    var note = (raw.read ? raw.read + " " : "") + outcome;
    var marks = raw.marks.map(function (mark) {
      var copy = {};
      var key;
      for (key in mark) {
        if (Object.prototype.hasOwnProperty.call(mark, key)) copy[key] = mark[key];
      }
      if (copy.kind === "level" && candles[copy.at]) {
        copy.price = copy.name.indexOf("high") >= 0 ? candles[copy.at].high : candles[copy.at].low;
      } else if (copy.kind === "zone" && candles[copy.topAt] && candles[copy.botAt]) {
        copy.price = candles[copy.topAt][copy.topKey];
        copy.price2 = candles[copy.botAt][copy.botKey];
      } else if (copy.kind === "sweep" && candles[copy.i]) {
        copy.price = copy.wick === "high" ? candles[copy.i].high : candles[copy.i].low;
      } else if (copy.kind === "line" && copy.priceAt != null && candles[copy.priceAt]) {
        copy.price = copy.priceKey === "high" ? candles[copy.priceAt].high : candles[copy.priceAt].low;
      } else if (copy.price != null) {
        copy.price = fromSigned(mapDist(signed(copy.price)));
      }
      if (copy.prices) {
        copy.prices = copy.prices.map(function (price) {
          if (price == null) return null;
          return fromSigned(mapDist(signed(price)));
        });
      }
      return copy;
    });
    return {
      caption: raw.caption,
      candles: candles,
      side: raw.side,
      entry: entry,
      entryAt: raw.entryAt,
      sl: sl,
      tp: tp,
      exitAt: raw.exitAt,
      win: raw.win,
      grade: raw.grade,
      result: raw.win ? "+" + rText + "R" : "-1.0R",
      title: raw.title,
      note: note,
      marks: marks
    };
  }

  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function rollAfter(model) {
    var list = model.candles;
    var exitAt = model.exitAt;
    if (!list || exitAt >= list.length - 1) return;
    var entry = model.entry;
    var up = model.tp > model.entry;
    var reward = Math.round(Math.abs(model.tp - entry));
    var rnd = mulberry32((Date.now() ^ (exitAt * 131) ^ ((Math.random() * 0x7fffffff) | 0)) >>> 0);
    var trend = rnd() < 0.5;
    var fillDir = model.win ? 1 : -1;
    var capHi = model.win ? reward + 72 : reward - 16;
    var capLo = model.win ? -(RISK - 10) : -(RISK + 62);

    function signed(price) {
      return up ? price - entry : entry - price;
    }

    function fromSigned(dist) {
      var value = up ? entry + dist : entry - dist;
      return Math.round(value * 10) / 10;
    }

    function clamp(dist) {
      if (dist > capHi) return capHi;
      if (dist < capLo) return capLo;
      return dist;
    }

    var cursor = signed(list[exitAt].close);
    var travel = 48 + rnd() * 36;
    var goal = clamp(trend ? cursor + fillDir * travel : cursor - fillDir * travel);
    var i;
    for (i = exitAt + 1; i < list.length; i += 1) {
      var room = list.length - i;
      var toward = goal - cursor;
      var dir = toward === 0 ? fillDir : (toward > 0 ? 1 : -1);
      if ((dir > 0 && cursor > capHi - 22) || (dir < 0 && cursor < capLo + 22)) dir = -dir;
      if (rnd() < 0.32 && room > 1) dir = -dir;
      var body = 18 + rnd() * 20;
      if (rnd() < 0.22) body = 32 + rnd() * 16;
      var openDist = clamp(cursor + (rnd() - 0.5) * 6);
      var closeDist = clamp(openDist + dir * body);
      if (Math.abs(closeDist - openDist) < 14) closeDist = clamp(openDist + dir * 20);
      if (Math.abs(closeDist - openDist) < 14) {
        dir = -dir;
        closeDist = clamp(openDist + dir * 20);
      }
      var upper = Math.max(openDist, closeDist);
      var lower = Math.min(openDist, closeDist);
      var favorWick = Math.min(4 + rnd() * 14, Math.max(2, capHi - upper));
      var adverseWick = Math.min(4 + rnd() * 14, Math.max(2, lower - capLo));
      var o = fromSigned(openDist);
      var c = fromSigned(closeDist);
      var hi = fromSigned(upper + favorWick);
      var lo = fromSigned(lower - adverseWick);
      list[i] = {
        open: o,
        close: c,
        high: Math.max(o, c, hi, lo),
        low: Math.min(o, c, hi, lo)
      };
      cursor = closeDist;
    }
  }

  setups = setups.map(function (raw) {
    var next = scaleSetup(raw);
    rollAfter(next);
    return next;
  });

  function loadModel() {
    model = setups[modelAt % setups.length];
    modelAt += 1;
    rollAfter(model);
    candles = model.candles;
    phase = "build";
    phaseAt = 0;
    drawn = 0;
    markIn = {};
    var card = document.getElementById("trade-read");
    if (card) card.classList.remove("in");
    var list = document.getElementById("read-cons");
    if (list) list.innerHTML = "";
    ["read-setup", "read-grade", "read-body", "read-result"].forEach(function (id) {
      var node = document.getElementById(id);
      if (node) {
        node.textContent = "";
        node.className = "";
      }
    });
    var caption = document.getElementById("chart-caption");
    if (caption) caption.textContent = "Trade replay · 1m";
    var tag = document.getElementById("logged-tag");
    if (tag) tag.textContent = "Logged trade";
  }

  function resize() {
    var pane = canvas.parentElement;
    var box = pane.getBoundingClientRect();
    width = Math.max(1, Math.round(box.width));
    height = Math.max(1, Math.round(box.height));
    var ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function yOf(price, low, high) {
    var span = high - low || 1;
    return 36 + (height - 72) * (1 - (price - low) / span);
  }

  var plot = { pad: 16, step: 12, body: 8, gap: 3 };

  function layoutPlot() {
    var count = Math.max(1, candles.length);
    var pad = 8;
    var step = (width - pad * 2) / count;
    var body = Math.max(4, step * 0.5);
    if (body > step - 1) body = Math.max(2, step - 1);
    plot = { pad: pad, step: step, body: body, gap: step - body };
  }

  function xAt(i) {
    return plot.pad + (i + 0.5) * plot.step;
  }

  function ease(t) {
    var x = Math.max(0, Math.min(1, t));
    return 1 - Math.pow(1 - x, 3);
  }

  function bounds() {
    var low = Math.min(model.sl, model.tp, model.entry);
    var high = Math.max(model.sl, model.tp, model.entry);
    var i;
    for (i = 0; i < candles.length; i += 1) {
      if (candles[i].low < low) low = candles[i].low;
      if (candles[i].high > high) high = candles[i].high;
    }
    var pad = (high - low) * 0.07 || 1;
    return { low: low - pad, high: high + pad };
  }

  function frame(now) {
    var span = bounds();
    var low = span.low;
    var high = span.high;
    var delta = last ? Math.min(40, now - last) : 16;
    last = now;
    if (reduced) {
      drawn = candles.length;
      phase = "hold";
    } else if (phase === "build") {
      drawn += delta / 293;
      if (drawn >= model.entryAt + 1) {
        drawn = model.entryAt + 1;
        phase = "order";
        phaseAt = now;
      }
    } else if (phase === "order") {
      if (now - phaseAt >= ORDER_MS) {
        phase = "play";
        phaseAt = now;
      }
    } else if (phase === "play") {
      drawn += delta / 293;
      if (drawn >= candles.length) {
        drawn = candles.length;
        phase = "hold";
        phaseAt = now;
      }
    } else if (now - phaseAt > 5600) {
      loadModel();
      span = bounds();
      low = span.low;
      high = span.high;
    }
    var show = Math.min(candles.length, Math.floor(drawn));
    paint(show, low, high, now);
    syncRead(show);
    if (!reduced) requestAnimationFrame(frame);
  }

  function clamp(value, lo, hi) {
    return Math.max(lo, Math.min(hi, value));
  }

  function lerp(from, to, amount) {
    return from + (to - from) * amount;
  }

  function markAge(key, now) {
    if (markIn[key] == null) markIn[key] = now || 0;
    if (reduced) return 1;
    return ease(((now || 0) - markIn[key]) / 480);
  }

  function withEntrance(key, now, draw) {
    var age = markAge(key, now);
    ctx.save();
    ctx.globalAlpha = age;
    ctx.translate((1 - age) * -26, 0);
    draw();
    ctx.restore();
  }

  function paint(show, low, high, now) {
    ctx.clearRect(0, 0, width, height);
    ctx.globalAlpha = 1;
    labelSlots = [];
    ctx.setLineDash([]);
    if (width < 20 || height < 20) return;
    layoutPlot();
    var i;
    for (i = 0; i < show; i += 1) {
      var item = candles[i];
      var x = xAt(i);
      var up = item.close >= item.open;
      var color = up ? UP : DOWN;
      ctx.lineWidth = Math.max(1.6, Math.min(2.8, plot.body * 0.16));
      ctx.strokeStyle = color;
      ctx.fillStyle = up ? "rgba(34,197,94,0.92)" : "rgba(239,68,68,0.9)";
      ctx.beginPath();
      ctx.moveTo(x, yOf(item.high, low, high));
      ctx.lineTo(x, yOf(item.low, low, high));
      ctx.stroke();
      var top = yOf(Math.max(item.open, item.close), low, high);
      var tall = Math.max(2, Math.abs(yOf(item.open, low, high) - yOf(item.close, low, high)));
      ctx.fillRect(x - plot.body / 2, top, plot.body, tall);
    }
    model.marks.forEach(function (mark, index) {
      if (show <= mark.reveal) return;
      var key = mark.name + ":" + index;
      withEntrance(key, now, function () {
        drawMark(mark, show, low, high);
      });
    });
    drawLevels(show, low, high, now);
  }

  var labelSlots = [];

  function claimLabel(x, y, text, low, high) {
    var card = document.getElementById("trade-read");
    var next = x;
    var ceiling = 28;
    var floor = height - 28;
    var tpY = yOf(model.tp, low, high);
    var slY = yOf(model.sl, low, high);
    if (Math.abs(y - tpY) < 26) ceiling = Math.max(ceiling, tpY + 22);
    if (Math.abs(y - slY) < 36) floor = Math.min(floor, slY - 22);
    if (card && card.classList.contains("in")) {
      var pane = canvas.getBoundingClientRect();
      var box = card.getBoundingClientRect();
      var right = box.right - pane.left;
      var top = box.top - pane.top;
      var bottom = box.bottom - pane.top;
      if (y > top - 6 && y < bottom + 6) {
        next = Math.max(next, right + 40);
        floor = Math.min(floor, top - 12);
      }
    }
    var textWidth = ctx.measureText(text).width;
    if (next + textWidth > width - 10) next = Math.max(8, width - textWidth - 10);
    var spotY = Math.max(ceiling, Math.min(floor, y));
    var guard = 0;
    while (labelSlots.some(function (slot) { return Math.abs(slot - spotY) < 16; }) && guard < 8) {
      spotY -= 16;
      guard += 1;
    }
    if (spotY < ceiling) spotY = ceiling;
    labelSlots.push(spotY);
    return { x: next, y: spotY };
  }

  function drawTag(text, x, y, color) {
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(7,11,18,0.88)";
    ctx.strokeText(text, x, y);
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
  }

  function drawMark(mark, show, low, high) {
    ctx.lineWidth = 1.25;
    ctx.font = "600 13px Figtree, Segoe UI, sans-serif";
    ctx.setLineDash([]);
    if (mark.kind === "zone" && mark.price != null && mark.price2 != null) {
      var zoneY1 = yOf(mark.price, low, high);
      var zoneY2 = yOf(mark.price2, low, high);
      var zoneTop = Math.min(zoneY1, zoneY2);
      var zoneBot = Math.max(zoneY1, zoneY2);
      if (zoneBot - zoneTop < 12) {
        var zoneMid = (zoneTop + zoneBot) / 2;
        zoneTop = zoneMid - 6;
        zoneBot = zoneMid + 6;
      }
      var zoneX0 = xAt(mark.i0) - plot.body * 0.55;
      var zoneX1 = xAt(mark.i1) + plot.body * 0.55;
      var zoneFill = "rgba(34,197,94,0.20)";
      var zoneStroke = "#86efac";
      var zoneDash = [];
      if (mark.style === "fvg-down") {
        zoneFill = "rgba(239,68,68,0.18)";
        zoneStroke = "#fca5a5";
      } else if (mark.style === "ifvg") {
        zoneFill = "rgba(132,245,165,0.16)";
        zoneStroke = "#d9f99d";
        zoneDash = [4, 3];
      } else if (mark.style === "ob") {
        zoneFill = "rgba(56,189,248,0.18)";
        zoneStroke = "#7dd3fc";
      } else if (mark.style === "bb") {
        zoneFill = "rgba(251,191,36,0.16)";
        zoneStroke = "#fbbf24";
        zoneDash = [4, 3];
      }
      ctx.fillStyle = zoneFill;
      ctx.strokeStyle = zoneStroke;
      ctx.lineWidth = 1.35;
      ctx.setLineDash(zoneDash);
      ctx.beginPath();
      ctx.rect(zoneX0, zoneTop, Math.max(8, zoneX1 - zoneX0), zoneBot - zoneTop);
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = "700 12px Figtree, Segoe UI, sans-serif";
      var zoneSpot = claimLabel(zoneX1 + 6, zoneTop + 12, mark.name, low, high);
      if (zoneSpot.x > zoneX1 + 18) {
        ctx.strokeStyle = zoneStroke;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(zoneX1, (zoneTop + zoneBot) / 2);
        ctx.lineTo(zoneSpot.x - 4, zoneSpot.y - 4);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      drawTag(mark.name, zoneSpot.x, zoneSpot.y, zoneStroke);
      return;
    }
    if (mark.kind === "level") {
      var levelY = yOf(mark.price, low, high);
      var start = Math.min(mark.at, Math.max(0, show - 1));
      var x0 = xAt(start);
      var x1 = xAt(Math.max(0, show - 1));
      ctx.strokeStyle = "rgba(247,250,247,0.72)";
      ctx.lineWidth = 1.15;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(x0, levelY);
      ctx.lineTo(Math.max(x0 + 28, x1), levelY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#f7faf7";
      ctx.font = "600 12px Figtree, Segoe UI, sans-serif";
      ctx.fillText(mark.name, x0 + 6, levelY - 5);
      return;
    }
    if (mark.kind === "line") {
      var lineY = yOf(mark.price, low, high);
      ctx.strokeStyle = "#e8ffb0";
      ctx.setLineDash([5, 4]);
      ctx.font = "700 12px Figtree, Segoe UI, sans-serif";
      var lineSpot = claimLabel(xAt(Math.max(0, show - 1)) - 28, lineY - 6, mark.name, low, high);
      ctx.beginPath();
      ctx.moveTo(xAt(mark.i0), lineY);
      ctx.lineTo(Math.max(xAt(mark.i1) + plot.body, lineSpot.x - 8), lineY);
      ctx.stroke();
      ctx.setLineDash([]);
      drawTag(mark.name, lineSpot.x, lineSpot.y, "#e8ffb0");
      return;
    }
    if (mark.kind === "sweep") {
      var sweepX = xAt(mark.i);
      var sweepY = yOf(mark.price, low, high);
      ctx.strokeStyle = "#e8ffb0";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(sweepX - 14, sweepY);
      ctx.lineTo(sweepX + 14, sweepY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#e8ffb0";
      ctx.font = "700 12px Figtree, Segoe UI, sans-serif";
      var sweepSpot = claimLabel(sweepX + 8, mark.wick === "high" ? sweepY - 14 : sweepY + 16, mark.name, low, high);
      if (sweepSpot.x > sweepX + 24 || Math.abs(sweepSpot.y - sweepY) > 18) {
        ctx.beginPath();
        ctx.moveTo(sweepX + 16, sweepY);
        ctx.lineTo(sweepSpot.x - 4, sweepSpot.y);
        ctx.stroke();
      }
      drawTag(mark.name, sweepSpot.x, sweepSpot.y, "#e8ffb0");
      return;
    }
    if (mark.kind === "smt") {
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      var started = false;
      mark.prices.forEach(function (price, index) {
        if (price == null || index >= show) return;
        var sx = xAt(index);
        var sy = yOf(price, low, high);
        if (!started) {
          ctx.moveTo(sx, sy);
          started = true;
        } else {
          ctx.lineTo(sx, sy);
        }
      });
      ctx.stroke();
      var labelPrice = mark.prices[mark.at];
      if (labelPrice != null && mark.at < show) {
        ctx.fillStyle = "#f59e0b";
        ctx.font = "700 12px Figtree, Segoe UI, sans-serif";
        var smtSpot = claimLabel(xAt(mark.at) + 8, yOf(labelPrice, low, high) - 8, mark.name, low, high);
        drawTag(mark.name, smtSpot.x, smtSpot.y, "#f59e0b");
      }
    }
  }

  function shadeZone(yA, yB, color, grow) {
    if (grow <= 0) return;
    var top = Math.min(yA, yB);
    var band = Math.max(2, Math.abs(yB - yA));
    var x0 = xAt(model.entryAt);
    var span = Math.max(8, (width - plot.pad - x0) * grow);
    ctx.save();
    ctx.globalAlpha = Math.min(1, grow);
    ctx.fillStyle = color;
    ctx.fillRect(x0, top, span, band);
    ctx.restore();
  }

  function drawR(entryY, tpY, grow) {
    if (grow < 0.45) return;
    ctx.save();
    ctx.globalAlpha = Math.min(1, (grow - 0.45) / 0.35);
    ctx.font = "700 28px 'JetBrains Mono', ui-monospace, monospace";
    ctx.fillStyle = model.result.charAt(0) === "-" ? DOWN : UP;
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    var label = model.result;
    var labelW = ctx.measureText(label).width;
    var x = xAt(model.entryAt) + Math.max(28, plot.step * 1.4);
    if (x + labelW > width - 12) x = Math.max(plot.pad, width - labelW - 12);
    ctx.fillText(label, x, (entryY + tpY) / 2);
    ctx.restore();
  }

  function drawLevels(show, low, high, now) {
    var placed = reduced || phase === "play" || phase === "hold";
    var progress = placed ? 1 : (phase === "order" ? clamp((now - phaseAt) / ORDER_MS, 0, 1) : 0);
    if (progress <= 0) return;
    var entryX = xAt(model.entryAt);
    var entryY = yOf(model.entry, low, high);
    var slY = yOf(model.sl, low, high);
    var tpY = yOf(model.tp, low, high);
    var menuW = 150;
    var menuH = 62;
    var menuX = entryX + 18;
    var menuY = entryY - menuH / 2;
    if (menuX + menuW > width - 8) menuX = entryX - menuW - 16;
    if (menuY < 8) menuY = 8;
    if (menuY + menuH > height - 8) menuY = Math.max(8, height - menuH - 8);
    var slGrow = progress >= 1 ? 1 : ease(clamp((progress - 0.58) / 0.18, 0, 1));
    var tpGrow = progress >= 1 ? 1 : ease(clamp((progress - 0.84) / 0.16, 0, 1));
    var settled = show > model.exitAt && (phase === "play" || phase === "hold");
    shadeZone(entryY, slY, "rgba(239,68,68,0.30)", slGrow);
    shadeZone(entryY, tpY, "rgba(34,197,94,0.30)", tpGrow);
    if (progress >= 0.48) {
      levelLine(plot.pad, entryY, "#f4ffe0", 1, 1.5, model.side === "long" ? "Limit Buy" : "Limit Sell", true, false);
    }
    if (slGrow > 0) {
      levelLine(plot.pad, slY, DOWN, slGrow, 3.4, "SL $" + model.sl.toFixed(1) + " · " + Math.round(Math.abs(model.sl - model.entry)) + "pt", true, true);
    }
    if (tpGrow > 0) {
      levelLine(plot.pad, tpY, UP, tpGrow, 3.4, "TP $" + model.tp.toFixed(1) + " · " + Math.round(Math.abs(model.tp - model.entry)) + "pt", true, true);
    }
    drawR(entryY, tpY, tpGrow);
    if (settled) {
      var hitY = model.win ? tpY : slY;
      var hitX = xAt(model.exitAt);
      ctx.fillStyle = model.win ? UP : DOWN;
      ctx.beginPath();
      ctx.arc(hitX, hitY, 6, 0, Math.PI * 2);
      ctx.fill();
    }
    if (phase === "order" && !reduced) {
      if (progress >= 0.14 && progress <= 0.32) {
        var ring = (progress - 0.14) / 0.18;
        ctx.strokeStyle = "rgba(255,255,255," + (0.85 * (1 - ring)).toFixed(3) + ")";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(entryX, entryY, 5 + ring * 18, 0, Math.PI * 2);
        ctx.stroke();
      }
      drawMenu(menuX, menuY, menuW, progress);
      var cursor = orderCursor(progress, entryX, entryY, slY, tpY, menuX, menuY);
      drawPointer(cursor.x, cursor.y, cursor.click);
    }
  }

  function levelLine(x1, y, color, grow, weight, text, pinLabel, big) {
    var x2 = x1 + (width - plot.pad - x1) * grow;
    var end = Math.max(x1 + 12, x2);
    ctx.save();
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = big ? 3.4 : weight;
    ctx.lineCap = "round";
    ctx.setLineDash(big ? [8, 5] : [5, 4]);
    ctx.beginPath();
    ctx.moveTo(x1, y);
    ctx.lineTo(end, y);
    ctx.stroke();
    ctx.setLineDash([]);
    if (big && grow > 0.2) {
      ctx.beginPath();
      ctx.arc(end, y, 5.5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.font = big ? "700 22px Figtree, Segoe UI, sans-serif" : "600 13px Figtree, Segoe UI, sans-serif";
    var textW = ctx.measureText(text).width;
    var textX = pinLabel ? x1 + 10 : Math.min(width - textW - 10, Math.max(x1 + 10, end - textW - 8));
    if (big) {
      var padX = 10;
      var pillW = textW + padX * 2;
      var pillH = 32;
      var px = Math.min(width - pillW - 8, Math.max(8, end - pillW - 12));
      var py = y - pillH - 10;
      if (py < 4) py = Math.min(height - pillH - 4, y + 10);
      ctx.fillStyle = "rgba(8,11,9,0.9)";
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.25;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(px, py, pillW, pillH, 9);
      else ctx.rect(px, py, pillW, pillH);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.textBaseline = "middle";
      ctx.fillText(text, px + padX, py + pillH / 2);
    } else {
      ctx.fillText(text, textX, y - 8);
    }
    ctx.restore();
  }

  function drawMenu(x, y, menuW, progress) {
    var fadeIn = ease(clamp((progress - 0.2) / 0.06, 0, 1));
    var fadeOut = progress < 0.5 ? 1 : 1 - ease(clamp((progress - 0.5) / 0.08, 0, 1));
    var alpha = fadeIn * fadeOut;
    if (alpha <= 0.02) return;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "#121826";
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, menuW, 62, 8);
    else ctx.rect(x, y, menuW, 62);
    ctx.fill();
    ctx.stroke();
    var hover = progress >= 0.36;
    var picked = model.side === "long" ? 0 : 1;
    var rows = ["Limit Buy", "Limit Sell"];
    var row;
    for (row = 0; row < rows.length; row += 1) {
      if (hover && row === picked) {
        ctx.fillStyle = "rgba(198,240,74,0.18)";
        ctx.fillRect(x + 4, y + 6 + row * 28, menuW - 8, 24);
      }
      ctx.font = "13px Segoe UI, sans-serif";
      ctx.fillStyle = hover && row === picked ? LIME : "#e5e7eb";
      ctx.fillText(rows[row], x + 12, y + 22 + row * 28);
    }
    ctx.restore();
  }

  function lineEnd(grow) {
    var x1 = plot.pad;
    var x2 = x1 + (width - plot.pad - x1) * grow;
    return Math.max(x1 + 12, x2);
  }

  function orderCursor(progress, entryX, entryY, slY, tpY, menuX, menuY) {
    var rowX = menuX + 28;
    var rowY = model.side === "long" ? menuY + 18 : menuY + 46;
    if (progress <= 0.14) {
      var travel = ease(progress / 0.14);
      return { x: lerp(width - 8, entryX, travel), y: lerp(height - 12, entryY, travel), click: null };
    }
    if (progress <= 0.26) return { x: entryX, y: entryY, click: "right" };
    if (progress <= 0.42) {
      var toward = ease((progress - 0.26) / 0.16);
      return { x: lerp(entryX, rowX, toward), y: lerp(entryY, rowY, toward), click: null };
    }
    if (progress <= 0.5) return { x: rowX, y: rowY, click: "left" };
    if (progress <= 0.58) {
      var toStop = ease((progress - 0.5) / 0.08);
      return { x: lerp(rowX, plot.pad, toStop), y: lerp(rowY, slY, toStop), click: null };
    }
    if (progress <= 0.76) {
      var slGrow = ease(clamp((progress - 0.58) / 0.18, 0, 1));
      return { x: lineEnd(slGrow), y: slY, click: null };
    }
    if (progress <= 0.84) {
      var toTarget = ease((progress - 0.76) / 0.08);
      return { x: lerp(lineEnd(1), plot.pad, toTarget), y: lerp(slY, tpY, toTarget), click: null };
    }
    var tpGrow = ease(clamp((progress - 0.84) / 0.16, 0, 1));
    return { x: lineEnd(tpGrow), y: tpY, click: null };
  }

  function drawPointer(x, y, click) {
    ctx.save();
    ctx.translate(x, y);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, 16);
    ctx.lineTo(4.2, 12.2);
    ctx.lineTo(7.4, 18.2);
    ctx.lineTo(10.2, 16.8);
    ctx.lineTo(6.8, 11);
    ctx.lineTo(12, 10.2);
    ctx.closePath();
    ctx.fillStyle = "#f8fafc";
    ctx.strokeStyle = "#0b0f17";
    ctx.lineWidth = 1.25;
    ctx.fill();
    ctx.stroke();
    if (click === "right") {
      ctx.beginPath();
      ctx.strokeStyle = "rgba(255,255,255,0.9)";
      ctx.lineWidth = 1.4;
      ctx.arc(1, 1, 10, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (click === "left") {
      ctx.fillStyle = LIME;
      ctx.beginPath();
      ctx.arc(1, 1, 3.2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function syncRead(show) {
    var card = document.getElementById("trade-read");
    var list = document.getElementById("read-cons");
    var tag = document.getElementById("logged-tag");
    if (tag && model) {
      var opened = show > model.entryAt && (reduced || phase === "order" || phase === "play" || phase === "hold");
      tag.textContent = opened
        ? "Logged trade · Entry " + model.entry.toFixed(1) + " · SL $" + model.sl.toFixed(1) + " · TP $" + model.tp.toFixed(1) + " · " + model.result
        : "Logged trade";
    }
    if (!card || !list || !model) return;
    model.marks.forEach(function (mark, index) {
      if (show <= mark.reveal || mark.role === "context") return;
      if (!card.classList.contains("in")) {
        card.classList.add("in");
        var title = document.getElementById("read-setup");
        if (title) title.textContent = model.title;
      }
      if (!list.querySelector('[data-i="' + index + '"]')) {
        var item = document.createElement("li");
        item.setAttribute("data-i", String(index));
        item.textContent = mark.name;
        list.appendChild(item);
      }
    });
    if (show > model.exitAt && (phase === "play" || phase === "hold")) {
      var grade = document.getElementById("read-grade");
      var result = document.getElementById("read-result");
      var body = document.getElementById("read-body");
      if (grade && !grade.textContent) {
        grade.textContent = model.grade;
        grade.className = model.win ? "" : "loss";
      }
      if (result && !result.textContent) {
        result.textContent = model.result;
        result.className = model.win ? "" : "loss";
      }
      if (body && !body.textContent) body.textContent = model.note;
    }
  }

  loadModel();
  resize();
  window.addEventListener("resize", resize);
  window.addEventListener("load", resize);
  if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas.parentElement);
  requestAnimationFrame(frame);

  var quotes = [
    "The setup is the easy part. The review is the edge.",
    "One revenge trade can spend a week of discipline.",
    "If it is not in the journal, it did not teach you.",
    "Protect the daily loss before you protect your pride.",
    "Size is a decision you make before the fill, not during it."
  ];
  var quote = document.getElementById("quote");
  var quoteAt = 0;
  function showQuote() {
    if (!quote) return;
    quote.classList.remove("in");
    window.setTimeout(function () {
      quote.textContent = quotes[quoteAt % quotes.length];
      quoteAt += 1;
      quote.classList.add("in");
    }, reduced ? 0 : 220);
  }
  showQuote();
  if (!reduced) window.setInterval(showQuote, 8000);

  var leadLine = document.getElementById("lead-line");
  var leadLines = [];
  var leadData = document.getElementById("lead-lines");
  if (leadData) {
    try { leadLines = JSON.parse(leadData.textContent); } catch (err) { leadLines = []; }
  }
  var leadAt = 1;
  function showLead() {
    if (!leadLine || leadLines.length < 2) return;
    leadLine.classList.remove("in");
    window.setTimeout(function () {
      leadLine.textContent = leadLines[leadAt % leadLines.length];
      leadAt += 1;
      leadLine.classList.add("in");
    }, reduced ? 0 : 280);
  }
  if (leadLine && !reduced && leadLines.length > 1) window.setInterval(showLead, 4600);

  var moments = document.getElementById("moments");
  var lines = [
    "A+ Silver Bullet: +3.2R",
    "5 green days",
    "Rule kept: no revenge trades",
    "NY AM win rate 68%",
    "News respected: CPI"
  ];
  var spots = [
    { top: "6%", left: "8%" },
    { top: "18%", right: "6%" },
    { bottom: "16%", left: "10%" },
    { bottom: "8%", right: "12%" }
  ];
  var momentAt = 0;
  function floatMoment() {
    if (!moments) return;
    var card = document.createElement("p");
    card.className = "moment";
    card.textContent = lines[momentAt % lines.length];
    var spot = spots[momentAt % spots.length];
    momentAt += 1;
    Object.keys(spot).forEach(function (key) { card.style[key] = spot[key]; });
    moments.appendChild(card);
    requestAnimationFrame(function () { card.classList.add("in"); });
    window.setTimeout(function () {
      card.classList.remove("in");
      window.setTimeout(function () { card.remove(); }, 600);
    }, reduced ? 0 : 4200);
  }
  if (moments && !reduced) {
    floatMoment();
    window.setInterval(floatMoment, 2200);
  }

  function nyParts(date) {
    var fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23"
    });
    var bag = { hour: 0, minute: 0, second: 0 };
    fmt.formatToParts(date).forEach(function (part) {
      if (part.type === "hour" || part.type === "minute" || part.type === "second") {
        bag[part.type] = Number(part.value);
      }
    });
    return bag.hour * 3600 + bag.minute * 60 + bag.second;
  }

  var sessions = [
    { name: "Asia", start: 18 * 3600, end: 26 * 3600 },
    { name: "London", start: 2 * 3600, end: 8 * 3600 },
    { name: "NY AM", start: 8 * 3600, end: 12 * 3600 },
    { name: "NY PM", start: 12 * 3600, end: 18 * 3600 }
  ];

  function tickSession() {
    var name = document.getElementById("session-name");
    var count = document.getElementById("session-count");
    if (!name || !count) return;
    var seconds = nyParts(new Date());
    var clock = seconds < 2 * 3600 ? seconds + 24 * 3600 : seconds;
    var current = sessions[0];
    sessions.forEach(function (session) {
      var start = session.start < 2 * 3600 ? session.start + 24 * 3600 : session.start;
      var end = session.end;
      if (clock >= start && clock < end) current = session;
    });
    var end = current.end;
    var left = end - clock;
    if (left < 0) left += 24 * 3600;
    var hours = Math.floor(left / 3600);
    var mins = Math.floor((left % 3600) / 60);
    var secs = left % 60;
    name.textContent = current.name;
    count.textContent = hours + "h " + String(mins).padStart(2, "0") + "m " + String(secs).padStart(2, "0") + "s left";
    var hit = document.querySelector(".news-hit");
    if (hit && hit.getAttribute("data-when")) {
      var when = Date.parse(hit.getAttribute("data-when"));
      if (!isNaN(when)) {
        var delta = Math.max(0, Math.round((when - Date.now()) / 1000));
        var dh = Math.floor(delta / 3600);
        var dm = Math.floor((delta % 3600) / 60);
        var title = hit.getAttribute("data-title") || "";
        var label = dh >= 24 ? Math.floor(dh / 24) + "d " + (dh % 24) + "h" : (dh > 0 ? dh + "h " + dm + "m" : dm + "m");
        hit.textContent = title + " · " + label;
      }
    }
  }
  tickSession();
  if (!reduced) window.setInterval(tickSession, 1000);
})();
