import { useCallback, useEffect, useState } from 'react'
import {
  ArrowRight,
  Award,
  BellRing,
  CheckCircle2,
  Flame,
  Info,
  Lock,
  Medal,
  Sparkles,
  Star,
  Target,
  TrendingUp,
  Trophy,
  Zap,
} from 'lucide-react'
import { api } from '../api'
import { useToast } from '../context/ToastContext'
import { formatDate, titleCase } from '../lib/format'
import { Badge, Card, EmptyState, PageHeader, ProgressBar, SectionTitle, Spinner, StatCard } from '../components/UI'
import NudgeCard from '../components/NudgeCard'

const RULE_LABELS = {
  budget_over: 'Budget overrun',
  budget_pace: 'Budget pace',
  low_savings: 'Savings rate',
  emergency_low: 'Emergency runway',
  high_interest_debt: 'High-interest debt',
  goal_at_risk: 'Goal behind plan',
  subscription_creep: 'Subscription creep',
  unusual_spend: 'Unusual spend',
  payday_save: 'Payday saving',
  forecast_overspend: 'Forecast overspend',
  streak_reinforce: 'Tracking streak',
}

export default function Momentum() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await api.nudges())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <div className="centered-loader"><Spinner label="Preparing your momentum…" /></div>
  if (error && !data) return <Card><EmptyState icon={Zap} title="Could not load momentum">{error}</EmptyState></Card>
  if (!data) return null

  const nudges = data.nudges || []
  const game = data.gamification || {}
  const effect = data.effectiveness || {}
  const nextLevelPoints = Math.min(200, game.points % 200)
  const badges = game.badges || []
  const available = game.badges_available || []

  return (
    <>
      <PageHeader
        eyebrow="SMALL MOMENTS, MEASURED"
        title="Momentum"
        description="Just-in-time nudges with their arithmetic attached, plus a private record of what you acted on."
        actions={<a href="/dashboard" className="btn btn-secondary" onClick={(event) => { event.preventDefault(); window.location.href = '/' }}>Back to overview</a>}
      />

      <section className="momentum-hero">
        <div className="level-badge">
          <span>LEVEL</span>
          <strong>{game.level || 1}</strong>
        </div>
        <div className="momentum-copy">
          <span className="eyebrow light">CONSISTENCY, NOT PERFECTION</span>
          <h2>{game.points || 0} points earned, {game.streak || 0}-day streak.</h2>
          <p>Points are a record of small actions: logging a transaction, funding a goal, finishing a module, acting on a nudge.</p>
          <ProgressBar value={nextLevelPoints} max={200} tone="sand" height={8} />
          <small>{game.points_to_next || 200} points to level {(game.level || 1) + 1}</small>
        </div>
        <div className="momentum-stats">
          <div><Flame size={16} /><span>Current streak</span><strong>{game.streak || 0} days</strong></div>
          <div><Trophy size={16} /><span>Longest streak</span><strong>{game.longest_streak || 0} days</strong></div>
          <div><Medal size={16} /><span>Badges</span><strong>{badges.length}</strong></div>
        </div>
      </section>

      <div className="stat-grid four">
        <StatCard label="Transactions logged" value={game.metrics?.transactions ?? 0} icon={CheckCircle2} note="Each entry improves every calculation" />
        <StatCard label="Nudges accepted" value={game.metrics?.nudges_accepted ?? 0} icon={BellRing} note="Actions, not just clicks" tone="sand" />
        <StatCard label="Modules completed" value={game.metrics?.modules_completed ?? 0} icon={BookIcon} note="Financial literacy progress" tone="blue" />
        <StatCard label="Budget adherence" value={`${game.metrics?.budget_adherence ?? 0}%`} icon={Target} note="Categories on or near pace" tone="green" />
      </div>

      <section className="section-block">
        <SectionTitle
          title="Active nudges"
          description="Generated from this month's budgets, goals, debts and forecasts. Dismissing one is a valid decision."
          action={<Badge tone={nudges.length ? 'amber' : 'green'} dot>{nudges.length} active</Badge>}
        />
        {nudges.length ? (
          <div className="nudge-grid">
            {nudges.map((nudge) => <NudgeCard key={nudge.id} nudge={nudge} onChanged={load} />)}
          </div>
        ) : (
          <Card>
            <EmptyState icon={CheckCircle2} title="No urgent nudges">
              Nothing in your current arithmetic calls for intervention. That is a result worth protecting.
            </EmptyState>
          </Card>
        )}
      </section>

      <div className="dashboard-grid">
        <Card>
          <SectionTitle title="Badges" description="Earned from real activity in this workspace." action={<Award size={18} />} />
          {badges.length ? (
            <div className="badge-grid">
              {badges.map((badge) => (
                <div className="badge-card earned" key={badge.id}>
                  <span><Star size={17} /></span>
                  <div><strong>{badge.label}</strong><small>{badge.description}</small></div>
                  <CheckCircle2 size={15} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={Award} title="No badges yet">Log your first transaction to start the record.</EmptyState>
          )}
          {available.length > 0 && (
            <>
              <div className="subhead"><span>Still to earn</span><i /></div>
              <div className="badge-grid muted">
                {available.slice(0, 6).map((badge) => (
                  <div className="badge-card" key={badge.id}>
                    <span><Lock size={15} /></span>
                    <div><strong>{badge.label}</strong><small>{badge.description}</small></div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card>
          <SectionTitle title="Nudge effectiveness" description="Only decisions you have made. No fabricated engagement." action={<TrendingUp size={18} />} />
          {effect.total_decided ? (
            <>
              <div className="effectiveness-summary">
                <div><span>Decided</span><strong>{effect.total_decided}</strong></div>
                <div><span>Accepted</span><strong className="positive">{effect.accepted}</strong></div>
                <div><span>Acceptance</span><strong>{effect.acceptance_rate}%</strong></div>
              </div>
              <div className="rule-list">
                {(effect.by_rule || []).map((rule) => (
                  <div key={rule.rule_id} className="rule-row">
                    <span>{RULE_LABELS[rule.rule_id] || titleCase(rule.rule_id)}</span>
                    <div className="rule-track"><i style={{ width: `${rule.acceptance_rate ?? 0}%` }} /></div>
                    <strong>{rule.acceptance_rate == null ? '—' : `${rule.acceptance_rate}%`}</strong>
                    <small>{rule.accepted} / {rule.decisions ?? rule.accepted + rule.dismissed}</small>
                  </div>
                ))}
              </div>
              <p className="model-note">A high acceptance rate is not automatically good. It may mean the nudges are too easy to accept, or that the user is over-trusting them.</p>
            </>
          ) : (
            <EmptyState icon={Info} title="No nudge decisions yet">Accept or dismiss a nudge and the effectiveness record starts here.</EmptyState>
          )}
        </Card>
      </div>

      <div className="dashboard-grid">
        <Card>
          <SectionTitle title="Recent activity" description="The last few actions that moved your record." />
          {(game.recent_activity || []).length ? (
            <div className="activity-list">
              {game.recent_activity.map((event) => (
                <div key={event.id} className="activity-row">
                  <span className="activity-icon"><Zap size={14} /></span>
                  <div><strong>{event.description || titleCase(event.type)}</strong><small>{formatDate(event.date)}</small></div>
                  <Badge tone="neutral">+{event.points} pts</Badge>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon={Zap} title="No activity recorded">Points appear after your first tracked action.</EmptyState>
          )}
        </Card>
        <Card className="plain-note-card">
          <Sparkles size={20} />
          <div>
            <strong>How the nudge engine decides</strong>
            <p>
              Rules watch budget pace, savings rate, emergency runway, high-interest debt, goal feasibility, subscription
              creep, anomalies and payday timing. The highest-priority four appear. Every nudge carries the numbers that
              triggered it.
            </p>
          </div>
        </Card>
      </div>
    </>
  )
}

function BookIcon() {
  return <span className="inline-book">▤</span>
}
