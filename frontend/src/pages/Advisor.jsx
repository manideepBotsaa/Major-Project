import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import {
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock3,
  Compass,
  Copy,
  Cpu,
  FileSearch,
  History,
  MessageSquarePlus,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Wrench,
  X,
} from 'lucide-react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { formatDate, formatMoney, titleCase } from '../lib/format'
import { Badge, Card, EmptyState, Spinner } from '../components/UI'

const STARTERS = [
  'Where did my money go this month?',
  'Can I afford a ₹25,000 purchase?',
  'How do I become debt-free faster?',
  'How much can I save in 6 months?',
  'How is my Food & Dining budget doing?',
]

export default function Advisor() {
  const { user } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const query = new URLSearchParams(location.search).get('q') || ''
  const currency = user?.currency || 'INR'

  const [status, setStatus] = useState(null)
  const [sessions, setSessions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState(query)
  const [booting, setBooting] = useState(true)
  const [loadingSession, setLoadingSession] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [showTools, setShowTools] = useState(false)
  const [catalog, setCatalog] = useState(null)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const autoSent = useRef(false)

  const loadSessions = useCallback(async () => {
    const data = await api.advisorSessions()
    setSessions(data.sessions)
    return data.sessions
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([api.advisorStatus(), api.advisorSessions()])
      .then(([statusData, sessionData]) => {
        if (!active) return
        setStatus(statusData)
        setSessions(sessionData.sessions)
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setBooting(false))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  const send = useCallback(
    async (rawQuestion) => {
      const question = String(rawQuestion || '').trim()
      if (!question || sending) return
      setSending(true)
      setError('')
      setInput('')
      const optimistic = { id: `local-${Date.now()}`, role: 'user', content: question, local: true, created_at: new Date().toISOString() }
      setMessages((current) => [...current, optimistic])
      try {
        const result = await api.chat({ message: question, session_id: sessionId || undefined })
        setSessionId(result.session.id)
        setMessages((current) => [...current, result.message])
        await loadSessions()
      } catch (err) {
        setError(err.message)
        setMessages((current) => current.filter((message) => message.id !== optimistic.id))
        setInput(question)
      } finally {
        setSending(false)
      }
    },
    [sessionId, sending, loadSessions],
  )

  useEffect(() => {
    if (booting || autoSent.current || !query) return
    autoSent.current = true
    send(query)
    navigate('/advisor', { replace: true })
  }, [booting, query, send, navigate])

  async function openSession(id) {
    if (id === sessionId) return
    setLoadingSession(true)
    setError('')
    try {
      const data = await api.advisorSession(id)
      setSessionId(id)
      setMessages(data.session.messages || [])
    } catch (err) {
      toast.push(err.message, 'error')
    } finally {
      setLoadingSession(false)
    }
  }

  function newConversation() {
    setSessionId(null)
    setMessages([])
    setInput('')
    setError('')
    textareaRef.current?.focus()
  }

  async function deleteSession(event, session) {
    event.stopPropagation()
    if (!window.confirm(`Delete “${session.title}”?`)) return
    try {
      await api.deleteAdvisorSession(session.id)
      if (session.id === sessionId) newConversation()
      await loadSessions()
      toast.push('Conversation deleted.')
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  async function toggleTools() {
    const next = !showTools
    setShowTools(next)
    if (next && !catalog) {
      try {
        setCatalog(await api.advisorTools())
      } catch (err) {
        toast.push(err.message, 'error')
      }
    }
  }

  async function rate(message, rating) {
    try {
      const data = await api.messageFeedback(message.id, { rating })
      setMessages((current) => current.map((row) => (row.id === message.id ? { ...row, rating: data.message.rating } : row)))
      toast.push(rating > 0 ? 'Thanks — that helps evaluate grounding.' : 'Feedback recorded.', 'info')
    } catch (err) {
      toast.push(err.message, 'error')
    }
  }

  function submit(event) {
    event.preventDefault()
    send(input)
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send(input)
    }
  }

  if (booting) return <div className="centered-loader"><Spinner label="Opening the advisor…" /></div>

  const llm = status?.llm
  const suggestions = status?.suggestions || STARTERS

  return (
    <div className="advisor-page">
      <aside className="advisor-sessions">
        <div className="session-rail-head">
          <span className="eyebrow">CONVERSATIONS</span>
          <button type="button" className="icon-btn" onClick={newConversation} aria-label="New conversation"><MessageSquarePlus size={18} /></button>
        </div>
        <button type="button" className={`new-session ${!sessionId ? 'active' : ''}`} onClick={newConversation}>
          <Plus size={16} /> New conversation
        </button>
        <div className="session-list">
          {sessions.length === 0 ? (
            <p className="session-empty">Your grounded conversations will appear here.</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`session-row ${session.id === sessionId ? 'active' : ''}`}
                onClick={() => openSession(session.id)}
              >
                <History size={15} />
                <span>
                  <strong>{session.title}</strong>
                  <small>{formatDate(session.updated_at, 'short')} · {session.message_count} messages</small>
                </span>
                <span
                  role="button"
                  tabIndex={0}
                  className="session-delete"
                  onClick={(event) => deleteSession(event, session)}
                  onKeyDown={(event) => event.key === 'Enter' && deleteSession(event, session)}
                  aria-label={`Delete ${session.title}`}
                >
                  <Trash2 size={13} />
                </span>
              </button>
            ))
          )}
        </div>
        <div className="session-rail-foot">
          <span className={`mode-pill ${llm?.available ? 'mode-llm' : 'mode-rules'}`}>
            <i /> {llm?.available ? `${llm.provider} · grounded` : 'Deterministic mode'}
          </span>
          <p>
            {llm?.available
              ? 'The language model plans and explains. Every figure still comes from a deterministic tool and is re-checked.'
              : 'No external model is configured. The full advisor runs locally from deterministic tools and curated literacy.'}
          </p>
          <button type="button" className="text-link small" onClick={toggleTools}>
            <Wrench size={13} /> {showTools ? 'Hide' : 'Show'} the tool catalogue
          </button>
        </div>
      </aside>

      <section className="advisor-main">
        <header className="advisor-header">
          <div>
            <span className="eyebrow"><ShieldCheck size={13} /> NUMBERS COMPUTED, THEN VERIFIED</span>
            <h1>Ask about your money.</h1>
            <p>
              Clearpath answers with your own arithmetic. The model may choose a tool and explain it; it is never allowed to invent a number.
            </p>
          </div>
          <div className="advisor-header-meta">
            <span><Cpu size={14} /> {llm?.available ? llm.model : 'clearpath-rules'}</span>
            <span><Clock3 size={14} /> {llm?.available ? 'External model configured' : 'Fully offline'}</span>
          </div>
        </header>

        <div className="chat-surface">
          {messages.length === 0 && !loadingSession ? (
            <div className="chat-empty">
              <span className="chat-empty-icon"><Compass size={26} /></span>
              <span className="eyebrow">START WITH A DECISION, NOT A PRODUCT</span>
              <h2>What would make this month feel clearer?</h2>
              <p>Ask about affordability, a budget, debt, a goal or a financial idea you want explained.</p>
              <div className="starter-grid">
                {suggestions.map((suggestion) => (
                  <button key={suggestion} type="button" onClick={() => send(suggestion)} className="starter-card">
                    <Sparkles size={15} />
                    <span>{suggestion}</span>
                    <ArrowRight size={14} />
                  </button>
                ))}
              </div>
            </div>
          ) : loadingSession ? (
            <div className="centered-loader"><Spinner label="Loading conversation…" /></div>
          ) : (
            <div className="message-list">
              {messages.map((message) =>
                message.role === 'user' ? (
                  <div className="message user-message" key={message.id}>
                    <div className="message-bubble"><p>{message.content}</p></div>
                    <span className="message-avatar user">{user?.name?.slice(0, 1) || 'Y'}</span>
                  </div>
                ) : (
                  <AssistantMessage key={message.id} message={message} currency={currency} onRate={rate} />
                ),
              )}
              {sending && (
                <div className="message assistant-message">
                  <span className="message-avatar bot"><Bot size={17} /></span>
                  <div className="thinking">
                    <span className="thinking-dots"><i /><i /><i /></span>
                    <span>Selecting tools and verifying the arithmetic…</span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {error && <div className="chat-error"><CircleAlert size={16} /> {error}<button type="button" onClick={() => setError('')} aria-label="Dismiss"><X size={14} /></button></div>}

        <form className="chat-composer" onSubmit={submit}>
          <div className="composer-box">
            <textarea
              ref={textareaRef}
              rows={1}
              maxLength={status?.max_question_chars || 1200}
              placeholder="Ask a question about your actual numbers…"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onKeyDown}
              disabled={sending}
            />
            <button type="submit" className="composer-send" disabled={sending || !input.trim()} aria-label="Send message">
              {sending ? <Spinner /> : <Send size={18} />}
            </button>
          </div>
          <div className="composer-foot">
            <span><ShieldCheck size={13} /> Answers use your ledger, budgets and goals. Nothing is sent anywhere unless a provider is configured.</span>
            <span>{input.length}/{status?.max_question_chars || 1200}</span>
          </div>
        </form>

        {showTools && (
          <Card className="tool-drawer">
            <div className="tool-drawer-head">
              <div>
                <span className="eyebrow">THE DETERMINISTIC TOOLBOX</span>
                <h3>{catalog?.tools?.length || 0} tools, one numeric source of truth</h3>
              </div>
              <button type="button" className="icon-btn" onClick={() => setShowTools(false)} aria-label="Close tool catalogue"><X size={17} /></button>
            </div>
            {catalog ? (
              <>
                <div className="tool-grid">
                  {catalog.tools.map((tool) => (
                    <div className="tool-row" key={tool.name}>
                      <Wrench size={14} />
                      <div><strong>{titleCase(tool.name)}</strong><p>{tool.description}</p></div>
                    </div>
                  ))}
                </div>
                <div className="tool-principles">
                  {catalog.principles.map((principle) => <span key={principle}>{principle}</span>)}
                </div>
              </>
            ) : (
              <div className="centered-loader"><Spinner label="Loading tools…" /></div>
            )}
          </Card>
        )}
      </section>
    </div>
  )
}

function AssistantMessage({ message, currency, onRate }) {
  const [showTrace, setShowTrace] = useState(false)
  const [showCitations, setShowCitations] = useState(false)
  const verification = message.verification || {}
  const passed = verification.passed !== false
  const trace = message.tool_trace || []
  const citations = message.citations || []
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* Clipboard may be unavailable over plain HTTP. */
    }
  }

  return (
    <div className="message assistant-message">
      <span className="message-avatar bot"><Bot size={17} /></span>
      <div className="message-column">
        <div className="assistant-meta">
          <strong>Clearpath</strong>
          <Badge tone={passed ? 'green' : 'red'} dot>{passed ? 'Numbers verified' : 'Verification failed'}</Badge>
          <span>{verification.mode === 'llm' ? 'LLM explanation' : 'Grounded rules'}</span>
          {message.latency_ms != null && <span>{message.latency_ms} ms</span>}
        </div>
        <div className="message-bubble assistant-bubble">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        <div className="message-tools">
          {trace.length > 0 && (
            <button type="button" onClick={() => setShowTrace((value) => !value)} className={showTrace ? 'active' : ''}>
              <Wrench size={13} /> {trace.length} tool{trace.length === 1 ? '' : 's'}
              <ChevronDown size={13} className={showTrace ? 'rotated' : ''} />
            </button>
          )}
          {citations.length > 0 && (
            <button type="button" onClick={() => setShowCitations((value) => !value)} className={showCitations ? 'active' : ''}>
              <BookOpen size={13} /> {citations.length} citation{citations.length === 1 ? '' : 's'}
              <ChevronDown size={13} className={showCitations ? 'rotated' : ''} />
            </button>
          )}
          <button type="button" onClick={copy}><Copy size={13} /> {copied ? 'Copied' : 'Copy'}</button>
          <span className="message-feedback">
            <button type="button" className={message.rating === 1 ? 'active' : ''} onClick={() => onRate(message, 1)} aria-label="Helpful"><ThumbsUp size={13} /></button>
            <button type="button" className={message.rating === -1 ? 'active' : ''} onClick={() => onRate(message, -1)} aria-label="Not helpful"><ThumbsDown size={13} /></button>
          </span>
        </div>

        {showTrace && (
          <div className="trace-panel">
            {trace.map((tool, index) => (
              <div className="trace-row" key={`${tool.tool}-${index}`}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{tool.label || titleCase(tool.tool)}</strong>
                  <p>{tool.headline}</p>
                  {tool.display && (
                    <ul>{tool.display.slice(0, 5).map((line) => <li key={line}>{line}</li>)}</ul>
                  )}
                  <small>
                    Deterministic tool output · {tool.tool}
                    {tool.error ? ` · ${tool.error}` : ''}
                  </small>
                </div>
              </div>
            ))}
            <div className="verification-row">
              <CheckCircle2 size={14} />
              <span>
                {verification.checked ?? 0} numeric claims checked against {verification.allowed_count ?? 0} computed values.
                {verification.attempts > 0 ? ` ${verification.attempts} model attempt(s).` : ' No model arithmetic involved.'}
              </span>
            </div>
          </div>
        )}

        {showCitations && (
          <div className="citation-panel">
            {citations.map((citation) => (
              <a key={citation.id} href={`/learn/${citation.module_slug}`} className="citation-card">
                <span>{citation.id}</span>
                <div>
                  <strong>{citation.title}</strong>
                  <small>{citation.heading}</small>
                  <p>{citation.text}</p>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
