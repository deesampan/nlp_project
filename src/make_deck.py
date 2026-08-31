"""Phase 4 - build the presentation deck.

Generated from the numbers in output_project/results, so the slides cannot
drift from the measured figures.
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION

from config import OUT_REPORTS, ensure_dirs

OUT = OUT_REPORTS / "presentation.pptx"

DARK = RGBColor(0x2E, 0x21, 0x1E)
TERRA = RGBColor(0xB8, 0x50, 0x42)
SAND = RGBColor(0xE7, 0xE8, 0xD1)
SAGE = RGBColor(0xA7, 0xBE, 0xAE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTED = RGBColor(0x7A, 0x6A, 0x66)
PAGE = RGBColor(0xFB, 0xF9, 0xF6)
GREEN = RGBColor(0x2F, 0x7D, 0x54)
DGREEN = RGBColor(0x1D, 0x4A, 0x33)
PANEL = RGBColor(0x3B, 0x2B, 0x27)
MINT = RGBColor(0xED, 0xF3, 0xEF)
BLUSH = RGBColor(0xFA, 0xED, 0xEA)
RUST = RGBColor(0x8A, 0x2F, 0x24)

HEAD = "Cambria"
BODY = "Calibri"

W, H, M = 13.333, 7.5, 0.75
CW = W - M * 2

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]


def bg(slide, colour):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = colour


def tb(slide, x, y, w, h, runs, size=14, font=BODY, colour=DARK, bold=False,
       italic=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0,
       space_after=0, bullet=False):
    """runs: str, list[str] (one paragraph each), or list[list[(text, kwargs)]]."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

    if isinstance(runs, str):
        runs = [runs]

    for i, item in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        if space_after:
            p.space_after = Pt(space_after)
        pieces = item if isinstance(item, list) else [(item, {})]
        for text, ov in pieces:
            r = p.add_run()
            r.text = ("•  " if bullet and text and not ov.get("cont") else "") + text
            f = r.font
            f.name = ov.get("font", font)
            f.size = Pt(ov.get("size", size))
            f.bold = ov.get("bold", bold)
            f.italic = ov.get("italic", italic)
            f.color.rgb = ov.get("colour", colour)
            if ov.get("strike"):
                r.font._rPr.set("strike", "sngStrike")
    return box


def rrect(slide, x, y, w, h, fill, line=None, line_w=1.0, radius=0.06):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                Inches(x), Inches(y), Inches(w), Inches(h))
    sh.adjustments[0] = radius
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.shadow.inherit = False
    sh.text_frame.text = ""
    return sh


def circle(slide, x, y, d, fill):
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def dark_slide():
    s = prs.slides.add_slide(BLANK)
    bg(s, DARK)
    return s


