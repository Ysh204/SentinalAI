import {
  type FormEvent,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
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

type HeroRoute = {
  width: number
  height: number
  startY: number
  leftPath: string
  rightPath: string
}

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
  const [incidentCount, setIncidentCount] = useState(0)
  const [statsOn, setStatsOn] = useState(false)
  const statsRef = useRef<HTMLElement>(null)
  const heroRef = useRef<HTMLElement>(null)
  const routeAnchorRef = useRef<HTMLSpanElement>(null)
  const heroCtaRef = useRef<HTMLAnchorElement>(null)
  const [heroRoute, setHeroRoute] = useState<HeroRoute>({
    width: 1200,
    height: 760,
    startY: 250,
    leftPath: 'M 9 250 H 300 C 390 250 510 410 600 410',
    rightPath: 'M 1191 250 H 900 C 810 250 690 410 600 410',
  })
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
  const statModes = useCountUp(5, statsOn)
  const statGates = useCountUp(4, statsOn)
  const statWrites = useCountUp(0, statsOn)
  const statTimeout = useCountUp(30, statsOn)

  useLayoutEffect(() => {
    const hero = heroRef.current
    const anchor = routeAnchorRef.current
    const cta = heroCtaRef.current
    if (!hero || !anchor || !cta) return

    const measureRoute = () => {
      const heroRect = hero.getBoundingClientRect()
      const anchorRect = anchor.getBoundingClientRect()
      const ctaRect = cta.getBoundingClientRect()
      if (
        !heroRect.width ||
        !heroRect.height ||
        !ctaRect.width ||
        !ctaRect.height
      ) {
        return
      }

      const round = (value: number) => Math.round(value * 10) / 10
      const width = round(heroRect.width)
      const height = round(heroRect.height)
      const centerX = round(ctaRect.left + ctaRect.width / 2 - heroRect.left)
      const centerY = round(ctaRect.top + ctaRect.height / 2 - heroRect.top)
      const startY = round(
        Math.max(40, Math.min(anchorRect.bottom - heroRect.top + 20, centerY - 44)),
      )
      // Slope strictly parallel to the black background facet:
      // Uses a true straight diagonal line L (matching the black polygon edge angle)
      // with sleek rounded corner fillets Q at the top and bottom.
      const edge = 9
      const deltaY = centerY - startY
      // Black slope ratio: dy/dx ≈ 1.08 (arctan ~47 degrees)
      const slopeRatio = 1.08
      const theta = Math.atan(slopeRatio)
      const ux = Math.cos(theta)
      const uy = Math.sin(theta)
      const r = 24 // corner fillet radius

      const rampDx = round(Math.max(170, deltaY / slopeRatio))
      const x2 = round(Math.max(edge + 120, centerX - 170))
      const x1 = round(x2 - rampDx)

      const rx2 = round(Math.min(width - edge - 120, centerX + 170))
      const rx1 = round(rx2 + rampDx)

      // Left path: horizontal -> round fillet -> straight diagonal parallel to black slope -> round fillet -> horizontal into button
      const c1EndX = round(x1 + r * ux)
      const c1EndY = round(startY + r * uy)
      const c2StartX = round(x2 - r * ux)
      const c2StartY = round(centerY - r * uy)

      // Right path: symmetrical
      const rc1EndX = round(rx1 - r * ux)
      const rc1EndY = round(startY + r * uy)
      const rc2StartX = round(rx2 + r * ux)
      const rc2StartY = round(centerY - r * uy)

      const leftPath = `M ${edge} ${startY} H ${x1 - r} Q ${x1} ${startY}, ${c1EndX} ${c1EndY} L ${c2StartX} ${c2StartY} Q ${x2} ${centerY}, ${x2 + r} ${centerY} H ${centerX}`
      const rightPath = `M ${round(
        width - edge,
      )} ${startY} H ${rx1 + r} Q ${rx1} ${startY}, ${rc1EndX} ${rc1EndY} L ${rc2StartX} ${rc2StartY} Q ${rx2} ${centerY}, ${rx2 - r} ${centerY} H ${centerX}`

      setHeroRoute((previous) => {
        if (
          Math.abs(previous.width - width) < 0.5 &&
          Math.abs(previous.height - height) < 0.5 &&
          previous.startY === startY &&
          previous.leftPath === leftPath &&
          previous.rightPath === rightPath
        ) {
          return previous
        }
        return { width, height, startY, leftPath, rightPath }
      })
    }

    measureRoute()
    const observer = new ResizeObserver(measureRoute)
    observer.observe(hero)
    observer.observe(anchor)
    observer.observe(cta)
    window.addEventListener('resize', measureRoute)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', measureRoute)
    }
  }, [])

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
    <LuxuryStage className="landing-shell">
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
        <section className="hero" ref={heroRef}>
          <div className="hero-lines" aria-hidden="true">
            <svg
              viewBox={`0 0 ${heroRoute.width} ${heroRoute.height}`}
              preserveAspectRatio="none"
            >
              <path
                className="draw-path flow-left"
                d={heroRoute.leftPath}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.2"
              />
              <path
                className="draw-path flow-right"
                d={heroRoute.rightPath}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.2"
              />
            </svg>
            <i
              className="node left pulse"
              style={{ top: `${heroRoute.startY}px` }}
            />
            <i
              className="node right pulse"
              style={{ top: `${heroRoute.startY}px` }}
            />
          </div>
          <p className="live-pill">
            <i className={health ? 'ok' : 'off'} />
            {health
              ? `${health.app} · ${health.ai_provider} · ${health.team}`
              : 'Backend offline — start uvicorn on :8000'}
          </p>
          <h1>
            <span>Build for</span>
            <span ref={routeAnchorRef}>Incident Repair</span>
            <span className="mark">Response</span>
          </h1>
          <p className="hero-copy">
            Ingest a software incident, generate an AI hypothesis, propose a
            patch, validate it in a disposable workspace, then wait for a human.
          </p>
          <a
            className="cta cta-gold hero-cta"
            href="#console"
            ref={heroCtaRef}
          >
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
              <span>Sandbox pytest</span>
              <span>HTTP replay</span>
              <span>Human sign-off</span>
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
                <strong>Team TriNova</strong>
                <span>Open-source remediation demo</span>
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
                Built for autonomous remediation demos: five injectable shop
                failures, a gated repair loop, and zero writes to the original
                tree.
              </h2>
            </Reveal>
            <div className="stat-row">
              <a className="gold-tag dark-gold" href="#console">
                <b>Open Console</b>
                <small>&gt;&gt;&gt;</small>
              </a>
              <div className="big-stat">
                {statModes}
                <span>modes</span>
              </div>
              <div className="stat">
                <strong>{statGates}</strong>
                <p>gated stages before a human approve/reject decision</p>
              </div>
              <div className="stat">
                <strong>{statWrites}</strong>
                <p>writes to the original repository — patches stay in a temp workspace</p>
              </div>
              <div className="stat">
                <strong>{statTimeout}s</strong>
                <p>pytest timeout inside a scrubbed sandbox subprocess</p>
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
            <SectionRail label="Design constraints" num="006" />
            <div className="quote-wrap fade-slide" key={t.name}>
              {t.img ? <img src={t.img} alt="" /> : null}
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
                <small>Original repo writes</small>
                <b>0</b>
              </div>
              <div>
                <small>Human sign-off</small>
                <b>Required</b>
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
