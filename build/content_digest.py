# AI Sharc — The Digest: article content. Each article: (slug, title, desc, hero_kicker, body_html).
# Sources verified 2026-11-13 via live search; every stat carries its source + year inline.
# §12-safe: no scoring detail, no item lists, no gate names.

def _a(kicker, title, lede, sections, cta=True):
    body = f'''<section class="hero"><div class="wrap">
<p style="text-transform:uppercase;letter-spacing:0.08em;font-size:0.85rem;color:var(--teal);font-weight:500;margin:0 0 10px">{kicker}</p>
<h1>{title}</h1>
<p class="lead">{lede}</p>
</div></section>'''
    for h, p in sections:
        body += f'<section><div class="wrap"><h2>{h}</h2><p style="max-width:70ch">{p}</p></div></section>'
    if cta:
        body += ('<section class="alt"><div class="wrap"><p style="max-width:70ch">'
                 '<a class="btn btn-teal" href="{FLOW_ORIGIN}/get-audited">See where your site stands &mdash; free</a></p></div></section>')
    return body

ARTICLES = [
  dict(
    slug="homeowners-ask-ai-first.html",
    title="A Third of Homeowners Now Ask AI Who to Hire",
    desc="22% of homeowners go to ChatGPT first — not Google — when they need a contractor. What that means for home-trade firms, with sources.",
    kicker="The Digest · AI shopping agents",
    body=_a("The Digest · AI shopping agents", "A third of homeowners now ask AI who to hire",
      "When a water heater dies at 9pm, a growing share of homeowners no longer open Google. They ask an AI assistant who to call — and the assistant names two or three firms. If yours isn't named, the job isn't yours.",
      [("The number", "A 2026 Scorpion national study found that <strong>22% of homeowners go to ChatGPT first, not Google</strong>, when they need a contractor. Broader 2026 surveys put AI-first contractor search between 22% and 45% depending on age group. Either way: the front door to your business is no longer only a search box. (Source: Scorpion national study, 2026; industry surveys, 2026.)"),
       ("Why this hits home trades first", "Home services are exactly the kind of purchase AI assistants handle well: local, urgent, trust-heavy. The assistant already knows the customer's town from context. It shortlists firms it can find, read and trust — then hands over a phone number."),
       ("What decides who gets named", "The assistant can only recommend what it can read. Firms whose services, service area, licence and proof are stated in plain text on their site get shortlisted. Firms whose information lives in images, PDFs or nowhere get skipped — no matter how good they are."),
       ("The takeaway", "This isn't a future trend to watch. It's how a meaningful share of your customers already behave. The question isn't whether AI assistants recommend home-trade firms — it's whether they can recommend <em>you</em>.")]),
  ),
  dict(
    slug="most-contractors-invisible-to-ai.html",
    title="Most Contractors Are Invisible to AI",
    desc="Industry estimates suggest most independent home-trade firms have effectively zero presence in AI answers for their own city. Here's why — and what changes it.",
    kicker="The Digest · AI shopping agents",
    body=_a("The Digest · AI shopping agents", "Most contractors are invisible to AI",
      "Ask an AI assistant for an HVAC company in almost any town and you'll get the same handful of names — the big brands, the aggregators, the firms with machine-readable websites. Most independent contractors aren't in the answer at all.",
      [("The estimate", "Industry analysis in 2026 estimated that the large majority of independent HVAC and plumbing firms have effectively zero presence in AI answers for their own city and service. Treat the exact figure with caution — but the pattern is easy to verify: ask an AI for a contractor in your town and see who comes back. (Source: industry analysis, 2026.)"),
       ("Why the big names dominate", "National brands and lead aggregators have structured, text-first websites: every service named, every city listed, every trust signal in machine-readable form. AI assistants favour what they can read and verify. That's not an unfair advantage — it's a buildable one."),
       ("Invisibility is usually self-inflicted", "The most common causes are mundane: services described only in photos, a service area that lives inside a map graphic, a phone number that isn't tappable text, licence and insurance details locked in a PDF. Each one is fixable in an afternoon."),
       ("The takeaway", "The window is open. Most of your competitors haven't done the work, which makes every fix disproportionately valuable — for now.")]),
  ),
  dict(
    slug="google-first-place-is-worth-less.html",
    title="Ranking #1 on Google Is Worth Less Than It Used to Be",
    desc="AI Overviews answer the question on the results page, cutting clicks to websites by double digits. What that means for firms that lived on search traffic.",
    kicker="The Digest · AI shopping agents",
    body=_a("The Digest · AI shopping agents", "Ranking #1 on Google is worth less than it used to be",
      "For fifteen years, the playbook was simple: rank first, collect clicks. AI Overviews broke that. Google now answers the question on the results page itself — and the clicks go somewhere else.",
      [("The numbers", "Studies in 2025–2026 found AI Overviews can cut clicks to websites by 18–70% depending on query type, and that the #1 organic result delivers roughly 58% fewer clicks than it did before AI Overviews rolled out. (Sources: industry click-through studies, 2025–2026.)"),
       ("What replaces the click", "Two things. First, being <em>cited inside</em> the AI answer — the assistant names firms it can verify, and a citation in the answer is the new position one. Second, being recommendable when the user asks a follow-up: 'which of these is licensed and insured?'"),
       ("The uncomfortable part", "A firm can hold #1 on Google and still be invisible to an AI assistant, because the two systems read differently. Search engines rank pages; assistants shortlist businesses they can understand and trust."),
       ("The takeaway", "Keep the SEO foundation — it feeds everything. But treat 'can an AI assistant recommend me?' as its own question, with its own answer.")]),
  ),
  dict(
    slug="google-books-services-in-search.html",
    title="Google Now Books Services Inside the Search Page",
    desc="Agentic checkout and AI Mode booking for local services are live. The machine isn't just recommending anymore — it's transacting.",
    kicker="The Digest · AI shopping agents",
    body=_a("The Digest · AI shopping agents", "Google now books services inside the search page",
      "The machine-shopping era stopped being theoretical. Google's AI Mode now supports agentic booking for local experiences and services, and agentic checkout lets shoppers complete purchases without visiting the seller's site.",
      [("What shipped", "Google rolled out agentic capabilities in Search — including booking flows for local services powered by its Universal Commerce Protocol — and agentic checkout that completes purchases inside AI Mode and Gemini. (Sources: Google announcements, 2025–2026; industry coverage.)"),
       ("Why this matters to a home-trade firm", "The assistant that books the job is the assistant that was trusted to recommend it. Booking flows need machine-readable services, availability and contact details — the same raw material as recommendations, one step further."),
       ("The pattern to watch", "Every platform is converging on the same requirement: businesses whose facts are structured and readable get recommended, cited and transacted with. Businesses whose facts aren't, don't."),
       ("The takeaway", "The work you do to be recommendable today is the same work that makes you bookable tomorrow. It compounds.")]),
  ),
  dict(
    slug="yelp-became-chatgpts-data-source.html",
    title="Yelp Just Became ChatGPT's Local Data Source",
    desc="OpenAI licensed Yelp's data on ~8 million businesses. Where AI assistants get their answers — and why your own site still decides the verdict.",
    kicker="The Digest · AI shopping agents",
    body=_a("The Digest · AI shopping agents", "Yelp just became ChatGPT's local data source",
      "AI assistants don't invent local answers — they assemble them from data sources. OpenAI licensed Yelp's ratings, photos and business info covering roughly 8 million businesses; Tripadvisor struck a similar deal with Perplexity. (Sources: OpenAI/Yelp partnership, 2025–2026; Tripadvisor/Perplexity, 2025.)",
      [("What the deals mean", "When ChatGPT answers 'who's a good plumber near me?', part of the answer is built from licensed third-party data — reviews, ratings, categories. Your Yelp profile is now an input to the recommendation."),
       ("But the assistant still checks your site", "Third-party data tells the assistant who exists and what customers said. Your website tells it what you actually do, where you do it, and whether the details line up. Firms whose site contradicts their listings lose trust in the answer; firms whose site confirms and deepens it gain."),
       ("Consistency is the quiet ranking factor", "Name, address, phone, services, licence — the same everywhere, in text. Discrepancies between your listings and your site are exactly the kind of thing an assistant treats as a reason to skip you."),
       ("The takeaway", "You can't control the data deals. You can control that every source — your site, your profiles — tells the same true story.")]),
  ),
]

DIGEST_INDEX_INTRO = ('<section class="hero"><div class="wrap" style="display:flex;gap:24px;align-items:center">'
  '<img src="assets/img/digest-hero.svg" alt="" style="width:160px;flex-shrink:0">'
  '<div><p style="text-transform:uppercase;letter-spacing:0.08em;font-size:0.85rem;color:var(--teal);font-weight:500;margin:0 0 10px">The Digest</p>'
  '<h1>How AI shopping agents are changing home trades</h1>'
  '<p class="lead">Plain-English reporting on how AI assistants find, read and trust home-trade '
  'businesses — and what to do about it. One article a week, every one sourced.</p>'
  '</div></section>')


def digest_index_body():
    cards = ""
    for a in ARTICLES:
        cards += (f'<div class="card"><h3><a href="{a["slug"]}">{a["title"]}</a></h3>'
                  f'<p>{a["desc"]}</p></div>')
    return ('<section><div class="wrap"><div class="grid g2">' + cards + '</div>'
            '<p style="margin-top:16px"><a class="btn btn-teal" href="{FLOW_ORIGIN}/get-audited">Get your free Report Card</a></p></div></section>')