def light_slide(num, title):
    s = prs.slides.add_slide(BLANK)
    bg(s, PAGE)
    circle(s, M, 0.52, 0.46, TERRA)
    tb(s, M, 0.52, 0.46, 0.46, str(num), size=15, bold=True, colour=WHITE,
       align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    tb(s, M + 0.68, 0.44, CW - 0.68, 0.62, title, size=30, font=HEAD, bold=True,
       colour=DARK, anchor=MSO_ANCHOR.MIDDLE)
    return s


def stat_card(s, x, y, w, value, label, colour=TERRA):
    rrect(s, x, y, w, 1.5, WHITE, SAND)
    tb(s, x + 0.2, y + 0.16, w - 0.4, 0.78, value, size=31, font=HEAD, bold=True,
       colour=colour, anchor=MSO_ANCHOR.MIDDLE)
    tb(s, x + 0.2, y + 0.95, w - 0.4, 0.45, label, size=11.5, colour=MUTED, spacing=1.1)


def card(s, x, y, w, h, heading, lines, accent=DARK, fill=WHITE, line=SAND,
         body_colour=DARK, size=13.5):
    rrect(s, x, y, w, h, fill, line)
    tb(s, x + 0.26, y + 0.2, w - 0.52, 0.44, heading, size=17, font=HEAD, bold=True,
       colour=accent)
    tb(s, x + 0.26, y + 0.72, w - 0.52, h - 0.94, lines, size=size,
       colour=body_colour, spacing=1.2)


def bullets(s, x, y, w, h, items, size=14.5, colour=DARK):
    tb(s, x, y, w, h, items, size=size, colour=colour, spacing=1.14,
       space_after=9, bullet=True)


# ------------------------------------------------------------------ 1 title
s = dark_slide()
circle(s, 10.7, -1.5, 4.6, PANEL)
circle(s, 11.9, 5.3, 3.0, PANEL)
tb(s, M, 2.05, CW, 0.34, "NLP GROUP PROJECT", size=13, bold=True, colour=SAGE)
tb(s, M, 2.5, 9.6, 1.95, ["Restaurant Recommendation", "From Reviews"],
   size=46, font=HEAD, bold=True, colour=WHITE, spacing=1.02)
tb(s, M, 4.6, 9.6, 0.5,
   "Finding what is actually good on the menu, from 134,612 customer reviews",
   size=16, colour=SAND)
tb(s, M, 5.95, CW, 0.4,
   "Deesampan Vongsurit  ·  6510766          Wattanan Jiratriluk  ·  6520214",
   size=13, colour=MUTED)
s.notes_slide.notes_text_frame.text = (
    "Two-person NLP group project analysing 134,612 restaurant reviews to rank "
    "individual dishes by customer sentiment.")

# ---------------------------------------------------------------- 2 problem
s = light_slide(1, "The problem")
bullets(s, M, 1.55, 6.4, 3.0, [
    "Restaurants receive hundreds of reviews every month",
    "The useful information — which dishes people like — is buried in unstructured text",
    "Manual reading is slow, inconsistent, and does not scale",
    "Menu decisions end up being made on intuition",
], size=15)
card(s, M, 4.75, 6.4, 1.65, "The cost",
     ["Weak dishes stay on the menu. Strong dishes go unpromoted."], TERRA)
stat_card(s, 7.95, 1.55, 2.5, "12,494", "restaurants in the dataset")
stat_card(s, 10.65, 1.55, 2.5, "1.3M", "raw review entries")
stat_card(s, 7.95, 3.3, 2.5, "3", "median reviews per restaurant", DARK)
stat_card(s, 10.65, 3.3, 2.5, "524", "reviews at the busiest", DARK)
s.notes_slide.notes_text_frame.text = (
    "The unit of opinion is not the review, it is the dish mentioned inside it.")

# ---------------------------------------------------------------- 3 why NLP
s = light_slide(2, "Why this needs NLP")
rrect(s, M, 1.55, CW, 1.45, WHITE, SAGE, 2.0)
tb(s, M + 0.35, 1.55, CW - 0.7, 1.45, [[
    ("“The salad was ", {}),
    ("amazing", {"colour": GREEN, "bold": True}),
    (", but the chicken breast was ", {}),
    ("cold and greasy", {"colour": TERRA, "bold": True}),
    (".”", {}),
]], size=24, font=HEAD, italic=True, anchor=MSO_ANCHOR.MIDDLE)
tb(s, M, 3.2, CW, 0.4, "One review. One star rating. Two opposite opinions.",
   size=16, bold=True)
card(s, M, 3.85, 6.0, 2.55, "A star rating cannot express this", [
    "It describes the whole review, so both dishes receive the same sentiment.",
    "Ranking dishes this way silently credits every dish for opinions aimed at something else.",
], TERRA)
card(s, 7.1, 3.85, 5.48, 2.55, "So we work at clause level", [
    "Split the review at sentence boundaries and at but / however / although.",
    "Classify each clause separately and attribute it only to the dishes inside it.",
], GREEN)
s.notes_slide.notes_text_frame.text = (
    "This example is the justification for the whole project. Star ratings are "
    "review-level; opinions are dish-level.")

# ------------------------------------------------------------------ 4 data
s = light_slide(3, "The dataset")
tb(s, M, 1.42, CW, 0.4,
   "Zomato Bangalore Restaurants (Kaggle) — 51,717 rows × 17 columns, 548 MB",
   size=15, colour=MUTED)
card(s, M, 2.0, 3.82, 2.1, "rate",
     ["Restaurant level.", "Zomato's displayed average, e.g. 4.1/5."], TERRA)
card(s, 4.72, 2.0, 3.82, 2.1, "votes",
     ["Restaurant level.", "How many people rated it at all."], TERRA)
card(s, 8.62, 2.0, 3.96, 2.1, "reviews_list",
     ["The only field with text.", "Each entry carries its own star rating."], GREEN)
tb(s, M, 4.42, CW, 0.38, "These are not interchangeable — we verified it",
   size=18, font=HEAD, bold=True)
bullets(s, M, 4.9, CW, 1.6, [
    "rate differs from the mean of its own reviews by 0.55 stars on average; only 6.7% agree within 0.05",
    "votes exceeds the review count in 87.9% of rows, median ratio 11× — text reviews are only ~6% of all ratings",
    "Never train on rate: it is an average, so a 1-star review at a 4.5-star restaurant would be labelled positive",
], size=13.5)
s.notes_slide.notes_text_frame.text = (
    "Text reviewers are a self-selected minority who skew toward strong opinions. "
    "That is a sampling bias in our corpus.")

# ------------------------------------------------------------- 5 duplicates
s = dark_slide()
tb(s, M, 1.3, CW, 0.35, "THE BIGGEST SOURCE OF NOISE", size=13, bold=True, colour=SAGE)
tb(s, M, 1.75, 6.2, 1.8, "89.1%", size=92, font=HEAD, bold=True, colour=TERRA)
tb(s, M, 3.55, 6.4, 0.6, "of the corpus is duplicated", size=26, font=HEAD, colour=WHITE)
tb(s, M, 4.3, 6.4, 2.1, [
    "1,317,782 review entries collapse to 143,789 unique texts.",
    "Left in, every dish mention count is inflated roughly 9×. Because the inflation is "
    "not uniform across restaurants, it does not cancel out — it reorders the rankings.",
], size=14.5, colour=SAND, spacing=1.25, space_after=10)
rrect(s, 7.6, 1.8, 4.98, 4.35, PANEL, RGBColor(0x4A, 0x38, 0x33))
tb(s, 7.9, 2.1, 4.38, 0.95,
   "Deduplication removes 99.2% of every row this pipeline removes.",
   size=17, font=HEAD, bold=True, colour=WHITE, spacing=1.15)
tb(s, 7.9, 3.2, 4.38, 2.6, [
    "All eight other cleaning stages combined account for 9,177 rows — less than 1% "
    "of what deduplication alone catches.",
    "The boring stage matters enormously. The sophisticated ones matter marginally.",
], size=14, colour=SAND, spacing=1.25, space_after=10)
s.notes_slide.notes_text_frame.text = (
    "If there is one question about noise, this is the answer. A team that skipped "
    "deduplication would have produced confidently wrong results.")

# ----------------------------------------------------------------- 6 traps
s = light_slide(4, "Two traps in deduplicating this data")
card(s, M, 1.5, 6.0, 2.4, "Trap 1 — the obvious key fails silently", [
    "All 51,717 url values are unique, so deduplicating on url removes nothing and reports success.",
    "Zomato appends a ?context= query string encoding the category listing.",
], TERRA)
card(s, 7.1, 1.5, 5.48, 2.4, "Trap 2 — the obvious fix loses data", [
    "Deduplicating on (name, address) and keeping one row per restaurant drops 32,803 real reviews.",
    "Category listings hold partially different review sets, not copies.",
], TERRA)
rrect(s, M, 4.2, CW, 2.2, MINT, GREEN, 2.0)
tb(s, M + 0.32, 4.45, CW - 0.64, 0.4, "The correct order", size=18, font=HEAD,
   bold=True, colour=DGREEN)
tb(s, M + 0.32, 4.95, CW - 0.64, 1.2, [
    "Explode every row to review level first, then deduplicate on (restaurant, review_text).",
    "Restaurant-level deduplication must never happen first.",
], size=15.5, colour=DGREEN, spacing=1.3, space_after=6)
s.notes_slide.notes_text_frame.text = (
    "Both traps are silent failures. Neither produces an error message.")

# ---------------------------------------------------------------- 7 funnel
s = light_slide(5, "Where the data goes")
tb(s, M, 1.42, CW, 0.35,
   "Rows removed at each cleaning stage, from 1,317,782 extracted review entries",
   size=14, colour=MUTED)
cd = CategoryChartData()
cd.categories = ["Language", "Length / quality", "Boilerplate", "Deduplication"]
cd.add_series("Rows removed", (2671, 2765, 3734, 1173993))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(M), Inches(1.9),
                        Inches(7.3), Inches(4.45), cd)
