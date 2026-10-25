import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import {
  benefits,
  faqs,
  logos,
  monthlyPlans,
  navLinks,
  posts,
  processSteps,
  services,
  testimonials,
} from './data'
import type { HealthResponse } from './types'
import { Cta, Gauge, LuxuryStage, Reveal, SectionRail, useCountUp } from './ui'

function GoldTag({ href, label }: { href: string; label: string }) {
  return (
    <a className="gold-tag" href={href}>
      <b>{label}</b>
      <small>&gt;&gt;&gt;</small>
    </a>
  )
}

export default function Landing() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [yearly, setYearly] = useState(false)
  const [faqOpen, setFaqOpen] = useState(0)
  const [process, setProcess] = useState(0)
  const [slide, setSlide] = useState(0)
  const [email, setEmail] = useState('')
  const [subscribed, setSubscribed] = useState(false)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [incidentCount, setIncidentCount] = useState(3254)
  const [statsOn, setStatsOn] = useState(false)
  const statsRef = useRef<HTMLElement>(null)
  const t = testimonials[slide]
  const step = processSteps[process]
  const plans = useMemo(
    () =>
      monthlyPlans.map((p) => ({
        ...p,
        price: yearly ? Math.round(p.price * 0.9) : p.price,
      })),
    [yearly],
  )
  const stat58 = useCountUp(58, statsOn)
  const stat73 = useCountUp(73, statsOn)
  const stat82 = useCountUp(82, statsOn)
  const stat91 = useCountUp(91, statsOn)

  useEffect(() => {
    let cancelled = false
    api
      .health()
      .then((h) => {
        if (!cancelled) setHealth(h)
      })
      .catch(() => {
        if (!cancelled) setHealth(null)
      })
    api
      .listIncidents()
      .then((list) => {
        if (!cancelled && list.length) setIncidentCount(list.length)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const id = window.setInterval(() => {
      setSlide((s) => (s + 1) % testimonials.length)
    }, 7000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    const el = statsRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setStatsOn(true)
      },
      { threshold: 0.3 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  function onSubscribe(e: FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setSubscribed(true)
  }

  return (
    <LuxuryStage>
      <header className="site-header">
        <a className="logo" href="#top">
          SENTINEL
          <sup>AI</sup>
        </a>
        <nav className={menuOpen ? 'open' : ''}>
          {navLinks.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setMenuOpen(false)}>
              {l.label}
            </a>
          ))}
        </nav>
        <Cta href="#console">Open Console</Cta>
        <button
          className="menu-btn"
          aria-label="Toggle menu"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span />
          <span />
        </button>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-lines" aria-hidden="true">
            <svg viewBox="0 0 1200 280" preserveAspectRatio="none">
              <path
                className="draw-path"
                d="M0 90 H340 C420 90 430 200 600 200 C770 200 780 90 860 90 H1200"
                fill="none"
                stroke="currentColor"
                strokeDasharray="6 8"
                strokeWidth="1.2"
              />
            </svg>
            <i className="node left pulse" />
            <i className="node right pulse" />
          </div>
          <p className="live-pill">
            <i className={health ? 'ok' : 'off'} />
            {health
              ? `${health.app} · ${health.ai_provider} · ${health.team}`
              : 'Backend offline — start uvicorn on :8000'}
          </p>
          <h1>
            <span>Build for</span>
            <span>Incident Repair</span>
            <span className="mark">Response</span>
          </h1>
          <p className="hero-copy">
            Ingest a software incident, generate an AI hypothesis, propose a
            patch, validate it in a disposable workspace, then wait for a human.
          </p>
          <a className="cta cta-gold hero-cta" href="#console">
            Open Console
          </a>

          <div className="hero-card float-card">
            <div className="dash">
              <div className="dash-top">
                <span>AI AUTOMATIONS</span>
                <b>This Month</b>
              </div>
              <Gauge value={incidentCount} />
              <div className="dash-pills">
                <span>Analyze</span>
                <span>Patch</span>
                <span>Validate</span>
              </div>
            </div>
          </div>

          <div className="hero-meta">
            <div className="pills">
              <span>Moderate</span>
              <span>Innovate</span>
              <span>Interactive</span>
            </div>
            <div className="trusted">
              <div className="mini-logos">
                <i />
                <i />
                <i />
                <i />
              </div>
              Trust by 5K+ businesses
            </div>
          </div>
        </section>

        <section className="marquee-wrap">
          <div className="pattern-field">
            <button className="float-btn" aria-label="Explore" type="button">
              →
            </button>
            <span className="crosshair" />
            <button className="float-btn" aria-label="Refresh" type="button">
              +
            </button>
          </div>
          <div className="marquee">
            <div className="track">
              {[...logos, ...logos].map((name, i) => (
                <span key={`${name}-${i}`}>{name}</span>
              ))}
            </div>
          </div>
        </section>

        <section className="about" id="about">
          <div className="frame">
            <div className="icon-row">
              <span>◆</span>
              <span>▣</span>
              <span>⬡</span>
              <span>◈</span>
              <span>☼</span>
              <span>◎</span>
            </div>
            <SectionRail label="About us" num="001" />
            <div className="about-grid">
              <GoldTag href="#console" label="Get Start" />
              <Reveal>
                <h2>
                  Local incident-response loop powered by{' '}
                  <span>Advanced AI Technology</span> for modern engineering
                  teams
                </h2>
                <Cta href="#console">Open Console</Cta>
                <div className="material">
                  <article>
                    <h3>Material</h3>
                    <p>
                      SentinelAI streamlines the path from a failing test to a
                      proposed patch. Analysis is a hypothesis. Validation is a
                      sandbox. Approval is a human.
                    </p>
                  </article>
                  <article>
                    <h3>Material</h3>
                    <p>
                      Built by Team TriNova. Mock provider for offline demos,
                      optional Gemini, SQLite state, FastAPI workflow.
                    </p>
                  </article>
                </div>
              </Reveal>
              <aside className="founder">
                <img src="https://i.pravatar.cc/180?img=68" alt="Team TriNova" />
                <strong>Team TriNova</strong>
                <span>Founders</span>
              </aside>
            </div>
          </div>
        </section>

        <section className="features" id="solution">
          <div className="frame">
            <SectionRail label="The Features" num="002" />
            <Reveal className="feature-grid">
              <div>
                <p className="kicker">AI AGENT</p>
                <h2>AI Solutions Built For Modern Teams</h2>
                <p>
                  One orchestrator owns the states: RECEIVED, ANALYZED,
                  PATCH_GENERATED, VALIDATED, then APPROVED or REJECTED. Failure
                  never silently pretends to succeed.
                </p>
              </div>
              <div className="mini-dash">
                <div className="dash">
                  <div className="dash-top">
                    <span>AI AUTOMATIONS</span>
                    <b>This Month</b>
                  </div>
                  <Gauge value={incidentCount} />
                </div>
              </div>
            </Reveal>
            <div className="agents-banner">
              <GoldTag href="#console" label="Get Start" />
              <h2>
                Intelligent <em>AI_Agents</em>
              </h2>
              <Cta href="#console">Open Console</Cta>
            </div>
          </div>
        </section>

        <section className="stats" id="case-study" ref={statsRef}>
          <div className="frame">
            <SectionRail label="The Statistics" num="003" />
            <Reveal>
              <h2>
                Teams are replacing ad-hoc incident chats with a gated AI
                repair loop — and the fastest ones already review diffs, not
                vibes.
              </h2>
            </Reveal>
            <div className="stat-row">
              <a className="gold-tag dark-gold" href="#console">
                <b>Book a Call</b>
                <small>&gt;&gt;&gt;</small>
              </a>
              <div className="big-stat">
                {stat58}
                <span>%</span>
              </div>
              <div className="stat">
                <strong>{stat73}%</strong>
                <p>of teams expect AI to improve daily productivity</p>
              </div>
              <div className="stat">
                <strong>{stat82}%</strong>
                <p>of companies are increasing investment in AI automation</p>
              </div>
              <div className="stat">
                <strong>{stat91}%</strong>
                <p>plan to adopt AI agents within the next two years</p>
              </div>
            </div>
          </div>
        </section>

        <section className="benefits">
          <div className="frame">
            <SectionRail label="Benefits" num="004" />
            <div className="benefits-head">
              <p className="kicker">Material</p>
              <p>
                We build an explicit workflow so engineers can ingest an
                incident, inspect a hypothesis, read a diff, and decide — with
                tests run off to the side of the real tree.
              </p>
              <Cta href="#console">Open Console</Cta>
            </div>
            <div className="benefit-cards">
              {benefits.map((b, i) => (
                <Reveal key={b.num} delay={i * 90}>
                  <article>
                    <span>{b.tag}</span>
                    <h3>
                      {b.num} {b.title}
                    </h3>
                    <p>{b.body}</p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="services">
          <div className="frame">
            <SectionRail label="Services" num="005" />
            <div className="svc-head">
              <h2>
                Best
                <br />
                for SME
              </h2>
            </div>
            <ul className="svc-list">
              {services.map((s) => (
                <li key={s.title}>
                  <strong>{s.title}</strong>
                  <div>
                    {s.tags.map((tag) => (
                      <em key={tag}>{tag}</em>
                    ))}
                  </div>
                  <span>↗</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="testimonials">
          <div className="frame">
            <SectionRail label="Testimonials" num="006" />
            <div className="quote-wrap fade-slide" key={t.name}>
              <img src={t.img} alt="" />
              <blockquote>“{t.quote}”</blockquote>
              <div className="who">
                <strong>{t.name}</strong>
                <span>{t.role}</span>
              </div>
              <div className="pager">
                <button
                  type="button"
                  onClick={() =>
                    setSlide((s) => (s === 0 ? testimonials.length - 1 : s - 1))
                  }
                >
                  ←
                </button>
                <span>
                  0-0{slide + 1} / 0-0{testimonials.length}
                </span>
                <button
                  type="button"
                  onClick={() => setSlide((s) => (s + 1) % testimonials.length)}
                >
                  →
                </button>
              </div>
            </div>
            <div className="kpi-row">
              <div>
                <small>Workflows Designed</small>
                <b>223</b>
              </div>
              <div>
                <small>Hours Saved Monthly</small>
                <b>32K</b>
              </div>
            </div>
          </div>
        </section>

        <section className="process">
          <div className="frame">
            <SectionRail label="The Process" num="007" />
            <div className="process-head">
              <h2>Custom AI system, built around your incident</h2>
              <Cta href="#console">Open Console</Cta>
            </div>
            <div className="tabs">
              {processSteps.map((s, i) => (
                <button
                  key={s.id}
                  type="button"
                  className={i === process ? 'active' : ''}
                  onClick={() => setProcess(i)}
                >
                  {s.label}
                  <span>{s.id}</span>
                </button>
              ))}
            </div>
            <article className="process-body fade-slide" key={step.id}>
              <p className="kicker">{step.kicker}</p>
              <h3>{step.label}</h3>
              <p>{step.body}</p>
            </article>
          </div>
        </section>

        <section className="blog" id="blog">
          <div className="frame">
            <SectionRail label="Blog" num="008" />
            <h2>Featured notes on a gated repair loop.</h2>
            <div className="posts">
              {posts.map((p, i) => (
                <article key={p.title}>
                  <span>0{i + 1}</span>
                  <div>
                    <small>
                      {p.date} · {p.tag}
                    </small>
                    <h3>{p.title}</h3>
                    <p>{p.body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="pricing" id="pricing">
          <div className="frame">
            <SectionRail label="Pricing" num="009" />
            <div className="price-head">
              <h2>Flexible AI solutions for every stage of growth</h2>
              <div className="toggle">
                <button
                  type="button"
                  className={!yearly ? 'on' : ''}
                  onClick={() => setYearly(false)}
                >
                  Monthly
                </button>
                <button
                  type="button"
                  className={yearly ? 'on' : ''}
                  onClick={() => setYearly(true)}
                >
                  Yearly <em>-10%</em>
                </button>
              </div>
            </div>
            <div className="plans">
              {plans.map((p) => (
                <article key={p.name} className={p.featured ? 'featured' : ''}>
                  <header>
                    <h3>{p.name}</h3>
                    <p>{p.desc}</p>
                    <b>
                      ${p.price.toLocaleString()}
                      <small>/month</small>
                    </b>
                  </header>
                  <Cta href="#console" variant={p.featured ? 'gold' : 'dark'}>
                    Open Console
                  </Cta>
                  <ul>
                    {p.features.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="cta-band">
          <div className="frame">
            <SectionRail label="The Statistics" num="010" />
            <h2>
              AI agents help teams walk incidents — without writing the original
              tree
            </h2>
            <div className="band-grid">
              <div>
                <p className="kicker">(I) Workflow Automation</p>
                <p>
                  Replace the scramble of “who looks at this stack trace” with
                  analyze → patch → validate → human. The source of truth stays
                  your repo; SentinelAI only proposes.
                </p>
                <Cta href="#console" variant="gold">
                  Open Console
                </Cta>
              </div>
              <div className="join">
                <h3>Transform incident response with a gated AI loop</h3>
                <Cta href="#console" variant="gold">
                  Join Us
                </Cta>
              </div>
            </div>
          </div>
        </section>

        <section className="faq">
          <div className="frame">
            <h2>
              Frequently Asked
              <br />
              Questions
            </h2>
            <div className="faq-list">
              {faqs.map((item, i) => (
                <div key={item.q} className={faqOpen === i ? 'open' : ''}>
                  <button type="button" onClick={() => setFaqOpen(faqOpen === i ? -1 : i)}>
                    {item.q}
                    <span>{faqOpen === i ? '−' : '+'}</span>
                  </button>
                  <p>{item.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="newsletter" id="contact">
          <div className="frame">
            <h2>Stay ahead with AI insights and industry updates</h2>
            <div className="news-grid">
              <form onSubmit={onSubscribe}>
                <label>Our newsletter</label>
                {subscribed ? (
                  <p className="thanks">Thank you! Your submission has been received.</p>
                ) : (
                  <div className="field">
                    <input
                      type="email"
                      required
                      placeholder="[enter your email]"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                    <button type="submit" aria-label="Subscribe">
                      →
                    </button>
                  </div>
                )}
                <p>
                  Local notes on incident ingest, hypothesis quality, sandbox
                  validation, and why approval is not a merge.
                </p>
              </form>
              <div>
                <p>Contact us:</p>
                <a href="mailto:info@sentinelai.dev">info@sentinelai.dev</a>
                <span>Team TriNova</span>
                <span>localhost:8000 /health</span>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="frame">
          <div className="foot-grid">
            <div>
              <p>Pages</p>
              <a href="#top">Home</a>
              <a href="#about">About Us</a>
              <a href="#pricing">Pricing</a>
              <a href="#console">Console</a>
            </div>
            <div>
              <p>Utility</p>
              <a href="#solution">Solution</a>
              <a href="#blog">Blog</a>
              <a href="#case-study">Case Study</a>
            </div>
            <a className="logo" href="#top">
              SENTINEL<sup>AI</sup>
            </a>
          </div>
          <div className="legal">
            <span>© 2026 — SentinelAI | Team TriNova</span>
            <a className="cta cta-dark" href="#top">
              Back to top
            </a>
          </div>
        </div>
      </footer>
    </LuxuryStage>
  )
}
