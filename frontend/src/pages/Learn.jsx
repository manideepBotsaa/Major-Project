import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import {
  ArrowLeft,
  ArrowRight,
  BookMarked,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  GraduationCap,
  Search,
  Sparkles,
  X,
} from 'lucide-react'
import { api } from '../api'
import { useToast } from '../context/ToastContext'
import { formatPct, titleCase } from '../lib/format'
import { Badge, Card, EmptyState, PageHeader, ProgressBar, SectionTitle, Spinner } from '../components/UI'

const LEVEL_TONE = { beginner: 'green', intermediate: 'sand', advanced: 'blue' }

export default function Learn() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [progress, setProgress] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [level, setLevel] = useState('all')
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)

  const load = useCallback(async () => {
    setError('')
    try {
      const [modules, stats] = await Promise.all([api.literacyModules(), api.literacyProgress()])
      setData(modules)
      setProgress(stats)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const term = search.trim()
    if (term.length < 3) {
      setSearchResults(null)
      return undefined
    }
    const timer = window.setTimeout(() => {
      setSearching(true)
      api
        .searchKnowledge(term)
        .then((result) => setSearchResults(result.results))
        .catch(() => setSearchResults([]))
        .finally(() => setSearching(false))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [search])

  const modules = useMemo(() => {
    if (!data) return []
    return data.modules.filter((module) => (level === 'all' || module.level === level) && (!search.trim() || module.title.toLowerCase().includes(search.toLowerCase()) || module.summary.toLowerCase().includes(search.toLowerCase())))
  }, [data, level, search])

  if (slug) return <ModuleDetail slug={slug} onBack={() => navigate('/learn')} onProgress={load} />

  return (
    <>
      <PageHeader
        eyebrow="EDUCATION AT THE MOMENT IT MATTERS"
        title="Financial literacy"
        description="Short, cited modules that explain the arithmetic behind your decisions. No product recommendations, no hype."
        actions={
          <Link to="/advisor" className="btn btn-primary"><Sparkles size={16} /> Ask for an explanation</Link>
        }
      />

      {loading ? (
        <div className="centered-loader"><Spinner label="Opening the curriculum…" /></div>
      ) : error ? (
        <Card><EmptyState icon={GraduationCap} title="Could not load the curriculum">{error}</EmptyState></Card>
      ) : (
        <>
          <section className="learn-hero">
            <div>
              <span className="eyebrow light">YOUR LEARNING PATH</span>
              <h2>{progress?.completed || 0} of {progress?.total || data.total} modules completed</h2>
              <p>Each module is short enough to finish at a decision point. Quizzes are scored, but scores are for you, not a leaderboard.</p>
              <ProgressBar value={progress?.completion_pct || 0} height={9} tone="sand" />
              <div className="learn-hero-meta">
                <span>{formatPct(progress?.completion_pct || 0, 0)} complete</span>
                <span>{progress?.attempts || 0} quiz attempts</span>
                <span>Best score: {progress?.best_score || 0}</span>
              </div>
            </div>
            <div className="learn-levels">
              {Object.entries(progress?.by_level || data.levels || {}).map(([name, value]) => (
                <div key={name}>
                  <span>{titleCase(name)}</span>
                  <strong>{value.completed ?? value}/{value.total ?? data.levels[name]}</strong>
                </div>
              ))}
            </div>
          </section>

          <div className="learn-toolbar">
            <label className="search-box">
              <Search size={17} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search the curriculum or ask a concept" />
              {search && <button type="button" onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>}
            </label>
            <div className="filter-pills">
              {['all', 'beginner', 'intermediate', 'advanced'].map((item) => (
                <button key={item} type="button" className={level === item ? 'active' : ''} onClick={() => setLevel(item)}>
                  {titleCase(item)}
                </button>
              ))}
            </div>
          </div>

          {searchResults && search.trim().length >= 3 && (
            <Card className="knowledge-search">
              <SectionTitle
                title="Knowledge search"
                description={`Passages relevant to “${search}”. The advisor cites these same chunks.`}
                action={searching ? <Spinner /> : <Badge tone="neutral">{searchResults.length} results</Badge>}
              />
              {searchResults.length ? (
                <div className="knowledge-results">
                  {searchResults.map((result) => (
                    <Link key={result.id} to={`/learn/${result.module_slug}`} className="knowledge-result">
                      <span>{result.score ? result.score.toFixed(2) : '—'}</span>
                      <div>
                        <strong>{result.title}</strong>
                        <small>{result.heading}</small>
                        <p>{result.text}</p>
                      </div>
                      <ChevronRight size={15} />
                    </Link>
                  ))}
                </div>
              ) : (
                <EmptyState icon={BookOpen} title="No matching passage">Try a shorter phrase like “emergency fund” or “EMI”.</EmptyState>
              )}
            </Card>
          )}

          <div className="module-grid">
            {modules.map((module, index) => (
              <Link to={`/learn/${module.slug}`} key={module.slug} className="module-card">
                <div className="module-top">
                  <span className="module-number">{String(index + 1).padStart(2, '0')}</span>
                  <Badge tone={LEVEL_TONE[module.level] || 'neutral'}>{titleCase(module.level)}</Badge>
                </div>
                <h2>{module.title}</h2>
                <p>{module.summary}</p>
                <div className="module-tags">
                  {(module.tags || []).slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
                </div>
                <div className="module-foot">
                  <span><Clock3 size={13} /> {module.minutes} min</span>
                  <span><BookMarked size={13} /> {module.quiz_count} questions</span>
                  {module.progress.status === 'completed' ? (
                    <Badge tone="green"><Check size={11} /> {module.progress.best_score}/{module.quiz_count}</Badge>
                  ) : (
                    <span className="module-start">Start <ArrowRight size={13} /></span>
                  )}
                </div>
              </Link>
            ))}
          </div>

          {modules.length === 0 && (
            <Card><EmptyState icon={BookOpen} title="No modules match this filter">{search ? 'Clear the search or choose another level.' : 'Choose a different level.'}</EmptyState></Card>
          )}

          <Card className="plain-note-card learn-note">
            <GraduationCap size={20} />
            <div>
              <strong>Why just-in-time education?</strong>
              <p>
                A concept is easier to use when it arrives beside the decision it explains. Every advisor answer links back to
                the same curated passages used here, so learning and advice cannot drift apart.
              </p>
            </div>
          </Card>
        </>
      )}
    </>
  )
}

function ModuleDetail({ slug, onBack, onProgress }) {
  const toast = useToast()
  const [module, setModule] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api
      .literacyModule(slug)
      .then((data) => {
        if (!active) return
        setModule(data.module)
        setAnswers(new Array(data.module.quiz?.length || 0).fill(null))
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [slug])

  async function submitQuiz(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const data = await api.submitQuiz(slug, answers)
      setResult(data)
      toast.push(data.passed ? `Passed with ${data.score}/${data.total}. ${data.points_awarded} points added.` : `${data.score}/${data.total}. Review the explanations and try again.`, data.passed ? 'success' : 'info')
      await onProgress()
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="centered-loader"><Spinner label="Opening the module…" /></div>
  if (error || !module) return <Card><EmptyState icon={BookOpen} title="Module not found">{error}<button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>Back to curriculum</button></EmptyState></Card>

  const quiz = module.quiz || []
  const allAnswered = answers.every((answer) => answer !== null)

  return (
    <>
      <button type="button" className="back-link" onClick={onBack}><ArrowLeft size={15} /> All modules</button>
      <article className="module-reader">
        <header className="module-reader-head">
          <span className="eyebrow">{module.level.toUpperCase()} · {module.minutes} MIN READ</span>
          <h1>{module.title}</h1>
          <p>{module.summary}</p>
          <div className="module-reader-meta">
            <Badge tone={LEVEL_TONE[module.level] || 'neutral'}>{titleCase(module.level)}</Badge>
            {module.progress.status === 'completed' && <Badge tone="green" dot>Completed · best {module.progress.best_score}/{quiz.length}</Badge>}
            <span>{quiz.length} quiz questions</span>
          </div>
        </header>
        <div className="reader-layout">
          <div className="prose">
            <ReactMarkdown>{module.content || ''}</ReactMarkdown>
          </div>
          <aside className="reader-aside">
            <Card>
              <span className="eyebrow">IN THIS MODULE</span>
              <ul>
                {(module.tags || []).map((tag) => <li key={tag}>{tag}</li>)}
              </ul>
              <div className="reader-aside-rule" />
              <p>Read the arithmetic slowly. The quiz checks understanding, not memorisation.</p>
            </Card>
            <Card className="reader-ask">
              <Sparkles size={18} />
              <strong>Apply it to your own numbers</strong>
              <p>Ask the advisor a question and it will cite the relevant passage here.</p>
              <Link to={`/advisor?q=${encodeURIComponent(`Explain ${module.title} using my own numbers.`)}`} className="text-link">Ask Clearpath <ArrowRight size={13} /></Link>
            </Card>
          </aside>
        </div>
      </article>

      {quiz.length > 0 && (
        <Card className="quiz-card">
          <SectionTitle
            title="Check your understanding"
            description="A score of 60% or more marks the module complete. Explanations appear after submission."
            action={module.progress.attempts > 0 ? <Badge tone="neutral">{module.progress.attempts} prior attempts</Badge> : null}
          />
          <form onSubmit={submitQuiz} className="quiz-list">
            {quiz.map((question, questionIndex) => {
              const questionResult = result?.results?.[questionIndex]
              return (
                <fieldset key={question.id || questionIndex} className={`quiz-question ${questionResult ? (questionResult.correct ? 'correct' : 'incorrect') : ''}`}>
                  <legend><span>{String(questionIndex + 1).padStart(2, '0')}</span>{question.prompt}</legend>
                  <div className="quiz-options">
                    {question.options.map((option, optionIndex) => {
                      const selected = answers[questionIndex] === optionIndex
                      const isCorrect = questionResult && questionResult.correct_index === optionIndex
                      const isWrongPick = questionResult && selected && !questionResult.correct
                      return (
                        <label key={option} className={`quiz-option ${selected ? 'selected' : ''} ${isCorrect ? 'answer-correct' : ''} ${isWrongPick ? 'answer-wrong' : ''}`}>
                          <input
                            type="radio"
                            name={`question-${questionIndex}`}
                            checked={selected}
                            disabled={Boolean(result)}
                            onChange={() => setAnswers((current) => current.map((value, index) => (index === questionIndex ? optionIndex : value)))}
                          />
                          <span className="quiz-radio">{isCorrect ? <CheckCircle2 size={15} /> : String.fromCharCode(65 + optionIndex)}</span>
                          <span>{option}</span>
                        </label>
                      )
                    })}
                  </div>
                  {questionResult && (
                    <p className={`quiz-explanation ${questionResult.correct ? 'good' : 'bad'}`}>
                      {questionResult.correct ? <CheckCircle2 size={14} /> : <X size={14} />}
                      {questionResult.explanation}
                    </p>
                  )}
                </fieldset>
              )
            })}
            <div className="quiz-actions">
              {result ? (
                <>
                  <Badge tone={result.passed ? 'green' : 'amber'}>{result.score}/{result.total} · {formatPct(result.percent, 0)}</Badge>
                  <button type="button" className="btn btn-secondary" onClick={() => { setResult(null); setAnswers(new Array(quiz.length).fill(null)) }}>Try again</button>
                  <button type="button" className="btn btn-primary" onClick={onBack}>Back to curriculum <ArrowRight size={14} /></button>
                </>
              ) : (
                <>
                  <span>{answers.filter((value) => value !== null).length} of {quiz.length} answered</span>
                  <button type="submit" className="btn btn-primary" disabled={!allAnswered || busy}>{busy ? <Spinner label="Scoring…" /> : 'Submit answers'}</button>
                </>
              )}
            </div>
          </form>
        </Card>
      )}
    </>
  )
}