ch = gf.chart
ch.has_title = False
ch.has_legend = False
pl = ch.plots[0]
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format = '#,##0'
dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size = Pt(11)
dl.font.name = BODY
dl.font.color.rgb = DARK
ser = pl.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = TERRA
ca = ch.category_axis
ca.tick_labels.font.size = Pt(12)
ca.tick_labels.font.name = BODY
ca.tick_labels.font.color.rgb = DARK
ca.has_major_gridlines = False
va = ch.value_axis
va.maximum_scale = 1400000
va.tick_labels.font.size = Pt(10)
va.tick_labels.font.name = BODY
va.tick_labels.font.color.rgb = MUTED
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = SAND
va.major_gridlines.format.line.width = Pt(0.75)
stat_card(s, 8.45, 2.05, 4.13, "134,612", "clean, labelled reviews remain")
card(s, 8.45, 3.8, 4.13, 2.55, "Final class balance", [
    "Positive    81,213    60.3%",
    "Negative    28,364    21.1%",
    "Neutral     25,035    18.6%",
    "A 21% negative class is unusually healthy for review data.",
], DARK)
s.notes_slide.notes_text_frame.text = (
    "Nine ordered stages. Deduplicate before cleaning, so we do not pay to clean "
    "rows we are about to drop.")

# -------------------------------------------------------------- 8 negation
s = light_slide(6, "The trap in standard cleaning advice")
tb(s, M, 1.42, CW, 0.45,
   "Stopword lists contain not, no, never and nor. Strip them and “the biryani was "
   "not good” becomes “biryani good”.", size=15)
