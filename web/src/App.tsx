import { useEffect, useMemo, useState } from 'react'

type District = { name: string; key: string; centroid: { latitude: number; longitude: number } | null; exposure: number; vulnerability: number; isolation: number; osm?: Record<string, number> }
type Bootstrap = { districts: District[]; events: any[]; event_count: number; boundaries: any; sources: Record<string, any>; osm: any; limitations: string[]; feature_assessment?: any; data_freshness?: Record<string, any> }
type Result = any

const API = '/api'
const DEFAULT_WEIGHTS = { hazard: 0.4, exposure: 0.25, vulnerability: 0.2, isolation: 0.15 }
const fmt = (v: unknown, n = 2) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(n) : '—'
const download = (name: string, body: string, type: string) => {
  const url = URL.createObjectURL(new Blob([body], { type }))
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url)
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

function geomPath(geometry: any, project: (coord: number[]) => [number, number]) {
  const rings: number[][][][] = geometry?.type === 'Polygon' ? [geometry.coordinates] : geometry?.type === 'MultiPolygon' ? geometry.coordinates : []
  return rings.flatMap(poly => poly.map(ring => ring.map((point, index) => {
    const [x, y] = project(point)
    return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ') + ' Z')).join(' ')
}

function PriorityMap({ data, ranking }: { data: any; ranking: any[] }) {
  const featureCollection = data?.boundaries
  const byName = new Map(ranking.map(row => [row.district.toLowerCase(), row]))
  const bounds = useMemo(() => {
    const all: number[][] = []
    const visit = (value: any): void => {
      if (Array.isArray(value) && typeof value[0] === 'number' && typeof value[1] === 'number') all.push(value)
      else if (Array.isArray(value)) value.forEach(visit)
    }
    featureCollection?.features?.forEach((f: any) => visit(f.geometry?.coordinates))
    if (!all.length) return { minX: 76, maxX: 80.5, minY: 8, maxY: 13.5 }
    return { minX: Math.min(...all.map(p => p[0])), maxX: Math.max(...all.map(p => p[0])), minY: Math.min(...all.map(p => p[1])), maxY: Math.max(...all.map(p => p[1])) }
  }, [featureCollection])
  const project = (coord: number[]): [number, number] => [18 + (coord[0] - bounds.minX) / (bounds.maxX - bounds.minX || 1) * 360, 410 - (coord[1] - bounds.minY) / (bounds.maxY - bounds.minY || 1) * 380]
  return <div className="map-wrap">
    <svg viewBox="0 0 400 430" role="img" aria-label="Tamil Nadu district priority map">
      {featureCollection?.features?.map((feature: any, i: number) => {
        const name = String(feature.properties?.shapeName || '')
        const row = byName.get(name.toLowerCase()) || ranking.find(r => r.district.toLowerCase() === name.toLowerCase())
        const alpha = row ? Math.min(.9, .18 + Number(row.priority) * .72) : .12
        return <path key={`${name}-${i}`} d={geomPath(feature.geometry, project)} fill={row ? `rgba(213,105,57,${alpha})` : '#e5e5df'} stroke="#fff" strokeWidth=".7"><title>{name}: {row ? `priority ${fmt(row.priority, 3)}` : 'no rank'}</title></path>
      })}
    </svg>
    <div className="map-legend"><span><i className="legend-high" />Higher priority</span><span><i className="legend-low" />Lower priority</span><span><i className="legend-none" />No score</span></div>
    <p className="muted tiny">Administrative district polygons, not flood extents. Scores are available where the model returns district labels.</p>
  </div>
}

function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null)
  const [bootError, setBootError] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [resultStale, setResultStale] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [evaluation, setEvaluation] = useState<any>(null)
  const [evaluationMode, setEvaluationMode] = useState('')
  const [evalLoading, setEvalLoading] = useState(false)
  const [form, setForm] = useState({ mode: 'manual', intensity_mm: 300, duration_hours: 48, antecedent_7d_mm: 120, antecedent_30d_mm: 320, uncertainty_pct: 25, month: new Date().getMonth() + 1, forecast_days: 3, load_reservoir_context: false, reservoir_threshold_pct: 80 })
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS)
  const [districtValues, setDistrictValues] = useState<Record<string, Record<string, number>>>({})
  const [showDistricts, setShowDistricts] = useState(false)

  useEffect(() => { request<Bootstrap>('/bootstrap').then(data => { setBoot(data); setDistrictValues(Object.fromEntries(data.districts.map(d => [d.key, { exposure: d.exposure, vulnerability: d.vulnerability, isolation: d.isolation }]))); }).catch(e => setBootError(e.message)) }, [])
  const setField = (key: string, value: any) => { if (result) setResultStale(true); setForm(prev => ({ ...prev, [key]: value })) }
  const patchDistrict = (key: string, field: string, value: number) => { if (result) setResultStale(true); setDistrictValues(prev => ({ ...prev, [key]: { ...prev[key], [field]: value } })) }

  const run = async () => {
    setLoading(true); setError(''); if (result) setResultStale(true)
    try {
      const exposure: Record<string, number> = {}, vulnerability: Record<string, number> = {}, isolation: Record<string, number> = {}
      Object.entries(districtValues).forEach(([key, values]) => { exposure[key] = values.exposure; vulnerability[key] = values.vulnerability; isolation[key] = values.isolation })
      const response = await request<Result>('/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...form, weights, exposure, vulnerability, isolation }) })
      setResult(response); setResultStale(false)
    } catch (e: any) { setError(e.message) } finally { setLoading(false) }
  }

  const runEvaluation = async () => {
    setEvalLoading(true); setError('')
    try { setEvaluation(await request('/evaluation')); setEvaluationMode('Leave-one-event-out · future cases may be in the library') } catch (e: any) { setError(e.message) } finally { setEvalLoading(false) }
  }

  const runForwardEvaluation = async () => {
    setEvalLoading(true); setError('')
    try { setEvaluation(await request('/forward-evaluation')); setEvaluationMode('Chronological · past cases only') } catch (e: any) { setError(e.message) } finally { setEvalLoading(false) }
  }

  if (bootError) return <main className="screen-error" role="alert" aria-live="assertive"><h1>Navigator API unavailable</h1><p>{bootError}</p><code>Start the backend with: python -m uvicorn api:app --reload</code></main>
  if (!boot) return <main className="screen-error" role="status" aria-live="polite">Loading project data…</main>

  const ranking = result?.ranking || []
  const top = ranking.slice(0, 5)
  const staticSnapshots = Object.values(result?.data_freshness?.static_reference_layers || {}) as any[]
  const timestampedSnapshots = staticSnapshots.filter(item => typeof item.age_days === 'number')
  const oldestSnapshotAge = timestampedSnapshots.length
    ? Math.max(...timestampedSnapshots.map(item => item.age_days))
    : null
  const reservoirFreshness = result?.data_freshness?.reservoir
  const formInput = (label: string, key: string, min: number, max: number, step: number, suffix = '') => <label className="field"><span>{label}</span><div className="field-control"><input type="number" min={min} max={max} step={step} value={(form as any)[key]} onChange={e => setField(key, Number(e.target.value))} /><small>{suffix}</small></div></label>
  const metric = (label: string, value: string, tone = '') => <article className={`metric ${tone}`}><span>{label}</span><strong>{value}</strong></article>

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#top"><span className="brand-mark">M</span><span>MONSOON<br /><b>IMPACT NAVIGATOR</b></span></a><div className="top-meta"><span className="live-dot" /> TAMIL NADU · DISTRICT PREPAREDNESS <i /> <span>{boot.event_count} curated events</span></div><a className="source-link" href="https://mausam.imd.gov.in/" target="_blank" rel="noreferrer">IMD source ↗</a></header>
    <main id="top" className="layout">
      <aside className="control-panel">
        <div className="panel-intro"><span className="eyebrow">DECISION SUPPORT · PROTOTYPE</span><h1>Turn rainfall<br />into readiness.</h1><p>Explore historical analogues and district preparation priorities. This tool supports judgement; it does not issue official warnings.</p></div>
        <div className="form-section"><div className="section-head"><span>01</span><h2>Rainfall scenario</h2></div>
          <label className="field"><span>Forecast input</span><select value={form.mode} onChange={e => setField('mode', e.target.value)}><option value="manual">Manual / planning scenario</option><option value="live_ensemble">Live ECMWF ensemble · district centroids</option></select></label>
          {form.mode === 'manual' ? <>{formInput('Maximum 24-hour rainfall', 'intensity_mm', 0, 2000, 5, 'mm')}{formInput('Rain duration', 'duration_hours', 0, 720, 1, 'hours')}</> : <label className="field"><span>Forecast horizon</span><select value={form.forecast_days} onChange={e => setField('forecast_days', Number(e.target.value))}><option value={1}>1 day</option><option value={2}>2 days</option><option value={3}>3 days</option><option value={5}>5 days</option><option value={7}>7 days</option></select></label>}
          {formInput('Antecedent · previous 7 days', 'antecedent_7d_mm', 0, 5000, 10, 'mm')}{formInput('Antecedent · previous 30 days', 'antecedent_30d_mm', 0, 10000, 10, 'mm')}
          <label className="field"><span>Climatology month</span><select value={form.month} onChange={e => setField('month', Number(e.target.value))}>{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
          {form.mode === 'manual' && <label className="field range-field"><span>Planning spread <b>{form.uncertainty_pct}%</b></span><input type="range" min="0" max="100" step="5" value={form.uncertainty_pct} onChange={e => setField('uncertainty_pct', Number(e.target.value))} /><small>Uncalibrated scenario range, not a probability interval.</small></label>}
        </div>
        <div className="form-section"><div className="section-head"><span>02</span><h2>Priority weights</h2></div><p className="muted tiny">Expert defaults · normalised automatically</p>
          {Object.entries(weights).map(([key, val]) => <label className="weight-row" key={key}><span>{key}</span><input type="range" min="0" max="1" step=".05" value={val} onChange={e => { if (result) setResultStale(true); setWeights(prev => ({ ...prev, [key]: Number(e.target.value) })) }} /><b>{val.toFixed(2)}</b></label>)}
        </div>
        <div className="form-section"><div className="section-head"><span>03</span><h2>Live context</h2></div>
          <label className="check-row"><input type="checkbox" checked={form.load_reservoir_context} onChange={e => setField('load_reservoir_context', e.target.checked)} /><span>Read AGRISNET reservoir storage</span></label>
          {form.load_reservoir_context && <label className="field"><span>Buffer-concern storage threshold</span><div className="field-control"><input type="number" min="0" max="100" step="5" value={form.reservoir_threshold_pct} onChange={e => setField('reservoir_threshold_pct', Number(e.target.value))} /><small>% full</small></div></label>}
          <button className="text-button" onClick={() => setShowDistricts(v => !v)}>{showDistricts ? 'Hide' : 'Edit'} district context values ↗</button>
        </div>
        <button className="run-button" disabled={loading} aria-busy={loading} onClick={run}>{loading ? <><span className="spinner" aria-hidden="true" /> Calculating priorities…</> : <>Run impact analysis <span aria-hidden="true">→</span></>}</button>
        <p className="fineprint">Not a flood-depth prediction, dispatch tool, dam-release recommendation, or substitute for IMD and district-administration warnings.</p>
      </aside>

      <section className="workspace">
        <div className="workspace-head"><div><span className="eyebrow">MONSOON READINESS / 2026</span><h2>District impact outlook</h2></div><div className="workspace-actions"><button className="quiet-button" onClick={() => runEvaluation()} disabled={evalLoading}>{evalLoading ? 'Running hindcast…' : 'Run LOEO hindcast'}</button><button className="quiet-button" onClick={() => runForwardEvaluation()} disabled={evalLoading}>{evalLoading ? 'Running hindcast…' : 'Run past-only check'}</button>{result && <button className="quiet-button" onClick={() => download('monsoon-impact-audit.json', JSON.stringify(result, null, 2), 'application/json')}>Export audit ↓</button>}</div></div>
        {error && <div className="alert error-alert" role="alert" aria-live="assertive"><span>{error}</span>{form.mode === 'live_ensemble' && <div className="recovery-actions"><button className="quiet-button" onClick={() => setField('mode', 'manual')}>Switch to manual scenario</button><button className="quiet-button" onClick={run} disabled={loading}>Retry live forecast</button></div>}</div>}
        {result && resultStale && <div className="alert stale-result-alert" role="status" aria-live="polite">Showing the last successful analysis. Inputs have changed or the latest run failed; these results do not reflect the current attempt.</div>}
        {!result && <section className="welcome-card"><div className="welcome-art"><span>01</span><i>≈</i><span>02</span></div><div><h3>A transparent forecast-to-priority workflow.</h3><p>Start with a manual scenario or fetch ensemble rainfall for district centroids. The model retrieves similar past events, shows uncertainty, and keeps its assumptions visible.</p><button className="inline-cta" onClick={run} disabled={loading}>Load the default scenario <span>→</span></button></div></section>}
        {result?.status === 'dry_or_no_significant_rain' && <div className="alert dry-alert"><b>No significant rain expected in the central scenario.</b><span>Impact analogue retrieval was skipped. Official warnings remain authoritative.</span></div>}
        {result?.status === 'ok' && <>
          <div className="metrics-grid">{metric('SYSTEM CONFIDENCE', result.confidence, result.confidence.toLowerCase())}{metric('TOP DISTRICT', top[0]?.district || '—')}{metric('BEST ANALOGUE DISTANCE', fmt(result.retrieval.analogues[0]?.distance, 3))}{metric('EVENT LIBRARY', `${boot.event_count} events`)}</div>
          <section className="ops-cards" aria-label="Operational data status">
            <article className="ops-card"><span>FORECAST INPUT</span><strong>{result.forecast_source?.source ? 'Live ensemble' : 'Manual scenario'}</strong><small>{result.forecast_source?.retrieved_at_utc ? `Retrieved ${result.forecast_source.retrieved_at_utc} UTC` : 'User-provided planning values'}</small></article>
            <article className="ops-card"><span>REFERENCE SNAPSHOTS</span><strong>{staticSnapshots.length} source layers</strong><small>{oldestSnapshotAge === null ? 'Retrieval age unavailable' : `Oldest recorded retrieval: ${fmt(oldestSnapshotAge, 0)} days · static data`}</small></article>
            <article className="ops-card"><span>RESERVOIR FEED</span><strong>{reservoirFreshness?.status === 'unavailable' ? 'Unavailable' : reservoirFreshness ? `${reservoirFreshness.staleness_days} day(s) old` : 'Not requested'}</strong><small>{reservoirFreshness?.data_date ? `Report date ${reservoirFreshness.data_date} · context only` : 'Does not affect district ranking'}</small></article>
          </section>
          {result.confidence_inputs.empirical_calibration_status !== 'validated' && <div className="alert">Empirical forecast-error calibration is pending. Confidence is capped at Medium; ensemble spread is not a probability.</div>}
          <div className="forecast-strip"><div><span className="eyebrow">RAINFALL SCENARIO</span><strong>{fmt(result.forecast_scenarios?.low?.[Object.keys(result.forecast_scenarios.low || {})[0]])} / {fmt(result.forecast_scenarios?.central?.[Object.keys(result.forecast_scenarios.central || {})[0]])} / {fmt(result.forecast_scenarios?.high?.[Object.keys(result.forecast_scenarios.high || {})[0]])} <small>mm · low / central / high</small></strong></div><div><span className="eyebrow">SOURCE</span><strong>{result.forecast_source?.source || 'Manual planning input'}</strong><small>{result.forecast_source?.model || result.climatology?.source || 'Climatology fallback: neutral percentile where unavailable'}</small>{result.forecast_source?.retrieved_at_utc && <small>Retrieved {result.forecast_source.retrieved_at_utc} · timestamps UTC</small>}</div><div><span className="eyebrow">UNCERTAINTY / DATA</span><strong>{result.confidence_inputs.forecast_spread_high ? 'High spread' : 'Within default'} · {Math.round(result.confidence_inputs.missing_feature_fraction * 100)}% missing</strong><small>Scenario confidence is not a calibrated probability</small></div></div>
          <details className="card feature-audit"><summary>Inspect ranking inputs, source coverage, and proxy limits</summary>{boot.feature_assessment ? <><div className="table-scroll"><table><thead><tr><th>Signal</th><th>Current use</th><th>Meaning and limitation</th></tr></thead><tbody>{boot.feature_assessment.ranking_inputs.map((item: any) => <tr key={item.signal}><td><b>{item.signal}</b></td><td>{item.current_use}</td><td>{item.meaning}<ul>{item.limitations.map((limitation: string) => <li key={limitation}>{limitation}</li>)}</ul></td></tr>)}</tbody></table></div><p className="muted tiny">Coverage: elevation {boot.feature_assessment.coverage.elevation.unique_district_count}/38, population {boot.feature_assessment.coverage.population.unique_district_count}/38, OSM {boot.feature_assessment.coverage.osm.unique_district_count}/38; rainfall {boot.feature_assessment.coverage.daily_rainfall.row_count.toLocaleString()} district-days.</p><p className="muted tiny">Reference snapshot age: {Object.entries(boot.data_freshness?.static_reference_layers || {}).map(([name, item]: [string, any]) => `${name} ${typeof item.age_days === 'number' ? `${item.age_days}d` : item.status}`).join(' · ')}. These are static layers, not live feeds.</p><p className="muted tiny">Added value status: {boot.feature_assessment.independent_added_value.status}. {boot.feature_assessment.independent_added_value.reason}</p><div className="table-scroll"><table><thead><tr><th>Candidate signal</th><th>Status and limitation</th></tr></thead><tbody>{boot.feature_assessment.candidate_signals.map((item: any) => <tr key={item.signal}><td><b>{item.signal}</b></td><td>{item.status}<br />{item.why_existing_waterway_counts_are_not_a_substitute || item.why}</td></tr>)}</tbody></table></div><p className="muted tiny">Source URLs, retrieval dates, licences, methods, and SHA-256 values are recorded in data/layers/hazard_exposure_assessment.json.</p></> : <p className="muted tiny">Feature quality assessment is not available; ranking context layers have not been independently validated for added value.</p>}</details>
          {result.retrieval.abstained && <div className="alert">No close historical analogue found; showing the partial ranking at low confidence.</div>}
          {result.retrieval.out_of_range.length > 0 && <div className="alert">Out-of-range query features: {result.retrieval.out_of_range.map((x: any) => x.feature).join(', ')}</div>}
          {result.confidence_inputs.overlap_adjustment_applied && <div className="alert">Exposure/isolation overlap detected (Spearman ρ={fmt(result.confidence_inputs.exposure_isolation_spearman)}); isolation weight was partially transferred to exposure.</div>}

          <div className="main-grid district-decisions-layout"><section className="card ranking-card"><div className="card-head"><div><span className="eyebrow">PREPARATION PRIORITY · ALL DISTRICTS</span><h3>District decision cards</h3></div><span className="unit-pill">{ranking.length} ranked · 0—1</span></div><div className="decision-grid" role="list" aria-label="Ranked district decisions">{ranking.map((row: any, i: number) => <article className="decision-card" role="listitem" key={row.district} aria-label={`Rank ${i + 1}: ${row.district}, priority ${fmt(row.priority, 3)}`}><div className="decision-card-head"><span className="decision-rank">#{String(i + 1).padStart(2, '0')}</span><span className={`badge ${(row.confidence || 'low').toLowerCase()}`}>{row.confidence || 'Unrated'}</span></div><h4>{row.district}</h4><div className="decision-score"><strong>{fmt(row.priority, 3)}</strong><span>priority score</span></div><div className="decision-meter" aria-hidden="true"><i style={{ width: `${Math.max(0, Math.min(100, Number(row.priority) * 100))}%` }} /></div><div className="decision-components">{[['Hazard', row.hazard], ['Exposure', row.exposure], ['Vulnerability', row.vulnerability], ['Isolation', row.isolation]].map(([label, value]: any) => <div className="decision-component" key={label}><span>{label}</span><b>{fmt(value, 2)}</b><i aria-hidden="true"><em style={{ width: `${Math.max(0, Math.min(100, Number(value) * 100))}%` }} /></i></div>)}</div><div className="decision-tags"><span className={`badge ${row.scenario_status === 'stable' ? 'high' : 'low'}`}>{row.scenario_status === 'stable' ? 'Scenario stable' : 'Scenario-sensitive'}</span>{row.district_abstained && <span className="badge low">No close analogue</span>}{row.district_out_of_range?.length > 0 && <span className="badge low">Outside library range</span>}</div></article>)}</div><button className="download-csv" onClick={() => { const cols = Object.keys(ranking[0] || {}); const csv = [cols.join(','), ...ranking.map((r: any) => cols.map(c => JSON.stringify(r[c] ?? '')).join(','))].join('\n'); download('district-priority.csv', csv, 'text/csv') }}>Download all district decisions as CSV ↓</button></section>
          <section className="card map-card"><div className="card-head"><div><span className="eyebrow">GEOGRAPHIC VIEW</span><h3>Priority by district</h3></div><span className="map-icon">⌖</span></div><PriorityMap data={boot} ranking={ranking} /></section></div>

          <div className="main-grid secondary-grid"><section className="card"><div className="card-head"><div><span className="eyebrow">CASE-BASED RETRIEVAL</span><h3>Closest historical events</h3></div><span className="unit-pill">Threshold {fmt(result.retrieval.threshold, 3)}</span></div>{result.retrieval.analogues.map((item: any, i: number) => <article className="event-row" key={item.event.event_id}><span className="event-index">0{i + 1}</span><div className="event-main"><b>{item.event.name}</b><span>{item.event.start_date} · {item.features_used} features · {item.event.affected_districts.join(', ')}</span><a href={item.event.source} target="_blank" rel="noreferrer">View source report ↗</a></div><strong>{fmt(item.distance, 3)}</strong></article>)}<details className="library-details"><summary>Inspect all {boot.events.length} curated events and label evidence</summary>{boot.events.map((event: any) => <article className="library-event" key={event.event_id}><div><b>{event.name}</b><span>{event.start_date}—{event.end_date} · {event.label_confidence || 'confidence not set'} confidence · {event.affected_districts.join(', ')}</span></div><a href={event.source} target="_blank" rel="noreferrer">IMD source ↗</a><p>{event.evidence_notes}</p><small>{event.label_status} · cyclone screen: {event.cyclone_window_evidence}</small></article>)}</details></section>
          <section className="card"><div className="card-head"><div><span className="eyebrow">UNCERTAINTY CHECK</span><h3>Scenario stability</h3></div></div><div className="scenario-list">{result.scenario_stability.filter((row: any) => top.some((r: any) => r.district === row.district)).map((row: any) => <div className="scenario-row" key={row.district}><span>{row.district}</span><div>{['low','central','high'].map(s => <small key={s}>{s.slice(0,1).toUpperCase()} {row.positions[s] ?? '—'}</small>)}</div><span className={`badge ${row.stable ? 'high' : 'low'}`}>{row.stable ? 'Stable' : 'Sensitive'}</span></div>)}</div><p className="muted tiny">Stable means a district remains in the top five under low, central, and high scenarios.</p></section></div>

          <div className="main-grid secondary-grid"><section className="card"><div className="card-head"><div><span className="eyebrow">METHOD COMPARISON</span><h3>Top-five baseline check</h3></div></div><div className="baseline-list"><div><span>Analogue + context</span><b>{top.map((r: any) => r.district).join(' · ')}</b></div><div><span>Rainfall only</span><b>{result.baselines.rainfall_only.join(' · ')}</b></div><div><span>Static flood-proneness</span><b>{result.baselines.static_flood_proneness.join(' · ')}</b></div></div><div className="sensitivity"><span className="eyebrow">WEIGHT SENSITIVITY</span>{result.sensitivity.map((row: any) => <div key={row.weight_set}><span>{row.weight_set}</span><b>{row.top_5.join(' · ')}</b></div>)}</div></section>
          <section className="card advisory-card"><div className="card-head"><div><span className="eyebrow">SOURCE-BACKED OUTPUT</span><h3>Preparedness advisory</h3></div><span className="language-tag">EN / TA</span></div><p className="advisory-text">{result.advisory.english.text}</p><p className="tamil-text" lang="ta">{result.advisory.tamil.text}</p><details><summary>Evidence and source tags</summary><pre>{JSON.stringify(result.advisory.english.source_tags, null, 2)}</pre></details><strong className="official-note">Official IMD and district-administration warnings take precedence.</strong></section></div>

          {result.reservoir_context && <section className="card reservoir-card"><div className="card-head"><div><span className="eyebrow">LIVE CONTEXT · GOVERNMENT DASHBOARD</span><h3>Reservoir storage</h3></div><a href="https://www.tnagrisnet.tn.gov.in/home/reservoir/" target="_blank" rel="noreferrer">AGRISNET source ↗</a></div>{result.reservoir_context.error ? <p role="status">{result.reservoir_context.error}</p> : <><p className="muted">Report {result.reservoir_context.data_date} · {result.reservoir_context.staleness_days} day(s) old · retrieved {result.reservoir_context.retrieved_at_utc} · {result.reservoir_context.records.filter((x: any) => x.buffer_concern).length} reservoirs meet the {result.reservoir_context.buffer_concern_threshold_pct}% storage heuristic.</p><p className="alert">Context only, not a flood warning or dam-release guidance. The feed is not district-linked and does not affect the ranking.</p><div className="table-scroll"><table><thead><tr><th>Reservoir</th><th>Storage</th><th>Capacity</th><th>% full</th><th>Status</th></tr></thead><tbody>{result.reservoir_context.records.map((r: any) => <tr key={r.reservoir}><td>{r.reservoir}</td><td>{fmt(r.current_storage_mcft, 1)} MCft</td><td>{fmt(r.total_capacity_mcft, 1)} MCft</td><td>{fmt(r.storage_pct_of_full_capacity, 1)}%</td><td>{r.status}</td></tr>)}</tbody></table></div></>}</section>}
        </>}

        {evaluation && <section className="card evaluation-card">
          <div className="card-head"><div><span className="eyebrow">RETROSPECTIVE CHECK · {evaluation.evaluated_event_count ?? evaluation.event_count} SCORED / {evaluation.event_count} EVENTS</span><h3>{evaluationMode || 'Hindcast evaluation'}</h3></div><button className="quiet-button" onClick={() => setEvaluation(null)}>Close</button></div>
          <p className="muted tiny">Macro-average across events · P@5 = precision among the five highest-ranked districts; R@5 = share of recorded affected districts recovered.</p>
          <div className="table-scroll"><table><thead><tr><th>Method</th><th>Macro P@5</th><th>Macro R@5</th><th>Events evaluated</th></tr></thead><tbody>
            {([['Analogue + context', 'analogue'], ['Rainfall only', 'rainfall_only'], ['Static flood-proneness', 'static_flood_proneness']] as const).map(([label, key]) => <tr key={key}><td><b>{label}</b></td><td>{evaluation.macro_average?.[key]?.precision_at_k == null ? 'n/a' : `${(evaluation.macro_average[key].precision_at_k * 100).toFixed(1)}%`}</td><td>{evaluation.macro_average?.[key]?.recall_at_k == null ? 'n/a' : `${(evaluation.macro_average[key].recall_at_k * 100).toFixed(1)}%`}</td><td>{key === 'rainfall_only' ? evaluation.macro_average?.rainfall_only?.evaluated_events ?? '—' : evaluation.event_count}</td></tr>)}
          </tbody></table></div>
          <div className="table-scroll"><table><thead><tr><th>Event</th><th>Training cases</th><th>Analogue P@5 / R@5</th><th>Rain-only P@5 / R@5</th><th>Static P@5 / R@5</th><th>Status</th></tr></thead><tbody>{evaluation.events.map((r: any) => <tr key={r.event_id}><td>{r.event}</td><td>{r.training_event_count ?? r.prior_event_count ?? '—'}</td>{r.status ? <><td>—</td><td>—</td><td>—</td><td>{r.status === 'not_evaluated_insufficient_prior_events' ? `Skipped · needs ${r.required_prior_events} prior cases` : r.status}</td></> : <><td>{(r.analogue.precision_at_k * 100).toFixed(0)}% / {(r.analogue.recall_at_k * 100).toFixed(0)}%</td><td>{r.rainfall_only.precision_at_k == null ? 'n/a' : `${(r.rainfall_only.precision_at_k * 100).toFixed(0)}% / ${(r.rainfall_only.recall_at_k * 100).toFixed(0)}%`}</td><td>{(r.static_flood_proneness.precision_at_k * 100).toFixed(0)}% / {(r.static_flood_proneness.recall_at_k * 100).toFixed(0)}%</td><td>{r.abstained ? 'Abstained' : 'Scored'}</td></>}</tr>)}</tbody></table></div>
          <p className="muted tiny">{evaluation.note} Report ground truth is uneven; per-event results matter more than a single aggregate. This retrospective test is not an operational forecast skill score.</p>
        </section>}

        {showDistricts && <section className="card district-editor"><div className="card-head"><div><span className="eyebrow">USER-EDITABLE INPUTS</span><h3>District context assumptions</h3></div><button className="quiet-button" onClick={() => { if (boot) { if (result) setResultStale(true); setDistrictValues(Object.fromEntries(boot.districts.map(d => [d.key, { exposure: d.exposure, vulnerability: d.vulnerability, isolation: d.isolation }]))); } }}>Reset source defaults</button></div><p className="muted">Scores range 0–1. Missing/neutral source values are editable assumptions; OSM proxies are not official inventories.</p><div className="table-scroll"><table><thead><tr><th>District</th><th>Exposure</th><th>Vulnerability</th><th>Isolation</th><th>Road ways / 100 km²</th><th>Waterway ways / 100 km²</th><th>Hospitals</th><th>Schools</th></tr></thead><tbody>{boot.districts.map(d => <tr key={d.key}><td>{d.name}</td>{(['exposure','vulnerability','isolation'] as const).map(field => <td key={field}><input className="mini-input" type="number" min="0" max="1" step="0.05" value={districtValues[d.key]?.[field] ?? .5} onChange={e => patchDistrict(d.key, field, Number(e.target.value))} /></td>)}<td>{d.osm?.road_ways_per_100_km2 ?? '—'}</td><td>{d.osm?.waterway_ways_per_100_km2 ?? '—'}</td><td>{d.osm?.hospital_count ?? '—'}</td><td>{d.osm?.school_count ?? '—'}</td></tr>)}</tbody></table></div><p className="muted tiny">Waterway way density is a mapping-context proxy, not measured river proximity, drainage capacity, or flood exposure.</p></section>}

        <footer className="page-footer"><span>MONSOON IMPACT NAVIGATOR · RESEARCH PROTOTYPE</span><span>{boot.osm.records}/38 district OSM profiles · {boot.event_count} events · district-scale only</span></footer>
      </section>
    </main>
  </div>
}

export default App
