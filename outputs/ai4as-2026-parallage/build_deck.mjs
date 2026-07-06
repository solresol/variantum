import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const ROOT = "/Users/gregb/Documents/devel/variantum";
const OUT = path.join(ROOT, "outputs", "ai4as-2026-parallage");
const DATA = path.join(ROOT, "analysis", "vanessa-set1-metric-scatter-data.csv");
const RAW_PLOT = path.join(ROOT, "analysis", "vanessa-set1-raw-metric-scatter.png");
const RESIDUAL_PLOT = path.join(ROOT, "analysis", "vanessa-set1-length-adjusted-residual-scatter.png");
const LENGTH_PLOT = path.join(ROOT, "analysis", "vanessa-set1-length-and-composite-scatter.png");
const POPULATION_PLOT = path.join(ROOT, "analysis", "vanessa-set1-population-length-bias-scatter.png");
const FINAL_PPTX = path.join(OUT, "parallage_ai4as_2026_deck.pptx");
const PREVIEW = path.join(OUT, "deck_preview");
const ARTIFACT_TOOL_WORKSPACE = "/tmp/codex-presentations/ai4as-2026-parallage";

const W = 1280;
const H = 720;
const COLORS = {
  canvas: "#FFFFFF",
  ink: "#000000",
  body: "#222222",
  muted: "#555555",
  rule: "#B8BCC4",
  panel: "#EDEDED",
  highlight: "#FF6B35",
};

function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    return Object.fromEntries(headers.map((header, index) => [header, values[index]]));
  });
}

function toNumber(value) {
  return Number.parseFloat(value);
}

function ranks(values) {
  const order = values.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
  const output = new Array(values.length).fill(0);
  for (let i = 0; i < order.length; ) {
    let j = i;
    while (j + 1 < order.length && order[j + 1].value === order[i].value) j += 1;
    const rank = (i + j + 2) / 2;
    for (let k = i; k <= j; k += 1) output[order[k].index] = rank;
    i = j + 1;
  }
  return output;
}

function spearman(xs, ys) {
  const rx = ranks(xs);
  const ry = ranks(ys);
  const mx = rx.reduce((a, b) => a + b, 0) / rx.length;
  const my = ry.reduce((a, b) => a + b, 0) / ry.length;
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < rx.length; i += 1) {
    num += (rx[i] - mx) * (ry[i] - my);
    dx += (rx[i] - mx) ** 2;
    dy += (ry[i] - my) ** 2;
  }
  return num / Math.sqrt(dx * dy);
}