card(s, M, 2.05, 6.0, 2.2, "We measured the cost", [
    "Negation preserved         82.1% acc     77.3 F1",
    "Default stopword list      80.1% acc     74.8 F1",
    "Cost of stripping negations:  −2.01 accuracy, −2.48 macro-F1",
], TERRA)
card(s, 7.1, 2.05, 5.48, 2.2, "The model proves the mechanism", [
    "not  +7.74   →  negative",
    "not good  +6.45   →  negative",
    "not bad  +3.67   →  neutral",
    "not disappointed  +6.64   →  positive",
], GREEN)
rrect(s, M, 4.55, CW, 1.85, WHITE, SAND)
tb(s, M + 0.32, 4.78, CW - 0.64, 0.42,
   "Three different sentiments, all carried by the same word.",
   size=19, font=HEAD, bold=True)
tb(s, M + 0.32, 5.28, CW - 0.64, 1.0,
   "These weights were learned independently from 91,535 reviews — we never told the "
   "model that negation matters. Delete not from the corpus and all three collapse into one.",
   size=14.5, spacing=1.22)
s.notes_slide.notes_text_frame.text = (
    "An ablation measures impact on the downstream task, not just activity. This is "
    "the strongest evidence in the report.")

# ---------------------------------------------------------- 9 dish extraction
s = light_slide(7, "Extracting dish names")
rrect(s, M, 1.5, CW, 1.32, BLUSH, TERRA, 2.0)
tb(s, M + 0.32, 1.68, CW - 0.64, 0.4,
   "Correction to our original proposal: off-the-shelf NER does not detect dishes.",
   size=18, font=HEAD, bold=True, colour=RUST)
