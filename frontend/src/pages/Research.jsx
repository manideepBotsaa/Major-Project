import { useEffect, useState } from 'react'
import {
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  Database,
  FileJson,
  FlaskConical,
  GitBranch,
  LineChart,
  Microscope,
  Quote,
  ShieldCheck,
  Sparkles,
  Terminal,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { formatDate, formatPct, titleCase } from '../lib/format'
import { Badge, Callout, Card, EmptyState, PageHeader, ProgressBar, SectionTitle, Spinner, StatCard } from '../components/UI'

const PAPER = {
  title: 'GroundedPath: Verifiable Numeric Reasoning and Measurable Just-in-Time Nudges for Personal Finance',
  one: 'AI-Powered Personalized Financial Advisor: Empowering Smarter Financial Decisions',
  two: 'Using Chatbot Technologies to Help Individuals Make Sound Personalized Financial Decisions (IHTC 2021)',
}

const COMMANDS = [
  ['Personas', 'python research/generate_personas.py'],
  ['Categorization', 'python research/bench_categorization.py'],
  ['Forecasting', 'python research/bench_forecasting.py'],
  ['Advisor grounding', 'python research/bench_advisor.py'],
  ['Nudge simulation', 'python research/simulate_nudges.py'],
  ['All + figures', 'python research/run_all.py'],
]

export default function Research() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .researchSummary()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="centered-loader"><Spinner label="Opening the research record…" /></div>

  const available = data?.available
  const experiments = data?.experiments || {}

  return (
    <>
      <PageHeader
        eyebrow="RESEARCH SYSTEM · CLEARPATH LAB"
        title={data?.system?.name || 'GroundedPath'}
        description="A neuro-symbolic personal finance advisor evaluated on reproducibility, numeric grounding and nudge behaviour — not on a fabricated user study."
        actions={
          <Link to="/advisor" className="btn btn-primary"><Sparkles size={16} /> Try the system</Link>
        }
      />

      <section className="research-hero">
        <div className="research-hero-copy">
          <span className="eyebrow light">MAJOR PROJECT · SYSTEM + EVALUATION</span>
          <h2>Language may explain. Only deterministic tools may compute.</h2>
          <p>
            GroundedPath joins two threads: an AI personal-finance advisor that can reason over a user&apos;s ledger, and
            just-in-time financial education delivered when a decision is being made. The contribution is the reliability
            mechanism — a numeric-claim verifier that rejects unsupported figures and falls back to a deterministic answer.
          </p>
          <div className="research-pills">
            <span><ShieldCheck size={13} /> Numeric verification</span>
            <span><Microscope size={13} /> Reproducible harness</span>
            <span><Users size={13} /> Synthetic personas</span>
            <span><Database size={13} /> Local-first</span>
          </div>
        </div>
        <div className="research-hero-side">
          <div>
            <span>Status</span>
            <Badge tone={available ? 'green' : 'amber'} dot>{available ? 'Results generated' : 'Harness not run'}</Badge>
          </div>
          <div><span>Generated</span><strong>{data?.generated_at ? formatDate(data.generated_at.slice(0, 10), 'long') : '—'}</strong></div>
          <div><span>Version</span><strong>{data?.version || '—'}</strong></div>
          <div><span>Paper</span><strong>2 IEEE sources</strong></div>
        </div>
      </section>

      {!available ? (
        <Callout tone="amber" title={data?.message || 'Research results are not available yet'} icon={CircleAlert}>
          <p>
            The product works without the harness. To generate the evaluation record and the figures used in the paper,
            run the commands below from the project root. Results are written to <code>research/results/summary.json</code>.
          </p>
          {error && <p className="inline-error">{error}</p>}
        </Callout>
      ) : (
        <>
          <div className="stat-grid four">
            <StatCard label="Synthetic personas" value={data.corpus?.personas ?? '—'} icon={Users} note={`${data.corpus?.transactions ?? '—'} generated transactions`} />
            <StatCard label="Models benchmarked" value="4" icon={BrainCircuit} note="Classifier, forecast, router, nudge simulator" tone="sand" />
            <StatCard label="Advisor questions" value={experiments.advisor?.n ?? '—'} icon={FlaskConical} note={`${experiments.advisor?.questions ?? '—'} held-out prompts`} tone="blue" />
            <StatCard label="Reproducible" value={data.reproducible ? 'Yes' : '—'} icon={GitBranch} note="Fixed seeds · committed results" tone="green" />
          </div>

          <div className="experiment-grid">
            <ExperimentCard
              icon={BookOpenCheck}
              label="Categorization"
              title="Does learned categorization beat rules on Indian merchant text?"
              primary={experiments.categorization?.accuracy}
              primaryLabel="test accuracy"
              secondary={experiments.categorization?.macro_f1}
              secondaryLabel="macro F1"
              baseline={experiments.categorization?.baseline_accuracy}
              baselineLabel="keyword baseline"
              note={experiments.categorization?.note}
            />
            <ExperimentCard
              icon={LineChart}
              label="Forecasting"
              title="Does a ridge model beat a naive seasonal baseline on household cash flow?"
              primary={experiments.forecasting?.mae}
              primaryLabel="model MAE"
              secondary={experiments.forecasting?.skill}
              secondaryLabel="skill vs baseline"
              baseline={experiments.forecasting?.baseline_mae}
              baselineLabel="baseline MAE"
              note={experiments.forecasting?.note}
              format="money"
            />
            <ExperimentCard
              icon={ShieldCheck}
              label="Advisor grounding"
              title="Are routing and numeric claims correct across the five JIT use cases?"
              primary={experiments.advisor?.verification_pass_rate}
              primaryLabel="verification pass"
              secondary={experiments.advisor?.routing_accuracy}
              secondaryLabel="routing accuracy"
              baseline={experiments.advisor?.unsupported_claims}
              baselineLabel="unsupported claims"
              note={experiments.advisor?.note}
              percent
            />
            <ExperimentCard
              icon={Users}
              label="Nudge simulation"
              title="Does context improve acceptance without manipulating the user?"
              primary={experiments.nudges?.acceptance_rate}
              primaryLabel="simulated acceptance"
              secondary={experiments.nudges?.impressions}
              secondaryLabel="impressions"
              baseline={experiments.nudges?.baseline_acceptance_rate}
              baselineLabel="generic tip baseline"
              note={experiments.nudges?.note}
              percent
            />
          </div>

          {experiments.advisor?.by_intent?.length > 0 && (
            <Card>
              <SectionTitle title="Advisor performance by request type" description="Routing is rule-based in deterministic mode; numeric verification applies in every mode." />
              <div className="research-table-wrap">
                <table className="data-table compact">
                  <thead><tr><th>Intent family</th><th className="right">Prompts</th><th className="right">Routed correctly</th><th className="right">Numeric pass</th><th className="right">Median latency</th></tr></thead>
                  <tbody>
                    {experiments.advisor.by_intent.map((row) => (
                      <tr key={row.intent}>
                        <td>{titleCase(row.intent)}</td>
                        <td className="right">{row.n}</td>
                        <td className="right">{formatPct(row.routing_accuracy * 100, 1)}</td>
                        <td className="right">{formatPct(row.verification_pass_rate * 100, 1)}</td>
                        <td className="right">{row.median_latency_ms} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {experiments.categorization?.top_confusions?.length > 0 && (
            <Card>
              <SectionTitle title="Where categorization is weakest" description="The categories that most often leak into each other in the held-out synthetic corpus." />
              <div className="confusion-list">
                {experiments.categorization.top_confusions.slice(0, 6).map((row) => (
                  <div key={`${row.actual}-${row.predicted}`}>
                    <span>{row.actual}</span>
                    <ArrowRight size={13} />
                    <span>{row.predicted}</span>
                    <strong>{row.count}</strong>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {experiments.forecasting?.per_persona?.length > 0 && (
            <Card>
              <SectionTitle title="Forecast error by persona" description="Aggregate numbers can hide a small number of very poor forecasts." />
              <div className="persona-table">
                {experiments.forecasting.per_persona.slice(0, 12).map((row) => (
                  <div key={row.persona}>
                    <span>{row.persona}</span>
                    <div><ProgressBar value={Math.min(100, row.error_pct)} max={100} tone={row.error_pct > 25 ? 'red' : row.error_pct > 15 ? 'amber' : 'green'} height={6} /></div>
                    <strong>{formatPct(row.error_pct, 1)}</strong>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      <div className="research-story-grid">
        <Card>
          <SectionTitle title="What is genuinely new" description="Positioning against the two source papers." action={<Quote size={18} />} />
          <div className="claim-list">
            <div>
              <span>01</span>
              <div>
                <strong>Verifiable numeric grounding.</strong>
                <p>The advisor separates planning, computation, explanation and verification. An answer is shown only after its figures are matched against tool outputs; otherwise the deterministic answer is used. This is stricter than prompt instructions alone.</p>
              </div>
            </div>
            <div>
              <span>02</span>
              <div>
                <strong>Just-in-time nudges with measurable decisions.</strong>
                <p>Paper 2 proposed five JIT use cases. Clearpath implements them as deterministic checks and records accept/dismiss outcomes, making effectiveness descriptive rather than assumed.</p>
              </div>
            </div>
            <div>
              <span>03</span>
              <div>
                <strong>An honest evaluation boundary.</strong>
                <p>No user study is claimed. Synthetic personas test reproducibility, model quality and failure modes. A separate pre-registered protocol describes the human study that would be needed next.</p>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <SectionTitle title="Source papers" description="What was kept, and what was not." action={<BookOpenCheck size={18} />} />
          <div className="source-paper">
            <span>PAPER 1</span>
            <strong>{PAPER.one}</strong>
            <p>Kept: the motivation for a conversational advisor, personalisation and decision support. Rejected: unconstrained LLM arithmetic and short-horizon market prediction.</p>
          </div>
          <div className="source-paper">
            <span>PAPER 2 · IHTC 2021</span>
            <strong>{PAPER.two}</strong>
            <p>Kept: the five just-in-time use cases, educational framing and chatbot delivery. Added: deterministic computation, outcome logging, forecasting and a verification layer.</p>
          </div>
          <div className="research-citation">
            <GitBranch size={14} />
            <span>Full references and method in <code>paper/main.tex</code> and <code>docs/EVALUATION_PROTOCOL.md</code>.</span>
          </div>
        </Card>
      </div>

      <Card className="method-card">
        <SectionTitle title="Reproduce every number" description="The harness writes machine-readable results, LaTeX tables and figures into research/results." action={<Terminal size={18} />} />
        <div className="command-grid">
          {COMMANDS.map(([label, command]) => (
            <div key={label}>
              <span>{label}</span>
              <code>{command}</code>
            </div>
          ))}
        </div>
        <Callout tone="green" title="No fabricated engagement" icon={CheckCircle2}>
          <p>
            Synthetic data are labelled as synthetic everywhere. The nudge simulation is a model of behaviour, not evidence
            that real users changed behaviour. Results files include the seed and configuration so a reviewer can rerun them.
          </p>
        </Callout>
      </Card>

      <div className="research-limits">
        <Card className="plain-note-card">
          <CircleAlert size={20} />
          <div>
            <strong>Limitations, stated plainly</strong>
            <p>Synthetic personas cannot substitute for real financial behaviour. The verifier checks numeric traceability, not every semantic claim. The forecast is univariate and ignores income shocks. The nudge simulator encodes assumptions about response probabilities.</p>
          </div>
        </Card>
        <Card className="plain-note-card">
          <FileJson size={20} />
          <div>
            <strong>Artifact availability</strong>
            <p>The system, harness, tests, results and paper source are in the repository. The API summary is available at <code>/api/insights/research-summary</code>; figures are regenerated by <code>research/make_figures.py</code>.</p>
          </div>
        </Card>
      </div>
    </>
  )
}

function ExperimentCard({ icon: Icon, label, title, primary, primaryLabel, secondary, secondaryLabel, baseline, baselineLabel, note, percent, format }) {
  const show = (value) => {
    if (value == null) return '—'
    if (percent) return `${value}%`
    if (format === 'money') return `₹${Number(value).toLocaleString('en-IN')}`
    return value
  }
  return (
    <Card className="experiment-card">
      <div className="experiment-head">
        <span><Icon size={18} /></span>
        <Badge tone="neutral">{label}</Badge>
      </div>
      <h3>{title}</h3>
      <div className="experiment-numbers">
        <div><strong>{show(primary)}</strong><span>{primaryLabel}</span></div>
        <div><strong>{show(secondary)}</strong><span>{secondaryLabel}</span></div>
      </div>
      <div className="experiment-baseline">
        <span>Baseline</span>
        <strong>{show(baseline)}</strong>
        <small>{baselineLabel}</small>
      </div>
      {note && <p>{note}</p>}
    </Card>
  )
}