async function readImageBlob(imagePath) {
  const bytes = await fs.readFile(imagePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function writeBlob(outputPath, blob) {
  await fs.writeFile(outputPath, new Uint8Array(await blob.arrayBuffer()));
}

async function loadArtifactTool() {
  const entrypoint = path.join(
    ARTIFACT_TOOL_WORKSPACE,
    "node_modules",
    "@oai",
    "artifact-tool",
    "dist",
    "artifact_tool.mjs",
  );
  return import(pathToFileURL(entrypoint).href);
}

function addText(slide, name, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    name,
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: style.fontSize ?? 22,
    bold: style.bold ?? false,
    color: style.color ?? COLORS.body,
  };
  return shape;
}

function addPanel(slide, name, position, fill = COLORS.panel, line = "none") {
  return slide.shapes.add({
    geometry: "rect",
    name,
    position,
    fill,
    line:
      line === "none"
        ? { style: "solid", fill: "none", width: 0 }
        : { style: "solid", fill: line, width: 1 },
  });
}

function addRule(slide, name, left, top, width, height = 1) {
  addPanel(slide, name, { left, top, width, height }, COLORS.rule, "none");
}

function addFrame(slide, number, eyebrow, title) {
  slide.background.fill = COLORS.canvas;
  addText(slide, `eyebrow-${number}`, eyebrow.toUpperCase(), { left: 42, top: 35, width: 520, height: 28 }, {
    fontSize: 16,
    bold: true,
    color: COLORS.muted,
  });
  addText(slide, `slide-no-${number}`, String(number).padStart(2, "0"), { left: 1170, top: 35, width: 70, height: 28 }, {
    fontSize: 16,
    bold: true,
    color: COLORS.muted,
  });
  addText(slide, `title-${number}`, title, { left: 42, top: 78, width: 1110, height: 92 }, {
    fontSize: 40,
    bold: true,
    color: COLORS.ink,
  });
  addRule(slide, `top-rule-${number}`, 42, 170, 1196);
  addText(slide, `footer-${number}`, "AI4AS 2026 | Into the Parallage | 27 July 2026", { left: 42, top: 672, width: 640, height: 26 }, {
    fontSize: 16,
    color: COLORS.muted,
  });
}

function addBullets(slide, name, items, position, fontSize = 24) {
  const text = items.map((item) => `- ${item}`).join("\n");
  return addText(slide, name, text, position, { fontSize, color: COLORS.body });
}

function addMetric(slide, name, value, label, left, top, width = 250) {
  addPanel(slide, `${name}-panel`, { left, top, width, height: 145 }, COLORS.panel);
  addText(slide, `${name}-value`, value, { left: left + 18, top: top + 18, width: width - 36, height: 58 }, {
    fontSize: 42,
    bold: true,
    color: COLORS.ink,
  });
  addText(slide, `${name}-label`, label, { left: left + 18, top: top + 82, width: width - 36, height: 48 }, {
    fontSize: 17,
    color: COLORS.muted,
  });
}

async function addPlot(slide, name, imagePath, position, alt) {
  addPanel(slide, `${name}-frame`, position, "#FFFFFF", COLORS.rule);
  slide.images.add({
    blob: await readImageBlob(imagePath),
    contentType: "image/png",
    alt,
    fit: "contain",
    position: {
      left: position.left + 12,
      top: position.top + 12,
      width: position.width - 24,
      height: position.height - 24,
    },
  });
}

function notes(slide, paragraphs) {
  slide.speakerNotes.textFrame.setText(paragraphs);
  slide.speakerNotes.setVisible(true);
}

async function build() {
  const { Presentation, PresentationFile } = await loadArtifactTool();

  await fs.mkdir(OUT, { recursive: true });
  await fs.mkdir(PREVIEW, { recursive: true });

  const rows = parseCsv(await fs.readFile(DATA, "utf8"));
  const ratings = rows.map((row) => toNumber(row.rating));
  const bleu = rows.map((row) => toNumber(row.mean_bleu4));
  const rouge = rows.map((row) => toNumber(row.mean_rouge_l));
  const trigram = rows.map((row) => toNumber(row.mean_3gram_f1));
  const residBleu = rows.map((row) => toNumber(row.mean_bleu4_resid_badness));
  const residRouge = rows.map((row) => toNumber(row.mean_rouge_l_resid_badness));
  const residTrigram = rows.map((row) => toNumber(row.mean_3gram_f1_resid_badness));
  const lengths = rows.map((row) => toNumber(row.reference_words));
  const highRated = rows.filter((row) => toNumber(row.rating) >= 7).map((row) => row.lemma_display);
  const topResidual = [...rows]
    .sort((a, b) => toNumber(b.composite_resid_badness) - toNumber(a.composite_resid_badness))
    .slice(0, 4)
    .map((row) => row.lemma_display);

  const rawBleu = spearman(ratings, bleu);
  const rawRouge = spearman(ratings, rouge);
  const rawTrigram = spearman(ratings, trigram);
  const adjBleu = spearman(ratings, residBleu);
  const adjRouge = spearman(ratings, residRouge);
  const adjTrigram = spearman(ratings, residTrigram);

  const presentation = Presentation.create({
    slideSize: { width: W, height: H },
  });

  {
    const slide = presentation.slides.add();
    slide.background.fill = COLORS.canvas;
    addText(slide, "title-main", "Into the Parallage", { left: 42, top: 72, width: 860, height: 92 }, {
      fontSize: 66,
      bold: true,
      color: COLORS.ink,
    });
    addText(slide, "title-subtitle", "Harnessing abundance, plurality and divergence in AI translation of ancient texts", { left: 42, top: 178, width: 980, height: 88 }, {
      fontSize: 30,
      color: COLORS.body,
    });
    addRule(slide, "title-rule", 42, 305, 1196, 2);
    addText(slide, "title-authors", "Greg Baker | Shirley Chan | Vanessa Enriquez Raido | Greta Hawes", { left: 42, top: 338, width: 700, height: 62 }, {
      fontSize: 23,
      color: COLORS.body,
    });
    addText(slide, "title-venue", "AI4AS 2026, online mini-conference within DH2026\n27 July 2026 | Daejeon, South Korea / remote", { left: 42, top: 430, width: 620, height: 78 }, {
      fontSize: 21,
      color: COLORS.muted,
    });
    addPanel(slide, "title-panel", { left: 760, top: 338, width: 478, height: 238 }, COLORS.panel);
    addText(slide, "title-claim", "Preliminary pilot finding", { left: 790, top: 365, width: 410, height: 34 }, {
      fontSize: 19,
      bold: true,
      color: COLORS.muted,
    });
    addText(slide, "title-claim-body", "Human judgement shows a directional raw signal, but length explains enough that the responsible claim is methodological rather than conclusive.", { left: 790, top: 415, width: 405, height: 120 }, {
      fontSize: 25,
      bold: true,
      color: COLORS.ink,
    });
    addText(slide, "title-footer", "Published abstract: theoretical framework, corpus rationale, preliminary pilot findings", { left: 42, top: 672, width: 900, height: 26 }, {
      fontSize: 16,
      color: COLORS.muted,
    });
    notes(slide, [
      "Open by locating the talk: this is the AI4AS 2026 mini-conference on ancient scripts, held online on 27 July 2026.",
      "The submitted abstract commits us to theory, corpus rationale, and preliminary pilot findings. Vanessa's first-set review gives us the pilot result we can responsibly discuss.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 2, "problem", "A single fluent translation hides a plural process");
    addPanel(slide, "single-output", { left: 42, top: 220, width: 365, height: 285 }, COLORS.panel);
    addPanel(slide, "expert-process", { left: 458, top: 220, width: 365, height: 285 }, COLORS.panel);
    addPanel(slide, "ancient-risk", { left: 874, top: 220, width: 365, height: 285 }, COLORS.panel);
    addText(slide, "single-output-title", "Reader sees", { left: 72, top: 248, width: 300, height: 38 }, { fontSize: 24, bold: true, color: COLORS.ink });
    addText(slide, "single-output-body", "one clean English surface\none implied authority\none path through ambiguity", { left: 72, top: 310, width: 300, height: 125 }, { fontSize: 27, color: COLORS.body });
    addText(slide, "expert-process-title", "Translator does", { left: 488, top: 248, width: 300, height: 38 }, { fontSize: 24, bold: true, color: COLORS.ink });
    addText(slide, "expert-process-body", "alternatives\nconstraints\npurposes\nrisk management", { left: 488, top: 310, width: 300, height: 145 }, { fontSize: 30, color: COLORS.body });
    addText(slide, "ancient-risk-title", "AI can compress", { left: 904, top: 248, width: 300, height: 38 }, { fontSize: 24, bold: true, color: COLORS.ink });
    addText(slide, "ancient-risk-body", "low-resource uncertainty\nfragmentary evidence\ncultural specificity\ninto fluent confidence", { left: 904, top: 310, width: 300, height: 150 }, { fontSize: 26, color: COLORS.body });
    addText(slide, "problem-close", "The problem is not abundance. The problem is unstructured abundance.", { left: 42, top: 548, width: 970, height: 42 }, {
      fontSize: 30,
      bold: true,
      color: COLORS.ink,
    });
    notes(slide, [
      "The abstract begins from translation as situated and purposive, not a lookup task.",
      "Use this slide to set up why one fluent model output is risky for ancient-language work: it removes signs of choice just where the reader most needs them.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 3, "method", "Parallage turns AI abundance into inspectable evidence");
    addText(slide, "pack-label", "A translation pack is not a vote. It is a structured field of alternatives.", { left: 42, top: 200, width: 850, height: 50 }, {
      fontSize: 29,
      bold: true,
      color: COLORS.ink,
    });
    const labels = [
      ["literal", "source-facing\ncontrol"],
      ["readable", "reader-facing\ncontinuity"],
      ["interpretive", "scholarly\ncommitment"],
      ["uncertainty", "marked doubt\nand alternatives"],
      ["adversarial", "challenge case\nagainst fluency"],
    ];
    labels.forEach(([head, body], index) => {
      const left = 42 + index * 239;
      addPanel(slide, `pack-${head}`, { left, top: 305, width: 205, height: 180 }, index === 3 ? "#FFE4D8" : COLORS.panel);
      addText(slide, `pack-${head}-head`, head, { left: left + 16, top: 328, width: 170, height: 34 }, {
        fontSize: 22,
        bold: true,
        color: index === 3 ? COLORS.highlight : COLORS.ink,
      });
      addText(slide, `pack-${head}-body`, body, { left: left + 16, top: 382, width: 170, height: 78 }, {
        fontSize: 23,
        color: COLORS.body,
      });
    });
    addText(slide, "pack-cues", "Inspection cues: source-segment alignment | named entities | ambiguity points | differences that matter", { left: 42, top: 548, width: 1065, height: 38 }, {
      fontSize: 24,
      color: COLORS.body,
    });
    notes(slide, [
      "This is the core methodological claim. Parallage is not an attempt to make one better AI translation.",
      "It structures model abundance into a pack that makes interpretive choice visible: literal, readable, interpretive, uncertainty-marked, and adversarial renderings with cues for inspection.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 4, "corpus", "The corpus makes reliability hard to outsource");
    addPanel(slide, "greek-panel", { left: 42, top: 220, width: 560, height: 292 }, COLORS.panel);
    addPanel(slide, "chinese-panel", { left: 678, top: 220, width: 560, height: 292 }, COLORS.panel);
    addText(slide, "greek-title", "Stephanos of Byzantium, Ethnica", { left: 78, top: 255, width: 470, height: 40 }, { fontSize: 30, bold: true, color: COLORS.ink });
    addBullets(slide, "greek-bullets", [
      "geographical lexicon",
      "compressed source tradition",
      "named entities carry the argument",
      "pilot analysis available now",
    ], { left: 78, top: 325, width: 455, height: 145 }, 23);
    addText(slide, "chinese-title", "Hanshu Dilizhi", { left: 714, top: 255, width: 470, height: 40 }, { fontSize: 30, bold: true, color: COLORS.ink });
    addBullets(slide, "chinese-bullets", [
      "Classical Chinese geography",
      "dense administrative and cultural categories",
      "tests the same method outside Greek",
      "evaluation stream still to complete",
    ], { left: 714, top: 325, width: 455, height: 145 }, 23);
    addText(slide, "corpus-conclusion", "Neither case lets a non-source-language reader simply defer to a stable complete English translation.", { left: 42, top: 555, width: 1050, height: 42 }, {
      fontSize: 29,
      bold: true,
      color: COLORS.ink,
    });
    notes(slide, [
      "The abstract names two corpora: Stephanos and Hanshu Dilizhi.",
      "Make the rationale explicit: these are not just examples; they are contexts where trust and agency become visible because the reader cannot rely on a finished English canon.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 5, "pilot design", "The first pilot asks whether expert judgement tracks overlap fragility");
    addMetric(slide, "n", "n=10", "Vanessa Set 1 Greek passages", 42, 220);
    addMetric(slide, "range", "18-268", "reference words per passage", 318, 220);
    addMetric(slide, "metrics", "3", "BLEU, ROUGE-L, 3-gram F1", 594, 220);
    addMetric(slide, "population", "101", "v3 rows for length model", 870, 220);
    addBullets(slide, "pilot-bullets", [
      "Vanessa rated expected divergence from hidden human translations.",
      "We compared those ratings with sentence-aligned overlap metrics.",
      "Then we adjusted scores for reference length, because all three metrics worsen on longer documents.",
    ], { left: 42, top: 430, width: 1080, height: 150 }, 26);
    notes(slide, [
      "Explain the design carefully. Vanessa's rating is human judgement about expected divergence.",
      "The automatic scores compare focal machine outputs against approved hidden human translations. They are diagnostic proxies, not ground truth for translation quality.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 6, "raw evidence", "Raw overlap gives a directional but fragile signal");
    await addPlot(slide, "raw-plot", RAW_PLOT, { left: 42, top: 202, width: 760, height: 410 }, "Raw metric scatter plots against Vanessa rating");
    addPanel(slide, "raw-readout", { left: 842, top: 202, width: 396, height: 410 }, COLORS.panel);
    addText(slide, "raw-readout-title", "Spearman r\nrating vs raw score", { left: 872, top: 235, width: 330, height: 70 }, {
      fontSize: 27,
      bold: true,
      color: COLORS.ink,
    });
    addText(slide, "raw-readout-values", `BLEU: ${rawBleu.toFixed(2)}\nROUGE-L: ${rawRouge.toFixed(2)}\n3-gram F1: ${rawTrigram.toFixed(2)}`, { left: 872, top: 345, width: 320, height: 128 }, {
      fontSize: 34,
      bold: true,
      color: COLORS.ink,
    });
    addText(slide, "raw-readout-note", "Negative is the expected direction: higher human divergence rating, lower lexical overlap.", { left: 872, top: 510, width: 320, height: 65 }, {
      fontSize: 20,
      color: COLORS.muted,
    });
    notes(slide, [
      "This is the answer to the first version of the question: yes, weakly and directionally, Vanessa was often pointing toward lower overlap cases.",
      "But the correlations are modest and the sample is only ten. Treat this as a raw signal, not the conclusion.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 7, "length confound", "Length is a real confound, not a footnote");
    await addPlot(slide, "population-plot", POPULATION_PLOT, { left: 42, top: 202, width: 650, height: 430 }, "Population length-bias scatter plot");
    await addPlot(slide, "length-plot", LENGTH_PLOT, { left: 725, top: 202, width: 513, height: 430 }, "Length and composite residual scatter plot");
    addText(slide, "length-caption", `Set 1 spans ${Math.min(...lengths).toFixed(0)}-${Math.max(...lengths).toFixed(0)} reference words, and Vanessa's ratings also rise with length.`, { left: 42, top: 630, width: 980, height: 34 }, {
      fontSize: 20,
      color: COLORS.body,
    });
    notes(slide, [
      "All of the overlap metrics do worse on longer documents in the broader population.",
      "That matters because Set 1 is small and Vanessa's ratings also rise with length. If we do not control for length, we overstate what the raw metrics are telling us.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 8, "adjusted evidence", "After length adjustment, the signal becomes cautious");
    await addPlot(slide, "residual-plot", RESIDUAL_PLOT, { left: 42, top: 202, width: 760, height: 410 }, "Length-adjusted residual scatter plots against Vanessa rating");
    addPanel(slide, "adjusted-readout", { left: 842, top: 202, width: 396, height: 410 }, COLORS.panel);
    addText(slide, "adjusted-readout-title", "Spearman r\nrating vs residual badness", { left: 872, top: 230, width: 330, height: 82 }, {
      fontSize: 26,
      bold: true,
      color: COLORS.ink,
    });
    addText(slide, "adjusted-readout-values", `BLEU: ${adjBleu.toFixed(2)}\nROUGE-L: ${adjRouge.toFixed(2)}\n3-gram F1: ${adjTrigram.toFixed(2)}`, { left: 872, top: 352, width: 320, height: 128 }, {
      fontSize: 34,
      bold: true,
      color: COLORS.ink,
    });
    addText(slide, "adjusted-readout-note", "The adjusted direction is positive, but weak at n=10. This is preliminary evidence for workflow value, not proof.", { left: 872, top: 515, width: 320, height: 72 }, {
      fontSize: 20,
      color: COLORS.muted,
    });
    notes(slide, [
      "This answers Greg's follow-up question. Once we account for length, there is still a hint of signal, especially on 3-gram F1 residual badness, but it is weak and not robust.",
      "The right claim is that the review task is producing analyzable judgement data and that the disagreements are diagnostically useful.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 9, "diagnosis", "The disagreements are the result, not a nuisance");
    addPanel(slide, "high-panel", { left: 42, top: 220, width: 365, height: 310 }, COLORS.panel);
    addPanel(slide, "resid-panel", { left: 458, top: 220, width: 365, height: 310 }, COLORS.panel);
    addPanel(slide, "mismatch-panel", { left: 874, top: 220, width: 365, height: 310 }, COLORS.panel);
    addText(slide, "high-title", "Human high-divergence cases", { left: 70, top: 250, width: 305, height: 58 }, {
      fontSize: 25,
      bold: true,
      color: COLORS.ink,
    });
    addBullets(slide, "high-list", highRated, { left: 70, top: 330, width: 300, height: 120 }, 25);
    addText(slide, "resid-title", "Worst after length adjustment", { left: 486, top: 250, width: 305, height: 58 }, {
      fontSize: 25,
      bold: true,
      color: COLORS.ink,
    });
    addBullets(slide, "resid-list", topResidual, { left: 486, top: 330, width: 300, height: 135 }, 24);
    addText(slide, "mismatch-title", "What the mismatch tells us", { left: 902, top: 250, width: 305, height: 58 }, {
      fontSize: 25,
      bold: true,
      color: COLORS.ink,
    });
    addBullets(slide, "mismatch-list", [
      "Karia: high rating, length explains much of the low score",
      "Kadmeia: low rating, poor adjusted overlap",
      "Kavalis: high rating, strong overlap",
    ], { left: 902, top: 330, width: 300, height: 145 }, 22);
    addText(slide, "diagnosis-line", "These are exactly the cases a pack-based interface should surface for review.", { left: 42, top: 570, width: 920, height: 40 }, {
      fontSize: 29,
      bold: true,
      color: COLORS.ink,
    });
    notes(slide, [
      "Use this slide to avoid sounding apologetic about the weak adjusted correlations.",
      "For Parallage, the mismatch between human judgement, overlap metrics, and document length is itself useful: it identifies where a reader or reviewer needs better evidence.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 10, "claim", "What we can responsibly claim at AI4AS");
    addPanel(slide, "claim-one", { left: 42, top: 220, width: 360, height: 230 }, COLORS.panel);
    addPanel(slide, "claim-two", { left: 460, top: 220, width: 360, height: 230 }, COLORS.panel);
    addPanel(slide, "claim-three", { left: 878, top: 220, width: 360, height: 230 }, COLORS.panel);
    addText(slide, "claim-one-head", "1. Method", { left: 72, top: 252, width: 300, height: 36 }, { fontSize: 26, bold: true, color: COLORS.ink });
    addText(slide, "claim-one-body", "Parallage gives AI translation abundance a visible, auditable structure.", { left: 72, top: 312, width: 290, height: 86 }, { fontSize: 25, color: COLORS.body });
    addText(slide, "claim-two-head", "2. Pilot", { left: 490, top: 252, width: 300, height: 36 }, { fontSize: 26, bold: true, color: COLORS.ink });
    addText(slide, "claim-two-body", "Vanessa's first set shows a raw signal, a length confound, and weak residual signal.", { left: 490, top: 312, width: 290, height: 105 }, { fontSize: 25, color: COLORS.body });
    addText(slide, "claim-three-head", "3. Next study", { left: 908, top: 252, width: 300, height: 36 }, { fontSize: 26, bold: true, color: COLORS.ink });
    addText(slide, "claim-three-body", "Scale to more reviewers, the Chinese stream, and direct comparison with single-output translation.", { left: 908, top: 312, width: 290, height: 112 }, { fontSize: 25, color: COLORS.body });
    addText(slide, "claim-close", "The evidence supports a publishable method-in-progress: not proof that the tool is better, but proof that the judgement problem is measurable.", { left: 42, top: 525, width: 1070, height: 74 }, {
      fontSize: 31,
      bold: true,
      color: COLORS.ink,
    });
    notes(slide, [
      "End with the strongest responsible claim.",
      "Do not claim the pilot proves Parallage improves reliability. Claim that Parallage turns multiplicity into a structured object for judgement, and that the first pilot shows how the judgement data can be analyzed.",
    ]);
  }

  {
    const slide = presentation.slides.add();
    addFrame(slide, 11, "sources", "Evidence base for this version");
    addBullets(slide, "source-list", [
      "AI4AS 2026 programme: the talk is in the 11:00-12:00 AI and Translations session on 27 July 2026.",
      "Published abstract: Baker, Chan, Enriquez Raido, Hawes, Into the Parallage.",
      "Macquarie project page: Into the Parallage: harnessing AI abundance in translation tasks.",
      "Variantum local analysis: Vanessa Set 1 scatter data and generated metric plots.",
    ], { left: 42, top: 220, width: 1060, height: 260 }, 26);
    addPanel(slide, "source-url-panel", { left: 42, top: 520, width: 1196, height: 88 }, COLORS.panel);
    addText(slide, "source-url-text", "https://ai4asconference.github.io/2026/abstracts/Session%201/Baker.pdf\noutputs/ai4as-2026-parallage/ and analysis/", { left: 68, top: 543, width: 1120, height: 46 }, {
      fontSize: 20,
      color: COLORS.muted,
    });
    notes(slide, [
      "Keep this slide as backup rather than presenting it unless questions come up.",
      "It makes the deck self-contained and records where the abstract and pilot evidence came from.",
    ]);
  }

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(PREVIEW, `${stem}.png`), await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(PREVIEW, `${stem}.layout.json`), await layout.text());
  }
  await writeBlob(path.join(PREVIEW, "deck-montage.webp"), await presentation.export({ format: "webp", montage: true, scale: 1 }));

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL_PPTX);
  console.log(FINAL_PPTX);
}

build().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