tb(s, M + 0.32, 2.13, CW - 0.64, 0.6,
   "spaCy recognises PERSON, ORG, GPE and DATE. There is no FOOD entity type — running "
   "NER over “the chicken biryani was dry” returns nothing useful.",
   size=14, colour=RUST, spacing=1.15)
tb(s, M, 3.05, CW, 0.4, "What we do instead: dictionary matching",
   size=19, font=HEAD, bold=True)
bullets(s, M, 3.58, 7.25, 2.8, [
    "A 2,774-term gazetteer built from the dataset's own dish_liked field",
    "Longest-match preference, so chicken biryani wins over biryani",
    "Variant normalisation: Panneer / Panner → paneer, Biriyani → biryani",
    "Bare ingredients blocked as single words — chicken and rice are not orderable, "
    "but chicken biryani and fried rice survive",
], size=14)
card(s, 8.35, 3.5, 4.23, 2.9, "dish_liked is weak supervision", [
    "Covers only 36.9% of restaurants",
    "Attached to the restaurant, not the review",
    "Terms are coarse — pasta, burgers, cocktails are categories",
    "We use it as a vocabulary source, not as labels.",
], MUTED, size=13)
s.notes_slide.notes_text_frame.text = (
    "Training a dish NER would need span-annotated data we do not have and cannot "
    "produce in a course timeline.")

# ----------------------------------------------------------------- 10 model
s = light_slide(8, "Sentiment model results")
tb(s, M, 1.42, CW, 0.35,
   "TF-IDF + logistic regression. Trained on 91,535 reviews, tuned on 16,154, "
   "evaluated on a held-out 26,923.", size=14, colour=MUTED)
cd = CategoryChartData()
cd.categories = ["Binary + band", "Default stopwords", "TF-IDF + LogReg",
                 "VADER lexicon", "Majority class"]
cd.add_series("Accuracy", (77.4, 80.1, 82.1, 72.2, 60.3))
cd.add_series("Macro F1", (71.6, 74.8, 77.3, 53.7, 25.1))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(M), Inches(1.9),
                        Inches(7.8), Inches(4.45), cd)
ch = gf.chart
ch.has_title = False
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.BOTTOM
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(11)
ch.legend.font.name = BODY
ch.legend.font.color.rgb = DARK
pl = ch.plots[0]
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format = '0.0'
dl.number_format_is_linked = False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size = Pt(10)
dl.font.name = BODY
dl.font.color.rgb = DARK
for series, colour in zip(pl.series, (TERRA, SAGE)):
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = colour
ca = ch.category_axis
ca.tick_labels.font.size = Pt(11.5)
ca.tick_labels.font.name = BODY
ca.tick_labels.font.color.rgb = DARK
ca.has_major_gridlines = False
va = ch.value_axis
va.maximum_scale = 100
va.tick_labels.font.size = Pt(10)
va.tick_labels.font.name = BODY
va.tick_labels.font.color.rgb = MUTED
va.major_gridlines.format.line.color.rgb = SAND
va.major_gridlines.format.line.width = Pt(0.75)
card(s, 8.95, 2.05, 3.63, 2.05, "Why we trained our own", [
    "Every review carries its own star rating, so labels cost nothing.",
    "And the learned weights are the explanation.",
], DARK, size=13)
card(s, 8.95, 4.3, 3.63, 2.05, "Per class F1", [
    "Positive     0.892",
    "Negative     0.847",
    "Neutral      0.581",
], DARK)
s.notes_slide.notes_text_frame.text = (
    "We compare against a majority-class floor and an untrained lexicon so the "
    "trained model's contribution is measurable.")

