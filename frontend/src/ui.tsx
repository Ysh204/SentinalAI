import { useEffect, useRef, useState, type ReactNode } from 'react'
import bgRedGold from './assets/bg-red-gold.png'

export function LuxuryStage({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  const isLanding = className.split(/\s+/).includes('landing-shell')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isLanding) return
    const el = ref.current
    if (!el) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) return
    const onMove = (e: PointerEvent) => {
      el.style.setProperty('--mx', `${e.clientX}px`)
      el.style.setProperty('--my', `${e.clientY}px`)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => window.removeEventListener('pointermove', onMove)
  }, [isLanding])

  return (
    <div className={`page ${className}`.trim()} ref={ref}>
      <div className="luxury-bg" aria-hidden="true">
        {isLanding ? (
          <svg className="gold-geometry" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice">
            <defs>
              <linearGradient id="goldStroke" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#fff1c2" stopOpacity="0.15" />
                <stop offset="45%" stopColor="#f0c14b" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#fff1c2" stopOpacity="0.2" />
              </linearGradient>
              <linearGradient id="redFacet" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#33040d" stopOpacity="0.76" />
                <stop offset="55%" stopColor="#a60918" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#180209" stopOpacity="0.7" />
              </linearGradient>
              <filter id="goldGlow" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="1.2" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="beamGlow" x="-40%" y="-20%" width="180%" height="140%">
                <feGaussianBlur stdDeviation="3.5" />
              </filter>
              <radialGradient id="beamGlint">
                <stop offset="0%" stopColor="#fff8dc" stopOpacity="1" />
                <stop offset="34%" stopColor="#ffe29a" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#f0b84b" stopOpacity="0" />
              </radialGradient>
            </defs>
            <path className="geo-facet left" d="M0 0 H335 L0 435 Z" />
            <path className="geo-facet right" d="M1600 0 H1265 L1600 435 Z" />
            <path className="geo-facet lower-left" d="M0 465 L330 310 L800 900 H0 Z" />
            <path className="geo-facet lower-right" d="M1600 465 L1270 310 L800 900 H1600 Z" />
            <path className="geo-facet lower-left" d="M0 760 L520 900 H0 Z" />
            <path className="geo-facet lower-right" d="M1600 760 L1080 900 H1600 Z" />
            <path className="geo-beam-halo" d="M330 -40 L0 435" />
            <path className="geo-beam-edge" d="M330 -40 L0 435" />
            <path className="geo-beam-halo" d="M160 120 L800 930" />
            <path className="geo-beam-core" d="M160 120 L800 930" />
            <path className="geo-beam-halo right" d="M1270 -40 L1600 435" />
            <path className="geo-beam-edge right" d="M1270 -40 L1600 435" />
            <path className="geo-beam-halo right" d="M1440 120 L800 930" />
            <path className="geo-beam-core right" d="M1440 120 L800 930" />
            <path className="geo-beam-edge lower" d="M0 590 L800 900" />
            <path className="geo-beam-edge lower right" d="M1600 590 L800 900" />
            <ellipse className="geo-glint" cx="150" cy="220" rx="5" ry="26" transform="rotate(-35 150 220)" />
            <ellipse className="geo-glint" cx="400" cy="420" rx="5" ry="30" transform="rotate(38 400 420)" />
            <ellipse className="geo-glint" cx="1450" cy="220" rx="5" ry="26" transform="rotate(35 1450 220)" />
            <ellipse className="geo-glint" cx="1200" cy="420" rx="5" ry="30" transform="rotate(-38 1200 420)" />
            <circle className="geo-flare f1" cx="75" cy="325" r="4" />
            <circle className="geo-flare f2" cx="610" cy="690" r="3" />
            <circle className="geo-flare f3" cx="1525" cy="325" r="4" />
            <circle className="geo-flare f4" cx="990" cy="690" r="3" />
          </svg>
        ) : (
          <>
            <img src={bgRedGold} alt="" />
            <svg className="gold-geometry" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice">
              <defs>
                <linearGradient id="goldStroke" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#fff1c2" stopOpacity="0.15" />
                  <stop offset="45%" stopColor="#f0c14b" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#fff1c2" stopOpacity="0.2" />
                </linearGradient>
                <filter id="goldGlow" x="-40%" y="-40%" width="180%" height="180%">
                  <feGaussianBlur stdDeviation="3" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              <path className="geo-line a" d="M80 820 L520 80" />
              <path className="geo-line b" d="M-40 640 L640 40" />
              <path className="geo-line c" d="M1520 80 L1080 820" />
              <path className="geo-line d" d="M1640 240 L980 860" />
              <circle className="geo-flare f1" cx="220" cy="690" r="5" />
              <circle className="geo-flare f2" cx="470" cy="160" r="4" />
              <circle className="geo-flare f3" cx="1380" cy="210" r="5" />
              <circle className="geo-flare f4" cx="1180" cy="700" r="4" />
              <circle className="geo-flare f5" cx="800" cy="120" r="3" />
            </svg>
          </>
        )}
      </div>
      {!isLanding && (
        <>
          <div className="pointer-glow" aria-hidden="true" />
          <div className="grain" aria-hidden="true" />
        </>
      )}
      <div className="stage">{children}</div>
    </div>
  )
}

export function IconSquares() {
  return (
    <span className="btn-marks" aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
    </span>
  )
}

export function Cta({
  children,
  href,
  variant = 'dark',
  onClick,
  type,
  disabled,
}: {
  children: string
  href?: string
  variant?: 'dark' | 'ghost' | 'gold'
  onClick?: () => void
  type?: 'button' | 'submit'
  disabled?: boolean
}) {
  const className = `cta cta-${variant}`
  if (href) {
    return (
      <a className={className} href={href} onClick={onClick}>
        {children}
        <IconSquares />
      </a>
    )
  }
  return (
    <button className={className} type={type ?? 'button'} onClick={onClick} disabled={disabled}>
      {children}
      <IconSquares />
    </button>
  )
}

export function SectionRail({ label, num }: { label: string; num: string }) {
  return (
    <div className="section-rail">
      <span>{label}</span>
      <span>{num}</span>
    </div>
  )
}

export function Gauge({ value = 3254 }: { value?: number }) {
  const ticks = Array.from({ length: 20 }, (_, i) => {
    const a = ((-200 + i * 11) * Math.PI) / 180
    const inner = 52
    const outer = 72
    return {
      i,
      x1: 100 + Math.cos(a) * inner,
      y1: 92 + Math.sin(a) * inner,
      x2: 100 + Math.cos(a) * outer,
      y2: 92 + Math.sin(a) * outer,
      on: i < 14,
    }
  })
  return (
    <div className="gauge">
      <svg viewBox="0 0 200 120" aria-hidden="true">
        {ticks.map((t) => (
          <line
            key={t.i}
            className={t.on ? 'tick-on' : 'tick-off'}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            strokeWidth="6"
            strokeLinecap="round"
            style={{ animationDelay: `${t.i * 40}ms` }}
          />
        ))}
      </svg>
      <div className="gauge-center">
        <small>Incidents in queue</small>
        <strong>{value.toLocaleString()}</strong>
      </div>
    </div>
  )
}

export function Reveal({
  children,
  className = '',
  delay = 0,
}: {
  children: ReactNode
  className?: string
  delay?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [on, setOn] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setOn(true)
      return
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setOn(true)
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={`reveal ${on ? 'in' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}

export function useCountUp(target: number, start: boolean, duration = 900) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!start) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setN(target)
      return
    }
    const t0 = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration)
      setN(Math.round(target * (1 - Math.pow(1 - p, 3))))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [start, target, duration])
  return n
}