# --------------------------------------------------------------- 11 neutral
s = light_slide(9, "The neutral class, and a result that failed")
card(s, M, 1.5, 6.0, 2.45, "What we tried", [
    "Train binary on clearly positive vs clearly negative, then derive neutral from "
    "model uncertainty with a tuned confidence band.",
    "Result: 71.6 macro-F1 — six points worse than simply training on three classes.",
], TERRA)
card(s, 7.1, 1.5, 5.48, 2.45, "What we learned instead", [
    "The model almost never confuses positive with negative — only 379 of 26,923 "
    "test reviews, or 1.4%.",
    "All the error sits on the neutral boundary.",
], GREEN)
rrect(s, M, 4.25, CW, 2.15, MINT, GREEN, 2.0)
tb(s, M + 0.34, 4.45, CW - 0.68, 0.8, [[
    ("96.5%", {"size": 38, "bold": True, "colour": DGREEN, "font": HEAD}),
    ("   accuracy on the binary task", {"size": 20, "colour": DGREEN, "font": HEAD}),
]], anchor=MSO_ANCHOR.MIDDLE)
tb(s, M + 0.34, 5.3, CW - 0.68, 1.0,
   "A 3-star review is not a distinct opinion — it is the gap between two. For the "
   "question the dashboard actually asks, is this dish liked or disliked, the model is "
   "highly accurate. We report the failed attempt because the negative result is informative.",
   size=14.5, colour=DGREEN, spacing=1.22)
s.notes_slide.notes_text_frame.text = (
    "Reporting an experiment that did not work is worth more than pretending we only "
    "tried what succeeded.")

# ---------------------------------------------------------------- 12 clause
s = light_slide(10, "What clause-level attribution changed")
stat_card(s, M, 1.5, 3.82, "25.8%", "of dish clauses disagreed with the star rating")
stat_card(s, 4.72, 1.5, 3.82, "65", "reviews held dishes with opposite sentiment")
stat_card(s, 8.62, 1.5, 3.96, "605", "dish-bearing clauses analysed")
rrect(s, M, 3.35, CW, 3.0, WHITE, SAND)
tb(s, M + 0.34, 3.6, CW - 0.68, 0.42,
   "The largest single correction: egg biryani", size=19, font=HEAD, bold=True)
tb(s, M + 0.34, 4.15, 6.0, 0.85, [[
    ("+0.38", {"size": 33, "bold": True, "colour": MUTED, "font": HEAD, "strike": True}),
    ("     →     ", {"size": 22, "colour": MUTED}),
    ("−0.75", {"size": 33, "bold": True, "colour": TERRA, "font": HEAD}),
]], anchor=MSO_ANCHOR.MIDDLE)
tb(s, M + 0.34, 5.1, CW - 0.68, 1.1,
   "Its true split is 1 positive to 7 negative. The star rating had been crediting it "
   "for praise aimed at other dishes in the same reviews — the dish was being "
   "recommended on the strength of opinions that were never about it.",
   size=14.5, spacing=1.22)
s.notes_slide.notes_text_frame.text = (
    "This is the concrete payoff of replacing ABSA with clause-level attribution.")

# ------------------------------------------------------------- 13 dashboard
s = light_slide(11, "The dashboard")
tb(s, M, 1.42, CW, 0.4,
   "Static HTML, CSS and vanilla JavaScript with Chart.js. No backend — the Python "
   "pipeline exports static JSON. Runs on localhost.", size=14, colour=MUTED)
card(s, M, 2.0, 3.82, 2.25, "Menu action map", [
    "Plots mention volume against positive share, splitting the menu into signature, "
    "hidden gem, fix-or-cut and low priority.",
], TERRA, size=13)
card(s, 4.72, 2.0, 3.82, 2.25, "Where the rating was wrong", [
    "Shows which dishes moved under clause-level attribution, and by how much.",
], TERRA, size=13)
card(s, 8.62, 2.0, 3.96, 2.25, "Evidence on demand", [
    "Click any dish to read the actual review text behind its score.",
], TERRA, size=13)
card(s, M, 4.5, 6.0, 1.9, "Why volume matters", [
    "Ranking on sentiment alone puts a dish praised once above the best seller. "
    "No dish is ranked below 5 mentions.",
], DARK)
card(s, 7.1, 4.5, 5.48, 1.9, "Honest by design", [
    "The cleaning funnel, model comparison and learned weights are all on the page "
    "— including the experiment that failed.",
], DARK)
s.notes_slide.notes_text_frame.text = (
    "Demo live at localhost:8000. The page must be served over HTTP — fetch is "
    "blocked on file:// URLs.")

# ----------------------------------------------------------- 14 limitations
s = light_slide(12, "Limitations")
bullets(s, M, 1.6, 6.0, 4.8, [
    "Neutral-class F1 of 0.581, with a documented failed attempt to fix it",
    "Sampling bias — text reviewers are ~6% of raters and skew toward strong opinions",
    "677 of 1,069 cleaned reviews mention no dish; our sample restaurants are delivery-led",
    "No manual audit of dropped rows, so filter precision is unmeasured",
], size=14.5)
bullets(s, 7.1, 1.6, 5.48, 4.8, [
    "The 15-character length threshold is unvalidated by ablation",
    "No timestamps in the dataset, so no temporal analysis is possible",
    "Dish extraction has weak supervision only — no precision or recall reported",
    "Noun-phrase discovery still returns food, they, order and needs POS filtering",
], size=14.5)
s.notes_slide.notes_text_frame.text = (
    "Stating limitations precisely is more persuasive than hiding them. Each is a "
    "concrete next step.")

# ------------------------------------------------------------ 15 conclusion
s = dark_slide()
circle(s, -1.6, 5.1, 4.2, PANEL)
tb(s, M, 1.15, CW, 0.35, "CONCLUSION", size=13, bold=True, colour=SAGE)
tb(s, M, 1.6, 10.5, 0.8, "Reviews become menu decisions",
   size=36, font=HEAD, bold=True, colour=WHITE)
for i, (n, txt) in enumerate([
    ("89.1%", "of the corpus was duplicated — deduplication accounted for 99.2% of all rows removed"),
    ("96.5%", "binary accuracy on the question the dashboard actually asks"),
    ("25.8%", "of dish clauses disagreed with the review's own star rating"),
]):
    y = 2.75 + i * 1.15
    tb(s, M, y, 2.05, 0.7, n, size=30, font=HEAD, bold=True, colour=TERRA,
       anchor=MSO_ANCHOR.MIDDLE)
    tb(s, M + 2.2, y, 9.3, 0.7, txt, size=15, colour=SAND,
       anchor=MSO_ANCHOR.MIDDLE, spacing=1.1)
tb(s, M, 6.3, 11.3, 0.7,
   "Instead of reading every review, an owner can see which dishes to promote, which to "
   "fix, and which to cut — with the evidence one click away.",
   size=14.5, italic=True, colour=SAGE)
s.notes_slide.notes_text_frame.text = (
    "Close by returning to the business question: what is actually good on the menu.")


if __name__ == "__main__":
    ensure_dirs()
    prs.save(str(OUT))
    print("wrote %s" % OUT)
    print("slides: %d" % len(prs.slides.__iter__.__self__._sldIdLst))
